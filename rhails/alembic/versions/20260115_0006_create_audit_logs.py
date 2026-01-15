"""Create audit_logs table

Revision ID: 20260115_0006
Revises: 20260115_0005
Create Date: 2026-01-15 00:06:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260115_0006'
down_revision: str | None = '20260115_0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create audit_logs table."""
    op.create_table(
        'audit_logs',
        sa.Column('log_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_command', sa.Text, nullable=False),
        sa.Column('parsed_intent', sa.JSON, nullable=False),
        sa.Column('openshift_operation', sa.String(100), nullable=False),
        sa.Column('operation_result', sa.JSON, nullable=False),
        sa.Column('operation_error', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
    )

    # Create indexes
    op.create_index('idx_user_audit', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('idx_session_audit', 'audit_logs', ['session_id'])
    op.create_index('idx_timestamp', 'audit_logs', ['timestamp'])

    # Create rules to prevent updates and deletes (PostgreSQL specific)
    op.execute("""
        CREATE RULE prevent_audit_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
    """)
    op.execute("""
        CREATE RULE prevent_audit_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
    """)


def downgrade() -> None:
    """Drop audit_logs table."""
    # Drop rules first
    op.execute("DROP RULE IF EXISTS prevent_audit_delete ON audit_logs;")
    op.execute("DROP RULE IF EXISTS prevent_audit_update ON audit_logs;")

    # Drop indexes
    op.drop_index('idx_timestamp', table_name='audit_logs')
    op.drop_index('idx_session_audit', table_name='audit_logs')
    op.drop_index('idx_user_audit', table_name='audit_logs')

    # Drop table
    op.drop_table('audit_logs')
