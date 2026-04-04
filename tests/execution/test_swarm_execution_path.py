import asyncio
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


class StubSwarmSystem:
    def execute_full_cycle(self, task_description, context):
        return {
            "phases": ["expand", "gate"],
            "total_artifacts": 2,
            "total_gates": 1,
            "final_confidence": 0.84,
            "avg_murphy_risk": 0.12
        }


def test_execute_task_includes_swarm_execution_summary():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.swarm_system = StubSwarmSystem()

    response = asyncio.run(
        murphy.execute_task(
            "Expand automation tasks into swarms",
            "automation",
            {"run_swarm_execution": True, "enforce_policy": False}
        )
    )

    swarm_execution = response.get("swarm_execution")
    assert swarm_execution is not None
    assert swarm_execution["id"] == "true_swarm_system"
    assert swarm_execution["status"] == "ok"
    assert swarm_execution["total_artifacts"] == 2
    assert swarm_execution["total_gates"] == 1


def test_execute_task_swarm_execution_handles_missing_swarm():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.swarm_system = None

    response = asyncio.run(
        murphy.execute_task(
            "Expand automation tasks into swarms",
            "automation",
            {"run_swarm_execution": True, "enforce_policy": False}
        )
    )

    swarm_execution = response.get("swarm_execution")
    assert swarm_execution is not None
    assert swarm_execution["id"] == "true_swarm_system"
    assert swarm_execution["status"] == "not_initialized"
