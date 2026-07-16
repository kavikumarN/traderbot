from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.role import Role


class ListRolesUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[Role]:
        async with self._uow_factory() as uow:
            return await uow.roles.list()
