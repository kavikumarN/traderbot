"""RefreshToken entity.

Refresh tokens are opaque, cryptographically random strings; only their
SHA-256 hash is ever persisted (see
``app.infrastructure.security.jwt_token_service``), so a database leak does
not hand out usable tokens. Rotation is enforced here: redeeming a token
issues a new one and marks the old one ``replaced_by_token_id`` so reuse of
an already-rotated token is detectable (a strong signal of token theft).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RefreshToken:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_token_id: uuid.UUID | None = None
    user_agent: str | None = None
    ip_address: str | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_active(self, now: datetime) -> bool:
        return not self.is_expired(now) and not self.is_revoked()

    def revoke(self, now: datetime, *, replaced_by: uuid.UUID | None = None) -> None:
        self.revoked_at = now
        self.replaced_by_token_id = replaced_by
