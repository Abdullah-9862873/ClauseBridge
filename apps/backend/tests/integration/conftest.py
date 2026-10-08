"""Integration test conftest — mock heavy deps and create tables for SQLite."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Mock sentence_transformers before anything imports it
_fake_st = ModuleType("sentence_transformers")
_fake_st.SentenceTransformer = MagicMock()  # type: ignore[attr-defined]
sys.modules["sentence_transformers"] = _fake_st

import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.base import Base
import models  # noqa: F401 — registers all models on Base.metadata


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def _create_tables():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def _db_session(_create_tables):
    session_factory = async_sessionmaker(_create_tables, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
