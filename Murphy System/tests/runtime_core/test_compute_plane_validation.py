import importlib.util
from pathlib import Path
import asyncio
from collections import deque
from decimal import Decimal
from datetime import datetime
from types import MappingProxyType


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent.parent
    module_path = runtime_dir / "murphy_system_1.0_runtime.py"
    if not module_path.exists():
        candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
        if not candidates:
            raise RuntimeError("Unable to locate Murphy runtime module")
        raise RuntimeError(f"Expected runtime 1.0 module missing. Found: {candidates}")
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_compute_plane_validation_returns_validated():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    payload = {
        "compute_request": {
            "expression": "minimize: x subject to: x >= 0",
            "language": "lp"
        }
    }
    result = murphy._execute_compute_plane_validation(payload)
    assert result is not None
    assert result["status"] == "validated"
    assert result["language"] == "lp"
    assert result["validation"]["is_valid"] is True


def test_compute_plane_validation_requires_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    payload = {"compute_request": {"expression": "", "language": "lp"}}
    result = murphy._execute_compute_plane_validation(payload)
    assert result is not None
    assert result["status"] == "error"


def test_compute_plane_validation_supports_deterministic_request_alias():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    payload = {
        "deterministic_request": {
            "expression": "minimize: x subject to: x >= 0",
            "language": "lp"
        }
    }
    result = murphy._execute_compute_plane_validation(payload)
    assert result is not None
    assert result["status"] == "validated"
    assert result["route_source"] == "deterministic_request"


def test_execute_task_routes_deterministic_request_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request route",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_deterministic_request_binds_compute_session_mapping():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Deterministic request session binding",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-bind-session"
        )
    )
    assert result["status"] == "validated"
    assert result.get("session_id")
    assert result["session_id"] in murphy.document_sessions
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_preserves_unknown_supplied_session_for_compute_binding():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    supplied_session = "session-supplied-compute-binding"
    result = asyncio.run(
        murphy.execute_task(
            "Deterministic request supplied session binding",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id=supplied_session
        )
    )

    assert result["status"] == "validated"
    assert result["session_id"] == supplied_session
    assert supplied_session in murphy.sessions
    created_at = murphy.sessions[supplied_session].get("created_at")
    assert created_at
    assert datetime.fromisoformat(created_at).tzinfo is not None
    assert supplied_session in murphy.document_sessions
    assert murphy.document_sessions[supplied_session] == result["doc_id"]


