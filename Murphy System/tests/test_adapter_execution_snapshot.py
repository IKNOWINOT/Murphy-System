import importlib.util
import os
import pytest

_spec = importlib.util.spec_from_file_location(
    "murphy_system_runtime",
    os.path.join(os.path.dirname(__file__), '..', 'murphy_system_1.0_runtime.py')
)
if _spec is None or _spec.loader is None:
    pytest.skip("murphy_system_1.0_runtime.py not found", allow_module_level=True)
_runtime = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_runtime)
    MurphySystem = _runtime.MurphySystem
except Exception:
    pytest.skip("murphy_system_1.0_runtime.py could not be loaded", allow_module_level=True)


def test_adapter_execution_snapshot_reports_available_adapters():
    murphy = MurphySystem.create_test_instance()
    snapshot = murphy._build_adapter_execution_snapshot()

    assert snapshot["summary"]["total"] == len(murphy.CORE_ADAPTER_CANDIDATES)
    for adapter in snapshot["adapters"]:
        assert adapter["status"] in {"configured", "available", "needs_integration"}


def test_adapter_execution_snapshot_marks_configured_adapters():
    murphy = MurphySystem.create_test_instance()
    murphy.integration_connectors["telemetry_adapter"] = {"status": "configured"}

    snapshot = murphy._build_adapter_execution_snapshot()
    telemetry = next(item for item in snapshot["adapters"] if item["id"] == "telemetry_adapter")

    assert telemetry["status"] == "configured"
    assert snapshot["summary"]["configured"] == 1
