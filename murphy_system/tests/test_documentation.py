"""
Tests for Stream 5: Documentation, README, and Assessment Sync.

Validates that:
1. README.md exists, is non-empty, and contains all required sections.
2. CHANGELOG.md exists and follows Keep a Changelog format.
3. full_system_assessment.md exists and is non-empty.
4. AUTHENTICATION.md documents auth as *implemented* (not absent).
5. Key API endpoints documented in ENDPOINTS.md are present in the codebase.
6. Environment variables documented in README.md are actually read by the code.

Design Label: DOCS-001 / Stream-5
Owner: QA Team
"""

import os
import re
import sys
import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MURPHY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(MURPHY_ROOT, "src")

README_PATH = os.path.join(REPO_ROOT, "README.md")
CHANGELOG_PATH = os.path.join(REPO_ROOT, "CHANGELOG.md")
ASSESSMENT_PATH = os.path.join(MURPHY_ROOT, "docs", "archive", "internal", "full_system_assessment.md")
AUTH_DOC_PATH = os.path.join(MURPHY_ROOT, "documentation", "api", "AUTHENTICATION.md")
ENDPOINTS_DOC_PATH = os.path.join(MURPHY_ROOT, "documentation", "api", "ENDPOINTS.md")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ===========================================================================
# Task 1 — README.md
# ===========================================================================


class TestReadme:
    """README.md must exist, be non-empty, and contain required sections."""

    def test_readme_exists(self):
        assert os.path.isfile(README_PATH), f"README.md not found at {README_PATH}"

    def test_readme_non_empty(self):
        content = _read(README_PATH)
        assert len(content) > 500, "README.md is unexpectedly short (< 500 chars)"

    @pytest.mark.parametrize(
        "section",
        [
            "Quick Start",
            "Features",
            "Architecture",
            "API Endpoints",
            "Configuration",
            "Testing",
            "Contributing",
            "License",
            "Security",
        ],
    )
    def test_readme_contains_section(self, section: str):
        content = _read(README_PATH)
        # Accept section keyword anywhere in a heading line (case-insensitive).
        # Double-braces {{}} escape the curly braces in the f-string so that
        # the resulting regex string contains the literal quantifier "{1,3}".
        pattern = rf"^#{{1,3}}\s.*{re.escape(section)}"
        assert re.search(pattern, content, re.MULTILINE | re.IGNORECASE), (
            f"README.md is missing a section matching '{section}'"
        )

    @pytest.mark.parametrize(
        "module_name",
        [
            "Self-Introspection",
            "Self-Codebase Swarm",
            "Cut Sheet Engine",
            "Visual Swarm Builder",
            "CEO Branch Activation",
            "Production Assistant Engine",
        ],
    )
    def test_readme_subsystem_lookup_contains_new_modules(self, module_name: str):
        """Subsystem Lookup table must contain entries for all 6 new modules."""
        content = _read(README_PATH)
        assert module_name in content, (
            f"README.md Subsystem Lookup table is missing entry for '{module_name}'"
        )

    def test_readme_api_endpoints_table(self):
        """The API Endpoints section must contain at least one Markdown table row."""
        content = _read(README_PATH)
        # Locate the API Endpoints section
        idx = content.lower().find("api endpoints")
        assert idx != -1, "README.md has no 'API Endpoints' text"
        # After that point there should be a table row (pipe-separated)
        after = content[idx:]
        assert re.search(r"\|.*\|.*\|", after), (
            "README.md API Endpoints section has no Markdown table"
        )

    def test_readme_configuration_env_vars(self):
        """Configuration section must document required environment variables."""
        content = _read(README_PATH)
        required_vars = [
            "GROQ_API_KEY",
            "MURPHY_ENV",
            "MURPHY_API_KEYS",
            "MURPHY_CORS_ORIGINS",
        ]
        for var in required_vars:
            assert var in content, (
                f"README.md Configuration section does not mention env var '{var}'"
            )

    def test_readme_project_structure(self):
        """README must reference the Murphy System directory structure."""
        content = _read(README_PATH)
        assert "murphy_system" in content, (
            "README.md does not reference 'Murphy System' directory"
        )
        assert "src/" in content, "README.md does not reference the src/ directory"


# ===========================================================================
# Task 5 — CHANGELOG.md
# ===========================================================================


class TestChangelog:
    """CHANGELOG.md must exist and follow Keep a Changelog format."""

    def test_changelog_exists(self):
        assert os.path.isfile(CHANGELOG_PATH), (
            f"CHANGELOG.md not found at {CHANGELOG_PATH}"
        )

    def test_changelog_non_empty(self):
        content = _read(CHANGELOG_PATH)
        assert len(content) > 200, "CHANGELOG.md is unexpectedly short"

    def test_changelog_keep_a_changelog_header(self):
        """Must reference Keep a Changelog spec."""
        content = _read(CHANGELOG_PATH)
        assert "Keep a Changelog" in content or "keepachangelog" in content.lower(), (
            "CHANGELOG.md does not reference Keep a Changelog format"
        )

    def test_changelog_has_unreleased_or_version_section(self):
        content = _read(CHANGELOG_PATH)
        assert re.search(r"^##\s+\[", content, re.MULTILINE), (
            "CHANGELOG.md has no version/unreleased sections (expected '## [...]' headings)"
        )

    def test_changelog_has_added_section(self):
        content = _read(CHANGELOG_PATH)
        assert re.search(r"^###\s+Added", content, re.MULTILINE), (
            "CHANGELOG.md does not have any '### Added' subsection"
        )

    def test_changelog_references_streams(self):
        """CHANGELOG must reference Stream work (Streams 1-5)."""
        content = _read(CHANGELOG_PATH)
        assert "Stream" in content, (
            "CHANGELOG.md does not reference Stream entries from the current work"
        )


