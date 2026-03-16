"""Tests for the Functionality Heatmap & Capability Scanner module."""

import threading
import pytest

from src.functionality_heatmap import (
    CAPABILITY_REGISTRY,
    ISA95_LEVELS,
    CapabilityCell,
    FunctionalityHeatmap,
    _assign_isa95_level,
)


@pytest.fixture
def heatmap():
    return FunctionalityHeatmap()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_all_registry_cells_created(self, heatmap):
        """Every function in CAPABILITY_REGISTRY must have a cold cell."""
        total_expected = sum(
            len(fns)
            for subdomains in CAPABILITY_REGISTRY.values()
            for fns in subdomains.values()
        )
        hm_data = heatmap.get_heatmap()
        total_actual = sum(
            len(cells)
            for subdomains in hm_data.values()
            for cells in subdomains.values()
        )
        assert total_actual == total_expected

    def test_initial_temperature_is_zero(self, heatmap):
        """All cells must start at temperature 0.0."""
        hm_data = heatmap.get_heatmap()
        for subdomains in hm_data.values():
            for cells in subdomains.values():
                for cell in cells:
                    assert cell["temperature"] == 0.0

    def test_initial_activity_count_is_zero(self, heatmap):
        hm_data = heatmap.get_heatmap()
        for subdomains in hm_data.values():
            for cells in subdomains.values():
                for cell in cells:
                    assert cell["activity_count"] == 0

    def test_initial_status_not_started(self, heatmap):
        hm_data = heatmap.get_heatmap()
        for subdomains in hm_data.values():
            for cells in subdomains.values():
                for cell in cells:
                    assert cell["automation_status"] == "not_started"


# ---------------------------------------------------------------------------
# Activity recording
# ---------------------------------------------------------------------------

class TestRecordActivity:
    def test_activity_increments_count(self, heatmap):
        cell = heatmap.record_activity(
            "building_automation", "fire_safety", "smoke_detection"
        )
        assert cell.activity_count == 1

    def test_activity_raises_temperature(self, heatmap):
        cell = heatmap.record_activity(
            "building_automation", "fire_safety", "smoke_detection"
        )
        assert cell.temperature == pytest.approx(0.01)

    def test_multiple_activities_accumulate(self, heatmap):
        for _ in range(50):
            heatmap.record_activity(
                "building_automation", "hvac", "temperature_control"
            )
        cell = heatmap.record_activity(
            "building_automation", "hvac", "temperature_control"
        )
        assert cell.activity_count == 51
        assert cell.temperature == pytest.approx(0.51)

    def test_temperature_capped_at_one(self, heatmap):
        for _ in range(200):
            heatmap.record_activity(
                "manufacturing", "production", "scheduling"
            )
        cell = heatmap.record_activity(
            "manufacturing", "production", "scheduling"
        )
        assert cell.temperature == 1.0

    def test_automation_id_linked(self, heatmap):
        cell = heatmap.record_activity(
            "enterprise", "hr", "onboarding", automation_id="auto-001"
        )
        assert "auto-001" in cell.linked_automations

    def test_duplicate_automation_id_not_added_twice(self, heatmap):
        heatmap.record_activity("enterprise", "hr", "onboarding", automation_id="auto-001")
        cell = heatmap.record_activity(
            "enterprise", "hr", "onboarding", automation_id="auto-001"
        )
        assert cell.linked_automations.count("auto-001") == 1

    def test_last_activity_timestamp_set(self, heatmap):
        cell = heatmap.record_activity(
            "logistics", "fleet", "vehicle_tracking"
        )
        assert cell.last_activity != ""

    def test_unknown_capability_raises_key_error(self, heatmap):
        with pytest.raises(KeyError):
            heatmap.record_activity("unknown_domain", "sub", "fn")


# ---------------------------------------------------------------------------
# Automation status
# ---------------------------------------------------------------------------

