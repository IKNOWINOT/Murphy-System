# Copyright © 2020 Inoni Limited Liability Company
# License: BSL 1.1
"""Contact Compliance Governor — centralized outreach enforcement gate.

Design Label: COMPL-001 — Contact Compliance Governor
Owner: Security Team / Legal
Dependencies:
    - thread_safe_operations.capped_append   (bounded audit log)
    - persistence_manager.PersistenceManager (save/load state)
    - event_backbone.EventBackbone           (optional, best-effort events)

Flow:
    Every outreach module calls ``validate_outreach()`` before sending any
    message.  The governor checks (in order):

    1. DNC (Do-Not-Contact) list — hard block, no override.
    2. Regulatory compliance gates — CAN-SPAM / TCPA / GDPR / CCPA / CASL.
    3. Contact cooldown — 30 days for non-customers, 7 days (configurable)
       for existing customer marketing outreach.

    The result is an ``OutreachDecision`` (ALLOW | BLOCK | REQUIRES_CONSENT).
    Every call is appended to an immutable, bounded audit log.

Safety invariants:
    - DNC entries are immutable; only re-opt-in removes them.
    - All mutable state is guarded by ``threading.Lock``.
    - Audit log is append-only and capped at _MAX_AUDIT_ENTRIES.
    - save_state / load_state follow the PersistenceManager pattern used
      by SelfImprovementEngine and SelfAutomationOrchestrator.
    - All public inputs are validated before processing (CWE-20).
    - Collection sizes are hard-capped to prevent memory exhaustion (CWE-400).
    - Raw email addresses are never written to log files (PII protection).
    - reply_text is capped before regex evaluation to prevent ReDoS (CWE-400).
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
# Input validation constants  [CWE-20]
# ---------------------------------------------------------------------------

# contact_id — alphanumeric + limited safe punctuation, 1–200 chars
_CONTACT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")

# email — conservative RFC-5321 pattern, max 254 chars
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MAX_EMAIL_LEN = 254  # RFC 5321 hard limit

# String field length caps
_MAX_REASON_LEN = 500           # DNC / audit reason
_MAX_ADDED_BY_LEN = 100         # add_to_dnc: added_by field
_MAX_CONSENT_PROOF_LEN = 500    # remove_from_dnc: consent_proof
_MAX_REPLY_TEXT_LEN = 50_000    # reply text before regex  [CWE-400 / ReDoS]

# message_metadata caps  [CWE-400]
_MAX_META_KEYS = 50
_MAX_META_KEY_LEN = 100
_MAX_META_VALUE_LEN = 1_000

# Collection hard caps  [CWE-400]
_MAX_DNC_ENTRIES = 10_000
_MAX_TRACKED_CONTACTS = 100_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DecisionType(str, Enum):
    """Possible outcomes of a compliance check."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRES_CONSENT = "REQUIRES_CONSENT"


class Regulation(str, Enum):
    """Regulations that may block an outreach attempt."""
    NONE = "NONE"
    CAN_SPAM = "CAN-SPAM"
    TCPA = "TCPA"
    GDPR = "GDPR"
    CCPA = "CCPA"
    CASL = "CASL"
    DNC = "DNC"
    COOLDOWN = "COOLDOWN"


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    LINKEDIN = "linkedin"
    PHONE = "phone"


class OutreachType(str, Enum):
    COLD_OUTREACH = "cold_outreach"
    FOLLOW_UP = "follow_up"
    MARKETING = "marketing"
    SERVICE = "service"
    TRANSACTIONAL = "transactional"


# Derived allowsets used by validators (built once at import time)
_VALID_CHANNELS: frozenset = frozenset(ch.value for ch in Channel)
_VALID_OUTREACH_TYPES: frozenset = frozenset(ot.value for ot in OutreachType)
_VALID_REGIONS: frozenset = frozenset({"", "US", "EU", "CA_US", "CA"})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OutreachDecision:
    """Result returned by ``ContactComplianceGovernor.validate_outreach()``."""
    allowed: bool
    decision: str                  # "ALLOW" | "BLOCK" | "REQUIRES_CONSENT"
    reason: str                    # Human-readable explanation
    regulation: str                # Which regulation blocked (or "NONE")
    cooldown_remaining_days: int   # Days until contact allowed again (0 if allowed)
    contact_id: str
    channel: str
    checked_at: str                # ISO 8601 timestamp


