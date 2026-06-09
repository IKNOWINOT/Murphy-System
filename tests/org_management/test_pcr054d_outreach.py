"""PCR-054d — engagement_outreach.py regression suite."""
import json

import pytest

from src.engagement_folder import (
    FolderState,
    create_folder,
    get_folder,
    transition,
)
from src.engagement_outreach import (
    ComposedEmail,
    compose_engagement_request,
    send_engagement_request,
)
from src.engagement_rates import RateQuote


@pytest.fixture
def paths(tmp_path):
    return {
        "db_path":     str(tmp_path / "engagement_folders.db"),
        "browse_root": str(tmp_path / "engagements"),
    }


@pytest.fixture
def staged_folder(paths):
    """A folder that's been advanced to outreach_queued with a practitioner."""
    f = create_folder(
        tenant_id="acme_corp",
        role_id="cpa_main",
        artifact_type="tax_return",
        artifact_content="Form 1120 draft - net income $487,500",
        license_type_required="CPA",
        jurisdiction_required="US-CA",
        **paths,
    )
    transition(
        f.engagement_id,
        FolderState.OUTREACH_QUEUED,
        actor="test",
        reason="staged",
        update_fields={"practitioner_email": "jane.cpa@example.com"},
        db_path=paths["db_path"],
    )
    return f.engagement_id, paths


# ─────────────────────────────────────────────────────────────────────
# Pure compose
# ─────────────────────────────────────────────────────────────────────


class TestCompose:
    def test_compose_includes_engagement_id(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="draft body",
        )
        assert "eng_abc" in c.body
        assert c.to_addr == "cpa@example.com"

    def test_compose_includes_rate_citation(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="draft body",
            hours_estimated=8,
        )
        # 90th p CPA CA = 80.20 -> 8h = 641.60
        assert "$641.60" in c.body
        assert "BLS OEWS" in c.body
        assert "13-2011" in c.body

    def test_compose_includes_attestation_template(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="draft body",
        )
        # Required attestation phrases
        assert "personally reviewed" in c.body
        assert "good standing" in c.body
        assert "License #" in c.body
        assert "DECLINE" in c.body

    def test_compose_includes_draft_preview(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="Form 1120 net income $487,500",
        )
        assert "Form 1120" in c.body

    def test_compose_subject_says_engagement_request(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="",
        )
        assert "Engagement Request" in c.subject
        assert "tax_return" in c.subject

    def test_compose_from_name_includes_tenant(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme_corp",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="",
        )
        assert "acme_corp" in c.from_name
        assert "Murphy" in c.from_name

    def test_compose_unknown_license_raises(self):
        with pytest.raises(ValueError):
            compose_engagement_request(
                engagement_id="eng_abc",
                practitioner_email="cpa@example.com",
                tenant_id="acme",
                artifact_type="tax_return",
                license_type_required="Astrologer",
                jurisdiction_required="US-CA",
                draft_preview="",
            )

    def test_compose_attaches_rate_quote_obj(self):
        c = compose_engagement_request(
            engagement_id="eng_abc",
            practitioner_email="cpa@example.com",
            tenant_id="acme",
            artifact_type="tax_return",
            license_type_required="CPA",
            jurisdiction_required="US-CA",
            draft_preview="",
        )
        assert isinstance(c.quote, RateQuote)
        assert c.quote.usd_total == 641.60


# ─────────────────────────────────────────────────────────────────────
# Send path (dry_run)
# ─────────────────────────────────────────────────────────────────────


class TestSendDryRun:
    def test_send_dry_run_advances_state(self, staged_folder):
        eid, paths = staged_folder
        result = send_engagement_request(
            eid, dry_run=True, db_path=paths["db_path"],
        )
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["status"] == "dry_run"
        folder = get_folder(eid, db_path=paths["db_path"])
        assert folder.state is FolderState.AWAITING_ATTESTATION
        assert folder.rate_quote_usd == 641.60
        assert "bls:13-2011:p90:US-CA" in folder.rate_quote_source

    def test_send_dry_run_records_outbound_event(self, staged_folder):
        from src.engagement_folder import get_events
        eid, paths = staged_folder
        send_engagement_request(eid, dry_run=True, db_path=paths["db_path"])
        events = get_events(eid, db_path=paths["db_path"])
        outbound = [e for e in events if e["event_type"] == "outbound_email"]
        assert len(outbound) == 1
        assert outbound[0]["payload"]["dry_run"] is True
        assert outbound[0]["payload"]["to"] == "jane.cpa@example.com"
        assert outbound[0]["payload"]["rate_usd_total"] == 641.60

    def test_send_missing_folder_returns_error(self, paths):
        result = send_engagement_request("eng_nope", db_path=paths["db_path"])
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_send_without_practitioner_returns_error(self, paths):
        f = create_folder(
            tenant_id="t1", role_id="r1", artifact_type="tax_return",
            license_type_required="CPA", jurisdiction_required="US-CA",
            **paths,
        )
        # folder is in DRAFTING; no practitioner_email
        result = send_engagement_request(f.engagement_id, db_path=paths["db_path"])
        assert result["ok"] is False
        assert "practitioner_email" in result["error"]

    def test_send_without_license_fields_returns_error(self, paths):
        f = create_folder(
            tenant_id="t1", role_id="r1", artifact_type="tax_return",
            **paths,  # no license_type_required / jurisdiction_required
        )
        transition(
            f.engagement_id, FolderState.OUTREACH_QUEUED,
            update_fields={"practitioner_email": "x@example.com"},
            db_path=paths["db_path"],
        )
        result = send_engagement_request(f.engagement_id, db_path=paths["db_path"])
        assert result["ok"] is False
        assert "license_type_required" in result["error"] or "jurisdiction_required" in result["error"]

    def test_send_no_advance_state_flag(self, staged_folder):
        eid, paths = staged_folder
        send_engagement_request(
            eid, dry_run=True, advance_state=False,
            db_path=paths["db_path"],
        )
        folder = get_folder(eid, db_path=paths["db_path"])
        assert folder.state is FolderState.OUTREACH_QUEUED  # stayed put


# ─────────────────────────────────────────────────────────────────────
# Result shape
# ─────────────────────────────────────────────────────────────────────


class TestResultShape:
    def test_result_has_rate_quote_dict(self, staged_folder):
        eid, paths = staged_folder
        result = send_engagement_request(eid, dry_run=True, db_path=paths["db_path"])
        rq = result["rate_quote"]
        assert rq["usd_total"] == 641.60
        assert rq["source"] == "bls"
        assert rq["soc_code"] == "13-2011"

    def test_result_has_body_preview(self, staged_folder):
        eid, paths = staged_folder
        result = send_engagement_request(eid, dry_run=True, db_path=paths["db_path"])
        assert "Engagement" in result["body_preview"]
        assert len(result["body_preview"]) <= 400
