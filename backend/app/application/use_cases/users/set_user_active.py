from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.user import User
from app.domain.exceptions import EntityNotFoundError


@dataclass(frozen=True, slots=True)
class SetUserActiveCommand:
    user_id: uuid.UUID
    is_active: bool


class SetUserActiveUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: SetUserActiveCommand) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise EntityNotFoundError("User", command.user_id)

            if command.is_active:
                user.activate()
            else:
                user.deactivate()
            user.updated_at = datetime.now(UTC)

            await uow.users.update(user)
            await uow.commit()
        return user
