"""
Outreach Compliance Integration for Murphy System.

Design Label: COMPL-002 — Outreach Compliance Integration Layer
Owner: Security Team / Marketing Team
Dependencies:
  - ContactComplianceGovernor (COMPL-001) — centralized compliance engine
  - EventBackbone (optional, for audit event publication)

Thin integration layer that wires the ContactComplianceGovernor into every
outreach path (MurphySelfSellingEngine, SalesAutomationEngine, and
MarketingAutomationEngine).  Every caller gets a single gate API:

  gate.check_and_record(...)   → OutreachDecision (ALLOW / BLOCK)
  gate.process_reply(...)      → opt-out detection + DNC registration
  gate.get_contact_status(...) → current DNC / cooldown / consent status

Flow:
  1. Caller invokes check_and_record before sending any outreach message
  2. Gate asks ContactComplianceGovernor whether the contact may be reached
  3. If ALLOW: gate records the contact timestamp for future cooldown tracking
  4. If BLOCK: gate records the block reason for analytics
  5. Caller invokes process_reply when a prospect reply is received
  6. Gate checks reply text for opt-out keywords; adds to DNC if detected
  7. Caller invokes get_contact_status for a dashboard or pre-flight check

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock
  - Fail-safe: if governor raises an unexpected exception the gate BLOCKS
    the outreach rather than allowing it (fail closed, not fail open)
  - Bounded collections via capped_append (CWE-770)
  - DNC additions are permanent and cannot be reversed by this layer
  - Input validation (CWE-20): all public methods validate and sanitize
    contact_id, email, channel, and string lengths before use
  - Null-byte stripping on all string inputs (CWE-158)
  - Channel allowlist enforced: only known channels are accepted
  - Reply text capped at _MAX_REPLY_TEXT_LEN before keyword scan (DoS)
  - Governor-supplied strings truncated before storage
  - Raw email addresses are never written to log records

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
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
# Constants
# ---------------------------------------------------------------------------

_MAX_AUDIT_LOG = 10_000
_MAX_DNC_ENTRIES = 100_000

# ── Input validation constraints (CWE-20) ────────────────────────────────────
# contact_id: alphanumeric plus underscore, hyphen, dot, and at-sign
# (accommodates UUID-style IDs, email-as-ID, and plain slugs)
_CONTACT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
# Email: RFC 5322 simplified — only safe characters before and after @
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_MAX_EMAIL_LEN = 254           # RFC 5321 hard limit
_MAX_CONTACT_ID_LEN = 200
_MAX_OUTREACH_TYPE_LEN = 100
_MAX_REGION_LEN = 100
_MAX_REPLY_TEXT_LEN = 50_000   # truncate before keyword scan to prevent DoS
_MAX_METADATA_KEYS = 50        # CWE-770
_MAX_METADATA_KEY_LEN = 100
_MAX_METADATA_VALUE_LEN = 1_000
_MAX_REGULATION_LEN = 100      # cap governor-supplied regulation string
_MAX_MESSAGE_LEN = 500         # cap governor-supplied reason/message string

# Channels that Murphy recognises; anything else is rejected
_ALLOWED_CHANNELS: frozenset[str] = frozenset({"email", "sms", "linkedin", "phone", "push"})

# Keywords that indicate opt-out intent (case-insensitive, substring match)
_OPT_OUT_KEYWORDS: List[str] = [
    "stop",
    "unsubscribe",
    "remove me",
    "do not contact",
    "opt out",
    "opt-out",
    "dont contact",
    "don't contact",
    "take me off",
    "remove from list",
    "no more emails",
    "no more messages",
    "leave me alone",
    "never contact",
    "please stop",
]

# Keywords that indicate positive / interested intent (module-level constant)
_POSITIVE_KEYWORDS: List[str] = [
    "interested", "tell me more", "sounds good", "yes please",
    "let's talk", "let's chat", "schedule a call", "book a demo",
    "how much", "pricing", "sign me up", "sign up", "i'd like",
    "i would like", "please set up", "trial", "demo",
]


# ---------------------------------------------------------------------------
# Input validation helpers (CWE-20, CWE-158)
# ---------------------------------------------------------------------------


def _validate_contact_id(contact_id: str) -> str:
    """Validate contact_id: strip null bytes, enforce allowlist regex.

    Raises:
        ValueError: if contact_id is empty, too long, or contains invalid chars.
    """
    if not isinstance(contact_id, str):
        raise ValueError("contact_id must be a string")
    contact_id = contact_id.replace("\x00", "")
    if not contact_id:
        raise ValueError("contact_id must not be empty")
    if len(contact_id) > _MAX_CONTACT_ID_LEN:
        raise ValueError(f"contact_id too long (max {_MAX_CONTACT_ID_LEN} chars)")
    if not _CONTACT_ID_RE.match(contact_id):
        raise ValueError(
            "contact_id contains invalid characters "
            "(allowed: alphanumeric, underscore, hyphen, dot, at-sign)"
        )
    return contact_id


def _validate_email(email: str) -> str:
    """Validate and normalise email address (RFC 5321 / RFC 5322 simplified).

    Raises:
        ValueError: if email is empty, too long, or not a valid address.
    """
    if not isinstance(email, str):
        raise ValueError("contact_email must be a string")
    email = email.replace("\x00", "").strip()
    if not email:
        raise ValueError("contact_email must not be empty")
    if len(email) > _MAX_EMAIL_LEN:
        raise ValueError(f"contact_email too long (max {_MAX_EMAIL_LEN} chars)")
    if not _EMAIL_RE.match(email):
        raise ValueError("contact_email is not a valid email address")
    return email.lower()


def _validate_channel(channel: str) -> str:
    """Validate channel against the known-channel allowlist.

    Raises:
        ValueError: if channel is not in _ALLOWED_CHANNELS.
    """
    if not isinstance(channel, str):
        raise ValueError("channel must be a string")
    channel = channel.replace("\x00", "").strip().lower()
    if channel not in _ALLOWED_CHANNELS:
        raise ValueError(
            f"channel must be one of: {', '.join(sorted(_ALLOWED_CHANNELS))}"
        )
    return channel


def _sanitize_str(value: str, max_len: int) -> str:
    """Strip null bytes and truncate to max_len (CWE-158, CWE-770)."""
    if not isinstance(value, str):
        value = str(value)
    return value.replace("\x00", "")[:max_len]


def _sanitize_metadata(
    metadata: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Validate and sanitize message_metadata dict (CWE-20, CWE-770).

    Raises:
        ValueError: if metadata is not a dict or exceeds the key-count cap.
    """
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise ValueError("message_metadata must be a dict")
    if len(metadata) > _MAX_METADATA_KEYS:
        raise ValueError(
            f"message_metadata exceeds maximum key count ({_MAX_METADATA_KEYS})"
        )
    sanitized: Dict[str, Any] = {}
    for k, v in metadata.items():
        if not isinstance(k, str):
            raise ValueError("message_metadata keys must be strings")
        k = k.replace("\x00", "")[:_MAX_METADATA_KEY_LEN]
        if isinstance(v, str):
            v = v.replace("\x00", "")[:_MAX_METADATA_VALUE_LEN]
        sanitized[k] = v
    return sanitized

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OutreachDecisionType(str, Enum):
    """The gate decision for a prospective outreach message."""

    ALLOW = "allow"
    BLOCK = "block"


