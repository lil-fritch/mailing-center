from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class EmailAccount(BaseModel):
    email: EmailStr
    password: str
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    selenium_required: bool = False


class EmailMessageIn(BaseModel):
    """Вхідна модель для запиту на відправку листа."""

    from_email: EmailStr
    to_email: EmailStr
    subject: str
    body: str
    password: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    selenium_required: bool = False
    sender_name: Optional[str] = None


class EmailMessageOut(BaseModel):
    """Вихідна модель з результатом відправки."""

    status: str
    from_email: EmailStr
    to_email: EmailStr
    error_message: Optional[str] = None


class HistoryItem(BaseModel):
    from_email: EmailStr
    to_email: EmailStr
    subject: str
    body: str
    sent_at: datetime
