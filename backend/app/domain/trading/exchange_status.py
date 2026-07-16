"""Translates Binance's own order-status vocabulary
(`app.domain.exchange.enums.OrderStatus`) into this platform's order
lifecycle (`app.domain.trading.enums.PlatformOrderStatus`).

The two enums look similar but aren't interchangeable: the platform has
states the exchange has no concept of (`PENDING_RISK`, `PENDING_SUBMIT`,
`SETTLED` — all before/after the exchange is involved at all), and even
the shared states don't share spelling (`CANCELED` vs `CANCELLED`). This
mapping is pure and total — every `OrderStatus` member has exactly one
`PlatformOrderStatus` it becomes — so it belongs in the domain layer, not
scattered across the infrastructure code that happens to call it.
"""

from __future__ import annotations

from app.domain.exchange.enums import OrderStatus
from app.domain.trading.enums import PlatformOrderStatus

_EXCHANGE_TO_PLATFORM: dict[OrderStatus, PlatformOrderStatus] = {
    # Acknowledged and resting on the exchange's book — this platform
    # calls that "submitted" regardless of whether it's brand new.
    OrderStatus.NEW: PlatformOrderStatus.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: PlatformOrderStatus.PARTIALLY_FILLED,
    OrderStatus.FILLED: PlatformOrderStatus.FILLED,
    OrderStatus.CANCELED: PlatformOrderStatus.CANCELLED,
    # A cancel request has been accepted but not yet confirmed executed —
    # the order is still live until told otherwise, so it stays SUBMITTED
    # rather than jumping the gun on CANCELLED.
    OrderStatus.PENDING_CANCEL: PlatformOrderStatus.SUBMITTED,
    OrderStatus.REJECTED: PlatformOrderStatus.REJECTED,
    OrderStatus.EXPIRED: PlatformOrderStatus.EXPIRED,
}


def to_platform_status(status: OrderStatus) -> PlatformOrderStatus:
    return _EXCHANGE_TO_PLATFORM[status]
