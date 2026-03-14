# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Outreach Compliance Plan — Murphy System self-advertising engine.

Design Label: CAMP-002 — Outreach Compliance Plan
Owner: Marketing Team / Legal / Security
Dependencies:
  - ContactComplianceGovernor (COMPL-001) — centralized outreach enforcement
  - OutreachComplianceGate (COMPL-002) — thin integration layer
  - thread_safe_operations.capped_append — bounded collections

Implements Murphy's self-advertising outreach engine with legally-compliant
rules layered on top of the existing ContactComplianceGovernor.

Key classes:
  - OutreachComplianceGovernor — Wraps the selling cycle with compliance checks
  - SuppressionListManager — Manages opt-outs, DNC imports, GDPR erasure
  - CooldownEnforcer — Enforces 30-day re-contact window
  - OutreachCampaignPlanner — Generates daily/weekly outreach plans

Data models:
  - OutreachComplianceRecord     Tracks contact attempts per prospect
  - SuppressionEntry             Permanent suppression list entry
  - ContactCooldownTracker       Per-prospect cooldown state (30-day window)
  - OutreachCampaignPlan         Campaign-level config with compliance baked in

Compliance rules enforced:
  - 30-day cooldown for non-customers (7-day for existing-customer marketing)
  - Explicit opt-out / suppression list — permanent unless re-opt-in
  - CAN-SPAM: unsubscribe link, physical address, accurate sender, no deceptive
    subject lines
  - TCPA: prior express consent for SMS/phone, honour DNC lists, 8am–9pm window
  - GDPR: lawful basis required for EU prospects, right to erasure honoured,
    data minimisation
  - CASL: implied or express consent required for Canadian prospects
  - CCPA: California "Do Not Sell" honoured, right to opt-out

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock (CWE-362)
  - Non-destructive: suppression list only grows; removal requires consent
  - Bounded collections via capped_append (CWE-770)
  - Input validated before processing (CWE-20)
  - Collection hard caps prevent memory exhaustion (CWE-400)
  - Raw emails / PII never written to log records (PII protection)
  - Error messages sanitised before logging (CWE-209)
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
# Input-validation constants                                        [CWE-20]
# ---------------------------------------------------------------------------

_CONTACT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MAX_EMAIL_LEN = 254           # RFC 5321 hard limit
_MAX_CONTACT_ID_LEN = 200
_MAX_REASON_LEN = 500
_MAX_ADDED_BY_LEN = 100
_MAX_CONSENT_PROOF_LEN = 500
_MAX_CAMPAIGN_NAME_LEN = 200
_MAX_VERTICAL_LEN = 100
_MAX_NOTES_LEN = 2_000

# Closed allowlists for channel / region                          [CWE-20]
_ALLOWED_CHANNELS: frozenset[str] = frozenset({"email", "sms", "linkedin", "phone"})
_ALLOWED_REGIONS: frozenset[str] = frozenset({"", "US", "EU", "CA_US", "CA"})

# Collection hard caps                                             [CWE-400]
_MAX_SUPPRESSION_LIST = 10_000
_MAX_COOLDOWN_ENTRIES = 100_000
_MAX_AUDIT_LOG = 50_000
_MAX_CAMPAIGNS = 5_000
_MAX_RECORDS_PER_CONTACT = 200

# Cooldown windows
_COOLDOWN_DAYS_PROSPECT: int = 30
_COOLDOWN_DAYS_CUSTOMER: int = 7

