from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.domain.entities.role import Role
from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Ticker
from app.domain.trading.entities import ExchangeAccount, Position, Trade, Wallet
from app.domain.trading.enums import AccountStatus
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.fakes.fake_unit_of_work import FakeUnitOfWork

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 7, 15, tzinfo=UTC)


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


async def _seeded_account(test_uow: FakeUnitOfWork, email: str = "trader@example.com") -> ExchangeAccount:
    user = await test_uow.users.get_by_email(email)
    assert user is not None
    account = ExchangeAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        exchange="PAPER",
        label="default",
        api_key_ciphertext="",
        api_key_last_four="0000",
        is_testnet=True,
        status=AccountStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    await test_uow.exchange_accounts.add(account)
    return account


async def test_portfolio_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/summary")
    assert response.status_code == 401


async def test_portfolio_summary_requires_permission(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes=set())

    response = await client.get("/api/v1/portfolio/summary", headers=headers)

    assert response.status_code == 403


async def test_portfolio_summary_with_no_account_returns_zero_equity(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})

    response = await client.get("/api/v1/portfolio/summary", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["equity"] == "0"
    assert body["roi_pct"] is None


async def test_portfolio_summary_reflects_wallet_and_marked_to_market_position(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})
    account = await _seeded_account(test_uow)
    await test_uow.wallets.upsert(
        Wallet(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            asset="USDT",
            free=Decimal("5000"),
            locked=Decimal(0),
            updated_at=_NOW,
        )
    )
    await test_uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            quantity=Decimal("1"),
            avg_entry_price=Decimal("100"),
            realized_pnl=Decimal(0),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )
    fake_market_data_reader.ticker_result = Ticker(
        symbol="BTCUSDT",
        last_price=Decimal("130"),
        bid_price=Decimal("130"),
        ask_price=Decimal("130"),
        high_price=Decimal("130"),
        low_price=Decimal("130"),
        volume=Decimal(0),
        quote_volume=Decimal(0),
        price_change_percent=Decimal(0),
        open_time=_NOW,
        close_time=_NOW,
    )

    response = await client.get("/api/v1/portfolio/summary", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["cash"] == "5000"
    assert body["positions_value"] == "130"
    assert body["equity"] == "5130"
    assert body["unrealized_pnl"] == "30"


async def test_portfolio_positions_lists_open_positions_marked_to_market(
    client: AsyncClient, test_uow: FakeUnitOfWork, fake_market_data_reader: FakeExchangeClient
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})
    account = await _seeded_account(test_uow)
    await test_uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="ETHUSDT",
            quantity=Decimal("2"),
            avg_entry_price=Decimal("50"),
            realized_pnl=Decimal(0),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )
    fake_market_data_reader.ticker_result = Ticker(
        symbol="ETHUSDT",
        last_price=Decimal("60"),
        bid_price=Decimal("60"),
        ask_price=Decimal("60"),
        high_price=Decimal("60"),
        low_price=Decimal("60"),
        volume=Decimal(0),
        quote_volume=Decimal(0),
        price_change_percent=Decimal(0),
        open_time=_NOW,
        close_time=_NOW,
    )

    response = await client.get("/api/v1/portfolio/positions", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["symbol"] == "ETHUSDT"
    assert body[0]["current_price"] == "60"
    assert body[0]["unrealized_pnl"] == "20"


async def test_portfolio_trades_paginates_newest_first(client: AsyncClient, test_uow: FakeUnitOfWork) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})
    account = await _seeded_account(test_uow)
    await test_uow.trades.add(
        Trade(
            id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("100"),
            quantity=Decimal("1"),
            quote_quantity=Decimal("100"),
            commission=Decimal("0.1"),
            exchange_trade_id=1,
            executed_at=datetime(2026, 1, 1, tzinfo=UTC),
            commission_asset="USDT",
        )
    )
    await test_uow.trades.add(
        Trade(
            id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            price=Decimal("110"),
            quantity=Decimal("1"),
            quote_quantity=Decimal("110"),
            commission=Decimal("0.1"),
            exchange_trade_id=2,
            executed_at=datetime(2026, 1, 2, tzinfo=UTC),
            commission_asset="USDT",
        )
    )

    response = await client.get("/api/v1/portfolio/trades?limit=1", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["price"] == "110"
    assert body["limit"] == 1
    assert body["offset"] == 0


async def test_portfolio_performance_with_no_trades_returns_empty_points(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})
    await _seeded_account(test_uow)

    response = await client.get("/api/v1/portfolio/performance", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["points"] == []
    assert body["sharpe_ratio"] is None


async def test_portfolio_wallets_with_no_account_returns_empty_list(
    client: AsyncClient, test_uow: FakeUnitOfWork
) -> None:
    headers = await _auth_headers(client, test_uow, codes={"portfolio:read"})

    response = await client.get("/api/v1/portfolio/wallets", headers=headers)

    assert response.status_code == 200
    assert response.json() == []
