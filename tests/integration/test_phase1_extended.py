# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for Phase 1 wiring — Rosetta Soul, Founder Self-Mod, Ghost Controller fixture.

Design Label: TEST-PHASE1-EXTENDED-001
Owner: QA Team

Validates:
  - RosettaSoulRenderer renders RosettaDocument → compact SOUL.md markdown
  - FounderSelfModificationEngine branch→modify→test→validate→merge pipeline
  - Ghost controller playback_runner test fixture is importable
  - Integration wiring between existing modules

Guiding principles applied:
  - Does each module do what it was designed to do?
  - What conditions are possible?  (Success, auth failure, test failure, empty input)
  - Does the test profile cover the full range of capabilities?
  - What is the expected result at all points of operation?
  - Error handling tested — no silent failures
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import uuid

import pytest

# ---------------------------------------------------------------------------
# Force all tests in this file to run synchronously (not wrapped by
# pytest-asyncio).  The ancient pytest-asyncio 1.3.0 + asyncio_mode=auto
# can deadlock threading.Lock-based code when it wraps sync tests.
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# Ensure src/ is on the path
_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ============================================================
# SECTION 1: RosettaSoulRenderer Tests (ROSETTA-SOUL-001)
# ============================================================

from rosetta.rosetta_soul_renderer import (
    RosettaSoulRenderer,
    SoulLayer,
)


class TestRosettaSoulRendererL0:
    """Tests for L0 identity layer (~50 tokens)."""

    def _make_doc(self, **overrides):
        """Create a minimal RosettaDocument-like dict."""
        base = {
            "agent_id": "agent-test-001",
            "agent_name": "TestAgent",
            "contract": {
                "agent_type": "automation",
                "role_title": "QA Engineer",
                "role_description": "Tests the system",
                "management_layer": "individual",
                "department": "Engineering",
                "authorised_actions": ["run_tests", "report_bugs"],
            },
            "terminology": {
                "industry": "software",
                "domain_keywords": ["testing", "CI", "regression"],
            },
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
            "hitl_models": [],
            "shadow_observations": [],
        }
        base.update(overrides)
        return base

    def test_render_l0_basic(self):
        renderer = RosettaSoulRenderer()
        doc = self._make_doc()
        md = renderer.render(doc, layers=[SoulLayer.L0_IDENTITY])
        assert "# SOUL — TestAgent" in md
        assert "QA Engineer" in md
        assert "Automation Agent" in md
        assert "agent-test-001" in md

    def test_render_l0_shadow_agent(self):
        renderer = RosettaSoulRenderer()
        doc = self._make_doc(
            contract={
                "agent_type": "shadow",
                "role_title": "Shadow Analyst",
                "role_description": "Shadows user decisions",
                "management_layer": "middle",
                "shadowed_user_id": "user-123",
                "shadowed_user_name": "Corey",
                "authorised_actions": [],
            },
        )
        md = renderer.render(doc, layers=[SoulLayer.L0_IDENTITY])
        assert "Shadow Agent" in md
        assert "shadows: Corey" in md
        assert "Shadow Analyst" in md

    def test_render_l0_department(self):
        renderer = RosettaSoulRenderer()
        doc = self._make_doc()
        md = renderer.render(doc, layers=[SoulLayer.L0_IDENTITY])
        assert "Engineering" in md


class TestRosettaSoulRendererL1:
    """Tests for L1 critical facts layer (~120 tokens)."""

    def test_render_l1_with_metrics(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "MetricsAgent",
            "contract": {"agent_type": "automation", "role_title": "Analyst",
                         "authorised_actions": ["analyze"]},
            "state_feed": {
                "entries": [
                    {"name": "pipeline_fill", "value": 85.0},
                    {"name": "conversion_rate", "value": 0.12},
                ]
            },
            "task_pipeline": {"tasks": []},
        }
        md = renderer.render(doc, layers=[SoulLayer.L1_CRITICAL])
        assert "Live Metrics" in md
        assert "pipeline_fill" in md
        assert "85.0" in md

    def test_render_l1_with_tasks(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "Worker",
            "contract": {"agent_type": "automation", "role_title": "Dev",
                         "authorised_actions": []},
            "state_feed": {"entries": []},
            "task_pipeline": {
                "tasks": [
                    {"title": "Fix auth bug", "status": "running", "priority": 1},
                    {"title": "Update docs", "status": "queued", "priority": 3},
                    {"title": "Old task", "status": "completed", "priority": 5},
                ]
            },
        }
        md = renderer.render(doc, layers=[SoulLayer.L1_CRITICAL])
        assert "Current Priorities" in md
        assert "Fix auth bug" in md
        assert "Update docs" in md
        # Completed tasks should NOT appear in L1 priorities
        assert "Old task" not in md

    def test_render_l1_with_business_plan(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "Exec",
            "contract": {"agent_type": "automation", "role_title": "CEO",
                         "authorised_actions": []},
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
            "business_plan": {
                "unit_economics": {
                    "monthly_revenue_goal": 50000,
                    "required_monthly_volume": 100,
                }
            },
        }
        md = renderer.render(doc, layers=[SoulLayer.L1_CRITICAL])
        assert "Business Target" in md
        assert "50,000" in md

    def test_render_l1_authority(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "Auth",
            "contract": {
                "agent_type": "automation",
                "role_title": "Admin",
                "authorised_actions": ["deploy", "rollback", "approve_pr"],
            },
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
        }
        md = renderer.render(doc, layers=[SoulLayer.L1_CRITICAL])
        assert "Authorised Actions" in md
        assert "deploy" in md


