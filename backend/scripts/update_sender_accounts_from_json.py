import json
from pathlib import Path
from typing import Any, Dict, List

from app.database.connection import SessionLocal
from app.database.models import SenderAccount
from app.core.logger import get_logger


logger = get_logger(__name__)

CORPORATE_SMTP_HOST = "mail.joga.space"
CORPORATE_SMTP_PORT = 465

DEFAULT_ACCOUNTS: List[Dict[str, Any]] = [
    {
        "email": "vita.rursus@gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "selenium_required": False,
    },
    {
        "email": "saranamaskar@op.pl",
        "selenium_required": True,
    },
    {
        "email": "kasia.nowak97@op.pl",
        "selenium_required": True,
    },
    {
        "email": "agnieszka.wiszniewska@op.pl",
        "selenium_required": True,
    },
    {
        "email": "zuza.namaste@gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "selenium_required": False,
    },
    {
        "email": "teresa.om.kaminska@o2.pl",
        "smtp_host": "poczta.o2.pl",
        "smtp_port": 465,
        "selenium_required": False,
    },
    {
        "email": "vita.ciepla@wp.pl",
        "smtp_host": "smtp.wp.pl",
        "smtp_port": 465,
        "selenium_required": False,
    },
    {
        "email": "tereza.kaminska@interia.pl",
        "smtp_host": "poczta.interia.pl",
        "smtp_port": 465,
        "selenium_required": False,
    },
    {
        "email": "helena@wydarzenia.yoga",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
    {
        "email": "adam@wydarzenia.yoga",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
    {
        "email": "shanti@wydarzenia.yoga",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
    {
        "email": "yogina@wydarzenia.yoga",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
    {
        "email": "namaste@wydarzenia.yoga",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
    {
        "email": "namaste@joga.space",
        "smtp_host": CORPORATE_SMTP_HOST,
        "smtp_port": CORPORATE_SMTP_PORT,
        "selenium_required": False,
    },
]

DEFAULT_JSON_PATH = Path(__file__).with_name("sender_accounts_defaults.json")


def load_account_records() -> List[Dict[str, Any]]:
    if DEFAULT_JSON_PATH.exists():
        try:
            with DEFAULT_JSON_PATH.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, list):
                return payload
            logger.warning(
                "Defaults file %s does not contain a list; using embedded defaults",
                DEFAULT_JSON_PATH,
            )
        except Exception as exc:
            logger.warning(
                "Failed to read %s (%s); using embedded defaults",
                DEFAULT_JSON_PATH,
                exc,
            )
    return DEFAULT_ACCOUNTS


def update_sender_accounts() -> None:
    records = load_account_records()
    record_map: Dict[str, Dict[str, Any]] = {
        item["email"]: item
        for item in records
        if isinstance(item, dict) and item.get("email")
    }

    session = SessionLocal()
    updated = 0
    missing = 0
    try:
        for email, data in record_map.items():
            account: SenderAccount | None = (
                session.query(SenderAccount)
                .filter(SenderAccount.email == email)
                .first()
            )
            if not account:
                missing += 1
                continue

            smtp_host = data.get("smtp_host")
            smtp_port = data.get("smtp_port")
            selenium_required = data.get("selenium_required")

            if not smtp_host and account.server_id == "2":
                smtp_host = CORPORATE_SMTP_HOST
            if not smtp_port and account.server_id == "2":
                smtp_port = CORPORATE_SMTP_PORT

            if smtp_host is not None:
                account.smtp_host = smtp_host or None
            elif not account.smtp_host and account.server_id == "2":
                account.smtp_host = CORPORATE_SMTP_HOST

            if smtp_port is not None:
                account.smtp_port = int(smtp_port) if smtp_port != "" else None
            elif not account.smtp_port and account.server_id == "2":
                account.smtp_port = CORPORATE_SMTP_PORT

            if selenium_required is not None:
                account.selenium_required = bool(selenium_required)

            updated += 1

        # Ensure all corporate accounts have defaults even if not listed explicitly
        corporate_accounts = (
            session.query(SenderAccount)
            .filter(SenderAccount.server_id == "2")
            .all()
        )
        for account in corporate_accounts:
            changed = False
            if not account.smtp_host:
                account.smtp_host = CORPORATE_SMTP_HOST
                changed = True
            if not account.smtp_port:
                account.smtp_port = CORPORATE_SMTP_PORT
                changed = True
            if changed:
                updated += 1

        session.commit()
    finally:
        session.close()

    logger.info(
        "Updated %d sender accounts; %d emails not found",
        updated,
        missing,
    )
    print(f"Updated {updated} accounts. {missing} emails were not found in DB.")


def main() -> None:
    update_sender_accounts()


if __name__ == "__main__":
    main()
