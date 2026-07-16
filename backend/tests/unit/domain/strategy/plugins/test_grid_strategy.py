from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.grid_strategy import GridStrategy


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
    plugin = GridStrategy(make_context(grid_levels=2, grid_spacing_pct="1"))
    with pytest.raises(InvalidStrategyConfigError):
        await plugin.initialize()


@pytest.mark.asyncio
async def test_on_candle_is_a_no_op() -> None:
    plugin = GridStrategy(make_context(quantity="1", grid_levels=2, grid_spacing_pct="1"))
    await plugin.initialize()
    await plugin.on_candle(make_candle())
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_base_price_is_lazily_seeded_from_first_tick_when_omitted() -> None:
    plugin = GridStrategy(make_context(quantity="1", grid_levels=2, grid_spacing_pct="1"))
    await plugin.initialize()
    assert plugin._base_price is None
    assert plugin._grid is None

    await plugin.on_tick(make_ticker(last_price=Decimal("100")))

    assert plugin._base_price == Decimal("100")
    assert plugin._grid == [Decimal("98"), Decimal("99"), Decimal("100"), Decimal("101"), Decimal("102")]
    # First tick just seeds — no signal should be emitted from it.
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_explicit_base_price_is_respected_instead_of_first_tick() -> None:
    plugin = GridStrategy(make_context(quantity="1", grid_levels=2, grid_spacing_pct="1", base_price="100"))
    await plugin.initialize()

    assert plugin._base_price == Decimal("100")
    assert plugin._grid == [Decimal("98"), Decimal("99"), Decimal("100"), Decimal("101"), Decimal("102")]

    # First tick, even far from the base price, must not re-seed the grid.
    await plugin.on_tick(make_ticker(last_price=Decimal("150")))
    assert plugin._base_price == Decimal("100")
    assert plugin.generate_signal() is None


@pytest.mark.asyncio
async def test_buy_on_step_down_and_sell_on_step_up_grid_rungs() -> None:
    plugin = GridStrategy(make_context(quantity="1", grid_levels=2, grid_spacing_pct="1"))
    await plugin.initialize()

    # Seeds base price at 100 -> grid = [98, 99, 100, 101, 102], current index 3.
    await plugin.on_tick(make_ticker(last_price=Decimal("100")))
    assert plugin.generate_signal() is None

    # Step down to a lower rung -> BUY.
    await plugin.on_tick(make_ticker(last_price=Decimal("99.5")))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.BUY

    # Same rung -> no duplicate signal.
    await plugin.on_tick(make_ticker(last_price=Decimal("99.5")))
    assert plugin.generate_signal() is None

    # Step up past the base to a higher rung -> SELL.
    await plugin.on_tick(make_ticker(last_price=Decimal("101.5")))
    signal = plugin.generate_signal()
    assert signal is not None
    assert signal.side == OrderSide.SELL
