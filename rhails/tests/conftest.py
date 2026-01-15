"""Shared pytest fixtures and configuration.

This module provides common fixtures used across all test types.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models to register them with Base.metadata
from src.models import conversation, intent  # noqa: F401
from src.models.base import Base


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Provide test database URL.

    Uses file-based SQLite for testing to avoid in-memory connection issues,
    or PostgreSQL if configured.
    """
    # Check for test database environment variable
    db_url = os.getenv("TEST_DATABASE_URL")

    if db_url:
        # Use configured test database (PostgreSQL)
        return db_url
    else:
        # Use file-based SQLite for tests (avoids NullPool isolation issues)
        import tempfile
        temp_dir = tempfile.gettempdir()
        return f"sqlite+aiosqlite:///{temp_dir}/test_rhails.db"


@pytest.fixture(scope="function")
async def async_db_session(test_database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for testing.

    Creates tables before each test and drops them after.
    """
    # Create async engine
    engine = create_async_engine(
        test_database_url,
        echo=False,
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Provide session
    async with async_session_factory() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Dispose engine
    await engine.dispose()


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


# Mark all tests to use asyncio by default
pytest_plugins = ("pytest_asyncio",)
