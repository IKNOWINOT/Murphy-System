"""
Tests for the Multi-Agent Coordinator (MAC-001..MAC-003).

Covers: decomposition, parallel execution, merge strategies,
conflict resolution, Murphy Validation, and error handling.
"""

from __future__ import annotations

import asyncio

import pytest

from src.multi_agent_coordinator.models import (
    CoordinationStatus,
    MergeStrategy,
    SubTask,
    SubTaskResult,
    SubTaskStatus,
    TaskDecomposition,
)
from src.multi_agent_coordinator.coordinator import TeamCoordinator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def coordinator():
    return TeamCoordinator(murphy_threshold=0.7)


def make_executor(output: dict, confidence: float = 0.9):
    """Create a simple sync executor that returns a result."""
    def executor(input_data):
        return SubTaskResult(
            subtask_id="",
            tool_id="",
            status=SubTaskStatus.COMPLETED,
            output=output,
            confidence=confidence,
        )
    return executor


def make_failing_executor(error_msg: str = "test error"):
    def executor(input_data):
        raise RuntimeError(error_msg)
    return executor


# ---------------------------------------------------------------------------
# Decomposition tests
# ---------------------------------------------------------------------------

class TestDecomposition:
    def test_decompose_creates_task(self):
        decomp = TeamCoordinator.decompose(
            "Analyze customer data",
            [
                {"assigned_tool_id": "bot.analysis", "name": "Analyze"},
                {"assigned_tool_id": "bot.report", "name": "Report"},
            ],
        )
        assert len(decomp.subtasks) == 2
        assert decomp.subtasks[0].assigned_tool_id == "bot.analysis"
        assert all(st.parent_task_id == decomp.task_id for st in decomp.subtasks)

    def test_decompose_with_strategy(self):
        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "t1"}],
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
        )
        assert decomp.merge_strategy == MergeStrategy.FIRST_SUCCESS


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestExecution:
    @pytest.mark.asyncio
    async def test_simple_execution(self, coordinator):
        coordinator.register_executor("tool_a", make_executor({"result": "A"}))
        coordinator.register_executor("tool_b", make_executor({"result": "B"}))

        decomp = TeamCoordinator.decompose(
            "test task",
            [
                {"assigned_tool_id": "tool_a"},
                {"assigned_tool_id": "tool_b"},
            ],
        )
        result = await coordinator.execute(decomp)
        assert result.status == CoordinationStatus.COMPLETED
        assert result.murphy_validation_passed is True
        assert len(result.subtask_results) == 2

    @pytest.mark.asyncio
    async def test_missing_executor(self, coordinator):
        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "nonexistent"}],
        )
        result = await coordinator.execute(decomp)
        assert result.subtask_results[0].status == SubTaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_failing_executor(self, coordinator):
        coordinator.register_executor("bad_tool", make_failing_executor())
        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "bad_tool"}],
        )
        result = await coordinator.execute(decomp)
        assert result.subtask_results[0].status == SubTaskStatus.FAILED
        assert "test error" in result.subtask_results[0].error

    @pytest.mark.asyncio
    async def test_dependency_ordering(self, coordinator):
        """Subtasks with dependencies should run after their deps."""
        execution_order = []

        def make_ordered_exec(name):
            def executor(input_data):
                execution_order.append(name)
                return {"name": name}
            return executor

        coordinator.register_executor("step1", make_ordered_exec("step1"))
        coordinator.register_executor("step2", make_ordered_exec("step2"))

        s1 = SubTask(subtask_id="s1", assigned_tool_id="step1")
        s2 = SubTask(subtask_id="s2", assigned_tool_id="step2", depends_on=["s1"])

        decomp = TaskDecomposition(
            original_request="ordered test",
            subtasks=[s1, s2],
        )
        result = await coordinator.execute(decomp)
        assert result.status == CoordinationStatus.COMPLETED
        assert execution_order.index("step1") < execution_order.index("step2")


# ---------------------------------------------------------------------------
# Merge strategy tests
# ---------------------------------------------------------------------------

class TestMergeStrategies:
    @pytest.mark.asyncio
    async def test_concat_merge(self, coordinator):
        coordinator.register_executor("t1", make_executor({"data": "A"}))
        coordinator.register_executor("t2", make_executor({"data": "B"}))

        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "t1"}, {"assigned_tool_id": "t2"}],
            merge_strategy=MergeStrategy.CONCAT,
        )
        result = await coordinator.execute(decomp)
        assert "data" in result.merged_output

    @pytest.mark.asyncio
    async def test_first_success_merge(self, coordinator):
        coordinator.register_executor("t1", make_executor({"result": "first"}))
        coordinator.register_executor("t2", make_executor({"result": "second"}))

        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "t1"}, {"assigned_tool_id": "t2"}],
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
        )
        result = await coordinator.execute(decomp)
        assert result.merged_output["result"] == "first"

    @pytest.mark.asyncio
    async def test_vote_merge_with_conflict(self, coordinator):
        coordinator.register_executor("t1", make_executor({"answer": "yes"}, confidence=0.9))
        coordinator.register_executor("t2", make_executor({"answer": "no"}, confidence=0.3))

        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "t1"}, {"assigned_tool_id": "t2"}],
            merge_strategy=MergeStrategy.VOTE,
        )
        result = await coordinator.execute(decomp)
        assert result.merged_output["answer"] == "yes"
        assert len(result.conflicts_resolved) == 1

    @pytest.mark.asyncio
    async def test_custom_merge(self, coordinator):
        coordinator.register_executor("t1", make_executor({"v": 1}))
        coordinator.register_executor("t2", make_executor({"v": 2}))

        def custom(results):
            total = sum(r.output.get("v", 0) for r in results)
            return {"sum": total}

        decomp = TeamCoordinator.decompose(
            "test",
            [{"assigned_tool_id": "t1"}, {"assigned_tool_id": "t2"}],
            merge_strategy=MergeStrategy.CUSTOM,
        )
        result = await coordinator.execute(decomp, custom_merge=custom)
        assert result.merged_output["sum"] == 3


# ---------------------------------------------------------------------------
# Murphy Validation tests
# ---------------------------------------------------------------------------

class TestMurphyValidation:
    @pytest.mark.asyncio
    async def test_validation_passes(self, coordinator):
        coordinator.register_executor("t1", make_executor({"ok": True}, confidence=0.95))
        decomp = TeamCoordinator.decompose("test", [{"assigned_tool_id": "t1"}])
        result = await coordinator.execute(decomp)
        assert result.murphy_validation_passed is True
        assert result.murphy_validation_score > 0.7

    @pytest.mark.asyncio
    async def test_validation_fails_all_errors(self, coordinator):
        coordinator.register_executor("t1", make_failing_executor())
        decomp = TeamCoordinator.decompose("test", [{"assigned_tool_id": "t1"}])
        result = await coordinator.execute(decomp)
        assert result.murphy_validation_passed is False

    def test_coordination_log(self, coordinator):
        log = coordinator.get_coordination_log()
        assert isinstance(log, list)
