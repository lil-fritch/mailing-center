from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime
from .models import B2BObject, Campaign, SentEmail, EmailStatus, CampaignTarget, EmailThread, MessageType, MailApiUrl, SenderAccount


class B2BObjectCRUD:
    """CRUD операції для B2B об'єктів"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_data: Dict[str, Any]) -> B2BObject:
        """Створити новий B2B об'єкт"""
        db_obj = B2BObject(**obj_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get_by_place_id(self, place_id: str) -> Optional[B2BObject]:
        """Отримати B2B об'єкт за place_id"""
        return self.db.query(B2BObject).filter(B2BObject.place_id == place_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[B2BObject]:
        """Отримати всі B2B об'єкти з пагінацією"""
        try:
            return self.db.query(B2BObject).offset(skip).limit(limit).all()
        except UnicodeDecodeError as e:
            # Якщо є проблеми з кодуванням, спробуємо отримати тільки основні поля
            try:
                return self.db.query(B2BObject.place_id, B2BObject.name, B2BObject.type, 
                                   B2BObject.email, B2BObject.phone, B2BObject.website,
                                   B2BObject.address, B2BObject.city, B2BObject.country).offset(skip).limit(limit).all()
            except Exception:
                return []
    
    def update(self, place_id: str, obj_data: Dict[str, Any]) -> Optional[B2BObject]:
        """Оновити B2B об'єкт"""
        db_obj = self.get_by_place_id(place_id)
        if not db_obj:
            return None
        
        for key, value in obj_data.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, place_id: str) -> bool:
        """Видалити B2B об'єкт"""
        db_obj = self.get_by_place_id(place_id)
        if not db_obj:
            return False
        
        self.db.delete(db_obj)
        self.db.commit()
        return True
    
    def search(self, 
               query: Optional[str] = None,
               obj_type: Optional[str] = None,
               city: Optional[str] = None,
               country: Optional[str] = None,
               has_email: Optional[bool] = None,
               skip: int = 0,
               limit: int = 100) -> List[B2BObject]:
        """Пошук B2B об'єктів за різними критеріями"""
        q = self.db.query(B2BObject)
        
        # Пошук по тексту (назва, опис, адреса) з обробкою кодування
        if query:
            try:
                # Переконуємося, що query в UTF-8
                query_utf8 = query.encode('utf-8', errors='ignore').decode('utf-8')
                search_filter = or_(
                    B2BObject.name.ilike(f"%{query_utf8}%"),
                    B2BObject.description.ilike(f"%{query_utf8}%"),
                    B2BObject.address.ilike(f"%{query_utf8}%"),
                    B2BObject.owner_name.ilike(f"%{query_utf8}%")
                )
                q = q.filter(search_filter)
            except UnicodeError:
                # Якщо є проблеми з кодуванням, пропускаємо пошук
                pass
        
        # Фільтр по типу
        if obj_type:
            try:
                obj_type_utf8 = obj_type.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.type == obj_type_utf8)
            except UnicodeError:
                pass
        
        # Фільтр по місту
        if city:
            try:
                city_utf8 = city.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.city.ilike(f"%{city_utf8}%"))
            except UnicodeError:
                pass
        
        # Фільтр по країні
        if country:
            try:
                country_utf8 = country.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.country.ilike(f"%{country_utf8}%"))
            except UnicodeError:
                pass
        
        # Фільтр по наявності email
        if has_email is not None:
            if has_email:
                q = q.filter(B2BObject.email.isnot(None))
            else:
                q = q.filter(B2BObject.email.is_(None))
        
        return q.offset(skip).limit(limit).all()
    
    def count_filtered(self,
                       obj_type: Optional[str] = None,
                       city: Optional[str] = None,
                       country: Optional[str] = None,
                       has_email: Optional[bool] = None) -> int:
        """Підрахувати кількість B2B об'єктів за фільтрами"""
        q = self.db.query(func.count(B2BObject.place_id))

        if obj_type:
            try:
                obj_type_utf8 = obj_type.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.type == obj_type_utf8)
            except UnicodeError:
                pass

        if city:
            try:
                city_utf8 = city.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.city.ilike(f"%{city_utf8}%"))
            except UnicodeError:
                pass

        if country:
            try:
                country_utf8 = country.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.country.ilike(f"%{country_utf8}%"))
            except UnicodeError:
                pass

        if has_email is not None:
            if has_email:
                q = q.filter(B2BObject.email.isnot(None))
            else:
                q = q.filter(B2BObject.email.is_(None))

        result = q.scalar()
        return int(result or 0)
    
    def get_by_type(self, obj_type: str, skip: int = 0, limit: int = 100) -> List[B2BObject]:
        """Отримати B2B об'єкти за типом"""
        return self.db.query(B2BObject).filter(
            B2BObject.type == obj_type
        ).offset(skip).limit(limit).all()
    
    def get_by_city(self, city: str, skip: int = 0, limit: int = 100) -> List[B2BObject]:
        """Отримати B2B об'єкти за містом"""
        return self.db.query(B2BObject).filter(
            B2BObject.city.ilike(f"%{city}%")
        ).offset(skip).limit(limit).all()
    
    def get_with_email(self, skip: int = 0, limit: int = 100) -> List[B2BObject]:
        """Отримати B2B об'єкти, які мають email"""
        return self.db.query(B2BObject).filter(
            B2BObject.email.isnot(None)
        ).offset(skip).limit(limit).all()

    def get_by_emails(self, emails: List[str]) -> List[B2BObject]:
        """Отримати B2B об'єкти за списком email-адрес."""
        if not emails:
            return []
        # Нормалізуємо пробіли
        normalized = [e.strip() for e in emails if e and e.strip()]
        if not normalized:
            return []
        return self.db.query(B2BObject).filter(B2BObject.email.in_(normalized)).all()
    
    def count(self) -> int:
        """Підрахувати загальну кількість B2B об'єктів"""
        return self.db.query(B2BObject).count()
    
    def count_by_type(self, obj_type: str) -> int:
        """Підрахувати кількість B2B об'єктів за типом"""
        return self.db.query(B2BObject).filter(B2BObject.type == obj_type).count()
    
    def get_types(self) -> List[str]:
        """Отримати список всіх типів B2B об'єктів"""
        result = self.db.query(B2BObject.type).distinct().all()
        return [row[0] for row in result if row[0]]
    
    def get_cities(self) -> List[str]:
        """Отримати список всіх міст"""
        result = self.db.query(B2BObject.city).distinct().all()
        return [row[0] for row in result if row[0]]
    
    def get_countries(self) -> List[str]:
        """Отримати список всіх країн"""
        result = self.db.query(B2BObject.country).distinct().all()
        return [row[0] for row in result if row[0]]

    # Filtered facets
    def get_types_for_country(self, country: str, has_email: Optional[bool] = None) -> List[str]:
        """Отримати типи об'єктів, які існують у вказаній країні (з опційним фільтром наявності email)."""
        q = self.db.query(B2BObject.type).distinct()
        if country:
            try:
                country_utf8 = country.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.country.ilike(f"%{country_utf8}%"))
            except UnicodeError:
                pass
        if has_email is not None:
            if has_email:
                q = q.filter(B2BObject.email.isnot(None))
            else:
                q = q.filter(B2BObject.email.is_(None))
        result = q.all()
        return [row[0] for row in result if row[0]]

    def get_countries_for_type(self, obj_type: str, has_email: Optional[bool] = None) -> List[str]:
        """Отримати країни, де існують об'єкти заданого типу (з опційним фільтром наявності email)."""
        q = self.db.query(B2BObject.country).distinct()
        if obj_type:
            try:
                type_utf8 = obj_type.encode('utf-8', errors='ignore').decode('utf-8')
                q = q.filter(B2BObject.type == type_utf8)
            except UnicodeError:
                pass
        if has_email is not None:
            if has_email:
                q = q.filter(B2BObject.email.isnot(None))
            else:
                q = q.filter(B2BObject.email.is_(None))
        result = q.all()
        return [row[0] for row in result if row[0]]


