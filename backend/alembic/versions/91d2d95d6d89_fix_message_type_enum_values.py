"""fix_message_type_enum_values

Revision ID: 91d2d95d6d89
Revises: g8h9i0j1k2l3
Create Date: 2025-10-24 00:11:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91d2d95d6d89'
down_revision: Union[str, None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Видалити старий enum і створити новий з правильними значеннями
    op.execute("DROP TYPE IF EXISTS messagetype CASCADE")
    op.execute("CREATE TYPE messagetype AS ENUM ('sent', 'received')")
    
    # Оновити колонку в таблиці email_threads
    op.execute("ALTER TABLE email_threads ALTER COLUMN message_type TYPE messagetype USING message_type::text::messagetype")


def downgrade() -> None:
    # Повернути старий enum
    op.execute("DROP TYPE IF EXISTS messagetype CASCADE")
    op.execute("CREATE TYPE messagetype AS ENUM ('SENT', 'RECEIVED')")
    op.execute("ALTER TABLE email_threads ALTER COLUMN message_type TYPE messagetype USING message_type::text::messagetype")
