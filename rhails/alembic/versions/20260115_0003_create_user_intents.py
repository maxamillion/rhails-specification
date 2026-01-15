"""Create user_intents table

Revision ID: 20260115_0003
Revises: 20260115_0002
Create Date: 2026-01-15 00:03:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0003'
down_revision: str | None = '20260115_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_intents table."""
    op.create_table(
        'user_intents',
        sa.Column('intent_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', UUID(as_uuid=True), sa.ForeignKey('messages.message_id'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_resources', sa.JSON, nullable=False),
        sa.Column('parameters', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False),
        sa.Column('ambiguities', sa.JSON, nullable=True),
        sa.Column('requires_confirmation', sa.String(10), nullable=False, server_default='false'),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name='user_intents_confidence_check'),
    )


def downgrade() -> None:
    """Drop user_intents table."""
    op.drop_table('user_intents')
