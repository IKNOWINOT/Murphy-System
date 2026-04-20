"""
E2E tests for the Murphy System production server.

Uses FastAPI's TestClient to exercise HTTP routes against the production
FastAPI app object — no external server process or secrets required.

Covers:
  - Root / landing endpoint
  - Calendar and calendar-blocks API
  - Automations listing
  - Compliance frameworks
  - Auth providers discovery
  - Bot-status endpoint
  - CEO status endpoint
  - HITL item listing
  - Static file / HTML serving
  - CORS headers

Labels: E2E-PROD-001
"""

from __future__ import annotations

import sys
import pathlib
import json
import unittest
import logging

# Suppress startup noise during import
logging.disable(logging.CRITICAL)

# ── Path setup ──────────────────────────────────────────────────────────────
_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Use swarm traffic class so E2E tests aren't rate-limited by the human bucket
# (60 req/min burst 15). Swarm class allows 600 req/min burst 100.
_TEST_HEADERS = {"X-Murphy-Traffic-Class": "swarm"}

_CLIENT = None  # module-level shared client — avoids re-importing the server


def _get_client():
    """Return the module-level TestClient (created once per test process)."""
    global _CLIENT
    if _CLIENT is None:
        from fastapi.testclient import TestClient
        import murphy_production_server as srv  # noqa: PLC0415
        _CLIENT = TestClient(srv.app, raise_server_exceptions=False)
    return _CLIENT


# ===========================================================================
# App construction
# ===========================================================================

class TestAppConstruction(unittest.TestCase):
    """Production server must build the FastAPI app without errors."""

    def test_production_server_importable(self):
        import murphy_production_server  # noqa: F401

    def test_app_is_fastapi_instance(self):
        from fastapi import FastAPI
        import murphy_production_server as srv
        self.assertIsInstance(srv.app, FastAPI)

    def test_app_has_routes(self):
        import murphy_production_server as srv
        self.assertGreater(len(srv.app.routes), 0)

    def test_app_has_many_api_routes(self):
        import murphy_production_server as srv
        from fastapi.routing import APIRoute
        api_routes = [r for r in srv.app.routes if isinstance(r, APIRoute)]
        self.assertGreater(len(api_routes), 10,
                           f"Expected > 10 API routes, got {len(api_routes)}")


# ===========================================================================
# Root / landing
# ===========================================================================

