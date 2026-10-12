"""create_campaigns_and_sent_emails_tables

Revision ID: 3907719c0122
Revises: c015be7f05bd
Create Date: 2025-10-07 15:12:24.145670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3907719c0122'
down_revision: Union[str, None] = 'c015be7f05bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.String(length=255), nullable=False, comment='Унікальний ідентифікатор кампанії'),
        sa.Column('name', sa.String(length=500), nullable=True, comment='Назва кампанії'),
        
        # Налаштування кампанії
        sa.Column('country', sa.String(length=100), nullable=True, comment='Фільтр по країні'),
        sa.Column('object_type', sa.String(length=100), nullable=True, comment='Фільтр по типу об\'єкта'),
        sa.Column('parsing', sa.Boolean(), nullable=True, server_default='false', comment='Чи використовується парсинг'),
        sa.Column('auto_answering', sa.Boolean(), nullable=True, server_default='false', comment='Чи включена автовідповідь'),
        sa.Column('use_corporate', sa.Boolean(), nullable=True, server_default='false', comment='Використання корпоративних акаунтів'),
        
        # Промпти
        sa.Column('subject_prompt', sa.Text(), nullable=True, comment='Промпт для генерації теми листа'),
        sa.Column('body_prompt', sa.Text(), nullable=True, comment='Промпт для генерації тіла листа'),
        sa.Column('parsing_prompt', sa.Text(), nullable=True, comment='Промпт для парсингу'),
        sa.Column('reply_prompt', sa.Text(), nullable=True, comment='Промпт для автовідповіді'),
        
        # Стилістика
        sa.Column('tov', sa.String(length=50), nullable=True, comment='Tone of voice'),
        sa.Column('style', sa.String(length=50), nullable=True, comment='Стиль написання'),
        sa.Column('language', sa.String(length=10), nullable=True, server_default='pl', comment='Мова листа'),
        
        # Обмеження
        sa.Column('daily_limit', sa.Integer(), nullable=True, comment='Денний ліміт відправки'),
        sa.Column('timezone', sa.String(length=10), nullable=True, comment='Часовий пояс'),
        
        # Статистика
        sa.Column('total_queued', sa.Integer(), nullable=True, server_default='0', comment='Всього в черзі'),
        sa.Column('total_sent', sa.Integer(), nullable=True, server_default='0', comment='Всього відправлено'),
        sa.Column('total_failed', sa.Integer(), nullable=True, server_default='0', comment='Всього з помилками'),
        sa.Column('total_replied', sa.Integer(), nullable=True, server_default='0', comment='Всього з відповідями'),
        sa.Column('total_bounced', sa.Integer(), nullable=True, server_default='0', comment='Всього повернуто'),
        
        # Системні поля
        sa.Column('status', sa.String(length=50), nullable=True, server_default='pending', comment='Статус кампанії: pending, in_progress, completed, failed'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Час початку'),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True, comment='Час завершення'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата створення'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата оновлення'),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for campaigns
    op.create_index('idx_campaign_status', 'campaigns', ['status'])
    op.create_index('idx_campaign_created_at', 'campaigns', ['created_at'])
    op.create_index('idx_campaign_started_at', 'campaigns', ['started_at'])
    
    # Create sent_emails table
    op.create_table(
        'sent_emails',
        sa.Column('id', sa.String(length=255), nullable=False, comment='Унікальний ідентифікатор відправленого листа'),
        sa.Column('campaign_id', sa.String(length=255), nullable=False, comment='ID кампанії'),
        
        # Інформація про об'єкт
        sa.Column('b2b_place_id', sa.String(length=255), nullable=True, comment='ID B2B об\'єкта'),
        sa.Column('b2b_name', sa.String(length=500), nullable=True, comment='Назва B2B об\'єкта'),
        sa.Column('b2b_type', sa.String(length=100), nullable=True, comment='Тип B2B об\'єкта'),
        
        # Email деталі
        sa.Column('from_email', sa.String(length=255), nullable=False, comment='Відправник'),
        sa.Column('to_email', sa.String(length=255), nullable=False, comment='Одержувач'),
        sa.Column('subject', sa.Text(), nullable=True, comment='Тема листа'),
        sa.Column('body', sa.Text(), nullable=True, comment='Тіло листа'),
        
        # Статус
        sa.Column('status', sa.Enum('PENDING', 'SENDING', 'SENT', 'FAILED', 'REPLIED', 'BOUNCED', name='emailstatus'), nullable=False, server_default='PENDING', comment='Статус відправки'),
        sa.Column('message_id', sa.String(length=500), nullable=True, comment='ID повідомлення від провайдера'),
        sa.Column('error', sa.Text(), nullable=True, comment='Опис помилки якщо є'),
        
        # Додаткова інформація
        sa.Column('sender_name', sa.String(length=255), nullable=True, comment='Ім\'я відправника'),
        sa.Column('server_id', sa.String(length=50), nullable=True, comment='ID сервера'),
        sa.Column('provider', sa.String(length=100), nullable=True, comment='Email провайдер'),
        
        # Відповіді
        sa.Column('reply_received_at', sa.DateTime(timezone=True), nullable=True, comment='Час отримання відповіді'),
        sa.Column('reply_subject', sa.Text(), nullable=True, comment='Тема відповіді'),
        sa.Column('reply_body', sa.Text(), nullable=True, comment='Тіло відповіді'),
        sa.Column('reply_from', sa.String(length=255), nullable=True, comment='Від кого відповідь'),
        
        # Системні поля
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True, comment='Час відправки'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата створення'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата оновлення'),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE')
    )
    
    # Create indexes for sent_emails
    op.create_index('idx_sent_email_campaign', 'sent_emails', ['campaign_id'])
    op.create_index('idx_sent_email_status', 'sent_emails', ['status'])
    op.create_index('idx_sent_email_to', 'sent_emails', ['to_email'])
    op.create_index('idx_sent_email_from', 'sent_emails', ['from_email'])
    op.create_index('idx_sent_email_sent_at', 'sent_emails', ['sent_at'])
    op.create_index('idx_sent_email_b2b_place_id', 'sent_emails', ['b2b_place_id'])


def downgrade() -> None:
    # Drop indexes for sent_emails
    op.drop_index('idx_sent_email_b2b_place_id', 'sent_emails')
    op.drop_index('idx_sent_email_sent_at', 'sent_emails')
    op.drop_index('idx_sent_email_from', 'sent_emails')
    op.drop_index('idx_sent_email_to', 'sent_emails')
    op.drop_index('idx_sent_email_status', 'sent_emails')
    op.drop_index('idx_sent_email_campaign', 'sent_emails')
    
    # Drop sent_emails table
    op.drop_table('sent_emails')
    
    # Drop indexes for campaigns
    op.drop_index('idx_campaign_started_at', 'campaigns')
    op.drop_index('idx_campaign_created_at', 'campaigns')
    op.drop_index('idx_campaign_status', 'campaigns')
    
    # Drop campaigns table
    op.drop_table('campaigns')
    
    # Drop enum type
    op.execute('DROP TYPE emailstatus')
