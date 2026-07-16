from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.indicators import RsiIndicator
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.rsi_strategy import RsiStrategy


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
    plugin = RsiStrategy(make_context(period=3))
    with pytest.raises(InvalidStrategyConfigError):
        await plugin.initialize()


@pytest.mark.asyncio
async def test_default_thresholds_are_30_and_70() -> None:
    plugin = RsiStrategy(make_context(quantity="1"))
    await plugin.initialize()
    assert plugin._oversold == Decimal("30")
    assert plugin._overbought == Decimal("70")


@pytest.mark.asyncio
async def test_custom_thresholds_via_parameters() -> None:
    plugin = RsiStrategy(make_context(quantity="1", oversold="20", overbought="80"))
    await plugin.initialize()
    assert plugin._oversold == Decimal("20")
    assert plugin._overbought == Decimal("80")


@pytest.mark.asyncio
async def test_on_tick_is_a_no_op() -> None:
    plugin = RsiStrategy(make_context(quantity="1", period=3))
    await plugin.initialize()
    await plugin.on_tick(make_ticker())
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_unclosed_candles_are_ignored() -> None:
    plugin = RsiStrategy(make_context(quantity="1", period=3))
    await plugin.initialize()
    await plugin.on_candle(make_candle(close=Decimal("999"), is_closed=False))
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_zone_edge_triggering_matches_indicator_zones() -> None:
    period = 3
    prices = [Decimal(v) for v in [100, 90, 80, 70, 75, 85, 95, 105, 115, 125, 120, 118]]
    oversold = Decimal("30")
    overbought = Decimal("70")

    rsi = RsiIndicator(period=period)
    zone: str | None = None
    expected: dict[int, OrderSide] = {}
    for i, price in enumerate(prices):
        value = rsi.update(price)
        if value is None:
            continue
        if value <= oversold:
            new_zone = "oversold"
        elif value >= overbought:
            new_zone = "overbought"
        else:
            new_zone = "neutral"
        if new_zone != zone:
            if new_zone == "oversold":
                expected[i] = OrderSide.BUY
            elif new_zone == "overbought":
                expected[i] = OrderSide.SELL
        zone = new_zone

    assert expected, "test setup should cross at least one zone boundary"

    plugin = RsiStrategy(make_context(quantity="1", period=period))
    await plugin.initialize()

    for i, price in enumerate(prices):
        await plugin.on_candle(make_candle(close=price))
        signal = plugin.generate_signal()
        if i in expected:
            assert signal is not None, f"expected a signal at candle {i}"
            assert signal.side == expected[i]
        else:
            assert signal is None, f"unexpected signal at candle {i}: {signal}"
