"""
UI Autopilot Tester Agent — Tests

Comprehensive test suite for the Murphy UI Autopilot Tester Agent that
validates authentication, endpoint probing, MultiCursor UI scanning,
feedback generation, fix strategy inference, and end-to-end phase execution.

Design Label: TEST-UI-AUTOPILOT-001
Owner: Production Commissioning Team

Commissioning Gates:
  G1: Agent authenticates, scans, generates feedback, and infers fixes
  G2: Spec — agent login, MCB scanning, structured feedback, PR-ready output
  G3: Conditions — stub auth, stub probes, empty results, full pipeline
  G4: Test profile covers authentication, probing, MCB, feedback, fixes
  G5: Expected vs actual verified at every assertion
  G8: Error handling — failed auth, missing reports, bad probe responses
  G9: Re-commission after all above
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src/ is on the path for Murphy System imports
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in [_repo_root, os.path.join(_repo_root, "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Force test environment
os.environ.setdefault("MURPHY_ENV", "test")
os.environ.setdefault("MURPHY_DB_MODE", "stub")
os.environ.setdefault("E2EE_STUB_ALLOWED", "true")
os.environ.setdefault("MURPHY_POOL_MODE", "simulated")

# Import agent components
sys.path.insert(0, os.path.join(_repo_root, "scripts"))
from ui_autopilot_tester_agent import (
    AGENT_ID,
    AGENT_LABEL,
    AGENT_VERSION,
    KNOWN_API_ENDPOINTS,
    KNOWN_UI_PAGES,
    AgentAuthenticator,
    EndpointProbeResult,
    EndpointProber,
    FeedbackGenerator,
    FeedbackReport,
    MultiCursorUIScanner,
    UIPageProbeResult,
    _infer_fix_strategy,
    phase_feedback,
    phase_fix,
    phase_login,
    phase_scan,
    run_all_phases,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory."""
    return tmp_path / "ui_autopilot"


@pytest.fixture
def authenticator():
    """Fresh AgentAuthenticator in test mode."""
    with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
        return AgentAuthenticator()


@pytest.fixture
def sample_api_results():
    """Sample API probe results — mix of pass/fail."""
    return [
        EndpointProbeResult(
            method="GET", path="/api/health", category="health",
            description="Health check", expected_status=200,
            actual_status=200, passed=True, response_time_ms=5.0,
        ),
        EndpointProbeResult(
            method="GET", path="/api/status", category="health",
            description="Status", expected_status=200,
            actual_status=200, passed=True, response_time_ms=8.0,
        ),
        EndpointProbeResult(
            method="GET", path="/api/missing", category="test",
            description="Missing endpoint", expected_status=200,
            actual_status=404, passed=False, error="Not Found",
        ),
        EndpointProbeResult(
            method="GET", path="/api/broken", category="test",
            description="Broken endpoint", expected_status=200,
            actual_status=500, passed=False, error="Internal Server Error",
        ),
    ]


@pytest.fixture
def sample_ui_results():
    """Sample UI page probe results — mix of pass/fail."""
    return [
        UIPageProbeResult(
            path="/", name="Landing Page", category="landing",
            has_title=True, title="Murphy — Landing", has_body_content=True,
            passed=True, load_time_ms=10.0,
        ),
        UIPageProbeResult(
            path="/dashboard", name="Dashboard", category="dashboard",
            has_title=False, title="", has_body_content=False,
            passed=False, error="Page failed to render",
        ),
    ]


# ==============================================================================
# 1. Authentication Tests
# ==============================================================================

