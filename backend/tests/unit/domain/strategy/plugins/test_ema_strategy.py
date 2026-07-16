from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.indicators import EmaIndicator
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.ema_strategy import EmaCrossoverStrategy


def make_candle(**overrides: object) -> Candle:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        interval=KlineInterval.ONE_MINUTE,
        open_time=now,
        close_time=now + timedelta(minutes=1),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        quote_volume=Decimal("100"),
        trade_count=1,
        is_closed=True,
    )
    defaults.update(overrides)
    return Candle(**defaults)  # type: ignore[arg-type]


def make_ticker(**overrides: object) -> Ticker:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        last_price=Decimal("100"),
        bid_price=Decimal("99.9"),
        ask_price=Decimal("100.1"),
        high_price=Decimal("101"),
        low_price=Decimal("99"),
        volume=Decimal("10"),
        quote_volume=Decimal("1000"),
        price_change_percent=Decimal("0"),
        open_time=now,
        close_time=now + timedelta(minutes=1),
    )
    defaults.update(overrides)
    return Ticker(**defaults)  # type: ignore[arg-type]


def make_context(**parameters: object) -> StrategyContext:
    return StrategyContext(strategy_id=uuid.uuid4(), symbol="BTCUSDT", parameters=parameters)


@pytest.mark.asyncio
async def test_initialize_raises_when_quantity_missing() -> None:
    plugin = EmaCrossoverStrategy(make_context(fast_period=2, slow_period=5))
    with pytest.raises(InvalidStrategyConfigError):
        await plugin.initialize()


@pytest.mark.asyncio
async def test_on_tick_is_a_no_op() -> None:
    plugin = EmaCrossoverStrategy(make_context(quantity="1", fast_period=2, slow_period=5))
    await plugin.initialize()
    await plugin.on_tick(make_ticker())
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_unclosed_candles_are_ignored() -> None:
    plugin = EmaCrossoverStrategy(make_context(quantity="1", fast_period=2, slow_period=5))
    await plugin.initialize()
    await plugin.on_candle(make_candle(close=Decimal("999"), is_closed=False))
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_crossovers_emit_signals_and_unchanged_relation_emits_nothing() -> None:
    fast_period, slow_period = 2, 5
    prices = [Decimal(v) for v in [100, 100, 100, 100, 100, 130, 150, 170, 60, 40, 20]]

    fast = EmaIndicator(period=fast_period)
    slow = EmaIndicator(period=slow_period)
    previous_relation: int | None = None
    expected: dict[int, OrderSide] = {}
    for i, price in enumerate(prices):
        fast_value = fast.update(price)
        slow_value = slow.update(price)
        relation = 1 if fast_value > slow_value else (-1 if fast_value < slow_value else 0)
        if previous_relation is not None and relation != previous_relation and relation != 0:
            expected[i] = OrderSide.BUY if relation == 1 else OrderSide.SELL
        previous_relation = relation

    assert {side for side in expected.values()} == {OrderSide.BUY, OrderSide.SELL}

    plugin = EmaCrossoverStrategy(make_context(quantity="1", fast_period=fast_period, slow_period=slow_period))
    await plugin.initialize()

    for i, price in enumerate(prices):
        await plugin.on_candle(make_candle(close=price))
        signal = plugin.generate_signal()
        if i in expected:
            assert signal is not None, f"expected a signal at candle {i}"
            assert signal.side == expected[i]
            assert signal.target_price == price
        else:
            assert signal is None, f"unexpected signal at candle {i}: {signal}"