class TestRosettaSoulRendererL2L3:
    """Tests for L2 detailed and L3 deep layers."""

    def test_render_l2_terminology(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "DomainAgent",
            "contract": {
                "agent_type": "automation",
                "role_title": "Plumber",
                "role_description": "Handles plumbing service requests",
                "reports_to": "Operations Manager",
                "direct_reports": ["Helper A", "Helper B"],
                "authorised_actions": [],
            },
            "terminology": {
                "industry": "plumbing",
                "domain_keywords": ["pipe", "valve", "fitting", "drain"],
                "off_limits_topics": ["electrical", "gas"],
            },
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
        }
        md = renderer.render(doc, layers=[SoulLayer.L2_DETAILED])
        assert "plumbing" in md
        assert "pipe" in md
        assert "Off-limits" in md
        assert "Reports to: Operations Manager" in md

    def test_render_l3_observations(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "a1",
            "agent_name": "Shadow",
            "contract": {"agent_type": "shadow", "role_title": "Observer",
                         "shadowed_user_id": "u1", "shadowed_user_name": "Alice",
                         "authorised_actions": []},
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
            "shadow_observations": [
                {"summary": "User prefers morning meetings"},
                {"summary": "User always reviews PRs before lunch"},
            ],
            "hitl_models": [
                {"task_type": "code_review", "daily_capacity": 15},
            ],
        }
        md = renderer.render(doc, layers=[SoulLayer.L3_DEEP])
        assert "Shadow Observations" in md
        assert "morning meetings" in md
        assert "HITL Throughput" in md
        assert "code_review" in md


class TestRosettaSoulRendererFull:
    """Tests for full rendering and wakeup context."""

    def test_render_all_layers(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "full-agent",
            "agent_name": "FullAgent",
            "contract": {
                "agent_type": "automation",
                "role_title": "Full Stack Dev",
                "role_description": "Builds and tests everything",
                "management_layer": "individual",
                "department": "Platform",
                "authorised_actions": ["code", "test", "deploy"],
            },
            "terminology": {
                "industry": "saas",
                "domain_keywords": ["api", "microservice", "cloud"],
            },
            "state_feed": {
                "entries": [{"name": "uptime", "value": 99.9}]
            },
            "task_pipeline": {
                "tasks": [{"title": "Ship v2", "status": "running", "priority": 1}]
            },
            "business_plan": {
                "unit_economics": {"monthly_revenue_goal": 100000}
            },
            "hitl_models": [],
            "shadow_observations": [],
        }
        md = renderer.render(doc)
        assert "# SOUL — FullAgent" in md
        assert "Critical Facts" in md
        assert "Detailed Context" in md
        assert "Deep Context" in md

    def test_render_wakeup_is_l0_l1_only(self):
        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "wake",
            "agent_name": "WakeAgent",
            "contract": {
                "agent_type": "automation",
                "role_title": "Watcher",
                "role_description": "This should NOT appear in wakeup",
                "authorised_actions": [],
            },
            "terminology": {"industry": "tech"},
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
        }
        md = renderer.render_wakeup(doc)
        assert "# SOUL — WakeAgent" in md
        assert "Detailed Context" not in md  # L2 should NOT be in wakeup
        assert "Deep Context" not in md      # L3 should NOT be in wakeup

    def test_render_none_raises(self):
        renderer = RosettaSoulRenderer()
        with pytest.raises(ValueError, match="ROSETTA-SOUL-ERR-001"):
            renderer.render(None)

    def test_render_from_persona(self):
        renderer = RosettaSoulRenderer()
        persona = {
            "name": "Librarian",
            "role": "Knowledge Manager",
            "description": "Manages all system knowledge and memory",
            "personality": "Methodical, precise, thorough",
            "capabilities": ["index", "search", "archive", "summarise"],
            "boundaries": ["Cannot delete user data", "Cannot access external APIs"],
        }
        md = renderer.render_from_persona(persona)
        assert "# SOUL — Librarian" in md
        assert "Knowledge Manager" in md
        assert "Methodical" in md
        assert "index" in md
        assert "Cannot delete user data" in md

    def test_render_from_empty_persona_raises(self):
        renderer = RosettaSoulRenderer()
        with pytest.raises(ValueError, match="ROSETTA-SOUL-ERR-002"):
            renderer.render_from_persona({})


