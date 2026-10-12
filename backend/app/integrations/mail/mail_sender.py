from typing import Optional

import httpx

from app.core.logger import get_logger
from app.core.settings import settings
from app.schemas.email import PersonalizedEmail, EmailSendResult
from app.services.recipient_registry import add_recipient
from app.database.connection import SessionLocal
from app.database.crud import SenderAccountCRUD, MailApiUrlCRUD
from app.database.models import SenderAccount, MailApiUrl

# Integration wrapper around an external email sending API/provider.


class MailSender:
    """Sends emails via an external provider.

    This class encapsulates all HTTP calls to the external email provider. It
    receives `PersonalizedEmail` objects and performs the actual send.
    """

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    async def send_email(self, *, email: PersonalizedEmail, from_email: str, to_email: str, use_corporate: bool = False, sender_name: str = None, is_list_campaign: bool = False, force_send: bool = False) -> EmailSendResult:
        """Send a single email.

        Parameters
        ----------
        email: PersonalizedEmail
            Email content to send.
        from_email: str
            Sender address.
        to_email: str
            Recipient address.
        use_corporate: bool
            If True, use corporate email server (MAIL_API_URL_2), otherwise use personal (MAIL_API_URL).
        sender_name: str
            Sender name for signature (e.g., "John Doe").
        is_list_campaign: bool
            True if campaign was created from email list, False if from database objects.
        """
        # Dev mode: only log to console for database campaigns, but actually send for list campaigns or forced sends
        if settings.development_mode and not is_list_campaign and not force_send:
            self.logger.info(
                "[DEV] Would send (from=%s, to=%s, subject=%r)\nBody:\n%s",
                from_email,
                to_email,
                email.subject,
                email.body,
            )
            return EmailSendResult(
                success=True,
                message_id=None,
                status="dev_mode_no_send",
                provider="dev",
                from_email=from_email,
                to_email=to_email,
                error=None,
            )

        # Get API URL from database based on sender account
        db = SessionLocal()
        api_url = None
        account: SenderAccount | None = None
        try:
            # Find sender account by email
            account_crud = SenderAccountCRUD(db)
            account = account_crud.get_by_email(from_email)
            if not account:
                return EmailSendResult(
                    success=False,
                    message_id=None,
                    status=None,
                    provider=None,
                    from_email=from_email,
                    to_email=to_email,
                    error=f"Sender account {from_email} not found",
                )
            if not account.password:
                return EmailSendResult(
                    success=False,
                    message_id=None,
                    status=None,
                    provider=None,
                    from_email=from_email,
                    to_email=to_email,
                    error=f"Sender account {from_email} is missing password",
                )

            if account and account.mail_api_url_id:
                # Get URL from account's linked MailApiUrl
                url_obj = MailApiUrlCRUD(db).get_by_id(account.mail_api_url_id)
                if url_obj and url_obj.is_active:
                    base_url = url_obj.url.rstrip('/')
                    endpoint = url_obj.endpoint.lstrip('/')
                    api_url = f"{base_url}/{endpoint}"

        except Exception as exc:
            self.logger.warning("Failed to get API URL from database: %s, falling back to settings", str(exc))
            base_url = settings.mail_api_url_2 if use_corporate else settings.mail_api_url
            if base_url:
                endpoint = settings.mail_api_endpoint.lstrip('/')
                api_url = f"{base_url.rstrip('/')}/{endpoint}"
        finally:
            db.close()

        if not api_url:
            return EmailSendResult(
                success=False,
                message_id=None,
                status=None,
                provider=None,
                from_email=from_email,
                to_email=to_email,
                error=f"MAIL_API_URL is not configured for account {from_email}",
            )

        smtp_host = account.smtp_host if account else None
        smtp_port = account.smtp_port if account else None
        if account and account.server_id == "2":
            smtp_host = smtp_host or "mail.joga.space"
            smtp_port = smtp_port or 465

        # Add signature to email body if sender name is provided
        email_body = email.body
        if sender_name:
            signature = f"\n\n{sender_name}"
            email_body = email.body + signature

        self.logger.info(
            "Mail: sending (from=%s, to=%s, subject=%r, use_corporate=%s, sender=%s, url=%s)",
            from_email,
            to_email,
            email.subject,
            use_corporate,
            sender_name or "Unknown",
            api_url,
        )

        payload = {
            "from_email": from_email,
            "to_email": to_email,
            "subject": email.subject,
            "body": email_body,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "password": account.password if account else None,
            "selenium_required": account.selenium_required if account else False,
        }
        if sender_name:
            payload["sender_name"] = sender_name
        if use_corporate is not None:
            payload["use_corporate"] = use_corporate
        if account and account.first_name:
            payload.setdefault("account_first_name", account.first_name)
        if account and account.last_name:
            payload.setdefault("account_last_name", account.last_name)

        if payload.get("password") is None:
            return EmailSendResult(
                success=False,
                message_id=None,
                status=None,
                provider=None,
                from_email=from_email,
                to_email=to_email,
                error=f"Sender account {from_email} is missing SMTP password",
            )

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(api_url, json=payload)
                is_json = response.headers.get("content-type", "").startswith("application/json")

                # Log full response for debugging
                self.logger.info(
                    "Mail: response received (status_code=%d, content_type=%s, is_json=%s)",
                    response.status_code,
                    response.headers.get("content-type", "unknown"),
                    is_json,
                )

                # Check HTTP status first
                http_success = 200 <= response.status_code < 300

                # Parse response data
                if is_json:
                    try:
                        data = response.json()
                    except Exception as e:
                        self.logger.error(f"Failed to parse JSON response: {e}")
                        data = {}
                else:
                    data = {}

                # Extract fields from mailing_sender response format:
                # EmailMessageOut: { status: str, from_email: str, to_email: str, error_message?: str }
                response_status = data.get("status", "")
                error_msg = data.get("error_message") or data.get("error") or data.get("detail") or data.get("message")

                # Determine success: HTTP must be OK AND response status must be "success"
                success = http_success and response_status == "success"

                # If HTTP failed, override with HTTP error
                if not http_success and not error_msg:
                    if is_json:
                        error_msg = f"HTTP {response.status_code}"
                    else:
                        try:
                            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        except Exception:
                            error_msg = f"HTTP {response.status_code}"

                result = EmailSendResult(
                    success=success,
                    message_id=None,  # mailing_sender doesn't return message_id
                    status=response_status or (f"HTTP {response.status_code}" if not http_success else None),
                    provider=None,  # mailing_sender doesn't return provider
                    from_email=data.get("from_email") or from_email,
                    to_email=data.get("to_email") or to_email,
                    error=error_msg,
                )

                if success:
                    self.logger.info(
                        "Mail: sent successfully (status=%s, from=%s, to=%s)",
                        result.status,
                        result.from_email,
                        result.to_email,
                    )
                    add_recipient(to_email)
                else:
                    self.logger.warning(
                        "Mail: failed (status_code=%d, status=%s, error=%s)",
                        response.status_code,
                        result.status,
                        result.error,
                    )
                return result
        except Exception as exc:
            self.logger.error(
                "Mail: exception (error=%s)",
                str(exc),
            )
            return EmailSendResult(
                success=False,
                message_id=None,
                status=None,
                provider=None,
                from_email=from_email,
                to_email=to_email,
                error=str(exc),
            ) 