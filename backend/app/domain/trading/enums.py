from __future__ import annotations

from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"


class PlatformOrderStatus(StrEnum):
    """The platform's own order lifecycle (see Phase 0's order-lifecycle
    state diagram) — distinct from `app.domain.exchange.enums.OrderStatus`,
    which is Binance's much narrower exchange-side vocabulary. An order
    exists in `PENDING_RISK` before it has ever touched the exchange."""

    PENDING_RISK = "PENDING_RISK"
    REJECTED = "REJECTED"
    PENDING_SUBMIT = "PENDING_SUBMIT"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SETTLED = "SETTLED"
