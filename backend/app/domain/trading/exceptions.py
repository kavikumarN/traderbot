"""Trading-domain exceptions.

Distinct from `app.domain.exchange.exceptions` (the exchange integration's
own hierarchy, translated from Binance's wire errors) — these describe
failures the *platform* itself decides, before or independent of ever
reaching the exchange: an account that isn't tradeable, a simulated fill
that can't be funded, an order the exchange refused. All subclass the
shared `DomainError` so the existing HTTP exception-handler pipeline
(`app.interface.api.errors`) picks them up automatically.
"""

from __future__ import annotations

import uuid

from app.domain.exceptions import DomainError


class AccountNotActiveError(DomainError):
    """An order was attempted against an exchange account that is disabled
    or revoked (see `app.domain.trading.enums.AccountStatus`)."""

    def __init__(self, account_id: uuid.UUID) -> None:
        self.account_id = account_id
        super().__init__(f"Exchange account {account_id} is not active")


class OrderRejectedError(DomainError):
    """The exchange (or, in paper mode, the simulator) refused an order."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Order rejected: {reason}")


class InsufficientBalanceError(DomainError):
    """Not enough free balance to place or simulate-fill an order."""

    def __init__(self, asset: str) -> None:
        self.asset = asset
        super().__init__(f"Insufficient {asset} balance")


class OrderNotCancelableError(DomainError):
    """A cancel was requested for an order already in a terminal state."""

    def __init__(self, order_id: uuid.UUID, status: str) -> None:
        self.order_id = order_id
        self.status = status
        super().__init__(f"Order {order_id} is already {status} and cannot be cancelled")
