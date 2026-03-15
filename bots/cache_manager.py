"""Simple cache manager with TTL and usage tracking."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

CACHE_FILE = Path("cache/cache_store.json")


def _load() -> Dict[str, Any]:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save(data: Dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def get_cache(key: str) -> Any | None:
    cache = _load()
    entry = cache.get(key)
    if not entry:
        return None
    try:
        expiry = datetime.fromisoformat(entry["validated_at"]) + timedelta(seconds=entry["ttl_seconds"])
    except Exception:
        expiry = datetime.now(timezone.utc)
    if datetime.now(timezone.utc) > expiry:
        cache.pop(key, None)
        _save(cache)
        return None
    entry["hits"] += 1
    entry["last_accessed"] = datetime.now(timezone.utc).isoformat()
    _save(cache)
    return entry["value"]


def set_cache(key: str, value: Any, ttl_seconds: int = 300) -> None:
    cache = _load()
    cache[key] = {
        "value": value,
        "ttl_seconds": ttl_seconds,
        "hits": 0,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "last_accessed": datetime.now(timezone.utc).isoformat(),
    }
    _save(cache)


def delete_cache(key: str) -> None:
    cache = _load()
    if key in cache:
        cache.pop(key)
        _save(cache)


def cache_stats() -> Dict[str, Any]:
    cache = _load()
    top_hits = sorted(cache.items(), key=lambda x: x[1]["hits"], reverse=True)[:5]
    return {
        "total_keys": len(cache),
        "top_hit_keys": [(k, v["hits"]) for k, v in top_hits],
    }


def cleanup_cache() -> int:
    cache = _load()
    now = datetime.now(timezone.utc)
    removed = 0
    for key in list(cache.keys()):
        entry = cache[key]
        try:
            expiry = datetime.fromisoformat(entry["validated_at"]) + timedelta(seconds=entry["ttl_seconds"])
        except Exception:
            expiry = now
        if now > expiry:
            cache.pop(key)
            removed += 1
    if removed:
        _save(cache)
    return removed
