"""Campaign API endpoints.

This module contains HTTP request handlers for campaign management.
Business logic is delegated to service layer.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.schemas.email import CampaignSetupRequest
from app.schemas.campaign import (
    CampaignListResponse,
    CampaignObjectsStatusResponse
)
from app.database import get_db
from app.services.campaign_api_service import CampaignAPIService
from app.database.crud import EmailThreadCRUD
from app.database.models import EmailThread, CampaignTarget, SentEmail, MessageType
from sqlalchemy import or_
import urllib.parse
from app.services.email_campaign_service import EmailCampaignService
from app.services.campaign_tracker import campaign_tracker
from app.services.inbound_scheduler import scheduler
# IMAP blocklist removed


router = APIRouter()


# ==================== Campaign Management ====================

@router.post("/emails/setup")
async def setup_campaign(
    request: CampaignSetupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and start email campaign.
    
    Select B2B objects by filters or emails, create campaign, and start sending in background.
    Returns immediately with campaign info, actual sending happens in background.
    """
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Campaign setup request: use_corporate=%s, auto_answering=%s, parsing=%s", 
                request.use_corporate, request.auto_answering, request.parsing)
    
    # Create campaign and targets
    campaign_id, b2b_objects = CampaignAPIService.create_campaign_from_request(request, db)
    logger.info("Campaign created: id=%s, use_corporate=%s, auto_answering=%s, parsing=%s", 
                campaign_id, request.use_corporate, request.auto_answering, request.parsing)
    
    # Start background content generation and processing
    service = EmailCampaignService()
    background_tasks.add_task(service.generate_content_for_campaign, campaign_id, request)
    background_tasks.add_task(service.process_campaign_by_id, campaign_id)
    
    return {
        "message": "Campaign started successfully",
        "campaign_id": campaign_id,
        "queued": len(b2b_objects),
        "filters": {
            "country": request.country,
            "object_type": request.object_type,
            "emails": request.emails
        },
        "settings": {
            "parsing": request.parsing,
            "auto_answering": request.auto_answering,
            "use_corporate": request.use_corporate,
            "tov": request.tov,
            "style": request.style
        }
    }


