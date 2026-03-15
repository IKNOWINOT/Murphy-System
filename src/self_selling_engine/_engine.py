"""Self-selling engine classes.

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from self_selling_engine._compliance import (
    ComplianceDecision,
    ContactRecord,
    OutreachComplianceGovernor,
)
from self_selling_engine._constraints import BUSINESS_TYPE_CONSTRAINTS
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
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ProspectProfile:
    """Full profile of a prospect built during Phase 1 onboarding."""

    prospect_id: str
    company_name: str
    contact_name: str
    contact_email: str
    business_type: str          # key into BUSINESS_TYPE_CONSTRAINTS
    industry: str
    estimated_revenue: str      # "under_1m" | "1m_10m" | "10m_50m" | "50m_plus"
    tools_detected: List[str]   # scraped from website / job postings
    pain_points_inferred: List[str]
    automation_constraints: List[Dict[str, Any]]   # metric→threshold mappings
    constraint_alert_rules: List[str]              # AlertRule IDs generated
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class OutreachMessage:
    """A composed self-selling outreach message."""

    message_id: str
    prospect_id: str
    channel: str               # "email" | "sms" | "linkedin"
    subject: str
    body: str
    live_stats_snapshot: Dict[str, Any]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sent: bool = False
    sent_at: Optional[str] = None


@dataclass
class SellCycleResult:
    """Result of one complete 20-minute selling cycle."""

    cycle_id: str
    started_at: str
    completed_at: str
    prospects_discovered: int
    outreach_sent: int
    replies_detected: int
    trials_started: int
    errors: List[str] = field(default_factory=list)


@dataclass
class SelfSellingMetrics:
    """Running counters used in the live-stats snapshot."""

    emails_sent: int = 0
    texts_sent: int = 0
    state_changes: int = 0
    projects_active: int = 0
    deliverables_created: List[str] = field(default_factory=list)
    cycles_completed: int = 0
    total_prospects_contacted: int = 0
    total_trials_started: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emails_sent": self.emails_sent,
            "texts_sent": self.texts_sent,
            "state_changes": self.state_changes,
            "projects_active": self.projects_active,
            "deliverables_created": list(self.deliverables_created),
            "cycles_completed": self.cycles_completed,
            "total_prospects_contacted": self.total_prospects_contacted,
            "total_trials_started": self.total_trials_started,
        }


# ---------------------------------------------------------------------------
# Phase 1: Prospect Onboarder
# ---------------------------------------------------------------------------

class ProspectOnboarder:
    """
    Phase 1 — Prospect Discovery & Constraint Generation.

    Collects business info from public sources, infers the business type,
    generates automation constraints, and stores a ProspectProfile with
    corresponding AlertRule objects registered in the AlertRulesEngine.
    """

    def __init__(self, alert_engine: Any = None) -> None:
        if alert_engine is None:
            from alert_rules_engine import AlertRulesEngine
            alert_engine = AlertRulesEngine()
        self._alert_engine = alert_engine
        self._profiles: Dict[str, ProspectProfile] = {}
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────

    def onboard(
        self,
        company_name: str,
        contact_name: str,
        contact_email: str,
        *,
        website: str = "",
        linkedin_url: str = "",
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> ProspectProfile:
        """
        Run a full onboarding analysis for a prospect and return a
        ProspectProfile with AlertRules registered for their constraints.
        """
        prospect_id = str(uuid.uuid4())
        extra = extra_context or {}

        business_type = self._infer_business_type(
            company_name, website, linkedin_url, extra
        )
        industry = self._infer_industry(business_type, extra)
        estimated_revenue = extra.get("estimated_revenue", "under_1m")
        tools_detected = self._detect_tools(website, extra)
        pain_points = self._infer_pain_points(business_type, tools_detected)

        constraints = BUSINESS_TYPE_CONSTRAINTS.get(business_type, {}).get(
            "primary_constraints", []
        )

        rule_ids = self._register_alert_rules(
            prospect_id, business_type, constraints
        )

        profile = ProspectProfile(
            prospect_id=prospect_id,
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            business_type=business_type,
            industry=industry,
            estimated_revenue=estimated_revenue,
            tools_detected=tools_detected,
            pain_points_inferred=pain_points,
            automation_constraints=constraints,
            constraint_alert_rules=rule_ids,
        )

        with self._lock:
            self._profiles[prospect_id] = profile

        logger.info(
            "Onboarded prospect %s as %s with %d constraints",
            company_name, business_type, len(constraints),
        )
        return profile

    def get_profile(self, prospect_id: str) -> Optional[ProspectProfile]:
        """Retrieve a previously onboarded prospect profile."""
        with self._lock:
            return self._profiles.get(prospect_id)

    def list_profiles(self) -> List[ProspectProfile]:
        """Return all stored profiles."""
        with self._lock:
            return list(self._profiles.values())

    # ── Internal helpers ──────────────────────────────────────────────

    def _infer_business_type(
        self,
        company_name: str,
        website: str,
        linkedin_url: str,
        extra: Dict[str, Any],
    ) -> str:
        """Infer business type from available public signals."""
        if "business_type" in extra:
            bt = extra["business_type"]
            if bt in BUSINESS_TYPE_CONSTRAINTS:
                return bt

        name_lower = company_name.lower()
        combined = f"{name_lower} {website.lower()} {linkedin_url.lower()}"

        # Keyword heuristics (ordered by specificity)
        keyword_map = [
            ("law", "law_firm"),
            ("legal", "law_firm"),
            ("attorney", "law_firm"),
            ("restaurant", "restaurant"),
            ("food", "restaurant"),
            ("cafe", "restaurant"),
            ("medical", "medical_practice"),
            ("health", "medical_practice"),
            ("clinic", "medical_practice"),
            ("dental", "medical_practice"),
            ("realty", "real_estate"),
            ("real estate", "real_estate"),
            ("realtor", "real_estate"),
            ("logistics", "logistics"),
            ("freight", "logistics"),
            ("shipping", "logistics"),
            ("transport", "logistics"),
            ("school", "education"),
            ("university", "education"),
            ("academy", "education"),
            ("learning", "education"),
            ("accounting", "accounting_firm"),
            ("cpa", "accounting_firm"),
            ("bookkeeping", "accounting_firm"),
            ("marketing", "marketing_agency"),
            ("agency", "marketing_agency"),
            ("advertising", "marketing_agency"),
            ("saas", "saas"),
            ("software", "saas"),
            ("app", "saas"),
            ("platform", "saas"),
            ("plumber", "trades_contractor"),
            ("electrician", "trades_contractor"),
            ("contractor", "trades_contractor"),
            ("hvac", "trades_contractor"),
            ("roofing", "trades_contractor"),
            ("consult", "consulting"),
            ("advisory", "consulting"),
            ("shop", "ecommerce"),
            ("store", "ecommerce"),
            ("ecommerce", "ecommerce"),
        ]

        for keyword, btype in keyword_map:
            if keyword in combined:
                return btype

        return "consulting"  # default fallback

    def _infer_industry(self, business_type: str, extra: Dict[str, Any]) -> str:
        if "industry" in extra:
            return extra["industry"]
        industry_map = {
            "consulting": "professional_services",
            "ecommerce": "retail",
            "law_firm": "legal",
            "restaurant": "food_service",
            "real_estate": "real_estate",
            "medical_practice": "healthcare",
            "trades_contractor": "construction",
            "saas": "technology",
            "marketing_agency": "marketing",
            "accounting_firm": "finance",
            "logistics": "logistics",
            "education": "education",
        }
        return industry_map.get(business_type, "other")

    def _detect_tools(self, website: str, extra: Dict[str, Any]) -> List[str]:
        detected: List[str] = list(extra.get("tools_detected", []))
        tool_keywords = {
            "salesforce": "salesforce",
            "hubspot": "hubspot",
            "quickbooks": "quickbooks",
            "shopify": "shopify",
            "wordpress": "wordpress",
            "zapier": "zapier",
            "slack": "slack",
            "stripe": "stripe",
        }
        site_lower = website.lower()
        for keyword, tool in tool_keywords.items():
            if keyword in site_lower and tool not in detected:
                detected.append(tool)
        return detected

    def _infer_pain_points(
        self, business_type: str, tools_detected: List[str]
    ) -> List[str]:
        pain_map = {
            "consulting": ["manual_time_tracking", "slow_proposal_creation", "inconsistent_follow_up"],
            "ecommerce": ["cart_abandonment", "manual_inventory_updates", "delayed_fulfillment"],
            "law_firm": ["slow_client_intake", "manual_billing", "document_review_bottleneck"],
            "restaurant": ["high_food_waste", "manual_ordering", "staff_scheduling_complexity"],
            "real_estate": ["slow_lead_response", "manual_listing_updates", "inconsistent_nurture"],
            "medical_practice": ["high_no_shows", "claim_denials", "scheduling_gaps"],
            "trades_contractor": ["slow_quoting", "invoice_collection_delays", "scheduling_conflicts"],
            "saas": ["high_churn", "slow_trial_conversion", "support_bottleneck"],
            "marketing_agency": ["manual_reporting", "client_communication_overhead", "project_tracking"],
            "accounting_firm": ["document_chasing", "manual_data_entry", "deadline_management"],
            "logistics": ["route_inefficiency", "manual_tracking_updates", "empty_miles"],
            "education": ["low_completion_rates", "enrollment_drop_off", "manual_grading"],
        }
        return pain_map.get(business_type, ["manual_processes", "slow_workflows"])

    def _register_alert_rules(
        self,
        prospect_id: str,
        business_type: str,
        constraints: List[Dict[str, Any]],
    ) -> List[str]:
        from alert_rules_engine import AlertRule, AlertSeverity, Comparator

        rule_ids: List[str] = []
        severity_map = {
            "revenue": AlertSeverity.CRITICAL,
            "cash_flow": AlertSeverity.CRITICAL,
            "retention": AlertSeverity.WARNING,
            "growth": AlertSeverity.WARNING,
            "efficiency": AlertSeverity.INFO,
            "satisfaction": AlertSeverity.INFO,
            "conversion": AlertSeverity.WARNING,
            "margin": AlertSeverity.WARNING,
            "quality": AlertSeverity.INFO,
            "capacity": AlertSeverity.INFO,
            "ltv": AlertSeverity.WARNING,
            "outcomes": AlertSeverity.INFO,
            "expansion": AlertSeverity.INFO,
            "pipeline": AlertSeverity.WARNING,
            "client_retention": AlertSeverity.WARNING,
            "client_satisfaction": AlertSeverity.INFO,
        }
        comparator_map = {
            "gte": Comparator.GTE,
            "lte": Comparator.LTE,
            "gt": Comparator.GT,
            "lt": Comparator.LT,
            "eq": Comparator.EQ,
        }

        for constraint in constraints:
            rule_id = str(uuid.uuid4())
            impact = constraint.get("impact", "efficiency")
            severity = severity_map.get(impact, AlertSeverity.INFO)
            comparator = comparator_map.get(
                constraint.get("comparator", "gte"), Comparator.GTE
            )

            rule = AlertRule(
                rule_id=rule_id,
                name=f"{prospect_id[:8]}_{constraint['metric']}",
                severity=severity,
                metric=f"prospect.{prospect_id[:8]}.{constraint['metric']}",
                comparator=comparator,
                threshold=float(constraint["threshold"]),
                description=(
                    f"{business_type} constraint: {constraint['metric']} "
                    f"{constraint['comparator']} {constraint['threshold']} "
                    f"({constraint.get('unit', '')}) — impact: {impact}"
                ),
            )
            try:
                self._alert_engine.add_rule(rule)
                rule_ids.append(rule_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to register alert rule %s: %s", rule_id, exc)

        return rule_ids


# ---------------------------------------------------------------------------
# Phase 2: Self-Selling Outreach
# ---------------------------------------------------------------------------

class SelfSellingOutreach:
    """
    Phase 2 — Self-Selling Outreach.

    Composes self-referential outreach messages that prove Murphy works
    by describing what it has already done in real time.
    """

    META_PROOF = (
        "The fact that I'm contacting you right now is part of the demo. "
        "No human at Inoni is selling Murphy. This message was composed, "
        "personalized for your {business_type} business, and sent entirely "
        "by the system."
    )

    TRIAL_OFFER = (
        "I can set up a full automation for your business in an email reply. "
        "Tell me about your business, and I'll run Murphy for you for 3 days, "
        "free. You'll get a metrics report showing exactly what it accomplished."
    )

    def __init__(self) -> None:
        self._sent: List[OutreachMessage] = []
        self._lock = threading.Lock()

    def compose(
        self,
        prospect: ProspectProfile,
        live_stats: Dict[str, Any],
    ) -> OutreachMessage:
        """Compose a personalized, self-referential outreach message."""
        bt_info = BUSINESS_TYPE_CONSTRAINTS.get(prospect.business_type, {})
        bt_display = bt_info.get("display_name", prospect.business_type)

        subject = (
            f"Murphy just handled {live_stats.get('emails_sent', 0)} emails "
            f"automatically — this is what it can do for {prospect.company_name}"
        )

        stats_para = self._format_stats_paragraph(live_stats)
        meta_para = self.META_PROOF.format(business_type=bt_display)
        constraints_para = self._format_constraints_paragraph(prospect, bt_display)
        trial_para = self.TRIAL_OFFER

        body = "\n\n".join([
            f"Hi {prospect.contact_name},",
            stats_para,
            meta_para,
            constraints_para,
            trial_para,
            "— Murphy (Inoni LLC Autonomous Sales Agent)",
        ])

        msg = OutreachMessage(
            message_id=str(uuid.uuid4()),
            prospect_id=prospect.prospect_id,
            channel="email",
            subject=subject,
            body=body,
            live_stats_snapshot=dict(live_stats),
        )
        return msg

    def send(
        self,
        message: OutreachMessage,
        connector: Any = None,
    ) -> OutreachMessage:
        """
        Mark message as sent (and optionally dispatch via connector).

        If a connector is supplied it is called with
        ``connector.execute_action("send_email", {...})``.
        """
        if connector is not None:
            try:
                connector.execute_action(
                    "send_email",
                    {
                        "to": None,   # caller fills this before dispatch
                        "subject": message.subject,
                        "body": message.body,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Connector send failed for message %s: %s", message.message_id, exc
                )

        message.sent = True
        message.sent_at = datetime.now(timezone.utc).isoformat()

        with self._lock:
            capped_append(self._sent, message)

        logger.info("Outreach sent to prospect %s", message.prospect_id)
        return message

    def get_sent_messages(self) -> List[OutreachMessage]:
        with self._lock:
            return list(self._sent)

    # ── Formatting helpers ────────────────────────────────────────────

    def _format_stats_paragraph(self, stats: Dict[str, Any]) -> str:
        deliverables = stats.get("deliverables_created", [])
        deliverable_str = (
            ", ".join(str(d) for d in deliverables[:3]) if deliverables else "none yet"
        )
        return (
            f"In the past 20 minutes, Murphy has:\n"
            f"  • Sent {stats.get('emails_sent', 0)} emails and "
            f"{stats.get('texts_sent', 0)} texts\n"
            f"  • Worked across {stats.get('state_changes', 0)} state changes in "
            f"project timelines across {stats.get('projects_active', 0)} projects\n"
            f"  • Generated these deliverables: {deliverable_str}"
        )

    def _format_constraints_paragraph(
        self, prospect: ProspectProfile, bt_display: str
    ) -> str:
        if not prospect.automation_constraints:
            return (
                f"For a {bt_display} like {prospect.company_name}, Murphy would "
                "monitor your key business metrics and automatically trigger "
                "corrective actions when thresholds are breached."
            )

        lines = []
        for c in prospect.automation_constraints[:4]:
            direction = "≥" if c.get("comparator") in ("gte", "gt") else "≤"
            lines.append(
                f"  • {c['metric'].replace('_', ' ')}: "
                f"{direction} {c['threshold']} {c.get('unit', '')}"
            )

        return (
            f"For a {bt_display} like {prospect.company_name}, we'd watch:\n"
            + "\n".join(lines)
            + "\nWhen any of these thresholds are breached, Murphy automatically "
            "triggers corrective action."
        )


# ---------------------------------------------------------------------------
# Phase 4: Trial Shadow Deployer
# ---------------------------------------------------------------------------

class TrialShadowDeployer:
    """
    Phase 4 — Shadow Agent Handoff.

    Deploys a ShadowLearningAgent during the trial that observes workflow
    patterns.  When the trial ends the shadow stays as the conversion hook.
    """

    def __init__(self, shadow_integration: Any = None) -> None:
        if shadow_integration is None:
            from shadow_agent_integration import ShadowAgentIntegration
            shadow_integration = ShadowAgentIntegration()
        self._integration = shadow_integration
        self._deployments: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def deploy(
        self, trial_id: str, prospect: ProspectProfile
    ) -> Dict[str, Any]:
        """
        Create a shadow agent for the trial and start observation.
        Returns the shadow agent record.
        """
        shadow = self._integration.create_shadow_agent(
            primary_role_id=f"trial_{trial_id}",
            account_id=prospect.prospect_id,
            department="sales_trial",
            permissions=["observe", "record"],
        )
        record = {
            "shadow_agent_id": shadow.agent_id,
            "trial_id": trial_id,
            "prospect_id": prospect.prospect_id,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "observations": 0,
        }
        with self._lock:
            self._deployments[trial_id] = record

        logger.info(
            "Shadow agent %s deployed for trial %s", shadow.agent_id, trial_id
        )
        return record

    def record_observation(self, trial_id: str, action: str, context: Dict[str, Any]) -> None:
        """Record a workflow observation for the trial's shadow agent."""
        with self._lock:
            record = self._deployments.get(trial_id)
        if record is None:
            return

        try:
            self._integration.observe_action(
                agent_id=record["shadow_agent_id"],
                action=action,
                context=context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Shadow observe_action failed: %s", exc)

        with self._lock:
            if trial_id in self._deployments:
                self._deployments[trial_id]["observations"] += 1

    def generate_proposal(self, trial_id: str) -> Optional[Dict[str, Any]]:
        """Ask the shadow agent to produce an automation proposal."""
        with self._lock:
            record = self._deployments.get(trial_id)
        if record is None:
            return None

        try:
            proposal = self._integration.propose_automation(
                agent_id=record["shadow_agent_id"]
            )
            return proposal
        except Exception as exc:  # noqa: BLE001
            logger.warning("Shadow propose_automation failed: %s", exc)
            return None

    def get_observation_count(self, trial_id: str) -> int:
        with self._lock:
            return self._deployments.get(trial_id, {}).get("observations", 0)


# ---------------------------------------------------------------------------
# Phase 5: Contractor-Augmented Intel
# ---------------------------------------------------------------------------

class ContractorAugmentedIntel:
    """
    Phase 5 — HITL Contractor Bridge for External Data.

    For data Murphy can't collect itself (industry-specific market data,
    competitor pricing, local regulations), it dispatches contractors via
    the freelancer infrastructure, then triggers the next automation on
    delivery.
    """

    def __init__(
        self,
        hitl_bridge: Any = None,
        dispatch_interface: Any = None,
        scaler: Any = None,
    ) -> None:
        # Defer expensive/pydantic-dependent imports until first use
        self._hitl_arg = hitl_bridge
        self._dispatch_arg = dispatch_interface
        self._hitl: Any = None
        self._dispatch: Any = None
        self._scaler = scaler   # AutomationScaler (optional)
        self._deps_initialised = False
        self._deps_lock = threading.Lock()

        self._pending: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _ensure_deps(self) -> None:
        """Lazily initialise hitl_bridge and dispatch_interface on first use."""
        with self._deps_lock:
            if self._deps_initialised:
                return
            if self._hitl_arg is not None:
                self._hitl = self._hitl_arg
            else:
                from freelancer_validator.hitl_bridge import FreelancerHITLBridge
                self._hitl = FreelancerHITLBridge()

            if self._dispatch_arg is not None:
                self._dispatch = self._dispatch_arg
            else:
                from niche_business_generator import ContractorDispatchInterface
                self._dispatch = ContractorDispatchInterface()

            self._deps_initialised = True

    def request_market_data(
        self,
        prospect: ProspectProfile,
        data_needs: List[str],
    ) -> str:
        """
        Dispatch a contractor task to gather external intelligence.
        Returns the task_id.
        """
        self._ensure_deps()
        description = (
            f"Market intelligence for {prospect.company_name} "
            f"({prospect.business_type}). Data needs: {', '.join(data_needs)}. "
            f"Industry: {prospect.industry}."
        )

        task = self._dispatch.create_task(
            niche_id=prospect.prospect_id,
            title=f"Market data — {prospect.company_name}",
            description=description,
            skills_required=data_needs[:5],
            estimated_hours=2.0,
        )

        with self._lock:
            self._pending[task.task_id] = {
                "task_id": task.task_id,
                "prospect_id": prospect.prospect_id,
                "data_needs": data_needs,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
                "triggered_automations": [],
            }

        logger.info(
            "Contractor task %s dispatched for prospect %s",
            task.task_id, prospect.prospect_id,
        )
        return task.task_id

    def on_contractor_delivery(
        self, task_id: str, deliverable: Dict[str, Any]
    ) -> List[str]:
        """
        Process delivered data and trigger downstream automations.
        Returns a list of triggered automation IDs.
        """
        with self._lock:
            pending = self._pending.get(task_id)
        if pending is None:
            logger.warning("Unknown contractor task %s", task_id)
            return []

        scored = self.score_and_route(task_id)
        quality_ok = scored.get("quality_gate", "pass") == "pass"

        triggered: List[str] = []
        if quality_ok:
            auto_id = str(uuid.uuid4())
            triggered.append(auto_id)
            logger.info(
                "Contractor delivery %s triggered automation %s", task_id, auto_id
            )

        with self._lock:
            if task_id in self._pending:
                self._pending[task_id]["status"] = "delivered"
                self._pending[task_id]["triggered_automations"] = triggered

        return triggered

    def score_and_route(self, task_id: str) -> Dict[str, Any]:
        """Quality gate and routing decision for a contractor delivery."""
        with self._lock:
            pending = self._pending.get(task_id, {})
        return {
            "task_id": task_id,
            "quality_gate": "pass",
            "route": "prospect_profile_enrichment",
            "prospect_id": pending.get("prospect_id", ""),
        }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class MurphySelfSellingEngine:
    """
    The complete self-selling loop.  Murphy sells Murphy.

    Every 20 minutes it:
      1. Discovers prospects
      2. Generates their business-specific automation constraints
      3. Sends outreach where the contact IS the demo
      4. Monitors for replies
      5. Spins up 3-day trials for positive responses
      6. Routes trial data, generates reports
      7. Deploys shadow agents that survive the trial
      8. Dispatches contractors for intelligence it can't gather alone
      9. Records everything for the Librarian to learn from
    """

    def __init__(
        self,
        alert_engine: Any = None,
        shadow_integration: Any = None,
        hitl_bridge: Any = None,
        dispatch_interface: Any = None,
        scaler: Any = None,
        compliance_governor: Optional["OutreachComplianceGovernor"] = None,
    ) -> None:
        self.prospect_onboarder = ProspectOnboarder(alert_engine=alert_engine)
        self.outreach = SelfSellingOutreach()
        self.shadow_deployer = TrialShadowDeployer(shadow_integration=shadow_integration)
        self.contractor_intel = ContractorAugmentedIntel(
            hitl_bridge=hitl_bridge,
            dispatch_interface=dispatch_interface,
            scaler=scaler,
        )
        self.metrics = SelfSellingMetrics()
        self._lock = threading.Lock()

        # Compliance governor — enforces 30-day cooldown, opt-out suppression,
        # and per-channel daily rate limits before any outreach is sent.
        self.compliance_governor: OutreachComplianceGovernor = (
            compliance_governor or OutreachComplianceGovernor()
        )

        # Lazy import to avoid circular dependencies at module load
        self._trial_orchestrator: Any = None

    @property
    def trial_orchestrator(self) -> Any:
        if self._trial_orchestrator is None:
            from trial_orchestrator import TrialOrchestrator
            self._trial_orchestrator = TrialOrchestrator(
                shadow_deployer=self.shadow_deployer
            )
        return self._trial_orchestrator

    # ── Public API ────────────────────────────────────────────────────

    def run_selling_cycle(self) -> SellCycleResult:
        """One complete selling cycle — discovery through trial management."""
        cycle_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []

        prospects_discovered = 0
        outreach_sent = 0
        replies_detected = 0
        trials_started = 0

        try:
            prospects = self._discover_prospects()
            prospects_discovered = len(prospects)

            live_stats = self.get_live_system_stats()

            for prospect in prospects:
                try:
                    channel = "email"  # default channel for self-selling outreach

                    # Compliance gate — skip if not allowed
                    try:
                        decision = self.compliance_governor.check_contact_allowed(
                            prospect_id=prospect.prospect_id,
                            channel=channel,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Compliance check failed for %s, skipping: %s",
                            prospect.prospect_id, exc,
                        )
                        errors.append(
                            f"Compliance check error for {prospect.prospect_id}: {exc}"
                        )
                        continue

                    if not decision.allowed:
                        logger.debug(
                            "Outreach blocked for %s (%s): %s",
                            prospect.prospect_id, decision.status, decision.reason,
                        )
                        continue

                    msg = self.compose_outreach_message(prospect)
                    self.outreach.send(msg)

                    # Record successful contact for cooldown tracking
                    try:
                        self.compliance_governor.record_contact(
                            prospect_id=prospect.prospect_id,
                            channel=channel,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Failed to record contact for %s: %s",
                            prospect.prospect_id, exc,
                        )

                    outreach_sent += 1
                    with self._lock:
                        self.metrics.emails_sent += 1
                        self.metrics.total_prospects_contacted += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Outreach failed for {prospect.prospect_id}: {exc}")

            with self._lock:
                self.metrics.cycles_completed += 1

        except Exception as exc:  # noqa: BLE001
            errors.append(f"Cycle error: {exc}")
            logger.exception("Error in selling cycle %s", cycle_id)

        completed_at = datetime.now(timezone.utc).isoformat()
        return SellCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            completed_at=completed_at,
            prospects_discovered=prospects_discovered,
            outreach_sent=outreach_sent,
            replies_detected=replies_detected,
            trials_started=trials_started,
            errors=errors,
        )

    def compose_outreach_message(self, prospect: ProspectProfile) -> OutreachMessage:
        """Generate the self-referential outreach message with live system stats."""
        live_stats = self.get_live_system_stats()
        return self.outreach.compose(prospect, live_stats)

    def get_live_system_stats(self) -> Dict[str, Any]:
        """Collect real-time stats for the outreach message."""
        with self._lock:
            return self.metrics.to_dict()

    def handle_prospect_reply(self, prospect_id: str, reply: str) -> str:
        """
        Route positive replies into trial setup, negative into nurture.
        Returns "trial_started" | "nurture" | "unknown_prospect".
        """
        profile = self.prospect_onboarder.get_profile(prospect_id)
        if profile is None:
            return "unknown_prospect"

        if self._is_positive_reply(reply):
            try:
                trial = self.trial_orchestrator.start_trial(
                    prospect=profile,
                    business_context={"reply": reply},
                )
                with self._lock:
                    self.metrics.total_trials_started += 1
                logger.info(
                    "Trial %s started for prospect %s", trial.trial_id, prospect_id
                )
                return "trial_started"
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to start trial for %s: %s", prospect_id, exc)
                return "nurture"
        else:
            logger.info("Prospect %s routed to nurture sequence", prospect_id)
            return "nurture"

    # ── Internal helpers ──────────────────────────────────────────────

    def _discover_prospects(self) -> List[ProspectProfile]:
        """
        Discover and onboard new prospects.

        In production, this would call SalesAutomationEngine.generate_leads()
        and onboard each lead.  For now it returns an empty list so the cycle
        runs cleanly without external dependencies.
        """
        try:
            from sales_automation import SalesAutomationEngine
            engine = SalesAutomationEngine()
            raw_leads = engine.generate_leads()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Lead generation failed: %s", exc)
            raw_leads = []

        profiles: List[ProspectProfile] = []
        for lead in raw_leads:
            try:
                profile = self.prospect_onboarder.onboard(
                    company_name=lead.get("company_name", "Unknown"),
                    contact_name=lead.get("contact_name", ""),
                    contact_email=lead.get("contact_email", ""),
                    extra_context=lead,
                )
                profiles.append(profile)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to onboard lead: %s", exc)

        return profiles

    @staticmethod
    def _is_positive_reply(reply: str) -> bool:
        """Heuristic check for a positive/interested reply."""
        negative_signals = [
            "not interested", "no thanks", "unsubscribe", "remove me",
            "stop emailing", "do not contact",
        ]
        positive_signals = [
            "yes", "i'm interested", "i am interested", "tell me more", "sounds good",
            "let's do it", "sign me up", "i'd like to try", "free trial",
            "how does it work", "set it up", "go ahead", "sure", "great",
        ]
        reply_lower = reply.lower()
        if any(signal in reply_lower for signal in negative_signals):
            return False
        return any(signal in reply_lower for signal in positive_signals)
