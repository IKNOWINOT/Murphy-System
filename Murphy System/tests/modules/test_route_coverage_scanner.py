"""Tests for Route Coverage Scanner module (PATCH-010)."""

import sys
import os
import pytest

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"),
)

from route_coverage_scanner import (
    RouteCoverageScanner,
    MODULE_PREFIX_MAP,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def scanner(tmp_path):
    """Return a scanner with a minimal spec file and no app."""
    spec = tmp_path / "API_ROUTES.md"
    spec.write_text(
        "| Method | Path | Auth | Description |\n"
        "|--------|------|------|-------------|\n"
        "| GET | /api/auth/login | No | Login page |\n"
        "| POST | /api/auth/signup | No | Create account |\n"
        "| GET | /api/hitl/pending | Yes | Pending items |\n"
        "| POST | ~~/api/old/removed~~ | Yes | Old route |\n"
        "| GET | /api/wingman/status | Yes | Wingman status |\n"
    )
    return RouteCoverageScanner(app=None, spec_path=str(spec))


# ------------------------------------------------------------------
# Spec parsing
# ------------------------------------------------------------------

class TestSpecParsing:
    def test_parse_spec_excludes_removed(self, scanner):
        routes = scanner._parse_spec()
        assert "POST /api/old/removed" not in routes

    def test_parse_spec_includes_active(self, scanner):
        routes = scanner._parse_spec()
        assert "GET /api/auth/login" in routes
        assert "POST /api/auth/signup" in routes
        assert "GET /api/hitl/pending" in routes
        assert "GET /api/wingman/status" in routes

    def test_parse_spec_count(self, scanner):
        routes = scanner._parse_spec()
        assert len(routes) == 4

    def test_parse_missing_file(self, tmp_path):
        scanner = RouteCoverageScanner(spec_path=str(tmp_path / "nonexistent.md"))
        routes = scanner._parse_spec()
        assert len(routes) == 0


# ------------------------------------------------------------------
# Coverage computation
# ------------------------------------------------------------------

class TestCoverageComputation:
    def test_scan_with_no_app(self, scanner):
        """With no app, nothing is implemented — coverage should be 0."""
        result = scanner.scan()
        assert result["overall"]["coverage_pct"] == 0
        assert result["overall"]["spec_routes"] == 4
        assert result["overall"]["implemented_routes"] == 0

    def test_scan_result_has_modules(self, scanner):
        result = scanner.scan()
        assert "modules" in result
        module_names = {m["name"] for m in result["modules"]}
        assert "auth" in module_names
        assert "hitl" in module_names
        assert "wingman" in module_names

    def test_scan_caches_result(self, scanner):
        assert scanner.get_last_scan() is None
        scanner.scan()
        assert scanner.get_last_scan() is not None

    def test_scanned_at_timestamp(self, scanner):
        result = scanner.scan()
        assert "scanned_at" in result
        assert "T" in result["scanned_at"]  # ISO format


# ------------------------------------------------------------------
# Module categorisation
# ------------------------------------------------------------------

class TestCategorisation:
    def test_auth_prefix(self):
        assert RouteCoverageScanner._categorise(
            "GET /api/auth/login", ["/api/auth/"]
        )

    def test_no_match(self):
        assert not RouteCoverageScanner._categorise(
            "GET /api/auth/login", ["/api/hitl/"]
        )


# ------------------------------------------------------------------
# Module prefix map
# ------------------------------------------------------------------

class TestModulePrefixMap:
    def test_all_dashboard_modules_present(self):
        expected = {
            "auth", "admin", "demo/forge", "hitl", "trading", "compliance",
            "automations", "agents", "llm", "mail", "boards", "crm",
            "workdocs", "onboarding", "dispatch", "gate-synthesis",
            "repair", "wingman",
        }
        assert expected == set(MODULE_PREFIX_MAP.keys())


# ------------------------------------------------------------------
# Integration with real API_ROUTES.md (if available)
# ------------------------------------------------------------------

class TestRealSpec:
    def test_real_spec_parses(self):
        """Verify the real API_ROUTES.md parses without error."""
        repo_root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        spec_path = os.path.join(repo_root, "API_ROUTES.md")
        if not os.path.exists(spec_path):
            pytest.skip("API_ROUTES.md not found")
        scanner = RouteCoverageScanner(spec_path=spec_path)
        routes = scanner._parse_spec()
        # We know there are 400+ routes in the spec
        assert len(routes) > 400