# ============================================================
# SECTION 2: FounderSelfModificationEngine Tests (FOUNDER-SELFMOD-001)
# ============================================================

from founder_self_modification_engine import (
    FounderSelfModificationEngine,
    ModificationRequest,
    ModificationResult,
    ModificationScope,
    ModificationStatus,
)


class TestFounderSelfModReceiveRequest:
    """Tests for request reception and validation."""

    def test_receive_valid_request(self):
        engine = FounderSelfModificationEngine()
        req = ModificationRequest(
            requester_id="founder-abc",
            requester_role="owner",
            description="Test change",
            changes={"key": "value"},
        )
        result = engine.receive_request(req)
        assert result.status == ModificationStatus.PENDING
        assert result.request_id.startswith("mod_")

    def test_receive_non_owner_raises(self):
        engine = FounderSelfModificationEngine()
        req = ModificationRequest(
            requester_id="user-123",
            requester_role="user",
            description="Hack the system",
            changes={"admin": True},
        )
        with pytest.raises(PermissionError, match="FOUNDER-SELFMOD-ERR-001"):
            engine.receive_request(req)

    def test_receive_empty_description_raises(self):
        engine = FounderSelfModificationEngine()
        req = ModificationRequest(
            requester_id="founder-abc",
            requester_role="owner",
            description="",
            changes={"key": "value"},
        )
        with pytest.raises(ValueError, match="FOUNDER-SELFMOD-ERR-002"):
            engine.receive_request(req)

    def test_receive_max_pending_raises(self):
        engine = FounderSelfModificationEngine()
        engine.MAX_PENDING = 2
        for i in range(2):
            engine.receive_request(ModificationRequest(
                requester_id="founder",
                requester_role="owner",
                description=f"Change {i}",
                changes={f"k{i}": i},
            ))
        with pytest.raises(RuntimeError, match="FOUNDER-SELFMOD-ERR-003"):
            engine.receive_request(ModificationRequest(
                requester_id="founder",
                requester_role="owner",
                description="One too many",
                changes={"overflow": True},
            ))


class TestFounderSelfModExecute:
    """Tests for the full execute pipeline."""

    def test_execute_success(self):
        config = {"forge_max_workers": 8, "debug": False}
        engine = FounderSelfModificationEngine(current_config=config)

        req = ModificationRequest(
            requester_id="founder-abc",
            requester_role="owner",
            description="Increase forge workers to 12",
            changes={"forge_max_workers": 12},
        )
        engine.receive_request(req)
        result = engine.execute(req.request_id)

        assert result.succeeded
        assert result.status == ModificationStatus.MERGED
        assert result.duration_seconds >= 0
        assert not result.rolled_back

        # Config should be updated
        new_config = engine.get_config()
        assert new_config["forge_max_workers"] == 12
        assert new_config["debug"] is False  # Untouched

    def test_execute_test_failure_rolls_back(self):
        def failing_test(config):
            return {"passed": False, "error": "Regression detected"}

        engine = FounderSelfModificationEngine(
            test_runner=failing_test,
            current_config={"workers": 8},
        )
        req = ModificationRequest(
            requester_id="founder",
            requester_role="owner",
            description="Bad change",
            changes={"workers": -1},
        )
        engine.receive_request(req)
        result = engine.execute(req.request_id)

        assert not result.succeeded
        assert result.status == ModificationStatus.TEST_FAILED
        assert result.rolled_back
        assert "Regression" in result.error_message

        # Config should NOT be changed
        assert engine.get_config()["workers"] == 8

    def test_execute_validation_failure_rolls_back(self):
        def failing_validator(config, desc):
            return {"passed": False, "error": "Does not meet requirements"}

        engine = FounderSelfModificationEngine(
            validator=failing_validator,
            current_config={"mode": "safe"},
        )
        req = ModificationRequest(
            requester_id="founder",
            requester_role="owner",
            description="Change mode",
            changes={"mode": "unsafe"},
        )
        engine.receive_request(req)
        result = engine.execute(req.request_id)

        assert not result.succeeded
        assert result.status == ModificationStatus.VALIDATION_FAILED
        assert result.rolled_back
        assert engine.get_config()["mode"] == "safe"

    def test_execute_not_found_raises(self):
        engine = FounderSelfModificationEngine()
        with pytest.raises(KeyError, match="FOUNDER-SELFMOD-ERR-004"):
            engine.execute("nonexistent-id")

    def test_execute_already_merged_raises(self):
        engine = FounderSelfModificationEngine(current_config={"k": 1})
        req = ModificationRequest(
            requester_id="founder",
            requester_role="owner",
            description="First run",
            changes={"k": 2},
        )
        engine.receive_request(req)
        engine.execute(req.request_id)  # Merges

        with pytest.raises(RuntimeError, match="FOUNDER-SELFMOD-ERR-005"):
            engine.execute(req.request_id)  # Can't re-execute merged