# Функції-хелпери для швидкого доступу
def create_b2b_object(db: Session, obj_data: Dict[str, Any]) -> B2BObject:
    """Створити B2B об'єкт"""
    crud = B2BObjectCRUD(db)
    return crud.create(obj_data)


def get_b2b_object(db: Session, place_id: str) -> Optional[B2BObject]:
    """Отримати B2B об'єкт за place_id"""
    crud = B2BObjectCRUD(db)
    return crud.get_by_place_id(place_id)


def get_b2b_objects(db: Session, skip: int = 0, limit: int = 100) -> List[B2BObject]:
    """Отримати всі B2B об'єкти"""
    crud = B2BObjectCRUD(db)
    return crud.get_all(skip, limit)


def update_b2b_object(db: Session, place_id: str, obj_data: Dict[str, Any]) -> Optional[B2BObject]:
    """Оновити B2B об'єкт"""
    crud = B2BObjectCRUD(db)
    return crud.update(place_id, obj_data)


def delete_b2b_object(db: Session, place_id: str) -> bool:
    """Видалити B2B об'єкт"""
    crud = B2BObjectCRUD(db)
    return crud.delete(place_id)


def search_b2b_objects(db: Session, **filters) -> List[B2BObject]:
    """Пошук B2B об'єктів"""
    crud = B2BObjectCRUD(db)
    return crud.search(**filters)


