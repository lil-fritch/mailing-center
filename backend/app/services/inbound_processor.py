from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.logger import get_logger
from app.core.settings import settings
from app.integrations.ai.assistant_client import OpenAIAssistantClient
from app.schemas.inbound import InboundMessage, PendingReply, SentReply
from app.services.inbound_imap import poller
from app.services.inbound_scheduler import scheduler
from app.services.email_campaign_service import EmailCampaignService
from app.services.recipient_registry import is_allowed
from app.database.crud import mark_email_as_replied, mark_email_as_bounced, mark_email_as_bounced_fallback, create_email_thread, EmailThreadCRUD, CampaignCRUD
from typing import Optional
from app.database.models import MessageType
from app.database.connection import SessionLocal
from app.utils.email_parser import clean_reply_body, decode_email_header


class InboundProcessor:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        # Assistant for answers (separate ID)
        self.answer_ai = OpenAIAssistantClient(assistant_id=settings.openai_assistant_id_answer_generator)
        self._running = False

    def _is_bounce_email(self, inbound: InboundMessage) -> bool:
        """Визначає чи є лист bounce (повернення через недійсну адресу)"""
        # Перевіряємо відправника - bounce листи зазвичай приходять від mailer-daemon, postmaster, noreply
        bounce_senders = [
            'mailer-daemon',
            'postmaster', 
            'noreply',
            'no-reply',
            'bounce',
            'mailer',
            'daemon',
            'mail-delivery',
            'delivery',
            'system',
            'automated',
            'noreply',
            'no-reply'
        ]
        
        from_email_lower = inbound.from_email.lower()
        for sender in bounce_senders:
            if sender in from_email_lower:
                return True
        
        # Перевіряємо тему - bounce листи часто мають специфічні теми
        subject_lower = inbound.subject.lower()
        bounce_subject_keywords = [
            'undelivered',
            'delivery failed',
            'delivery status notification',
            'returned mail',
            'mail delivery failure',
            'message not delivered',
            'bounce',
            'undeliverable',
            'recipient address rejected',
            'user unknown',
            'mailbox unavailable',
            'address not found',
            'no such user',
            'invalid recipient',
            'recipient not found',
            'delivery status notification (failure)',
            'failure notice',
            'mail delivery system',
            'returned message',
            'delivery error',
            'mail system error',
            'permanent failure',
            'temporary failure'
        ]
        
        for keyword in bounce_subject_keywords:
            if keyword in subject_lower:
                return True
        
        # Перевіряємо тіло листа на bounce індикатори
        body_lower = inbound.body.lower()
        bounce_body_keywords = [
            'delivery has failed',
            'recipient address rejected',
            'user unknown',
            'mailbox unavailable',
            'no such user',
            'invalid recipient',
            'recipient not found',
            'address not found',
            'mailbox does not exist',
            'user does not exist',
            'recipient does not exist',
            'delivery failure',
            'message undeliverable',
            'permanent failure',
            'temporary failure'
        ]
        
        for keyword in bounce_body_keywords:
            if keyword in body_lower:
                return True
        
        return False

    def _extract_failed_recipient(self, bounce_body: str) -> Optional[str]:
        """Витягти недійсну email адресу з bounce листа"""
        import re
        
        # Common patterns for failed recipient in bounce messages
        patterns = [
            r'<([^>]+@[^>]+)>',  # <email@domain.com>
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # email@domain.com
            r'To:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # To: email@domain.com
            r'Recipient:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # Recipient: email@domain.com
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, bounce_body, re.IGNORECASE)
            if matches:
                # Return the first valid email found
                for match in matches:
                    if '@' in match and '.' in match.split('@')[-1]:
                        return match.strip('<>')
        
        return None

    async def run_polling_once(self) -> int:
        """Poll IMAP once and enqueue any pending replies. Returns count enqueued."""
        enqueued = 0
        async for inbound in poller.poll_new_messages_async():
            # Check if this is a bounce email FIRST (before allowed_recipients check)
            if self._is_bounce_email(inbound):
                self.logger.info(
                    "Inbound: detected bounce email from %s to %s (subject: %s)",
                    inbound.from_email,
                    inbound.account_email,
                    inbound.subject
                )
                
                # Mark the original sent email as bounced in database
                db = SessionLocal()
                try:
                    # Try to extract the failed recipient from bounce body
                    failed_recipient = self._extract_failed_recipient(inbound.body)
                    
                    if failed_recipient:
                        # Mark specific email as bounced
                        updated_emails = mark_email_as_bounced(
                            db=db,
                            to_email=failed_recipient,  # The email that failed
                            bounce_subject=inbound.subject,
                            bounce_body=inbound.body,
                        )
                    else:
                        # Fallback: mark all recent emails from this account as bounced
                        # This is less precise but better than nothing
                        updated_emails = mark_email_as_bounced_fallback(
                            db=db,
                            from_email=inbound.account_email,  # Our account that received the bounce
                            bounce_subject=inbound.subject,
                            bounce_body=inbound.body,
                        )
                    if updated_emails:
                        self.logger.info(
                            "Inbound: marked %d email(s) as bounced (from=%s, to=%s)",
                            len(updated_emails),
                            inbound.from_email,
                            inbound.account_email,
                        )
                        # Update campaign statistics
                        for email in updated_emails:
                            campaign_crud = CampaignCRUD(db)
                            campaign_crud.update_statistics(email.campaign_id)
                    else:
                        self.logger.warning(
                            "Inbound: no matching sent emails found for bounce (from=%s, to=%s)",
                            inbound.from_email,
                            inbound.account_email,
                        )
                except Exception as exc:
                    self.logger.error("Inbound: failed to mark email as bounced: %s", str(exc))
                finally:
                    db.close()
                
                # Don't process bounce emails as replies
                continue
            
            # For regular emails, check if sender is allowed
            if not is_allowed(inbound.from_email):
                self.logger.info(
                    "Inbound: sender %s is not allowed; skipping", inbound.from_email
                )
                continue
            
            # Mark the original sent email as replied in database
            # Можливо кілька кампаній з одним email, тому обробляємо всі
            campaigns_to_process = []
            
            db = SessionLocal()
            try:
                # Decode the subject from MIME encoded-word format
                decoded_subject = decode_email_header(inbound.subject)
                
                # Try to find thread using headers first (most accurate)
                thread_crud = EmailThreadCRUD(db)
                found_threads = []
                
                # Спробувати знайти thread через in_reply_to (найточніший метод)
                if inbound.in_reply_to:
                    found_thread = thread_crud.find_thread_by_message_id(inbound.in_reply_to)
                    if found_thread:
                        found_threads.append(found_thread)
                        self.logger.info("Inbound: found thread via in_reply_to header: thread_id=%s, campaign_id=%s, message_id=%s", 
                                       found_thread.thread_id, found_thread.campaign_id, inbound.in_reply_to)
                    else:
                        self.logger.warning("Inbound: in_reply_to=%s not found in email_threads", inbound.in_reply_to)
                
                # Якщо не знайдено через in_reply_to, спробувати через references
                if not found_threads and inbound.references:
                    # References може містити кілька message_id, спробуємо всі
                    ref_ids = [ref.strip().strip("<>") for ref in inbound.references.split() if ref.strip()]
                    for ref_id in ref_ids:
                        found_thread = thread_crud.find_thread_by_message_id(ref_id)
                        if found_thread and found_thread not in found_threads:
                            found_threads.append(found_thread)
                            self.logger.info("Inbound: found thread via references header: thread_id=%s, campaign_id=%s, ref_id=%s", 
                                           found_thread.thread_id, found_thread.campaign_id, ref_id)
                
                # Fallback: якщо не знайдено через headers, спробувати знайти thread за email адресами та subject
                # Це важливо для випадків, коли message_id не зберігся або не збігається
                if not found_threads:
                    # Знайти всі threads для цієї пари email адрес
                    from app.database.models import MessageType
                    all_thread_ids = thread_crud.get_threads_by_email(inbound.from_email, inbound.account_email)
                    
                    self.logger.info("Inbound: fallback search - found %d threads for email pair (from=%s, to=%s)", 
                                   len(all_thread_ids), inbound.from_email, inbound.account_email)
                    
                    # Для кожного thread перевірити, чи відповідає subject
                    import re
                    cleaned_subject = re.sub(r'^(Re:|RE:|Fwd:|FWD:|Fw:|FW:)\s*', '', decoded_subject, flags=re.IGNORECASE).strip()
                    
                    for thread_id in all_thread_ids:
                        thread_messages = thread_crud.get_by_thread_id(thread_id)
                        if not thread_messages:
                            continue
                        
                        # Знайти перше відправлене повідомлення в thread (оригінальний лист)
                        sent_messages = [msg for msg in thread_messages if msg.message_type == MessageType.sent]
                        if sent_messages:
                            first_sent = sent_messages[0]
                            if first_sent.subject:
                                first_subject_clean = first_sent.subject.strip()
                                # Перевірити чи cleaned_subject відповідає first_subject_clean
                                if (cleaned_subject.lower() == first_subject_clean.lower() or 
                                    cleaned_subject.lower().startswith(first_subject_clean.lower()) or
                                    first_subject_clean.lower() in cleaned_subject.lower()):
                                    # Знайти thread об'єкт для отримання campaign_id
                                    thread_obj = thread_messages[0]  # Будь-яке повідомлення з thread
                                    found_threads.append(thread_obj)
                                    self.logger.info("Inbound: found thread via subject fallback: thread_id=%s, campaign_id=%s, subject_match=%s", 
                                                   thread_id, thread_obj.campaign_id, first_subject_clean)
                                    break
                
                # Використовувати headers для точного зв'язування
                updated_emails = mark_email_as_replied(
                    db=db,
                    to_email=inbound.account_email,  # Our account that received the reply
                    from_email=inbound.from_email,  # Who sent the reply
                    reply_subject=decoded_subject,
                    reply_body=inbound.body,
                    in_reply_to=inbound.in_reply_to,
                    message_id=inbound.message_id,
                )
                
                # Зібрати унікальні пари (campaign_id, thread_id) для обробки
                # Важливо: обробляємо тільки ОДНУ кампанію, яка точно відповідає відповіді
                processed_pairs = set()
                
                # Пріоритет 1: знайдені через headers (найточніші)
                # Якщо знайдено через headers (in_reply_to/references), це означає що це точно правильний thread
                # Обробити всі знайдені threads через headers
                for found_thread in found_threads:
                    pair = (found_thread.campaign_id, found_thread.thread_id)
                    if pair not in processed_pairs:
                        campaigns_to_process.append({
                            'campaign_id': found_thread.campaign_id,
                            'thread_id': found_thread.thread_id,
                            'source': 'headers'
                        })
                        processed_pairs.add(pair)
                        self.logger.info("Inbound: using thread from headers: campaign_id=%s, thread_id=%s", 
                                       found_thread.campaign_id, found_thread.thread_id)
                    
                    # Зберегти відповідь в thread (навіть якщо thread вже в обробці)
                    # Це важливо для продовження листування
                    thread_messages = thread_crud.get_by_thread_id(found_thread.thread_id)
                    last_message = thread_messages[-1] if thread_messages else None
                    in_reply_to_value = last_message.message_id if last_message and last_message.message_id else inbound.in_reply_to
                    
                    # Перевірити, чи вже є це повідомлення
                    existing = thread_crud.get_by_thread_id(found_thread.thread_id)
                    already_exists = any(
                        msg.message_id == inbound.message_id 
                        for msg in existing 
                        if msg.message_id and inbound.message_id
                    )
                    
                    if not already_exists:
                        thread_data = {
                            "id": str(uuid.uuid4()),
                            "thread_id": found_thread.thread_id,
                            "campaign_id": found_thread.campaign_id,
                            "sent_email_id": None,
                            "message_type": MessageType.received,
                            "from_email": inbound.from_email,
                            "to_email": inbound.account_email,
                            "subject": decoded_subject,
                            "body": inbound.body,
                            "message_id": inbound.message_id,
                            "in_reply_to": in_reply_to_value,
                            "references": inbound.references,
                        }
                        try:
                            create_email_thread(db, thread_data)
                            self.logger.info("Inbound: saved reply to thread via headers (priority 1): %s", found_thread.thread_id)
                            
                            # Оновити статистику кампанії
                            campaign_crud = CampaignCRUD(db)
                            campaign_crud.update_statistics(found_thread.campaign_id)
                        except Exception as e:
                            self.logger.error("Inbound: failed to save reply to thread via headers: %s", str(e))
                    else:
                        self.logger.info("Inbound: reply already exists in thread via headers: %s, skipping", found_thread.thread_id)
                
                # Пріоритет 2: знайдені через mark_as_replied (які вже врахували subject)
                if updated_emails:
                    self.logger.info(
                        "Inbound: marked %d email(s) as replied (from=%s, to=%s)",
                        len(updated_emails),
                        inbound.from_email,
                        inbound.account_email,
                    )
                    
                    # Додати тільки перший email (mark_as_replied тепер повертає тільки один правильний)
                    if updated_emails:
                        email = updated_emails[0]
                        if email.thread_id and email.campaign_id:
                            pair = (email.campaign_id, email.thread_id)
                            # Якщо вже є через headers, не додавати дублікат
                            if pair not in processed_pairs:
                                campaigns_to_process.append({
                                    'campaign_id': email.campaign_id,
                                    'thread_id': email.thread_id,
                                    'source': 'sent_email'
                                })
                                processed_pairs.add(pair)
                                self.logger.info("Inbound: using thread from sent_email: campaign_id=%s, thread_id=%s", 
                                               email.campaign_id, email.thread_id)
                    
                    # Зберегти відповідь в thread (тільки для правильної кампанії)
                    if updated_emails:
                        email = updated_emails[0]  # Тільки перший (правильний)
                        thread_id_to_use = email.thread_id
                        campaign_id_to_use = email.campaign_id
                        
                        if thread_id_to_use and campaign_id_to_use:
                            # Знайти останнє повідомлення в thread для встановлення in_reply_to
                            thread_messages = thread_crud.get_by_thread_id(thread_id_to_use)
                            
                            # Визначити in_reply_to: використовувати message_id останнього повідомлення в thread
                            # Або використовувати inbound.in_reply_to, якщо він є
                            in_reply_to_value = inbound.in_reply_to
                            references_value = inbound.references
                            
                            # Якщо inbound.in_reply_to немає, спробувати знайти останнє повідомлення в thread
                            if not in_reply_to_value and thread_messages:
                                last_message = thread_messages[-1]
                                if last_message and last_message.message_id:
                                    in_reply_to_value = last_message.message_id
                            
                            # Перевірити, чи вже є це повідомлення в thread (щоб уникнути дублікатів)
                            existing = thread_crud.get_by_thread_id(thread_id_to_use)
                            already_exists = any(
                                msg.message_id == inbound.message_id 
                                for msg in existing 
                                if msg.message_id and inbound.message_id
                            )
                            
                            if not already_exists:
                                # Зберегти відповідь в thread
                                self.logger.info("Inbound: saving reply to thread: thread_id=%s, campaign_id=%s", 
                                               thread_id_to_use, campaign_id_to_use)
                                thread_data = {
                                    "id": str(uuid.uuid4()),
                                    "thread_id": thread_id_to_use,
                                    "campaign_id": campaign_id_to_use,
                                    "sent_email_id": None,  # Це не наша відповідь
                                    "message_type": MessageType.received,
                                    "from_email": inbound.from_email,
                                    "to_email": inbound.account_email,
                                    "subject": decoded_subject,
                                    "body": inbound.body,
                                    "message_id": inbound.message_id,  # Зберігаємо message_id отриманого листа
                                    "in_reply_to": in_reply_to_value,
                                    "references": inbound.references,
                                }
                                try:
                                    create_email_thread(db, thread_data)
                                    self.logger.info("Inbound: successfully saved reply to thread: %s", thread_id_to_use)
                                except Exception as e:
                                    self.logger.error("Inbound: failed to save reply to thread: %s", str(e))
                                    raise
                            else:
                                self.logger.info("Inbound: reply already exists in thread: %s, skipping", thread_id_to_use)
                        
                        # Update campaign statistics
                        campaign_crud = CampaignCRUD(db)
                        campaign_crud.update_statistics(email.campaign_id)
                
                # Якщо нічого не знайдено
                if not found_threads and not updated_emails:
                    self.logger.warning(
                        "Inbound: no matching sent emails or threads found for reply (from=%s, to=%s, subject=%s)",
                        inbound.from_email,
                        inbound.account_email,
                        decoded_subject,
                    )
            except Exception as exc:
                self.logger.error("Inbound: failed to mark email as replied: %s", str(exc), exc_info=True)
            finally:
                db.close()
            
            # Generate auto-reply for the correct campaign (only ONE)
            # campaigns_to_process тепер містить тільки одну правильну кампанію
            for campaign_info in campaigns_to_process:
                campaign_id = campaign_info['campaign_id']
                thread_id = campaign_info['thread_id']
                self.logger.info("Inbound: checking auto-reply for campaign_id=%s, thread_id=%s (source=%s)", 
                               campaign_id, thread_id, campaign_info['source'])
                try:
                    pending = await self._build_pending_reply(inbound, campaign_id, thread_id)
                    if pending:  # Only enqueue if auto_answering is enabled
                        scheduler.enqueue(pending)
                        enqueued += 1
                        self.logger.info(
                            "Inbound: enqueued auto-reply id=%s for campaign_id=%s, account=%s to=%s scheduled_at=%s",
                            pending.id,
                            campaign_id,
                            pending.account_email,
                            pending.to_email,
                            pending.scheduled_at.isoformat(),
                        )
                    else:
                        # Більш детальне повідомлення вже виведено в _build_pending_reply
                        self.logger.debug(
                            "Inbound: auto-reply not generated for campaign_id=%s (see previous logs for reason)",
                            campaign_id,
                        )
                except Exception as exc:
                    self.logger.error("Inbound: failed to generate auto-reply for campaign_id=%s: %s", 
                                    campaign_id, str(exc), exc_info=True)
        return enqueued

    async def _build_pending_reply(self, inbound: InboundMessage, campaign_id: str, thread_id: str) -> Optional[PendingReply]:
        """Build pending reply only if campaign has auto_answering enabled.
        
        Перевіряє, чи вже була згенерована відповідь на останнє повідомлення в thread,
        щоб уникнути дублікатів. Генерує відповідь для кожної нової відповіді.
        Якщо single_reply_only увімкнено, відправляє лише одну відповідь за thread.
        """
        # Check if campaign has auto_answering enabled
        db = SessionLocal()
        try:
            from app.database.crud import CampaignCRUD
            campaign_crud = CampaignCRUD(db)
            campaign = campaign_crud.get_by_id(campaign_id)
            
            if not campaign:
                self.logger.warning("Inbound: campaign %s not found in database, skipping auto-reply", campaign_id)
                return None
            
            # Log campaign settings for debugging
            self.logger.info(
                "Inbound: checking auto-reply conditions for campaign_id=%s: auto_answering=%s, single_reply_only=%s, thread_id=%s",
                campaign_id,
                campaign.auto_answering,
                getattr(campaign, 'single_reply_only', None),
                thread_id
            )
            
            if not campaign.auto_answering:
                self.logger.info("Inbound: campaign %s does not have auto_answering enabled (auto_answering=%s), skipping auto-reply", 
                               campaign_id, campaign.auto_answering)
                return None
            
            # Get thread messages for context
            thread_crud = EmailThreadCRUD(db)
            thread_messages = thread_crud.get_by_thread_id(thread_id)
            self.logger.info("Inbound: found %d messages in thread %s for campaign %s", 
                           len(thread_messages) if thread_messages else 0, thread_id, campaign_id)
            
            # Якщо single_reply_only увімкнено, перевірити чи вже була відправлена авто-відповідь для цього thread
            # Авто-відповіді мають sent_email_id IS NULL (на відміну від оригінальних листів кампанії, які мають sent_email_id)
            single_reply_only = getattr(campaign, 'single_reply_only', False)
            if single_reply_only:
                from app.database.models import MessageType
                # Перевірити чи є хоча б одне відправлене повідомлення-авто-відповідь (sent_email_id IS NULL)
                auto_reply_messages = [
                    msg for msg in thread_messages 
                    if msg.message_type == MessageType.sent and msg.sent_email_id is None
                ]
                if auto_reply_messages:
                    # Вже була відправлена авто-відповідь, просто зберігаємо лист без генерації нової відповіді
                    self.logger.info(
                        "Inbound: campaign %s has single_reply_only=True and auto-reply already sent for thread %s (found %d auto-reply messages), saving email without generating reply",
                        campaign_id, thread_id, len(auto_reply_messages)
                    )
                    return None
                else:
                    self.logger.info(
                        "Inbound: campaign %s has single_reply_only=True but no auto-reply sent yet in thread %s (total sent messages: %d), will generate first auto-reply",
                        campaign_id, 
                        thread_id,
                        len([msg for msg in thread_messages if msg.message_type == MessageType.sent])
                    )
            
            # Перевірити, чи вже була згенерована відповідь саме на ЦЕ повідомлення (за message_id)
            # Це важливо для уникнення дублікатів, але дозволяє генерувати відповіді на нові повідомлення
            from app.database.models import MessageType
            if inbound.message_id:
                # Шукаємо, чи вже є відправлене повідомлення після цього отриманого (за message_id)
                received_with_this_id = [
                    msg for msg in thread_messages 
                    if msg.message_type == MessageType.received 
                    and msg.message_id == inbound.message_id
                ]
                if received_with_this_id:
                    last_received = received_with_this_id[-1]
                    # Перевірити, чи вже є відправлене повідомлення після цього отриманого
                    sent_after_received = [
                        msg for msg in thread_messages 
                        if msg.message_type == MessageType.sent 
                        and msg.created_at > last_received.created_at
                    ]
                    # Якщо вже є відправлене повідомлення після цього отриманого, не генерувати дублікат
                    if sent_after_received:
                        self.logger.info("Inbound: auto-reply already generated for message_id=%s in thread=%s, skipping duplicate", 
                                       inbound.message_id, thread_id)
                        return None
            
            # Generate reply content using assistant with campaign settings and thread context
            subject, body = await self._generate_answer(inbound, campaign, thread_messages)

            # Keep subject within the same thread by reusing previous subject when possible
            subject = self._build_reply_subject(inbound, thread_messages) or subject

            scheduled_at = scheduler.schedule_time_for_reply(inbound.received_at)
            
            return PendingReply(
                id=str(uuid.uuid4()),
                account_email=inbound.account_email,
                to_email=inbound.from_email,
                subject=subject,
                body=body,
                scheduled_at=scheduled_at,
                created_at=datetime.now(timezone.utc),
                campaign_id=campaign_id,
                thread_id=thread_id,
            )
        finally:
            db.close()

    async def _generate_answer(self, inbound: InboundMessage, campaign, thread_messages) -> tuple[str, str]:
        """Generate reply using assistant with campaign settings and thread context."""
        return await self.answer_ai.generate_reply_for_inbound(
            inbound, 
            campaign=campaign,
            thread_messages=thread_messages
        )

    def _build_reply_subject(self, inbound: InboundMessage, thread_messages) -> Optional[str]:
        """
        Ensure auto-reply subject stays inside the original thread.
        Preference order:
        1. Use decoded inbound subject (add "Re:" if it lacks reply prefixes).
        2. Fallback to the first sent subject in the thread.
        """
        decoded_subject = (decode_email_header(inbound.subject) or "").strip()
        if decoded_subject:
            lowered = decoded_subject.lower()
            reply_prefixes = ("re:", "aw:", "fw:", "fwd:")
            if any(lowered.startswith(prefix) for prefix in reply_prefixes):
                return decoded_subject
            return f"Re: {decoded_subject}"

        if thread_messages:
            from app.database.models import MessageType
            for msg in thread_messages:
                if msg.message_type == MessageType.sent and msg.subject:
                    return f"Re: {msg.subject.strip()}"

        return None

    async def dispatch_due(self) -> int:
        """Send any due pending replies using the existing send service. Returns count sent."""
        due = scheduler.pop_due()
        if not due:
            self.logger.info("Inbound: no due replies to dispatch this tick")
            return 0
        service = EmailCampaignService()
        sent_count = 0
        for pending in due:
            # Wrap reply content into PersonalizedEmail
            from app.schemas.email import PersonalizedEmail
            email_content = PersonalizedEmail(subject=pending.subject, body=pending.body, language="pl")
            
            # Get campaign to determine use_corporate
            use_corporate = False
            db = SessionLocal()
            try:
                if pending.campaign_id:
                    from app.database.crud import CampaignCRUD
                    campaign_crud = CampaignCRUD(db)
                    campaign = campaign_crud.get_by_id(pending.campaign_id)
                    use_corporate = campaign.use_corporate if campaign else False
            finally:
                db.close()
            
            # Find the account for this email to get sender name
            account = next((acc for acc in service.all_accounts if acc.email == pending.account_email), None)
            sender_name = None
            if account and account.first_name and account.last_name:
                sender_name = f"{account.first_name} {account.last_name}"
            
            result = await service.mail_sender.send_email(
                email=email_content,
                from_email=pending.account_email,
                to_email=pending.to_email,
                use_corporate=use_corporate,
                sender_name=sender_name,
                is_list_campaign=False,
                force_send=True,
            )
            # Save reply to thread if we have campaign_id and thread_id (even if failed, to show error)
            if pending.campaign_id and pending.thread_id:
                db = SessionLocal()
                try:
                    # Get last message in thread for in_reply_to
                    thread_crud = EmailThreadCRUD(db)
                    thread_messages = thread_crud.get_by_thread_id(pending.thread_id)
                    
                    # Знайти останнє отримане повідомлення (на яке ми відповідаємо)
                    from app.database.models import MessageType
                    received_messages = [msg for msg in thread_messages if msg.message_type == MessageType.received]
                    in_reply_to_value = None
                    references_value = None
                    
                    if received_messages:
                        last_received = received_messages[-1]
                        # in_reply_to повинен вказувати на message_id останнього отриманого повідомлення
                        in_reply_to_value = last_received.message_id
                        # References може містити всі попередні message_id
                        if last_received.references:
                            references_value = last_received.references
                        elif last_received.message_id:
                            # Якщо references немає, створити з message_id останнього повідомлення
                            references_value = last_received.message_id
                    
                    # Якщо провайдер не повернув message_id, згенерувати свій для збереження в thread
                    # Це важливо для подальшого пошуку через in_reply_to
                    message_id_to_save = result.message_id
                    if not message_id_to_save and result.success:
                        # Генерувати унікальний message_id тільки якщо відправка успішна
                        message_id_to_save = f"<auto-reply-{uuid.uuid4()}@{pending.account_email.split('@')[1] if '@' in pending.account_email else 'local'}>"
                        self.logger.warning("Inbound: provider did not return message_id, generated: %s", message_id_to_save)
                    
                    thread_data = {
                        "id": str(uuid.uuid4()),
                        "thread_id": pending.thread_id,
                        "campaign_id": pending.campaign_id,
                        "sent_email_id": None,  # No SentEmail record for auto-replies from inbound
                        "message_type": MessageType.sent,
                        "from_email": pending.account_email,
                        "to_email": pending.to_email,
                        "subject": pending.subject,
                        "body": pending.body,
                        "message_id": message_id_to_save,  # message_id від провайдера або згенерований (або None якщо помилка)
                        "in_reply_to": in_reply_to_value,  # message_id останнього отриманого повідомлення
                        "references": references_value,
                        "error": result.error if not result.success else None,  # Зберігати помилку якщо відправка не вдалася
                    }
                    create_email_thread(db, thread_data)
                    if result.success:
                        self.logger.info("Inbound: saved auto-reply to thread %s with message_id=%s", 
                                       pending.thread_id, message_id_to_save)
                    else:
                        self.logger.warning("Inbound: saved failed auto-reply to thread %s with error: %s", 
                                          pending.thread_id, result.error)
                except Exception as exc:
                    self.logger.error("Inbound: failed to save auto-reply to thread: %s", str(exc), exc_info=True)
                finally:
                    db.close()
            
            sent = SentReply(
                id=pending.id,
                account_email=pending.account_email,
                to_email=pending.to_email,
                subject=pending.subject,
                body=pending.body,
                scheduled_at=pending.scheduled_at,
                sent_at=datetime.now(timezone.utc),
                success=result.success,
                message_id=result.message_id,
                error=result.error,
            )
            scheduler.record_history(sent)
            sent_count += 1
            self.logger.info(
                "Inbound: dispatched id=%s to=%s success=%s message_id=%s error=%s",
                sent.id,
                sent.to_email,
                sent.success,
                sent.message_id,
                sent.error,
            )
        self.logger.info("Inbound: total dispatched this tick = %d", sent_count)
        return sent_count


processor = InboundProcessor() 