# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for ARCH-020-API: SystemUpdateRecommendationEngine REST API.

Validates:
  - Each endpoint returns expected status codes
  - Recommendation filtering by category and priority
  - Bug report ingestion produces an auto-response recommendation
  - Recommendation status update (approve / dismiss)
  - Full scan aggregates across all 5 domains
  - Error handling for invalid IDs and invalid filter values
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import system_update_api as api_module
from system_update_recommendation_engine import (
    BugReportInput,
    Recommendation,
    RecommendationType,
    SystemUpdateRecommendationEngine,
    CATEGORY_MAINTENANCE,
    CATEGORY_SDK_UPDATE,
    CATEGORY_AUTO_UPDATE,
    CATEGORY_BUG_RESPONSE,
    CATEGORY_OPERATIONS,
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_DISMISSED,
)

_CATEGORY_TO_REC_TYPE = {
    CATEGORY_MAINTENANCE: RecommendationType.MAINTENANCE,
    CATEGORY_SDK_UPDATE: RecommendationType.SDK_UPDATE,
    CATEGORY_AUTO_UPDATE: RecommendationType.AUTO_UPDATE,
    CATEGORY_BUG_RESPONSE: RecommendationType.BUG_REPORT_RESPONSE,
    CATEGORY_OPERATIONS: RecommendationType.OPERATIONAL_ANALYSIS,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine() -> SystemUpdateRecommendationEngine:
    """Create a bare engine instance with no external dependencies."""
    return SystemUpdateRecommendationEngine()


def _make_client(engine: Optional[SystemUpdateRecommendationEngine] = None) -> TestClient:
    """Build a TestClient with the given engine injected."""
    if engine is None:
        engine = _make_engine()
    api_module.set_engine(engine)
    app = FastAPI()
    app.include_router(api_module.router)
    return TestClient(app, raise_server_exceptions=True)


def _add_pending_rec(
    engine: SystemUpdateRecommendationEngine,
    category: str = CATEGORY_MAINTENANCE,
    priority: str = "medium",
) -> str:
    """Insert a pending recommendation directly into the engine store."""
    rec = Recommendation(
        recommendation_id=str(uuid.uuid4()),
        subsystem="test_subsystem",
        recommendation_type=_CATEGORY_TO_REC_TYPE[category],
        priority=priority,
        confidence_score=0.8,
        description="Test description",
        suggested_action="Test action",
        estimated_effort="< 1h",
        risk_level="low",
        auto_applicable=False,
        requires_review=True,
    )
    with engine._lock:
        engine._recommendations[rec.recommendation_id] = rec
    return rec.recommendation_id


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


class TestStatus:
    def test_returns_200(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/status")
        assert resp.status_code == 200

    def test_response_contains_engine_key(self) -> None:
        client = _make_client()
        data = client.get("/api/system-updates/status").json()
        assert "engine" in data
        assert data["engine"] == "SystemUpdateRecommendationEngine"

    def test_response_contains_subsystems(self) -> None:
        client = _make_client()
        data = client.get("/api/system-updates/status").json()
        assert "subsystems" in data


# ---------------------------------------------------------------------------
# List recommendations
# ---------------------------------------------------------------------------


class TestListRecommendations:
    def test_empty_store_returns_empty_list(self) -> None:
        engine = _make_engine()
        client = _make_client(engine)
        resp = client.get("/api/system-updates/recommendations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_pending_by_default(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/recommendations")
        assert resp.status_code == 200
        ids = [r["recommendation_id"] for r in resp.json()]
        assert rec_id in ids

    def test_filter_by_category(self) -> None:
        engine = _make_engine()
        maint_id = _add_pending_rec(engine, category=CATEGORY_MAINTENANCE)
        _add_pending_rec(engine, category=CATEGORY_SDK_UPDATE)
        client = _make_client(engine)
        resp = client.get(f"/api/system-updates/recommendations?category={CATEGORY_MAINTENANCE}")
        assert resp.status_code == 200
        ids = [r["recommendation_id"] for r in resp.json()]
        assert maint_id in ids
        for r in resp.json():
            assert r["category"] == CATEGORY_MAINTENANCE

    def test_filter_by_priority(self) -> None:
        engine = _make_engine()
        high_id = _add_pending_rec(engine, priority="high")
        _add_pending_rec(engine, priority="low")
        client = _make_client(engine)
        resp = client.get("/api/system-updates/recommendations?priority=high")
        assert resp.status_code == 200
        ids = [r["recommendation_id"] for r in resp.json()]
        assert high_id in ids
        for r in resp.json():
            assert r["priority"] == "high"

    def test_invalid_category_returns_400(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/recommendations?category=not_a_category")
        assert resp.status_code == 400

    def test_invalid_priority_returns_400(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/recommendations?priority=ultra")
        assert resp.status_code == 400

    def test_invalid_status_returns_400(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/recommendations?status=unknown_status")
        assert resp.status_code == 400

    def test_filter_by_status_approved(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        engine.approve_recommendation(rec_id)
        client = _make_client(engine)
        resp = client.get(f"/api/system-updates/recommendations?status={STATUS_APPROVED}")
        assert resp.status_code == 200
        ids = [r["recommendation_id"] for r in resp.json()]
        assert rec_id in ids


# ---------------------------------------------------------------------------
# Get single recommendation
# ---------------------------------------------------------------------------


class TestGetRecommendation:
    def test_known_id_returns_200(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        client = _make_client(engine)
        resp = client.get(f"/api/system-updates/recommendations/{rec_id}")
        assert resp.status_code == 200
        assert resp.json()["recommendation_id"] == rec_id

    def test_unknown_id_returns_404(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/recommendations/does-not-exist-999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update recommendation status
# ---------------------------------------------------------------------------


class TestUpdateRecommendationStatus:
    def test_approve_returns_200_and_approved_status(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        client = _make_client(engine)
        resp = client.put(
            f"/api/system-updates/recommendations/{rec_id}/status",
            json={"action": "approve", "approved_by": "test_user"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == STATUS_APPROVED

    def test_dismiss_returns_200_and_dismissed_status(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        client = _make_client(engine)
        resp = client.put(
            f"/api/system-updates/recommendations/{rec_id}/status",
            json={"action": "dismiss", "reason": "not applicable"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == STATUS_DISMISSED

    def test_invalid_action_returns_400(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        client = _make_client(engine)
        resp = client.put(
            f"/api/system-updates/recommendations/{rec_id}/status",
            json={"action": "execute"},
        )
        assert resp.status_code == 400

    def test_unknown_id_approve_returns_404(self) -> None:
        client = _make_client()
        resp = client.put(
            "/api/system-updates/recommendations/no-such-id/status",
            json={"action": "approve"},
        )
        assert resp.status_code == 404

    def test_unknown_id_dismiss_returns_404(self) -> None:
        client = _make_client()
        resp = client.put(
            "/api/system-updates/recommendations/no-such-id/status",
            json={"action": "dismiss"},
        )
        assert resp.status_code == 404

    def test_double_approve_returns_422(self) -> None:
        engine = _make_engine()
        rec_id = _add_pending_rec(engine)
        engine.approve_recommendation(rec_id)
        client = _make_client(engine)
        resp = client.put(
            f"/api/system-updates/recommendations/{rec_id}/status",
            json={"action": "approve"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Maintenance domain
# ---------------------------------------------------------------------------


class TestMaintenanceDomain:
    def test_maintenance_scan_returns_200(self) -> None:
        client = _make_client()
        resp = client.post("/api/system-updates/maintenance/scan")
        assert resp.status_code == 200

    def test_maintenance_scan_returns_recommendations(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/maintenance/scan").json()
        assert data["domain"] == "maintenance"
        assert data["new_recommendations"] >= 0

    def test_maintenance_recommendations_returns_200(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_MAINTENANCE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/maintenance/recommendations")
        assert resp.status_code == 200

    def test_maintenance_recommendations_only_maintenance_category(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_MAINTENANCE)
        _add_pending_rec(engine, category=CATEGORY_SDK_UPDATE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/maintenance/recommendations")
        for r in resp.json():
            assert r["category"] == CATEGORY_MAINTENANCE

    def test_maintenance_recommendations_invalid_priority_400(self) -> None:
        client = _make_client()
        resp = client.get("/api/system-updates/maintenance/recommendations?priority=nope")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# SDK update domain
# ---------------------------------------------------------------------------


class TestSDKDomain:
    def test_sdk_scan_returns_200(self) -> None:
        client = _make_client()
        resp = client.post("/api/system-updates/sdk/scan")
        assert resp.status_code == 200

    def test_sdk_scan_domain_field(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/sdk/scan").json()
        assert data["domain"] == "sdk_update"

    def test_sdk_recommendations_returns_200(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_SDK_UPDATE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/sdk/recommendations")
        assert resp.status_code == 200

    def test_sdk_recommendations_only_sdk_category(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_SDK_UPDATE)
        _add_pending_rec(engine, category=CATEGORY_MAINTENANCE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/sdk/recommendations")
        for r in resp.json():
            assert r["category"] == CATEGORY_SDK_UPDATE


# ---------------------------------------------------------------------------
# Auto-update domain
# ---------------------------------------------------------------------------


class TestAutoUpdateDomain:
    def test_auto_update_scan_returns_200(self) -> None:
        client = _make_client()
        resp = client.post("/api/system-updates/auto-update/scan")
        assert resp.status_code == 200

    def test_auto_update_scan_domain_field(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/auto-update/scan").json()
        assert data["domain"] == "auto_update"

    def test_auto_update_recommendations_returns_200(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_AUTO_UPDATE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/auto-update/recommendations")
        assert resp.status_code == 200

    def test_auto_update_recommendations_only_auto_update_category(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_AUTO_UPDATE)
        _add_pending_rec(engine, category=CATEGORY_OPERATIONS)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/auto-update/recommendations")
        for r in resp.json():
            assert r["category"] == CATEGORY_AUTO_UPDATE


# ---------------------------------------------------------------------------
# Bug responses domain
# ---------------------------------------------------------------------------


class TestBugResponsesDomain:
    def test_ingest_returns_200_and_auto_response(self) -> None:
        engine = _make_engine()
        client = _make_client(engine)
        resp = client.post(
            "/api/system-updates/bug-responses/ingest",
            json={
                "title": "Crash on login",
                "description": "Critical crash when user attempts to login",
                "component": "auth_service",
                "severity": "critical",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
        assert "auto_response_id" in data
        assert "classification" in data
        assert "recommendation_id" in data

    def test_ingest_creates_recommendation_in_store(self) -> None:
        engine = _make_engine()
        client = _make_client(engine)
        resp = client.post(
            "/api/system-updates/bug-responses/ingest",
            json={
                "title": "Error on logout",
                "description": "Exception thrown during logout flow",
                "component": "auth_service",
            },
        )
        rec_id = resp.json()["recommendation_id"]
        rec = engine.get_recommendation(rec_id)
        assert rec is not None
        assert rec.category == CATEGORY_BUG_RESPONSE

    def test_ingest_generates_report_id_when_not_provided(self) -> None:
        client = _make_client()
        resp = client.post(
            "/api/system-updates/bug-responses/ingest",
            json={"title": "Test bug", "description": "Bug description"},
        )
        assert resp.status_code == 200
        assert resp.json()["report_id"] is not None

    def test_bug_response_recommendations_returns_200(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_BUG_RESPONSE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/bug-responses/recommendations")
        assert resp.status_code == 200

    def test_bug_response_recommendations_only_bug_response_category(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_BUG_RESPONSE)
        _add_pending_rec(engine, category=CATEGORY_MAINTENANCE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/bug-responses/recommendations")
        for r in resp.json():
            assert r["category"] == CATEGORY_BUG_RESPONSE


# ---------------------------------------------------------------------------
# Operations domain
# ---------------------------------------------------------------------------


class TestOperationsDomain:
    def test_operations_analyze_returns_200(self) -> None:
        client = _make_client()
        resp = client.post("/api/system-updates/operations/analyze")
        assert resp.status_code == 200

    def test_operations_analyze_includes_health(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/operations/analyze").json()
        assert "health" in data
        assert "overall_score" in data["health"]

    def test_operations_recommendations_returns_200(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_OPERATIONS)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/operations/recommendations")
        assert resp.status_code == 200

    def test_operations_recommendations_only_operations_category(self) -> None:
        engine = _make_engine()
        _add_pending_rec(engine, category=CATEGORY_OPERATIONS)
        _add_pending_rec(engine, category=CATEGORY_SDK_UPDATE)
        client = _make_client(engine)
        resp = client.get("/api/system-updates/operations/recommendations")
        for r in resp.json():
            assert r["category"] == CATEGORY_OPERATIONS


# ---------------------------------------------------------------------------
# Full scan
# ---------------------------------------------------------------------------


class TestFullScan:
    def test_full_scan_returns_200(self) -> None:
        client = _make_client()
        resp = client.post("/api/system-updates/full-scan")
        assert resp.status_code == 200

    def test_full_scan_scans_all_5_domains(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/full-scan").json()
        assert data["status"] == "ok"
        domains = data["domains_scanned"]
        assert set(domains) == {
            "maintenance",
            "sdk_update",
            "auto_update",
            "bug_response",
            "operations",
        }

    def test_full_scan_returns_new_recommendation_count(self) -> None:
        engine = _make_engine()
        client = _make_client(engine)
        data = client.post("/api/system-updates/full-scan").json()
        assert isinstance(data["new_recommendations"], int)
        assert data["new_recommendations"] > 0

    def test_full_scan_includes_engine_status(self) -> None:
        client = _make_client()
        data = client.post("/api/system-updates/full-scan").json()
        assert "engine_status" in data
        assert "recommendations" in data["engine_status"]

    def test_full_scan_populates_all_categories(self) -> None:
        engine = _make_engine()
        client = _make_client(engine)
        client.post("/api/system-updates/full-scan")
        # After full scan, at least one recommendation per category should exist
        categories_seen = {
            r.category for r in engine._recommendations.values()
        }
        expected = {
            CATEGORY_MAINTENANCE,
            CATEGORY_SDK_UPDATE,
            CATEGORY_AUTO_UPDATE,
            CATEGORY_BUG_RESPONSE,
            CATEGORY_OPERATIONS,
        }
        assert expected.issubset(categories_seen)
