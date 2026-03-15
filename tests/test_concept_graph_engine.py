"""Tests for the Concept Graph Engine (CGE).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from concept_graph_engine import (
    ConceptGraphEngine,
    CrossDomainOpportunity,
    EDGE_CONFLICTS_WITH,
    EDGE_CONSUMES,
    EDGE_DEPENDS_ON,
    EDGE_IMPROVES,
    EDGE_PRODUCES,
    EDGE_REGULATED_BY,
    GraphHealthResult,
    NODE_TYPE_ACTOR,
    NODE_TYPE_CONCEPT,
    NODE_TYPE_DATA,
    NODE_TYPE_MODULE,
    NODE_TYPE_REGULATION,
    VALID_EDGE_TYPES,
    VALID_NODE_TYPES,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Return a fresh ConceptGraphEngine instance."""
    return ConceptGraphEngine()


@pytest.fixture
def populated_engine(engine):
    """Engine pre-loaded with a small but structurally rich graph."""
    engine.add_node("mod_a", NODE_TYPE_MODULE)
    engine.add_node("mod_b", NODE_TYPE_MODULE)
    engine.add_node("concept_x", NODE_TYPE_CONCEPT)
    engine.add_node("concept_y", NODE_TYPE_CONCEPT)
    engine.add_node("reg_1", NODE_TYPE_REGULATION)
    engine.add_node("data_1", NODE_TYPE_DATA)

    engine.add_edge("mod_a", "data_1", EDGE_DEPENDS_ON)
    engine.add_edge("mod_b", "data_1", EDGE_DEPENDS_ON)
    engine.add_edge("mod_a", "reg_1", EDGE_REGULATED_BY)
    engine.add_edge("concept_x", "mod_a", EDGE_IMPROVES)
    engine.add_edge("concept_y", "mod_a", EDGE_IMPROVES)
    return engine


# ── 1. add_node CRUD ────────────────────────────────────────────────


class TestAddNode:
    def test_add_node_returns_ok(self, engine):
        result = engine.add_node("n1", NODE_TYPE_MODULE)
        assert result["status"] == "ok"
        assert result["node_id"] == "n1"
        assert result["updated"] is False

    def test_add_node_appears_in_serialization(self, engine):
        engine.add_node("n1", NODE_TYPE_CONCEPT, {"desc": "hello"})
        data = engine.to_json()
        nodes_by_id = {n["id"]: n for n in data["nodes"]}
        assert "n1" in nodes_by_id
        assert nodes_by_id["n1"]["type"] == NODE_TYPE_CONCEPT
        assert nodes_by_id["n1"]["attributes"]["desc"] == "hello"

    def test_add_node_invalid_type_rejected(self, engine):
        result = engine.add_node("bad", "InvalidType")
        assert result["status"] == "error"
        assert "Invalid node type" in result["message"]

    def test_add_duplicate_node_updates_attributes(self, engine):
        engine.add_node("n1", NODE_TYPE_MODULE, {"a": 1})
        result = engine.add_node("n1", NODE_TYPE_MODULE, {"b": 2})
        assert result["updated"] is True
        data = engine.to_json()
        node = next(n for n in data["nodes"] if n["id"] == "n1")
        assert node["attributes"]["a"] == 1
        assert node["attributes"]["b"] == 2

    def test_add_node_without_attributes(self, engine):
        engine.add_node("n1", NODE_TYPE_ACTOR)
        data = engine.to_json()
        node = next(n for n in data["nodes"] if n["id"] == "n1")
        assert node["attributes"] == {}


# ── 2. add_edge CRUD ───────────────────────────────────────────────


