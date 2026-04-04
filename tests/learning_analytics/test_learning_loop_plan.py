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


def test_learning_loop_plan_needs_info_when_answers_missing():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    plan = murphy._build_learning_loop_plan(
        "Automate onboarding for compliance",
        onboarding_context=None,
        librarian_context={"recommended_conditions": []}
    )

    assert plan["status"] == "needs_info"
    assert plan["requirements_identification"]["missing_count"] > 0
    assert plan["iterations"][0]["status"] == "pending_setup"


def test_learning_loop_plan_ready_with_answers_and_swarm():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.swarm_system = object()
    answers = {step["stage"]: "confirmed" for step in murphy.flow_steps}

    plan = murphy._build_learning_loop_plan(
        "Automate onboarding for compliance",
        onboarding_context={"answers": answers},
        librarian_context={"recommended_conditions": [{"id": "policy"}]}
    )

    assert plan["status"] == "ready"
    assert plan["requirements_identification"]["missing_count"] == 0
    assert any(target["id"] == "document" for target in plan["output_targets"])
