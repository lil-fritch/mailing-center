"""increase timezone column size

Revision ID: i9j0k1l2m3n4
Revises: j1k2l3m4n5o6
Create Date: 2025-11-18 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Increase timezone column size from 10 to 50 to support full timezone names like 'Europe/Warsaw'
    # Use SQL directly for PostgreSQL to ensure it works correctly
    op.execute("ALTER TABLE campaigns ALTER COLUMN timezone TYPE VARCHAR(50)")


def downgrade() -> None:
    # Revert timezone column size back to 10
    op.execute("ALTER TABLE campaigns ALTER COLUMN timezone TYPE VARCHAR(10)")

