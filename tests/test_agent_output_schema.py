# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for the Murphy universal agent schema + all production agents.

Design Label: TEST-MURPHY-AGENTS-001
Owner: QA Team

Covers:
  - AgentOutput schema: valid construction, validators, factories, serialisation
  - Rosetta org lookup: authority resolution, empty/malformed org chart, BAT seal
  - Rosetta state hash: consistency, change detection
  - ManifestAgent: valid manifest, missing field FAIL, Rosetta snapshot
  - RosettaAgent: vote success, vote failure blocks, conflict resolution, propagation
  - LyapunovAgent: stable, drift alert, critical alert triggers HITL
  - RecommissionAgent: dependent re-test, failure returns FAIL, silent pass impossible
  - RenderAgent: routing table, unknown type FAIL
  - PackageAgent: CI fail blocks, CI pass proceeds, smoke failure FAIL
  - Schema enforcer middleware: valid pass-through, invalid rejection

Guiding principles applied:
  - Does each module do what it was designed to do? → Verified per test
  - What conditions are possible? → Success, auth failure, missing data, drift
  - Error handling? → Every error surfaces in AgentOutput.error — never silent
  - Does the test profile reflect the full range? → All branches covered
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime

import pytest

# Ensure murphy package is importable
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


# ===========================================================================
# SECTION 1: AgentOutput Schema Tests  (MURPHY-SCHEMA-TEST-001)
# ===========================================================================

from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType


class TestAgentOutputValid:
    """Valid construction of AgentOutput."""

    def test_minimal_valid(self):
        """All required fields present → succeeds."""
        out = AgentOutput(
            agent_id="test-001",
            agent_name="TestAgent",
            file_path="output/main.py",
            content_type=ContentType.CODE,
            content="print('hello')",
            org_node_id="eng-team",
            rosetta_state_hash="abc123def456",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        assert out.agent_id == "test-001"
        assert out.content_type == ContentType.CODE
        assert out.schema_version == "1.0.0"
        assert out.error is None
        assert out.hitl_required is False

    def test_pass_fail_pass(self):
        """content_type=pass_fail with content=PASS → valid."""
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.PASS_FAIL, content="PASS",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        assert out.content == "PASS"

    def test_pass_fail_fail(self):
        """content_type=pass_fail with content=FAIL → valid."""
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.PASS_FAIL, content="FAIL",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        assert out.content == "FAIL"

    def test_hitl_with_authority(self):
        """hitl_required=True with hitl_authority_node_id set → valid."""
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="x",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
            hitl_required=True,
            hitl_authority_node_id="exec-node",
        )
        assert out.hitl_authority_node_id == "exec-node"

    def test_schema_version_present(self):
        """schema_version defaults to 1.0.0."""
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="x",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        assert out.schema_version == "1.0.0"

    def test_timestamp_auto_set(self):
        """timestamp is auto-set to current UTC."""
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="x",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        assert isinstance(out.timestamp, datetime)


class TestAgentOutputValidators:
    """Validator enforcement on AgentOutput."""

    def test_hitl_required_missing_authority_raises(self):
        """hitl_required=True without hitl_authority_node_id → ValueError."""
        with pytest.raises(ValueError, match="MURPHY-SCHEMA-ERR-001"):
            AgentOutput(
                agent_id="t", agent_name="T", file_path="f",
                content_type=ContentType.CODE, content="x",
                org_node_id="n", rosetta_state_hash="h",
                render_type=RenderType.SYNTAX_HIGHLIGHT,
                hitl_required=True,
                hitl_authority_node_id=None,
            )

    def test_pass_fail_invalid_content_raises(self):
        """content_type=pass_fail with content not PASS/FAIL → ValueError."""
        with pytest.raises(ValueError, match="MURPHY-SCHEMA-ERR-002"):
            AgentOutput(
                agent_id="t", agent_name="T", file_path="f",
                content_type=ContentType.PASS_FAIL, content="MAYBE",
                org_node_id="n", rosetta_state_hash="h",
                render_type=RenderType.SYNTAX_HIGHLIGHT,
            )


