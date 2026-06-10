"""PCR-054m — corpus feedback loop regression suite."""
import pytest

from src.corpus_feedback import (
    DEFAULT_INTENT_MODIFIER,
    INTENT_MODIFIERS,
    OUTCOME_DELTAS,
    compute_weight_delta,
    explain_entry_weight,
    get_entry_weight,
    get_entry_weights_bulk,
    process_resolved_engagements,
    record_engagement_feedback,
)
from src.engagement_correspondence import attach_correspondence
from src.engagement_folder import FolderState, create_folder, transition
from src.practitioner_corpus import (
    harvest_from_thread,
    voice_for_practitioner_at_tenant,
)


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


def _engagement_with_corpus(paths, *, tenant_id="acme",
                             practitioner_email="jane@cpa.com",
                             messages_with_intents=None):
    """Create folder + finalize + attach messages + harvest corpus.

    messages_with_intents: list of (body, intent_hint_text).
    The intent classifier picks up cues from body text, so we use
    body text that naturally classifies — 'I attest...' for
    attestation, 'What about...' for clarifying_question, etc.
    """
    f = create_folder(
        tenant_id=tenant_id, role_id="cpa", artifact_type="tax_return",
        license_type_required="CPA", jurisdiction_required="US-CA",
        **paths,
    )
    transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
               update_fields={"practitioner_email": practitioner_email},
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.VALIDATING_ATTESTATION,
               db_path=paths["db_path"])
    transition(f.engagement_id, FolderState.FINALIZED,
               db_path=paths["db_path"])

    for body in (messages_with_intents or []):
        attach_correspondence(f.engagement_id, "in", practitioner_email, body,
                              db_path=paths["db_path"])
    harvest_from_thread(f.engagement_id, db_path=paths["db_path"])
    return f.engagement_id


# ─────────────────────────────────────────────────────────────────────
# Weight math
# ─────────────────────────────────────────────────────────────────────


class TestWeightMath:
    def test_attestation_on_verified_is_max_positive(self):
        # +1.0 outcome * 1.0 intent modifier = +1.0
        assert compute_weight_delta("verified", "attestation") == 1.0

    def test_attestation_on_flagged_is_negative(self):
        # -0.8 * 1.0 = -0.8
        assert compute_weight_delta("flagged", "attestation") == -0.8

    def test_clarifying_question_is_weak_signal(self):
        # +1.0 * 0.3 = +0.3 (small reinforcement)
        assert compute_weight_delta("verified", "clarifying_question") == pytest.approx(0.3)

    def test_unknown_intent_uses_default(self):
        # +1.0 * 0.2 (DEFAULT_INTENT_MODIFIER) = +0.2
        assert compute_weight_delta("verified", "totally_made_up") == pytest.approx(0.2)

    def test_unknown_outcome_is_zero(self):
        # 0.0 * anything = 0.0
        assert compute_weight_delta("not_a_state", "attestation") == 0.0


# ─────────────────────────────────────────────────────────────────────
# Record + idempotency
# ─────────────────────────────────────────────────────────────────────


