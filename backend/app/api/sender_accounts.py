"""API endpoints for managing sender accounts and mail API URLs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.database import get_db
from app.database.crud import (
    MailApiUrlCRUD, SenderAccountCRUD,
    create_mail_api_url, get_mail_api_url, get_mail_api_urls,
    create_sender_account, get_sender_account, get_sender_accounts,
)
from app.database.models import MailApiUrl, SenderAccount
from pydantic import BaseModel


router = APIRouter()


# ==================== Schemas ====================

class MailApiUrlCreate(BaseModel):
    name: str
    url: str
    endpoint: str = "/email/send"
    is_active: bool = True


class MailApiUrlUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    endpoint: Optional[str] = None
    is_active: Optional[bool] = None


class MailApiUrlResponse(BaseModel):
    id: str
    name: str
    url: str
    endpoint: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class SenderAccountCreate(BaseModel):
    email: str
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: int = 993
    imap_ssl: bool = True
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    selenium_required: bool = False
    server_id: str = "1"
    mail_api_url_id: Optional[str] = None
    is_active: bool = True


class SenderAccountUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_ssl: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    selenium_required: Optional[bool] = None
    server_id: Optional[str] = None
    mail_api_url_id: Optional[str] = None
    is_active: Optional[bool] = None


class SenderAccountResponse(BaseModel):
    id: str
    email: str
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: int
    imap_ssl: bool
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    selenium_required: bool
    server_id: str
    mail_api_url_id: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== Mail API URLs ====================

@router.post("/mail-api-urls", response_model=MailApiUrlResponse)
async def create_mail_api_url_endpoint(
    url_data: MailApiUrlCreate,
    db: Session = Depends(get_db)
):
    """Create a new mail API URL"""
    crud = MailApiUrlCRUD(db)
    url_obj = crud.create({
        "id": str(uuid.uuid4()),
        **url_data.model_dump()
    })
    return MailApiUrlResponse(
        id=url_obj.id,
        name=url_obj.name,
        url=url_obj.url,
        endpoint=url_obj.endpoint,
        is_active=url_obj.is_active,
        created_at=url_obj.created_at.isoformat() if url_obj.created_at else None,
        updated_at=url_obj.updated_at.isoformat() if url_obj.updated_at else None,
    )


@router.get("/mail-api-urls", response_model=List[MailApiUrlResponse])
async def list_mail_api_urls(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all mail API URLs"""
    crud = MailApiUrlCRUD(db)
    urls = crud.get_all(active_only=active_only)
    return [
        MailApiUrlResponse(
            id=url.id,
            name=url.name,
            url=url.url,
            endpoint=url.endpoint,
            is_active=url.is_active,
            created_at=url.created_at.isoformat() if url.created_at else None,
            updated_at=url.updated_at.isoformat() if url.updated_at else None,
        )
        for url in urls
    ]


@router.get("/mail-api-urls/{url_id}", response_model=MailApiUrlResponse)
async def get_mail_api_url_endpoint(
    url_id: str,
    db: Session = Depends(get_db)
):
    """Get a mail API URL by ID"""
    crud = MailApiUrlCRUD(db)
    url_obj = crud.get_by_id(url_id)
    if not url_obj:
        raise HTTPException(status_code=404, detail=f"Mail API URL {url_id} not found")
    return MailApiUrlResponse(
        id=url_obj.id,
        name=url_obj.name,
        url=url_obj.url,
        endpoint=url_obj.endpoint,
        is_active=url_obj.is_active,
        created_at=url_obj.created_at.isoformat() if url_obj.created_at else None,
        updated_at=url_obj.updated_at.isoformat() if url_obj.updated_at else None,
    )


