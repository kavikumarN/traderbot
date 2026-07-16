from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.domain.entities.permission import Permission
from app.domain.entities.role import Role
from tests.fakes.fake_unit_of_work import FakeUnitOfWork

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correcthorse1", "first_name": "A", "last_name": "B"},
    )
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "correcthorse1"})
    return response.json()


async def _seed_admin_role(uow: FakeUnitOfWork) -> None:
    for code in ("users:read", "users:write", "roles:read", "roles:manage", "permissions:read"):
        await uow.permissions.add(Permission(id=uuid.uuid4(), code=code, description=""))
    admin_role = Role(
        id=uuid.uuid4(),
        name="admin",
        description="",
        permission_codes={"users:read", "users:write", "roles:read", "roles:manage", "permissions:read"},
    )
    await uow.roles.add(admin_role)
    # `trader` must also exist since self-registration assigns it.
    await uow.roles.add(Role(id=uuid.uuid4(), name="trader", description="", permission_codes=set()))


async def test_default_trader_role_cannot_list_users(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    await _seed_admin_role(test_uow)
    tokens = await _register_and_login(client, "trader@example.com")

    response = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 403
    assert response.json()["type"] == "PermissionDeniedError"


async def test_admin_role_can_list_users(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    await _seed_admin_role(test_uow)
    tokens = await _register_and_login(client, "admin@example.com")

    # Promote the just-registered user to admin directly through the fake repo
    # (bypasses the API's own roles:manage-gated endpoint, which is exercised
    # separately below).
    user = await test_uow.users.get_by_email("admin@example.com")
    assert user is not None
    user.assign_role("admin")
    await test_uow.users.update(user)

    # Re-login so the new access token carries the "admin" role claim.
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "correcthorse1"}
    )
    tokens = login_response.json()

    response = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "admin@example.com"


async def test_assign_role_endpoint_requires_roles_manage_permission(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    await _seed_admin_role(test_uow)
    tokens = await _register_and_login(client, "plain@example.com")
    user = await test_uow.users.get_by_email("plain@example.com")
    assert user is not None

    response = await client.post(
        f"/api/v1/users/{user.id}/roles",
        json={"role_name": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 403


async def test_permission_grant_takes_effect_without_reissuing_the_token(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    """Access tokens only carry role *names*; permissions are resolved fresh
    on every request, so granting a permission to a role already on the
    token's claims must take effect immediately — no new login required."""
    await _seed_admin_role(test_uow)
    await _register_and_login(client, "reader@example.com")
    user = await test_uow.users.get_by_email("reader@example.com")
    assert user is not None

    reader_role = Role(id=uuid.uuid4(), name="reader", description="", permission_codes=set())
    await test_uow.roles.add(reader_role)
    user.assign_role("reader")
    await test_uow.users.update(user)

    # Re-login so the access token's role claim includes "reader" — only
    # the *permissions* behind that role are meant to apply without a
    # fresh login, not the role assignment itself.
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "reader@example.com", "password": "correcthorse1"}
    )
    tokens = login_response.json()

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    before = await client.get("/api/v1/users", headers=headers)
    assert before.status_code == 403

    reader_role.grant("users:read")
    await test_uow.roles.update(reader_role)

    after = await client.get("/api/v1/users", headers=headers)
    assert after.status_code == 200
