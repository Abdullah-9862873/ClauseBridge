from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings

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
