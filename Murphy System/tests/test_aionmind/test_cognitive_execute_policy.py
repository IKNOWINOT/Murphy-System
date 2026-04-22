"""Tests for the Phase-1 additions to ``AionMindKernel.cognitive_execute``.

Covers:
- ``metadata`` kwarg flows into the resulting ``ContextObject``.
- ``actor`` kwarg is recorded on every ``OrchestrationState`` audit entry.
- ``max_auto_approve_risk`` honors the role+risk policy (owner can
  auto-approve MEDIUM; default behavior still gates MEDIUM behind
  human approval).
"""

from __future__ import annotations

import pytest

from aionmind.capability_registry import Capability
from aionmind.models.context_object import RiskLevel
from aionmind.runtime_kernel import AionMindKernel, _risk_le


def _kernel_with_handler() -> AionMindKernel:
    kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
    kernel.register_capability(
        Capability(
            capability_id="cap-x",
            name="exec-x",
            provider="bot-x",
            tags=["general"],
        )
    )
    kernel.register_handler("cap-x", lambda node: {"ok": True})
    return kernel


class TestRiskOrdering:
    def test_low_le_medium(self):
        assert _risk_le(RiskLevel.LOW, RiskLevel.MEDIUM)
        assert _risk_le(RiskLevel.MEDIUM, RiskLevel.MEDIUM)
        assert not _risk_le(RiskLevel.HIGH, RiskLevel.MEDIUM)
        assert not _risk_le(RiskLevel.CRITICAL, RiskLevel.LOW)


class TestCognitiveExecuteIdentity:
    def test_metadata_threads_into_context(self):
        kernel = _kernel_with_handler()
        result = kernel.cognitive_execute(
            source="user:cpost@murphy.systems",
            raw_input="diagnostic ping",
            auto_approve=True,
            approver="cpost@murphy.systems",
            metadata={"founder": True, "user_email": "cpost@murphy.systems"},
            actor="cpost@murphy.systems",
        )
        assert result["status"] != "no_candidates"
        ctx_id = result["context_id"]
        ctx = kernel.memory.retrieve_context(f"ctx:{ctx_id}")
        assert ctx is not None
        meta = ctx.get("metadata", {})
        assert meta.get("founder") is True
        assert meta.get("user_email") == "cpost@murphy.systems"
        assert meta.get("actor") == "cpost@murphy.systems"

    def test_actor_appears_in_audit_trail(self):
        kernel = _kernel_with_handler()
        result = kernel.cognitive_execute(
            source="user:cpost@murphy.systems",
            raw_input="diagnostic ping",
            auto_approve=True,
            approver="cpost@murphy.systems",
            actor="cpost@murphy.systems",
        )
        # The kernel only returns audit entries when the graph executed.
        assert result.get("status") in {"completed", "running", "awaiting_approval"}
        audit = result.get("audit_trail") or []
        assert audit, "expected at least one audit entry"
        # Every entry should record the initiating actor.
        actors = {entry["details"].get("actor") for entry in audit}
        assert actors == {"cpost@murphy.systems"}


class TestCognitiveExecutePolicy:
    def test_default_blocks_medium_auto_approve(self):
        """Default ceiling (LOW) must still require approval for MEDIUM."""
        kernel = _kernel_with_handler()
        result = kernel.cognitive_execute(
            source="api:anonymous",
            raw_input="deploy v2",
            task_type="deployment",  # mapped to MEDIUM in cognitive_execute
            auto_approve=True,  # but policy ceiling is LOW by default
            approver="anonymous",
        )
        assert result["status"] == "pending_approval"

    def test_owner_ceiling_auto_approves_medium(self):
        """Raising the ceiling to MEDIUM lets owners self-approve MEDIUM tasks."""
        kernel = _kernel_with_handler()
        result = kernel.cognitive_execute(
            source="user:cpost@murphy.systems",
            raw_input="deploy v2",
            task_type="deployment",  # MEDIUM
            auto_approve=True,
            approver="cpost@murphy.systems",
            actor="cpost@murphy.systems",
            max_auto_approve_risk=RiskLevel.MEDIUM,
        )
        # Should now flow past the approval gate and execute (or at
        # least reach a non-pending status).
        assert result["status"] != "pending_approval"