def test_execute_task_whitespace_session_id_normalized_for_compute_path():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Deterministic request whitespace session binding",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="   "
        )
    )

    assert result["status"] == "validated"
    assert result["session_id"]
    assert result["session_id"].strip() != ""
    assert result["session_id"] in murphy.sessions
    assert result["session_id"] in murphy.document_sessions
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_compute_validation_handles_invalid_create_session_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    # create_session() is expected to return a dict; returning a string simulates
    # an invalid payload type from a broken session provider.
    murphy.create_session = lambda: "invalid-session-payload"
    result = asyncio.run(
        murphy.execute_task(
            "Compute validation with invalid create_session payload",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] is None


def test_execute_task_compute_validation_rejects_invalid_create_session_id_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    # create_session() returns a dictionary payload, but with an invalid session_id
    # type that should be normalized to None during compute-session resolution.
    murphy.create_session = lambda: {"session_id": b"compute-session-bytes"}
    result = asyncio.run(
        murphy.execute_task(
            "Compute validation with invalid create_session session_id payload",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] is None


def test_execute_task_compute_validation_registers_valid_create_session_id_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session"
    murphy.create_session = lambda: {"session_id": created_session_id}
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_create_session_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-key"
    murphy.create_session = lambda: {"id": created_session_id}
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id key",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_accepts_large_finite_decimal_session_id():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = Decimal("1E+10000")
    murphy.create_session = lambda: {"session_id": created_session_id}
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using large finite decimal session_id",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    normalized_session_id = str(created_session_id)
    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == normalized_session_id
    assert normalized_session_id in murphy.sessions
    assert murphy.document_sessions[normalized_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_when_session_id_is_invalid():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-fallback"
    murphy.create_session = lambda: {"session_id": "   ", "id": created_session_id}
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id fallback",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_when_session_id_is_mapping():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-mapping-fallback"
    murphy.create_session = lambda: {
        "session_id": MappingProxyType({"invalid": "session-id"}),
        "id": created_session_id,
    }
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id fallback for mapping session_id",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_when_session_id_is_deque():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-deque-fallback"
    murphy.create_session = lambda: {
        "session_id": deque(["invalid"]),
        "id": created_session_id,
    }
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id fallback for deque session_id",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_when_session_id_access_raises():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-access-fallback"

    class _SessionPayload(dict):
        def get(self, key, default=None):
            if key == "session_id":
                raise RuntimeError("session_id access failed")
            return super().get(key, default)

    murphy.create_session = lambda: _SessionPayload({"id": created_session_id})
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id fallback when session_id access fails",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_uses_id_key_when_payload_get_access_raises():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-id-get-access-fallback"

    class _SessionPayload(dict):
        def get(self, key, default=None):
            raise RuntimeError(f"{key} access failed")

    murphy.create_session = lambda: _SessionPayload({"id": created_session_id})
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using id fallback when payload get access fails",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_accepts_mapping_create_session_payload():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    created_session_id = "compute-created-session-mapping"
    murphy.create_session = lambda: MappingProxyType({"session_id": created_session_id})
    result = asyncio.run(
        murphy.execute_task(
            "Test compute validation session registration using mapping payload",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] == created_session_id
    assert created_session_id in murphy.sessions
    assert murphy.document_sessions[created_session_id] == result["doc_id"]


def test_execute_task_compute_validation_handles_create_session_exception():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    def _raise_create_session():
        raise RuntimeError("session allocation failed")

    murphy.create_session = _raise_create_session
    result = asyncio.run(
        murphy.execute_task(
            "Compute validation with create_session exception",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
        )
    )

    assert result["status"] == "validated"
    assert result["success"] is True
    assert result["session_id"] is None


def test_execute_task_whitespace_session_id_normalized_for_non_compute_path():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Non-compute whitespace session normalization",
            "general",
            {"enforce_policy": False},
            session_id="   ",
        )
    )

    assert result["session_id"]
    assert result["session_id"].strip() != ""
    assert result["session_id"] in murphy.sessions
    assert "   " not in murphy.sessions


def test_execute_task_non_string_session_id_normalized_to_string():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Non-compute integer session normalization",
            "general",
            {"enforce_policy": False},
            session_id=12345,
        )
    )

    assert result["session_id"] == "12345"
    assert 12345 not in murphy.sessions


def test_execute_task_boolean_session_id_normalized_as_missing():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Non-compute boolean session normalization",
            "general",
            {"enforce_policy": False},
            session_id=True,
        )
    )

    assert result["session_id"]
    assert result["session_id"] != "True"
    assert result["session_id"] in murphy.sessions
    assert True not in murphy.sessions


def test_execute_task_reuses_existing_compute_session_document_mapping():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    first = asyncio.run(
        murphy.execute_task(
            "Deterministic request first mapping",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            }
        )
    )
    second = asyncio.run(
        murphy.execute_task(
            "Deterministic request second mapping",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: y subject to: y >= 1",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id=first["session_id"]
        )
    )

    assert first["status"] == "validated"
    assert second["status"] == "validated"
    assert second["session_id"] == first["session_id"]
    assert second["doc_id"] == first["doc_id"]
    assert murphy.document_sessions[first["session_id"]] == first["doc_id"]