class CampaignCRUD:
    """CRUD операції для кампаній"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, campaign_data: Dict[str, Any]) -> Campaign:
        """Створити нову кампанію"""
        db_campaign = Campaign(**campaign_data)
        self.db.add(db_campaign)
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign
    
    def get_by_id(self, campaign_id: str) -> Optional[Campaign]:
        """Отримати кампанію за ID"""
        return self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Campaign]:
        """Отримати всі кампанії з пагінацією"""
        return self.db.query(Campaign).order_by(desc(Campaign.created_at)).offset(skip).limit(limit).all()
    
    def update(self, campaign_id: str, campaign_data: Dict[str, Any]) -> Optional[Campaign]:
        """Оновити кампанію"""
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return None
        
        for key, value in campaign_data.items():
            if hasattr(db_campaign, key):
                setattr(db_campaign, key, value)
        
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign
    
    def delete(self, campaign_id: str) -> bool:
        """Видалити кампанію"""
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return False
        
        self.db.delete(db_campaign)
        self.db.commit()
        return True
    
    def update_statistics(self, campaign_id: str) -> Optional[Campaign]:
        """Оновити статистику кампанії на основі відправлених листів"""
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return None
        
        # Підрахувати статистику з sent_emails
        sent_count = self.db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id,
            SentEmail.status == EmailStatus.SENT
        ).count()
        
        failed_count = self.db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id,
            SentEmail.status == EmailStatus.FAILED
        ).count()
        
        replied_count = self.db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id,
            SentEmail.status == EmailStatus.REPLIED
        ).count()
        
        bounced_count = self.db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id,
            SentEmail.status == EmailStatus.BOUNCED
        ).count()
        
        db_campaign.total_sent = sent_count
        db_campaign.total_failed = failed_count
        db_campaign.total_replied = replied_count
        db_campaign.total_bounced = bounced_count
        
        
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign

    def update_heartbeat(self, campaign_id: str) -> Optional[Campaign]:
        """Оновити heartbeat_at на поточний час (UTC)."""
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return None
        from datetime import datetime, timezone
        db_campaign.heartbeat_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign

    def set_status(self, campaign_id: str, status: str, **fields) -> Optional[Campaign]:
        """Змінити статус кампанії з додатковими полями (paused_at тощо)."""
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return None
        db_campaign.status = status
        for k, v in fields.items():
            if hasattr(db_campaign, k):
                setattr(db_campaign, k, v)
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign

    def set_next_wake_at(self, campaign_id: str, when) -> Optional[Campaign]:
        db_campaign = self.get_by_id(campaign_id)
        if not db_campaign:
            return None
        db_campaign.next_wake_at = when
        self.db.commit()
        self.db.refresh(db_campaign)
        return db_campaign
    
    def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Campaign]:
        """Отримати кампанії за статусом"""
        return self.db.query(Campaign).filter(
            Campaign.status == status
        ).order_by(desc(Campaign.created_at)).offset(skip).limit(limit).all()
    
    def count(self) -> int:
        """Підрахувати загальну кількість кампаній"""
        return self.db.query(Campaign).count()


class SentEmailCRUD:
    """CRUD операції для відправлених email"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, email_data: Dict[str, Any]) -> SentEmail:
        """Створити запис про відправлений email"""
        db_email = SentEmail(**email_data)
        self.db.add(db_email)
        self.db.commit()
        self.db.refresh(db_email)
        return db_email
    
    def get_by_id(self, email_id: str) -> Optional[SentEmail]:
        """Отримати відправлений email за ID"""
        return self.db.query(SentEmail).filter(SentEmail.id == email_id).first()
    
    def get_by_campaign(self, campaign_id: str, skip: int = 0, limit: int = 1000) -> List[SentEmail]:
        """Отримати всі відправлені листи для кампанії"""
        return self.db.query(SentEmail).filter(
            SentEmail.campaign_id == campaign_id
        ).order_by(desc(SentEmail.created_at)).offset(skip).limit(limit).all()
    
    def get_by_to_email(self, to_email: str) -> List[SentEmail]:
        """Отримати всі листи відправлені на конкретний email"""
        return self.db.query(SentEmail).filter(
            SentEmail.to_email == to_email
        ).order_by(desc(SentEmail.sent_at)).all()
    
    def update(self, email_id: str, email_data: Dict[str, Any]) -> Optional[SentEmail]:
        """Оновити відправлений email"""
        db_email = self.get_by_id(email_id)
        if not db_email:
            return None
        
        for key, value in email_data.items():
            if hasattr(db_email, key):
                setattr(db_email, key, value)
        
        self.db.commit()
        self.db.refresh(db_email)
        return db_email
    
    def update_status(self, email_id: str, status: EmailStatus, error: Optional[str] = None) -> Optional[SentEmail]:
        """Оновити статус відправленого email"""
        db_email = self.get_by_id(email_id)
        if not db_email:
            return None
        
        db_email.status = status
        if error:
            db_email.error = error
        if status == EmailStatus.SENT and not db_email.sent_at:
            db_email.sent_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(db_email)
        return db_email
    
    def mark_as_replied(self, to_email: str, from_email: str, reply_subject: str, reply_body: str, 
                       in_reply_to: Optional[str] = None, message_id: Optional[str] = None) -> List[SentEmail]:
        """Позначити листи як ті, на які отримана відповідь.
        
        Використовує headers та subject для точного зв'язування:
        - Якщо є in_reply_to, шукає лист з відповідним message_id (найточніший)
        - Якщо є message_id, шукає лист з відповідним message_id в thread
        - Інакше використовує subject для пошуку правильного листа
        
        Повертає тільки ОДИН лист, який точно відповідає відповіді.
        """
        from app.database.models import EmailThread
        from sqlalchemy import or_
        
        email = None
        
        # Спробувати знайти через in_reply_to (найточніший метод)
        if in_reply_to:
            # in_reply_to вказує на message_id нашого відправленого листа
            thread_crud = EmailThreadCRUD(self.db)
            replied_thread = thread_crud.find_thread_by_message_id(in_reply_to)
            if replied_thread:
                # Спочатку спробувати знайти SentEmail через thread
                email = self.db.query(SentEmail).filter(
                    SentEmail.thread_id == replied_thread.thread_id,
                    SentEmail.campaign_id == replied_thread.campaign_id,
                    SentEmail.status.in_([EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING])
                ).order_by(SentEmail.sent_at.desc()).first()
                
                # Якщо не знайдено в SentEmail, це може бути авто-відповідь, яка збережена тільки в email_threads
                # В такому випадку, якщо знайдено thread з правильним message_id, це означає що відповідь на авто-відповідь
                # Повертаємо порожній список, але thread вже знайдено, тому inbound_processor зможе обробити
                if not email:
                    # Перевірити, чи це відправлене повідомлення (авто-відповідь)
                    from app.database.models import MessageType
                    if replied_thread.message_type == MessageType.sent:
                        # Це авто-відповідь, яка збережена тільки в email_threads
                        # Створити фейковий SentEmail для обробки (або повернути None і обробити через thread)
                        # Але краще повернути None і обробити через thread в inbound_processor
                        pass
        
        # Якщо не знайдено через in_reply_to, спробувати через message_id в thread
        if not email and message_id:
            thread_crud = EmailThreadCRUD(self.db)
            # Шукаємо thread, де є повідомлення з цим message_id
            thread = thread_crud.find_thread_by_message_id(message_id)
            if thread:
                # Знайти SentEmail в цьому thread
                email = self.db.query(SentEmail).filter(
                    SentEmail.thread_id == thread.thread_id,
                    SentEmail.campaign_id == thread.campaign_id,
                    SentEmail.status.in_([EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING])
                ).order_by(SentEmail.sent_at.desc()).first()
        
        # Fallback: використовувати subject для пошуку правильного листа
        # Відповідь має subject типу "Re: Original Subject", тому шукаємо лист з "Original Subject"
        if not email and reply_subject:
            # Видалити "Re:", "RE:", "Fwd:", "FWD:" та інші префікси
            import re
            cleaned_subject = re.sub(r'^(Re:|RE:|Fwd:|FWD:|Fw:|FW:)\s*', '', reply_subject, flags=re.IGNORECASE).strip()
            
            # Шукати лист з subject, який відповідає cleaned_subject
            # Можливо точний збіг або cleaned_subject містить original subject
            all_candidates = self.db.query(SentEmail).filter(
                SentEmail.to_email == from_email,  # Відповідь прийшла від того, кому ми відправляли
                SentEmail.from_email == to_email,  # Відповідь прийшла на адресу, з якої ми відправляли
                SentEmail.status.in_([EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING])
            ).order_by(SentEmail.sent_at.desc()).all()
            
            # Спробувати знайти точний збіг subject
            for candidate in all_candidates:
                if candidate.subject:
                    candidate_clean = candidate.subject.strip()
                    # Перевірити чи cleaned_subject містить candidate_clean або навпаки
                    if cleaned_subject.lower() == candidate_clean.lower():
                        email = candidate
                        break
                    # Або чи cleaned_subject починається з candidate_clean (для випадків коли додається текст)
                    elif cleaned_subject.lower().startswith(candidate_clean.lower()):
                        email = candidate
                        break
                    # Або чи candidate_clean міститься в cleaned_subject
                    elif candidate_clean.lower() in cleaned_subject.lower():
                        email = candidate
                        break
            
            # Якщо не знайдено за subject, взяти останній лист (fallback)
            if not email and all_candidates:
                email = all_candidates[0]
        
        # If no email found, return empty list
        if not email:
            return []
        
        emails = [email]
        
        updated = []
        for email in emails:
            email.status = EmailStatus.REPLIED
            updated.append(email)
            
            # Also update corresponding CampaignTarget status
            if email.campaign_id:
                target = self.db.query(CampaignTarget).filter(
                    CampaignTarget.campaign_id == email.campaign_id,
                    CampaignTarget.to_email == email.to_email,
                    CampaignTarget.status.in_(['sent', 'sending', 'scheduled'])
                ).first()
                if target:
                    target.status = 'replied'
        
        if updated:
            self.db.commit()
            for email in updated:
                self.db.refresh(email)
        
        return updated

    def mark_as_bounced(self, to_email: str, bounce_subject: str, bounce_body: str) -> List[SentEmail]:
        """Позначити листи як ті, які повернулись (bounce) через недійсну адресу"""
        # Знайти всі листи відправлені НА цей email, які ще не мають відповіді або bounce
        emails = self.db.query(SentEmail).filter(
            SentEmail.to_email == to_email,  # Bounce для листів відправлених НА цю адресу
            SentEmail.status.in_([EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING])
        ).all()
        
        updated = []
        for email in emails:
            email.status = EmailStatus.BOUNCED
            email.reply_received_at = datetime.utcnow()
            email.reply_subject = bounce_subject
            email.reply_body = bounce_body
            email.reply_from = "bounce-system"  # Системний відправник для bounce
            updated.append(email)
            
            # Also update corresponding CampaignTarget status
            if email.campaign_id:
                target_crud = CampaignTargetCRUD(self.db)
                target = self.db.query(CampaignTarget).filter(
                    CampaignTarget.campaign_id == email.campaign_id,
                    CampaignTarget.to_email == email.to_email,
                    CampaignTarget.status.in_(['sent', 'sending', 'scheduled'])
                ).first()
                if target:
                    target.status = 'bounced'
        
        if updated:
            self.db.commit()
            for email in updated:
                self.db.refresh(email)
        
        return updated

    def mark_as_bounced_fallback(self, from_email: str, bounce_subject: str, bounce_body: str) -> List[SentEmail]:
        """Fallback: позначити недавні листи від цієї адреси як bounced (менш точно)"""
        # Знайти листи відправлені з цієї адреси за останні 24 години
        from datetime import datetime, timezone, timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        
        emails = self.db.query(SentEmail).filter(
            SentEmail.from_email == from_email,
            SentEmail.status.in_([EmailStatus.SENT, EmailStatus.PENDING, EmailStatus.SENDING]),
            SentEmail.created_at >= yesterday
        ).all()
        
        updated = []
        for email in emails:
            email.status = EmailStatus.BOUNCED
            email.reply_received_at = datetime.utcnow()
            email.reply_subject = bounce_subject
            email.reply_body = bounce_body
            email.reply_from = "bounce-system"
            updated.append(email)
            
            # Also update corresponding CampaignTarget status
            if email.campaign_id:
                target = self.db.query(CampaignTarget).filter(
                    CampaignTarget.campaign_id == email.campaign_id,
                    CampaignTarget.to_email == email.to_email,
                    CampaignTarget.status.in_(['sent', 'sending', 'scheduled'])
                ).first()
                if target:
                    target.status = 'bounced'
        
        if updated:
            self.db.commit()
            for email in updated:
                self.db.refresh(email)
        
        return updated

    def get_by_status(self, status: EmailStatus, skip: int = 0, limit: int = 100) -> List[SentEmail]:
        """Отримати листи за статусом"""
        return self.db.query(SentEmail).filter(
            SentEmail.status == status
        ).order_by(desc(SentEmail.created_at)).offset(skip).limit(limit).all()
    
    def get_statistics_by_campaign(self, campaign_id: str) -> Dict[str, int]:
        """Отримати статистику по кампанії"""
        stats = {
            "total": 0,
            "pending": 0,
            "sending": 0,
            "sent": 0,
            "failed": 0,
            "replied": 0,
            "bounced": 0,
        }
        
        result = self.db.query(
            SentEmail.status,
            func.count(SentEmail.id)
        ).filter(
            SentEmail.campaign_id == campaign_id
        ).group_by(SentEmail.status).all()
        
        for status, count in result:
            stats["total"] += count
            stats[status.value.lower()] = count
        
        return stats
    
    def delete(self, email_id: str) -> bool:
        """Видалити запис про відправлений email"""
        db_email = self.get_by_id(email_id)
        if not db_email:
            return False
        
        self.db.delete(db_email)
        self.db.commit()
        return True


