"""PCR-054e — engagement_inbound.py regression suite."""
import sqlite3
import time

import pytest

from src.engagement_folder import (
    FolderState,
    create_folder,
    get_attestations,
    get_events,
    get_folder,
    transition,
)
from src.engagement_inbound import (
    ATTESTATION_PHRASES,
    GateResult,
    ParsedAttestation,
    fetch_candidate_replies,
    parse_attestation,
    process_pending_replies,
    process_reply,
    run_gate,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


@pytest.fixture
def inbound_db(tmp_path):
    """Fresh inbound_replies.db with the real schema."""
    path = str(tmp_path / "inbound_replies.db")
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE inbound_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_hash TEXT UNIQUE NOT NULL,
            received_at TEXT NOT NULL DEFAULT (datetime('now')),
            mailbox TEXT NOT NULL,
            from_addr TEXT,
            from_domain TEXT,
            to_addr TEXT,
            subject TEXT,
            date_header TEXT,
            is_internal INTEGER DEFAULT 0,
            is_prospect_domain INTEGER DEFAULT 0,
            prospect_deal_id TEXT,
            body_preview TEXT,
            schema_version INTEGER DEFAULT 1
        )
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture
def staged_awaiting_folder(paths):
    """A folder advanced to AWAITING_ATTESTATION."""
    f = create_folder(
        tenant_id="acme_corp",
        role_id="cpa_main",
        artifact_type="tax_return",
        artifact_content="Form 1120 draft",
        license_type_required="CPA",
        jurisdiction_required="US-CA",
        **paths,
    )
    transition(
        f.engagement_id, FolderState.OUTREACH_QUEUED,
        update_fields={"practitioner_email": "jane.cpa@example.com"},
        db_path=paths["db_path"],
    )
    transition(
        f.engagement_id, FolderState.AWAITING_ATTESTATION,
        db_path=paths["db_path"],
    )
    return f.engagement_id, paths


def good_attestation_body(engagement_id: str) -> str:
    return f"""
Dear Murphy,

Thank you for the engagement {engagement_id}.

I, Jane Q. CPA, holder of CPA license number CA-12345, issued by US-CA,
current and in good standing through 2027-12-31, have personally
reviewed engagement {engagement_id} and take professional responsibility
for the conclusions reached in this artifact.

Signed: Jane Q. CPA
License #: CA-12345
Date: 2026-06-09
"""


# ─────────────────────────────────────────────────────────────────────
# parse_attestation
# ─────────────────────────────────────────────────────────────────────


class TestParse:
    def test_parse_extracts_engagement_id(self):
        p = parse_attestation("Re: engagement eng_abc123def456 - approved")
        assert p.engagement_id == "eng_abc123def456"

    def test_parse_extracts_license_number(self):
        p = parse_attestation("License #: CA-99887")
        assert p.license_number == "CA-99887"

    def test_parse_detects_decline_standalone_line(self):
        p = parse_attestation("Sorry, I can't take this.\nDECLINE\n")
        assert p.declined is True

    def test_parse_does_not_misfire_on_decline_in_paragraph(self):
        p = parse_attestation("My fees decline by 10% in summer")
        assert p.declined is False

    def test_parse_attestation_language_requires_all_three_phrases(self):
        # All three present
        p = parse_attestation(
            "I have personally reviewed this and take professional "
            "responsibility, current and in good standing."
        )
        assert p.has_attestation_lang is True

    def test_parse_attestation_language_misses_one_phrase(self):
        # Only two of three
        p = parse_attestation(
            "I have personally reviewed this and take professional responsibility."
        )
        assert p.has_attestation_lang is False

    def test_parse_license_type_match_case_insensitive(self):
        p = parse_attestation(
            "I am a cpa and confirm this work",
            folder_license_type="CPA",
        )
        assert p.license_type_claimed == "CPA"

    def test_parse_jurisdiction_full_code(self):
        p = parse_attestation(
            "Issued by US-CA, current and active",
            folder_jurisdiction="US-CA",
        )
        assert p.jurisdiction_claimed == "US-CA"

    def test_parse_jurisdiction_state_only(self):
        p = parse_attestation(
            "I practice in CA and am licensed in that state",
            folder_jurisdiction="US-CA",
        )
        assert p.jurisdiction_claimed == "US-CA"


# ─────────────────────────────────────────────────────────────────────
# run_gate (6-point gate)
# ─────────────────────────────────────────────────────────────────────


