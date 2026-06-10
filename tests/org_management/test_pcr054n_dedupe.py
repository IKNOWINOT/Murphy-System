"""PCR-054n — dedupe inbound_replies processing."""
import sqlite3
import time
import pytest

from src.engagement_folder import FolderState, create_folder, transition
from src.engagement_inbound import (
    INBOUND_DB_PATH,
    _ensure_inbound_processed_columns,
    _mark_reply_processed,
    fetch_candidate_replies,
    process_pending_replies,
    process_reply,
)


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":         str(tmp_path / "engagement_folders.db"),
        "browse_root":     str(tmp_path / "engagements"),
        "inbound_db_path": str(tmp_path / "inbound_replies.db"),
    }


def _seed_inbound(inbound_db_path: str, rows):
    """Create the inbound_replies schema and insert rows."""
    con = sqlite3.connect(inbound_db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS inbound_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_hash TEXT,
            received_at TEXT,
            mailbox TEXT,
            from_addr TEXT,
            from_domain TEXT,
            to_addr TEXT,
            subject TEXT,
            body_preview TEXT
        )
    """)
    for r in rows:
        con.execute(
            "INSERT INTO inbound_replies (msg_hash, received_at, mailbox, from_addr, from_domain, to_addr, subject, body_preview) "
            "VALUES (?,?,?,?,?,?,?,?)",
            r,
        )
    con.commit()
    con.close()


def _new_awaiting_folder(paths, email="jane@x.com"):
    f = create_folder(
        tenant_id="acme", role_id="cpa", artifact_type="tax_return",
        license_type_required="CPA", jurisdiction_required="US-CA",
        db_path=paths["db_path"], browse_root=paths["browse_root"],
    )
    transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
               update_fields={"practitioner_email": email},
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
               db_path=paths["db_path"])
    return f.engagement_id


class TestMigration:
    def test_ensure_columns_idempotent(self, paths):
        _seed_inbound(paths["inbound_db_path"], [])
        _ensure_inbound_processed_columns(paths["inbound_db_path"])
        _ensure_inbound_processed_columns(paths["inbound_db_path"])  # twice
        con = sqlite3.connect(paths["inbound_db_path"])
        cols = {r[1] for r in con.execute("PRAGMA table_info(inbound_replies)").fetchall()}
        con.close()
        assert "engagement_processed_at" in cols
        assert "engagement_processed_corr_id" in cols

    def test_ensure_columns_on_missing_table(self, tmp_path):
        # No table exists — should not raise
        empty_db = str(tmp_path / "empty.db")
        _ensure_inbound_processed_columns(empty_db)


class TestFetchFiltersProcessed:
    def test_fetch_excludes_processed_rows(self, paths):
        eid = _new_awaiting_folder(paths)
        _seed_inbound(paths["inbound_db_path"], [
            (f"h1", "2026-06-09T00:00:00", "m", "j@x.com", "x.com", "y",
             f"Re: {eid}", f"engagement {eid} - question?"),
            (f"h2", "2026-06-09T00:00:01", "m", "j@x.com", "x.com", "y",
             f"Re: {eid}", f"engagement {eid} - another question?"),
        ])

        # First fetch: both rows visible
        rows1 = fetch_candidate_replies(inbound_db_path=paths["inbound_db_path"])
        assert len(rows1) == 2

        # Mark row 1 processed
        _mark_reply_processed(rows1[1]["id"], "corr_abc", paths["inbound_db_path"])

        # Second fetch: only the unprocessed row visible
        rows2 = fetch_candidate_replies(inbound_db_path=paths["inbound_db_path"])
        assert len(rows2) == 1
        assert rows2[0]["id"] != rows1[1]["id"]

    def test_mark_writes_corr_id_and_timestamp(self, paths):
        _seed_inbound(paths["inbound_db_path"], [
            ("h1", "2026-06-09T00:00:00", "m", "x@x.com", "x.com", "y", "Re: eng_test", "body"),
        ])
        _ensure_inbound_processed_columns(paths["inbound_db_path"])
        _mark_reply_processed(1, "corr_xyz123", paths["inbound_db_path"])

        con = sqlite3.connect(paths["inbound_db_path"])
        row = con.execute(
            "SELECT engagement_processed_at, engagement_processed_corr_id "
            "FROM inbound_replies WHERE id = 1"
        ).fetchone()
        con.close()
        assert row[0] is not None
        assert row[1] == "corr_xyz123"


class TestDedupeEndToEnd:
    def test_process_reply_marks_row_in_attach_path(self, paths):
        eid = _new_awaiting_folder(paths)
        _seed_inbound(paths["inbound_db_path"], [
            ("h1", "2026-06-09T00:00:00", "m", "j@x.com", "x.com", "y",
             f"Re: {eid}",
             f"engagement {eid} - clarifying question, what about line 47?"),
        ])
        replies = fetch_candidate_replies(inbound_db_path=paths["inbound_db_path"])
        assert len(replies) == 1

        result = process_reply(replies[0], **{k: v for k, v in paths.items()
                                              if k in ("db_path", "inbound_db_path")})
        # Either gate ran (gate_applied) or attach happened — either way,
        # row must now be marked processed
        replies_after = fetch_candidate_replies(inbound_db_path=paths["inbound_db_path"])
        assert len(replies_after) == 0   # NOT re-processed on next fetch

    def test_batch_doesnt_reprocess_same_row_twice(self, paths):
        """The PCR-054n contract: a row processed in batch N+1 is invisible to batch N+2."""
        eid = _new_awaiting_folder(paths)
        _seed_inbound(paths["inbound_db_path"], [
            ("h1", "2026-06-09T00:00:00", "m", "j@x.com", "x.com", "y",
             f"Re: {eid}", f"engagement {eid} - what is line 5?"),
        ])

        # Batch 1
        r1 = process_pending_replies(
            db_path=paths["db_path"],
            inbound_db_path=paths["inbound_db_path"],
        )
        # At least one result (the gate-failed reply pushes to declined)
        assert (r1.get("finalized", 0) + r1.get("declined", 0) + r1.get("skipped", 0)) >= 1

        # Batch 2 — row is now marked processed, fetch returns 0 candidates
        r2 = process_pending_replies(
            db_path=paths["db_path"],
            inbound_db_path=paths["inbound_db_path"],
        )
        assert r2.get("finalized", 0) == 0
        assert r2.get("declined", 0) == 0
        assert r2.get("skipped", 0) == 0
        assert len(r2.get("results", [])) == 0
