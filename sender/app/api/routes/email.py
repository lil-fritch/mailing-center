from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.schemas.email import EmailMessageIn, EmailMessageOut
from app.services.email_service import email_service
from app.services.history_service import email_history
from app.services.cleanup_service import screenshot_cleaner

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/send", response_model=EmailMessageOut)
async def send_email(message: EmailMessageIn) -> EmailMessageOut:
    """Відправити лист негайно через SMTP або Selenium"""
    return await email_service.send_email(message)


@router.get("/history")
async def get_history(limit: Optional[int] = None):
    """Отримати історію відправлених листів"""
    items = email_history.list(limit=limit)
    return [
        {
            "from_email": i.from_email,
            "to_email": i.to_email,
            "subject": i.subject,
            "body": i.body,
            "sent_at": i.sent_at.isoformat(),
        }
        for i in items
    ]


@router.post("/history/clear")
async def clear_history():
    """Очистити історію відправлених листів"""
    email_history.clear()
    return {"status": "cleared"}


# Керування скриншотами Selenium
@router.get("/screenshots/runs")
async def list_screenshot_runs(account_email: Optional[EmailStr] = None):
    """Список всіх запусків зі скриншотами"""
    runs = [str(p) for p in screenshot_cleaner.list_runs(account_email)]
    return {"runs": runs, "count": len(runs)}


class CleanupScreenshotsIn(BaseModel):
    older_than_days: int = 7
    account_email: Optional[EmailStr] = None
    dry_run: bool = True
    limit: Optional[int] = None
    remove_empty_parents: bool = True


@router.post("/screenshots/cleanup")
async def cleanup_screenshots(payload: CleanupScreenshotsIn):
    """Очистити старі скриншоти"""
    result = screenshot_cleaner.cleanup(
        older_than_days=payload.older_than_days,
        account_email=payload.account_email,
        dry_run=payload.dry_run,
        limit=payload.limit,
        remove_empty_parents=payload.remove_empty_parents,
    )
    return result