class TestAgentOutputFromError:
    """from_error factory tests."""

    def test_from_error_basic(self):
        """from_error produces valid FAIL AgentOutput."""
        out = AgentOutput.from_error(
            agent_id="err-agent",
            agent_name="ErrorAgent",
            file_path="output/broken.py",
            org_node_id="eng-team",
            error_message="Something broke",
        )
        assert out.content == "FAIL"
        assert out.content_type == ContentType.PASS_FAIL
        assert out.error == "Something broke"
        assert out.bat_seal_required is True

    def test_from_error_serialises(self):
        """from_error output can be serialised to JSON and back."""
        out = AgentOutput.from_error(
            agent_id="e", agent_name="E", file_path="f",
            org_node_id="n", error_message="msg",
        )
        j = out.to_json()
        restored = AgentOutput.from_json(j)
        assert restored.error == "msg"


class TestAgentOutputSerialization:
    """JSON round-trip tests."""

    def test_round_trip(self):
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="hello",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        j = out.to_json()
        restored = AgentOutput.from_json(j)
        assert restored.agent_id == "t"
        assert restored.content == "hello"


# ===========================================================================
# SECTION 2: Rosetta Org Lookup Tests  (ROSETTA-ORG-TEST-001)
# ===========================================================================

from murphy.rosetta.org_lookup import (
    OrgChartLookupError,
    BATSealError,
    resolve_hitl_authority,
    get_rosetta_state_hash,
    set_bat_recorder,
    set_rosetta_state_provider,
)


def _make_org_chart(*node_types):
    """Helper: make an org chart with nodes of given types."""
    return {
        "nodes": [
            {"node_id": f"{t}-node-001", "type": t, "name": f"{t} Node"}
            for t in node_types
        ],
    }


FULL_ORG_CHART = _make_org_chart(
    "executive", "department_head", "team_lead", "direct_manager",
)


class TestResolveHITLAuthority:
    """resolve_hitl_authority with valid org charts."""

    def setup_method(self):
        """Wire a mock BAT recorder."""
        self._bat_calls = []
        set_bat_recorder(lambda **kw: self._bat_calls.append(kw))

    def teardown_method(self):
        set_bat_recorder(None)

    def test_critical_resolves_executive(self):
        result = resolve_hitl_authority("deploy", "critical", FULL_ORG_CHART)
        assert result == "executive-node-001"

    def test_high_resolves_dept_head(self):
        result = resolve_hitl_authority("config_change", "high", FULL_ORG_CHART)
        assert result == "department_head-node-001"

    def test_medium_resolves_team_lead(self):
        result = resolve_hitl_authority("code_review", "medium", FULL_ORG_CHART)
        assert result == "team_lead-node-001"

    def test_low_resolves_direct_manager(self):
        result = resolve_hitl_authority("minor_fix", "low", FULL_ORG_CHART)
        assert result == "direct_manager-node-001"

    def test_bat_seal_recorded(self):
        resolve_hitl_authority("deploy", "critical", FULL_ORG_CHART)
        assert len(self._bat_calls) == 1
        assert "hitl_authority_resolved" in self._bat_calls[0]["action"]


class TestResolveHITLAuthorityErrors:
    """resolve_hitl_authority error paths."""

    def setup_method(self):
        set_bat_recorder(lambda **kw: None)

    def teardown_method(self):
        set_bat_recorder(None)

    def test_empty_org_chart_raises(self):
        with pytest.raises(OrgChartLookupError, match="ROSETTA-ORG-ERR-001"):
            resolve_hitl_authority("deploy", "critical", {})

    def test_malformed_org_chart_no_nodes_raises(self):
        with pytest.raises(OrgChartLookupError, match="ROSETTA-ORG-ERR-003"):
            resolve_hitl_authority("deploy", "critical", {"nodes": []})

    def test_malformed_org_chart_wrong_type_raises(self):
        with pytest.raises(OrgChartLookupError, match="ROSETTA-ORG-ERR-002"):
            resolve_hitl_authority("deploy", "critical", "not_a_dict")  # type: ignore

    def test_invalid_risk_level_raises(self):
        with pytest.raises(OrgChartLookupError, match="ROSETTA-ORG-ERR-004"):
            resolve_hitl_authority("deploy", "unknown_risk", FULL_ORG_CHART)

    def test_missing_node_type_raises(self):
        """Org chart missing the required node type."""
        partial_chart = _make_org_chart("team_lead")  # No executive
        with pytest.raises(OrgChartLookupError, match="ROSETTA-ORG-ERR-004"):
            resolve_hitl_authority("deploy", "critical", partial_chart)

    def test_bat_seal_failure_raises(self):
        def failing_recorder(**kw):
            raise RuntimeError("BAT down")
        set_bat_recorder(failing_recorder)
        with pytest.raises(BATSealError, match="ROSETTA-ORG-ERR-006"):
            resolve_hitl_authority("deploy", "critical", FULL_ORG_CHART)


