"""Tests for WorkflowDAGEngine."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from workflow_dag_engine import (
    WorkflowDAGEngine,
    WorkflowDefinition,
    StepDefinition,
    StepStatus,
    WorkflowStatus,
)


class TestWorkflowDAGEngine(unittest.TestCase):

    def setUp(self):
        self.engine = WorkflowDAGEngine()

    def _simple_workflow(self):
        return WorkflowDefinition(
            workflow_id="wf1",
            name="Simple Workflow",
            steps=[
                StepDefinition(step_id="a", name="Step A", action="do_a"),
                StepDefinition(step_id="b", name="Step B", action="do_b", depends_on=["a"]),
                StepDefinition(step_id="c", name="Step C", action="do_c", depends_on=["b"]),
            ],
        )

    def test_register_workflow(self):
        wf = self._simple_workflow()
        self.assertTrue(self.engine.register_workflow(wf))

    def test_register_workflow_with_cycle(self):
        wf = WorkflowDefinition(
            workflow_id="cycle",
            name="Cyclic",
            steps=[
                StepDefinition(step_id="a", name="A", action="a", depends_on=["c"]),
                StepDefinition(step_id="b", name="B", action="b", depends_on=["a"]),
                StepDefinition(step_id="c", name="C", action="c", depends_on=["b"]),
            ],
        )
        self.assertFalse(self.engine.register_workflow(wf))

    def test_register_workflow_invalid_dependency(self):
        wf = WorkflowDefinition(
            workflow_id="bad",
            name="Bad deps",
            steps=[
                StepDefinition(step_id="a", name="A", action="a", depends_on=["nonexistent"]),
            ],
        )
        self.assertFalse(self.engine.register_workflow(wf))

    def test_create_execution(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        self.assertIsNotNone(exec_id)

    def test_create_execution_unknown_workflow(self):
        result = self.engine.create_execution("nonexistent")
        self.assertIsNone(result)

    def test_execute_simple_workflow(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["failed"], 0)

    def test_execute_with_handler(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        handler_calls = []
        def handler(step_def, ctx):
            handler_calls.append(step_def.step_id)
            return {"processed": True}
        self.engine.register_step_handler("do_a", handler)
        exec_id = self.engine.create_execution("wf1")
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["status"], "completed")
        self.assertIn("a", handler_calls)

    def test_execute_with_failing_handler(self):
        wf = WorkflowDefinition(
            workflow_id="fail_wf",
            name="Failing",
            steps=[
                StepDefinition(step_id="a", name="A", action="fail_action"),
                StepDefinition(step_id="b", name="B", action="do_b", depends_on=["a"]),
            ],
        )
        self.engine.register_workflow(wf)
        self.engine.register_step_handler("fail_action", lambda s, c: 1/0)
        exec_id = self.engine.create_execution("fail_wf")
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["status"], "failed")
        self.assertGreater(result["failed"], 0)

    def test_conditional_step(self):
        wf = WorkflowDefinition(
            workflow_id="cond",
            name="Conditional",
            steps=[
                StepDefinition(step_id="a", name="A", action="do_a"),
                StepDefinition(step_id="b", name="B", action="do_b", depends_on=["a"], condition="skip_b!=true"),
            ],
        )
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("cond", context={"skip_b": "true"})
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["steps"]["b"]["status"], "skipped")

    def test_condition_equals(self):
        wf = WorkflowDefinition(
            workflow_id="cond_eq",
            name="Cond Eq",
            steps=[
                StepDefinition(step_id="a", name="A", action="do_a", condition="env=production"),
            ],
        )
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("cond_eq", context={"env": "production"})
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["steps"]["a"]["status"], "completed")

    def test_topological_sort(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        order = self.engine.get_execution_order("wf1")
        self.assertEqual(order, ["a", "b", "c"])

    def test_parallel_groups(self):
        wf = WorkflowDefinition(
            workflow_id="parallel",
            name="Parallel",
            steps=[
                StepDefinition(step_id="a", name="A", action="do_a"),
                StepDefinition(step_id="b", name="B", action="do_b"),
                StepDefinition(step_id="c", name="C", action="do_c", depends_on=["a", "b"]),
            ],
        )
        self.engine.register_workflow(wf)
        groups = self.engine.get_parallel_groups("parallel")
        self.assertEqual(len(groups), 2)
        self.assertIn("a", groups[0])
        self.assertIn("b", groups[0])
        self.assertIn("c", groups[1])

    def test_checkpoint_and_resume(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        self.engine.execute_workflow(exec_id)
        checkpoint = self.engine.checkpoint_execution(exec_id)
        self.assertIsNotNone(checkpoint)
        self.assertIn("step_states", checkpoint)

    def test_pause_cancel(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        self.assertTrue(self.engine.pause_execution(exec_id))
        self.assertTrue(self.engine.cancel_execution(exec_id))

    def test_get_execution(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        self.engine.execute_workflow(exec_id)
        state = self.engine.get_execution(exec_id)
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "completed")

    def test_get_execution_not_found(self):
        self.assertIsNone(self.engine.get_execution("nonexistent"))

    def test_list_workflows(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        workflows = self.engine.list_workflows()
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows[0]["name"], "Simple Workflow")

    def test_statistics(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        self.engine.execute_workflow(exec_id)
        stats = self.engine.get_statistics()
        self.assertEqual(stats["total_workflows"], 1)
        self.assertGreater(stats["completed_executions"], 0)

    def test_status(self):
        status = self.engine.status()
        self.assertEqual(status["module"], "workflow_dag_engine")

    def test_execute_unknown_execution(self):
        result = self.engine.execute_workflow("nonexistent")
        self.assertIn("error", result)

    def test_dependency_not_met_skips_downstream(self):
        wf = WorkflowDefinition(
            workflow_id="dep_fail",
            name="Dep Fail",
            steps=[
                StepDefinition(step_id="a", name="A", action="fail_action"),
                StepDefinition(step_id="b", name="B", action="do_b", depends_on=["a"]),
            ],
        )
        self.engine.register_workflow(wf)
        self.engine.register_step_handler("fail_action", lambda s, c: 1/0)
        exec_id = self.engine.create_execution("dep_fail")
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["steps"]["b"]["status"], "skipped")

    def test_diamond_workflow(self):
        wf = WorkflowDefinition(
            workflow_id="diamond",
            name="Diamond",
            steps=[
                StepDefinition(step_id="a", name="A", action="do_a"),
                StepDefinition(step_id="b", name="B", action="do_b", depends_on=["a"]),
                StepDefinition(step_id="c", name="C", action="do_c", depends_on=["a"]),
                StepDefinition(step_id="d", name="D", action="do_d", depends_on=["b", "c"]),
            ],
        )
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("diamond")
        result = self.engine.execute_workflow(exec_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total"], 4)

    def test_parallel_groups_unknown_workflow(self):
        self.assertIsNone(self.engine.get_parallel_groups("nope"))

    def test_execution_order_unknown_workflow(self):
        self.assertIsNone(self.engine.get_execution_order("nope"))

    def test_resume_without_checkpoint(self):
        wf = self._simple_workflow()
        self.engine.register_workflow(wf)
        exec_id = self.engine.create_execution("wf1")
        result = self.engine.resume_execution(exec_id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
