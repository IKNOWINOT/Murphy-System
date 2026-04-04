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


def test_activation_preview_includes_execution_wiring():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.gate_synthesis_gates = [{"id": "gate-1", "category": "compliance"}]
    doc.generated_tasks = [{"task_id": "task-1", "stage": "automation_design", "description": "Design flow"}]

    preview = murphy._build_activation_preview(doc, "Test request", {})

    wiring = preview["execution_wiring"]
    assert wiring["gate_synthesis"]["total_gates"] == 1
    assert wiring["gate_synthesis"]["status"] == "ready"
    assert wiring["swarm_tasks"]["total_tasks"] == 1
    assert wiring["swarm_tasks"]["status"] == "ready"
    assert "swarm_system" in wiring
    assert "execution_ready" in wiring