class TestAgentAuthenticator:
    """G1: Agent authenticates using service-account credentials."""

    def test_login_stub_mode_succeeds(self, authenticator):
        """G5: Stub mode login always succeeds."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            result = authenticator.login()
        assert result is True
        assert authenticator.authenticated is True
        assert authenticator.session_token is not None

    def test_stub_token_is_deterministic(self, authenticator):
        """G5: Same day produces same stub token."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            authenticator.login()
            token1 = authenticator.session_token
        auth2 = AgentAuthenticator()
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            auth2.login()
            token2 = auth2.session_token
        assert token1 == token2

    def test_get_auth_headers_with_session_token(self, authenticator):
        """G5: Auth headers include Bearer token after login."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            authenticator.login()
        headers = authenticator.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "X-Agent-ID" in headers
        assert headers["X-Agent-ID"] == AGENT_ID

    def test_get_auth_headers_fallback_api_key(self):
        """G5: Auth headers use X-API-Key when no session token."""
        auth = AgentAuthenticator()
        auth.api_key = "test-key-123"
        auth.authenticated = True
        headers = auth.get_auth_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-key-123"

    def test_agent_id_constant(self):
        """G2: Agent ID matches spec."""
        assert AGENT_ID == "ui_autopilot_tester"

    def test_agent_label_constant(self):
        """G2: Agent label matches spec."""
        assert AGENT_LABEL == "UI-AUTOPILOT-001"


# ==============================================================================
# 2. Endpoint Probing Tests
# ==============================================================================

class TestEndpointProber:
    """G1: Endpoint prober correctly tests API surfaces."""

    def test_probe_all_returns_results_for_every_endpoint(self):
        """G4: Every known endpoint is probed."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            prober = EndpointProber("http://localhost:8000", {})
            results = prober.probe_all()
        assert len(results) == len(KNOWN_API_ENDPOINTS)

    def test_stub_probe_marks_all_passed(self):
        """G5: Stub mode marks all probes as passed."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            prober = EndpointProber("http://localhost:8000", {})
            results = prober.probe_all()
        assert all(r.passed for r in results)

    def test_stub_probe_sets_actual_status(self):
        """G5: Stub mode sets actual_status to expected."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            prober = EndpointProber("http://localhost:8000", {})
            result = prober.probe_one("GET", "/api/health", 200, "health", "test")
        assert result.actual_status == 200

    def test_probe_result_has_timestamp(self):
        """G5: Each probe result has a timestamp."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            prober = EndpointProber("http://localhost:8000", {})
            result = prober.probe_one("GET", "/api/health", 200, "health", "test")
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format

    def test_known_endpoints_have_required_fields(self):
        """G3: Every known endpoint tuple has 5 fields."""
        for entry in KNOWN_API_ENDPOINTS:
            assert len(entry) == 5
            method, path, status, category, desc = entry
            assert method in ("GET", "POST", "PUT", "DELETE", "PATCH")
            assert path.startswith("/")
            assert isinstance(status, int)
            assert len(category) > 0
            assert len(desc) > 0


# ==============================================================================
# 3. MultiCursor UI Scanner Tests
# ==============================================================================

class TestMultiCursorUIScanner:
    """G1: MCB-based UI scanner probes all pages."""

    def test_scan_pages_returns_results(self):
        """G4: All known UI pages are scanned."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            scanner = MultiCursorUIScanner()
            results = scanner.scan_pages()
            scanner.release()
        assert len(results) == len(KNOWN_UI_PAGES)

    def test_stub_scan_marks_all_passed(self):
        """G5: Stub mode marks all pages as passed."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            scanner = MultiCursorUIScanner()
            results = scanner.scan_pages()
            scanner.release()
        assert all(r.passed for r in results)

    def test_stub_scan_has_titles(self):
        """G5: Stub pages have titles."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            scanner = MultiCursorUIScanner()
            results = scanner.scan_pages()
            scanner.release()
        for r in results:
            assert r.has_title is True
            assert "Murphy" in r.title

    def test_scanner_release_is_idempotent(self):
        """G8: Releasing scanner twice does not raise."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            scanner = MultiCursorUIScanner()
            scanner.release()
            scanner.release()  # Should not raise

    def test_known_ui_pages_have_required_fields(self):
        """G3: Every known UI page tuple has 3 fields."""
        for entry in KNOWN_UI_PAGES:
            assert len(entry) == 3
            path, name, category = entry
            assert path.startswith("/")
            assert len(name) > 0
            assert len(category) > 0


# ==============================================================================
# 4. Feedback Generator Tests
# ==============================================================================

class TestFeedbackGenerator:
    """G1: Feedback generator produces correct structured reports."""

    def test_generate_all_passed(self):
        """G5: All-pass scenario yields overall_passed=True."""
        api = [
            EndpointProbeResult(
                method="GET", path="/api/health", category="health",
                description="Health", expected_status=200,
                actual_status=200, passed=True,
            ),
        ]
        ui = [
            UIPageProbeResult(
                path="/", name="Landing", category="landing",
                passed=True, has_title=True,
            ),
        ]
        report = FeedbackGenerator.generate(api, ui, authenticated=True)
        assert report.overall_passed is True
        assert report.summary["api_passed"] == 1
        assert report.summary["ui_passed"] == 1
        assert report.summary["overall_pass_rate"] == 100.0

    def test_generate_with_failures(self, sample_api_results, sample_ui_results):
        """G5: Failures are counted and fixable issues populated."""
        report = FeedbackGenerator.generate(
            sample_api_results, sample_ui_results, authenticated=True
        )
        assert report.overall_passed is False
        assert report.summary["api_failed"] == 2
        assert report.summary["ui_failed"] == 1
        assert len(report.fixable_issues) == 3

    def test_generate_empty_inputs(self):
        """G3: Empty input produces valid report with zero counts."""
        report = FeedbackGenerator.generate([], [], authenticated=False)
        assert report.overall_passed is True
        assert report.summary["api_total"] == 0
        assert report.summary["ui_total"] == 0

    def test_to_markdown_contains_header(self, sample_api_results, sample_ui_results):
        """G5: Markdown output contains expected header."""
        report = FeedbackGenerator.generate(
            sample_api_results, sample_ui_results, authenticated=True
        )
        md = FeedbackGenerator.to_markdown(report)
        assert "# UI Autopilot Tester" in md
        assert "Summary" in md
        assert "API Endpoints Passed" in md

    def test_to_markdown_shows_failures(self, sample_api_results, sample_ui_results):
        """G5: Markdown lists failed endpoints."""
        report = FeedbackGenerator.generate(
            sample_api_results, sample_ui_results, authenticated=True
        )
        md = FeedbackGenerator.to_markdown(report)
        assert "/api/missing" in md
        assert "/api/broken" in md
        assert "Dashboard" in md

    def test_to_markdown_all_passed(self):
        """G5: All-pass markdown shows success badge."""
        report = FeedbackGenerator.generate([], [], authenticated=True)
        md = FeedbackGenerator.to_markdown(report)
        assert "All checks passed" in md

    def test_report_has_timestamp(self):
        """G5: Report includes ISO timestamp."""
        report = FeedbackGenerator.generate([], [], authenticated=True)
        assert "T" in report.timestamp


# ==============================================================================
# 5. Fix Strategy Inference Tests
# ==============================================================================

class TestFixStrategyInference:
    """G1: Fix strategies are correctly inferred from probe failures."""

    def test_404_suggests_add_route(self):
        """G5: 404 → add_missing_route."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=404,
        )
        assert _infer_fix_strategy(r) == "add_missing_route"

    def test_405_suggests_fix_method(self):
        """G5: 405 → fix_http_method."""
        r = EndpointProbeResult(
            method="POST", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=405,
        )
        assert _infer_fix_strategy(r) == "fix_http_method"

    def test_500_suggests_fix_server_error(self):
        """G5: 500 → fix_server_error."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=500,
        )
        assert _infer_fix_strategy(r) == "fix_server_error"

    def test_401_suggests_fix_auth(self):
        """G5: 401 → fix_auth_config."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=401,
        )
        assert _infer_fix_strategy(r) == "fix_auth_config"

    def test_403_suggests_fix_auth(self):
        """G5: 403 → fix_auth_config."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=403,
        )
        assert _infer_fix_strategy(r) == "fix_auth_config"

    def test_0_suggests_connection_error(self):
        """G5: 0 (no response) → fix_connection_error."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=0,
        )
        assert _infer_fix_strategy(r) == "fix_connection_error"

    def test_unknown_status_suggests_investigate(self):
        """G5: Unknown status → investigate_status_mismatch."""
        r = EndpointProbeResult(
            method="GET", path="/api/test", category="test",
            description="test", expected_status=200, actual_status=302,
        )
        assert _infer_fix_strategy(r) == "investigate_status_mismatch"


