from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Strategy


class GetStrategyUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, user_id: uuid.UUID, strategy_id: uuid.UUID) -> Strategy:
        async with self._uow_factory() as uow:
            strategy = await uow.strategies.get_by_id(strategy_id)
        # Same 404 whether the strategy doesn't exist or belongs to someone
        # else — an id that exists but isn't yours shouldn't be
        # distinguishable from one that doesn't exist at all.
        if strategy is None or strategy.user_id != user_id:
            raise EntityNotFoundError("Strategy", strategy_id)
        return strategy
