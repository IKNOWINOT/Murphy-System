"""
Test Suite: Domain Gate Validators — DEFICIENCY-1

Verifies that each of the 10 gate validators in DomainGateGenerator uses
real validation logic instead of the former mock that always returned
{"passed": True, "score": 0.95}.

Each validator is tested for:
  - Valid data → passes with score > 0.8
  - Invalid data → fails with score < 0.5
  - Edge cases (empty dict, missing keys) → handled gracefully, no exceptions

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from domain_gate_generator import DomainGateGenerator  # noqa: E402


@pytest.fixture(scope="module")
def gen():
    return DomainGateGenerator()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _call(gen: DomainGateGenerator, name: str, data: dict) -> dict:
    fn = gen.function_registry[name]
    return fn(data)


# ---------------------------------------------------------------------------
# validate_code_review
# ---------------------------------------------------------------------------

class TestValidateCodeReview:
    def test_valid_passes(self, gen):
        result = _call(gen, "validate_code_review", {
            "reviewers": ["alice", "bob"],
            "approvals": 2,
            "comments_resolved": True,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_no_approvals_fails(self, gen):
        result = _call(gen, "validate_code_review", {
            "reviewers": ["alice"],
            "approvals": 0,
            "comments_resolved": True,
        })
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_unresolved_comments_fails(self, gen):
        result = _call(gen, "validate_code_review", {
            "reviewers": ["alice"],
            "approvals": 1,
            "comments_resolved": False,
        })
        assert result["passed"] is False

    def test_empty_dict_no_exception(self, gen):
        result = _call(gen, "validate_code_review", {})
        assert result["passed"] is False

    def test_result_has_required_keys(self, gen):
        result = _call(gen, "validate_code_review", {
            "reviewers": ["alice"],
            "approvals": 1,
            "comments_resolved": True,
        })
        for key in ("validation_type", "passed", "score", "details", "timestamp"):
            assert key in result


# ---------------------------------------------------------------------------
# validate_test_coverage
# ---------------------------------------------------------------------------

class TestValidateTestCoverage:
    def test_above_threshold_passes(self, gen):
        result = _call(gen, "validate_test_coverage", {"coverage_percent": 85.0})
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_below_threshold_fails(self, gen):
        result = _call(gen, "validate_test_coverage", {"coverage_percent": 50.0})
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_missing_field_fails(self, gen):
        result = _call(gen, "validate_test_coverage", {})
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_exact_threshold_passes(self, gen):
        result = _call(gen, "validate_test_coverage", {"coverage_percent": 80.0})
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# validate_documentation
# ---------------------------------------------------------------------------

class TestValidateDocumentation:
    def test_valid_passes(self, gen):
        result = _call(gen, "validate_documentation", {
            "doc_files_present": ["README.md", "API.md"],
            "has_readme": True,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_no_readme_fails(self, gen):
        result = _call(gen, "validate_documentation", {
            "doc_files_present": ["API.md"],
            "has_readme": False,
        })
        assert result["passed"] is False

    def test_empty_doc_files_fails(self, gen):
        result = _call(gen, "validate_documentation", {
            "doc_files_present": [],
            "has_readme": True,
        })
        assert result["passed"] is False

    def test_empty_dict_no_exception(self, gen):
        result = _call(gen, "validate_documentation", {})
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# validate_security_scan
# ---------------------------------------------------------------------------

class TestValidateSecurityScan:
    def test_clean_scan_passes(self, gen):
        result = _call(gen, "validate_security_scan", {
            "critical_vulnerabilities": 0,
            "high_vulnerabilities": 2,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_critical_vuln_fails(self, gen):
        result = _call(gen, "validate_security_scan", {
            "critical_vulnerabilities": 1,
            "high_vulnerabilities": 0,
        })
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_too_many_high_fails(self, gen):
        result = _call(gen, "validate_security_scan", {
            "critical_vulnerabilities": 0,
            "high_vulnerabilities": 10,
        })
        assert result["passed"] is False

    def test_missing_fields_fails(self, gen):
        result = _call(gen, "validate_security_scan", {})
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# validate_performance
# ---------------------------------------------------------------------------

class TestValidatePerformance:
    def test_good_perf_passes(self, gen):
        result = _call(gen, "validate_performance", {
            "p99_latency_ms": 200.0,
            "error_rate": 0.001,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_high_latency_fails(self, gen):
        result = _call(gen, "validate_performance", {
            "p99_latency_ms": 1000.0,
            "error_rate": 0.001,
        })
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_high_error_rate_fails(self, gen):
        result = _call(gen, "validate_performance", {
            "p99_latency_ms": 100.0,
            "error_rate": 0.05,
        })
        assert result["passed"] is False

    def test_empty_dict_no_exception(self, gen):
        result = _call(gen, "validate_performance", {})
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# validate_compliance_gdpr
# ---------------------------------------------------------------------------

class TestValidateComplianceGdpr:
    def test_all_fields_passes(self, gen):
        result = _call(gen, "validate_compliance_gdpr", {
            "data_inventory": True,
            "consent_mechanism": True,
            "dpo_assigned": True,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_missing_dpo_fails(self, gen):
        result = _call(gen, "validate_compliance_gdpr", {
            "data_inventory": True,
            "consent_mechanism": True,
            "dpo_assigned": False,
        })
        assert result["passed"] is False

    def test_empty_dict_fails(self, gen):
        result = _call(gen, "validate_compliance_gdpr", {})
        assert result["passed"] is False
        assert result["score"] < 0.5


# ---------------------------------------------------------------------------
# validate_compliance_hipaa
# ---------------------------------------------------------------------------

class TestValidateComplianceHipaa:
    def test_all_fields_passes(self, gen):
        result = _call(gen, "validate_compliance_hipaa", {
            "encryption_at_rest": True,
            "access_controls": True,
            "audit_logging": True,
            "baa_signed": True,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_missing_baa_fails(self, gen):
        result = _call(gen, "validate_compliance_hipaa", {
            "encryption_at_rest": True,
            "access_controls": True,
            "audit_logging": True,
            "baa_signed": False,
        })
        assert result["passed"] is False

    def test_empty_dict_fails(self, gen):
        result = _call(gen, "validate_compliance_hipaa", {})
        assert result["passed"] is False
        assert result["score"] < 0.5


# ---------------------------------------------------------------------------
# validate_scalability
# ---------------------------------------------------------------------------

class TestValidateScalability:
    def test_above_threshold_passes(self, gen):
        result = _call(gen, "validate_scalability", {"max_concurrent_users": 2000})
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_below_threshold_fails(self, gen):
        result = _call(gen, "validate_scalability", {"max_concurrent_users": 100})
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_missing_field_fails(self, gen):
        result = _call(gen, "validate_scalability", {})
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# validate_availability
# ---------------------------------------------------------------------------

class TestValidateAvailability:
    def test_high_uptime_passes(self, gen):
        result = _call(gen, "validate_availability", {"uptime_percent": 99.9})
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_low_uptime_fails(self, gen):
        result = _call(gen, "validate_availability", {"uptime_percent": 95.0})
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_missing_field_fails(self, gen):
        result = _call(gen, "validate_availability", {})
        assert result["passed"] is False

    def test_exactly_995_passes(self, gen):
        result = _call(gen, "validate_availability", {"uptime_percent": 99.5})
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# validate_backup
# ---------------------------------------------------------------------------

class TestValidateBackup:
    def test_frequent_tested_backup_passes(self, gen):
        result = _call(gen, "validate_backup", {
            "backup_frequency_hours": 6,
            "restore_tested": True,
        })
        assert result["passed"] is True
        assert result["score"] > 0.8

    def test_infrequent_backup_fails(self, gen):
        result = _call(gen, "validate_backup", {
            "backup_frequency_hours": 48,
            "restore_tested": True,
        })
        assert result["passed"] is False
        assert result["score"] < 0.5

    def test_untested_restore_fails(self, gen):
        result = _call(gen, "validate_backup", {
            "backup_frequency_hours": 12,
            "restore_tested": False,
        })
        assert result["passed"] is False

    def test_empty_dict_fails(self, gen):
        result = _call(gen, "validate_backup", {})
        assert result["passed"] is False
        assert result["score"] < 0.5
