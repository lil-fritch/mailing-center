"""remove_break_reason_from_campaigns

Revision ID: f65df263156f
Revises: a1b2c3d4e6f7
Create Date: 2025-10-17 16:16:14.088206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f65df263156f'
down_revision: Union[str, None] = 'a1b2c3d4e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('campaigns', 'break_reason')


def downgrade() -> None:
    op.add_column('campaigns', sa.Column('break_reason', sa.Text(), nullable=True, comment='Причина зупинки (збій)'))
