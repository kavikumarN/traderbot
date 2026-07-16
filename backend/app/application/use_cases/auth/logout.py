"""Log out: revoke the refresh token and blacklist the current access token.

The refresh token revocation is durable (Postgres); the access token
blacklist entry only needs to live as long as the access token would have
been valid anyway, so it's cheap to keep in Redis (see
``app.application.ports.token_blacklist``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.ports.token_blacklist import TokenBlacklist
from app.application.ports.token_service import TokenService
from app.application.ports.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    raw_refresh_token: str
    access_token_jti: str
    access_token_expires_at: datetime


class LogoutUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        token_service: TokenService,
        token_blacklist: TokenBlacklist,
    ) -> None:
        self._uow_factory = uow_factory
        self._token_service = token_service
        self._token_blacklist = token_blacklist

    async def execute(self, command: LogoutCommand) -> None:
        token_hash = self._token_service.hash_refresh_token(command.raw_refresh_token)

        async with self._uow_factory() as uow:
            existing = await uow.refresh_tokens.get_by_hash(token_hash)
            if existing is not None and not existing.is_revoked():
                existing.revoke(datetime.now(UTC))
                await uow.refresh_tokens.update(existing)
                await uow.commit()

        await self._token_blacklist.blacklist(
            command.access_token_jti, command.access_token_expires_at
        )
