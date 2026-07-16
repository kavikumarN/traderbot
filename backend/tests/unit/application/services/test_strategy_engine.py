from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.strategy_engine import StrategyEngine
from app.domain.exchange.enums import OrderSide
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.plugin import SignalProposal, StrategyContext, StrategyPlugin
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.unit.application.strategies.helpers import (
    DummyPlugin,
    FakeStrategyLoader,
    SpySignalManager,
    make_candle,
    make_strategy,
    make_ticker,
)


def make_plugin(strategy) -> DummyPlugin:
    return DummyPlugin(
        StrategyContext(strategy_id=strategy.id, symbol=strategy.symbol, parameters={"quantity": "0.01"})
    )


class _MappingLoader:
    """Routes `load(strategy)` to a pre-built plugin keyed by strategy id —
    used where a test needs more than one strategy running concurrently
    under a single engine, each with its own plugin instance."""

    def __init__(self, plugins: dict[uuid.UUID, StrategyPlugin]) -> None:
        self._plugins = plugins

    async def load(self, strategy) -> StrategyPlugin:
        return self._plugins[strategy.id]


@pytest.mark.asyncio
async def test_start_strategy_and_stop_strategy_lifecycle(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    exchange.candles_result = []
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), SpySignalManager(), poll_interval_seconds=5.0
    )

    await engine.start_strategy(strategy)
    assert strategy.id in engine.running_strategy_ids

    await asyncio.sleep(0)
    assert plugin.initialized is True
    assert len(plugin.ticks) == 1

    await engine.stop_strategy(strategy.id)

    assert strategy.id not in engine.running_strategy_ids
    assert plugin.shutdown_called is True


@pytest.mark.asyncio
async def test_start_strategy_is_a_no_op_if_already_tracked(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    loader = FakeStrategyLoader(plugin=plugin)
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    engine = StrategyEngine(uow_factory, exchange, loader, SpySignalManager(), poll_interval_seconds=5.0)

    await engine.start_strategy(strategy)
    first_task = engine.running_strategy_ids
    await engine.start_strategy(strategy)

    assert engine.running_strategy_ids == first_task
    assert loader.load_calls == 1

    await engine.stop_strategy(strategy.id)


@pytest.mark.asyncio
async def test_stop_strategy_on_unknown_id_is_a_safe_no_op(uow_factory) -> None:
    exchange = FakeExchangeClient()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(), SpySignalManager(), poll_interval_seconds=5.0
    )

    await engine.stop_strategy(uuid.uuid4())

    assert engine.running_strategy_ids == []


@pytest.mark.asyncio
async def test_start_picks_up_active_strategies_and_rejects_double_start(uow, uow_factory) -> None:
    active = make_strategy(status=StrategyStatus.PAPER_TRADING)
    draft = make_strategy(status=StrategyStatus.DRAFT)
    await uow.strategies.add(active)
    await uow.strategies.add(draft)

    plugin = make_plugin(active)
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), SpySignalManager(), poll_interval_seconds=5.0
    )

    await engine.start()

    assert engine.running_strategy_ids == [active.id]

    with pytest.raises(RuntimeError):
        await engine.start()

    await engine.stop()
    assert engine.running_strategy_ids == []


@pytest.mark.asyncio
async def test_poll_once_ticks_and_only_processes_new_closed_candles(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    await plugin.initialize()
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), SpySignalManager(), poll_interval_seconds=5.0
    )

    now = datetime.now(UTC)
    closed_candle = make_candle(close_time=now - timedelta(minutes=2))
    future_candle = make_candle(close_time=now + timedelta(minutes=5))
    exchange.candles_result = [closed_candle, future_candle]

    last_close = await engine._poll_once(strategy, plugin, None)

    assert plugin.candles == [closed_candle]
    assert last_close == closed_candle.close_time
    assert len(plugin.ticks) == 1

    last_close_again = await engine._poll_once(strategy, plugin, last_close)

    assert plugin.candles == [closed_candle]
    assert last_close_again == last_close
    assert len(plugin.ticks) == 2


@pytest.mark.asyncio
async def test_poll_once_forwards_tick_signal_to_signal_manager(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    await plugin.initialize()
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("0.01"))
    plugin.next_signal_on_tick = proposal

    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    exchange.candles_result = []
    signals = SpySignalManager()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), signals, poll_interval_seconds=5.0
    )

    await engine._poll_once(strategy, plugin, None)

    assert len(signals.submissions) == 1
    submitted_strategy, submitted_proposal = signals.submissions[0]
    assert submitted_strategy is strategy
    assert submitted_proposal is proposal


@pytest.mark.asyncio
async def test_poll_once_forwards_candle_signal_to_signal_manager(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    await plugin.initialize()
    proposal = SignalProposal(side=OrderSide.SELL, quantity=Decimal("0.01"))
    plugin.next_signal_on_candle = proposal

    now = datetime.now(UTC)
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    exchange.candles_result = [make_candle(close_time=now - timedelta(minutes=1))]
    signals = SpySignalManager()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), signals, poll_interval_seconds=5.0
    )

    await engine._poll_once(strategy, plugin, None)

    assert len(signals.submissions) == 1
    submitted_strategy, submitted_proposal = signals.submissions[0]
    assert submitted_strategy is strategy
    assert submitted_proposal is proposal


@pytest.mark.asyncio
async def test_plugin_load_failure_logs_and_never_starts_polling(uow_factory) -> None:
    strategy = make_strategy()
    plugin = make_plugin(strategy)
    loader = FakeStrategyLoader(plugin=plugin, error=RuntimeError("boom"))
    exchange = FakeExchangeClient()
    signals = SpySignalManager()
    engine = StrategyEngine(uow_factory, exchange, loader, signals, poll_interval_seconds=5.0)

    await engine.start_strategy(strategy)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert plugin.initialized is False
    assert plugin.ticks == []
    assert signals.submissions == []

    await engine.stop_strategy(strategy.id)


@pytest.mark.asyncio
async def test_stop_stops_every_tracked_strategy(uow_factory) -> None:
    strategy_one = make_strategy()
    strategy_two = make_strategy()
    plugin_one = make_plugin(strategy_one)
    plugin_two = make_plugin(strategy_two)
    loader = _MappingLoader({strategy_one.id: plugin_one, strategy_two.id: plugin_two})
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()

    engine = StrategyEngine(uow_factory, exchange, loader, SpySignalManager(), poll_interval_seconds=5.0)
    await engine.start_strategy(strategy_one)
    await engine.start_strategy(strategy_two)

    assert set(engine.running_strategy_ids) == {strategy_one.id, strategy_two.id}

    await engine.stop()

    assert engine.running_strategy_ids == []
    assert plugin_one.shutdown_called is True
    assert plugin_two.shutdown_called is True
