from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.user import User
from app.domain.exceptions import EntityNotFoundError


@dataclass(frozen=True, slots=True)
class AssignRoleToUserCommand:
    user_id: uuid.UUID
    role_name: str


@dataclass(frozen=True, slots=True)
class RevokeRoleFromUserCommand:
    user_id: uuid.UUID
    role_name: str


class AssignRoleToUserUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: AssignRoleToUserCommand) -> User:
        role_name = command.role_name.strip().lower()
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise EntityNotFoundError("User", command.user_id)
            if await uow.roles.get_by_name(role_name) is None:
                raise EntityNotFoundError("Role", role_name)

            user.assign_role(role_name)
            user.updated_at = datetime.now(UTC)
            await uow.users.update(user)
            await uow.commit()
        return user


class RevokeRoleFromUserUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: RevokeRoleFromUserCommand) -> User:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise EntityNotFoundError("User", command.user_id)

            user.revoke_role(command.role_name.strip().lower())
            user.updated_at = datetime.now(UTC)
            await uow.users.update(user)
            await uow.commit()
        return user
