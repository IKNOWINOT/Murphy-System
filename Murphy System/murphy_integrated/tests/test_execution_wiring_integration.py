"""Execution wiring integration tests for execute_task."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


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


class StubResponse:
    def to_dict(self):
        return {"status": "stubbed", "message": "Processed by stub integrator"}


class StubIntegrator:
    @staticmethod
    def process_user_request(*_args, **_kwargs):
        return StubResponse()


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
    assert response["session_id"] == "session-1"
    assert "mfgc_execution" in response
    assert "execution_ready" in response["activation_preview"]["execution_wiring"]


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