@router.put("/mail-api-urls/{url_id}", response_model=MailApiUrlResponse)
async def update_mail_api_url_endpoint(
    url_id: str,
    url_data: MailApiUrlUpdate,
    db: Session = Depends(get_db)
):
    """Update a mail API URL"""
    crud = MailApiUrlCRUD(db)
    update_data = {k: v for k, v in url_data.model_dump().items() if v is not None}
    url_obj = crud.update(url_id, update_data)
    if not url_obj:
        raise HTTPException(status_code=404, detail=f"Mail API URL {url_id} not found")
    return MailApiUrlResponse(
        id=url_obj.id,
        name=url_obj.name,
        url=url_obj.url,
        endpoint=url_obj.endpoint,
        is_active=url_obj.is_active,
        created_at=url_obj.created_at.isoformat() if url_obj.created_at else None,
        updated_at=url_obj.updated_at.isoformat() if url_obj.updated_at else None,
    )


@router.delete("/mail-api-urls/{url_id}")
async def delete_mail_api_url_endpoint(
    url_id: str,
    db: Session = Depends(get_db)
):
    """Delete a mail API URL"""
    crud = MailApiUrlCRUD(db)
    success = crud.delete(url_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Mail API URL {url_id} not found")
    return {"message": f"Mail API URL {url_id} deleted successfully"}


# ==================== Sender Accounts ====================

def _get_default_mail_api_url_id(db: Session, server_id: str) -> Optional[str]:
    """Отримати mail_api_url_id за замовчуванням на основі server_id"""
    url_crud = MailApiUrlCRUD(db)
    # Для server_id="1" шукаємо "Personal", для server_id="2" - "Corporate"
    url_name = "Personal" if server_id == "1" else "Corporate"
    urls = url_crud.get_all(active_only=True)
    for url in urls:
        if url.name.lower() == url_name.lower():
            return url.id
    return None


@router.post("/sender-accounts", response_model=SenderAccountResponse)
async def create_sender_account_endpoint(
    account_data: SenderAccountCreate,
    db: Session = Depends(get_db)
):
    """Create a new sender account"""
    # Auto-set mail_api_url_id if not provided based on server_id
    account_dict = account_data.model_dump()
    if not account_dict.get("mail_api_url_id") and account_dict.get("server_id"):
        default_url_id = _get_default_mail_api_url_id(db, account_dict["server_id"])
        if default_url_id:
            account_dict["mail_api_url_id"] = default_url_id
    
    # Validate mail_api_url_id if provided
    if account_dict.get("mail_api_url_id"):
        url_crud = MailApiUrlCRUD(db)
        url_obj = url_crud.get_by_id(account_dict["mail_api_url_id"])
        if not url_obj:
            raise HTTPException(status_code=400, detail=f"Mail API URL {account_dict['mail_api_url_id']} not found")
    
    crud = SenderAccountCRUD(db)
    account_obj = crud.create({
        "id": str(uuid.uuid4()),
        **account_dict
    })
    return SenderAccountResponse(
        id=account_obj.id,
        email=account_obj.email,
        password=account_obj.password,
        first_name=account_obj.first_name,
        last_name=account_obj.last_name,
        imap_host=account_obj.imap_host,
        imap_port=account_obj.imap_port,
        imap_ssl=account_obj.imap_ssl,
        smtp_host=account_obj.smtp_host,
        smtp_port=account_obj.smtp_port,
        selenium_required=account_obj.selenium_required,
        server_id=account_obj.server_id,
        mail_api_url_id=account_obj.mail_api_url_id,
        is_active=account_obj.is_active,
        created_at=account_obj.created_at.isoformat() if account_obj.created_at else None,
        updated_at=account_obj.updated_at.isoformat() if account_obj.updated_at else None,
    )


@router.get("/sender-accounts", response_model=List[SenderAccountResponse])
async def list_sender_accounts(
    active_only: bool = True,
    server_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all sender accounts"""
    crud = SenderAccountCRUD(db)
    accounts = crud.get_all(active_only=active_only, server_id=server_id)
    return [
        SenderAccountResponse(
            id=acc.id,
            email=acc.email,
            password=acc.password,
            first_name=acc.first_name,
            last_name=acc.last_name,
            imap_host=acc.imap_host,
            imap_port=acc.imap_port,
            imap_ssl=acc.imap_ssl,
            smtp_host=acc.smtp_host,
            smtp_port=acc.smtp_port,
            selenium_required=acc.selenium_required,
            server_id=acc.server_id,
            mail_api_url_id=acc.mail_api_url_id,
            is_active=acc.is_active,
            created_at=acc.created_at.isoformat() if acc.created_at else None,
            updated_at=acc.updated_at.isoformat() if acc.updated_at else None,
        )
        for acc in accounts
    ]


@router.get("/sender-accounts/{account_id}", response_model=SenderAccountResponse)
async def get_sender_account_endpoint(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Get a sender account by ID"""
    crud = SenderAccountCRUD(db)
    account_obj = crud.get_by_id(account_id)
    if not account_obj:
        raise HTTPException(status_code=404, detail=f"Sender account {account_id} not found")
    return SenderAccountResponse(
        id=account_obj.id,
        email=account_obj.email,
        password=account_obj.password,
        first_name=account_obj.first_name,
        last_name=account_obj.last_name,
        imap_host=account_obj.imap_host,
        imap_port=account_obj.imap_port,
        imap_ssl=account_obj.imap_ssl,
        smtp_host=account_obj.smtp_host,
        smtp_port=account_obj.smtp_port,
        selenium_required=account_obj.selenium_required,
        server_id=account_obj.server_id,
        mail_api_url_id=account_obj.mail_api_url_id,
        is_active=account_obj.is_active,
        created_at=account_obj.created_at.isoformat() if account_obj.created_at else None,
        updated_at=account_obj.updated_at.isoformat() if account_obj.updated_at else None,
    )


@router.put("/sender-accounts/{account_id}", response_model=SenderAccountResponse)
async def update_sender_account_endpoint(
    account_id: str,
    account_data: SenderAccountUpdate,
    db: Session = Depends(get_db)
):
    """Update a sender account"""
    crud = SenderAccountCRUD(db)
    # Get current account to check server_id
    current_account = crud.get_by_id(account_id)
    if not current_account:
        raise HTTPException(status_code=404, detail=f"Sender account {account_id} not found")
    
    update_data = {k: v for k, v in account_data.model_dump().items() if v is not None}
    
    # Auto-set mail_api_url_id if not provided (or if server_id is being changed)
    server_id = update_data.get("server_id", current_account.server_id)
    if "mail_api_url_id" not in update_data or update_data.get("mail_api_url_id") is None:
        # Mail API URL not provided, auto-set based on server_id
        default_url_id = _get_default_mail_api_url_id(db, server_id)
        if default_url_id:
            update_data["mail_api_url_id"] = default_url_id
    
    # Validate mail_api_url_id if provided
    if update_data.get("mail_api_url_id") is not None:
        url_crud = MailApiUrlCRUD(db)
        url_obj = url_crud.get_by_id(update_data["mail_api_url_id"])
        if not url_obj:
            raise HTTPException(status_code=400, detail=f"Mail API URL {update_data['mail_api_url_id']} not found")
    
    account_obj = crud.update(account_id, update_data)
    if not account_obj:
        raise HTTPException(status_code=404, detail=f"Sender account {account_id} not found")
    return SenderAccountResponse(
        id=account_obj.id,
        email=account_obj.email,
        password=account_obj.password,
        first_name=account_obj.first_name,
        last_name=account_obj.last_name,
        imap_host=account_obj.imap_host,
        imap_port=account_obj.imap_port,
        imap_ssl=account_obj.imap_ssl,
        smtp_host=account_obj.smtp_host,
        smtp_port=account_obj.smtp_port,
        selenium_required=account_obj.selenium_required,
        server_id=account_obj.server_id,
        mail_api_url_id=account_obj.mail_api_url_id,
        is_active=account_obj.is_active,
        created_at=account_obj.created_at.isoformat() if account_obj.created_at else None,
        updated_at=account_obj.updated_at.isoformat() if account_obj.updated_at else None,
    )


@router.delete("/sender-accounts/{account_id}")
async def delete_sender_account_endpoint(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Delete a sender account"""
    crud = SenderAccountCRUD(db)
    success = crud.delete(account_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Sender account {account_id} not found")
    return {"message": f"Sender account {account_id} deleted successfully"}






