# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
TOS Acceptance Gate — Murphy System

Provides a Human-in-the-Loop gate that MUST be passed before Murphy can
check any "I Agree" / "Accept Terms" checkbox on a third-party provider's
signup page.  Murphy is the automation tool; the human is the legal party
accepting the terms.

Design Principles:
  - NEVER auto-accept TOS — always wait for explicit human approval
  - Full audit trail: every acceptance/rejection logged with timestamp,
    provider, user identity, TOS URL, and liability note
  - Thread-safe with threading.Lock
  - Bounded audit log via capped_append (CWE-770)

Follows the HITLApprovalGate pattern from environment_setup_agent.py and
the format_approval_request pattern from integration_engine/hitl_approval.py.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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
# Credential collection HITL gate — public surface used by KeyHarvester
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_AUDIT_LOG = 5_000

_DEFAULT_LIABILITY_NOTE = (
    "By approving this request you — the human operator — personally accept "
    "the provider's Terms of Service, Privacy Policy, and Acceptable Use "
    "Policy on your own behalf.  Murphy System is the automation tool; "
    "it bears no legal responsibility for third-party agreements.  "
    "Your approval constitutes your legal acceptance."
)


# ---------------------------------------------------------------------------
# Provider TOS registry
# ---------------------------------------------------------------------------

@dataclass
class ProviderTOS:
    """Metadata for a single provider's Terms of Service."""

    provider_name: str
    tos_url: str
    privacy_url: str
    acceptable_use_url: str = ""
    data_processing_url: str = ""


#: Registry mapping provider key → ProviderTOS.
#: Keep URLs current with each provider's actual legal pages.
PROVIDER_TOS_REGISTRY: Dict[str, ProviderTOS] = {
    "groq": ProviderTOS(
        provider_name="Groq",
        tos_url="https://groq.com/terms-of-use/",
        privacy_url="https://groq.com/privacy-policy/",
    ),
    "openai": ProviderTOS(
        provider_name="OpenAI",
        tos_url="https://openai.com/policies/terms-of-use/",
        privacy_url="https://openai.com/policies/privacy-policy/",
    ),
    "anthropic": ProviderTOS(
        provider_name="Anthropic",
        tos_url="https://www.anthropic.com/legal/consumer-terms",
        privacy_url="https://www.anthropic.com/legal/privacy",
    ),
    "elevenlabs": ProviderTOS(
        provider_name="ElevenLabs",
        tos_url="https://elevenlabs.io/terms-of-service",
        privacy_url="https://elevenlabs.io/privacy-policy",
    ),
    "sendgrid": ProviderTOS(
        provider_name="SendGrid (Twilio)",
        tos_url="https://www.twilio.com/en-us/legal/tos",
        privacy_url="https://www.twilio.com/en-us/legal/privacy",
    ),
    "stripe": ProviderTOS(
        provider_name="Stripe",
        tos_url="https://stripe.com/legal/ssa",
        privacy_url="https://stripe.com/privacy",
    ),
    "twilio": ProviderTOS(
        provider_name="Twilio",
        tos_url="https://www.twilio.com/en-us/legal/tos",
        privacy_url="https://www.twilio.com/en-us/legal/privacy",
    ),
    "heygen": ProviderTOS(
        provider_name="HeyGen",
        tos_url="https://www.heygen.com/terms-of-service",
        privacy_url="https://www.heygen.com/privacy-policy",
    ),
    "tavus": ProviderTOS(
        provider_name="Tavus",
        tos_url="https://www.tavus.io/terms-of-service",
        privacy_url="https://www.tavus.io/privacy-policy",
    ),
    "vapi": ProviderTOS(
        provider_name="Vapi",
        tos_url="https://vapi.ai/terms",
        privacy_url="https://vapi.ai/privacy",
    ),
    "hubspot": ProviderTOS(
        provider_name="HubSpot",
        tos_url="https://legal.hubspot.com/terms-of-service",
        privacy_url="https://legal.hubspot.com/privacy-policy",
    ),
    "shopify": ProviderTOS(
        provider_name="Shopify",
        tos_url="https://www.shopify.com/legal/terms",
        privacy_url="https://www.shopify.com/legal/privacy",
    ),
    "coinbase": ProviderTOS(
        provider_name="Coinbase",
        tos_url="https://www.coinbase.com/legal/user_agreement",
        privacy_url="https://www.coinbase.com/legal/privacy",
    ),
    "github": ProviderTOS(
        provider_name="GitHub",
        tos_url="https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
        privacy_url="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
    ),
    "slack": ProviderTOS(
        provider_name="Slack",
        tos_url="https://slack.com/terms-of-service",
        privacy_url="https://slack.com/privacy-policy",
    ),
}


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------

