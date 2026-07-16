"""Reads the current user's performance analytics — the derived equity
curve, monthly returns, Sharpe ratio, and drawdown figures."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.portfolio_service import PerformanceResult, PortfolioService
from app.domain.exchange.ports.market_data_reader import IMarketDataReader


class GetPerformanceUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        portfolio_service: PortfolioService,
        market_data: IMarketDataReader,
    ) -> None:
        self._uow_factory = uow_factory
        self._portfolio = portfolio_service
        self._market_data = market_data

    async def execute(self, *, user_id: uuid.UUID) -> PerformanceResult:
        async with self._uow_factory() as uow:
            account = await self._portfolio.active_account(uow, user_id)
            if account is None:
                return PerformanceResult()
            return await self._portfolio.get_performance(uow, account, self._market_data)
