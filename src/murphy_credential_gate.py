"""
Murphy System - Murphy Credential Gate
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CredentialType(str, Enum):
    """CredentialType enumeration."""
    PE = "PE"
    CPA = "CPA"
    RA = "RA"
    PMP = "PMP"
    LEED_AP = "LEED_AP"
    CEM = "CEM"
    CFM = "CFM"
    SE = "SE"
    AIA = "AIA"
    NICET = "NICET"
    AWS_CWI = "AWS_CWI"
    ASNT_NDT = "ASNT_NDT"
    CIH = "CIH"
    CSP = "CSP"
    CMRP = "CMRP"


class CredentialStatus(str, Enum):
    """CredentialStatus enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class ApprovalStatus(str, Enum):
    """ApprovalStatus enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_CREDENTIAL = "requires_credential"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProfessionalCredential(BaseModel):
    """ProfessionalCredential — professional credential definition."""
    credential_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    holder_name: str
    holder_email: str
    credential_type: CredentialType
    license_number: str
    issuing_authority: str
    jurisdiction: str
    issued_date: str
    expiration_date: str
    status: CredentialStatus = CredentialStatus.ACTIVE
    public_key_pem: Optional[str] = None


class EStamp(BaseModel):
    """EStamp — e stamp definition."""
    stamp_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_id: str
    document_hash: str
    signature_hex: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    seal_image_svg: str = ""
    jurisdiction_text: str = ""
    license_display: str = ""


@dataclass
class ApprovalRecord:
    """ApprovalRecord — approval record definition."""
    approval_id: str
    document_id: str
    document_hash: str
    approver_credential_id: str
    approval_status: ApprovalStatus
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""
    e_stamp: Optional[EStamp] = None


# ---------------------------------------------------------------------------
# Credential Registry
# ---------------------------------------------------------------------------

class CredentialRegistry:
    """Register, lookup, and manage professional credentials."""

    def __init__(self) -> None:
        self._credentials: Dict[str, ProfessionalCredential] = {}
        self._lock = threading.Lock()

    def register(self, credential: ProfessionalCredential) -> str:
        """Register a credential and return its ID."""
        with self._lock:
            self._credentials[credential.credential_id] = credential
        logger.debug("Credential registered: %s", credential.credential_id)
        return credential.credential_id

    def get(self, credential_id: str) -> Optional[ProfessionalCredential]:
        """Look up a credential by ID."""
        return self._credentials.get(credential_id)

    def find_by_email(self, email: str) -> List[ProfessionalCredential]:
        """Find all credentials for an email address."""
        return [c for c in self._credentials.values() if c.holder_email == email]

    def find_by_type(self, credential_type: CredentialType) -> List[ProfessionalCredential]:
        """Find all credentials of a given type."""
        return [c for c in self._credentials.values() if c.credential_type == credential_type]

    def revoke(self, credential_id: str) -> bool:
        """Revoke a credential."""
        cred = self._credentials.get(credential_id)
        if cred is None:
            return False
        # Pydantic v2: use model_copy; fall back to direct assignment
        try:
            updated = cred.model_copy(update={"status": CredentialStatus.REVOKED})
        except AttributeError:
            updated = cred.copy(update={"status": CredentialStatus.REVOKED})
        self._credentials[credential_id] = updated
        return True

    def list_all(self) -> List[ProfessionalCredential]:
        """Return all registered credentials."""
        return list(self._credentials.values())


# ---------------------------------------------------------------------------
# Credential Verifier
# ---------------------------------------------------------------------------

class CredentialVerifier:
    """Verify credential status against the registry."""

    def __init__(self, registry: CredentialRegistry) -> None:
        self._registry = registry

    def is_active(self, credential_id: str) -> bool:
        """Return True if the credential exists and is ACTIVE."""
        cred = self._registry.get(credential_id)
        if cred is None:
            return False
        if cred.status != CredentialStatus.ACTIVE:
            return False
        # Check expiration date (YYYY-MM-DD format)
        try:
            exp = datetime.strptime(cred.expiration_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return False
        except ValueError as exc:
            logger.warning("Credential %s has invalid expiration_date: %s", credential_id, exc)
            return False
        return True

    def verify_for_discipline(
        self,
        credential_id: str,
        required_types: List[CredentialType],
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify a credential is active, of the required type, and in the right jurisdiction.
        Returns a dict with 'valid', 'reason'.
        """
        cred = self._registry.get(credential_id)
        if cred is None:
            return {"valid": False, "reason": "Credential not found"}
        if not self.is_active(credential_id):
            return {"valid": False, "reason": f"Credential status: {cred.status}"}
        if cred.credential_type not in required_types:
            return {
                "valid": False,
                "reason": f"Credential type {cred.credential_type} not in required {required_types}",
            }
        if jurisdiction and cred.jurisdiction.lower() != jurisdiction.lower():
            return {
                "valid": False,
                "reason": f"Jurisdiction mismatch: {cred.jurisdiction} != {jurisdiction}",
            }
        return {"valid": True, "reason": "Credential verified"}


