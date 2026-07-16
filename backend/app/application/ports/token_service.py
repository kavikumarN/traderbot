"""Port for token issuance and verification.

Two distinct token kinds are handled here:

* **Access tokens** are self-contained JWTs (sub, email, roles, jti, exp) —
  verified locally on every request with no I/O.
* **Refresh tokens** are opaque random strings; only their SHA-256 hash is
  ever persisted (see ``RefreshTokenRepository``), so this port also exposes
  ``hash_refresh_token`` for repositories/use-cases to look tokens up by hash.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    user_id: uuid.UUID
    email: str
    role_names: frozenset[str]
    jti: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    token: str
    payload: AccessTokenPayload


class TokenService(ABC):
    @abstractmethod
    def create_access_token(
        self, *, user_id: uuid.UUID, email: str, role_names: set[str]
    ) -> IssuedAccessToken: ...

    @abstractmethod
    def decode_access_token(self, token: str) -> AccessTokenPayload:
        """Raises ``app.domain.exceptions.InvalidTokenError`` on any failure."""
        ...

    @abstractmethod
    def generate_refresh_token(self) -> str:
        """A new cryptographically random opaque refresh token (raw, unhashed)."""
        ...

    @abstractmethod
    def hash_refresh_token(self, raw_token: str) -> str: ...

    @abstractmethod
    def refresh_token_ttl_seconds(self) -> int: ...
