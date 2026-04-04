"""Execution wiring integration tests for execute_task."""

import asyncio
import importlib.util
from collections import deque
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest


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


class StubResponse:
    def to_dict(self):
        return {"status": "stubbed", "message": "Processed by stub integrator"}


class StubIntegrator:
    @staticmethod
    def process_user_request(*_args, **_kwargs):
        return StubResponse()


class StubAsyncOrchestratorSetupFailure:
    async def phase1_generative_setup(self, **_kwargs):
        return {"success": False, "error": "setup unavailable"}

    async def phase2_production_execution(self, **_kwargs):
        return {"success": True}


class StubAsyncOrchestratorExecutionFailure:
    async def phase1_generative_setup(self, **_kwargs):
        return {"success": True, "session_id": "async-session-1", "execution_packet": {"id": "pkt-1"}}

    async def phase2_production_execution(self, **_kwargs):
        return {"success": False, "error": "execution unavailable"}


class StubAsyncOrchestratorInvalidSessionId:
    def __init__(self):
        self.phase2_called = False

    async def phase1_generative_setup(self, **_kwargs):
        # Whitespace-only session IDs must be normalized as invalid.
        return {"success": True, "session_id": "   ", "execution_packet": {"id": "pkt-invalid"}}

    async def phase2_production_execution(self, **_kwargs):
        self.phase2_called = True
        return {"success": True}


def test_execute_task_uses_mfgc_fallback_when_orchestrator_missing():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id="session-1"
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["metadata"]["orchestration_mode"] == "fallback"
    timestamp = datetime.fromisoformat(response["metadata"]["timestamp"])
    assert timestamp.tzinfo is timezone.utc
    assert response["session_id"] == "session-1"
    assert "mfgc_execution" in response
    assert "execution_ready" in response["activation_preview"]["execution_wiring"]


def test_execute_task_preserves_supplied_fallback_session_id_without_autocreate():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id="session-new-fallback"
        )
    )

    assert response["session_id"] == "session-new-fallback"
    assert len(murphy.sessions) == 0


def test_simulate_execution_mfgc_fallback_timestamp_is_timezone_aware_without_adapter():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._execute_with_mfgc_adapter = lambda *_args, **_kwargs: {
        "success": True,
        "execution_time": 0.01,
        "integrator_response": {"status": "ok"},
    }
    murphy.create_session = lambda *args, **kwargs: {"session_id": "session-fallback"}

    response = murphy._simulate_execution(
        "Draft an automation plan",
        "automation",
        {"enforce_policy": False},
        session_id=None,
    )

    timestamp = datetime.fromisoformat(response["metadata"]["timestamp"])
    assert timestamp.tzinfo is timezone.utc
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["metadata"]["orchestration_mode"] == "fallback"
    assert response["session_id"] == "session-fallback"


def test_execute_task_registers_valid_create_session_id_in_fallback():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": "external-fallback-session"}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert response["session_id"] == "external-fallback-session"
    assert murphy.sessions["external-fallback-session"]["source"] == "orchestrator_session_autocreate"
    created_at = datetime.fromisoformat(murphy.sessions["external-fallback-session"]["created_at"])
    assert created_at.tzinfo is timezone.utc


def test_execute_task_fallback_handles_missing_create_session_payload():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_handles_invalid_create_session_payload_type():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: "session-invalid-payload"

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_from_create_session_payload():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"id": "session-from-id-key"}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-key"
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_when_session_id_is_invalid():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {
        "session_id": "   ",
        "id": "session-from-id-fallback"
    }

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-fallback"
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_when_session_id_is_mapping():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {
        "session_id": MappingProxyType({"invalid": "session-id"}),
        "id": "session-from-id-mapping-fallback",
    }

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-mapping-fallback"
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_when_session_id_is_deque():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {
        "session_id": deque(["invalid"]),
        "id": "session-from-id-deque-fallback",
    }

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-deque-fallback"
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_when_session_id_access_raises():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    class _SessionPayload(dict):
        def get(self, key, default=None):
            if key == "session_id":
                raise RuntimeError("session_id access failed")
            return super().get(key, default)

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: _SessionPayload({"id": "session-from-id-access-fallback"})

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-access-fallback"
    assert "mfgc_execution" in response