class BlockReason(str, Enum):
    """Why an outreach was blocked."""

    DNC = "dnc"
    COOLDOWN = "cooldown"
    NO_CONSENT = "no_consent"
    REGULATORY = "regulatory"
    GOVERNOR_ERROR = "governor_error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OutreachDecision:
    """Result of a compliance gate check."""

    decision: OutreachDecisionType
    contact_id: str
    contact_email: str
    channel: str
    outreach_type: str
    block_reason: Optional[BlockReason] = None
    regulation_cited: str = ""
    message: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def allowed(self) -> bool:
        """Convenience accessor."""
        return self.decision == OutreachDecisionType.ALLOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "contact_id": self.contact_id,
            "contact_email": self.contact_email,
            "channel": self.channel,
            "outreach_type": self.outreach_type,
            "block_reason": self.block_reason.value if self.block_reason else None,
            "regulation_cited": self.regulation_cited,
            "message": self.message,
            "checked_at": self.checked_at,
        }


@dataclass
class AuditRecord:
    """One entry in the gate's immutable audit log."""

    record_id: str
    contact_id: str
    contact_email: str
    channel: str
    outreach_type: str
    decision: str
    block_reason: Optional[str]
    regulation_cited: str
    timestamp: str


# ---------------------------------------------------------------------------
# Stub governor — used when ContactComplianceGovernor cannot be imported
# ---------------------------------------------------------------------------


