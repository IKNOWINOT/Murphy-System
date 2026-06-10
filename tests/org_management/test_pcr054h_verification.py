"""PCR-054h — engagement_verification.py regression suite."""
import pytest

from src.engagement_folder import (
    FolderState,
    create_folder,
    get_events,
    get_folder,
    record_attestation_payload,
    transition,
)
from src.engagement_verification import (
    LICENSE_TYPE_TO_AUTHORITY,
    PROVIDERS,
    VerificationResult,
    verify,
    verify_attorney,
    verify_cpa,
    verify_folder,
    verify_finalized_engagements,
    verify_pe,
)


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


def _make_finalized_folder(paths, license_type="CPA", license_number="CA-12345",
                            jurisdiction="US-CA"):
    """Helper: create a folder, push it to FINALIZED with an attestation."""
    f = create_folder(
        tenant_id="acme",
        role_id="r1",
        artifact_type="tax_return",
        artifact_content="draft",
        license_type_required=license_type,
        jurisdiction_required=jurisdiction,
        **paths,
    )
    # Walk through the state machine
    transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
               update_fields={"practitioner_email": "x@example.com"},
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.VALIDATING_ATTESTATION,
               db_path=paths["db_path"])
    record_attestation_payload(
        engagement_id=f.engagement_id,
        from_email="x@example.com",
        raw_body=f"signed by {license_type} #{license_number}",
        license_type_claimed=license_type,
        license_number_claimed=license_number,
        license_jurisdiction_claimed=jurisdiction,
        attestation_language_present=True,
        db_path=paths["db_path"],
    )
    transition(f.engagement_id, FolderState.FINALIZED,
               db_path=paths["db_path"])
    return f.engagement_id


# ─────────────────────────────────────────────────────────────────────
# Provider stubs
# ─────────────────────────────────────────────────────────────────────


class TestProviderStubs:
    def test_cpa_good_prefix_verifies(self):
        r = verify_cpa("GOOD-12345", "US-CA")
        assert r.verified is True
        assert "AICPA" in r.source
        assert r.evidence["match_confidence"] == "high"

    def test_cpa_bad_prefix_flagged(self):
        r = verify_cpa("BAD-99999", "US-CA")
        assert r.verified is False
        assert r.error is not None
        assert r.evidence["lookup_outcome"] == "no_record"

    def test_cpa_exp_prefix_flagged_as_expired(self):
        r = verify_cpa("EXP-12345", "US-CA")
        assert r.verified is False
        assert "expired" in r.error.lower()

    def test_arbitrary_number_passes_through(self):
        # CA-12345 doesn't start with GOOD/BAD/EXP -> default pass
        r = verify_cpa("CA-12345", "US-CA")
        assert r.verified is True
        assert r.evidence["match_confidence"] == "stub_passthrough"

    def test_pe_uses_ncees_source(self):
        r = verify_pe("PE-001", "US-TX")
        assert "NCEES" in r.source

    def test_attorney_uses_state_bar_source(self):
        r = verify_attorney("BAR-001", "US-NY")
        assert "Bar" in r.source

    def test_all_providers_registered(self):
        for license_type in ["CPA", "PE", "Attorney", "PMP", "RA"]:
            assert license_type in PROVIDERS, f"missing provider: {license_type}"

    def test_authority_map_complete(self):
        for license_type in PROVIDERS:
            assert license_type in LICENSE_TYPE_TO_AUTHORITY


# ─────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────


class TestDispatch:
    def test_unknown_license_type_returns_error(self):
        r = verify("Astrologer", "AST-1", "US-CA")
        assert r.verified is False
        assert "no provider configured" in r.error
        assert "CPA" in r.evidence["known_types"]

    def test_known_type_dispatches(self):
        r = verify("CPA", "GOOD-1", "US-CA")
        assert r.verified is True


# ─────────────────────────────────────────────────────────────────────
# verify_folder (end-to-end)
# ─────────────────────────────────────────────────────────────────────


