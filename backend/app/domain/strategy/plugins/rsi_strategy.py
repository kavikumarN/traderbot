"""RSI mean reversion: buy when the Relative Strength Index drops into
oversold territory (the recent selloff looks overdone), sell when it rises
into overbought territory (the recent rally looks overdone).

Edge-triggered on the oversold/overbought *zone*, not the raw RSI value —
without that, a strategy sitting at RSI 25 for ten straight candles would
otherwise fire ten identical BUY signals instead of one.

Parameters: `period` (default 14), `oversold` (default 30), `overbought`
(default 70), `quantity` (required).
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.indicators import RsiIndicator
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class RsiStrategy(StrategyPlugin):
    strategy_type = "RSI"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._rsi = RsiIndicator(period=int(params.get("period", 14)))
        self._oversold = Decimal(str(params.get("oversold", "30")))
        self._overbought = Decimal(str(params.get("overbought", "70")))
        self._quantity()
        self._zone: str | None = None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        if not candle.is_closed:
            return

        rsi = self._rsi.update(candle.close)
        if rsi is None:
            return

        if rsi <= self._oversold:
            zone = "oversold"
        elif rsi >= self._overbought:
            zone = "overbought"
        else:
            zone = "neutral"

        if zone != self._zone:
            if zone == "oversold":
                self._emit(OrderSide.BUY, target_price=candle.close, reason=f"RSI {rsi:.2f} entered oversold")
            elif zone == "overbought":
                self._emit(OrderSide.SELL, target_price=candle.close, reason=f"RSI {rsi:.2f} entered overbought")
        self._zone = zone

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
