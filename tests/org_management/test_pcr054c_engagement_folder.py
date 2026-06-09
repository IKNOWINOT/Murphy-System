"""PCR-054c — EngagementFolder state machine + persistence regression suite."""
import json
import os
import sqlite3
import tempfile
import time

import pytest

from src.engagement_folder import (
    AttestationPayload,
    EngagementFolder,
    FolderState,
    IllegalTransition,
    create_folder,
    folder_summary,
    get_attestations,
    get_events,
    get_folder,
    init_db,
    list_folders,
    record_external_event,
    store_attestation_payload,
    transition,
)


@pytest.fixture
def isolated_paths(tmp_path):
    """Per-test SQLite db + browse root so tests don't collide."""
    return {
        "db_path": str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


# ─────────────────────────────────────────────────────────────────────
# Schema bootstrap
# ─────────────────────────────────────────────────────────────────────


class TestSchema:
    def test_init_db_is_idempotent(self, isolated_paths):
        init_db(isolated_paths["db_path"])
        init_db(isolated_paths["db_path"])  # second call must not fail

    def test_init_db_creates_three_tables(self, isolated_paths):
        init_db(isolated_paths["db_path"])
        con = sqlite3.connect(isolated_paths["db_path"])
        try:
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        finally:
            con.close()
        assert "engagement_folders" in tables
        assert "engagement_events" in tables
        assert "attestation_payloads" in tables


# ─────────────────────────────────────────────────────────────────────
# Folder creation
# ─────────────────────────────────────────────────────────────────────


class TestCreateFolder:
    def test_create_returns_drafting_folder(self, isolated_paths):
        f = create_folder(
            tenant_id="t1", role_id="cpa_main", artifact_type="tax_return",
            artifact_content="draft body here",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **isolated_paths,
        )
        assert f.state is FolderState.DRAFTING
        assert f.tenant_id == "t1"
        assert f.role_id == "cpa_main"
        assert f.artifact_type == "tax_return"
        assert f.license_type_required == "CPA"
        assert f.engagement_id.startswith("eng_")

    def test_create_writes_draft_to_browse_dir(self, isolated_paths):
        f = create_folder(
            tenant_id="t1", role_id="r1", artifact_type="tax_return",
            artifact_content="hello practitioner",
            **isolated_paths,
        )
        # File should exist with that content
        with open(f.artifact_path) as fh:
            assert fh.read() == "hello practitioner"

    def test_create_records_initial_event(self, isolated_paths):
        f = create_folder(
            tenant_id="t1", role_id="r1", artifact_type="tax_return",
            **isolated_paths,
        )
        events = get_events(f.engagement_id, db_path=isolated_paths["db_path"])
        assert len(events) == 1
        assert events[0]["event_type"] == "transition"
        assert events[0]["to_state"] == "drafting"


# ─────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────


def _new(isolated_paths, **kw):
    return create_folder(
        tenant_id=kw.pop("tenant_id", "t1"),
        role_id=kw.pop("role_id", "r1"),
        artifact_type=kw.pop("artifact_type", "tax_return"),
        **isolated_paths, **kw,
    )


class TestTransitions:
    def test_happy_path_to_finalized(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]

        transition(eid, FolderState.OUTREACH_QUEUED, db_path=db,
                   update_fields={"practitioner_email": "cpa@example.com"})
        transition(eid, FolderState.AWAITING_ATTESTATION, db_path=db)
        transition(eid, FolderState.VALIDATING_ATTESTATION, db_path=db)
        transition(eid, FolderState.FINALIZED, db_path=db)

        final = get_folder(eid, db_path=db)
        assert final.state is FolderState.FINALIZED
        assert final.finalized_at is not None
        assert final.practitioner_email == "cpa@example.com"

    def test_can_go_to_verifying_after_finalized(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        for s in [FolderState.OUTREACH_QUEUED,
                  FolderState.AWAITING_ATTESTATION,
                  FolderState.VALIDATING_ATTESTATION,
                  FolderState.FINALIZED,
                  FolderState.VERIFYING,
                  FolderState.VERIFIED]:
            transition(eid, s, db_path=db)
        assert get_folder(eid, db_path=db).state is FolderState.VERIFIED

    def test_can_flag_after_verifying(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        for s in [FolderState.OUTREACH_QUEUED,
                  FolderState.AWAITING_ATTESTATION,
                  FolderState.VALIDATING_ATTESTATION,
                  FolderState.FINALIZED,
                  FolderState.VERIFYING,
                  FolderState.FLAGGED]:
            transition(eid, s, db_path=db)
        assert get_folder(eid, db_path=db).state is FolderState.FLAGGED

    def test_illegal_transition_raises(self, isolated_paths):
        f = _new(isolated_paths)
        with pytest.raises(IllegalTransition):
            transition(f.engagement_id, FolderState.FINALIZED,
                       db_path=isolated_paths["db_path"])

    def test_cannot_skip_validating(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        transition(eid, FolderState.OUTREACH_QUEUED, db_path=db)
        transition(eid, FolderState.AWAITING_ATTESTATION, db_path=db)
        with pytest.raises(IllegalTransition):
            transition(eid, FolderState.FINALIZED, db_path=db)

    def test_decline_loop_back_to_drafting(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        transition(eid, FolderState.OUTREACH_QUEUED, db_path=db)
        transition(eid, FolderState.DECLINED_OR_EDITS_ASKED, db_path=db)
        transition(eid, FolderState.DRAFTING, db_path=db)
        assert get_folder(eid, db_path=db).state is FolderState.DRAFTING

    def test_terminal_verified_locks_out(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        for s in [FolderState.OUTREACH_QUEUED,
                  FolderState.AWAITING_ATTESTATION,
                  FolderState.VALIDATING_ATTESTATION,
                  FolderState.FINALIZED,
                  FolderState.VERIFYING,
                  FolderState.VERIFIED]:
            transition(eid, s, db_path=db)
        with pytest.raises(IllegalTransition):
            transition(eid, FolderState.DRAFTING, db_path=db)

    def test_transition_unknown_folder_raises(self, isolated_paths):
        init_db(isolated_paths["db_path"])
        with pytest.raises(IllegalTransition):
            transition("eng_nope", FolderState.OUTREACH_QUEUED,
                       db_path=isolated_paths["db_path"])

    def test_transition_records_event_log_row(self, isolated_paths):
        f = _new(isolated_paths)
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        transition(eid, FolderState.OUTREACH_QUEUED, actor="system",
                   reason="practitioner selected", db_path=db)
        events = get_events(eid, db_path=db)
        assert len(events) == 2  # create + transition
        last = events[-1]
        assert last["from_state"] == "drafting"
        assert last["to_state"] == "outreach_queued"
        assert last["payload"]["reason"] == "practitioner selected"


# ─────────────────────────────────────────────────────────────────────
# Listing / filtering
# ─────────────────────────────────────────────────────────────────────


class TestListFolders:
    def test_filter_by_tenant(self, isolated_paths):
        _new(isolated_paths, tenant_id="t1")
        _new(isolated_paths, tenant_id="t2")
        out = list_folders(tenant_id="t1", db_path=isolated_paths["db_path"])
        assert len(out) == 1
        assert out[0].tenant_id == "t1"

    def test_filter_by_state(self, isolated_paths):
        f = _new(isolated_paths)
        transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
                   db_path=isolated_paths["db_path"])
        _new(isolated_paths)  # leave a second one in DRAFTING
        drafts = list_folders(state=FolderState.DRAFTING,
                              db_path=isolated_paths["db_path"])
        outs = list_folders(state=FolderState.OUTREACH_QUEUED,
                            db_path=isolated_paths["db_path"])
        assert len(drafts) == 1
        assert len(outs) == 1


# ─────────────────────────────────────────────────────────────────────
# Attestation payload persistence
# ─────────────────────────────────────────────────────────────────────


class TestAttestationStorage:
    def test_store_and_retrieve_attestation(self, isolated_paths):
        f = _new(isolated_paths, license_type_required="CPA",
                 jurisdiction_required="US-CA")
        eid = f.engagement_id
        db = isolated_paths["db_path"]
        payload = AttestationPayload(
            payload_id=None, engagement_id=eid, received_at=time.time(),
            from_email="cpa@example.com",
            raw_body="I, Jane Doe, license CPA-CA-12345...",
            license_type_claimed="CPA",
            license_number_claimed="CA-12345",
            license_jurisdiction_claimed="US-CA",
            expires_at_claimed=time.time() + 365 * 86400,
            attestation_language_present=True,
            qc_acknowledgments_json=json.dumps(["depreciation_check", "carryforward"]),
        )
        rowid = store_attestation_payload(payload, db_path=db)
        assert rowid > 0
        rows = get_attestations(eid, db_path=db)
        assert len(rows) == 1
        assert rows[0]["license_number_claimed"] == "CA-12345"
        assert rows[0]["attestation_language_present"] == 1


# ─────────────────────────────────────────────────────────────────────
# External events (non-transition)
# ─────────────────────────────────────────────────────────────────────


class TestExternalEvents:
    def test_record_outbound_email(self, isolated_paths):
        f = _new(isolated_paths)
        db = isolated_paths["db_path"]
        record_external_event(
            f.engagement_id, "outbound_email", actor="system",
            payload={"to": "cpa@example.com", "subject": "Engagement Request"},
            db_path=db,
        )
        events = get_events(f.engagement_id, db_path=db)
        types = [e["event_type"] for e in events]
        assert "outbound_email" in types

    def test_summary_includes_browse_path(self, isolated_paths, tmp_path):
        f = _new(isolated_paths)
        summary = folder_summary(f)
        assert "browse_path" in summary
        assert summary["state"] == "drafting"
