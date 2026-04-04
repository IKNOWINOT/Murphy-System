"""
Tests for Persistent Memory + Context Compression (PM-001..PM-003).

Covers: per-tenant CRUD, preferences, execution patterns, search,
TTL expiry, tenant limits, context compression strategies.
"""

from __future__ import annotations

import time

import pytest

from src.persistent_memory.tenant_memory import (
    MemoryEntry,
    TenantMemoryStore,
)
from src.persistent_memory.context_compressor import (
    CompressionStrategy,
    ContextCompressor,
    ContextMessage,
    MessagePriority,
)


# ---------------------------------------------------------------------------
# TenantMemoryStore tests
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    return TenantMemoryStore(max_entries_per_tenant=100, max_tenants=10)


class TestTenantCRUD:
    def test_store_and_retrieve(self, store):
        store.store("t1", "key1", "value1")
        entry = store.retrieve("t1", "key1")
        assert entry is not None
        assert entry.value == "value1"

    def test_retrieve_nonexistent(self, store):
        assert store.retrieve("t1", "missing") is None

    def test_retrieve_from_nonexistent_tenant(self, store):
        assert store.retrieve("missing_tenant", "key") is None

    def test_update_existing(self, store):
        store.store("t1", "key1", "v1")
        store.store("t1", "key1", "v2")
        entry = store.retrieve("t1", "key1")
        assert entry.value == "v2"

    def test_delete(self, store):
        store.store("t1", "key1", "v1")
        assert store.delete("t1", "key1") is True
        assert store.retrieve("t1", "key1") is None

    def test_delete_nonexistent(self, store):
        assert store.delete("t1", "missing") is False

    def test_list_keys(self, store):
        store.store("t1", "a", 1)
        store.store("t1", "b", 2)
        keys = store.list_keys("t1")
        assert set(keys) == {"a", "b"}

    def test_list_keys_by_category(self, store):
        store.store("t1", "a", 1, category="prefs")
        store.store("t1", "b", 2, category="other")
        keys = store.list_keys("t1", category="prefs")
        assert keys == ["a"]


class TestPreferences:
    def test_store_and_get_preference(self, store):
        store.store_preference("t1", "theme", "dark")
        assert store.get_preference("t1", "theme") == "dark"

    def test_get_missing_preference(self, store):
        assert store.get_preference("t1", "missing") is None

    def test_get_all_preferences(self, store):
        store.store_preference("t1", "theme", "dark")
        store.store_preference("t1", "language", "en")
        prefs = store.get_all_preferences("t1")
        assert prefs == {"theme": "dark", "language": "en"}


class TestExecutionPatterns:
    def test_store_execution_pattern(self, store):
        store.store_execution_pattern("t1", "deploy", {"steps": 3})
        entry = store.retrieve("t1", "pattern:deploy")
        assert entry is not None
        assert entry.value == {"steps": 3}


class TestSearch:
    def test_search_by_category(self, store):
        store.store("t1", "a", 1, category="prefs")
        store.store("t1", "b", 2, category="data")
        results = store.search("t1", category="prefs")
        assert len(results) == 1

    def test_search_by_tags(self, store):
        store.store("t1", "a", 1, tags=["important"])
        store.store("t1", "b", 2, tags=["routine"])
        results = store.search("t1", tags=["important"])
        assert len(results) == 1

    def test_search_by_text(self, store):
        store.store("t1", "greeting", "hello world")
        results = store.search("t1", text_contains="hello")
        assert len(results) == 1

    def test_search_empty_tenant(self, store):
        results = store.search("nonexistent")
        assert results == []


class TestTTL:
    def test_expired_entry_not_returned(self, store):
        store.store("t1", "temp", "data", ttl_seconds=0.01)
        time.sleep(0.05)
        assert store.retrieve("t1", "temp") is None


