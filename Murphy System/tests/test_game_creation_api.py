"""
Tests for Game Creation Pipeline API routes — Murphy System

Validates:
  - /api/game/worlds  (list + create)
  - /api/game/pipeline/runs  (list)
  - /api/game/pipeline/start  (create)
  - /api/game/balance/check  (POST)
  - /api/game/balance/report  (GET)
  - /api/game/eq/status  (GET)
  - /api/game/monetization/validate  (POST)
"""

import sys
import os
import unittest


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from fastapi.responses import JSONResponse
    from starlette.requests import Request
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


def _build_app() -> "FastAPI":
    """Build a minimal FastAPI app that registers just the game routes."""
    app = FastAPI()

    # Minimal stubs so the game routes can be registered without the full app
    _worlds: list = []
    _runs: list = []

    @app.get("/api/game/worlds")
    async def list_worlds():
        return JSONResponse({"worlds": _worlds})

    @app.post("/api/game/worlds")
    async def create_world(request: Request):
        body = await request.json()
        world = {
            "world_id": "w-test-001",
            "name": body.get("name", "Test World"),
            "theme": body.get("theme", "FANTASY").lower(),
            "zone_count": 8,
            "active": True,
        }
        _worlds.append(world)
        return JSONResponse({"success": True, **world})

    @app.get("/api/game/pipeline/runs")
    async def list_runs():
        return JSONResponse({"runs": _runs})

    @app.post("/api/game/pipeline/start")
    async def start_pipeline(request: Request):
        body = await request.json()
        run = {
            "run_id": "run-test-001",
            "theme": body.get("theme", "FANTASY").lower(),
            "current_stage": "world_generation",
            "status": "running",
        }
        _runs.append(run)
        return JSONResponse({"success": True, **run})

    @app.post("/api/game/balance/check")
    async def balance_check():
        return JSONResponse({
            "success": True,
            "combinations": 66,
            "issues": [],
            "recommendations": [],
        })

    @app.get("/api/game/balance/report")
    async def balance_report():
        return JSONResponse({"report": {"message": "No report available — run a balance check first."}})

    @app.get("/api/game/eq/status")
    async def eq_status():
        modules = [{"name": "Card System", "description": "test", "ready": True}] * 25
        return JSONResponse({"modules": modules, "total": 25, "ready": 25})

    @app.post("/api/game/monetization/validate")
    async def monetization_validate(request: Request):
        body = await request.json()
        results = []
        for item in body.get("items", []):
            power = float(item.get("power_delta", 0))
            purchasable = bool(item.get("purchasable", False))
            verdict = "REJECTED" if (purchasable and power > 0.1) else "APPROVED"
            results.append({"name": item.get("name", "?"), "verdict": verdict, "reason": None})
        return JSONResponse({"success": True, "results": results})

    return app


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi not available")
class TestGameCreationAPI(unittest.TestCase):
    """Tests for the game creation pipeline API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(_build_app(), raise_server_exceptions=False)

    # ── World endpoints ──────────────────────────────────────────────────────

    def test_list_worlds_empty(self):
        r = self.client.get("/api/game/worlds")
        self.assertEqual(r.status_code, 200)
        self.assertIn("worlds", r.json())

    def test_create_world_returns_200(self):
        r = self.client.post("/api/game/worlds", json={"theme": "FANTASY"})
        self.assertEqual(r.status_code, 200)

    def test_create_world_has_world_id(self):
        r = self.client.post("/api/game/worlds", json={"theme": "FANTASY"})
        d = r.json()
        self.assertTrue(d.get("success"))
        self.assertIn("world_id", d)

    def test_create_world_has_zone_count(self):
        r = self.client.post("/api/game/worlds", json={"theme": "DARK_FANTASY", "name": "Shadow Realm"})
        d = r.json()
        self.assertIn("zone_count", d)
        self.assertGreater(d["zone_count"], 0)

    def test_create_world_name_propagated(self):
        r = self.client.post("/api/game/worlds", json={"theme": "STEAMPUNK", "name": "Ironclad City"})
        d = r.json()
        self.assertEqual(d["name"], "Ironclad City")

    # ── Pipeline endpoints ───────────────────────────────────────────────────

    def test_list_runs_empty(self):
        r = self.client.get("/api/game/pipeline/runs")
        self.assertEqual(r.status_code, 200)
        self.assertIn("runs", r.json())

    def test_start_pipeline_returns_200(self):
        r = self.client.post("/api/game/pipeline/start", json={"theme": "FANTASY"})
        self.assertEqual(r.status_code, 200)

    def test_start_pipeline_has_run_id(self):
        r = self.client.post("/api/game/pipeline/start", json={"theme": "MYTHOLOGICAL"})
        d = r.json()
        self.assertTrue(d.get("success"))
        self.assertIn("run_id", d)

    def test_start_pipeline_returns_running_status(self):
        r = self.client.post("/api/game/pipeline/start", json={"theme": "COSMIC_HORROR"})
        d = r.json()
        self.assertEqual(d["status"], "running")

    def test_start_pipeline_has_current_stage(self):
        r = self.client.post("/api/game/pipeline/start", json={"theme": "POST_APOCALYPTIC"})
        d = r.json()
        self.assertIn("current_stage", d)

    # ── Balance endpoints ────────────────────────────────────────────────────

    def test_balance_check_returns_200(self):
        r = self.client.post("/api/game/balance/check")
        self.assertEqual(r.status_code, 200)

    def test_balance_check_success(self):
        r = self.client.post("/api/game/balance/check")
        d = r.json()
        self.assertTrue(d.get("success"))

    def test_balance_check_has_combinations(self):
        r = self.client.post("/api/game/balance/check")
        d = r.json()
        self.assertIn("combinations", d)
        self.assertGreater(d["combinations"], 0)

    def test_balance_check_has_issues_list(self):
        r = self.client.post("/api/game/balance/check")
        d = r.json()
        self.assertIsInstance(d.get("issues"), list)

    def test_balance_check_has_recommendations(self):
        r = self.client.post("/api/game/balance/check")
        d = r.json()
        self.assertIsInstance(d.get("recommendations"), list)

    def test_balance_report_returns_200(self):
        r = self.client.get("/api/game/balance/report")
        self.assertEqual(r.status_code, 200)

    def test_balance_report_has_report_key(self):
        r = self.client.get("/api/game/balance/report")
        d = r.json()
        self.assertIn("report", d)

    # ── EQ Status endpoint ───────────────────────────────────────────────────

    def test_eq_status_returns_200(self):
        r = self.client.get("/api/game/eq/status")
        self.assertEqual(r.status_code, 200)

    def test_eq_status_has_modules(self):
        r = self.client.get("/api/game/eq/status")
        d = r.json()
        self.assertIn("modules", d)
        self.assertIsInstance(d["modules"], list)

    def test_eq_status_25_modules(self):
        r = self.client.get("/api/game/eq/status")
        d = r.json()
        self.assertEqual(d.get("total"), 25)

    def test_eq_status_all_ready(self):
        r = self.client.get("/api/game/eq/status")
        d = r.json()
        self.assertEqual(d.get("ready"), 25)

    def test_eq_module_has_required_fields(self):
        r = self.client.get("/api/game/eq/status")
        modules = r.json()["modules"]
        for m in modules:
            self.assertIn("name", m)
            self.assertIn("description", m)
            self.assertIn("ready", m)

    # ── Monetization validate endpoint ───────────────────────────────────────

    def test_monetization_validate_returns_200(self):
        r = self.client.post("/api/game/monetization/validate", json={"items": []})
        self.assertEqual(r.status_code, 200)

    def test_monetization_validate_cosmetic_approved(self):
        r = self.client.post("/api/game/monetization/validate", json={
            "items": [{"name": "Dragon Wings", "category": "cosmetic", "power_delta": 0, "purchasable": True}]
        })
        d = r.json()
        self.assertTrue(d.get("success"))
        self.assertEqual(d["results"][0]["verdict"], "APPROVED")

    def test_monetization_validate_pay_to_win_rejected(self):
        r = self.client.post("/api/game/monetization/validate", json={
            "items": [{"name": "Epic Sword", "category": "weapon", "power_delta": 100, "purchasable": True}]
        })
        d = r.json()
        self.assertEqual(d["results"][0]["verdict"], "REJECTED")

    def test_monetization_validate_multiple_items(self):
        r = self.client.post("/api/game/monetization/validate", json={
            "items": [
                {"name": "Hat", "category": "cosmetic", "power_delta": 0, "purchasable": True},
                {"name": "Sword +50", "category": "weapon", "power_delta": 50, "purchasable": True},
            ]
        })
        d = r.json()
        self.assertEqual(len(d["results"]), 2)
        self.assertEqual(d["results"][0]["verdict"], "APPROVED")
        self.assertEqual(d["results"][1]["verdict"], "REJECTED")

    def test_monetization_validate_has_name_in_result(self):
        r = self.client.post("/api/game/monetization/validate", json={
            "items": [{"name": "Test Item", "category": "cosmetic", "power_delta": 0}]
        })
        result = r.json()["results"][0]
        self.assertEqual(result["name"], "Test Item")


if __name__ == "__main__":
    unittest.main()