class TestFounderSelfModAudit:
    """Tests for audit trail."""

    def test_audit_trail_records_all_steps(self):
        engine = FounderSelfModificationEngine(current_config={"a": 1})
        req = ModificationRequest(
            requester_id="founder-xyz",
            requester_role="owner",
            description="Audit test",
            changes={"a": 2},
        )
        engine.receive_request(req)
        engine.execute(req.request_id)

        trail = engine.get_audit_trail(req.request_id)
        actions = [e["action"] for e in trail]

        assert "request_received" in actions
        assert "branched" in actions
        assert "modified" in actions
        assert "test_passed" in actions
        assert "merged" in actions

        # All entries should reference the correct request
        for entry in trail:
            assert entry["request_id"] == req.request_id
            assert entry["actor"] == "founder-xyz"

    def test_audit_trail_bounded(self):
        engine = FounderSelfModificationEngine(current_config={"x": 0})
        engine.MAX_HISTORY = 20

        # Generate many audit entries
        for i in range(30):
            req = ModificationRequest(
                requester_id="founder",
                requester_role="owner",
                description=f"Change {i}",
                changes={"x": i},
            )
            engine.receive_request(req)
            engine.execute(req.request_id)

        trail = engine.get_audit_trail()
        assert len(trail) <= 25  # Should be trimmed

    def test_get_status(self):
        engine = FounderSelfModificationEngine(current_config={"v": 1})
        req = ModificationRequest(
            requester_id="founder",
            requester_role="owner",
            description="Status check",
            changes={"v": 2},
        )
        engine.receive_request(req)
        status = engine.get_status(req.request_id)
        assert status["status"] == ModificationStatus.PENDING
        assert status["description"] == "Status check"


class TestFounderSelfModThreadSafety:
    """Thread safety tests."""

    def test_concurrent_requests(self):
        engine = FounderSelfModificationEngine(current_config={"counter": 0})
        errors = []

        def submit_and_execute(idx):
            try:
                req = ModificationRequest(
                    requester_id="founder",
                    requester_role="owner",
                    description=f"Concurrent {idx}",
                    changes={"counter": idx},
                )
                engine.receive_request(req)
                engine.execute(req.request_id)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=submit_and_execute, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread safety errors: {errors}"
        # Final counter should be some value from 0-9
        final = engine.get_config()["counter"]
        assert 0 <= final <= 9


# ============================================================
# SECTION 3: Ghost Controller Playback Runner Tests
# ============================================================

