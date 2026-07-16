from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.entities import Signal, Strategy
from app.domain.strategy.enums import SignalStatus, StrategyStatus
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import SignalProposal, StrategyContext, StrategyPlugin


class DummyPlugin(StrategyPlugin):
    """A minimal, fully scriptable `StrategyPlugin` used across the Phase 7
    test suite instead of any real built-in strategy — deterministic and
    decoupled from indicator math. Requires `parameters.quantity`, exactly
    like the shared `_quantity()` helper on the base class."""

    strategy_type = "DUMMY"

    def __init__(self, context: StrategyContext) -> None:
        super().__init__(context)
        self.initialized = False
        self.shutdown_called = False
        self.ticks: list[Ticker] = []
        self.candles: list[Candle] = []
        self.next_signal_on_tick: SignalProposal | None = None
        self.next_signal_on_candle: SignalProposal | None = None

    async def initialize(self) -> None:
        quantity = self.context.parameters.get("quantity")
        if quantity is None:
            raise InvalidStrategyConfigError(self.strategy_type, "parameters.quantity is required")
        self.initialized = True

    async def on_tick(self, ticker: Ticker) -> None:
        self.ticks.append(ticker)
        if self.next_signal_on_tick is not None:
            self._pending_signal = self.next_signal_on_tick
            self.next_signal_on_tick = None

    async def on_candle(self, candle: Candle) -> None:
        self.candles.append(candle)
        if self.next_signal_on_candle is not None:
            self._pending_signal = self.next_signal_on_candle
            self.next_signal_on_candle = None

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        self.shutdown_called = True


class FakeStrategyLoader:
    """Duck-typed `StrategyLoader` stand-in: hands back a pre-built plugin
    instance the test already holds a reference to (so `on_tick`/
    `on_candle`/signals can be scripted), or raises a scripted error."""

    def __init__(self, plugin: StrategyPlugin | None = None, error: Exception | None = None) -> None:
        self.plugin = plugin
        self.error = error
        self.load_calls = 0

    async def load(self, strategy: Strategy) -> StrategyPlugin:
        self.load_calls += 1
        if self.error is not None:
            raise self.error
        assert self.plugin is not None, "FakeStrategyLoader requires a plugin or an error"
        return self.plugin


class SpySignalManager:
    """Duck-typed `SignalManager` stand-in recording every `submit(...)`
    call without persisting or executing anything."""

    def __init__(self) -> None:
        self.submissions: list[tuple[Strategy, SignalProposal]] = []

    async def submit(
        self, strategy: Strategy, proposal: SignalProposal, *, exchange: Any, auto_execute: bool = True
    ) -> Signal | None:
        self.submissions.append((strategy, proposal))
        return None


def make_strategy(**overrides: Any) -> Strategy:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test Strategy",
        description="",
        symbol="BTCUSDT",
        status=StrategyStatus.PAPER_TRADING,
        version=1,
        created_at=now,
        updated_at=now,
        config={"strategy_type": "DUMMY", "parameters": {"quantity": "0.01"}},
    )
    defaults.update(overrides)
    return Strategy(**defaults)


def make_signal(**overrides: Any) -> Signal:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = dict(
        id=uuid.uuid4(),
        strategy_id=uuid.uuid4(),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.01"),
        status=SignalStatus.PENDING,
        generated_at=now,
    )
    defaults.update(overrides)
    return Signal(**defaults)


def make_ticker(**overrides: Any) -> Ticker:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = dict(
        symbol="BTCUSDT",
        last_price=Decimal("50000"),
        bid_price=Decimal("49999"),
        ask_price=Decimal("50001"),
        high_price=Decimal("51000"),
        low_price=Decimal("49000"),
        volume=Decimal("100"),
        quote_volume=Decimal("5000000"),
        price_change_percent=Decimal("1.5"),
        open_time=now - timedelta(minutes=1),
        close_time=now,
    )
    defaults.update(overrides)
    return Ticker(**defaults)


def make_candle(**overrides: Any) -> Candle:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = dict(
        symbol="BTCUSDT",
        interval=KlineInterval.ONE_MINUTE,
        open_time=now - timedelta(minutes=1),
        close_time=now,
        open=Decimal("50000"),
        high=Decimal("50100"),
        low=Decimal("49900"),
        close=Decimal("50050"),
        volume=Decimal("10"),
        quote_volume=Decimal("500000"),
        trade_count=100,
        is_closed=True,
    )
    defaults.update(overrides)
    return Candle(**defaults)
