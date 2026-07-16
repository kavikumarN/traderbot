from __future__ import annotations

import uuid

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.user import User
from app.domain.exceptions import EntityNotFoundError


class GetUserUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_id: uuid.UUID) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
        if user is None:
            raise EntityNotFoundError("User", user_id)
        return user
