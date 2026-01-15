"""Error handling middleware and exception handlers."""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from kubernetes.client.rest import ApiException
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format."""

    @staticmethod
    def create(
        error_type: str,
        message: str,
        details: str | dict | None = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> JSONResponse:
        """Create error response.

        Args:
            error_type: Error type identifier
            message: Human-readable error message
            details: Additional error details
            status_code: HTTP status code

        Returns:
            JSONResponse with error information
        """
        content = {
            "error": {
                "type": error_type,
                "message": message,
            }
        }

        if details:
            content["error"]["details"] = details

        return JSONResponse(
            status_code=status_code,
            content=content,
        )


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: FastAPI request
        exc: Validation error

    Returns:
        JSON error response
    """
    logger.warning(f"Validation error: {exc}")

    return ErrorResponse.create(
        error_type="validation_error",
        message="Request validation failed",
        details=exc.errors(),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def kubernetes_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Handle Kubernetes API exceptions.

    Args:
        request: FastAPI request
        exc: Kubernetes API exception

    Returns:
        JSON error response with user-friendly message
    """
    logger.error(f"Kubernetes API error: {exc}")

    # Map Kubernetes errors to user-friendly messages
    status_code = exc.status
    reason = exc.reason

    if status_code == 404:
        message = "The requested resource was not found in OpenShift AI"
    elif status_code == 403:
        message = "You don't have permission to perform this operation"
    elif status_code == 409:
        message = "The resource already exists or there's a conflict"
    elif status_code == 422:
        message = "The resource configuration is invalid"
    else:
        message = f"OpenShift AI error: {reason}"

    return ErrorResponse.create(
        error_type="openshift_error",
        message=message,
        details={"reason": reason, "status": status_code},
        status_code=status_code if status_code < 500 else status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def permission_exception_handler(request: Request, exc: PermissionError) -> JSONResponse:
    """Handle permission errors.

    Args:
        request: FastAPI request
        exc: Permission error

    Returns:
        JSON error response
    """
    logger.warning(f"Permission denied: {exc}")

    return ErrorResponse.create(
        error_type="permission_denied",
        message=str(exc),
        status_code=status.HTTP_403_FORBIDDEN,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: Any exception

    Returns:
        JSON error response
    """
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    return ErrorResponse.create(
        error_type="internal_error",
        message="An unexpected error occurred. Please try again later.",
        details=str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
