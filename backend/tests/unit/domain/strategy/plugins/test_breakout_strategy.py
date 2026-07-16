from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.breakout_strategy import BreakoutStrategy


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
    plugin = BreakoutStrategy(make_context(lookback_period=3))
    with pytest.raises(InvalidStrategyConfigError):
        await plugin.initialize()


@pytest.mark.asyncio
async def test_on_tick_is_a_no_op() -> None:
    plugin = BreakoutStrategy(make_context(quantity="1", lookback_period=3))
    await plugin.initialize()
    await plugin.on_tick(make_ticker())
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_unclosed_candles_are_ignored_and_not_pushed_to_window() -> None:
    plugin = BreakoutStrategy(make_context(quantity="1", lookback_period=3))
    await plugin.initialize()

    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(8)))
    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(999), is_closed=False))
    assert plugin.generate_signal() is None
    assert plugin._window.is_full is False


@pytest.mark.asyncio
async def test_no_breakout_fires_before_window_is_full() -> None:
    plugin = BreakoutStrategy(make_context(quantity="1", lookback_period=3))
    await plugin.initialize()

    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(8)))
    assert plugin.generate_signal() is None
    # A dramatic close that would otherwise be a breakout — window isn't full yet.
    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(999)))
    assert plugin.generate_signal() is None
    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(8)))
    assert plugin.generate_signal() is None
    assert plugin._window.is_full is True


@pytest.mark.asyncio
async def test_breakout_up_down_rearm_and_no_duplicate_sequence() -> None:
    plugin = BreakoutStrategy(make_context(quantity="1", lookback_period=3))
    await plugin.initialize()

    candles = [
        # Fill the window: highest_high=10, lowest_low=5.
        dict(high=Decimal(10), low=Decimal(5), close=Decimal(8)),
        dict(high=Decimal(10), low=Decimal(5), close=Decimal(8)),
        dict(high=Decimal(10), low=Decimal(5), close=Decimal(8)),
        # window full now [10,10,10]/[5,5,5] -> close 12 > 10 -> BUY.
        dict(high=Decimal(12), low=Decimal(9), close=Decimal(12)),
        # window [10,10,12]/[5,5,9] -> high=12,low=5 -> close 9 within range -> rearm.
        dict(high=Decimal(9), low=Decimal(8), close=Decimal(9)),
        # window [10,12,9]/[5,9,8] -> high=12,low=5 -> close 13 > 12, rearmed -> BUY again.
        dict(high=Decimal(13), low=Decimal(10), close=Decimal(13)),
        # window [12,9,13]/[9,8,10] -> high=13,low=8 -> close 5 < 8 -> SELL.
        dict(high=Decimal(6), low=Decimal(4), close=Decimal(5)),
        # window [9,13,6]/[8,10,4] -> high=13,low=4 -> close 5 within [4,13] -> rearm, no signal.
        dict(high=Decimal(5), low=Decimal(5), close=Decimal(5)),
    ]
    expected = {3: OrderSide.BUY, 5: OrderSide.BUY, 6: OrderSide.SELL}

    for i, candle_kwargs in enumerate(candles):
        await plugin.on_candle(make_candle(**candle_kwargs))
        signal = plugin.generate_signal()
        if i in expected:
            assert signal is not None, f"expected a signal at candle {i}"
            assert signal.side == expected[i]
        else:
            assert signal is None, f"unexpected signal at candle {i}: {signal}"


@pytest.mark.asyncio
async def test_no_duplicate_signal_while_still_broken_out() -> None:
    plugin = BreakoutStrategy(make_context(quantity="1", lookback_period=2))
    await plugin.initialize()

    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(8)))
    assert plugin.generate_signal() is None
    await plugin.on_candle(make_candle(high=Decimal(10), low=Decimal(5), close=Decimal(8)))
    assert plugin.generate_signal() is None  # window just became full, no candle to compare against yet

    # window [10,10]/[5,5] -> close 12 > 10 -> BUY.
    await plugin.on_candle(make_candle(high=Decimal(12), low=Decimal(9), close=Decimal(12)))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.BUY

    # window [10,12]/[5,9] -> high=12,low=5 -> close 13 > 12 but still "up" -> no duplicate.
    await plugin.on_candle(make_candle(high=Decimal(13), low=Decimal(10), close=Decimal(13)))
    assert plugin.generate_signal() is None
