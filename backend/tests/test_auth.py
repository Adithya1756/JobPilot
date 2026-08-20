"""
Auth flow tests for JobPilot.

Tests: signup, login, token refresh, protected endpoints.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

TEST_PASSWORD = "SecurePass123!"


def get_test_email():
    """Generate unique test email for isolation."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_signup():
    """Test user signup creates a new account."""
    email = get_test_email()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/signup",
            json={"email": email, "password": TEST_PASSWORD, "name": "Test User"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login():
    """Test login with valid credentials."""
    email = get_test_email()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/signup",
            json={"email": email, "password": TEST_PASSWORD, "name": "Test User"}
        )

        response = await client.post(
            "/auth/login",
            json={"email": email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth():
    """Test that protected endpoints require authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me")
        # FastAPI HTTPBearer returns 403 for missing auth header
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_endpoint_with_token():
    """Test /auth/me returns user info with valid token."""
    email = get_test_email()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup = await client.post(
            "/auth/signup",
            json={"email": email, "password": TEST_PASSWORD, "name": "Test User"}
        )
        token = signup.json()["access_token"]

        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["name"] == "Test User"


@pytest.mark.asyncio
async def test_duplicate_signup_fails():
    """Test that duplicate email signup is rejected."""
    email = get_test_email()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/signup",
            json={"email": email, "password": TEST_PASSWORD}
        )
        response = await client.post(
            "/auth/signup",
            json={"email": email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
