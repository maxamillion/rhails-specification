"""Create conversation_sessions table

Revision ID: 20260115_0001
Revises:
Create Date: 2026-01-15 00:01:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create conversation_sessions table."""
    op.create_table(
        'conversation_sessions',
        sa.Column('session_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived', 'expired')", name='conversation_sessions_status_check'),
    )

    # Create index for user_id and updated_at
    op.create_index('idx_user_sessions', 'conversation_sessions', ['user_id', 'updated_at'])


def downgrade() -> None:
    """Drop conversation_sessions table."""
    op.drop_index('idx_user_sessions', table_name='conversation_sessions')
    op.drop_table('conversation_sessions')
