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


def test_persistence_snapshot_index_empty(tmp_path, monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.setenv(murphy.PERSISTENCE_DIR_ENV, str(tmp_path))
    status = murphy._build_persistence_status()
    index = status["snapshot_index"]
    assert index["status"] == "empty"
    assert index["count"] == 0
    assert index["snapshots"] == []


def test_persistence_snapshot_index_lists_snapshots(tmp_path, monkeypatch):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    monkeypatch.setenv(murphy.PERSISTENCE_DIR_ENV, str(tmp_path))
    snapshot_name = f"{murphy.PERSISTENCE_SNAPSHOT_PREFIX}_doc_20240101T000000Z.json"
    (tmp_path / snapshot_name).write_text("{}")
    index = murphy._build_persistence_snapshot_index(tmp_path)
    assert index["status"] == "ready"
    assert index["count"] == 1
    assert snapshot_name in index["snapshots"]