# ==============================================================================
# 6. Phase Execution Tests
# ==============================================================================

class TestPhaseExecution:
    """G1: Phase runners execute correctly in test/stub mode."""

    def test_phase_login(self):
        """G5: Login phase returns authenticated agent."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            auth = phase_login()
        assert auth.authenticated is True

    def test_phase_scan(self, tmp_output):
        """G5: Scan phase returns API and UI results."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            auth = phase_login()
            api_results, ui_results = phase_scan(auth, tmp_output)
        assert len(api_results) == len(KNOWN_API_ENDPOINTS)
        assert len(ui_results) == len(KNOWN_UI_PAGES)

    def test_phase_feedback_writes_files(self, tmp_output):
        """G5: Feedback phase writes JSON and Markdown reports."""
        api = [
            EndpointProbeResult(
                method="GET", path="/api/health", category="health",
                description="test", expected_status=200,
                actual_status=200, passed=True,
            ),
        ]
        ui = [
            UIPageProbeResult(
                path="/", name="Landing", category="landing", passed=True,
            ),
        ]
        report = phase_feedback(api, ui, True, tmp_output)
        assert (tmp_output / "ui_autopilot_report.json").exists()
        assert (tmp_output / "ui_autopilot_report.md").exists()
        assert report.overall_passed is True

    def test_phase_fix_writes_summary(self, tmp_output):
        """G5: Fix phase writes fix summary JSON."""
        report = FeedbackReport(
            fixable_issues=[
                {"type": "api_endpoint", "path": "/api/test",
                 "method": "GET", "fix_strategy": "add_missing_route"},
            ],
        )
        fix_summary = phase_fix(report, tmp_output)
        assert (tmp_output / "ui_autopilot_fix_summary.json").exists()
        assert fix_summary["total_issues"] == 1

    def test_run_all_phases(self, tmp_output):
        """G5: Full pipeline runs end-to-end in stub mode."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            report = run_all_phases(tmp_output)
        assert report.overall_passed is True
        assert (tmp_output / "ui_autopilot_report.json").exists()
        assert (tmp_output / "ui_autopilot_report.md").exists()
        assert (tmp_output / "ui_autopilot_fix_summary.json").exists()
        assert (tmp_output / "ui_autopilot_overall.json").exists()

    def test_run_all_phases_overall_json_structure(self, tmp_output):
        """G5: Overall JSON has expected structure."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            run_all_phases(tmp_output)
        data = json.loads((tmp_output / "ui_autopilot_overall.json").read_text())
        assert data["agent"] == AGENT_LABEL
        assert data["version"] == AGENT_VERSION
        assert "summary" in data
        assert "fix_summary" in data


