"""Add email_threads table for conversation threads

Revision ID: f7a8b9c0d1e2
Revises: f65df263156f
Create Date: 2025-01-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = '502af0aced37'
branch_labels = None
depends_on = None


def upgrade():
    # Create email_threads table
    op.create_table('email_threads',
        sa.Column('id', sa.String(255), nullable=False, comment='Унікальний ідентифікатор повідомлення'),
        sa.Column('thread_id', sa.String(255), nullable=False, comment='ID thread (зв\'язує всі повідомлення в розмові)'),
        sa.Column('campaign_id', sa.String(255), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, comment='ID кампанії'),
        sa.Column('sent_email_id', sa.String(255), sa.ForeignKey('sent_emails.id', ondelete='CASCADE'), nullable=True, comment='ID відправленого листа (якщо це наша відповідь)'),
        sa.Column('message_type', sa.Enum('sent', 'received', name='message_type'), nullable=False, comment='Тип повідомлення: відправлене або отримане'),
        sa.Column('from_email', sa.String(255), nullable=False, comment='Відправник'),
        sa.Column('to_email', sa.String(255), nullable=False, comment='Одержувач'),
        sa.Column('subject', sa.Text(), nullable=True, comment='Тема листа'),
        sa.Column('body', sa.Text(), nullable=True, comment='Тіло листа'),
        sa.Column('message_id', sa.String(500), nullable=True, comment='ID повідомлення від провайдера'),
        sa.Column('in_reply_to', sa.String(500), nullable=True, comment='ID повідомлення на яке відповідаємо'),
        sa.Column('references', sa.Text(), nullable=True, comment='References header для thread'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='Дата створення'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_email_threads_thread_id', 'email_threads', ['thread_id'])
    op.create_index('idx_email_threads_campaign_id', 'email_threads', ['campaign_id'])
    op.create_index('idx_email_threads_sent_email_id', 'email_threads', ['sent_email_id'])
    op.create_index('idx_email_threads_message_type', 'email_threads', ['message_type'])
    op.create_index('idx_email_threads_created_at', 'email_threads', ['created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_email_threads_created_at', table_name='email_threads')
    op.drop_index('idx_email_threads_message_type', table_name='email_threads')
    op.drop_index('idx_email_threads_sent_email_id', table_name='email_threads')
    op.drop_index('idx_email_threads_campaign_id', table_name='email_threads')
    op.drop_index('idx_email_threads_thread_id', table_name='email_threads')
    
    # Drop table
    op.drop_table('email_threads')
