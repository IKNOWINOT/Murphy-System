"""
Test suite for PersistenceManager
Verifies document storage, gate history, librarian context,
audit trails, replay support, status, and thread safety.
"""

import pytest
import sys
import os
import time
import threading

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from persistence_manager import PersistenceManager


@pytest.fixture
def pm(tmp_path):
    """Create a PersistenceManager backed by a temporary directory."""
    return PersistenceManager(persistence_dir=str(tmp_path / "murphy_test"))


class TestDocumentPersistence:
    """Test LivingDocument save and load."""

    def test_save_and_load_document(self, pm):
        """Test round-trip save and load."""
        doc = {"title": "Test Doc", "version": 1, "content": {"key": "value"}}
        result = pm.save_document("doc-001", doc)
        assert result == "doc-001"

        loaded = pm.load_document("doc-001")
        assert loaded is not None
        assert loaded["title"] == "Test Doc"
        assert loaded["content"]["key"] == "value"

    def test_load_missing_document(self, pm):
        """Test loading a document that doesn't exist."""
        result = pm.load_document("nonexistent")
        assert result is None

    def test_overwrite_document(self, pm):
        """Test that saving overwrites previous version."""
        pm.save_document("doc-002", {"version": 1})
        pm.save_document("doc-002", {"version": 2})

        loaded = pm.load_document("doc-002")
        assert loaded["version"] == 2

    def test_list_documents(self, pm):
        """Test listing all stored documents."""
        pm.save_document("alpha", {"a": 1})
        pm.save_document("beta", {"b": 2})
        pm.save_document("gamma", {"c": 3})

        docs = pm.list_documents()
        assert docs == ["alpha", "beta", "gamma"]

    def test_list_documents_empty(self, pm):
        """Test listing when no documents exist."""
        assert pm.list_documents() == []


class TestGateHistory:
    """Test gate event persistence."""

    def test_save_and_get_gate_event(self, pm):
        """Test appending and retrieving gate events."""
        event_id = pm.save_gate_event("session-1", {
            "gate": "domain_gate",
            "decision": "allow",
            "confidence": 0.95,
        })
        assert event_id  # non-empty UUID string

        history = pm.get_gate_history("session-1")
        assert len(history) == 1
        assert history[0]["data"]["decision"] == "allow"
        assert history[0]["session_id"] == "session-1"

    def test_multiple_gate_events(self, pm):
        """Test multiple events accumulate in order."""
        pm.save_gate_event("session-2", {"step": 1})
        time.sleep(0.01)
        pm.save_gate_event("session-2", {"step": 2})
        time.sleep(0.01)
        pm.save_gate_event("session-2", {"step": 3})

        history = pm.get_gate_history("session-2")
        assert len(history) == 3
        steps = [e["data"]["step"] for e in history]
        assert steps == [1, 2, 3]

    def test_gate_history_separate_sessions(self, pm):
        """Test that sessions are isolated."""
        pm.save_gate_event("sess-a", {"gate": "a"})
        pm.save_gate_event("sess-b", {"gate": "b"})

        assert len(pm.get_gate_history("sess-a")) == 1
        assert len(pm.get_gate_history("sess-b")) == 1

    def test_gate_history_missing_session(self, pm):
        """Test getting history for nonexistent session."""
        assert pm.get_gate_history("nope") == []


class TestLibrarianContext:
    """Test librarian context persistence."""

    def test_save_and_load_context(self, pm):
        """Test round-trip save and load."""
        context = {
            "conditions": ["condition_a", "condition_b"],
            "domain": "healthcare",
            "priority": "high",
        }
        result = pm.save_librarian_context("req-001", context)
        assert result == "req-001"

        loaded = pm.load_librarian_context("req-001")
        assert loaded is not None
        assert loaded["context"]["domain"] == "healthcare"
        assert loaded["request_id"] == "req-001"
        assert "timestamp" in loaded

    def test_load_missing_context(self, pm):
        """Test loading context that doesn't exist."""
        assert pm.load_librarian_context("missing") is None

    def test_overwrite_context(self, pm):
        """Test that saving overwrites previous context."""
        pm.save_librarian_context("req-002", {"version": 1})
        pm.save_librarian_context("req-002", {"version": 2})

        loaded = pm.load_librarian_context("req-002")
        assert loaded["context"]["version"] == 2


