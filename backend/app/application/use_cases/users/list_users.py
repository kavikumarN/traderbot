from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.user import User


@dataclass(frozen=True, slots=True)
class ListUsersQuery:
    offset: int = 0
    limit: int = 50


class ListUsersUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListUsersQuery) -> tuple[list[User], int]:
        async with self._uow_factory() as uow:
            users = await uow.users.list(offset=query.offset, limit=query.limit)
            total = await uow.users.count()
        return users, total
