"""Tests for executive_planning_engine module."""

import threading
import time

import pytest

from src.executive_planning_engine import (
    BindingStatus,
    BusinessGateGenerator,
    ExecutiveDashboardGenerator,
    ExecutivePlanningEngine,
    ExecutiveStrategyPlanner,
    GateStatus,
    GateType,
    InitiativeStatus,
    IntegrationAutomationBinder,
    ObjectiveCategory,
    ObjectiveStatus,
    ResponseEngine,
    WorkflowNodeStatus,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def planner():
    return ExecutiveStrategyPlanner()


@pytest.fixture
def gate_gen():
    return BusinessGateGenerator()


@pytest.fixture
def binder():
    return IntegrationAutomationBinder()


@pytest.fixture
def engine():
    return ExecutivePlanningEngine()


def _make_objective(planner, category="revenue_target"):
    return planner.create_objective(
        name="Increase Q4 Revenue",
        category=category,
        target_metric="revenue >= 10M",
        deadline="2025-12-31",
        priority=1,
    )


# ------------------------------------------------------------------
# ExecutiveStrategyPlanner tests
# ------------------------------------------------------------------

class TestExecutiveStrategyPlanner:

    def test_create_objective_returns_dict(self, planner):
        obj = _make_objective(planner)
        assert isinstance(obj, dict)
        assert obj["name"] == "Increase Q4 Revenue"
        assert obj["category"] == "revenue_target"
        assert obj["priority"] == 1
        assert obj["status"] == ObjectiveStatus.DRAFT.value

    def test_create_objective_generates_unique_id(self, planner):
        o1 = _make_objective(planner)
        o2 = _make_objective(planner)
        assert o1["objective_id"] != o2["objective_id"]

    def test_create_objective_clamps_priority(self, planner):
        obj = planner.create_objective("X", "cost_reduction", "m", "2025-01-01", priority=99)
        assert obj["priority"] == 5

    def test_create_objective_clamps_priority_low(self, planner):
        obj = planner.create_objective("X", "cost_reduction", "m", "2025-01-01", priority=-1)
        assert obj["priority"] == 1

    def test_get_objective(self, planner):
        obj = _make_objective(planner)
        fetched = planner.get_objective(obj["objective_id"])
        assert fetched is not None
        assert fetched["objective_id"] == obj["objective_id"]

    def test_get_objective_not_found(self, planner):
        assert planner.get_objective("nonexistent") is None

    def test_activate_objective(self, planner):
        obj = _make_objective(planner)
        result = planner.activate_objective(obj["objective_id"])
        assert result["status"] == ObjectiveStatus.ACTIVE.value

    def test_activate_objective_not_found(self, planner):
        result = planner.activate_objective("nope")
        assert "error" in result

    def test_list_objectives(self, planner):
        _make_objective(planner)
        _make_objective(planner)
        assert len(planner.list_objectives()) == 2

    def test_decompose_into_initiatives(self, planner):
        obj = _make_objective(planner)
        initiatives = planner.decompose_into_initiatives(obj["objective_id"])
        assert len(initiatives) >= 2
        for init in initiatives:
            assert init["objective_id"] == obj["objective_id"]
            assert init["status"] == InitiativeStatus.PROPOSED.value

    def test_decompose_updates_objective_initiatives(self, planner):
        obj = _make_objective(planner)
        initiatives = planner.decompose_into_initiatives(obj["objective_id"])
        updated = planner.get_objective(obj["objective_id"])
        assert len(updated["initiatives"]) == len(initiatives)

    def test_decompose_nonexistent_objective(self, planner):
        result = planner.decompose_into_initiatives("bad-id")
        assert result == []

    def test_rank_initiatives_default_criteria(self, planner):
        obj = _make_objective(planner)
        planner.decompose_into_initiatives(obj["objective_id"])
        ranked = planner.rank_initiatives()
        assert len(ranked) >= 2
        scores = [r["composite_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_initiatives_custom_criteria(self, planner):
        obj = _make_objective(planner)
        planner.decompose_into_initiatives(obj["objective_id"])
        ranked = planner.rank_initiatives(criteria={"roi": 1.0, "urgency": 0, "risk": 0, "feasibility": 0})
        assert all("composite_score" in r for r in ranked)

    def test_all_categories_decompose(self, planner):
        for cat in ObjectiveCategory:
            obj = planner.create_objective("T", cat.value, "m", "2025-01-01")
            inits = planner.decompose_into_initiatives(obj["objective_id"])
            assert len(inits) >= 2, f"No initiatives for {cat}"


# ------------------------------------------------------------------
# BusinessGateGenerator tests
# ------------------------------------------------------------------

class TestBusinessGateGenerator:

    def test_generate_gates_for_revenue(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target")
        assert len(gates) >= 3
        types = {g["gate_type"] for g in gates}
        assert GateType.BUDGET_GATE.value in types
        assert GateType.ROI_GATE.value in types

    def test_generate_gates_custom_thresholds(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective(
            "obj-1", "revenue_target",
            budget_threshold=50000, roi_threshold=3.0,
        )
        budget_gates = [g for g in gates if g["gate_type"] == GateType.BUDGET_GATE.value]
        assert budget_gates[0]["threshold"] == 50000

    def test_gate_has_required_fields(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "compliance_mandate")
        for g in gates:
            assert "gate_id" in g
            assert "gate_type" in g
            assert "condition" in g
            assert "threshold" in g
            assert "approvers" in g
            assert "status" in g

    def test_evaluate_gate_budget_pass(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target", budget_threshold=100000)
        budget = next(g for g in gates if g["gate_type"] == GateType.BUDGET_GATE.value)
        result = gate_gen.evaluate_gate(budget["gate_id"], 50000)
        assert result["status"] == GateStatus.PASSED.value
        assert result["evaluation_result"]["passed"] is True

    def test_evaluate_gate_budget_fail(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target", budget_threshold=100000)
        budget = next(g for g in gates if g["gate_type"] == GateType.BUDGET_GATE.value)
        result = gate_gen.evaluate_gate(budget["gate_id"], 200000)
        assert result["status"] == GateStatus.FAILED.value

    def test_evaluate_gate_roi_pass(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target")
        roi = next(g for g in gates if g["gate_type"] == GateType.ROI_GATE.value)
        result = gate_gen.evaluate_gate(roi["gate_id"], 5.0)
        assert result["evaluation_result"]["passed"] is True

    def test_evaluate_gate_roi_fail(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target")
        roi = next(g for g in gates if g["gate_type"] == GateType.ROI_GATE.value)
        result = gate_gen.evaluate_gate(roi["gate_id"], 0.5)
        assert result["evaluation_result"]["passed"] is False

    def test_evaluate_gate_not_found(self, gate_gen):
        result = gate_gen.evaluate_gate("no-gate", 1.0)
        assert "error" in result

    def test_get_gate(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "cost_reduction")
        fetched = gate_gen.get_gate(gates[0]["gate_id"])
        assert fetched is not None

    def test_get_gates_for_objective(self, gate_gen):
        gate_gen.generate_gates_for_objective("obj-A", "revenue_target")
        gate_gen.generate_gates_for_objective("obj-B", "cost_reduction")
        a_gates = gate_gen.get_gates_for_objective("obj-A")
        assert all(g["objective_id"] == "obj-A" for g in a_gates)

    def test_update_gate_status(self, gate_gen):
        gates = gate_gen.generate_gates_for_objective("obj-1", "revenue_target")
        result = gate_gen.update_gate_status(gates[0]["gate_id"], "waived")
        assert result["status"] == GateStatus.WAIVED.value

    def test_all_categories_generate_gates(self, gate_gen):
        for cat in ObjectiveCategory:
            gates = gate_gen.generate_gates_for_objective(f"obj-{cat.value}", cat.value)
            assert len(gates) >= 3, f"Too few gates for {cat}"


# ------------------------------------------------------------------
# IntegrationAutomationBinder tests
# ------------------------------------------------------------------

class TestIntegrationAutomationBinder:

    def test_discover_integrations(self, binder):
        intgs = binder.discover_integrations_for_objective("obj-1", "revenue_target")
        assert len(intgs) >= 2
        assert all(i["recommended"] for i in intgs)

    def test_discover_integrations_includes_custom(self, binder):
        binder.register_integration({
            "integration_id": "custom_crm",
            "name": "Custom CRM",
            "capability": "sales",
            "category": "revenue_target",
        })
        intgs = binder.discover_integrations_for_objective("obj-1", "revenue_target")
        ids = [i["integration_id"] for i in intgs]
        assert "custom_crm" in ids

    def test_bind_integration(self, binder):
        binding = binder.bind_integration_to_workflow(
            "crm_connector", "wf-1", {"step": "fetch_leads"}
        )
        assert binding["status"] == BindingStatus.BOUND.value
        assert binding["integration_id"] == "crm_connector"

    def test_activate_binding(self, binder):
        binding = binder.bind_integration_to_workflow("x", "wf-1", {})
        result = binder.activate_binding(binding["binding_id"])
        assert result["status"] == BindingStatus.ACTIVE.value

    def test_activate_binding_not_found(self, binder):
        result = binder.activate_binding("nope")
        assert "error" in result

    def test_list_bindings_for_workflow(self, binder):
        binder.bind_integration_to_workflow("a", "wf-1", {})
        binder.bind_integration_to_workflow("b", "wf-1", {})
        binder.bind_integration_to_workflow("c", "wf-2", {})
        assert len(binder.list_bindings_for_workflow("wf-1")) == 2

    def test_generate_automation_workflow(self, binder):
        wf = binder.generate_automation_workflow("obj-1", "revenue_target")
        assert "workflow_id" in wf
        assert wf["node_count"] >= 3  # start + integrations + end
        assert wf["status"] == "generated"
        assert len(wf["edges"]) >= 2

    def test_generate_workflow_with_gates(self, binder):
        gates = [
            {"gate_id": "g1", "gate_type": "budget_gate", "condition": "budget_ok"},
            {"gate_id": "g2", "gate_type": "roi_gate", "condition": "roi_ok"},
        ]
        wf = binder.generate_automation_workflow("obj-1", "revenue_target", gates=gates)
        assert wf["gate_count"] == 2
        gate_nodes = [n for n in wf["nodes"] if n["type"] == "gate_check"]
        assert len(gate_nodes) == 2

    def test_workflow_creates_bindings(self, binder):
        wf = binder.generate_automation_workflow("obj-1", "cost_reduction")
        bindings = binder.list_bindings_for_workflow(wf["workflow_id"])
        assert len(bindings) >= 2

    def test_all_categories_discover(self, binder):
        for cat in ObjectiveCategory:
            intgs = binder.discover_integrations_for_objective("obj", cat.value)
            assert len(intgs) >= 2, f"Too few integrations for {cat}"


# ------------------------------------------------------------------
# ExecutiveDashboardGenerator tests
# ------------------------------------------------------------------

class TestExecutiveDashboardGenerator:

    def test_objective_progress_report(self, engine):
        obj = _make_objective(engine.planner)
        oid = obj["objective_id"]
        gates = engine.gate_generator.generate_gates_for_objective(oid, obj["category"])
        engine.gate_generator.evaluate_gate(gates[0]["gate_id"], 0)  # pass budget

        report = engine.dashboard.objective_progress_report(oid)
        assert report["objective_id"] == oid
        assert report["gates_total"] == len(gates)
        assert report["gates_passed"] >= 1

    def test_objective_progress_not_found(self, engine):
        result = engine.dashboard.objective_progress_report("bad-id")
        assert "error" in result

    def test_portfolio_summary(self, engine):
        _make_objective(engine.planner, "revenue_target")
        _make_objective(engine.planner, "cost_reduction")
        summary = engine.dashboard.portfolio_summary()
        assert summary["total_objectives"] == 2
        assert len(summary["objectives"]) == 2

    def test_gate_compliance_matrix(self, engine):
        obj = _make_objective(engine.planner)
        engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        matrix = engine.dashboard.gate_compliance_matrix()
        assert matrix["counts"]["total"] >= 3
        assert "matrix" in matrix

    def test_integration_utilization_report(self, engine):
        obj = _make_objective(engine.planner)
        engine.binder.generate_automation_workflow(obj["objective_id"], obj["category"])
        report = engine.dashboard.integration_utilization_report()
        assert report["total_integrations"] >= 1


# ------------------------------------------------------------------
# ResponseEngine tests
# ------------------------------------------------------------------

class TestResponseEngine:

    def test_generate_response_passed(self, engine):
        obj = _make_objective(engine.planner)
        gates = engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        resp = engine.response_engine.generate_response(gates[0]["gate_id"], "passed")
        assert resp["outcome"] == "passed"
        assert resp["severity"] == "info"
        assert "next_steps" in resp

    def test_generate_response_failed(self, engine):
        obj = _make_objective(engine.planner)
        gates = engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        resp = engine.response_engine.generate_response(gates[0]["gate_id"], "failed")
        assert resp["outcome"] == "failed"
        assert resp["severity"] == "warning"

    def test_generate_response_not_found(self, engine):
        result = engine.response_engine.generate_response("bad", "passed")
        assert "error" in result

    def test_escalation_handler(self, engine):
        obj = _make_objective(engine.planner)
        gates = engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        brief = engine.response_engine.escalation_handler(gates[0]["gate_id"])
        assert "escalation_id" in brief
        assert "stakeholders" in brief
        assert len(brief["stakeholders"]) >= 1
        assert "recommended_actions" in brief

    def test_escalation_handler_not_found(self, engine):
        result = engine.response_engine.escalation_handler("bad")
        assert "error" in result

    def test_escalation_compliance_adds_legal(self, engine):
        obj = engine.planner.create_objective("C", "compliance_mandate", "m", "2025-01-01")
        gates = engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        brief = engine.response_engine.escalation_handler(gates[0]["gate_id"])
        assert "legal_counsel" in brief["stakeholders"]

    def test_recommend_course_correction_no_failures(self, engine):
        obj = _make_objective(engine.planner)
        engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        rec = engine.response_engine.recommend_course_correction(obj["objective_id"])
        assert rec["overall_health"] == "healthy"
        assert rec["failing_gates"] == 0

    def test_recommend_course_correction_with_failures(self, engine):
        obj = _make_objective(engine.planner)
        gates = engine.gate_generator.generate_gates_for_objective(
            obj["objective_id"], obj["category"], budget_threshold=100
        )
        # Fail budget gate
        budget = next(g for g in gates if g["gate_type"] == GateType.BUDGET_GATE.value)
        engine.gate_generator.evaluate_gate(budget["gate_id"], 999999)

        rec = engine.response_engine.recommend_course_correction(obj["objective_id"])
        assert rec["failing_gates"] >= 1
        assert rec["overall_health"] in ("at_risk", "critical")
        assert len(rec["recommendations"]) >= 1

    def test_recommend_not_found(self, engine):
        result = engine.response_engine.recommend_course_correction("bad")
        assert "error" in result

    def test_list_responses(self, engine):
        obj = _make_objective(engine.planner)
        gates = engine.gate_generator.generate_gates_for_objective(obj["objective_id"], obj["category"])
        engine.response_engine.generate_response(gates[0]["gate_id"], "passed")
        assert len(engine.response_engine.list_responses()) == 1


# ------------------------------------------------------------------
# Thread-safety tests
# ------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_objective_creation(self, planner):
        errors = []

        def create():
            try:
                planner.create_objective("T", "revenue_target", "m", "2025-01-01")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(planner.list_objectives()) == 20

    def test_concurrent_gate_generation(self, gate_gen):
        errors = []

        def gen(i):
            try:
                gate_gen.generate_gates_for_objective(f"obj-{i}", "cost_reduction")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=gen, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(gate_gen.list_gates()) == 20 * 4  # 4 gates per cost_reduction


# ------------------------------------------------------------------
# Facade / Integration tests
# ------------------------------------------------------------------

class TestExecutivePlanningEngine:

    def test_end_to_end_flow(self, engine):
        # 1. Create objective
        obj = engine.planner.create_objective(
            "Reduce OpEx", "cost_reduction", "cost <= 5M", "2025-06-30", 2
        )
        oid = obj["objective_id"]

        # 2. Decompose
        initiatives = engine.planner.decompose_into_initiatives(oid)
        assert len(initiatives) >= 2

        # 3. Generate gates
        gates = engine.gate_generator.generate_gates_for_objective(oid, obj["category"])
        assert len(gates) >= 3

        # 4. Discover integrations
        intgs = engine.binder.discover_integrations_for_objective(oid, obj["category"])
        assert len(intgs) >= 2

        # 5. Generate workflow
        wf = engine.binder.generate_automation_workflow(oid, obj["category"], gates=gates)
        assert wf["gate_count"] == len(gates)

        # 6. Evaluate gates
        budget = next(g for g in gates if g["gate_type"] == GateType.BUDGET_GATE.value)
        engine.gate_generator.evaluate_gate(budget["gate_id"], 50000)

        # 7. Dashboard
        report = engine.dashboard.objective_progress_report(oid)
        assert report["gates_passed"] >= 1

        # 8. Response
        resp = engine.response_engine.generate_response(budget["gate_id"], "passed")
        assert resp["severity"] == "info"

    def test_facade_components_wired(self, engine):
        assert engine.planner is not None
        assert engine.gate_generator is not None
        assert engine.binder is not None
        assert engine.dashboard is not None
        assert engine.response_engine is not None
