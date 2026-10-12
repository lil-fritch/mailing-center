from typing import List, Optional
from datetime import datetime, timezone, timedelta, time
from sqlalchemy import asc
import random
import uuid
import pytz

from app.core.settings import settings
from app.core.logger import get_logger
from app.database.models import B2BObject, EmailStatus, MessageType, EmailThread
from app.database.crud import create_campaign, create_sent_email, SentEmailCRUD, CampaignCRUD, CampaignTargetCRUD, create_email_thread, EmailThreadCRUD
from app.database.connection import SessionLocal
from sqlalchemy.orm import Session
from app.schemas.email import EmailSendResult, CampaignSetupRequest
from app.integrations.ai.assistant_client import OpenAIAssistantClient
from app.integrations.mail.mail_sender import MailSender
from app.utils.throttle import pause_between_emails_random
from app.services.campaign_tracker import campaign_tracker
from app.integrations.mail import load_sender_accounts_from_db, SenderAccount
from app.services.paralleai import parallel_enricher


def create_or_get_thread_id(db: Session, campaign_id: str, from_email: str, to_email: str) -> str:
    """Створити новий thread_id або отримати існуючий для пари email адрес в межах кампанії"""
    thread_crud = EmailThreadCRUD(db)
    existing_thread = thread_crud.get_latest_thread_for_campaign(campaign_id, from_email, to_email)
    
    if existing_thread:
        return existing_thread
    else:
        # Створити новий thread_id для цієї кампанії
        return str(uuid.uuid4())


def save_email_to_thread(db: Session, thread_id: str, campaign_id: str, sent_email_id: str, 
                        from_email: str, to_email: str, subject: str, body: str, 
                        message_id: str = None) -> None:
    """Зберегти відправлений лист в thread"""
    print(f"DEBUG: Saving email to thread: thread_id={thread_id}, campaign_id={campaign_id}, sent_email_id={sent_email_id}")
    
    thread_data = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "campaign_id": campaign_id,
        "sent_email_id": sent_email_id,
        "message_type": MessageType.sent,
        "from_email": from_email,
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "message_id": message_id,
        "in_reply_to": None,
        "references": None,
    }
    
    try:
        create_email_thread(db, thread_data)
        print(f"DEBUG: Successfully saved email to thread: {thread_id}")
    except Exception as e:
        print(f"DEBUG: Failed to save email to thread: {e}")
        raise
# Service layer orchestrating email generation and sending for a list of studios.


