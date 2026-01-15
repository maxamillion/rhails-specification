"""Session management endpoints.

This module provides endpoints for creating and managing conversation sessions.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.agent.conversation.session_manager import SessionManager
from src.api.middleware.auth import get_current_user
from src.services.database import DatabaseManager

router = APIRouter(prefix="/v1", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request schema for creating a new session."""

    metadata: dict | None = Field(None, description="Optional session metadata")


class SessionResponse(BaseModel):
    """Response schema for session operations."""

    session_id: uuid.UUID = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User who owns this session")
    created_at: str = Field(..., description="Session creation timestamp")
    status: str = Field(..., description="Session status (active, archived, expired)")


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    current_user: dict = Depends(get_current_user),
) -> SessionResponse:
    """Create a new conversation session.

    Args:
        request: Session creation request with optional metadata
        current_user: Authenticated user information

    Returns:
        SessionResponse with new session details

    Raises:
        HTTPException: If session creation fails
    """
    # Get database URL from environment
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/openshift_ai_agent")

    # Initialize database manager
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize_async()

    try:
        async with db_manager.get_async_session() as session:
            session_manager = SessionManager(session)

            # Create new session
            session_id = await session_manager.create_session(
                user_id=current_user["username"],
                metadata=request.metadata,
            )

            # Get session details
            session_details = await session_manager.get_session(session_id)

            return SessionResponse(
                session_id=session_id,
                user_id=current_user["username"],
                created_at=session_details["created_at"].isoformat(),
                status=session_details["status"],
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session creation failed: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> SessionResponse:
    """Get session details.

    Args:
        session_id: Session identifier
        current_user: Authenticated user information

    Returns:
        SessionResponse with session details

    Raises:
        HTTPException: If session not found or access denied
    """
    # Get database URL from environment
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/openshift_ai_agent")

    # Initialize database manager
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize_async()

    try:
        async with db_manager.get_async_session() as session:
            session_manager = SessionManager(session)

            # Get session details
            session_details = await session_manager.get_session(session_id)

            if not session_details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session {session_id} not found",
                )

            # Verify user owns this session
            if session_details["user_id"] != current_user["username"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this session",
                )

            return SessionResponse(
                session_id=session_id,
                user_id=session_details["user_id"],
                created_at=session_details["created_at"].isoformat(),
                status=session_details["status"],
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session: {str(e)}",
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_session(
    session_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
) -> None:
    """Archive a conversation session.

    Args:
        session_id: Session identifier
        current_user: Authenticated user information

    Raises:
        HTTPException: If session not found or access denied
    """
    # Get database URL from environment
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/openshift_ai_agent")

    # Initialize database manager
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize_async()

    try:
        async with db_manager.get_async_session() as session:
            session_manager = SessionManager(session)

            # Get session to verify ownership
            session_details = await session_manager.get_session(session_id)

            if not session_details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session {session_id} not found",
                )

            # Verify user owns this session
            if session_details["user_id"] != current_user["username"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this session",
                )

            # Archive session
            await session_manager.archive_session(session_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive session: {str(e)}",
        )
