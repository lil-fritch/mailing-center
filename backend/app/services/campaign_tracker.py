from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, Field

from app.schemas.email import EmailSendResult


class CampaignStatus(BaseModel):
    id: str
    campaign_id: Optional[str] = None
    queued: int
    processed: int
    successes: int
    failures: int
    in_progress: bool
    started_at: datetime
    finished_at: Optional[datetime] = None
    last_pause_seconds: Optional[float] = None
    next_send_at: Optional[datetime] = None
    results: List[EmailSendResult] = Field(default_factory=list)


class CampaignTracker:
    def __init__(self) -> None:
        self._status: Optional[CampaignStatus] = None

    def start(self, queued: int) -> None:
        now = datetime.now(timezone.utc)
        self._status = CampaignStatus(
            id=now.isoformat(),
            campaign_id=None,
            queued=queued,
            processed=0,
            successes=0,
            failures=0,
            in_progress=True,
            started_at=now,
            finished_at=None,
            last_pause_seconds=None,
            next_send_at=None,
            results=[],
        )

    def record_result(self, result: EmailSendResult) -> None:
        if not self._status:
            return
        self._status.results.append(result)
        self._status.processed += 1
        if result.success:
            self._status.successes += 1
        else:
            self._status.failures += 1

    def set_last_pause(self, seconds: float) -> None:
        if not self._status:
            return
        self._status.last_pause_seconds = float(seconds)

    def set_campaign_id(self, campaign_id: str) -> None:
        if not self._status:
            return
        self._status.campaign_id = campaign_id

    def set_next_send_at(self, when: Optional[datetime]) -> None:
        if not self._status:
            return
        self._status.next_send_at = when

    def clear(self) -> None:
        """Reset tracker (used when campaign is paused externally)."""
        self._status = None

    def finish(self) -> None:
        if not self._status:
            return
        self._status.in_progress = False
        self._status.finished_at = datetime.now(timezone.utc)

    def get_status(self) -> Optional[CampaignStatus]:
        return self._status


campaign_tracker = CampaignTracker() 