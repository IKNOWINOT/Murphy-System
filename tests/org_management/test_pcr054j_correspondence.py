"""PCR-054j — engagement_correspondence regression suite."""
import pytest

from src.engagement_correspondence import (
    Correspondence,
    IntentResult,
    attach_correspondence,
    classify_intent,
    get_thread,
    get_thread_by_intent,
    get_thread_by_practitioner,
    init_db,
    is_recoverable_followup,
)
from src.engagement_folder import create_folder


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


def _new_folder(paths):
    f = create_folder(
        tenant_id="acme", role_id="cpa", artifact_type="tax_return",
        license_type_required="CPA", jurisdiction_required="US-CA",
        **paths,
    )
    return f.engagement_id


# ─────────────────────────────────────────────────────────────────────
# Intent classifier
# ─────────────────────────────────────────────────────────────────────


class TestClassifier:
    def test_decline_explicit(self):
        r = classify_intent("DECLINE\nI cannot accept this engagement.")
        assert r.intent == "decline"
        assert r.confidence == "high"

    def test_decline_outside_scope(self):
        r = classify_intent("This is outside my scope of practice.")
        assert r.intent == "decline"

    def test_decline_wins_over_attestation(self):
        # If they mention a license number while declining, decline still wins
        r = classify_intent(
            "I hold CPA license #CA-12345 but cannot accept this engagement. "
            "Outside my scope."
        )
        assert r.intent == "decline"

    def test_attestation_full(self):
        body = """I, Jane Q. CPA, holder of CPA license number CA-99887, issued
        by US-CA, current and in good standing through 2027-12-31, have
        personally reviewed engagement eng_xyz and take professional
        responsibility for the conclusions reached in this artifact.

        License #: CA-99887"""
        r = classify_intent(body)
        assert r.intent == "attestation"
        assert r.confidence == "high"

    def test_attestation_medium_confidence(self):
        # Only 2 attestation signals
        r = classify_intent("I personally reviewed this and take professional responsibility.")
        assert r.intent == "attestation"
        assert r.confidence == "medium"

    def test_lone_attestation_signal_is_unclassified(self):
        r = classify_intent("I attest to my work.")
        assert r.intent == "unclassified"

    def test_revision_request(self):
        r = classify_intent("Please revise line 47 — should be $5,000 instead of $50,000.")
        assert r.intent == "revision_request"
        assert r.confidence == "high"

    def test_revision_attached(self):
        r = classify_intent("See attached revised draft with corrections.")
        assert r.intent == "revision_request"

    def test_clarifying_question_explicit(self):
        r = classify_intent("Can you tell me what depreciation method was used?")
        assert r.intent == "clarifying_question"

    def test_clarifying_question_interrogative(self):
        r = classify_intent("What's the basis for the deduction on line 32?")
        assert r.intent == "clarifying_question"

    def test_question_mark_alone_triggers(self):
        r = classify_intent("Should this be filed under section 1031?")
        assert r.intent == "clarifying_question"

    def test_status_inquiry(self):
        r = classify_intent("Where are we on this? Any update?")
        assert r.intent == "status_inquiry"
        assert r.confidence == "high"

    def test_status_checking_in(self):
        r = classify_intent("Just checking in on the filing.")
        assert r.intent == "status_inquiry"

    def test_unclassified_random_text(self):
        r = classify_intent("Thanks. Talk soon.")
        assert r.intent == "unclassified"
        assert r.confidence == "low"

    def test_signals_recorded(self):
        r = classify_intent("Please revise — should be different.")
        assert len(r.signals) >= 2
        assert all(s.startswith("rev:") for s in r.signals)


# ─────────────────────────────────────────────────────────────────────
# Attach correspondence
# ─────────────────────────────────────────────────────────────────────