# ==============================================================================
# 7. Data Model Tests
# ==============================================================================

class TestDataModels:
    """G3: Data models serialize correctly."""

    def test_endpoint_probe_result_defaults(self):
        """G5: Default values are sensible."""
        r = EndpointProbeResult(
            method="GET", path="/test", category="test",
            description="test", expected_status=200,
        )
        assert r.actual_status is None
        assert r.passed is False
        assert r.error is None
        assert r.response_time_ms == 0.0

    def test_ui_page_probe_result_defaults(self):
        """G5: Default values are sensible."""
        r = UIPageProbeResult(path="/", name="Home", category="home")
        assert r.has_title is False
        assert r.passed is False
        assert r.load_time_ms == 0.0

    def test_feedback_report_defaults(self):
        """G5: Report defaults are valid."""
        r = FeedbackReport()
        assert r.agent == AGENT_LABEL
        assert r.version == AGENT_VERSION
        assert r.overall_passed is False
        assert r.api_results == []
        assert r.ui_results == []

    def test_feedback_report_serializable(self):
        """G5: Report can be serialized to JSON."""
        from dataclasses import asdict
        r = FeedbackReport()
        data = json.dumps(asdict(r), default=str)
        assert isinstance(data, str)
        parsed = json.loads(data)
        assert parsed["agent"] == AGENT_LABEL


# ==============================================================================
# 8. Edge Case Tests
# ==============================================================================

class TestEdgeCases:
    """G8: Edge cases and error handling."""

    def test_feedback_generator_single_failure(self):
        """G3: Single failed endpoint produces one fixable issue."""
        api = [
            EndpointProbeResult(
                method="GET", path="/api/test", category="test",
                description="test", expected_status=200,
                actual_status=404, passed=False, error="Not Found",
            ),
        ]
        report = FeedbackGenerator.generate(api, [], authenticated=True)
        assert len(report.fixable_issues) == 1
        assert report.fixable_issues[0]["fix_strategy"] == "add_missing_route"

    def test_feedback_generator_all_failures(self):
        """G3: All failures produces correct count."""
        api = [
            EndpointProbeResult(
                method="GET", path=f"/api/test{i}", category="test",
                description="test", expected_status=200,
                actual_status=500, passed=False,
            )
            for i in range(5)
        ]
        report = FeedbackGenerator.generate(api, [], authenticated=True)
        assert report.summary["api_failed"] == 5
        assert report.summary["overall_pass_rate"] == 0.0

    def test_fix_phase_empty_issues(self, tmp_output):
        """G3: Fix phase with no issues produces empty summary."""
        report = FeedbackReport(fixable_issues=[])
        fix_summary = phase_fix(report, tmp_output)
        assert fix_summary["total_issues"] == 0
        assert fix_summary["auto_fixed"] == 0

    def test_markdown_escaping(self):
        """G8: Markdown handles special characters in paths."""
        api = [
            EndpointProbeResult(
                method="GET", path="/api/test?q=<script>", category="test",
                description="XSS test", expected_status=200,
                actual_status=404, passed=False, error="Not Found",
            ),
        ]
        report = FeedbackGenerator.generate(api, [], authenticated=True)
        md = FeedbackGenerator.to_markdown(report)
        assert isinstance(md, str)
        # Should not crash on special chars
        assert "/api/test" in md
