"""FastAPI application setup and configuration."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kubernetes.client.rest import ApiException
from pydantic import ValidationError

from src.api.middleware.error_handler import (
    generic_exception_handler,
    kubernetes_exception_handler,
    permission_exception_handler,
    validation_exception_handler,
)
from src.api.middleware.logging import LoggingMiddleware, setup_logging
from src.api.routes import health
from src.services.database import initialize_database, shutdown_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    setup_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_format=os.getenv("LOG_FORMAT", "json"),
    )

    # Initialize database
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        db_manager = initialize_database(database_url)
        await db_manager.initialize_async()

    yield

    # Shutdown
    await shutdown_database()


# Create FastAPI application
app = FastAPI(
    title="OpenShift AI Conversational Agent",
    description="Conversational AI agent for managing OpenShift AI resources through natural language",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ========== CORS Configuration ==========

# Get allowed origins from environment
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# ========== Custom Middleware ==========

# Logging middleware (must be first to log all requests)
app.add_middleware(LoggingMiddleware)

# ========== Exception Handlers ==========

app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(ApiException, kubernetes_exception_handler)
app.add_exception_handler(PermissionError, permission_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ========== Route Registration ==========

# Health check routes
app.include_router(health.router)

# Conversation API routes
from src.api.routes import confirm, query, sessions

app.include_router(query.router)
app.include_router(sessions.router)
app.include_router(confirm.router)

# ========== Root Endpoint ==========


@app.get(
    "/",
    tags=["root"],
    summary="API root",
    description="Returns API information and available endpoints",
)
async def root() -> dict:
    """API root endpoint.

    Returns:
        API information and version
    """
    return {
        "service": "OpenShift AI Conversational Agent",
        "version": "0.1.0",
        "description": "Manage OpenShift AI resources through natural language conversation",
        "documentation": {
            "openapi": "/openapi.json",
            "swagger": "/docs",
            "redoc": "/redoc",
        },
        "health": {
            "liveness": "/v1/liveness",
            "readiness": "/v1/readiness",
            "health": "/v1/health",
        },
    }


# ========== Development Server ==========

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
