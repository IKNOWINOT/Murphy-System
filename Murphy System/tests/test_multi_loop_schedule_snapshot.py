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


def _build_ready_plan(runtime_module, murphy, iterations_override=None):
    murphy.orchestrator = DummyOrchestrator()
    murphy.flow_steps = []
    murphy.swarm_system = object()
    murphy.integration_engine = object()
    doc = runtime_module.LivingDocument("doc-ml", "Test", "content", "request")
    doc.confidence = 0.95
    doc.gates = [{"status": "open"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {}}, {})
    if iterations_override is not None:
        learning_loop["iterations"] = iterations_override
    trigger_plan = {"status": "scheduled"}
    org_chart_plan = {"coverage_summary": {"total_deliverables": 100, "uncovered_deliverables": 0}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(
        doc,
        org_chart_plan,
        learning_loop,
        sensor_plan,
        []
    )
    return murphy._build_dynamic_implementation_plan(
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


def test_multi_loop_schedule_ready_when_iterations_multiple():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    plan = _build_ready_plan(runtime, murphy)
    stage_map = {stage["id"]: stage for stage in plan["stages"]}

    assert stage_map["multi_loop_schedule"]["status"] == "ready"
    assert "Define multi-loop scheduling" not in " ".join(plan["next_actions"])


def test_multi_loop_schedule_pending_with_single_iteration():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    base_plan = _build_ready_plan(runtime, murphy)
    iterations_override = base_plan["loop_iterations"][:1]
    plan = _build_ready_plan(runtime, murphy, iterations_override=iterations_override)
    stage_map = {stage["id"]: stage for stage in plan["stages"]}

    assert stage_map["multi_loop_schedule"]["status"] == "pending"
    assert "Define multi-loop scheduling" in " ".join(plan["next_actions"])