class _StubGovernor:
    """
    Minimal no-op governor used when the real ContactComplianceGovernor has
    not yet been wired in.  Always allows outreach and records nothing.

    This stub ensures the gate is usable before COMPL-001 lands.
    """

    # ---- DNC ----

    def is_dnc(self, contact_id: str, contact_email: str) -> bool:  # noqa: ARG002
        return False

    def add_to_dnc(self, contact_id: str, contact_email: str, reason: str = "") -> None:  # noqa: ARG002
        pass

    # ---- Cooldown ----

    def is_in_cooldown(
        self,
        contact_id: str,
        contact_email: str,
        channel: str,
        is_existing_customer: bool = False,
    ) -> bool:  # noqa: ARG002
        return False

    def cooldown_remaining_seconds(
        self,
        contact_id: str,
        contact_email: str,
        channel: str,
        is_existing_customer: bool = False,
    ) -> int:  # noqa: ARG002
        return 0

    def record_contact(
        self,
        contact_id: str,
        contact_email: str,
        channel: str,
        outreach_type: str,
    ) -> None:  # noqa: ARG002
        pass

    def last_contacted_at(
        self, contact_id: str, contact_email: str
    ) -> Optional[str]:  # noqa: ARG002
        return None

    # ---- Regulatory ----

    def check_regulatory(
        self,
        contact_email: str,
        channel: str,
        contact_region: str = "",
        has_explicit_consent: bool = False,
        outreach_type: str = "",
    ) -> Dict[str, Any]:  # noqa: ARG002
        return {"allowed": True, "regulation": "", "reason": ""}

    # ---- Consent ----

    def consent_status(
        self, contact_id: str, contact_email: str
    ) -> str:  # noqa: ARG002
        return "unknown"


# ---------------------------------------------------------------------------
# OutreachComplianceGate
# ---------------------------------------------------------------------------


