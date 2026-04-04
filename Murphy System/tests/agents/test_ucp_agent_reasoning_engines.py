"""Tests for GAP-4: UniversalControlPlane creates AGENT_REASONING sessions
that include DynamicAssistEngine and ShadowKnostalgiaBridge.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _root_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_ucp():
    root = str(_root_path())
    if root not in sys.path:
        sys.path.insert(0, root)
    src = str(_root_path() / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib
    mod = importlib.import_module("universal_control_plane")
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIsolatedSessionAgentReasoningAttributes:
    """GAP-4: IsolatedSession has dynamic_assist_engine and shadow_knostalgia_bridge."""

    def test_isolated_session_has_dynamic_assist_engine_attribute(self):
        mod = _load_ucp()
        session = mod.IsolatedSession(
            session_id="test-001",
            user_id="u1",
            repository_id="r1",
            control_type=mod.ControlType.AGENT_REASONING,
        )
        assert hasattr(session, "dynamic_assist_engine"), (
            "IsolatedSession must have dynamic_assist_engine attribute"
        )

    def test_isolated_session_has_shadow_knostalgia_bridge_attribute(self):
        mod = _load_ucp()
        session = mod.IsolatedSession(
            session_id="test-002",
            user_id="u1",
            repository_id="r1",
            control_type=mod.ControlType.AGENT_REASONING,
        )
        assert hasattr(session, "shadow_knostalgia_bridge"), (
            "IsolatedSession must have shadow_knostalgia_bridge attribute"
        )

    def test_non_agent_reasoning_session_attributes_are_none(self):
        """For non-AGENT_REASONING sessions, new module attrs should be None."""
        mod = _load_ucp()
        session = mod.IsolatedSession(
            session_id="test-003",
            user_id="u1",
            repository_id="r1",
            control_type=mod.ControlType.SENSOR_ACTUATOR,
        )
        assert session.dynamic_assist_engine is None
        assert session.shadow_knostalgia_bridge is None

    def test_agent_reasoning_session_never_raises_on_create(self):
        """Creating an AGENT_REASONING session must not raise even without the PR #195 modules."""
        mod = _load_ucp()
        try:
            session = mod.IsolatedSession(
                session_id="test-004",
                user_id="u1",
                repository_id="r1",
                control_type=mod.ControlType.AGENT_REASONING,
            )
        except Exception as exc:
            pytest.fail(f"Creating AGENT_REASONING session raised: {exc}")


class TestLoadAgentReasoningModulesMethod:
    """GAP-4: IsolatedSession has _load_agent_reasoning_modules() method."""

    def test_method_exists(self):
        mod = _load_ucp()
        session = mod.IsolatedSession(
            session_id="test-005",
            user_id="u1",
            repository_id="r1",
            control_type=mod.ControlType.CONTENT_API,
        )
        assert hasattr(session, "_load_agent_reasoning_modules"), (
            "IsolatedSession must have _load_agent_reasoning_modules()"
        )

    def test_method_does_not_raise(self):
        mod = _load_ucp()
        session = mod.IsolatedSession(
            session_id="test-006",
            user_id="u1",
            repository_id="r1",
            control_type=mod.ControlType.CONTENT_API,
        )
        try:
            session._load_agent_reasoning_modules()
        except Exception as exc:
            pytest.fail(f"_load_agent_reasoning_modules raised: {exc}")


class TestUniversalControlPlaneAgentReasoningSession:
    """GAP-4: UniversalControlPlane.create_automation() creates AGENT_REASONING sessions."""

    def test_create_automation_agent_reasoning_request(self):
        mod = _load_ucp()
        ucp = mod.UniversalControlPlane()
        session_id = ucp.create_automation(
            request="analyze and reason about this complex agent swarm task",
            user_id="test_user",
            repository_id="test_repo",
        )
        assert session_id in ucp.sessions
        session = ucp.sessions[session_id]
        assert session.control_type == mod.ControlType.AGENT_REASONING

    def test_agent_reasoning_session_has_new_module_attributes(self):
        mod = _load_ucp()
        ucp = mod.UniversalControlPlane()
        session_id = ucp.create_automation(
            request="research and analyze complex multi-agent reasoning",
            user_id="u2",
            repository_id="r2",
        )
        session = ucp.sessions[session_id]
        assert session.control_type == mod.ControlType.AGENT_REASONING
        assert hasattr(session, "dynamic_assist_engine")
        assert hasattr(session, "shadow_knostalgia_bridge")

    def test_agent_reasoning_session_can_execute(self):
        """An AGENT_REASONING session must be able to run end-to-end without crashing."""
        mod = _load_ucp()
        ucp = mod.UniversalControlPlane()
        session_id = ucp.create_automation(
            request="reason and analyze a complex swarm agent network",
            user_id="u3",
            repository_id="r3",
        )
        result = ucp.run_automation(session_id)
        assert isinstance(result, dict)
        # Should not be an error dict
        assert result.get("error") != "Session not found"
