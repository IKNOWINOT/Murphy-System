import importlib.util
import json
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


def test_persistence_snapshot_written(tmp_path, monkeypatch):
    monkeypatch.setenv("MURPHY_PERSISTENCE_DIR", str(tmp_path))
    runtime_module = load_runtime_module()
    runtime = runtime_module.MurphySystem.create_test_instance()
    doc = runtime._create_document("Snapshot", "Test persistence snapshot.", "general", session_id="s1")
    preview = {"document_id": doc.doc_id}
    snapshot = runtime._persist_execution_snapshot(doc, preview, {"task_description": doc.content})
    assert snapshot["status"] == "stored"
    snapshot_path = Path(snapshot["path"])
    assert snapshot_path.exists()
    payload = json.loads(snapshot_path.read_text())
    assert payload["document"]["doc_id"] == doc.doc_id
