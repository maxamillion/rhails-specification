"""Query endpoint for conversational queries.

This endpoint handles natural language queries from users and executes
the corresponding OpenShift AI operations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.agent.conversation.session_manager import SessionManager
from src.agent.operations.model_operations import ModelOperationExecutor
from src.agent.operations.monitoring_operations import MonitoringOperationExecutor
from src.agent.operations.notebook_operations import NotebookOperationExecutor
from src.agent.operations.pipeline_operations import PipelineOperationExecutor
from src.agent.operations.project_operations import ProjectOperationExecutor
from src.api.middleware.auth import get_current_user
from src.models.conversation import MessageRole
from src.models.intent import OperationRequest
from src.models.openshift import ResourceType
from src.services.database import DatabaseManager
from src.services.intent_parser import IntentParser
from src.services.openshift_client import OpenShiftClient

router = APIRouter(prefix="/v1", tags=["query"])


class QueryRequest(BaseModel):
    """Request schema for conversation queries."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")
    session_id: uuid.UUID | None = Field(None, description="Conversation session ID (optional for new sessions)")


class QueryResponse(BaseModel):
    """Response schema for conversation queries."""

    session_id: uuid.UUID = Field(..., description="Conversation session ID")
    message_id: uuid.UUID = Field(..., description="Message ID for this interaction")
    response: str = Field(..., description="Agent response to user query")
    requires_confirmation: bool = Field(..., description="Whether operation requires user confirmation")
    confirmation_token: str | None = Field(None, description="Token for confirming destructive operations")
    metadata: dict = Field(..., description="Additional metadata about the operation")


@router.post("/query", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> QueryResponse:
    """Process conversational query and execute operations.

    Args:
        request: Query request with user query and optional session ID
        current_user: Authenticated user information

    Returns:
        QueryResponse with operation results and next steps

    Raises:
        HTTPException: If query processing fails
    """
    # Get database URL from environment
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/openshift_ai_agent")

    # Initialize services
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize_async()

    try:
        async with db_manager.get_async_session() as session:
            # Initialize managers
            session_manager = SessionManager(session)
            intent_parser = IntentParser()
            openshift_client = OpenShiftClient()

            # Get or create conversation session
            if request.session_id:
                session_id = request.session_id
                # Verify session exists and belongs to user
                context = await session_manager.get_context_window(session_id)
                if not context:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Session {session_id} not found",
                    )
            else:
                # Create new session
                session_id = await session_manager.create_session(
                    user_id=current_user["username"],
                    metadata={"source": "api"},
                )

            # Get conversation context for intent parsing
            context_window = await session_manager.get_context_window(session_id)

            # Parse user intent
            intent = await intent_parser.parse_intent(
                user_query=request.query,
                conversation_context=context_window,
            )

            # Validate intent
            await intent_parser.validate_request(intent)

            # Create message for user query
            message_id = await session_manager.add_message(
                session_id=session_id,
                role=MessageRole.USER,
                content=request.query,
            )

            # If operation requires confirmation but no token provided
            if intent.requires_confirmation:
                confirmation_token = str(uuid.uuid4())

                # Add system message about confirmation
                await session_manager.add_message(
                    session_id=session_id,
                    role=MessageRole.SYSTEM,
                    content="This operation requires confirmation. Please confirm to proceed.",
                )

                return QueryResponse(
                    session_id=session_id,
                    message_id=message_id,
                    response=f"This operation requires confirmation. Would you like to proceed with {intent.action_type}?",
                    requires_confirmation=True,
                    confirmation_token=confirmation_token,
                    metadata={
                        "intent": intent.action_type,
                        "confidence": intent.confidence,
                        "target_resources": list(intent.target_resources),
                    },
                )

            # Determine target resource and resource name based on intent
            is_pipeline_operation = _is_pipeline_operation(intent.action_type)
            is_notebook_operation = _is_notebook_operation(intent.action_type)
            is_project_operation = _is_project_operation(intent.action_type)
            is_monitoring_operation = _is_monitoring_operation(intent.action_type)

            if is_pipeline_operation:
                target_resource = ResourceType.PIPELINE
                resource_name = intent.parameters.get("pipeline_name")
                operation_executor = PipelineOperationExecutor(
                    openshift_client=openshift_client,
                    db_session=session,
                )
            elif is_notebook_operation:
                target_resource = ResourceType.NOTEBOOK
                resource_name = intent.parameters.get("notebook_name")
                operation_executor = NotebookOperationExecutor(
                    openshift_client=openshift_client,
                    db_session=session,
                )
            elif is_project_operation:
                target_resource = ResourceType.PROJECT
                resource_name = intent.parameters.get("project_name")
                operation_executor = ProjectOperationExecutor(
                    openshift_client=openshift_client,
                    db_session=session,
                )
            elif is_monitoring_operation:
                target_resource = ResourceType.INFERENCE_SERVICE
                resource_name = intent.parameters.get("model_name")
                # Add action parameter for monitoring operation routing
                intent.parameters["action"] = intent.action_type
                operation_executor = MonitoringOperationExecutor(
                    openshift_client=openshift_client,
                    db_session=session,
                )
            else:
                target_resource = ResourceType.INFERENCE_SERVICE
                resource_name = intent.parameters.get("model_name")
                operation_executor = ModelOperationExecutor(
                    openshift_client=openshift_client,
                    db_session=session,
                )

            # Build operation request
            operation_request = OperationRequest(
                session_id=session_id,
                user_id=current_user["username"],
                operation_type=_map_action_to_operation(intent.action_type),
                target_resource=target_resource,
                resource_name=resource_name,
                parameters=intent.parameters,
                requires_confirmation=intent.requires_confirmation,
                confirmation_token=None,
            )

            # Execute operation
            result = await operation_executor.execute(operation_request)

            # Generate human-friendly response
            if result.status == "success":
                response_text = _generate_success_response(
                    action=intent.action_type,
                    resource_name=result.resource_name,
                    result_data=result.result_data,
                )
            else:
                response_text = f"Operation failed: {result.error_message}"

            # Add assistant message
            await session_manager.add_message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
            )

            return QueryResponse(
                session_id=session_id,
                message_id=message_id,
                response=response_text,
                requires_confirmation=False,
                confirmation_token=None,
                metadata={
                    "intent": intent.action_type,
                    "confidence": intent.confidence,
                    "target_resources": list(intent.target_resources),
                    "execution_status": result.status,
                },
            )

    except HTTPException:
        # Re-raise HTTPException to preserve status codes (404, 422, etc.)
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}",
        )


