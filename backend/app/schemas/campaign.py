from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class B2BObjectWithStatus(BaseModel):
    """B2B об'єкт зі статусом відправки"""
    
    place_id: str
    name: Optional[str] = None
    type: Optional[str] = None
    email: Optional[str] = None
    
    # Статус листа: queued -> enriching -> generated -> scheduled -> sending -> sent/failed/replied/bounced
    email_status: Optional[str] = Field(None, description="Статус листа: queued, enriching, generated, scheduled, sending, sent, failed, replied, bounced")
    planned_send_at: Optional[datetime] = Field(None, description="Запланований час відправки")
    sent_at: Optional[datetime] = Field(None, description="Фактична дата відправки")
    from_email: Optional[str] = Field(None, description="З якої адреси відправлено")
    error: Optional[str] = Field(None, description="Помилка якщо є")
    generation_error: Optional[str] = Field(None, description="Помилка генерації контенту")
    reply_count: Optional[int] = Field(0, description="Кількість отриманих відповідей для цього об'єкта")
    
    class Config:
        from_attributes = True


class SimpleCampaignStatistics(BaseModel):
    """Спрощена статистика кампанії"""
    
    total: int = Field(..., description="Скільки всього листів має бути")
    sent: int = Field(..., description="Скільки успішно відправлено")
    failed: int = Field(..., description="Скільки не успішно")
    replied: int = Field(..., description="Скільки отримали відповідь")
    bounced: int = Field(0, description="Скільки повернулось (bounced)")


class SentEmailResponse(BaseModel):
    """Відповідь з інформацією про відправлений email"""
    
    id: str
    campaign_id: str
    
    # B2B об'єкт
    b2b_place_id: Optional[str] = None
    b2b_name: Optional[str] = None
    b2b_type: Optional[str] = None
    
    # Email деталі
    from_email: str
    to_email: str
    subject: Optional[str] = None
    body: Optional[str] = None
    
    # Статус
    status: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    
    # Додаткова інформація
    sender_name: Optional[str] = None
    server_id: Optional[str] = None
    provider: Optional[str] = None
    
    # Відповіді
    reply_received_at: Optional[datetime] = None
    reply_subject: Optional[str] = None
    reply_body: Optional[str] = None
    reply_from: Optional[str] = None
    
    # Системні поля
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CampaignStatistics(BaseModel):
    """Статистика кампанії"""
    
    total_queued: int = Field(..., description="Всього в черзі")
    total_sent: int = Field(..., description="Всього відправлено")
    total_failed: int = Field(..., description="Всього з помилками")
    total_replied: int = Field(..., description="Всього з відповідями")
    total_bounced: int = Field(..., description="Всього повернуто")
    total_pending: int = Field(0, description="Всього в очікуванні")
    total_sending: int = Field(0, description="Всього в процесі відправки")
    
    # Відсотки
    success_rate: Optional[float] = Field(None, description="Відсоток успішних відправок")
    reply_rate: Optional[float] = Field(None, description="Відсоток відповідей")


class CampaignResponse(BaseModel):
    """Повна інформація про кампанію"""
    
    id: str
    name: Optional[str] = None
    
    # Налаштування кампанії
    country: Optional[str] = None
    object_type: Optional[str] = None
    parsing: bool = False
    auto_answering: bool = False
    use_corporate: bool = False
    
    # Промпти
    subject_prompt: Optional[str] = None
    body_prompt: Optional[str] = None
    parsing_prompt: Optional[str] = None
    reply_prompt: Optional[str] = None
    
    # Стилістика
    tov: Optional[str] = None
    style: Optional[str] = None
    language: str = "pl"
    
    # Обмеження
    daily_limit: Optional[int] = None
    timezone: Optional[str] = None
    
    # Статистика
    statistics: CampaignStatistics
    
    # Статус
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CampaignStatusResponse(BaseModel):
    """Детальний статус кампанії з списком відправлених emails"""
    
    campaign: CampaignResponse
    sent_emails: List[SentEmailResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class CampaignObjectsStatusResponse(BaseModel):
    """Статус кампанії зі списком B2B об'єктів та їх статусами"""
    
    campaign_id: str
    name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # Фільтри
    country: Optional[str] = None
    object_type: Optional[str] = None
    
    # Налаштування кампанії
    parsing: bool = False
    auto_answering: bool = False
    use_corporate: bool = False
    
    # Промпти
    subject_prompt: Optional[str] = None
    body_prompt: Optional[str] = None
    parsing_prompt: Optional[str] = None
    reply_prompt: Optional[str] = None
    
    # Стилістика
    tov: Optional[str] = Field(None, description="Tone of voice")
    style: Optional[str] = Field(None, description="Writing style")
    language: str = "pl"
    
    # Обмеження
    daily_limit: Optional[int] = None
    timezone: Optional[str] = None
    
    # Work hours (from settings)
    work_start_hour: int = Field(9, description="Start hour for campaign work window (24-hour format)")
    work_end_hour: int = Field(18, description="End hour for campaign work window (24-hour format)")
    
    # Спрощена статистика
    statistics: SimpleCampaignStatistics
    
    # Список об'єктів зі статусами
    objects: List[B2BObjectWithStatus] = Field(default_factory=list)
    # Додаткова інформація
    next_send_in_seconds: Optional[float] = Field(None, description="Скільки секунд залишилось до наступної відправки")
    estimated_seconds_to_finish: Optional[float] = Field(None, description="Орієнтовні секунди до завершення всієї кампанії")
    
    class Config:
        from_attributes = True


class SimpleCampaignInfo(BaseModel):
    """Базова інформація про кампанію для списку"""
    
    campaign_id: str
    name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    
    # Фільтри
    country: Optional[str] = None
    object_type: Optional[str] = None
    
    # Налаштування
    parsing: bool = False
    auto_answering: bool = False
    use_corporate: bool = False
    
    # Стилістика
    tov: Optional[str] = None
    style: Optional[str] = None
    language: str = "pl"
    
    # Проста статистика
    total_queued: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_replied: int = 0
    total_bounced: int = 0
    
    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Список кампаній"""
    
    campaigns: List[SimpleCampaignInfo]
    total: int
    
    class Config:
        from_attributes = True


__all__ = [
    "SentEmailResponse",
    "CampaignStatistics",
    "SimpleCampaignStatistics",
    "SimpleCampaignInfo",
    "CampaignResponse",
    "CampaignStatusResponse",
    "CampaignObjectsStatusResponse",
    "B2BObjectWithStatus",
    "CampaignListResponse",
]

