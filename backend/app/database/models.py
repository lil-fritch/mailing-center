from sqlalchemy import Column, String, Text, DateTime, Index, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .connection import Base


class EmailStatus(str, enum.Enum):
    """Статуси відправлених email"""
    PENDING = "pending"  # В черзі на відправку
    SENDING = "sending"  # В процесі відправки
    SENT = "sent"  # Відправлено
    FAILED = "failed"  # Помилка відправки
    REPLIED = "replied"  # Отримана відповідь
    BOUNCED = "bounced"  # Адреса не існує / повернуто


class MessageType(str, enum.Enum):
    """Типи повідомлень в thread"""
    sent = "sent"  # Відправлене нами
    received = "received"  # Отримане від клієнта


class B2BObject(Base):
    """Модель B2B об'єкта для бази даних"""
    
    __tablename__ = "b2b_objects"
    
    # Основні поля
    place_id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор місця")
    name = Column(String(500), nullable=False, comment="Назва об'єкта")
    type = Column(String(100), nullable=False, comment="Тип об'єкта")
    
    # Контактна інформація
    owner_name = Column(String(255), nullable=True, comment="Ім'я власника")
    email = Column(String(255), nullable=True, comment="Email адреса")
    phone = Column(String(50), nullable=True, comment="Номер телефону")
    website = Column(String(500), nullable=True, comment="Веб-сайт")
    description = Column(Text, nullable=True, comment="Опис об'єкта")
    
    # Адресна інформація
    address = Column(Text, nullable=True, comment="Адреса")
    city = Column(String(100), nullable=True, comment="Місто")
    country = Column(String(100), nullable=True, comment="Країна")
    
    # Системні поля
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")
    
    # Індекси для покращення продуктивності
    __table_args__ = (
        Index('idx_b2b_type', 'type'),
        Index('idx_b2b_city', 'city'),
        Index('idx_b2b_country', 'country'),
        Index('idx_b2b_email', 'email'),
        Index('idx_b2b_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<B2BObject(place_id='{self.place_id}', name='{self.name}', type='{self.type}')>"
    
    def to_dict(self):
        """Конвертує об'єкт в словник"""
        return {
            'place_id': self.place_id,
            'name': self.name,
            'type': self.type,
            'owner_name': self.owner_name,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'description': self.description,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Campaign(Base):
    """Модель кампанії розсилки"""
    
    __tablename__ = "campaigns"
    
    # Основні поля
    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор кампанії")
    name = Column(String(500), nullable=True, comment="Назва кампанії")
    
    # Налаштування кампанії
    country = Column(String(100), nullable=True, comment="Фільтр по країні")
    object_type = Column(String(100), nullable=True, comment="Фільтр по типу об'єкта")
    parsing = Column(Boolean, default=False, comment="Чи використовується парсинг")
    auto_answering = Column(Boolean, default=False, comment="Чи включена автовідповідь")
    single_reply_only = Column(Boolean, default=False, comment="Чи відправляти лише одну автовідповідь за thread (далі лише зберігати листи)")
    use_corporate = Column(Boolean, default=False, comment="Використання корпоративних акаунтів")
    
    # Промпти
    subject_prompt = Column(Text, nullable=True, comment="Промпт для генерації теми листа")
    body_prompt = Column(Text, nullable=True, comment="Промпт для генерації тіла листа")
    parsing_prompt = Column(Text, nullable=True, comment="Промпт для парсингу")
    reply_prompt = Column(Text, nullable=True, comment="Промпт для автовідповіді")
    
    # Стилістика
    tov = Column(String(50), nullable=True, comment="Tone of voice")
    style = Column(String(50), nullable=True, comment="Стиль написання")
    language = Column(String(10), default="pl", comment="Мова листа")
    
    # Обмеження
    daily_limit = Column(Integer, nullable=True, comment="Денний ліміт відправки")
    timezone = Column(String(50), nullable=True, comment="Часовий пояс")
    
    # Статистика
    total_queued = Column(Integer, default=0, comment="Всього в черзі")
    total_sent = Column(Integer, default=0, comment="Всього відправлено")
    total_failed = Column(Integer, default=0, comment="Всього з помилками")
    total_replied = Column(Integer, default=0, comment="Всього з відповідями")
    total_bounced = Column(Integer, default=0, comment="Всього повернуто")
    
    # Системні поля
    status = Column(String(50), default="pending", comment="Статус кампанії: pending, in_progress, completed, failed")
    started_at = Column(DateTime(timezone=True), nullable=True, comment="Час початку")
    finished_at = Column(DateTime(timezone=True), nullable=True, comment="Час завершення")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")
    # Додаткові системні поля
    heartbeat_at = Column(DateTime(timezone=True), nullable=True, comment="Останній пульс воркера")
    paused_at = Column(DateTime(timezone=True), nullable=True, comment="Час постановки на паузу")
    request_payload = Column(JSON, nullable=True, comment="Оригінальні налаштування кампанії для відновлення")
    next_wake_at = Column(DateTime(timezone=True), nullable=True, comment="Очікуваний час пробудження воркера")
    
    # Відношення
    sent_emails = relationship("SentEmail", back_populates="campaign", cascade="all, delete-orphan")
    targets = relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")
    
    # Індекси
    __table_args__ = (
        Index('idx_campaign_status', 'status'),
        Index('idx_campaign_created_at', 'created_at'),
        Index('idx_campaign_started_at', 'started_at'),
    )
    
    def __repr__(self):
        return f"<Campaign(id='{self.id}', name='{self.name}', status='{self.status}')>"


class SentEmail(Base):
    """Модель відправленого email"""
    
    __tablename__ = "sent_emails"
    
    # Основні поля
    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор відправленого листа")
    campaign_id = Column(String(255), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, comment="ID кампанії")
    
    # Інформація про об'єкт
    b2b_place_id = Column(String(255), nullable=True, comment="ID B2B об'єкта")
    b2b_name = Column(String(500), nullable=True, comment="Назва B2B об'єкта")
    b2b_type = Column(String(100), nullable=True, comment="Тип B2B об'єкта")
    
    # Email деталі
    from_email = Column(String(255), nullable=False, comment="Відправник")
    to_email = Column(String(255), nullable=False, comment="Одержувач")
    subject = Column(Text, nullable=True, comment="Тема листа")
    body = Column(Text, nullable=True, comment="Тіло листа")
    
    # Статус
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING, nullable=False, comment="Статус відправки")
    message_id = Column(String(500), nullable=True, comment="ID повідомлення від провайдера")
    error = Column(Text, nullable=True, comment="Опис помилки якщо є")
    
    # Додаткова інформація
    sender_name = Column(String(255), nullable=True, comment="Ім'я відправника")
    server_id = Column(String(50), nullable=True, comment="ID сервера")
    provider = Column(String(100), nullable=True, comment="Email провайдер")
    
    # Thread linking
    thread_id = Column(String(255), nullable=True, comment="ID thread для зв'язку з email_threads")
    
    # Системні поля
    sent_at = Column(DateTime(timezone=True), nullable=True, comment="Час відправки")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")
    
    # Відношення
    campaign = relationship("Campaign", back_populates="sent_emails")
    
    # Індекси
    __table_args__ = (
        Index('idx_sent_email_campaign', 'campaign_id'),
        Index('idx_sent_email_status', 'status'),
        Index('idx_sent_email_to', 'to_email'),
        Index('idx_sent_email_from', 'from_email'),
        Index('idx_sent_email_sent_at', 'sent_at'),
        Index('idx_sent_email_b2b_place_id', 'b2b_place_id'),
    )
    
    def __repr__(self):
        return f"<SentEmail(id='{self.id}', to='{self.to_email}', status='{self.status}')>"


class CampaignTarget(Base):
    """Ціль кампанії (окрема адреса), яку треба відправити"""
    __tablename__ = "campaign_targets"

    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор цілі кампанії")
    campaign_id = Column(String(255), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, comment="ID кампанії")

    # Ідентифікація об'єкта
    place_id = Column(String(255), nullable=True, comment="ID B2B об'єкта")
    name = Column(String(500), nullable=True, comment="Назва об'єкта/контакту")
    type = Column(String(100), nullable=True, comment="Тип об'єкта")

    # Email цілі
    to_email = Column(String(255), nullable=False, comment="Email одержувача")

    # Статус і спроби
    # Статуси: queued -> enriching -> generated -> scheduled -> sending -> sent/failed/replied/bounced
    status = Column(String(50), default="queued", nullable=False, comment="queued/enriching/generated/scheduled/sending/sent/failed/replied/bounced")
    attempts = Column(Integer, default=0, comment="К-сть спроб відправки")
    last_error = Column(Text, nullable=True, comment="Остання помилка")

    # Thread linking
    thread_id = Column(String(255), nullable=True, comment="ID thread для зв'язку з email_threads")
    sent_at = Column(DateTime(timezone=True), nullable=True, comment="Час відправки")
    planned_send_at = Column(DateTime(timezone=True), nullable=True, comment="Запланований час відправки (UTC)")
    # Згенерований контент
    email_subject = Column(Text, nullable=True, comment="Згенерована тема")
    email_body = Column(Text, nullable=True, comment="Згенерований текст")
    email_language = Column(String(10), nullable=True, comment="Мова листа")
    generation_error = Column(Text, nullable=True, comment="Помилка генерації")

    # Системні поля
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")

    # Відношення
    campaign = relationship("Campaign", back_populates="targets")
    
    def __repr__(self):
        return f"<CampaignTarget(id='{self.id}', campaign_id='{self.campaign_id}', to_email='{self.to_email}')>"


class EmailThread(Base):
    """Модель для зберігання всіх повідомлень в email thread"""
    
    __tablename__ = "email_threads"
    
    # Основні поля
    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор повідомлення")
    thread_id = Column(String(255), nullable=False, comment="ID thread (зв'язує всі повідомлення в розмові)")
    campaign_id = Column(String(255), ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, comment="ID кампанії")
    sent_email_id = Column(String(255), ForeignKey('sent_emails.id', ondelete='CASCADE'), nullable=True, comment="ID відправленого листа (якщо це наша відповідь)")
    
    # Тип повідомлення
    message_type = Column(SQLEnum(MessageType), nullable=False, comment="Тип повідомлення: відправлене або отримане")
    
    # Email деталі
    from_email = Column(String(255), nullable=False, comment="Відправник")
    to_email = Column(String(255), nullable=False, comment="Одержувач")
    subject = Column(Text, nullable=True, comment="Тема листа")
    body = Column(Text, nullable=True, comment="Тіло листа")
    
    # Thread деталі
    message_id = Column(String(500), nullable=True, comment="ID повідомлення від провайдера")
    in_reply_to = Column(String(500), nullable=True, comment="ID повідомлення на яке відповідаємо")
    references = Column(Text, nullable=True, comment="References header для thread")
    
    # Помилка відправки (для авто-відповідей)
    error = Column(Text, nullable=True, comment="Помилка відправки авто-відповіді, якщо не вдалося відправити")
    
    # Системні поля
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    
    # Відношення
    campaign = relationship("Campaign")
    sent_email = relationship("SentEmail")
    
    # Індекси
    __table_args__ = (
        Index('idx_email_threads_thread_id', 'thread_id'),
        Index('idx_email_threads_campaign_id', 'campaign_id'),
        Index('idx_email_threads_sent_email_id', 'sent_email_id'),
        Index('idx_email_threads_message_type', 'message_type'),
        Index('idx_email_threads_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<EmailThread(id='{self.id}', thread_id='{self.thread_id}', type='{self.message_type}')>"


class MailApiUrl(Base):
    """Модель для зберігання URL API для відправки email"""
    
    __tablename__ = "mail_api_urls"
    
    # Основні поля
    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор URL")
    name = Column(String(255), nullable=False, comment="Назва/опис URL (наприклад, 'Personal', 'Corporate')")
    url = Column(String(500), nullable=False, comment="URL API для відправки email")
    endpoint = Column(String(100), default="/email/send", nullable=False, comment="Endpoint path")
    is_active = Column(Boolean, default=True, nullable=False, comment="Чи активний цей URL")
    
    # Системні поля
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")
    
    # Відношення
    sender_accounts = relationship("SenderAccount", back_populates="mail_api_url", cascade="all, delete-orphan")
    
    # Індекси
    __table_args__ = (
        Index('idx_mail_api_url_active', 'is_active'),
        Index('idx_mail_api_url_name', 'name'),
    )
    
    def __repr__(self):
        return f"<MailApiUrl(id='{self.id}', name='{self.name}', url='{self.url}')>"


class SenderAccount(Base):
    """Модель для зберігання аккаунтів відправників email"""
    
    __tablename__ = "sender_accounts"
    
    # Основні поля
    id = Column(String(255), primary_key=True, nullable=False, comment="Унікальний ідентифікатор акаунта")
    email = Column(String(255), nullable=False, unique=True, comment="Email адреса акаунта")
    password = Column(String(500), nullable=True, comment="Пароль або app password")
    first_name = Column(String(255), nullable=True, comment="Ім'я відправника")
    last_name = Column(String(255), nullable=True, comment="Прізвище відправника")
    
    # IMAP налаштування
    imap_host = Column(String(255), nullable=True, comment="IMAP хост")
    imap_port = Column(Integer, default=993, nullable=False, comment="IMAP порт")
    imap_ssl = Column(Boolean, default=True, nullable=False, comment="Чи використовувати SSL для IMAP")
    smtp_host = Column(String(255), nullable=True, comment="SMTP хост")
    smtp_port = Column(Integer, nullable=True, comment="SMTP порт")
    selenium_required = Column(Boolean, default=False, nullable=False, comment="Потребує Selenium для відправки")
    
    # VPS та сервер
    server_id = Column(String(50), default="1", nullable=False, comment="ID сервера (1 для personal, 2 для corporate)")
    
    # Зв'язок з MailApiUrl
    mail_api_url_id = Column(String(255), ForeignKey('mail_api_urls.id', ondelete='SET NULL'), nullable=True, comment="ID URL API для відправки")
    
    # Статус
    is_active = Column(Boolean, default=True, nullable=False, comment="Чи активний акаунт")
    
    # Системні поля
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Дата створення")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Дата оновлення")
    
    # Відношення
    mail_api_url = relationship("MailApiUrl", back_populates="sender_accounts")
    
    # Індекси
    __table_args__ = (
        Index('idx_sender_account_email', 'email'),
        Index('idx_sender_account_server_id', 'server_id'),
        Index('idx_sender_account_active', 'is_active'),
        Index('idx_sender_account_mail_api_url', 'mail_api_url_id'),
    )
    
    def __repr__(self):
        return f"<SenderAccount(id='{self.id}', email='{self.email}', server_id='{self.server_id}')>"