def test_execute_task_falls_back_to_deterministic_request_prompt_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Fallback deterministic request prompt expression from malformed compute request",
            "automation",
            {
                "compute_request": {"language": "lp"},
                "deterministic_request": {
                    "prompt": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-prompt-expression-fallback"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_routes_compute_request_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request route",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_routes_string_compute_request_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute string compute request route",
            "automation",
            {
                "compute_request": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-string-compute-request"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"
    assert result["compute_plane"]["language"] == "lp"


def test_execute_task_prefers_compute_request_over_deterministic_request():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence route",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "deterministic_request": {
                    "expression": "maximize: y subject to: y <= 10",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_malformed_deterministic_request():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over malformed deterministic request",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "deterministic_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-malformed-deterministic-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_deterministic_request_over_malformed_compute_request():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over malformed compute request",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "compute_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-malformed-compute-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_compute_request_over_confidence_required_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over confidence fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "confidence_expression": "maximize: y subject to: y <= 10",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-confidence-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_confidence_required_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over confidence-required compute expression",
            "confidence_engine",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-confidence-required-compute-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_confidence_task_type_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_expression": "maximize: y subject to: y <= 10",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-confidence-task-type-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_with_blank_confidence_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "confidence_expression": "   ",
                "enforce_policy": False
            },
            session_id="session-compute-request-blank-confidence-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_math_required_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over math fallback",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "math_required": True,
                "math_expression": "maximize: y subject to: y <= 10",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-math-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_math_task_type_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "math_expression": "maximize: y subject to: y <= 10",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-math-task-type-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_with_blank_math_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "math_expression": "   ",
                "enforce_policy": False
            },
            session_id="session-compute-request-blank-math-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_over_deterministic_required_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over deterministic required fallback",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "deterministic_required": True,
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-compute-request-deterministic-required-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_compute_request_when_deterministic_required_expression_blank():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute compute request precedence over blank deterministic required expression",
            "automation",
            {
                "compute_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "deterministic_required": True,
                "compute_expression": "   ",
                "enforce_policy": False
            },
            session_id="session-compute-request-deterministic-required-blank-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_prefers_deterministic_request_over_confidence_required_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over confidence fallback",
            "confidence_engine",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-confidence-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_deterministic_request_over_confidence_expression_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over confidence expression fallback",
            "confidence_engine",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "confidence_expression": "maximize: y subject to: y <= 10",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-confidence-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_deterministic_request_over_deterministic_required():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over deterministic required",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "deterministic_required": True,
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-deterministic-required-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_deterministic_request_over_math_required_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over math required",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "math_required": True,
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-math-required-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_deterministic_request_over_math_expression_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute deterministic request precedence over math expression fallback",
            "automation",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "math_required": True,
                "math_expression": "maximize: y subject to: y <= 10",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-math-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_prefers_deterministic_request_over_math_task_type_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: z subject to: z >= 1",
            "math",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "compute_expression": "maximize: y subject to: y <= 10",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-math-task-type-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_deterministic_request_precedence_over_confidence_task_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: z subject to: z >= 1",
            "confidence_engine",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-confidence-task-type-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_deterministic_request_precedence_over_confidence_expression_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_expression": "maximize: y subject to: y <= 10",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-confidence-expression-task-type-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_deterministic_request_precedence_over_blank_confidence_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "confidence_required": True,
                "confidence_expression": "   ",
                "enforce_policy": False
            },
            session_id="session-deterministic-request-blank-confidence-expression-precedence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_compute_request_missing_expression_returns_failed_route():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request route",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-missing-expression"
        )
    )
    assert result["status"] == "error"
    assert result["compute_plane"]["status"] == "error"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_compute_request_whitespace_expression_returns_missing_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute whitespace compute request route",
            "automation",
            {
                "compute_request": {
                    "expression": "   ",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-whitespace-expression"
        )
    )
    assert result["status"] == "error"
    assert result["compute_plane"]["status"] == "error"
    assert result["compute_plane"]["route_source"] == "compute_request"
    assert result["compute_plane"]["error"] == "Missing compute expression."