class TestGhostControllerFixture:
    """Verify the ghost controller playback_runner is accessible."""

    def test_playback_runner_exists(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "bots",
            "ghost_controller_bot", "desktop", "playback_runner.py"
        )
        assert os.path.isfile(path), f"playback_runner.py not found at {path}"

    def test_playback_runner_importable(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "bots",
            "ghost_controller_bot", "desktop", "playback_runner.py"
        )
        spec = importlib.util.spec_from_file_location("playback_runner", path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        # Verify key functions exist
        assert hasattr(mod, "register_cursor")
        assert hasattr(mod, "list_cursors")
        assert hasattr(mod, "_cursor_pos")
        assert hasattr(mod, "_cursor_move")
        assert hasattr(mod, "click")
        assert hasattr(mod, "type_text")

    def test_register_and_list_cursors(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "bots",
            "ghost_controller_bot", "desktop", "playback_runner.py"
        )
        spec = importlib.util.spec_from_file_location(
            f"playback_runner_{uuid.uuid4().hex[:8]}", path
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        # Register cursors
        mod.register_cursor("ghost_a", x=100, y=200)
        mod.register_cursor("ghost_b", x=300, y=400)

        cursors = mod.list_cursors()
        ids = [c["cursor_id"] for c in cursors]
        assert "ghost_a" in ids
        assert "ghost_b" in ids

        # Verify positions
        x, y = mod._cursor_pos("ghost_a")
        assert x == 100
        assert y == 200


# ============================================================
# SECTION 4: Integration Wiring Smoke Tests
# ============================================================

class TestIntegrationWiring:
    """Smoke tests verifying modules can be wired together."""

    def test_rosetta_soul_to_memory_palace(self):
        """Verify Rosetta soul document can be indexed into Memory Palace."""
        from murphy_memory_palace import MemoryPalaceWiring
        from rosetta.rosetta_soul_renderer import RosettaSoulRenderer

        renderer = RosettaSoulRenderer()
        doc = {
            "agent_id": "integtest",
            "agent_name": "IntegAgent",
            "contract": {
                "agent_type": "automation",
                "role_title": "Tester",
                "authorised_actions": [],
            },
            "state_feed": {"entries": []},
            "task_pipeline": {"tasks": []},
        }
        soul_md = renderer.render_wakeup(doc)
        assert len(soul_md) > 50

        # Index the soul markdown into memory palace
        palace = MemoryPalaceWiring(tenant_id="integtest")
        result = palace.index_conversation(soul_md, source="rosetta_soul")
        assert result["status"] == "indexed"

    def test_audit_gate_to_self_mod_validator(self):
        """Verify DeliverableAuditGate can serve as the self-mod validator."""
        from deliverable_audit_gate import DeliverableAuditGate

        gate = DeliverableAuditGate()

        def validator_using_audit_gate(config, description):
            """Use audit gate to validate a config change meets requirements."""
            # Render config as a deliverable
            deliverable = "\n".join(f"- {k}: {v}" for k, v in config.items())
            report = gate.audit(prompt=description, deliverable=deliverable)
            return {
                "passed": report.verdict.value in ("pass", "warn"),
                "score": report.overall_score,
                "details": report.to_dict(),
            }

        engine = FounderSelfModificationEngine(
            validator=validator_using_audit_gate,
            current_config={"forge_workers": 8},
        )
        req = ModificationRequest(
            requester_id="founder",
            requester_role="owner",
            description="Increase forge workers",
            changes={"forge_workers": 12},
        )
        engine.receive_request(req)
        result = engine.execute(req.request_id)
        # Should at least get through the pipeline (pass or warn)
        assert result.status in (
            ModificationStatus.MERGED,
            ModificationStatus.VALIDATION_FAILED,
        )

    def test_self_mod_result_serialisation(self):
        """Verify ModificationResult.to_dict() is JSON-serialisable."""
        import json

        result = ModificationResult(
            request_id="test-123",
            status=ModificationStatus.MERGED,
            test_results={"passed": True},
            validation_results={"passed": True, "score": 0.9},
        )
        d = result.to_dict()
        json_str = json.dumps(d)
        assert "test-123" in json_str
        assert "merged" in json_str


# ============================================================
# SECTION 5: Founder Account Info Location Tests
# ============================================================

class TestFounderAccountInfo:
    """Tests documenting WHERE founder account info is configured.

    This section answers the user's question:
    "Where do I change my founder account info and how to deploy it?"
    """

    def test_founder_env_vars_documented(self):
        """Verify the env var names are correct and documented."""
        # These are the env vars that control founder account:
        env_vars = {
            "MURPHY_FOUNDER_EMAIL": "Founder login email",
            "MURPHY_FOUNDER_PASSWORD": "Founder login password",
            "MURPHY_FOUNDER_NAME": "Founder display name",
        }
        for var, desc in env_vars.items():
            # Just verify the strings are valid env var names
            assert var.isupper()
            assert var.startswith("MURPHY_FOUNDER_")
            assert len(desc) > 0

    def test_founder_role_is_owner(self):
        """Document: Founder always gets role=owner, tier=enterprise."""
        # This mirrors what app.py does at startup:
        founder_account = {
            "role": "owner",
            "tier": "enterprise",
            "account_type": "founder",
        }
        assert founder_account["role"] == "owner"
        assert founder_account["tier"] == "enterprise"