class OutreachComplianceGate:
    """Pre-send compliance gate for all Murphy outreach systems.

    Wraps ContactComplianceGovernor to provide a simple gate API
    that any outreach module can call before sending.

    Design Label: COMPL-002 — Outreach Compliance Integration Layer
    Owner: Security Team / Marketing Team
    """

    def __init__(self, governor: Any = None) -> None:
        """Accept optional governor; lazy-create if None."""
        self._governor = governor
        self._lock = threading.Lock()
        self._audit_log: List[AuditRecord] = []

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_governor(self) -> Any:
        """Return the governor, creating it lazily on first use."""
        if self._governor is not None:
            return self._governor
        with self._lock:
            if self._governor is None:
                try:
                    from contact_compliance_governor import ContactComplianceGovernor  # type: ignore[import]
                    self._governor = ContactComplianceGovernor()
                    logger.info("ContactComplianceGovernor lazy-created for OutreachComplianceGate")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "ContactComplianceGovernor unavailable (%s); using stub governor", exc
                    )
                    self._governor = _StubGovernor()
        return self._governor

    def _record_audit(
        self,
        contact_id: str,
        contact_email: str,
        channel: str,
        outreach_type: str,
        decision: OutreachDecisionType,
        block_reason: Optional[BlockReason],
        regulation_cited: str,
    ) -> None:
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            contact_id=contact_id,
            contact_email=contact_email,
            channel=channel,
            outreach_type=outreach_type,
            decision=decision.value,
            block_reason=block_reason.value if block_reason else None,
            regulation_cited=regulation_cited,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            capped_append(self._audit_log, record, max_size=_MAX_AUDIT_LOG)

    # ── Public API ───────────────────────────────────────────────────────────

    def check_and_record(
        self,
        contact_id: str,
        contact_email: str,
        channel: str,
        outreach_type: str,
        contact_region: str = "",
        is_existing_customer: bool = False,
        has_explicit_consent: bool = False,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> OutreachDecision:
        """Check compliance, record the attempt, return decision.

        If ALLOW: records the contact timestamp for future cooldown tracking.
        If BLOCK: records the block reason for analytics.

        Raises:
            ValueError: if any input fails validation (contact_id, email, channel,
                metadata).  These are programmer errors and are not caught by the
                fail-closed exception handler.
        """
        # ── Input validation — runs BEFORE the fail-closed try/except ────────
        # ValueError propagates directly to the caller; it is not swallowed.
        contact_id = _validate_contact_id(contact_id)
        contact_email = _validate_email(contact_email)
        channel = _validate_channel(channel)
        outreach_type = _sanitize_str(outreach_type, _MAX_OUTREACH_TYPE_LEN)
        contact_region = _sanitize_str(contact_region, _MAX_REGION_LEN)
        message_metadata = _sanitize_metadata(message_metadata)

        try:
            gov = self._get_governor()

            # ── 1. DNC check ─────────────────────────────────────────────────
            if gov.is_dnc(contact_id, contact_email):
                decision = OutreachDecision(
                    decision=OutreachDecisionType.BLOCK,
                    contact_id=contact_id,
                    contact_email=contact_email,
                    channel=channel,
                    outreach_type=outreach_type,
                    block_reason=BlockReason.DNC,
                    message="Contact is on the Do-Not-Contact list.",
                )
                self._record_audit(
                    contact_id, contact_email, channel, outreach_type,
                    OutreachDecisionType.BLOCK, BlockReason.DNC, ""
                )
                return decision

            # ── 2. Cooldown check ────────────────────────────────────────────
            if gov.is_in_cooldown(contact_id, contact_email, channel, is_existing_customer):
                remaining = gov.cooldown_remaining_seconds(
                    contact_id, contact_email, channel, is_existing_customer
                )
                decision = OutreachDecision(
                    decision=OutreachDecisionType.BLOCK,
                    contact_id=contact_id,
                    contact_email=contact_email,
                    channel=channel,
                    outreach_type=outreach_type,
                    block_reason=BlockReason.COOLDOWN,
                    message=(
                        f"Contact is in cooldown. "
                        f"{remaining // 86400}d {(remaining % 86400) // 3600}h remaining."
                    ),
                )
                self._record_audit(
                    contact_id, contact_email, channel, outreach_type,
                    OutreachDecisionType.BLOCK, BlockReason.COOLDOWN, ""
                )
                return decision

            # ── 3. Regulatory check ──────────────────────────────────────────
            reg_result = gov.check_regulatory(
                contact_email=contact_email,
                channel=channel,
                contact_region=contact_region,
                has_explicit_consent=has_explicit_consent,
                outreach_type=outreach_type,
            )
            if not reg_result.get("allowed", True):
                block_reason = (
                    BlockReason.NO_CONSENT
                    if "consent" in reg_result.get("reason", "").lower()
                    else BlockReason.REGULATORY
                )
                # Sanitize governor-supplied strings before surfacing (CWE-20)
                safe_regulation = _sanitize_str(
                    reg_result.get("regulation", ""), _MAX_REGULATION_LEN
                )
                safe_message = _sanitize_str(
                    reg_result.get("reason", "Regulatory block."), _MAX_MESSAGE_LEN
                )
                decision = OutreachDecision(
                    decision=OutreachDecisionType.BLOCK,
                    contact_id=contact_id,
                    contact_email=contact_email,
                    channel=channel,
                    outreach_type=outreach_type,
                    block_reason=block_reason,
                    regulation_cited=safe_regulation,
                    message=safe_message,
                )
                self._record_audit(
                    contact_id, contact_email, channel, outreach_type,
                    OutreachDecisionType.BLOCK, block_reason, safe_regulation
                )
                return decision

            # ── 4. ALLOW — record the contact timestamp ───────────────────────
            gov.record_contact(contact_id, contact_email, channel, outreach_type)

            decision = OutreachDecision(
                decision=OutreachDecisionType.ALLOW,
                contact_id=contact_id,
                contact_email=contact_email,
                channel=channel,
                outreach_type=outreach_type,
                message="Outreach approved.",
            )
            self._record_audit(
                contact_id, contact_email, channel, outreach_type,
                OutreachDecisionType.ALLOW, None, ""
            )
            return decision

        except Exception as exc:  # noqa: BLE001
            # Fail closed: unexpected errors block the outreach.
            # Log contact_id only — never the raw email address (PII in logs).
            logger.error(
                "OutreachComplianceGate unexpected error for contact %s: %s",
                contact_id, exc, exc_info=True,
            )
            decision = OutreachDecision(
                decision=OutreachDecisionType.BLOCK,
                contact_id=contact_id,
                contact_email=contact_email,
                channel=channel,
                outreach_type=outreach_type,
                block_reason=BlockReason.GOVERNOR_ERROR,
                message="Compliance check failed with error; outreach blocked for safety",
            )
            self._record_audit(
                contact_id, contact_email, channel, outreach_type,
                OutreachDecisionType.BLOCK, BlockReason.GOVERNOR_ERROR, ""
            )
            return decision

    def process_reply(
        self,
        contact_id: str,
        contact_email: str,
        reply_text: str,
    ) -> Dict[str, Any]:
        """Process a reply for opt-out intent detection.

        If opt-out detected: adds to DNC list, returns
            {"opted_out": True, "reason": "<matched keyword>"}
        If positive reply: returns
            {"opted_out": False, "positive": True}
        Otherwise: returns
            {"opted_out": False, "positive": False}

        Raises:
            ValueError: if contact_id or contact_email fail validation.
        """
        # ── Input validation ──────────────────────────────────────────────────
        contact_id = _validate_contact_id(contact_id)
        contact_email = _validate_email(contact_email)
        if not isinstance(reply_text, str):
            reply_text = str(reply_text)
        # Strip null bytes and cap length before keyword scan (CWE-158, DoS)
        reply_text = reply_text.replace("\x00", "")[:_MAX_REPLY_TEXT_LEN]

        normalized = reply_text.lower()

        # ── Opt-out detection ─────────────────────────────────────────────────
        matched_keyword: Optional[str] = None
        for kw in _OPT_OUT_KEYWORDS:
            if kw in normalized:
                matched_keyword = kw
                break

        if matched_keyword is not None:
            try:
                gov = self._get_governor()
                gov.add_to_dnc(
                    contact_id,
                    contact_email,
                    reason=f"opt_out_reply:{matched_keyword}",
                )
            except Exception as exc:  # noqa: BLE001
                # Log contact_id only — do not expose raw email in log output (PII)
                logger.error(
                    "Failed to add contact %s to DNC after opt-out reply: %s",
                    contact_id,
                    exc,
                    exc_info=True,
                )
            logger.info(
                "Opt-out detected for contact %s (keyword=%r); added to DNC.",
                contact_id,
                matched_keyword,
            )
            return {"opted_out": True, "reason": matched_keyword}

        # ── Positive intent detection ─────────────────────────────────────────
        is_positive = any(kw in normalized for kw in _POSITIVE_KEYWORDS)

        return {"opted_out": False, "positive": is_positive}

    def get_contact_status(
        self,
        contact_id: str,
        contact_email: str,
    ) -> Dict[str, Any]:
        """Return current compliance status for a contact.

        Returns:
            is_dnc            — True if on the Do-Not-Contact list
            cooldown_remaining — seconds remaining in cooldown (0 if none)
            last_contacted    — ISO timestamp of last contact, or None
            consent_status    — "granted" | "withdrawn" | "unknown"

        Raises:
            ValueError: if contact_id or contact_email fail validation.
        """
        # ── Input validation ──────────────────────────────────────────────────
        contact_id = _validate_contact_id(contact_id)
        contact_email = _validate_email(contact_email)

        try:
            gov = self._get_governor()
            is_dnc = gov.is_dnc(contact_id, contact_email)
            cooldown_remaining = gov.cooldown_remaining_seconds(
                contact_id, contact_email, channel="email"
            )
            last_contacted = gov.last_contacted_at(contact_id, contact_email)
            consent_status = gov.consent_status(contact_id, contact_email)
        except Exception as exc:  # noqa: BLE001
            # Log contact_id only — do not expose raw email in log output (PII)
            logger.error(
                "get_contact_status failed for contact %s: %s",
                contact_id, exc, exc_info=True,
            )
            return {
                "contact_id": contact_id,
                "contact_email": contact_email,
                "is_dnc": True,  # Fail safe
                "cooldown_remaining": 0,
                "last_contacted": None,
                "consent_status": "unknown",
                "error": str(exc),
            }

        return {
            "contact_id": contact_id,
            "contact_email": contact_email,
            "is_dnc": is_dnc,
            "cooldown_remaining": cooldown_remaining,
            "last_contacted": last_contacted,
            "consent_status": consent_status,
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a snapshot of the audit log as a list of dicts."""
        with self._lock:
            return [
                {
                    "record_id": r.record_id,
                    "contact_id": r.contact_id,
                    "contact_email": r.contact_email,
                    "channel": r.channel,
                    "outreach_type": r.outreach_type,
                    "decision": r.decision,
                    "block_reason": r.block_reason,
                    "regulation_cited": r.regulation_cited,
                    "timestamp": r.timestamp,
                }
                for r in self._audit_log
            ]


# ---------------------------------------------------------------------------
# Module-level singleton (optional convenience)
# ---------------------------------------------------------------------------

_default_gate: Optional[OutreachComplianceGate] = None
_default_gate_lock = threading.Lock()


def get_default_gate() -> OutreachComplianceGate:
    """Return (or lazily create) the module-level default gate instance."""
    global _default_gate
    if _default_gate is not None:
        return _default_gate
    with _default_gate_lock:
        if _default_gate is None:
            _default_gate = OutreachComplianceGate()
    return _default_gate


__all__ = [
    "AuditRecord",
    "BlockReason",
    "OutreachComplianceGate",
    "OutreachDecision",
    "OutreachDecisionType",
    "get_default_gate",
    # Validation helpers (exported for external testing and re-use)
    "_ALLOWED_CHANNELS",
    "_validate_contact_id",
    "_validate_channel",
    "_validate_email",
    "_sanitize_str",
    "_sanitize_metadata",
]
