"""add error field to email_threads

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2025-01-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l3m4n5o6p7q8'
down_revision: Union[str, None] = 'k2l3m4n5o6p7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add error column to email_threads table
    op.add_column(
        'email_threads',
        sa.Column(
            'error',
            sa.Text(),
            nullable=True,
            comment="Помилка відправки авто-відповіді, якщо не вдалося відправити"
        )
    )


def downgrade() -> None:
    # Remove error column from email_threads table
    op.drop_column('email_threads', 'error')



