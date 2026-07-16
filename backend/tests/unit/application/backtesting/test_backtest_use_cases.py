from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.use_cases.backtesting.get_backtest import GetBacktestUseCase
from app.application.use_cases.backtesting.list_backtests import ListBacktestsUseCase
from app.application.use_cases.backtesting.run_backtest import RunBacktestCommand, RunBacktestUseCase
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle
from app.domain.marketdata.entities import PersistedCandle
from app.domain.strategy.enums import BacktestStatus
from app.domain.strategy.plugin import SignalProposal, StrategyContext
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.unit.application.strategies.helpers import DummyPlugin, FakeStrategyLoader, make_candle, make_strategy

pytestmark = pytest.mark.asyncio

_SYMBOL = "BTCUSDT"
_START = datetime(2026, 1, 1, tzinfo=UTC)
_END = _START + timedelta(hours=5)


def _persisted_candles(count: int = 5) -> list[PersistedCandle]:
    candles = []
    for i in range(count):
        candle = make_candle(
            symbol=_SYMBOL,
            interval=KlineInterval.ONE_HOUR,
            open_time=_START + timedelta(hours=i),
            close_time=_START + timedelta(hours=i, minutes=59, seconds=59),
        )
        candles.append(
            PersistedCandle(
                symbol=candle.symbol,
                interval=candle.interval,
                open_time=candle.open_time,
                close_time=candle.close_time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                quote_volume=candle.quote_volume,
                trade_count=candle.trade_count,
            )
        )
    return candles


def _command(strategy_id: uuid.UUID, user_id: uuid.UUID) -> RunBacktestCommand:
    return RunBacktestCommand(
        user_id=user_id,
        strategy_id=strategy_id,
        period_start=_START,
        period_end=_END,
        interval=KlineInterval.ONE_HOUR,
        initial_balance=Decimal("10000"),
        commission_rate=Decimal("0.001"),
    )


async def test_run_backtest_persists_a_completed_backtest(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    for candle in _persisted_candles():
        await uow.candles.upsert(candle)

    dummy = DummyPlugin(StrategyContext(strategy_id=strategy.id, symbol=_SYMBOL, parameters={"quantity": "1"}))
    await dummy.initialize()
    dummy.next_signal_on_candle = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"), reason="test")

    use_case = RunBacktestUseCase(
        uow_factory, FakeExchangeClient(), strategy_loader=FakeStrategyLoader(plugin=dummy)
    )

    backtest = await use_case.execute(_command(strategy.id, strategy.user_id))

    assert backtest.status == BacktestStatus.COMPLETED
    assert backtest.strategy_id == strategy.id
    assert backtest.total_trades == 1
    assert backtest.results["symbol"] == _SYMBOL
    assert len(backtest.results["equity_curve"]) == 5
    stored = await uow.backtests.get_by_id(backtest.id)
    assert stored is not None


async def test_run_backtest_for_unowned_strategy_raises_not_found(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)

    use_case = RunBacktestUseCase(uow_factory, FakeExchangeClient())

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(_command(strategy.id, uuid.uuid4()))


async def test_run_backtest_rejects_a_backwards_period(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    use_case = RunBacktestUseCase(uow_factory, FakeExchangeClient())

    bad_command = RunBacktestCommand(
        user_id=strategy.user_id,
        strategy_id=strategy.id,
        period_start=_END,
        period_end=_START,
        interval=KlineInterval.ONE_HOUR,
        initial_balance=Decimal("10000"),
        commission_rate=Decimal("0.001"),
    )

    with pytest.raises(ValidationError):
        await use_case.execute(bad_command)


async def test_run_backtest_raises_when_no_candles_are_available_anywhere(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    market_data = FakeExchangeClient()
    market_data.candles_result = []

    use_case = RunBacktestUseCase(uow_factory, market_data)

    with pytest.raises(ValidationError):
        await use_case.execute(_command(strategy.id, strategy.user_id))


async def test_run_backtest_backfills_from_market_data_when_persisted_store_is_empty(uow, uow_factory) -> None:
    strategy = make_strategy(config={"strategy_type": "EMA_CROSSOVER", "parameters": {"quantity": "1"}})
    await uow.strategies.add(strategy)
    market_data = FakeExchangeClient()
    market_data.candles_result = _domain_candles()

    use_case = RunBacktestUseCase(uow_factory, market_data)

    backtest = await use_case.execute(_command(strategy.id, strategy.user_id))

    assert backtest.status == BacktestStatus.COMPLETED
    backfilled = await uow.candles.list_range(_SYMBOL, KlineInterval.ONE_HOUR, start=_START, end=_END)
    assert len(backfilled) > 0


def _domain_candles() -> list[Candle]:
    candles: list[Candle] = []
    for i in range(5):
        open_time = _START + timedelta(hours=i)
        candles.append(
            Candle(
                symbol=_SYMBOL,
                interval=KlineInterval.ONE_HOUR,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=59, seconds=59),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=Decimal("1"),
                quote_volume=Decimal("100"),
                trade_count=1,
                is_closed=True,
            )
        )
    return candles


async def test_list_and_get_backtest_are_scoped_to_the_owning_strategy(uow, uow_factory) -> None:
    strategy = make_strategy(config={"strategy_type": "EMA_CROSSOVER", "parameters": {"quantity": "1"}})
    await uow.strategies.add(strategy)
    for candle in _persisted_candles():
        await uow.candles.upsert(candle)

    run_use_case = RunBacktestUseCase(uow_factory, FakeExchangeClient())
    backtest = await run_use_case.execute(_command(strategy.id, strategy.user_id))

    listed = await ListBacktestsUseCase(uow_factory).execute(user_id=strategy.user_id, strategy_id=strategy.id)
    assert [b.id for b in listed] == [backtest.id]

    fetched = await GetBacktestUseCase(uow_factory).execute(
        user_id=strategy.user_id, strategy_id=strategy.id, backtest_id=backtest.id
    )
    assert fetched.id == backtest.id

    with pytest.raises(EntityNotFoundError):
        await GetBacktestUseCase(uow_factory).execute(
            user_id=uuid.uuid4(), strategy_id=strategy.id, backtest_id=backtest.id
        )
