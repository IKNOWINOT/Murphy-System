"""PCR-060k — drill driver requirements integration tests."""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.pcr060_drill_driver import (
    drive_boundary_loop,
    init_drill_db,
    IterationRecord,
    _persist_iteration,
)
from src.pcr060_requirement_tracker import (
    Requirement, RequirementStatus, SolvedSet,
)


# ─── Reusable stubs (mirror test_060i fixtures) ───

class _StubTrajectoryPoint:
    def __init__(self, t, op, money, name):
        self.t = t; self.operational_targets = op
        self.money_ratio_targets = money; self.state_name = name

class _StubGoalPlot:
    def __init__(self, points):
        self.r_curve = points

def _good_goal_plot():
    return _StubGoalPlot([
        _StubTrajectoryPoint(0.0, {"resolution_score": 4.5, "iqs": 0.9,
                                    "density_index": 0.9, "coherence_score": 0.9,
                                    "cqi": 0.9}, {}, "goal"),
        _StubTrajectoryPoint(1.0, {"resolution_score": 1.5, "iqs": 0.3,
                                    "density_index": 0.3, "coherence_score": 0.3,
                                    "cqi": 0.3}, {}, "present"),
    ])

def _good_magnify(score=0.5):
    return {
        "success": True,
        "result": {
            "output": {
                "concept_overview": "A CRM",
                "industry": "tech",
                "target_audience": "users",
                "cost_complexity_estimate": "moderate",
            },
            "input_quality": {"resolution_score": 1.5, "density_index": 0.3,
                              "coherence_score": 0.4, "iqs": 0.3, "cqi": 0.4},
            "output_quality": {"resolution_score": score * 5, "density_index": score,
                                "coherence_score": score, "iqs": score, "cqi": score},
        },
    }


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "drill.db")


# ─────────────────────────────────────────────────────────────────────
# Schema migration
# ─────────────────────────────────────────────────────────────────────

class TestSchema:
    def test_new_columns_present_on_iterations(self, db_path):
        init_drill_db(db_path)
        con = sqlite3.connect(db_path)
        cols = {row[1] for row in con.execute(
            "PRAGMA table_info(boundary_loop_iterations)").fetchall()}
        assert "solved_ratio" in cols
        assert "solved_count" in cols
        assert "total_count" in cols
        assert "boundary_state" in cols
        con.close()

    def test_requirements_table_created(self, db_path):
        init_drill_db(db_path)
        con = sqlite3.connect(db_path)
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "boundary_loop_requirements" in tables
        con.close()

    def test_migration_idempotent(self, db_path):
        # Run twice — should not error
        init_drill_db(db_path)
        init_drill_db(db_path)


# ─────────────────────────────────────────────────────────────────────
# Backwards compat — default-off behavior
# ─────────────────────────────────────────────────────────────────────

class TestBackwardsCompat:
    def test_track_requirements_off_by_default(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "test prompt",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=2,
                api_key="test-key",
            )
        # No requirements column populated
        for r in result.iteration_log:
            assert r.solved_ratio is None
            assert r.total_count is None
            assert r.boundary_state is None

    def test_solved_ratio_none_when_off(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(score=0.5)
            drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=1, api_key="test-key",
            )
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT solved_ratio, boundary_state FROM boundary_loop_iterations"
        ).fetchall()
        con.close()
        assert all(r[0] is None and r[1] is None for r in rows)


# ─────────────────────────────────────────────────────────────────────
# Requirements tracking enabled
# ─────────────────────────────────────────────────────────────────────