class EmailCampaignService:
    """Coordinates AI generation and mail sending for studios with throttling.

    This service accepts a list of `Studio` instances, asks the AI integration
    to generate personalized emails for each, and then sends them using the
    mail integration. It is also responsible for pausing between emails.
    """

    def __init__(
        self,
        ai_client: Optional[OpenAIAssistantClient] = None,
        mail_sender: Optional[MailSender] = None,
        pause_seconds: Optional[float] = None,
    ) -> None:
        """Initialize the service with integration clients and pause settings."""
        self.logger = get_logger(__name__)
        self.ai_client = ai_client or OpenAIAssistantClient()
        self.mail_sender = mail_sender or MailSender()
        self.pause_seconds = pause_seconds if pause_seconds is not None else settings.email_pause_seconds
        # Load sender accounts from database
        accounts_1 = load_sender_accounts_from_db(active_only=True, server_id="1")
        accounts_2 = load_sender_accounts_from_db(active_only=True, server_id="2")
            
        self.all_accounts: List[SenderAccount] = accounts_1 + accounts_2
        self.logger.info("Loaded %d personal accounts (server_id=1) and %d corporate accounts (server_id=2)", len(accounts_1), len(accounts_2))
        # from_emails will be filtered based on use_corporate per campaign
        self.pause_min_seconds: float = (
            settings.email_pause_min_seconds if settings.email_pause_min_seconds is not None else self.pause_seconds
        )
        self.pause_max_seconds: float = (
            settings.email_pause_max_seconds if settings.email_pause_max_seconds is not None else self.pause_seconds
        )
    
    def _get_accounts_for_campaign(
        self,
        use_corporate: bool,
        allowed_account_ids: Optional[List[str]] = None
    ) -> tuple[List[SenderAccount], List[str]]:
        """Get filtered accounts and emails based on use_corporate flag.
        
        Returns:
            tuple: (filtered_accounts, filtered_from_emails)
        """
        allowed_set = {acc_id for acc_id in (allowed_account_ids or []) if acc_id}
        allowed_order: dict[str, int] = {
            acc_id: index for index, acc_id in enumerate(allowed_account_ids or [])
        }

        if use_corporate:
            # Use only corporate accounts (server_id == "2")
            filtered_accounts = [acc for acc in self.all_accounts if acc.server_id == "2"]
            account_type = "corporate"
        else:
            # Use only personal accounts (server_id == "1")
            filtered_accounts = [acc for acc in self.all_accounts if acc.server_id == "1"]
            account_type = "personal"
        
        if allowed_set:
            filtered_accounts = [
                acc for acc in filtered_accounts
                if getattr(acc, "id", None) in allowed_set
            ]
            filtered_accounts.sort(key=lambda acc: allowed_order.get(acc.id, len(allowed_order)))
            if not filtered_accounts:
                self.logger.warning(
                    "Campaign accounts filter: allowed sender IDs %s not found among available %s accounts",
                    list(allowed_set),
                    account_type,
                )

        from_emails_from_accounts = [acc.email for acc in filtered_accounts if acc.email]
        if from_emails_from_accounts:
            from_emails = from_emails_from_accounts
        elif allowed_set:
            # User explicitly limited accounts but none are available with email
            from_emails = []
        else:
            from_emails = settings.campaign_from_emails or []
        
        self.logger.info(
            "Campaign accounts filter: use_corporate=%s, allowed_ids=%s, found %d %s accounts, %d emails available",
            use_corporate,
            list(allowed_set) if allowed_set else "ALL",
            len(filtered_accounts),
            account_type,
            len(from_emails),
        )
        
        return filtered_accounts, from_emails

    async def _pause(self) -> float:
        """Pause between sending emails according to configured random range."""
        chosen = await pause_between_emails_random(self.pause_min_seconds, self.pause_max_seconds)
        self.logger.info("Campaign: paused for %.2fs", chosen)
        return chosen

    async def _wait_for_slot(self, *, campaign_id: Optional[str], daily_limit: Optional[int], tz_offset: Optional[str]) -> float:
        """Wait until sending is allowed per timezone window and daily_limit.

        Rules:
        - Allowed sending window is 09:00–18:00 in the campaign's timezone.
        - No more than `daily_limit` SENT emails within that window per local day.
        - Within the window and under the limit, wait a random pause in configured range.

        Returns the number of seconds actually slept.
        """
        # Import at method level to avoid cycles
        from app.database.connection import SessionLocal
        from app.database.models import SentEmail, EmailStatus
        from sqlalchemy import and_
        
        # Parse timezone: supports full timezone names (e.g., "Europe/Warsaw") or offsets (e.g., "+2", "-5")
        def parse_tz(offset_str: Optional[str]) -> timezone:
            if not offset_str:
                return timezone.utc
            s = str(offset_str).strip()
            
            # First try to parse as full timezone name (e.g., "Europe/Warsaw", "America/Toronto")
            try:
                tz = pytz.timezone(s)
                return tz
            except (pytz.UnknownTimeZoneError, AttributeError):
                pass
            
            # If not a timezone name, try to parse as offset (e.g., "+2", "-5", "+02:00")
            try:
                # support "+2", "-3", "2" forms
                hours = int(s)
                return timezone(timedelta(hours=hours))
            except Exception:
                try:
                    # support "+02:00" like forms
                    sign = 1 if s.startswith("+") else -1 if s.startswith("-") else 1
                    parts = s[1:].split(":") if s[:1] in "+-" else s.split(":")
                    h = int(parts[0]) if parts and parts[0] else 0
                    m = int(parts[1]) if len(parts) > 1 else 0
                    return timezone(sign * timedelta(hours=h, minutes=m))
                except Exception:
                    return timezone.utc

        tzinfo = parse_tz(tz_offset)
        slept_seconds_total = 0.0

        while True:
            now_utc = datetime.now(timezone.utc)
            now_local = now_utc.astimezone(tzinfo)

            start_local = datetime.combine(now_local.date(), time(hour=settings.campaign_work_start_hour, minute=0, tzinfo=tzinfo))
            end_local = datetime.combine(now_local.date(), time(hour=settings.campaign_work_end_hour, minute=0, tzinfo=tzinfo))

            # If before window, wait until start
            if now_local < start_local:
                wait_sec = (start_local - now_local).total_seconds()
                if wait_sec > 0:
                    self.logger.info("Campaign: outside window, sleeping until %02d:00 local (%.0fs)", settings.campaign_work_start_hour, wait_sec)
                    # persist planned wake-up
                    if campaign_id:
                        db_tmp = SessionLocal()
                        try:
                            CampaignCRUD(db_tmp).set_next_wake_at(campaign_id, datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                        finally:
                            db_tmp.close()
                    campaign_tracker.set_next_send_at(datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                    await pause_between_emails_random(wait_sec, wait_sec)  # deterministic sleep
                    slept_seconds_total += wait_sec
                    continue

            # If after window, wait until next day 09:00
            if now_local >= end_local:
                next_start_local = start_local + timedelta(days=1)
                wait_sec = (next_start_local - now_local).total_seconds()
                if wait_sec > 0:
                    self.logger.info("Campaign: after 18:00, sleeping until next 09:00 local (%.0fs)", wait_sec)
                    if campaign_id:
                        db_tmp = SessionLocal()
                        try:
                            CampaignCRUD(db_tmp).set_next_wake_at(campaign_id, datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                        finally:
                            db_tmp.close()
                    campaign_tracker.set_next_send_at(datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                    await pause_between_emails_random(wait_sec, wait_sec)
                    slept_seconds_total += wait_sec
                    continue

            # Within window
            if daily_limit is None or daily_limit <= 0 or not campaign_id:
                # No quota enforcement possible/required -> random pause only
                chosen = random.uniform(max(0.0, self.pause_min_seconds), max(self.pause_min_seconds, self.pause_max_seconds))
                if campaign_id:
                    db_tmp = SessionLocal()
                    try:
                        CampaignCRUD(db_tmp).set_next_wake_at(campaign_id, datetime.now(timezone.utc) + timedelta(seconds=chosen))
                    finally:
                        db_tmp.close()
                campaign_tracker.set_next_send_at(datetime.now(timezone.utc) + timedelta(seconds=chosen))
                await pause_between_emails_random(chosen, chosen)
                self.logger.info("Campaign: within window, random pause %.2fs (no quota)", chosen)
                slept_seconds_total += chosen
                break

            # Count SENT emails for this campaign in today's local window
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)

            db = SessionLocal()
            try:
                sent_today = db.query(SentEmail).filter(
                    and_(
                        SentEmail.campaign_id == campaign_id,
                        SentEmail.status == EmailStatus.SENT,
                        SentEmail.sent_at >= start_utc,
                        SentEmail.sent_at <= end_utc,
                    )
                ).count()
            except Exception:
                sent_today = 0
            finally:
                db.close()

            if sent_today >= daily_limit:
                # Quota reached for today -> wait to next day 09:00
                next_start_local = start_local + timedelta(days=1)
                wait_sec = (next_start_local - now_local).total_seconds()
                self.logger.info(
                    "Campaign: daily_limit reached (%d >= %d). Sleeping until next 09:00 local (%.0fs)",
                    sent_today,
                    daily_limit,
                    wait_sec,
                )
                if campaign_id:
                    db_tmp = SessionLocal()
                    try:
                        CampaignCRUD(db_tmp).set_next_wake_at(campaign_id, datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                    finally:
                        db_tmp.close()
                campaign_tracker.set_next_send_at(datetime.now(timezone.utc) + timedelta(seconds=wait_sec))
                await pause_between_emails_random(wait_sec, wait_sec)
                slept_seconds_total += wait_sec
                continue

            # Under the limit -> apply random pause
            chosen = random.uniform(max(0.0, self.pause_min_seconds), max(self.pause_min_seconds, self.pause_max_seconds))
            if campaign_id:
                db_tmp = SessionLocal()
                try:
                    CampaignCRUD(db_tmp).set_next_wake_at(campaign_id, datetime.now(timezone.utc) + timedelta(seconds=chosen))
                finally:
                    db_tmp.close()
            campaign_tracker.set_next_send_at(datetime.now(timezone.utc) + timedelta(seconds=chosen))
            await pause_between_emails_random(chosen, chosen)
            self.logger.info("Campaign: within window, random pause %.2fs (quota %d/%d)", chosen, sent_today, daily_limit)
            slept_seconds_total += chosen
            break

        return slept_seconds_total

    async def process_campaign_by_id(self, campaign_id: str) -> None:
        """Process campaign by reading campaign_targets one-by-one with heartbeat and pause checks.
        Refactored to use short-lived DB sessions to avoid holding connections across awaits.
        """
        # Load initial campaign and request payload
        from app.schemas.email import CampaignSetupRequest
        campaign_request: Optional[CampaignSetupRequest] = None

        # Fetch campaign once to check existence and paused state
        with_session_campaign = None
        from sqlalchemy import asc
        db = SessionLocal()
        try:
            campaign_crud = CampaignCRUD(db)
            with_session_campaign = campaign_crud.get_by_id(campaign_id)
        finally:
            db.close()

        if not with_session_campaign:
            self.logger.error("Campaign: %s not found", campaign_id)
            return
        if with_session_campaign.status == "paused":
            self.logger.info("Campaign: %s is paused; skipping processing", campaign_id)
            return

        # Ensure in_progress
        if with_session_campaign.status not in ("in_progress",):
            db = SessionLocal()
            try:
                CampaignCRUD(db).set_status(campaign_id, "in_progress", started_at=datetime.now(timezone.utc))
            finally:
                db.close()

        # Parse request payload
        try:
            if with_session_campaign.request_payload:
                campaign_request = CampaignSetupRequest.model_validate(with_session_campaign.request_payload)
        except Exception as exc:
            self.logger.warning("Campaign: failed to parse request_payload for %s: %s", campaign_id, str(exc))

        # Compute total targets count
        from app.database.models import CampaignTarget
        total = 0
        db = SessionLocal()
        try:
            total = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign_id).count()
        finally:
            db.close()

        campaign_tracker.start(total)
        campaign_tracker.set_campaign_id(campaign_id)

        # Re-plan overdue targets (planned_send_at <= now) to next valid slots respecting window and daily_limit
        await self._replan_overdue_targets(
            campaign_id=campaign_id,
            tz_offset=with_session_campaign.timezone,
            daily_limit=with_session_campaign.daily_limit,
        )

        # Read campaign again to get latest use_corporate value
        db = SessionLocal()
        try:
            campaign_latest = CampaignCRUD(db).get_by_id(campaign_id)
            use_corporate = campaign_latest.use_corporate if campaign_latest else False
            self.logger.info("Campaign %s: use_corporate=%s (from DB)", campaign_id, use_corporate)
        finally:
            db.close()
        
        # Get accounts and emails filtered by use_corporate and selected sender ids
        allowed_sender_ids = campaign_request.sender_account_ids if campaign_request else None
        accounts, from_emails = self._get_accounts_for_campaign(use_corporate, allowed_sender_ids)
        
        if not from_emails:
            self.logger.error("Campaign %s: no sender accounts/emails configured for use_corporate=%s; cannot send. Available accounts: personal=%d, corporate=%d", 
                            campaign_id, use_corporate,
                            len([a for a in self.all_accounts if a.server_id == "1"]),
                            len([a for a in self.all_accounts if a.server_id == "2"]))
            return
        
        # Email rotation counter - tracks which email to use next (rotates across all targets)
        email_rotation_index = 0
        
        finished_normally = False
        # Use a single DB session across the processing loop to avoid excessive churn
        shared_db = SessionLocal()
        try:
            while True:
                # Heartbeat
                CampaignCRUD(shared_db).update_heartbeat(campaign_id)

                # Re-read campaign for status and limits
                campaign = CampaignCRUD(shared_db).get_by_id(campaign_id)
                if not campaign or campaign.status == "paused":
                    self.logger.info("Campaign: %s paused/stopped during processing", campaign_id)
                    break

                # Get next target (use earliest planned_send_at)
                target = CampaignTargetCRUD(shared_db).next_pending(campaign_id)
                # Count targets by status for debugging
                if not target:
                    status_counts = {}
                    for status in ['queued', 'enriching', 'generated', 'scheduled', 'sending', 'sent', 'failed', 'replied', 'bounced']:
                        count = shared_db.query(CampaignTarget).filter(
                            CampaignTarget.campaign_id == campaign_id,
                            CampaignTarget.status == status
                        ).count()
                        if count > 0:
                            status_counts[status] = count
                    self.logger.info("Campaign: %s no more scheduled targets. Status counts: %s", campaign_id, status_counts)
                if not target:
                    finished_normally = True
                    break

                # Wait until planned_send_at if set; otherwise fallback to slot logic
                from datetime import timezone as tz
                if target.planned_send_at:
                    now = datetime.now(tz.utc)
                    to_wait = max(0.0, (target.planned_send_at - now).total_seconds())
                    if to_wait > 0:
                        campaign_tracker.set_next_send_at(now + timedelta(seconds=to_wait))
                        # persist wake
                        CampaignCRUD(shared_db).set_next_wake_at(campaign_id, now + timedelta(seconds=to_wait))
                        await pause_between_emails_random(to_wait, to_wait)
                        campaign_tracker.set_last_pause(to_wait)
                else:
                    waited = await self._wait_for_slot(
                        campaign_id=campaign_id,
                        daily_limit=campaign.daily_limit,
                        tz_offset=campaign.timezone,
                    )
                    if waited:
                        campaign_tracker.set_last_pause(waited)

                # Check if campaign is paused before marking as sending
                campaign = CampaignCRUD(shared_db).get_by_id(campaign_id)
                if not campaign or campaign.status == "paused":
                    self.logger.info("Campaign: %s paused before processing target %s; skipping", campaign_id, target.id)
                    continue

                # Mark sending
                target = CampaignTargetCRUD(shared_db).mark_sending(target.id)
                if not target:
                    continue

                # Skip if still queued/enriching/generated (content not ready yet)
                if target.status in ['queued', 'enriching', 'generated'] or not target.email_subject or not target.email_body:
                    self.logger.warning("Campaign: target %s not ready (status=%s), skipping", target.id, target.status)
                    continue

                # Build minimal B2B-like object
                class _TmpObj:
                    pass
                b2b_obj = _TmpObj()
                b2b_obj.place_id = target.place_id
                b2b_obj.name = target.name
                b2b_obj.type = target.type
                b2b_obj.email = target.to_email
                b2b_obj.city = None
                b2b_obj.website = None
                b2b_obj.description = None
                b2b_obj.owner_name = None
                b2b_obj.address = None

                # Generate email content
                # We now have generated content on target
                class _EmailContent:
                    pass
                email_content = _EmailContent()
                email_content.subject = target.email_subject or ""
                email_content.body = target.email_body or ""
                email_content.language = None

                # Prepare sending
                send_result = None
                attempts = 0
                max_attempts = len(from_emails) or 1
                sent_email_id = str(uuid.uuid4())

                # Pre-create SentEmail record
                # Створити або отримати thread_id
                thread_id = create_or_get_thread_id(shared_db, campaign_id, from_emails[0] if from_emails else "", target.to_email)
                
                sent_email_data = {
                    "id": sent_email_id,
                    "campaign_id": campaign_id,
                    "b2b_place_id": target.place_id,
                    "b2b_name": target.name,
                    "b2b_type": target.type,
                    "from_email": from_emails[0] if from_emails else "",
                    "to_email": target.to_email,
                    "subject": getattr(email_content, 'subject', None),
                    "body": getattr(email_content, 'body', None),
                    "status": EmailStatus.PENDING,
                    "thread_id": thread_id,
                }
                create_sent_email(shared_db, sent_email_data)
                
                # Зберегти в thread
                save_email_to_thread(
                    shared_db, thread_id, campaign_id, sent_email_id,
                    sent_email_data["from_email"], sent_email_data["to_email"],
                    sent_email_data["subject"], sent_email_data["body"]
                )
                
                # Оновити CampaignTarget з thread_id
                target.thread_id = thread_id
                shared_db.commit()  # Зберегти зміни
                
                # Оновити target об'єкт для подальшого використання
                target.thread_id = thread_id

                while attempts < max_attempts:
                    # Use global rotation index + attempt number for proper rotation
                    from_email_index = (email_rotation_index + attempts) % len(from_emails) if from_emails else 0
                    from_email = from_emails[from_email_index] if from_emails else ""
                    attempts += 1

                    account = next((acc for acc in accounts if acc.email == from_email), None)
                    server_id = account.server_id if account else "1"
                    sender_name = f"{account.first_name} {account.last_name}" if account and account.first_name and account.last_name else None

                    # Update SentEmail to SENDING
                    sent_email_crud = SentEmailCRUD(shared_db)
                    sent_email_crud.update(sent_email_id, {
                        "status": EmailStatus.SENDING,
                        "from_email": from_email,
                        "sender_name": sender_name,
                        "server_id": server_id,
                        "thread_id": thread_id,
                    })

                    # Check if campaign is paused before sending (works in both dev and production mode)
                    campaign = CampaignCRUD(shared_db).get_by_id(campaign_id)
                    if not campaign or campaign.status == "paused":
                        self.logger.info("Campaign: %s paused before sending email to %s; aborting send", campaign_id, target.to_email)
                        # Mark target as scheduled again so it can be processed when resumed
                        CampaignTargetCRUD(shared_db).update_status(target.id, 'scheduled')
                        # Update SentEmail status back to pending
                        sent_email_crud.update(sent_email_id, {"status": EmailStatus.PENDING})
                        break
                    
                    # Determine if this is a list campaign (place_id starts with "email_")
                    is_list_campaign = target.place_id.startswith("email_") if target.place_id else False
                    
                    # Force send database objects even in dev mode
                    force_send = not is_list_campaign

                    # Send (use the use_corporate value we read earlier)
                    send_result = await self.mail_sender.send_email(
                        email=email_content,
                        from_email=from_email,
                        to_email=target.to_email,
                        use_corporate=use_corporate,
                        sender_name=sender_name,
                        is_list_campaign=is_list_campaign,
                        force_send=force_send,
                    )

                    if send_result.success:
                        # Mark sent in SentEmail and target
                        sent_email_crud = SentEmailCRUD(shared_db)
                        sent_email_crud.update(sent_email_id, {
                            "status": EmailStatus.SENT,
                            "message_id": send_result.message_id,
                            "provider": send_result.provider,
                            "sent_at": datetime.now(timezone.utc),
                            "thread_id": thread_id,
                        })
                        CampaignTargetCRUD(shared_db).mark_sent(target.id, thread_id, datetime.now(timezone.utc))
                        
                        # Update EmailThread with correct from_email and message_id
                        thread_msg = shared_db.query(EmailThread).filter(
                            EmailThread.sent_email_id == sent_email_id
                        ).first()
                        if thread_msg:
                            thread_msg.from_email = from_email
                            thread_msg.message_id = send_result.message_id
                            shared_db.commit()
                        
                        # Increment rotation index for next email (rotate to next sender)
                        email_rotation_index += 1
                        break
                    else:
                        # Failure path
                        if attempts >= max_attempts:
                            sent_email_crud = SentEmailCRUD(shared_db)
                            sent_email_crud.update(sent_email_id, {
                                "status": EmailStatus.FAILED,
                                "error": send_result.error,
                                "thread_id": thread_id,
                            })
                            CampaignTargetCRUD(shared_db).mark_failed(target.id, send_result.error or "send failed")
                        # If not the last attempt, retry immediately with next sender (no delay)

                # Record result in tracker
                campaign_tracker.record_result(send_result or EmailSendResult(success=False, message_id=None, error="unknown"))

            # Finish (outside loop)
            campaign_tracker.finish()
            campaign_crud = CampaignCRUD(shared_db)
            campaign_crud.update_statistics(campaign_id)
            if finished_normally:
                campaign_crud.set_status(campaign_id, "completed", finished_at=datetime.now(timezone.utc))
        finally:
            try:
                shared_db.close()
            except Exception:
                pass

    async def generate_content_for_campaign(self, campaign_id: str, campaign_request: Optional['CampaignSetupRequest'] = None):
        """Background task to generate email content for all 'queued' targets in the campaign.
        
        After generation completes, plans send times for all scheduled targets.
        """
        from app.database.models import CampaignTarget
        from app.schemas.email import CampaignSetupRequest
        self.logger.info("ContentGeneration: starting for campaign %s", campaign_id)

        # Fetch campaign
        db = SessionLocal()
        try:
            campaign = CampaignCRUD(db).get_by_id(campaign_id)
        finally:
            db.close()
        if not campaign:
            self.logger.error("ContentGeneration: campaign %s not found", campaign_id)
            return

        # Reconstruct request payload
        campaign_request = None
        if campaign.request_payload:
            from app.schemas.email import CampaignSetupRequest
            campaign_request = CampaignSetupRequest(**campaign.request_payload)

        # Fetch all 'queued' targets (change to 'generating' as we process them)
        db = SessionLocal()
        try:
            targets = db.query(CampaignTarget).filter(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.status == 'queued'
            ).all()
        finally:
            db.close()

        if not targets:
            self.logger.info("ContentGeneration: no queued targets for campaign %s", campaign_id)
            return

        total = len(targets)
        self.logger.info("ContentGeneration: found %d targets to generate content", total)

        for idx, target in enumerate(targets, start=1):
            self.logger.info("ContentGeneration: [%d/%d] generating for target %s (place_id=%s)", idx, total, target.id, target.place_id)

            # Build minimal B2B-like object
            class _TmpObj:
                pass
            gobj = _TmpObj()
            gobj.place_id = target.place_id
            gobj.name = target.name
            gobj.type = target.type
            gobj.email = target.to_email
            gobj.city = None
            gobj.website = None
            gobj.description = None
            gobj.owner_name = None
            gobj.address = None
            
            # Try to load full B2B object data if place_id exists
            if target.place_id:
                db = SessionLocal()
                try:
                    from app.database.crud import B2BObjectCRUD
                    b2b_crud = B2BObjectCRUD(db)
                    b2b_obj = b2b_crud.get_by_place_id(target.place_id)
                    if b2b_obj:
                        gobj.city = b2b_obj.city
                        gobj.website = b2b_obj.website
                        gobj.description = b2b_obj.description
                        gobj.owner_name = b2b_obj.owner_name
                        gobj.address = b2b_obj.address
                        self.logger.info("ContentGeneration: loaded B2B data for place_id=%s (website=%s)", target.place_id, bool(b2b_obj.website))
                except Exception as e:
                    self.logger.warning("ContentGeneration: failed to load B2B object for place_id=%s: %s", target.place_id, str(e))
                finally:
                    db.close()

            try:
                enriched_context = None
                
                # Use new enricher if parsing enabled and parsing_prompt provided
                if campaign_request and getattr(campaign_request, 'parsing', False):
                    parsing_prompt = getattr(campaign_request, 'parsing_prompt', None)
                    if parsing_prompt and gobj.website:
                        # Встановити статус 'enriching' перед початком обогачення
                        db_enriching = SessionLocal()
                        try:
                            CampaignTargetCRUD(db_enriching).set_enriching(target.id)
                        finally:
                            db_enriching.close()
                        
                        self.logger.info("ContentGeneration: enriching data for %s (parsing_prompt provided)", target.name or target.place_id)
                        enriched_context = await parallel_enricher.enrich_object(
                            website=gobj.website,
                            prompt=parsing_prompt,
                            object_name=target.name or target.place_id
                        )
                        if enriched_context:
                            self.logger.info("ContentGeneration: enrichment successful for %s", target.name or target.place_id)
                    else:
                        self.logger.info("ContentGeneration: parsing enabled but no parsing_prompt or website for %s", target.name or target.place_id)
                
                if campaign_request is None:
                    from app.schemas.email import CampaignSetupRequest as CSR
                    campaign_request = CSR(subject_prompt="", body_prompt="")
                
                email_content = await self.ai_client.generate_email_for_b2b_object(gobj, campaign_request, None, enriched_context)
                
                # Update target to scheduled
                db = SessionLocal()
                try:
                    CampaignTargetCRUD(db).set_generated(target.id, email_content.subject, email_content.body, email_content.language)
                    self.logger.info("ContentGeneration: [%d/%d] success for target %s", idx, total, target.id)
                finally:
                    db.close()

            except Exception as exc:
                self.logger.error("ContentGeneration: [%d/%d] failed for target %s: %s", idx, total, target.id, str(exc))
                db = SessionLocal()
                try:
                    CampaignTargetCRUD(db).set_generation_error(target.id, f"AI generation failed: {str(exc)}")
                finally:
                    db.close()

        self.logger.info("ContentGeneration: completed for campaign %s", campaign_id)
        
        # NOW plan send times for all scheduled targets (after generation completes)
        if campaign_request:
            self.logger.info("ContentGeneration: planning send times for campaign %s", campaign_id)
            await self._plan_send_times(campaign_id, campaign_request)
            self.logger.info("ContentGeneration: planning completed for campaign %s", campaign_id)

    async def _plan_send_times(self, campaign_id: str, campaign_request: 'CampaignSetupRequest') -> None:
        """Plan send times for all scheduled targets after generation completes."""
        from app.database.models import CampaignTarget
        from datetime import datetime, timedelta, time, timezone as tz
        from sqlalchemy import asc
        import random
        
        db = SessionLocal()
        try:
            # Fetch all generated targets (generation completed, but not yet scheduled) in creation order
            scheduled = db.query(CampaignTarget).filter(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.status == 'generated'
            ).order_by(asc(CampaignTarget.created_at)).all()
        finally:
            db.close()
        
        if not scheduled:
            self.logger.info("Planning: no generated targets to schedule for campaign %s", campaign_id)
            return
        
        # Development mode: simple sequential planning (current time + 15 seconds for each)
        if settings.development_mode:
            now_utc = datetime.now(tz.utc)
            assignments: list[tuple[str, datetime]] = []
            for i, tgt in enumerate(scheduled):
                planned_utc = now_utc + timedelta(seconds=15 * (i + 1))
                assignments.append((tgt.id, planned_utc))
            
            if assignments:
                db = SessionLocal()
                try:
                    CampaignTargetCRUD(db).set_planned_send_at_bulk(campaign_id, assignments)
                    earliest = min(p for _, p in assignments)
                    CampaignCRUD(db).set_next_wake_at(campaign_id, earliest)
                finally:
                    db.close()
                self.logger.info("Planning (DEV MODE): planned %d targets sequentially, earliest at %s", len(assignments), earliest)
            return
        
        # Production mode: respect work hours and daily limits
        # Parse timezone: supports full timezone names (e.g., "Europe/Warsaw") or offsets (e.g., "+2", "-5")
        def parse_tz(offset_str: Optional[str]):
            if not offset_str:
                return tz.utc
            s = str(offset_str).strip()
            
            # First try to parse as full timezone name (e.g., "Europe/Warsaw", "America/Toronto")
            try:
                pytz_tz = pytz.timezone(s)
                return pytz_tz
            except (pytz.UnknownTimeZoneError, AttributeError):
                pass
            
            # If not a timezone name, try to parse as offset (e.g., "+2", "-5", "+02:00")
            try:
                hours = int(s)
                return tz(timedelta(hours=hours))
            except Exception:
                try:
                    sign = 1 if s.startswith('+') else -1 if s.startswith('-') else 1
                    parts = s[1:].split(':') if s[:1] in '+-' else s.split(':')
                    h = int(parts[0]) if parts and parts[0] else 0
                    m = int(parts[1]) if len(parts) > 1 else 0
                    return tz(sign * timedelta(hours=h, minutes=m))
                except Exception:
                    return tz.utc
        
        tzinfo = parse_tz(campaign_request.timezone)
        daily_limit = campaign_request.daily_limit or len(scheduled)
        slot_count = max(1, int(daily_limit))
        work_hours = settings.campaign_work_end_hour - settings.campaign_work_start_hour
        window_seconds = work_hours * 60 * 60
        slot_sec = max(1, window_seconds // slot_count)
        
        # Start from next valid day/time in local tz
        now_utc = datetime.now(tz.utc)
        now_local = now_utc.astimezone(tzinfo)
        start_local_today = datetime.combine(now_local.date(), time(hour=settings.campaign_work_start_hour, minute=0, tzinfo=tzinfo))
        end_local_today = datetime.combine(now_local.date(), time(hour=settings.campaign_work_end_hour, minute=0, tzinfo=tzinfo))
        
        # Calculate starting slot index
        if now_local < start_local_today:
            base_day_start_local = start_local_today
            start_slot_index = 0
        elif now_local >= end_local_today:
            base_day_start_local = start_local_today + timedelta(days=1)
            start_slot_index = 0
        else:
            base_day_start_local = start_local_today
            elapsed = (now_local - start_local_today).total_seconds()
            start_slot_index = int(elapsed // slot_sec) + 1
        
        assignments: list[tuple[str, datetime]] = []
        for i, tgt in enumerate(scheduled):
            absolute_slot = start_slot_index + i
            day_offset = absolute_slot // slot_count
            slot_in_day = absolute_slot % slot_count
            slot_start_local = base_day_start_local + timedelta(days=day_offset, seconds=slot_in_day * slot_sec)
            jitter = random.uniform(0, float(slot_sec))
            planned_local = slot_start_local + timedelta(seconds=jitter)
            planned_utc = planned_local.astimezone(tz.utc)
            assignments.append((tgt.id, planned_utc))
        
        if assignments:
            db = SessionLocal()
            try:
                CampaignTargetCRUD(db).set_planned_send_at_bulk(campaign_id, assignments)
                earliest = min(p for _, p in assignments)
                CampaignCRUD(db).set_next_wake_at(campaign_id, earliest)
            finally:
                db.close()
            self.logger.info("Planning: planned %d targets, earliest at %s", len(assignments), earliest)

    async def _replan_overdue_targets(self, *, campaign_id: str, tz_offset: Optional[str], daily_limit: Optional[int]) -> None:
        """Move overdue or unscheduled pending targets to the next valid slots.

        - Keeps scheduling inside 09:00–18:00 local window
        - Respects daily_limit by slotting across days
        - Preserves order: overdue emails are scheduled AFTER non-overdue ones
        - Sets campaign.next_wake_at to earliest planned time
        """
        from app.database.models import CampaignTarget
        from sqlalchemy import or_
        now_utc = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            # Find overdue targets (need replanning)
            overdue = db.query(CampaignTarget).filter(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.status == 'scheduled',
                or_(CampaignTarget.planned_send_at == None, CampaignTarget.planned_send_at <= now_utc)  # type: ignore
            ).order_by(asc(CampaignTarget.created_at)).all()
            
            # Find latest non-overdue scheduled target to plan AFTER it
            latest_valid = db.query(CampaignTarget).filter(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.status == 'scheduled',
                CampaignTarget.planned_send_at > now_utc
            ).order_by(CampaignTarget.planned_send_at.desc()).first()
        except Exception:
            overdue = []
            latest_valid = None
        finally:
            db.close()

        if not overdue:
            return
        
        pending = overdue

        # Development mode: simple sequential planning from current time
        if settings.development_mode:
            assignments: list[tuple[str, object]] = []
            start_time = now_utc
            
            # If there are non-overdue targets, plan after them
            if latest_valid and latest_valid.planned_send_at and latest_valid.planned_send_at > now_utc:
                start_time = latest_valid.planned_send_at
                self.logger.info("Replanning (DEV MODE): starting after latest valid target at %s", latest_valid.planned_send_at)
            else:
                self.logger.info("Replanning (DEV MODE): starting from now")
            
            for i, tgt in enumerate(pending):
                planned_utc = start_time + timedelta(seconds=15 * (i + 1))
                assignments.append((tgt.id, planned_utc))
            
            if assignments:
                db = SessionLocal()
                try:
                    CampaignTargetCRUD(db).set_planned_send_at_bulk(campaign_id, assignments)
                    earliest = min(p for _, p in assignments)
                    CampaignCRUD(db).set_next_wake_at(campaign_id, earliest)
                finally:
                    db.close()
                self.logger.info("Replanning (DEV MODE): replanned %d targets sequentially", len(assignments))
            return

        # Production mode: respect work hours and daily limits
        # Parse timezone: supports full timezone names (e.g., "Europe/Warsaw") or offsets (e.g., "+2", "-5")
        def parse_tz(offset_str: Optional[str]) -> timezone:
            if not offset_str:
                return timezone.utc
            s = str(offset_str).strip()
            
            # First try to parse as full timezone name (e.g., "Europe/Warsaw", "America/Toronto")
            try:
                tz = pytz.timezone(s)
                return tz
            except (pytz.UnknownTimeZoneError, AttributeError):
                pass
            
            # If not a timezone name, try to parse as offset (e.g., "+2", "-5", "+02:00")
            try:
                hours = int(s)
                return timezone(timedelta(hours=hours))
            except Exception:
                try:
                    sign = 1 if s.startswith("+") else -1 if s.startswith("-") else 1
                    parts = s[1:].split(":") if s[:1] in "+-" else s.split(":")
                    h = int(parts[0]) if parts and parts[0] else 0
                    m = int(parts[1]) if len(parts) > 1 else 0
                    return timezone(sign * timedelta(hours=h, minutes=m))
                except Exception:
                    return timezone.utc

        tzinfo = parse_tz(tz_offset)
        slot_count = max(1, int(daily_limit) if daily_limit and daily_limit > 0 else len(pending))
        work_hours = settings.campaign_work_end_hour - settings.campaign_work_start_hour
        window_seconds = work_hours * 60 * 60
        slot_sec = max(1, window_seconds // slot_count)

        # Determine starting point: AFTER latest_valid or from current time
        if latest_valid and latest_valid.planned_send_at:
            # Plan after the last non-overdue target
            start_from_utc = latest_valid.planned_send_at + timedelta(seconds=1)
            start_from_local = start_from_utc.astimezone(tzinfo)
            self.logger.info("Replanning: starting after latest valid target at %s", latest_valid.planned_send_at)
        else:
            # No non-overdue targets, start from current time
            start_from_utc = now_utc
            start_from_local = now_utc.astimezone(tzinfo)
            self.logger.info("Replanning: no valid targets, starting from now")
        
        day_start_local = datetime.combine(start_from_local.date(), time(hour=settings.campaign_work_start_hour, minute=0, tzinfo=tzinfo))
        day_end_local = datetime.combine(start_from_local.date(), time(hour=settings.campaign_work_end_hour, minute=0, tzinfo=tzinfo))
        
        if start_from_local < day_start_local:
            base_day_start_local = day_start_local
            start_slot_index = 0
        elif start_from_local >= day_end_local:
            base_day_start_local = day_start_local + timedelta(days=1)
            start_slot_index = 0
        else:
            base_day_start_local = day_start_local
            elapsed = (start_from_local - day_start_local).total_seconds()
            start_slot_index = int(elapsed // slot_sec) + 1  # next slot

        assignments: list[tuple[str, object]] = []
        for i, tgt in enumerate(pending):
            absolute_slot = start_slot_index + i
            day_offset = absolute_slot // slot_count
            slot_in_day = absolute_slot % slot_count
            slot_start_local = base_day_start_local + timedelta(days=day_offset, seconds=slot_in_day * slot_sec)
            jitter = random.uniform(0.0, float(slot_sec))
            planned_local = slot_start_local + timedelta(seconds=jitter)
            planned_utc = planned_local.astimezone(timezone.utc)
            assignments.append((tgt.id, planned_utc))

        if not assignments:
            return

        db = SessionLocal()
        try:
            CampaignTargetCRUD(db).set_planned_send_at_bulk(campaign_id, assignments)
            earliest = min(p for _, p in assignments)
            CampaignCRUD(db).set_next_wake_at(campaign_id, earliest)
        finally:
            db.close()