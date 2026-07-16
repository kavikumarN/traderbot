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

_START = datetime(2026, 1, 1, tzinfo=UTC)


async def _seed_trader_role(uow: FakeUnitOfWork, *, codes: set[str]) -> None:
    await uow.roles.add(Role(id=uuid.uuid4(), name="trader", description="", permission_codes=codes))


async def _auth_headers(client: AsyncClient, uow: FakeUnitOfWork, *, codes: set[str]) -> dict[str, str]:
    await _seed_trader_role(uow, codes=codes)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "trader@example.com", "password": "correcthorse1", "first_name": "A", "last_name": "B"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "trader@example.com", "password": "correcthorse1"}
    )
    tokens = response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _flat_candles(count: int = 40) -> list[Candle]:
    candles = []
    for i in range(count):
        open_time = _START + timedelta(hours=i)
        candles.append(
            Candle(
                symbol="BTCUSDT",
                interval=KlineInterval.ONE_HOUR,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=59, seconds=59),
                open=Decimal(100),
                high=Decimal("100.5"),
                low=Decimal("99.5"),
                close=Decimal(100),
                volume=Decimal("1"),
                quote_volume=Decimal(100),
                trade_count=1,
                is_closed=True,
            )
        )
    return candles


async def test_analyze_patterns_requires_read_permission(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes=set())

    response = await client.post(
        "/api/v1/strategies/ai-builder/analyze",
        json={"symbol": "BTCUSDT", "intervals": ["1h"]},
        headers=headers,
    )

    assert response.status_code == 403


async def test_analyze_patterns_returns_intervals_and_suggestion(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})
    fake_market_data_reader.candles_result = _flat_candles()

    response = await client.post(
        "/api/v1/strategies/ai-builder/analyze",
        json={"symbol": "BTCUSDT", "intervals": ["1h", "1d"]},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    assert len(body["intervals"]) == 2
    assert {interval["interval"] for interval in body["intervals"]} == {"1h", "1d"}
    assert body["suggestion"] is not None
    assert body["suggestion"]["strategy_type"] in {"GRID", "RSI", "EMA_CROSSOVER", "BREAKOUT"}


async def test_analyze_patterns_rejects_empty_candle_history(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"strategies:read"})
    fake_market_data_reader.candles_result = []

    response = await client.post(
        "/api/v1/strategies/ai-builder/analyze",
        json={"symbol": "BTCUSDT", "intervals": ["1h"]},
        headers=headers,
    )

    assert response.status_code == 422
