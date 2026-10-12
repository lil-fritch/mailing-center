"""add smtp fields to sender accounts

Revision ID: 533cb6ecd1e8
Revises: h9i0j1k2l3m4
Create Date: 2025-11-12 13:36:32.798995

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '533cb6ecd1e8'
down_revision: Union[str, None] = 'h9i0j1k2l3m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sender_accounts") as batch:
        batch.add_column(sa.Column("smtp_host", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_port", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("selenium_required", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("sender_accounts") as batch:
        batch.drop_column("selenium_required")
        batch.drop_column("smtp_port")
        batch.drop_column("smtp_host")