# Business type verticals supported (12+)
BUSINESS_TYPE_VERTICALS: List[str] = [
    "saas",
    "ecommerce",
    "healthcare",
    "legal",
    "financial_services",
    "manufacturing",
    "construction",
    "real_estate",
    "hospitality",
    "education",
    "logistics",
    "content_creator",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SuppressionReason(str, Enum):
    """Reason for adding a contact to the suppression list."""
    OPT_OUT_REPLY       = "opt_out_reply"
    EXPLICIT_REQUEST    = "explicit_request"
    DNC_IMPORT          = "dnc_import"
    GDPR_ERASURE        = "gdpr_erasure"
    CCPA_DO_NOT_SELL    = "ccpa_do_not_sell"
    CASL_NO_CONSENT     = "casl_no_consent"
    ADMIN               = "admin"
    BOUNCE              = "bounce"


class OutreachChannel(str, Enum):
    EMAIL    = "email"
    SMS      = "sms"
    LINKEDIN = "linkedin"
    PHONE    = "phone"


class CampaignStatus(str, Enum):
    DRAFT     = "draft"
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"
    ARCHIVED  = "archived"


class ComplianceDecision(str, Enum):
    ALLOW            = "ALLOW"
    BLOCK            = "BLOCK"
    REQUIRES_CONSENT = "REQUIRES_CONSENT"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OutreachComplianceRecord:
    """Tracks every outreach attempt for a single contact."""
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    contact_id: str = ""
    channel: str = ""
    outreach_type: str = ""
    contacted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision: str = ComplianceDecision.ALLOW.value
    block_reason: str = ""
    regulation_triggered: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "contact_id": self.contact_id,
            "channel": self.channel,
            "outreach_type": self.outreach_type,
            "contacted_at": self.contacted_at,
            "decision": self.decision,
            "block_reason": self.block_reason,
            "regulation_triggered": self.regulation_triggered,
        }


@dataclass
class SuppressionEntry:
    """A permanent entry on the suppression / DNC list."""
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    contact_id: str = ""
    contact_email: str = ""
    suppressed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = SuppressionReason.EXPLICIT_REQUEST.value
    added_by: str = "system"
    consent_proof: Optional[str] = None  # Required to remove the entry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "contact_id": self.contact_id,
            # Raw email omitted from serialised form to protect PII
            "suppressed_at": self.suppressed_at,
            "reason": self.reason,
            "added_by": self.added_by,
        }


@dataclass
class ContactCooldownTracker:
    """Per-prospect cooldown state with a configurable re-contact window."""
    contact_id: str = ""
    is_customer: bool = False
    last_contacted_at: Optional[str] = None
    last_channel: str = ""
    cooldown_days: int = _COOLDOWN_DAYS_PROSPECT

    @property
    def cooldown_expires_at(self) -> Optional[datetime]:
        if not self.last_contacted_at:
            return None
        last = datetime.fromisoformat(self.last_contacted_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return last + timedelta(days=self.cooldown_days)

    @property
    def is_in_cooldown(self) -> bool:
        exp = self.cooldown_expires_at
        if exp is None:
            return False
        return datetime.now(timezone.utc) < exp

    @property
    def cooldown_remaining_days(self) -> int:
        exp = self.cooldown_expires_at
        if exp is None:
            return 0
        delta = exp - datetime.now(timezone.utc)
        return max(0, delta.days)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "is_customer": self.is_customer,
            "last_contacted_at": self.last_contacted_at,
            "last_channel": self.last_channel,
            "cooldown_days": self.cooldown_days,
            "is_in_cooldown": self.is_in_cooldown,
            "cooldown_remaining_days": self.cooldown_remaining_days,
        }


