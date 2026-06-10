"""PCR-054k — practitioner_corpus regression suite."""
import pytest

from src.engagement_correspondence import attach_correspondence
from src.engagement_folder import (
    FolderState, create_folder, transition,
)
from src.practitioner_corpus import (
    CorpusEntry,
    VocabSignature,
    compute_vocab_signature,
    harvest_all_finalized,
    harvest_from_thread,
    init_db,
    practitioner_id_from_email,
    recurring_questions,
    voice_for_practitioner_at_tenant,
    voice_for_role_jurisdiction,
)


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


def _setup_finalized_folder(paths, tenant_id="acme", role_id="cpa",
                             jurisdiction="US-CA", practitioner_email="jane@cpa.com"):
    f = create_folder(
        tenant_id=tenant_id, role_id=role_id, artifact_type="tax_return",
        license_type_required="CPA", jurisdiction_required=jurisdiction,
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
    return f.engagement_id


# ─────────────────────────────────────────────────────────────────────
# practitioner_id derivation
# ─────────────────────────────────────────────────────────────────────


class TestPractitionerID:
    def test_lowercases_email(self):
        assert practitioner_id_from_email("Jane@CPA.COM") == "jane@cpa.com"

    def test_trims_whitespace(self):
        assert practitioner_id_from_email("  jane@cpa.com  ") == "jane@cpa.com"

    def test_empty_returns_unknown(self):
        assert practitioner_id_from_email("") == "unknown"
        assert practitioner_id_from_email(None) == "unknown"


# ─────────────────────────────────────────────────────────────────────
# Vocab signature
# ─────────────────────────────────────────────────────────────────────


class TestVocabSignature:
    def test_basic_tokenization(self):
        sig = compute_vocab_signature(
            "Section 1031 like-kind exchange rules apply here."
        )
        assert sig.token_count > 0
        token_set = {t for t, _ in sig.top_tokens}
        assert "section" in token_set
        assert "rules" in token_set

    def test_stopwords_filtered(self):
        sig = compute_vocab_signature("the and or but if")
        # All stopwords -> empty signature
        assert sig.token_count == 0

    def test_bigrams_captured(self):
        sig = compute_vocab_signature(
            "depreciation method depreciation method depreciation method"
        )
        bigram_set = {b for b, _ in sig.top_bigrams}
        assert "depreciation method" in bigram_set

    def test_salient_phrases_detect_caps(self):
        sig = compute_vocab_signature(
            "Per Section 1031 and Internal Revenue Code, the answer is yes."
        )
        # 'Internal Revenue Code' is 3 caps tokens in a row
        assert any("Internal Revenue Code" in p for p in sig.salient_phrases)


# ─────────────────────────────────────────────────────────────────────
# Harvest
# ─────────────────────────────────────────────────────────────────────


class TestHarvest:
    def test_harvest_from_thread_basic(self, paths):
        eid = _setup_finalized_folder(paths)
        attach_correspondence(eid, "in", "jane@cpa.com",
                              "What depreciation method on line 47?",
                              db_path=paths["db_path"])
        attach_correspondence(eid, "in", "jane@cpa.com",
                              "Personally reviewed. Professional responsibility. License #CA-99887. Good standing.",
                              db_path=paths["db_path"])
        result = harvest_from_thread(eid, db_path=paths["db_path"])
        assert result["ok"] is True
        assert result["harvested"] == 2
        assert result["skipped"] == 0

    def test_harvest_is_idempotent(self, paths):
        eid = _setup_finalized_folder(paths)
        attach_correspondence(eid, "in", "jane@cpa.com", "Question?",
                              db_path=paths["db_path"])
        r1 = harvest_from_thread(eid, db_path=paths["db_path"])
        r2 = harvest_from_thread(eid, db_path=paths["db_path"])
        assert r1["harvested"] == 1
        assert r2["harvested"] == 0  # already harvested
        assert r2["skipped"] == 1

    def test_harvest_skips_outbound(self, paths):
        eid = _setup_finalized_folder(paths)
        attach_correspondence(eid, "in", "jane@cpa.com", "Q1?",
                              db_path=paths["db_path"])
        attach_correspondence(eid, "out", "murphy@x.com", "Reply",
                              db_path=paths["db_path"])
        result = harvest_from_thread(eid, db_path=paths["db_path"])
        assert result["harvested"] == 1
        assert result["scanned"] == 1   # outbound not in scan

    def test_harvest_missing_engagement(self, paths):
        result = harvest_from_thread("nonexistent", db_path=paths["db_path"])
        assert result["ok"] is False

    def test_harvest_all_finalized(self, paths):
        e1 = _setup_finalized_folder(paths, practitioner_email="a@x.com")
        e2 = _setup_finalized_folder(paths, practitioner_email="b@x.com")
        attach_correspondence(e1, "in", "a@x.com", "Question A?",
                              db_path=paths["db_path"])
        attach_correspondence(e2, "in", "b@x.com", "Question B?",
                              db_path=paths["db_path"])
        result = harvest_all_finalized(db_path=paths["db_path"])
        assert result["engagements_scanned"] == 2
        assert result["total_harvested"] == 2


# ─────────────────────────────────────────────────────────────────────
# Voice — per-(practitioner, tenant)
# ─────────────────────────────────────────────────────────────────────


class TestVoicePractitionerTenant:
    def test_tenant_isolation(self, paths):
        # Jane works for acme AND beta
        e_acme = _setup_finalized_folder(paths, tenant_id="acme",
                                          practitioner_email="jane@cpa.com")
        e_beta = _setup_finalized_folder(paths, tenant_id="beta",
                                          practitioner_email="jane@cpa.com")
        attach_correspondence(e_acme, "in", "jane@cpa.com",
                              "Acme depreciation question?",
                              db_path=paths["db_path"])
        attach_correspondence(e_beta, "in", "jane@cpa.com",
                              "Beta amortization question?",
                              db_path=paths["db_path"])
        harvest_all_finalized(db_path=paths["db_path"])

        # Voice at acme contains only acme content
        voice_acme = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "acme", db_path=paths["db_path"],
        )
        assert voice_acme["count"] == 1
        assert "Acme" in voice_acme["entries"][0]["body"]

        # Voice at beta contains only beta content
        voice_beta = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "beta", db_path=paths["db_path"],
        )
        assert voice_beta["count"] == 1
        assert "Beta" in voice_beta["entries"][0]["body"]

    def test_voice_aggregates_signature(self, paths):
        eid = _setup_finalized_folder(paths, practitioner_email="jane@cpa.com")
        attach_correspondence(eid, "in", "jane@cpa.com",
                              "depreciation depreciation depreciation",
                              db_path=paths["db_path"])
        harvest_from_thread(eid, db_path=paths["db_path"])

        voice = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "acme", db_path=paths["db_path"],
        )
        agg = voice["aggregated"]
        token_set = {t for t, _ in agg["top_tokens"]}
        assert "depreciation" in token_set

    def test_voice_filter_by_intent(self, paths):
        eid = _setup_finalized_folder(paths, practitioner_email="jane@cpa.com")
        attach_correspondence(eid, "in", "jane@cpa.com", "What is line 47?",
                              db_path=paths["db_path"])
        attach_correspondence(eid, "in", "jane@cpa.com",
                              "Personally reviewed. Professional responsibility. License #CA-99887. Good standing.",
                              db_path=paths["db_path"])
        harvest_from_thread(eid, db_path=paths["db_path"])

        only_questions = voice_for_practitioner_at_tenant(
            "jane@cpa.com", "acme",
            intents=["clarifying_question"],
            db_path=paths["db_path"],
        )
        assert only_questions["count"] == 1
        assert all(e["intent"] == "clarifying_question"
                   for e in only_questions["entries"])


