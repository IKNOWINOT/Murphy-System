from pathlib import Path
import importlib.util

from src.telemetry_learning.ingestion import TelemetryBus, TelemetryIngester


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


def test_observability_snapshot_unavailable():
    module = load_runtime_module()
    murphy = module.MurphySystem.create_test_instance()
    snapshot = murphy._build_observability_snapshot()
    assert snapshot["status"] == "unavailable"
    assert "reason" in snapshot


def test_observability_snapshot_available():
    module = load_runtime_module()
    murphy = module.MurphySystem.create_test_instance()
    murphy.telemetry_bus = TelemetryBus()
    murphy.telemetry_ingester = TelemetryIngester(murphy.telemetry_bus)
    snapshot = murphy._build_observability_snapshot()
    assert snapshot["status"] == "available"
    assert snapshot["telemetry_bus"]["events_received"] == 0
    assert "artifacts_ingested" in snapshot["ingestion"]
