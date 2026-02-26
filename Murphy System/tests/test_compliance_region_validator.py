"""Tests for the Compliance Region Validator — Section 12 Step 5.2."""

import pytest
from src.compliance_region_validator import (
    ComplianceRegionValidator,
    RegionRequirement,
)


@pytest.fixture
def validator():
    """Return a fresh ComplianceRegionValidator with default requirements."""
    return ComplianceRegionValidator()


# ------------------------------------------------------------------
# Default region requirements
# ------------------------------------------------------------------

class TestDefaultRegions:
    def test_eu_defaults_loaded(self, validator):
        info = validator.get_region_requirements("EU")
        assert info["status"] == "found"
        assert info["framework"] == "GDPR"

    def test_us_ca_defaults_loaded(self, validator):
        info = validator.get_region_requirements("US_CA")
        assert info["status"] == "found"
        assert info["framework"] == "CCPA"

    def test_us_hipaa_defaults_loaded(self, validator):
        info = validator.get_region_requirements("US_HIPAA")
        assert info["status"] == "found"
        assert info["framework"] == "HIPAA"
        assert info["retention_max_days"] == 2190

    def test_ca_defaults_loaded(self, validator):
        info = validator.get_region_requirements("CA")
        assert info["status"] == "found"
        assert info["framework"] == "PIPEDA"

    def test_br_defaults_loaded(self, validator):
        info = validator.get_region_requirements("BR")
        assert info["status"] == "found"
        assert info["framework"] == "LGPD"

    def test_au_defaults_loaded(self, validator):
        info = validator.get_region_requirements("AU")
        assert info["status"] == "found"
        assert info["framework"] == "Privacy Act"
        assert info["cross_border_allowed"] is True


# ------------------------------------------------------------------
# Region registration and retrieval
# ------------------------------------------------------------------

class TestRegionRegistration:
    def test_register_new_region(self, validator):
        req = RegionRequirement(
            region="JP",
            framework="APPI",
            data_residency="JP",
            regulatory_body="PPC",
        )
        reg_id = validator.register_region(req)
        assert isinstance(reg_id, str)
        assert len(reg_id) == 12

    def test_registered_region_retrievable(self, validator):
        req = RegionRequirement(
            region="JP",
            framework="APPI",
            data_residency="JP",
            regulatory_body="PPC",
        )
        validator.register_region(req)
        info = validator.get_region_requirements("JP")
        assert info["status"] == "found"
        assert info["framework"] == "APPI"

    def test_register_overrides_existing(self, validator):
        req = RegionRequirement(
            region="EU",
            framework="GDPR_v2",
            data_residency="EU",
            retention_max_days=180,
            regulatory_body="EDPB",
        )
        validator.register_region(req)
        info = validator.get_region_requirements("EU")
        assert info["framework"] == "GDPR_v2"
        assert info["retention_max_days"] == 180

    def test_get_unknown_region(self, validator):
        info = validator.get_region_requirements("UNKNOWN")
        assert info["status"] == "unknown_region"


# ------------------------------------------------------------------
# Delivery validation — compliant
# ------------------------------------------------------------------

class TestDeliveryValidationCompliant:
    def test_compliant_delivery_same_region(self, validator):
        result = validator.validate_delivery("US_CA", ["email", "name"])
        assert result["status"] == "compliant"
        assert result["compliant"] is True

    def test_compliant_delivery_cross_border_allowed(self, validator):
        result = validator.validate_delivery("US_CA", ["email"], destination_region="CA")
        assert result["status"] == "compliant"
        assert result["compliant"] is True

    def test_compliant_delivery_has_framework(self, validator):
        result = validator.validate_delivery("EU", ["email", "name"])
        assert result["framework"] == "GDPR"


# ------------------------------------------------------------------
# Delivery validation — non-compliant
# ------------------------------------------------------------------

class TestDeliveryValidationNonCompliant:
    def test_non_compliant_cross_border_blocked(self, validator):
        result = validator.validate_delivery("EU", ["email"], destination_region="US_CA")
        assert result["status"] == "non_compliant"
        assert result["compliant"] is False
        assert any("Cross-border" in i for i in result["issues"])

    def test_non_compliant_empty_data_types(self, validator):
        result = validator.validate_delivery("EU", [])
        assert result["status"] == "non_compliant"
        assert result["compliant"] is False

    def test_unknown_region_delivery(self, validator):
        result = validator.validate_delivery("MARS", ["email"])
        assert result["status"] == "unknown_region"
        assert result["compliant"] is False


# ------------------------------------------------------------------
# Cross-border checks
# ------------------------------------------------------------------

class TestCrossBorderChecks:
    def test_cross_border_allowed(self, validator):
        result = validator.check_cross_border("US_CA", "CA")
        assert result["status"] == "allowed"
        assert result["allowed"] is True

    def test_cross_border_blocked(self, validator):
        result = validator.check_cross_border("EU", "US_CA")
        assert result["status"] == "blocked"
        assert result["allowed"] is False
        assert "GDPR" in result["reason"]

    def test_cross_border_unknown_source(self, validator):
        result = validator.check_cross_border("UNKNOWN", "EU")
        assert result["status"] == "unknown_region"
        assert result["allowed"] is False

    def test_cross_border_returns_framework(self, validator):
        result = validator.check_cross_border("CA", "AU")
        assert result["framework"] == "PIPEDA"