class TestAddEdge:
    def test_add_edge_returns_ok(self, engine):
        result = engine.add_edge("a", "b", EDGE_DEPENDS_ON)
        assert result["status"] == "ok"
        assert result["duplicate"] is False

    def test_add_edge_appears_in_serialization(self, engine):
        engine.add_edge("a", "b", EDGE_PRODUCES)
        data = engine.to_json()
        assert any(
            e["source"] == "a" and e["target"] == "b" and e["type"] == EDGE_PRODUCES
            for e in data["edges"]
        )

    def test_add_edge_invalid_type_rejected(self, engine):
        result = engine.add_edge("a", "b", "made_up_type")
        assert result["status"] == "error"
        assert "Invalid edge type" in result["message"]

    def test_add_duplicate_edge_is_idempotent(self, engine):
        engine.add_edge("a", "b", EDGE_DEPENDS_ON)
        result = engine.add_edge("a", "b", EDGE_DEPENDS_ON)
        assert result["duplicate"] is True


# ── 3. remove_node ─────────────────────────────────────────────────


class TestRemoveNode:
    def test_remove_existing_node(self, engine):
        engine.add_node("n1", NODE_TYPE_MODULE)
        result = engine.remove_node("n1")
        assert result["status"] == "ok"
        assert result["node_id"] == "n1"

    def test_remove_node_also_removes_edges(self, engine):
        engine.add_node("n1", NODE_TYPE_MODULE)
        engine.add_node("n2", NODE_TYPE_DATA)
        engine.add_edge("n1", "n2", EDGE_DEPENDS_ON)
        engine.add_edge("n2", "n1", EDGE_PRODUCES)
        result = engine.remove_node("n1")
        assert result["edges_removed"] == 2
        data = engine.to_json()
        assert len(data["edges"]) == 0

    def test_remove_nonexistent_node_returns_error(self, engine):
        result = engine.remove_node("ghost")
        assert result["status"] == "error"


# ── 4. remove_edge ─────────────────────────────────────────────────


class TestRemoveEdge:
    def test_remove_existing_edge(self, engine):
        engine.add_edge("a", "b", EDGE_DEPENDS_ON)
        result = engine.remove_edge("a", "b", EDGE_DEPENDS_ON)
        assert result["status"] == "ok"
        assert len(engine.to_json()["edges"]) == 0

    def test_remove_nonexistent_edge_returns_error(self, engine):
        result = engine.remove_edge("x", "y", EDGE_DEPENDS_ON)
        assert result["status"] == "error"


# ── 5. find_missing_dependencies ───────────────────────────────────


class TestFindMissingDependencies:
    def test_no_missing_when_all_nodes_present(self, populated_engine):
        missing = populated_engine.find_missing_dependencies()
        assert missing == []

    def test_detects_missing_target_node(self, engine):
        engine.add_node("a", NODE_TYPE_MODULE)
        engine.add_edge("a", "phantom", EDGE_DEPENDS_ON)
        missing = engine.find_missing_dependencies()
        assert "phantom" in missing

    def test_detects_missing_source_node(self, engine):
        engine.add_node("b", NODE_TYPE_DATA)
        engine.add_edge("phantom_src", "b", EDGE_DEPENDS_ON)
        missing = engine.find_missing_dependencies()
        assert "phantom_src" in missing


# ── 6. find_regulatory_gaps ────────────────────────────────────────


class TestFindRegulatoryGaps:
    def test_module_with_regulation_not_a_gap(self, populated_engine):
        gaps = populated_engine.find_regulatory_gaps()
        assert "mod_a" not in gaps

    def test_module_without_regulation_is_a_gap(self, populated_engine):
        gaps = populated_engine.find_regulatory_gaps()
        assert "mod_b" in gaps

    def test_non_module_nodes_ignored(self, engine):
        engine.add_node("c1", NODE_TYPE_CONCEPT)
        gaps = engine.find_regulatory_gaps()
        assert gaps == []


# ── 7. find_redundant_modules ──────────────────────────────────────


