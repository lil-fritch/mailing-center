"""add campaign_targets and campaign extra fields

Revision ID: d1e2f3a4b5c6
Revises: 3907719c0122
Create Date: 2025-10-16 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '3907719c0122'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add extra fields to campaigns
    op.add_column('campaigns', sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True, comment='Останній пульс воркера'))
    op.add_column('campaigns', sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True, comment='Час постановки на паузу'))
    op.add_column('campaigns', sa.Column('break_reason', sa.Text(), nullable=True, comment='Причина зупинки (збій)'))
    op.add_column('campaigns', sa.Column('request_payload', sa.JSON(), nullable=True, comment='Оригінальні налаштування кампанії для відновлення'))

    # Create campaign_targets table
    op.create_table(
        'campaign_targets',
        sa.Column('id', sa.String(length=255), nullable=False, comment='Унікальний ідентифікатор цілі кампанії'),
        sa.Column('campaign_id', sa.String(length=255), nullable=False, comment='ID кампанії'),
        sa.Column('place_id', sa.String(length=255), nullable=True, comment='ID B2B об\'єкта'),
        sa.Column('name', sa.String(length=500), nullable=True, comment='Назва об\'єкта/контакту'),
        sa.Column('type', sa.String(length=100), nullable=True, comment='Тип об\'єкта'),
        sa.Column('to_email', sa.String(length=255), nullable=False, comment='Email одержувача'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending', comment='pending/sending/sent/failed/skipped'),
        sa.Column('attempts', sa.Integer(), nullable=True, server_default='0', comment='К-сть спроб відправки'),
        sa.Column('last_error', sa.Text(), nullable=True, comment='Остання помилка'),
        sa.Column('sent_email_id', sa.String(length=255), nullable=True, comment='ID запису у sent_emails'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True, comment='Час відправки'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата створення'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True, comment='Дата оновлення'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE')
    )

    op.create_index('idx_campaign_target_campaign', 'campaign_targets', ['campaign_id'])
    op.create_index('idx_campaign_target_status', 'campaign_targets', ['status'])
    op.create_index('idx_campaign_target_to_email', 'campaign_targets', ['to_email'])


def downgrade() -> None:
    op.drop_index('idx_campaign_target_to_email', table_name='campaign_targets')
    op.drop_index('idx_campaign_target_status', table_name='campaign_targets')
    op.drop_index('idx_campaign_target_campaign', table_name='campaign_targets')
    op.drop_table('campaign_targets')

    op.drop_column('campaigns', 'request_payload')
    op.drop_column('campaigns', 'break_reason')
    op.drop_column('campaigns', 'paused_at')
    op.drop_column('campaigns', 'heartbeat_at')


