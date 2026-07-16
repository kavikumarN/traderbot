from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories.user_repository import UserRepository
from app.domain.value_objects.email import Email
from app.infrastructure.db.models import RoleModel, UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=Email(model.email),
        hashed_password=model.hashed_password,
        first_name=model.first_name,
        last_name=model.last_name,
        is_active=model.is_active,
        is_verified=model.is_verified,
        created_at=model.created_at,
        updated_at=model.updated_at,
        role_names={role.name for role in model.roles},
    )


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            email=str(user.email),
            hashed_password=user.hashed_password,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=await self._role_models_for_names(user.role_names),
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        stmt = (
            select(UserModel)
            .order_by(UserModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def count(self) -> int:
        stmt = select(func.count()).select_from(UserModel)
        return (await self._session.execute(stmt)).scalar_one()

    async def update(self, user: User) -> None:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise EntityNotFoundError("User", user.id)

        model.hashed_password = user.hashed_password
        model.first_name = user.first_name
        model.last_name = user.last_name
        model.is_active = user.is_active
        model.is_verified = user.is_verified
        model.updated_at = user.updated_at
        model.roles = await self._role_models_for_names(user.role_names)
        await self._session.flush()

    async def _role_models_for_names(self, role_names: set[str]) -> list[RoleModel]:
        if not role_names:
            return []
        stmt = select(RoleModel).where(RoleModel.name.in_(role_names))
        return list((await self._session.execute(stmt)).scalars().all())
