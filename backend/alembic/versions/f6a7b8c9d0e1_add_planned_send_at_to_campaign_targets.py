"""add planned_send_at to campaign_targets

Revision ID: f6a7b8c9d0e1
Revises: e7a1b2c3d4e5
Create Date: 2025-10-16 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaign_targets', sa.Column('planned_send_at', sa.DateTime(timezone=True), nullable=True, comment='Запланований час відправки (UTC)'))
    op.create_index('idx_campaign_target_planned_send_at', 'campaign_targets', ['planned_send_at'])


def downgrade() -> None:
    op.drop_index('idx_campaign_target_planned_send_at', table_name='campaign_targets')
    op.drop_column('campaign_targets', 'planned_send_at')