@router.get("/campaigns", response_model=CampaignListResponse)
async def get_campaigns(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get list of all campaigns with basic info"""
    return CampaignAPIService.get_campaigns_list(db, skip, limit)


@router.get("/campaigns/{campaign_id}", response_model=CampaignObjectsStatusResponse)
async def get_campaign_status(campaign_id: str, db: Session = Depends(get_db)):
    """Get campaign status with B2B objects and their statuses"""
    response = CampaignAPIService.get_campaign_status(campaign_id, db)
    if not response:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
    return response


@router.get("/campaigns/{campaign_id}/objects/{object_id}", response_model=dict, tags=["Campaigns"])
async def get_campaign_object_details(campaign_id: str, object_id: str, db: Session = Depends(get_db)):
    """Get detailed information about a specific campaign object."""
    result = CampaignAPIService.get_campaign_object_details(campaign_id, object_id, db)
    if not result:
        raise HTTPException(status_code=404, detail=f"Object {object_id} not found in campaign {campaign_id}")
    return result


@router.delete("/campaigns/{campaign_id}", status_code=204, tags=["Campaigns"])
async def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Delete completed campaign along with related data."""
    CampaignAPIService.delete_campaign(campaign_id, db)
    return Response(status_code=204)


@router.get("/campaigns/{campaign_id}/threads/{thread_id}", response_model=dict, tags=["Campaigns"])
async def get_email_thread(campaign_id: str, thread_id: str, db: Session = Depends(get_db)):
    """Get all messages in an email thread, including pending auto-replies."""
    print(f"DEBUG: Looking for thread_id={thread_id} in campaign_id={campaign_id}")
    
    thread_crud = EmailThreadCRUD(db)
    messages = thread_crud.get_by_thread_id(thread_id)
    
    print(f"DEBUG: Found {len(messages) if messages else 0} messages for thread_id={thread_id}")
    
    if not messages:
        # Додаткова діагностика
        all_threads = db.query(EmailThread).limit(5).all()
        print(f"DEBUG: Sample threads in DB: {[(t.thread_id, t.campaign_id) for t in all_threads]}")
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    
    # Перевірити що thread належить до цієї кампанії
    if messages[0].campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found in campaign {campaign_id}")
    
    # Отримати pending replies для цього thread
    from app.services.inbound_scheduler import scheduler
    pending_replies = []
    try:
        all_pending = scheduler.list_queue()
        # Фільтрувати pending replies для цього thread
        for pending in all_pending:
            if pending.thread_id == thread_id and pending.campaign_id == campaign_id:
                pending_replies.append({
                    "id": pending.id,
                    "type": "pending_reply",
                    "from_email": pending.account_email,
                    "to_email": pending.to_email,
                    "subject": pending.subject,
                    "body": pending.body,
                    "scheduled_at": pending.scheduled_at.isoformat(),
                    "created_at": pending.created_at.isoformat(),
                })
    except Exception as exc:
        print(f"DEBUG: Failed to load pending replies: {exc}")
    
    # Build messages list, using from_email from SentEmail if available (fixes old campaigns)
    formatted_messages = []
    participants = set()
    for msg in messages:
        # For sent messages, prefer from_email from SentEmail if sent_email_id exists
        from_email = msg.from_email
        if msg.message_type == MessageType.sent and msg.sent_email_id:
            sent_email = db.query(SentEmail).filter(SentEmail.id == msg.sent_email_id).first()
            if sent_email:
                from_email = sent_email.from_email
        
        formatted_messages.append({
            "id": msg.id,
            "type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
            "from_email": from_email,
            "to_email": msg.to_email,
            "subject": msg.subject,
            "body": msg.body,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "in_reply_to": msg.in_reply_to,
            "message_id": msg.message_id,
            "error": msg.error,  # Помилка відправки авто-відповіді, якщо є
        })
        participants.add(from_email)
        participants.add(msg.to_email)
    
    return {
        "thread_id": thread_id,
        "campaign_id": campaign_id,
        "participants": list(participants),
        "messages": formatted_messages,
        "pending_replies": pending_replies
    }


@router.post("/campaigns/{campaign_id}/objects/{object_id}/reply", tags=["Campaigns"])
async def send_reply(
    campaign_id: str, 
    object_id: str, 
    reply_data: dict,
    db: Session = Depends(get_db)
):
    """Send a reply to a campaign object."""
    from app.services.email_campaign_service import EmailCampaignService
    from app.integrations.mail import load_sender_accounts
    from app.schemas.email import PersonalizedEmail
    from app.database.crud import SentEmailCRUD, CampaignTargetCRUD, EmailThreadCRUD, create_email_thread
    from app.database.models import MessageType
    import uuid
    from datetime import datetime, timezone
    
    # Get campaign target
    decoded_object_id = urllib.parse.unquote(object_id)
    target = db.query(CampaignTarget).filter(
                    CampaignTarget.campaign_id == campaign_id,
        or_(
            CampaignTarget.place_id == decoded_object_id,
            CampaignTarget.to_email == decoded_object_id
        )
    ).first()
    
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    # Get thread_id
    thread_id = target.thread_id
    if not thread_id:
        raise HTTPException(status_code=400, detail="No thread found for this target")
    
    # Load sender accounts
    from app.core.settings import settings
    accounts = load_sender_accounts(settings.sender_accounts_file)
    if not accounts:
        raise HTTPException(status_code=500, detail="No sender accounts configured")
    
    # Find the account that sent the original email
    sent_email = db.query(SentEmail).filter(SentEmail.thread_id == thread_id).first()
    from_email = sent_email.from_email if sent_email else accounts[0].email
    
    # Find the account
    account = next((acc for acc in accounts if acc.email == from_email), accounts[0])
    
    # Create email service
    email_service = EmailCampaignService()
    
    # Send email
    email_content = PersonalizedEmail(
        subject=reply_data.get("subject", ""),
        body=reply_data.get("body", ""),
        language="pl"
    )
    
    result = await email_service.mail_sender.send_email(
        email=email_content,
        from_email=account.email,
        to_email=target.to_email,
        sender_name=f"{account.first_name} {account.last_name}" if account.first_name and account.last_name else None,
        use_corporate=(account.server_id == "2"),
        is_list_campaign=False,
        force_send=True  # Always send replies from form, even in dev mode
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {result.error}")
    
    # Create SentEmail record
    from app.database.crud import create_sent_email
    from app.database.models import EmailStatus
    
    sent_email_id = str(uuid.uuid4())
    sent_email_data = {
        "id": sent_email_id,
        "campaign_id": campaign_id,
        "b2b_place_id": target.place_id,
        "b2b_name": target.name,
        "b2b_type": target.type,
        "from_email": account.email,
        "to_email": target.to_email,
        "subject": reply_data.get("subject", ""),
        "body": reply_data.get("body", ""),
        "status": EmailStatus.SENT,
        "thread_id": thread_id,
        "message_id": result.message_id,
        "sender_name": f"{account.first_name} {account.last_name}" if account.first_name and account.last_name else None,
        "server_id": account.server_id,
        "provider": result.provider,
        "sent_at": datetime.now(timezone.utc),
    }
    create_sent_email(db, sent_email_data)
    
    # Save to email_threads
    thread_crud = EmailThreadCRUD(db)
    existing_messages = thread_crud.get_by_thread_id(thread_id)
    last_message_id = existing_messages[-1].id if existing_messages else None
    
    thread_data = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "campaign_id": campaign_id,
        "sent_email_id": sent_email_id,
        "message_type": MessageType.sent,
        "from_email": account.email,
        "to_email": target.to_email,
        "subject": reply_data.get("subject", ""),
        "body": reply_data.get("body", ""),
        "message_id": result.message_id,
        "in_reply_to": last_message_id,
        "references": None,
    }
    create_email_thread(db, thread_data)
    
    return {"success": True, "message_id": result.message_id}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Pause campaign"""
    success = CampaignAPIService.pause_campaign(campaign_id, db)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause campaign {campaign_id}. It may not exist or not be in valid state."
        )
    return {"message": f"Campaign {campaign_id} paused successfully"}


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Resume paused campaign"""
    success = CampaignAPIService.resume_campaign(campaign_id, db)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume campaign {campaign_id}. It may not exist or not be paused."
        )
    
    # Restart processing in background
    from fastapi import Request
    background_tasks = BackgroundTasks()
    service = EmailCampaignService()
    background_tasks.add_task(service.process_campaign_by_id, campaign_id)
    
    return {"message": f"Campaign {campaign_id} resumed successfully"}