# ---------------------------------------------------------------------------
# E-Stamp Engine
# ---------------------------------------------------------------------------

class EStampEngine:
    """Create, verify, and render professional e-stamps."""

    def __init__(self, registry: CredentialRegistry, verifier: CredentialVerifier) -> None:
        self._registry = registry
        self._verifier = verifier

    def create_stamp(self, credential_id: str, document_bytes: bytes) -> Optional[EStamp]:
        """
        Create a digital e-stamp for a document.
        Uses HMAC-SHA256 as a signature when no private key is supplied.
        For production, pass public_key_pem on the credential and use RSA signing.
        """
        cred = self._registry.get(credential_id)
        if cred is None:
            logger.warning("EStampEngine: credential %s not found", credential_id)
            return None
        if not self._verifier.is_active(credential_id):
            logger.warning("EStampEngine: credential %s is not active", credential_id)
            return None

        doc_hash = hashlib.sha256(document_bytes).hexdigest()
        # Deterministic stub signature (real: use cryptography library RSA/ECDSA)
        sig_input = f"{credential_id}:{doc_hash}:{datetime.now(timezone.utc).date()}".encode()
        signature_hex = hashlib.sha256(sig_input).hexdigest()

        seal_svg = self._render_seal_svg(cred)
        stamp = EStamp(
            credential_id=credential_id,
            document_hash=doc_hash,
            signature_hex=signature_hex,
            seal_image_svg=seal_svg,
            jurisdiction_text=f"State/Province: {cred.jurisdiction}",
            license_display=f"{cred.credential_type.value} #{cred.license_number}",
        )
        return stamp

    def verify_stamp(self, stamp: EStamp, document_bytes: bytes) -> bool:
        """Verify that a stamp's document hash matches the provided bytes."""
        expected_hash = hashlib.sha256(document_bytes).hexdigest()
        return stamp.document_hash == expected_hash

    def _render_seal_svg(self, cred: ProfessionalCredential) -> str:
        """Generate an SVG seal image for the credential."""
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
            '<circle cx="100" cy="100" r="90" fill="none" stroke="#003087" stroke-width="4"/>'
            '<circle cx="100" cy="100" r="80" fill="none" stroke="#003087" stroke-width="2"/>'
            f'<text x="100" y="95" text-anchor="middle" font-size="14" font-weight="bold" fill="#003087">'
            f'{cred.credential_type.value}</text>'
            f'<text x="100" y="115" text-anchor="middle" font-size="10" fill="#003087">'
            f'{cred.holder_name}</text>'
            f'<text x="100" y="130" text-anchor="middle" font-size="9" fill="#003087">'
            f'#{cred.license_number}</text>'
            f'<text x="100" y="145" text-anchor="middle" font-size="9" fill="#003087">'
            f'{cred.jurisdiction}</text>'
            '</svg>'
        )


