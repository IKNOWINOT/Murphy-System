# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for parallel groups (dependency levels)."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG
from src.platform_onboarding.progress_tracker import ProgressTracker


def test_parallel_groups_returns_dict():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    assert isinstance(groups, dict)


def test_level_0_exists():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    assert 0 in groups


def test_level_0_contains_cloud_credits():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_0 = set(groups[0])
    for tid in ["4.01", "4.02", "4.03", "4.04", "4.05", "4.06", "4.07", "4.08"]:
        assert tid in level_0, f"{tid} (cloud credit) should be in level 0"


def test_level_0_contains_api_keys():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_0 = set(groups[0])
    api_key_tasks = [t for t in TASK_CATALOG if t.section == "5"]
    for t in api_key_tasks:
        assert t.task_id in level_0, f"{t.task_id} (API key) should be level 0"


def test_level_0_contains_ein():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    assert "1.02" in groups[0], "EIN (1.02) has no deps so must be level 0"


def test_sam_gov_is_level_1():
    """1.01 depends on 1.02 (level 0) → SAM.gov must be level 1."""
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_1 = set(groups.get(1, []))
    assert "1.01" in level_1, "SAM.gov (1.01) should be level 1"


def test_grants_gov_is_level_2():
    """1.03 depends on 1.01 (level 1) → Grants.gov must be level 2."""
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    level_2 = set(groups.get(2, []))
    assert "1.03" in level_2, "Grants.gov (1.03) should be level 2"


def test_sbir_phase_i_is_level_3_or_higher():
    """2.01 depends on 1.01, 1.03, 1.05 — all level >= 1. So 2.01 should be >= 2."""
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    # Find which level 2.01 is in
    sbir_level = None
    for lvl, tids in groups.items():
        if "2.01" in tids:
            sbir_level = lvl
            break
    assert sbir_level is not None
    assert sbir_level >= 2, f"SBIR (2.01) should be at least level 2, got {sbir_level}"


def test_all_tasks_have_a_level():
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    all_in_groups = {tid for tids in groups.values() for tid in tids}
    for task in TASK_CATALOG:
        assert task.task_id in all_in_groups, f"{task.task_id} missing from parallel groups"


def test_level_0_has_no_dep_tasks():
    """Every task in level 0 must have no dependencies."""
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    task_map = {t.task_id: t for t in TASK_CATALOG}
    for tid in groups.get(0, []):
        task = task_map.get(tid)
        if task:
            assert task.depends_on == [], f"{tid} in level 0 but has deps: {task.depends_on}"


def test_higher_levels_depend_on_lower():
    """Tasks in level N must only depend on tasks in levels < N."""
    tracker = ProgressTracker()
    groups = tracker.get_parallel_groups()
    task_map = {t.task_id: t for t in TASK_CATALOG}
    level_of = {tid: lvl for lvl, tids in groups.items() for tid in tids}
    for tid, lvl in level_of.items():
        task = task_map.get(tid)
        if task:
            for dep in task.depends_on:
                if dep in level_of:
                    assert level_of[dep] < lvl, (
                        f"{tid} (level {lvl}) depends on {dep} (level {level_of[dep]})"
                    )