class CampaignTargetCRUD:
    """CRUD для campaign_targets"""

    def __init__(self, db: Session):
        self.db = db

    def create_bulk(self, targets: list[dict]) -> int:
        objs = [CampaignTarget(**t) for t in targets]
        self.db.add_all(objs)
        self.db.commit()
        return len(objs)

    def next_pending(self, campaign_id: str) -> Optional[CampaignTarget]:
        # Prefer the earliest planned_send_at among scheduled; fall back to created_at
        q = self.db.query(CampaignTarget).filter(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.status == 'scheduled'
        )
        # Correct SQL generation: ASC NULLS LAST
        return q.order_by(
            CampaignTarget.planned_send_at.asc().nulls_last(),
            CampaignTarget.created_at.asc(),
        ).first()

    def mark_sending(self, target_id: str) -> Optional[CampaignTarget]:
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.status = 'sending'
        obj.attempts = (obj.attempts or 0) + 1
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def set_planned_send_at_bulk(self, campaign_id: str, items: list[tuple[str, object]]) -> int:
        # items: [(target_id, planned_send_at_utc), ...]
        updated = 0
        for target_id, planned in items:
            obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
            if not obj:
                continue
            obj.planned_send_at = planned
            # Якщо статус 'generated', змінюємо на 'scheduled'
            if obj.status == 'generated':
                obj.status = 'scheduled'
            updated += 1
        if updated:
            self.db.commit()
        return updated

    def mark_sent(self, target_id: str, thread_id: str, sent_at) -> Optional[CampaignTarget]:
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.status = 'sent'
        obj.thread_id = thread_id
        obj.sent_at = sent_at
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def mark_failed(self, target_id: str, error: str) -> Optional[CampaignTarget]:
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.status = 'failed'
        obj.last_error = error
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update_status(self, target_id: str, status: str) -> Optional[CampaignTarget]:
        """Оновити статус target"""
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.status = status
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def set_enriching(self, target_id: str) -> Optional[CampaignTarget]:
        """Встановити статус 'enriching' перед початком обогачення"""
        return self.update_status(target_id, 'enriching')

    def set_generated(self, target_id: str, subject: str, body: str, language: Optional[str]) -> Optional[CampaignTarget]:
        """Встановити статус 'generated' після генерації листа"""
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.email_subject = subject
        obj.email_body = body
        obj.email_language = language
        obj.status = 'generated'
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def set_scheduled(self, target_id: str) -> Optional[CampaignTarget]:
        """Встановити статус 'scheduled' після планування відправки"""
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.status = 'scheduled'
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def set_generation_error(self, target_id: str, error: str) -> Optional[CampaignTarget]:
        obj = self.db.query(CampaignTarget).filter(CampaignTarget.id == target_id).first()
        if not obj:
            return None
        obj.generation_error = error
        obj.status = 'failed'
        self.db.commit()
        self.db.refresh(obj)
        return obj


