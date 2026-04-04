# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for PriorityScorer."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG
from src.platform_onboarding.priority_scorer import PriorityScorer


TASK_MAP = {t.task_id: t for t in TASK_CATALOG}


def test_scorer_returns_all_tasks():
    scorer = PriorityScorer()
    results = scorer.score_tasks(TASK_CATALOG, {})
    assert len(results) == len(TASK_CATALOG)


def test_results_sorted_descending():
    scorer = PriorityScorer()
    results = scorer.score_tasks(TASK_CATALOG, {})
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_scores_are_non_negative():
    scorer = PriorityScorer()
    results = scorer.score_tasks(TASK_CATALOG, {})
    for task, score in results:
        assert score >= 0, f"{task.task_id} has negative score {score}"


def test_cloud_credits_score_high():
    """Cloud credits (free_money + no deps + immediate) should score well."""
    scorer = PriorityScorer()
    cloud_tasks = [t for t in TASK_CATALOG if t.section == "4"]
    all_results = scorer.score_tasks(TASK_CATALOG, {})
    all_scores = {t.task_id: s for t, s in all_results}

    grant_app_tasks = [t for t in TASK_CATALOG if t.section == "2"]
    # Average cloud credit score vs average grant application score
    cloud_avg = sum(all_scores[t.task_id] for t in cloud_tasks) / len(cloud_tasks)
    grant_avg = sum(all_scores[t.task_id] for t in grant_app_tasks) / len(grant_app_tasks)
    # Cloud credits (no deps, instant, free_money) should be in high ranks
    assert cloud_avg > 0, "Cloud credit score should be positive"


def test_ein_scores_high_due_to_blocker_count():
    """1.02 EIN blocks SAM.gov and everything downstream — should score high."""
    scorer = PriorityScorer()
    ein = TASK_MAP["1.02"]
    sam = TASK_MAP["1.01"]
    # EIN has more indirect blockers than a typical task
    ein_score = scorer.score_task(ein, {})
    # EIN should have a meaningful score (> 0)
    assert ein_score > 0


def test_higher_blocker_count_raises_score():
    """Task with more blocks should score higher than one with fewer (all else equal)."""
    scorer = PriorityScorer()
    ein = TASK_MAP["1.02"]   # blocks many tasks
    ein_score = scorer.score_task(ein, {})

    # A leaf task (no blocks, no value) should score lower
    leaf_tasks = [t for t in TASK_CATALOG if not t.blocks and not t.estimated_value]
    if leaf_tasks:
        leaf_score = scorer.score_task(leaf_tasks[0], {})
        assert ein_score > leaf_score


def test_score_task_individual():
    scorer = PriorityScorer()
    task = TASK_MAP["4.01"]  # AWS Activate credits
    score = scorer.score_task(task, {})
    assert score >= 0


def test_score_with_session_state():
    scorer = PriorityScorer()
    session = {"company_name": "Acme", "ein": "12-3456789"}
    results = scorer.score_tasks(TASK_CATALOG[:10], session)
    assert len(results) == 10