def test_execute_task_fallback_uses_id_key_when_payload_get_access_raises():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    class _SessionPayload(dict):
        def get(self, key, default=None):
            raise RuntimeError(f"{key} access failed")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: _SessionPayload({"id": "session-from-id-get-access-fallback"})

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "session-from-id-get-access-fallback"
    assert "mfgc_execution" in response


def test_execute_task_fallback_accepts_mapping_create_session_payload():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: MappingProxyType({"session_id": "mapped-session-id"})

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "mapped-session-id"
    assert "mfgc_execution" in response


def test_execute_task_fallback_calls_create_session_only_once_when_payload_missing():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    call_count = {"count": 0}

    def _create_session_missing_payload():
        call_count["count"] += 1
        return None

    murphy.create_session = _create_session_missing_payload

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert call_count["count"] == 1


def test_execute_task_fallback_normalizes_whitespace_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": "   "}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_preserves_zero_like_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": 0}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "0"
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_non_finite_numeric_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": float("nan")}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_non_finite_decimal_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": Decimal("NaN")}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    # Decimal NaN is coerced to string "NaN" by the runtime
    assert response["session_id"] == "NaN"
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_container_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": ["session-invalid-container"]}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_normalizes_frozenset_session_id_from_create_session_to_none():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": frozenset([1, 2])}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_container_input_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": "fallback-session-id"}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id={"invalid": "session-container"}
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] == "fallback-session-id"
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_bytes_create_session_payload_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": b"session-bytes"}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_rejects_complex_create_session_payload_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda *args, **kwargs: {"session_id": 1 + 2j}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_handles_create_session_exception():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    def _raise_create_session(*_args, **_kwargs):
        raise RuntimeError("session creation unavailable")

    murphy.create_session = _raise_create_session

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_fallback_handles_unstringifiable_create_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    class _UnstringifiableSessionId:
        def __str__(self):
            raise RuntimeError("cannot stringify session id")

    murphy.create_session = lambda *args, **kwargs: {"session_id": _UnstringifiableSessionId()}

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": False},
            session_id=None
        )
    )

    assert isinstance(response["success"], bool)
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["session_id"] is None
    assert "mfgc_execution" in response


def test_execute_task_blocks_when_orchestrator_missing_and_policy_enforced():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": True},
            session_id="session-1"
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-1"
    assert "mfgc_execution" not in response
    assert "error" in response
    assert "reason" in response
    assert response["error"] == response["reason"]
    assert response["metadata"]["task_description"] == "Draft an automation plan"
    assert response["metadata"]["task_type"] == "automation"
    timestamp = datetime.fromisoformat(response["metadata"]["timestamp"])
    assert timestamp <= datetime.now(timezone.utc) + timedelta(seconds=1)


def test_execute_task_does_not_block_when_enforce_policy_string_false():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": "false"},
            session_id="session-1"
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["metadata"]["orchestration_mode"] == "fallback"


def test_execute_task_does_not_block_when_enforce_policy_bytes_false():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": b"false"},
            session_id="session-1"
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["mode"] == "mfgc_fallback"
    assert response["metadata"]["orchestration_mode"] == "fallback"


def test_execute_task_blocks_when_require_orchestrator_online_string_true():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-string-true"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online string-true requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": "true"},
            session_id="session-online-string-true",
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-online-string-true"
    assert "orchestration-online execution is required" in response["reason"]


