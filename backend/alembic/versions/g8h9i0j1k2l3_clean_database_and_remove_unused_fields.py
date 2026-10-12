"""Clean database and remove unused fields

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2025-01-22 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'g8h9i0j1k2l3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    # Clear all data except b2b_objects and alembic_versions
    op.execute("DELETE FROM email_threads")
    op.execute("DELETE FROM sent_emails")
    op.execute("DELETE FROM campaign_targets")
    op.execute("DELETE FROM campaigns")
    
    # Remove unused fields from sent_emails table
    op.drop_column('sent_emails', 'reply_received_at')
    op.drop_column('sent_emails', 'reply_subject')
    op.drop_column('sent_emails', 'reply_body')
    op.drop_column('sent_emails', 'reply_from')
    
    # Remove unused fields from campaign_targets table
    op.drop_column('campaign_targets', 'sent_email_id')
    
    # Add thread_id to sent_emails for linking to email_threads
    op.add_column('sent_emails', sa.Column('thread_id', sa.String(255), nullable=True, comment='ID thread для зв\'язку з email_threads'))
    
    # Add thread_id to campaign_targets for easy lookup
    op.add_column('campaign_targets', sa.Column('thread_id', sa.String(255), nullable=True, comment='ID thread для зв\'язку з email_threads'))
    
    # Create indexes for new fields
    op.create_index('idx_sent_emails_thread_id', 'sent_emails', ['thread_id'])
    op.create_index('idx_campaign_targets_thread_id', 'campaign_targets', ['thread_id'])


def downgrade():
    # Remove new fields
    op.drop_index('idx_campaign_targets_thread_id', table_name='campaign_targets')
    op.drop_index('idx_sent_emails_thread_id', table_name='sent_emails')
    op.drop_column('campaign_targets', 'thread_id')
    op.drop_column('sent_emails', 'thread_id')
    
    # Restore old fields
    op.add_column('campaign_targets', sa.Column('sent_email_id', sa.String(255), nullable=True))
    op.add_column('sent_emails', sa.Column('reply_from', sa.String(255), nullable=True))
    op.add_column('sent_emails', sa.Column('reply_body', sa.Text(), nullable=True))
    op.add_column('sent_emails', sa.Column('reply_subject', sa.Text(), nullable=True))
    op.add_column('sent_emails', sa.Column('reply_received_at', sa.DateTime(timezone=True), nullable=True))
