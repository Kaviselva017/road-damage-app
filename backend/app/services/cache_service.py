import json
import logging
import os
from typing import Any, Protocol

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class CacheInterface(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int = 60) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_pattern(self, pattern: str) -> None: ...
    async def list(self, prefix: str) -> list[Any]: ...
    async def flush_all(self) -> None: ...


class NoOpCache:
    """Fallback cache for local dev without Redis."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def delete_pattern(self, pattern: str) -> None:
        pass

    async def list(self, prefix: str) -> list[Any]:
        return []

    async def flush_all(self) -> None:
        pass


class RedisCache:
    def __init__(self, url: str):
        pool = redis.ConnectionPool.from_url(url, decode_responses=True, max_connections=10)
        self.redis = redis.Redis(connection_pool=pool)

    async def get(self, key: str) -> Any | None:
        try:
            val = await self.redis.get(key)
            from app.utils import metrics

            if val:
                metrics.track_redis_access(hit=True)
                return json.loads(str(val))
            metrics.track_redis_access(hit=False)
        except Exception as e:
            logger.error(f"Redis GET error for {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        try:
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis SET error for {key}: {e}")

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis DEL error for {key}: {e}")

    async def delete_pattern(self, pattern: str) -> None:
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis Pattern DEL error for {pattern}: {e}")

    async def list(self, prefix: str) -> list[Any]:
        try:
            keys = await self.redis.keys(f"{prefix}*")
            if not keys:
                return []
            vals = await self.redis.mget(keys)
            return [json.loads(str(v)) for v in vals if v]
        except Exception as e:
            logger.error(f"Redis LIST error for {prefix}: {e}")
            return []

    async def flush_all(self) -> None:
        try:
            await self.redis.flushdb()
        except Exception as e:
            logger.error(f"Redis FLUSH error: {e}")


# Global cache instance
REDIS_URL = os.getenv("REDIS_URL")
cache: CacheInterface
if REDIS_URL:
    logger.info(f"Redis Cache initialized at {REDIS_URL.split('@')[-1]}")
    cache = RedisCache(REDIS_URL)
else:
    logger.warning("REDIS_URL not set. Using NoOpCache (caching disabled).")
    cache = NoOpCache()
