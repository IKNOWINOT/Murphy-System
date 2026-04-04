"""
Tests for the Portfolio module (Phase 4 of management systems parity).

Covers:
  1. Models & serialization
  2. Dependency manager (CRUD, cycle detection, topological sort)
  3. Critical path calculation
  4. Gantt engine (bars, milestones, baselines, rendering)
  5. API router
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from portfolio.models import (
    Baseline,
    Dependency,
    DependencyType,
    GanttBar,
    Milestone,
    MilestoneStatus,
    PortfolioProject,
)
from portfolio.dependencies import DependencyManager
from portfolio.critical_path import CriticalPathEngine
from portfolio.gantt import GanttEngine


# ===================================================================
# 1. Models & serialization
# ===================================================================

class TestModels:
    def test_gantt_bar_to_dict(self):
        bar = GanttBar(item_id="i1", item_name="Design",
                       start_date="2025-01-01", end_date="2025-01-11")
        d = bar.to_dict()
        assert d["item_id"] == "i1"
        assert d["duration_days"] == 10

    def test_gantt_bar_duration_invalid(self):
        bar = GanttBar(item_id="i1", start_date="bad", end_date="bad")
        assert bar.duration_days() == 0

    def test_dependency_to_dict(self):
        dep = Dependency(predecessor_id="i1", successor_id="i2",
                         dependency_type=DependencyType.FINISH_TO_START)
        d = dep.to_dict()
        assert d["dependency_type"] == "fs"

    def test_milestone_to_dict(self):
        ms = Milestone(name="MVP", target_date="2025-03-01",
                       status=MilestoneStatus.IN_PROGRESS)
        d = ms.to_dict()
        assert d["status"] == "in_progress"

    def test_baseline_to_dict(self):
        bar = GanttBar(item_id="i1", start_date="2025-01-01", end_date="2025-01-10")
        bl = Baseline(name="Sprint 1", bars=[bar])
        d = bl.to_dict()
        assert len(d["bars"]) == 1

    def test_portfolio_project_to_dict(self):
        p = PortfolioProject(board_id="b1", name="Project X", progress=0.5)
        d = p.to_dict()
        assert d["progress"] == 0.5


# ===================================================================
# 2. Dependency manager
# ===================================================================

class TestDependencyManager:
    def test_add_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2")
        assert dep.predecessor_id == "i1"
        assert dep.successor_id == "i2"

    def test_add_self_dependency(self):
        dm = DependencyManager()
        with pytest.raises(ValueError, match="cannot depend on itself"):
            dm.add_dependency("i1", "i1")

    def test_add_duplicate_dependency(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        with pytest.raises(ValueError, match="already exists"):
            dm.add_dependency("i1", "i2")

    def test_cycle_detection(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        with pytest.raises(ValueError, match="cycle"):
            dm.add_dependency("i3", "i1")

    def test_remove_dependency(self):
        dm = DependencyManager()
        dep = dm.add_dependency("i1", "i2")
        assert dm.remove_dependency(dep.id)
        assert len(dm.get_dependencies("i1")) == 0

    def test_remove_dependency_not_found(self):
        dm = DependencyManager()
        assert not dm.remove_dependency("nope")

    def test_get_dependencies(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        deps = dm.get_dependencies("i2")
        assert len(deps) == 2  # i2 is both successor and predecessor

    def test_get_predecessors(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i3")
        dm.add_dependency("i2", "i3")
        assert set(dm.get_predecessors("i3")) == {"i1", "i2"}

    def test_get_successors(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i1", "i3")
        assert set(dm.get_successors("i1")) == {"i2", "i3"}

    def test_topological_sort(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        order = dm.topological_sort()
        assert order.index("i1") < order.index("i2")
        assert order.index("i2") < order.index("i3")

    def test_topological_sort_with_subset(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        order = dm.topological_sort(["i1", "i2"])
        assert order.index("i1") < order.index("i2")


# ===================================================================
# 3. Critical path
# ===================================================================

class TestCriticalPath:
    def test_simple_chain(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i2", "i3")
        cp = CriticalPathEngine(dm)
        bars = [
            GanttBar(item_id="i1", start_date="2025-01-01", end_date="2025-01-06"),  # 5 days
            GanttBar(item_id="i2", start_date="2025-01-06", end_date="2025-01-11"),  # 5 days
            GanttBar(item_id="i3", start_date="2025-01-11", end_date="2025-01-16"),  # 5 days
        ]
        result = cp.compute(bars)
        assert result["total_duration"] == 15
        assert set(result["critical_items"]) == {"i1", "i2", "i3"}

    def test_parallel_paths(self):
        dm = DependencyManager()
        dm.add_dependency("i1", "i2")
        dm.add_dependency("i1", "i3")
        dm.add_dependency("i2", "i4")
        dm.add_dependency("i3", "i4")
        cp = CriticalPathEngine(dm)
        bars = [
            GanttBar(item_id="i1", start_date="2025-01-01", end_date="2025-01-06"),  # 5 days
            GanttBar(item_id="i2", start_date="2025-01-06", end_date="2025-01-16"),  # 10 days (longer)
            GanttBar(item_id="i3", start_date="2025-01-06", end_date="2025-01-09"),  # 3 days (shorter)
            GanttBar(item_id="i4", start_date="2025-01-16", end_date="2025-01-21"),  # 5 days
        ]
        result = cp.compute(bars)
        assert "i1" in result["critical_items"]
        assert "i2" in result["critical_items"]  # longer path
        assert "i4" in result["critical_items"]
        # i3 is NOT critical (shorter parallel path)
        assert "i3" not in result["critical_items"]

    def test_empty_bars(self):
        dm = DependencyManager()
        cp = CriticalPathEngine(dm)
        result = cp.compute([])
        assert result["critical_items"] == []
        assert result["total_duration"] == 0

    def test_single_bar(self):
        dm = DependencyManager()
        cp = CriticalPathEngine(dm)
        bars = [GanttBar(item_id="i1", start_date="2025-01-01", end_date="2025-01-06")]
        result = cp.compute(bars)
        assert result["total_duration"] == 5
        assert result["critical_items"] == ["i1"]


# ===================================================================
# 4. Gantt engine
# ===================================================================

class TestGanttEngine:
    def test_add_bar(self):
        eng = GanttEngine()
        bar = eng.add_bar("i1", "Design", "2025-01-01", "2025-01-10", board_id="b1")
        assert bar.item_id == "i1"

    def test_update_bar(self):
        eng = GanttEngine()
        eng.add_bar("i1", "Design", "2025-01-01", "2025-01-10")
        updated = eng.update_bar("i1", progress=0.5)
        assert updated.progress == 0.5

    def test_update_bar_not_found(self):
        eng = GanttEngine()
        with pytest.raises(KeyError):
            eng.update_bar("missing")

    def test_remove_bar(self):
        eng = GanttEngine()
        eng.add_bar("i1", "Design", "2025-01-01", "2025-01-10")
        assert eng.remove_bar("i1")
        assert len(eng.get_bars()) == 0

    def test_remove_bar_not_found(self):
        eng = GanttEngine()
        assert not eng.remove_bar("nope")

    def test_get_bars_filtered(self):
        eng = GanttEngine()
        eng.add_bar("i1", "A", "2025-01-01", "2025-01-10", board_id="b1")
        eng.add_bar("i2", "B", "2025-01-01", "2025-01-10", board_id="b2")
        assert len(eng.get_bars("b1")) == 1

    def test_add_milestone(self):
        eng = GanttEngine()
        ms = eng.add_milestone("MVP", "2025-03-01", board_id="b1")
        assert ms.name == "MVP"

    def test_update_milestone(self):
        eng = GanttEngine()
        ms = eng.add_milestone("MVP", "2025-03-01")
        updated = eng.update_milestone(ms.id, status=MilestoneStatus.COMPLETED)
        assert updated.status == MilestoneStatus.COMPLETED

    def test_update_milestone_not_found(self):
        eng = GanttEngine()
        with pytest.raises(KeyError):
            eng.update_milestone("missing")

    def test_get_milestones_filtered(self):
        eng = GanttEngine()
        eng.add_milestone("A", "2025-01-01", board_id="b1")
        eng.add_milestone("B", "2025-02-01", board_id="b2")
        assert len(eng.get_milestones("b1")) == 1

    def test_create_baseline(self):
        eng = GanttEngine()
        eng.add_bar("i1", "Design", "2025-01-01", "2025-01-10", board_id="b1")
        eng.add_bar("i2", "Build", "2025-01-11", "2025-01-20", board_id="b1")
        bl = eng.create_baseline("Sprint 1 Plan", "b1", created_by="u1")
        assert len(bl.bars) == 2

    def test_baseline_is_snapshot(self):
        eng = GanttEngine()
        eng.add_bar("i1", "Design", "2025-01-01", "2025-01-10", board_id="b1")
        bl = eng.create_baseline("Plan", "b1")
        # Modify the original bar
        eng.update_bar("i1", end_date="2025-01-15")
        # Baseline should still have original date
        assert bl.bars[0].end_date == "2025-01-10"

    def test_get_baselines(self):
        eng = GanttEngine()
        eng.add_bar("i1", "A", "2025-01-01", "2025-01-10", board_id="b1")
        eng.create_baseline("BL1", "b1")
        eng.create_baseline("BL2", "b1")
        assert len(eng.get_baselines("b1")) == 2

    def test_get_baseline(self):
        eng = GanttEngine()
        bl = eng.create_baseline("BL1", "b1")
        assert eng.get_baseline(bl.id) is bl
        assert eng.get_baseline("nope") is None

    def test_compute_critical_path(self):
        eng = GanttEngine()
        eng.add_bar("i1", "A", "2025-01-01", "2025-01-06", board_id="b1")
        eng.add_bar("i2", "B", "2025-01-06", "2025-01-11", board_id="b1")
        eng.deps.add_dependency("i1", "i2")
        result = eng.compute_critical_path("b1")
        assert "i1" in result["critical_items"]

    def test_render_gantt(self):
        eng = GanttEngine()
        eng.add_bar("i1", "Design", "2025-01-01", "2025-01-06", board_id="b1")
        eng.add_bar("i2", "Build", "2025-01-06", "2025-01-11", board_id="b1")
        eng.deps.add_dependency("i1", "i2")
        eng.add_milestone("MVP", "2025-01-11", board_id="b1")
        data = eng.render_gantt("b1")
        assert len(data["bars"]) == 2
        assert len(data["dependencies"]) >= 1
        assert len(data["milestones"]) == 1
        assert "critical_path" in data


# ===================================================================
# 5. API router
# ===================================================================

class TestAPIRouter:
    def test_create_portfolio_router(self):
        try:
            from portfolio.api import create_portfolio_router
            router = create_portfolio_router()
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")

    def test_router_with_custom_engine(self):
        try:
            from portfolio.api import create_portfolio_router
            eng = GanttEngine()
            router = create_portfolio_router(eng)
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")
