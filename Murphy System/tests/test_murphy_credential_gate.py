"""
Tests for Murphy Credential Gate (Subsystem 2).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.murphy_credential_gate import (
    ApprovalStatus,
    ApprovalWorkflow,
    CredentialGatedApproval,
    CredentialRegistry,
    CredentialStatus,
    CredentialType,
    CredentialVerifier,
    EStampEngine,
    ProfessionalCredential,
    WorkflowStep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_credential(
    credential_type: CredentialType = CredentialType.PE,
    status: CredentialStatus = CredentialStatus.ACTIVE,
    expires_days: int = 365,
    jurisdiction: str = "CA",
) -> ProfessionalCredential:
    exp = (datetime.now(timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%d")
    iss = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ProfessionalCredential(
        holder_name="John Engineer",
        holder_email="john@example.com",
        credential_type=credential_type,
        license_number="PE-12345",
        issuing_authority="State Board",
        jurisdiction=jurisdiction,
        issued_date=iss,
        expiration_date=exp,
        status=status,
    )


@pytest.fixture
def registry():
    return CredentialRegistry()


@pytest.fixture
def verifier(registry):
    return CredentialVerifier(registry)


@pytest.fixture
def e_stamp_engine(registry, verifier):
    return EStampEngine(registry, verifier)


@pytest.fixture
def gated_approval(registry, verifier, e_stamp_engine):
    return CredentialGatedApproval(registry, verifier, e_stamp_engine)


@pytest.fixture
def active_pe(registry):
    cred = make_credential()
    registry.register(cred)
    return cred


# ---------------------------------------------------------------------------
# Credential Registry
# ---------------------------------------------------------------------------

class TestCredentialRegistry:

    def test_register_and_get(self, registry):
        cred = make_credential()
        cid = registry.register(cred)
        fetched = registry.get(cid)
        assert fetched is not None
        assert fetched.credential_type == CredentialType.PE

    def test_get_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_find_by_email(self, registry):
        cred = make_credential()
        registry.register(cred)
        results = registry.find_by_email("john@example.com")
        assert len(results) == 1

    def test_find_by_type(self, registry):
        cred_pe = make_credential(CredentialType.PE)
        cred_cpa = make_credential(CredentialType.CPA)
        registry.register(cred_pe)
        registry.register(cred_cpa)
        pe_list = registry.find_by_type(CredentialType.PE)
        assert len(pe_list) == 1
        assert pe_list[0].credential_type == CredentialType.PE

    def test_revoke(self, registry):
        cred = make_credential()
        cid = registry.register(cred)
        assert registry.revoke(cid) is True
        assert registry.get(cid).status == CredentialStatus.REVOKED

    def test_revoke_nonexistent(self, registry):
        assert registry.revoke("bad-id") is False

    def test_list_all(self, registry):
        registry.register(make_credential())
        registry.register(make_credential(CredentialType.CPA))
        assert len(registry.list_all()) == 2


# ---------------------------------------------------------------------------
# Credential Verifier
# ---------------------------------------------------------------------------

class TestCredentialVerifier:

    def test_active_credential(self, registry, verifier, active_pe):
        assert verifier.is_active(active_pe.credential_id) is True

    def test_expired_credential(self, registry, verifier):
        cred = make_credential(expires_days=-1)
        registry.register(cred)
        assert verifier.is_active(cred.credential_id) is False

    def test_revoked_credential(self, registry, verifier):
        cred = make_credential(status=CredentialStatus.REVOKED)
        registry.register(cred)
        assert verifier.is_active(cred.credential_id) is False

    def test_missing_credential(self, verifier):
        assert verifier.is_active("nonexistent") is False

    def test_verify_for_discipline_success(self, registry, verifier, active_pe):
        result = verifier.verify_for_discipline(
            active_pe.credential_id, [CredentialType.PE], jurisdiction="CA"
        )
        assert result["valid"] is True

    def test_verify_wrong_type(self, registry, verifier, active_pe):
        result = verifier.verify_for_discipline(
            active_pe.credential_id, [CredentialType.CPA]
        )
        assert result["valid"] is False

    def test_verify_wrong_jurisdiction(self, registry, verifier, active_pe):
        result = verifier.verify_for_discipline(
            active_pe.credential_id, [CredentialType.PE], jurisdiction="TX"
        )
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# E-Stamp Engine
# ---------------------------------------------------------------------------

class TestEStampEngine:

    def test_create_stamp(self, e_stamp_engine, active_pe):
        doc = b"Engineering document content"
        stamp = e_stamp_engine.create_stamp(active_pe.credential_id, doc)
        assert stamp is not None
        assert stamp.credential_id == active_pe.credential_id
        assert len(stamp.document_hash) == 64  # SHA-256 hex

    def test_stamp_has_svg(self, e_stamp_engine, active_pe):
        stamp = e_stamp_engine.create_stamp(active_pe.credential_id, b"doc")
        assert "<svg" in stamp.seal_image_svg
        assert "PE" in stamp.seal_image_svg

    def test_verify_stamp_valid(self, e_stamp_engine, active_pe):
        doc = b"Document to stamp"
        stamp = e_stamp_engine.create_stamp(active_pe.credential_id, doc)
        assert e_stamp_engine.verify_stamp(stamp, doc) is True

    def test_verify_stamp_tampered(self, e_stamp_engine, active_pe):
        doc = b"Original document"
        stamp = e_stamp_engine.create_stamp(active_pe.credential_id, doc)
        assert e_stamp_engine.verify_stamp(stamp, b"Tampered document") is False

    def test_stamp_inactive_credential(self, registry, verifier, e_stamp_engine):
        cred = make_credential(status=CredentialStatus.REVOKED)
        registry.register(cred)
        stamp = e_stamp_engine.create_stamp(cred.credential_id, b"doc")
        assert stamp is None

    def test_stamp_missing_credential(self, e_stamp_engine):
        stamp = e_stamp_engine.create_stamp("bad-id", b"doc")
        assert stamp is None


# ---------------------------------------------------------------------------
# Credential-Gated Approval
# ---------------------------------------------------------------------------

class TestCredentialGatedApproval:

    def test_approval_with_valid_credential(self, gated_approval, active_pe):
        doc = b"Engineering drawing"
        record = gated_approval.request_approval(
            document_id="doc-001",
            document_bytes=doc,
            approver_credential_id=active_pe.credential_id,
            required_credential_types=[CredentialType.PE],
        )
        assert record.approval_status == ApprovalStatus.APPROVED
        assert record.e_stamp is not None

    def test_approval_denied_wrong_type(self, gated_approval, active_pe):
        record = gated_approval.request_approval(
            document_id="doc-002",
            document_bytes=b"Financial document",
            approver_credential_id=active_pe.credential_id,
            required_credential_types=[CredentialType.CPA],
        )
        assert record.approval_status == ApprovalStatus.REQUIRES_CREDENTIAL

    def test_approval_denied_no_credential(self, gated_approval):
        record = gated_approval.request_approval(
            document_id="doc-003",
            document_bytes=b"doc",
            approver_credential_id="nonexistent",
            required_credential_types=[CredentialType.PE],
        )
        assert record.approval_status == ApprovalStatus.REQUIRES_CREDENTIAL

    def test_list_approvals(self, gated_approval, active_pe):
        doc = b"doc"
        gated_approval.request_approval("doc-1", doc, active_pe.credential_id, [CredentialType.PE])
        gated_approval.request_approval("doc-2", doc, active_pe.credential_id, [CredentialType.PE])
        assert len(gated_approval.list_approvals()) == 2

    def test_list_approvals_by_document(self, gated_approval, active_pe):
        doc = b"doc"
        gated_approval.request_approval("doc-1", doc, active_pe.credential_id, [CredentialType.PE])
        gated_approval.request_approval("doc-2", doc, active_pe.credential_id, [CredentialType.PE])
        assert len(gated_approval.list_approvals("doc-1")) == 1

    def test_get_approval_by_id(self, gated_approval, active_pe):
        record = gated_approval.request_approval(
            "doc-x", b"doc", active_pe.credential_id, [CredentialType.PE]
        )
        fetched = gated_approval.get_approval(record.approval_id)
        assert fetched is not None
        assert fetched.approval_id == record.approval_id


# ---------------------------------------------------------------------------
# Approval Workflow
# ---------------------------------------------------------------------------

class TestApprovalWorkflow:

    def test_workflow_creation(self):
        wf = ApprovalWorkflow(
            workflow_id="wf-1",
            document_id="doc-1",
            steps=[
                WorkflowStep("s1", "drawn_by", [CredentialType.PE]),
                WorkflowStep("s2", "checked_by", [CredentialType.PE]),
            ],
        )
        assert not wf.is_complete()
        assert wf.current_step().role == "drawn_by"

    def test_complete_steps(self):
        wf = ApprovalWorkflow(
            workflow_id="wf-2",
            document_id="doc-2",
            steps=[
                WorkflowStep("s1", "drawn_by", [CredentialType.PE]),
                WorkflowStep("s2", "checked_by", [CredentialType.PE]),
            ],
        )
        wf.complete_step("s1", "approval-id-1")
        assert wf.current_step().role == "checked_by"
        wf.complete_step("s2", "approval-id-2")
        assert wf.is_complete()

    def test_workflow_summary(self):
        wf = ApprovalWorkflow(
            workflow_id="wf-3",
            document_id="doc-3",
            steps=[WorkflowStep("s1", "drawn_by", [CredentialType.PE])],
        )
        summary = wf.get_summary()
        assert summary["total_steps"] == 1
        assert summary["completed_steps"] == 0
        assert summary["is_complete"] is False

    def test_complete_nonexistent_step(self):
        wf = ApprovalWorkflow(
            workflow_id="wf-4",
            document_id="doc-4",
            steps=[WorkflowStep("s1", "drawn_by", [CredentialType.PE])],
        )
        assert wf.complete_step("nonexistent", "appr-1") is False