class TestFindRedundantModules:
    def test_identical_dep_sets_detected(self, populated_engine):
        pairs = populated_engine.find_redundant_modules()
        assert ("mod_a", "mod_b") in pairs or ("mod_b", "mod_a") in pairs

    def test_different_dep_sets_not_flagged(self, engine):
        engine.add_node("m1", NODE_TYPE_MODULE)
        engine.add_node("m2", NODE_TYPE_MODULE)
        engine.add_node("d1", NODE_TYPE_DATA)
        engine.add_node("d2", NODE_TYPE_DATA)
        engine.add_edge("m1", "d1", EDGE_DEPENDS_ON)
        engine.add_edge("m2", "d2", EDGE_DEPENDS_ON)
        pairs = engine.find_redundant_modules()
        assert pairs == []

    def test_modules_without_deps_not_flagged(self, engine):
        engine.add_node("m1", NODE_TYPE_MODULE)
        engine.add_node("m2", NODE_TYPE_MODULE)
        pairs = engine.find_redundant_modules()
        assert pairs == []


# ── 8. detect_cross_domain_opportunities ───────────────────────────


class TestDetectCrossDomainOpportunities:
    def test_shared_targets_detected(self, populated_engine):
        opps = populated_engine.detect_cross_domain_opportunities()
        assert len(opps) >= 1
        opp = opps[0]
        assert isinstance(opp, CrossDomainOpportunity)
        assert "mod_a" in opp.shared_targets

    def test_no_shared_targets_yields_empty(self, engine):
        engine.add_node("c1", NODE_TYPE_CONCEPT)
        engine.add_node("c2", NODE_TYPE_CONCEPT)
        engine.add_node("t1", NODE_TYPE_MODULE)
        engine.add_node("t2", NODE_TYPE_MODULE)
        engine.add_edge("c1", "t1", EDGE_IMPROVES)
        engine.add_edge("c2", "t2", EDGE_IMPROVES)
        opps = engine.detect_cross_domain_opportunities()
        assert opps == []


# ── 9. compute_graph_health ────────────────────────────────────────


class TestComputeGraphHealth:
    def test_returns_graph_health_result(self, populated_engine):
        health = populated_engine.compute_graph_health()
        assert isinstance(health, GraphHealthResult)

    def test_metrics_in_valid_range(self, populated_engine):
        health = populated_engine.compute_graph_health()
        assert 0.0 <= health.node_coverage <= 1.0
        assert 0.0 <= health.dependency_completeness <= 1.0
        assert 0.0 <= health.regulatory_coverage <= 1.0
        assert 0.0 <= health.redundancy_score <= 1.0

    def test_cache_key_is_sha256_hex(self, populated_engine):
        health = populated_engine.compute_graph_health()
        assert len(health.cache_key) == 64
        int(health.cache_key, 16)  # must be valid hex

    def test_empty_graph_health(self, engine):
        health = engine.compute_graph_health()
        assert health.node_coverage == 1.0
        assert health.dependency_completeness == 1.0
        assert health.regulatory_coverage == 1.0
        assert health.redundancy_score == 0.0


# ── 10. Graph Connectivity Score ───────────────────────────────────


class TestComputeGCS:
    def test_gcs_in_valid_range(self, populated_engine):
        gcs = populated_engine.compute_gcs()
        assert 0.0 <= gcs <= 1.0

    def test_empty_graph_gcs_zero(self, engine):
        assert engine.compute_gcs() == 0.0

    def test_single_node_gcs_zero(self, engine):
        engine.add_node("solo", NODE_TYPE_MODULE)
        assert engine.compute_gcs() == 0.0

    def test_fully_connected_pair(self, engine):
        engine.add_node("a", NODE_TYPE_MODULE)
        engine.add_node("b", NODE_TYPE_DATA)
        engine.add_edge("a", "b", EDGE_DEPENDS_ON)
        engine.add_edge("b", "a", EDGE_PRODUCES)
        # 2 nodes, 2 edges → 2 / (2*1) = 1.0
        assert engine.compute_gcs() == 1.0


# ── 11. JSON persistence roundtrip ────────────────────────────────


