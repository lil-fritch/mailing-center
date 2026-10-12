from typing import Optional, Any, List
from pydantic import BaseModel, Field, model_validator
from enum import Enum

from app.models.studio import Studio

# Defines Pydantic schemas for email content and sending results.

class PersonalizedEmail(BaseModel):
    """Represents a personalized email generated for a specific studio.

    This model is produced by the AI integration and later consumed by the
    mail sending integration.
    """

    subject: str = Field(..., description="Email subject, personalized per studio")
    body: str = Field(..., description="Email body text, may contain personalization tokens")
    language: Optional[str] = Field(None, description="Language code, typically 'pl'")
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional generation metadata (model, temperature, etc.)",
    )


class ToneOfVoice(str, Enum):
    """Predefined tones of voice for email generation."""

    CASUAL = "casual"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    ENTHUSIASTIC = "enthusiastic"
    SINCERE = "sincere"
    PLAYFUL = "playful"


class WritingStyle(str, Enum):
    """Predefined writing styles for email generation."""

    SHORT = "short"
    STORYTELLING = "storytelling"
    QUESTION_CENTRIC = "question_centric"
    COMPLIMENT_FIRST = "compliment_first"
    CONVERSATIONAL = "conversational"
    STRUCTURED = "structured"


class EmailSendResult(BaseModel):
    """Represents the outcome of sending an email.

    The actual sending is performed by an external provider and integrated via
    the MailSender. This model captures success/failure and any identifiers.
    """

    success: bool = Field(..., description="Whether the email was sent successfully")
    message_id: Optional[str] = Field(
        default=None, description="External provider message identifier, if available"
    )
    status: Optional[str] = Field(default=None, description="Provider-reported status text")
    provider: Optional[str] = Field(default=None, description="Mail provider name if available")
    from_email: Optional[str] = Field(default=None, description="Sender used for this send")
    to_email: Optional[str] = Field(default=None, description="Recipient used for this send")
    error: Optional[str] = Field(default=None, description="Error details, if any")


__all__ = [
    "PersonalizedEmail",
    "EmailSendResult",
]


class CampaignSetupRequest(BaseModel):
    """Request payload for configuring a campaign without executing it.

    Note: This schema is intentionally light on validation/logic as per requirement
    to only accept data. Downstream services can perform stricter checks.
    """

    name: Optional[str] = Field(
        default=None, description="Custom campaign name"
    )
    sender_account_ids: Optional[List[str]] = Field(
        default=None, description="List of sender account IDs to use for this campaign"
    )
    # Filters or explicit recipients
    country: Optional[str] = Field(
        default=None, description="Country filter for database-backed selection"
    )
    object_type: Optional[str] = Field(
        default=None, description="Type filter for database-backed selection"
    )
    emails: Optional[List[str]] = Field(
        default=None, description="Explicit list of recipient email addresses"
    )
    included_place_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of B2B place_ids to include when using filters mode",
    )

    # Parsing controls
    parsing: bool = Field(
        default=False,
        description="Whether parsing via AI should be applied",
    )
    parsing_prompt: Optional[str] = Field(
        default=None,
        description="Prompt for AI parsing when parsing is enabled",
    )

    # Generation prompts
    subject_prompt: Optional[str] = Field(
        default=None, description="Prompt to generate email subject"
    )
    body_prompt: Optional[str] = Field(
        default=None, description="Prompt to generate email body"
    )

    # Auto answering
    auto_answering: bool = Field(
        default=False, description="Enable auto-answering generation"
    )
    single_reply_only: bool = Field(
        default=False, description="If enabled, send only one auto-reply per thread and save further emails without responding"
    )
    reply_prompt: Optional[str] = Field(
        default=None, description="Prompt to generate auto-reply body when enabled"
    )

    # Style controls
    tov: Optional[ToneOfVoice] = Field(default=None, description="Tone of voice")
    style: Optional[WritingStyle] = Field(default=None, description="Writing style")
    language: Optional[str] = Field(default="pl", description="Language code for email generation")

    # Sending and schedule settings
    use_corporate: bool = Field(
        default=False,
        description="Send from corporate (True) vs personal (False) email accounts",
    )
    daily_limit: Optional[int] = Field(
        default=None, description="Maximum emails to send per day"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="Timezone name (e.g., 'Europe/Warsaw') or offset (e.g., '+2', '-2') for scheduling context",
    )

    @model_validator(mode="after")
    def _validate_exclusive_inputs(self):  # type: ignore[override]
        has_emails = bool(self.emails and len(self.emails) > 0)
        has_filters = bool((self.country or "") and (self.object_type or ""))

        if has_emails and has_filters:
            raise ValueError(
                "Provide either emails list OR (country and object_type), not both"
            )

        if not has_emails and not has_filters:
            raise ValueError(
                "You must provide emails list OR both country and object_type"
            )

        if self.parsing and not (self.parsing_prompt and self.parsing_prompt.strip()):
            raise ValueError(
                "parsing_prompt is required when parsing is True"
            )

        if self.auto_answering and not (self.reply_prompt and self.reply_prompt.strip()):
            raise ValueError(
                "reply_prompt is required when auto_answering is True"
            )

        # Validate that both generation prompts are provided
        if not (self.subject_prompt and self.subject_prompt.strip()):
            raise ValueError("subject_prompt is required")
        
        if not (self.body_prompt and self.body_prompt.strip()):
            raise ValueError("body_prompt is required")

        return self


__all__.extend(["CampaignSetupRequest", "ToneOfVoice", "WritingStyle"])