def test_execute_task_deterministic_request_missing_expression_returns_error_route():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed deterministic request route",
            "automation",
            {
                "deterministic_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-missing-expression"
        )
    )
    assert result["status"] == "error"
    assert result["compute_plane"]["status"] == "error"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_and_deterministic_requests_return_compute_error_route():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute and deterministic request route",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-and-deterministic"
        )
    )
    assert result["status"] == "error"
    assert result["compute_plane"]["status"] == "error"
    assert result["compute_plane"]["route_source"] == "compute_request"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_request():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "expression": "minimize: x subject to: x >= 0",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_request_falls_back_to_trimmed_deterministic_request():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with trimmed deterministic request fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "expression": "   minimize: x subject to: x >= 0   ",
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-trimmed-deterministic-request"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_request_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request compute-expression fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "compute_expression": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-compute-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_request_description_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request description fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "task_description": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-description-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_request_description_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request description-field fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "description": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-description-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_task_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request task-expression fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "task": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-task-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_trimmed_deterministic_request_task_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with trimmed deterministic request task-expression fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "task": "   minimize: x subject to: x >= 0   ",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-trimmed-deterministic-request-task-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_query_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request query fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "query": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-query-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_input_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request input fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "input": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-input-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_text_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request text-field fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "text": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-text-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_content_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request content fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "content": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-content-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_deterministic_request_message_field():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic request message fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "message": "minimize: x subject to: x >= 0",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-request-message-field"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_fallback_to_trimmed_deterministic_request_description():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with trimmed deterministic request description fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_request": {
                    "task_description": "   minimize: x subject to: x >= 0   ",
                    "compute_language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-trimmed-deterministic-request-description-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_request"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_malformed_compute_fallback_to_deterministic_required_trimmed_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic trimmed fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "compute_expression": "   minimize: x subject to: x >= 0   ",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-trimmed"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_input():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic input fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "input": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-input"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_description():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic description fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "description": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-description"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_task():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic task fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "task": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-task"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_prompt():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic prompt fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "prompt": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-prompt"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_query():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic query fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "query": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-query"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_content():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic content fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "content": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-content"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_message():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic message fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "message": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-message"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_deterministic_required_message_binds_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic message fallback binding session",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "message": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-message-bind-session"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"
    assert result["session_id"]
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_malformed_compute_request_falls_back_to_deterministic_required_text():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with deterministic text fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "deterministic_required": True,
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-required-text"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "confidence_expression": "minimize: x subject to: x >= 0",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence compute-expression fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-compute-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_prompt():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence prompt fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "prompt": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-prompt"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_input():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence input fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "input": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-input"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_text():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence text fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-text"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_content():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence content fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "content": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-content"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_query():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence query fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "query": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-query"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_description():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence description fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "description": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-description"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_task():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence task fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "task": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-task"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_required_message():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with confidence message fallback",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_required": True,
                "message": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-required-message"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_task_type():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_expression": "minimize: x subject to: x >= 0",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_task_type_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-compute-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_task_type_text():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-text"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_execute_task_malformed_compute_request_confidence_task_type_text_binds_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-text-bind-session"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"
    assert result["session_id"]
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_malformed_compute_request_falls_back_to_confidence_task_type_query():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "query": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-query"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_execute_task_malformed_compute_request_falls_back_to_confidence_task_type_prompt():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess confidence pathway",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "prompt": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-prompt"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_malformed_compute_fallback_to_confidence_via_description_expr():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: x subject to: x >= 0",
            "confidence_engine",
            {
                "compute_request": {
                    "language": "lp"
                },
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-confidence-task-type-description-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"


def test_execute_task_malformed_compute_request_deterministic_task_type_text_binds_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Route through deterministic task type",
            "deterministic",
            {
                "compute_request": {
                    "language": "lp"
                },
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-deterministic-task-type-text-bind-session"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_task_type"
    assert result["session_id"]
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_malformed_compute_request_falls_back_to_math_required():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "math_expression": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math compute-expression fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-compute-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_text():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math text fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "text": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-text"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_content():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math content fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "content": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-content"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_prompt():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math prompt fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "prompt": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-prompt"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_task():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math task fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "task": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-task"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_query():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math query fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "query": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-query"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_required_message():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request with math message fallback",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_required": True,
                "message": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-required-message"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_task_type():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_expression": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_task_type_compute_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-compute-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_task_type_text():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "text": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-text"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_math_task_type_text_binds_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "text": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-text-bind-session"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"
    assert result["session_id"]
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_execute_task_malformed_compute_request_falls_back_to_math_task_type_prompt():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "prompt": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-prompt"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_malformed_compute_request_falls_back_to_math_task_type_input():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Solve optimization",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "input": "minimize: x subject to: x >= 0",
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-input"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_malformed_compute_fallback_to_math_via_description_expr():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: x subject to: x >= 0",
            "math",
            {
                "compute_request": {
                    "language": "lp"
                },
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-malformed-compute-with-math-task-type-description-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"


def test_execute_task_compute_request_error_keeps_compute_validation_mode():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request mode check",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-error-mode"
        )
    )
    assert result["status"] == "error"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_compute_request_error_does_not_allocate_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed compute request session allocation check",
            "automation",
            {
                "compute_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-compute-request-error-no-session"
        )
    )
    assert result["status"] == "error"
    assert result["session_id"] is None
    assert set(murphy.document_sessions.keys()) == {"session-compute-request-error-no-session"}


