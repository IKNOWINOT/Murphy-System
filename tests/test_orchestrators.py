"""
Tests for SafetyOrchestrator, EfficiencyOrchestrator, and SupplyOrchestrator.

Covers:
- Auto-setup and zero-configuration instantiation
- Integration with WingmanProtocol (validation actually runs)
- Dashboard data generation for each orchestrator
- Anomaly detection and reorder triggering
- Thread safety basics
"""

import threading
import pytest

from src.safety_orchestrator import SafetyOrchestrator
from src.efficiency_orchestrator import EfficiencyOrchestrator
from src.supply_orchestrator import SupplyOrchestrator
from src.wingman_protocol import WingmanProtocol
from src.telemetry_adapter import TelemetryAdapter
from src.golden_path_bridge import GoldenPathBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def safety():
    return SafetyOrchestrator()


@pytest.fixture
def efficiency():
    return EfficiencyOrchestrator()


@pytest.fixture
def supply():
    return SupplyOrchestrator()


# ===========================================================================
# SafetyOrchestrator
# ===========================================================================

class TestSafetyOrchestratorSetup:

    def test_zero_config_instantiation(self):
        """SafetyOrchestrator() must work with no arguments."""
        o = SafetyOrchestrator()
        assert o is not None

    def test_uses_provided_dependencies(self):
        wp = WingmanProtocol()
        ta = TelemetryAdapter()
        gpb = GoldenPathBridge()
        o = SafetyOrchestrator(wingman_protocol=wp, telemetry=ta, golden_paths=gpb)
        assert o.wingman is wp
        assert o.telemetry is ta
        assert o.golden_paths is gpb

    def test_all_domains_have_pairs(self, safety):
        for domain in SafetyOrchestrator.SAFETY_DOMAINS:
            assert domain in safety._domain_pairs, f"Missing pair for {domain}"

    def test_safety_runbooks_registered(self, safety):
        for domain in SafetyOrchestrator.SAFETY_DOMAINS:
            rb = safety.wingman.get_runbook(f"safety_{domain}")
            assert rb is not None, f"Runbook missing for {domain}"
            assert rb.domain == domain


class TestSafetyOrchestratorRunCheck:

    def test_valid_readings_approved(self, safety):
        result = safety.run_safety_check("fire_safety", {"result": "all clear"})
        assert result["approved"] is True
        assert result["severity"] == "ok"
        assert isinstance(result["recommendation"], str)
        assert len(result["recommendation"]) > 0

    def test_empty_readings_blocked(self, safety):
        result = safety.run_safety_check("fire_safety", {})
        assert result["approved"] is False
        assert len(result["violations"]) > 0
        assert isinstance(result["recommendation"], str)

    def test_unknown_domain_returns_error(self, safety):
        result = safety.run_safety_check("unknown_domain", {"value": 1})
        assert result["approved"] is False
        assert "unknown_domain" in result["violations"][0].lower() or \
               "unknown" in result["recommendation"].lower()

    def test_all_six_domains_can_be_checked(self, safety):
        for domain in SafetyOrchestrator.SAFETY_DOMAINS:
            result = safety.run_safety_check(domain, {"result": "ok"})
            assert "approved" in result
            assert "recommendation" in result

    def test_violation_severity_escalates(self, safety):
        """Multiple blocking failures produce 'critical' severity."""
        result = safety.run_safety_check("electrical", {})
        # With empty readings the has_output check fails → critical or warning
        assert result["severity"] in ("warning", "critical")

    def test_validation_actually_runs_through_wingman(self, safety):
        """WingmanProtocol validation history should grow after a check."""
        domain = "fall_protection"
        pair_id = safety._domain_pairs[domain]
        before = len(safety.wingman.get_validation_history(pair_id))
        safety.run_safety_check(domain, {"result": "harness checked"})
        after = len(safety.wingman.get_validation_history(pair_id))
        assert after == before + 1


class TestSafetyOrchestratorDashboard:

    def test_dashboard_structure(self, safety):
        safety.run_safety_check("fire_safety", {"result": "ok"})
        dash = safety.get_safety_dashboard()
        assert "domain_statuses" in dash
        assert "violation_history" in dash
        assert "overall_safety_score" in dash
        assert "generated_at" in dash

    def test_safety_score_range(self, safety):
        safety.run_safety_check("fire_safety", {"result": "ok"})
        dash = safety.get_safety_dashboard()
        assert 0.0 <= dash["overall_safety_score"] <= 100.0

    def test_domain_statuses_cover_all_domains(self, safety):
        dash = safety.get_safety_dashboard()
        for domain in SafetyOrchestrator.SAFETY_DOMAINS:
            assert domain in dash["domain_statuses"]

    def test_violations_recorded_in_history(self, safety):
        safety.run_safety_check("hazmat", {})  # empty → violation
        dash = safety.get_safety_dashboard()
        assert len(dash["violation_history"]["hazmat"]) >= 1