class TestRosettaStateHash:
    """get_rosetta_state_hash tests."""

    def test_consistent_for_same_state(self):
        state = {"agents": {"a1": {"status": "running"}}}
        set_rosetta_state_provider(lambda: state)
        h1 = get_rosetta_state_hash()
        h2 = get_rosetta_state_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex
        set_rosetta_state_provider(None)

    def test_different_for_changed_state(self):
        set_rosetta_state_provider(lambda: {"v": 1})
        h1 = get_rosetta_state_hash()
        set_rosetta_state_provider(lambda: {"v": 2})
        h2 = get_rosetta_state_hash()
        assert h1 != h2
        set_rosetta_state_provider(None)

    def test_returns_hash_when_no_provider(self):
        set_rosetta_state_provider(None)
        h = get_rosetta_state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ===========================================================================
# SECTION 3: ManifestAgent Tests  (MANIFEST-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.manifest_agent import ManifestAgent


class TestManifestAgent:
    """ManifestAgent tests."""

    def setup_method(self):
        set_bat_recorder(lambda **kw: None)
        set_rosetta_state_provider(lambda: {"test": True})

    def teardown_method(self):
        set_bat_recorder(None)
        set_rosetta_state_provider(None)

    def test_valid_manifest(self):
        agent = ManifestAgent()
        out = agent.run(
            normalized_request={"description": "Build a web app"},
            deliverable_type="web_app",
            tech_stack=["python"],
            org_chart=FULL_ORG_CHART,
        )
        assert out.content_type == ContentType.JSON_MANIFEST
        assert out.error is None
        manifest = json.loads(out.content)
        assert isinstance(manifest, list)
        assert len(manifest) >= 3  # main + README + test at minimum

    def test_missing_field_returns_fail(self):
        agent = ManifestAgent()
        # Monkey-patch _build_manifest to return entries with missing fields
        agent._build_manifest = lambda *a: [{"file_path": "x.py"}]  # Missing many fields
        out = agent.run(
            normalized_request={}, deliverable_type="test",
            tech_stack=["python"], org_chart=FULL_ORG_CHART,
        )
        assert out.content == "FAIL"
        assert "MANIFEST-ERR-002" in (out.error or "")

    def test_rosetta_snapshot_emitted(self):
        agent = ManifestAgent()
        out = agent.run(
            normalized_request={"description": "test"},
            deliverable_type="test", tech_stack=["python"],
            org_chart=FULL_ORG_CHART,
        )
        assert len(out.rosetta_state_hash) == 64


# ===========================================================================
# SECTION 4: RosettaAgent Tests  (ROSETTA-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.rosetta_agent import RosettaAgent


class TestRosettaAgentVote:
    """RosettaAgent vote tests."""

    def test_vote_success(self):
        agent = RosettaAgent()
        states = [
            {"agent_id": "a1", "state_hash": "h1", "agrees": True},
            {"agent_id": "a2", "state_hash": "h2", "agrees": True},
        ]
        assert agent.vote(states) is True

    def test_vote_failure_blocks(self):
        agent = RosettaAgent()
        states = [
            {"agent_id": "a1", "state_hash": "h1", "agrees": True},
            {"agent_id": "a2", "state_hash": "h2", "agrees": False},
        ]
        assert agent.vote(states) is False

    def test_vote_empty_fails(self):
        agent = RosettaAgent()
        assert agent.vote([]) is False

    def test_run_vote_failure_returns_fail(self):
        set_rosetta_state_provider(lambda: {"t": 1})
        agent = RosettaAgent()
        out = agent.run(
            manifest_state={},
            agent_states=[{"agent_id": "a1", "agrees": False}],
            org_chart=FULL_ORG_CHART,
        )
        assert out.content == "FAIL"
        assert "vote failed" in (out.error or "").lower()
        set_rosetta_state_provider(None)


