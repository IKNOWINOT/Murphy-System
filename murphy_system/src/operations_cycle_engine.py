"""
Operations Cycle Engine — Continuous Business Loops

Design Label: OPS-004 — Traction Cycles, R&D Sprints, Disruption Response & Branding
Owner: Founder / CRO / Chief Research Officer
Dependencies:
  - AdaptiveCampaignEngine (MKT-004, per-tier campaigns)
  - CompetitiveIntelligenceEngine (MKT-005, gaps & R&D backlog)
  - UnitEconomicsAnalyzer (BIZ-002, margin viability)
  - EventBackbone (audit trail)
  - HITLApprovalSystem (founder approval for disruptions)

Purpose:
  Ties together all business automation loops into repeating cycles
  that run alongside each other:

  TRACTION CYCLE (30 days):
    - Measure per-tier traction on rolling 30-day trends
    - Evaluate conversion rates, lead velocity, campaign ROI
    - Auto-adjust campaigns and demographics when traction is low
    - Propose paid advertising if organic pivots fail (HITL founder gate)

  R&D CYCLE (60 days):
    - At end of cycle, build everything queued in competitive R&D backlog
    - Create modules from accepted R&D items
    - Review what was built, run gap analysis, verify completion
    - Start next 60-day cycle with remaining + new items

  DISRUPTION RESPONSE (instant):
    - When an industry disruption is detected, immediately:
      1. Identify what's being created by the disruptor
      2. Gap-analyze against our capabilities
      3. Create our own non-plagiarized version using the system
      4. Route through HITL founder review before execution

  BRANDING SYSTEM:
    - Logo/identity specification
    - Brand guidelines for all campaign outputs
    - Consistent brand voice across marketing agents

  All cycles repeat continuously alongside other automations.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Disruption builds require HITL founder approval
  - Bounded history: configurable max cycles
  - Audit trail: every cycle tick is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
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
# Enums
# ---------------------------------------------------------------------------

class CycleType(str, Enum):
    """Type of operational cycle."""

    TRACTION = "traction"          # 30-day
    RD_SPRINT = "rd_sprint"        # 60-day
    DISRUPTION = "disruption"      # Instant


class CycleStatus(str, Enum):
    """Status of an operational cycle."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DisruptionSeverity(str, Enum):
    """Severity classification for a market disruption event."""

    CRITICAL = "critical"          # Major industry shift
    HIGH = "high"                  # Significant new competitor/product
    MEDIUM = "medium"              # Notable feature release by competitor
    LOW = "low"                    # Minor market change


class DisruptionResponseStatus(str, Enum):
    """Lifecycle status of a disruption response."""

    DETECTED = "detected"
    ANALYZING = "analyzing"
    PROPOSAL_READY = "proposal_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    BUILDING = "building"
    COMPLETED = "completed"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Brand Identity
# ---------------------------------------------------------------------------

@dataclass
class BrandIdentity:
    """Murphy System brand specification."""
    name: str = "murphy_system"
    tagline: str = "The Self-Running Automation Control Plane"
    logo_description: str = (
        "A stylized 'M' formed from interconnected circuit paths in neon green "
        "(#00ff41) on a dark background (#0a0a0a). The circuit paths represent "
        "automation flows converging into a unified system. Below the mark, "
        "'MURPHY' in clean sans-serif uppercase, 'SYSTEM' in lighter weight."
    )
    primary_color: str = "#00ff41"       # Neon green
    secondary_color: str = "#0a0a0a"     # Near-black
    accent_color: str = "#00d4ff"        # Cyan accent
    warning_color: str = "#ff6b35"       # Orange for alerts
    font_primary: str = "Inter, system-ui, sans-serif"
    font_mono: str = "JetBrains Mono, monospace"
    voice: str = (
        "Authoritative yet approachable. Technical precision with human "
        "warmth. We speak as builders to builders — clear, direct, "
        "no jargon for jargon's sake. Safety-first, always."
    )
    values: List[str] = field(default_factory=lambda: [
        "Safety first — every automation has guardrails",
        "Transparency — open source core, clear pricing",
        "Builder empowerment — your workflows, your control",
        "Continuous improvement — the system gets smarter",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tagline": self.tagline,
            "logo_description": self.logo_description,
            "colors": {
                "primary": self.primary_color,
                "secondary": self.secondary_color,
                "accent": self.accent_color,
                "warning": self.warning_color,
            },
            "fonts": {
                "primary": self.font_primary,
                "mono": self.font_mono,
            },
            "voice": self.voice,
            "values": list(self.values),
        }

    def campaign_style_guide(self) -> Dict[str, str]:
        """Return brand guidelines for campaign content generation."""
        return {
            "tone": self.voice,
            "product_name": self.name,
            "tagline": self.tagline,
            "primary_color_hex": self.primary_color,
            "accent_color_hex": self.accent_color,
            "font": self.font_primary,
            "always_include": "safety-first architecture, open source core",
            "never_say": (
                "Never claim 100% uptime. Never say 'AI replaces humans'. "
                "Always position as 'human-in-the-loop' augmentation."
            ),
        }


# ---------------------------------------------------------------------------
# Cycle Records
# ---------------------------------------------------------------------------

@dataclass
class TractionCycle:
    """A 30-day traction measurement cycle."""
    cycle_id: str
    cycle_number: int
    start_date: str
    end_date: str
    status: CycleStatus = CycleStatus.ACTIVE
    tier_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    adjustments_made: int = 0
    proposals_generated: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status.value,
            "tier_results": dict(self.tier_results),
            "adjustments_made": self.adjustments_made,
            "proposals_generated": self.proposals_generated,
        }


