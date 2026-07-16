from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.vwap_strategy import VwapMeanReversionStrategy


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
    plugin = VwapMeanReversionStrategy(make_context(deviation_pct="1"))
    with pytest.raises(InvalidStrategyConfigError):
        await plugin.initialize()


@pytest.mark.asyncio
async def test_on_tick_with_no_vwap_yet_is_a_no_op() -> None:
    plugin = VwapMeanReversionStrategy(make_context(quantity="1", deviation_pct="1"))
    await plugin.initialize()
    await plugin.on_tick(make_ticker(last_price=Decimal("500")))
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_on_candle_ignores_unclosed_candles() -> None:
    plugin = VwapMeanReversionStrategy(make_context(quantity="1", deviation_pct="1"))
    await plugin.initialize()
    await plugin.on_candle(
        make_candle(high=Decimal("100"), low=Decimal("100"), close=Decimal("100"), volume=Decimal("1"), is_closed=False)
    )
    assert plugin._vwap.value is None


@pytest.mark.asyncio
async def test_on_tick_only_fires_on_zone_transition() -> None:
    plugin = VwapMeanReversionStrategy(make_context(quantity="1", deviation_pct="1"))
    await plugin.initialize()

    await plugin.on_candle(
        make_candle(high=Decimal("100"), low=Decimal("100"), close=Decimal("100"), volume=Decimal("1"))
    )
    assert plugin._vwap.value == Decimal("100")

    # First tick: within band, zone goes None -> "within", no signal (no "within" branch).
    await plugin.on_tick(make_ticker(last_price=Decimal("100")))
    assert plugin.generate_signal() is None

    # Drops below the 1% band -> BUY.
    await plugin.on_tick(make_ticker(last_price=Decimal("98")))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.BUY

    # Still below the band -> no duplicate signal.
    await plugin.on_tick(make_ticker(last_price=Decimal("98.5")))
    assert plugin.generate_signal() is None

    # Back within the band -> zone changes but no emit (no "within" branch).
    await plugin.on_tick(make_ticker(last_price=Decimal("100")))
    assert plugin.generate_signal() is None

    # Rises above the 1% band -> SELL.
    await plugin.on_tick(make_ticker(last_price=Decimal("102")))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.SELL

    # Still above the band -> no duplicate signal.
    await plugin.on_tick(make_ticker(last_price=Decimal("103")))
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_vwap_resets_on_new_session_and_flows_through_to_ticks() -> None:
    plugin = VwapMeanReversionStrategy(make_context(quantity="1", deviation_pct="1"))
    await plugin.initialize()

    day_one = datetime(2024, 1, 1, 23, 0, tzinfo=UTC)
    day_two = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)

    await plugin.on_candle(
        make_candle(open_time=day_one, high=Decimal("100"), low=Decimal("100"), close=Decimal("100"), volume=Decimal("1"))
    )
    assert plugin._vwap.value == Decimal("100")

    await plugin.on_candle(
        make_candle(open_time=day_two, high=Decimal("200"), low=Decimal("200"), close=Decimal("200"), volume=Decimal("1"))
    )
    assert plugin._vwap.value == Decimal("200")

    await plugin.on_tick(make_ticker(last_price=Decimal("202")))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.SELL