class TestRosettaAgentConflict:
    """RosettaAgent conflict resolution tests."""

    def _make_output(self, name, confidence):
        return AgentOutput(
            agent_id=f"agent-{name}",
            agent_name=name,
            file_path="f.py",
            content_type=ContentType.JSON_MANIFEST,
            content=json.dumps({"confidence_score": confidence}),
            org_node_id="n",
            rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )

    def test_higher_confidence_wins(self):
        agent = RosettaAgent()
        a = self._make_output("A", 0.9)
        b = self._make_output("B", 0.3)
        winner, loser = agent.resolve_conflict(a, b)
        assert winner.agent_name == "A"
        assert loser.content == "FAIL"
        assert "retry" in (loser.error or "").lower()


class TestRosettaAgentPropagation:
    """RosettaAgent change propagation tests."""

    def test_successful_propagation(self):
        agent = RosettaAgent()
        agents = [lambda d: True, lambda d: True]
        assert agent.propagate_change({"key": "val"}, agents) is True

    def test_failed_propagation_triggers_rollback(self):
        rollback_called = []
        def agent_ok(d):
            if d.get("_rollback"):
                rollback_called.append(True)
            return True
        def agent_fail(d):
            return False
        agent = RosettaAgent()
        assert agent.propagate_change({"key": "val"}, [agent_ok, agent_fail]) is False
        assert len(rollback_called) == 1  # First agent was rolled back


# ===========================================================================
# SECTION 5: LyapunovAgent Tests  (LYAPUNOV-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.lyapunov_agent import LyapunovAgent, STABLE_THRESHOLD, CRITICAL_THRESHOLD


class TestLyapunovAgent:
    """LyapunovAgent stability tests."""

    def setup_method(self):
        set_bat_recorder(lambda **kw: None)
        set_rosetta_state_provider(lambda: {"lyapunov": True})

    def teardown_method(self):
        set_bat_recorder(None)
        set_rosetta_state_provider(None)

    def test_stable_telemetry(self):
        """No drift → score >= 0.7."""
        agent = LyapunovAgent()
        telemetry = [
            {"name": "cpu", "value": 50},
            {"name": "mem", "value": 60},
        ]
        baseline = {"metrics": {"cpu": 50, "mem": 60}}
        out = agent.run(telemetry, baseline)
        report = json.loads(out.content)
        assert report["stability_score"] >= STABLE_THRESHOLD
        assert report["alert_level"] == "stable"
        assert out.hitl_required is False

    def test_drift_triggers_warning(self):
        """Moderate drift → warning alert."""
        agent = LyapunovAgent()
        telemetry = [
            {"name": "cpu", "value": 80},  # 60% drift from 50
            {"name": "mem", "value": 90},  # 50% drift from 60
        ]
        baseline = {"metrics": {"cpu": 50, "mem": 60}}
        out = agent.run(telemetry, baseline)
        report = json.loads(out.content)
        assert report["stability_score"] < STABLE_THRESHOLD
        assert report["alert_level"] in ("warning", "critical")

    def test_critical_drift_triggers_hitl(self):
        """Extreme drift → critical alert with HITL required."""
        agent = LyapunovAgent()
        telemetry = [
            {"name": "cpu", "value": 200},  # 300% drift from 50
            {"name": "mem", "value": 300},  # 400% drift from 60
        ]
        baseline = {"metrics": {"cpu": 50, "mem": 60}}
        out = agent.run(telemetry, baseline, org_chart=FULL_ORG_CHART)
        report = json.loads(out.content)
        assert report["stability_score"] < CRITICAL_THRESHOLD
        assert report["alert_level"] == "critical"
        assert out.hitl_required is True
        assert out.hitl_authority_node_id is not None


