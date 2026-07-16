"""Unit of Work port.

Bundles one transactional scope with the repositories that participate in
it, so a use case that touches two aggregates (e.g. creating a user and
recording an audit-worthy event) commits or rolls back atomically. Used as
an async context manager:

    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Protocol, Self

from app.domain.audit.repositories import AuditLogRepository
from app.domain.marketdata.repositories import (
    CandleRepository,
    MarketTickRepository,
    OrderBookRepository,
    VolumeStatsRepository,
)
from app.domain.notification.repositories import NotificationRepository
from app.domain.repositories.permission_repository import PermissionRepository
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.role_repository import RoleRepository
from app.domain.repositories.user_repository import UserRepository
from app.domain.risk.repositories import RiskRuleRepository, RiskStateRepository
from app.domain.strategy.repositories import BacktestRepository, SignalRepository, StrategyRepository
from app.domain.trading.repositories import (
    ExchangeAccountRepository,
    OrderRepository,
    PositionRepository,
    TradeRepository,
    WalletRepository,
)


class UnitOfWork(ABC):
    users: UserRepository
    roles: RoleRepository
    permissions: PermissionRepository
    refresh_tokens: RefreshTokenRepository
    exchange_accounts: ExchangeAccountRepository
    wallets: WalletRepository
    orders: OrderRepository
    positions: PositionRepository
    trades: TradeRepository
    strategies: StrategyRepository
    signals: SignalRepository
    backtests: BacktestRepository
    risk_rules: RiskRuleRepository
    risk_state: RiskStateRepository
    notifications: NotificationRepository
    candles: CandleRepository
    market_ticks: MarketTickRepository
    order_book: OrderBookRepository
    volume_stats: VolumeStatsRepository
    audit_logs: AuditLogRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Commits are always explicit (``await uow.commit()``). On exception,
        # or if the caller simply forgot to commit, roll back so nothing
        # partial is ever persisted.
        if exc is not None:
            await self.rollback()

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
