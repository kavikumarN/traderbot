"""Trading rules ("filters") and the symbol catalog.

Exposed as behavior (``round_price`` / ``round_quantity``), not just data —
placing an order at a price the exchange will reject for violating its own
tick size is exactly the kind of bug this is meant to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import SymbolStatus


@dataclass(frozen=True, slots=True)
class PriceFilter:
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal


@dataclass(frozen=True, slots=True)
class LotSizeFilter:
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal


@dataclass(frozen=True, slots=True)
class NotionalFilter:
    min_notional: Decimal


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    symbol: str
    base_asset: str
    quote_asset: str
    status: SymbolStatus
    price_filter: PriceFilter | None = None
    lot_size_filter: LotSizeFilter | None = None
    notional_filter: NotionalFilter | None = None

    @property
    def is_trading(self) -> bool:
        return self.status == SymbolStatus.TRADING

    def round_price(self, price: Decimal) -> Decimal:
        """Floor `price` to the nearest valid tick, per Binance's PRICE_FILTER."""
        step = self.price_filter.tick_size if self.price_filter else None
        return _floor_to_step(price, step)

    def round_quantity(self, quantity: Decimal) -> Decimal:
        """Floor `quantity` to the nearest valid lot, per Binance's LOT_SIZE filter."""
        step = self.lot_size_filter.step_size if self.lot_size_filter else None
        return _floor_to_step(quantity, step)

    def meets_min_notional(self, price: Decimal, quantity: Decimal) -> bool:
        if self.notional_filter is None:
            return True
        return price * quantity >= self.notional_filter.min_notional


def _floor_to_step(value: Decimal, step: Decimal | None) -> Decimal:
    if not step or step == 0:
        return value
    return (value // step) * step


@dataclass(frozen=True, slots=True)
class ExchangeInfo:
    server_time: datetime
    symbols: tuple[SymbolInfo, ...]

    def get_symbol(self, symbol: str) -> SymbolInfo | None:
        target = symbol.upper()
        return next((info for info in self.symbols if info.symbol == target), None)
