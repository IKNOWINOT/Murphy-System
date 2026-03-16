"""
Tests: Cost Dashboard API and GovernanceKernel Extensions

Verifies that:
- record_execution() stores project_id on execution records
- get_costs_by_project() aggregates costs correctly by project
- get_costs_by_caller() aggregates costs correctly by caller/bot
- /api/costs/* endpoints return correct data shapes
- Edge cases: no departments, no executions, unknown IDs
"""

import os
import unittest


from governance_kernel import GovernanceKernel, DepartmentScope


class TestProjectIdOnRecordExecution(unittest.TestCase):
    """record_execution() must store project_id on execution records."""

    def setUp(self):
        self.kernel = GovernanceKernel()
        self.kernel.register_department(DepartmentScope(department_id="eng", name="Engineering"))
        self.kernel.set_budget("eng", total_budget=500.0)

    def test_project_id_stored(self):
        """project_id is persisted in the execution record."""
        self.kernel.record_execution(
            "bot-a", "search", 1.0, True,
            department_id="eng", project_id="proj-001",
        )
        with self.kernel._lock:
            last = self.kernel._executions[-1]
        self.assertEqual(last["project_id"], "proj-001")

    def test_project_id_defaults_none(self):
        """project_id defaults to None when not supplied."""
        self.kernel.record_execution("bot-a", "search", 1.0, True)
        with self.kernel._lock:
            last = self.kernel._executions[-1]
        self.assertIsNone(last["project_id"])

    def test_multiple_project_ids_stored_independently(self):
        """Two executions with different project_ids are stored independently."""
        self.kernel.record_execution("bot-a", "t1", 2.0, True, project_id="proj-x")
        self.kernel.record_execution("bot-b", "t2", 3.0, True, project_id="proj-y")
        with self.kernel._lock:
            recs = list(self.kernel._executions)
        proj_ids = {r["project_id"] for r in recs}
        self.assertIn("proj-x", proj_ids)
        self.assertIn("proj-y", proj_ids)


class TestGetCostsByProject(unittest.TestCase):
    """get_costs_by_project() must aggregate costs by project_id."""

    def setUp(self):
        self.kernel = GovernanceKernel()

    def test_empty_returns_empty_dict(self):
        result = self.kernel.get_costs_by_project()
        self.assertEqual(result, {})

    def test_single_project_aggregated(self):
        self.kernel.record_execution("bot", "t", 5.0, True, project_id="alpha")
        self.kernel.record_execution("bot", "t", 3.0, True, project_id="alpha")
        result = self.kernel.get_costs_by_project()
        self.assertIn("alpha", result)
        self.assertAlmostEqual(result["alpha"]["total_cost"], 8.0)
        self.assertEqual(result["alpha"]["execution_count"], 2)

    def test_multiple_projects_separated(self):
        self.kernel.record_execution("bot", "t", 10.0, True, project_id="p1")
        self.kernel.record_execution("bot", "t", 20.0, True, project_id="p2")
        result = self.kernel.get_costs_by_project()
        self.assertAlmostEqual(result["p1"]["total_cost"], 10.0)
        self.assertAlmostEqual(result["p2"]["total_cost"], 20.0)

    def test_no_project_id_goes_to_unassigned(self):
        self.kernel.record_execution("bot", "t", 7.0, True)
        result = self.kernel.get_costs_by_project()
        self.assertIn("__unassigned__", result)
        self.assertAlmostEqual(result["__unassigned__"]["total_cost"], 7.0)

    def test_project_id_field_in_result(self):
        self.kernel.record_execution("bot", "t", 1.0, True, project_id="myproj")
        result = self.kernel.get_costs_by_project()
        self.assertEqual(result["myproj"]["project_id"], "myproj")


class TestGetCostsByCaller(unittest.TestCase):
    """get_costs_by_caller() must aggregate costs by caller_id."""

    def setUp(self):
        self.kernel = GovernanceKernel()

    def test_empty_returns_empty_dict(self):
        result = self.kernel.get_costs_by_caller()
        self.assertEqual(result, {})

    def test_single_caller_aggregated(self):
        self.kernel.record_execution("bot-a", "t", 4.0, True)
        self.kernel.record_execution("bot-a", "t", 6.0, True)
        result = self.kernel.get_costs_by_caller()
        self.assertIn("bot-a", result)
        self.assertAlmostEqual(result["bot-a"]["total_cost"], 10.0)
        self.assertEqual(result["bot-a"]["execution_count"], 2)

    def test_multiple_callers_separated(self):
        self.kernel.record_execution("bot-x", "t", 1.0, True)
        self.kernel.record_execution("bot-y", "t", 2.0, True)
        result = self.kernel.get_costs_by_caller()
        self.assertAlmostEqual(result["bot-x"]["total_cost"], 1.0)
        self.assertAlmostEqual(result["bot-y"]["total_cost"], 2.0)

    def test_caller_id_field_in_result(self):
        self.kernel.record_execution("agent-007", "t", 1.5, True)
        result = self.kernel.get_costs_by_caller()
        self.assertEqual(result["agent-007"]["caller_id"], "agent-007")