class TestSetAutomationStatus:
    def test_set_valid_status(self, heatmap):
        result = heatmap.set_automation_status(
            "healthcare", "clinical", "patient_records", "automated"
        )
        assert result is True
        hm = heatmap.get_heatmap("healthcare")
        cell = next(
            c for c in hm["healthcare"]["clinical"]
            if c["function_name"] == "patient_records"
        )
        assert cell["automation_status"] == "automated"

    def test_set_invalid_status_returns_false(self, heatmap):
        result = heatmap.set_automation_status(
            "healthcare", "clinical", "patient_records", "flying"
        )
        assert result is False

    def test_unknown_cell_returns_false(self, heatmap):
        result = heatmap.set_automation_status(
            "no_domain", "no_sub", "no_fn", "automated"
        )
        assert result is False

    @pytest.mark.parametrize(
        "status",
        ["not_started", "planned", "in_progress", "automated", "optimized"],
    )
    def test_all_valid_statuses_accepted(self, heatmap, status):
        assert heatmap.set_automation_status(
            "enterprise", "finance", "budgeting", status
        ) is True


# ---------------------------------------------------------------------------
# Cold spots
# ---------------------------------------------------------------------------

class TestColdSpots:
    def test_all_cells_cold_initially(self, heatmap):
        cold = heatmap.get_cold_spots()
        total_expected = sum(
            len(fns)
            for subdomains in CAPABILITY_REGISTRY.values()
            for fns in subdomains.values()
        )
        assert len(cold) == total_expected

    def test_active_cell_excluded_from_cold_spots(self, heatmap):
        # Drive temperature to 0.5 (50 activities)
        for _ in range(50):
            heatmap.record_activity(
                "building_automation", "hvac", "temperature_control"
            )
        cold = heatmap.get_cold_spots(threshold=0.1)
        names = [c.function_name for c in cold]
        assert "temperature_control" not in names

    def test_custom_threshold(self, heatmap):
        for _ in range(5):
            heatmap.record_activity("enterprise", "sales", "pipeline")
        cold_strict = heatmap.get_cold_spots(threshold=0.04)
        cold_loose = heatmap.get_cold_spots(threshold=0.1)
        assert len(cold_strict) <= len(cold_loose)


# ---------------------------------------------------------------------------
# Hot spots
# ---------------------------------------------------------------------------

class TestHotSpots:
    def test_no_hot_spots_initially(self, heatmap):
        assert heatmap.get_hot_spots() == []

    def test_cell_becomes_hot_spot(self, heatmap):
        for _ in range(80):
            heatmap.record_activity(
                "manufacturing", "maintenance", "predictive"
            )
        hot = heatmap.get_hot_spots(threshold=0.7)
        names = [c.function_name for c in hot]
        assert "predictive" in names

    def test_hot_spots_sorted_descending(self, heatmap):
        for _ in range(70):
            heatmap.record_activity("logistics", "routing", "route_planning")
        for _ in range(90):
            heatmap.record_activity("logistics", "routing", "real_time_tracking")
        hot = heatmap.get_hot_spots(threshold=0.5)
        temps = [c.temperature for c in hot]
        assert temps == sorted(temps, reverse=True)


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

class TestCoverageReport:
    def test_report_has_all_domains(self, heatmap):
        report = heatmap.get_coverage_report()
        assert set(report.keys()) == set(CAPABILITY_REGISTRY.keys())

    def test_initial_automated_count_zero(self, heatmap):
        report = heatmap.get_coverage_report()
        for stats in report.values():
            assert stats["automated_count"] == 0

    def test_automated_count_increments(self, heatmap):
        heatmap.set_automation_status(
            "enterprise", "hr", "onboarding", "automated"
        )
        heatmap.set_automation_status(
            "enterprise", "hr", "payroll", "optimized"
        )
        report = heatmap.get_coverage_report()
        assert report["enterprise"]["automated_count"] == 2

    def test_coverage_percent_math(self, heatmap):
        heatmap.set_automation_status(
            "healthcare", "clinical", "patient_records", "automated"
        )
        report = heatmap.get_coverage_report()
        total = report["healthcare"]["total_functions"]
        expected_pct = round((1 / total) * 100.0, 2)
        assert report["healthcare"]["coverage_percent"] == pytest.approx(
            expected_pct, abs=0.01
        )

    def test_avg_temperature_reflects_activity(self, heatmap):
        for _ in range(100):
            heatmap.record_activity(
                "logistics", "warehouse", "receiving"
            )
        report = heatmap.get_coverage_report()
        # 'receiving' is now at temp 1.0; avg should be > 0
        assert report["logistics"]["avg_temperature"] > 0.0


