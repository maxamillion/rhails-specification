"""Health check endpoints for readiness and liveness probes."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.services.database import _db_manager

router = APIRouter(tags=["health"])


@router.get(
    "/v1/readiness",
    summary="Readiness probe",
    description="Check if the service is ready to accept requests",
    status_code=status.HTTP_200_OK,
)
async def readiness() -> JSONResponse:
    """Readiness probe endpoint.

    Returns 200 if the service is ready to handle requests,
    503 if any required dependencies are unavailable.

    Checks:
    - Database connectivity
    - Critical service availability

    Returns:
        JSONResponse with readiness status
    """
    checks = {}

    # Check database connection
    if _db_manager:
        db_healthy = await _db_manager.health_check()
        checks["database"] = "healthy" if db_healthy else "unhealthy"
    else:
        checks["database"] = "not_initialized"

    # Determine overall readiness
    all_healthy = all(status == "healthy" for status in checks.values())

    if all_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "checks": checks,
            },
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "checks": checks,
            },
        )


@router.get(
    "/v1/liveness",
    summary="Liveness probe",
    description="Check if the service is alive",
    status_code=status.HTTP_200_OK,
)
async def liveness() -> dict:
    """Liveness probe endpoint.

    Returns 200 if the service is alive and running.
    Kubernetes uses this to determine if the pod should be restarted.

    Returns:
        Simple status dict
    """
    return {
        "status": "alive",
    }


@router.get(
    "/v1/health",
    summary="General health check",
    description="Comprehensive health check with detailed status",
    status_code=status.HTTP_200_OK,
)
async def health() -> dict:
    """Comprehensive health check endpoint.

    Provides detailed health information including:
    - Service status
    - Database connectivity
    - System resources (optional)

    Returns:
        Detailed health status dict
    """
    checks = {}

    # Check database
    if _db_manager:
        db_healthy = await _db_manager.health_check()
        checks["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "postgresql",
        }
    else:
        checks["database"] = {
            "status": "not_initialized",
            "type": "postgresql",
        }

    # Overall status
    all_healthy = all(
        check.get("status") == "healthy" for check in checks.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "0.1.0",
        "service": "openshift-ai-agent",
        "checks": checks,
    }
