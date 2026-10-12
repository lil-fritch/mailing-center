"""add single_reply_only to campaigns

Revision ID: k2l3m4n5o6p7
Revises: i9j0k1l2m3n4
Create Date: 2025-01-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k2l3m4n5o6p7'
down_revision: Union[str, None] = 'i9j0k1l2m3n4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add single_reply_only column to campaigns table
    op.add_column(
        'campaigns',
        sa.Column(
            'single_reply_only',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment="Чи відправляти лише одну автовідповідь за thread (далі лише зберігати листи)"
        )
    )


def downgrade() -> None:
    # Remove single_reply_only column from campaigns table
    op.drop_column('campaigns', 'single_reply_only')