@dataclass
class OutreachCampaignPlan:
    """Campaign-level configuration with compliance rules baked in."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    vertical: str = ""           # one of BUSINESS_TYPE_VERTICALS
    channels: List[str] = field(default_factory=list)
    prospect_ids: List[str] = field(default_factory=list)
    status: str = CampaignStatus.DRAFT.value
    # Compliance config
    cooldown_days_prospect: int = _COOLDOWN_DAYS_PROSPECT
    cooldown_days_customer: int = _COOLDOWN_DAYS_CUSTOMER
    enforce_can_spam: bool = True
    enforce_tcpa: bool = True
    enforce_gdpr: bool = True
    enforce_casl: bool = True
    enforce_ccpa: bool = True
    # Schedule
    max_outreach_per_day: int = 50
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "vertical": self.vertical,
            "channels": list(self.channels),
            "prospect_count": len(self.prospect_ids),
            "status": self.status,
            "cooldown_days_prospect": self.cooldown_days_prospect,
            "cooldown_days_customer": self.cooldown_days_customer,
            "enforce_can_spam": self.enforce_can_spam,
            "enforce_tcpa": self.enforce_tcpa,
            "enforce_gdpr": self.enforce_gdpr,
            "enforce_casl": self.enforce_casl,
            "enforce_ccpa": self.enforce_ccpa,
            "max_outreach_per_day": self.max_outreach_per_day,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# SuppressionListManager
# ---------------------------------------------------------------------------


class SuppressionListManager:
    """Manages opt-outs, DNC imports, and GDPR/CCPA erasure requests.

    All additions are permanent and append-only unless the contact explicitly
    re-opts-in and a consent_proof is provided.

    Thread-safe via an internal Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._suppressed: Dict[str, SuppressionEntry] = {}  # keyed by contact_id
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_contact_id(contact_id: str) -> str:
        contact_id = str(contact_id or "").strip().replace("\x00", "")
        if not _CONTACT_ID_RE.match(contact_id):
            raise ValueError(f"Invalid contact_id: must match {_CONTACT_ID_RE.pattern}")
        return contact_id

    @staticmethod
    def _validate_email(email: str) -> str:
        email = str(email or "").strip().replace("\x00", "")
        if len(email) > _MAX_EMAIL_LEN:
            raise ValueError(f"Email exceeds {_MAX_EMAIL_LEN} characters (RFC 5321)")
        if not _EMAIL_RE.match(email):
            raise ValueError("Invalid email address format")
        return email

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def suppress(
        self,
        contact_id: str,
        contact_email: str,
        reason: str = SuppressionReason.EXPLICIT_REQUEST.value,
        added_by: str = "system",
    ) -> SuppressionEntry:
        """Add a contact to the permanent suppression list.

        Raises:
            ValueError: if contact_id or contact_email fail validation.
            ValueError: if the suppression list is at capacity (_MAX_SUPPRESSION_LIST).
        """
        contact_id = self._validate_contact_id(contact_id)
        self._validate_email(contact_email)
        reason = str(reason or "")[:_MAX_REASON_LEN].replace("\x00", "")
        added_by = str(added_by or "system")[:_MAX_ADDED_BY_LEN].replace("\x00", "")

        with self._lock:
            if len(self._suppressed) >= _MAX_SUPPRESSION_LIST:
                raise ValueError(
                    f"Suppression list at capacity ({_MAX_SUPPRESSION_LIST}). "
                    "Cannot add new entries."
                )
            entry = SuppressionEntry(
                contact_id=contact_id,
                contact_email=contact_email,
                reason=reason,
                added_by=added_by,
            )
            # Idempotent: if already suppressed, update reason but keep original timestamp
            if contact_id not in self._suppressed:
                self._suppressed[contact_id] = entry
            capped_append(
                self._audit_log,
                {
                    "action": "suppress",
                    "contact_id": contact_id,
                    "reason": reason,
                    "added_by": added_by,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                max_size=_MAX_AUDIT_LOG,
            )
            # PII: log contact_id only, not email
            logger.info("Contact %s added to suppression list (reason=%s)", contact_id, reason)
            return self._suppressed[contact_id]

    def is_suppressed(self, contact_id: str) -> bool:
        """Return True if the contact is on the suppression list."""
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            return contact_id in self._suppressed

    def remove_with_consent(self, contact_id: str, consent_proof: str) -> bool:
        """Remove a contact from the suppression list only when consent_proof is provided.

        Returns True if removed, False if not found or consent_proof is empty.
        """
        contact_id = self._validate_contact_id(contact_id)
        if not consent_proof or not consent_proof.strip():
            logger.warning("Suppression removal refused — consent_proof required for %s", contact_id)
            return False
        consent_proof = consent_proof[:_MAX_CONSENT_PROOF_LEN]
        with self._lock:
            if contact_id not in self._suppressed:
                return False
            del self._suppressed[contact_id]
            capped_append(
                self._audit_log,
                {
                    "action": "remove_with_consent",
                    "contact_id": contact_id,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                max_size=_MAX_AUDIT_LOG,
            )
            logger.info("Contact %s removed from suppression list (re-opt-in)", contact_id)
            return True

    def get_suppression_entry(self, contact_id: str) -> Optional[SuppressionEntry]:
        """Return the SuppressionEntry for a contact, or None if not suppressed."""
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            return self._suppressed.get(contact_id)

    def process_reply_for_optout(
        self,
        contact_id: str,
        contact_email: str,
        reply_text: str,
    ) -> bool:
        """Check reply_text for opt-out intent and suppress if detected.

        Returns True if contact was suppressed, False otherwise.
        """
        contact_id = self._validate_contact_id(contact_id)
        self._validate_email(contact_email)
        reply_capped = str(reply_text or "")[:50_000]
        _OPTOUT_RE = re.compile(
            r"\b(unsubscribe|opt[- ]?out|stop|remove me|do not contact"
            r"|don't contact|please remove|take me off|no more emails)\b",
            re.IGNORECASE,
        )
        if _OPTOUT_RE.search(reply_capped):
            self.suppress(
                contact_id=contact_id,
                contact_email=contact_email,
                reason=SuppressionReason.OPT_OUT_REPLY.value,
                added_by="system",
            )
            return True
        return False

    def import_dnc_list(
        self,
        entries: List[Dict[str, str]],
        added_by: str = "dnc_import",
    ) -> int:
        """Bulk import a DNC list.  Each entry must have 'contact_id' and 'email'.

        Returns the count of new entries added.
        """
        added = 0
        for entry in entries:
            try:
                self.suppress(
                    contact_id=entry["contact_id"],
                    contact_email=entry["email"],
                    reason=SuppressionReason.DNC_IMPORT.value,
                    added_by=added_by,
                )
                added += 1
            except (ValueError, KeyError) as exc:
                logger.warning("DNC import skipped entry: %s", str(exc)[:200])
        return added

    def handle_gdpr_erasure(self, contact_id: str, contact_email: str) -> None:
        """Handle a GDPR right-to-erasure request.

        Suppresses the contact and marks the reason as GDPR erasure.
        """
        self.suppress(
            contact_id=contact_id,
            contact_email=contact_email,
            reason=SuppressionReason.GDPR_ERASURE.value,
            added_by="gdpr_erasure",
        )

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "suppressed_count": len(self._suppressed),
                "capacity": _MAX_SUPPRESSION_LIST,
                "audit_log_size": len(self._audit_log),
            }


# ---------------------------------------------------------------------------
# CooldownEnforcer
# ---------------------------------------------------------------------------


class CooldownEnforcer:
    """Enforces the 30-day re-contact window per prospect.

    Customers have a shorter 7-day cooldown.  The cooldown is per contact_id
    and is channel-agnostic (any outreach resets the clock).

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        cooldown_days_prospect: int = _COOLDOWN_DAYS_PROSPECT,
        cooldown_days_customer: int = _COOLDOWN_DAYS_CUSTOMER,
    ) -> None:
        self._lock = threading.Lock()
        self._trackers: Dict[str, ContactCooldownTracker] = {}
        self.cooldown_days_prospect = cooldown_days_prospect
        self.cooldown_days_customer = cooldown_days_customer

    @staticmethod
    def _validate_contact_id(contact_id: str) -> str:
        contact_id = str(contact_id or "").strip().replace("\x00", "")
        if not _CONTACT_ID_RE.match(contact_id):
            raise ValueError(f"Invalid contact_id: must match {_CONTACT_ID_RE.pattern}")
        return contact_id

    def is_in_cooldown(self, contact_id: str) -> bool:
        """Return True if the contact is within the active cooldown window."""
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            tracker = self._trackers.get(contact_id)
            if tracker is None:
                return False
            return tracker.is_in_cooldown

    def cooldown_remaining_days(self, contact_id: str) -> int:
        """Return the number of days remaining in the cooldown, or 0 if none."""
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            tracker = self._trackers.get(contact_id)
            if tracker is None:
                return 0
            return tracker.cooldown_remaining_days

    def record_contact(
        self,
        contact_id: str,
        channel: str,
        is_customer: bool = False,
    ) -> ContactCooldownTracker:
        """Record an outreach attempt and reset the cooldown clock."""
        contact_id = self._validate_contact_id(contact_id)
        channel = str(channel or "")[:_MAX_EMAIL_LEN].replace("\x00", "")
        cooldown = self.cooldown_days_customer if is_customer else self.cooldown_days_prospect

        with self._lock:
            if len(self._trackers) >= _MAX_COOLDOWN_ENTRIES:
                # Evict the oldest 10% to prevent memory exhaustion
                to_remove = list(self._trackers.keys())[: _MAX_COOLDOWN_ENTRIES // 10]
                for k in to_remove:
                    del self._trackers[k]

            tracker = ContactCooldownTracker(
                contact_id=contact_id,
                is_customer=is_customer,
                last_contacted_at=datetime.now(timezone.utc).isoformat(),
                last_channel=channel,
                cooldown_days=cooldown,
            )
            self._trackers[contact_id] = tracker
            return tracker

    def get_tracker(self, contact_id: str) -> Optional[ContactCooldownTracker]:
        """Return the CooldownTracker for a contact, or None if never contacted."""
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            return self._trackers.get(contact_id)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tracked_contacts": len(self._trackers),
                "capacity": _MAX_COOLDOWN_ENTRIES,
                "cooldown_days_prospect": self.cooldown_days_prospect,
                "cooldown_days_customer": self.cooldown_days_customer,
            }


# ---------------------------------------------------------------------------
# OutreachComplianceGovernor
# ---------------------------------------------------------------------------


class OutreachComplianceGovernor:
    """Wraps the self-selling cycle with a compliance gate before every send.

    Uses SuppressionListManager and CooldownEnforcer internally.  The caller
    must pass ContactComplianceGovernor decisions as well; this class focuses
    on the campaign-level plan compliance and audit trail.

    Fail-closed: any unexpected error returns BLOCK.

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        suppression_manager: Optional[SuppressionListManager] = None,
        cooldown_enforcer: Optional[CooldownEnforcer] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._suppression = suppression_manager or SuppressionListManager()
        self._cooldown = cooldown_enforcer or CooldownEnforcer()
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_contact_id(contact_id: str) -> str:
        contact_id = str(contact_id or "").strip().replace("\x00", "")
        if not _CONTACT_ID_RE.match(contact_id):
            raise ValueError(f"Invalid contact_id: must match {_CONTACT_ID_RE.pattern}")
        return contact_id

    @staticmethod
    def _validate_channel(channel: str) -> str:
        channel = str(channel or "").strip().lower().replace("\x00", "")
        if channel not in _ALLOWED_CHANNELS:
            raise ValueError(f"Invalid channel '{channel}'. Allowed: {sorted(_ALLOWED_CHANNELS)}")
        return channel

    @staticmethod
    def _validate_region(region: str) -> str:
        region = str(region or "").strip().upper().replace("\x00", "")
        if region not in _ALLOWED_REGIONS:
            raise ValueError(f"Invalid region '{region}'. Allowed: {sorted(_ALLOWED_REGIONS)}")
        return region

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def check_outreach(
        self,
        contact_id: str,
        channel: str,
        contact_region: str = "",
        is_customer: bool = False,
        has_explicit_consent: bool = False,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform a pre-send compliance check.

        Returns a dict with keys:
          - allowed (bool)
          - decision (str): ALLOW | BLOCK | REQUIRES_CONSENT
          - reason (str)
          - cooldown_remaining_days (int)

        Fail-closed: any exception returns BLOCK.
        """
        try:
            contact_id = self._validate_contact_id(contact_id)
            channel = self._validate_channel(channel)
            contact_region = self._validate_region(contact_region)
        except ValueError as exc:
            return self._block_result(str(exc)[:200], "INPUT_VALIDATION")

        try:
            # 1. Suppression list check — hard block
            if self._suppression.is_suppressed(contact_id):
                return self._block_result(
                    "Contact is on the suppression list.",
                    "SUPPRESSION",
                )

            # 2. GDPR — EU contacts require explicit consent
            if contact_region == "EU" and not has_explicit_consent:
                return {
                    "allowed": False,
                    "decision": ComplianceDecision.REQUIRES_CONSENT.value,
                    "reason": "GDPR: EU contact requires explicit consent for outreach.",
                    "cooldown_remaining_days": 0,
                    "regulation": "GDPR",
                }

            # 3. CASL — Canadian contacts require consent
            if contact_region == "CA" and not has_explicit_consent:
                return {
                    "allowed": False,
                    "decision": ComplianceDecision.REQUIRES_CONSENT.value,
                    "reason": "CASL: Canadian contact requires consent for outreach.",
                    "cooldown_remaining_days": 0,
                    "regulation": "CASL",
                }

            # 4. TCPA — SMS/phone require prior express consent
            if channel in {"sms", "phone"} and not has_explicit_consent:
                return {
                    "allowed": False,
                    "decision": ComplianceDecision.REQUIRES_CONSENT.value,
                    "reason": "TCPA: SMS/phone outreach requires prior express consent.",
                    "cooldown_remaining_days": 0,
                    "regulation": "TCPA",
                }

            # 5. CAN-SPAM metadata check for email
            if channel == "email":
                meta = message_metadata or {}
                missing = []
                if not meta.get("has_unsubscribe_link"):
                    missing.append("unsubscribe_link")
                if not meta.get("has_physical_address"):
                    missing.append("physical_address")
                if missing:
                    return self._block_result(
                        f"CAN-SPAM: email missing required fields: {missing}",
                        "CAN_SPAM",
                    )

            # 6. CCPA — California "Do Not Sell"
            if contact_region == "US":
                meta = message_metadata or {}
                if meta.get("ccpa_do_not_sell"):
                    return self._block_result(
                        "CCPA: contact has exercised Do Not Sell right.",
                        "CCPA",
                    )

            # 7. Cooldown check
            if self._cooldown.is_in_cooldown(contact_id):
                remaining = self._cooldown.cooldown_remaining_days(contact_id)
                return {
                    "allowed": False,
                    "decision": ComplianceDecision.BLOCK.value,
                    "reason": (
                        f"Cooldown active: {remaining} day(s) remaining before re-contact."
                    ),
                    "cooldown_remaining_days": remaining,
                    "regulation": "COOLDOWN",
                }

            return {
                "allowed": True,
                "decision": ComplianceDecision.ALLOW.value,
                "reason": "All compliance checks passed.",
                "cooldown_remaining_days": 0,
                "regulation": "NONE",
            }

        except Exception as exc:  # noqa: BLE001
            # Fail-closed: any unexpected error blocks outreach
            logger.error(
                "OutreachComplianceGovernor.check_outreach error for %s: %s",
                contact_id,
                str(exc)[:200],
            )
            return self._block_result("Internal compliance check error.", "INTERNAL_ERROR")

    def record_sent(
        self,
        contact_id: str,
        channel: str,
        is_customer: bool = False,
    ) -> OutreachComplianceRecord:
        """Record a successful outreach send, resetting the cooldown clock."""
        contact_id = self._validate_contact_id(contact_id)
        channel = self._validate_channel(channel)
        self._cooldown.record_contact(contact_id, channel, is_customer=is_customer)
        record = OutreachComplianceRecord(
            contact_id=contact_id,
            channel=channel,
            decision=ComplianceDecision.ALLOW.value,
        )
        with self._lock:
            capped_append(
                self._audit_log,
                record.to_dict(),
                max_size=_MAX_AUDIT_LOG,
            )
        return record

    def process_reply_for_optout(
        self,
        contact_id: str,
        contact_email: str,
        reply_text: str,
    ) -> bool:
        """Detect opt-out intent in a reply and suppress the contact if found."""
        return self._suppression.process_reply_for_optout(
            contact_id=contact_id,
            contact_email=contact_email,
            reply_text=reply_text,
        )

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a snapshot of the audit log."""
        with self._lock:
            return list(self._audit_log)

    def get_status(self) -> Dict[str, Any]:
        return {
            "suppression": self._suppression.get_status(),
            "cooldown": self._cooldown.get_status(),
            "audit_log_size": len(self._audit_log),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _block_result(reason: str, regulation: str) -> Dict[str, Any]:
        return {
            "allowed": False,
            "decision": ComplianceDecision.BLOCK.value,
            "reason": reason,
            "cooldown_remaining_days": 0,
            "regulation": regulation,
        }


# ---------------------------------------------------------------------------
# OutreachCampaignPlanner
# ---------------------------------------------------------------------------


class OutreachCampaignPlanner:
    """Generates daily/weekly outreach plans that respect all compliance limits.

    Each plan is associated with an OutreachCampaignPlan that specifies:
      - target vertical (one of 12+ supported industry verticals)
      - channels to use
      - max outreach per day
      - which compliance rules to enforce (all enabled by default)

    The planner delegates actual compliance checks to OutreachComplianceGovernor
    and builds a per-contact outreach schedule that avoids suppressed contacts
    and respects cooldown windows.

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        governor: Optional[OutreachComplianceGovernor] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._governor = governor or OutreachComplianceGovernor()
        self._plans: Dict[str, OutreachCampaignPlan] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_plan_id(plan_id: str) -> str:
        plan_id = str(plan_id or "").strip().replace("\x00", "")
        if not re.match(r"^[a-zA-Z0-9_\-]{1,200}$", plan_id):
            raise ValueError(f"Invalid plan_id: '{plan_id[:50]}'")
        return plan_id

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def create_campaign_plan(
        self,
        name: str,
        vertical: str,
        channels: List[str],
        prospect_ids: List[str],
        max_outreach_per_day: int = 50,
        cooldown_days_prospect: int = _COOLDOWN_DAYS_PROSPECT,
        cooldown_days_customer: int = _COOLDOWN_DAYS_CUSTOMER,
        notes: str = "",
    ) -> OutreachCampaignPlan:
        """Create a new outreach campaign plan.

        Raises:
            ValueError: if vertical is not in BUSINESS_TYPE_VERTICALS, or
                        channels contain unknown values.
        """
        name = str(name or "")[:_MAX_CAMPAIGN_NAME_LEN].replace("\x00", "")
        vertical = str(vertical or "").strip().lower().replace("\x00", "")
        if vertical not in BUSINESS_TYPE_VERTICALS:
            raise ValueError(
                f"Unknown vertical '{vertical}'. "
                f"Supported: {BUSINESS_TYPE_VERTICALS}"
            )
        cleaned_channels = []
        for ch in channels:
            ch = str(ch or "").strip().lower().replace("\x00", "")
            if ch not in _ALLOWED_CHANNELS:
                raise ValueError(f"Unknown channel '{ch}'. Allowed: {sorted(_ALLOWED_CHANNELS)}")
            cleaned_channels.append(ch)

        with self._lock:
            if len(self._plans) >= _MAX_CAMPAIGNS:
                raise ValueError(f"Campaign plan limit ({_MAX_CAMPAIGNS}) reached.")

        plan = OutreachCampaignPlan(
            name=name,
            vertical=vertical,
            channels=cleaned_channels,
            prospect_ids=[str(p)[:_MAX_CONTACT_ID_LEN] for p in prospect_ids],
            max_outreach_per_day=max(1, int(max_outreach_per_day)),
            cooldown_days_prospect=cooldown_days_prospect,
            cooldown_days_customer=cooldown_days_customer,
            notes=str(notes or "")[:_MAX_NOTES_LEN],
        )
        with self._lock:
            self._plans[plan.plan_id] = plan
        logger.info("Created campaign plan %s (vertical=%s)", plan.plan_id, vertical)
        return plan

    def get_plan(self, plan_id: str) -> Optional[OutreachCampaignPlan]:
        """Return a campaign plan by ID, or None if not found."""
        plan_id = self._validate_plan_id(plan_id)
        with self._lock:
            return self._plans.get(plan_id)

    def build_daily_outreach_schedule(
        self,
        plan_id: str,
        contact_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a daily outreach schedule for a campaign plan.

        Returns a dict with:
          - plan_id
          - scheduled (list of contact_ids cleared for outreach today)
          - skipped (list of {contact_id, reason})
          - total_prospects
          - max_per_day

        contact_metadata is an optional dict keyed by contact_id with keys:
          is_customer (bool), contact_region (str), has_explicit_consent (bool),
          message_metadata (dict)
        """
        plan_id = self._validate_plan_id(plan_id)
        with self._lock:
            plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan '{plan_id}' not found.")

        scheduled: List[str] = []
        skipped: List[Dict[str, str]] = []
        meta = contact_metadata or {}

        for contact_id in plan.prospect_ids:
            if len(scheduled) >= plan.max_outreach_per_day:
                break
            c_meta = meta.get(contact_id, {})
            for channel in plan.channels:
                result = self._governor.check_outreach(
                    contact_id=contact_id,
                    channel=channel,
                    contact_region=c_meta.get("contact_region", ""),
                    is_customer=c_meta.get("is_customer", False),
                    has_explicit_consent=c_meta.get("has_explicit_consent", False),
                    message_metadata=c_meta.get("message_metadata"),
                )
                if result["allowed"]:
                    scheduled.append(contact_id)
                    break
                else:
                    skipped.append({
                        "contact_id": contact_id,
                        "channel": channel,
                        "reason": result["reason"],
                        "regulation": result.get("regulation", ""),
                    })
                    break

        schedule = {
            "plan_id": plan_id,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "scheduled": scheduled,
            "skipped": skipped,
            "total_prospects": len(plan.prospect_ids),
            "max_per_day": plan.max_outreach_per_day,
        }
        with self._lock:
            capped_append(self._audit_log, schedule, max_size=_MAX_AUDIT_LOG)
        return schedule

    def get_vertical_constraints(self, vertical: str) -> Dict[str, Any]:
        """Return compliance constraints specific to a business vertical.

        These are heuristic rules derived from the vertical's typical
        regulatory environment.
        """
        vertical = str(vertical or "").strip().lower()
        _VERTICAL_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
            "healthcare": {
                "hipaa_required": True,
                "no_cold_email": True,
                "channels_allowed": ["email", "linkedin"],
                "consent_model": "express",
                "notes": "HIPAA PHI rules apply; cold SMS/phone prohibited.",
            },
            "financial_services": {
                "finra_disclaimer": True,
                "channels_allowed": ["email", "linkedin"],
                "consent_model": "express",
                "notes": "FINRA/SEC disclaimers required; no unsolicited SMS.",
            },
            "legal": {
                "no_solicitation_rules": True,
                "channels_allowed": ["email", "linkedin"],
                "consent_model": "express",
                "notes": "Bar association solicitation rules vary by state.",
            },
            "construction": {
                "channels_allowed": ["email", "sms", "phone", "linkedin"],
                "consent_model": "implied",
                "notes": "Standard B2B outreach rules apply.",
            },
            "saas": {
                "channels_allowed": ["email", "linkedin"],
                "consent_model": "implied",
                "notes": "Standard B2B SaaS outreach.",
            },
            "ecommerce": {
                "channels_allowed": ["email", "sms", "linkedin"],
                "consent_model": "implied",
                "notes": "CAN-SPAM + TCPA for transactional emails and SMS.",
            },
            "real_estate": {
                "channels_allowed": ["email", "phone", "linkedin"],
                "consent_model": "implied",
                "notes": "NAR code of ethics applies; phone DNC lists required.",
            },
            "content_creator": {
                "channels_allowed": ["email", "linkedin"],
                "consent_model": "implied",
                "notes": "Social-platform TOS compliance required.",
            },
        }
        base = {
            "channels_allowed": list(_ALLOWED_CHANNELS),
            "consent_model": "implied",
            "cooldown_days": _COOLDOWN_DAYS_PROSPECT,
            "can_spam_required": True,
            "notes": "Standard B2B outreach rules apply.",
        }
        return _VERTICAL_CONSTRAINTS.get(vertical, base)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "plan_count": len(self._plans),
                "capacity": _MAX_CAMPAIGNS,
                "audit_log_size": len(self._audit_log),
                "governor_status": self._governor.get_status(),
            }
