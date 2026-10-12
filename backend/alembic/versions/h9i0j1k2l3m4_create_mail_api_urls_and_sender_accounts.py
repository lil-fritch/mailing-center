"""Create mail_api_urls and sender_accounts tables

Revision ID: h9i0j1k2l3m4
Revises: 91d2d95d6d89
Create Date: 2025-01-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h9i0j1k2l3m4'
down_revision: Union[str, None] = '91d2d95d6d89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mail_api_urls table
    op.create_table('mail_api_urls',
    sa.Column('id', sa.String(length=255), nullable=False, comment='Унікальний ідентифікатор URL'),
    sa.Column('name', sa.String(length=255), nullable=False, comment='Назва/опис URL (наприклад, \'Personal\', \'Corporate\')'),
    sa.Column('url', sa.String(length=500), nullable=False, comment='URL API для відправки email'),
    sa.Column('endpoint', sa.String(length=100), nullable=False, server_default='/email/send', comment='Endpoint path'),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Чи активний цей URL'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата створення'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата оновлення'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_mail_api_url_active', 'mail_api_urls', ['is_active'], unique=False)
    op.create_index('idx_mail_api_url_name', 'mail_api_urls', ['name'], unique=False)
    
    # Create sender_accounts table
    op.create_table('sender_accounts',
    sa.Column('id', sa.String(length=255), nullable=False, comment='Унікальний ідентифікатор акаунта'),
    sa.Column('email', sa.String(length=255), nullable=False, comment='Email адреса акаунта'),
    sa.Column('password', sa.String(length=500), nullable=True, comment='Пароль або app password'),
    sa.Column('first_name', sa.String(length=255), nullable=True, comment='Ім\'я відправника'),
    sa.Column('last_name', sa.String(length=255), nullable=True, comment='Прізвище відправника'),
    sa.Column('imap_host', sa.String(length=255), nullable=True, comment='IMAP хост'),
    sa.Column('imap_port', sa.Integer(), nullable=False, server_default='993', comment='IMAP порт'),
    sa.Column('imap_ssl', sa.Boolean(), nullable=False, server_default='true', comment='Чи використовувати SSL для IMAP'),
    sa.Column('vps', sa.String(length=100), nullable=True, comment='VPS назва'),
    sa.Column('server_id', sa.String(length=50), nullable=False, server_default='1', comment='ID сервера (1 для personal, 2 для corporate)'),
    sa.Column('mail_api_url_id', sa.String(length=255), nullable=True, comment='ID URL API для відправки'),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Чи активний акаунт'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата створення'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата оновлення'),
    sa.ForeignKeyConstraint(['mail_api_url_id'], ['mail_api_urls.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_index('idx_sender_account_email', 'sender_accounts', ['email'], unique=False)
    op.create_index('idx_sender_account_server_id', 'sender_accounts', ['server_id'], unique=False)
    op.create_index('idx_sender_account_active', 'sender_accounts', ['is_active'], unique=False)
    op.create_index('idx_sender_account_mail_api_url', 'sender_accounts', ['mail_api_url_id'], unique=False)


def downgrade() -> None:
    # Drop sender_accounts table and indexes
    op.drop_index('idx_sender_account_mail_api_url', table_name='sender_accounts')
    op.drop_index('idx_sender_account_active', table_name='sender_accounts')
    op.drop_index('idx_sender_account_server_id', table_name='sender_accounts')
    op.drop_index('idx_sender_account_email', table_name='sender_accounts')
    op.drop_table('sender_accounts')
    
    # Drop mail_api_urls table and indexes
    op.drop_index('idx_mail_api_url_name', table_name='mail_api_urls')
    op.drop_index('idx_mail_api_url_active', table_name='mail_api_urls')
    op.drop_table('mail_api_urls')