class TestAuditTrail:
    """Test audit trail append and query."""

    def test_append_and_get(self, pm):
        """Test appending and retrieving audit events."""
        event_id = pm.append_audit_event({
            "session_id": "audit-sess-1",
            "event_type": "execution",
            "action": "run_task",
        })
        assert event_id

        trail = pm.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["data"]["action"] == "run_task"

    def test_audit_filter_by_session(self, pm):
        """Test filtering audit events by session_id."""
        pm.append_audit_event({"session_id": "s1", "action": "a"})
        pm.append_audit_event({"session_id": "s2", "action": "b"})
        pm.append_audit_event({"session_id": "s1", "action": "c"})

        s1_trail = pm.get_audit_trail(session_id="s1")
        assert len(s1_trail) == 2
        assert all(e["session_id"] == "s1" for e in s1_trail)

    def test_audit_limit(self, pm):
        """Test that limit restricts number of returned events."""
        for i in range(10):
            pm.append_audit_event({"session_id": "s", "index": i})

        limited = pm.get_audit_trail(limit=3)
        assert len(limited) == 3

    def test_audit_trail_empty(self, pm):
        """Test getting audit trail when none exists."""
        assert pm.get_audit_trail() == []

    def test_audit_ordering(self, pm):
        """Test that audit trail returns most recent first."""
        pm.append_audit_event({"session_id": "s", "event_type": "first", "timestamp": 100.0})
        pm.append_audit_event({"session_id": "s", "event_type": "second", "timestamp": 200.0})

        trail = pm.get_audit_trail()
        assert trail[0]["timestamp"] >= trail[1]["timestamp"]


class TestReplaySupport:
    """Test replay event enumeration."""

    def test_replay_events_ordered(self, pm):
        """Test that replay merges and orders events chronologically."""
        pm.save_gate_event("replay-sess", {"step": "gate_1"})
        time.sleep(0.01)
        pm.append_audit_event({"session_id": "replay-sess", "step": "audit_1"})
        time.sleep(0.01)
        pm.save_gate_event("replay-sess", {"step": "gate_2"})

        events = pm.get_replay_events("replay-sess")
        assert len(events) == 3

        timestamps = [e.get("timestamp", 0) for e in events]
        assert timestamps == sorted(timestamps)

    def test_replay_empty_session(self, pm):
        """Test replay for session with no events."""
        assert pm.get_replay_events("empty") == []


class TestStatus:
    """Test status reporting."""

    def test_status_empty(self, pm):
        """Test status when persistence is empty."""
        status = pm.get_status()
        assert status["documents"] == 0
        assert status["gate_sessions"] == 0
        assert status["librarian_contexts"] == 0
        assert status["audit_events"] == 0
        assert "persistence_dir" in status

    def test_status_with_data(self, pm):
        """Test status reflects stored data."""
        pm.save_document("d1", {"x": 1})
        pm.save_document("d2", {"y": 2})
        pm.save_gate_event("s1", {"g": 1})
        pm.save_librarian_context("r1", {"c": 1})
        pm.append_audit_event({"session_id": "s1", "a": 1})
        pm.append_audit_event({"session_id": "s1", "a": 2})

        status = pm.get_status()
        assert status["documents"] == 2
        assert status["gate_sessions"] == 1
        assert status["librarian_contexts"] == 1
        assert status["audit_events"] == 2


class TestThreadSafety:
    """Basic thread safety verification."""

    def test_concurrent_document_writes(self, pm):
        """Test that concurrent writes don't corrupt data."""
        errors = []

        def write_doc(i):
            try:
                pm.save_document(f"thread-doc-{i}", {"index": i, "data": "x" * 100})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_doc, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        docs = pm.list_documents()
        assert len(docs) == 20

    def test_concurrent_audit_appends(self, pm):
        """Test that concurrent audit appends don't lose events."""
        errors = []

        def append_event(i):
            try:
                pm.append_audit_event({"session_id": "concurrent", "index": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=append_event, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        trail = pm.get_audit_trail(session_id="concurrent", limit=1000)
        assert len(trail) == 20


class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_corrupt_json_document(self, pm, tmp_path):
        """Test graceful handling of corrupt JSON files."""
        doc_dir = tmp_path / "murphy_test" / "documents"
        corrupt_file = doc_dir / "corrupt.json"
        corrupt_file.write_text("{invalid json", encoding="utf-8")

        result = pm.load_document("corrupt")
        assert result is None

    def test_special_characters_in_doc_id(self, pm):
        """Test document IDs with simple special characters."""
        doc_id = "doc-with-dashes_and_underscores"
        pm.save_document(doc_id, {"content": "test"})
        loaded = pm.load_document(doc_id)
        assert loaded is not None
        assert loaded["content"] == "test"

    def test_empty_document(self, pm):
        """Test saving and loading an empty document."""
        pm.save_document("empty", {})
        loaded = pm.load_document("empty")
        assert loaded == {}

    def test_env_var_default(self, tmp_path, monkeypatch):
        """Test that MURPHY_PERSISTENCE_DIR env var is respected."""
        env_dir = str(tmp_path / "env_persistence")
        monkeypatch.setenv("MURPHY_PERSISTENCE_DIR", env_dir)

        manager = PersistenceManager()
        manager.save_document("env-doc", {"env": True})

        loaded = manager.load_document("env-doc")
        assert loaded is not None
        assert loaded["env"] is True
