from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.refresh_token import RefreshToken
from app.domain.exceptions import EntityNotFoundError
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.db.models import RefreshTokenModel


def _to_domain(model: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        replaced_by_token_id=model.replaced_by_token_id,
        user_agent=model.user_agent,
        ip_address=model.ip_address,
    )


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> None:
        self._session.add(
            RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                issued_at=token.issued_at,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                replaced_by_token_id=token.replaced_by_token_id,
                user_agent=token.user_agent,
                ip_address=token.ip_address,
            )
        )
        await self._session.flush()

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def update(self, token: RefreshToken) -> None:
        model = await self._session.get(RefreshTokenModel, token.id)
        if model is None:
            raise EntityNotFoundError("RefreshToken", token.id)

        model.revoked_at = token.revoked_at
        model.replaced_by_token_id = token.replaced_by_token_id
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, revoked_at: datetime) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(stmt)
        await self._session.flush()
