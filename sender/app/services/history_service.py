from __future__ import annotations
import json
from pathlib import Path
from typing import List
from datetime import datetime

from app.core.config import settings
from app.core.logger import logger
from app.schemas.email import HistoryItem


class EmailHistory:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._items: List[HistoryItem] = []
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            self._items = []
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self._items = [HistoryItem(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            self._items = []

    def _save(self) -> None:
        try:
            data = []
            for item in self._items:
                d = item.model_dump()
                d["sent_at"] = item.sent_at.isoformat()
                data.append(d)
            self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add(self, item: HistoryItem) -> None:
        self._items.append(item)
        self._save()

    def list(self, limit: int | None = None) -> List[HistoryItem]:
        items = list(self._items)
        if limit is not None:
            items = items[-limit:]
        return items

    def clear(self) -> None:
        self._items = []
        self._save()


email_history = EmailHistory(settings.EMAIL_HISTORY_FILE) 