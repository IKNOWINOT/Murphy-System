"""
Acceptance tests – Management Parity Phase 4: Portfolio Management
==================================================================

Validates the Portfolio Management module (``src/portfolio``):

- Project grouping via Gantt boards and PortfolioProject
- Cross-project dependencies (FS, SS, FF, SF) with cycle detection
- Resource allocation proxied through assignee_ids on GanttBar
- Portfolio-level KPIs: critical path, baseline variance, milestone status

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase4.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os

import pytest


import portfolio
from portfolio import (
    Baseline,
    Dependency,
    DependencyManager,
    DependencyType,
    GanttBar,
    GanttEngine,
    Milestone,
    MilestoneStatus,
    PortfolioProject,
    CriticalPathEngine,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(portfolio, "__version__")

    def test_gantt_engine_importable(self):
        assert GanttEngine is not None

    def test_dependency_manager_importable(self):
        assert DependencyManager is not None

    def test_critical_path_engine_importable(self):
        assert CriticalPathEngine is not None

    def test_dependency_types_defined(self):
        for dt in (
            DependencyType.FINISH_TO_START,
            DependencyType.START_TO_START,
            DependencyType.FINISH_TO_FINISH,
            DependencyType.START_TO_FINISH,
        ):
            assert dt is not None

    def test_milestone_status_values(self):
        for s in (
            MilestoneStatus.PENDING,
            MilestoneStatus.IN_PROGRESS,
            MilestoneStatus.COMPLETED,
            MilestoneStatus.MISSED,
        ):
            assert s is not None


# ---------------------------------------------------------------------------
# 2. Project grouping
# ---------------------------------------------------------------------------


class TestProjectGrouping:
    """Gantt bars from multiple boards represent distinct projects."""

    def test_add_bars_to_different_boards(self):
        engine = GanttEngine()
        engine.add_bar("i1", "Alpha Task", "2025-01-01", "2025-01-10", board_id="project-alpha")
        engine.add_bar("i2", "Beta Task", "2025-01-01", "2025-01-15", board_id="project-beta")
        alpha_bars = engine.get_bars("project-alpha")
        beta_bars = engine.get_bars("project-beta")
        assert len(alpha_bars) == 1
        assert len(beta_bars) == 1

    def test_portfolio_project_model(self):
        proj = PortfolioProject(
            board_id="board-alpha",
            name="Alpha",
            owner_id="u1",
            status="in_progress",
            start_date="2025-01-01",
            end_date="2025-03-31",
            progress=0.4,
            health="on_track",
        )
        data = proj.to_dict()
        assert data["name"] == "Alpha"
        assert data["progress"] == 0.4
        assert data["health"] == "on_track"

    def test_multiple_bars_same_project(self):
        engine = GanttEngine()
        for i in range(5):
            engine.add_bar(
                f"task-{i}", f"Task {i}",
                "2025-01-01", "2025-01-10",
                board_id="project-gamma",
            )
        bars = engine.get_bars("project-gamma")
        assert len(bars) == 5

    def test_render_gantt_returns_board_data(self):
        engine = GanttEngine()
        engine.add_bar("t1", "Task 1", "2025-01-01", "2025-01-05", board_id="proj-1")
        engine.add_bar("t2", "Task 2", "2025-01-06", "2025-01-10", board_id="proj-1")
        result = engine.render_gantt("proj-1")
        assert "bars" in result
        assert len(result["bars"]) == 2


# ---------------------------------------------------------------------------
# 3. Cross-project dependencies
# ---------------------------------------------------------------------------


class TestCrossProjectDependencies:
    """Dependency manager correctly stores, validates, and detects cycles."""

    def test_add_finish_to_start_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2", DependencyType.FINISH_TO_START)
        assert dep.predecessor_id == "i1"
        assert dep.successor_id == "i2"
        assert dep.dependency_type == DependencyType.FINISH_TO_START

    def test_add_start_to_start_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2", DependencyType.START_TO_START)
        assert dep.dependency_type == DependencyType.START_TO_START

    def test_add_finish_to_finish_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2", DependencyType.FINISH_TO_FINISH)
        assert dep.dependency_type == DependencyType.FINISH_TO_FINISH

    def test_cycle_detection_raises(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        with pytest.raises(ValueError, match="cycle"):
            dm.add_dependency("i3", "i1")

    def test_self_dependency_raises(self):
        dm = DependencyManager()
        with pytest.raises(ValueError):
            dm.add_dependency("i1", "i1")

    def test_duplicate_dependency_raises(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        with pytest.raises(ValueError):
            dm.add_dependency("i1", "i2")

    def test_dependency_with_lag(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2", DependencyType.FINISH_TO_START, lag_days=3)
        assert dep.lag_days == 3

    def test_remove_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2")
        removed = dm.remove_dependency(dep.id)
        assert removed is True
        # Verify it's gone by checking get_dependencies returns no match
        remaining = dm.get_dependencies("i1")
        assert all(d.id != dep.id for d in remaining)

    def test_get_successors(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i1", "i3")
        successors = dm.get_successors("i1")
        assert set(successors) == {"i2", "i3"}

    def test_get_predecessors(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i3")
        dm.add_dependency("i2", "i3")
        preds = dm.get_predecessors("i3")
        assert set(preds) == {"i1", "i2"}


# ---------------------------------------------------------------------------
# 4. Resource allocation
# ---------------------------------------------------------------------------


class TestResourceAllocation:
    """Resources (assignees) are tracked per Gantt bar and queried."""

    def test_assignee_on_gantt_bar(self):
        engine = GanttEngine()
        bar = engine.add_bar(
            "t1", "Design",
            "2025-01-01", "2025-01-10",
            board_id="proj",
            assignee_ids=["alice", "bob"],
        )
        assert "alice" in bar.assignee_ids
        assert "bob" in bar.assignee_ids

    def test_update_assignees(self):
        engine = GanttEngine()
        engine.add_bar("t1", "Task", "2025-01-01", "2025-01-05", board_id="proj",
                       assignee_ids=["carol"])
        bars = engine.get_bars("proj")
        assert bars[0].assignee_ids == ["carol"]

    def test_multiple_bars_with_assignees(self):
        engine = GanttEngine()
        engine.add_bar("t1", "T1", "2025-01-01", "2025-01-05",
                       board_id="proj", assignee_ids=["alice"])
        engine.add_bar("t2", "T2", "2025-01-06", "2025-01-10",
                       board_id="proj", assignee_ids=["alice", "bob"])
        bars = engine.get_bars("proj")
        all_assignees = {a for bar in bars for a in bar.assignee_ids}
        assert "alice" in all_assignees
        assert "bob" in all_assignees


# ---------------------------------------------------------------------------
# 5. Portfolio-level KPIs
# ---------------------------------------------------------------------------


class TestPortfolioKPIs:
    """Milestones, baselines, and critical path provide portfolio-level metrics."""

    def test_milestone_creation(self):
        engine = GanttEngine()
        ms = engine.add_milestone(
            "MVP Release",
            "2025-03-01",
            board_id="proj-1",
        )
        assert ms.name == "MVP Release"
        assert ms.status == MilestoneStatus.PENDING

    def test_milestone_status_update(self):
        engine = GanttEngine()
        ms = engine.add_milestone("Beta", "2025-04-01", board_id="proj-1")
        updated = engine.update_milestone(ms.id, status=MilestoneStatus.COMPLETED)
        assert updated.status == MilestoneStatus.COMPLETED

    def test_milestones_list_per_board(self):
        engine = GanttEngine()
        engine.add_milestone("M1", "2025-01-31", board_id="proj-a")
        engine.add_milestone("M2", "2025-02-28", board_id="proj-a")
        engine.add_milestone("M3", "2025-03-31", board_id="proj-b")
        assert len(engine.get_milestones("proj-a")) == 2
        assert len(engine.get_milestones("proj-b")) == 1

    def test_baseline_snapshot(self):
        engine = GanttEngine()
        engine.add_bar("t1", "Task A", "2025-01-01", "2025-01-10", board_id="proj")
        engine.add_bar("t2", "Task B", "2025-01-11", "2025-01-20", board_id="proj")
        baseline = engine.create_baseline("Sprint 1 Baseline", board_id="proj")
        assert baseline.name == "Sprint 1 Baseline"
        assert len(baseline.bars) == 2

    def test_critical_path_computation(self):
        engine = GanttEngine()
        engine.add_bar("t1", "Design", "2025-01-01", "2025-01-10", board_id="proj")
        engine.add_bar("t2", "Build", "2025-01-11", "2025-01-25", board_id="proj")
        engine.deps.add_dependency("t1", "t2", DependencyType.FINISH_TO_START)
        result = engine.compute_critical_path("proj")
        # The engine returns critical_items; validate structure
        assert "critical_items" in result
        assert isinstance(result["critical_items"], list)

    def test_render_gantt_includes_milestones(self):
        engine = GanttEngine()
        engine.add_bar("t1", "Task", "2025-01-01", "2025-01-10", board_id="proj")
        engine.add_milestone("Go Live", "2025-01-15", board_id="proj")
        result = engine.render_gantt("proj")
        assert "milestones" in result
        assert len(result["milestones"]) == 1
