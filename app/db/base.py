from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str, *, debug: bool = False) -> None:
    """Create the engine and session factory. Called once during app startup."""
    global _engine, _session_factory

    _engine = create_async_engine(
        database_url,
        echo=debug,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Dispose the connection pool. Called once during app shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a session scoped to a single request."""
    assert _session_factory is not None, "init_db() must be called before the first request."
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