class TestLimits:
    def test_eviction_on_limit(self):
        store = TenantMemoryStore(max_entries_per_tenant=3, max_tenants=10)
        store.store("t1", "a", 1)
        store.store("t1", "b", 2)
        store.store("t1", "c", 3)
        store.store("t1", "d", 4)  # should evict 'a'
        assert store.retrieve("t1", "a") is None
        assert store.retrieve("t1", "d") is not None

    def test_tenant_eviction(self):
        store = TenantMemoryStore(max_entries_per_tenant=100, max_tenants=2)
        store.store("t1", "a", 1)
        store.store("t2", "b", 2)
        store.store("t3", "c", 3)  # should evict t1
        assert store.retrieve("t1", "a") is None
        assert store.retrieve("t3", "c") is not None


class TestStats:
    def test_stats_empty(self, store):
        stats = store.stats("t1")
        assert stats.total_entries == 0

    def test_stats_populated(self, store):
        store.store("t1", "a", 1, category="cat1")
        store.store("t1", "b", 2, category="cat2")
        stats = store.stats("t1")
        assert stats.total_entries == 2
        assert stats.categories == {"cat1": 1, "cat2": 1}

    def test_tenant_count(self, store):
        store.store("t1", "a", 1)
        store.store("t2", "b", 2)
        assert store.tenant_count() == 2


# ---------------------------------------------------------------------------
# ContextCompressor tests
# ---------------------------------------------------------------------------

@pytest.fixture
def compressor():
    return ContextCompressor(max_tokens=100, window_size=5, summary_max_tokens=30)


def make_messages(count: int, tokens_each: int = 20) -> list:
    return [
        ContextMessage(
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i} " + "x" * (tokens_each * 4 - 10),
            token_estimate=tokens_each,
        )
        for i in range(count)
    ]


class TestCompressionBasic:
    def test_no_compression_needed(self, compressor):
        msgs = make_messages(3, tokens_each=10)  # 30 tokens total, under 100
        result = compressor.compress(msgs)
        assert result.compressed_messages == 3
        assert result.savings_ratio == 0.0

    def test_sliding_window(self, compressor):
        msgs = make_messages(10, tokens_each=20)
        result = compressor.compress(
            msgs, strategy=CompressionStrategy.SLIDING_WINDOW,
        )
        assert result.compressed_messages < result.original_messages
        assert result.compressed_tokens <= 100

    def test_summary_extraction(self, compressor):
        msgs = make_messages(10, tokens_each=20)
        result = compressor.compress(
            msgs, strategy=CompressionStrategy.SUMMARY,
        )
        assert result.compressed_messages < result.original_messages
        # First message should be the summary
        assert result.messages[0].is_compressed is True

    def test_priority_based(self, compressor):
        msgs = [
            ContextMessage(content="Critical info", priority=MessagePriority.CRITICAL,
                           token_estimate=20),
            ContextMessage(content="Low info " + "x" * 80, priority=MessagePriority.LOW,
                           token_estimate=30),
            ContextMessage(content="High info", priority=MessagePriority.HIGH,
                           token_estimate=20),
        ]
        result = compressor.compress(
            msgs, strategy=CompressionStrategy.PRIORITY, max_tokens=50,
        )
        # Critical and High should be kept
        priorities = [m.priority for m in result.messages]
        assert MessagePriority.CRITICAL in priorities

    def test_hybrid_strategy(self, compressor):
        msgs = make_messages(10, tokens_each=20)
        result = compressor.compress(
            msgs, strategy=CompressionStrategy.HYBRID,
        )
        assert result.compressed_messages <= result.original_messages


class TestTokenEstimation:
    def test_estimate_tokens(self, compressor):
        assert compressor.estimate_tokens("hello") >= 1
        assert compressor.estimate_tokens("a" * 400) == 100

    def test_auto_populate_tokens(self, compressor):
        msgs = [ContextMessage(content="hello world")]
        result = compressor.compress(msgs)
        assert result.messages[0].token_estimate > 0
