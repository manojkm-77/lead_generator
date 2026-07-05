import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

_redis = None
_redis_pool = None
_available = False


async def get_redis():
    global _redis, _redis_pool, _available
    if _redis is not None:
        return _redis

    from backend.config import get_settings
    settings = get_settings()

    if not settings.redis_enabled:
        _available = False
        return None

    try:
        import redis.asyncio as aioredis
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=5,
            max_connections=20,
        )
        _redis = aioredis.Redis(connection_pool=_redis_pool)
        await _redis.ping()
        _available = True
        logger.info("Redis connected at %s", settings.redis_url)
    except Exception as e:
        logger.warning("Redis unavailable, using in-memory fallback: %s", e)
        _redis = None
        _available = False

    return _redis


def is_redis_available() -> bool:
    return _available


async def close_redis():
    global _redis, _redis_pool, _available
    if _redis_pool:
        await _redis_pool.disconnect()
    _redis = None
    _redis_pool = None
    _available = False
    logger.info("Redis connection closed")