@dataclass
class RDSprintCycle:
    """A 60-day R&D build cycle."""
    cycle_id: str
    cycle_number: int
    start_date: str
    end_date: str
    status: CycleStatus = CycleStatus.ACTIVE
    queued_items: List[Dict[str, Any]] = field(default_factory=list)
    built_items: List[Dict[str, Any]] = field(default_factory=list)
    gap_analysis_result: Optional[Dict[str, Any]] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status.value,
            "queued_items_count": len(self.queued_items),
            "built_items_count": len(self.built_items),
            "has_gap_analysis": self.gap_analysis_result is not None,
        }


@dataclass
class DisruptionResponse:
    """Response to an industry disruption — instant analysis + build."""
    response_id: str
    disruptor: str                      # Company/product causing disruption
    description: str                    # What they launched/announced
    severity: DisruptionSeverity
    status: DisruptionResponseStatus = DisruptionResponseStatus.DETECTED
    our_gaps: List[str] = field(default_factory=list)
    our_existing_capabilities: List[str] = field(default_factory=list)
    proposed_builds: List[Dict[str, Any]] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "disruptor": self.disruptor,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "our_gaps": list(self.our_gaps),
            "our_existing_capabilities": list(self.our_existing_capabilities),
            "proposed_builds": list(self.proposed_builds),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Murphy's capabilities (shared with competitive intel)
# ---------------------------------------------------------------------------

_MURPHY_CAPABILITIES = {
    "natural_language_automation",
    "75_plus_connectors",
    "enterprise_governance_rbac",
    "audit_trail_compliance",
    "human_in_the_loop",
    "emergency_stop",
    "swarm_orchestration",
    "self_improving_ml",
    "scada_iot_integration",
    "on_premise_deployment",
    "content_creator_tools",
    "multi_llm_routing",
    "financial_reporting",
    "executive_planning",
    "domain_engine_10_domains",
    "zero_budget_bootstrap",
    "open_source_core",
    "safety_first_architecture",
    "deterministic_routing",
    "workspace_boundaries",
    "unit_economics_analyzer",
    "adaptive_campaign_engine",
    "competitive_intelligence",
}


# ---------------------------------------------------------------------------
# Operations Cycle Engine
# ---------------------------------------------------------------------------

