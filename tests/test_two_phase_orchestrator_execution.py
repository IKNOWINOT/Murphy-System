import asyncio
import importlib.util
from pathlib import Path
from typing import Any, Dict


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

    # TwoPhaseOrchestrator.create_automation(request: str, domain: str) in Murphy System/two_phase_orchestrator.py
    def create_automation(self, request: str, domain: str) -> str:
        self.calls.append(("create", request, domain))
        return "automation-123"

    def run_automation(self, automation_id: str) -> Dict[str, Any]:
        self.calls.append(("run", automation_id))
        return {
            "automation_id": automation_id,
            "deliverables": [{"type": "report", "path": "report.pdf"}],
            "status": "success"
        }


def test_execute_task_routes_to_two_phase_orchestrator():
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
    assert response["session_id"] is not None
    assert response["session_id"] != response["automation_id"]
    assert response["session_id_source"] == "session_id"
    # Deliverables include the original report plus runtime-appended delivery adapters
    assert any(d.get("type") == "report" or d.get("path") == "report.pdf" for d in response["deliverables"])
    assert response["metadata"]["mode"] == "two_phase_orchestrator"
    assert ("create", "Generate a compliance report", "compliance") in stub.calls
    assert ("run", "automation-123") in stub.calls


def test_two_phase_orchestrator_defaults_domain_to_task_type():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    stub = StubTwoPhaseOrchestrator()
    murphy.orchestrator = stub

    response = asyncio.run(
        murphy.execute_task(
            "Draft a response letter",
            "operations",
            {"enforce_policy": False}
        )
    )

    assert response["success"] is True
    assert ("create", "Draft a response letter", "operations") in stub.calls


def test_two_phase_orchestrator_accepts_empty_domain():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    stub = StubTwoPhaseOrchestrator()
    murphy.orchestrator = stub

    response = asyncio.run(
        murphy.execute_task(
            "Run onboarding automation",
            "operations",
            {"enforce_policy": False, "domain": ""}
        )
    )

    assert response["success"] is True
    assert ("create", "Run onboarding automation", "") in stub.calls
