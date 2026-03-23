"""Lightweight Redis cache for frequently-accessed data (user profiles, etc.)."""

import json
import logging

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def cache_get(key: str) -> dict | None:
    """Get a JSON-serialized value from Redis. Returns None on miss or error."""
    try:
        raw = await _get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        logger.debug("Cache miss/error for %s", key, exc_info=True)
        return None


async def cache_set(key: str, value: dict, ttl_seconds: int = 300) -> None:
    """Set a JSON-serialized value in Redis with TTL. Fails silently."""
    try:
        await _get_redis().setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.debug("Cache write error for %s", key, exc_info=True)


async def cache_delete(key: str) -> None:
    """Delete a key from Redis. Fails silently."""
    try:
        await _get_redis().delete(key)
    except Exception:
        logger.debug("Cache delete error for %s", key, exc_info=True)