# Функції-хелпери для швидкого доступу
def create_campaign(db: Session, campaign_data: Dict[str, Any]) -> Campaign:
    """Створити кампанію"""
    crud = CampaignCRUD(db)
    return crud.create(campaign_data)


def get_campaign(db: Session, campaign_id: str) -> Optional[Campaign]:
    """Отримати кампанію за ID"""
    crud = CampaignCRUD(db)
    return crud.get_by_id(campaign_id)


def get_campaigns(db: Session, skip: int = 0, limit: int = 100) -> List[Campaign]:
    """Отримати всі кампанії"""
    crud = CampaignCRUD(db)
    return crud.get_all(skip, limit)


def update_campaign(db: Session, campaign_id: str, campaign_data: Dict[str, Any]) -> Optional[Campaign]:
    """Оновити кампанію"""
    crud = CampaignCRUD(db)
    return crud.update(campaign_id, campaign_data)


def create_sent_email(db: Session, email_data: Dict[str, Any]) -> SentEmail:
    """Створити запис про відправлений email"""
    crud = SentEmailCRUD(db)
    return crud.create(email_data)


def get_sent_email(db: Session, email_id: str) -> Optional[SentEmail]:
    """Отримати відправлений email за ID"""
    crud = SentEmailCRUD(db)
    return crud.get_by_id(email_id)


