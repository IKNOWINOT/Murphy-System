# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for ExecutionGateway (execution_gateway.py).

Validates:
  - OBSERVER mode blocks execution
  - SUGGESTION mode produces proposals without executing
  - SUPERVISED mode produces proposals (waits for approval)
  - AUTONOMOUS mode executes after passing governance/safety checks
  - Governance kernel blocks unsafe operations
  - Emergency stop halts all operations
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from copilot_tenant.execution_gateway import ExecutionGateway, ExecutionResult, Proposal
from copilot_tenant.task_planner import PlannedTask
from copilot_tenant.tenant_agent import CopilotTenantMode


def _task(**kwargs) -> PlannedTask:
    kwargs.setdefault("description", "test action")
    return PlannedTask(**kwargs)


class TestExecutionGateway:
    def test_instantiation(self) -> None:
        gw = ExecutionGateway()
        assert gw is not None

    def test_observer_mode_blocks(self) -> None:
        gw    = ExecutionGateway()
        task  = _task()
        result = gw.execute(task, CopilotTenantMode.OBSERVER)
        assert result.status == "blocked"
        assert result.blocked_reason == "observer_mode"

    def test_suggestion_mode_produces_proposal(self) -> None:
        gw    = ExecutionGateway()
        task  = _task()
        result = gw.execute(task, CopilotTenantMode.SUGGESTION)
        assert result.status == "proposed"
        assert result.proposal_id is not None

    def test_supervised_mode_produces_proposal(self) -> None:
        gw    = ExecutionGateway()
        task  = _task()
        result = gw.execute(task, CopilotTenantMode.SUPERVISED)
        assert result.status == "proposed"

    def test_autonomous_mode_executes(self) -> None:
        gw    = ExecutionGateway()
        task  = _task()
        result = gw.execute(task, CopilotTenantMode.AUTONOMOUS)
        # Without governance/safety modules, should execute
        assert result.status == "executed"

    def test_autonomous_blocked_by_governance(self) -> None:
        gw = ExecutionGateway()
        governance_mock = MagicMock()
        governance_mock.evaluate = MagicMock(return_value=False)
        gw._governance = governance_mock
        task   = _task()
        result = gw.execute(task, CopilotTenantMode.AUTONOMOUS)
        assert result.status == "blocked"
        assert "governance" in result.blocked_reason

    def test_autonomous_blocked_by_safety(self) -> None:
        gw = ExecutionGateway()
        safety_mock = MagicMock()
        safety_mock.check = MagicMock(return_value=False)
        gw._safety = safety_mock
        task   = _task()
        result = gw.execute(task, CopilotTenantMode.AUTONOMOUS)
        assert result.status == "blocked"
        assert "safety" in result.blocked_reason

    def test_emergency_stop_blocks_all_modes(self) -> None:
        gw = ExecutionGateway()
        gw.emergency_stop()
        task = _task()
        for mode in CopilotTenantMode:
            result = gw.execute(task, mode)
            assert result.status == "blocked"
            assert result.blocked_reason == "emergency_stop_active"

    def test_emergency_stop_reset_allows_execution(self) -> None:
        gw = ExecutionGateway()
        gw.emergency_stop()
        gw.reset_emergency_stop()
        task   = _task()
        result = gw.execute(task, CopilotTenantMode.AUTONOMOUS)
        assert result.status == "executed"


class TestProposal:
    def test_propose_returns_proposal(self) -> None:
        gw       = ExecutionGateway()
        task     = _task(description="write blog post")
        proposal = gw.propose(task)
        assert isinstance(proposal, Proposal)
        assert proposal.description == "write blog post"
        assert proposal.proposal_id

    def test_propose_sets_task_id(self) -> None:
        gw   = ExecutionGateway()
        task = PlannedTask(task_id="my-task-123", description="test")
        prop = gw.propose(task)
        assert prop.task_id == "my-task-123"


class TestExecutionResult:
    def test_default_result(self) -> None:
        r = ExecutionResult()
        assert r.status == "pending"
        assert r.result_id

    def test_executed_result(self) -> None:
        r = ExecutionResult(task_id="t1", status="executed", output={"key": "val"})
        assert r.output["key"] == "val"
