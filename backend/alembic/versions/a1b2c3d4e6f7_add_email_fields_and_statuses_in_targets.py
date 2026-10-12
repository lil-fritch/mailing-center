"""add email fields and widen statuses in campaign_targets

Revision ID: a1b2c3d4e6f7
Revises: f6a7b8c9d0e1
Create Date: 2025-10-16 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e6f7'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaign_targets', sa.Column('email_subject', sa.Text(), nullable=True, comment='Згенерована тема'))
    op.add_column('campaign_targets', sa.Column('email_body', sa.Text(), nullable=True, comment='Згенерований текст'))
    op.add_column('campaign_targets', sa.Column('email_language', sa.String(length=10), nullable=True, comment='Мова листа'))
    op.add_column('campaign_targets', sa.Column('generation_error', sa.Text(), nullable=True, comment='Помилка генерації'))


def downgrade() -> None:
    op.drop_column('campaign_targets', 'generation_error')
    op.drop_column('campaign_targets', 'email_language')
    op.drop_column('campaign_targets', 'email_body')
    op.drop_column('campaign_targets', 'email_subject')


