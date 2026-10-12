import asyncio
from abc import ABC, abstractmethod

from app.schemas.email import EmailMessageIn, EmailMessageOut, EmailAccount
from app.core.errors import AppError
from app.services.smtp_service import smtp_service
from app.services.selenium.op_pl import OPPLSender
from app.core.logger import logger

# Global lock to serialize Selenium-based sending to avoid conflicts
_selenium_send_lock = asyncio.Lock()


class BaseSender(ABC):
    @abstractmethod
    async def send(self, message: EmailMessageIn, account: EmailAccount) -> None:  # pragma: no cover - interface
        pass


class SMTPSender(BaseSender):
    async def send(self, message: EmailMessageIn, account: EmailAccount) -> None:
        await smtp_service.send_email(message, account)


class SeleniumSender(BaseSender):
    async def send(self, message: EmailMessageIn, account: EmailAccount) -> None:
        async with _selenium_send_lock:
            sender = OPPLSender(account)
            await sender.send_email(message)


class EmailService:
    @staticmethod
    async def send_email(message: EmailMessageIn) -> EmailMessageOut:
        try:
            if message.selenium_required:
                if not message.password:
                    raise AppError(message="Missing password for Selenium login", details={"email": message.from_email})
                account = EmailAccount(
                    email=message.from_email,
                    password=message.password,
                    selenium_required=True,
                )
                sender: BaseSender = SeleniumSender()
            else:
                if not message.smtp_host or message.smtp_port is None or not message.password:
                    raise AppError(
                        message="SMTP configuration missing",
                        details={
                            "email": message.from_email,
                            "smtp_host": message.smtp_host,
                            "smtp_port": message.smtp_port,
                        },
                    )
                account = EmailAccount(
                    email=message.from_email,
                    password=message.password,
                    smtp_host=message.smtp_host,
                    smtp_port=message.smtp_port,
                    selenium_required=False,
                )
                sender = SMTPSender()

            logger.info(
                "Sending email from %s via %s",
                message.from_email,
                "selenium" if account.selenium_required else f"SMTP({account.smtp_host}:{account.smtp_port})",
            )

            await sender.send(message, account)

            return EmailMessageOut(
                status="success",
                from_email=message.from_email,
                to_email=message.to_email,
            )

        except AppError as e:
            logger.warning("Sending error for %s: %s", message.from_email, e.message)
            return EmailMessageOut(
                status="error",
                from_email=message.from_email,
                to_email=message.to_email,
                error_message=e.message,
            )
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.error(f"Unexpected error sending email: {e}")
            return EmailMessageOut(
                status="error",
                from_email=message.from_email,
                to_email=message.to_email,
                error_message=f"Unexpected error: {str(e)}",
            )


email_service = EmailService() 