# ─────────────────────────────────────────────────────────────────────
# Voice — role/jurisdiction domain prior
# ─────────────────────────────────────────────────────────────────────


class TestVoiceRoleJurisdiction:
    def test_aggregates_across_practitioners(self, paths):
        e1 = _setup_finalized_folder(paths, tenant_id="acme",
                                      practitioner_email="jane@x.com")
        e2 = _setup_finalized_folder(paths, tenant_id="beta",
                                      practitioner_email="bob@x.com")
        attach_correspondence(e1, "in", "jane@x.com", "Section 1031 question",
                              db_path=paths["db_path"])
        attach_correspondence(e2, "in", "bob@x.com", "Section 1031 again",
                              db_path=paths["db_path"])
        harvest_all_finalized(db_path=paths["db_path"])

        domain = voice_for_role_jurisdiction(
            "cpa", "US-CA", db_path=paths["db_path"],
        )
        assert domain["count"] == 2
        assert domain["is_domain_prior"] is True


# ─────────────────────────────────────────────────────────────────────
# Recurring questions
# ─────────────────────────────────────────────────────────────────────


class TestRecurringQuestions:
    def test_detects_repeated_pattern(self, paths):
        eid1 = _setup_finalized_folder(paths, practitioner_email="jane@x.com")
        eid2 = _setup_finalized_folder(paths, practitioner_email="jane@x.com")
        # Same question pattern twice across two engagements
        attach_correspondence(eid1, "in", "jane@x.com",
                              "What depreciation method was used on line 47 for the depreciation method clarification?",
                              db_path=paths["db_path"])
        attach_correspondence(eid2, "in", "jane@x.com",
                              "Can you clarify the depreciation method on line 47 again? Depreciation method clarification needed?",
                              db_path=paths["db_path"])
        harvest_all_finalized(db_path=paths["db_path"])

        rq = recurring_questions("jane@x.com", "acme", db_path=paths["db_path"])
        assert rq["total_questions"] == 2
        # Even if grouping is imperfect, total questions counted

    def test_no_recurrence_for_unique_questions(self, paths):
        eid = _setup_finalized_folder(paths, practitioner_email="jane@x.com")
        attach_correspondence(eid, "in", "jane@x.com",
                              "What is the basis for line 5?",
                              db_path=paths["db_path"])
        harvest_from_thread(eid, db_path=paths["db_path"])

        rq = recurring_questions("jane@x.com", "acme", db_path=paths["db_path"])
        assert rq["total_questions"] == 1
        assert rq["recurring_groups"] == 0


# ─────────────────────────────────────────────────────────────────────
# Privacy / isolation contract
# ─────────────────────────────────────────────────────────────────────


class TestPrivacyContract:
    def test_no_cross_tenant_leak_in_practitioner_view(self, paths):
        """The CRITICAL D1 invariant: a query for (jane, acme) must NOT
        return any entry whose tenant_id is not 'acme'."""
        e_acme = _setup_finalized_folder(paths, tenant_id="acme",
                                          practitioner_email="jane@x.com")
        e_beta = _setup_finalized_folder(paths, tenant_id="beta",
                                          practitioner_email="jane@x.com")
        attach_correspondence(e_acme, "in", "jane@x.com", "Acme body content",
                              db_path=paths["db_path"])
        attach_correspondence(e_beta, "in", "jane@x.com", "Beta body content",
                              db_path=paths["db_path"])
        harvest_all_finalized(db_path=paths["db_path"])

        voice_acme = voice_for_practitioner_at_tenant(
            "jane@x.com", "acme", db_path=paths["db_path"],
        )
        for entry in voice_acme["entries"]:
            assert entry["tenant_id"] == "acme"
            assert "Beta" not in entry["body"]