class TestTracking:
    def test_tracking_populates_columns(self, db_path):
        fake_reqs = [
            Requirement(id="req_001", text="r1", category="functional",
                         evaluable_question="?"),
            Requirement(id="req_002", text="r2", category="functional",
                         evaluable_question="?"),
        ]
        fake_ss = SolvedSet(
            iteration=0,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="addressed",
                                   evidence="x", confidence="high"),
                RequirementStatus(requirement_id="req_002", status="unaddressed",
                                   evidence="", confidence="medium"),
            ],
            solved_count=1, unaddressed_count=1, total_count=2,
        )
        with patch("src.pcr060_drill_driver.call_magnify") as mag, \
             patch("src.pcr060_requirement_tracker.extract_requirements",
                    return_value=fake_reqs) as ext, \
             patch("src.pcr060_requirement_tracker.evaluate_solved",
                    return_value=fake_ss) as ev:
            mag.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=1, api_key="test-key",
                track_requirements=True,
            )
        # Iteration record carries the requirements summary
        assert len(result.iteration_log) >= 1
        r = result.iteration_log[0]
        assert r.solved_ratio == 0.5
        assert r.solved_count == 1
        assert r.total_count == 2
        assert r.boundary_state in ("drilling", "polish", "success",
                                     "failure_stalled", "failure_impossible")

    def test_persists_requirement_detail_rows(self, db_path):
        fake_reqs = [Requirement(id="req_001", text="r1", category="functional",
                                   evaluable_question="?")]
        fake_ss = SolvedSet(
            iteration=0,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="addressed",
                                   evidence="found", confidence="high"),
            ],
            solved_count=1, total_count=1,
        )
        with patch("src.pcr060_drill_driver.call_magnify") as mag, \
             patch("src.pcr060_requirement_tracker.extract_requirements",
                    return_value=fake_reqs), \
             patch("src.pcr060_requirement_tracker.evaluate_solved",
                    return_value=fake_ss):
            mag.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=1, api_key="test-key",
                track_requirements=True,
            )
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT requirement_id, status, evidence, confidence "
            "FROM boundary_loop_requirements WHERE dispatch_id=?",
            (result.dispatch_id,),
        ).fetchall()
        con.close()
        assert len(rows) == 1
        assert rows[0][0] == "req_001"
        assert rows[0][1] == "addressed"
        assert rows[0][2] == "found"
        assert rows[0][3] == "high"


# ─────────────────────────────────────────────────────────────────────
# Failure surface — halt_on_impossible
# ─────────────────────────────────────────────────────────────────────

class TestHaltOnImpossible:
    def test_halts_when_impossible_requirement(self, db_path):
        fake_reqs = [Requirement(id="req_001", text="quantum compliance",
                                   category="constraint", evaluable_question="?")]
        fake_ss = SolvedSet(
            iteration=0,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="impossible",
                                   evidence="no such thing", confidence="high"),
            ],
            impossible_count=1, total_count=1,
        )
        with patch("src.pcr060_drill_driver.call_magnify") as mag, \
             patch("src.pcr060_requirement_tracker.extract_requirements",
                    return_value=fake_reqs), \
             patch("src.pcr060_requirement_tracker.evaluate_solved",
                    return_value=fake_ss):
            mag.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "build a quantum compliance widget",
                goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=5, api_key="test-key",
                track_requirements=True,
            )
        # Should halt at iter 0 because impossible was detected
        assert result.iterations_run == 1
        assert result.success is False
        assert result.deliverable_quality == "impossible_requirement"
        assert "impossible" in result.reason.lower()

    def test_continues_when_halt_disabled(self, db_path):
        fake_reqs = [Requirement(id="req_001", text="r", category="functional",
                                   evaluable_question="?")]
        fake_ss = SolvedSet(
            iteration=0,
            statuses=[
                RequirementStatus(requirement_id="req_001", status="impossible",
                                   evidence="no", confidence="high"),
            ],
            impossible_count=1, total_count=1,
        )
        with patch("src.pcr060_drill_driver.call_magnify") as mag, \
             patch("src.pcr060_requirement_tracker.extract_requirements",
                    return_value=fake_reqs), \
             patch("src.pcr060_requirement_tracker.evaluate_solved",
                    return_value=fake_ss):
            mag.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=2, api_key="test-key",
                track_requirements=True, halt_on_impossible=False,
            )
        # Did NOT halt early — ran multiple iterations
        assert result.iterations_run >= 2
        assert result.deliverable_quality != "impossible_requirement"


# ─────────────────────────────────────────────────────────────────────
# Failure on extraction
# ─────────────────────────────────────────────────────────────────────

class TestExtractionFailure:
    def test_falls_back_to_delta_only_when_extraction_empty(self, db_path):
        """If extract_requirements returns [], loop behaves as if track was off."""
        with patch("src.pcr060_drill_driver.call_magnify") as mag, \
             patch("src.pcr060_requirement_tracker.extract_requirements",
                    return_value=[]):
            mag.return_value = _good_magnify(score=0.5)
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=2, api_key="test-key",
                track_requirements=True,
            )
        # Loop ran, but no requirements were tracked
        for r in result.iteration_log:
            assert r.solved_ratio is None
            assert r.boundary_state is None