def get_campaign_emails(db: Session, campaign_id: str, skip: int = 0, limit: int = 1000) -> List[SentEmail]:
    """Отримати всі відправлені листи для кампанії"""
    crud = SentEmailCRUD(db)
    return crud.get_by_campaign(campaign_id, skip, limit)


def mark_email_as_replied(db: Session, to_email: str, from_email: str, reply_subject: str, reply_body: str,
                          in_reply_to: Optional[str] = None, message_id: Optional[str] = None) -> List[SentEmail]:
    """Позначити листи як ті, на які отримана відповідь"""
    crud = SentEmailCRUD(db)
    return crud.mark_as_replied(to_email, from_email, reply_subject, reply_body, in_reply_to, message_id)


def mark_email_as_bounced(db: Session, to_email: str, bounce_subject: str, bounce_body: str) -> List[SentEmail]:
    """Позначити листи як ті, які повернулись (bounce) через недійсну адресу"""
    crud = SentEmailCRUD(db)
    return crud.mark_as_bounced(to_email, bounce_subject, bounce_body)


def mark_email_as_bounced_fallback(db: Session, from_email: str, bounce_subject: str, bounce_body: str) -> List[SentEmail]:
    """Fallback: позначити недавні листи від цієї адреси як bounced"""
    crud = SentEmailCRUD(db)
    return crud.mark_as_bounced_fallback(from_email, bounce_subject, bounce_body)