class TOSAcceptanceStatus(str, Enum):
    """Lifecycle states for a TOS approval request."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass
class TOSApprovalRequest:
    """A single TOS approval request queued for human review."""

    request_id: str
    provider_key: str
    provider_name: str
    tos_url: str
    privacy_url: str
    acceptable_use_url: str = ""
    screenshot_path: Optional[str] = None
    status: TOSAcceptanceStatus = TOSAcceptanceStatus.PENDING
    accepted_by: Optional[str] = None
    accepted_at: Optional[str] = None
    liability_note: str = _DEFAULT_LIABILITY_NOTE
    audit_entry: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class TOSAcceptanceGate:
    """HITL gate for third-party Terms-of-Service acceptance.

    Murphy NEVER auto-accepts any TOS.  Every provider signup MUST pause here
    and wait for an explicit human approval before any checkbox is clicked.

    Usage::

        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq", screenshot_path="/tmp/groq.png")
        # ... HITL UI shows the pending request ...
        gate.approve(req.request_id, approved_by="alice@example.com")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, TOSApprovalRequest] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_approval(
        self,
        provider_key: str,
        screenshot_path: Optional[str] = None,
    ) -> TOSApprovalRequest:
        """Create a new TOS approval request and add it to the pending queue.

        Args:
            provider_key: Key into PROVIDER_TOS_REGISTRY (e.g. ``"groq"``).
            screenshot_path: Optional filesystem path to a page screenshot.

        Returns:
            The newly created :class:`TOSApprovalRequest` (status=PENDING).

        Raises:
            KeyError: If *provider_key* is not in PROVIDER_TOS_REGISTRY.
        """
        tos = PROVIDER_TOS_REGISTRY[provider_key]
        request_id = f"tos-{uuid.uuid4().hex[:16]}"
        req = TOSApprovalRequest(
            request_id=request_id,
            provider_key=provider_key,
            provider_name=tos.provider_name,
            tos_url=tos.tos_url,
            privacy_url=tos.privacy_url,
            acceptable_use_url=tos.acceptable_use_url,
            screenshot_path=screenshot_path,
        )
        with self._lock:
            self._requests[request_id] = req
        logger.info(
            "TOS approval requested for provider '%s' (request_id=%s)",
            provider_key,
            request_id,
        )
        return req

    def approve(self, request_id: str, approved_by: str) -> bool:
        """Mark a pending request as ACCEPTED.

        Records a full audit entry including the provider, TOS URL, privacy
        URL, timestamp, approver identity, and the liability note transferring
        legal responsibility to the human operator.

        Args:
            request_id: ID returned by :meth:`request_approval`.
            approved_by: Identity of the approving human (email / username).

        Returns:
            ``True`` if the request was found and transitioned; ``False`` if
            the request does not exist or is not in PENDING state.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != TOSAcceptanceStatus.PENDING:
                return False
            req.status = TOSAcceptanceStatus.ACCEPTED
            req.accepted_by = approved_by
            req.accepted_at = datetime.now(timezone.utc).isoformat()
            entry = self._build_audit_entry(req, action="accepted", actor=approved_by)
            req.audit_entry = entry
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)
        logger.info(
            "TOS for '%s' ACCEPTED by '%s' (request_id=%s)",
            req.provider_key,
            approved_by,
            request_id,
        )
        return True

    def reject(self, request_id: str, rejected_by: str, reason: str = "") -> bool:
        """Mark a pending request as REJECTED.

        Args:
            request_id: ID returned by :meth:`request_approval`.
            rejected_by: Identity of the rejecting human.
            reason: Optional human-readable reason for rejection.

        Returns:
            ``True`` if found and transitioned; ``False`` otherwise.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != TOSAcceptanceStatus.PENDING:
                return False
            req.status = TOSAcceptanceStatus.REJECTED
            req.accepted_by = rejected_by
            req.accepted_at = datetime.now(timezone.utc).isoformat()
            entry = self._build_audit_entry(req, action="rejected", actor=rejected_by)
            entry["reason"] = reason
            req.audit_entry = entry
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)
        logger.info(
            "TOS for '%s' REJECTED by '%s' (request_id=%s, reason=%r)",
            req.provider_key,
            rejected_by,
            request_id,
            reason,
        )
        return True

    def skip(self, request_id: str) -> bool:
        """Mark a pending request as SKIPPED (provider will not be set up).

        Args:
            request_id: ID returned by :meth:`request_approval`.

        Returns:
            ``True`` if found and transitioned; ``False`` otherwise.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != TOSAcceptanceStatus.PENDING:
                return False
            req.status = TOSAcceptanceStatus.SKIPPED
            req.accepted_at = datetime.now(timezone.utc).isoformat()
            entry = self._build_audit_entry(req, action="skipped", actor="system")
            req.audit_entry = entry
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)
        logger.info(
            "TOS for '%s' SKIPPED (request_id=%s)",
            req.provider_key,
            request_id,
        )
        return True

    def get_pending(self) -> List[TOSApprovalRequest]:
        """Return all requests currently in PENDING state."""
        with self._lock:
            return [
                r for r in self._requests.values()
                if r.status == TOSAcceptanceStatus.PENDING
            ]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return the full audit trail (a snapshot copy)."""
        with self._lock:
            return list(self._audit_log)

    def format_approval_message(self, request: TOSApprovalRequest) -> str:
        """Format a human-readable HITL queue message for the given request.

        Mirrors the style used in
        ``integration_engine/hitl_approval.py::format_approval_request``.

        Args:
            request: The :class:`TOSApprovalRequest` to format.

        Returns:
            A multi-line string suitable for display in the HITL queue UI.
        """
        lines: List[str] = []

        lines.append("╔" + "═" * 78 + "╗")
        lines.append("║" + "  ⚖️  TERMS OF SERVICE ACCEPTANCE REQUIRED".center(78) + "║")
        lines.append("╚" + "═" * 78 + "╝")
        lines.append("")
        lines.append(f"🏢 Provider       : {request.provider_name}")
        lines.append(f"🆔 Request ID     : {request.request_id}")
        lines.append(f"📋 Status         : {request.status.value.upper()}")
        lines.append("")
        lines.append("📜 Legal Links:")
        lines.append(f"   Terms of Service  → {request.tos_url}")
        lines.append(f"   Privacy Policy    → {request.privacy_url}")
        if request.acceptable_use_url:
            lines.append(f"   Acceptable Use    → {request.acceptable_use_url}")
        lines.append("")
        if request.screenshot_path:
            lines.append(f"📸 Screenshot: {request.screenshot_path}")
            lines.append("")
        lines.append("⚠️  LIABILITY NOTICE:")
        for part in request.liability_note.split(". "):
            if part.strip():
                lines.append(f"   {part.strip()}.")
        lines.append("")
        lines.append("─" * 80)
        lines.append(
            "Approve only after YOU have personally read and agreed to the above links."
        )
        lines.append("─" * 80)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_audit_entry(
        req: TOSApprovalRequest,
        action: str,
        actor: str,
    ) -> Dict[str, Any]:
        return {
            "request_id": req.request_id,
            "provider": req.provider_key,
            "provider_name": req.provider_name,
            "tos_url": req.tos_url,
            "privacy_url": req.privacy_url,
            "acceptable_use_url": req.acceptable_use_url,
            "action": action,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "liability_note": req.liability_note,
        }


