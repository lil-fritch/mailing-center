from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    id: str = Field(..., description="Unique ID of the inbound message (e.g., IMAP UID)")
    account_email: str = Field(..., description="Account that received the message")
    from_email: str = Field(..., description="Sender address from the inbound message")
    subject: str = Field(..., description="Subject of the inbound message")
    body: str = Field(..., description="Plain text body extracted from the inbound message")
    received_at: datetime = Field(..., description="Timestamp when the message was received (server time)")
    message_id: Optional[str] = Field(None, description="Message-ID header from the email")
    in_reply_to: Optional[str] = Field(None, description="In-Reply-To header from the email")
    references: Optional[str] = Field(None, description="References header from the email")


class PendingReply(BaseModel):
    id: str = Field(..., description="Unique ID for the pending reply (correlates to inbound id)")
    account_email: str = Field(..., description="Account that will send the reply")
    to_email: str = Field(..., description="Recipient for the reply (original sender)")
    subject: str = Field(..., description="Subject for the reply")
    body: str = Field(..., description="Body for the reply")
    scheduled_at: datetime = Field(..., description="When the reply should be sent")
    created_at: datetime = Field(..., description="When the pending reply was created")
    campaign_id: Optional[str] = Field(None, description="Campaign ID for auto-reply")
    thread_id: Optional[str] = Field(None, description="Thread ID for saving reply to thread")


class SentReply(BaseModel):
    id: str = Field(..., description="ID of the reply (matching PendingReply.id)")
    account_email: str = Field(..., description="Account that sent the reply")
    to_email: str = Field(..., description="Recipient of the reply")
    subject: str = Field(..., description="Subject used for the reply")
    body: str = Field(..., description="Body used for the reply")
    scheduled_at: datetime = Field(..., description="Planned send time")
    sent_at: datetime = Field(..., description="Actual send time")
    success: bool = Field(..., description="Whether sending succeeded")
    message_id: Optional[str] = Field(default=None, description="Provider message ID if available")
    error: Optional[str] = Field(default=None, description="Error message if sending failed")


__all__ = [
    "InboundMessage",
    "PendingReply",
    "SentReply",
] 