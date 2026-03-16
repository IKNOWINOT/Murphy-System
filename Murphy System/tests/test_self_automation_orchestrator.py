"""
Test suite for SelfAutomationOrchestrator.
Validates task management, cycle lifecycle, gap analysis,
prompt generation, dependency resolution, and status reporting.
"""

import os
import unittest

# Add src to path

from self_automation_orchestrator import (
    SelfAutomationOrchestrator,
    TaskCategory,
    TaskStatus,
    PromptStep,
    ImprovementTask,
    CycleRecord,
)


class TestTaskCreation(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_create_task_returns_task(self):
        task = self.orch.create_task("Fix bug", TaskCategory.BUG_FIX, description="bug")
        self.assertIsInstance(task, ImprovementTask)
        self.assertTrue(task.task_id.startswith("task-"))

    def test_create_task_sets_defaults(self):
        task = self.orch.create_task("t1", TaskCategory.COVERAGE_GAP)
        self.assertEqual(task.status, TaskStatus.QUEUED)
        self.assertEqual(task.priority, 3)
        self.assertEqual(task.retry_count, 0)
        self.assertEqual(task.current_step, PromptStep.ANALYSIS)

    def test_create_task_with_module_name(self):
        task = self.orch.create_task("t1", TaskCategory.FEATURE_REQUEST, module_name="my_module")
        self.assertEqual(task.module_name, "my_module")
        self.assertEqual(task.test_file, "tests/test_my_module.py")

    def test_create_task_custom_priority(self):
        task = self.orch.create_task("t1", TaskCategory.SELF_IMPROVEMENT, priority=1)
        self.assertEqual(task.priority, 1)

    def test_priority_clamped_to_range(self):
        t_low = self.orch.create_task("t1", TaskCategory.BUG_FIX, priority=0)
        t_high = self.orch.create_task("t2", TaskCategory.BUG_FIX, priority=10)
        self.assertEqual(t_low.priority, 1)
        self.assertEqual(t_high.priority, 5)

    def test_create_task_with_dependencies(self):
        task = self.orch.create_task("t1", TaskCategory.BUG_FIX, dependencies=["dep-1", "dep-2"])
        self.assertEqual(task.dependencies, ["dep-1", "dep-2"])

    def test_create_task_increments_queue(self):
        self.orch.create_task("t1", TaskCategory.BUG_FIX)
        self.orch.create_task("t2", TaskCategory.BUG_FIX)
        self.assertEqual(self.orch.get_status()["total_tasks"], 2)
        self.assertEqual(self.orch.get_status()["queue_length"], 2)


class TestTaskLookup(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()
        self.task = self.orch.create_task("t1", TaskCategory.BUG_FIX)

    def test_get_task_by_id(self):
        found = self.orch.get_task(self.task.task_id)
        self.assertIs(found, self.task)

    def test_get_task_returns_none_for_missing(self):
        self.assertIsNone(self.orch.get_task("nonexistent"))

    def test_list_tasks_all(self):
        self.orch.create_task("t2", TaskCategory.FEATURE_REQUEST)
        tasks = self.orch.list_tasks()
        self.assertEqual(len(tasks), 2)

    def test_list_tasks_filter_by_status(self):
        self.orch.start_task(self.task.task_id)
        queued = self.orch.list_tasks(status=TaskStatus.QUEUED)
        in_progress = self.orch.list_tasks(status=TaskStatus.IN_PROGRESS)
        self.assertEqual(len(queued), 0)
        self.assertEqual(len(in_progress), 1)

    def test_list_tasks_filter_by_category(self):
        self.orch.create_task("t2", TaskCategory.FEATURE_REQUEST)
        bugs = self.orch.list_tasks(category=TaskCategory.BUG_FIX)
        features = self.orch.list_tasks(category=TaskCategory.FEATURE_REQUEST)
        self.assertEqual(len(bugs), 1)
        self.assertEqual(len(features), 1)


class TestTaskLifecycle(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()
        self.task = self.orch.create_task("t1", TaskCategory.BUG_FIX)

    def test_start_task(self):
        result = self.orch.start_task(self.task.task_id)
        self.assertTrue(result)
        self.assertEqual(self.task.status, TaskStatus.IN_PROGRESS)
        self.assertIsNotNone(self.task.started_at)
        self.assertEqual(self.task.current_step, PromptStep.IMPLEMENTATION)

    def test_start_nonexistent_task(self):
        self.assertFalse(self.orch.start_task("nonexistent"))

    def test_start_already_started_task(self):
        self.orch.start_task(self.task.task_id)
        self.assertFalse(self.orch.start_task(self.task.task_id))

    def test_advance_step_to_testing(self):
        self.orch.start_task(self.task.task_id)
        result = self.orch.advance_step(self.task.task_id, PromptStep.TESTING)
        self.assertTrue(result)
        self.assertEqual(self.task.current_step, PromptStep.TESTING)
        self.assertEqual(self.task.status, TaskStatus.TESTING)

    def test_advance_step_to_review(self):
        self.orch.start_task(self.task.task_id)
        result = self.orch.advance_step(self.task.task_id, PromptStep.REVIEW)
        self.assertTrue(result)
        self.assertEqual(self.task.status, TaskStatus.REVIEW)

    def test_complete_task(self):
        self.orch.start_task(self.task.task_id)
        result = self.orch.complete_task(self.task.task_id, result={"tests_added": 30})
        self.assertTrue(result)
        self.assertEqual(self.task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(self.task.result["tests_added"], 30)

    def test_complete_removes_from_queue(self):
        self.orch.start_task(self.task.task_id)
        self.orch.complete_task(self.task.task_id)
        self.assertEqual(self.orch.get_status()["queue_length"], 0)

    def test_fail_task_retries(self):
        self.orch.start_task(self.task.task_id)
        self.orch.fail_task(self.task.task_id, "error occurred")
        self.assertEqual(self.task.status, TaskStatus.QUEUED)
        self.assertEqual(self.task.retry_count, 1)

    def test_fail_task_max_retries_exhausted(self):
        self.orch.start_task(self.task.task_id)
        for i in range(3):
            self.orch.fail_task(self.task.task_id, f"error {i}")
        self.assertEqual(self.task.status, TaskStatus.FAILED)
        self.assertEqual(self.task.retry_count, 3)

    def test_block_task(self):
        result = self.orch.block_task(self.task.task_id, "waiting for dependency")
        self.assertTrue(result)
        self.assertEqual(self.task.status, TaskStatus.BLOCKED)
        self.assertEqual(self.task.result["blocked_reason"], "waiting for dependency")


class TestDependencyResolution(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_get_next_task_no_deps(self):
        t1 = self.orch.create_task("t1", TaskCategory.BUG_FIX, priority=1)
        t2 = self.orch.create_task("t2", TaskCategory.BUG_FIX, priority=2)
        next_task = self.orch.get_next_task()
        self.assertEqual(next_task.task_id, t1.task_id)

    def test_get_next_skips_unmet_deps(self):
        t1 = self.orch.create_task("t1", TaskCategory.BUG_FIX, priority=2)
        t2 = self.orch.create_task("t2", TaskCategory.BUG_FIX, priority=1,
                                    dependencies=[t1.task_id])
        # t2 has higher priority but unmet deps, so t1 should be next
        next_task = self.orch.get_next_task()
        self.assertEqual(next_task.task_id, t1.task_id)

    def test_get_next_after_dep_completed(self):
        t1 = self.orch.create_task("t1", TaskCategory.BUG_FIX, priority=2)
        t2 = self.orch.create_task("t2", TaskCategory.BUG_FIX, priority=1,
                                    dependencies=[t1.task_id])
        self.orch.start_task(t1.task_id)
        self.orch.complete_task(t1.task_id)
        next_task = self.orch.get_next_task()
        self.assertEqual(next_task.task_id, t2.task_id)

    def test_get_next_returns_none_when_empty(self):
        self.assertIsNone(self.orch.get_next_task())

    def test_get_next_returns_none_all_blocked(self):
        t1 = self.orch.create_task("t1", TaskCategory.BUG_FIX, dependencies=["nonexistent"])
        self.assertIsNone(self.orch.get_next_task())


class TestCycleManagement(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_start_cycle(self):
        cycle = self.orch.start_cycle(gap_analysis={"gaps": 5})
        self.assertIsInstance(cycle, CycleRecord)
        self.assertTrue(cycle.cycle_id.startswith("cycle-"))
        self.assertEqual(cycle.gap_analysis["gaps"], 5)

    def test_complete_cycle(self):
        self.orch.start_cycle()
        t = self.orch.create_task("t1", TaskCategory.BUG_FIX, estimated_tests=10, module_name="mod")
        self.orch.start_task(t.task_id)
        self.orch.complete_task(t.task_id)
        cycle = self.orch.complete_cycle()
        self.assertIsNotNone(cycle)
        self.assertIsNotNone(cycle.completed_at)
        self.assertEqual(cycle.tasks_completed, 1)
        self.assertEqual(cycle.tests_added, 10)
        self.assertIn("mod", cycle.modules_added)

    def test_complete_cycle_when_none_active(self):
        self.assertIsNone(self.orch.complete_cycle())

    def test_cycle_history(self):
        self.orch.start_cycle()
        self.orch.complete_cycle()
        self.orch.start_cycle()
        self.orch.complete_cycle()
        history = self.orch.get_cycle_history()
        self.assertEqual(len(history), 2)

    def test_failed_task_counted_in_cycle(self):
        self.orch.start_cycle()
        t = self.orch.create_task("t1", TaskCategory.BUG_FIX)
        t.max_retries = 0
        self.orch.start_task(t.task_id)
        self.orch.fail_task(t.task_id, "fatal")
        cycle = self.orch.complete_cycle()
        self.assertEqual(cycle.tasks_failed, 1)


class TestGapAnalysis(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_register_gap(self):
        self.orch.register_gap("gap-1", TaskCategory.COVERAGE_GAP, "Low tests")
        gaps = self.orch.get_open_gaps()
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["gap_id"], "gap-1")

    def test_resolve_gap(self):
        self.orch.register_gap("gap-1", TaskCategory.COVERAGE_GAP, "Low tests")
        result = self.orch.resolve_gap("gap-1", "Added 20 tests")
        self.assertTrue(result)
        self.assertEqual(len(self.orch.get_open_gaps()), 0)

    def test_resolve_nonexistent_gap(self):
        self.assertFalse(self.orch.resolve_gap("nonexistent"))

    def test_analyze_coverage_gaps(self):
        modules = {"mod_a": 10, "mod_b": 30, "mod_c": 5}
        gaps = self.orch.analyze_coverage_gaps(modules, min_tests=25)
        self.assertEqual(len(gaps), 2)
        # mod_c has bigger deficit
        self.assertEqual(gaps[0]["module"], "mod_c")
        self.assertEqual(gaps[0]["deficit"], 20)

    def test_analyze_coverage_registers_gaps(self):
        self.orch.analyze_coverage_gaps({"mod_a": 10}, min_tests=25)
        open_gaps = self.orch.get_open_gaps()
        self.assertEqual(len(open_gaps), 1)
        self.assertIn("coverage-mod_a", open_gaps[0]["gap_id"])


class TestPromptGeneration(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_generate_prompt_for_task(self):
        task = self.orch.create_task("Fix X", TaskCategory.BUG_FIX, module_name="my_mod")
        prompt = self.orch.generate_prompt(task, PromptStep.IMPLEMENTATION)
        self.assertIn("my_mod", prompt)
        self.assertIn("src/my_mod.py", prompt)

    def test_generate_full_chain(self):
        task = self.orch.create_task("Fix X", TaskCategory.BUG_FIX, module_name="my_mod")
        chain = self.orch.generate_full_chain(task)
        self.assertEqual(len(chain), 8)
        for step in PromptStep:
            self.assertIn(step.value, chain)

    def test_custom_prompt_template(self):
        task = self.orch.create_task(
            "Fix X", TaskCategory.BUG_FIX,
            prompt_template="Custom: {title} for {module_name}"
        )
        task.module_name = "custom_mod"
        prompt = self.orch.generate_prompt(task, PromptStep.IMPLEMENTATION)
        self.assertIn("Custom: Fix X for custom_mod", prompt)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_empty_status(self):
        status = self.orch.get_status()
        self.assertEqual(status["total_tasks"], 0)
        self.assertEqual(status["queue_length"], 0)
        self.assertEqual(status["completed_count"], 0)
        self.assertEqual(status["open_gaps"], 0)
        self.assertIsNone(status["current_cycle"])
        self.assertEqual(status["completed_cycles"], 0)
        self.assertEqual(len(status["prompt_steps"]), 8)
        self.assertEqual(len(status["available_categories"]), 8)

    def test_status_with_tasks(self):
        self.orch.create_task("t1", TaskCategory.BUG_FIX)
        t2 = self.orch.create_task("t2", TaskCategory.FEATURE_REQUEST)
        self.orch.start_task(t2.task_id)
        self.orch.complete_task(t2.task_id)
        status = self.orch.get_status()
        self.assertEqual(status["total_tasks"], 2)
        self.assertEqual(status["completed_count"], 1)
        self.assertEqual(status["status_breakdown"]["queued"], 1)
        self.assertEqual(status["status_breakdown"]["completed"], 1)

    def test_status_with_cycle(self):
        self.orch.start_cycle()
        status = self.orch.get_status()
        self.assertIsNotNone(status["current_cycle"])

    def test_status_category_breakdown(self):
        self.orch.create_task("t1", TaskCategory.BUG_FIX)
        self.orch.create_task("t2", TaskCategory.BUG_FIX)
        self.orch.create_task("t3", TaskCategory.FEATURE_REQUEST)
        status = self.orch.get_status()
        self.assertEqual(status["category_breakdown"]["bug_fix"], 2)
        self.assertEqual(status["category_breakdown"]["feature_request"], 1)


class TestQueuePriority(unittest.TestCase):
    def setUp(self):
        self.orch = SelfAutomationOrchestrator()

    def test_queue_sorted_by_priority(self):
        t3 = self.orch.create_task("low", TaskCategory.BUG_FIX, priority=5)
        t1 = self.orch.create_task("high", TaskCategory.BUG_FIX, priority=1)
        t2 = self.orch.create_task("med", TaskCategory.BUG_FIX, priority=3)
        next_task = self.orch.get_next_task()
        self.assertEqual(next_task.task_id, t1.task_id)


if __name__ == "__main__":
    unittest.main()
