"""In-memory repository fakes.

These implement the same ports (``app.domain.repositories.*``) as the
SQLAlchemy repositories, so application-layer use cases can be exercised as
true unit tests — no database, no event loop surprises, no fixtures beyond
plain Python objects.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.domain.audit.entities import AuditLog
from app.domain.audit.repositories import AuditLogRepository
from app.domain.entities.permission import Permission
from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.role import Role
from app.domain.entities.user import User
from app.domain.exceptions import EntityNotFoundError
from app.domain.exchange.enums import KlineInterval
from app.domain.marketdata.entities import PersistedCandle
from app.domain.marketdata.repositories import CandleRepository
from app.domain.repositories.permission_repository import PermissionRepository
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.role_repository import RoleRepository
from app.domain.repositories.user_repository import UserRepository
from app.domain.risk.entities import RiskRule, RiskState
from app.domain.risk.repositories import RiskRuleRepository, RiskStateRepository
from app.domain.strategy.entities import Backtest, Signal, Strategy
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.repositories import BacktestRepository, SignalRepository, StrategyRepository
from app.domain.trading.entities import ExchangeAccount, Order, Position, Trade, Wallet
from app.domain.trading.repositories import (
    ExchangeAccountRepository,
    OrderRepository,
    PositionRepository,
    TradeRepository,
    WalletRepository,
)

_ACTIVE_STRATEGY_STATUSES = (StrategyStatus.LIVE, StrategyStatus.PAPER_TRADING)


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        for user in self._by_id.values():
            if str(user.email) == email:
                return user
        return None

    async def list(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        users = sorted(self._by_id.values(), key=lambda u: u.created_at)
        return users[offset : offset + limit]

    async def count(self) -> int:
        return len(self._by_id)

    async def update(self, user: User) -> None:
        self._by_id[user.id] = user


class FakeRoleRepository(RoleRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Role] = {}

    async def add(self, role: Role) -> None:
        self._by_id[role.id] = role

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        return self._by_id.get(role_id)

    async def get_by_name(self, name: str) -> Role | None:
        for role in self._by_id.values():
            if role.name == name:
                return role
        return None

    async def list(self) -> list[Role]:
        return sorted(self._by_id.values(), key=lambda r: r.name)

    async def update(self, role: Role) -> None:
        self._by_id[role.id] = role

    async def get_permission_codes_for_roles(self, role_names: set[str]) -> set[str]:
        codes: set[str] = set()
        for role in self._by_id.values():
            if role.name in role_names:
                codes |= role.permission_codes
        return codes


class FakePermissionRepository(PermissionRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Permission] = {}

    async def add(self, permission: Permission) -> None:
        self._by_id[permission.id] = permission

    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        return self._by_id.get(permission_id)

    async def get_by_code(self, code: str) -> Permission | None:
        for permission in self._by_id.values():
            if permission.code == code:
                return permission
        return None

    async def list(self) -> list[Permission]:
        return sorted(self._by_id.values(), key=lambda p: p.code)


class FakeRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> None:
        self._by_id[token.id] = token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._by_id.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def update(self, token: RefreshToken) -> None:
        self._by_id[token.id] = token

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, revoked_at: datetime) -> None:
        for token in self._by_id.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = revoked_at


class FakeExchangeAccountRepository(ExchangeAccountRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, ExchangeAccount] = {}

    async def add(self, account: ExchangeAccount) -> None:
        self._by_id[account.id] = account

    async def get_by_id(self, account_id: uuid.UUID) -> ExchangeAccount | None:
        return self._by_id.get(account_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[ExchangeAccount]:
        return [a for a in self._by_id.values() if a.user_id == user_id]

    async def update(self, account: ExchangeAccount) -> None:
        self._by_id[account.id] = account


class FakeWalletRepository(WalletRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[uuid.UUID, str], Wallet] = {}

    async def upsert(self, wallet: Wallet) -> None:
        self._by_key[(wallet.exchange_account_id, wallet.asset)] = wallet

    async def get(self, exchange_account_id: uuid.UUID, asset: str) -> Wallet | None:
        return self._by_key.get((exchange_account_id, asset))

    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Wallet]:
        return sorted(
            (w for (account_id, _asset), w in self._by_key.items() if account_id == exchange_account_id),
            key=lambda w: w.asset,
        )


class FakeOrderRepository(OrderRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Order] = {}

    async def add(self, order: Order) -> None:
        self._by_id[order.id] = order

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        return self._by_id.get(order_id)

    async def get_by_client_order_id(self, client_order_id: str) -> Order | None:
        for order in self._by_id.values():
            if order.client_order_id == client_order_id:
                return order
        return None

    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Order]:
        return [
            order
            for order in self._by_id.values()
            if order.exchange_account_id == exchange_account_id and not order.is_terminal
        ]

    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Order]:
        return [order for order in self._by_id.values() if order.strategy_id == strategy_id]

    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Order]:
        orders = sorted(
            (o for o in self._by_id.values() if o.exchange_account_id == exchange_account_id),
            key=lambda o: o.created_at,
            reverse=True,
        )
        return orders[offset : offset + limit]

    async def update(self, order: Order) -> None:
        self._by_id[order.id] = order


class FakePositionRepository(PositionRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[uuid.UUID, str], Position] = {}

    async def upsert(self, position: Position) -> None:
        self._by_key[(position.exchange_account_id, position.symbol)] = position

    async def get(self, exchange_account_id: uuid.UUID, symbol: str) -> Position | None:
        return self._by_key.get((exchange_account_id, symbol))

    async def list_open_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]:
        return [
            p
            for (account_id, _symbol), p in self._by_key.items()
            if account_id == exchange_account_id and p.closed_at is None
        ]

    async def list_for_account(self, exchange_account_id: uuid.UUID) -> list[Position]:
        return [p for (account_id, _symbol), p in self._by_key.items() if account_id == exchange_account_id]


class FakeTradeRepository(TradeRepository):
    def __init__(self) -> None:
        self._items: list[Trade] = []

    async def add(self, trade: Trade) -> None:
        self._items.append(trade)

    async def list_for_order(self, order_id: uuid.UUID) -> list[Trade]:
        return [t for t in self._items if t.order_id == order_id]

    async def list_for_account(
        self, exchange_account_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Trade]:
        trades = sorted(
            (t for t in self._items if t.exchange_account_id == exchange_account_id),
            key=lambda t: t.executed_at,
            reverse=True,
        )
        return trades[offset : offset + limit]

    async def list_all_for_account(self, exchange_account_id: uuid.UUID) -> list[Trade]:
        return sorted(
            (t for t in self._items if t.exchange_account_id == exchange_account_id),
            key=lambda t: t.executed_at,
        )


class FakeAuditLogRepository(AuditLogRepository):
    def __init__(self) -> None:
        self._items: list[AuditLog] = []

    async def add(self, entry: AuditLog) -> None:
        self._items.append(entry)

    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[AuditLog]:
        return [
            e for e in self._items if e.entity_type == entity_type and e.entity_id == entity_id
        ]

    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        entries = sorted(self._items, key=lambda e: e.occurred_at, reverse=True)
        return entries[offset : offset + limit]


class FakeStrategyRepository(StrategyRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Strategy] = {}

    async def add(self, strategy: Strategy) -> None:
        self._by_id[strategy.id] = strategy

    async def get_by_id(self, strategy_id: uuid.UUID) -> Strategy | None:
        return self._by_id.get(strategy_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Strategy]:
        return [s for s in self._by_id.values() if s.user_id == user_id]

    async def list_active(self) -> list[Strategy]:
        return [s for s in self._by_id.values() if s.status in _ACTIVE_STRATEGY_STATUSES]

    async def update(self, strategy: Strategy) -> None:
        self._by_id[strategy.id] = strategy


class FakeRiskRuleRepository(RiskRuleRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, RiskRule] = {}

    async def add(self, rule: RiskRule) -> None:
        self._by_id[rule.id] = rule

    async def get_by_id(self, rule_id: uuid.UUID) -> RiskRule | None:
        return self._by_id.get(rule_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[RiskRule]:
        return [r for r in self._by_id.values() if r.user_id == user_id]

    async def list_active_for_strategy(self, strategy_id: uuid.UUID) -> list[RiskRule]:
        return [r for r in self._by_id.values() if r.applies_to(strategy_id)]

    async def update(self, rule: RiskRule) -> None:
        self._by_id[rule.id] = rule

    async def delete(self, rule_id: uuid.UUID) -> None:
        if rule_id not in self._by_id:
            raise EntityNotFoundError("RiskRule", rule_id)
        del self._by_id[rule_id]


class FakeRiskStateRepository(RiskStateRepository):
    def __init__(self) -> None:
        self._by_user_id: dict[uuid.UUID, RiskState] = {}

    async def get_for_user(self, user_id: uuid.UUID) -> RiskState | None:
        return self._by_user_id.get(user_id)

    async def upsert(self, state: RiskState) -> None:
        self._by_user_id[state.user_id] = state


class FakeSignalRepository(SignalRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Signal] = {}

    async def add(self, signal: Signal) -> None:
        self._by_id[signal.id] = signal

    async def get_by_id(self, signal_id: uuid.UUID) -> Signal | None:
        return self._by_id.get(signal_id)

    async def list_for_strategy(
        self, strategy_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Signal]:
        signals = sorted(
            (s for s in self._by_id.values() if s.strategy_id == strategy_id),
            key=lambda s: s.generated_at,
            reverse=True,
        )
        return signals[offset : offset + limit]

    async def update(self, signal: Signal) -> None:
        self._by_id[signal.id] = signal


class FakeCandleRepository(CandleRepository):
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, KlineInterval, datetime], PersistedCandle] = {}

    async def upsert(self, candle: PersistedCandle) -> None:
        self._by_key[(candle.symbol, candle.interval, candle.open_time)] = candle

    async def upsert_many(self, candles: list[PersistedCandle]) -> None:
        for candle in candles:
            await self.upsert(candle)

    async def list_range(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        candles = [
            c
            for c in self._by_key.values()
            if c.symbol == symbol and c.interval == interval and start <= c.open_time <= end
        ]
        return sorted(candles, key=lambda c: c.open_time)

    async def get_latest(self, symbol: str, interval: KlineInterval) -> PersistedCandle | None:
        candles = [c for c in self._by_key.values() if c.symbol == symbol and c.interval == interval]
        return max(candles, key=lambda c: c.open_time) if candles else None


class FakeBacktestRepository(BacktestRepository):
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Backtest] = {}

    async def add(self, backtest: Backtest) -> None:
        self._by_id[backtest.id] = backtest

    async def get_by_id(self, backtest_id: uuid.UUID) -> Backtest | None:
        return self._by_id.get(backtest_id)

    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Backtest]:
        return [b for b in self._by_id.values() if b.strategy_id == strategy_id]

    async def update(self, backtest: Backtest) -> None:
        self._by_id[backtest.id] = backtest
