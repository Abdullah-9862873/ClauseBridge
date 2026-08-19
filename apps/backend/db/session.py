from collections.abc import AsyncIterator

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

# Create the async engine
engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)

# Create the session maker
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)



# Create a dependency to get a session
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
