"""Create messages table

Revision ID: 20260115_0002
Revises: 20260115_0001
Create Date: 2026-01-15 00:02:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0002'
down_revision: str | None = '20260115_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create messages table."""
    op.create_table(
        'messages',
        sa.Column('message_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('conversation_sessions.session_id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name='messages_role_check'),
        sa.CheckConstraint("length(content) <= 10000", name='messages_content_length_check'),
    )

    # Create index for session_id and timestamp
    op.create_index('idx_session_messages', 'messages', ['session_id', 'timestamp'])


def downgrade() -> None:
    """Drop messages table."""
    op.drop_index('idx_session_messages', table_name='messages')
    op.drop_table('messages')