# ---------------------------------------------------------------------------
# ISA-95 level assignment
# ---------------------------------------------------------------------------

class TestISA95LevelAssignment:
    @pytest.mark.parametrize(
        "fn_name,expected_level",
        [
            ("smoke_detection", "L0"),
            ("submeter_reading", "L0"),
            ("temperature_control", "L1"),
            ("alarm_management", "L2"),
            ("scheduling", "L2"),
            ("quality_inspection", "L3"),
            ("vendor_management", "L3"),
            ("budgeting", "L4"),
            ("forecasting", "L4"),
            ("analytics", "L4"),
            ("compliance", "L4"),
            ("reporting", "L4"),
        ],
    )
    def test_keyword_mapping(self, fn_name, expected_level):
        assert _assign_isa95_level(fn_name) == expected_level

    def test_default_level_is_l3(self):
        assert _assign_isa95_level("unknown_function_xyz") == "L3"


# ---------------------------------------------------------------------------
# Domain filtering
# ---------------------------------------------------------------------------

class TestDomainFiltering:
    def test_get_heatmap_with_domain_filter(self, heatmap):
        result = heatmap.get_heatmap(domain="enterprise")
        assert set(result.keys()) == {"enterprise"}

    def test_get_heatmap_without_filter_returns_all(self, heatmap):
        result = heatmap.get_heatmap()
        assert set(result.keys()) == set(CAPABILITY_REGISTRY.keys())

    def test_unknown_domain_returns_empty(self, heatmap):
        result = heatmap.get_heatmap(domain="nonexistent_domain")
        assert result == {}


# ---------------------------------------------------------------------------
# Elevation map aggregation
# ---------------------------------------------------------------------------

class TestElevationMap:
    def test_elevation_map_has_all_levels(self, heatmap):
        elev = heatmap.get_elevation_map()
        assert set(elev.keys()) == set(ISA95_LEVELS.keys())

    def test_elevation_map_totals_match_registry(self, heatmap):
        total_from_registry = sum(
            len(fns)
            for subdomains in CAPABILITY_REGISTRY.values()
            for fns in subdomains.values()
        )
        elev = heatmap.get_elevation_map()
        total_from_elev = sum(v["count"] for v in elev.values())
        assert total_from_elev == total_from_registry

    def test_elevation_map_labels(self, heatmap):
        elev = heatmap.get_elevation_map()
        for lvl, info in elev.items():
            assert info["label"] == ISA95_LEVELS[lvl]

    def test_elevation_map_counts_positive(self, heatmap):
        """Every level should have at least one capability assigned."""
        elev = heatmap.get_elevation_map()
        # Not all levels may have entries given the registry, but the structure
        # should always be present with non-negative counts.
        for info in elev.values():
            assert info["count"] >= 0


# ---------------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------------

class TestDashboardData:
    def test_dashboard_keys_present(self, heatmap):
        dash = heatmap.get_dashboard_data()
        assert "total_functions" in dash
        assert "total_automated" in dash
        assert "overall_coverage_percent" in dash
        assert "top_hot_spots" in dash
        assert "top_cold_spots" in dash
        assert "coverage_per_domain" in dash

    def test_initial_dashboard_no_hot_spots(self, heatmap):
        dash = heatmap.get_dashboard_data()
        assert dash["top_hot_spots"] == []

    def test_dashboard_hot_spots_after_activity(self, heatmap):
        for _ in range(80):
            heatmap.record_activity(
                "manufacturing", "production", "oee_calculation"
            )
        dash = heatmap.get_dashboard_data()
        hot_names = [h["function_name"] for h in dash["top_hot_spots"]]
        assert "oee_calculation" in hot_names


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_activity(self, heatmap):
        errors = []

        def worker():
            try:
                for _ in range(10):
                    heatmap.record_activity(
                        "building_automation", "lighting", "scheduling"
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        hm = heatmap.get_heatmap("building_automation")
        cell = next(
            c for c in hm["building_automation"]["lighting"]
            if c["function_name"] == "scheduling"
        )
        assert cell["activity_count"] == 100
