from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.exceptions import EntityNotFoundError
from app.domain.strategy.entities import Signal


class ListSignalsUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, *, user_id: uuid.UUID, strategy_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[Signal]:
        async with self._uow_factory() as uow:
            strategy = await uow.strategies.get_by_id(strategy_id)
            if strategy is None or strategy.user_id != user_id:
                raise EntityNotFoundError("Strategy", strategy_id)
            return await uow.signals.list_for_strategy(strategy_id, limit=limit, offset=offset)
