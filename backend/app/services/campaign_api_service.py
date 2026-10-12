"""Service layer for campaign API operations.

This module contains business logic for campaign creation, status retrieval,
and campaign management. It separates business logic from API controllers.
"""
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database.crud import B2BObjectCRUD, CampaignCRUD, CampaignTargetCRUD, SentEmailCRUD
from app.database.models import CampaignTarget, SentEmail, EmailThread, MessageType
from app.schemas.email import CampaignSetupRequest
from app.schemas.campaign import (
    SimpleCampaignInfo,
    CampaignListResponse,
    CampaignObjectsStatusResponse,
    SimpleCampaignStatistics,
    B2BObjectWithStatus
)
from app.core.logger import get_logger


logger = get_logger(__name__)


class CampaignAPIService:
    """Service for campaign API operations"""

    @staticmethod
    def create_campaign_from_request(
        request: CampaignSetupRequest,
        db: Session
    ) -> tuple[str, list]:
        """Create campaign and targets from setup request.
        
        Returns:
            tuple: (campaign_id, list of b2b_objects)
        """
        crud = B2BObjectCRUD(db)
        campaign_id = str(uuid.uuid4())

        # Prepare B2B objects
        if request.emails:
            # For email list - create lightweight plain objects
            b2b_objects: list[object] = []
            for email in request.emails:
                obj = type('B2BLight', (), {})()
                obj.place_id = f"email_{email}"
                obj.name = None
                obj.type = None
                obj.email = email
                obj.address = None
                obj.city = None
                obj.country = None
                obj.phone = None
                obj.website = None
                obj.description = None
                b2b_objects.append(obj)
        else:
            # For database search - get full B2B objects
            _db_objects = crud.search(
                obj_type=request.object_type,
                country=request.country,
                has_email=True,
                skip=0,
                limit=1000,
            )
            # If frontend provided explicit included_place_ids, filter DB objects accordingly.
            include_ids = {pid for pid in (request.included_place_ids or []) if pid}
            if include_ids:
                _db_objects = [
                    row for row in _db_objects
                    if getattr(row, "place_id", None) in include_ids
                ]
            # Convert ORM objects to lightweight plain objects
            b2b_objects: list[object] = []
            for row in _db_objects:
                obj = type('B2BLight', (), {})()
                obj.place_id = getattr(row, 'place_id', None)
                obj.name = getattr(row, 'name', None)
                obj.type = getattr(row, 'type', None)
                obj.email = getattr(row, 'email', None)
                obj.address = getattr(row, 'address', None)
                obj.city = getattr(row, 'city', None)
                obj.country = getattr(row, 'country', None)
                obj.phone = getattr(row, 'phone', None)
                obj.website = getattr(row, 'website', None)
                obj.description = getattr(row, 'description', None)
                b2b_objects.append(obj)

        # Create campaign
        campaign_crud = CampaignCRUD(db)
        custom_name = (request.name or "").strip() if hasattr(request, "name") else ""
        campaign_data = {
            "id": campaign_id,
            "name": custom_name or f"Campaign {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "country": request.country,
            "object_type": request.object_type,
            "parsing": request.parsing,
            "auto_answering": request.auto_answering,
            "single_reply_only": request.single_reply_only,
            "use_corporate": request.use_corporate,
            "subject_prompt": request.subject_prompt,
            "body_prompt": request.body_prompt,
            "parsing_prompt": request.parsing_prompt,
            "reply_prompt": request.reply_prompt,
            "tov": request.tov.value if request.tov else None,
            "style": request.style.value if request.style else None,
            "language": request.language,
            "daily_limit": request.daily_limit,
            "timezone": request.timezone,
            "total_queued": len(b2b_objects),
            "status": "pending",
            "started_at": None,
            "request_payload": request.model_dump(mode='json')
        }
        logger.info("Creating campaign with data: auto_answering=%s, parsing=%s, use_corporate=%s", 
                   campaign_data.get('auto_answering'), campaign_data.get('parsing'), campaign_data.get('use_corporate'))
        campaign_crud.create(campaign_data)

        # Create campaign targets
        target_crud = CampaignTargetCRUD(db)
        targets = []
        for obj in b2b_objects:
            targets.append({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign_id,
                "place_id": getattr(obj, 'place_id', None),
                "name": getattr(obj, 'name', None),
                "type": getattr(obj, 'type', None),
                "to_email": getattr(obj, 'email', None),
                "status": 'queued',
                "attempts": 0,
            })
        if targets:
            target_crud.create_bulk(targets)

        logger.info("Campaign created: id=%s, targets=%d", campaign_id, len(b2b_objects))
        return campaign_id, b2b_objects

    @staticmethod
    def get_campaigns_list(db: Session, skip: int = 0, limit: int = 100) -> CampaignListResponse:
        """Get list of all campaigns with basic info"""
        crud = CampaignCRUD(db)
        campaigns = crud.get_all(skip=skip, limit=limit)
        total = crud.count()
        
        campaign_responses = []
        for campaign in campaigns:
            campaign_info = SimpleCampaignInfo(
                campaign_id=campaign.id,
                name=campaign.name,
                status=campaign.status,
                started_at=campaign.started_at,
                finished_at=campaign.finished_at,
                created_at=campaign.created_at,
                country=campaign.country,
                object_type=campaign.object_type,
                parsing=campaign.parsing,
                auto_answering=campaign.auto_answering,
                use_corporate=campaign.use_corporate,
                tov=campaign.tov,
                style=campaign.style,
                language=campaign.language,
                total_queued=campaign.total_queued,
                total_sent=campaign.total_sent,
                total_failed=campaign.total_failed,
                total_replied=campaign.total_replied,
            )
            campaign_responses.append(campaign_info)
        
        return CampaignListResponse(
            campaigns=campaign_responses,
            total=total
        )

    @staticmethod
    def delete_campaign(campaign_id: str, db: Session) -> None:
        """Delete completed campaign and related records."""
        campaign_crud = CampaignCRUD(db)
        campaign = campaign_crud.get_by_id(campaign_id)
        if not campaign:
            raise AppError(f"CAMPAIGN_NOT_FOUND: campaign {campaign_id} not found", status_code=404)

        db.query(EmailThread).filter(EmailThread.campaign_id == campaign_id).delete(synchronize_session=False)
        db.query(SentEmail).filter(SentEmail.campaign_id == campaign_id).delete(synchronize_session=False)
        db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign_id).delete(synchronize_session=False)

        campaign_crud.delete(campaign_id)

    @staticmethod
    def get_campaign_status(campaign_id: str, db: Session) -> CampaignObjectsStatusResponse:
        """Get campaign status with B2B objects and their statuses"""
        campaign_crud = CampaignCRUD(db)
        campaign = campaign_crud.get_by_id(campaign_id)
        
        if not campaign:
            return None
        
        logger.info("Getting campaign status: id=%s, auto_answering=%s, parsing=%s, use_corporate=%s",
                   campaign_id, campaign.auto_answering, campaign.parsing, campaign.use_corporate)
        
        # Get all campaign targets
        targets = db.query(CampaignTarget).filter(CampaignTarget.campaign_id == campaign_id).all()
        thread_ids = [t.thread_id for t in targets if t.thread_id]
        reply_counts: dict[str, int] = {}
        if thread_ids:
            reply_rows = (
                db.query(EmailThread.thread_id.label("thread_id"), func.count().label("reply_count"))
                .filter(
                    EmailThread.thread_id.in_(thread_ids),
                    EmailThread.campaign_id == campaign_id,
                    EmailThread.message_type == MessageType.received,
                )
                .group_by(EmailThread.thread_id)
                .all()
            )
            reply_counts = {row.thread_id: row.reply_count for row in reply_rows}
        
        # Build objects list from campaign_targets
        objects = []
        for target in targets:
            from_email_val = None
            if target.thread_id:
                # Find sent email by thread_id AND b2b_place_id to get the correct one for this specific target
                query = db.query(SentEmail).filter(
                    SentEmail.thread_id == target.thread_id,
                    SentEmail.campaign_id == campaign_id,
                    SentEmail.to_email == target.to_email
                )
                # If target has place_id, filter by it to get the exact sent_email for this target
                if target.place_id:
                    query = query.filter(SentEmail.b2b_place_id == target.place_id)
                sent_email = query.first()
                if sent_email:
                    from_email_val = sent_email.from_email
            
            objects.append(B2BObjectWithStatus(
                place_id=target.place_id or "",
                name=target.name,
                type=target.type,
                email=target.to_email,
                email_status=target.status,
                planned_send_at=target.planned_send_at,
                sent_at=target.sent_at,
                from_email=from_email_val,
                error=target.last_error,
                generation_error=target.generation_error,
                reply_count=reply_counts.get(target.thread_id, 0),
            ))
        
        # Calculate statistics
        total = len(targets)
        sent = sum(1 for t in targets if t.status == 'sent')
        failed = sum(1 for t in targets if t.status == 'failed')
        replied = sum(1 for t in targets if t.status == 'replied')
        bounced = sum(1 for t in targets if t.status == 'bounced')
        
        
        statistics = SimpleCampaignStatistics(
            total=total,
            sent=sent,
            failed=failed,
            replied=replied,
            bounced=bounced
        )
        
        # Calculate time estimates from database (always available, independent of tracker state)
        now = datetime.now(timezone.utc)
        next_send_in_seconds = None
        estimated_seconds_to_finish = None
        
        # Find next scheduled send: earliest planned_send_at that is in the future and not yet sent
        # Statuses that can still be sent: queued, enriching, generated, scheduled, sending
        next_scheduled = db.query(CampaignTarget.planned_send_at).filter(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.planned_send_at.isnot(None),
            CampaignTarget.planned_send_at > now,
            CampaignTarget.sent_at.is_(None),
            CampaignTarget.status.in_(['queued', 'enriching', 'generated', 'scheduled', 'sending'])
        ).order_by(CampaignTarget.planned_send_at.asc()).first()
        
        if next_scheduled and next_scheduled[0]:
            next_send_delta = next_scheduled[0] - now
            next_send_in_seconds = max(0, int(next_send_delta.total_seconds()))
        
        # Calculate time to last planned send (ETA to finish)
        if campaign.status in ['in_progress', 'pending']:
            # Find the latest planned_send_at for targets that are not yet sent
            latest_planned = db.query(CampaignTarget.planned_send_at).filter(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.planned_send_at.isnot(None),
                CampaignTarget.sent_at.is_(None),
                CampaignTarget.status.in_(['queued', 'enriching', 'generated', 'scheduled', 'sending'])
            ).order_by(CampaignTarget.planned_send_at.desc()).first()
            
            if latest_planned and latest_planned[0]:
                time_to_last = latest_planned[0] - now
                estimated_seconds_to_finish = max(0, int(time_to_last.total_seconds()))
        
        from app.core.settings import settings
        
        return CampaignObjectsStatusResponse(
            campaign_id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            started_at=campaign.started_at,
            finished_at=campaign.finished_at,
            country=campaign.country,
            object_type=campaign.object_type,
            parsing=campaign.parsing,
            auto_answering=campaign.auto_answering,
            use_corporate=campaign.use_corporate,
            subject_prompt=campaign.subject_prompt,
            body_prompt=campaign.body_prompt,
            parsing_prompt=campaign.parsing_prompt,
            reply_prompt=campaign.reply_prompt,
            tov=campaign.tov,
            style=campaign.style,
            language=campaign.language,
            daily_limit=campaign.daily_limit,
            timezone=campaign.timezone,
            work_start_hour=settings.campaign_work_start_hour,
            work_end_hour=settings.campaign_work_end_hour,
            statistics=statistics,
            objects=objects,
            next_send_in_seconds=next_send_in_seconds,
            estimated_seconds_to_finish=estimated_seconds_to_finish,
        )

    @staticmethod
    def get_campaign_object_details(campaign_id: str, object_id: str, db: Session) -> dict:
        """Get detailed information about a specific campaign object"""
        # URL decode the object_id
        import urllib.parse
        decoded_object_id = urllib.parse.unquote(object_id)
        print(f"DEBUG: Looking for object_id='{object_id}' -> decoded='{decoded_object_id}'")
        
        # Get campaign info
        campaign_crud = CampaignCRUD(db)
        campaign = campaign_crud.get_by_id(campaign_id)
        if not campaign:
            print(f"DEBUG: Campaign {campaign_id} not found")
            return None
        
        # Get campaign target - search by place_id, not id
        target_crud = CampaignTargetCRUD(db)
        target = db.query(CampaignTarget).filter(
            CampaignTarget.place_id == decoded_object_id,
            CampaignTarget.campaign_id == campaign_id
        ).first()
        
        if not target:
            print(f"DEBUG: Target {decoded_object_id} not found in campaign {campaign_id}")
            return None
        
        # Get sent email details if exists
        sent_email = None
        print(f"DEBUG: Target thread_id: {target.thread_id}, place_id: {target.place_id}, to_email: {target.to_email}")
        if target.thread_id:
            # Find sent email by thread_id AND b2b_place_id to get the correct one for this specific target
            # Multiple targets can share the same thread_id, but each has unique place_id
            sent_email_crud = SentEmailCRUD(db)
            query = db.query(SentEmail).filter(
                SentEmail.thread_id == target.thread_id,
                SentEmail.campaign_id == campaign_id
            )
            # If target has place_id, filter by it to get the exact sent_email for this target
            if target.place_id:
                query = query.filter(SentEmail.b2b_place_id == target.place_id)
            # Also filter by to_email to ensure we get the right one
            query = query.filter(SentEmail.to_email == target.to_email)
            sent_email = query.first()
            print(f"DEBUG: Found sent_email: {sent_email.id if sent_email else 'None'}")
        
        # If no sent_email record but we have generated content in target, create a virtual sent_email
        # Only create virtual sent_email if the target is not sent yet
        if not sent_email and (target.email_subject or target.email_body) and target.status not in ['sent', 'replied', 'bounced']:
            # Try to find sent_email by place_id and to_email without thread_id filter
            # This helps when thread_id is not set yet but sent_email exists
            from_email = "Unknown Sender"  # Default placeholder
            if target.place_id:
                alt_sent_email = db.query(SentEmail).filter(
                    SentEmail.b2b_place_id == target.place_id,
                    SentEmail.campaign_id == campaign_id,
                    SentEmail.to_email == target.to_email
                ).first()
                if alt_sent_email:
                    # Found actual sent_email, use it instead of creating virtual one
                    sent_email = alt_sent_email
                else:
                    # No sent_email found, create virtual one with placeholder
                    sent_email = type('SentEmail', (), {
                        'id': f"generated_{target.id}",
                        'from_email': from_email,
                        'to_email': target.to_email,
                        'subject': target.email_subject or '',
                        'body': target.email_body or '',
                        'status': target.status,
                        'message_id': None,
                        'error': target.last_error,
                        'sender_name': None,
                        'server_id': None,
                        'provider': None,
                        'sent_at': target.sent_at,
                        'thread_id': target.thread_id,
                        'created_at': target.created_at if hasattr(target, 'created_at') else None,
                    })()
            else:
                # No place_id, create virtual sent_email with placeholder
                sent_email = type('SentEmail', (), {
                    'id': f"generated_{target.id}",
                    'from_email': from_email,
                    'to_email': target.to_email,
                    'subject': target.email_subject or '',
                    'body': target.email_body or '',
                    'status': target.status,
                    'message_id': None,
                    'error': target.last_error,
                    'sender_name': None,
                    'server_id': None,
                    'provider': None,
                    'sent_at': target.sent_at,
                    'thread_id': target.thread_id,
                    'created_at': target.created_at if hasattr(target, 'created_at') else None,
                })()
        
        # Get B2B object details if exists
        b2b_object = None
        if target.place_id and not target.place_id.startswith("email_"):
            b2b_crud = B2BObjectCRUD(db)
            b2b_object = b2b_crud.get_by_place_id(target.place_id)
        
        return {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "country": campaign.country,
                "object_type": campaign.object_type,
                "parsing": campaign.parsing,
                "auto_answering": campaign.auto_answering,
                "use_corporate": campaign.use_corporate,
                "tov": campaign.tov,
                "style": campaign.style,
                "language": campaign.language,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            },
                "target": {
                    "id": target.id,
                    "place_id": target.place_id,
                    "name": target.name,
                    "type": target.type,
                    "to_email": target.to_email,
                    "status": target.status,
                    "attempts": target.attempts,
                    "last_error": target.last_error,
                    "generation_error": target.generation_error,
                    "planned_send_at": target.planned_send_at.isoformat() if target.planned_send_at else None,
                    "sent_at": target.sent_at.isoformat() if target.sent_at else None,
                    "email_subject": target.email_subject,
                    "email_body": target.email_body,
                    "email_language": target.email_language,
                    "thread_id": target.thread_id,
                },
                "sent_email": {
                    "id": sent_email.id,
                    "from_email": sent_email.from_email,
                    "to_email": sent_email.to_email,
                    "subject": sent_email.subject,
                    "body": sent_email.body,
                    "status": sent_email.status if sent_email.status else None,
                    "message_id": sent_email.message_id,
                    "error": sent_email.error,
                    "sender_name": sent_email.sender_name,
                    "server_id": sent_email.server_id,
                    "provider": sent_email.provider,
                    "sent_at": sent_email.sent_at.isoformat() if sent_email.sent_at else None,
                    "thread_id": sent_email.thread_id,
                    "created_at": sent_email.created_at.isoformat() if sent_email.created_at else None,
                } if sent_email else None,
            "b2b_object": {
                "place_id": b2b_object.place_id,
                "name": b2b_object.name,
                "type": b2b_object.type,
                "email": b2b_object.email,
                "phone": b2b_object.phone,
                "website": b2b_object.website,
                "address": b2b_object.address,
                "city": b2b_object.city,
                "country": b2b_object.country,
                "description": b2b_object.description,
                "created_at": b2b_object.created_at.isoformat() if b2b_object.created_at else None,
            } if b2b_object else None,
        }
        
        print(f"DEBUG: Returning result with thread_id: {result['target']['thread_id']}")
        print(f"DEBUG: Returning sent_email thread_id: {result['sent_email']['thread_id'] if result['sent_email'] else 'None'}")
        
        return result

    @staticmethod
    def pause_campaign(campaign_id: str, db: Session) -> bool:
        """Pause campaign"""
        campaign_crud = CampaignCRUD(db)
        campaign = campaign_crud.get_by_id(campaign_id)
        
        if not campaign or campaign.status not in ('in_progress', 'pending'):
            return False
        
        campaign_crud.set_status(campaign_id, 'paused')
        logger.info("Campaign paused: id=%s", campaign_id)
        return True

    @staticmethod
    def resume_campaign(campaign_id: str, db: Session) -> bool:
        """Resume paused campaign"""
        campaign_crud = CampaignCRUD(db)
        campaign = campaign_crud.get_by_id(campaign_id)
        
        if not campaign or campaign.status != 'paused':
            return False
        
        campaign_crud.set_status(campaign_id, 'in_progress', started_at=datetime.now(timezone.utc))
        logger.info("Campaign resumed: id=%s", campaign_id)
        return True

