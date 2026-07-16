"""Redis-backed access-token deny-list.

Each blacklisted ``jti`` is stored with a TTL equal to the token's
remaining lifetime, so entries self-expire and the key space never grows
unbounded regardless of how many users log out.
"""

from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis

from app.application.ports.token_blacklist import TokenBlacklist

_KEY_PREFIX = "auth:blacklist:jti:"


class RedisTokenBlacklist(TokenBlacklist):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def blacklist(self, jti: str, expires_at: datetime) -> None:
        ttl_seconds = max(int((expires_at - datetime.now(UTC)).total_seconds()), 1)
        await self._redis.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_blacklisted(self, jti: str) -> bool:
        return bool(await self._redis.exists(f"{_KEY_PREFIX}{jti}"))
