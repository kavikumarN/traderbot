from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from tests.fakes.fake_repositories import (
    FakeAuditLogRepository,
    FakeBacktestRepository,
    FakeCandleRepository,
    FakeExchangeAccountRepository,
    FakeOrderRepository,
    FakePermissionRepository,
    FakePositionRepository,
    FakeRefreshTokenRepository,
    FakeRiskRuleRepository,
    FakeRiskStateRepository,
    FakeRoleRepository,
    FakeSignalRepository,
    FakeStrategyRepository,
    FakeTradeRepository,
    FakeUserRepository,
    FakeWalletRepository,
)


class FakeUnitOfWork(UnitOfWork):
    """A single in-memory 'transaction' shared across repositories.

    Unlike the real SQLAlchemy UoW, state here isn't actually rolled back on
    ``rollback()`` — tests that need to assert atomicity belong at the
    infrastructure/integration level, not here. This fake exists purely to
    let use cases run against something that satisfies the port.
    """

    def __init__(
        self,
        users: FakeUserRepository | None = None,
        roles: FakeRoleRepository | None = None,
        permissions: FakePermissionRepository | None = None,
        refresh_tokens: FakeRefreshTokenRepository | None = None,
        exchange_accounts: FakeExchangeAccountRepository | None = None,
        wallets: FakeWalletRepository | None = None,
        orders: FakeOrderRepository | None = None,
        positions: FakePositionRepository | None = None,
        trades: FakeTradeRepository | None = None,
        audit_logs: FakeAuditLogRepository | None = None,
        strategies: FakeStrategyRepository | None = None,
        signals: FakeSignalRepository | None = None,
        risk_rules: FakeRiskRuleRepository | None = None,
        risk_state: FakeRiskStateRepository | None = None,
        candles: FakeCandleRepository | None = None,
        backtests: FakeBacktestRepository | None = None,
    ) -> None:
        self.users = users or FakeUserRepository()
        self.roles = roles or FakeRoleRepository()
        self.permissions = permissions or FakePermissionRepository()
        self.refresh_tokens = refresh_tokens or FakeRefreshTokenRepository()
        self.exchange_accounts = exchange_accounts or FakeExchangeAccountRepository()
        self.wallets = wallets or FakeWalletRepository()
        self.orders = orders or FakeOrderRepository()
        self.positions = positions or FakePositionRepository()
        self.trades = trades or FakeTradeRepository()
        self.audit_logs = audit_logs or FakeAuditLogRepository()
        self.strategies = strategies or FakeStrategyRepository()
        self.signals = signals or FakeSignalRepository()
        self.risk_rules = risk_rules or FakeRiskRuleRepository()
        self.risk_state = risk_state or FakeRiskStateRepository()
        self.candles = candles or FakeCandleRepository()
        self.backtests = backtests or FakeBacktestRepository()
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def make_uow_factory(uow: FakeUnitOfWork) -> UnitOfWorkFactory:
    """Every call returns the *same* fake UoW, so state persists across
    the multiple ``async with uow_factory() as uow`` blocks a use case
    (or a sequence of use cases in one test) may open."""

    def _factory() -> FakeUnitOfWork:
        return uow

    return _factory
