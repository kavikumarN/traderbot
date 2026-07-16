"""Reads the current user's trade history (executions/fills), paginated,
newest first — the Portfolio page's Trade History tab."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.portfolio_service import PortfolioService
from app.domain.trading.entities import Trade


class ListTradeHistoryUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, portfolio_service: PortfolioService) -> None:
        self._uow_factory = uow_factory
        self._portfolio = portfolio_service

    async def execute(self, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Trade]:
        async with self._uow_factory() as uow:
            account = await self._portfolio.active_account(uow, user_id)
            if account is None:
                return []
            return await self._portfolio.get_trade_history(uow, account, limit=limit, offset=offset)
