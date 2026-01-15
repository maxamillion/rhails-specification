"""Database connection manager with connection pooling and async support."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, QueuePool

from src.models.base import Base


class DatabaseManager:
    """Manages database connections with pooling and lifecycle management.

    Supports both sync and async database operations with proper connection pooling,
    health checks, and graceful shutdown.
    """

    def __init__(self, database_url: str, pool_size: int = 20, max_overflow: int = 10):
        """Initialize database manager.

        Args:
            database_url: Database connection string (postgresql://user:pass@host:port/db)
            pool_size: Size of the connection pool
            max_overflow: Max connections beyond pool_size
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow

        # Sync engine for migrations and admin tasks
        self._sync_engine = None
        self._sync_session_factory = None

        # Async engine for application runtime
        self._async_engine = None
        self._async_session_factory = None

        self._initialized = False

    def initialize_sync(self) -> None:
        """Initialize synchronous database engine and session factory."""
        if self._sync_engine is not None:
            return

        # Convert async URL to sync if needed (asyncpg -> psycopg2)
        sync_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")

        self._sync_engine = create_engine(
            sync_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )

        # Configure connection pool events
        @event.listens_for(self._sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Set connection parameters on connect."""
            # Set timezone to UTC
            cursor = dbapi_conn.cursor()
            cursor.execute("SET timezone='UTC'")
            cursor.close()

        self._sync_session_factory = sessionmaker(
            bind=self._sync_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    async def initialize_async(self) -> None:
        """Initialize asynchronous database engine and session factory."""
        if self._async_engine is not None:
            return

        # Ensure URL uses appropriate async driver
        async_url = self.database_url

        # Handle PostgreSQL URLs
        if "postgresql://" in async_url and "postgresql+asyncpg://" not in async_url:
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

        # SQLite URLs are already async (sqlite+aiosqlite://)
        # No transformation needed for SQLite

        # Use NullPool for SQLite in-memory databases, AsyncAdaptedQueuePool for others
        if "sqlite" in async_url and ":memory:" in async_url:
            # NullPool doesn't support pool_size/max_overflow
            self._async_engine = create_async_engine(
                async_url,
                poolclass=NullPool,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            # Use AsyncAdaptedQueuePool for async engines (file-based SQLite or PostgreSQL)
            self._async_engine = create_async_engine(
                async_url,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                echo=False,
            )

        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self._initialized = True

    def get_sync_session(self) -> Session:
        """Get a synchronous database session.

        Returns:
            SQLAlchemy Session instance

        Raises:
            RuntimeError: If sync engine not initialized
        """
        if self._sync_session_factory is None:
            raise RuntimeError("Sync database not initialized. Call initialize_sync() first.")
        return self._sync_session_factory()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session context manager.

        Yields:
            SQLAlchemy AsyncSession instance

        Raises:
            RuntimeError: If async engine not initialized

        Example:
            async with db_manager.get_async_session() as session:
                result = await session.execute(select(ConversationSession))
        """
        if self._async_session_factory is None:
            raise RuntimeError("Async database not initialized. Call initialize_async() first.")

        session = self._async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def create_tables(self) -> None:
        """Create all database tables (for development/testing only).

        Note: In production, use Alembic migrations instead.
        """
        if self._async_engine is None:
            await self.initialize_async()

        # Import models to ensure they're registered with Base.metadata
        # This must happen before create_all() is called
        from src.models import conversation, intent  # noqa: F401

        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all database tables (for testing only).

        Warning: This will delete all data!
        """
        if self._async_engine is None:
            await self.initialize_async()

        # Import models to ensure they're registered with Base.metadata
        from src.models import conversation, intent  # noqa: F401

        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def health_check(self) -> bool:
        """Check database connection health.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            if self._async_engine is None:
                await self.initialize_async()

            async with self.get_async_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close database connections and dispose of connection pool."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_factory = None

        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            self._sync_session_factory = None

        self._initialized = False

    async def shutdown_async(self) -> None:
        """Shutdown database connections (alias for close()).

        This method provides backward compatibility for tests that expect shutdown_async().
        """
        await self.close()


# Global database manager instance (initialized in application startup)
_db_manager: DatabaseManager | None = None


def initialize_database(database_url: str | None = None) -> DatabaseManager:
    """Initialize global database manager.

    Args:
        database_url: Database connection string (defaults to DATABASE_URL env var)

    Returns:
        DatabaseManager instance
    """
    global _db_manager

    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
        if database_url is None:
            raise ValueError("DATABASE_URL environment variable not set")

    _db_manager = DatabaseManager(database_url)
    return _db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session.

    Yields:
        AsyncSession instance

    Example:
        @app.get("/sessions")
        async def list_sessions(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(ConversationSession))
            return result.scalars().all()
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")

    async with _db_manager.get_async_session() as session:
        yield session


async def shutdown_database() -> None:
    """Shutdown database connections (call on application shutdown)."""
    global _db_manager
    if _db_manager is not None:
        await _db_manager.close()
        _db_manager = None
