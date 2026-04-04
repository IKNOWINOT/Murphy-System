"""
Per-tenant persistent memory store.

Design Label: PM-002

Murphy remembers user preferences, past execution patterns, and
domain-specific corrections across sessions.  Extends AionMind's STM/LTM
concept to system-wide per-tenant scope.

Thread-safe, bounded per-tenant storage (default 10 000 entries per tenant).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_MAX_ENTRIES_PER_TENANT = 10_000
_MAX_TENANTS = 1_000


class MemoryEntry(BaseModel):
    """A single memory entry stored per tenant."""

    key: str
    value: Any
    category: str = "general"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    access_count: int = 0
    ttl_seconds: Optional[float] = None  # None = never expires
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TenantMemoryStats(BaseModel):
    """Statistics for a single tenant's memory."""

    tenant_id: str
    total_entries: int = 0
    categories: Dict[str, int] = Field(default_factory=dict)
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None


class TenantMemoryStore:
    """Thread-safe per-tenant persistent memory.

    Provides key-value storage with categories, tags, TTL, and search.
    Bounded to prevent unbounded growth (CWE-770).
    """

    def __init__(
        self,
        *,
        max_entries_per_tenant: int = _MAX_ENTRIES_PER_TENANT,
        max_tenants: int = _MAX_TENANTS,
    ) -> None:
        self._lock = threading.Lock()
        self._max_entries = max_entries_per_tenant
        self._max_tenants = max_tenants
        # tenant_id → OrderedDict[key → MemoryEntry]
        self._stores: Dict[str, OrderedDict[str, MemoryEntry]] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def store(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        *,
        category: str = "general",
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Store or update a memory entry for a tenant."""
        with self._lock:
            store = self._get_or_create_store(tenant_id)
            now = datetime.now(timezone.utc)

            existing = store.get(key)
            if existing:
                existing.value = value
                existing.category = category
                existing.tags = tags or existing.tags
                existing.updated_at = now
                existing.ttl_seconds = ttl_seconds
                if metadata:
                    existing.metadata.update(metadata)
                store.move_to_end(key)
                return existing

            # Enforce per-tenant limit (evict oldest)
            while len(store) >= self._max_entries:
                evicted_key, _ = store.popitem(last=False)
                logger.debug("Evicted memory entry %s for tenant %s",
                             evicted_key, tenant_id)

            entry = MemoryEntry(
                key=key,
                value=value,
                category=category,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                ttl_seconds=ttl_seconds,
                metadata=metadata or {},
            )
            store[key] = entry
            return entry

    def retrieve(self, tenant_id: str, key: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry.  Returns None if not found or expired."""
        with self._lock:
            store = self._stores.get(tenant_id)
            if not store:
                return None
            entry = store.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                del store[key]
                return None
            entry.access_count += 1
            return entry

    def delete(self, tenant_id: str, key: str) -> bool:
        """Delete a memory entry.  Returns True if it existed."""
        with self._lock:
            store = self._stores.get(tenant_id)
            if store and key in store:
                del store[key]
                return True
            return False

    def list_keys(
        self,
        tenant_id: str,
        *,
        category: Optional[str] = None,
    ) -> List[str]:
        """List all keys for a tenant, optionally filtered by category."""
        with self._lock:
            store = self._stores.get(tenant_id)
            if not store:
                return []
            self._gc_expired(store)
            if category:
                return [k for k, e in store.items() if e.category == category]
            return list(store.keys())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        tenant_id: str,
        *,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        text_contains: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """Search tenant memory with optional filters (AND-combined)."""
        with self._lock:
            store = self._stores.get(tenant_id)
            if not store:
                return []
            self._gc_expired(store)
            results: List[MemoryEntry] = []
            for entry in store.values():
                if category and entry.category != category:
                    continue
                if tags and not set(tags).intersection(entry.tags):
                    continue
                if text_contains:
                    text_lower = text_contains.lower()
                    val_str = str(entry.value).lower()
                    key_str = entry.key.lower()
                    if text_lower not in val_str and text_lower not in key_str:
                        continue
                results.append(entry)
            return results

    # ------------------------------------------------------------------
    # Bulk / Preferences
    # ------------------------------------------------------------------

    def store_preference(
        self,
        tenant_id: str,
        pref_key: str,
        pref_value: Any,
    ) -> MemoryEntry:
        """Convenience: store a user preference."""
        return self.store(
            tenant_id, f"pref:{pref_key}", pref_value,
            category="preference",
            tags=["preference", "user_setting"],
        )

    def get_preference(self, tenant_id: str, pref_key: str) -> Any:
        """Convenience: retrieve a preference value."""
        entry = self.retrieve(tenant_id, f"pref:{pref_key}")
        return entry.value if entry else None

    def store_execution_pattern(
        self,
        tenant_id: str,
        pattern_name: str,
        pattern_data: Dict[str, Any],
    ) -> MemoryEntry:
        """Store an execution pattern for later recall."""
        return self.store(
            tenant_id, f"pattern:{pattern_name}", pattern_data,
            category="execution_pattern",
            tags=["pattern", "execution"],
        )

    def get_all_preferences(self, tenant_id: str) -> Dict[str, Any]:
        """Retrieve all preferences for a tenant."""
        entries = self.search(tenant_id, category="preference")
        return {
            e.key.removeprefix("pref:"): e.value
            for e in entries
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self, tenant_id: str) -> TenantMemoryStats:
        """Get memory statistics for a tenant."""
        with self._lock:
            store = self._stores.get(tenant_id)
            if not store:
                return TenantMemoryStats(tenant_id=tenant_id)
            self._gc_expired(store)
            cats: Dict[str, int] = {}
            oldest: Optional[datetime] = None
            newest: Optional[datetime] = None
            for entry in store.values():
                cats[entry.category] = cats.get(entry.category, 0) + 1
                if oldest is None or entry.created_at < oldest:
                    oldest = entry.created_at
                if newest is None or entry.created_at > newest:
                    newest = entry.created_at
            return TenantMemoryStats(
                tenant_id=tenant_id,
                total_entries=len(store),
                categories=cats,
                oldest_entry=oldest,
                newest_entry=newest,
            )

    def tenant_count(self) -> int:
        """Number of active tenants."""
        with self._lock:
            return len(self._stores)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_or_create_store(
        self, tenant_id: str,
    ) -> OrderedDict[str, MemoryEntry]:
        """Get or create a per-tenant store.  Enforces max_tenants."""
        if tenant_id in self._stores:
            return self._stores[tenant_id]
        if len(self._stores) >= self._max_tenants:
            # Evict oldest tenant (first in dict)
            oldest_tid = next(iter(self._stores))
            del self._stores[oldest_tid]
            logger.warning("Evicted tenant %s memory (max tenants reached)", oldest_tid)
        store: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._stores[tenant_id] = store
        return store

    @staticmethod
    def _is_expired(entry: MemoryEntry) -> bool:
        """Check if an entry has expired based on TTL."""
        if entry.ttl_seconds is None:
            return False
        elapsed = (datetime.now(timezone.utc) - entry.updated_at).total_seconds()
        return elapsed > entry.ttl_seconds

    def _gc_expired(self, store: OrderedDict[str, MemoryEntry]) -> None:
        """Garbage-collect expired entries from a store."""
        expired = [k for k, e in store.items() if self._is_expired(e)]
        for k in expired:
            del store[k]
