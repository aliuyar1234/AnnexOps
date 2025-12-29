"""Database connection and session management."""

from __future__ import annotations

import logging
import os
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import get_settings
from src.core.structured_logging import log_json

settings = get_settings()
logger = logging.getLogger(__name__)

# Create async engine
# Use NullPool for testing environments to avoid connection pool issues
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    poolclass=NullPool if "test" in settings.database_url else None,
)

_slow_query_threshold_ms = float(os.getenv("SLOW_QUERY_MS", "0") or "0")
if _slow_query_threshold_ms > 0:

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        context._query_start_time = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        start = getattr(context, "_query_start_time", None)
        if start is None:
            return

        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms < _slow_query_threshold_ms:
            return

        max_len = 2000
        stmt = str(statement)
        if len(stmt) > max_len:
            stmt = stmt[: max_len - 3] + "..."

        log_json(
            logger,
            logging.WARNING,
            "slow_query",
            duration_ms=round(duration_ms, 2),
            statement=stmt,
        )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Get database session dependency.

    Yields:
        AsyncSession: Database session

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
