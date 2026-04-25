from __future__ import annotations

import json

import redis
import redis.asyncio as aioredis

from koh.core.config import settings

_pool: aioredis.ConnectionPool | None = None
_TOKEN_PREFIX = "auth:token:"
_API_PREFIX = "api:cache:"
_CACHE_TTL = 60  # seconds

_sync_client: redis.Redis | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return _pool


def _get_sync_client() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_client


# ── token auth cache ──────────────────────────────────────────────────────────

async def get_cached_token(token: str) -> dict | None:
    client = aioredis.Redis(connection_pool=_get_pool())
    data = await client.get(f"{_TOKEN_PREFIX}{token}")
    return json.loads(data) if data else None


async def set_cached_token(token: str, user_data: dict, ttl: int = _CACHE_TTL) -> None:
    client = aioredis.Redis(connection_pool=_get_pool())
    await client.setex(f"{_TOKEN_PREFIX}{token}", ttl, json.dumps(user_data))


async def invalidate_cached_token(token: str) -> None:
    client = aioredis.Redis(connection_pool=_get_pool())
    await client.delete(f"{_TOKEN_PREFIX}{token}")


# ── API response cache (async for routes, sync for Celery tasks) ──────────────

async def get_api_cache(key: str) -> dict | None:
    client = aioredis.Redis(connection_pool=_get_pool())
    data = await client.get(f"{_API_PREFIX}{key}")
    return json.loads(data) if data else None


async def set_api_cache(key: str, value: dict, ttl: int) -> None:
    client = aioredis.Redis(connection_pool=_get_pool())
    await client.setex(f"{_API_PREFIX}{key}", ttl, json.dumps(value))


def get_api_cache_sync(key: str) -> dict | None:
    r = _get_sync_client()
    data: str | None = r.get(f"{_API_PREFIX}{key}")  # type: ignore[assignment]
    return json.loads(data) if data else None


def set_api_cache_sync(key: str, value: dict, ttl: int) -> None:
    r = _get_sync_client()
    r.setex(f"{_API_PREFIX}{key}", ttl, json.dumps(value))


def invalidate_api_caches_sync(*keys: str) -> None:
    """Called from Celery tasks (sync context) to bust API caches."""
    r = _get_sync_client()
    full_keys = [f"{_API_PREFIX}{k}" for k in keys]
    if full_keys:
        r.delete(*full_keys)
