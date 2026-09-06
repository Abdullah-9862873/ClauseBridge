from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

_engine_kwargs: dict = {
    "echo": False,
}

# Only use connection pooling for PostgreSQL (Supabase), not SQLite (tests)
if settings.database_url.startswith("postgresql"):
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Create the session maker
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Create a dependency to get a session
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
