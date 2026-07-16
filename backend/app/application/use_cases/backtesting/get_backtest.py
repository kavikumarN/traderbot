"""Reads one backtest's full results (trade log, equity curve, summary
stats), scoped to a strategy the current user owns."""

from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Backtest


class GetBacktestUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, user_id: uuid.UUID, strategy_id: uuid.UUID, backtest_id: uuid.UUID) -> Backtest:
        async with self._uow_factory() as uow:
            strategy = await uow.strategies.get_by_id(strategy_id)
            if strategy is None or strategy.user_id != user_id:
                raise EntityNotFoundError("Strategy", strategy_id)
            backtest = await uow.backtests.get_by_id(backtest_id)
            if backtest is None or backtest.strategy_id != strategy_id:
                raise EntityNotFoundError("Backtest", backtest_id)
            return backtest
