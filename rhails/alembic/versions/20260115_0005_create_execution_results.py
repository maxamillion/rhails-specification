"""Create execution_results table

Revision ID: 20260115_0005
Revises: 20260115_0004
Create Date: 2026-01-15 00:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0005'
down_revision: str | None = '20260115_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create execution_results table."""
    op.create_table(
        'execution_results',
        sa.Column('result_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('operation_id', UUID(as_uuid=True), sa.ForeignKey('operation_requests.operation_id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('output_data', sa.JSON, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('resource_state', sa.JSON, nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=False),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('success', 'failure', 'partial', 'pending')",
            name='execution_results_status_check'
        ),
        sa.CheckConstraint("retry_count <= 3", name='execution_results_retry_count_check'),
    )


def downgrade() -> None:
    """Drop execution_results table."""
    op.drop_table('execution_results')
