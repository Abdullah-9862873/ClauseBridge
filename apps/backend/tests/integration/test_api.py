"""Integration tests for API endpoints.

Uses httpx.AsyncClient with app.dependency_overrides for DI mocking.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.v1.deps import get_current_user
from db.session import get_session


def _build_test_app():
    from main import app
    return app


@pytest.fixture()
def app():
    return _build_test_app()


@pytest.fixture(autouse=True)
def _clear_overrides(app):
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Fake objects for DB mocking
# ---------------------------------------------------------------------------

class FakeUser:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.firm_id = kwargs.get("firm_id", uuid.uuid4())
        self.email = kwargs.get("email", "test@example.com")
        self.password_hash = kwargs.get("password_hash", "salt$hash")
        self.role = kwargs.get("role", "admin")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


class FakeFirm:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.name = kwargs.get("name", "Test Firm")
        self.plan_tier = kwargs.get("plan_tier", "free")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


class FakeCase:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.firm_id = kwargs.get("firm_id", uuid.uuid4())
        self.title = kwargs.get("title", "Test Case")
        self.status = kwargs.get("status", "active")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


def _make_mock_session(**overrides) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    for attr, val in overrides.items():
        setattr(session, attr, val)
    return session


def _auth_headers(user: FakeUser | None = None) -> dict[str, str]:
    from core.security import create_access_token
    u = user or FakeUser()
    token = create_access_token(str(u.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Health endpoint (no DB needed)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_root_returns_alive(self, client: AsyncClient) -> None:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "alive" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_signup_creates_user(self, app, client: AsyncClient) -> None:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session

        resp = await client.post(
            "/api/v1/auth/signup",
            json={"firm_name": "Acme", "email": "new@acme.com", "password": "pass123"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert "firm_id" in data
        assert "user_id" in data
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_signup_duplicate_email_409(self, app, client: AsyncClient) -> None:
        mock_session = AsyncMock()
        existing_user = FakeUser(email="taken@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session

        resp = await client.post(
            "/api/v1/auth/signup",
            json={"firm_name": "Acme", "email": "taken@example.com", "password": "pass"},
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login_success(self, app, client: AsyncClient) -> None:
        from core.security import hash_password

        user = FakeUser(
            id=uuid.uuid4(),
            email="login@test.com",
            password_hash=hash_password("correct_pass"),
        )
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "correct_pass"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password_401(self, app, client: AsyncClient) -> None:
        from core.security import hash_password

        user = FakeUser(password_hash=hash_password("correct_pass"))
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "wrong_pass"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user_401(self, app, client: AsyncClient) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "pass"},
        )

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cases endpoints (protected)
# ---------------------------------------------------------------------------

class TestCaseEndpoints:
    @pytest.mark.asyncio
    async def test_create_case(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.post(
            "/api/v1/cases",
            json={"title": "My New Case"},
            headers=_auth_headers(user),
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My New Case"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_case_empty_title_422(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        mock_session = AsyncMock()

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.post(
            "/api/v1/cases",
            json={"title": "   "},
            headers=_auth_headers(user),
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_cases(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        case = FakeCase(firm_id=user.firm_id)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [case]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.get("/api/v1/cases", headers=_auth_headers(user))

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_single_case(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        case = FakeCase(firm_id=user.firm_id)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=case)

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.get(
            f"/api/v1/cases/{case.id}",
            headers=_auth_headers(user),
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Case"

    @pytest.mark.asyncio
    async def test_get_case_wrong_firm_404(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        other_firm_user = FakeUser()
        case = FakeCase(firm_id=other_firm_user.firm_id)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=case)

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.get(
            f"/api/v1/cases/{case.id}",
            headers=_auth_headers(user),
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dashboard endpoint
# ---------------------------------------------------------------------------

class TestDashboardEndpoint:
    @pytest.mark.asyncio
    async def test_get_stats(self, app, client: AsyncClient) -> None:
        user = FakeUser()
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=5)

        async def fake_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = fake_get_session
        app.dependency_overrides[get_current_user] = lambda: user

        resp = await client.get(
            "/api/v1/dashboard/stats",
            headers=_auth_headers(user),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "total_cases" in data
        assert "total_documents" in data
        assert "anomalies_detected" in data
