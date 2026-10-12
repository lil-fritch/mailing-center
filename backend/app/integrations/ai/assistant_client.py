import asyncio
import json
from typing import Optional

from openai import AsyncOpenAI

from app.core.settings import settings
from app.core.logger import get_logger
from app.database.models import B2BObject
from app.schemas.email import PersonalizedEmail, CampaignSetupRequest
from app.schemas.inbound import InboundMessage

# Client for interacting with the OpenAI Assistant API.


class OpenAIAssistantClient:
    """Thin client wrapper around the OpenAI Assistant API.

    This class is responsible for preparing prompts, invoking the Assistant,
    and mapping the response into a `PersonalizedEmail`.
    """

    def __init__(self, assistant_id: Optional[str] = None) -> None:
        """Initialize the client with a specific Assistant ID or use settings.

        Parameters
        ----------
        assistant_id: Optional[str]
            Explicit Assistant ID. If not provided, the value from settings
            (`settings.openai_assistant_id_mail_generator`) will be used.
        """
        self.logger = get_logger(__name__)
        self.assistant_id = assistant_id or settings.openai_assistant_id_mail_generator
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_email_for_b2b_object(
        self, b2b_obj: B2BObject, campaign_request: CampaignSetupRequest, retreat_info: Optional[str] = None, enriched_context: Optional[str] = None
    ) -> PersonalizedEmail:
        """Generate a personalized email for the given B2B object via Assistants API.

        The Assistant should return a JSON object with keys: subject, body, and
        optionally language. If parsing fails, a fallback is built.
        """
        if not self.assistant_id:
            raise RuntimeError("OpenAI Assistant ID is not configured.")

        prompt = self._build_prompt(b2b_obj, campaign_request, retreat_info, enriched_context)
        
        self.logger.info(
            "AI: starting email generation (assistant_id=%s, place_id=%s, name=%s, language=%s, has_retreat_info=%s, has_enriched_context=%s)",
            self.assistant_id,
            b2b_obj.place_id,
            b2b_obj.name,
            campaign_request.language,
            bool(retreat_info),
            bool(enriched_context)
        )
        
        # Log the complete prompt for debugging
        self.logger.info("AI: PROMPT SENT TO AI:\n%s", prompt)

        thread = await self._client.beta.threads.create()
        await self._client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
        )

        run = await self._client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id,
        )

        # Poll until the run completes
        status = run.status
        while status not in {"completed", "failed", "cancelled", "expired"}:
            await asyncio.sleep(0.5)
            run = await self._client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            status = run.status

        if status != "completed":
            self.logger.error(
                "AI: run did not complete (status=%s, place_id=%s)", status, b2b_obj.place_id
            )
            raise RuntimeError(f"Assistant run did not complete: {status}")

        messages = await self._client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=1)
        text_content = ""
        if messages.data:
            msg = messages.data[0]
            for part in msg.content:
                if getattr(part, "type", None) == "text":
                    text_content += part.text.value

        email = self._parse_email_json_or_fallback(text_content, b2b_obj, campaign_request)
        body_preview = (email.body or "")[:200].replace("\n", " ")
        self.logger.info(
            "AI: generated email (place_id=%s, subject=%r, language=%s, body_preview=%r)",
            b2b_obj.place_id,
            email.subject,
            email.language,
            body_preview,
        )
        return email

    async def generate_reply_for_inbound(
        self, 
        inbound: InboundMessage, 
        campaign=None, 
        thread_messages=None
    ) -> tuple[str, str]:
        """Generate reply using campaign settings and thread context."""
        # Use answer generator assistant ID
        answer_assistant_id = settings.openai_assistant_id_answer_generator
        if not answer_assistant_id:
            raise RuntimeError("OpenAI Assistant ID for answer generator is not configured.")

        # Build prompt with campaign settings and thread context
        prompt = self._build_reply_prompt(inbound, campaign, thread_messages)
        
        self.logger.info(
            "AI: starting reply generation (assistant_id=%s, campaign_id=%s, thread_messages=%d)",
            answer_assistant_id,
            campaign.id if campaign else None,
            len(thread_messages) if thread_messages else 0
        )
        self.logger.info("AI: REPLY PROMPT:\n%s", prompt)

        thread = await self._client.beta.threads.create()

        await self._client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
        )

        run = await self._client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=answer_assistant_id,
        )

        while True:
            run_status = await self._client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run_status.status == "completed":
                break
            elif run_status.status == "failed":
                raise RuntimeError("Assistant run failed")
            await asyncio.sleep(1)

        messages = await self._client.beta.threads.messages.list(thread_id=thread.id)

        for message in messages.data:
            if message.role == "assistant":
                raw = message.content[0].text.value
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON from assistant: {e}")

                if not isinstance(data, dict) or "subject" not in data or "body" not in data:
                    raise ValueError("Assistant JSON must contain 'subject' and 'body'")

                self.logger.info(
                    "AI: generated reply (subject=%r, body_length=%d)",
                    data["subject"],
                    len(data["body"])
                )
                return data["subject"], data["body"]

        raise RuntimeError("No assistant response received.")
    
    def _build_reply_prompt(self, inbound: InboundMessage, campaign, thread_messages) -> str:
        """Build prompt for reply generation with campaign settings and thread context."""
        # Build thread context - all previous messages in chronological order
        thread_context = ""
        if thread_messages:
            thread_context_parts = []
            for msg in thread_messages:
                direction = "FROM US" if msg.message_type.value == "sent" else "FROM THEM"
                thread_context_parts.append(
                    f"[{direction}]\n"
                    f"Subject: {msg.subject or '(no subject)'}\n"
                    f"From: {msg.from_email}\n"
                    f"To: {msg.to_email}\n"
                    f"Body:\n{msg.body or '(empty)'}\n"
                    + "-" * 50 + "\n"
                )
            thread_context = "\n".join(thread_context_parts)
        else:
            thread_context = "[No previous messages in thread]"
        
        # Build tone and style instructions
        tone_instruction = ""
        if campaign and campaign.tov:
            tone_map = {
                "casual": "casual, relaxed tone",
                "friendly": "friendly, warm tone", 
                "professional": "professional, business tone",
                "enthusiastic": "enthusiastic, energetic tone",
                "sincere": "sincere, honest tone",
                "playful": "playful, light tone"
            }
            tone_instruction = f"Tone: {tone_map.get(campaign.tov, campaign.tov)}. "
        
        style_instruction = ""
        if campaign and campaign.style:
            style_map = {
                "short": "short, concise style",
                "storytelling": "storytelling style with narratives",
                "question_centric": "question-focused style",
                "compliment_first": "start with compliments",
                "conversational": "conversational, natural style",
                "structured": "structured, organized style"
            }
            style_instruction = f"Style: {style_map.get(campaign.style, campaign.style)}. "
        
        language = campaign.language if campaign and campaign.language else "pl"
        reply_prompt = campaign.reply_prompt if campaign and campaign.reply_prompt else "Generate an appropriate reply to the received email."
        
        return (
            f"Generate a reply email in {language}.\n\n"
            f"Reply generation instructions:\n{reply_prompt}\n\n"
            f"{tone_instruction}{style_instruction}\n"
            "REQUIREMENTS:\n"
            "- Return ONLY JSON object with keys: subject, body\n"
            f"- Language must be: {language}\n"
            "- Do not add explanations, comments or markdown\n"
            "- The reply should be appropriate and contextual based on the conversation history\n\n"
            "CONVERSATION HISTORY:\n"
            f"{thread_context}\n\n"
            "LATEST MESSAGE (to reply to):\n"
            f"Subject: {inbound.subject}\n"
            f"From: {inbound.from_email}\n"
            f"Body:\n{inbound.body}\n"
        )

    def _build_prompt(self, b2b_obj: B2BObject, campaign_request: CampaignSetupRequest, retreat_info: Optional[str] = None, enriched_context: Optional[str] = None) -> str:
        """Compose the user message using campaign-specific prompts and parameters."""
        name = b2b_obj.name or "Unknown Organization"
        city = b2b_obj.city or "Unknown City"
        obj_type = b2b_obj.type or "Not specified"
        website = b2b_obj.website or "Not available"
        description = (b2b_obj.description or "").strip() or "No description available"
        owner_name = (b2b_obj.owner_name or "").strip() or "Not available"
        address = (b2b_obj.address or "").strip() or "Not available"
        
        # Check if we have organization data (for email list campaigns, most fields will be None)
        has_org_data = b2b_obj.name is not None and b2b_obj.name.strip()
        
        # Build tone and style instructions in English
        tone_instruction = ""
        if campaign_request.tov:
            tone_map = {
                "casual": "casual, relaxed tone",
                "friendly": "friendly, warm tone", 
                "professional": "professional, business tone",
                "enthusiastic": "enthusiastic, energetic tone",
                "sincere": "sincere, honest tone",
                "playful": "playful, light tone"
            }
            tone_instruction = f"Tone: {tone_map.get(campaign_request.tov.value, campaign_request.tov.value)}. "
        
        style_instruction = ""
        if campaign_request.style:
            style_map = {
                "short": "short, concise style",
                "storytelling": "storytelling style with narratives",
                "question_centric": "question-focused style",
                "compliment_first": "start with compliments",
                "conversational": "conversational, natural style",
                "structured": "structured, organized style"
            }
            style_instruction = f"Style: {style_map.get(campaign_request.style.value, campaign_request.style.value)}. "
        
        # Build the combined prompt
        combined_prompt = f"{campaign_request.subject_prompt}\n\n{campaign_request.body_prompt}"
        
        # Add retreat info if available (legacy support)
        retreat_context = ""
        if retreat_info:
            retreat_context = f"\n\nAdditional retreat information: {retreat_info.strip()}"
        
        # Add enriched context from web research if available
        enriched_section = ""
        if enriched_context:
            enriched_section = f"\n\nADDITIONAL WEB RESEARCH DATA:\n{enriched_context.strip()}\n\nUse this research data to personalize your email and make it more relevant to the recipient."
        
        # Build organization data section with clear indication of missing data
        if has_org_data:
            org_data_section = (
                "ORGANIZATION DATA:\n"
                f"Name: {name}\n"
                f"City: {city}\n"
                f"Type: {obj_type}\n"
                f"Owner name: {owner_name}\n"
                f"Website: {website}\n"
                f"Address: {address}\n"
                f"Description: {description}"
            )
        else:
            org_data_section = (
                "ORGANIZATION DATA: LIMITED INFORMATION AVAILABLE\n"
                "Name: Not provided\n"
                "City: Not provided\n"
                "Type: Not provided\n"
                "Owner name: Not provided\n"
                "Website: Not provided\n"
                "Address: Not provided\n"
                "Description: Not provided\n"
                f"Email: {b2b_obj.email or 'Not provided'}\n\n"
                "IMPORTANT: Since detailed organization information is not available, "
                "create a generic but personalized email. Do NOT invent specific details "
                "about services, classes, or organization features. Focus on the general "
                "purpose of your email as specified in the generation prompt."
            )
        
        return (
            f"Create an email in {campaign_request.language} for the following organization.\n\n"
            f"Generation prompt:\n{combined_prompt}\n\n"
            f"{tone_instruction}{style_instruction}"
            "REQUIREMENTS:\n"
            "- Return ONLY JSON object with keys: subject, body, language\n"
            f"- Language must be: {campaign_request.language}\n"
            "- Do not add explanations, comments or markdown\n"
            "- Personalize the message appropriately based on available data\n\n"
            f"{org_data_section}"
            f"{retreat_context}"
            f"{enriched_section}"
        )
    def _parse_email_json_or_fallback(self, text: str, b2b_obj: B2BObject, campaign_request: CampaignSetupRequest) -> PersonalizedEmail:
        """Attempt to parse Assistant text as JSON; fallback to a minimal email (participant perspective)."""
        subject = (
            f"Podziękowania dla {b2b_obj.name} — od uczestnika" if b2b_obj.name else "Podziękowania — od uczestnika"
        )
        body = (
            f"Dzień dobry {b2b_obj.name},\n"
            f"chciałem/chciałam serdecznie podziękować za Waszą pracę i atmosferę, którą tworzycie. "
            f"Będzie mi miło, jeśli odpiszą Państwo w dogodnym terminie.\n"
            f"Pozdrawiam serdecznie."
        )
        language = campaign_request.language
        metadata = {"assistant_id": self.assistant_id, "campaign_request": campaign_request.dict()}

        if text:
            try:
                payload = json.loads(text)
                subject = payload.get("subject") or subject
                body = payload.get("body") or body
                language = payload.get("language") or language
            except Exception:
                pass

        return PersonalizedEmail(
            subject=subject,
            body=body,
            language=language,
            metadata=metadata,
        ) 