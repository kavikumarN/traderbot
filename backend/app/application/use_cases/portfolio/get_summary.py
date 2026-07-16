"""Reads the current user's portfolio summary — cash, positions value,
equity, realized/unrealized pnl, ROI, and per-asset fees — the headline
numbers for the Portfolio Overview page."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.portfolio_service import PortfolioService, PortfolioSummary
from app.domain.exchange.ports.market_data_reader import IMarketDataReader

_EMPTY_SUMMARY = PortfolioSummary(
    cash=Decimal(0),
    positions_value=Decimal(0),
    equity=Decimal(0),
    realized_pnl=Decimal(0),
    unrealized_pnl=Decimal(0),
    total_pnl=Decimal(0),
    roi_pct=None,
    fees_by_asset={},
    open_position_count=0,
    total_trade_count=0,
)


class GetPortfolioSummaryUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        portfolio_service: PortfolioService,
        market_data: IMarketDataReader,
    ) -> None:
        self._uow_factory = uow_factory
        self._portfolio = portfolio_service
        self._market_data = market_data

    async def execute(self, *, user_id: uuid.UUID) -> PortfolioSummary:
        async with self._uow_factory() as uow:
            account = await self._portfolio.active_account(uow, user_id)
            if account is None:
                return _EMPTY_SUMMARY
            return await self._portfolio.get_summary(uow, account, self._market_data)
