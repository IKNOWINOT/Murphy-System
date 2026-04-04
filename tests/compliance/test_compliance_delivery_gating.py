import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent.parent
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


def test_compliance_gate_blocks_delivery_release():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.flow_steps = []
    murphy.swarm_system = object()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.confidence = 0.9
    doc.gates = [{"name": "Compliance Gate", "status": "blocked"}]
    doc.generated_tasks = [{"stage": "automation_design", "description": "Design automation"}]
    operations_plan = murphy._build_operations_plan(doc)
    learning_loop = murphy._build_learning_loop_plan("Compliance task", {"answers": {}}, {})
    org_chart_plan = {"coverage_summary": {"total_deliverables": 1, "uncovered_deliverables": 0}}
    sensor_plan = {"region": "global", "primary_regulatory_source": {"id": "regulatory_source"}}
    delivery_readiness = murphy._build_delivery_readiness(doc, org_chart_plan, learning_loop, sensor_plan, [])

    plan = murphy._build_dynamic_implementation_plan(
        doc,
        "Compliance task",
        [],
        learning_loop,
        operations_plan,
        delivery_readiness,
        [],
        sensor_plan,
        org_chart_plan,
        {"status": "scheduled"}
    )

    stage_map = {stage["id"]: stage for stage in plan["stages"]}
    assert stage_map["compliance_review"]["status"] == "blocked"
    assert stage_map["output_delivery"]["status"] == "needs_compliance"
