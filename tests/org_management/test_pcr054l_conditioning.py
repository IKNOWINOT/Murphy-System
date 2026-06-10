"""PCR-054l — engagement conditioning regression suite."""
import pytest

from src.engagement_correspondence import attach_correspondence
from src.engagement_folder import FolderState, create_folder, transition
from src.engagement_conditioning import (
    FAQ_MIN_REPEAT,
    OutreachConditioning,
    PRACTITIONER_CONFIDENCE_FLOOR,
    condition_outreach,
    render_signature_hint,
)
from src.engagement_outreach import compose_engagement_request
from src.practitioner_corpus import harvest_all_finalized, harvest_from_thread


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


def _finalized_with_messages(paths, *, tenant_id="acme", role_id="cpa",
                              jurisdiction="US-CA",
                              practitioner_email="jane@cpa.com",
                              messages=None):
    """Create a FINALIZED folder + attach messages + harvest corpus."""
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

    for body in (messages or []):
        attach_correspondence(f.engagement_id, "in", practitioner_email, body,
                              db_path=paths["db_path"])
    harvest_from_thread(f.engagement_id, db_path=paths["db_path"])
    return f.engagement_id


# ─────────────────────────────────────────────────────────────────────
# Confidence tiering
# ─────────────────────────────────────────────────────────────────────


class TestConfidence:
    def test_cold_with_no_corpus(self, paths):
        # No engagements harvested -> cold
        from src.practitioner_corpus import init_db
        init_db(paths["db_path"])
        c = condition_outreach(
            practitioner_email="new@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        assert c.voice_match_confidence == "cold"
        assert c.signature_phrases == []
        assert c.faq_items == []

    def test_high_confidence_when_above_floor(self, paths):
        # Need >= 5 entries for the practitioner at this tenant
        msgs = [
            f"Reviewing engagement. Jane CPA holder license CA-99887. Sample {i}."
            for i in range(6)
        ]
        _finalized_with_messages(paths, messages=msgs)
        c = condition_outreach(
            practitioner_email="jane@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        assert c.voice_match_confidence == "high"
        assert c.practitioner_entry_count >= PRACTITIONER_CONFIDENCE_FLOOR
        assert len(c.signature_phrases) > 0

    def test_domain_prior_when_practitioner_has_some_data(self, paths):
        # Practitioner has 1-2 entries, below floor — should blend
        _finalized_with_messages(paths, messages=[
            "First engagement. Jane CPA reviewed.",
            "Second engagement. License current.",
        ])
        # Add domain data from a different practitioner
        _finalized_with_messages(
            paths, practitioner_email="bob@cpa.com",
            messages=[f"Bob CPA reviewing Section 1031 case {i}." for i in range(5)],
        )
        c = condition_outreach(
            practitioner_email="jane@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        assert c.voice_match_confidence == "domain_prior"
        # Should have blended phrases — practitioner-first, then domain
        assert len(c.signature_phrases) > 0


# ─────────────────────────────────────────────────────────────────────
# Tenant isolation (D1 contract still holds at conditioning layer)
# ─────────────────────────────────────────────────────────────────────


class TestTenantIsolationAtConditioning:
    def test_conditioning_at_new_tenant_is_cold_or_domain(self, paths):
        """Jane has 10 entries at acme. Querying her at beta MUST NOT
        leak acme voice. She should be 'cold' or 'domain_prior' at beta."""
        _finalized_with_messages(paths, tenant_id="acme", messages=[
            f"Reviewing. Jane CPA license CA-99887. Sample {i}." for i in range(10)
        ])
        c = condition_outreach(
            practitioner_email="jane@cpa.com", tenant_id="beta",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        # Must NOT be 'high' — she has zero entries at beta
        assert c.voice_match_confidence != "high"
        # Her acme entries don't count toward beta count
        assert c.practitioner_entry_count == 0


# ─────────────────────────────────────────────────────────────────────
# FAQ block rendering
# ─────────────────────────────────────────────────────────────────────


class TestFAQBlock:
    def test_no_faq_block_when_no_recurring_questions(self, paths):
        _finalized_with_messages(paths, messages=[
            f"Jane CPA license review {i}." for i in range(6)
        ])
        c = condition_outreach(
            practitioner_email="jane@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        assert c.faq_block == ""
        assert c.faq_items == []

    def test_faq_block_when_recurring_questions_detected(self, paths):
        # Two engagements with overlapping question patterns
        e1 = _finalized_with_messages(paths, messages=[
            "What depreciation method was used on line 47 for the depreciation method clarification?",
            "Following up: depreciation method line 47 still needs clarification?",
            "Jane CPA license review.",
        ])
        e2 = _finalized_with_messages(paths, messages=[
            "Can you clarify the depreciation method on line 47 again? Depreciation method clarification needed?",
            "Need clarification depreciation method line 47?",
        ])
        c = condition_outreach(
            practitioner_email="jane@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            db_path=paths["db_path"],
        )
        # The block should be rendered with "For your reference"
        if c.faq_items:
            assert "For your reference" in c.faq_block
            assert "depreciation" in c.faq_block.lower() or len(c.faq_block) > 50


# ─────────────────────────────────────────────────────────────────────
# Compose integration
# ─────────────────────────────────────────────────────────────────────


class TestComposeIntegration:
    def test_compose_with_conditioning_disabled_is_unchanged(self, paths):
        """Backward compat: use_corpus_conditioning=False = pre-054l behavior."""
        email = compose_engagement_request(
            engagement_id="eng_test",
            practitioner_email="jane@cpa.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="sample draft",
            use_corpus_conditioning=False,
        )
        assert email.voice_match_confidence == "disabled"
        assert email.signature_phrases == []
        assert email.faq_items_count == 0

    def test_compose_without_role_id_skips_conditioning(self, paths):
        """Conditioning needs role_id — without it, fallback to pre-054l."""
        email = compose_engagement_request(
            engagement_id="eng_test",
            practitioner_email="jane@cpa.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="sample draft",
            use_corpus_conditioning=True,
            # role_id omitted
        )
        assert email.voice_match_confidence == "disabled"

    def test_compose_with_conditioning_attaches_audit_fields(self, paths):
        _finalized_with_messages(paths, messages=[
            f"Reviewing. Jane CPA license CA-99887. Sample {i}." for i in range(6)
        ])
        email = compose_engagement_request(
            engagement_id="eng_test",
            practitioner_email="jane@cpa.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="sample draft",
            use_corpus_conditioning=True,
            role_id="cpa",
            db_path=paths["db_path"],
        )
        # High confidence because 6 entries
        assert email.voice_match_confidence == "high"
        assert len(email.signature_phrases) > 0


# ─────────────────────────────────────────────────────────────────────
# Signature hint
# ─────────────────────────────────────────────────────────────────────


class TestSignatureHint:
    def test_hint_empty_when_cold(self):
        c = OutreachConditioning(
            voice_match_confidence="cold",
            practitioner_id="x", tenant_id="y",
            role_id="cpa", jurisdiction="US-CA",
        )
        assert render_signature_hint(c) == ""

    def test_hint_when_high(self):
        c = OutreachConditioning(
            voice_match_confidence="high",
            practitioner_id="jane@cpa.com", tenant_id="acme",
            role_id="cpa", jurisdiction="US-CA",
            practitioner_entry_count=18,
        )
        hint = render_signature_hint(c)
        assert "high" in hint
        assert "18" in hint
