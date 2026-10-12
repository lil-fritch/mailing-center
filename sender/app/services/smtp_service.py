import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.schemas.email import EmailMessageIn, EmailAccount
from app.core.logger import logger
from app.core.errors import AppError


class SMTPService:
    @staticmethod
    async def send_email(message: EmailMessageIn, account: EmailAccount) -> None:
        if not account.smtp_host or not account.smtp_port:
            raise AppError(
                message="SMTP configuration missing",
                details={"email": account.email}
            )

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = message.subject
        msg['From'] = message.from_email
        msg['To'] = message.to_email
        msg.attach(MIMEText(message.body, 'plain'))

        try:
            if account.smtp_port == 465:
                smtp = aiosmtplib.SMTP(
                    hostname=account.smtp_host,
                    port=account.smtp_port,
                    use_tls=True,
                    timeout=60,
                )
            else:  # STARTTLS для порту 587
                smtp = aiosmtplib.SMTP(
                    hostname=account.smtp_host,
                    port=account.smtp_port,
                    start_tls=True,
                    timeout=60
                )

            await smtp.connect()
            await smtp.login(account.email, account.password)
            await smtp.send_message(msg)
            await smtp.quit()

            logger.info(f"Email sent successfully via SMTP from {message.from_email} to {message.to_email}")

        except Exception as e:
            logger.error(f"Unexpected error during SMTP sending: {str(e)}")
            raise AppError(
                message=f"Unexpected error: {str(e)}",
                details={"error": str(e)}
            )



smtp_service = SMTPService() 