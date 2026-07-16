from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.backtest_engine import BacktestEngine
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugins.ema_strategy import EmaCrossoverStrategy
from app.domain.strategy.plugins.rsi_strategy import RsiStrategy

pytestmark = pytest.mark.asyncio

_SYMBOL = "BTCUSDT"
_START = datetime(2026, 1, 1, tzinfo=UTC)


def _candles(closes: list[str]) -> list[Candle]:
    candles = []
    for i, close in enumerate(closes):
        open_time = _START + timedelta(hours=i)
        price = Decimal(close)
        candles.append(
            Candle(
                symbol=_SYMBOL,
                interval=KlineInterval.ONE_HOUR,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=59, seconds=59),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal("1"),
                quote_volume=price,
                trade_count=1,
                is_closed=True,
            )
        )
    return candles


async def test_ema_crossover_backtest_produces_fills_and_a_full_equity_curve() -> None:
    # A sharp rally then reversal all but guarantees the fast EMA crosses
    # above, then back below, the slow EMA at least once each.
    closes = ["100", "100", "150", "200", "150", "100", "50", "50"]
    candles = _candles(closes)

    plugin = EmaCrossoverStrategy(
        StrategyContext(
            strategy_id=uuid.uuid4(),
            symbol=_SYMBOL,
            parameters={"fast_period": 2, "slow_period": 4, "quantity": "1"},
        )
    )
    await plugin.initialize()

    engine = BacktestEngine()
    result = await engine.run(
        plugin,
        candles,
        initial_balance=Decimal("10000"),
        commission_rate=Decimal("0.001"),
        periods_per_year=Decimal(365 * 24),
    )

    assert len(result.equity_curve) == len(candles)
    assert result.equity_curve[-1].equity == result.final_balance
    assert result.total_trades == len(result.fills)
    assert len(result.fills) >= 1
    assert result.fills[0].side.value == "BUY"  # the initial rally triggers the first crossover
    assert Decimal("0") <= result.win_rate <= Decimal("1")
    assert result.max_drawdown_pct >= Decimal("0")


async def test_rsi_backtest_stays_flat_when_price_never_leaves_the_neutral_zone() -> None:
    # Small alternating up/down wiggles keep average gains and losses close
    # to equal, so RSI hovers near 50 — never actually flat (RSI defaults to
    # 100 on a truly flat series: zero losses makes it "maximally overbought"
    # by the standard formula, not neutral).
    closes = [str(100 + (1 if i % 2 == 0 else -1)) for i in range(20)]
    candles = _candles(closes)

    plugin = RsiStrategy(
        StrategyContext(
            strategy_id=uuid.uuid4(), symbol=_SYMBOL, parameters={"period": 14, "quantity": "1"}
        )
    )
    await plugin.initialize()

    engine = BacktestEngine()
    result = await engine.run(
        plugin,
        candles,
        initial_balance=Decimal("10000"),
        commission_rate=Decimal("0.001"),
        periods_per_year=Decimal(365 * 24),
    )

    assert result.fills == []
    assert result.final_balance == Decimal("10000")
    assert result.total_trades == 0
