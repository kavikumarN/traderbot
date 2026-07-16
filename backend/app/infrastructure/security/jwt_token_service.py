"""JWT access tokens + opaque refresh tokens.

Access tokens are signed (HS256 by default) JWTs carrying ``sub``, ``email``,
``roles`` and a unique ``jti`` used for revocation (see
``app.infrastructure.cache.redis_token_blacklist``). Refresh tokens are
plain random strings — never JWTs — so they carry no decodable information
and their only representation server-side is a SHA-256 hash.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.application.ports.token_service import AccessTokenPayload, IssuedAccessToken, TokenService
from app.domain.exceptions import InvalidTokenError


class JwtTokenService(TokenService):
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        access_token_expire_minutes: int,
        refresh_token_expire_days: int,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_days = refresh_token_expire_days

    def create_access_token(
        self, *, user_id: uuid.UUID, email: str, role_names: set[str]
    ) -> IssuedAccessToken:
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self._access_token_expire_minutes)
        jti = str(uuid.uuid4())

        claims = {
            "sub": str(user_id),
            "email": email,
            "roles": sorted(role_names),
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(claims, self._secret_key, algorithm=self._algorithm)
        payload = AccessTokenPayload(
            user_id=user_id,
            email=email,
            role_names=frozenset(role_names),
            jti=jti,
            issued_at=now,
            expires_at=expires_at,
        )
        return IssuedAccessToken(token=token, payload=payload)

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        try:
            claims = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        try:
            return AccessTokenPayload(
                user_id=uuid.UUID(claims["sub"]),
                email=claims["email"],
                role_names=frozenset(claims.get("roles", [])),
                jti=claims["jti"],
                issued_at=datetime.fromtimestamp(claims["iat"], tz=UTC),
                expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
            )
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError("Malformed token claims") from exc

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def hash_refresh_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def refresh_token_ttl_seconds(self) -> int:
        return self._refresh_token_expire_days * 24 * 3600
