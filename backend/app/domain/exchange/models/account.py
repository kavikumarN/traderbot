"""Account-side models — require a signed request to obtain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import OrderSide, OrderStatus, OrderType, TimeInForce


@dataclass(frozen=True, slots=True)
class AssetBalance:
    asset: str
    free: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass(frozen=True, slots=True)
class ExchangeOrder:
    """The exchange's own view of an order — distinct from (and mapped
    into, by a future execution-service) this platform's own ``Order``
    aggregate. Keeping them separate is the anti-corruption layer: exchange
    vocabulary never leaks past this integration."""

    symbol: str
    exchange_order_id: int
    client_order_id: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    time_in_force: TimeInForce | None
    price: Decimal
    original_quantity: Decimal
    executed_quantity: Decimal
    cumulative_quote_quantity: Decimal
    created_at: datetime
    updated_at: datetime
    stop_price: Decimal | None = None

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        )

    @property
    def remaining_quantity(self) -> Decimal:
        return self.original_quantity - self.executed_quantity