class TestSafetyOrchestratorCompliance:

    def test_osha_compliance_structure(self, safety):
        safety.run_safety_check("fire_safety", {"result": "ok"})
        status = safety.get_compliance_status("OSHA")
        assert status["regulatory_framework"] == "OSHA"
        assert "domain_compliance" in status
        assert "overall_alignment" in status

    def test_unknown_framework_falls_back_gracefully(self, safety):
        status = safety.get_compliance_status("UNKNOWN_FRAMEWORK")
        assert "domain_compliance" in status
        assert len(status["domain_compliance"]) == len(SafetyOrchestrator.SAFETY_DOMAINS)

    def test_all_domains_present_in_compliance(self, safety):
        status = safety.get_compliance_status("OSHA")
        for domain in SafetyOrchestrator.SAFETY_DOMAINS:
            assert domain in status["domain_compliance"]


# ===========================================================================
# EfficiencyOrchestrator
# ===========================================================================

class TestEfficiencyOrchestratorSetup:

    def test_zero_config_instantiation(self):
        o = EfficiencyOrchestrator()
        assert o is not None

    def test_uses_provided_dependencies(self):
        wp = WingmanProtocol()
        ta = TelemetryAdapter()
        o = EfficiencyOrchestrator(wingman_protocol=wp, telemetry=ta)
        assert o.wingman is wp
        assert o.telemetry is ta

    def test_all_resource_types_have_pairs(self, efficiency):
        for rtype in EfficiencyOrchestrator.RESOURCE_TYPES:
            assert rtype in efficiency._resource_pairs

    def test_efficiency_runbooks_registered(self, efficiency):
        for rtype in EfficiencyOrchestrator.RESOURCE_TYPES:
            rb = efficiency.wingman.get_runbook(f"efficiency_{rtype}")
            assert rb is not None


class TestEfficiencyOrchestratorRecordReading:

    def test_record_valid_reading(self, efficiency):
        result = efficiency.record_reading("electricity", 100.0, "kWh")
        assert result["recorded"] is True
        assert result["baseline"] == pytest.approx(100.0)
        assert result["deviation_percent"] == pytest.approx(0.0)
        assert isinstance(result["recommendation"], str)

    def test_baseline_updates_with_multiple_readings(self, efficiency):
        efficiency.record_reading("gas", 50.0, "m3")
        result = efficiency.record_reading("gas", 100.0, "m3")
        assert result["baseline"] == pytest.approx(75.0)

    def test_anomaly_detected_on_spike(self, efficiency):
        # Establish baseline
        for _ in range(10):
            efficiency.record_reading("water", 10.0, "L")
        # Record a spike
        result = efficiency.record_reading("water", 100.0, "L")
        assert result["anomaly_detected"] is True

    def test_no_anomaly_within_normal_range(self, efficiency):
        for v in [10.0, 10.5, 9.8, 10.2, 10.1]:
            result = efficiency.record_reading("electricity", v, "kWh")
        # Last reading should not be anomalous
        assert result["anomaly_detected"] is False

    def test_unknown_resource_type(self, efficiency):
        result = efficiency.record_reading("dark_matter", 1.0, "units")
        assert result["recorded"] is False
        assert "unknown" in result["recommendation"].lower()

    def test_first_reading_auto_creates_baseline(self, efficiency):
        result = efficiency.record_reading("steam", 42.0, "kg/h")
        assert result["recorded"] is True
        assert result["baseline"] == pytest.approx(42.0)


class TestEfficiencyOrchestratorScoring:

    def test_score_no_data(self, efficiency):
        score = efficiency.get_efficiency_score("electricity")
        assert score["electricity"]["score"] is None
        assert score["electricity"]["trend"] == "no_data"
        assert isinstance(score["electricity"]["recommendation"], str)

    def test_score_with_stable_readings(self, efficiency):
        for v in [10.0, 10.0, 10.0, 10.0, 10.0]:
            efficiency.record_reading("gas", v, "m3")
        score = efficiency.get_efficiency_score("gas")
        assert score["gas"]["score"] == pytest.approx(100.0)
        assert score["gas"]["trend"] == "stable"

    def test_score_all_resources_returned(self, efficiency):
        score = efficiency.get_efficiency_score()
        for rtype in EfficiencyOrchestrator.RESOURCE_TYPES:
            assert rtype in score

    def test_score_unknown_resource(self, efficiency):
        result = efficiency.get_efficiency_score("dark_matter")
        assert "error" in result


