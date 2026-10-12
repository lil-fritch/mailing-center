"""fix stale alembic version

Revision ID: j1k2l3m4n5o6
Revises: 533cb6ecd1e8
Create Date: 2025-11-18 18:05:00.000000

This migration fixes databases that have stale version 'j1k2l3m4n5o6' in alembic_version table.
This version appears in DB but doesn't exist in migration files - likely from deleted migration
or manual DB change. This migration normalizes the version to allow subsequent migrations.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, None] = '533cb6ecd1e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # If current version is 'j1k2l3m4n5o6', this means DB thinks it's at this version
    # but this migration file exists now, so we just need to confirm we're at correct state
    # No actual schema changes needed - this is just a version marker fix
    pass


def downgrade() -> None:
    # No downgrade needed for this fix
    pass