@dataclass
class DNCEntry:
    """A single Do-Not-Contact entry (immutable after creation)."""
    contact_id: str
    contact_email: str
    added_at: str
    reason: str
    added_by: str = "system"       # "system" | "contact" | "agent"
    consent_proof: Optional[str] = None  # Required to remove the entry


@dataclass
class ContactRecord:
    """Per-contact, per-channel outreach tracking."""
    contact_id: str
    channel: str
    last_contact_at: Optional[str] = None
    is_existing_customer: bool = False
    has_explicit_consent: bool = False
    suppressed: bool = False


# ---------------------------------------------------------------------------
# Regex patterns for opt-out detection
# ---------------------------------------------------------------------------

_OPTOUT_RE = re.compile(
    r"(unsubscribe|remove\s+me|stop|opt\s*out|do\s*not\s*contact|"
    r"please\s+remove|take\s+me\s+off|no\s+more\s+emails|"
    r"cancel\s+subscription|cease\s+contact)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# TCPA — quiet-hours window (8 am – 9 pm recipient local, approximated by UTC)
# ---------------------------------------------------------------------------

_TCPA_CALL_HOUR_START = 8   # 08:00
_TCPA_CALL_HOUR_END = 21    # 21:00  (calls *after* 9 pm are blocked)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ContactComplianceGovernor:
    """Centralized contact compliance enforcement gate.

    All outreach modules must call :meth:`validate_outreach` before
    sending any message.  The governor enforces:

    * DNC (Do-Not-Contact) list — hard, un-overridable block.
    * Regulatory compliance (CAN-SPAM, TCPA, GDPR, CCPA, CASL).
    * Cooldown windows (30 days non-customer; configurable for customers).

    Thread-safety: all mutations are protected by ``self._lock``.
    Persistence: ``save_state`` / ``load_state`` via PersistenceManager.

    Hardening invariants (CWE-20 / CWE-400):
        - contact_id validated against ``_CONTACT_ID_RE`` before any processing.
        - contact_email validated against ``_EMAIL_RE``, max 254 chars.
        - channel and outreach_type validated against closed allowlists.
        - contact_region validated against closed allowlist.
        - reply_text capped at ``_MAX_REPLY_TEXT_LEN`` before regex to prevent ReDoS.
        - message_metadata capped at ``_MAX_META_KEYS`` keys / ``_MAX_META_KEY_LEN`` key
          chars / ``_MAX_META_VALUE_LEN`` value chars.
        - DNC list hard-capped at ``_MAX_DNC_ENTRIES`` (CWE-400).
        - Contact tracking hard-capped at ``_MAX_TRACKED_CONTACTS`` (CWE-400).
        - Raw email never written to log files (PII protection).
        - load_state caps loaded collections to prevent persistence-based OOM.
    """

    _PERSIST_DOC_ID = "contact_compliance_governor_state"
    _MAX_AUDIT_ENTRIES = 100_000

    def __init__(
        self,
        persistence_manager: Any = None,
        event_backbone: Any = None,
        non_customer_cooldown_days: int = 30,
        customer_marketing_cooldown_days: int = 7,
    ) -> None:
        self._lock = threading.Lock()
        self._persistence = persistence_manager
        self._backbone = event_backbone

        self._non_customer_cooldown = non_customer_cooldown_days
        self._customer_marketing_cooldown = customer_marketing_cooldown_days

        # contact_id → {channel → ContactRecord}
        self._contacts: Dict[str, Dict[str, ContactRecord]] = {}

        # contact_id → DNCEntry
        self._dnc: Dict[str, DNCEntry] = {}

        # Immutable append-only audit trail
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input validators  [CWE-20]
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_contact_id(contact_id: str) -> str:
        """Validate contact_id matches safe pattern (CWE-20).

        Raises ValueError on invalid input.
        """
        if not isinstance(contact_id, str) or not _CONTACT_ID_RE.match(contact_id):
            raise ValueError("Invalid contact_id format")
        return contact_id

    @staticmethod
    def _validate_email(contact_email: str) -> str:
        """Validate email format and length (CWE-20). Never log raw value (PII).

        Raises ValueError on invalid input.
        """
        if not isinstance(contact_email, str):
            raise ValueError("Invalid contact_email")
        if len(contact_email) > _MAX_EMAIL_LEN:
            raise ValueError("contact_email exceeds maximum length")
        if not _EMAIL_RE.match(contact_email):
            raise ValueError("Invalid contact_email format")
        return contact_email

    @staticmethod
    def _validate_channel(channel: str) -> str:
        """Validate channel is in the closed allowlist (CWE-20).

        Raises ValueError on invalid input.
        """
        if not isinstance(channel, str) or channel.lower() not in _VALID_CHANNELS:
            raise ValueError(
                f"Invalid channel — must be one of {sorted(_VALID_CHANNELS)}"
            )
        return channel.lower()

    @staticmethod
    def _validate_outreach_type(outreach_type: str) -> str:
        """Validate outreach_type is in the closed allowlist (CWE-20).

        Raises ValueError on invalid input.
        """
        if not isinstance(outreach_type, str) or outreach_type.lower() not in _VALID_OUTREACH_TYPES:
            raise ValueError(
                f"Invalid outreach_type — must be one of {sorted(_VALID_OUTREACH_TYPES)}"
            )
        return outreach_type.lower()

    @staticmethod
    def _validate_region(contact_region: str) -> str:
        """Validate contact_region is in the closed allowlist (CWE-20).

        Raises ValueError on invalid input.
        """
        if not isinstance(contact_region, str):
            raise ValueError("Invalid contact_region")
        region = contact_region.upper()
        if region not in _VALID_REGIONS:
            raise ValueError(
                f"Invalid contact_region — must be one of {sorted(_VALID_REGIONS)}"
            )
        return region

    @staticmethod
    def _sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Cap message_metadata keys, key lengths, and value lengths (CWE-400)."""
        if not isinstance(meta, dict):
            return {}
        result: Dict[str, Any] = {}
        for k, v in list(meta.items())[:_MAX_META_KEYS]:
            if not isinstance(k, str):
                continue
            k = k[:_MAX_META_KEY_LEN]
            if isinstance(v, str):
                v = v[:_MAX_META_VALUE_LEN]
            result[k] = v
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_outreach(
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
        """Check whether an outreach attempt is compliant.

        Args:
            contact_id:          Unique contact identifier.
            contact_email:       Contact e-mail address.
            channel:             Delivery channel (email/sms/linkedin/phone).
            outreach_type:       Nature of the message (cold_outreach/follow_up/
                                 marketing/service/transactional).
            contact_region:      Regulatory jurisdiction ("US" | "EU" | "CA_US"
                                 | "CA" | "").
            is_existing_customer: True if contact is an existing customer.
            has_explicit_consent: True if contact has given written consent.
            message_metadata:    Dict with optional keys:
                                   has_unsubscribe_link (bool),
                                   has_physical_address (bool),
                                   subject (str),
                                   hour_utc (int)   — for TCPA check.

        Returns:
            :class:`OutreachDecision` with ``allowed``, ``decision``,
            ``reason``, ``regulation``, and ``cooldown_remaining_days``.

        Raises:
            ValueError: if contact_id, contact_email, channel, outreach_type,
                        or contact_region fail validation (CWE-20).
        """
        # -- Input validation (CWE-20) ------------------------------------
        contact_id = self._validate_contact_id(contact_id)
        self._validate_email(contact_email)         # validate but don't re-bind (PII)
        channel = self._validate_channel(channel)
        outreach_type = self._validate_outreach_type(outreach_type)
        contact_region = self._validate_region(contact_region)
        meta = self._sanitize_metadata(message_metadata)
        # -----------------------------------------------------------------

        checked_at = datetime.now(timezone.utc).isoformat()

        def _block(reason: str, regulation: Regulation, cooldown: int = 0) -> OutreachDecision:
            decision = OutreachDecision(
                allowed=False,
                decision=DecisionType.BLOCK.value,
                reason=reason,
                regulation=regulation.value,
                cooldown_remaining_days=cooldown,
                contact_id=contact_id,
                channel=channel,
                checked_at=checked_at,
            )
            self._record_audit(decision)
            self._publish("OUTREACH_BLOCKED", {
                "contact_id": contact_id,
                "channel": channel,
                "reason": reason,
                "regulation": regulation.value,
            })
            return decision

        def _consent_required(reason: str, regulation: Regulation) -> OutreachDecision:
            decision = OutreachDecision(
                allowed=False,
                decision=DecisionType.REQUIRES_CONSENT.value,
                reason=reason,
                regulation=regulation.value,
                cooldown_remaining_days=0,
                contact_id=contact_id,
                channel=channel,
                checked_at=checked_at,
            )
            self._record_audit(decision)
            self._publish("OUTREACH_BLOCKED", {
                "contact_id": contact_id,
                "channel": channel,
                "reason": reason,
                "regulation": regulation.value,
            })
            return decision

        # 1. DNC check — hard block, no override
        with self._lock:
            on_dnc = contact_id in self._dnc
        if on_dnc:
            return _block(
                "Contact is on the Do-Not-Contact list.",
                Regulation.DNC,
            )

        # 2. Regulatory compliance gates
        reg_decision = self._check_regulations(
            channel=channel,
            outreach_type=outreach_type,
            contact_region=contact_region,
            has_explicit_consent=has_explicit_consent,
            meta=meta,
        )
        if reg_decision is not None:
            reason, regulation, requires_consent = reg_decision
            if requires_consent:
                return _consent_required(reason, regulation)
            return _block(reason, regulation)

        # 3. Cooldown check
        is_service = outreach_type in (
            OutreachType.SERVICE.value,
            OutreachType.TRANSACTIONAL.value,
        )
        if is_existing_customer and is_service:
            # Exempt from cooldown for service/transactional messages
            pass
        else:
            cooldown_days = (
                self._customer_marketing_cooldown
                if is_existing_customer
                else self._non_customer_cooldown
            )
            remaining = self._cooldown_remaining(contact_id, channel, cooldown_days)
            if remaining > 0:
                return _block(
                    f"Contact is in cooldown period — {remaining} day(s) remaining.",
                    Regulation.COOLDOWN,
                    cooldown=remaining,
                )

        # 4. ALLOW — record last contact
        self._record_contact(contact_id, channel, is_existing_customer, has_explicit_consent)

        decision = OutreachDecision(
            allowed=True,
            decision=DecisionType.ALLOW.value,
            reason="All compliance checks passed.",
            regulation=Regulation.NONE.value,
            cooldown_remaining_days=0,
            contact_id=contact_id,
            channel=channel,
            checked_at=checked_at,
        )
        self._record_audit(decision)
        return decision

    def add_to_dnc(
        self,
        contact_id: str,
        contact_email: str,
        reason: str,
        added_by: str = "system",
        consent_proof: Optional[str] = None,
    ) -> DNCEntry:
        """Add a contact to the Do-Not-Contact list.

        DNC entries are immutable once added.  Only
        :meth:`remove_from_dnc_with_consent` can remove them.

        Raises:
            ValueError: if contact_id or contact_email fail validation (CWE-20).
            ValueError: if the DNC list is at capacity (CWE-400).
        """
        contact_id = self._validate_contact_id(contact_id)
        self._validate_email(contact_email)  # validate; raw email not logged (PII)

        # Cap free-text fields (CWE-400)
        reason = str(reason)[:_MAX_REASON_LEN] if reason else ""
        added_by = str(added_by)[:_MAX_ADDED_BY_LEN] if added_by else "system"

        with self._lock:
            if len(self._dnc) >= _MAX_DNC_ENTRIES:
                raise ValueError(
                    f"DNC list has reached capacity ({_MAX_DNC_ENTRIES} entries). "
                    "Contact an administrator to resolve."
                )

        entry = DNCEntry(
            contact_id=contact_id,
            contact_email=contact_email,
            added_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            added_by=added_by,
            consent_proof=consent_proof,
        )
        with self._lock:
            self._dnc[contact_id] = entry
        # Log contact_id only — never log raw email (PII)
        logger.info("DNC: added contact %s", contact_id)
        self._publish("DNC_ADDED", {
            "contact_id": contact_id,
            "reason": reason,
            "added_by": added_by,
        })
        return entry

    def remove_from_dnc_with_consent(
        self,
        contact_id: str,
        consent_proof: str,
    ) -> bool:
        """Remove a contact from DNC only when they have re-opted in.

        Args:
            contact_id:    Contact to remove.
            consent_proof: Non-empty string proving re-opt-in (e.g. form ID).

        Returns:
            True if removed, False if not found or consent_proof empty.

        Raises:
            ValueError: if contact_id fails validation (CWE-20).
        """
        contact_id = self._validate_contact_id(contact_id)
        if not consent_proof or not consent_proof.strip():
            logger.warning("DNC removal refused — consent_proof required for %s", contact_id)
            return False
        # Cap consent_proof length (CWE-400)
        consent_proof = consent_proof[:_MAX_CONSENT_PROOF_LEN]
        with self._lock:
            if contact_id not in self._dnc:
                return False
            del self._dnc[contact_id]
        logger.info("DNC: removed contact %s with consent proof", contact_id)
        return True

    def is_on_dnc(self, contact_id: str) -> bool:
        """Return True if the contact is on the DNC list.

        Raises:
            ValueError: if contact_id fails validation (CWE-20).
        """
        contact_id = self._validate_contact_id(contact_id)
        with self._lock:
            return contact_id in self._dnc

    def detect_optout_intent(self, reply_text: str) -> bool:
        """Return True if *reply_text* contains opt-out intent.

        Caps input at ``_MAX_REPLY_TEXT_LEN`` before regex to prevent ReDoS
        (CWE-400).
        """
        if not isinstance(reply_text, str):
            return False
        # Cap before regex to prevent ReDoS on arbitrarily large input (CWE-400)
        capped = reply_text[:_MAX_REPLY_TEXT_LEN]
        return bool(_OPTOUT_RE.search(capped))

    def process_reply_for_optout(
        self,
        contact_id: str,
        contact_email: str,
        reply_text: str,
    ) -> bool:
        """If *reply_text* signals opt-out, add contact to DNC automatically.

        Returns True if contact was added to DNC, False otherwise.

        Raises:
            ValueError: if contact_id or contact_email fail validation (CWE-20).
        """
        contact_id = self._validate_contact_id(contact_id)
        self._validate_email(contact_email)
        if self.detect_optout_intent(reply_text):
            self.add_to_dnc(
                contact_id=contact_id,
                contact_email=contact_email,
                reason="Opt-out detected in reply text.",
                added_by="system",
            )
            self._publish("CONTACT_SUPPRESSED", {
                "contact_id": contact_id,
                "trigger": "reply_optout",
            })
            return True
        return False

    # ------------------------------------------------------------------
    # Persistence  [COMPL-001]
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """Persist governor state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._persistence is None:
            logger.debug("No PersistenceManager attached; skipping save_state")
            return False
        with self._lock:
            state = {
                "dnc": {
                    cid: {
                        "contact_id": e.contact_id,
                        "contact_email": e.contact_email,
                        "added_at": e.added_at,
                        "reason": e.reason,
                        "added_by": e.added_by,
                        "consent_proof": e.consent_proof,
                    }
                    for cid, e in self._dnc.items()
                },
                "contacts": {
                    cid: {
                        ch: {
                            "contact_id": r.contact_id,
                            "channel": r.channel,
                            "last_contact_at": r.last_contact_at,
                            "is_existing_customer": r.is_existing_customer,
                            "has_explicit_consent": r.has_explicit_consent,
                            "suppressed": r.suppressed,
                        }
                        for ch, r in channels.items()
                    }
                    for cid, channels in self._contacts.items()
                },
                "audit_log": list(self._audit_log),
            }
        try:
            self._persistence.save_document(self._PERSIST_DOC_ID, state)
            logger.info("ContactComplianceGovernor state persisted")
            return True
        except Exception as exc:
            logger.error("Failed to persist ContactComplianceGovernor state: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore governor state from PersistenceManager.

        Returns True on success, False if persistence unavailable or no
        prior state exists.
        """
        if self._persistence is None:
            logger.debug("No PersistenceManager attached; skipping load_state")
            return False
        try:
            state = self._persistence.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:
            logger.error("Failed to load ContactComplianceGovernor state: %s", exc)
            return False
        if state is None:
            logger.debug("No prior ContactComplianceGovernor state found")
            return False
        with self._lock:
            # Cap loaded DNC entries to hard limit (CWE-400)
            dnc_items = list(state.get("dnc", {}).items())[:_MAX_DNC_ENTRIES]
            self._dnc = {
                cid: DNCEntry(
                    contact_id=e["contact_id"],
                    contact_email=e["contact_email"],
                    added_at=e["added_at"],
                    reason=str(e.get("reason", ""))[:_MAX_REASON_LEN],
                    added_by=str(e.get("added_by", "system"))[:_MAX_ADDED_BY_LEN],
                    consent_proof=e.get("consent_proof"),
                )
                for cid, e in dnc_items
            }
            # Cap loaded contacts to hard limit (CWE-400)
            contact_items = list(state.get("contacts", {}).items())[:_MAX_TRACKED_CONTACTS]
            self._contacts = {
                cid: {
                    ch: ContactRecord(
                        contact_id=r["contact_id"],
                        channel=r["channel"],
                        last_contact_at=r.get("last_contact_at"),
                        is_existing_customer=r.get("is_existing_customer", False),
                        has_explicit_consent=r.get("has_explicit_consent", False),
                        suppressed=r.get("suppressed", False),
                    )
                    for ch, r in channels.items()
                }
                for cid, channels in contact_items
            }
            # Cap loaded audit log to hard limit (CWE-400)
            self._audit_log = list(state.get("audit_log", []))[:self._MAX_AUDIT_ENTRIES]
        logger.info(
            "ContactComplianceGovernor state restored (%d DNC, %d contacts, %d audit entries)",
            len(self._dnc), len(self._contacts), len(self._audit_log),
        )
        return True

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a snapshot of the audit log (read-only copy)."""
        with self._lock:
            return list(self._audit_log)

    def get_dnc_list(self) -> List[DNCEntry]:
        """Return all DNC entries (read-only copy)."""
        with self._lock:
            return list(self._dnc.values())

    def get_status(self) -> Dict[str, Any]:
        """Return summary statistics."""
        with self._lock:
            return {
                "dnc_count": len(self._dnc),
                "tracked_contacts": len(self._contacts),
                "audit_entries": len(self._audit_log),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_regulations(
        self,
        channel: str,
        outreach_type: str,
        contact_region: str,
        has_explicit_consent: bool,
        meta: Dict[str, Any],
    ) -> Optional[tuple[str, Regulation, bool]]:
        """Return ``(reason, Regulation, requires_consent)`` if blocked, else None."""
        region = contact_region.upper()
        ch = channel.lower()
        otype = outreach_type.lower()
        is_marketing = otype in (
            OutreachType.COLD_OUTREACH.value,
            OutreachType.FOLLOW_UP.value,
            OutreachType.MARKETING.value,
        )

        # CAN-SPAM (US email)
        if ch == Channel.EMAIL.value and region in ("US", ""):
            if is_marketing:
                if not meta.get("has_unsubscribe_link", False):
                    return (
                        "CAN-SPAM requires a clear unsubscribe mechanism in every marketing email.",
                        Regulation.CAN_SPAM,
                        False,
                    )
                if not meta.get("has_physical_address", False):
                    return (
                        "CAN-SPAM requires a sender physical address in every marketing email.",
                        Regulation.CAN_SPAM,
                        False,
                    )

        # TCPA (US phone/SMS)
        if ch in (Channel.SMS.value, Channel.PHONE.value) and region in ("US", "CA_US", ""):
            if is_marketing and not has_explicit_consent:
                return (
                    "TCPA requires prior express written consent for marketing calls/texts.",
                    Regulation.TCPA,
                    True,
                )
            # Time-of-day enforcement (8 am – 9 pm recipient local, proxied via UTC)
            hour_utc = meta.get("hour_utc")
            if hour_utc is not None:
                try:
                    h = int(hour_utc)
                    if not (_TCPA_CALL_HOUR_START <= h < _TCPA_CALL_HOUR_END):
                        return (
                            f"TCPA prohibits calls/texts before 8 am or after 9 pm (hour_utc={h}).",
                            Regulation.TCPA,
                            False,
                        )
                except (ValueError, TypeError):  # PROD-HARD A2: malformed hour_utc shouldn't silently bypass TCPA gate
                    logger.warning("TCPA quiet-hour check skipped: hour_utc=%r is not coercible to int", hour_utc)

        # GDPR (EU)
        if region == "EU":
            if is_marketing and not has_explicit_consent:
                return (
                    "GDPR requires a lawful basis (explicit consent) for EU marketing outreach.",
                    Regulation.GDPR,
                    True,
                )

        # CCPA (California)
        if region == "CA_US":
            if meta.get("do_not_sell_requested", False):
                return (
                    "CCPA: contact has exercised their right to opt out of data sale/use for marketing.",
                    Regulation.CCPA,
                    False,
                )

        # CASL (Canada)
        if region == "CA":
            if is_marketing and not has_explicit_consent:
                return (
                    "CASL requires express consent for commercial electronic messages to Canadian contacts.",
                    Regulation.CASL,
                    True,
                )

        return None

    def _cooldown_remaining(
        self,
        contact_id: str,
        channel: str,
        cooldown_days: int,
    ) -> int:
        """Return number of days remaining in cooldown (0 if none)."""
        with self._lock:
            channels = self._contacts.get(contact_id, {})
            record = channels.get(channel)
            if record is None or record.last_contact_at is None:
                return 0
            try:
                last = datetime.fromisoformat(record.last_contact_at)
            except ValueError:
                return 0
            now = datetime.now(timezone.utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = (now - last).days
            remaining = cooldown_days - delta
            return max(0, remaining)

    def _record_contact(
        self,
        contact_id: str,
        channel: str,
        is_existing_customer: bool,
        has_explicit_consent: bool,
    ) -> None:
        """Update the last-contact timestamp for contact+channel.

        Enforces ``_MAX_TRACKED_CONTACTS`` hard cap by evicting the oldest
        10% of contacts when capacity is reached (CWE-400).
        """
        with self._lock:
            if contact_id not in self._contacts:
                if len(self._contacts) >= _MAX_TRACKED_CONTACTS:
                    # Evict oldest 10% of tracked contacts (CWE-400)
                    evict_count = _MAX_TRACKED_CONTACTS // 10
                    evict_keys = list(self._contacts.keys())[:evict_count]
                    for k in evict_keys:
                        del self._contacts[k]
                    logger.debug(
                        "ContactComplianceGovernor: evicted %d contact records (cap=%d)",
                        evict_count, _MAX_TRACKED_CONTACTS,
                    )
                self._contacts[contact_id] = {}
            self._contacts[contact_id][channel] = ContactRecord(
                contact_id=contact_id,
                channel=channel,
                last_contact_at=datetime.now(timezone.utc).isoformat(),
                is_existing_customer=is_existing_customer,
                has_explicit_consent=has_explicit_consent,
            )

    def _record_audit(self, decision: OutreachDecision) -> None:
        """Append decision to the immutable, bounded audit log."""
        entry = {
            "audit_id": uuid.uuid4().hex,
            "contact_id": decision.contact_id,
            "channel": decision.channel,
            "decision": decision.decision,
            "reason": decision.reason,
            "regulation": decision.regulation,
            "cooldown_remaining_days": decision.cooldown_remaining_days,
            "timestamp": decision.checked_at,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=self._MAX_AUDIT_ENTRIES)

    def _publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish an event to EventBackbone if available (best-effort).

        The merged payload always includes ``source`` and ``action`` keys.
        Caller-supplied keys with the same names will be overwritten by the
        envelope values.

        Falls back to the global backbone via ``event_backbone_client`` when
        no backbone was injected at construction time.
        """
        try:
            from event_backbone import EventType
            backbone = self._backbone
            if backbone is None:
                try:
                    import event_backbone_client as _ebc
                    backbone = _ebc.get_backbone()
                except Exception:
                    logger.debug("Suppressed exception in contact_compliance_governor")
            if backbone is None:
                logger.warning("ContactComplianceGovernor: no backbone available")
                return
            # Map known event names to EventType values
            event_type_map: Dict[str, Any] = {
                "OUTREACH_BLOCKED": EventType.TASK_FAILED,
                "DNC_ADDED": EventType.LEARNING_FEEDBACK,
                "CONTACT_SUPPRESSED": EventType.TASK_FAILED,
            }
            et = event_type_map.get(event_name, EventType.LEARNING_FEEDBACK)
            backbone.publish(
                event_type=et,
                payload={
                    **payload,
                    "source": "contact_compliance_governor",
                    "action": event_name.lower(),
                },
            )
        except Exception as exc:
            logger.debug("ContactComplianceGovernor: event publish skipped: %s", exc)


__all__ = [
    "ContactComplianceGovernor",
    "OutreachDecision",
    "DNCEntry",
    "ContactRecord",
    "DecisionType",
    "Regulation",
    "Channel",
    "OutreachType",
]
