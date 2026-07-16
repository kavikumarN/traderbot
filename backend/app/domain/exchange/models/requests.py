"""Request DTOs for the order-placing port — kept in the domain because the
"a LIMIT order needs a price" rule is a trading-domain invariant, not an
HTTP concern."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce

_PRICE_REQUIRED_TYPES = frozenset(
    {OrderType.LIMIT, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT, OrderType.LIMIT_MAKER}
)
# Binance triggers these order types once the market price crosses
# `stopPrice` — a distinct field from `price` (the limit price used only
# once triggered, for the `_LIMIT` variants). Omitting it is not a
# simplification: Binance rejects these order types outright without it.
_STOP_PRICE_REQUIRED_TYPES = frozenset(
    {OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT}
)


@dataclass(frozen=True, slots=True)
class PlaceOrderRequest:
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    # Caller-supplied idempotency key: retrying a submission with the same
    # client_order_id is safe — the exchange rejects the duplicate instead
    # of placing a second order.
    client_order_id: str | None = None

    def __post_init__(self) -> None:
        if self.type in _PRICE_REQUIRED_TYPES and self.price is None:
            raise ValueError(f"{self.type} orders require a price")
        if self.type in _STOP_PRICE_REQUIRED_TYPES and self.stop_price is None:
            raise ValueError(f"{self.type} orders require a stop_price")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