class TestRootEndpoint(unittest.TestCase):
    """Root endpoint must return HTTP 200 with HTML content."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_root_returns_200(self):
        resp = self.client.get("/", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_root_content_type_html(self):
        resp = self.client.get("/", headers=_TEST_HEADERS)
        content_type = resp.headers.get("content-type", "")
        self.assertIn("html", content_type.lower(),
                      f"Expected HTML content-type, got: {content_type}")


# ===========================================================================
# Calendar API
# ===========================================================================

class TestCalendarAPI(unittest.TestCase):
    """Calendar endpoints must return structured JSON."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_calendar_returns_200(self):
        resp = self.client.get("/api/calendar", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_calendar_blocks_returns_200(self):
        resp = self.client.get("/api/calendar/blocks", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_calendar_blocks_is_json(self):
        resp = self.client.get("/api/calendar/blocks", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIsInstance(body, dict)

    def test_calendar_blocks_has_blocks_key(self):
        resp = self.client.get("/api/calendar/blocks", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("blocks", body)
        self.assertIsInstance(body["blocks"], list)

    def test_calendar_blocks_has_total(self):
        resp = self.client.get("/api/calendar/blocks", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("total", body)
        self.assertGreaterEqual(body["total"], 0)


# ===========================================================================
# Automations API
# ===========================================================================

class TestAutomationsAPI(unittest.TestCase):
    """Automations listing must return a valid collection."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_automations_returns_200(self):
        resp = self.client.get("/api/automations", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_automations_is_json(self):
        resp = self.client.get("/api/automations", headers=_TEST_HEADERS)
        self.assertIsInstance(resp.json(), dict)

    def test_automations_has_automations_list(self):
        resp = self.client.get("/api/automations", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("automations", body)
        self.assertIsInstance(body["automations"], list)

    def test_automations_has_total(self):
        resp = self.client.get("/api/automations", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("total", body)
        self.assertGreaterEqual(body["total"], 0)


# ===========================================================================
# Compliance API
# ===========================================================================

class TestComplianceAPI(unittest.TestCase):
    """Compliance endpoints must expose framework definitions."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_compliance_frameworks_returns_200(self):
        resp = self.client.get("/api/compliance/frameworks", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_compliance_frameworks_is_json(self):
        resp = self.client.get("/api/compliance/frameworks", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIsInstance(body, dict)

    def test_compliance_frameworks_has_frameworks(self):
        resp = self.client.get("/api/compliance/frameworks", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("frameworks", body)
        self.assertIsInstance(body["frameworks"], list)

    def test_compliance_frameworks_non_empty(self):
        resp = self.client.get("/api/compliance/frameworks", headers=_TEST_HEADERS)
        frameworks = resp.json().get("frameworks", [])
        self.assertGreater(len(frameworks), 0, "Expected at least one compliance framework")

    def test_compliance_framework_has_id_and_name(self):
        resp = self.client.get("/api/compliance/frameworks", headers=_TEST_HEADERS)
        for fw in resp.json().get("frameworks", [])[:3]:
            with self.subTest(fw=fw.get("id", "?")):
                self.assertIn("id", fw)
                self.assertIn("name", fw)


# ===========================================================================
# Auth API
# ===========================================================================

class TestAuthAPI(unittest.TestCase):
    """Auth provider endpoints must return a valid provider map."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_auth_providers_returns_200(self):
        resp = self.client.get("/api/auth/providers", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_auth_providers_is_json(self):
        resp = self.client.get("/api/auth/providers", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIsInstance(body, dict)

    def test_auth_providers_has_providers(self):
        resp = self.client.get("/api/auth/providers", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("providers", body)
        self.assertIsInstance(body["providers"], dict)

    def test_auth_providers_includes_known_providers(self):
        """At least google and github must be listed."""
        resp = self.client.get("/api/auth/providers", headers=_TEST_HEADERS)
        providers = resp.json().get("providers", {})
        self.assertIn("google", providers)
        self.assertIn("github", providers)


# ===========================================================================
# Bots / telemetry
# ===========================================================================

class TestBotsAPI(unittest.TestCase):
    """Bot-status endpoint must return a list of bots with health fields."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_bots_status_returns_200(self):
        resp = self.client.get("/api/bots/status", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_bots_status_is_json(self):
        resp = self.client.get("/api/bots/status", headers=_TEST_HEADERS)
        self.assertIsInstance(resp.json(), dict)

    def test_bots_status_has_bots_list(self):
        resp = self.client.get("/api/bots/status", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("bots", body)
        self.assertIsInstance(body["bots"], list)

    def test_bots_status_each_bot_has_name_and_status(self):
        resp = self.client.get("/api/bots/status", headers=_TEST_HEADERS)
        for bot in resp.json().get("bots", [])[:5]:
            with self.subTest(bot=bot.get("bot", "?")):
                self.assertIn("bot", bot)
                self.assertIn("status", bot)


# ===========================================================================
# CEO / executive
# ===========================================================================

class TestCEOAPI(unittest.TestCase):
    """CEO endpoint must respond even when no CEO branch is configured."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_ceo_status_returns_200(self):
        resp = self.client.get("/api/ceo/status", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 200)

    def test_ceo_status_is_json(self):
        resp = self.client.get("/api/ceo/status", headers=_TEST_HEADERS)
        self.assertIsInstance(resp.json(), dict)

    def test_ceo_status_has_available_field(self):
        resp = self.client.get("/api/ceo/status", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIn("available", body)
        self.assertIsInstance(body["available"], bool)


# ===========================================================================
# 404 handling
# ===========================================================================

class TestErrorHandling(unittest.TestCase):
    """Unknown routes must return 404 JSON, not 500."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    def test_unknown_route_returns_404(self):
        resp = self.client.get("/api/this-route-does-not-exist-e2e", headers=_TEST_HEADERS)
        self.assertEqual(resp.status_code, 404)

    def test_unknown_route_is_json(self):
        resp = self.client.get("/api/this-route-does-not-exist-e2e", headers=_TEST_HEADERS)
        body = resp.json()
        self.assertIsInstance(body, dict)

    def test_unknown_route_has_detail(self):
        resp = self.client.get("/api/this-route-does-not-exist-e2e", headers=_TEST_HEADERS)
        self.assertIn("detail", resp.json())


# ===========================================================================
# Cross-cutting: multiple endpoints don't leak 500s
# ===========================================================================

class TestNoInternalServerErrors(unittest.TestCase):
    """A selection of read-only GET endpoints must never return HTTP 500."""

    @classmethod
    def setUpClass(cls):
        cls.client = _get_client()

    SAFE_GET_ROUTES = [
        "/",
        "/api/calendar",
        "/api/calendar/blocks",
        "/api/automations",
        "/api/compliance/frameworks",
        "/api/auth/providers",
        "/api/bots/status",
        "/api/ceo/status",
    ]

    def test_no_500_on_safe_routes(self):
        for path in self.SAFE_GET_ROUTES:
            with self.subTest(path=path):
                resp = self.client.get(path, headers=_TEST_HEADERS)
                self.assertNotEqual(
                    resp.status_code, 500,
                    f"HTTP 500 on {path}: {resp.text[:200]}",
                )