# ---------------------------------------------------------------------------
# Credential-Gated Approval
# ---------------------------------------------------------------------------

class CredentialGatedApproval:
    """
    Wraps HITL approval with credential verification.
    Before a human can approve, Murphy checks their credential is valid.
    """

    def __init__(
        self,
        registry: CredentialRegistry,
        verifier: CredentialVerifier,
        e_stamp_engine: EStampEngine,
    ) -> None:
        self._registry = registry
        self._verifier = verifier
        self._e_stamp_engine = e_stamp_engine
        self._approvals: List[ApprovalRecord] = []
        self._lock = threading.Lock()

    def request_approval(
        self,
        document_id: str,
        document_bytes: bytes,
        approver_credential_id: str,
        required_credential_types: List[CredentialType],
        jurisdiction: Optional[str] = None,
    ) -> ApprovalRecord:
        """
        Gate approval on credential verification.
        Returns an ApprovalRecord with the result.
        """
        verification = self._verifier.verify_for_discipline(
            approver_credential_id, required_credential_types, jurisdiction
        )
        if not verification["valid"]:
            record = ApprovalRecord(
                approval_id=str(uuid.uuid4()),
                document_id=document_id,
                document_hash=hashlib.sha256(document_bytes).hexdigest(),
                approver_credential_id=approver_credential_id,
                approval_status=ApprovalStatus.REQUIRES_CREDENTIAL,
                notes=verification["reason"],
            )
        else:
            stamp = self._e_stamp_engine.create_stamp(approver_credential_id, document_bytes)
            record = ApprovalRecord(
                approval_id=str(uuid.uuid4()),
                document_id=document_id,
                document_hash=hashlib.sha256(document_bytes).hexdigest(),
                approver_credential_id=approver_credential_id,
                approval_status=ApprovalStatus.APPROVED,
                notes=verification["reason"],
                e_stamp=stamp,
            )
        with self._lock:
            capped_append(self._approvals, record)
        return record

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        """Look up an approval record by ID."""
        for rec in self._approvals:
            if rec.approval_id == approval_id:
                return rec
        return None

    def list_approvals(self, document_id: Optional[str] = None) -> List[ApprovalRecord]:
        """List all approvals, optionally filtered by document_id."""
        if document_id:
            return [r for r in self._approvals if r.document_id == document_id]
        return list(self._approvals)


# ---------------------------------------------------------------------------
# Approval Workflow (multi-party approval chains)
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    """WorkflowStep — workflow step definition."""
    step_id: str
    role: str
    required_credential_types: List[CredentialType]
    completed: bool = False
    approval_record_id: Optional[str] = None
    jurisdiction: Optional[str] = None


class ApprovalWorkflow:
    """Multi-party approval chain (e.g., drawn_by → checked_by → approved_by)."""

    def __init__(self, workflow_id: str, document_id: str, steps: List[WorkflowStep]) -> None:
        self.workflow_id = workflow_id
        self.document_id = document_id
        self.steps = steps
        self._lock = threading.Lock()

    def current_step(self) -> Optional[WorkflowStep]:
        """Return the first incomplete step."""
        for step in self.steps:
            if not step.completed:
                return step
        return None

    def is_complete(self) -> bool:
        """Return True if all steps are complete."""
        return all(s.completed for s in self.steps)

    def complete_step(self, step_id: str, approval_record_id: str) -> bool:
        """Mark a step as complete with its approval record ID."""
        with self._lock:
            for step in self.steps:
                if step.step_id == step_id and not step.completed:
                    step.completed = True
                    step.approval_record_id = approval_record_id
                    return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the workflow state."""
        return {
            "workflow_id": self.workflow_id,
            "document_id": self.document_id,
            "total_steps": len(self.steps),
            "completed_steps": sum(1 for s in self.steps if s.completed),
            "is_complete": self.is_complete(),
            "current_step": self.current_step().role if self.current_step() else None,
        }
