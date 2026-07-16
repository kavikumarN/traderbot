from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "password": "correcthorse1",
    "first_name": "Alice",
    "last_name": "Smith",
}


async def _register_and_login(client: AsyncClient) -> dict:
    register_response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    assert login_response.status_code == 200
    return login_response.json()


async def test_register_returns_201_with_user_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["type"] == "EntityAlreadyExistsError"


async def test_register_rejects_weak_password(client: AsyncClient) -> None:
    payload = {**REGISTER_PAYLOAD, "password": "weak"}
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


async def test_login_returns_token_pair(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login", json={"email": REGISTER_PAYLOAD["email"], "password": "wrong-password-1"}
    )

    assert response.status_code == 401
    assert response.json()["type"] == "InvalidCredentialsError"


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_valid_token_returns_profile(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role_names"] == ["trader"]


async def test_refresh_rotates_tokens(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert new_tokens["access_token"] != tokens["access_token"]


async def test_reusing_a_rotated_refresh_token_fails(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)
    await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 401


async def test_logout_blacklists_the_access_token(client: AsyncClient) -> None:
    tokens = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert logout_response.status_code == 204

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401
