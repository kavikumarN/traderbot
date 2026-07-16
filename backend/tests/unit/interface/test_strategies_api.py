from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.domain.entities.role import Role
from tests.fakes.fake_unit_of_work import FakeUnitOfWork

pytestmark = pytest.mark.asyncio

_STRATEGY_PAYLOAD = {
    "name": "My EMA bot",
    "description": "Crosses fast/slow EMAs on BTCUSDT",
    "symbol": "btcusdt",
    "strategy_type": "EMA_CROSSOVER",
    "parameters": {"fast_period": 12, "slow_period": 26, "quantity": "0.01"},
}


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


async def test_create_strategy_requires_write_permission(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})

    response = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)

    assert response.status_code == 403


async def test_create_strategy_returns_draft_strategy(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})

    response = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["symbol"] == "BTCUSDT"
    assert body["strategy_type"] == "EMA_CROSSOVER"
    assert body["parameters"] == _STRATEGY_PAYLOAD["parameters"]
    assert body["version"] == 1


async def test_create_strategy_with_unknown_type_returns_422(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:write"})
    payload = {**_STRATEGY_PAYLOAD, "strategy_type": "NOT_A_REAL_STRATEGY"}

    response = await client.post("/api/v1/strategies", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["type"] == "UnknownStrategyTypeError"


async def test_create_strategy_with_missing_quantity_returns_422(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:write"})
    payload = {**_STRATEGY_PAYLOAD, "parameters": {"fast_period": 12, "slow_period": 26}}

    response = await client.post("/api/v1/strategies", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["type"] == "InvalidStrategyConfigError"


async def test_list_strategy_types_includes_all_built_ins(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})

    response = await client.get("/api/v1/strategies/types", headers=headers)

    assert response.status_code == 200
    types = {item["strategy_type"] for item in response.json()}
    assert types == {"BREAKOUT", "EMA_CROSSOVER", "GRID", "MACD", "RSI", "VWAP_MEAN_REVERSION"}


async def test_get_strategy_not_found_returns_404(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})

    response = await client.get(f"/api/v1/strategies/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_get_strategy_owned_by_another_user_returns_404(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    # `_seed_trader_role` only needs to run once — permissions are resolved
    # fresh per request against whichever role names are on the caller's
    # token, and both users below get "trader" from self-registration.
    await _seed_trader_role(test_uow, codes={"strategies:read", "strategies:write"})
    owner_tokens = await _register_and_login(client, "owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_tokens['access_token']}"}
    created = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=owner_headers)
    strategy_id = created.json()["id"]

    other_tokens = await _register_and_login(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}

    response = await client.get(f"/api/v1/strategies/{strategy_id}", headers=other_headers)

    assert response.status_code == 404


async def test_list_strategies_returns_only_current_users_strategies(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)

    response = await client.get("/api/v1/strategies", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["strategy_type"] == "EMA_CROSSOVER"


async def test_update_strategy_status_start_paper_trading(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    created = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)
    strategy_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/status",
        json={"action": "start_paper_trading"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PAPER_TRADING"


async def test_update_strategy_status_invalid_transition_returns_422(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    created = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)
    strategy_id = created.json()["id"]

    # Still DRAFT — can't promote straight to LIVE.
    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/status",
        json={"action": "promote_to_live"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["type"] == "ValidationError"


async def test_list_signals_for_new_strategy_is_empty(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    created = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)
    strategy_id = created.json()["id"]

    response = await client.get(f"/api/v1/strategies/{strategy_id}/signals", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_strategies_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/strategies")

    assert response.status_code == 401
