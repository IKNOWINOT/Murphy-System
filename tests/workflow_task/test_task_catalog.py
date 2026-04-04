# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for task_catalog: validates catalog structure, count, URLs, and dependency refs."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.platform_onboarding.task_catalog import TASK_CATALOG, OnboardingTask


TASK_IDS = {t.task_id for t in TASK_CATALOG}
EXPECTED_COUNT = len(TASK_CATALOG)  # 147 explicitly-listed tasks


def test_catalog_count():
    assert len(TASK_CATALOG) == EXPECTED_COUNT


def test_no_duplicate_task_ids():
    ids = [t.task_id for t in TASK_CATALOG]
    assert len(ids) == len(set(ids)), "Duplicate task IDs found"


def test_all_tasks_are_onboarding_task_instances():
    for t in TASK_CATALOG:
        assert isinstance(t, OnboardingTask), f"{t.task_id} is not an OnboardingTask"


def test_required_fields_present():
    for t in TASK_CATALOG:
        assert t.task_id, f"Missing task_id"
        assert t.title, f"{t.task_id}: missing title"
        assert t.target_url, f"{t.task_id}: missing target_url"
        assert t.section, f"{t.task_id}: missing section"
        assert t.task_type, f"{t.task_id}: missing task_type"
        assert t.hitl_level, f"{t.task_id}: missing hitl_level"
        assert t.category, f"{t.task_id}: missing category"
        assert t.value_type, f"{t.task_id}: missing value_type"
        assert isinstance(t.depends_on, list), f"{t.task_id}: depends_on must be list"
        assert isinstance(t.blocks, list), f"{t.task_id}: blocks must be list"
        assert isinstance(t.prefill_fields, dict), f"{t.task_id}: prefill_fields must be dict"
        assert t.time_estimate_minutes > 0, f"{t.task_id}: time_estimate_minutes must be > 0"


def test_all_urls_are_https():
    for t in TASK_CATALOG:
        assert t.target_url.startswith("https://"), (
            f"{t.task_id}: URL must start with https://: {t.target_url}"
        )


def test_depends_on_refs_are_valid_task_ids():
    for t in TASK_CATALOG:
        for dep in t.depends_on:
            assert dep in TASK_IDS, (
                f"{t.task_id}: depends_on references unknown task '{dep}'"
            )


def test_blocks_are_reverse_of_depends_on():
    """blocks[X] must contain Y iff Y.depends_on contains X."""
    task_map = {t.task_id: t for t in TASK_CATALOG}
    for task in TASK_CATALOG:
        for dep_id in task.depends_on:
            dep_task = task_map[dep_id]
            assert task.task_id in dep_task.blocks, (
                f"Expected {dep_id}.blocks to contain {task.task_id}"
            )


def test_task_types_are_valid():
    valid_types = {"human_required", "agent_assisted", "agent_auto", "recurring"}
    for t in TASK_CATALOG:
        assert t.task_type in valid_types, f"{t.task_id}: invalid task_type '{t.task_type}'"


def test_hitl_levels_are_valid():
    valid = {"auto", "needs_review", "blocked_human_required"}
    for t in TASK_CATALOG:
        assert t.hitl_level in valid, f"{t.task_id}: invalid hitl_level '{t.hitl_level}'"


def test_categories_are_valid():
    valid = {"grant", "api_key", "cloud_credit", "compliance", "marketplace", "financing", "international"}
    for t in TASK_CATALOG:
        assert t.category in valid, f"{t.task_id}: invalid category '{t.category}'"


def test_value_types_are_valid():
    valid = {"free_money", "revenue_channel", "prerequisite", "trust_signal"}
    for t in TASK_CATALOG:
        assert t.value_type in valid, f"{t.task_id}: invalid value_type '{t.value_type}'"


def test_section_1_has_10_tasks():
    s1 = [t for t in TASK_CATALOG if t.section == "1"]
    assert len(s1) == 10


def test_section_5_has_50_tasks():
    s5 = [t for t in TASK_CATALOG if t.section == "5"]
    assert len(s5) == 50


def test_ein_task_exists():
    ein_task = next((t for t in TASK_CATALOG if t.task_id == "1.02"), None)
    assert ein_task is not None
    assert ein_task.title == "Get EIN from IRS"
    assert ein_task.depends_on == []


def test_sam_gov_depends_on_ein():
    sam = next(t for t in TASK_CATALOG if t.task_id == "1.01")
    assert "1.02" in sam.depends_on


def test_cloud_credits_have_no_deps():
    cloud_credits = [t for t in TASK_CATALOG if t.section == "4"]
    for t in cloud_credits:
        assert t.depends_on == [], f"{t.task_id} should have no dependencies"