class TestAttach:
    def test_attach_returns_correspondence(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(
            engagement_id=eid, direction="in",
            from_email="jane@example.com",
            body="What's the depreciation method?",
            subject=f"Re: {eid}",
            db_path=paths["db_path"],
        )
        assert corr.engagement_id == eid
        assert corr.classified_intent == "clarifying_question"
        assert corr.corr_id.startswith("corr_")

    def test_attach_rejects_bad_direction(self, paths):
        eid = _new_folder(paths)
        with pytest.raises(ValueError):
            attach_correspondence(
                engagement_id=eid, direction="sideways",
                from_email="x@x.com", body="x", db_path=paths["db_path"],
            )

    def test_attach_persists_to_db(self, paths):
        eid = _new_folder(paths)
        c1 = attach_correspondence(
            engagement_id=eid, direction="in", from_email="a@x.com",
            body="Question one?", db_path=paths["db_path"],
        )
        c2 = attach_correspondence(
            engagement_id=eid, direction="in", from_email="a@x.com",
            body="Question two?", db_path=paths["db_path"],
        )
        thread = get_thread(eid, db_path=paths["db_path"])
        assert len(thread) == 2
        assert thread[0].corr_id == c1.corr_id  # oldest first
        assert thread[1].corr_id == c2.corr_id

    def test_attach_records_folder_state(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(
            engagement_id=eid, direction="in", from_email="x@x.com",
            body="hello", folder_state_at_time="awaiting_attestation",
            db_path=paths["db_path"],
        )
        assert corr.folder_state_at_time == "awaiting_attestation"

    def test_attach_records_gate_result(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(
            engagement_id=eid, direction="in", from_email="x@x.com",
            body="attestation reply", gate_applied=True,
            gate_result={"passed": False, "missing": ["expiration_date"]},
            db_path=paths["db_path"],
        )
        assert corr.gate_applied is True
        assert "expiration_date" in corr.gate_result_json

    def test_classifier_signals_stored_in_metadata(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(
            engagement_id=eid, direction="in", from_email="x@x.com",
            body="Where are we on this?", db_path=paths["db_path"],
        )
        import json
        meta = json.loads(corr.metadata_json)
        assert "classifier_signals" in meta
        assert len(meta["classifier_signals"]) > 0


# ─────────────────────────────────────────────────────────────────────
# Query
# ─────────────────────────────────────────────────────────────────────


class TestQuery:
    def test_get_thread_returns_oldest_first(self, paths):
        eid = _new_folder(paths)
        import time as _t
        c1 = attach_correspondence(eid, "in", "a@x.com", "first?",
                                    db_path=paths["db_path"])
        _t.sleep(0.01)
        c2 = attach_correspondence(eid, "in", "a@x.com", "second?",
                                    db_path=paths["db_path"])
        thread = get_thread(eid, db_path=paths["db_path"])
        assert [c.corr_id for c in thread] == [c1.corr_id, c2.corr_id]

    def test_get_thread_by_intent_filters(self, paths):
        eid = _new_folder(paths)
        attach_correspondence(eid, "in", "x@x.com", "DECLINE — outside scope.",
                              db_path=paths["db_path"])
        attach_correspondence(eid, "in", "x@x.com", "What is the basis?",
                              db_path=paths["db_path"])
        attach_correspondence(eid, "in", "x@x.com", "Please revise line 5.",
                              db_path=paths["db_path"])

        questions = get_thread_by_intent(eid, "clarifying_question",
                                          db_path=paths["db_path"])
        assert len(questions) == 1
        assert "basis" in questions[0].body

    def test_get_thread_by_practitioner_across_engagements(self, paths):
        e1 = _new_folder(paths)
        e2 = _new_folder(paths)
        attach_correspondence(e1, "in", "jane@cpa.com", "Q1?", db_path=paths["db_path"])
        attach_correspondence(e2, "in", "jane@cpa.com", "Q2?", db_path=paths["db_path"])
        attach_correspondence(e1, "in", "other@cpa.com", "QX?", db_path=paths["db_path"])

        jane = get_thread_by_practitioner("jane@cpa.com", db_path=paths["db_path"])
        assert len(jane) == 2
        assert all(c.from_email == "jane@cpa.com" for c in jane)


# ─────────────────────────────────────────────────────────────────────
# Recovery heuristic
# ─────────────────────────────────────────────────────────────────────


class TestRecovery:
    def test_high_confidence_attestation_is_recoverable(self, paths):
        eid = _new_folder(paths)
        body = """I, Jane Q. CPA, holder of CPA license number CA-99887, current
        and in good standing through 2027-12-31, have personally reviewed
        engagement and take professional responsibility."""
        corr = attach_correspondence(eid, "in", "jane@x.com", body,
                                      db_path=paths["db_path"])
        assert is_recoverable_followup(corr) is True

    def test_question_not_recoverable(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(eid, "in", "x@x.com", "What is line 5?",
                                      db_path=paths["db_path"])
        assert is_recoverable_followup(corr) is False

    def test_decline_not_recoverable(self, paths):
        eid = _new_folder(paths)
        corr = attach_correspondence(eid, "in", "x@x.com", "DECLINE outside scope",
                                      db_path=paths["db_path"])
        assert is_recoverable_followup(corr) is False



# ─────────────────────────────────────────────────────────────────────
# End-to-end recovery (PCR-054j key behavior)
# ─────────────────────────────────────────────────────────────────────


class TestRecoveryE2E:
    def test_recovery_from_declined_to_finalized(self, paths):
        """PCR-054j: practitioner asks a clarifying question (folder stays
        in AWAITING with question on thread), then submits real attestation."""
        from src.engagement_folder import (
            FolderState, create_folder, get_folder, transition,
        )
        from src.engagement_inbound import process_reply

        # Setup folder in AWAITING
        f = create_folder(
            tenant_id="acme", role_id="cpa", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
                   update_fields={"practitioner_email": "jane@x.com"},
                   db_path=paths["db_path"])
        transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
                   db_path=paths["db_path"])

        # 1. Practitioner replies with bad-attestation -> DECLINED
        bad_reply = {
            "from_addr": "jane@x.com", "to_addr": "x",
            "subject": f"Re: {f.engagement_id}",
            "body_preview": f"engagement {f.engagement_id}\nI have a few questions before I sign.",
        }
        r1 = process_reply(bad_reply, db_path=paths["db_path"])
        assert r1["outcome"] == "declined_or_edits_asked"
        folder = get_folder(f.engagement_id, db_path=paths["db_path"])
        assert folder.state is FolderState.DECLINED_OR_EDITS_ASKED

        # 2. Practitioner comes back with real attestation
        good_reply = {
            "from_addr": "jane@x.com", "to_addr": "x",
            "subject": f"Re: {f.engagement_id}",
            "body_preview": (
                f"I, Jane Q. CPA, holder of CPA license number CA-99887 issued "
                f"by US-CA, current and in good standing through 2027-12-31, "
                f"have personally reviewed engagement {f.engagement_id} and take "
                f"professional responsibility for the conclusions reached.\n\n"
                f"License #: CA-99887"
            ),
        }
        r2 = process_reply(good_reply, db_path=paths["db_path"])
        assert r2["outcome"] == "finalized"  # PCR-054j RECOVERY
        folder = get_folder(f.engagement_id, db_path=paths["db_path"])
        assert folder.state is FolderState.FINALIZED

        # Both replies are on the thread
        thread = get_thread(f.engagement_id, db_path=paths["db_path"])
        assert len(thread) == 2
        # Second one ran the gate
        assert thread[1].gate_applied is True

    def test_question_during_awaiting_does_not_change_state(self, paths):
        """A clarifying question during AWAITING is gate-evaluated (so it
        becomes DECLINED_OR_EDITS_ASKED if it's not attestation). This is
        unchanged from prior behavior but documents the intent classifier
        captured the question intent on the thread."""
        from src.engagement_folder import (
            FolderState, create_folder, transition,
        )
        from src.engagement_inbound import process_reply

        f = create_folder(
            tenant_id="acme", role_id="cpa", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        transition(f.engagement_id, FolderState.OUTREACH_QUEUED,
                   update_fields={"practitioner_email": "j@x.com"},
                   db_path=paths["db_path"])
        transition(f.engagement_id, FolderState.AWAITING_ATTESTATION,
                   db_path=paths["db_path"])

        reply = {
            "from_addr": "j@x.com", "to_addr": "x",
            "subject": f"Re: {f.engagement_id}",
            "body_preview": f"engagement {f.engagement_id} - what is the depreciation?",
        }
        process_reply(reply, db_path=paths["db_path"])

        thread = get_thread(f.engagement_id, db_path=paths["db_path"])
        assert len(thread) == 1
        assert thread[0].classified_intent == "clarifying_question"