class OperationsCycleEngine:
    """Manages continuous repeating business cycles.

    Three cycle types run in parallel:
      1. TRACTION (30-day) — measure & adjust marketing per tier
      2. RD_SPRINT (60-day) — build queued R&D items as modules
      3. DISRUPTION (instant) — respond to industry disruptions immediately

    All cycles include branding consistency and audit logging.
    """

    TRACTION_CYCLE_DAYS = 30
    RD_SPRINT_CYCLE_DAYS = 60

    def __init__(self) -> None:
        self._brand = BrandIdentity()
        self._traction_cycles: List[TractionCycle] = []
        self._rd_cycles: List[RDSprintCycle] = []
        self._disruptions: List[DisruptionResponse] = []
        self._lock = threading.Lock()
        self._event_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Brand
    # ------------------------------------------------------------------

    @property
    def brand(self) -> BrandIdentity:
        return self._brand

    def get_brand(self) -> Dict[str, Any]:
        return self._brand.to_dict()

    def get_campaign_style_guide(self) -> Dict[str, str]:
        return self._brand.campaign_style_guide()

    # ------------------------------------------------------------------
    # TRACTION CYCLE (30-day)
    # ------------------------------------------------------------------

    def start_traction_cycle(
        self,
        start_date: Optional[str] = None,
    ) -> TractionCycle:
        """Start a new 30-day traction measurement cycle."""
        now = datetime.now(timezone.utc)
        start = start_date or now.isoformat()
        end = (now + timedelta(days=self.TRACTION_CYCLE_DAYS)).isoformat()

        with self._lock:
            cycle_num = len(self._traction_cycles) + 1
            cycle = TractionCycle(
                cycle_id=f"tc-{uuid.uuid4().hex[:8]}",
                cycle_number=cycle_num,
                start_date=start,
                end_date=end,
            )
            capped_append(self._traction_cycles, cycle, max_size=100)
            self._log_event("traction_cycle_started", {
                "cycle_id": cycle.cycle_id,
                "cycle_number": cycle_num,
            })
        return cycle

    def evaluate_traction_cycle(
        self,
        tier_performance: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate traction across all tiers for the current 30-day cycle.

        Args:
            tier_performance: Dict mapping tier name to performance data:
                {"impressions": int, "leads": int, "conversions": int,
                 "spend_usd": float}

        Returns evaluation with per-tier traction status and actions.
        """
        with self._lock:
            current = self._traction_cycles[-1] if self._traction_cycles else None

        if current is None:
            current = self.start_traction_cycle()

        results: Dict[str, Dict[str, Any]] = {}
        total_adjustments = 0
        total_proposals = 0

        for tier, perf in tier_performance.items():
            leads = perf.get("leads", 0)
            conversions = perf.get("conversions", 0)
            conv_rate = conversions / leads if leads > 0 else 0.0

            if conv_rate >= 0.03:
                traction = "healthy"
                action = "maintain"
            elif conv_rate >= 0.01:
                traction = "low"
                action = "adjust_campaign"
                total_adjustments += 1
            else:
                traction = "critical"
                action = "propose_paid_ads"
                total_proposals += 1

            results[tier] = {
                "impressions": perf.get("impressions", 0),
                "leads": leads,
                "conversions": conversions,
                "conversion_rate": round(conv_rate, 4),
                "traction": traction,
                "action": action,
            }

        with self._lock:
            current.tier_results = results
            current.adjustments_made = total_adjustments
            current.proposals_generated = total_proposals

        self._log_event("traction_evaluated", {
            "cycle_id": current.cycle_id,
            "tiers_evaluated": len(results),
            "adjustments": total_adjustments,
            "proposals": total_proposals,
        })

        return {
            "cycle_id": current.cycle_id,
            "cycle_number": current.cycle_number,
            "tier_results": results,
            "adjustments_needed": total_adjustments,
            "proposals_needed": total_proposals,
        }

    def complete_traction_cycle(self) -> Optional[Dict[str, Any]]:
        """Complete the current traction cycle and auto-start next one."""
        with self._lock:
            if not self._traction_cycles:
                return None
            current = self._traction_cycles[-1]
            if current.status != CycleStatus.ACTIVE:
                return None
            current.status = CycleStatus.COMPLETED

        # Auto-start next cycle
        next_cycle = self.start_traction_cycle()

        self._log_event("traction_cycle_completed", {
            "completed": current.cycle_id,
            "next": next_cycle.cycle_id,
        })

        return {
            "completed_cycle": current.to_dict(),
            "next_cycle": next_cycle.to_dict(),
        }

    # ------------------------------------------------------------------
    # R&D SPRINT CYCLE (60-day)
    # ------------------------------------------------------------------

    def start_rd_cycle(
        self,
        queued_items: Optional[List[Dict[str, Any]]] = None,
        start_date: Optional[str] = None,
    ) -> RDSprintCycle:
        """Start a new 60-day R&D build cycle.

        Args:
            queued_items: R&D backlog items to build during this cycle.
        """
        now = datetime.now(timezone.utc)
        start = start_date or now.isoformat()
        end = (now + timedelta(days=self.RD_SPRINT_CYCLE_DAYS)).isoformat()

        with self._lock:
            cycle_num = len(self._rd_cycles) + 1
            cycle = RDSprintCycle(
                cycle_id=f"rd-{uuid.uuid4().hex[:8]}",
                cycle_number=cycle_num,
                start_date=start,
                end_date=end,
                queued_items=list(queued_items or []),
            )
            capped_append(self._rd_cycles, cycle, max_size=100)
            self._log_event("rd_cycle_started", {
                "cycle_id": cycle.cycle_id,
                "cycle_number": cycle_num,
                "queued_count": len(cycle.queued_items),
            })
        return cycle

    def queue_rd_item(self, item: Dict[str, Any]) -> bool:
        """Queue an R&D item into the current active cycle."""
        with self._lock:
            if not self._rd_cycles:
                return False
            current = self._rd_cycles[-1]
            if current.status != CycleStatus.ACTIVE:
                return False
            capped_append(current.queued_items, item, max_size=200)
        return True

    def complete_rd_cycle(
        self,
        built_modules: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Complete the current R&D cycle: mark items as built, run gap
        analysis, and auto-start the next cycle with remaining items.

        Args:
            built_modules: List of modules that were built during this cycle.
                           Each should have at minimum {"title": str, "status": str}.
        """
        with self._lock:
            if not self._rd_cycles:
                return None
            current = self._rd_cycles[-1]
            if current.status != CycleStatus.ACTIVE:
                return None

            current.built_items = list(built_modules or [])
            built_titles = {m.get("title", "") for m in current.built_items}

            # Items not built carry over to next cycle
            remaining = [
                item for item in current.queued_items
                if item.get("title", "") not in built_titles
            ]

            # Gap analysis: what percentage of queued items were completed
            total_queued = len(current.queued_items)
            total_built = len(current.built_items)
            completion_rate = total_built / total_queued if total_queued > 0 else 0.0

            current.gap_analysis_result = {
                "total_queued": total_queued,
                "total_built": total_built,
                "completion_rate": round(completion_rate, 4),
                "remaining_items": len(remaining),
                "carried_over": len(remaining),
            }

            current.status = CycleStatus.COMPLETED

        # Auto-start next cycle with remaining items
        next_cycle = self.start_rd_cycle(queued_items=remaining)

        self._log_event("rd_cycle_completed", {
            "completed": current.cycle_id,
            "built": total_built,
            "remaining": len(remaining),
            "next": next_cycle.cycle_id,
        })

        return {
            "completed_cycle": current.to_dict(),
            "gap_analysis": current.gap_analysis_result,
            "next_cycle": next_cycle.to_dict(),
        }

    # ------------------------------------------------------------------
    # DISRUPTION RESPONSE (instant)
    # ------------------------------------------------------------------

    def report_disruption(
        self,
        disruptor: str,
        description: str,
        severity: DisruptionSeverity,
        disruptor_features: Optional[List[str]] = None,
    ) -> DisruptionResponse:
        """Report an industry disruption for immediate analysis.

        Instantly:
          1. Identify what the disruptor is creating
          2. Gap-analyze against our capabilities
          3. Propose non-plagiarized builds for missing features
          4. Queue for HITL founder review
        """
        features = set(disruptor_features or [])

        # Gap analysis: what they have that we don't
        our_caps = set(_MURPHY_CAPABILITIES)
        gaps = sorted(features - our_caps)
        existing = sorted(features & our_caps)

        # Build proposals for each gap (non-plagiarized — our own approach)
        proposed_builds: List[Dict[str, Any]] = []
        for gap_feature in gaps:
            proposed_builds.append({
                "feature": gap_feature,
                "our_approach": (
                    f"Build Murphy-native '{gap_feature}' module using "
                    f"our safety-first architecture, governance layer, and "
                    f"multi-LLM routing. Non-derivative implementation "
                    f"leveraging existing Murphy subsystems."
                ),
                "estimated_effort": "medium",
                "priority": "high" if severity in (DisruptionSeverity.CRITICAL, DisruptionSeverity.HIGH) else "medium",
            })

        response = DisruptionResponse(
            response_id=f"dis-{uuid.uuid4().hex[:8]}",
            disruptor=disruptor,
            description=description,
            severity=severity,
            status=DisruptionResponseStatus.AWAITING_APPROVAL,
            our_gaps=gaps,
            our_existing_capabilities=existing,
            proposed_builds=proposed_builds,
        )

        with self._lock:
            capped_append(self._disruptions, response, max_size=200)

        self._log_event("disruption_reported", {
            "response_id": response.response_id,
            "disruptor": disruptor,
            "severity": severity.value,
            "gaps": len(gaps),
            "proposed_builds": len(proposed_builds),
            "requires": "founder_hitl_approval",
        })

        return response

    def approve_disruption_response(
        self,
        response_id: str,
        approved_by: str,
    ) -> Optional[DisruptionResponse]:
        """Founder approves a disruption response for building."""
        with self._lock:
            for dr in self._disruptions:
                if dr.response_id == response_id and dr.status == DisruptionResponseStatus.AWAITING_APPROVAL:
                    dr.status = DisruptionResponseStatus.APPROVED
                    dr.approved_by = approved_by
                    dr.approved_at = datetime.now(timezone.utc).isoformat()
                    self._log_event("disruption_approved", {
                        "response_id": response_id,
                        "approved_by": approved_by,
                    })
                    return dr
        return None

    def reject_disruption_response(
        self,
        response_id: str,
        reason: str = "",
    ) -> Optional[DisruptionResponse]:
        """Founder rejects a disruption response."""
        with self._lock:
            for dr in self._disruptions:
                if dr.response_id == response_id and dr.status == DisruptionResponseStatus.AWAITING_APPROVAL:
                    dr.status = DisruptionResponseStatus.REJECTED
                    dr.rejection_reason = reason
                    self._log_event("disruption_rejected", {
                        "response_id": response_id,
                        "reason": reason,
                    })
                    return dr
        return None

    def get_pending_disruptions(self) -> List[Dict[str, Any]]:
        """Get all disruptions awaiting founder approval."""
        with self._lock:
            return [
                dr.to_dict() for dr in self._disruptions
                if dr.status == DisruptionResponseStatus.AWAITING_APPROVAL
            ]

    # ------------------------------------------------------------------
    # Full cycle tick (runs all cycles)
    # ------------------------------------------------------------------

    def tick(
        self,
        tier_performance: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run one tick of all operation cycles.

        This is the main entry point called periodically by the scheduler.
        It evaluates traction (if data provided), checks R&D cycle status,
        and returns a combined status report.
        """
        result: Dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat()}

        # Traction evaluation
        if tier_performance:
            result["traction"] = self.evaluate_traction_cycle(tier_performance)
        else:
            with self._lock:
                current_tc = self._traction_cycles[-1] if self._traction_cycles else None
            result["traction"] = current_tc.to_dict() if current_tc else None

        # R&D cycle status
        with self._lock:
            current_rd = self._rd_cycles[-1] if self._rd_cycles else None
        result["rd_sprint"] = current_rd.to_dict() if current_rd else None

        # Pending disruptions
        result["pending_disruptions"] = self.get_pending_disruptions()

        # Brand
        result["brand"] = self._brand.name

        self._log_event("tick", {
            "traction_cycles": len(self._traction_cycles),
            "rd_cycles": len(self._rd_cycles),
            "disruptions": len(self._disruptions),
        })

        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_traction_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_dict() for c in self._traction_cycles]

    def get_rd_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c.to_dict() for c in self._rd_cycles]

    def get_disruption_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dr.to_dict() for dr in self._disruptions]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active_tc = next(
                (c for c in reversed(self._traction_cycles)
                 if c.status == CycleStatus.ACTIVE), None
            )
            active_rd = next(
                (c for c in reversed(self._rd_cycles)
                 if c.status == CycleStatus.ACTIVE), None
            )
            pending_disruptions = sum(
                1 for dr in self._disruptions
                if dr.status == DisruptionResponseStatus.AWAITING_APPROVAL
            )
        return {
            "traction_cycle_count": len(self._traction_cycles),
            "rd_cycle_count": len(self._rd_cycles),
            "disruption_count": len(self._disruptions),
            "active_traction_cycle": active_tc.cycle_id if active_tc else None,
            "active_rd_cycle": active_rd.cycle_id if active_rd else None,
            "pending_disruptions": pending_disruptions,
            "brand": self._brand.name,
            "traction_cycle_days": self.TRACTION_CYCLE_DAYS,
            "rd_cycle_days": self.RD_SPRINT_CYCLE_DAYS,
            "event_log_count": len(self._event_log),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _log_event(self, action: str, details: Dict[str, Any]) -> None:
        event = {
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._event_log, event, max_size=10_000)
        logger.info("OperationsCycle: %s", action)