def test_execute_task_deterministic_request_error_does_not_allocate_compute_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Execute malformed deterministic request session allocation check",
            "automation",
            {
                "deterministic_request": {
                    "language": "lp"
                },
                "enforce_policy": False
            },
            session_id="session-deterministic-request-error-no-session"
        )
    )
    assert result["status"] == "error"
    assert result["session_id"] is None
    assert set(murphy.document_sessions.keys()) == {"session-deterministic-request-error-no-session"}


def test_execute_task_routes_deterministic_required_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Validate deterministic route",
            "automation",
            {
                "deterministic_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-det"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_routes_confidence_required_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Confidence validation deterministic route",
            "confidence_engine",
            {
                "confidence_required": True,
                "confidence_expression": "minimize: x subject to: x >= 0",
                "confidence_language": "lp",
                "enforce_policy": False
            },
            session_id="session-confidence"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_confidence_required_with_compute_expression_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Confidence validation deterministic route fallback",
            "confidence_engine",
            {
                "confidence_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-confidence-fallback"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_required"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_routes_math_task_type_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: x subject to: x >= 0",
            "math",
            {
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-math"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_execute_task_routes_confidence_task_type_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: x subject to: x >= 0",
            "confidence_engine",
            {
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-confidence-task-type"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "confidence_task_type"
    assert result["metadata"]["mode"] == "compute_plane_validation"


def test_confidence_task_without_expression_skips_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Review this proposal and summarize key risks",
            "confidence_engine",
            {
                "enforce_policy": False
            },
            session_id="session-confidence-non-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_compute_plane_result_embeds_execution_wiring_snapshot():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "minimize: x subject to: x >= 0",
            "math",
            {
                "math_language": "lp",
                "enforce_policy": False
            },
            session_id="session-wiring-snapshot"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"
    assert "execution_wiring" in result["compute_plane"]
    assert result["compute_plane"]["wiring_enforced"] is False


def test_math_task_without_expression_skips_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Prepare a concise launch status summary for stakeholders",
            "math",
            {
                "enforce_policy": False
            },
            session_id="session-math-non-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_math_required_without_expression_skips_compute_plane_and_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Coordinate release checklist with stakeholders",
            "automation",
            {
                "math_required": True,
                "enforce_policy": False
            },
            session_id="session-math-required-non-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_confidence_required_without_expression_skips_compute_plane_and_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Review stakeholder concerns and summarize next steps",
            "automation",
            {
                "confidence_required": True,
                "enforce_policy": False
            },
            session_id="session-confidence-required-non-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_deterministic_required_without_expression_skips_compute_plane_and_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess rollout readiness",
            "automation",
            {
                "deterministic_required": True,
                "enforce_policy": False
            },
            session_id="session-deterministic-required-non-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_deterministic_required_with_blank_expression_skips_compute_plane_and_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Assess rollout readiness",
            "automation",
            {
                "deterministic_required": True,
                "compute_expression": "   ",
                "enforce_policy": False
            },
            session_id="session-deterministic-required-blank-expression"
        )
    )
    assert "compute_plane" not in result
    assert len(murphy.sessions) == 0


def test_deterministic_required_text_expression_routes_to_compute_plane_and_binds_session():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Route via deterministic_required text expression",
            "automation",
            {
                "deterministic_required": True,
                "text": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-deterministic-required-text-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "deterministic_required"
    assert result["session_id"]
    assert murphy.document_sessions[result["session_id"]] == result["doc_id"]


def test_math_required_with_expression_routes_to_compute_plane():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    result = asyncio.run(
        murphy.execute_task(
            "Route via math_required expression",
            "automation",
            {
                "math_required": True,
                "compute_expression": "minimize: x subject to: x >= 0",
                "compute_language": "lp",
                "enforce_policy": False
            },
            session_id="session-math-required-expression"
        )
    )
    assert result["status"] == "validated"
    assert result["compute_plane"]["route_source"] == "math_deterministic"