class TestVerifyFolder:
    def test_verified_path_finalizes_to_verified(self, paths):
        eid = _make_finalized_folder(paths, license_number="GOOD-CA-12345")
        result = verify_folder(eid, db_path=paths["db_path"])
        assert result["ok"] is True
        assert result["outcome"] == "verified"
        f = get_folder(eid, db_path=paths["db_path"])
        assert f.state is FolderState.VERIFIED
        assert f.verified_at is not None
        assert "AICPA" in f.verified_via
        assert "GOOD-CA-12345 verified" in f.verification_notes

    def test_bad_license_flags(self, paths):
        eid = _make_finalized_folder(paths, license_number="BAD-99999")
        result = verify_folder(eid, db_path=paths["db_path"])
        assert result["outcome"] == "flagged"
        f = get_folder(eid, db_path=paths["db_path"])
        assert f.state is FolderState.FLAGGED
        assert f.verification_notes is not None
        assert "not found" in f.verification_notes

    def test_expired_license_flags(self, paths):
        eid = _make_finalized_folder(paths, license_number="EXP-12345")
        result = verify_folder(eid, db_path=paths["db_path"])
        assert result["outcome"] == "flagged"
        f = get_folder(eid, db_path=paths["db_path"])
        assert "expired" in f.verification_notes

    def test_unknown_engagement_skipped(self, paths):
        result = verify_folder("eng_nonexistent", db_path=paths["db_path"])
        assert result["ok"] is False
        assert result["skipped"] is True

    def test_not_finalized_folder_skipped(self, paths):
        f = create_folder(
            tenant_id="acme", role_id="r", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        # folder is in DRAFTING
        result = verify_folder(f.engagement_id, db_path=paths["db_path"])
        assert result["ok"] is False
        assert "drafting" in result["reason"]

    def test_records_verification_event(self, paths):
        eid = _make_finalized_folder(paths, license_number="GOOD-1")
        verify_folder(eid, db_path=paths["db_path"])
        events = get_events(eid, db_path=paths["db_path"])
        verif_events = [e for e in events if e["event_type"] == "license_verification"]
        assert len(verif_events) == 1
        p = verif_events[0]["payload"]
        assert p["verified"] is True
        assert "AICPA" in p["source"]

    def test_two_transitions_on_verification(self, paths):
        eid = _make_finalized_folder(paths, license_number="GOOD-1")
        verify_folder(eid, db_path=paths["db_path"])
        events = get_events(eid, db_path=paths["db_path"])
        states = [e.get("to_state") for e in events if e["event_type"] == "transition"]
        # The FINALIZED transition is already there from setup. We add 2 more.
        assert "verifying" in states
        assert "verified" in states

    def test_unknown_license_type_flags(self, paths):
        eid = _make_finalized_folder(paths, license_type="CPA", license_number="x")
        # mutate attestation to claim a bogus type
        import sqlite3
        con = sqlite3.connect(paths["db_path"])
        con.execute("UPDATE attestation_payloads SET license_type_claimed = 'Astrologer' WHERE engagement_id = ?", (eid,))
        con.commit(); con.close()

        result = verify_folder(eid, db_path=paths["db_path"])
        assert result["outcome"] == "flagged"


# ─────────────────────────────────────────────────────────────────────
# Batch
# ─────────────────────────────────────────────────────────────────────


class TestBatch:
    def test_batch_processes_mixed(self, paths):
        e1 = _make_finalized_folder(paths, license_number="GOOD-1")
        e2 = _make_finalized_folder(paths, license_number="BAD-1")
        e3 = _make_finalized_folder(paths, license_number="EXP-1")

        result = verify_finalized_engagements(db_path=paths["db_path"])
        assert result["scanned"] == 3
        assert result["verified"] == 1
        assert result["flagged"] == 2
        assert result["skipped"] == 0

        assert get_folder(e1, db_path=paths["db_path"]).state is FolderState.VERIFIED
        assert get_folder(e2, db_path=paths["db_path"]).state is FolderState.FLAGGED
        assert get_folder(e3, db_path=paths["db_path"]).state is FolderState.FLAGGED

    def test_batch_idempotent_skips_already_verified(self, paths):
        eid = _make_finalized_folder(paths, license_number="GOOD-1")
        verify_finalized_engagements(db_path=paths["db_path"])  # finalizes
        # Run again — should be a no-op because nothing is in FINALIZED
        result = verify_finalized_engagements(db_path=paths["db_path"])
        assert result["scanned"] == 0