def _is_pipeline_operation(action_type: str) -> bool:
    """Check if action type is a pipeline operation.

    Args:
        action_type: ActionType enum value

    Returns:
        True if pipeline operation, False otherwise
    """
    pipeline_actions = {
        "create_pipeline",
        "update_pipeline",
        "list_pipelines",
    }
    return action_type in pipeline_actions


def _is_notebook_operation(action_type: str) -> bool:
    """Check if action type is a notebook operation.

    Args:
        action_type: ActionType enum value

    Returns:
        True if notebook operation, False otherwise
    """
    notebook_actions = {
        "create_notebook",
        "list_notebooks",
        "start_notebook",
        "stop_notebook",
        "delete_notebook",
    }
    return action_type in notebook_actions


def _is_project_operation(action_type: str) -> bool:
    """Check if action type is a project operation.

    Args:
        action_type: ActionType enum value

    Returns:
        True if project operation, False otherwise
    """
    project_actions = {
        "create_project",
        "list_projects",
        "add_user_to_project",
        "get_project_resources",
    }
    return action_type in project_actions


def _is_monitoring_operation(action_type: str) -> bool:
    """Check if action type is a monitoring operation.

    Args:
        action_type: ActionType enum value

    Returns:
        True if monitoring operation, False otherwise
    """
    monitoring_actions = {
        "analyze_logs",
        "compare_metrics",
        "diagnose_performance",
        "get_prediction_distribution",
    }
    return action_type in monitoring_actions


