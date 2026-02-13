"""Tests for MFGC fallback execution wiring."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


class StubResponse:
    def to_dict(self):
        return {"status": "stubbed", "message": "Processed by stub integrator"}


class StubIntegrator:
    @staticmethod
    def process_user_request(*_args, **_kwargs):
        return StubResponse()


def test_mfgc_adapter_execution_payload(runtime_module):
    if runtime_module.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")
    system = runtime_module.MurphySystem.create_test_instance()
    system.sessions = {}

    system.system_integrator = StubIntegrator()
    system.mfgc_adapter = runtime_module.MFGCAdapter(system.system_integrator)

    payload = system._execute_with_mfgc_adapter("Draft automation workflow", "general", {})
    assert payload is not None
    assert "success" in payload
    assert "total_gates" in payload
    assert payload["total_gates"] >= 0


def test_simulation_uses_mfgc_fallback_when_available(runtime_module):
    if runtime_module.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")
    system = runtime_module.MurphySystem.create_test_instance()
    system.sessions = {}
    system.system_integrator = StubIntegrator()
    system.mfgc_adapter = runtime_module.MFGCAdapter(system.system_integrator)

    result = system._simulate_execution("Run compliance audit", "general", {}, None)
    assert result["metadata"]["mode"] == "mfgc_fallback"
    assert "mfgc_execution" in result
