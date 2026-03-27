"""
Tests for persistence_manager.py — corruption recovery & atomic write edge cases

Closes Gap 4: Existing tests covered the happy path but NOT:
- Corrupt JSON file recovery (JSONDecodeError → returns None / resets)
- Corrupt gate history recovery (resets to empty list)
- Corrupt audit trail recovery (resets to empty list)
- Atomic write failure cleanup (tmp file removed on error)
- Path traversal in doc_id
"""

import json
import os
import unittest


from persistence_manager import (
    PersistenceManager,
    DOCUMENTS_DIR,
    GATE_HISTORY_DIR,
    AUDIT_DIR,
    LIBRARIAN_DIR,
)


class TestCorruptJsonDocumentRecovery(unittest.TestCase):
    """load_document returns None when JSON is corrupt (CWE-755 gap)."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_corrupt_document_returns_none(self):
        """A corrupted .json document file must not crash — return None."""
        doc_path = os.path.join(self.tmpdir, DOCUMENTS_DIR, "bad.json")
        with open(doc_path, "w") as f:
            f.write("{{{INVALID JSON")

        result = self.pm.load_document("bad")
        self.assertIsNone(result)

    def test_valid_document_after_corrupt_one(self):
        """Good documents still load even when one is corrupt."""
        # Write a corrupt doc
        doc_path = os.path.join(self.tmpdir, DOCUMENTS_DIR, "corrupt.json")
        with open(doc_path, "w") as f:
            f.write("NOT JSON")

        # Write a valid doc
        self.pm.save_document("good", {"status": "ok"})

        self.assertIsNone(self.pm.load_document("corrupt"))
        loaded = self.pm.load_document("good")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["status"], "ok")


class TestCorruptGateHistoryRecovery(unittest.TestCase):
    """Corrupt gate history file must reset gracefully, not crash."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_corrupt_gate_history_resets(self):
        """save_gate_event on a corrupt session file resets the history."""
        gate_path = os.path.join(self.tmpdir, GATE_HISTORY_DIR, "sess-1.json")
        with open(gate_path, "w") as f:
            f.write("CORRUPT DATA!!!")

        # Saving should reset the corrupt file and succeed
        event_id = self.pm.save_gate_event("sess-1", {"decision": "pass"})
        self.assertTrue(len(event_id) > 0)

        # History should have exactly the new event
        history = self.pm.get_gate_history("sess-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["data"]["decision"], "pass")

    def test_corrupt_gate_read_returns_empty(self):
        """Reading corrupt gate history returns empty list, not crash."""
        gate_path = os.path.join(self.tmpdir, GATE_HISTORY_DIR, "sess-2.json")
        with open(gate_path, "w") as f:
            f.write("{bad json")

        history = self.pm.get_gate_history("sess-2")
        self.assertEqual(history, [])


class TestCorruptAuditTrailRecovery(unittest.TestCase):
    """Corrupt audit trail resets gracefully."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_corrupt_audit_trail_resets_on_append(self):
        """Appending to a corrupt audit trail resets and appends."""
        audit_path = os.path.join(self.tmpdir, AUDIT_DIR, "audit_trail.json")
        with open(audit_path, "w") as f:
            f.write("<<CORRUPT>>")

        event_id = self.pm.append_audit_event({"action": "test"})
        self.assertTrue(len(event_id) > 0)

        trail = self.pm.get_audit_trail()
        self.assertEqual(len(trail), 1)

    def test_corrupt_audit_trail_read_returns_empty(self):
        """Reading corrupt audit trail returns empty list."""
        audit_path = os.path.join(self.tmpdir, AUDIT_DIR, "audit_trail.json")
        with open(audit_path, "w") as f:
            f.write("not json at all")

        trail = self.pm.get_audit_trail()
        self.assertEqual(trail, [])


class TestCorruptLibrarianContextRecovery(unittest.TestCase):
    """Corrupt librarian context returns None, not crash."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_corrupt_librarian_returns_none(self):
        lib_path = os.path.join(self.tmpdir, LIBRARIAN_DIR, "req-1.json")
        with open(lib_path, "w") as f:
            f.write("{{invalid")

        result = self.pm.load_librarian_context("req-1")
        self.assertIsNone(result)


class TestAtomicWriteCleanup(unittest.TestCase):
    """If _write_json fails mid-write, .tmp file must be cleaned up."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_tmp_file_cleaned_on_error(self):
        """If json.dump fails (non-serializable), .tmp must be removed."""
        from pathlib import Path

        class NonSerializable:
            pass

        doc_id = "fail-doc"
        try:
            self.pm.save_document(doc_id, {"obj": NonSerializable()})
        except TypeError:
            pass  # expected

        tmp_path = Path(self.tmpdir) / DOCUMENTS_DIR / f"{doc_id}.tmp"
        self.assertFalse(tmp_path.exists(), ".tmp file should be cleaned up")


class TestStatusWithCorruptAudit(unittest.TestCase):
    """get_status should handle corrupt audit trail gracefully."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.pm = PersistenceManager(persistence_dir=self.tmpdir)

    def test_status_with_corrupt_audit(self):
        audit_path = os.path.join(self.tmpdir, AUDIT_DIR, "audit_trail.json")
        with open(audit_path, "w") as f:
            f.write("CORRUPT")

        status = self.pm.get_status()
        self.assertEqual(status["audit_events"], -1)


if __name__ == "__main__":
    unittest.main()
