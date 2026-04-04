import importlib.util
from pathlib import Path


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


def test_audit_snapshot_disabled(monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.delenv(murphy.PERSISTENCE_DIR_ENV, raising=False)
    status = murphy._build_persistence_status()
    audit_snapshot = status["audit_snapshot"]
    assert audit_snapshot["status"] == "disabled"
    assert "reason" in audit_snapshot


def test_audit_snapshot_latest(tmp_path, monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.setenv(murphy.PERSISTENCE_DIR_ENV, str(tmp_path))
    first = f"{murphy.PERSISTENCE_SNAPSHOT_PREFIX}_doc_20240101T000000Z.json"
    second = f"{murphy.PERSISTENCE_SNAPSHOT_PREFIX}_doc_20240102T000000Z.json"
    (tmp_path / first).write_text("{}")
    (tmp_path / second).write_text("{}")
    status = murphy._build_persistence_status()
    audit_snapshot = status["audit_snapshot"]
    assert audit_snapshot["status"] == "ready"
    assert audit_snapshot["snapshot_count"] == 2
    assert audit_snapshot["latest_snapshot"] == second
