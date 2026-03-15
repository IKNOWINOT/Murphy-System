"""
Tests for Layer 5 — MemoryLayer (STM / LTM).
"""

import pytest

from aionmind.memory_layer import MemoryLayer


class TestMemoryLayer:

    def test_stm_store_and_retrieve(self):
        ml = MemoryLayer()
        ml.store_intermediate_state("k1", {"value": 42})
        result = ml.retrieve_context("k1")
        assert result is not None
        assert result["value"] == 42
        assert "_stored_at" in result

    def test_stm_retrieve_missing_returns_none(self):
        ml = MemoryLayer()
        assert ml.retrieve_context("missing") is None

    def test_stm_delete(self):
        ml = MemoryLayer()
        ml.store_intermediate_state("k1", {"v": 1})
        assert ml.delete_stm("k1") is True
        assert ml.retrieve_context("k1") is None
        assert ml.delete_stm("k1") is False

    def test_stm_list_keys(self):
        ml = MemoryLayer()
        ml.store_intermediate_state("a", {})
        ml.store_intermediate_state("b", {})
        assert sorted(ml.list_stm_keys()) == ["a", "b"]

    def test_ltm_archive_and_retrieve(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-1", {"outcome": "success", "tags": ["deploy"]})
        result = ml.retrieve_archived("wf-1")
        assert result is not None
        assert result["outcome"] == "success"
        assert "_archived_at" in result

    def test_ltm_search_by_tags(self):
        ml = MemoryLayer()
        ml.archive_workflow("wf-1", {"tags": ["deploy", "v2"]})
        ml.archive_workflow("wf-2", {"tags": ["rollback"]})
        results = ml.search_ltm(tags=["deploy"])
        assert len(results) == 1

    def test_ltm_search_no_filter(self):
        ml = MemoryLayer()
        ml.archive_workflow("a", {"tags": []})
        ml.archive_workflow("b", {"tags": []})
        results = ml.search_ltm()
        assert len(results) == 2

    def test_stats(self):
        ml = MemoryLayer()
        ml.store_intermediate_state("s1", {})
        ml.archive_workflow("l1", {})
        stats = ml.stats()
        assert stats["stm_entries"] == 1
        assert stats["ltm_entries"] == 1