# ===========================================================================
# SECTION 6: RecommissionAgent Tests  (RECOMMISSION-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.recommission_agent import RecommissionAgent


class TestRecommissionAgent:
    """RecommissionAgent tests."""

    def setup_method(self):
        set_bat_recorder(lambda **kw: None)
        set_rosetta_state_provider(lambda: {"recom": True})

    def teardown_method(self):
        set_bat_recorder(None)
        set_rosetta_state_provider(None)

    def test_all_pass(self):
        """All tests pass → success AgentOutput."""
        def runner(fp):
            return {"passed": True, "details": "OK"}
        agent = RecommissionAgent()
        out = agent.run("main.py", ["util.py"], {}, test_runner=runner)
        assert out.content_type == ContentType.TEST_SUITE
        assert out.error is None

    def test_failure_returns_fail(self):
        """One test fails → FAIL AgentOutput listing the failure."""
        def runner(fp):
            return {"passed": fp != "util.py", "details": "failed" if fp == "util.py" else "ok"}
        agent = RecommissionAgent()
        out = agent.run("main.py", ["util.py"], {}, test_runner=runner)
        assert out.content == "FAIL"
        assert "util.py" in (out.error or "")

    def test_no_runner_returns_fail(self):
        """No test runner wired → FAIL."""
        agent = RecommissionAgent()
        out = agent.run("main.py", [], {})
        assert out.content == "FAIL"
        assert "RECOMMISSION-ERR-001" in (out.error or "")

    def test_runner_exception_returns_fail(self):
        """Test runner raises → FAIL."""
        def runner(fp):
            raise RuntimeError("test runner crashed")
        agent = RecommissionAgent()
        out = agent.run("main.py", [], {}, test_runner=runner)
        assert out.content == "FAIL"


# ===========================================================================
# SECTION 7: RenderAgent Tests  (RENDER-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.render_agent import RenderAgent, _RENDER_ROUTES


class TestRenderAgent:
    """RenderAgent routing tests."""

    def setup_method(self):
        set_rosetta_state_provider(lambda: {"render": True})

    def teardown_method(self):
        set_rosetta_state_provider(None)

    def _make_upstream(self, content_type, render_type=RenderType.SYNTAX_HIGHLIGHT):
        return AgentOutput(
            agent_id="upstream-001",
            agent_name="UpstreamAgent",
            file_path="output/file",
            content_type=content_type,
            content="test content",
            org_node_id="eng",
            rosetta_state_hash="hash",
            render_type=render_type,
        )

    def test_svg_routes_to_diagram(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.SVG))
        assert out.render_type == RenderType.DIAGRAM

    def test_html_routes_to_widget(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.HTML))
        assert out.render_type == RenderType.WIDGET

    def test_zip_routes_to_download(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.ZIP))
        assert out.render_type == RenderType.DOWNLOAD

    def test_pdf_routes_to_document(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.PDF))
        assert out.render_type == RenderType.DOCUMENT

    def test_code_routes_to_syntax_highlight(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.CODE))
        assert out.render_type == RenderType.SYNTAX_HIGHLIGHT

    def test_chart_routes_to_data_viz(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.CHART))
        assert out.render_type == RenderType.DATA_VIZ

    def test_matrix_message_routes_to_message(self):
        agent = RenderAgent()
        out = agent.run(self._make_upstream(ContentType.MATRIX_MESSAGE))
        assert out.render_type == RenderType.MESSAGE

    def test_all_content_types_have_routes(self):
        """Every ContentType must have a route — no gaps."""
        for ct in ContentType:
            assert ct in _RENDER_ROUTES, f"Missing route for {ct}"


# ===========================================================================
# SECTION 8: PackageAgent Tests  (PACKAGE-AGENT-TEST-001)
# ===========================================================================

from murphy.agents.package_agent import PackageAgent