class TestGate:
    def test_perfect_reply_passes(self):
        p = parse_attestation(
            good_attestation_body("eng_abc123def456"),
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(
            p,
            expected_engagement_id="eng_abc123def456",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        assert g.passed is True
        assert g.failures == []

    def test_decline_short_circuits(self):
        p = parse_attestation(
            f"eng_abc123def456\nDECLINE\nCPA license CA-12345 US-CA personally reviewed professional responsibility good standing",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(
            p,
            expected_engagement_id="eng_abc123def456",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        assert g.passed is False
        assert g.failures == ["explicitly_declined"]

    def test_missing_engagement_id_fails(self):
        p = parse_attestation(
            "License #: CA-12345 CPA US-CA personally reviewed professional responsibility good standing",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(p, expected_engagement_id="eng_abc123def456",
                    folder_license_type="CPA", folder_jurisdiction="US-CA")
        assert "missing_engagement_id" in g.failures

    def test_engagement_id_mismatch_fails(self):
        p = parse_attestation(
            "eng_999999999999 License #: CA-12345 CPA US-CA personally reviewed professional responsibility good standing",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(p, expected_engagement_id="eng_abc123def456",
                    folder_license_type="CPA", folder_jurisdiction="US-CA")
        assert "engagement_id_mismatch" in g.failures
        assert g.details["found_engagement_id"] == "eng_999999999999"

    def test_missing_license_number_fails(self):
        p = parse_attestation(
            "eng_abc123def456 CPA US-CA personally reviewed professional responsibility good standing",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(p, expected_engagement_id="eng_abc123def456",
                    folder_license_type="CPA", folder_jurisdiction="US-CA")
        assert "missing_license_number" in g.failures

    def test_missing_attestation_language_fails(self):
        p = parse_attestation(
            "eng_abc123def456 License #: CA-12345 CPA US-CA - this looks fine to me",
            folder_license_type="CPA",
            folder_jurisdiction="US-CA",
        )
        g = run_gate(p, expected_engagement_id="eng_abc123def456",
                    folder_license_type="CPA", folder_jurisdiction="US-CA")
        assert "missing_attestation_language" in g.failures


# ─────────────────────────────────────────────────────────────────────
# fetch_candidate_replies
# ─────────────────────────────────────────────────────────────────────


class TestFetch:
    def test_fetch_returns_rows_mentioning_eng_(self, inbound_db):
        con = sqlite3.connect(inbound_db)
        con.execute(
            "INSERT INTO inbound_replies (msg_hash, mailbox, from_addr, to_addr, "
            "subject, body_preview) VALUES (?, ?, ?, ?, ?, ?)",
            ("h1", "cpost", "jane@example.com", "murphy@murphy.systems",
             "Re: eng_abc123def456", "good reply body"),
        )
        con.execute(
            "INSERT INTO inbound_replies (msg_hash, mailbox, from_addr, to_addr, "
            "subject, body_preview) VALUES (?, ?, ?, ?, ?, ?)",
            ("h2", "cpost", "spam@example.com", "murphy@murphy.systems",
             "buy more SEO", "totally unrelated"),
        )
        con.commit(); con.close()

        rows = fetch_candidate_replies(inbound_db_path=inbound_db)
        assert len(rows) == 1
        assert rows[0]["subject"] == "Re: eng_abc123def456"

    def test_fetch_missing_db_returns_empty_list(self, tmp_path):
        assert fetch_candidate_replies(
            inbound_db_path=str(tmp_path / "nope.db")
        ) == []


# ─────────────────────────────────────────────────────────────────────
# process_reply (end-to-end against a folder)
# ─────────────────────────────────────────────────────────────────────


class TestProcessReply:
    def test_good_reply_pushes_folder_to_finalized(self, staged_awaiting_folder):
        eid, paths = staged_awaiting_folder
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "jane.cpa@example.com",
            "to_addr": "murphy@murphy.systems",
            "subject": f"Re: Engagement Request - {eid}",
            "body_preview": good_attestation_body(eid),
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["ok"] is True
        assert result["outcome"] == "finalized"
        f = get_folder(eid, db_path=paths["db_path"])
        assert f.state is FolderState.FINALIZED

    def test_bad_reply_pushes_to_declined_or_edits(self, staged_awaiting_folder):
        eid, paths = staged_awaiting_folder
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "jane.cpa@example.com",
            "to_addr": "murphy@murphy.systems",
            "subject": f"Re: {eid}",
            "body_preview": f"Hi - I looked at {eid} and have a few questions before I can sign.",
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["ok"] is True
        assert result["outcome"] == "declined_or_edits_asked"
        f = get_folder(eid, db_path=paths["db_path"])
        assert f.state is FolderState.DECLINED_OR_EDITS_ASKED

    def test_decline_reply_pushes_to_declined(self, staged_awaiting_folder):
        eid, paths = staged_awaiting_folder
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "jane.cpa@example.com", "to_addr": "x",
            "subject": f"Re: {eid}",
            "body_preview": f"engagement {eid}\nDECLINE\nThanks anyway.",
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["outcome"] == "declined_or_edits_asked"
        assert "explicitly_declined" in result["gate"]["failures"]

    def test_no_engagement_id_in_message_is_skipped(self, paths):
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "x", "to_addr": "y",
            "subject": "Hello!", "body_preview": "random message",
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["ok"] is False
        assert result["skipped"] is True

    def test_unknown_engagement_is_skipped(self, paths):
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "x", "to_addr": "y",
            "subject": "Re: eng_aaaaaaaaaaaa", "body_preview": good_attestation_body("eng_aaaaaaaaaaaa"),
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["ok"] is False
        assert "not found" in result["reason"]

    def test_folder_not_awaiting_is_skipped(self, paths):
        f = create_folder(
            tenant_id="t", role_id="r", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        # Folder is in DRAFTING, not AWAITING_ATTESTATION
        reply = {
            "id": 1, "received_at": "x",
            "from_addr": "x", "to_addr": "y",
            "subject": f"Re: {f.engagement_id}",
            "body_preview": good_attestation_body(f.engagement_id),
        }
        result = process_reply(reply, db_path=paths["db_path"])
        assert result["ok"] is False
        assert "drafting" in result["reason"]

    def test_attestation_payload_recorded(self, staged_awaiting_folder):
        eid, paths = staged_awaiting_folder
        reply = {
            "id": 1, "received_at": "2026-06-09T23:00:00",
            "from_addr": "jane.cpa@example.com", "to_addr": "x",
            "subject": f"Re: {eid}",
            "body_preview": good_attestation_body(eid),
        }
        process_reply(reply, db_path=paths["db_path"])
        atts = get_attestations(eid, db_path=paths["db_path"])
        assert len(atts) == 1
        a = atts[0]
        assert a["from_email"] == "jane.cpa@example.com"
        assert a["license_number_claimed"] == "CA-12345"
        assert a["license_type_claimed"] == "CPA"
        assert a["attestation_language_present"] == 1

    def test_three_transitions_recorded(self, staged_awaiting_folder):
        eid, paths = staged_awaiting_folder
        reply = {
            "id": 1, "received_at": "x",
            "from_addr": "jane.cpa@example.com", "to_addr": "x",
            "subject": f"Re: {eid}",
            "body_preview": good_attestation_body(eid),
        }
        process_reply(reply, db_path=paths["db_path"])
        events = get_events(eid, db_path=paths["db_path"])
        # Initial creation + outreach_queued + awaiting + validating + finalized
        states = [e.get("to_state") for e in events if e["event_type"] == "transition"]
        assert "validating_attestation" in states
        assert "finalized" in states


# ─────────────────────────────────────────────────────────────────────
# process_pending_replies (batch / cron)
# ─────────────────────────────────────────────────────────────────────


class TestBatch:
    def test_batch_processes_multiple_folders(self, paths, inbound_db, tmp_path):
        # Two folders both AWAITING_ATTESTATION
        f1 = create_folder(
            tenant_id="t1", role_id="r1", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        f2 = create_folder(
            tenant_id="t2", role_id="r2", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        for f in (f1, f2):
            transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
                       update_fields={"practitioner_email": "x@example.com"},
                       db_path=paths["db_path"])
            transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
                       db_path=paths["db_path"])

        # Insert one good and one decline into inbound
        con = sqlite3.connect(inbound_db)
        con.execute(
            "INSERT INTO inbound_replies (msg_hash, mailbox, from_addr, to_addr, subject, body_preview)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("h1", "cpost", "a@x", "x", f"Re: {f1.engagement_id}",
             good_attestation_body(f1.engagement_id)),
        )
        con.execute(
            "INSERT INTO inbound_replies (msg_hash, mailbox, from_addr, to_addr, subject, body_preview)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("h2", "cpost", "b@x", "x", f"Re: {f2.engagement_id}",
             f"engagement {f2.engagement_id}\nDECLINE\n"),
        )
        con.commit(); con.close()

        result = process_pending_replies(
            db_path=paths["db_path"],
            inbound_db_path=inbound_db,
        )
        assert result["scanned"] == 2
        assert result["finalized"] == 1
        assert result["declined"] == 1

        # Verify final states
        assert get_folder(f1.engagement_id, db_path=paths["db_path"]).state is FolderState.FINALIZED
        assert get_folder(f2.engagement_id, db_path=paths["db_path"]).state is FolderState.DECLINED_OR_EDITS_ASKED
