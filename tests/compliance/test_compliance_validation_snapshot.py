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


def test_compliance_validation_snapshot_ready():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    snapshot = murphy._build_compliance_validation_snapshot(
        {"compliance_status": "clear", "regulatory_source": "reg_source"},
        {"regulatory_sources": [{"id": "reg_source"}]}
    )

    assert snapshot["status"] == "ready"
    assert snapshot["regulatory_source"] == "reg_source"
    assert snapshot["next_action"] == "Compliance gates clear; proceed with delivery approvals."


def test_compliance_validation_snapshot_pending():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    snapshot = murphy._build_compliance_validation_snapshot(
        {"compliance_status": "pending"},
        {
            "primary_regulatory_source": {"id": "reg_api"},
            "regulatory_sources": [{"id": "reg_api"}]
        }
    )

    assert snapshot["status"] == "needs_compliance"
    assert snapshot["regulatory_source"] == "reg_api"
    assert snapshot["next_action"] == "Resolve compliance gates before delivery release."


def test_compliance_validation_snapshot_in_system_status():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.latest_activation_preview = {
        "delivery_readiness": {"compliance_status": "pending"},
        "external_api_sensors": {
            "primary_regulatory_source": {"id": "reg_api"},
            "regulatory_sources": [{"id": "reg_api"}]
        }
    }

    status = murphy.get_system_status()

    compliance_validation = status["compliance_validation"]
    assert compliance_validation["status"] == "needs_compliance"
    assert compliance_validation["regulatory_source"] == "reg_api"
