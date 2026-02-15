import asyncio
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


class StubTwoPhaseOrchestrator:
    def __init__(self):
        self.calls = []

    # TwoPhaseOrchestrator.create_automation(request: str, domain: str)
    def create_automation(self, request: str, domain: str) -> str:
        self.calls.append(("create", request, domain))
        return "automation-123"

    def run_automation(self, automation_id: str):
        self.calls.append(("run", automation_id))
        return {
            "automation_id": automation_id,
            "deliverables": ["report.pdf"],
            "status": "success"
        }


def test_execute_task_uses_two_phase_orchestrator():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    stub = StubTwoPhaseOrchestrator()
    murphy.orchestrator = stub

    response = asyncio.run(
        murphy.execute_task(
            "Generate a compliance report",
            "automation",
            {"enforce_policy": False, "domain": "compliance"}
        )
    )

    assert response["success"] is True
    assert response["automation_id"] == "automation-123"
    assert response["deliverables"] == ["report.pdf"]
    assert response["metadata"]["mode"] == "two_phase_orchestrator"
    assert ("create", "Generate a compliance report", "compliance") in stub.calls
    assert ("run", "automation-123") in stub.calls
