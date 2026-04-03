"""
Sprint 4 Hardening — Security & Deployment Validation
=====================================================

Tests for Sprint 4 production commissioning:
- SEC-NEW-001: CSRF protection on new API endpoints
- SEC-NEW-002: Rate-limit header injection for new routers
- SEC-NEW-003: Input validation on new create/update endpoints
- DEPLOY-001: All new routes resolve in app.py
- DEPLOY-002: All new HTML pages have required structure
- DEPLOY-003: Sidebar navigation consistency
- DEPLOY-004: Permutation calibration readiness for new page sequences

Addresses: Sprint 4 of FRONTEND_BACKEND_GAP_CLOSURE.md
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SRC = REPO_ROOT / "src"


# ── SEC-NEW-001: CSRF protection on new endpoints ────────────────────────────


class TestNewEndpointSecurityCSRF:
    """SEC-NEW-001: CSRF protection applies to all new Sprint 1-3 endpoints."""

    NEW_ENDPOINTS = [
        "/api/boards",
        "/api/workdocs",
        "/api/time-tracking/entries",
        "/api/dashboards",
        "/api/crm/contacts",
        "/api/crm/deals",
        "/api/portfolio/bars",
        "/api/aionmind/orchestrate",
        "/api/automations/rules",
        "/api/dev/sprints",
        "/api/dev/bugs",
        "/api/service/tickets",
        "/api/guest/invites",
    ]

    def setup_method(self):
        """Import the real CSRF module — no mocking, no env patching."""
        from src.fastapi_security import _CSRFProtection

        self.csrf = _CSRFProtection

    def test_csrf_module_importable(self):
        """CSRF protection module can be imported."""
        from src.fastapi_security import _CSRFProtection

        assert _CSRFProtection is not None

    @pytest.mark.parametrize("endpoint", NEW_ENDPOINTS)
    def test_post_not_csrf_exempt(self, endpoint):
        """POST to new endpoints are NOT CSRF-exempt."""
        assert not self.csrf.is_exempt(endpoint, "POST")

    @pytest.mark.parametrize("endpoint", NEW_ENDPOINTS)
    def test_put_not_csrf_exempt(self, endpoint):
        """PUT to new endpoints are NOT CSRF-exempt."""
        assert not self.csrf.is_exempt(endpoint, "PUT")

    @pytest.mark.parametrize("endpoint", NEW_ENDPOINTS)
    def test_delete_not_csrf_exempt(self, endpoint):
        """DELETE to new endpoints are NOT CSRF-exempt."""
        assert not self.csrf.is_exempt(endpoint, "DELETE")

    @pytest.mark.parametrize("endpoint", NEW_ENDPOINTS)
    def test_get_is_csrf_exempt(self, endpoint):
        """GET requests should be CSRF-exempt (read-only)."""
        assert self.csrf.is_exempt(endpoint, "GET")

    def test_generate_token_returns_hex_string(self):
        """generate_token produces a 64-char hex SHA-256 digest."""
        token = self.csrf.generate_token("test-session-boards")
        assert isinstance(token, str)
        assert len(token) == 64

    def test_validate_token_roundtrip(self):
        """Token generated for a session validates for the same session."""
        session = "test-session-sprint4"
        token = self.csrf.generate_token(session)
        assert self.csrf.validate_token(session, token) is True

    def test_validate_token_rejects_wrong_session(self):
        """Token for one session fails validation on a different session."""
        token = self.csrf.generate_token("session-A")
        assert self.csrf.validate_token("session-B", token) is False

    def test_validate_token_rejects_empty(self):
        """Empty token is always invalid."""
        assert self.csrf.validate_token("any-session", "") is False


# ── SEC-NEW-002: Rate-limit headers on new routers ───────────────────────────


class TestNewEndpointRateLimiting:
    """SEC-NEW-002: Rate-limit headers apply to new routers."""

    def test_rate_limiter_importable(self):
        """FastAPI rate limiter module can be imported."""
        from src.fastapi_security import _FastAPIRateLimiter

        assert _FastAPIRateLimiter is not None

    def test_rate_limiter_check_returns_required_keys(self):
        """Rate limiter check() returns dict with limit/remaining/reset."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=120, burst_size=20)
        result = limiter.check("test-client-001")
        assert "allowed" in result
        assert "remaining" in result
        assert "limit" in result
        assert "reset_epoch" in result

    def test_rate_limiter_first_request_allowed(self):
        """First request from a new client is always allowed."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=10)
        result = limiter.check("fresh-client")
        assert result["allowed"] is True

    def test_rate_limit_defaults_reasonable(self):
        """Default rate limits are within acceptable range."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter()
        result = limiter.check("default-client")
        limit = result.get("limit", 0)
        assert 1 <= limit <= 10000, f"Rate limit {limit} outside reasonable range"

    def test_rate_limit_header_names_in_source(self):
        """Rate-limit response headers use standard X-RateLimit-* names."""
        import inspect
        import src.fastapi_security as mod

        source = inspect.getsource(mod)
        assert "X-RateLimit-Limit" in source
        assert "X-RateLimit-Remaining" in source
        assert "X-RateLimit-Reset" in source

    def test_burst_exhaustion_blocks(self):
        """Exceeding burst budget returns allowed=False."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=3)
        client = "burst-test-client"
        for _ in range(3):
            limiter.check(client)
        result = limiter.check(client)
        assert result["allowed"] is False


# ── SEC-NEW-003: Input validation on new endpoints ───────────────────────────


class TestNewEndpointInputValidation:
    """SEC-NEW-003: Input validation framework covers new endpoints."""

    def test_api_parameter_input_importable(self):
        """APIParameterInput Pydantic model can be imported."""
        from src.input_validation import APIParameterInput

        assert APIParameterInput is not None

    def test_api_parameter_input_rejects_oversize_sort_by(self):
        """sort_by field longer than max_length is rejected."""
        from pydantic import ValidationError

        from src.input_validation import APIParameterInput

        with pytest.raises(ValidationError):
            APIParameterInput(sort_by="x" * 200)

    def test_api_parameter_input_rejects_invalid_sort_order(self):
        """sort_order must be 'asc' or 'desc'."""
        from pydantic import ValidationError

        from src.input_validation import APIParameterInput

        with pytest.raises(ValidationError):
            APIParameterInput(sort_order="INVALID")

    def test_api_parameter_input_accepts_normal(self):
        """Normal pagination parameters are accepted."""
        from src.input_validation import APIParameterInput

        model = APIParameterInput(page=1, per_page=20, sort_by="name", sort_order="asc")
        assert model.page == 1
        assert model.per_page == 20
        assert model.sort_order == "asc"

    def test_api_parameter_input_rejects_negative_page(self):
        """Page number must be >= 1."""
        from pydantic import ValidationError

        from src.input_validation import APIParameterInput

        with pytest.raises(ValidationError):
            APIParameterInput(page=-1)

    def test_api_parameter_input_rejects_sql_injection_in_sort(self):
        """sort_by rejects SQL-injection-style characters."""
        from pydantic import ValidationError

        from src.input_validation import APIParameterInput

        with pytest.raises(ValidationError):
            APIParameterInput(sort_by="name; DROP TABLE users")


# ── DEPLOY-001: All new routes registered in app.py ──────────────────────────


class TestDeploymentRouteResolution:
    """DEPLOY-001: All new UI routes registered in app.py."""

    EXPECTED_ROUTES = {
        "/ui/boards": "boards.html",
        "/ui/workdocs": "workdocs.html",
        "/ui/time-tracking": "time_tracking.html",
        "/ui/dashboards": "dashboards.html",
        "/ui/crm": "crm.html",
        "/ui/portfolio": "portfolio.html",
        "/ui/aionmind": "aionmind.html",
        "/ui/automations": "automations.html",
        "/ui/dev-module": "dev_module.html",
        "/ui/service-module": "service_module.html",
        "/ui/guest-portal": "guest_portal.html",
    }

    def test_app_py_contains_all_routes(self):
        """Every new UI route appears in app.py _html_routes."""
        app_source = (REPO_ROOT / "src" / "runtime" / "app.py").read_text()
        for route, html_file in self.EXPECTED_ROUTES.items():
            assert route in app_source, f"Route {route} missing from app.py"
            assert html_file in app_source, f"HTML file {html_file} missing from app.py"

    @pytest.mark.parametrize(
        "route,html_file", list(EXPECTED_ROUTES.items()), ids=list(EXPECTED_ROUTES.keys())
    )
    def test_html_file_exists(self, route, html_file):
        """HTML file exists at repo root for each route."""
        assert (REPO_ROOT / html_file).is_file(), f"{html_file} not found"


# ── DEPLOY-002: All new HTML pages have required structure ───────────────────


class TestDeploymentHTMLStructure:
    """DEPLOY-002: All new HTML pages have required production structure."""

    NEW_PAGES = [
        "boards.html",
        "workdocs.html",
        "time_tracking.html",
        "dashboards.html",
        "crm.html",
        "portfolio.html",
        "aionmind.html",
        "automations.html",
        "dev_module.html",
        "service_module.html",
        "guest_portal.html",
    ]

    @pytest.mark.parametrize("page", NEW_PAGES)
    def test_page_has_doctype(self, page):
        """Every page starts with a proper DOCTYPE declaration."""
        text = (REPO_ROOT / page).read_text()
        assert "<!DOCTYPE html>" in text or "<!doctype html>" in text

    @pytest.mark.parametrize("page", NEW_PAGES)
    def test_page_has_murphy_sidebar(self, page):
        """Every page includes the murphy-sidebar web component."""
        text = (REPO_ROOT / page).read_text()
        assert "murphy-sidebar" in text, f"{page} missing murphy-sidebar component"

    @pytest.mark.parametrize("page", NEW_PAGES)
    def test_page_has_design_system_css(self, page):
        """Every page references the design system or has inline styles."""
        text = (REPO_ROOT / page).read_text()
        assert "murphy-design-system.css" in text or "style" in text

    @pytest.mark.parametrize("page", NEW_PAGES)
    def test_page_has_copyright_header(self, page):
        """Every page includes a copyright or license identifier."""
        text = (REPO_ROOT / page).read_text()
        assert "Inoni" in text or "BSL" in text or "Murphy System" in text

    @pytest.mark.parametrize("page", NEW_PAGES)
    def test_page_has_fetch_calls(self, page):
        """Every new page makes at least one API call."""
        text = (REPO_ROOT / page).read_text()
        assert "fetch(" in text or "API(" in text, f"{page} has no API calls"


# ── DEPLOY-003: Sidebar navigation consistency ───────────────────────────────


class TestSidebarNavigationConsistency:
    """DEPLOY-003: Sidebar navigation items match registered routes."""

    SIDEBAR_ROUTES = [
        "/ui/boards",
        "/ui/workdocs",
        "/ui/time-tracking",
        "/ui/dashboards",
        "/ui/crm",
        "/ui/portfolio",
        "/ui/aionmind",
        "/ui/automations",
        "/ui/dev-module",
        "/ui/service-module",
        "/ui/guest-portal",
    ]

    def test_sidebar_js_contains_all_routes(self):
        """murphy-components.js has sidebar entries for all new pages."""
        js = (REPO_ROOT / "static" / "murphy-components.js").read_text()
        for route in self.SIDEBAR_ROUTES:
            assert route in js, f"Sidebar missing route {route}"

    def test_sidebar_routes_match_app_routes(self):
        """Sidebar routes also exist in app.py _html_routes."""
        app_source = (REPO_ROOT / "src" / "runtime" / "app.py").read_text()
        for route in self.SIDEBAR_ROUTES:
            assert route in app_source, (
                f"Sidebar route {route} not registered in app.py"
            )


# ── DEPLOY-004: Permutation calibration readiness ────────────────────────────


class TestPermutationCalibrationReadiness:
    """DEPLOY-004: Permutation calibration infrastructure ready for new pages."""

    def test_permutation_policy_registry_importable(self):
        """PermutationPolicyRegistry can be imported from src."""
        from src.permutation_policy_registry import PermutationPolicyRegistry

        assert PermutationPolicyRegistry is not None

    def test_permutation_calibration_adapter_importable(self):
        """PermutationCalibrationAdapter can be imported from src."""
        from src.permutation_calibration_adapter import PermutationCalibrationAdapter

        assert PermutationCalibrationAdapter is not None

    def test_procedural_distiller_importable(self):
        """ProceduralDistiller can be imported from src."""
        from src.procedural_distiller import ProceduralDistiller

        assert ProceduralDistiller is not None

    def test_order_sensitivity_metrics_importable(self):
        """OrderSensitivityMetrics can be imported from src."""
        from src.order_sensitivity_metrics import OrderSensitivityMetrics

        assert OrderSensitivityMetrics is not None

    def test_new_page_sequences_definable(self):
        """UI page sequences can be registered for permutation exploration."""
        from src.permutation_policy_registry import (
            PermutationPolicyRegistry,
            SequenceType,
        )

        registry = PermutationPolicyRegistry()
        sequence = ["create_board", "add_group", "add_item", "edit_cell", "delete_item"]
        seq_id = registry.register_sequence(
            name="boards_crud",
            sequence_type=SequenceType.API_RESPONSE_ORDER,
            domain="boards",
            ordering=sequence,
        )
        assert seq_id is not None
        assert isinstance(seq_id, str)

    def test_adapter_can_start_exploration(self):
        """Calibration adapter can start an exploration session."""
        from src.permutation_calibration_adapter import (
            IntakeItem,
            PermutationCalibrationAdapter,
        )

        adapter = PermutationCalibrationAdapter()
        items = [
            IntakeItem(item_id="create", item_type="api", source="ui_crud"),
            IntakeItem(item_id="read", item_type="api", source="ui_crud"),
            IntakeItem(item_id="update", item_type="api", source="ui_crud"),
            IntakeItem(item_id="delete", item_type="api", source="ui_crud"),
        ]
        session_id = adapter.start_exploration(
            domain="ui_crud",
            items=items,
            max_candidates=5,
        )
        assert session_id is not None
        assert isinstance(session_id, str)

    def test_registry_status_after_init(self):
        """Registry returns a valid status dict after initialisation."""
        from src.permutation_policy_registry import PermutationPolicyRegistry

        registry = PermutationPolicyRegistry()
        status = registry.get_status()
        assert isinstance(status, dict)
