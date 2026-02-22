import importlib.util
from pathlib import Path
import asyncio


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
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
