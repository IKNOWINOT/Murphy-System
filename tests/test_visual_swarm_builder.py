"""
Tests for Visual Swarm Builder (VSB-001).

Covers:
  - create_blueprint / add_node / connect_nodes
  - generate_recommendations (missing gate, missing output, isolated nodes)
  - validate_blueprint (errors, warnings, HITL gate check)
  - export_as_spec (JSON-serialisable production capability spec)
  - import_project (external project analysis, language detection)
  - get_blueprint / list_blueprints / get_audit_log
  - Input validation guards
  - Thread-safety

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import sys
import os
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from visual_swarm_builder import (
    ProjectAnalysis,
    Recommendation,
    SwarmBlueprint,
    ValidationResult,
    VisualNode,
    VisualSwarmBuilder,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builder():
    return VisualSwarmBuilder()


def _minimal_valid_blueprint(builder: VisualSwarmBuilder) -> str:
    """Create a minimal valid blueprint (agent → HITL gate → output)."""
    bp = builder.create_blueprint("Minimal Valid", "Test")
    bid = bp.blueprint_id
    agent = builder.add_node(bid, "agent", "Primary Agent")
    gate = builder.add_node(bid, "gate", "HITL Approval Gate",
                            config={"requires_human": True})
    output = builder.add_node(bid, "output", "Deliverable Output")
    builder.connect_nodes(bid, agent.node_id, gate.node_id)
    builder.connect_nodes(bid, gate.node_id, output.node_id)
    return bid


# ---------------------------------------------------------------------------
# Blueprint creation
# ---------------------------------------------------------------------------

class TestCreateBlueprint:
    def test_returns_blueprint(self, builder):
        bp = builder.create_blueprint("My Swarm", "A test swarm")
        assert isinstance(bp, SwarmBlueprint)
        assert bp.blueprint_id != ""

    def test_name_stored(self, builder):
        bp = builder.create_blueprint("Named Blueprint")
        assert bp.name == "Named Blueprint"

    def test_status_draft(self, builder):
        bp = builder.create_blueprint("Draft")
        assert bp.status == "draft"

    def test_stored_and_retrievable(self, builder):
        bp = builder.create_blueprint("Stored")
        retrieved = builder.get_blueprint(bp.blueprint_id)
        assert retrieved is not None
        assert retrieved.blueprint_id == bp.blueprint_id

    def test_listed(self, builder):
        builder.create_blueprint("BP1")
        builder.create_blueprint("BP2")
        listing = builder.list_blueprints()
        assert len(listing) == 2


# ---------------------------------------------------------------------------
# add_node
# ---------------------------------------------------------------------------

class TestAddNode:
    def test_adds_agent_node(self, builder):
        bp = builder.create_blueprint("bp")
        node = builder.add_node(bp.blueprint_id, "agent", "My Agent")
        assert isinstance(node, VisualNode)
        assert node.node_type == "agent"
        assert node.label == "My Agent"

    def test_adds_gate_node(self, builder):
        bp = builder.create_blueprint("bp")
        node = builder.add_node(bp.blueprint_id, "gate", "Compliance Gate")
        assert node.node_type == "gate"

    def test_invalid_node_type_raises(self, builder):
        bp = builder.create_blueprint("bp")
        with pytest.raises(ValueError):
            builder.add_node(bp.blueprint_id, "robot", "Bad Node")

    def test_config_stored(self, builder):
        bp = builder.create_blueprint("bp")
        node = builder.add_node(bp.blueprint_id, "gate", "Gate",
                                config={"requires_human": True})
        assert node.config.get("requires_human") is True

    def test_position_stored(self, builder):
        bp = builder.create_blueprint("bp")
        node = builder.add_node(bp.blueprint_id, "agent", "A",
                                position=(10.0, 20.0))
        assert node.position == (10.0, 20.0)

    def test_to_dict(self, builder):
        bp = builder.create_blueprint("bp")
        node = builder.add_node(bp.blueprint_id, "agent", "A")
        d = node.to_dict()
        assert "node_id" in d
        assert "node_type" in d
        assert "connections" in d


# ---------------------------------------------------------------------------
# connect_nodes
# ---------------------------------------------------------------------------

class TestConnectNodes:
    def test_connects_nodes(self, builder):
        bp = builder.create_blueprint("bp")
        n1 = builder.add_node(bp.blueprint_id, "agent", "A")
        n2 = builder.add_node(bp.blueprint_id, "output", "O")
        result = builder.connect_nodes(bp.blueprint_id, n1.node_id, n2.node_id)
        assert result is True

    def test_edge_appears_in_blueprint(self, builder):
        bp = builder.create_blueprint("bp")
        n1 = builder.add_node(bp.blueprint_id, "agent", "A")
        n2 = builder.add_node(bp.blueprint_id, "output", "O")
        builder.connect_nodes(bp.blueprint_id, n1.node_id, n2.node_id)
        retrieved = builder.get_blueprint(bp.blueprint_id)
        assert (n1.node_id, n2.node_id) in retrieved.edges

    def test_node_connections_list_updated(self, builder):
        bp = builder.create_blueprint("bp")
        n1 = builder.add_node(bp.blueprint_id, "agent", "A")
        n2 = builder.add_node(bp.blueprint_id, "output", "O")
        builder.connect_nodes(bp.blueprint_id, n1.node_id, n2.node_id)
        retrieved = builder.get_blueprint(bp.blueprint_id)
        source = next(n for n in retrieved.nodes if n.node_id == n1.node_id)
        assert n2.node_id in source.connections

    def test_nonexistent_node_returns_false(self, builder):
        bp = builder.create_blueprint("bp")
        n1 = builder.add_node(bp.blueprint_id, "agent", "A")
        result = builder.connect_nodes(bp.blueprint_id, n1.node_id, "fake-node-id")
        assert result is False

    def test_duplicate_edge_not_added(self, builder):
        bp = builder.create_blueprint("bp")
        n1 = builder.add_node(bp.blueprint_id, "agent", "A")
        n2 = builder.add_node(bp.blueprint_id, "output", "O")
        builder.connect_nodes(bp.blueprint_id, n1.node_id, n2.node_id)
        builder.connect_nodes(bp.blueprint_id, n1.node_id, n2.node_id)
        retrieved = builder.get_blueprint(bp.blueprint_id)
        edge_count = sum(
            1 for e in retrieved.edges
            if e == (n1.node_id, n2.node_id)
        )
        assert edge_count == 1


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    def test_recommends_output_node_when_missing(self, builder):
        bp = builder.create_blueprint("no-output")
        builder.add_node(bp.blueprint_id, "agent", "Agent")
        recs = builder.generate_recommendations(bp.blueprint_id)
        titles = [r.title for r in recs]
        assert any("Output" in t for t in titles)

    def test_recommends_hitl_gate_when_missing(self, builder):
        bp = builder.create_blueprint("no-gate")
        builder.add_node(bp.blueprint_id, "agent", "Agent")
        builder.add_node(bp.blueprint_id, "output", "Out")
        recs = builder.generate_recommendations(bp.blueprint_id)
        titles = [r.title for r in recs]
        assert any("HITL" in t for t in titles)

    def test_recommends_compliance_gate(self, builder):
        bp = builder.create_blueprint("no-compliance")
        builder.add_node(bp.blueprint_id, "agent", "Agent")
        recs = builder.generate_recommendations(bp.blueprint_id)
        categories = [r.category for r in recs]
        assert "compliance" in categories

    def test_no_recs_for_nonexistent_blueprint(self, builder):
        recs = builder.generate_recommendations("nonexistent-id-xyz")
        assert recs == []

    def test_returns_list_of_recommendation(self, builder):
        bp = builder.create_blueprint("rec-test")
        recs = builder.generate_recommendations(bp.blueprint_id)
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_to_dict(self, builder):
        bp = builder.create_blueprint("rec-test")
        builder.add_node(bp.blueprint_id, "agent", "A")
        recs = builder.generate_recommendations(bp.blueprint_id)
        assert all("recommendation_id" in r.to_dict() for r in recs)


# ---------------------------------------------------------------------------
# validate_blueprint
# ---------------------------------------------------------------------------

class TestValidateBlueprint:
    def test_valid_blueprint_passes(self, builder):
        bid = _minimal_valid_blueprint(builder)
        result = builder.validate_blueprint(bid)
        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.errors == []

    def test_empty_blueprint_fails(self, builder):
        bp = builder.create_blueprint("empty")
        result = builder.validate_blueprint(bp.blueprint_id)
        assert result.passed is False
        assert len(result.errors) >= 1

    def test_missing_agent_fails(self, builder):
        bp = builder.create_blueprint("no-agent")
        builder.add_node(bp.blueprint_id, "output", "Out")
        result = builder.validate_blueprint(bp.blueprint_id)
        assert result.passed is False
        assert any("agent" in e.lower() for e in result.errors)

    def test_missing_output_fails(self, builder):
        bp = builder.create_blueprint("no-output")
        builder.add_node(bp.blueprint_id, "agent", "Agent")
        result = builder.validate_blueprint(bp.blueprint_id)
        assert result.passed is False
        assert any("output" in e.lower() for e in result.errors)

    def test_missing_hitl_gate_fails(self, builder):
        bp = builder.create_blueprint("no-hitl")
        builder.add_node(bp.blueprint_id, "agent", "Agent")
        builder.add_node(bp.blueprint_id, "output", "Out")
        result = builder.validate_blueprint(bp.blueprint_id)
        assert result.passed is False
        assert any("HITL" in e for e in result.errors)

    def test_has_output_flag(self, builder):
        bid = _minimal_valid_blueprint(builder)
        result = builder.validate_blueprint(bid)
        assert result.has_output_node is True

    def test_has_hitl_gate_flag(self, builder):
        bid = _minimal_valid_blueprint(builder)
        result = builder.validate_blueprint(bid)
        assert result.has_hitl_gate is True

    def test_status_updated_to_valid(self, builder):
        bid = _minimal_valid_blueprint(builder)
        builder.validate_blueprint(bid)
        bp = builder.get_blueprint(bid)
        assert bp.status == "valid"

    def test_status_updated_to_invalid(self, builder):
        bp = builder.create_blueprint("invalid-bp")
        builder.validate_blueprint(bp.blueprint_id)
        bp_fresh = builder.get_blueprint(bp.blueprint_id)
        assert bp_fresh.status == "invalid"

    def test_to_dict(self, builder):
        bid = _minimal_valid_blueprint(builder)
        result = builder.validate_blueprint(bid)
        d = result.to_dict()
        assert "passed" in d
        assert "errors" in d
        assert "has_hitl_gate" in d


# ---------------------------------------------------------------------------
# export_as_spec
# ---------------------------------------------------------------------------

class TestExportAsSpec:
    def test_export_contains_agents(self, builder):
        bid = _minimal_valid_blueprint(builder)
        spec = builder.export_as_spec(bid)
        assert "agents" in spec
        assert len(spec["agents"]) >= 1

    def test_export_contains_gates(self, builder):
        bid = _minimal_valid_blueprint(builder)
        spec = builder.export_as_spec(bid)
        assert "gates" in spec
        assert len(spec["gates"]) >= 1

    def test_export_contains_edges(self, builder):
        bid = _minimal_valid_blueprint(builder)
        spec = builder.export_as_spec(bid)
        assert "edges" in spec
        assert len(spec["edges"]) >= 1

    def test_export_is_json_serialisable(self, builder):
        import json
        bid = _minimal_valid_blueprint(builder)
        spec = builder.export_as_spec(bid)
        json_str = json.dumps(spec)
        parsed = json.loads(json_str)
        assert parsed["blueprint_id"] == bid

    def test_export_unknown_id(self, builder):
        spec = builder.export_as_spec("nonexistent-id-xxx")
        assert "error" in spec


# ---------------------------------------------------------------------------
# import_project
# ---------------------------------------------------------------------------

class TestImportProject:
    def test_returns_project_analysis(self, builder):
        pa = builder.import_project("https://github.com/example/python-api")
        assert isinstance(pa, ProjectAnalysis)
        assert pa.project_id != ""

    def test_detects_python(self, builder):
        pa = builder.import_project("https://github.com/example/python-flask-app")
        assert "python" in pa.languages

    def test_detects_bms_domain(self, builder):
        pa = builder.import_project("https://github.com/example/bacnet-bms-controller")
        assert "bms" in pa.frameworks

    def test_recommends_agents(self, builder):
        pa = builder.import_project("https://github.com/example/django-project")
        assert len(pa.recommended_agents) >= 3

    def test_recommends_hitl_gate(self, builder):
        pa = builder.import_project("https://github.com/example/some-project")
        assert "hitl_gate" in pa.recommended_gates

    def test_complexity_score_in_range(self, builder):
        pa = builder.import_project("https://github.com/example/small-app")
        assert 0.0 <= pa.complexity_score <= 1.0

    def test_recommendations_populated(self, builder):
        pa = builder.import_project("https://github.com/example/api")
        assert len(pa.recommendations) >= 1

    def test_to_dict(self, builder):
        pa = builder.import_project("https://github.com/example/app")
        d = pa.to_dict()
        assert "project_id" in d
        assert "languages" in d
        assert "recommended_agents" in d


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_audit_log_grows(self, builder):
        builder.create_blueprint("Audit Test")
        log = builder.get_audit_log()
        assert len(log) >= 1

    def test_entries_have_action(self, builder):
        builder.create_blueprint("A")
        builder.import_project("https://github.com/example/x")
        log = builder.get_audit_log()
        assert all("action" in e for e in log)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_create_blueprint(self, builder):
        errors = []

        def create():
            try:
                builder.create_blueprint("concurrent-bp")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(builder.list_blueprints()) == 20

    def test_concurrent_validate(self, builder):
        bid = _minimal_valid_blueprint(builder)
        errors = []

        def validate():
            try:
                builder.validate_blueprint(bid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