# ------------------------------------------------------------------
# Retention validation
# ------------------------------------------------------------------

class TestRetentionValidation:
    def test_retention_within_limit(self, validator):
        result = validator.validate_retention("EU", 300)
        assert result["status"] == "compliant"
        assert result["compliant"] is True

    def test_retention_exceeds_limit(self, validator):
        result = validator.validate_retention("EU", 400)
        assert result["status"] == "non_compliant"
        assert result["compliant"] is False

    def test_retention_at_limit(self, validator):
        result = validator.validate_retention("EU", 365)
        assert result["status"] == "compliant"
        assert result["compliant"] is True

    def test_retention_unknown_region(self, validator):
        result = validator.validate_retention("UNKNOWN", 100)
        assert result["status"] == "unknown_region"
        assert result["compliant"] is False


# ------------------------------------------------------------------
# Multi-region framework aggregation
# ------------------------------------------------------------------

class TestFrameworkAggregation:
    def test_aggregate_multiple_regions(self, validator):
        result = validator.get_required_frameworks(["EU", "US_CA", "CA"])
        assert result["status"] == "aggregated"
        assert "GDPR" in result["frameworks"]
        assert "CCPA" in result["frameworks"]
        assert "PIPEDA" in result["frameworks"]
        assert result["total_frameworks"] == 3

    def test_aggregate_with_unknown_regions(self, validator):
        result = validator.get_required_frameworks(["EU", "MARS"])
        assert "MARS" in result["unknown_regions"]
        assert result["total_frameworks"] == 1

    def test_aggregate_empty_list(self, validator):
        result = validator.get_required_frameworks([])
        assert result["total_frameworks"] == 0
        assert result["frameworks"] == {}


# ------------------------------------------------------------------
# Validation history
# ------------------------------------------------------------------

class TestValidationHistory:
    def test_record_validation(self, validator):
        record_id = validator.record_validation("EU", {"status": "compliant"})
        assert isinstance(record_id, str)
        assert len(record_id) == 12

    def test_history_contains_record(self, validator):
        validator.record_validation("EU", {"status": "compliant"})
        history = validator.get_validation_history()
        assert len(history) == 1
        assert history[0]["region"] == "EU"
        assert "recorded_at" in history[0]

    def test_history_filter_by_region(self, validator):
        validator.record_validation("EU", {"status": "compliant"})
        validator.record_validation("US_CA", {"status": "non_compliant"})
        validator.record_validation("EU", {"status": "compliant"})
        eu_history = validator.get_validation_history(region="EU")
        assert len(eu_history) == 2

    def test_history_all_regions(self, validator):
        validator.record_validation("EU", {"status": "compliant"})
        validator.record_validation("US_CA", {"status": "non_compliant"})
        all_history = validator.get_validation_history()
        assert len(all_history) == 2

    def test_history_empty_initially(self, validator):
        assert validator.get_validation_history() == []


# ------------------------------------------------------------------
# Compliance report
# ------------------------------------------------------------------

class TestComplianceReport:
    def test_report_all_regions(self, validator):
        report = validator.get_compliance_report()
        assert report["status"] == "report_generated"
        assert report["total_regions"] == 6
        assert report["known_regions"] == 6
        assert "generated_at" in report

    def test_report_specific_regions(self, validator):
        report = validator.get_compliance_report(regions=["EU", "CA"])
        assert report["total_regions"] == 2
        assert report["known_regions"] == 2

    def test_report_with_unknown_region(self, validator):
        report = validator.get_compliance_report(regions=["EU", "MARS"])
        assert report["total_regions"] == 2
        assert report["unknown_regions"] == 1

    def test_report_includes_validation_history_count(self, validator):
        validator.record_validation("EU", {"status": "compliant"})
        report = validator.get_compliance_report()
        assert report["validation_history_count"] == 1


# ------------------------------------------------------------------
# Reset / clear
# ------------------------------------------------------------------

class TestClear:
    def test_clear_resets_history(self, validator):
        validator.record_validation("EU", {"status": "compliant"})
        validator.clear()
        assert validator.get_validation_history() == []

    def test_clear_reloads_defaults(self, validator):
        validator.register_region(RegionRequirement(
            region="JP", framework="APPI", data_residency="JP",
            regulatory_body="PPC",
        ))
        validator.clear()
        info = validator.get_region_requirements("JP")
        assert info["status"] == "unknown_region"
        # Defaults should still be present
        eu = validator.get_region_requirements("EU")
        assert eu["status"] == "found"

    def test_clear_preserves_default_count(self, validator):
        validator.clear()
        report = validator.get_compliance_report()
        assert report["total_regions"] == 6