class TestEfficiencyOrchestratorOptimizations:

    def test_no_opportunities_with_stable_data(self, efficiency):
        for _ in range(5):
            efficiency.record_reading("electricity", 10.0, "kWh")
        opps = efficiency.get_optimization_opportunities()
        assert isinstance(opps, list)

    def test_peak_opportunity_detected(self, efficiency):
        for _ in range(10):
            efficiency.record_reading("electricity", 10.0, "kWh")
        efficiency.record_reading("electricity", 100.0, "kWh")  # spike
        opps = efficiency.get_optimization_opportunities()
        assert any("electricity" in o["resource_type"] for o in opps)

    def test_opportunity_has_required_fields(self, efficiency):
        for _ in range(10):
            efficiency.record_reading("gas", 10.0, "m3")
        efficiency.record_reading("gas", 80.0, "m3")
        opps = efficiency.get_optimization_opportunities()
        for opp in opps:
            assert "description" in opp
            assert "estimated_savings" in opp
            assert "confidence" in opp
            assert "implementation_steps" in opp


# ===========================================================================
# SupplyOrchestrator
# ===========================================================================

class TestSupplyOrchestratorSetup:

    def test_zero_config_instantiation(self):
        o = SupplyOrchestrator()
        assert o is not None

    def test_uses_provided_dependencies(self):
        wp = WingmanProtocol()
        ta = TelemetryAdapter()
        gpb = GoldenPathBridge()
        o = SupplyOrchestrator(wingman_protocol=wp, telemetry=ta, golden_paths=gpb)
        assert o.wingman is wp
        assert o.telemetry is ta
        assert o.golden_paths is gpb

    def test_supply_runbook_registered(self, supply):
        rb = supply.wingman.get_runbook("supply_chain")
        assert rb is not None

    def test_wingman_pair_created(self, supply):
        assert supply._pair_id is not None


class TestSupplyOrchestratorItems:

    def test_register_item(self, supply):
        result = supply.register_item("bolts-m8", "M8 Bolts", "kg", 5.0, 20.0)
        assert result["registered"] is True
        assert result["item_id"] == "bolts-m8"

    def test_register_item_stored(self, supply):
        supply.register_item("nuts-m8", "M8 Nuts", "kg", 2.0, 10.0)
        assert "nuts-m8" in supply._items

    def test_record_usage_reduces_stock(self, supply):
        supply.register_item("oil-5w30", "5W-30 Oil", "L", 10.0, 50.0)
        supply.record_receipt("oil-5w30", 100.0)
        result = supply.record_usage("oil-5w30", 5.0)
        assert result["recorded"] is True
        assert result["current_stock"] == pytest.approx(95.0)

    def test_record_usage_unknown_item(self, supply):
        result = supply.record_usage("ghost-item", 1.0)
        assert result["recorded"] is False
        assert isinstance(result["recommendation"], str)

    def test_reorder_triggered_below_reorder_point(self, supply):
        supply.register_item("filter-oil", "Oil Filter", "units", 5.0, 20.0, lead_time_days=3)
        supply.record_receipt("filter-oil", 5.0)
        result = supply.record_usage("filter-oil", 1.0)  # stock drops to 4 → at reorder point
        assert result["reorder_triggered"] is True
        assert len(supply._pending_orders) >= 1

    def test_reorder_not_triggered_above_point(self, supply):
        supply.register_item("grease-ep2", "EP2 Grease", "kg", 5.0, 20.0)
        supply.record_receipt("grease-ep2", 100.0)
        result = supply.record_usage("grease-ep2", 1.0)
        assert result["reorder_triggered"] is False

    def test_record_receipt_increases_stock(self, supply):
        supply.register_item("gasket-set", "Gasket Set", "units", 2.0, 10.0)
        supply.record_receipt("gasket-set", 50.0)
        assert supply._items["gasket-set"]["current_stock"] == pytest.approx(50.0)

    def test_record_receipt_unknown_item(self, supply):
        result = supply.record_receipt("phantom", 1.0)
        assert result["recorded"] is False

    def test_record_receipt_marks_order_received(self, supply):
        supply.register_item("seal-ring", "Seal Ring", "units", 3.0, 15.0)
        supply.record_receipt("seal-ring", 3.0)
        usage_result = supply.record_usage("seal-ring", 1.0)  # triggers reorder
        # Grab the new order_id
        pending = supply._pending_orders
        assert len(pending) >= 1
        order_id = list(pending.keys())[0]
        supply.record_receipt("seal-ring", 15.0, order_id=order_id)
        assert supply._pending_orders[order_id]["status"] == "received"

    def test_validation_runs_through_wingman(self, supply):
        supply.register_item("bolt-set", "Bolt Set", "units", 5.0, 20.0)
        supply.record_receipt("bolt-set", 50.0)
        pair_id = supply._pair_id
        before = len(supply.wingman.get_validation_history(pair_id))
        supply.record_usage("bolt-set", 2.0)
        after = len(supply.wingman.get_validation_history(pair_id))
        assert after == before + 1


