"""
Tests for Trading Routes — Murphy System

Verifies API endpoints return correct data using FastAPI TestClient.
"""

import sys
import os
import unittest


try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from trading_routes import create_trading_router
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi not available")
class TestTradingRoutesAPI(unittest.TestCase):
    """FastAPI route tests via TestClient."""

    @classmethod
    def setUpClass(cls):
        app    = FastAPI()
        router = create_trading_router()
        app.include_router(router)
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_status_endpoint_returns_200(self):
        r = self.client.get("/api/trading/status")
        self.assertEqual(r.status_code, 200)

    def test_status_response_has_state_field(self):
        r = self.client.get("/api/trading/status")
        d = r.json()
        self.assertIn("state", d)

    def test_mode_get_returns_200(self):
        r = self.client.get("/api/trading/mode")
        self.assertEqual(r.status_code, 200)

    def test_mode_get_returns_paper_by_default(self):
        r = self.client.get("/api/trading/mode")
        self.assertEqual(r.json()["mode"], "paper")

    def test_portfolio_endpoint_returns_200(self):
        r = self.client.get("/api/trading/portfolio")
        self.assertEqual(r.status_code, 200)

    def test_portfolio_history_endpoint_returns_200(self):
        r = self.client.get("/api/trading/portfolio/history")
        self.assertEqual(r.status_code, 200)
        self.assertIn("history", r.json())

    def test_positions_endpoint_returns_200(self):
        r = self.client.get("/api/trading/positions")
        self.assertEqual(r.status_code, 200)
        self.assertIn("positions", r.json())

    def test_trades_endpoint_returns_200(self):
        r = self.client.get("/api/trading/trades")
        self.assertEqual(r.status_code, 200)
        self.assertIn("trades", r.json())

    def test_trades_today_endpoint_returns_200(self):
        r = self.client.get("/api/trading/trades/today")
        self.assertEqual(r.status_code, 200)
        self.assertIn("trades", r.json())

    def test_sweep_status_returns_200(self):
        r = self.client.get("/api/trading/sweep/status")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("next_sweep", d)
        self.assertIn("stats", d)

    def test_sweep_history_returns_200(self):
        r = self.client.get("/api/trading/sweep/history")
        self.assertEqual(r.status_code, 200)
        self.assertIn("history", r.json())

    def test_sweep_trigger_dry_run_returns_200(self):
        r = self.client.post(
            "/api/trading/sweep/trigger",
            json={"dry_run": True, "portfolio_value": 11000.0},
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d.get("success"))
        self.assertIn("record", d)

    def test_sweep_trigger_record_has_status(self):
        r = self.client.post(
            "/api/trading/sweep/trigger",
            json={"dry_run": True, "portfolio_value": 11000.0},
        )
        record = r.json()["record"]
        self.assertIn("status", record)

    def test_atom_balance_endpoint_returns_200(self):
        r = self.client.get("/api/trading/sweep/atom-balance")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("atom_staked", d)
        self.assertIn("staking_apy", d)

    def test_invalid_mode_switch_returns_400(self):
        r = self.client.post("/api/trading/mode", json={"mode": "invalid_mode"})
        self.assertEqual(r.status_code, 400)

    def test_live_mode_switch_blocked_without_gates(self):
        r = self.client.post("/api/trading/mode", json={"mode": "live"})
        # Live mode should be blocked (403) because gates don't pass
        self.assertIn(r.status_code, [403, 500])

    def test_start_orchestrator_returns_200(self):
        r = self.client.post("/api/trading/start")
        self.assertEqual(r.status_code, 200)

    def test_stop_orchestrator_returns_200(self):
        r = self.client.post("/api/trading/stop")
        self.assertEqual(r.status_code, 200)

    def test_unknown_position_returns_404(self):
        r = self.client.get("/api/trading/positions/nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_sweep_history_limit_param(self):
        r = self.client.get("/api/trading/sweep/history?limit=5")
        self.assertEqual(r.status_code, 200)

    # ── Emergency / Risk / Graduation endpoints ──────────────────────────────

    def test_emergency_status_returns_200(self):
        r = self.client.get("/api/trading/emergency/status")
        self.assertEqual(r.status_code, 200)

    def test_emergency_status_has_required_fields(self):
        r = self.client.get("/api/trading/emergency/status")
        d = r.json()
        self.assertIn("emergency_stop_active", d)
        self.assertIn("trading_allowed", d)

    def test_emergency_trigger_returns_200(self):
        r = self.client.post("/api/trading/emergency/trigger")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d.get("success"))

    def test_risk_assessment_returns_200(self):
        r = self.client.get("/api/trading/risk/assessment")
        self.assertEqual(r.status_code, 200)

    def test_risk_assessment_has_risk_level(self):
        r = self.client.get("/api/trading/risk/assessment")
        d = r.json()
        self.assertIn("risk_level", d)

    def test_graduation_status_returns_200(self):
        r = self.client.get("/api/trading/graduation/status")
        self.assertEqual(r.status_code, 200)

    def test_graduation_status_has_graduated_field(self):
        r = self.client.get("/api/trading/graduation/status")
        d = r.json()
        self.assertIn("graduated", d)


if __name__ == "__main__":
    unittest.main()
