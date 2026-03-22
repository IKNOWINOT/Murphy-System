# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for critical path."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.progress_tracker import ProgressTracker


def test_critical_path_is_list():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert isinstance(path, list)


def test_critical_path_not_empty():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert len(path) > 0


def test_critical_path_contains_ein():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert "1.02" in path


def test_critical_path_contains_sam_gov():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert "1.01" in path


def test_critical_path_contains_grants_gov():
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert "1.03" in path


def test_critical_path_ein_before_sam():
    """1.02 must come before 1.01 in the critical path."""
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert path.index("1.02") < path.index("1.01")


def test_critical_path_sam_before_grants_gov():
    """1.01 must come before 1.03."""
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    assert path.index("1.01") < path.index("1.03")


def test_critical_path_valid_task_ids():
    """All IDs in the critical path must be real task IDs."""
    from src.platform_onboarding.task_catalog import TASK_CATALOG
    valid_ids = {t.task_id for t in TASK_CATALOG}
    tracker = ProgressTracker()
    path = tracker.get_critical_path()
    for tid in path:
        assert tid in valid_ids, f"Critical path contains unknown task ID: {tid}"
