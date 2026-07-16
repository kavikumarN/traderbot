from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.portfolio_service import PortfolioService
from app.application.use_cases.portfolio.get_performance import GetPerformanceUseCase
from app.application.use_cases.portfolio.get_summary import GetPortfolioSummaryUseCase
from app.application.use_cases.portfolio.list_positions import ListPositionsUseCase
from app.application.use_cases.portfolio.list_trade_history import ListTradeHistoryUseCase
from app.application.use_cases.portfolio.list_wallets import ListWalletsUseCase
from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Ticker
from app.domain.trading.entities import ExchangeAccount, Position, Trade, Wallet
from app.domain.trading.enums import AccountStatus
from tests.fakes.fake_exchange_client import FakeExchangeClient

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 7, 15, tzinfo=UTC)


def _account(user_id: uuid.UUID) -> ExchangeAccount:
    return ExchangeAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        exchange="PAPER",
        label="default",
        api_key_ciphertext="",
        api_key_last_four="0000",
        is_testnet=True,
        status=AccountStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _ticker(symbol: str, last_price: str) -> Ticker:
    return Ticker(
        symbol=symbol,
        last_price=Decimal(last_price),
        bid_price=Decimal(last_price),
        ask_price=Decimal(last_price),
        high_price=Decimal(last_price),
        low_price=Decimal(last_price),
        volume=Decimal(0),
        quote_volume=Decimal(0),
        price_change_percent=Decimal(0),
        open_time=_NOW,
        close_time=_NOW,
    )


async def _seed_trade(uow, account: ExchangeAccount, *, price: str, quantity: str, side: OrderSide, when: datetime) -> Trade:
    trade = Trade(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        exchange_account_id=account.id,
        symbol="BTCUSDT",
        side=side,
        price=Decimal(price),
        quantity=Decimal(quantity),
        quote_quantity=Decimal(price) * Decimal(quantity),
        commission=Decimal("0.1"),
        exchange_trade_id=1,
        executed_at=when,
        commission_asset="USDT",
    )
    await uow.trades.add(trade)
    return trade


async def test_get_summary_with_no_account_returns_zero_summary(uow_factory) -> None:
    market_data = FakeExchangeClient()
    use_case = GetPortfolioSummaryUseCase(uow_factory, PortfolioService(), market_data)

    summary = await use_case.execute(user_id=uuid.uuid4())

    assert summary.equity == Decimal(0)
    assert summary.roi_pct is None
    assert summary.open_position_count == 0


async def test_get_summary_computes_cash_equity_realized_and_unrealized_pnl(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)
    await uow.wallets.upsert(
        Wallet(id=uuid.uuid4(), exchange_account_id=account.id, asset="USDT", free=Decimal("9000"), locked=Decimal(0), updated_at=_NOW)
    )
    await uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            quantity=Decimal("1"),
            avg_entry_price=Decimal("100"),
            realized_pnl=Decimal("50"),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )
    await _seed_trade(uow, account, price="100", quantity="1", side=OrderSide.BUY, when=_NOW)

    market_data = FakeExchangeClient()
    market_data.ticker_result = _ticker("BTCUSDT", "150")

    use_case = GetPortfolioSummaryUseCase(uow_factory, PortfolioService(), market_data)
    summary = await use_case.execute(user_id=user_id)

    assert summary.cash == Decimal("9000")
    assert summary.positions_value == Decimal("150")  # 1 BTC marked to the 150 ticker
    assert summary.equity == Decimal("9150")
    assert summary.realized_pnl == Decimal("50")
    assert summary.unrealized_pnl == Decimal("50")  # (150 - 100) * 1
    assert summary.total_pnl == Decimal("100")
    assert summary.open_position_count == 1
    assert summary.total_trade_count == 1
    assert summary.fees_by_asset == {"USDT": Decimal("0.1")}


async def test_get_summary_falls_back_to_avg_entry_price_when_ticker_fetch_fails(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)
    await uow.positions.upsert(
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

    market_data = FakeExchangeClient()
    market_data.ticker_result = RuntimeError("exchange unavailable")

    use_case = GetPortfolioSummaryUseCase(uow_factory, PortfolioService(), market_data)
    summary = await use_case.execute(user_id=user_id)

    assert summary.positions_value == Decimal("100")  # fell back to avg_entry_price
    assert summary.unrealized_pnl == Decimal("0")


async def test_list_positions_marks_open_positions_to_market(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)
    await uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            quantity=Decimal("2"),
            avg_entry_price=Decimal("100"),
            realized_pnl=Decimal(0),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )

    market_data = FakeExchangeClient()
    market_data.ticker_result = _ticker("BTCUSDT", "120")

    use_case = ListPositionsUseCase(uow_factory, PortfolioService(), market_data)
    views = await use_case.execute(user_id=user_id)

    assert len(views) == 1
    assert views[0].current_price == Decimal("120")
    assert views[0].market_value == Decimal("240")
    assert views[0].unrealized_pnl == Decimal("40")


async def test_list_wallets_with_no_account_returns_empty(uow_factory) -> None:
    use_case = ListWalletsUseCase(uow_factory, PortfolioService())
    assert await use_case.execute(user_id=uuid.uuid4()) == []


async def test_list_trade_history_paginates_newest_first(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)
    await _seed_trade(uow, account, price="100", quantity="1", side=OrderSide.BUY, when=datetime(2026, 1, 1, tzinfo=UTC))
    await _seed_trade(uow, account, price="110", quantity="1", side=OrderSide.SELL, when=datetime(2026, 1, 2, tzinfo=UTC))

    use_case = ListTradeHistoryUseCase(uow_factory, PortfolioService())
    trades = await use_case.execute(user_id=user_id, limit=1, offset=0)

    assert len(trades) == 1
    assert trades[0].price == Decimal("110")  # newest first


async def test_get_performance_with_no_trades_returns_empty_curve(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)

    market_data = FakeExchangeClient()
    use_case = GetPerformanceUseCase(uow_factory, PortfolioService(), market_data)

    result = await use_case.execute(user_id=user_id)

    assert result.points == []
    assert result.sharpe_ratio is None
    assert result.max_drawdown_pct == Decimal(0)


async def test_get_performance_builds_a_curve_anchored_to_current_equity(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = _account(user_id)
    await uow.exchange_accounts.add(account)
    await uow.wallets.upsert(
        Wallet(id=uuid.uuid4(), exchange_account_id=account.id, asset="USDT", free=Decimal("10000"), locked=Decimal(0), updated_at=_NOW)
    )
    await _seed_trade(uow, account, price="100", quantity="1", side=OrderSide.BUY, when=datetime(2026, 1, 1, tzinfo=UTC))
    await _seed_trade(uow, account, price="150", quantity="1", side=OrderSide.SELL, when=datetime(2026, 1, 2, tzinfo=UTC))

    market_data = FakeExchangeClient()
    use_case = GetPerformanceUseCase(uow_factory, PortfolioService(), market_data)

    result = await use_case.execute(user_id=user_id)

    assert len(result.points) >= 2
    assert result.points[-1].equity == result.current_equity
    assert result.starting_equity == result.points[0].equity