class EmailThreadCRUD:
    """CRUD операції для email threads"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, thread_data: Dict[str, Any]) -> EmailThread:
        """Створити нове повідомлення в thread"""
        print(f"DEBUG: Creating EmailThread with data: {thread_data}")
        thread = EmailThread(**thread_data)
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)
        print(f"DEBUG: Successfully created EmailThread with id: {thread.id}")
        return thread
    
    def get_by_thread_id(self, thread_id: str) -> List[EmailThread]:
        """Отримати всі повідомлення в thread"""
        return self.db.query(EmailThread).filter(
            EmailThread.thread_id == thread_id
        ).order_by(EmailThread.created_at.asc()).all()
    
    def get_by_campaign_id(self, campaign_id: str) -> List[EmailThread]:
        """Отримати всі threads для кампанії"""
        return self.db.query(EmailThread).filter(
            EmailThread.campaign_id == campaign_id
        ).order_by(EmailThread.created_at.asc()).all()
    
    def get_threads_by_email(self, from_email: str, to_email: str) -> List[str]:
        """Отримати всі thread_id для пари email адрес"""
        threads = self.db.query(EmailThread.thread_id).filter(
            or_(
                and_(EmailThread.from_email == from_email, EmailThread.to_email == to_email),
                and_(EmailThread.from_email == to_email, EmailThread.to_email == from_email)
            )
        ).distinct().all()
        return [t[0] for t in threads]
    
    def get_latest_thread(self, from_email: str, to_email: str) -> Optional[str]:
        """Отримати найновіший thread_id для пари email адрес"""
        latest = self.db.query(EmailThread.thread_id).filter(
            or_(
                and_(EmailThread.from_email == from_email, EmailThread.to_email == to_email),
                and_(EmailThread.from_email == to_email, EmailThread.to_email == from_email)
            )
        ).order_by(EmailThread.created_at.desc()).first()
        return latest[0] if latest else None
    
    def get_latest_thread_for_campaign(self, campaign_id: str, from_email: str, to_email: str) -> Optional[str]:
        """Отримати найновіший thread_id для пари email адрес в межах конкретної кампанії"""
        latest = self.db.query(EmailThread.thread_id).filter(
            EmailThread.campaign_id == campaign_id,
            or_(
                and_(EmailThread.from_email == from_email, EmailThread.to_email == to_email),
                and_(EmailThread.from_email == to_email, EmailThread.to_email == from_email)
            )
        ).order_by(EmailThread.created_at.desc()).first()
        return latest[0] if latest else None
    
    def find_thread_by_message_id(self, message_id: str) -> Optional[EmailThread]:
        """Знайти thread повідомлення за message_id"""
        if not message_id:
            return None
        thread = self.db.query(EmailThread).filter(
            EmailThread.message_id == message_id
        ).first()
        return thread
    
    def find_thread_by_in_reply_to(self, in_reply_to: str) -> Optional[EmailThread]:
        """Знайти thread повідомлення за in_reply_to (знаходить повідомлення, на яке відповідають)"""
        if not in_reply_to:
            return None
        # in_reply_to вказує на message_id попереднього повідомлення
        thread = self.db.query(EmailThread).filter(
            EmailThread.message_id == in_reply_to
        ).first()
        return thread


def create_email_thread(db: Session, thread_data: Dict[str, Any]) -> EmailThread:
    """Створити нове повідомлення в thread"""
    crud = EmailThreadCRUD(db)
    return crud.create(thread_data)


def get_thread_messages(db: Session, thread_id: str) -> List[EmailThread]:
    """Отримати всі повідомлення в thread"""
    crud = EmailThreadCRUD(db)
    return crud.get_by_thread_id(thread_id)


def get_campaign_threads(db: Session, campaign_id: str) -> List[EmailThread]:
    """Отримати всі threads для кампанії"""
    crud = EmailThreadCRUD(db)
    return crud.get_by_campaign_id(campaign_id)


class MailApiUrlCRUD:
    """CRUD операції для MailApiUrl"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, url_data: Dict[str, Any]) -> MailApiUrl:
        """Створити новий MailApiUrl"""
        db_url = MailApiUrl(**url_data)
        self.db.add(db_url)
        self.db.commit()
        self.db.refresh(db_url)
        return db_url
    
    def get_by_id(self, url_id: str) -> Optional[MailApiUrl]:
        """Отримати MailApiUrl за ID"""
        return self.db.query(MailApiUrl).filter(MailApiUrl.id == url_id).first()
    
    def get_all(self, active_only: bool = False) -> List[MailApiUrl]:
        """Отримати всі MailApiUrl"""
        q = self.db.query(MailApiUrl)
        if active_only:
            q = q.filter(MailApiUrl.is_active == True)
        return q.all()
    
    def update(self, url_id: str, url_data: Dict[str, Any]) -> Optional[MailApiUrl]:
        """Оновити MailApiUrl"""
        db_url = self.get_by_id(url_id)
        if not db_url:
            return None
        
        for key, value in url_data.items():
            if hasattr(db_url, key):
                setattr(db_url, key, value)
        
        self.db.commit()
        self.db.refresh(db_url)
        return db_url
    
    def delete(self, url_id: str) -> bool:
        """Видалити MailApiUrl"""
        db_url = self.get_by_id(url_id)
        if not db_url:
            return False
        
        self.db.delete(db_url)
        self.db.commit()
        return True