# ---------------------------------------------------------------------------
# User Credential Collection Gate
# ---------------------------------------------------------------------------

class CredentialRequestStatus(str, Enum):
    """Lifecycle states for a user credential collection request."""

    PENDING = "pending"
    PROVIDED = "provided"
    DECLINED = "declined"


@dataclass
class CredentialRequest:
    """A HITL request that asks the user what signup credentials to use.

    The password is NOT stored inside this object — it lives only in
    ``UserCredentialGate._passwords`` (in-memory, cleared after first use).
    """

    request_id: str
    purpose: str
    suggested_email: str = ""
    status: CredentialRequestStatus = CredentialRequestStatus.PENDING
    email: Optional[str] = None
    password_set: bool = False  # True once provide() is called
    requested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    responded_at: Optional[str] = None


class UserCredentialGate:
    """HITL gate that collects signup credentials from the human operator
    before any browser automation begins.

    Murphy NEVER hard-codes or caches credentials permanently.  The password
    is held in memory only for the duration of the harvest session and cleared
    after each use.

    Usage::

        gate = UserCredentialGate()
        req = gate.request_credentials(
            purpose="API key acquisition for 15 providers",
            suggested_email="you@example.com",
        )
        # --- HITL UI presents the request ---
        gate.provide(req.request_id, email="you@example.com", password="s3cr3t")
        email, password = gate.get_credentials(req.request_id)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, CredentialRequest] = {}
        # Passwords stored separately — never embedded in CredentialRequest
        self._passwords: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_credentials(
        self,
        purpose: str,
        suggested_email: str = "",
    ) -> CredentialRequest:
        """Create a pending credential request and add it to the queue.

        Args:
            purpose: Human-readable description of why credentials are needed.
            suggested_email: Pre-fill hint shown in the HITL message.

        Returns:
            Newly created :class:`CredentialRequest` (status=PENDING).
        """
        request_id = f"cred-{uuid.uuid4().hex[:16]}"
        req = CredentialRequest(
            request_id=request_id,
            purpose=purpose,
            suggested_email=suggested_email,
        )
        with self._lock:
            self._requests[request_id] = req
        logger.info("Credential request created (request_id=%s)", request_id)
        return req

    def provide(
        self,
        request_id: str,
        email: str,
        password: str,
    ) -> bool:
        """Supply credentials in response to a pending request.

        The password is stored in a separate in-memory dict and never
        written to disk, logs, or the :class:`CredentialRequest` object.

        Args:
            request_id: ID returned by :meth:`request_credentials`.
            email: Email address the user wants to use for signups.
            password: Password for signup automation (held in-memory only).

        Returns:
            ``True`` if the request was found and updated; ``False`` otherwise.
        """
        if not email or not password:
            logger.warning(
                "provide() called with empty email or password for request_id=%s",
                request_id,
            )
            return False
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != CredentialRequestStatus.PENDING:
                return False
            req.status = CredentialRequestStatus.PROVIDED
            req.email = email
            req.password_set = True
            req.responded_at = datetime.now(timezone.utc).isoformat()
            self._passwords[request_id] = password
        logger.info(
            "Credentials provided for request_id=%s (email=%s)",
            request_id,
            email,
        )
        return True

    def decline(self, request_id: str) -> bool:
        """Human declines to provide credentials — harvest will not run.

        Args:
            request_id: ID returned by :meth:`request_credentials`.

        Returns:
            ``True`` if found and transitioned; ``False`` otherwise.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != CredentialRequestStatus.PENDING:
                return False
            req.status = CredentialRequestStatus.DECLINED
            req.responded_at = datetime.now(timezone.utc).isoformat()
        logger.info("Credential request declined (request_id=%s)", request_id)
        return True

    def get_credentials(self, request_id: str) -> Optional[tuple]:
        """Return ``(email, password)`` for a PROVIDED request, then clear
        the in-memory password entry.

        Returns ``None`` if the request is not in PROVIDED state.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != CredentialRequestStatus.PROVIDED:
                return None
            email = req.email or ""
            password = self._passwords.pop(request_id, "")
        return (email, password)

    def get_pending(self) -> List[CredentialRequest]:
        """Return all requests currently in PENDING state."""
        with self._lock:
            return [
                r for r in self._requests.values()
                if r.status == CredentialRequestStatus.PENDING
            ]

    def format_request_message(self, req: CredentialRequest) -> str:
        """Format a HITL queue message asking the user for signup credentials.

        Args:
            req: The :class:`CredentialRequest` to format.

        Returns:
            A multi-line string suitable for display in the HITL queue UI.
        """
        lines: List[str] = []
        lines.append("╔" + "═" * 78 + "╗")
        lines.append("║" + "  🔐 SIGNUP CREDENTIALS REQUIRED".center(78) + "║")
        lines.append("╚" + "═" * 78 + "╝")
        lines.append("")
        lines.append(f"🆔 Request ID  : {req.request_id}")
        lines.append(f"📋 Purpose     : {req.purpose}")
        if req.suggested_email:
            lines.append(f"📧 Suggested   : {req.suggested_email}")
        lines.append("")
        lines.append("Murphy will use your credentials ONLY to:")
        lines.append("  ✅ Create free-tier accounts with API providers")
        lines.append("  ✅ Receive and process account verification emails")
        lines.append("  ✅ Extract API keys from provider dashboards")
        lines.append("")
        lines.append("Murphy will NOT:")
        lines.append("  ❌ Store your password permanently on disk")
        lines.append("  ❌ Share credentials with any third party")
        lines.append("  ❌ Use credentials for any purpose beyond key acquisition")
        lines.append("")
        lines.append("─" * 80)
        lines.append(
            "Please respond via the HITL queue with your preferred email and password."
        )
        lines.append("─" * 80)
        return "\n".join(lines)
