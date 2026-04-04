import importlib.util
from pathlib import Path


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


def test_connector_orchestration_snapshot_defaults():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    snapshot = murphy._build_connector_orchestration_snapshot()

    summary = snapshot["summary"]
    assert summary["total"] == len(murphy.DELIVERY_ADAPTER_CANDIDATES)
    assert summary["configured"] == 0
    assert snapshot["status"] == "needs_integration"
    channels = snapshot["channels"]
    assert len(channels) == summary["total"]
    for entry in channels:
        assert entry["status"] in {"configured", "available", "needs_integration"}
        assert entry["adapter_id"]


def test_connector_orchestration_snapshot_all_configured():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    for candidate in murphy.DELIVERY_ADAPTER_CANDIDATES:
        murphy.integration_connectors[candidate["id"]] = {
            "status": "configured",
            "channel": candidate["channel"]
        }

    snapshot = murphy._build_connector_orchestration_snapshot()

    summary = snapshot["summary"]
    assert summary["configured"] == summary["total"]
    assert summary["needs_integration"] == 0
    assert snapshot["status"] == "ready"


def test_connector_orchestration_snapshot_in_system_status():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    status = murphy.get_system_status()

    orchestration = status["connector_orchestration"]
    summary = orchestration["summary"]
    assert summary["total"] == len(murphy.DELIVERY_ADAPTER_CANDIDATES)
    assert orchestration["status"] in {"needs_integration", "partial", "ready"}
