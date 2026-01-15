"""Audit logging service for compliance and troubleshooting."""

import uuid
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import AuditLogEntryDB


class AuditLogger:
    """Audit logging service for recording all user operations.

    Provides immutable audit trail of user commands, system interpretations,
    and operation outcomes for compliance and troubleshooting.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize audit logger.

        Args:
            db_session: Database session for writing audit logs
        """
        self.db_session = db_session

    async def log_operation(
        self,
        user_id: str,
        session_id: uuid.UUID,
        user_command: str,
        parsed_intent: dict,
        openshift_operation: str,
        operation_result: dict,
        duration_ms: int,
        operation_error: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> uuid.UUID:
        """Log a user operation to audit trail.

        Args:
            user_id: OpenShift user identity
            session_id: Conversation session ID
            user_command: Original natural language input
            parsed_intent: JSON representation of UserIntent
            openshift_operation: Kubernetes API operation performed
            operation_result: Structured result data
            duration_ms: Total operation duration in milliseconds
            operation_error: Error message if operation failed
            ip_address: User's IP address
            user_agent: Client user agent string

        Returns:
            Audit log entry ID

        Note:
            This operation uses INSERT directly to ensure append-only behavior.
            The audit_logs table has PostgreSQL rules preventing updates/deletes.
        """
        log_id = uuid.uuid4()

        stmt = insert(AuditLogEntryDB).values(
            log_id=log_id,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            user_command=user_command,
            parsed_intent=parsed_intent,
            openshift_operation=openshift_operation,
            operation_result=operation_result,
            operation_error=operation_error,
            duration_ms=duration_ms,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db_session.execute(stmt)
        await self.db_session.commit()

        return log_id

    async def get_user_activity(
        self,
        user_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get user activity from audit logs.

        Args:
            user_id: OpenShift user identity
            start_time: Start of time range (optional)
            end_time: End of time range (optional)
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        from sqlalchemy import select

        query = select(AuditLogEntryDB).where(AuditLogEntryDB.user_id == user_id)

        if start_time:
            query = query.where(AuditLogEntryDB.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLogEntryDB.timestamp <= end_time)

        query = query.order_by(AuditLogEntryDB.timestamp.desc()).limit(limit)

        result = await self.db_session.execute(query)
        entries = result.scalars().all()

        return [
            {
                "log_id": str(entry.log_id),
                "timestamp": entry.timestamp.isoformat(),
                "user_id": entry.user_id,
                "session_id": str(entry.session_id),
                "user_command": entry.user_command,
                "parsed_intent": entry.parsed_intent,
                "openshift_operation": entry.openshift_operation,
                "operation_result": entry.operation_result,
                "operation_error": entry.operation_error,
                "duration_ms": entry.duration_ms,
            }
            for entry in entries
        ]

    async def get_session_audit_trail(
        self, session_id: uuid.UUID
    ) -> list[dict]:
        """Get complete audit trail for a conversation session.

        Args:
            session_id: Conversation session ID

        Returns:
            List of audit log entries for the session
        """
        from sqlalchemy import select

        query = (
            select(AuditLogEntryDB)
            .where(AuditLogEntryDB.session_id == session_id)
            .order_by(AuditLogEntryDB.timestamp.asc())
        )

        result = await self.db_session.execute(query)
        entries = result.scalars().all()

        return [
            {
                "log_id": str(entry.log_id),
                "timestamp": entry.timestamp.isoformat(),
                "user_command": entry.user_command,
                "openshift_operation": entry.openshift_operation,
                "operation_result": entry.operation_result,
                "operation_error": entry.operation_error,
                "duration_ms": entry.duration_ms,
            }
            for entry in entries
        ]

    async def get_failed_operations(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get failed operations from audit logs.

        Args:
            start_time: Start of time range (optional)
            end_time: End of time range (optional)
            limit: Maximum number of entries to return

        Returns:
            List of failed operation audit entries
        """
        from sqlalchemy import select

        query = select(AuditLogEntryDB).where(
            AuditLogEntryDB.operation_error.isnot(None)
        )

        if start_time:
            query = query.where(AuditLogEntryDB.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLogEntryDB.timestamp <= end_time)

        query = query.order_by(AuditLogEntryDB.timestamp.desc()).limit(limit)

        result = await self.db_session.execute(query)
        entries = result.scalars().all()

        return [
            {
                "log_id": str(entry.log_id),
                "timestamp": entry.timestamp.isoformat(),
                "user_id": entry.user_id,
                "user_command": entry.user_command,
                "openshift_operation": entry.openshift_operation,
                "operation_error": entry.operation_error,
                "duration_ms": entry.duration_ms,
            }
            for entry in entries
        ]

    async def get_operation_statistics(
        self,
        user_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Get operation statistics from audit logs.

        Args:
            user_id: Filter by user (optional)
            start_time: Start of time range (optional)
            end_time: End of time range (optional)

        Returns:
            Statistics including total operations, success rate, avg duration
        """
        from sqlalchemy import func, select

        # Build base query
        conditions = []
        if user_id:
            conditions.append(AuditLogEntryDB.user_id == user_id)
        if start_time:
            conditions.append(AuditLogEntryDB.timestamp >= start_time)
        if end_time:
            conditions.append(AuditLogEntryDB.timestamp <= end_time)

        # Total operations
        total_query = select(func.count(AuditLogEntryDB.log_id))
        if conditions:
            total_query = total_query.where(*conditions)
        total_result = await self.db_session.execute(total_query)
        total_operations = total_result.scalar() or 0

        # Failed operations
        failed_query = select(func.count(AuditLogEntryDB.log_id)).where(
            AuditLogEntryDB.operation_error.isnot(None)
        )
        if conditions:
            failed_query = failed_query.where(*conditions)
        failed_result = await self.db_session.execute(failed_query)
        failed_operations = failed_result.scalar() or 0

        # Average duration
        avg_query = select(func.avg(AuditLogEntryDB.duration_ms))
        if conditions:
            avg_query = avg_query.where(*conditions)
        avg_result = await self.db_session.execute(avg_query)
        avg_duration = avg_result.scalar() or 0

        # Success rate
        success_rate = (
            ((total_operations - failed_operations) / total_operations * 100)
            if total_operations > 0
            else 0
        )

        return {
            "total_operations": total_operations,
            "successful_operations": total_operations - failed_operations,
            "failed_operations": failed_operations,
            "success_rate_percent": round(success_rate, 2),
            "average_duration_ms": round(avg_duration, 2),
        }
