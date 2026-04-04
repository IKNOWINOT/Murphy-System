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


def test_audit_export_snapshot_disabled(monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.delenv(murphy.PERSISTENCE_DIR_ENV, raising=False)
    status = murphy._build_persistence_status()
    export_snapshot = status["audit_export_snapshot"]
    assert export_snapshot["status"] == "disabled"
    assert export_snapshot["supported_formats"] == []


def test_audit_export_snapshot_empty(tmp_path, monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.setenv(murphy.PERSISTENCE_DIR_ENV, str(tmp_path))
    status = murphy._build_persistence_status()
    export_snapshot = status["audit_export_snapshot"]
    assert export_snapshot["status"] == "empty"
    assert export_snapshot["supported_formats"] == ["json", "csv"]
    assert export_snapshot["export_count"] == 0


def test_audit_export_snapshot_ready(tmp_path, monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.setenv(murphy.PERSISTENCE_DIR_ENV, str(tmp_path))
    first = f"{murphy.AUDIT_EXPORT_PREFIX}_20240101.json"
    second = f"{murphy.AUDIT_EXPORT_PREFIX}_20240102.csv"
    (tmp_path / first).write_text("{}")
    (tmp_path / second).write_text("data")
    status = murphy._build_persistence_status()
    export_snapshot = status["audit_export_snapshot"]
    assert export_snapshot["status"] == "ready"
    assert export_snapshot["export_count"] == 2
    assert export_snapshot["latest_export"] == second
