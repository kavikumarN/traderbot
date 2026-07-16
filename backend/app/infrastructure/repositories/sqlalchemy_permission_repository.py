from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.permission import Permission
from app.domain.repositories.permission_repository import PermissionRepository
from app.infrastructure.db.models import PermissionModel


def _to_domain(model: PermissionModel) -> Permission:
    return Permission(id=model.id, code=model.code, description=model.description)


class SqlAlchemyPermissionRepository(PermissionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, permission: Permission) -> None:
        self._session.add(
            PermissionModel(
                id=permission.id, code=permission.code, description=permission.description
            )
        )
        await self._session.flush()

    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        model = await self._session.get(PermissionModel, permission_id)
        return _to_domain(model) if model else None

    async def get_by_code(self, code: str) -> Permission | None:
        stmt = select(PermissionModel).where(PermissionModel.code == code)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list(self) -> list[Permission]:
        stmt = select(PermissionModel).order_by(PermissionModel.code)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]
