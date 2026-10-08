from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake Redis (in-memory dict)
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory Redis substitute for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    def scan_iter(self, pattern: str = "*") -> list[str]:
        import fnmatch
        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, Any]] = []

    def delete(self, key: str) -> FakePipeline:
        self._ops.append(("delete", key))
        return self

    def execute(self) -> list[int]:
        results = []
        for op, key in self._ops:
            if op == "delete":
                results.append(self._redis.delete(key))
        self._ops.clear()
        return results


@pytest.fixture()
def fake_redis() -> FakeRedis:
    return FakeRedis()


# ---------------------------------------------------------------------------
# Settings patcher (only used by tests that import app modules)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_settings():
    """Provide a minimal Settings object for tests that need it."""
    mock = MagicMock()
    mock.app_name = "ClauseBridge"
    mock.app_version = "1.0.0"
    mock.database_url = "sqlite+aiosqlite:///:memory:"
    mock.jwt_secret = "test-secret-key-for-testing-only"
    mock.jwt_algorithm = "HS256"
    mock.access_token_expire_minutes = 15
    mock.refresh_token_expire_days = 7
    mock.supabase_storage_access_key = "test-key"
    mock.supabase_storage_secret = "test-secret"
    mock.supabase_storage_endpoint = "http://localhost:9000"
    mock.supabase_storage_bucket = "test-bucket"
    mock.redis_url = "redis://localhost:6379/0"
    mock.groq_api_key = "test-groq-key"
    mock.llm_provider = "groq"
    mock.cache_ttl_seconds = 300
    return mock


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_text() -> str:
    return (
        "This Non-Disclosure Agreement is entered into between Party A and Party B.\n\n"
        "1. Confidentiality. Both parties shall keep confidential all information "
        "received during the term of this agreement.\n\n"
        "2. Termination. Either party may terminate this agreement with 30 days "
        "written notice to the other party.\n\n"
        "3. Liability. Total liability shall not exceed the total fees paid under "
        "this agreement."
    )


@pytest.fixture
def firm_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def case_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def clause_id() -> uuid.UUID:
    return uuid.uuid4()