# ==================== Campaign Status & Monitoring ====================

@router.get("/emails/status")
async def get_campaign_tracker_status():
    """Get current in-memory campaign tracker status (real-time progress)"""
    status = campaign_tracker.get_status()
    return status or {"detail": "no campaign in progress"}


@router.get("/timezones/{country_name}")
async def get_timezones_by_country(country_name: str):
    """Get list of unique timezones with UTC offsets for a given country name"""
    import pycountry
    import pytz
    from datetime import datetime
    
    try:
        country = pycountry.countries.search_fuzzy(country_name)[0]
        country_code = country.alpha_2
        timezone_list = pytz.country_timezones.get(country_code)
        
        if not timezone_list:
            return {"timezones": [], "country_code": country_code}
        
        # Групуємо timezone за offset для отримання унікальних значень
        unique_offsets = {}  # {offset_seconds: (formatted_offset, timezone_name)}
        
        for tz_name in timezone_list:
            try:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
                
                # Отримуємо зміщення у форматі рядка (наприклад, +0300 або -0500)
                offset_str = now.strftime('%z')
                
                # Форматуємо для краси (додаємо двокрапку: +03:00)
                formatted_offset = f"UTC{offset_str[:-2]}:{offset_str[-2:]}"
                
                # Зберігаємо по offset_seconds (унікальність)
                offset_seconds = now.utcoffset().total_seconds()
                
                # Якщо offset ще не існує, або якщо це перша timezone з цим offset
                if offset_seconds not in unique_offsets:
                    unique_offsets[offset_seconds] = (formatted_offset, tz_name)
                    
            except pytz.UnknownTimeZoneError:
                continue
        
        # Сортуємо за числовим значенням (від мінуса до плюса)
        sorted_items = sorted(unique_offsets.items(), key=lambda x: x[0])
        
        # Форматуємо як "UTC+01:00 (Europe/Warsaw)"
        formatted_timezones = [
            f"{formatted_offset} ({tz_name})" 
            for _, (formatted_offset, tz_name) in sorted_items
        ]
        
        return {"timezones": formatted_timezones, "country_code": country_code}
    except (LookupError, IndexError):
        raise HTTPException(status_code=404, detail=f"Country '{country_name}' not found")


# ==================== Inbound Email Management ====================

@router.get("/inbound/queue")
async def get_inbound_queue():
    """List pending replies queued for sending"""
    return scheduler.list_queue()


@router.get("/inbound/history")
async def get_inbound_history():
    """List sent replies history"""
    return scheduler.list_history()


# ==================== IMAP Management ====================
# IMAP blocklist endpoints removed - no more account blocking
