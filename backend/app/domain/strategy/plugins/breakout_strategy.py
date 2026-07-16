"""Breakout: buy when price closes above the highest high of the last N
*prior* candles (a fresh high says the range just got broken to the
upside), sell/short-signal when it closes below the lowest low of the same
window.

Candle-driven — a breakout is defined against a candle's close, not an
intra-candle wick, so `on_tick` does nothing. `RollingHighLow` explicitly
excludes the candle currently being evaluated from its own window (pushed
*after* the breakout check, not before) — comparing a candle's close to a
window that already includes that same candle's high/low would make a
breakout almost tautological.

Parameters: `lookback_period` (default 20), `quantity` (required).
"""

from __future__ import annotations

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.indicators import RollingHighLow
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class BreakoutStrategy(StrategyPlugin):
    strategy_type = "BREAKOUT"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._window = RollingHighLow(period=int(params.get("lookback_period", 20)))
        self._quantity()
        self._last_breakout: str | None = None  # "up" | "down" | None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        if not candle.is_closed:
            return

        if self._window.is_full:
            rolling_high = self._window.highest_high
            rolling_low = self._window.lowest_low
            if candle.close > rolling_high and self._last_breakout != "up":
                self._emit(OrderSide.BUY, target_price=candle.close, reason=f"Broke above {self._window_size()}-candle high")
                self._last_breakout = "up"
            elif candle.close < rolling_low and self._last_breakout != "down":
                self._emit(OrderSide.SELL, target_price=candle.close, reason=f"Broke below {self._window_size()}-candle low")
                self._last_breakout = "down"
            elif rolling_low <= candle.close <= rolling_high:
                self._last_breakout = None  # back inside the range — arm for the next breakout

        self._window.push(high=candle.high, low=candle.low)

    def _window_size(self) -> int:
        return int(self.context.parameters.get("lookback_period", 20))

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
