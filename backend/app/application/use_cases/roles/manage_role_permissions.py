from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.role import Role
from app.domain.exceptions import EntityNotFoundError


@dataclass(frozen=True, slots=True)
class GrantPermissionCommand:
    role_id: uuid.UUID
    permission_code: str


@dataclass(frozen=True, slots=True)
class RevokePermissionCommand:
    role_id: uuid.UUID
    permission_code: str


class GrantPermissionUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: GrantPermissionCommand) -> Role:
        async with self._uow_factory() as uow:
            role = await uow.roles.get_by_id(command.role_id)
            if role is None:
                raise EntityNotFoundError("Role", command.role_id)
            if await uow.permissions.get_by_code(command.permission_code) is None:
                raise EntityNotFoundError("Permission", command.permission_code)

            role.grant(command.permission_code)
            await uow.roles.update(role)
            await uow.commit()
        return role


class RevokePermissionUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: RevokePermissionCommand) -> Role:
        async with self._uow_factory() as uow:
            role = await uow.roles.get_by_id(command.role_id)
            if role is None:
                raise EntityNotFoundError("Role", command.role_id)

            role.revoke(command.permission_code)
            await uow.roles.update(role)
            await uow.commit()
        return role
