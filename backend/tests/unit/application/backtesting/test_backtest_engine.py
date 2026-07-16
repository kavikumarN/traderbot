from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.backtest_engine import BacktestEngine
from app.domain.exchange.enums import KlineInterval, OrderSide, OrderType
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.plugin import SignalProposal, StrategyContext, StrategyPlugin
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


def _ohlc_candles(bars: list[tuple[str, str, str, str, str]]) -> list[Candle]:
    """Each bar is `(open, high, low, close, volume)` — for order-simulation
    tests that need distinct intracandle ranges, unlike `_candles`'s flat
    open==high==low==close bars."""
    candles = []
    for i, (open_, high, low, close, volume) in enumerate(bars):
        open_time = _START + timedelta(hours=i)
        candles.append(
            Candle(
                symbol=_SYMBOL,
                interval=KlineInterval.ONE_HOUR,
                open_time=open_time,
                close_time=open_time + timedelta(minutes=59, seconds=59),
                open=Decimal(open_),
                high=Decimal(high),
                low=Decimal(low),
                close=Decimal(close),
                volume=Decimal(volume),
                quote_volume=Decimal(volume) * Decimal(close),
                trade_count=1,
                is_closed=True,
            )
        )
    return candles


class _ScriptedPlugin(StrategyPlugin):
    """Emits a pre-scripted `SignalProposal` on specific candle indices
    (0-based, in the order `BacktestEngine.run` iterates `candles`) — finer
    control than `tests.unit.application.strategies.helpers.DummyPlugin`'s
    single one-shot signal, needed here to script signals several candles
    apart within one backtest run."""

    strategy_type = "SCRIPTED"

    def __init__(self, context: StrategyContext, script: dict[int, SignalProposal]) -> None:
        super().__init__(context)
        self._script = script
        self._candle_index = -1

    async def initialize(self) -> None:
        return None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        self._candle_index += 1
        if self._candle_index in self._script:
            self._pending_signal = self._script[self._candle_index]

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None


def _scripted_plugin(script: dict[int, SignalProposal]) -> _ScriptedPlugin:
    context = StrategyContext(strategy_id=uuid.uuid4(), symbol=_SYMBOL, parameters={"quantity": "1"})
    return _ScriptedPlugin(context, script)


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


async def test_limit_entry_does_not_fill_until_a_later_candle_touches_it() -> None:
    candles = _ohlc_candles(
        [
            ("100", "101", "99", "100", "1000"),  # signal emitted here; nothing fills yet
            ("100", "101", "99", "100", "1000"),  # low 99 never reaches the 95 limit
            ("100", "101", "94", "98", "1000"),  # low 94 touches 95 — fills here
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("95"),
            order_type=OrderType.LIMIT, reason="limit entry",
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24),
    )

    assert len(result.fills) == 1
    fill = result.fills[0]
    assert fill.price == Decimal("95")
    assert fill.quantity == Decimal("1")
    assert fill.executed_at == candles[2].close_time
    assert "limit" in fill.reason


async def test_limit_entry_partially_fills_across_several_candles() -> None:
    candles = _ohlc_candles(
        [
            ("100", "101", "99", "100", "100"),  # signal emitted here
            ("100", "101", "90", "95", "100"),  # touches: fills 10 (10% of volume 100)
            ("100", "101", "90", "95", "100"),  # touches: fills another 10
            ("100", "101", "90", "95", "100"),  # touches: fills the remaining 5
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("25"), target_price=Decimal("95"), order_type=OrderType.LIMIT
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24),
    )

    assert [f.quantity for f in result.fills] == [Decimal("10"), Decimal("10"), Decimal("5")]
    assert "partial" in result.fills[0].reason
    assert "partial" in result.fills[1].reason
    assert "partial" not in result.fills[2].reason
    assert result.fills[-1].position_after == Decimal("25")


async def test_stop_loss_closes_the_entire_position_when_touched() -> None:
    candles = _ohlc_candles(
        [
            ("100", "100", "100", "100", "100"),  # market entry here
            ("100", "102", "99", "101", "100"),  # doesn't touch the 90 stop
            ("100", "101", "85", "90", "100"),  # low 85 touches the stop at 90
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("100"),
            stop_loss_price=Decimal("90"), reason="entry",
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24),
    )

    assert len(result.fills) == 2
    exit_fill = result.fills[1]
    assert exit_fill.reason == "stop_loss"
    assert exit_fill.price == Decimal("90")
    assert exit_fill.side == OrderSide.SELL
    assert exit_fill.position_after == Decimal("0")
    assert exit_fill.executed_at == candles[2].close_time


async def test_take_profit_closes_the_entire_position_when_touched() -> None:
    candles = _ohlc_candles(
        [
            ("100", "100", "100", "100", "100"),  # market entry here
            ("100", "102", "99", "101", "100"),  # doesn't touch the 110 target
            ("100", "112", "99", "108", "100"),  # high 112 touches the target at 110
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("100"),
            take_profit_price=Decimal("110"), reason="entry",
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24),
    )

    assert len(result.fills) == 2
    exit_fill = result.fills[1]
    assert exit_fill.reason == "take_profit"
    assert exit_fill.price == Decimal("110")


async def test_trailing_stop_ratchets_across_candles_then_triggers_on_a_pullback() -> None:
    candles = _ohlc_candles(
        [
            ("100", "100", "100", "100", "100"),  # market entry here, trailing_stop_pct=0.1
            ("100", "110", "105", "108", "100"),  # ratchets to 110*0.9 = 99, no trigger
            ("108", "115", "110", "112", "100"),  # ratchets to 115*0.9 = 103.5, no trigger
            ("112", "113", "100", "105", "100"),  # stays at 103.5 (113*0.9=101.7 is looser); low 100 triggers it
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("100"),
            trailing_stop_pct=Decimal("0.1"), reason="entry",
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24),
    )

    assert len(result.fills) == 2
    exit_fill = result.fills[1]
    assert exit_fill.reason == "trailing_stop"
    assert exit_fill.price == Decimal("103.5")
    assert exit_fill.executed_at == candles[3].close_time


async def test_slippage_worsens_market_fills_but_never_touches_limit_fills() -> None:
    candles = _ohlc_candles(
        [
            ("100", "101", "99", "100", "1000"),  # market entry — should slip worse than 100
            ("100", "101", "94", "98", "1000"),  # limit sell at 105 never reached; irrelevant here
        ]
    )
    script = {
        0: SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("100"), reason="entry"),
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24), slippage_bps=Decimal("100"),  # 1%
    )

    assert result.fills[0].price == Decimal("100") * Decimal("1.01")


async def test_limit_fill_price_is_exact_regardless_of_slippage_setting() -> None:
    candles = _ohlc_candles(
        [
            ("100", "101", "99", "100", "1000"),  # limit buy emitted here
            ("100", "101", "94", "98", "1000"),  # touches the 95 limit
        ]
    )
    script = {
        0: SignalProposal(
            side=OrderSide.BUY, quantity=Decimal("1"), target_price=Decimal("95"), order_type=OrderType.LIMIT
        )
    }
    plugin = _scripted_plugin(script)
    await plugin.initialize()

    result = await BacktestEngine().run(
        plugin, candles, initial_balance=Decimal("10000"), commission_rate=Decimal("0"),
        periods_per_year=Decimal(365 * 24), slippage_bps=Decimal("100"),
    )

    assert result.fills[0].price == Decimal("95")  # unchanged — limit fills never slip
