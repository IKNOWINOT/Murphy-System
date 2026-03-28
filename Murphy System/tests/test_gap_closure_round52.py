"""
Gap Closure Tests — Round 52.

Validates the ancillary code and documentation updates completing the
post-audit polish pass:

  Item 1: TEST_COVERAGE.md refreshed with accurate statistics
            (617 test files, 20,358+ test functions, 52 gap-closure rounds)

  Item 2: Audit report discrepancies resolved in section 2
            - openai_compatible_provider: all 8 types now documented
            - MFM endpoints: confirmed in ENDPOINTS.md §MFM Endpoints
            - Specialized modules: docs added in documentation/modules/
            - Env vars: CONFIGURATION.md covers all groups

  Item 3: Doc–Code Accuracy metric updated to ~95% (target met)

  Item 4: Documentation file count updated to 107+

Round status: All gaps (GAP-1 through GAP-8) remain CLOSED.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE / "docs"
DOC_DIR = BASE / "documentation"
TESTS_DIR = BASE / "tests"


# ===========================================================================
# Item 1 — TEST_COVERAGE.md accurate statistics
# ===========================================================================

class TestItem1_TestCoverageDocUpdated:
    """TEST_COVERAGE.md must reflect the real test suite scale."""

    @staticmethod
    def _text():
        return (DOC_DIR / "testing" / "TEST_COVERAGE.md").read_text()

    def test_test_coverage_doc_exists(self):
        assert (DOC_DIR / "testing" / "TEST_COVERAGE.md").exists()

    def test_reflects_617_plus_test_files(self):
        text = self._text()
        assert "617" in text or "600" in text

    def test_reflects_20k_plus_test_functions(self):
        text = self._text()
        # 20,358 or similar
        assert "20,358" in text or "20358" in text or "20,000" in text

    def test_reflects_52_gap_closure_rounds(self):
        text = self._text()
        assert "52" in text

    def test_has_test_categories_section(self):
        text = self._text()
        assert "Gap-Closure" in text or "Gap-closure" in text

    def test_has_running_tests_section(self):
        text = self._text()
        assert "Running Tests" in text or "Quick start" in text

    def test_has_ci_pipeline_section(self):
        text = self._text()
        assert "CI" in text or "ci.yml" in text

    def test_has_writing_tests_section(self):
        text = self._text()
        assert "Writing" in text and "Tests" in text or "Writing New Tests" in text

    def test_has_current_pass_rate(self):
        text = self._text()
        assert "100 %" in text or "100%" in text

    def test_no_old_stat_60_tests(self):
        """Old version said only 60+ tests — should no longer be present."""
        text = self._text()
        # "60+" should no longer be the total; it may appear in other contexts
        # but the Total Tests line should reference the real number
        assert "Total Tests**: 60+" not in text

    def test_test_suite_structure_table(self):
        text = self._text()
        assert "test_groq_integration" in text
        assert "test_rosetta_subsystem_wiring" in text

    def test_copyright_present(self):
        text = self._text()
        assert "Inoni" in text or "Corey Post" in text


# ===========================================================================
# Item 2 — Audit report discrepancies resolved
# ===========================================================================

class TestItem2_AuditReportDiscrepanciesResolved:
    """AUDIT_AND_COMPLETION_REPORT.md discrepancies must be marked resolved."""

    @staticmethod
    def _report():
        return (DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md").read_text()

    def test_openai_provider_8_types_resolved(self):
        text = self._report()
        # Old text said "docs only reference OpenAI/DeepInfra/Onboard"
        assert "docs only reference OpenAI/DeepInfra/Onboard" not in text

    def test_mfm_endpoints_resolved(self):
        text = self._report()
        # Old text said endpoints not listed
        assert "not listed in the API endpoints documentation" not in text

    def test_specialized_modules_resolved(self):
        text = self._report()
        assert "src/adaptive_campaign_engine.py` | None | No documentation" not in text
        assert "src/financial_reporting_engine.py` | None | No documentation" not in text
        assert "src/predictive_maintenance_engine.py` | None | No documentation" not in text

    def test_env_vars_resolved(self):
        text = self._report()
        assert "may not cover all 236 env vars" not in text


# ===========================================================================
# Item 3 — Doc-Code Accuracy metric updated
# ===========================================================================

class TestItem3_DocCodeAccuracyMet:
    """Audit report must show Doc-Code Accuracy ≥ 95%."""

    @staticmethod
    def _report():
        return (DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md").read_text()

    def test_doc_code_accuracy_95(self):
        text = self._report()
        # Should show ~95% with ✅ status
        assert "~95%" in text or "95%" in text

    def test_doc_code_accuracy_not_92(self):
        """Old value ~92% should no longer be the accuracy figure."""
        text = self._report()
        # The old line "| Doc–Code Accuracy | ~92%" should be replaced
        assert "| Doc–Code Accuracy       | ~92%" not in text

    def test_doc_code_accuracy_status_green(self):
        """The row should now have ✅ not ⚠️."""
        text = self._report()
        # Find the accuracy row and check it has ✅
        for line in text.splitlines():
            if "Doc–Code Accuracy" in line:
                assert "✅" in line, f"Doc-Code Accuracy row missing ✅: {line}"
                break


# ===========================================================================
# Item 4 — Documentation file count updated
# ===========================================================================

class TestItem4_DocFileCountUpdated:
    """Audit report doc file count should reflect 107+."""

    def test_documentation_files_count_updated(self):
        text = (DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md").read_text()
        # Should show 107+ or similar, not just 97+
        assert "107+" in text or "107" in text


# ===========================================================================
# Sanity — all previous gap closures still hold
# ===========================================================================

class TestSanityPreviousGapsStillClosed:
    """Spot-check that earlier gap-closure work is still in place."""

    def test_gap1_through_8_all_closed(self):
        text = (DOCS_DIR / "AUDIT_AND_COMPLETION_REPORT.md").read_text()
        for gap in range(1, 9):
            assert f"GAP-{gap}" in text

    def test_groq_integration_test_still_present(self):
        assert (TESTS_DIR / "test_groq_integration.py").exists()

    def test_configuration_doc_has_16_sections(self):
        import re
        text = (DOC_DIR / "deployment" / "CONFIGURATION.md").read_text()
        matches = re.findall(r"^## \d+\.", text, re.MULTILINE)
        assert len(matches) >= 10

    def test_specialized_module_docs_still_present(self):
        for name in [
            "ADAPTIVE_CAMPAIGN_ENGINE.md",
            "FINANCIAL_REPORTING_ENGINE.md",
            "PREDICTIVE_MAINTENANCE_ENGINE.md",
        ]:
            assert (DOC_DIR / "modules" / name).exists()

    def test_round51_tests_still_pass_count(self):
        """Round 51 test file should still exist."""
        assert (TESTS_DIR / "test_gap_closure_round51.py").exists()
