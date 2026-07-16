from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.role import Role
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories.role_repository import RoleRepository
from app.infrastructure.db.models import PermissionModel, RoleModel


def _to_domain(model: RoleModel) -> Role:
    return Role(
        id=model.id,
        name=model.name,
        description=model.description,
        permission_codes={permission.code for permission in model.permissions},
    )


class SqlAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, role: Role) -> None:
        model = RoleModel(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=await self._permission_models_for_codes(role.permission_codes),
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        model = await self._session.get(RoleModel, role_id)
        return _to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(RoleModel).where(RoleModel.name == name)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list(self) -> list[Role]:
        stmt = select(RoleModel).order_by(RoleModel.name)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def update(self, role: Role) -> None:
        model = await self._session.get(RoleModel, role.id)
        if model is None:
            raise EntityNotFoundError("Role", role.id)

        model.description = role.description
        model.permissions = await self._permission_models_for_codes(role.permission_codes)
        await self._session.flush()

    async def get_permission_codes_for_roles(self, role_names: set[str]) -> set[str]:
        if not role_names:
            return set()
        stmt = (
            select(PermissionModel.code)
            .join(PermissionModel.roles)
            .where(RoleModel.name.in_(role_names))
            .distinct()
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return set(rows)

    async def _permission_models_for_codes(self, codes: set[str]) -> list[PermissionModel]:
        if not codes:
            return []
        stmt = select(PermissionModel).where(PermissionModel.code.in_(codes))
        return list((await self._session.execute(stmt)).scalars().all())
