# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Cache module for Murphy System.

Provides a CacheClient that uses Redis when REDIS_URL is set,
otherwise falls back to an in-memory dict with TTL eviction.
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "")
CACHE_TTL = int(os.environ.get("MURPHY_CACHE_TTL", "3600"))


class _InMemoryCache:
    """Simple in-memory cache with TTL eviction."""

    def __init__(self, default_ttl: int = 3600):
        self._store: dict = {}
        self._ttl = default_ttl

    async def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        expire = time.monotonic() + (ttl or self._ttl)
        self._store[key] = (value, expire)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> str:
        return "PONG"

    async def close(self) -> None:
        self._store.clear()


class _RedisCache:
    """Redis-backed cache wrapper."""

    def __init__(self, url: str, default_ttl: int = 3600):
        self._url = url
        self._ttl = default_ttl
        self._client = None

    async def _ensure_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(self._url, decode_responses=True)
            except ImportError:
                logger.warning("redis package not installed — falling back to in-memory cache")
                raise

    async def get(self, key: str) -> Optional[str]:
        await self._ensure_client()
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        await self._ensure_client()
        await self._client.setex(key, ttl or self._ttl, value)

    async def delete(self, key: str) -> None:
        await self._ensure_client()
        await self._client.delete(key)

    async def ping(self) -> str:
        await self._ensure_client()
        result = await self._client.ping()
        return "PONG" if result else "error"

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class CacheClient:
    """
    Unified cache client for Murphy System.

    Uses Redis when REDIS_URL is set, otherwise uses in-memory dict.
    Register as a FastAPI dependency via ``get_cache()``.
    """

    def __init__(self, redis_url: str = "", ttl: int = CACHE_TTL):
        self._redis_url = redis_url or REDIS_URL
        self._ttl = ttl
        self._backend = None

    def _get_backend(self):
        if self._backend is None:
            if self._redis_url:
                try:
                    self._backend = _RedisCache(self._redis_url, self._ttl)
                    logger.info("CacheClient using Redis: %s", self._redis_url)
                except Exception as exc:
                    self._backend = _InMemoryCache(self._ttl)
                    logger.info("CacheClient falling back to in-memory cache")
            else:
                self._backend = _InMemoryCache(self._ttl)
                logger.info("CacheClient using in-memory cache (no REDIS_URL)")
        return self._backend

    @staticmethod
    def _make_key(prefix: str, data: str) -> str:
        """Create a cache key from prefix and data."""
        h = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"murphy:{prefix}:{h}"

    async def get(self, key: str) -> Optional[str]:
        return await self._get_backend().get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        await self._get_backend().set(key, value, ttl)

    async def delete(self, key: str) -> None:
        await self._get_backend().delete(key)

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        await self.set(key, json.dumps(value, default=str), ttl)

    async def ping(self) -> str:
        try:
            return await self._get_backend().ping()
        except Exception as exc:
            logger.warning("Cache ping failed: %s", exc)
            return "error"

    async def close(self) -> None:
        if self._backend is not None:
            await self._backend.close()


# ---------------------------------------------------------------------------
# Module-level singleton & FastAPI dependency
# ---------------------------------------------------------------------------

_cache_client: Optional[CacheClient] = None


def get_cache() -> CacheClient:
    """FastAPI dependency that returns the CacheClient singleton."""
    global _cache_client
    if _cache_client is None:
        _cache_client = CacheClient()
    return _cache_client
