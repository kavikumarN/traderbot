from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.role import Role
from app.domain.exceptions import EntityAlreadyExistsError


@dataclass(frozen=True, slots=True)
class CreateRoleCommand:
    name: str
    description: str


class CreateRoleUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: CreateRoleCommand) -> Role:
        name = command.name.strip().lower()
        async with self._uow_factory() as uow:
            if await uow.roles.get_by_name(name) is not None:
                raise EntityAlreadyExistsError("Role", "name", name)

            role = Role(id=uuid.uuid4(), name=name, description=command.description.strip())
            await uow.roles.add(role)
            await uow.commit()
        return role