def _map_action_to_operation(action_type: str) -> str:
    """Map action type to Kubernetes operation type.

    Args:
        action_type: ActionType enum value

    Returns:
        Kubernetes operation type (create, get, list, patch, delete)
    """
    mapping = {
        # Model operations
        "deploy_model": "create",
        "get_status": "get",
        "list_models": "list",
        "scale_model": "patch",
        "delete_model": "delete",
        # Pipeline operations
        "create_pipeline": "create",
        "update_pipeline": "patch",
        "list_pipelines": "list",
        # Notebook operations
        "create_notebook": "create",
        "list_notebooks": "list",
        "start_notebook": "patch",
        "stop_notebook": "patch",
        "delete_notebook": "delete",
        # Project operations
        "create_project": "create",
        "list_projects": "list",
        "add_user_to_project": "update",
        "get_project_resources": "get",
        # Monitoring operations
        "analyze_logs": "get",
        "compare_metrics": "get",
        "diagnose_performance": "get",
        "get_prediction_distribution": "get",
    }
    return mapping.get(action_type, "get")


def _generate_success_response(
    action: str, resource_name: str, result_data: dict
) -> str:
    """Generate human-friendly success response.

    Args:
        action: Action type performed
        resource_name: Name of resource operated on
        result_data: Result data from operation

    Returns:
        Human-readable success message
    """
    # Model operations
    if action == "deploy_model":
        return f"Successfully deployed model '{resource_name}'. The model is now available."
    elif action == "get_status":
        status_info = result_data.get("status", {})
        conditions = status_info.get("conditions", [])
        if conditions:
            ready_condition = next(
                (c for c in conditions if c.get("type") == "Ready"), None
            )
            if ready_condition and ready_condition.get("status") == "True":
                return f"Model '{resource_name}' is ready and serving requests."
            else:
                return f"Model '{resource_name}' is not ready yet."
        return f"Model '{resource_name}' status retrieved."
    elif action == "list_models":
        count = len(result_data) if isinstance(result_data, list) else 0
        if count == 0:
            return "No models found."
        elif count == 1:
            return f"Found 1 model: {result_data[0].get('metadata', {}).get('name', 'unknown')}"
        else:
            names = [m.get("metadata", {}).get("name", "unknown") for m in result_data[:3]]
            names_str = ", ".join(names)
            if count > 3:
                return f"Found {count} models. First 3: {names_str}, ..."
            return f"Found {count} models: {names_str}"
    elif action == "scale_model":
        return f"Successfully scaled model '{resource_name}'."
    elif action == "delete_model":
        return f"Successfully deleted model '{resource_name}'."
    # Pipeline operations
    elif action == "create_pipeline":
        return f"Successfully created pipeline '{resource_name}'. The pipeline is now configured."
    elif action == "update_pipeline":
        schedule = result_data.get("spec", {}).get("schedule")
        if schedule:
            return f"Successfully updated pipeline '{resource_name}' schedule to: {schedule}"
        return f"Successfully updated pipeline '{resource_name}'."
    elif action == "list_pipelines":
        count = len(result_data) if isinstance(result_data, list) else 0
        if count == 0:
            return "No pipelines found."
        elif count == 1:
            return f"Found 1 pipeline: {result_data[0].get('metadata', {}).get('name', 'unknown')}"
        else:
            names = [p.get("metadata", {}).get("name", "unknown") for p in result_data[:3]]
            names_str = ", ".join(names)
            if count > 3:
                return f"Found {count} pipelines. First 3: {names_str}, ..."
            return f"Found {count} pipelines: {names_str}"
    # Notebook operations
    elif action == "create_notebook":
        return f"Successfully created notebook '{resource_name}'. The notebook is now available."
    elif action == "list_notebooks":
        count = len(result_data) if isinstance(result_data, list) else 0
        if count == 0:
            return "No notebooks found."
        elif count == 1:
            return f"Found 1 notebook: {result_data[0].get('metadata', {}).get('name', 'unknown')}"
        else:
            names = [n.get("metadata", {}).get("name", "unknown") for n in result_data[:3]]
            names_str = ", ".join(names)
            if count > 3:
                return f"Found {count} notebooks. First 3: {names_str}, ..."
            return f"Found {count} notebooks: {names_str}"
    elif action == "start_notebook":
        return f"Successfully started notebook '{resource_name}'."
    elif action == "stop_notebook":
        return f"Successfully stopped notebook '{resource_name}'."
    elif action == "delete_notebook":
        return f"Successfully deleted notebook '{resource_name}'."
    # Project operations
    elif action == "create_project":
        return f"Successfully created project '{resource_name}'. The project is now available."
    elif action == "list_projects":
        count = len(result_data) if isinstance(result_data, list) else 0
        if count == 0:
            return "No projects found."
        elif count == 1:
            return f"Found 1 project: {result_data[0].get('metadata', {}).get('name', 'unknown')}"
        else:
            names = [p.get("metadata", {}).get("name", "unknown") for p in result_data[:3]]
            names_str = ", ".join(names)
            if count > 3:
                return f"Found {count} projects. First 3: {names_str}, ..."
            return f"Found {count} projects: {names_str}"
    elif action == "add_user_to_project":
        return f"Successfully added user to project '{resource_name}'."
    elif action == "get_project_resources":
        # Format resource usage if available
        if "status" in result_data and "used" in result_data["status"]:
            used = result_data["status"]["used"]
            memory = used.get("requests.memory", "N/A")
            cpu = used.get("requests.cpu", "N/A")
            return f"Project '{resource_name}' is using {memory} memory and {cpu} CPU."
        return f"Retrieved resource usage for project '{resource_name}'."
    # Monitoring operations
    elif action == "analyze_logs":
        error_count = result_data.get("error_count", 0)
        warning_count = result_data.get("warning_count", 0)
        logs = result_data.get("logs", [])

        if error_count > 0 or warning_count > 0:
            summary = f"Found {error_count} errors and {warning_count} warnings for '{resource_name}'."
            if logs:
                # Show first 2 error messages
                errors = [log for log in logs[:5] if log.get("level") == "ERROR"][:2]
                if errors:
                    summary += " Recent errors: " + "; ".join([e.get("message", "") for e in errors])
            return summary
        return f"No errors found in logs for '{resource_name}'."
    elif action == "compare_metrics":
        current = result_data.get("current", {})
        baseline = result_data.get("baseline", {})

        if current and baseline:
            latency_current = current.get("avg_latency_ms", 0)
            latency_baseline = baseline.get("avg_latency_ms", 0)
            error_current = current.get("error_rate", 0)
            error_baseline = baseline.get("error_rate", 0)

            latency_change = ((latency_current - latency_baseline) / latency_baseline * 100) if latency_baseline > 0 else 0
            error_change = ((error_current - error_baseline) / error_baseline * 100) if error_baseline > 0 else 0

            summary = f"Metrics for '{resource_name}': "
            summary += f"Latency {latency_current}ms ({latency_change:+.1f}%), "
            summary += f"Error rate {error_current*100:.2f}% ({error_change:+.1f}%)"
            return summary
        return f"Retrieved metrics for '{resource_name}'."
    elif action == "diagnose_performance":
        bottleneck = result_data.get("bottleneck", "unknown")
        cpu = result_data.get("cpu", {})
        memory = result_data.get("memory", {})

        summary = f"Performance analysis for '{resource_name}': "
        if bottleneck == "cpu":
            cpu_usage = cpu.get("current_usage_percent", 0)
            summary += f"CPU-bound (current usage: {cpu_usage}%). Consider increasing CPU allocation."
        elif bottleneck == "memory":
            mem_usage = memory.get("current_usage_mb", 0)
            summary += f"Memory-bound (current usage: {mem_usage}MB). Consider increasing memory allocation."
        else:
            summary += "No significant bottlenecks detected."
        return summary
    elif action == "get_prediction_distribution":
        total = result_data.get("total_predictions", 0)
        time_range = result_data.get("time_range", "unknown period")
        result_data.get("distribution", {})
        distribution_pct = result_data.get("distribution_percent", {})

        summary = f"Prediction distribution for '{resource_name}' over {time_range}: "
        summary += f"{total:,} total predictions. "
        if distribution_pct:
            # Show top 3 categories
            top_categories = sorted(distribution_pct.items(), key=lambda x: x[1], reverse=True)[:3]
            summary += "Distribution: " + ", ".join([f"{cat} {pct:.1f}%" for cat, pct in top_categories])
        return summary
    else:
        return f"Operation completed successfully for '{resource_name}'."
