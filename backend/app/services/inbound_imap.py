from __future__ import annotations

import asyncio
import email
import imaplib
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator, List, Set
import socket
import concurrent.futures

from app.core.logger import get_logger
from app.core.settings import settings
from app.integrations.mail import load_sender_accounts_from_db
from app.schemas.inbound import InboundMessage


# Blocklist functionality removed - no more account blocking


class InboundIMAPPoller:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        # Initial load of accounts from database
        self.accounts = []
        self.refresh_accounts()
        
        # Thread pool for IMAP operations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=settings.imap_thread_pool_size)

    def refresh_accounts(self) -> None:
        """Reload active sender accounts from the database."""
        try:
            accounts_1 = load_sender_accounts_from_db(active_only=True, server_id="1")
            accounts_2 = load_sender_accounts_from_db(active_only=True, server_id="2")
            new_accounts = accounts_1 + accounts_2
            old_count = len(self.accounts)
            self.accounts = new_accounts
            self.logger.info(
                "IMAP: refreshed accounts for polling: %d -> %d (server1=%d, server2=%d)",
                old_count,
                len(self.accounts),
                len(accounts_1),
                len(accounts_2),
            )
        except Exception as exc:
            self.logger.warning("IMAP: failed to refresh accounts: %s", str(exc))

    def _connect(self, host: str | None, port: int, use_ssl: bool) -> imaplib.IMAP4:
        timeout = 20 
        socket.setdefaulttimeout(timeout)
        if use_ssl:
            return imaplib.IMAP4_SSL(host or "imap.gmail.com", port, timeout=timeout)
        return imaplib.IMAP4(host or "imap.gmail.com", port, timeout=timeout)

    def _poll_account_sync(self, acc) -> List[InboundMessage]:
        """Synchronous method to poll a single account - runs in thread pool"""
        messages = []
        try:
            if not acc.email:
                raise RuntimeError("IMAP account email missing in configuration")
            if not acc.password:
                raise RuntimeError(f"IMAP password missing for account {acc.email}")

            imap = self._connect(acc.imap_host, acc.imap_port, acc.imap_ssl)
                
            try:
                imap.login(acc.email, acc.password)
                self.logger.debug("IMAP: login OK for %s", acc.email)
            except Exception as login_error:
                self.logger.warning(
                    "IMAP: login failed for %s: %s", 
                    acc.email, 
                    str(login_error)
                )
                return messages

            imap.select("INBOX")
            status, data = imap.search(None, "UNSEEN")
            if status != "OK":
                self.logger.warning(f"IMAP search failed for {acc.email} with status {status}")
                imap.logout()
                return messages

            uids = data[0].split() if data and isinstance(data[0], (bytes, bytearray)) else []
            if len(uids) > 0:
                self.logger.info("IMAP: %s found %d unseen message(s)", acc.email, len(uids))

            for num in uids:
                try:
                    status, msg_data = imap.fetch(num, "(RFC822)")
                    if status != "OK" or not msg_data:
                        self.logger.warning(f"IMAP fetch failed for {acc.email} (uid {num!r})")
                        continue
                    _, raw = msg_data[0]
                    msg = email.message_from_bytes(raw)
                    subject = msg.get("Subject", "")
                    if subject:
                        # Handle email.header.Header objects properly
                        try:
                            subject = str(subject)
                        except:
                            subject = ""
                    from_hdr = msg.get("From", "")
                    if from_hdr:
                        try:
                            from_hdr = str(from_hdr)
                        except:
                            from_hdr = ""
                    name, addr = email.utils.parseaddr(from_hdr)
                    from_addr = addr or from_hdr
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = (part.get_payload(decode=True) or b"").decode(errors="ignore")
                                break
                    else:
                        body = (msg.get_payload(decode=True) or b"").decode(errors="ignore")

                    # Extract email headers for thread matching
                    message_id = msg.get("Message-ID", "").strip()
                    in_reply_to = msg.get("In-Reply-To", "").strip()
                    references = msg.get("References", "").strip()
                    
                    # Clean up headers (remove angle brackets if present)
                    if message_id:
                        message_id = message_id.strip("<>")
                    if in_reply_to:
                        in_reply_to = in_reply_to.strip("<>")
                    if references:
                        # References can contain multiple message IDs, keep as is
                        references = references.strip()

                    try:
                        inbound = InboundMessage(
                            id=str(num.decode()),
                            account_email=acc.email,
                            from_email=from_addr,
                            subject=subject,
                            body=body,
                            received_at=datetime.now(timezone.utc),
                            message_id=message_id if message_id else None,
                            in_reply_to=in_reply_to if in_reply_to else None,
                            references=references if references else None,
                        )
                    except Exception as e:
                        self.logger.warning(f"IMAP: failed to create InboundMessage for {acc.email} (uid {num!r}): {e}")
                        continue

                    # Mark as seen
                    try:
                        imap.store(num, "+FLAGS", r"(\Seen)")
                    except Exception as exc:
                        self.logger.warning("IMAP: failed to mark seen uid=%s for %s: %s", inbound.id, acc.email, str(exc))

                    self.logger.info(
                        "IMAP: %s new message uid=%s subject=%r from=%s",
                        acc.email,
                        inbound.id,
                        inbound.subject,
                        inbound.from_email,
                    )
                    messages.append(inbound)

                except Exception as exc:
                    self.logger.warning("IMAP: failed to process uid=%s for %s: %s", num, acc.email, str(exc))

            imap.logout()

        except Exception as exc:
            self.logger.warning("IMAP: failed to poll %s: %s", acc.email, str(exc))

        return messages

    async def poll_new_messages_async(self) -> AsyncGenerator[InboundMessage, None]:
        """Asynchronous method to poll all accounts in parallel"""
        # Hot-reload accounts list before each polling cycle
        self.refresh_accounts()
        if not self.accounts:
            return

        start_time = asyncio.get_event_loop().time()
        self.logger.info("IMAP: starting async polling of %d accounts", len(self.accounts))

        # Create tasks for all accounts
        tasks = []
        for acc in self.accounts:
            task = asyncio.get_event_loop().run_in_executor(
                self.executor, 
                self._poll_account_sync, 
                acc
            )
            tasks.append(task)

        # Wait for all tasks to complete
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_messages = 0
            # Yield all messages from all accounts
            for result in results:
                if isinstance(result, Exception):
                    self.logger.warning("IMAP: account polling failed: %s", str(result))
                else:
                    for message in result:
                        total_messages += 1
                        yield message
            
            elapsed = asyncio.get_event_loop().time() - start_time
            self.logger.info("IMAP: async polling completed in %.2fs, found %d messages", elapsed, total_messages)
                        
        except Exception as exc:
            self.logger.error("IMAP: polling failed: %s", str(exc))

    def poll_new_messages(self) -> Generator[InboundMessage, None, None]:
        """Synchronous method for backward compatibility"""
        # Hot-reload accounts list before each polling cycle
        self.refresh_accounts()
        for acc in self.accounts:
            try:
                if not acc.email:
                    raise RuntimeError("IMAP account email missing in configuration")
                if not acc.password:
                    raise RuntimeError(f"IMAP password missing for account {acc.email}")

                imap = self._connect(acc.imap_host, acc.imap_port, acc.imap_ssl)
                
                try:
                    imap.login(acc.email, acc.password)
                    self.logger.debug("IMAP: login OK for %s", acc.email)
                except Exception as login_error:
                    self.logger.warning(
                        "IMAP: login failed for %s: %s", 
                        acc.email, 
                        str(login_error)
                    )
                    continue

                imap.select("INBOX")
                status, data = imap.search(None, "UNSEEN")
                if status != "OK":
                    self.logger.warning(f"IMAP search failed for {acc.email} with status {status}")
                    imap.logout()
                    continue

                uids = data[0].split() if data and isinstance(data[0], (bytes, bytearray)) else []
                if len(uids) > 0:
                    self.logger.info("IMAP: %s found %d unseen message(s)", acc.email, len(uids))

                for num in uids:
                    try:
                        status, msg_data = imap.fetch(num, "(RFC822)")
                        if status != "OK" or not msg_data:
                            self.logger.warning(f"IMAP fetch failed for {acc.email} (uid {num!r})")
                            continue
                        _, raw = msg_data[0]
                        msg = email.message_from_bytes(raw)
                        subject = msg.get("Subject", "")
                        if subject:
                            # Handle email.header.Header objects properly
                            try:
                                subject = str(subject)
                            except:
                                subject = ""
                        from_hdr = msg.get("From", "")
                        if from_hdr:
                            try:
                                from_hdr = str(from_hdr)
                            except:
                                from_hdr = ""
                        name, addr = email.utils.parseaddr(from_hdr)
                        from_addr = addr or from_hdr
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = (part.get_payload(decode=True) or b"").decode(errors="ignore")
                                    break
                        else:
                            body = (msg.get_payload(decode=True) or b"").decode(errors="ignore")

                        # Extract email headers for thread matching
                        message_id = msg.get("Message-ID", "").strip()
                        in_reply_to = msg.get("In-Reply-To", "").strip()
                        references = msg.get("References", "").strip()
                        
                        # Clean up headers (remove angle brackets if present)
                        if message_id:
                            message_id = message_id.strip("<>")
                        if in_reply_to:
                            in_reply_to = in_reply_to.strip("<>")
                        if references:
                            # References can contain multiple message IDs, keep as is
                            references = references.strip()

                        inbound = InboundMessage(
                            id=str(num.decode()),
                            account_email=acc.email,
                            from_email=from_addr,
                            subject=subject,
                            body=body,
                            received_at=datetime.now(timezone.utc),
                            message_id=message_id if message_id else None,
                            in_reply_to=in_reply_to if in_reply_to else None,
                            references=references if references else None,
                        )

                        # Mark as seen
                        try:
                            imap.store(num, "+FLAGS", r"(\Seen)")
                        except Exception as exc:
                            self.logger.warning("IMAP: failed to mark seen uid=%s for %s: %s", inbound.id, acc.email, str(exc))

                        self.logger.info(
                            "IMAP: %s new message uid=%s subject=%r from=%s",
                            acc.email,
                            inbound.id,
                            inbound.subject,
                            inbound.from_email,
                        )
                        yield inbound

                    except Exception as exc:
                        self.logger.warning("IMAP: failed to process uid=%s for %s: %s", num, acc.email, str(exc))

                imap.logout()

            except Exception as exc:
                self.logger.warning("IMAP: failed to poll %s: %s", acc.email, str(exc))

    def __del__(self):
        """Cleanup thread pool"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# Global instance
poller = InboundIMAPPoller()