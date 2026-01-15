"""Confirmation endpoint for destructive operations.

This endpoint handles confirmation of operations that require user approval
before execution (e.g., scaling models, deleting resources).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.agent.conversation.session_manager import SessionManager
from src.agent.operations.model_operations import ModelOperationExecutor
from src.api.middleware.auth import get_current_user
from src.models.conversation import MessageRole
from src.models.intent import OperationRequest
from src.models.openshift import ResourceType
from src.services.database import DatabaseManager
from src.services.openshift_client import OpenShiftClient

router = APIRouter(prefix="/v1", tags=["confirm"])


class ConfirmRequest(BaseModel):
    """Request schema for confirming operations."""

    session_id: uuid.UUID = Field(..., description="Conversation session ID")
    confirmation_token: str = Field(..., description="Confirmation token from query response")
    operation_type: str = Field(..., description="Operation type to confirm")
    resource_name: str = Field(..., description="Resource name to operate on")
    parameters: dict = Field(default_factory=dict, description="Operation parameters")


class ConfirmResponse(BaseModel):
    """Response schema for confirmed operations."""

    session_id: uuid.UUID = Field(..., description="Conversation session ID")
    response: str = Field(..., description="Operation result message")
    execution_status: str = Field(..., description="Execution status (success, error)")


@router.post("/confirm", response_model=ConfirmResponse, status_code=status.HTTP_200_OK)
async def confirm_operation(
    request: ConfirmRequest,
    current_user: dict = Depends(get_current_user),
) -> ConfirmResponse:
    """Confirm and execute a pending destructive operation.

    Args:
        request: Confirmation request with token and operation details
        current_user: Authenticated user information

    Returns:
        ConfirmResponse with execution results

    Raises:
        HTTPException: If confirmation fails or operation execution fails
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
            openshift_client = OpenShiftClient()
            operation_executor = ModelOperationExecutor(
                openshift_client=openshift_client,
                db_session=session,
            )

            # Verify session exists and belongs to user
            session_details = await session_manager.get_session(request.session_id)

            if not session_details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session {request.session_id} not found",
                )

            if session_details["user_id"] != current_user["username"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this session",
                )

            # Build operation request with confirmation token
            operation_request = OperationRequest(
                session_id=request.session_id,
                user_id=current_user["username"],
                operation_type=request.operation_type,
                target_resource=ResourceType.INFERENCE_SERVICE,
                resource_name=request.resource_name,
                parameters=request.parameters,
                requires_confirmation=True,
                confirmation_token=request.confirmation_token,
            )

            # Execute confirmed operation
            result = await operation_executor.execute(operation_request)

            # Generate response message
            if result.status == "success":
                response_text = f"Successfully completed {request.operation_type} operation on '{request.resource_name}'."
            else:
                response_text = f"Operation failed: {result.error_message}"

            # Add message to conversation
            await session_manager.add_message(
                session_id=request.session_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
            )

            return ConfirmResponse(
                session_id=request.session_id,
                response=response_text,
                execution_status=result.status,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confirmation failed: {str(e)}",
        )
