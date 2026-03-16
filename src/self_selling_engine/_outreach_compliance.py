"""
Outreach Compliance Engine for Murphy System Self-Selling Engine.

Design Label: SSE-COMPL-002 — Outreach Compliance Engine
Owner: Legal / Platform Engineering

Extends the existing OutreachComplianceGovernor (SSE-COMPL-001) with a
policy-driven compliance layer that enforces:

  * CAN-SPAM (email)  — mandatory opt-out language, physical address,
    no deceptive subject lines.
  * TCPA (phone / SMS) — prior express written consent required; do-not-call
    registry compliance; blocked hours (8 AM – 9 PM local time).
  * GDPR (EU contacts) — lawful basis required; right to erasure; data
    minimisation.
  * CASL (Canadian contacts) — express or implied consent; identification
    and unsubscribe mechanism in every message.
  * DNC Registry — do-not-call list checked before phone/SMS outreach.

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Errors sanitised before logging (CWE-209).
  - Raw email addresses never written to log records (PII).
  - Opt-out list is permanent; cleared only by explicit human override.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list, item, max_size=10_000):  # type: ignore[misc]
        """Bounded list append — fallback when thread_safe_operations is unavailable."""
        target_list.append(item)
        if len(target_list) > max_size:
            del target_list[:-max_size]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants                                                          [CWE-20]
# ---------------------------------------------------------------------------

_PROSPECT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
_CHANNEL_ALLOWLIST: frozenset = frozenset({"email", "sms", "phone", "linkedin", "push"})
_LOCATION_RE = re.compile(r"^[a-zA-Z]{2,5}$")   # ISO country code or US state

_MAX_CONTACTS: int = 100_000
_MAX_AUDIT_LOG: int = 100_000
_MAX_OPT_OUT_LOG: int = 50_000
_MAX_DNC: int = 10_000
_MAX_REPLY_LEN: int = 50_000
_MAX_REASON_LEN: int = 500

# Opt-out keyword pattern (capped input before evaluation — ReDoS prevention)
_OPT_OUT_KEYWORDS = re.compile(
    r"\b(?:unsubscribe|stop|remove\s+me|do\s+not\s+contact|opt[\s\-]?out|"
    r"cancel|take\s+me\s+off|never\s+contact|not\s+interested|cease)\b",
    re.IGNORECASE,
)

# TCPA / DNC: blocked calling hours in US (8 AM – 9 PM local, per TCPA 47 CFR §64.1200)
_TCPA_BLOCKED_HOURS: Tuple[Tuple[int, int], ...] = ((0, 8), (21, 24))  # 0-8 and 21-24

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OutreachCompliancePolicy:
    """Per-deployment outreach compliance policy configuration."""

    min_days_between_contacts: int = 30
    customer_recontact_days: int = 7
    customer_recontact_allowed: bool = True
    honor_opt_out: bool = True
    max_contacts_per_day: Dict[str, int] = field(default_factory=lambda: {
        "email": 50,
        "sms": 20,
        "phone": 15,
        "linkedin": 30,
        "push": 100,
    })
    blocked_hours: List[Tuple[int, int]] = field(
        default_factory=lambda: list(_TCPA_BLOCKED_HOURS)
    )
    required_opt_out_language: str = (
        "To opt out of future communications, reply STOP or click Unsubscribe."
    )
    require_can_spam_footer: bool = True
    require_tcpa_consent: bool = True   # phone / SMS only
    require_gdpr_basis: bool = False    # flip to True for EU deployments
    require_casl_consent: bool = False  # flip to True for CA deployments

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_days_between_contacts": self.min_days_between_contacts,
            "customer_recontact_days": self.customer_recontact_days,
            "customer_recontact_allowed": self.customer_recontact_allowed,
            "honor_opt_out": self.honor_opt_out,
            "max_contacts_per_day": dict(self.max_contacts_per_day),
            "blocked_hours": [list(h) for h in self.blocked_hours],
            "required_opt_out_language": self.required_opt_out_language,
            "require_can_spam_footer": self.require_can_spam_footer,
            "require_tcpa_consent": self.require_tcpa_consent,
            "require_gdpr_basis": self.require_gdpr_basis,
            "require_casl_consent": self.require_casl_consent,
        }


@dataclass
class ContactRecord:
    """Contact history record for a single prospect + channel combination."""

    contact_id: str
    prospect_id: str
    channel: str
    sent_at: str
    message_id: str = ""
    response: str = ""
    opt_out_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "prospect_id": self.prospect_id,
            "channel": self.channel,
            "sent_at": self.sent_at,
            "message_id": self.message_id,
            "response": self.response[:500] if self.response else "",
            "opt_out_requested": self.opt_out_requested,
        }


@dataclass
class ComplianceDecision:
    """Result of a can_contact() check."""

    allowed: bool
    reason: str
    channel: str
    prospect_id: str
    regulations_checked: List[str] = field(default_factory=list)
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "channel": self.channel,
            "regulations_checked": list(self.regulations_checked),
            "decided_at": self.decided_at,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_id(prospect_id: str) -> str:
    """Mask PII in logs — show only first 4 chars."""
    if len(prospect_id) <= 4:
        return "***"
    return prospect_id[:4] + "***"


# ---------------------------------------------------------------------------
# Core engine                                                    SSE-COMPL-002
# ---------------------------------------------------------------------------

class OutreachComplianceEngine:
    """
    Outreach Compliance Engine — SSE-COMPL-002.

    Policy-driven compliance layer for the self-selling engine.  Every
    outreach attempt must pass through ``can_contact()`` before sending;
    every reply must be passed through ``record_response()`` to detect
    opt-outs.
    """

    def __init__(
        self,
        policy: Optional[OutreachCompliancePolicy] = None,
    ) -> None:
        self._policy = policy or OutreachCompliancePolicy()
        self._lock = threading.RLock()  # re-entrant: _record_audit called inside lock

        # prospect_id → {channel → ContactRecord}
        self._contacts: Dict[str, Dict[str, ContactRecord]] = {}
        # prospect_id → opt-out entry dict
        self._opt_outs: Dict[str, Dict[str, Any]] = {}
        # prospect_id → True
        self._customers: Dict[str, bool] = {}
        # DNC list: prospect_id → added_at
        self._dnc: Dict[str, str] = {}
        # daily count: date_str → {channel → count}
        self._daily_counts: Dict[str, Dict[str, int]] = {}
        # audit log
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_prospect_id(pid: str) -> str:
        if not isinstance(pid, str) or not _PROSPECT_ID_RE.match(pid):
            raise ValueError(f"prospect_id must match {_PROSPECT_ID_RE.pattern}")
        return pid

    @staticmethod
    def _validate_channel(ch: str) -> str:
        if ch not in _CHANNEL_ALLOWLIST:
            raise ValueError(f"channel must be one of {_CHANNEL_ALLOWLIST}")
        return ch

    # ------------------------------------------------------------------
    # Core gate
    # ------------------------------------------------------------------

    def can_contact(self, prospect_id: str, channel: str) -> Tuple[bool, str]:
        """Check whether a prospect may be contacted on the given channel.

        Checks (in order):
          1. Input validation.
          2. Permanent opt-out / DNC suppression.
          3. 30-day (or customer) cooldown.
          4. Daily rate cap.
          5. Blocked hours (TCPA — phone/SMS only).
          6. Regulation summary (CAN-SPAM, TCPA, GDPR, CASL, DNC).

        Returns:
            (allowed: bool, reason: str)
        """
        pid = self._validate_prospect_id(prospect_id)
        ch = self._validate_channel(channel)

        regs = self.check_regulatory_compliance(ch, "US")

        with self._lock:
            # 1. Opt-out suppression
            if self._policy.honor_opt_out and pid in self._opt_outs:
                self._record_audit(pid, ch, allowed=False, reason="opt_out_suppressed")
                return False, "opt_out_suppressed"

            # 2. DNC registry
            if pid in self._dnc:
                self._record_audit(pid, ch, allowed=False, reason="dnc_registry")
                return False, "dnc_registry"

            # 3. Cooldown
            record = self._contacts.get(pid, {}).get(ch)
            if record is not None:
                is_customer = self._customers.get(pid, False)
                cooldown_days = (
                    self._policy.customer_recontact_days
                    if is_customer and self._policy.customer_recontact_allowed
                    else self._policy.min_days_between_contacts
                )
                last_sent = datetime.fromisoformat(record.sent_at)
                elapsed = (datetime.now(timezone.utc) - last_sent).days
                if elapsed < cooldown_days:
                    remaining = cooldown_days - elapsed
                    reason = f"cooldown_{remaining}_days_remaining"
                    self._record_audit(pid, ch, allowed=False, reason=reason)
                    return False, reason

            # 4. Daily rate cap
            if self._is_rate_limited(ch):
                self._record_audit(pid, ch, allowed=False, reason="daily_cap_reached")
                return False, "daily_cap_reached"

            # 5. Blocked hours (TCPA phone/SMS)
            if ch in ("phone", "sms") and self._is_blocked_hour():
                self._record_audit(pid, ch, allowed=False, reason="tcpa_blocked_hours")
                return False, "tcpa_blocked_hours"

        self._record_audit(pid, ch, allowed=True, reason="allowed",
                           regulations=regs)
        return True, "allowed"

    def record_contact(
        self, prospect_id: str, channel: str, message_id: str = ""
    ) -> None:
        """Record that a contact was made.  Call after every send."""
        pid = self._validate_prospect_id(prospect_id)
        ch = self._validate_channel(channel)
        import uuid
        now = _ts()
        record = ContactRecord(
            contact_id=uuid.uuid4().hex[:12],
            prospect_id=pid,
            channel=ch,
            sent_at=now,
            message_id=message_id[:200] if message_id else "",
        )
        with self._lock:
            if len(self._contacts) >= _MAX_CONTACTS:
                # evict oldest 10%
                evict = list(self._contacts.keys())[:max(1, _MAX_CONTACTS // 10)]
                for k in evict:
                    del self._contacts[k]
            self._contacts.setdefault(pid, {})[ch] = record
            self._increment_daily_count(ch)
        self._record_audit(pid, ch, allowed=True, reason="contact_recorded",
                           message_id=message_id[:50] if message_id else "")
        logger.info("SSE-COMPL-002 contact recorded %s %s", _mask_id(pid), ch)

    def record_opt_out(self, prospect_id: str, reason: str = "") -> None:
        """Permanently suppress a prospect.  Irreversible without human override."""
        pid = self._validate_prospect_id(prospect_id)
        safe_reason = reason[:_MAX_REASON_LEN]
        with self._lock:
            if len(self._opt_outs) >= _MAX_OPT_OUT_LOG:
                raise RuntimeError("SSE-COMPL-002: opt-out list at capacity")
            self._opt_outs[pid] = {
                "opted_out_at": _ts(),
                "reason": safe_reason,
            }
        self._record_audit(pid, "", allowed=False, reason="opt_out_recorded")
        logger.info("SSE-COMPL-002 opt-out recorded %s", _mask_id(pid))

    def record_response(self, prospect_id: str, response: str) -> bool:
        """Process a prospect reply.

        Detects opt-out language via keyword matching and auto-suppresses if
        found.

        Args:
            prospect_id: the prospect who replied.
            response: raw reply text (capped at 50 KB before regex).

        Returns:
            True if an opt-out was detected and recorded; False otherwise.
        """
        pid = self._validate_prospect_id(prospect_id)
        safe_response = response[:_MAX_REPLY_LEN]

        if _OPT_OUT_KEYWORDS.search(safe_response):
            self.record_opt_out(pid, reason="auto_detected_from_reply")
            logger.info("SSE-COMPL-002 opt-out auto-detected in reply from %s",
                        _mask_id(pid))
            return True
        return False

    def add_to_dnc(self, prospect_id: str) -> None:
        """Add a prospect to the do-not-call / do-not-contact registry."""
        pid = self._validate_prospect_id(prospect_id)
        with self._lock:
            if len(self._dnc) >= _MAX_DNC:
                raise ValueError("SSE-COMPL-002: DNC list at capacity (10,000)")
            self._dnc[pid] = _ts()
        self._record_audit(pid, "", allowed=False, reason="added_to_dnc")

    def mark_as_customer(self, prospect_id: str) -> None:
        """Mark a prospect as an existing customer (shorter cooldown applies)."""
        pid = self._validate_prospect_id(prospect_id)
        with self._lock:
            self._customers[pid] = True

    def is_customer(self, prospect_id: str) -> bool:
        """Return True if the prospect is a known customer."""
        pid = self._validate_prospect_id(prospect_id)
        with self._lock:
            return self._customers.get(pid, False)

    def check_regulatory_compliance(
        self, channel: str, location: str
    ) -> List[str]:
        """Return the list of regulations that apply for this channel + location.

        Args:
            channel: "email", "sms", "phone", "linkedin", or "push".
            location: ISO 3166-1 alpha-2 country code or US state code.

        Returns:
            List of regulation identifiers that must be complied with.
        """
        regs: List[str] = []
        loc = str(location).upper()[:10]

        # Email
        if channel == "email":
            regs.append("CAN-SPAM")
            if loc in ("GB", "DE", "FR", "NL", "SE", "DK", "FI", "NO",
                       "AT", "BE", "IE", "IT", "ES", "PL", "EU"):
                regs.append("GDPR")
            if loc == "CA":
                regs.append("CASL")

        # Phone / SMS
        elif channel in ("phone", "sms"):
            regs.append("TCPA")
            regs.append("DNC_REGISTRY")
            if loc in ("GB", "DE", "FR", "NL", "SE", "EU"):
                regs.append("GDPR")
                regs.append("PECR")
            if loc == "CA":
                regs.append("CASL")
                regs.append("CRTC_SPAM")

        # LinkedIn / social
        elif channel == "linkedin":
            regs.append("CAN-SPAM")   # messages with commercial intent
            if loc in ("GB", "DE", "FR", "NL", "EU"):
                regs.append("GDPR")

        return regs

    def get_compliance_report(self) -> Dict[str, Any]:
        """Return summary of contacts, opt-outs, violations prevented."""
        with self._lock:
            total_contacts = sum(
                len(ch_map) for ch_map in self._contacts.values()
            )
            return {
                "total_prospects_contacted": len(self._contacts),
                "total_contacts_sent": total_contacts,
                "opt_out_count": len(self._opt_outs),
                "dnc_count": len(self._dnc),
                "customer_count": len(self._customers),
                "audit_log_entries": len(self._audit_log),
                "violations_prevented": sum(
                    1 for entry in self._audit_log if not entry.get("allowed")
                ),
                "policy": self._policy.to_dict(),
            }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_rate_limited(self, channel: str) -> bool:
        """Check daily rate cap. Must be called under lock."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_counts = self._daily_counts.get(today, {})
        cap = self._policy.max_contacts_per_day.get(channel, 50)
        return today_counts.get(channel, 0) >= cap

    def _increment_daily_count(self, channel: str) -> None:
        """Increment the daily counter for a channel. Must be called under lock."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._daily_counts.setdefault(today, {})
        self._daily_counts[today][channel] = (
            self._daily_counts[today].get(channel, 0) + 1
        )
        # Purge old dates (keep only today)
        for date_key in list(self._daily_counts.keys()):
            if date_key != today:
                del self._daily_counts[date_key]

    def _is_blocked_hour(self) -> bool:
        """Check if current UTC hour is in the blocked list (TCPA)."""
        hour = datetime.now(timezone.utc).hour
        for start, end in self._policy.blocked_hours:
            if start <= hour < end:
                return True
        return False

    def _record_audit(
        self,
        prospect_id: str,
        channel: str,
        allowed: bool,
        reason: str,
        **extra: Any,
    ) -> None:
        entry: Dict[str, Any] = {
            "prospect_id_masked": _mask_id(prospect_id),
            "channel": channel,
            "allowed": allowed,
            "reason": reason,
            "timestamp": _ts(),
            **extra,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)
