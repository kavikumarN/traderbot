"""Trading bounded context: the platform's own account, ledger, and order
records — as distinct from `app.domain.exchange`, which models Binance's
API surface. `Order` here is what the platform decided to do; the eventual
`ExchangeOrder` (Phase 3) is what Binance says actually happened. A future
execution-service reconciles the two.

`OrderSide` / `OrderType` / `TimeInForce` are imported from the exchange
context rather than redefined — "an order has a side" is a universal
trading concept, not something specific to talking to Binance, so treating
it as a shared kernel avoids two enums meaning the same thing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.trading.enums import AccountStatus, PlatformOrderStatus

_TERMINAL_ORDER_STATUSES = frozenset(
    {
        PlatformOrderStatus.FILLED,
        PlatformOrderStatus.REJECTED,
        PlatformOrderStatus.CANCELLED,
        PlatformOrderStatus.EXPIRED,
        PlatformOrderStatus.SETTLED,
    }
)


@dataclass(slots=True)
class ExchangeAccount:
    id: uuid.UUID
    user_id: uuid.UUID
    exchange: str
    label: str
    api_key_ciphertext: str
    api_key_last_four: str
    is_testnet: bool
    status: AccountStatus
    created_at: datetime
    updated_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status == AccountStatus.ACTIVE

    def disable(self) -> None:
        self.status = AccountStatus.DISABLED

    def revoke(self) -> None:
        self.status = AccountStatus.REVOKED


@dataclass(slots=True)
class Wallet:
    id: uuid.UUID
    exchange_account_id: uuid.UUID
    asset: str
    free: Decimal
    locked: Decimal
    updated_at: datetime

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass(slots=True)
class Order:
    id: uuid.UUID
    exchange_account_id: uuid.UUID
    symbol: str
    side: OrderSide
    type: OrderType
    status: PlatformOrderStatus
    quantity: Decimal
    executed_quantity: Decimal
    cumulative_quote_quantity: Decimal
    client_order_id: str
    created_at: datetime
    updated_at: datetime
    strategy_id: uuid.UUID | None = None
    signal_id: uuid.UUID | None = None
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    exchange_order_id: int | None = None
    rejection_reason: str | None = None
    submitted_at: datetime | None = None
    filled_at: datetime | None = None

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.executed_quantity

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_ORDER_STATUSES


@dataclass(slots=True)
class Position:
    id: uuid.UUID
    exchange_account_id: uuid.UUID
    symbol: str
    quantity: Decimal
    avg_entry_price: Decimal
    realized_pnl: Decimal
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None


@dataclass(slots=True)
class Trade:
    """A single execution ("fill") against an order. One order can produce
    many trades (partial fills); `trade_history` is this platform's durable
    record of them, keyed by Binance's own trade id for idempotent ingestion."""

    id: uuid.UUID
    order_id: uuid.UUID
    exchange_account_id: uuid.UUID
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    commission: Decimal
    exchange_trade_id: int
    executed_at: datetime
    commission_asset: str | None = None
