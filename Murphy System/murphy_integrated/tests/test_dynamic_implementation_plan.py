import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
    candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
    if not candidates:
        raise RuntimeError("Unable to locate Murphy runtime module")
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


class DummyOrchestrator:
    async def phase1_generative_setup(self):
        return {}

    async def phase2_production_execution(self):
        return {}


def test_dynamic_implementation_plan_requires_requirements():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.gates = [{"status": "blocked"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Test request", {}, {})
    trigger_plan = {"status": "unavailable"}
    org_chart_plan = {"coverage_summary": {"status": "partial"}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Test request",
        [],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        trigger_plan
    )

    assert plan["status"] == "needs_info"
    assert plan["execution_strategy"] == "simulation"
    stages = {stage["id"]: stage for stage in plan["stages"]}
    assert stages["requirements_identification"]["status"] == "needs_info"
    assert stages["gate_alignment"]["status"] == "blocked"
    assert stages["gate_sequencing"]["status"] == "blocked"
    assert stages["compliance_review"]["status"] == "blocked"
    assert stages["swarm_generation"]["status"] == "needs_wiring"
    assert stages["integration_wiring"]["status"] == "needs_wiring"
    assert stages["automation_loop"]["status"] == "needs_info"
    assert stages["multi_loop_schedule"]["status"] == "needs_info"
    assert stages["trigger_schedule"]["status"] == "needs_wiring"
    assert stages["monitoring_feedback"]["status"] == "ready"
    assert stages["output_delivery"]["status"] == "needs_info"
    assert stages["rollback_plan"]["status"] == "needs_wiring"
    assert plan["chain_plan"]["mode"] == "adaptive"
    assert "requirements_identification" in plan["chain_plan"]["control_points"]
    wiring_ids = {gap["id"] for gap in plan["wiring_gaps"]}
    assert {"execution_plan", "swarm_generation", "integration_wiring", "trigger_schedule", "rollback_plan"}.issubset(
        wiring_ids
    )
    info_ids = {gap["id"] for gap in plan["information_gaps"]}
    assert {"requirements_identification", "output_delivery"}.issubset(info_ids)


def test_dynamic_implementation_plan_ready_with_orchestrator():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.orchestrator = DummyOrchestrator()
    murphy.flow_steps = []
    murphy.swarm_system = object()
    murphy.integration_engine = object()
    doc = runtime.LivingDocument("doc-2", "Test", "content", "request")
    doc.gates = [{"status": "open"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {}}, {})
    trigger_plan = {"status": "scheduled"}
    org_chart_plan = {"coverage_summary": {"total_deliverables": 100, "uncovered_deliverables": 0}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Automation",
        [{"id": "compute_plane"}],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        trigger_plan
    )

    assert plan["execution_strategy"] == "orchestrator"
    assert plan["status"] == "ready"
    stage_map = {stage["id"]: stage for stage in plan["stages"]}
    assert stage_map["gate_alignment"]["status"] == "ready"
    assert stage_map["gate_sequencing"]["status"] == "ready"
    assert stage_map["compliance_review"]["status"] == "ready"
    assert stage_map["swarm_generation"]["status"] == "ready"
    assert stage_map["integration_wiring"]["status"] == "ready"
    assert stage_map["automation_loop"]["status"] == "ready"
    assert stage_map["multi_loop_schedule"]["status"] == "ready"
    assert stage_map["trigger_schedule"]["status"] == "ready"
    assert stage_map["monitoring_feedback"]["status"] == "ready"
    assert stage_map["output_delivery"]["status"] == "ready"
    assert stage_map["rollback_plan"]["status"] == "ready"
    assert plan["chain_plan"]["mode"] == "adaptive"
    assert plan["wiring_gaps"] == []
    assert plan["information_gaps"] == []
