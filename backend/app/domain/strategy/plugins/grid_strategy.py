"""Grid trading: lay a ladder of evenly-spaced price levels around a base
price, buy whenever price steps down onto a lower rung, sell whenever it
steps up onto a higher one — a range-bound market oscillating across the
grid produces a steady stream of small round-trip profits.

Entirely tick-driven (grid crossings are a pure price phenomenon, not a
candle-close one) and lazily initialized: the base price defaults to
whatever the *first* ticker price turns out to be if `base_price` isn't
given in `parameters`, since a grid centered on an arbitrary hardcoded
price would drift out of range as soon as the market moved.

Parameters: `grid_levels` (rungs on *each* side of the base price; default
5), `grid_spacing_pct` (percent distance between adjacent rungs; default
`1`), `base_price` (optional — seeded from the first tick if omitted),
`quantity` (required, per rung).
"""

from __future__ import annotations

from bisect import bisect_right
from decimal import Decimal

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import register_strategy


@register_strategy
class GridStrategy(StrategyPlugin):
    strategy_type = "GRID"

    async def initialize(self) -> None:
        params = self.context.parameters
        self._levels = int(params.get("grid_levels", 5))
        self._spacing = Decimal(str(params.get("grid_spacing_pct", "1"))) / Decimal(100)
        self._quantity()

        base_price = params.get("base_price")
        self._base_price: Decimal | None = Decimal(str(base_price)) if base_price is not None else None
        self._grid: list[Decimal] | None = self._build_grid(self._base_price) if self._base_price else None
        self._current_index: int | None = None

    def _build_grid(self, base_price: Decimal) -> list[Decimal]:
        return sorted(base_price * (Decimal(1) + self._spacing * i) for i in range(-self._levels, self._levels + 1))

    async def on_tick(self, ticker: Ticker) -> None:
        if self._grid is None:
            self._base_price = ticker.last_price
            self._grid = self._build_grid(self._base_price)
            self._current_index = bisect_right(self._grid, ticker.last_price)
            return

        new_index = bisect_right(self._grid, ticker.last_price)
        if self._current_index is not None and new_index != self._current_index:
            if new_index < self._current_index:
                self._emit(OrderSide.BUY, target_price=ticker.last_price, reason="Price dropped to a lower grid level")
            else:
                self._emit(OrderSide.SELL, target_price=ticker.last_price, reason="Price rose to a higher grid level")
        self._current_index = new_index

    async def on_candle(self, candle: Candle) -> None:
        return None

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None