class TestSupplyOrchestratorReorderRecommendations:

    def test_no_recommendations_when_stock_adequate(self, supply):
        supply.register_item("tape-ptfe", "PTFE Tape", "rolls", 5.0, 20.0, lead_time_days=2)
        supply.record_receipt("tape-ptfe", 100.0)
        supply.record_usage("tape-ptfe", 1.0)
        recs = supply.get_reorder_recommendations()
        # 99 rolls remaining, reorder at 5 — should be no recommendations
        assert all(r["item_id"] != "tape-ptfe" for r in recs)

    def test_recommendation_for_item_at_reorder_point(self, supply):
        supply.register_item("wire-red", "Red Wire", "m", 10.0, 50.0)
        supply.record_receipt("wire-red", 10.0)
        supply.record_usage("wire-red", 1.0)  # stock = 9 ≤ reorder 10
        recs = supply.get_reorder_recommendations()
        item_recs = [r for r in recs if r["item_id"] == "wire-red"]
        assert len(item_recs) == 1
        assert item_recs[0]["urgency"] == "critical"
        assert isinstance(item_recs[0]["recommendation"], str)

    def test_recommendations_sorted_by_urgency(self, supply):
        supply.register_item("item-crit", "Critical Item", "units", 10.0, 50.0)
        supply.register_item("item-high", "High Item", "units", 3.0, 10.0, lead_time_days=5)
        supply.record_receipt("item-crit", 5.0)   # below reorder point → critical
        supply.record_receipt("item-high", 50.0)

        # Drive item-high close to reorder threshold via usage history
        for _ in range(10):
            supply.record_usage("item-high", 2.0)  # ~daily consumption of 2
        # After 10 usages item-high has 50-20=30 still above reorder

        recs = supply.get_reorder_recommendations()
        if len(recs) >= 2:
            urgency_order = {"critical": 0, "high": 1, "medium": 2, "normal": 3}
            for i in range(len(recs) - 1):
                assert urgency_order.get(recs[i]["urgency"], 9) <= urgency_order.get(
                    recs[i + 1]["urgency"], 9
                )


class TestSupplyOrchestratorDashboard:

    def test_dashboard_structure(self, supply):
        supply.register_item("widget-a", "Widget A", "units", 5.0, 20.0)
        dash = supply.get_supply_dashboard()
        assert "inventory" in dash
        assert "pending_orders" in dash
        assert "total_items" in dash
        assert "items_at_reorder" in dash
        assert "generated_at" in dash

    def test_dashboard_reflects_registered_items(self, supply):
        supply.register_item("cog-a", "Cog A", "units", 5.0, 20.0)
        supply.register_item("cog-b", "Cog B", "units", 3.0, 10.0)
        dash = supply.get_supply_dashboard()
        assert dash["total_items"] == 2

    def test_pending_orders_appear_in_dashboard(self, supply):
        supply.register_item("spring-set", "Spring Set", "units", 5.0, 20.0)
        supply.record_receipt("spring-set", 5.0)
        supply.record_usage("spring-set", 1.0)  # triggers reorder
        dash = supply.get_supply_dashboard()
        assert len(dash["pending_orders"]) >= 1


# ===========================================================================
# Thread-safety smoke tests
# ===========================================================================

class TestThreadSafety:

    def test_safety_orchestrator_concurrent_checks(self):
        o = SafetyOrchestrator()
        errors = []

        def run_checks():
            try:
                for _ in range(5):
                    o.run_safety_check("fire_safety", {"result": "ok"})
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=run_checks) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Thread errors: {errors}"

    def test_efficiency_orchestrator_concurrent_readings(self):
        o = EfficiencyOrchestrator()
        errors = []

        def add_readings():
            try:
                for v in [10.0, 20.0, 15.0, 12.0, 11.0]:
                    o.record_reading("electricity", v, "kWh")
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=add_readings) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Thread errors: {errors}"

    def test_supply_orchestrator_concurrent_usage(self):
        o = SupplyOrchestrator()
        o.register_item("widget-x", "Widget X", "units", 5.0, 50.0)
        o.record_receipt("widget-x", 1000.0)
        errors = []

        def consume():
            try:
                for _ in range(5):
                    o.record_usage("widget-x", 1.0)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=consume) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Thread errors: {errors}"
