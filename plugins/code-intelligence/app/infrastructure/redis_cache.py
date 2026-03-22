"""Redis cache implementation. Implements CachePort."""

from __future__ import annotations

import redis

from app.infrastructure.logging import get_logger

logger = get_logger("cache.redis")


class RedisCache:
    def __init__(self, url: str, default_ttl: int = 300):
        self._client = redis.from_url(url, decode_responses=True)
        self._default_ttl = default_ttl
        logger.info("Redis cache connected: %s", url)

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except redis.RedisError as e:
            logger.warning("Redis GET error: %s", e)
            return None

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        t = ttl if ttl is not None else self._default_ttl
        try:
            if t > 0:
                self._client.setex(key, t, value)
            else:
                self._client.set(key, value)
        except redis.RedisError as e:
            logger.warning("Redis SET error: %s", e)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except redis.RedisError as e:
            logger.warning("Redis DELETE error: %s", e)

    def clear(self) -> None:
        try:
            self._client.flushdb()
        except redis.RedisError as e:
            logger.warning("Redis CLEAR error: %s", e)
