"""Port for access-token revocation.

Access tokens are stateless JWTs, so revoking one before its natural
expiry (logout, forced sign-out) requires an external deny-list. Redis is a
natural fit: entries are keyed by the token's ``jti`` and expire on their
own once the token would have expired anyway, so the list never grows
unbounded. See ``app.infrastructure.cache.redis_token_blacklist``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class TokenBlacklist(ABC):
    @abstractmethod
    async def blacklist(self, jti: str, expires_at: datetime) -> None: ...

    @abstractmethod
    async def is_blacklisted(self, jti: str) -> bool: ...