class TestRecord:
    def test_record_creates_events_for_each_entry(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA license CA-99887.",
            "I attest as the CPA holder of license number CA-99887.",
        ])
        result = record_engagement_feedback(eid, "verified", db_path=paths["db_path"])
        assert result["ok"] is True
        assert result["events"] >= 1  # at least one entry harvested

    def test_record_is_idempotent(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        r1 = record_engagement_feedback(eid, "verified", db_path=paths["db_path"])
        r2 = record_engagement_feedback(eid, "verified", db_path=paths["db_path"])
        # Second call should skip everything (UNIQUE violation path)
        assert r2["events"] == 0
        assert r2["skipped"] == r1["events"]

    def test_record_rejects_unknown_outcome(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        result = record_engagement_feedback(eid, "not_real_state", db_path=paths["db_path"])
        assert result["ok"] is False
        assert result["events"] == 0


# ─────────────────────────────────────────────────────────────────────
# Weight read + explain
# ─────────────────────────────────────────────────────────────────────


class TestWeightRead:
    def test_default_weight_is_one_for_new_entry(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        # No feedback yet
        from src.practitioner_corpus import voice_for_practitioner_at_tenant
        v = voice_for_practitioner_at_tenant("jane@cpa.com", "acme",
                                              db_path=paths["db_path"])
        entry_id = v["entries"][0]["entry_id"]
        assert get_entry_weight(entry_id, db_path=paths["db_path"]) == 1.0

    def test_weight_increases_after_verified(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA license CA-99887.",
        ])
        v = voice_for_practitioner_at_tenant("jane@cpa.com", "acme",
                                              db_path=paths["db_path"])
        entry_id = v["entries"][0]["entry_id"]

        record_engagement_feedback(eid, "verified", db_path=paths["db_path"])

        w = get_entry_weight(entry_id, db_path=paths["db_path"])
        assert w > 1.0  # weight is now > default

    def test_weight_decreases_after_flagged(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        v = voice_for_practitioner_at_tenant("jane@cpa.com", "acme",
                                              db_path=paths["db_path"])
        entry_id = v["entries"][0]["entry_id"]
        record_engagement_feedback(eid, "flagged", db_path=paths["db_path"])
        w = get_entry_weight(entry_id, db_path=paths["db_path"])
        assert w < 1.0

    def test_explain_returns_event_log(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        v = voice_for_practitioner_at_tenant("jane@cpa.com", "acme",
                                              db_path=paths["db_path"])
        entry_id = v["entries"][0]["entry_id"]
        record_engagement_feedback(eid, "verified", db_path=paths["db_path"])
        exp = explain_entry_weight(entry_id, db_path=paths["db_path"])
        assert exp["entry_id"] == entry_id
        assert exp["event_count"] == 1
        assert exp["weight"] > 1.0
        assert exp["events"][0]["outcome_state"] == "verified"

    def test_bulk_returns_default_for_missing_ids(self, paths):
        result = get_entry_weights_bulk(["fake_1", "fake_2"], db_path=paths["db_path"])
        assert result == {"fake_1": 1.0, "fake_2": 1.0}


# ─────────────────────────────────────────────────────────────────────
# Voice query Y strategy: rank by weight
# ─────────────────────────────────────────────────────────────────────


class TestVoiceQueryWithWeights:
    def test_include_weights_false_is_byte_identical(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            f"I attest as Jane CPA holder license #{i}." for i in range(3)
        ])
        v1 = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "acme",
            db_path=paths["db_path"], include_weights=False,
        )
        # Old shape — no weights_applied flag at all, or False
        assert v1.get("weights_applied", False) is False
        for entry in v1["entries"]:
            assert "weight" not in entry

    def test_include_weights_true_returns_weighted_order(self, paths):
        eid1 = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA license CA-99887.",
        ])
        eid2 = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA holder license number CA-99887.",
        ])
        # Reinforce eid1 with verified, eid2 with flagged
        record_engagement_feedback(eid1, "verified", db_path=paths["db_path"])
        record_engagement_feedback(eid2, "flagged", db_path=paths["db_path"])

        v = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "acme",
            db_path=paths["db_path"], include_weights=True,
        )
        assert v["weights_applied"] is True
        assert all("weight" in e for e in v["entries"])
        # Highest-weight entry should rank first
        weights = [e["weight"] for e in v["entries"]]
        assert weights == sorted(weights, reverse=True)


# ─────────────────────────────────────────────────────────────────────
# Batch processor
# ─────────────────────────────────────────────────────────────────────


class TestBatchProcessor:
    def test_process_resolved_picks_up_terminal_folders(self, paths):
        # Create one finalized folder (not yet terminal — should be skipped)
        f1 = create_folder(
            tenant_id="acme", role_id="cpa", artifact_type="x",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        # Create one terminal-verified folder
        eid_verified = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        # Push to VERIFIED via VERIFYING
        transition(eid_verified, FolderState.VERIFYING, db_path=paths["db_path"])
        transition(eid_verified, FolderState.VERIFIED, db_path=paths["db_path"])

        result = process_resolved_engagements(db_path=paths["db_path"])
        assert result["ok"] is True
        # Should have processed at least the verified one
        engagement_ids = [r["engagement_id"] for r in result["results"]]
        assert eid_verified in engagement_ids

    def test_process_is_idempotent_across_runs(self, paths):
        eid = _engagement_with_corpus(paths, messages_with_intents=[
            "I attest as Jane CPA.",
        ])
        transition(eid, FolderState.VERIFYING, db_path=paths["db_path"])
        transition(eid, FolderState.VERIFIED, db_path=paths["db_path"])
        r1 = process_resolved_engagements(db_path=paths["db_path"])
        r2 = process_resolved_engagements(db_path=paths["db_path"])
        # Second run should record zero new events (all UNIQUE-rejected)
        assert r2["events_recorded"] == 0
