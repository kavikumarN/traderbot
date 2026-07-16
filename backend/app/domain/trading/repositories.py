"""Repository ports for the trading bounded context.

`Wallet` and `Position` expose `upsert` rather than separate `add`/`update`:
both are naturally keyed by a stable identity (account+asset,
account+symbol) that gets refreshed wholesale every time a balance or
position update event arrives — there's no meaningful "first write" the
caller needs to distinguish from a later one.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.trading.entities import ExchangeAccount, Order, Position, Trade, Wallet


class ExchangeAccountRepository(ABC):
    @abstractmethod
    async def add(self, account: ExchangeAccount) -> None: ...

    @abstractmethod
    async def get_by_id(self, account_id: uuid.UUID) -> ExchangeAccount | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> list[ExchangeAccount]: ...

    @abstractmethod
    async def update(self, account: ExchangeAccount) -> None: ...


class WalletRepository(ABC):
    @abstractmethod
    async def upsert(self, wallet: Wallet) -> None: ...

    @abstractmethod
    async def get(self, exchange_account_id: uuid.UUID, asset: str) -> Wallet | None: ...

    @abstractmethod
    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Wallet]: ...


class OrderRepository(ABC):
    @abstractmethod
    async def add(self, order: Order) -> None: ...

    @abstractmethod
    async def get_by_id(self, order_id: uuid.UUID) -> Order | None: ...

    @abstractmethod
    async def get_by_client_order_id(self, client_order_id: str) -> Order | None: ...

    @abstractmethod
    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Order]: ...

    @abstractmethod
    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Order]: ...

    @abstractmethod
    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Order]:
        """Full order history (every status), newest first — distinct from
        `list_open_for_account`, which exists for the trading engine's own
        polling/reconciliation loop rather than a user-facing history view."""
        ...

    @abstractmethod
    async def update(self, order: Order) -> None: ...


class PositionRepository(ABC):
    @abstractmethod
    async def upsert(self, position: Position) -> None: ...

    @abstractmethod
    async def get(self, exchange_account_id: uuid.UUID, symbol: str) -> Position | None: ...

    @abstractmethod
    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]: ...

    @abstractmethod
    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]:
        """Every position for this account, open and closed — distinct from
        `list_open_for_account`, which the trading/risk engines use for
        live exposure and would silently drop symbols that are fully
        closed (their lifetime `realized_pnl` still matters for portfolio
        totals)."""
        ...


class TradeRepository(ABC):
    @abstractmethod
    async def add(self, trade: Trade) -> None: ...

    @abstractmethod
    async def list_for_order(self, order_id: uuid.UUID) -> list[Trade]: ...

    @abstractmethod
    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Trade]: ...

    @abstractmethod
    async def list_all_for_account(self, exchange_account_id: uuid.UUID) -> list[Trade]:
        """Every trade for this account, oldest first, unpaginated — for
        portfolio analytics (equity-curve replay), not the user-facing
        paginated history `list_for_account` serves."""
        ...
