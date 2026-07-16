"""Redeem a refresh token for a new access/refresh token pair.

Refresh tokens rotate on every use: the presented token is revoked and a
new one is issued in the same transaction. If a token that was *already*
revoked is presented again, that's a strong signal it was stolen and used
by two parties — every refresh token for that user is revoked defensively
and the caller is forced to log in again.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.ports.token_service import TokenService
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.refresh_token import RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidTokenError, TokenRevokedError


@dataclass(frozen=True, slots=True)
class RefreshAccessTokenCommand:
    raw_refresh_token: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshAccessTokenResult:
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime


class RefreshAccessTokenUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, token_service: TokenService) -> None:
        self._uow_factory = uow_factory
        self._token_service = token_service

    async def execute(self, command: RefreshAccessTokenCommand) -> RefreshAccessTokenResult:
        token_hash = self._token_service.hash_refresh_token(command.raw_refresh_token)
        now = datetime.now(UTC)

        async with self._uow_factory() as uow:
            existing = await uow.refresh_tokens.get_by_hash(token_hash)
            if existing is None:
                raise InvalidTokenError("Unknown refresh token")

            if existing.is_revoked():
                await uow.refresh_tokens.revoke_all_for_user(existing.user_id, revoked_at=now)
                await uow.commit()
                raise TokenRevokedError()

            if existing.is_expired(now):
                raise InvalidTokenError("Refresh token expired")

            user = await uow.users.get_by_id(existing.user_id)
            if user is None or not user.is_active:
                raise InactiveUserError()

            new_raw_token = self._token_service.generate_refresh_token()
            new_expires_at = now + timedelta(
                seconds=self._token_service.refresh_token_ttl_seconds()
            )
            new_entity = RefreshToken(
                id=uuid.uuid4(),
                user_id=user.id,
                token_hash=self._token_service.hash_refresh_token(new_raw_token),
                issued_at=now,
                expires_at=new_expires_at,
                user_agent=command.user_agent,
                ip_address=command.ip_address,
            )
            await uow.refresh_tokens.add(new_entity)

            existing.revoke(now, replaced_by=new_entity.id)
            await uow.refresh_tokens.update(existing)

            issued = self._token_service.create_access_token(
                user_id=user.id, email=str(user.email), role_names=user.role_names
            )
            await uow.commit()

        return RefreshAccessTokenResult(
            access_token=issued.token,
            access_token_expires_at=issued.payload.expires_at,
            refresh_token=new_raw_token,
            refresh_token_expires_at=new_expires_at,
        )
