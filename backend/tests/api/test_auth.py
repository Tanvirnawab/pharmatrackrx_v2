import pytest
from httpx import AsyncClient
from tests.conftest import get_auth_token


@pytest.mark.asyncio
async def test_login_success(client):
    ac, data = client
    resp = await ac.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "testpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    ac, _ = client
    resp = await ac.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    ac, _ = client
    resp = await ac.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.com", "password": "testpass123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    ac, _ = client
    token = await get_auth_token(ac, "manager@test.com")
    resp = await ac.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "manager@test.com"
    assert resp.json()["role"] == "store_manager"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    ac, _ = client
    resp = await ac.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client):
    ac, _ = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "testpass123"},
    )
    refresh_token = login.json()["refresh_token"]

    resp = await ac.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
