"""Tests for Murphy System self-operation status reporting."""

import importlib.util
from pathlib import Path


def load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_self_operation_status_fields():
    runtime = load_runtime_module()
    system = runtime.MurphySystem()

    if system.integration_engine is None:
        class IntegrationEngineStub:
            @staticmethod
            def list_pending_integrations():
                return []

            @staticmethod
            def list_committed_integrations():
                return []

        system.integration_engine = IntegrationEngineStub()

    status = system.get_system_status()
    assert "self_operation" in status

    self_operation = status["self_operation"]
    assert isinstance(self_operation["enabled"], bool)
    assert isinstance(self_operation["can_work_on_self"], bool)
    assert self_operation["activation_required"] is True
    assert self_operation["state"] in {"active", "unavailable"}