class TestCostsDashboardEndpoints(unittest.TestCase):
    """Integration tests for /api/costs/* FastAPI endpoints."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("fastapi not installed — skipping endpoint tests")

        # Raise rate limit for test runs to avoid 429 errors
        os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "10000")
        os.environ.setdefault("MURPHY_RATE_LIMIT_BURST", "10000")

        import importlib.util as _ilu
        _rt_path = os.path.join(os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py")
        _spec = _ilu.spec_from_file_location("murphy_system_1_0_runtime", _rt_path)
        _rt = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_rt)
        app = _rt.create_app()
        cls.client = TestClient(app)

        # Seed some data via kernel directly
        murphy_instance = None
        for route in app.routes:
            if hasattr(route, 'endpoint'):
                closure = getattr(route.endpoint, '__globals__', {})
                if '_cost_kernel' in closure and closure['_cost_kernel'] is not None:
                    murphy_instance = closure['_cost_kernel']
                    break
        cls.kernel = murphy_instance

    def _get_kernel(self):
        if self.kernel is None:
            self.skipTest("Could not retrieve kernel from app — skipping")
        return self.kernel

    # ── GET /api/costs/summary ────────────────────────────────────────

    def test_summary_returns_success(self):
        r = self.client.get("/api/costs/summary")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])

    def test_summary_shape(self):
        r = self.client.get("/api/costs/summary")
        s = r.json()["summary"]
        for key in ("total_budget", "spent", "pending", "remaining",
                    "utilisation_pct", "department_count"):
            self.assertIn(key, s, f"Missing key: {key}")

    def test_summary_reflects_set_budget(self):
        k = self._get_kernel()
        k.set_budget("test-dept-summary", total_budget=200.0)
        r = self.client.get("/api/costs/summary")
        s = r.json()["summary"]
        self.assertGreaterEqual(s["total_budget"], 200.0)
        self.assertGreaterEqual(s["department_count"], 1)

    # ── GET /api/costs/by-department ─────────────────────────────────

    def test_by_department_returns_list(self):
        r = self.client.get("/api/costs/by-department")
        self.assertEqual(r.status_code, 200)
        self.assertIn("departments", r.json())
        self.assertIsInstance(r.json()["departments"], list)

    def test_by_department_shape(self):
        k = self._get_kernel()
        k.set_budget("test-dept-shape", total_budget=100.0)
        r = self.client.get("/api/costs/by-department")
        depts = r.json()["departments"]
        dept = next((d for d in depts if d["department_id"] == "test-dept-shape"), None)
        self.assertIsNotNone(dept)
        for key in ("total_budget", "spent", "pending", "remaining",
                    "limit_per_task", "utilisation_pct"):
            self.assertIn(key, dept, f"Missing dept key: {key}")

    def test_utilisation_pct_accurate(self):
        k = self._get_kernel()
        k.set_budget("util-test", total_budget=100.0)
        k.enforce("u", "util-test", "tool", estimated_cost=50.0)
        k.record_execution("u", "tool", 50.0, True, department_id="util-test")
        r = self.client.get("/api/costs/by-department")
        depts = r.json()["departments"]
        dept = next((d for d in depts if d["department_id"] == "util-test"), None)
        self.assertIsNotNone(dept)
        self.assertAlmostEqual(dept["utilisation_pct"], 50.0, places=1)

    # ── GET /api/costs/by-project ─────────────────────────────────────

    def test_by_project_returns_list(self):
        r = self.client.get("/api/costs/by-project")
        self.assertEqual(r.status_code, 200)
        self.assertIn("projects", r.json())
        self.assertIsInstance(r.json()["projects"], list)

    def test_by_project_after_assignment(self):
        k = self._get_kernel()
        k.record_execution("bot", "tool", 9.0, True, project_id="api-test-proj")
        r = self.client.get("/api/costs/by-project")
        projects = r.json()["projects"]
        proj = next((p for p in projects if p["project_id"] == "api-test-proj"), None)
        self.assertIsNotNone(proj)
        self.assertGreaterEqual(proj["total_cost"], 9.0)

    # ── GET /api/costs/by-bot ─────────────────────────────────────────

    def test_by_bot_returns_list(self):
        r = self.client.get("/api/costs/by-bot")
        self.assertEqual(r.status_code, 200)
        self.assertIn("bots", r.json())
        self.assertIsInstance(r.json()["bots"], list)

    def test_by_bot_after_execution(self):
        k = self._get_kernel()
        k.record_execution("unique-bot-xyz", "tool", 3.5, True)
        r = self.client.get("/api/costs/by-bot")
        bots = r.json()["bots"]
        bot = next((b for b in bots if b["caller_id"] == "unique-bot-xyz"), None)
        self.assertIsNotNone(bot)
        self.assertGreaterEqual(bot["total_cost"], 3.5)

    # ── POST /api/costs/assign ────────────────────────────────────────

    def test_assign_success(self):
        r = self.client.post("/api/costs/assign", json={
            "caller_id": "test-bot", "tool_name": "search", "cost": 0.25,
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])

    def test_assign_with_department_and_project(self):
        k = self._get_kernel()
        k.register_department(DepartmentScope(department_id="assign-dept", name="Assign Test"))
        k.set_budget("assign-dept", total_budget=100.0)
        r = self.client.post("/api/costs/assign", json={
            "caller_id": "bot-x",
            "tool_name": "infer",
            "cost": 1.0,
            "department_id": "assign-dept",
            "project_id": "assign-proj",
        })
        self.assertTrue(r.json()["success"])
        by_proj = self.client.get("/api/costs/by-project").json()["projects"]
        proj = next((p for p in by_proj if p["project_id"] == "assign-proj"), None)
        self.assertIsNotNone(proj)

    def test_assign_missing_fields_400(self):
        r = self.client.post("/api/costs/assign", json={"caller_id": "bot"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["success"])

    # ── PATCH /api/costs/budget ───────────────────────────────────────

    def test_set_budget_success(self):
        r = self.client.patch("/api/costs/budget", json={
            "department_id": "patch-dept", "total_budget": 500.0,
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])

    def test_set_budget_updates_department(self):
        self.client.patch("/api/costs/budget", json={
            "department_id": "patch-dept2", "total_budget": 250.0, "limit_per_task": 10.0,
        })
        r = self.client.get("/api/costs/by-department")
        depts = r.json()["departments"]
        dept = next((d for d in depts if d["department_id"] == "patch-dept2"), None)
        self.assertIsNotNone(dept)
        self.assertAlmostEqual(dept["total_budget"], 250.0)
        self.assertAlmostEqual(dept["limit_per_task"], 10.0)

    def test_set_budget_missing_fields_400(self):
        r = self.client.patch("/api/costs/budget", json={"department_id": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["success"])

    # ── Edge cases ────────────────────────────────────────────────────

    def test_summary_no_departments_zero_utilisation(self):
        """A fresh kernel returns 0% utilisation and no departments."""
        fresh = GovernanceKernel()
        # Override the kernel directly — create a minimal test app
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from fastapi.responses import JSONResponse
        except ImportError:
            self.skipTest("fastapi not installed")

        mini_app = FastAPI()

        @mini_app.get("/api/costs/summary")
        async def mini_summary():
            all_budgets = fresh.get_budget_status()
            total_budget = sum(v["total_budget"] for v in all_budgets.values())
            total_spent = sum(v["spent"] for v in all_budgets.values())
            total_pending = sum(v["pending"] for v in all_budgets.values())
            util = round((total_spent / total_budget * 100) if total_budget > 0 else 0.0, 2)
            return JSONResponse({
                "success": True,
                "summary": {
                    "total_budget": total_budget,
                    "spent": total_spent,
                    "pending": total_pending,
                    "remaining": total_budget - total_spent - total_pending,
                    "utilisation_pct": util,
                    "department_count": len(all_budgets),
                },
            })

        c = TestClient(mini_app)
        r = c.get("/api/costs/summary")
        s = r.json()["summary"]
        self.assertEqual(s["department_count"], 0)
        self.assertAlmostEqual(s["utilisation_pct"], 0.0)

    def test_by_project_empty(self):
        fresh = GovernanceKernel()
        result = fresh.get_costs_by_project()
        self.assertEqual(result, {})

    def test_by_caller_empty(self):
        fresh = GovernanceKernel()
        result = fresh.get_costs_by_caller()
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
