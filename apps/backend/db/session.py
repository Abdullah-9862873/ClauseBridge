import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings

logger = logging.getLogger(__name__)

_engine_kwargs: dict = {
    "echo": False,
}

if settings.database_url.startswith("postgresql"):
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# For Celery workers: create a fresh engine with NullPool (no connection reuse across event loops)
_celery_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)
CelerySessionLocal = async_sessionmaker(_celery_engine, class_=AsyncSession, expire_on_commit=False)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_session_with_retry() -> AsyncIterator[AsyncSession]:
    """Yield a session with retry on DNS/connection failures."""
    import socket
    last_err = None
    for attempt in range(3):
        try:
            async with SessionLocal() as session:
                yield session
                return
        except (socket.gaierror, OSError, ConnectionError) as e:
            last_err = e
            logger.warning("DB connection failed (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))
    raise last_err
