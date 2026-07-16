"""EMA crossover: the classic trend-following signal — go long when a fast
EMA crosses above a slow EMA (an uptrend just started dominating), go flat/
short when it crosses back below.

Candle-driven, not tick-driven: an EMA crossover is a statement about where
the market closed over a period, so `on_tick` deliberately does nothing —
computing it off every intra-candle tick would just make the crossover
noisier without making it more correct.

Parameters: `fast_period` (default 12), `slow_period` (default 26),
`quantity` (required).
"""

from __future__ import annotations

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.indicators import EmaIndicator
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class EmaCrossoverStrategy(StrategyPlugin):
    strategy_type = "EMA_CROSSOVER"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._fast = EmaIndicator(period=int(params.get("fast_period", 12)))
        self._slow = EmaIndicator(period=int(params.get("slow_period", 26)))
        self._quantity()  # fail fast if parameters.quantity is missing/invalid
        self._previous_relation: int | None = None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        if not candle.is_closed:
            return

        fast_value = self._fast.update(candle.close)
        slow_value = self._slow.update(candle.close)
        relation = 1 if fast_value > slow_value else (-1 if fast_value < slow_value else 0)

        if self._previous_relation is not None and relation != self._previous_relation and relation != 0:
            if relation == 1:
                self._emit(OrderSide.BUY, target_price=candle.close, reason="EMA fast crossed above slow")
            else:
                self._emit(OrderSide.SELL, target_price=candle.close, reason="EMA fast crossed below slow")
        self._previous_relation = relation

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
