from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_blacklist import TokenBlacklist
from app.application.ports.token_service import AccessTokenPayload, IssuedAccessToken, TokenService
from app.domain.exceptions import InvalidTokenError
from app.domain.value_objects.password import PlainPassword


class FakePasswordHasher(PasswordHasher):
    """No real hashing — deterministic and fast, which is all a unit test needs."""

    def hash(self, password: PlainPassword) -> str:
        return f"hashed::{password.value}"

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return hashed_password == f"hashed::{plain_password}"

    def needs_rehash(self, hashed_password: str) -> bool:
        return False


class FakeTokenService(TokenService):
    """Issues opaque, non-cryptographic tokens and remembers their payload
    in memory so ``decode_access_token`` can look them back up."""

    def __init__(self, refresh_ttl_seconds: int = 7 * 24 * 3600) -> None:
        self._issued: dict[str, AccessTokenPayload] = {}
        self._counter = 0
        self._refresh_ttl_seconds = refresh_ttl_seconds

    def create_access_token(
        self, *, user_id: uuid.UUID, email: str, role_names: set[str]
    ) -> IssuedAccessToken:
        self._counter += 1
        now = datetime.now(UTC)
        payload = AccessTokenPayload(
            user_id=user_id,
            email=email,
            role_names=frozenset(role_names),
            jti=f"jti-{self._counter}",
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
        )
        token = f"access-token-{self._counter}"
        self._issued[token] = payload
        return IssuedAccessToken(token=token, payload=payload)

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        payload = self._issued.get(token)
        if payload is None:
            raise InvalidTokenError("Unknown token")
        if datetime.now(UTC) >= payload.expires_at:
            raise InvalidTokenError("Token expired")
        return payload

    def generate_refresh_token(self) -> str:
        self._counter += 1
        return f"refresh-token-{self._counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        return f"hash::{raw_token}"

    def refresh_token_ttl_seconds(self) -> int:
        return self._refresh_ttl_seconds


class FakeTokenBlacklist(TokenBlacklist):
    def __init__(self) -> None:
        self._blacklisted: set[str] = set()

    async def blacklist(self, jti: str, expires_at: datetime) -> None:
        self._blacklisted.add(jti)

    async def is_blacklisted(self, jti: str) -> bool:
        return jti in self._blacklisted