class TestPackageAgent:
    """PackageAgent tests."""

    def setup_method(self):
        set_rosetta_state_provider(lambda: {"pkg": True})

    def teardown_method(self):
        set_rosetta_state_provider(None)

    def _make_manifest(self):
        return [
            AgentOutput(
                agent_id="src-001", agent_name="SourceAgent",
                file_path="output/main.py", content_type=ContentType.CODE,
                content="print('hello')", org_node_id="eng",
                rosetta_state_hash="h", render_type=RenderType.SYNTAX_HIGHLIGHT,
            ),
        ]

    def test_ci_fail_blocks_packaging(self):
        """ci_status != PASS → immediate FAIL."""
        agent = PackageAgent()
        out = agent.run(self._make_manifest(), ci_status="FAIL")
        assert out.content == "FAIL"
        assert "PACKAGE-ERR-002" in (out.error or "")

    def test_ci_pass_proceeds(self):
        """ci_status == PASS → zip produced (skip smoke for test isolation)."""
        agent = PackageAgent()
        out = agent.run(self._make_manifest(), ci_status="PASS", skip_smoke=True)
        assert out.content_type == ContentType.ZIP
        assert out.error is None
        # Content is base64-encoded zip
        import base64
        raw = base64.b64decode(out.content)
        assert raw[:2] == b"PK"  # ZIP magic bytes

    def test_smoke_failure_returns_fail(self):
        """Smoke test failure → FAIL with output in error field."""
        agent = PackageAgent()
        # Monkey-patch the smoke runner to fail
        agent._run_smoke_test = lambda code: {"passed": False, "output": "process crashed"}
        out = agent.run(self._make_manifest(), ci_status="PASS")
        assert out.content == "FAIL"
        assert "PACKAGE-ERR-003" in (out.error or "")


# ===========================================================================
# SECTION 9: Schema Enforcer Middleware Tests  (SCHEMA-ENFORCE-TEST-001)
# ===========================================================================

from murphy.middleware.schema_enforcer import (
    SchemaEnforcementError,
    enforce_schema,
    validate_agent_message,
    validate_all_outputs,
)


class TestSchemaEnforcer:
    """Schema enforcement middleware tests."""

    def test_valid_agentoutput_passes(self):
        out = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="x",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        validated = validate_agent_message(out)
        assert validated.agent_id == "t"

    def test_valid_dict_passes(self):
        d = {
            "agent_id": "t", "agent_name": "T", "file_path": "f",
            "content_type": "code", "content": "x",
            "org_node_id": "n", "rosetta_state_hash": "h",
            "render_type": "syntax_highlight",
        }
        validated = validate_agent_message(d)
        assert validated.agent_id == "t"

    def test_invalid_dict_raises(self):
        with pytest.raises(SchemaEnforcementError, match="SCHEMA-ENFORCE-ERR-001"):
            validate_agent_message({"bad": "data"})

    def test_invalid_type_raises(self):
        with pytest.raises(SchemaEnforcementError, match="SCHEMA-ENFORCE-ERR-002"):
            validate_agent_message(42)

    def test_enforce_schema_decorator(self):
        @enforce_schema
        def good_agent():
            return AgentOutput(
                agent_id="t", agent_name="T", file_path="f",
                content_type=ContentType.CODE, content="x",
                org_node_id="n", rosetta_state_hash="h",
                render_type=RenderType.SYNTAX_HIGHLIGHT,
            )
        out = good_agent()
        assert out.agent_id == "t"

    def test_enforce_schema_catches_bad_return(self):
        @enforce_schema
        def bad_agent():
            return {"not": "an agent output"}
        out = bad_agent()
        assert out.content == "FAIL"  # SchemaEnforcer returns FAIL

    def test_enforce_schema_catches_exception(self):
        @enforce_schema
        def crashing_agent():
            raise RuntimeError("boom")
        out = crashing_agent()
        assert out.content == "FAIL"
        assert "SCHEMA-ENFORCE-ERR-003" in (out.error or "")

    def test_validate_all_outputs(self):
        good = AgentOutput(
            agent_id="t", agent_name="T", file_path="f",
            content_type=ContentType.CODE, content="x",
            org_node_id="n", rosetta_state_hash="h",
            render_type=RenderType.SYNTAX_HIGHLIGHT,
        )
        valid, errors = validate_all_outputs([good, {"bad": "data"}])
        assert len(valid) == 1
        assert len(errors) == 1