# ===========================================================================
# Task 2 — full_system_assessment.md
# ===========================================================================


class TestFullSystemAssessment:
    """full_system_assessment.md must exist and contain key assessment sections."""

    def test_assessment_exists(self):
        assert os.path.isfile(ASSESSMENT_PATH), (
            f"full_system_assessment.md not found at {ASSESSMENT_PATH}"
        )

    def test_assessment_non_empty(self):
        content = _read(ASSESSMENT_PATH)
        assert len(content) > 500, "full_system_assessment.md is unexpectedly short"

    def test_assessment_has_maturity_score(self):
        content = _read(ASSESSMENT_PATH)
        assert re.search(r"\d+\s*/\s*100", content), (
            "full_system_assessment.md does not contain a maturity score (N/100)"
        )

    def test_assessment_has_module_inventory(self):
        content = _read(ASSESSMENT_PATH)
        assert re.search(
            r"module\s+inventory|module inventory", content, re.IGNORECASE
        ), "full_system_assessment.md has no 'Module Inventory' section"

    def test_assessment_has_test_counts(self):
        content = _read(ASSESSMENT_PATH)
        # Must mention a test count figure
        assert re.search(r"\d{3,}", content), (
            "full_system_assessment.md mentions no test counts"
        )


# ===========================================================================
# Task 3 — AUTHENTICATION.md documents auth as implemented
# ===========================================================================


class TestAuthenticationDoc:
    """AUTHENTICATION.md must reflect that auth IS implemented."""

    def test_auth_doc_exists(self):
        assert os.path.isfile(AUTH_DOC_PATH), (
            f"AUTHENTICATION.md not found at {AUTH_DOC_PATH}"
        )

    def test_auth_doc_describes_implementation(self):
        content = _read(AUTH_DOC_PATH)
        positive_phrases = [
            "implemented",
            "enforced",
            "Security Hardening Applied",
            "API key",
        ]
        assert any(p.lower() in content.lower() for p in positive_phrases), (
            "AUTHENTICATION.md does not describe auth as implemented"
        )

    def test_auth_doc_no_absence_claim(self):
        """Doc must not claim auth is absent or not implemented."""
        content = _read(AUTH_DOC_PATH)
        absence_phrases = [
            "auth is not implemented",
            "no authentication",
            "authentication is absent",
            "auth absent",
        ]
        for phrase in absence_phrases:
            assert phrase.lower() not in content.lower(), (
                f"AUTHENTICATION.md contains stale 'absence of auth' text: '{phrase}'"
            )

    def test_auth_doc_mentions_api_key_header(self):
        """Doc must explain how to pass credentials."""
        content = _read(AUTH_DOC_PATH)
        assert "Authorization" in content or "X-API-Key" in content, (
            "AUTHENTICATION.md does not mention Authorization or X-API-Key header"
        )


# ===========================================================================
# Verify env vars documented in README are read by source code
# ===========================================================================


class TestEnvVarsInCode:
    """Environment variables mentioned in the README must be read by source code."""

    def _codebase_text(self) -> str:
        """Concatenate relevant source files for searching."""
        pieces = []
        for root_dir, _dirs, files in os.walk(SRC_ROOT):
            for fname in files:
                if fname.endswith(".py"):
                    try:
                        pieces.append(_read(os.path.join(root_dir, fname)))
                    except (OSError, UnicodeDecodeError):
                        pass
        return "\n".join(pieces)

    @pytest.fixture(scope="class")
    def code(self):
        return self._codebase_text()

    @pytest.mark.parametrize(
        "env_var",
        [
            "GROQ_API_KEY",
            "MURPHY_ENV",
            "MURPHY_API_KEYS",
            "MURPHY_CORS_ORIGINS",
        ],
    )
    def test_env_var_read_in_code(self, code, env_var: str):
        assert env_var in code, (
            f"Env var '{env_var}' is documented in README but not found in src/ code"
        )


# ===========================================================================
# Verify key API endpoint paths exist in codebase
# ===========================================================================


class TestEndpointsInCode:
    """Endpoints documented in ENDPOINTS.md must have a matching route in the codebase."""

    def _runtime_text(self) -> str:
        """Read the main runtime files which contain route definitions.

        After the INC-13 refactor, routes live in src/runtime/app.py rather
        than the thin wrapper murphy_system_1.0_runtime.py.
        """
        parts: list[str] = []
        for rel in (
            "murphy_system_1.0_runtime.py",
            os.path.join("src", "runtime", "app.py"),
        ):
            path = os.path.join(MURPHY_ROOT, rel)
            if os.path.isfile(path):
                try:
                    parts.append(_read(path))
                except (OSError, UnicodeDecodeError):
                    pass
        return "\n".join(parts)

    @pytest.fixture(scope="class")
    def runtime(self):
        return self._runtime_text()

    @pytest.mark.parametrize(
        "path",
        [
            "/api/health",
            "/api/status",
            "/api/execute",
            "/api/forms/task-execution",
            "/api/forms/plan-generation",
        ],
    )
    def test_endpoint_exists_in_runtime(self, runtime: str, path: str):
        assert path in runtime, (
            f"Endpoint '{path}' not found in murphy_system_1.0_runtime.py"
        )
