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
        org_chart_plan
    )

    assert plan["status"] == "needs_info"
    assert plan["execution_strategy"] == "simulation"
    stages = {stage["id"]: stage for stage in plan["stages"]}
    assert stages["requirements_identification"]["status"] == "needs_info"
    assert stages["gate_alignment"]["status"] == "blocked"


def test_dynamic_implementation_plan_ready_with_orchestrator():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.orchestrator = DummyOrchestrator()
    murphy.flow_steps = []
    doc = runtime.LivingDocument("doc-2", "Test", "content", "request")
    doc.gates = [{"status": "open"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {}}, {})
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
        org_chart_plan
    )

    assert plan["execution_strategy"] == "orchestrator"
    assert plan["status"] == "ready"
