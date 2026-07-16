from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    return Redis.from_url(str(settings.redis_url), decode_responses=True)
