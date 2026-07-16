"""MACD signal-line crossover: buy when the MACD line crosses above its own
signal line (momentum turning up), sell when it crosses back below.

Same candle-driven shape as the EMA strategy (MACD is itself built from
EMAs of the close price) — `on_tick` is a no-op for the same reason.

Parameters: `fast_period` (default 12), `slow_period` (default 26),
`signal_period` (default 9), `quantity` (required).
"""

from __future__ import annotations

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.indicators import MacdIndicator
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class MacdStrategy(StrategyPlugin):
    strategy_type = "MACD"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._macd = MacdIndicator(
            fast_period=int(params.get("fast_period", 12)),
            slow_period=int(params.get("slow_period", 26)),
            signal_period=int(params.get("signal_period", 9)),
        )
        self._quantity()
        self._previous_relation: int | None = None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        if not candle.is_closed:
            return

        macd_line, signal_line = self._macd.update(candle.close)
        relation = 1 if macd_line > signal_line else (-1 if macd_line < signal_line else 0)

        if self._previous_relation is not None and relation != self._previous_relation and relation != 0:
            if relation == 1:
                self._emit(OrderSide.BUY, target_price=candle.close, reason="MACD crossed above signal line")
            else:
                self._emit(OrderSide.SELL, target_price=candle.close, reason="MACD crossed below signal line")
        self._previous_relation = relation

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
