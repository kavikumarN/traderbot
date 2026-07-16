from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.strategy.entities import Strategy


class ListStrategiesUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, user_id: uuid.UUID) -> list[Strategy]:
        async with self._uow_factory() as uow:
            return await uow.strategies.list_for_user(user_id)
