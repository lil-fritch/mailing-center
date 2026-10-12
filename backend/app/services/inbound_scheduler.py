from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, time, timezone
from typing import List, Optional

from app.core.logger import get_logger
from app.core.settings import settings
from app.schemas.inbound import PendingReply, SentReply


QUEUE_FILE = "app/data/inbound_queue.json"
HISTORY_FILE = "app/data/inbound_history.json"


def _ensure_files() -> None:
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    for path in (QUEUE_FILE, HISTORY_FILE):
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)


def _load_json_list(path: str) -> list:
    _ensure_files()
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _save_json_list(path: str, items: list) -> None:
    _ensure_files()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


class InboundScheduler:
    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    def schedule_time_for_reply(self, received_at: datetime) -> datetime:
        """Schedule reply to be sent.
        
        In development mode: 15 seconds after receipt
        In production mode: 4-7 minutes (240-420 seconds) after receipt
        """
        # Normalize to aware UTC datetimes
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
        
        # In development mode, use 15 seconds delay
        if settings.development_mode:
            delay_seconds = 15
        else:
            # Random delay between 4-7 minutes (240-420 seconds)
            delay_seconds = random.randint(240, 420)
        
        scheduled = received_at + timedelta(seconds=delay_seconds)
        
        self.logger.info("Inbound: scheduled reply at %s (received %s, delay %d seconds, dev_mode=%s)", 
                        scheduled.isoformat(), received_at.isoformat(), delay_seconds, settings.development_mode)
        return scheduled

    def enqueue(self, pending: PendingReply) -> None:
        items = _load_json_list(QUEUE_FILE)
        items.append(pending.model_dump(mode="json"))
        _save_json_list(QUEUE_FILE, items)

    def list_queue(self) -> List[PendingReply]:
        items = _load_json_list(QUEUE_FILE)
        return [PendingReply(**it) for it in items]

    def pop_due(self, now: Optional[datetime] = None) -> List[PendingReply]:
        now = now or datetime.now(timezone.utc)
        items = _load_json_list(QUEUE_FILE)
        remaining = []
        due: List[dict] = []
        for it in items:
            try:
                scheduled_at = datetime.fromisoformat(it["scheduled_at"].replace("Z", "+00:00"))  # Pydantic dumps ISO
            except Exception:
                remaining.append(it)
                continue
            if scheduled_at <= now:
                due.append(it)
            else:
                remaining.append(it)
        _save_json_list(QUEUE_FILE, remaining)
        return [PendingReply(**d) for d in due]

    def record_history(self, sent: SentReply) -> None:
        items = _load_json_list(HISTORY_FILE)
        items.append(sent.model_dump(mode="json"))
        _save_json_list(HISTORY_FILE, items)

    def list_history(self) -> List[SentReply]:
        items = _load_json_list(HISTORY_FILE)
        return [SentReply(**it) for it in items]


scheduler = InboundScheduler() 