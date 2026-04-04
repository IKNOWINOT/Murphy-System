"""
Tests for ARCH-007: FounderDigestGenerator.

Validates digest generation with real telemetry from ObservabilitySummaryCounters
and OperatingAnalysisDashboard, period support, history, and status reporting.

Design Label: TEST-ARCH007-DIG
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from founder_update_engine.digest_generator import (
    FounderDigestGenerator,
    DigestPeriod,
    FounderDigest,
)
from founder_update_engine import (
    FounderDigestGenerator as FounderDigestGeneratorExport,
    DigestPeriod as DigestPeriodExport,
    FounderDigest as FounderDigestExport,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def generator():
    """Generator with no injected dependencies (lazy loads if available)."""
    return FounderDigestGenerator(
        observability_counters=None,
        operating_analysis_dashboard=None,
        subsystem_registry=None,
    )


# ------------------------------------------------------------------
# Package-level exports
# ------------------------------------------------------------------

class TestPackageExports:
    def test_exported_from_package(self):
        assert FounderDigestGeneratorExport is FounderDigestGenerator
        assert DigestPeriodExport is DigestPeriod
        assert FounderDigestExport is FounderDigest


# ------------------------------------------------------------------
# DigestPeriod enum
# ------------------------------------------------------------------

class TestDigestPeriod:
    def test_daily_value(self):
        assert DigestPeriod.DAILY.value == "daily"

    def test_weekly_value(self):
        assert DigestPeriod.WEEKLY.value == "weekly"

    def test_all_periods(self):
        assert set(p.value for p in DigestPeriod) == {"daily", "weekly"}


# ------------------------------------------------------------------
# Digest generation
# ------------------------------------------------------------------

class TestDigestGeneration:
    def test_generate_returns_digest(self, generator):
        d = generator.generate()
        assert isinstance(d, FounderDigest)

    def test_generate_daily(self, generator):
        d = generator.generate(DigestPeriod.DAILY)
        assert d.period == DigestPeriod.DAILY

    def test_generate_weekly(self, generator):
        d = generator.generate(DigestPeriod.WEEKLY)
        assert d.period == DigestPeriod.WEEKLY

    def test_digest_id_format(self, generator):
        d = generator.generate()
        assert d.digest_id.startswith("digest-")

    def test_digest_has_timestamp(self, generator):
        d = generator.generate()
        assert d.generated_at is not None
        assert "T" in d.generated_at  # ISO format

    def test_digest_unique_ids(self, generator):
        ids = {generator.generate().digest_id for _ in range(5)}
        assert len(ids) == 5

    def test_digest_to_dict(self, generator):
        d = generator.generate()
        dd = d.to_dict()
        assert isinstance(dd, dict)
        required_keys = {
            "digest_id", "period", "generated_at",
            "total_subsystems", "healthy_subsystems",
            "degraded_subsystems", "failed_subsystems",
            "total_behavior_fixes", "total_coverage_events",
            "error_rate_pct", "open_recommendations",
            "counter_summary", "subsystem_health",
        }
        assert required_keys <= set(dd.keys())

    def test_digest_numeric_fields_are_non_negative(self, generator):
        d = generator.generate()
        assert d.total_subsystems >= 0
        assert d.healthy_subsystems >= 0
        assert d.degraded_subsystems >= 0
        assert d.failed_subsystems >= 0
        assert d.total_behavior_fixes >= 0
        assert d.total_coverage_events >= 0
        assert d.error_rate_pct >= 0.0


# ------------------------------------------------------------------
# Counter integration
# ------------------------------------------------------------------

class TestCounterIntegration:
    def test_digest_with_real_counters(self):
        from observability_counters import ObservabilitySummaryCounters
        counters = ObservabilitySummaryCounters()
        # Record some activity
        counters.record_fix("module_a", "timeout", "Fixed timeout handling")
        counters.record_fix("module_b", "null_check", "Added null guard")
        counters.record_coverage("test_mod", 5, "Added coverage")

        generator = FounderDigestGenerator(observability_counters=counters)
        d = generator.generate()
        assert d.total_behavior_fixes >= 2
        assert d.counter_summary.get("behavior_fix", 0) >= 2

    def test_digest_error_rate_from_counters(self):
        from observability_counters import ObservabilitySummaryCounters
        counters = ObservabilitySummaryCounters()
        # 5 fixes, 5 permutation_coverage → error_rate = 50%
        for _ in range(5):
            counters.record_fix("mod", "type", "desc")
        for _ in range(5):
            counters.record_coverage("mod", 1, "desc")

        generator = FounderDigestGenerator(observability_counters=counters)
        d = generator.generate()
        assert d.error_rate_pct == pytest.approx(50.0, abs=1.0)


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

class TestDigestHistory:
    def test_get_digests_empty(self, generator):
        assert generator.get_digests() == []

    def test_get_digests_after_generate(self, generator):
        generator.generate()
        generator.generate(DigestPeriod.WEEKLY)
        digests = generator.get_digests()
        assert len(digests) == 2

    def test_get_digests_limit(self, generator):
        for _ in range(10):
            generator.generate()
        digests = generator.get_digests(limit=3)
        assert len(digests) == 3

    def test_get_digests_returns_dicts(self, generator):
        generator.generate()
        digests = generator.get_digests()
        assert isinstance(digests[0], dict)
        assert "digest_id" in digests[0]

    def test_digest_history_bounded(self):
        gen = FounderDigestGenerator(
            observability_counters=None,
            operating_analysis_dashboard=None,
            subsystem_registry=None,
            max_digest_history=10,
        )
        for _ in range(25):
            gen.generate()
        # With max=10, eviction removes 1 when full → max stored ≈ 10
        assert len(gen._digests) <= 11


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_empty(self, generator):
        s = generator.get_status()
        assert s["total_digests"] == 0

    def test_status_after_generate(self, generator):
        generator.generate()
        s = generator.get_status()
        assert s["total_digests"] == 1

    def test_status_has_attachment_flags(self, generator):
        s = generator.get_status()
        assert "counters_attached" in s
        assert "dashboard_attached" in s
        assert "registry_attached" in s

    def test_status_with_counters(self):
        from observability_counters import ObservabilitySummaryCounters
        gen = FounderDigestGenerator(observability_counters=ObservabilitySummaryCounters())
        s = gen.get_status()
        assert s["counters_attached"] is True


# ------------------------------------------------------------------
# FounderDigest dataclass
# ------------------------------------------------------------------

class TestFounderDigest:
    def test_defaults(self, generator):
        d = generator.generate()
        assert isinstance(d.counter_summary, dict)
        assert isinstance(d.subsystem_health, list)

    def test_to_dict_period_serialised_as_string(self, generator):
        d = generator.generate(DigestPeriod.WEEKLY)
        dd = d.to_dict()
        assert dd["period"] == "weekly"

    def test_to_dict_error_rate_rounded(self, generator):
        d = generator.generate()
        dd = d.to_dict()
        assert isinstance(dd["error_rate_pct"], float)
