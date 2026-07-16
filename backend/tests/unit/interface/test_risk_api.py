from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.domain.entities.role import Role
from tests.fakes.fake_unit_of_work import FakeUnitOfWork

pytestmark = pytest.mark.asyncio

_RULE_PAYLOAD = {"rule_type": "MAX_DAILY_LOSS", "threshold": "500"}


async def _seed_trader_role(uow: FakeUnitOfWork, *, codes: set[str]) -> None:
    await uow.roles.add(Role(id=uuid.uuid4(), name="trader", description="", permission_codes=codes))


async def _register_and_login(client: AsyncClient, email: str = "trader@example.com") -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correcthorse1", "first_name": "A", "last_name": "B"},
    )
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "correcthorse1"})
    return response.json()


async def _auth_headers(client: AsyncClient, uow: FakeUnitOfWork, *, codes: set[str]) -> dict[str, str]:
    await _seed_trader_role(uow, codes=codes)
    tokens = await _register_and_login(client)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_create_risk_rule_requires_write_permission(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read"})

    response = await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=headers)

    assert response.status_code == 403


async def test_create_risk_rule_returns_active_rule(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read", "risk:write"})

    response = await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["rule_type"] == "MAX_DAILY_LOSS"
    assert body["threshold"] == "500"
    assert body["is_active"] is True


async def test_create_risk_rule_without_required_threshold_returns_422(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:write"})

    response = await client.post("/api/v1/risk/rules", json={"rule_type": "MAX_DAILY_LOSS"}, headers=headers)

    assert response.status_code == 422
    assert response.json()["type"] == "ValidationError"


async def test_list_risk_rules_returns_only_current_users_rules(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read", "risk:write"})
    await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=headers)

    response = await client.get("/api/v1/risk/rules", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["rule_type"] == "MAX_DAILY_LOSS"


async def test_get_risk_rule_owned_by_another_user_returns_404(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    await _seed_trader_role(test_uow, codes={"risk:read", "risk:write"})
    owner_tokens = await _register_and_login(client, "owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_tokens['access_token']}"}
    created = await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=owner_headers)
    rule_id = created.json()["id"]

    other_tokens = await _register_and_login(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}

    response = await client.get(f"/api/v1/risk/rules/{rule_id}", headers=other_headers)

    assert response.status_code == 404


async def test_update_risk_rule_changes_threshold_and_active_flag(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read", "risk:write"})
    created = await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=headers)
    rule_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/risk/rules/{rule_id}", json={"is_active": False, "threshold": "750"}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert body["threshold"] == "750"


async def test_delete_risk_rule_removes_it(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read", "risk:write"})
    created = await client.post("/api/v1/risk/rules", json=_RULE_PAYLOAD, headers=headers)
    rule_id = created.json()["id"]

    response = await client.delete(f"/api/v1/risk/rules/{rule_id}", headers=headers)
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/risk/rules/{rule_id}", headers=headers)
    assert get_response.status_code == 404


async def test_get_risk_state_returns_closed_circuit_breaker_by_default(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read"})

    response = await client.get("/api/v1/risk/state", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["circuit_breaker"] == "CLOSED"
    assert body["emergency_stop"] is False
    assert body["is_trading_allowed"] is True


async def test_emergency_stop_halts_and_resumes_trading(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read", "risk:write"})

    stop_response = await client.post(
        "/api/v1/risk/emergency-stop", json={"active": True, "reason": "manual halt"}, headers=headers
    )
    assert stop_response.status_code == 200
    assert stop_response.json()["emergency_stop"] is True
    assert stop_response.json()["is_trading_allowed"] is False

    resume_response = await client.post(
        "/api/v1/risk/emergency-stop", json={"active": False}, headers=headers
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["emergency_stop"] is False
    assert resume_response.json()["is_trading_allowed"] is True


async def test_circuit_breaker_reset_requires_write_permission(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read"})

    response = await client.post("/api/v1/risk/circuit-breaker/reset", headers=headers)

    assert response.status_code == 403


async def test_position_size_preview_with_no_account_yet_returns_zero_quantity(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"risk:read"})

    response = await client.post(
        "/api/v1/risk/position-size",
        json={"side": "BUY", "entry_price": "100"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quantity"] == "0"
    assert body["stop_loss_price"] == "98.00"
    assert body["take_profit_price"] == "104.00"


async def test_risk_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/risk/rules")

    assert response.status_code == 401
