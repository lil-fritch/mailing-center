"""add campaign next_wake_at

Revision ID: e7a1b2c3d4e5
Revises: d1e2f3a4b5c6
Create Date: 2025-10-16 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1b2c3d4e5'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('next_wake_at', sa.DateTime(timezone=True), nullable=True, comment='Коли воркер планує прокинутися для наступної відправки'))


def downgrade() -> None:
    op.drop_column('campaigns', 'next_wake_at')


