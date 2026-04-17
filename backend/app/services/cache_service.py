import json
import logging
import os
from typing import Any, Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class NoOpCache:
    """Fallback cache for local dev without Redis."""
    async def get(self, key: str) -> Optional[Any]:
        return None
    async def set(self, key: str, value: Any, ttl: int = 60):
        pass
    async def delete(self, key: str):
        pass
    async def delete_pattern(self, pattern: str):
        pass
    async def flush_all(self):
        pass

class RedisCache:
    def __init__(self, url: str):
        self.redis = redis.from_url(url, decode_responses=True)
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            val = await self.redis.get(key)
            from app.utils import metrics
            if val:
                metrics.track_redis_access(hit=True)
                return json.loads(val)
            metrics.track_redis_access(hit=False)
        except Exception as e:
            logger.error(f"Redis GET error for {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: int = 60):
        try:
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis SET error for {key}: {e}")

    async def delete(self, key: str):
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis DEL error for {key}: {e}")

    async def delete_pattern(self, pattern: str):
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis Pattern DEL error for {pattern}: {e}")

    async def flush_all(self):
        try:
            await self.redis.flushdb()
        except Exception as e:
            logger.error(f"Redis FLUSH error: {e}")

# Global cache instance
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    logger.info(f"Redis Cache initialized at {REDIS_URL.split('@')[-1]}")
    cache = RedisCache(REDIS_URL)
else:
    logger.warning("REDIS_URL not set. Using NoOpCache (caching disabled).")
    cache = NoOpCache()
