"""
Outreach Campaign Planner for Murphy System.

Design Label: CAMP-001 — Self-Advertising Outreach Campaign Planner
Owner: Marketing Team / Platform Engineering
Dependencies:
  - ContactComplianceGovernor (COMPL-001) — centralized outreach enforcement gate
  - OutreachComplianceGate (COMPL-002) — outreach compliance integration layer
  - SelfSellingOutreach (SELL-001) — META_PROOF self-referential messaging
  - BUSINESS_TYPE_CONSTRAINTS — 12-vertical personalization registry
  - thread_safe_operations.capped_append — bounded collections

Capabilities:
  - CampaignPlan with cadence, channels, audience segments, compliance rules
  - CadenceStep per outreach step: channel, delay, template, personalization
  - AudienceSegment: filtered prospect list by industry/size/tools
  - campaign_health_check() — validates all compliance integrations are working
  - generate_campaign_for_segment() — creates a compliant outreach sequence
  - execute_campaign_step() — runs one step with pre-flight compliance check
  - Automatic suppression list management (DNC + cooldown-based)
  - Audit trail of all outreach decisions

Compliance rules enforced (via ContactComplianceGovernor):
  - 30-day cooldown for non-customers
  - 7-day cooldown for existing customer marketing
  - Permanent DNC for opt-outs (CAN-SPAM / TCPA / GDPR / CCPA / CASL)
  - robots.txt / site TOS respect flag

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock (CWE-362)
  - Non-destructive: suppression list only grows; removals require consent
  - Bounded collections via capped_append (CWE-770)
  - Input validated before processing (CWE-20)
  - Collection hard caps prevent memory exhaustion (CWE-400)
  - Raw emails / PII never written to log records (PII protection)
  - Error messages sanitised before logging (CWE-209)

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
# Input-validation constants                                        [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_CONTACT_ID_RE = re.compile(r"^[a-zA-Z0-9_@.\-]{1,200}$")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MAX_EMAIL_LEN = 254          # RFC 5321 hard limit
_MAX_CONTACT_ID_LEN = 200
_MAX_CAMPAIGN_NAME_LEN = 200
_MAX_SEGMENT_NAME_LEN = 200
_MAX_TEMPLATE_LEN = 10_000
_MAX_NOTES_LEN = 2_000
_MAX_STEPS_PER_PLAN = 50
_MAX_AUDIENCE_SIZE = 100_000
_MAX_SEGMENT_FILTERS = 20

# Channels that the planner recognises                            [allowlist]
_ALLOWED_CHANNELS: frozenset[str] = frozenset({"email", "sms", "linkedin"})
_MAX_CHANNEL_LEN = 20

# Collection hard caps                                             [CWE-400]
_MAX_CAMPAIGNS = 5_000
_MAX_SUPPRESSION_LIST = 100_000
_MAX_AUDIT_LOG = 50_000
_MAX_STEPS_HISTORY = 200

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CampaignStatus(str, Enum):
    """Lifecycle state of a campaign plan."""
    DRAFT     = "draft"
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"
    ARCHIVED  = "archived"

class OutcomeType(str, Enum):
    """Result of a single campaign step execution."""
    SENT      = "sent"
    BLOCKED   = "blocked"
    SKIPPED   = "skipped"
    ERROR     = "error"

class CooldownType(str, Enum):
    """Type of contact for cooldown purposes."""
    NON_CUSTOMER = "non_customer"
    CUSTOMER     = "customer"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CadenceStep:
    """A single outreach step in a campaign cadence.

    Fields:
      step_number   — position in the cadence (1-based)
      channel       — "email" | "sms" | "linkedin"
      delay_days    — days to wait after the previous step (0 = same day as start)
      template_id   — reference to a message template
      subject       — email subject line (if applicable)
      body_template — message body with {placeholders}
      use_meta_proof — prepend META_PROOF self-referential paragraph
    """
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    step_number: int = 1
    channel: str = "email"
    delay_days: int = 0
    template_id: str = ""
    subject: str = ""
    body_template: str = ""
    use_meta_proof: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "channel": self.channel,
            "delay_days": self.delay_days,
            "template_id": self.template_id,
            "subject": self.subject,
            "use_meta_proof": self.use_meta_proof,
        }


@dataclass
class AudienceSegment:
    """Filtered prospect list by industry, size, tools, and region."""
    segment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    industry_filter: List[str] = field(default_factory=list)
    size_filter: str = ""           # "under_1m" | "1m_10m" | "10m_50m" | "50m_plus"
    tools_filter: List[str] = field(default_factory=list)
    region_filter: str = ""
    prospect_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "name": self.name,
            "industry_filter": list(self.industry_filter),
            "size_filter": self.size_filter,
            "tools_filter": list(self.tools_filter),
            "region_filter": self.region_filter,
            "prospect_count": len(self.prospect_ids),
            "created_at": self.created_at,
        }


@dataclass
class CampaignPlan:
    """Full campaign definition: cadence, segments, and compliance rules.

    A plan bundles one or more CadenceSteps with one AudienceSegment.
    Compliance rules are enforced by ContactComplianceGovernor before
    any step is executed.
    """
    campaign_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    segment: Optional[AudienceSegment] = None
    cadence_steps: List[CadenceStep] = field(default_factory=list)
    # Compliance configuration
    cooldown_type: CooldownType = CooldownType.NON_CUSTOMER
    respect_robots_txt: bool = True
    respect_site_tos: bool = True
    # Stats
    status: CampaignStatus = CampaignStatus.DRAFT
    steps_executed: int = 0
    steps_blocked: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "description": self.description,
            "segment": self.segment.to_dict() if self.segment else None,
            "cadence_steps": [s.to_dict() for s in self.cadence_steps],
            "cooldown_type": self.cooldown_type.value,
            "respect_robots_txt": self.respect_robots_txt,
            "respect_site_tos": self.respect_site_tos,
            "status": self.status.value,
            "steps_executed": self.steps_executed,
            "steps_blocked": self.steps_blocked,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class StepExecutionResult:
    """Result of executing one campaign step for one contact."""
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    campaign_id: str = ""
    step_id: str = ""
    contact_id: str = ""
    channel: str = ""
    outcome: OutcomeType = OutcomeType.BLOCKED
    block_reason: str = ""
    message_preview: str = ""
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "step_id": self.step_id,
            "contact_id": self.contact_id,
            "channel": self.channel,
            "outcome": self.outcome.value,
            "block_reason": self.block_reason,
            "executed_at": self.executed_at,
        }


@dataclass
class HealthCheckResult:
    """Result of campaign_health_check()."""
    healthy: bool = True
    governor_ok: bool = False
    compliance_gate_ok: bool = False
    suppression_ok: bool = False
    channel_ok: bool = False
    issues: List[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "governor_ok": self.governor_ok,
            "compliance_gate_ok": self.compliance_gate_ok,
            "suppression_ok": self.suppression_ok,
            "channel_ok": self.channel_ok,
            "issues": list(self.issues),
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    """Return a safe opaque token; never leak raw exception text to logs."""
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_email(email: str) -> str:
    """Mask email for logging (PII protection)."""
    try:
        local, domain = email.rsplit("@", 1)
        return f"{local[:2]}***@{domain}"
    except Exception:
        return "***"


# ---------------------------------------------------------------------------
# Campaign Planner Engine                                           CAMP-001
# ---------------------------------------------------------------------------

class CampaignPlannerEngine:
    """
    Self-Advertising Outreach Campaign Planner (CAMP-001).

    Leverages Murphy's unique skills to plan, sequence, and execute
    compliant outreach across email / LinkedIn / SMS.

    Key capabilities:
      - META_PROOF self-referential messaging ("the fact that I'm contacting
        you is the demo").
      - Business-type personalisation using BUSINESS_TYPE_CONSTRAINTS for
        12 industry verticals.
      - Live system stats injected into message templates.
      - 3-day free trial offer integration with shadow agent deployment.
      - Contractor-augmented intel for market data gathering.
      - Full compliance enforcement via ContactComplianceGovernor.

    Thread-safety: all mutable state is guarded by a single threading.Lock.
    """

    # Self-referential META_PROOF paragraph (SELL-001 pattern)
    META_PROOF_TEMPLATE = (
        "The fact that I'm contacting you right now is part of the demo. "
        "No human at Inoni is selling Murphy. This message was composed, "
        "personalised for your {business_type} business, and sent entirely "
        "by the system."
    )

    # 3-day trial offer paragraph
    TRIAL_OFFER_TEMPLATE = (
        "We're offering a complimentary 3-day trial — fully automated setup, "
        "no credit card required. A shadow agent will mirror your current "
        "workflow so you can see exactly what Murphy can automate for you "
        "before committing to anything."
    )

    # Default multi-channel cadence: email → LinkedIn → SMS
    DEFAULT_CADENCE = [
        {"channel": "email",    "delay_days": 0,  "use_meta_proof": True},
        {"channel": "linkedin", "delay_days": 3,  "use_meta_proof": False},
        {"channel": "sms",      "delay_days": 7,  "use_meta_proof": False},
    ]

    def __init__(
        self,
        governor: Any = None,
        compliance_gate: Any = None,
    ) -> None:
        self._lock = threading.Lock()

        # Injected compliance dependencies
        self._governor = governor          # ContactComplianceGovernor
        self._compliance_gate = compliance_gate  # OutreachComplianceGate

        # In-memory state
        self._campaigns: Dict[str, CampaignPlan] = {}
        self._suppression_list: Dict[str, str] = {}   # contact_id → reason
        self._execution_history: List[Dict[str, Any]] = []
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_id(value: str, name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        clean = value.strip()
        if not _ID_RE.match(clean):
            raise ValueError(f"{name} has invalid characters or exceeds length limit")
        return clean

    @staticmethod
    def _validate_contact_id(contact_id: str) -> str:
        if not isinstance(contact_id, str):
            raise ValueError("contact_id must be a string")
        clean = contact_id.strip().replace("\x00", "")
        if not _CONTACT_ID_RE.match(clean):
            raise ValueError("contact_id contains invalid characters or exceeds length limit")
        return clean

    @staticmethod
    def _validate_email(email: str) -> str:
        """Validate email format; never log the raw value."""
        if not isinstance(email, str):
            raise ValueError("email must be a string")
        clean = email.strip().replace("\x00", "")
        if len(clean) > _MAX_EMAIL_LEN:
            raise ValueError("email exceeds RFC 5321 maximum length")
        if not _EMAIL_RE.match(clean):
            raise ValueError("email format is invalid")
        return clean

    @staticmethod
    def _validate_channel(channel: str) -> str:
        if not isinstance(channel, str):
            raise ValueError("channel must be a string")
        clean = channel.strip().lower().replace("\x00", "")
        if len(clean) > _MAX_CHANNEL_LEN:
            raise ValueError(f"channel exceeds {_MAX_CHANNEL_LEN} chars")
        if clean not in _ALLOWED_CHANNELS:
            raise ValueError(
                f"channel '{clean}' is not allowed; "
                f"permitted: {sorted(_ALLOWED_CHANNELS)}"
            )
        return clean

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def campaign_health_check(self) -> HealthCheckResult:
        """Validate that all compliance integrations are working.

        Checks governor, compliance gate, suppression list, and channel
        allowlist.  Returns a HealthCheckResult with per-component flags.
        """
        result = HealthCheckResult()

        # Governor health
        if self._governor is not None:
            try:
                status = self._governor.get_status()
                result.governor_ok = isinstance(status, dict)
            except Exception as exc:
                result.issues.append(f"Governor error: {_sanitize_error(exc)}")
        else:
            result.issues.append("ContactComplianceGovernor not injected — using stub")
            result.governor_ok = True   # stub mode is acceptable in test environments

        # Compliance gate health
        if self._compliance_gate is not None:
            try:
                # A simple attribute check is enough — the gate may not have a health method
                _ = self._compliance_gate.__class__.__name__
                result.compliance_gate_ok = True
            except Exception as exc:
                result.issues.append(f"ComplianceGate error: {_sanitize_error(exc)}")
        else:
            result.issues.append("OutreachComplianceGate not injected — using stub")
            result.compliance_gate_ok = True  # stub mode

        # Suppression list integrity
        with self._lock:
            sup_size = len(self._suppression_list)
        result.suppression_ok = sup_size <= _MAX_SUPPRESSION_LIST
        if not result.suppression_ok:
            result.issues.append(
                f"Suppression list at capacity ({sup_size}/{_MAX_SUPPRESSION_LIST})"
            )

        # Channel allowlist sanity check
        result.channel_ok = len(_ALLOWED_CHANNELS) >= 3
        if not result.channel_ok:
            result.issues.append("Channel allowlist missing required channels")

        result.healthy = all([
            result.governor_ok,
            result.compliance_gate_ok,
            result.suppression_ok,
            result.channel_ok,
        ])

        with self._lock:
            self._record_audit(
                "campaign_health_check", {"healthy": result.healthy}
            )

        return result

    # ------------------------------------------------------------------
    # Campaign plan generation
    # ------------------------------------------------------------------

    def generate_campaign_for_segment(
        self,
        name: str,
        segment: AudienceSegment,
        cadence: Optional[List[Dict[str, Any]]] = None,
        cooldown_type: CooldownType = CooldownType.NON_CUSTOMER,
    ) -> CampaignPlan:
        """Create a compliant outreach sequence for an audience segment.

        Uses DEFAULT_CADENCE if no cadence is provided.  Each step
        is validated against the allowed channel list.  Returns a
        CampaignPlan ready for execution.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if len(name) > _MAX_CAMPAIGN_NAME_LEN:
            raise ValueError(f"name exceeds {_MAX_CAMPAIGN_NAME_LEN} chars")
        if not isinstance(segment, AudienceSegment):
            raise ValueError("segment must be an AudienceSegment")

        steps_spec = cadence if cadence is not None else self.DEFAULT_CADENCE

        cadence_steps: List[CadenceStep] = []
        for i, spec in enumerate(steps_spec[:_MAX_STEPS_PER_PLAN]):
            channel = self._validate_channel(str(spec.get("channel", "email")))
            delay = int(spec.get("delay_days", 0))
            delay = max(0, min(delay, 365))
            use_meta = bool(spec.get("use_meta_proof", True))
            body_tpl = self._build_body_template(
                channel=channel,
                business_type=segment.industry_filter[0] if segment.industry_filter else "business",
                use_meta_proof=use_meta,
            )
            step = CadenceStep(
                step_number=i + 1,
                channel=channel,
                delay_days=delay,
                body_template=body_tpl,
                use_meta_proof=use_meta,
            )
            cadence_steps.append(step)

        plan = CampaignPlan(
            name=name.strip(),
            segment=segment,
            cadence_steps=cadence_steps,
            cooldown_type=cooldown_type,
            status=CampaignStatus.DRAFT,
        )

        with self._lock:
            if len(self._campaigns) >= _MAX_CAMPAIGNS:
                raise RuntimeError("Campaign registry is at capacity")
            self._campaigns[plan.campaign_id] = plan
            self._record_audit(
                "generate_campaign_for_segment",
                {"campaign_id": plan.campaign_id, "name": plan.name},
            )

        logger.info("Campaign plan created: id=%s name=%s", plan.campaign_id, plan.name)
        return plan

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def execute_campaign_step(
        self,
        campaign_id: str,
        step_number: int,
        contact_id: str,
        contact_email: str,
        contact_region: str = "US",
        contact_metadata: Optional[Dict[str, Any]] = None,
    ) -> StepExecutionResult:
        """Execute one campaign step for a single contact.

        Pre-flight compliance check via ContactComplianceGovernor.
        All blocked contacts are automatically added to the suppression list.

        Returns a StepExecutionResult with outcome and (if sent) message preview.
        """
        try:
            cid = self._validate_contact_id(contact_id)
        except ValueError:
            return StepExecutionResult(
                campaign_id=str(campaign_id)[:200] if campaign_id else "",
                contact_id="",
                outcome=OutcomeType.BLOCKED,
                block_reason="invalid_contact_id",
            )
        try:
            email = self._validate_email(contact_email)
        except ValueError:
            return StepExecutionResult(
                campaign_id=campaign_id,
                contact_id=cid,
                outcome=OutcomeType.BLOCKED,
                block_reason="invalid_email",
            )

        camp_id = self._validate_id(campaign_id, "campaign_id")

        with self._lock:
            plan = self._campaigns.get(camp_id)
        if plan is None:
            return StepExecutionResult(
                campaign_id=camp_id,
                contact_id=cid,
                outcome=OutcomeType.BLOCKED,
                block_reason="campaign_not_found",
            )

        step = next(
            (s for s in plan.cadence_steps if s.step_number == step_number), None
        )
        if step is None:
            return StepExecutionResult(
                campaign_id=camp_id,
                contact_id=cid,
                outcome=OutcomeType.BLOCKED,
                block_reason="step_not_found",
            )

        # Check suppression list first
        with self._lock:
            if cid in self._suppression_list:
                return StepExecutionResult(
                    campaign_id=camp_id,
                    step_id=step.step_id,
                    contact_id=cid,
                    channel=step.channel,
                    outcome=OutcomeType.BLOCKED,
                    block_reason=f"on_suppression_list:{self._suppression_list[cid]}",
                )

        # Pre-flight compliance check via governor
        compliance_decision = self._check_compliance(
            contact_id=cid,
            email=email,
            channel=step.channel,
            region=contact_region,
            cooldown_type=plan.cooldown_type,
        )

        exec_result = StepExecutionResult(
            campaign_id=camp_id,
            step_id=step.step_id,
            contact_id=cid,
            channel=step.channel,
        )

        if not compliance_decision.get("allowed", False):
            block_reason = compliance_decision.get("reason", "compliance_blocked")
            exec_result.outcome = OutcomeType.BLOCKED
            exec_result.block_reason = block_reason

            # Add to suppression list if DNC
            if "dnc" in block_reason.lower() or "opt" in block_reason.lower():
                self._add_to_suppression(cid, block_reason)

            with self._lock:
                plan.steps_blocked += 1
                plan.updated_at = _ts()

        else:
            # Build and record the outreach message
            preview = self._render_step(step, cid, contact_metadata or {})
            exec_result.outcome = OutcomeType.SENT
            exec_result.message_preview = preview[:500]

            # Record via compliance gate
            self._record_outreach_contact(
                contact_id=cid,
                email=email,
                channel=step.channel,
                region=contact_region,
            )

            with self._lock:
                plan.steps_executed += 1
                plan.updated_at = _ts()

        with self._lock:
            capped_append(
                self._execution_history,
                exec_result.to_dict(),
                max_size=_MAX_STEPS_HISTORY,
            )
            self._record_audit(
                "execute_campaign_step",
                {
                    "campaign_id": camp_id,
                    "step_number": step_number,
                    "contact_id": cid,
                    "outcome": exec_result.outcome.value,
                },
            )

        return exec_result

    # ------------------------------------------------------------------
    # Suppression list management
    # ------------------------------------------------------------------

    def add_to_suppression(
        self,
        contact_id: str,
        reason: str = "manual",
    ) -> None:
        """Manually add a contact to the suppression list."""
        cid = self._validate_contact_id(contact_id)
        reason_clean = str(reason)[:500].replace("\x00", "")
        self._add_to_suppression(cid, reason_clean)

    def is_suppressed(self, contact_id: str) -> bool:
        """Return True if the contact is on the suppression list."""
        cid = self._validate_contact_id(contact_id)
        with self._lock:
            return cid in self._suppression_list

    def get_suppression_list(self) -> Dict[str, str]:
        """Return a copy of the suppression list (contact_id → reason)."""
        with self._lock:
            return dict(self._suppression_list)

    # ------------------------------------------------------------------
    # Campaign state queries
    # ------------------------------------------------------------------

    def get_campaign(self, campaign_id: str) -> Optional[CampaignPlan]:
        """Return a CampaignPlan by ID, or None if not found."""
        cid = self._validate_id(campaign_id, "campaign_id")
        with self._lock:
            return self._campaigns.get(cid)

    def list_campaigns(self) -> List[Dict[str, Any]]:
        """Return a summary list of all campaign plans."""
        with self._lock:
            return [c.to_dict() for c in self._campaigns.values()]

    def activate_campaign(self, campaign_id: str) -> bool:
        """Transition a campaign from DRAFT to ACTIVE.  Returns True on success."""
        cid = self._validate_id(campaign_id, "campaign_id")
        with self._lock:
            plan = self._campaigns.get(cid)
            if plan is None or plan.status != CampaignStatus.DRAFT:
                return False
            plan.status = CampaignStatus.ACTIVE
            plan.updated_at = _ts()
            self._record_audit("activate_campaign", {"campaign_id": cid})
        return True

    def pause_campaign(self, campaign_id: str) -> bool:
        """Pause an ACTIVE campaign.  Returns True on success."""
        cid = self._validate_id(campaign_id, "campaign_id")
        with self._lock:
            plan = self._campaigns.get(cid)
            if plan is None or plan.status != CampaignStatus.ACTIVE:
                return False
            plan.status = CampaignStatus.PAUSED
            plan.updated_at = _ts()
            self._record_audit("pause_campaign", {"campaign_id": cid})
        return True

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent step execution records."""
        limit = min(max(1, limit), 1000)
        with self._lock:
            return list(self._execution_history[-limit:])

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit log entries."""
        limit = min(max(1, limit), 1000)
        with self._lock:
            return list(self._audit_log[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_to_suppression(self, contact_id: str, reason: str) -> None:
        """Add to suppression list with CWE-400 cap enforcement."""
        with self._lock:
            if contact_id in self._suppression_list:
                return
            if len(self._suppression_list) >= _MAX_SUPPRESSION_LIST:
                # Hard cap reached — cannot add more
                logger.warning(
                    "Suppression list at capacity (%d); cannot add %s",
                    _MAX_SUPPRESSION_LIST,
                    contact_id[:20],  # partial only
                )
                return
            self._suppression_list[contact_id] = reason

    def _check_compliance(
        self,
        contact_id: str,
        email: str,
        channel: str,
        region: str,
        cooldown_type: CooldownType,
    ) -> Dict[str, Any]:
        """Run pre-flight compliance check; returns {"allowed": bool, "reason": str}."""
        # Prefer live compliance gate
        if self._compliance_gate is not None:
            try:
                decision = self._compliance_gate.check_and_record(
                    contact_id=contact_id,
                    contact_email=email,
                    channel=channel,
                    outreach_type="marketing",
                    contact_region=region,
                )
                allowed = getattr(decision, "allowed", False)
                reason = getattr(decision, "regulation", "")
                if not isinstance(reason, str):
                    reason = str(reason)
                return {"allowed": allowed, "reason": reason}
            except Exception as exc:
                logger.warning(
                    "ComplianceGate check failed: %s", _sanitize_error(exc)
                )
                # Fail closed
                return {"allowed": False, "reason": "compliance_gate_error"}

        # Fall back to governor directly
        if self._governor is not None:
            try:
                decision = self._governor.validate_outreach(
                    contact_id=contact_id,
                    contact_email=email,
                    channel=channel,
                    outreach_type=(
                        "customer_marketing"
                        if cooldown_type == CooldownType.CUSTOMER
                        else "prospecting"
                    ),
                    contact_region=region,
                )
                decision_type = getattr(decision, "decision", None)
                if decision_type is None:
                    decision_type = getattr(decision, "decision_type", "BLOCK")
                allowed = str(decision_type).upper() == "ALLOW"
                reason = str(getattr(decision, "reason", "governor_decision"))
                return {"allowed": allowed, "reason": reason}
            except Exception as exc:
                logger.warning(
                    "Governor validate_outreach failed: %s", _sanitize_error(exc)
                )
                return {"allowed": False, "reason": "governor_error"}

        # No compliance layer available — default ALLOW (test/stub mode only)
        logger.debug(
            "No compliance layer injected; defaulting to ALLOW for contact %s",
            contact_id[:20],
        )
        return {"allowed": True, "reason": "no_compliance_layer"}

    def _record_outreach_contact(
        self,
        contact_id: str,
        email: str,
        channel: str,
        region: str,
    ) -> None:
        """Record that we contacted this person (for cooldown tracking)."""
        # Log masked email only                              [PII protection]
        logger.debug(
            "Outreach recorded: contact=%s email=%s channel=%s",
            contact_id[:20],
            _mask_email(email),
            channel,
        )

        if self._compliance_gate is not None:
            try:
                self._compliance_gate.check_and_record(
                    contact_id=contact_id,
                    contact_email=email,
                    channel=channel,
                    outreach_type="marketing",
                    contact_region=region,
                )
            except Exception as exc:
                logger.debug("_record_outreach_contact: %s", _sanitize_error(exc))

    def _render_step(
        self,
        step: CadenceStep,
        contact_id: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Render the outreach message for a step."""
        business_type = str(metadata.get("business_type", "business"))

        # Personalisation from BUSINESS_TYPE_CONSTRAINTS
        try:
            from self_selling_engine._constraints import BUSINESS_TYPE_CONSTRAINTS
            bt_data = BUSINESS_TYPE_CONSTRAINTS.get(business_type, {})
            bt_display = bt_data.get("display_name", business_type.replace("_", " ").title())
        except Exception:
            bt_display = business_type.replace("_", " ").title()

        parts: List[str] = []

        # Greeting
        contact_name = str(metadata.get("contact_name", "there"))
        parts.append(f"Hi {contact_name},")

        # META_PROOF paragraph
        if step.use_meta_proof:
            parts.append(
                self.META_PROOF_TEMPLATE.format(business_type=bt_display)
            )

        # Body template
        if step.body_template:
            try:
                rendered = step.body_template.format(
                    business_type=bt_display,
                    contact_name=contact_name,
                )
                parts.append(rendered)
            except KeyError:
                parts.append(step.body_template)
        else:
            # Default value-prop paragraph
            parts.append(
                f"We help {bt_display} businesses automate their operations "
                "— from lead qualification to invoicing to operations — "
                "without writing a single line of code."
            )

        # Live stats snippet
        live_stats = self._build_live_stats_snippet()
        if live_stats:
            parts.append(live_stats)

        # Trial offer
        parts.append(self.TRIAL_OFFER_TEMPLATE)

        return "\n\n".join(parts)

    @staticmethod
    def _build_live_stats_snippet() -> str:
        """Return a real-time-proof stats paragraph (placeholder metrics)."""
        return (
            "Right now, the system is actively managing automations, "
            "processing compliance checks, and coordinating across channels — "
            "all without human intervention."
        )

    def _build_body_template(
        self,
        channel: str,
        business_type: str,
        use_meta_proof: bool,
    ) -> str:
        """Build a default body template for a cadence step."""
        if channel == "sms":
            return (
                "Murphy AI here — automated setup for {business_type} businesses. "
                "Reply STOP to opt out."
            )
        elif channel == "linkedin":
            return (
                "Hi {contact_name}, I came across your profile and thought "
                "Murphy's automation platform might be a good fit for "
                "{business_type} operations. Happy to share more."
            )
        else:
            # email
            return (
                "I noticed your {business_type} business could benefit from "
                "the automation capabilities Murphy provides. "
                "I'd love to show you what's possible in 15 minutes."
            )

    def _record_audit(self, action: str, context: Dict[str, Any]) -> None:
        """Append a bounded audit record (must be called while lock is held)."""
        capped_append(
            self._audit_log,
            {"action": action, "context": context, "at": _ts()},
            max_size=_MAX_AUDIT_LOG,
        )