def test_execute_task_does_not_block_when_require_orchestrator_online_string_false():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-string-false"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online string-false requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": "false"},
            session_id="session-online-string-false",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_does_not_block_when_require_orchestrator_online_string_invalid():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-string-invalid"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online string-invalid requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": "definitely-maybe"},
            session_id="session-online-string-invalid",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_does_not_block_when_require_orchestrator_online_container():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-container"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online container requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": {"enabled": False}},
            session_id="session-online-container",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_does_not_block_when_require_orchestrator_online_non_finite_numeric():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-non-finite"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online non-finite requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": float("nan")},
            session_id="session-online-non-finite",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_does_not_block_when_require_orchestrator_online_complex_numeric():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-complex"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online complex requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": complex(1, 0)},
            session_id="session-online-complex",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_non_finite_decimal_policy_flag():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-nan-decimal"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online non-finite decimal requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": Decimal("NaN")},
            session_id="session-online-non-finite-decimal",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_infinite_decimal_policy_flag():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-positive-infinity-decimal"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online infinite decimal requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": Decimal("Infinity")},
            session_id="session-online-infinite-decimal",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_overflowing_decimal_policy_flag():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-overflow-decimal"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online overflowing decimal requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": Decimal("1e10000000")},
            session_id="session-online-overflow-decimal",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_uncoercible_policy_flag_object():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-uncoercible-policy-flag"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    class _UncoercibleFlag:
        def __bool__(self):
            raise TypeError("bool coercion failed")

    response = asyncio.run(
        murphy.execute_task(
            "Execute with uncoercible policy-flag object",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": _UncoercibleFlag()},
            session_id="session-online-uncoercible-flag",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_runtimeerror_policy_flag_object():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-runtimeerror-policy-flag"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    class _RuntimeErrorFlag:
        def __bool__(self):
            raise RuntimeError("runtime bool coercion failed")

    response = asyncio.run(
        murphy.execute_task(
            "Execute with runtime-error policy-flag object",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": _RuntimeErrorFlag()},
            session_id="session-online-runtimeerror-flag",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_fallback_with_generic_exception_policy_flag_object():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-generic-exception-policy-flag"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    class _GenericExceptionFlag:
        def __bool__(self):
            raise Exception("generic bool coercion failed")

    response = asyncio.run(
        murphy.execute_task(
            "Execute with generic-exception policy-flag object",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": _GenericExceptionFlag()},
            session_id="session-online-generic-exception-flag",
        )
    )

    assert isinstance(response["success"], bool)
    assert response.get("status") != "blocked"
    assert response["metadata"]["orchestration_mode"] in {"fallback", "simulation"}


def test_execute_task_blocks_when_orchestrator_missing_normalizes_whitespace_session_id():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": True},
            session_id="   "
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    # Whitespace session_id is normalized to None; runtime may auto-create a new session
    assert response["session_id"] is None or isinstance(response["session_id"], str)


def test_execute_task_policy_block_includes_reason_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check",
            "automation",
            {"enforce_policy": True},
            session_id="session-policy",
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["error"] == response["reason"]
    assert response["metadata"]["mode"] == "blocked"
    assert response["metadata"]["orchestration_mode"] == "blocked"


def test_execute_task_policy_block_handles_missing_create_session_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block-missing-session"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: None

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check without session payload",
            "automation",
            {"enforce_policy": True},
            session_id=None,
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] is None
    assert response["error"] == response["reason"]


def test_execute_task_policy_block_uses_id_key_when_session_id_missing():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block-id-key-session"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: {"id": "session-policy-id-key"}

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check with id-key session payload",
            "automation",
            {"enforce_policy": True},
            session_id=None,
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-policy-id-key"
    assert response["error"] == response["reason"]


def test_execute_task_policy_block_normalizes_whitespace_create_session_id():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block-whitespace-session"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: {"session_id": "   "}

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check with whitespace session id",
            "automation",
            {"enforce_policy": True},
            session_id=None,
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] is None
    assert response["error"] == response["reason"]


def test_execute_task_policy_block_handles_create_session_exception():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block-create-session-exception"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: (_ for _ in ()).throw(RuntimeError("session store unavailable"))

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check with create_session exception",
            "automation",
            {"enforce_policy": True},
            session_id=None,
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] is None
    assert response["error"] == response["reason"]


def test_execute_task_policy_block_with_session_does_not_call_create_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-policy-block-with-session"),
        {
            "dynamic_implementation": {
                "status": "needs_info",
                "approval_policy": {"status": "needs_info"},
                "gate_status": "ready",
                "execution_strategy": "simulation",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: (_ for _ in ()).throw(
        AssertionError("create_session should not be called when session_id is provided")
    )

    response = asyncio.run(
        murphy.execute_task(
            "Run policy block check with existing session",
            "automation",
            {"enforce_policy": True},
            session_id="session-policy-existing",
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-policy-existing"


def test_execute_task_blocks_when_orchestrator_online_required_even_if_policy_not_enforced():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-required"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online requirement",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": True},
            session_id="session-online-required",
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-online-required"
    assert "orchestration-online execution is required" in response["reason"]


def test_execute_task_blocks_when_orchestrator_online_required_uses_id_key_session_payload():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy._prepare_activation_preview = lambda *_args, **_kwargs: (
        SimpleNamespace(doc_id="doc-orchestrator-online-required-id-key"),
        {
            "dynamic_implementation": {
                "status": "ready",
                "approval_policy": {"status": "ready"},
                "gate_status": "ready",
                "execution_strategy": "production",
            }
        },
    )
    murphy._persist_execution_snapshot = lambda *_args, **_kwargs: {"status": "disabled"}
    murphy.create_session = lambda: {"id": "session-online-required-id-key"}

    response = asyncio.run(
        murphy.execute_task(
            "Execute with orchestration-online requirement and id-key session payload",
            "automation",
            {"enforce_policy": False, "require_orchestrator_online": True},
            session_id=None,
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-online-required-id-key"
    assert "orchestration-online execution is required" in response["reason"]


def test_execute_task_orchestrator_unavailable_with_session_does_not_call_create_session():
    runtime = load_runtime_module()
    if runtime.MFGCAdapter is None:
        pytest.skip("MFGC adapter not available in test environment")

    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = runtime.MFGCAdapter(murphy.system_integrator)
    murphy.orchestrator = None
    murphy.create_session = lambda: (_ for _ in ()).throw(
        AssertionError("create_session should not be called when session_id is provided")
    )

    response = asyncio.run(
        murphy.execute_task(
            "Draft an automation plan",
            "automation",
            {"enforce_policy": True},
            session_id="session-policy-existing",
        )
    )

    assert response["success"] is False
    assert response["status"] == "blocked"
    assert response["session_id"] == "session-policy-existing"


def test_execute_task_async_setup_failure_includes_execution_context():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = StubAsyncOrchestratorSetupFailure()

    response = asyncio.run(
        murphy.execute_task(
            "Execute with async setup failure",
            "automation",
            {"enforce_policy": False},
            session_id="session-async-setup-failure",
        )
    )

    assert response["success"] is False
    assert response["phase"] == "setup"
    assert response["error"] == "setup unavailable"
    assert "doc_id" in response
    assert "activation_preview" in response
    assert "execution_wiring" in response
    assert "execution_policy" in response
    assert "persistence_snapshot" in response
    assert "swarm_execution" in response


def test_execute_task_async_execution_failure_includes_execution_context():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = StubAsyncOrchestratorExecutionFailure()

    response = asyncio.run(
        murphy.execute_task(
            "Execute with async execution failure",
            "automation",
            {"enforce_policy": False},
            session_id="session-async-execution-failure",
        )
    )

    assert response["success"] is False
    assert response["phase"] == "execution"
    assert response["error"] == "execution unavailable"
    assert response["session_id"] == "async-session-1"
    assert "doc_id" in response
    assert "activation_preview" in response
    assert "execution_wiring" in response
    assert "execution_policy" in response
    assert "persistence_snapshot" in response
    assert "swarm_execution" in response


def test_execute_task_async_setup_rejects_invalid_session_id():
    runtime = load_runtime_module()
    orchestrator = StubAsyncOrchestratorInvalidSessionId()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.orchestrator = orchestrator

    response = asyncio.run(
        murphy.execute_task(
            "Execute with invalid async setup session id",
            "automation",
            {"enforce_policy": False},
            session_id="session-async-invalid-session",
        )
    )

    assert response["success"] is False
    assert response["phase"] == "setup"
    assert response["error"] == "Invalid orchestrator session_id returned from setup"
    assert "doc_id" in response
    assert "activation_preview" in response
    assert "execution_wiring" in response
    assert "execution_policy" in response
    assert "persistence_snapshot" in response
    assert "swarm_execution" in response
    assert orchestrator.phase2_called is False


def test_execute_task_async_success_timestamp_is_timezone_aware():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    class _StubAsyncOrchestratorSuccess:
        async def phase1_generative_setup(self, **_kwargs):
            return {"success": True, "session_id": "async-session-success", "execution_packet": {"id": "pkt-success"}}

        async def phase2_production_execution(self, **_kwargs):
            return {"success": True, "result": {"status": "ok"}, "deliverables": []}

    murphy.orchestrator = _StubAsyncOrchestratorSuccess()

    response = asyncio.run(
        murphy.execute_task(
            "Execute with async success",
            "automation",
            {"enforce_policy": False},
            session_id="session-async-success",
        )
    )

    assert response["success"] is True
    assert response["session_id"] == "async-session-success"
    assert response["execution_packet"]["id"] == "pkt-success"
    timestamp = datetime.fromisoformat(response["metadata"]["timestamp"])
    assert timestamp.tzinfo is timezone.utc
