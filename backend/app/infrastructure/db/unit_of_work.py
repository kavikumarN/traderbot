"""SQLAlchemy implementation of the Unit of Work port.

One instance wraps exactly one ``AsyncSession`` / transaction. A fresh
instance is created per use-case invocation via ``SqlAlchemyUnitOfWork.factory``,
which closes over the session factory so use cases only ever see the
``UnitOfWorkFactory`` protocol (``Callable[[], UnitOfWork]``).
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.unit_of_work import UnitOfWork
from app.infrastructure.repositories.sqlalchemy_audit_log_repository import SqlAlchemyAuditLogRepository
from app.infrastructure.repositories.sqlalchemy_backtest_repository import SqlAlchemyBacktestRepository
from app.infrastructure.repositories.sqlalchemy_candle_repository import SqlAlchemyCandleRepository
from app.infrastructure.repositories.sqlalchemy_exchange_account_repository import (
    SqlAlchemyExchangeAccountRepository,
)
from app.infrastructure.repositories.sqlalchemy_market_tick_repository import SqlAlchemyMarketTickRepository
from app.infrastructure.repositories.sqlalchemy_notification_repository import (
    SqlAlchemyNotificationRepository,
)
from app.infrastructure.repositories.sqlalchemy_order_book_repository import SqlAlchemyOrderBookRepository
from app.infrastructure.repositories.sqlalchemy_order_repository import SqlAlchemyOrderRepository
from app.infrastructure.repositories.sqlalchemy_permission_repository import (
    SqlAlchemyPermissionRepository,
)
from app.infrastructure.repositories.sqlalchemy_position_repository import SqlAlchemyPositionRepository
from app.infrastructure.repositories.sqlalchemy_refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.repositories.sqlalchemy_risk_rule_repository import SqlAlchemyRiskRuleRepository
from app.infrastructure.repositories.sqlalchemy_risk_state_repository import SqlAlchemyRiskStateRepository
from app.infrastructure.repositories.sqlalchemy_role_repository import SqlAlchemyRoleRepository
from app.infrastructure.repositories.sqlalchemy_signal_repository import SqlAlchemySignalRepository
from app.infrastructure.repositories.sqlalchemy_strategy_repository import SqlAlchemyStrategyRepository
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository
from app.infrastructure.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.sqlalchemy_volume_stats_repository import (
    SqlAlchemyVolumeStatsRepository,
)
from app.infrastructure.repositories.sqlalchemy_wallet_repository import SqlAlchemyWalletRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self._session)
        self.roles = SqlAlchemyRoleRepository(self._session)
        self.permissions = SqlAlchemyPermissionRepository(self._session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(self._session)
        self.exchange_accounts = SqlAlchemyExchangeAccountRepository(self._session)
        self.wallets = SqlAlchemyWalletRepository(self._session)
        self.orders = SqlAlchemyOrderRepository(self._session)
        self.positions = SqlAlchemyPositionRepository(self._session)
        self.trades = SqlAlchemyTradeRepository(self._session)
        self.strategies = SqlAlchemyStrategyRepository(self._session)
        self.signals = SqlAlchemySignalRepository(self._session)
        self.backtests = SqlAlchemyBacktestRepository(self._session)
        self.risk_rules = SqlAlchemyRiskRuleRepository(self._session)
        self.risk_state = SqlAlchemyRiskStateRepository(self._session)
        self.notifications = SqlAlchemyNotificationRepository(self._session)
        self.candles = SqlAlchemyCandleRepository(self._session)
        self.market_ticks = SqlAlchemyMarketTickRepository(self._session)
        self.order_book = SqlAlchemyOrderBookRepository(self._session)
        self.volume_stats = SqlAlchemyVolumeStatsRepository(self._session)
        self.audit_logs = SqlAlchemyAuditLogRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()

    @classmethod
    def factory(cls, session_factory: async_sessionmaker[AsyncSession]):
        def _create() -> SqlAlchemyUnitOfWork:
            return cls(session_factory)

        return _create