class SenderAccountCRUD:
    """CRUD операції для SenderAccount"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, account_data: Dict[str, Any]) -> SenderAccount:
        """Створити новий SenderAccount"""
        db_account = SenderAccount(**account_data)
        self.db.add(db_account)
        self.db.commit()
        self.db.refresh(db_account)
        return db_account
    
    def get_by_id(self, account_id: str) -> Optional[SenderAccount]:
        """Отримати SenderAccount за ID"""
        return self.db.query(SenderAccount).filter(SenderAccount.id == account_id).first()
    
    def get_by_email(self, email: str) -> Optional[SenderAccount]:
        """Отримати SenderAccount за email"""
        return self.db.query(SenderAccount).filter(SenderAccount.email == email).first()
    
    def get_all(self, active_only: bool = False, server_id: Optional[str] = None) -> List[SenderAccount]:
        """Отримати всі SenderAccount з опціональними фільтрами"""
        q = self.db.query(SenderAccount)
        if active_only:
            q = q.filter(SenderAccount.is_active == True)
        if server_id:
            q = q.filter(SenderAccount.server_id == server_id)
        return q.all()
    
    def get_by_server_id(self, server_id: str, active_only: bool = True) -> List[SenderAccount]:
        """Отримати акаунти за server_id"""
        return self.get_all(active_only=active_only, server_id=server_id)
    
    def update(self, account_id: str, account_data: Dict[str, Any]) -> Optional[SenderAccount]:
        """Оновити SenderAccount"""
        db_account = self.get_by_id(account_id)
        if not db_account:
            return None
        
        for key, value in account_data.items():
            if hasattr(db_account, key):
                setattr(db_account, key, value)
        
        self.db.commit()
        self.db.refresh(db_account)
        return db_account
    
    def delete(self, account_id: str) -> bool:
        """Видалити SenderAccount"""
        db_account = self.get_by_id(account_id)
        if not db_account:
            return False
        
        self.db.delete(db_account)
        self.db.commit()
        return True


# Функції-хелпери для швидкого доступу
def create_mail_api_url(db: Session, url_data: Dict[str, Any]) -> MailApiUrl:
    """Створити MailApiUrl"""
    crud = MailApiUrlCRUD(db)
    return crud.create(url_data)


def get_mail_api_url(db: Session, url_id: str) -> Optional[MailApiUrl]:
    """Отримати MailApiUrl за ID"""
    crud = MailApiUrlCRUD(db)
    return crud.get_by_id(url_id)


def get_mail_api_urls(db: Session, active_only: bool = False) -> List[MailApiUrl]:
    """Отримати всі MailApiUrl"""
    crud = MailApiUrlCRUD(db)
    return crud.get_all(active_only=active_only)


def get_mail_api_url_by_account(db: Session, account: SenderAccount) -> Optional[str]:
    """Отримати повний URL API для акаунта (base_url + endpoint)"""
    if account.mail_api_url_id:
        url_obj = MailApiUrlCRUD(db).get_by_id(account.mail_api_url_id)
        if url_obj and url_obj.is_active:
            base_url = url_obj.url.rstrip('/')
            endpoint = url_obj.endpoint.lstrip('/')
            return f"{base_url}/{endpoint}"
    return None


def create_sender_account(db: Session, account_data: Dict[str, Any]) -> SenderAccount:
    """Створити SenderAccount"""
    crud = SenderAccountCRUD(db)
    return crud.create(account_data)


def get_sender_account(db: Session, account_id: str) -> Optional[SenderAccount]:
    """Отримати SenderAccount за ID"""
    crud = SenderAccountCRUD(db)
    return crud.get_by_id(account_id)


def get_sender_accounts(db: Session, active_only: bool = True, server_id: Optional[str] = None) -> List[SenderAccount]:
    """Отримати всі SenderAccount"""
    crud = SenderAccountCRUD(db)
    return crud.get_all(active_only=active_only, server_id=server_id)
