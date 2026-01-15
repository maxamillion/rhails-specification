"""Create operation_requests table

Revision ID: 20260115_0004
Revises: 20260115_0003
Create Date: 2026-01-15 00:04:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0004'
down_revision: str | None = '20260115_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create operation_requests table."""
    op.create_table(
        'operation_requests',
        sa.Column('operation_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('intent_id', UUID(as_uuid=True), sa.ForeignKey('user_intents.intent_id'), nullable=False),
        sa.Column('operation_type', sa.String(20), nullable=False),
        sa.Column('api_group', sa.String(100), nullable=False),
        sa.Column('api_version', sa.String(20), nullable=False),
        sa.Column('resource_plural', sa.String(50), nullable=False),
        sa.Column('namespace', sa.String(255), nullable=False),
        sa.Column('resource_name', sa.String(255), nullable=True),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('confirmation_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "operation_type IN ('create', 'get', 'list', 'patch', 'delete')",
            name='operation_requests_operation_type_check'
        ),
        sa.CheckConstraint(
            "confirmation_status IN ('pending', 'confirmed', 'rejected')",
            name='operation_requests_confirmation_status_check'
        ),
    )


def downgrade() -> None:
    """Drop operation_requests table."""
    op.drop_table('operation_requests')
