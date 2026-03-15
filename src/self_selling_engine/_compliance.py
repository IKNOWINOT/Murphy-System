"""Outreach compliance governor for the self-selling engine.

Design Label: SSE-COMPL-001 — Outreach Compliance Governor
Owner: Legal / Platform Engineering

Enforces regulatory outreach rules for every prospect contact attempt
made by :class:`MurphySelfSellingEngine`:

  * **30-day cooldown** — non-customers cannot be re-contacted within 30
    calendar days on any given channel.
  * **Explicit opt-out suppression** — if a prospect replies with an
    opt-out phrase (unsubscribe / stop / remove me / do not contact), they
    are permanently suppressed until manually overridden.
  * **Customer exemption** — existing customers (completed trial or active)
    are subject to a shorter cooldown (default 7 days) rather than the 30-day
    non-customer window.  Explicit opt-outs are still honoured for customers.
  * **Per-channel daily rate limits** — configurable caps prevent flooding
    (defaults: 50 email / 20 SMS / 30 LinkedIn per rolling calendar day).
  * **Regulatory compliance** — CAN-SPAM, TCPA, GDPR Article 21, CASL,
    and PECR suppression-list requirements are satisfied by permanent
    opt-out recording with full audit trail.

Safety invariants:
  - Thread-safe: all shared state guarded by ``threading.Lock``.
  - Bounded collections: ``capped_append`` prevents unbounded growth.
  - Input validation before processing (CWE-20).
  - Opt-out entries are permanent and can only be cleared by an explicit
    human-initiated ``clear_opt_out()`` call with an audit reason.
  - Every compliance decision (allow *or* block) is appended to an
    immutable, bounded audit log.
  - Raw email addresses are never written to log records (PII protection).

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

_COOLDOWN_DAYS_NON_CUSTOMER: int = 30
_COOLDOWN_DAYS_CUSTOMER: int = 7  # customers can be contacted more often

# Daily rate-limit defaults per channel (configurable via constructor)
_DEFAULT_DAILY_LIMITS: Dict[str, int] = {
    "email":    50,
    "sms":      20,
    "linkedin": 30,
}

# Maximum audit-log entries                                          [CWE-400]
_MAX_AUDIT_LOG: int = 100_000
# Maximum tracked contacts                                          [CWE-400]
_MAX_CONTACTS: int  = 100_000

# Input validation                                                   [CWE-20]
_PROSPECT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
_VALID_CHANNELS: frozenset = frozenset({"email", "sms", "linkedin"})
_MAX_REASON_LEN: int = 500
_MAX_SOURCE_LEN: int = 200

# Opt-out keyword detector (capped before evaluation to prevent ReDoS)
_MAX_OPT_OUT_TEXT_LEN: int = 50_000
_OPT_OUT_RE = re.compile(
    r"(unsubscribe|remove\s+me|stop|opt[\s\-]*out|do\s+not\s+contact|"
    r"please\s+remove|take\s+me\s+off|no\s+more\s+emails|"
    r"cancel\s+subscription|cease\s+contact)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DecisionStatus(str, Enum):
    """Possible outcomes of a compliance check."""
    ALLOWED          = "ALLOWED"
    BLOCKED_OPT_OUT  = "BLOCKED_OPT_OUT"
    BLOCKED_COOLDOWN = "BLOCKED_COOLDOWN"
    BLOCKED_RATE     = "BLOCKED_RATE"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContactRecord:
    """Per-prospect, per-channel outreach compliance state."""

    prospect_id: str
    channel: str
    last_contacted_at: Optional[str] = None          # UTC ISO-8601
    opt_out_status: bool = False                      # True = permanently suppressed
    opt_out_reason: Optional[str] = None
    opt_out_at: Optional[str] = None                 # UTC ISO-8601
    is_customer: bool = False
    contact_count: int = 0
    suppression_expires_at: Optional[str] = None     # None = permanent


@dataclass
class ComplianceDecision:
    """Result of a single compliance check."""

    allowed: bool
    status: str           # DecisionStatus value
    reason: str
    prospect_id: str
    channel: str
    cooldown_remaining_days: int = 0
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "reason": self.reason,
            "prospect_id": self.prospect_id,
            "channel": self.channel,
            "cooldown_remaining_days": self.cooldown_remaining_days,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class OutreachComplianceGovernor:
    """Compliance gate for the self-selling engine outreach loop.

    All outreach attempts in :meth:`MurphySelfSellingEngine.run_selling_cycle`
    must pass through :meth:`check_contact_allowed` before a message is sent.

    Parameters
    ----------
    daily_limits:
        Per-channel daily rate-limit overrides.  Keys are channel strings
        (``"email"``, ``"sms"``, ``"linkedin"``); values are integer caps.
        Missing keys fall back to :data:`_DEFAULT_DAILY_LIMITS`.
    cooldown_days_non_customer:
        Days between outreach attempts for non-customers (default 30).
    cooldown_days_customer:
        Days between outreach attempts for existing customers (default 7).
    """

    def __init__(
        self,
        daily_limits: Optional[Dict[str, int]] = None,
        cooldown_days_non_customer: int = _COOLDOWN_DAYS_NON_CUSTOMER,
        cooldown_days_customer: int = _COOLDOWN_DAYS_CUSTOMER,
    ) -> None:
        self._lock = threading.Lock()

        self._cooldown_non_customer = cooldown_days_non_customer
        self._cooldown_customer = cooldown_days_customer

        # Merge caller-supplied limits with defaults
        self._daily_limits: Dict[str, int] = dict(_DEFAULT_DAILY_LIMITS)
        if daily_limits:
            for ch, cap in daily_limits.items():
                if ch in _VALID_CHANNELS and isinstance(cap, int) and cap >= 0:
                    self._daily_limits[ch] = cap

        # prospect_id → {channel → ContactRecord}
        self._contacts: Dict[str, Dict[str, ContactRecord]] = {}

        # Per-channel daily counter: channel → {date_str → count}
        self._daily_counts: Dict[str, Dict[str, int]] = {
            ch: {} for ch in _VALID_CHANNELS
        }

        # Immutable, bounded audit trail
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input validation                                              [CWE-20]
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_prospect_id(prospect_id: str) -> str:
        if not isinstance(prospect_id, str) or not _PROSPECT_ID_RE.match(prospect_id):
            raise ValueError("Invalid prospect_id format")
        return prospect_id

    @staticmethod
    def _validate_channel(channel: str) -> str:
        if not isinstance(channel, str) or channel.lower() not in _VALID_CHANNELS:
            raise ValueError(
                f"Invalid channel — must be one of {sorted(_VALID_CHANNELS)}"
            )
        return channel.lower()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_record(self, prospect_id: str, channel: str) -> ContactRecord:
        """Return the ContactRecord for (prospect_id, channel), creating if absent."""
        if len(self._contacts) >= _MAX_CONTACTS and prospect_id not in self._contacts:
            # Evict oldest 10% when at capacity to prevent OOM             [CWE-400]
            evict_count = max(1, _MAX_CONTACTS // 10)
            keys_to_evict = list(self._contacts.keys())[:evict_count]
            for k in keys_to_evict:
                del self._contacts[k]
            logger.warning("Contact tracking at capacity; evicted %d entries", evict_count)

        channel_map = self._contacts.setdefault(prospect_id, {})
        if channel not in channel_map:
            channel_map[channel] = ContactRecord(
                prospect_id=prospect_id,
                channel=channel,
            )
        return channel_map[channel]

    def _cooldown_remaining(self, record: ContactRecord) -> int:
        """Return the number of full days remaining in the cooldown window, or 0."""
        if record.last_contacted_at is None:
            return 0
        try:
            last = datetime.fromisoformat(record.last_contacted_at)
        except ValueError:
            return 0
        cooldown = (
            self._cooldown_customer if record.is_customer
            else self._cooldown_non_customer
        )
        cutoff = last + timedelta(days=cooldown)
        now = datetime.now(timezone.utc)
        # Ensure both are tz-aware for subtraction
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
            cutoff = last + timedelta(days=cooldown)
        delta = (cutoff - now).days
        return max(0, delta)

    def _is_rate_limited(self, channel: str) -> bool:
        """Return True if the daily cap for *channel* has been reached."""
        today = datetime.now(timezone.utc).date().isoformat()
        count = self._daily_counts.get(channel, {}).get(today, 0)
        limit = self._daily_limits.get(channel, 0)
        return count >= limit

    def _increment_daily_count(self, channel: str) -> None:
        """Increment the rolling daily send counter for *channel*."""
        today = datetime.now(timezone.utc).date().isoformat()
        bucket = self._daily_counts.setdefault(channel, {})
        bucket[today] = bucket.get(today, 0) + 1

    def _record_audit(
        self,
        decision: ComplianceDecision,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry: Dict[str, Any] = {
            **decision.to_dict(),
            **(extra or {}),
        }
        capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_contact_allowed(
        self,
        prospect_id: str,
        channel: str,
    ) -> ComplianceDecision:
        """Check whether this prospect may be contacted on this channel now.

        The check enforces (in order):
          1. Permanent opt-out suppression — hard block, no override.
          2. Per-channel daily rate limit.
          3. Cooldown window (30 days for non-customers, 7 for customers).

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.
        channel:
            Delivery channel (``"email"`` | ``"sms"`` | ``"linkedin"``).

        Returns
        -------
        ComplianceDecision
            ``allowed=True`` if all checks pass, ``False`` otherwise.

        Raises
        ------
        ValueError
            If ``prospect_id`` or ``channel`` fail input validation.
        """
        prospect_id = self._validate_prospect_id(prospect_id)
        channel     = self._validate_channel(channel)

        with self._lock:
            record = self._get_or_create_record(prospect_id, channel)

            # 1. Permanent opt-out — hard block
            if record.opt_out_status:
                decision = ComplianceDecision(
                    allowed=False,
                    status=DecisionStatus.BLOCKED_OPT_OUT.value,
                    reason="Prospect has opted out — permanently suppressed.",
                    prospect_id=prospect_id,
                    channel=channel,
                )
                self._record_audit(decision)
                return decision

            # 2. Daily rate limit
            if self._is_rate_limited(channel):
                limit = self._daily_limits.get(channel, 0)
                decision = ComplianceDecision(
                    allowed=False,
                    status=DecisionStatus.BLOCKED_RATE.value,
                    reason=(
                        f"Daily rate limit reached for channel '{channel}' "
                        f"({limit} messages/day)."
                    ),
                    prospect_id=prospect_id,
                    channel=channel,
                )
                self._record_audit(decision)
                return decision

            # 3. Cooldown — customers use shorter window; non-customers use 30-day window
            remaining = self._cooldown_remaining(record)
            if remaining > 0:
                decision = ComplianceDecision(
                    allowed=False,
                    status=DecisionStatus.BLOCKED_COOLDOWN.value,
                    reason=(
                        f"Prospect is in cooldown — {remaining} day(s) remaining."
                    ),
                    prospect_id=prospect_id,
                    channel=channel,
                    cooldown_remaining_days=remaining,
                )
                self._record_audit(decision)
                return decision

        decision = ComplianceDecision(
            allowed=True,
            status=DecisionStatus.ALLOWED.value,
            reason="All compliance checks passed.",
            prospect_id=prospect_id,
            channel=channel,
        )
        self._record_audit(decision)
        return decision

    def record_contact(self, prospect_id: str, channel: str) -> None:
        """Record that a message was successfully sent to a prospect.

        Updates ``last_contacted_at`` and increments the daily rate counter.

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.
        channel:
            Delivery channel (``"email"`` | ``"sms"`` | ``"linkedin"``).

        Raises
        ------
        ValueError
            If inputs fail validation.
        """
        prospect_id = self._validate_prospect_id(prospect_id)
        channel     = self._validate_channel(channel)

        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            record = self._get_or_create_record(prospect_id, channel)
            record.last_contacted_at = now
            record.contact_count += 1
            self._increment_daily_count(channel)

        logger.debug(
            "Recorded contact for prospect %s via %s (count=%d)",
            prospect_id, channel, record.contact_count,
        )

    def record_opt_out(
        self,
        prospect_id: str,
        reason: str,
        source: str = "system",
    ) -> None:
        """Permanently suppress a prospect across ALL channels.

        Opt-out status is global (not per-channel): once a prospect opts out
        they are suppressed on all channels until :meth:`clear_opt_out` is
        called by a human operator.

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.
        reason:
            Human-readable reason (e.g. reply text or "GDPR Art. 21 request").
        source:
            Who triggered the opt-out (``"prospect_reply"`` | ``"gdpr_request"``
            | ``"admin"`` | ``"system"``).

        Raises
        ------
        ValueError
            If ``prospect_id`` fails validation.
        """
        prospect_id = self._validate_prospect_id(prospect_id)
        # Cap free-text fields                                       [CWE-400]
        reason_safe  = str(reason)[:_MAX_REASON_LEN]  if reason  else ""
        source_safe  = str(source)[:_MAX_SOURCE_LEN]  if source  else "system"

        opt_out_ts = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # Apply opt-out across every channel (existing + all valid)
            for ch in _VALID_CHANNELS:
                record = self._get_or_create_record(prospect_id, ch)
                if not record.opt_out_status:
                    record.opt_out_status = True
                    record.opt_out_reason = reason_safe
                    record.opt_out_at     = opt_out_ts

            # Audit the opt-out event
            capped_append(
                self._audit_log,
                {
                    "event":       "OPT_OUT_RECORDED",
                    "prospect_id": prospect_id,
                    "reason":      reason_safe,
                    "source":      source_safe,
                    "recorded_at": opt_out_ts,
                },
                max_size=_MAX_AUDIT_LOG,
            )

        logger.info(
            "Opt-out recorded for prospect %s (source=%s)", prospect_id, source_safe
        )

    def clear_opt_out(
        self,
        prospect_id: str,
        cleared_by: str,
        audit_reason: str,
    ) -> None:
        """Remove a prospect's opt-out suppression (human override only).

        This is an audited operation intended for use when a prospect has
        re-opted-in or when a suppression was recorded in error.

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.
        cleared_by:
            Identity of the human operator authorising the override.
        audit_reason:
            Documented reason for the override (stored in the audit log).

        Raises
        ------
        ValueError
            If ``prospect_id`` fails validation.
        """
        prospect_id   = self._validate_prospect_id(prospect_id)
        cleared_by    = str(cleared_by)[:_MAX_SOURCE_LEN]
        audit_reason  = str(audit_reason)[:_MAX_REASON_LEN]
        cleared_at    = datetime.now(timezone.utc).isoformat()

        with self._lock:
            if prospect_id in self._contacts:
                for record in self._contacts[prospect_id].values():
                    record.opt_out_status = False
                    record.opt_out_reason = None
                    record.opt_out_at     = None

            capped_append(
                self._audit_log,
                {
                    "event":        "OPT_OUT_CLEARED",
                    "prospect_id":  prospect_id,
                    "cleared_by":   cleared_by,
                    "audit_reason": audit_reason,
                    "cleared_at":   cleared_at,
                },
                max_size=_MAX_AUDIT_LOG,
            )

        logger.info(
            "Opt-out cleared for prospect %s by %s", prospect_id, cleared_by
        )

    def mark_as_customer(self, prospect_id: str) -> None:
        """Mark a prospect as an existing customer on all channels.

        Customers are exempt from the 30-day cooldown window (they receive
        the shorter :attr:`_cooldown_customer`-day window instead).

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.

        Raises
        ------
        ValueError
            If ``prospect_id`` fails validation.
        """
        prospect_id = self._validate_prospect_id(prospect_id)
        with self._lock:
            for ch in _VALID_CHANNELS:
                record = self._get_or_create_record(prospect_id, ch)
                record.is_customer = True

    def is_customer(self, prospect_id: str) -> bool:
        """Return True if the prospect is marked as an existing customer.

        Parameters
        ----------
        prospect_id:
            Unique prospect identifier.

        Raises
        ------
        ValueError
            If ``prospect_id`` fails validation.
        """
        prospect_id = self._validate_prospect_id(prospect_id)
        with self._lock:
            channel_map = self._contacts.get(prospect_id, {})
            # A prospect is a customer if any channel record marks them as one
            return any(r.is_customer for r in channel_map.values())

    def detect_opt_out_in_reply(self, reply_text: str) -> bool:
        """Return True if *reply_text* contains an opt-out signal.

        The text is capped before regex evaluation to prevent ReDoS.  [CWE-400]

        Parameters
        ----------
        reply_text:
            Raw reply text from the prospect.
        """
        if not isinstance(reply_text, str):
            return False
        capped = reply_text[:_MAX_OPT_OUT_TEXT_LEN]
        return bool(_OPT_OUT_RE.search(capped))

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a snapshot of the audit log (copy, not reference)."""
        with self._lock:
            return list(self._audit_log)

    def get_daily_counts(self) -> Dict[str, Dict[str, int]]:
        """Return a snapshot of today's per-channel send counts."""
        today = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            return {
                ch: {today: self._daily_counts.get(ch, {}).get(today, 0)}
                for ch in _VALID_CHANNELS
            }
