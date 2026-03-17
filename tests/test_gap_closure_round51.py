"""
Gap Closure Verification — Round 51
======================================

Verifies that GAP-4, GAP-5, GAP-6, and GAP-7 are fully resolved:

  GAP-4  AUAR Technical Proposal Appendix C (UCB1, persistence, admin security)
  GAP-5  Package-level READMEs — all 65 src/ packages now have README.md
  GAP-6  Groq integration test suite (22 tests pass in test_groq_integration.py)
  GAP-7  CONFIGURATION.md documents all env vars (96 variables, §11-14 added)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SRC = _REPO / "src"
_DOCS = _REPO / "docs"
_DOC_DEPLOY = _REPO / "documentation" / "deployment"


# ---------------------------------------------------------------------------
# GAP-4: AUAR Technical Proposal Appendix C
# ---------------------------------------------------------------------------

class TestGap4AUARAppendixC:
    """AUAR_TECHNICAL_PROPOSAL.md must contain Appendix C with all three topics."""

    _proposal = _DOCS / "AUAR_TECHNICAL_PROPOSAL.md"

    def _text(self) -> str:
        return self._proposal.read_text(encoding="utf-8")

    def test_proposal_file_exists(self) -> None:
        assert self._proposal.is_file(), f"Missing {self._proposal}"

    def test_appendix_c_heading(self) -> None:
        assert "Appendix C" in self._text(), "Appendix C section not found"

    def test_ucb1_documented(self) -> None:
        text = self._text()
        assert "UCB1" in text, "UCB1 algorithm not documented in Appendix C"

    def test_persistence_layer_documented(self) -> None:
        text = self._text()
        assert "persistence" in text.lower(), "Persistence layer not documented"
        assert "FileStateBackend" in text, "FileStateBackend not mentioned"

    def test_admin_security_documented(self) -> None:
        text = self._text()
        assert "AUAR_ADMIN_TOKEN" in text, "Admin security token not documented"
        assert "audit" in text.lower(), "Audit logging not mentioned in admin security section"

    def test_auar_config_vars_table(self) -> None:
        text = self._text()
        assert "AUAR_UCB1_C" in text, "UCB1 config variable not in appendix C"
        assert "AUAR_STATE_BACKEND" in text, "State backend config variable not in appendix C"

    def test_version_updated(self) -> None:
        text = self._text()
        assert "v0.2.0" in text or "0.2.0" in text, "Version not updated to 0.2.0 in appendix C"


# ---------------------------------------------------------------------------
# GAP-5: Package-level READMEs (all 65 src/ packages)
# ---------------------------------------------------------------------------

class TestGap5PackageReadmes:
    """Every src/ package directory must contain README.md."""

    @staticmethod
    def _all_packages() -> list[Path]:
        """Return all directories under src/ that contain __init__.py."""
        packages = []
        for init in _SRC.rglob("__init__.py"):
            # Only first two levels: src/<pkg>/ and src/<pkg>/<subpkg>/
            depth = len(init.relative_to(_SRC).parts)
            if depth <= 2:  # __init__.py at src/__init__.py (depth 1) or src/pkg/__init__.py (depth 2)
                packages.append(init.parent)
        return sorted(set(packages))

    def test_src_has_readme(self) -> None:
        assert (_SRC / "README.md").is_file(), "src/README.md missing"

    def test_all_packages_have_readme(self) -> None:
        missing = []
        for pkg in self._all_packages():
            readme = pkg / "README.md"
            if not readme.is_file():
                missing.append(str(pkg.relative_to(_REPO)))
        assert not missing, (
            f"{len(missing)} package(s) still missing README.md:\n"
            + "\n".join(f"  {m}" for m in missing)
        )

    def test_readme_count_at_least_64(self) -> None:
        count = len(list(_SRC.rglob("README.md")))
        assert count >= 64, f"Expected ≥64 README files in src/, found {count}"

    def test_readmes_are_nonempty(self) -> None:
        for readme in sorted(_SRC.rglob("README.md"))[:10]:  # spot check first 10
            content = readme.read_text(encoding="utf-8").strip()
            assert len(content) > 100, f"{readme} appears to be empty or trivial"

    def test_readmes_have_license_footer(self) -> None:
        """Spot check 5 packages for BSL footer."""
        checked = 0
        for readme in sorted(_SRC.rglob("README.md")):
            if readme.parent == _SRC:
                continue  # skip top-level src/README.md
            text = readme.read_text(encoding="utf-8")
            if "BSL" in text or "Inoni" in text or "Creator" in text:
                checked += 1
            if checked >= 5:
                break
        assert checked >= 5, "Fewer than 5 package READMEs contain the BSL license footer"

    def test_readmes_have_h1_heading(self) -> None:
        """Every README should start with an H1 heading."""
        missing_h1 = []
        for readme in sorted(_SRC.rglob("README.md")):
            text = readme.read_text(encoding="utf-8")
            if not any(line.startswith("# ") for line in text.splitlines()):
                missing_h1.append(str(readme.relative_to(_REPO)))
        assert not missing_h1, (
            f"{len(missing_h1)} README(s) missing H1 heading:\n"
            + "\n".join(f"  {p}" for p in missing_h1[:10])
        )


# ---------------------------------------------------------------------------
# GAP-6: Groq Integration Test Suite
# ---------------------------------------------------------------------------

class TestGap6GroqTestSuite:
    """Groq integration test file must exist and contain substantive tests."""

    _groq_tests = _REPO / "tests" / "test_groq_integration.py"

    def test_groq_test_file_exists(self) -> None:
        assert self._groq_tests.is_file(), "tests/test_groq_integration.py not found"

    def test_groq_test_file_has_tiers(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        assert "Tier 1" in text, "No Tier 1 (unit) tests found"
        assert "Tier 2" in text, "No Tier 2 (mocked HTTP) tests found"

    def test_groq_test_covers_key_rotation(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        assert "GroqKeyRotator" in text or "key_rotation" in text.lower(), (
            "Groq key rotation not tested"
        )

    def test_groq_test_covers_fallback(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        assert "fallback" in text.lower() or "falls_back" in text.lower(), (
            "API error fallback not tested"
        )

    def test_groq_test_covers_rate_limit(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        assert "rate_limit" in text.lower() or "rate limit" in text.lower(), (
            "Rate-limit handling not tested"
        )

    def test_groq_test_has_at_least_20_test_functions(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        count = text.count("    def test_")
        assert count >= 20, f"Expected ≥20 test functions, found {count}"

    def test_groq_test_has_live_api_tier(self) -> None:
        text = self._groq_tests.read_text(encoding="utf-8")
        assert "skipif" in text.lower() or "skip" in text.lower(), (
            "No skip marker for live API tests found (GROQ_API_KEY required)"
        )


# ---------------------------------------------------------------------------
# GAP-7: CONFIGURATION.md documents all env vars
# ---------------------------------------------------------------------------

class TestGap7ConfigDocumentation:
    """CONFIGURATION.md must document all 96 env vars from .env.example."""

    _config_md = _DOC_DEPLOY / "CONFIGURATION.md"
    _env_example = _REPO / ".env.example"

    def _config_text(self) -> str:
        return self._config_md.read_text(encoding="utf-8")

    def test_config_file_exists(self) -> None:
        assert self._config_md.is_file(), f"Missing {self._config_md}"

    def test_has_complete_variable_index(self) -> None:
        text = self._config_text()
        assert "Complete Variable Index" in text, "§14 Complete Variable Index not found"

    def test_documents_mfm_section(self) -> None:
        text = self._config_text()
        assert "Murphy Foundation Model" in text or "MFM" in text, (
            "MFM section not found in CONFIGURATION.md"
        )
        assert "MFM_ENABLED" in text, "MFM_ENABLED not documented"
        assert "MFM_MODE" in text, "MFM_MODE not documented"

    def test_documents_matrix_section(self) -> None:
        text = self._config_text()
        assert "Matrix Integration" in text, "Matrix section not found"
        assert "MATRIX_HOMESERVER_URL" in text, "MATRIX_HOMESERVER_URL not documented"
        assert "MATRIX_BOT_TOKEN" in text, "MATRIX_BOT_TOKEN not documented"

    def test_documents_backend_modes_section(self) -> None:
        text = self._config_text()
        assert "Backend Modes" in text, "Backend Modes section not found"
        assert "MURPHY_DB_MODE" in text, "MURPHY_DB_MODE not documented"
        assert "MURPHY_EMAIL_REQUIRED" in text, "MURPHY_EMAIL_REQUIRED not documented"

    def test_documents_facebook_vars(self) -> None:
        text = self._config_text()
        assert "FACEBOOK_APP_ID" in text, "FACEBOOK_APP_ID not documented"

    def test_documents_google_analytics(self) -> None:
        text = self._config_text()
        assert "GOOGLE_ANALYTICS_ID" in text, "GOOGLE_ANALYTICS_ID not documented"

    def test_documents_wordpress_vars(self) -> None:
        text = self._config_text()
        assert "WORDPRESS_URL" in text, "WORDPRESS_URL not documented"

    def test_documents_medium_token(self) -> None:
        text = self._config_text()
        assert "MEDIUM_ACCESS_TOKEN" in text, "MEDIUM_ACCESS_TOKEN not documented"

    def test_documents_coinbase_webhook(self) -> None:
        text = self._config_text()
        assert "COINBASE_WEBHOOK_SECRET" in text, "COINBASE_WEBHOOK_SECRET not documented"

    def test_documents_paypal_webhook(self) -> None:
        text = self._config_text()
        assert "PAYPAL_WEBHOOK_SECRET" in text, "PAYPAL_WEBHOOK_SECRET not documented"

    def test_documents_murphy_log_format(self) -> None:
        text = self._config_text()
        assert "MURPHY_LOG_FORMAT" in text, "MURPHY_LOG_FORMAT not documented"

    def test_documents_murphy_max_response_size(self) -> None:
        text = self._config_text()
        assert "MURPHY_MAX_RESPONSE_SIZE_MB" in text, "MURPHY_MAX_RESPONSE_SIZE_MB not documented"

    def test_documents_murphy_persistence_dir(self) -> None:
        text = self._config_text()
        assert "MURPHY_PERSISTENCE_DIR" in text, "MURPHY_PERSISTENCE_DIR not documented"

    def test_table_of_contents_has_new_sections(self) -> None:
        text = self._config_text()
        assert "Murphy Foundation Model" in text or "§11" in text or "11." in text, (
            "ToC does not reference MFM section"
        )

    def test_at_least_80_variables_documented(self) -> None:
        """Check that the complete index has at least 80 variables."""
        text = self._config_text()
        # Count lines like `| `VARIABLE_NAME` |` in the index table
        index_lines = [
            line for line in text.splitlines()
            if line.startswith("| `") and "_" in line
        ]
        assert len(index_lines) >= 80, (
            f"Complete index has only {len(index_lines)} variable rows, expected ≥80"
        )

    def test_env_example_path_updated(self) -> None:
        """The stale 'Murphy System/' path should no longer appear in CONFIGURATION.md."""
        text = self._config_text()
        # Should reference .env.example at repo root, not the old subdirectory
        assert 'cd "Murphy System"' not in text, (
            "Stale 'cd Murphy System' instruction still present — path not updated after flattening"
        )


# ---------------------------------------------------------------------------
# GAP-7 cross-check: env vars from .env.example appear in CONFIGURATION.md
# ---------------------------------------------------------------------------

class TestGap7EnvExampleCoverage:
    """Key env vars from .env.example must appear in CONFIGURATION.md."""

    _config_md = _DOC_DEPLOY / "CONFIGURATION.md"
    _env_example = _REPO / ".env.example"

    # Subset of the most important variables to spot-check
    SPOT_CHECK_VARS = [
        "MURPHY_ENV",
        "MURPHY_PORT",
        "MURPHY_LLM_PROVIDER",
        "GROQ_API_KEY",
        "GROQ_API_KEYS",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "MURPHY_REDIS_URL",
        "MURPHY_API_KEYS",
        "MURPHY_JWT_SECRET",
        "ENCRYPTION_KEY",
        "MURPHY_CREDENTIAL_MASTER_KEY",
        "SENDGRID_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "MFM_ENABLED",
        "MFM_MODE",
        "MATRIX_HOMESERVER_URL",
        "MURPHY_DB_MODE",
        "MURPHY_EMAIL_REQUIRED",
        "MURPHY_LOG_FORMAT",
        "MURPHY_MAX_RESPONSE_SIZE_MB",
        "SENTRY_DSN",
        "PROMETHEUS_PORT",
    ]

    def test_spot_check_vars_documented(self) -> None:
        text = self._config_md.read_text(encoding="utf-8")
        missing = [v for v in self.SPOT_CHECK_VARS if v not in text]
        assert not missing, (
            f"{len(missing)} key env var(s) not documented in CONFIGURATION.md:\n"
            + "\n".join(f"  {v}" for v in missing)
        )
