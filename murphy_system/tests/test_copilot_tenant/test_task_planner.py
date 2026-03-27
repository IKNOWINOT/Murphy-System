# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for TaskPlanner (task_planner.py).

Validates:
  - Task queue generation
  - Priority ordering
  - System state assessment
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from copilot_tenant.task_planner import PlannedTask, TaskPlanner


class TestPlannedTask:
    def test_default_task_has_id(self) -> None:
        task = PlannedTask()
        assert task.task_id  # non-empty UUID string

    def test_custom_fields(self) -> None:
        task = PlannedTask(
            task_type="content_creation",
            description="Write a blog post",
            priority=0.8,
            domain="marketing",
        )
        assert task.task_type == "content_creation"
        assert task.priority == 0.8

    def test_proposed_at_is_set(self) -> None:
        task = PlannedTask()
        assert "T" in task.proposed_at  # ISO timestamp


class TestTaskPlanner:
    def test_instantiation(self) -> None:
        planner = TaskPlanner()
        assert planner is not None

    def test_assess_system_state_returns_dict(self) -> None:
        planner = TaskPlanner()
        state = planner.assess_system_state()
        assert isinstance(state, dict)
        assert "assessed_at" in state

    def test_generate_task_queue_returns_list(self) -> None:
        planner = TaskPlanner()
        queue = planner.generate_task_queue()
        assert isinstance(queue, list)
        assert len(queue) >= 1  # at least the heartbeat

    def test_generate_task_queue_default_heartbeat(self) -> None:
        planner = TaskPlanner()
        queue = planner.generate_task_queue()
        # With no external engines, should have a heartbeat task
        types = {t.task_type for t in queue}
        assert "heartbeat" in types

    def test_prioritize_orders_descending(self) -> None:
        planner = TaskPlanner()
        tasks = [
            PlannedTask(priority=0.3),
            PlannedTask(priority=0.9),
            PlannedTask(priority=0.6),
        ]
        ordered = planner.prioritize(tasks)
        assert ordered[0].priority >= ordered[1].priority >= ordered[2].priority

    def test_prioritize_handles_empty(self) -> None:
        planner = TaskPlanner()
        assert planner.prioritize([]) == []

    def test_full_cycle_generate_and_prioritize(self) -> None:
        planner = TaskPlanner()
        queue   = planner.generate_task_queue()
        ordered = planner.prioritize(queue)
        assert len(ordered) == len(queue)

    def test_tasks_have_unique_ids(self) -> None:
        planner = TaskPlanner()
        queue   = planner.generate_task_queue()
        ids = [t.task_id for t in queue]
        assert len(ids) == len(set(ids))
