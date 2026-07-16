from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.domain.entities.role import Role
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.fakes.fake_unit_of_work import FakeUnitOfWork

pytestmark = pytest.mark.asyncio

_STRATEGY_PAYLOAD = {
    "name": "My EMA bot",
    "description": "",
    "symbol": "BTCUSDT",
    "strategy_type": "EMA_CROSSOVER",
    "parameters": {"fast_period": 2, "slow_period": 4, "quantity": "1"},
}
_START = datetime(2026, 1, 1, tzinfo=UTC)
_END = _START + timedelta(hours=5)


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


def _candles() -> list[Candle]:
    closes = ["100", "100", "150", "200", "150", "100"]
    candles = []
    for i, close in enumerate(closes):
        open_time = _START + timedelta(hours=i)
        price = Decimal(close)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                interval=KlineInterval.ONE_HOUR,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=59, seconds=59),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1"),
                quote_volume=price,
                trade_count=1,
                is_closed=True,
            )
        )
    return candles


def _backtest_payload() -> dict:
    return {
        "period_start": _START.isoformat(),
        "period_end": _END.isoformat(),
        "interval": "1h",
        "initial_balance": "10000",
        "commission_rate": "0.001",
    }


async def _create_strategy(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/api/v1/strategies", json=_STRATEGY_PAYLOAD, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_run_backtest_requires_write_permission(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    # Permission is checked before the route body ever resolves the
    # strategy, so a nonexistent id is enough to prove the 403 comes from
    # the permission gate, not a 404 from a missing strategy.
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})

    response = await client.post(
        f"/api/v1/strategies/{uuid.uuid4()}/backtests", json=_backtest_payload(), headers=headers
    )

    assert response.status_code == 403


async def test_run_backtest_returns_completed_results(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    strategy_id = await _create_strategy(client, headers)
    fake_market_data_reader.candles_result = _candles()

    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/backtests", json=_backtest_payload(), headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["strategy_id"] == strategy_id
    assert body["symbol"] == "BTCUSDT"
    assert body["interval"] == "1h"
    assert len(body["equity_curve"]) == len(_candles())
    assert body["total_trades"] == len(body["trade_log"])


async def test_run_backtest_for_unowned_strategy_returns_404(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    owner_headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    strategy_id = await _create_strategy(client, owner_headers)

    await _seed_trader_role(test_uow, codes={"strategies:read", "strategies:write"})
    other_tokens = await _register_and_login(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}
    fake_market_data_reader.candles_result = _candles()

    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/backtests", json=_backtest_payload(), headers=other_headers
    )

    assert response.status_code == 404


async def test_list_and_get_backtest_round_trip(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    strategy_id = await _create_strategy(client, headers)
    fake_market_data_reader.candles_result = _candles()
    created = await client.post(
        f"/api/v1/strategies/{strategy_id}/backtests", json=_backtest_payload(), headers=headers
    )
    backtest_id = created.json()["id"]

    list_response = await client.get(f"/api/v1/strategies/{strategy_id}/backtests", headers=headers)
    assert list_response.status_code == 200
    assert [b["id"] for b in list_response.json()] == [backtest_id]

    get_response = await client.get(
        f"/api/v1/strategies/{strategy_id}/backtests/{backtest_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == backtest_id


async def test_run_backtest_with_no_candles_available_returns_422(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read", "strategies:write"})
    strategy_id = await _create_strategy(client, headers)
    fake_market_data_reader.candles_result = []

    response = await client.post(
        f"/api/v1/strategies/{strategy_id}/backtests", json=_backtest_payload(), headers=headers
    )

    assert response.status_code == 422