class TestJsonRoundtrip:
    def test_roundtrip_preserves_nodes_and_edges(self, populated_engine):
        snapshot = populated_engine.to_json()
        restored = ConceptGraphEngine.from_json(snapshot)
        restored_snapshot = restored.to_json()
        assert len(snapshot["nodes"]) == len(restored_snapshot["nodes"])
        assert len(snapshot["edges"]) == len(restored_snapshot["edges"])

    def test_roundtrip_preserves_attributes(self, engine):
        engine.add_node("n1", NODE_TYPE_MODULE, {"key": "value"})
        snapshot = engine.to_json()
        restored = ConceptGraphEngine.from_json(snapshot)
        restored_data = restored.to_json()
        node = next(n for n in restored_data["nodes"] if n["id"] == "n1")
        assert node["attributes"]["key"] == "value"

    def test_roundtrip_cache_keys_match(self, populated_engine):
        snap_a = populated_engine.to_json()
        restored = ConceptGraphEngine.from_json(snap_a)
        snap_b = restored.to_json()
        assert snap_a["cache_key"] == snap_b["cache_key"]

    def test_from_json_empty_dict(self):
        engine = ConceptGraphEngine.from_json({})
        assert engine.to_json()["nodes"] == []
        assert engine.to_json()["edges"] == []


# ── 12. Thread safety ──────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_add_nodes(self, engine):
        errors = []

        def add_batch(start):
            try:
                for i in range(50):
                    engine.add_node(f"n_{start}_{i}", NODE_TYPE_MODULE)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_batch, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        data = engine.to_json()
        assert len(data["nodes"]) == 200

    def test_concurrent_add_edges(self, engine):
        for i in range(20):
            engine.add_node(f"n{i}", NODE_TYPE_MODULE)
        errors = []

        def add_edge_batch(offset):
            try:
                for i in range(19):
                    engine.add_edge(f"n{i}", f"n{i+1}", EDGE_DEPENDS_ON)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(add_edge_batch, t) for t in range(4)]
            for f in as_completed(futs):
                f.result()

        assert errors == []


# ── 13. Determinism ────────────────────────────────────────────────


class TestDeterminism:
    def test_same_ops_same_health(self):
        def build():
            e = ConceptGraphEngine()
            e.add_node("m1", NODE_TYPE_MODULE)
            e.add_node("m2", NODE_TYPE_MODULE)
            e.add_node("d1", NODE_TYPE_DATA)
            e.add_edge("m1", "d1", EDGE_DEPENDS_ON)
            e.add_edge("m2", "d1", EDGE_DEPENDS_ON)
            return e.compute_graph_health()

        h1 = build()
        h2 = build()
        assert h1 == h2
        assert h1.cache_key == h2.cache_key

    def test_same_ops_same_gcs(self):
        def build():
            e = ConceptGraphEngine()
            e.add_node("a", NODE_TYPE_MODULE)
            e.add_node("b", NODE_TYPE_DATA)
            e.add_edge("a", "b", EDGE_DEPENDS_ON)
            return e.compute_gcs()

        assert build() == build()


# ── 14. Edge cases ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_graph_find_missing(self, engine):
        assert engine.find_missing_dependencies() == []

    def test_empty_graph_find_regulatory_gaps(self, engine):
        assert engine.find_regulatory_gaps() == []

    def test_empty_graph_find_redundant_modules(self, engine):
        assert engine.find_redundant_modules() == []

    def test_empty_graph_cross_domain(self, engine):
        assert engine.detect_cross_domain_opportunities() == []

    def test_single_node_no_edges(self, engine):
        engine.add_node("solo", NODE_TYPE_MODULE)
        assert engine.find_missing_dependencies() == []
        gaps = engine.find_regulatory_gaps()
        assert gaps == ["solo"]

    def test_all_valid_node_types_accepted(self, engine):
        for i, ntype in enumerate(sorted(VALID_NODE_TYPES)):
            result = engine.add_node(f"node_{i}", ntype)
            assert result["status"] == "ok"

    def test_all_valid_edge_types_accepted(self, engine):
        for i, etype in enumerate(sorted(VALID_EDGE_TYPES)):
            result = engine.add_edge(f"s{i}", f"t{i}", etype)
            assert result["status"] == "ok"
