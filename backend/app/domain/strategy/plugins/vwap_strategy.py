"""VWAP mean reversion: the session Volume-Weighted Average Price is the
"fair value" a lot of intraday desks trade against — buy when price drifts
too far below it, sell when it drifts too far above, on the assumption
price tends to revert toward VWAP over the session.

VWAP itself is candle-driven (it needs volume, which a ticker doesn't
carry) — `on_candle` maintains the indicator. The deviation check is
tick-driven, since "how far is the *current* price from VWAP" is exactly
what a ticker update answers, and reacting only on candle close would add
up to a whole candle's worth of unnecessary lag.

Parameters: `deviation_pct` (percent distance from VWAP that triggers a
signal; default `0.5`), `quantity` (required).
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.indicators import VwapIndicator
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class VwapMeanReversionStrategy(StrategyPlugin):
    strategy_type = "VWAP_MEAN_REVERSION"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._vwap = VwapIndicator()
        self._deviation = Decimal(str(params.get("deviation_pct", "0.5"))) / Decimal(100)
        self._quantity()
        self._zone: str | None = None  # "below" | "above" | "within"

    async def on_candle(self, candle: Candle) -> None:
        if candle.is_closed:
            self._vwap.update(candle)

    async def on_tick(self, ticker: Ticker) -> None:
        vwap = self._vwap.value
        if vwap is None or vwap == 0:
            return

        deviation = (ticker.last_price - vwap) / vwap
        if deviation <= -self._deviation:
            zone = "below"
        elif deviation >= self._deviation:
            zone = "above"
        else:
            zone = "within"

        if zone != self._zone:
            if zone == "below":
                self._emit(OrderSide.BUY, target_price=ticker.last_price, reason="Price dropped below VWAP band")
            elif zone == "above":
                self._emit(OrderSide.SELL, target_price=ticker.last_price, reason="Price rose above VWAP band")
        self._zone = zone

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
