from __future__ import annotations

import json
import os
import uuid
from typing import List, Optional
from pydantic import BaseModel
from app.database.connection import SessionLocal
from app.database.crud import get_sender_accounts
from app.database.models import SenderAccount as DBSenderAccount


class SenderAccount(BaseModel):
    id: str
    email: str
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    imap_host: Optional[str] = None
    imap_port: int = 993
    imap_ssl: bool = True
    server_id: str = "1"  # Default to server 1, "2" for second server

    @classmethod
    def from_db(cls, db_account: DBSenderAccount) -> "SenderAccount":
        """Конвертує DB модель в Pydantic модель"""
        return cls(
            id=db_account.id,
            email=db_account.email,
            password=db_account.password,
            first_name=db_account.first_name,
            last_name=db_account.last_name,
            imap_host=db_account.imap_host,
            imap_port=db_account.imap_port,
            imap_ssl=db_account.imap_ssl,
            server_id=db_account.server_id,
        )


def load_sender_accounts_from_db(active_only: bool = True, server_id: Optional[str] = None) -> List[SenderAccount]:
    """Завантажити акаунти відправників з бази даних"""
    db = SessionLocal()
    try:
        db_accounts = get_sender_accounts(db, active_only=active_only, server_id=server_id)
        return [SenderAccount.from_db(acc) for acc in db_accounts]
    finally:
        db.close()


def load_sender_accounts(file_path: str) -> List[SenderAccount]:
    """Завантажити акаунти з JSON файлу (legacy, для сумісності)"""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    accounts: List[SenderAccount] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        payload = item.copy()
        payload.setdefault("id", payload.get("id") or payload.get("email") or str(uuid.uuid4()))
        accounts.append(SenderAccount(**payload))
    return accounts


__all__ = [
    "SenderAccount",
    "load_sender_accounts",
    "load_sender_accounts_from_db",
] 