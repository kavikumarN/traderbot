"""Authenticate a user and issue an access/refresh token pair."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_service import TokenService
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.refresh_token import RefreshToken
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    user_id: uuid.UUID
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime


class LoginUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._uow_factory = uow_factory
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def execute(self, command: LoginCommand) -> LoginResult:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_email(command.email.strip().lower())
            # Run verify() even when no user was found so login latency
            # doesn't leak whether an email is registered (timing side-channel).
            hash_to_check = user.hashed_password if user else _DUMMY_HASH
            password_ok = self._password_hasher.verify(command.password, hash_to_check)
            if user is None or not password_ok:
                raise InvalidCredentialsError()
            if not user.is_active:
                raise InactiveUserError()

            issued = self._token_service.create_access_token(
                user_id=user.id, email=str(user.email), role_names=user.role_names
            )

            now = datetime.now(UTC)
            raw_refresh_token = self._token_service.generate_refresh_token()
            refresh_expires_at = now + timedelta(
                seconds=self._token_service.refresh_token_ttl_seconds()
            )
            await uow.refresh_tokens.add(
                RefreshToken(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    token_hash=self._token_service.hash_refresh_token(raw_refresh_token),
                    issued_at=now,
                    expires_at=refresh_expires_at,
                    user_agent=command.user_agent,
                    ip_address=command.ip_address,
                )
            )
            await uow.commit()

        return LoginResult(
            user_id=user.id,
            access_token=issued.token,
            access_token_expires_at=issued.payload.expires_at,
            refresh_token=raw_refresh_token,
            refresh_token_expires_at=refresh_expires_at,
        )


# A pre-computed Argon2id hash of a random, never-used password. Verifying
# against it keeps the "user not found" and "wrong password" code paths
# doing the same amount of hashing work.
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "N0VVNklOOEZBOUpDNkVKQg$Xt2y1E9m2b8G3z0qk4h8mQ6z8b8f7oQ2m3h4j5k6l7M"
)
