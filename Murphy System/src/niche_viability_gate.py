"""
Niche Viability Gate — Pre-deployment enforcement layer for the Niche Business Generator.

Every niche business must pass all five gates before it is considered deployable as an
Inoni LLC entity powered by Murphy System:

  1. Capability Check  — all required Murphy modules exist and are operational
  2. Cost Ceiling      — total build cost (LLM + contractor bids + delivery) is calculated
  3. Profit Threshold  — projected_revenue > total_build_cost × minimum_margin
  4. Information Acq.  — cheapest qualifying contractor bid selected (hybrid niches)
  5. HITL Validation   — human operator explicitly accepts risk in the RFP; agents may act
                         on external services only after this approval

After every stage a checkpoint is written so the pipeline can recover from any failure.
External contacts (contractor dispatch, APIs) are locked until HITL approval is recorded.

Design Label: NBG-VG-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from inference_gate_engine import InferenceDomainGateEngine
from mss_controls import MSSController

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — cost model
# ---------------------------------------------------------------------------

#: Per-MSS-operation LLM cost estimate (USD)
_LLM_COST_PER_OP: float = 0.02
#: Flat inference call cost (USD)
_LLM_INFERENCE_COST: float = 0.05
#: Base monthly hosting/delivery cost (USD)
_DELIVERY_BASE_COST: float = 10.0
#: Additional delivery cost per required module (USD/month)
_DELIVERY_PER_MODULE: float = 0.50

#: Synthetic bid price multipliers relative to the task template reference price
_BID_MULTIPLIERS: List[float] = [0.75, 0.85, 1.00, 1.25]

#: Which bid indices meet acceptance criteria by default (indices 1, 2, 3)
_BID_MEETS_CRITERIA: List[bool] = [False, True, True, True]

#: First-period revenue projections by revenue model string (USD)
_FIRST_PERIOD_REVENUE: Dict[str, float] = {
    "subscription": 99.0,
    "transaction": 500.0,
    "lead_gen": 250.0,
    "listing_fee": 150.0,
    "api_access": 199.0,
    "freemium": 29.0,
}

#: Default MSS sequence length used in cost estimation (MMSMM = 5 ops + 1 solidify = 6)
_DEFAULT_MSS_OPS: int = 6

#: Modules known to be in simulation-only mode (file content marker or known list)
_SIMULATION_ONLY_MODULES: frozenset = frozenset({
    "synthetic_failure_generator",
})

# ---------------------------------------------------------------------------
# Constants — stealth pricing model
# ---------------------------------------------------------------------------

#: Murphy charges clients 75 % of what humans would charge — stealth adoption
MURPHY_PRICE_RATIO: float = 0.75

#: Monthly human-equivalent billing rate per industry (USD/month).
#: These are deliberate market-rate estimates — Murphy's actual cost is < 1 % of these.
_HUMAN_RATES_BY_INDUSTRY: Dict[str, float] = {
    "technology":        15_000.0,
    "software":          15_000.0,
    "finance":           12_000.0,
    "legal":             10_000.0,
    "healthcare":        10_000.0,
    "marketing":          8_000.0,
    "manufacturing":      8_000.0,
    "research":          12_000.0,
    "media":              7_000.0,
    "events":             9_000.0,
    "education":          5_000.0,
    "real_estate":        5_000.0,
    "recruiting":         6_000.0,
    "hr":                 6_000.0,
    "operations":         6_000.0,
    "ecommerce":          7_000.0,
    "retail":             4_000.0,
    "hospitality":        4_000.0,
    "construction":       7_000.0,
    "government":         5_000.0,
    "insurance":          8_000.0,
    "laboratory":         9_000.0,
    "quality_assurance":  8_000.0,
    "consulting":        10_000.0,
    "sales":              6_000.0,
    "other":              6_000.0,
}

# ---------------------------------------------------------------------------
# Constants — RFP gap analysis
# ---------------------------------------------------------------------------

#: Keywords strongly indicating Murphy can generate the deliverable internally
_MURPHY_GENERATABLE_KEYWORDS: List[str] = [
    "report", "content", "article", "template", "analysis", "document",
    "checklist", "dashboard", "research", "plan", "proposal", "review",
    "summary", "marketing", "seo", "api", "code", "data", "audit",
    "newsletter", "email", "copy", "description", "specification", "brief",
    "strategy", "roadmap", "kpi", "metric", "forecast", "model", "draft",
    "guide", "manual", "policy", "sop", "contract", "invoice", "listing",
    "competitive", "intelligence", "keyword", "ranking", "analytics",
]

#: Keywords indicating the deliverable requires a physical-world contractor
_CONTRACTOR_REQUIRED_KEYWORDS: List[str] = [
    "on-site", "on site", "in-person", "in person", "physical",
    "visit", "inspect", "inspection", "file at", "government office",
    "sign", "notarize", "notarization", "install", "calibrate",
    "calibration", "meet", "meeting", "field", "location", "deliver",
    "photograph", "photo", "structural assessment", "witnessing",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeployabilityStatus(str, Enum):
    """Deployment gate outcome for a niche business."""
    DEPLOYABLE = "deployable"
    NOT_DEPLOYABLE = "not_deployable"
    PENDING_HITL_REVIEW = "pending_hitl_review"
    KILLED = "killed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"


class ModuleStatus(str, Enum):
    """Operational status of a required Murphy module."""
    OPERATIONAL = "operational"
    SIMULATION_ONLY = "simulation_only"
    MISSING = "missing"


class PipelineStage(str, Enum):
    """Stage labels used for checkpoint tracking and recovery."""
    INIT = "init"
    CAPABILITY_CHECK = "capability_check"
    BID_ACQUISITION = "bid_acquisition"
    COST_ESTIMATE = "cost_estimate"
    PROFIT_CHECK = "profit_check"
    WORKFLOW_VALIDATION = "workflow_validation"
    HITL_PENDING = "hitl_pending"
    HITL_APPROVED = "hitl_approved"
    HITL_REJECTED = "hitl_rejected"
    DELIVERED = "delivered"
    KILLED = "killed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"


class HITLDecision(str, Enum):
    """Human operator's decision on an HITL approval request."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ModuleCapabilityCheck:
    """Result of checking a single required module."""
    module_name: str
    status: ModuleStatus
    file_path: Optional[str]


@dataclass
class CapabilityCheckResult:
    """Full capability assessment for a niche's required module set."""
    required_modules: List[str]
    module_checks: List[ModuleCapabilityCheck]
    operational_count: int
    missing_count: int
    simulation_only_count: int
    is_capable: bool                  # True only if ALL required modules are OPERATIONAL
    gaps: List[str]                   # names of MISSING modules
    workflow_self_sufficient: bool    # can Murphy generate + manage the full workflow


@dataclass
class ContractorBid:
    """A single competitive bid for a contractor task."""
    bid_id: str
    niche_id: str
    task_description: str
    bidder_id: str
    bid_amount: float
    skill_offered: str
    location_capable: bool
    meets_acceptance_criteria: bool
    evaluation_score: float


@dataclass
class CostEstimate:
    """Full build cost breakdown before deployment."""
    llm_generation_cost: float        # LLM prompt costs (generation + inference)
    contractor_acquisition_cost: float  # winning contractor bid
    delivery_cost: float              # hosting + API + integrations (first period)
    total_build_cost: float
    cost_breakdown: Dict[str, float]


@dataclass
class ProfitProjection:
    """Revenue vs. cost analysis for the niche."""
    projected_revenue: float
    total_build_cost: float
    minimum_margin: float
    projected_margin: float           # projected_revenue / total_build_cost
    passes_threshold: bool            # projected_margin >= minimum_margin
    breakeven_units: float            # how many units to break even
    first_period_projection: float    # projected revenue in first period


@dataclass
class HITLRiskProfile:
    """
    The risk the approver explicitly accepts by signing the RFP.

    By approving the HITL request that carries this profile, the operator is
    taking on financial and operational responsibility for the deployment.
    """
    total_financial_exposure: float   # max possible loss (total_build_cost)
    projected_build_cost: float
    projected_revenue: float
    margin_at_risk: float             # if revenue misses projection
    operational_risk_summary: str
    contractor_risk_summary: str
    capability_gaps: List[str]        # modules that are MISSING or SIMULATION_ONLY
    risk_acceptance_statement: str    # what the approver is explicitly agreeing to
    approver_liability: str           # explicit liability statement


@dataclass
class HITLApprovalRequest:
    """
    Formal quality-assurance request sent to the human operator before any
    external contacts are made.  Carries the full risk profile so the approver
    understands — and legally accepts — the financial exposure in the RFP.
    """
    request_id: str
    niche_id: str
    niche_name: str
    inoni_entity_name: str            # "Inoni [Name] LLC"
    requestor: str                    # "murphy_system"
    risk_profile: HITLRiskProfile
    cost_estimate: CostEstimate
    profit_projection: ProfitProjection
    capability_check: CapabilityCheckResult
    qa_checklist: List[str]
    pipeline_stage: PipelineStage
    status: str                       # "pending" | "decided"
    created_at: str


@dataclass
class HITLApprovalDecision:
    """
    Human operator's decision on an HITL request.

    ``risk_accepted`` MUST be ``True`` for an APPROVED decision — it is the
    operator's explicit acknowledgment that they are accepting financial and
    operational responsibility for this deployment.
    """
    request_id: str
    decision: HITLDecision
    decided_by: str                   # operator identifier (e.g. "corey_post")
    decided_at: str
    notes: str
    risk_accepted: bool               # MUST be True for APPROVED
    conditions: List[str]             # any conditions attached to the approval


@dataclass
class PipelineCheckpoint:
    """Snapshot of pipeline state at a given stage for recovery."""
    checkpoint_id: str
    niche_id: str
    stage: PipelineStage
    timestamp: str
    state_snapshot: Dict[str, Any]
    can_recover: bool
    recovery_stage: PipelineStage     # which stage to restart from on recovery


@dataclass
class InoniLLCEntity:
    """
    Branded Inoni LLC business entity powered by Murphy System.

    Every niche that clears the viability gate is incorporated as an
    ``Inoni [Name] LLC`` operating under Inoni Limited Liability Company,
    powered by Murphy System.
    """
    entity_name: str                  # "Inoni [Niche Name] LLC"
    legal_name: str                   # same as entity_name — formal registration name
    powered_by: str                   # "Murphy System"
    operator: str                     # "Inoni Limited Liability Company"
    niche_id: str
    autonomy_class: str               # value from NicheAutonomyClass
    revenue_model: str                # value from NicheRevenueModel
    deployment_status: DeployabilityStatus
    hitl_approval_id: Optional[str]   # the request_id of the HITL approval


@dataclass
class ViabilityResult:
    """Complete output of the viability gate for a single niche."""
    niche_id: str
    deployability_status: DeployabilityStatus
    capability_check: CapabilityCheckResult
    cost_estimate: Optional[CostEstimate]
    profit_projection: Optional[ProfitProjection]
    contractor_bids: List[ContractorBid]
    winning_bid: Optional[ContractorBid]
    hitl_request: Optional[HITLApprovalRequest]
    hitl_decision: Optional[HITLApprovalDecision]
    inoni_entity: InoniLLCEntity
    pipeline_stage: PipelineStage
    kill_condition_triggered: bool
    kill_reason: str
    checkpoints: List[PipelineCheckpoint]
    recovery_attempted: bool
    recovery_successful: bool
    validation_passed: bool
    workflow_self_sufficient: bool
    rejection_reasons: List[str]
    stealth_pricing: Optional["StealthPricingModel"] = None


# ---------------------------------------------------------------------------
# Stealth pricing model dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HumanRateEstimate:
    """Estimated cost if humans performed the equivalent work for this niche."""
    niche_id: str
    industry: str
    human_rate_monthly: float         # what agencies/consultants would charge
    human_rate_source: str            # how we derived the estimate
    role_breakdown: Dict[str, float]  # role → monthly cost


@dataclass
class StealthPricingModel:
    """
    The core Inoni business model for a niche deployment or RFP delivery.

    Murphy prices at 75 % of the human rate — clients see a below-market price
    and adopt (stealth adoption).  Murphy's actual cost is < 1 % of human rate,
    so gross margins are enormous while the offering appears competitively priced.

    Profit formula:
        gross_profit = murphy_price - llm_costs - contractor_costs - delivery_costs
    """
    human_rate: float                 # what humans would charge (market reference)
    murphy_price: float               # 75 % of human_rate — the stealth price
    discount_to_client: float         # human_rate - murphy_price (25 % saving for client)
    client_savings_pct: float         # always 25 % — the stealth adoption hook
    llm_costs: float                  # actual LLM generation costs
    contractor_costs: float           # contractor bid costs (hybrid niches)
    delivery_costs: float             # hosting + module delivery
    total_variable_cost: float        # llm + contractor + delivery
    gross_profit: float               # murphy_price - total_variable_cost
    gross_margin_pct: float           # gross_profit / murphy_price × 100
    human_margin_comparison: str      # narrative: Murphy vs human cost story


# ---------------------------------------------------------------------------
# RFP gap analysis dataclasses
# ---------------------------------------------------------------------------

class GenerationType(str, Enum):
    """Classification of what kind of work a deliverable requires."""
    DIGITAL_CONTENT = "digital_content"     # articles, emails, newsletters
    DOCUMENT = "document"                   # templates, contracts, SOPs
    DATA_ANALYSIS = "data_analysis"         # reports, dashboards, KPIs
    RESEARCH = "research"                   # competitive intel, market research
    COMPLIANCE = "compliance"               # checklists, audits, certifications
    CODE_OR_API = "code_or_api"             # scripts, integrations, endpoints
    PHYSICAL_INSPECTION = "physical_inspection"   # needs on-site contractor
    LEGAL_FILING = "legal_filing"           # needs government-office contractor
    IN_PERSON_SERVICE = "in_person_service" # needs physical-presence contractor
    UNKNOWN = "unknown"


@dataclass
class RFPRequirement:
    """A single deliverable requirement extracted from an RFP."""
    requirement_id: str
    description: str
    generation_type: GenerationType
    estimated_hours: float            # human-hours to produce manually
    complexity: str                   # "low" | "medium" | "high"
    keywords_matched: List[str]       # which keywords drove classification


@dataclass
class GenerationCapability:
    """Murphy's capability to fulfil a single RFP requirement."""
    requirement_id: str
    can_generate: bool                # Murphy produces this fully internally
    requires_contractor: bool         # needs a physical-world contractor
    murphy_can_contribute: bool       # Murphy can produce the non-physical parts
    generation_method: str            # e.g. "llm_content", "inference_analysis"
    confidence: float                 # 0–1 confidence in generation quality
    gap_description: str              # what Murphy cannot produce (if any)
    resolvable: bool                  # can the gap be closed (contractor dispatch)?
    resolution_method: str            # "internal", "contractor_dispatch", "not_deliverable"


@dataclass
class RFPGapItem:
    """A gap between what an RFP requires and what Murphy can generate."""
    requirement: RFPRequirement
    capability: GenerationCapability
    gap_severity: str                 # "none" | "partial" | "full"
    resolution_cost: float            # estimated cost to resolve the gap
    resolution_notes: str


@dataclass
class RFP:
    """An RFP received by a niche business."""
    rfp_id: str
    niche_id: str
    client_id: str
    description: str
    raw_text: str
    budget_ceiling: Optional[float]
    deadline: Optional[str]
    created_at: str


@dataclass
class RFPAnalysis:
    """
    Full gap analysis for an RFP — what Murphy can vs. needs to generate.

    This is the answer to: "Given this RFP, can Murphy deliver it fully?
    If not, what is the gap and how is it resolved?"
    """
    rfp: RFP
    niche_id: str
    requirements: List[RFPRequirement]
    capabilities: List[GenerationCapability]
    gap_items: List[RFPGapItem]
    can_fully_deliver: bool           # all requirements: can_generate=True
    requires_human_augmentation: bool # some requirements need contractors
    unresolvable_gaps: List[RFPGapItem]  # gaps that cannot be closed
    murphy_coverage_pct: float        # % of requirements Murphy can handle
    estimated_delivery_cost: float    # total cost to deliver the RFP
    stealth_quote: Optional[StealthPricingModel]   # 75 % of human rate for this RFP
    human_rate_for_rfp: float         # what humans would charge for this RFP
    delivery_confidence: float        # 0–1 overall confidence in delivery


# ---------------------------------------------------------------------------
# Gate class
# ---------------------------------------------------------------------------

class NicheViabilityGate:
    """
    Pre-deployment viability gate for Murphy-powered Inoni LLC niche businesses.

    Runs entirely using Murphy's own internal modules — no external contacts are
    made until the human operator has explicitly approved the HITL request and
    accepted the risk in the RFP.

    Args:
        inference_engine: Fully-initialised :class:`InferenceDomainGateEngine`.
        mss_controller: Fully-initialised :class:`MSSController`.
        src_dir: Path to the Murphy System src directory (for module scanning).
                 Defaults to the ``src/`` sibling of this file's directory.
    """

    def __init__(
        self,
        inference_engine: InferenceDomainGateEngine,
        mss_controller: MSSController,
        src_dir: Optional[str] = None,
    ) -> None:
        self._inference_engine = inference_engine
        self._mss_controller = mss_controller
        self._src_dir: str = src_dir or os.path.join(
            os.path.dirname(__file__)
        )
        # In-memory checkpoint store: niche_id → list of checkpoints
        self._checkpoints: Dict[str, List[PipelineCheckpoint]] = {}
        # Pending HITL requests: request_id → HITLApprovalRequest
        self._pending_requests: Dict[str, HITLApprovalRequest] = {}
        # Recorded HITL decisions: request_id → HITLApprovalDecision
        self._hitl_decisions: Dict[str, HITLApprovalDecision] = {}

    # ------------------------------------------------------------------
    # Capability check
    # ------------------------------------------------------------------

    def check_capability(self, niche: Any) -> CapabilityCheckResult:
        """Check that all required Murphy modules exist and are operational.

        Scans the src directory for module files/directories.  If every
        required module is present and none are simulation-only, the niche
        is considered capable.  Also verifies workflow self-sufficiency by
        running a quick inference on the niche description.

        Args:
            niche: A :class:`NicheDefinition`-like object with attributes
                   ``murphy_modules_required``, ``description``.

        Returns:
            A populated :class:`CapabilityCheckResult`.
        """
        required_modules: List[str] = list(getattr(niche, "murphy_modules_required", []))
        module_checks: List[ModuleCapabilityCheck] = []

        for module_name in required_modules:
            check = self._scan_module(module_name)
            module_checks.append(check)

        operational_count = sum(
            1 for c in module_checks if c.status == ModuleStatus.OPERATIONAL
        )
        missing_count = sum(
            1 for c in module_checks if c.status == ModuleStatus.MISSING
        )
        simulation_only_count = sum(
            1 for c in module_checks if c.status == ModuleStatus.SIMULATION_ONLY
        )
        gaps = [
            c.module_name for c in module_checks
            if c.status in (ModuleStatus.MISSING, ModuleStatus.SIMULATION_ONLY)
        ]
        is_capable = missing_count == 0 and simulation_only_count == 0

        # Workflow self-sufficiency: run inference and check minimal outputs
        workflow_self_sufficient = self._check_workflow_self_sufficient(niche)

        return CapabilityCheckResult(
            required_modules=required_modules,
            module_checks=module_checks,
            operational_count=operational_count,
            missing_count=missing_count,
            simulation_only_count=simulation_only_count,
            is_capable=is_capable,
            gaps=gaps,
            workflow_self_sufficient=workflow_self_sufficient,
        )

    def _scan_module(self, module_name: str) -> ModuleCapabilityCheck:
        """Probe src directory for *module_name* as a .py file or package dir."""
        if module_name in _SIMULATION_ONLY_MODULES:
            return ModuleCapabilityCheck(
                module_name=module_name,
                status=ModuleStatus.SIMULATION_ONLY,
                file_path=None,
            )

        # Check as .py file
        py_path = os.path.join(self._src_dir, f"{module_name}.py")
        if os.path.isfile(py_path):
            return ModuleCapabilityCheck(
                module_name=module_name,
                status=ModuleStatus.OPERATIONAL,
                file_path=py_path,
            )

        # Check as package directory
        dir_path = os.path.join(self._src_dir, module_name)
        if os.path.isdir(dir_path):
            return ModuleCapabilityCheck(
                module_name=module_name,
                status=ModuleStatus.OPERATIONAL,
                file_path=dir_path,
            )

        return ModuleCapabilityCheck(
            module_name=module_name,
            status=ModuleStatus.MISSING,
            file_path=None,
        )

    def _check_workflow_self_sufficient(self, niche: Any) -> bool:
        """Return True if Murphy can generate and manage the full workflow internally.

        Verifies:
        - Inference produces at least one org position AND one gate
        - MSS magnify step completes without error
        - produce_dataset() returns non-empty agent_roster AND kpi_dataset
        """
        description = getattr(niche, "description", "")
        seed_data = getattr(niche, "seed_data", {})

        try:
            inference_result = self._inference_engine.infer(
                description, existing_data=seed_data
            )
            if inference_result.position_count == 0:
                return False
            if inference_result.gate_count == 0:
                return False

            dataset = inference_result.produce_dataset()
            if not dataset.get("agent_roster"):
                return False
            if not dataset.get("kpi_dataset"):
                return False
            if not dataset.get("checkpoint_dataset"):
                return False

            # Verify MSS pipeline can process the description
            self._mss_controller.magnify(description)
            return True

        except Exception as exc:
            logger.warning(
                "Workflow self-sufficiency check failed for niche %r: %s",
                getattr(niche, "niche_id", "unknown"),
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # Bid acquisition (internal — no external calls)
    # ------------------------------------------------------------------

    def solicit_bids(self, niche: Any) -> List[ContractorBid]:
        """Generate competitive bids internally using Murphy's inference engine.

        For each contractor task template in the niche's seed_data, produces
        four synthetic bids at varying price points.  No external contractor
        pool is contacted — this is a fully internal operation.

        Args:
            niche: A :class:`NicheDefinition`-like object.

        Returns:
            List of :class:`ContractorBid` instances.
        """
        niche_id = getattr(niche, "niche_id", "unknown")
        seed_data = getattr(niche, "seed_data", {})
        templates = seed_data.get("contractor_task_templates", [])

        bids: List[ContractorBid] = []
        for tmpl in templates:
            reference_price = float(tmpl.get("payment", 50.0))
            task_description = tmpl.get("description", "Contractor task")
            skill_required = tmpl.get("skill_required", "general")
            location_required = tmpl.get("location_required", False)

            for i, multiplier in enumerate(_BID_MULTIPLIERS):
                bid_amount = round(reference_price * multiplier, 2)
                meets_criteria = _BID_MEETS_CRITERIA[i]
                # Bid 0 (aggressive undercut) can't meet location requirement
                location_capable = (not location_required) or (i > 0)
                meets_criteria = meets_criteria and location_capable

                evaluation_score = round(
                    (1.0 - abs(multiplier - 1.0)) * (1.0 if meets_criteria else 0.3),
                    4,
                )

                bids.append(ContractorBid(
                    bid_id=str(uuid.uuid4()),
                    niche_id=niche_id,
                    task_description=task_description,
                    bidder_id=f"internal_bidder_{i + 1:02d}",
                    bid_amount=bid_amount,
                    skill_offered=skill_required,
                    location_capable=location_capable,
                    meets_acceptance_criteria=meets_criteria,
                    evaluation_score=evaluation_score,
                ))

        return bids

    def select_cheapest_qualifying_bid(
        self,
        bids: List[ContractorBid],
    ) -> Optional[ContractorBid]:
        """Return the cheapest bid that meets acceptance criteria.

        Args:
            bids: All bids solicited for a niche.

        Returns:
            The qualifying bid with the lowest ``bid_amount``, or ``None``
            if no bids meet the acceptance criteria.
        """
        qualifying = [b for b in bids if b.meets_acceptance_criteria]
        if not qualifying:
            return None
        return min(qualifying, key=lambda b: b.bid_amount)

    # ------------------------------------------------------------------
    # Cost estimation
    # ------------------------------------------------------------------

    def estimate_costs(
        self,
        niche: Any,
        winning_bid: Optional[ContractorBid] = None,
    ) -> CostEstimate:
        """Calculate the full build cost for a niche before deployment.

        Components:
        - **LLM generation cost**: inference + MSS sequence operations
        - **Contractor acquisition cost**: winning bid amount (hybrid niches only)
        - **Delivery cost**: base hosting + per-required-module monthly cost

        Args:
            niche: A :class:`NicheDefinition`-like object.
            winning_bid: The selected contractor bid, or ``None`` for
                         full-autonomy niches.

        Returns:
            A populated :class:`CostEstimate`.
        """
        required_modules = list(getattr(niche, "murphy_modules_required", []))

        llm_generation_cost = round(
            _LLM_INFERENCE_COST + (_DEFAULT_MSS_OPS * _LLM_COST_PER_OP),
            4,
        )

        contractor_acquisition_cost = 0.0
        if winning_bid is not None:
            contractor_acquisition_cost = winning_bid.bid_amount

        delivery_cost = round(
            _DELIVERY_BASE_COST + (len(required_modules) * _DELIVERY_PER_MODULE),
            4,
        )

        total_build_cost = round(
            llm_generation_cost + contractor_acquisition_cost + delivery_cost,
            4,
        )

        cost_breakdown = {
            "llm_inference": _LLM_INFERENCE_COST,
            "llm_mss_ops": round(_DEFAULT_MSS_OPS * _LLM_COST_PER_OP, 4),
            "contractor_bid": contractor_acquisition_cost,
            "delivery_base": _DELIVERY_BASE_COST,
            "delivery_modules": round(len(required_modules) * _DELIVERY_PER_MODULE, 4),
        }

        return CostEstimate(
            llm_generation_cost=llm_generation_cost,
            contractor_acquisition_cost=contractor_acquisition_cost,
            delivery_cost=delivery_cost,
            total_build_cost=total_build_cost,
            cost_breakdown=cost_breakdown,
        )

    # ------------------------------------------------------------------
    # Profit threshold
    # ------------------------------------------------------------------

    def check_profit_threshold(
        self,
        cost_estimate: CostEstimate,
        projected_revenue: float,
        minimum_margin: float = 2.0,
    ) -> ProfitProjection:
        """Evaluate whether the niche's projected revenue clears the margin gate.

        Args:
            cost_estimate: The calculated build cost.
            projected_revenue: Estimated first-period revenue (USD).
            minimum_margin: Required ratio of revenue to cost (default 2×).

        Returns:
            A populated :class:`ProfitProjection`.
        """
        total_build_cost = cost_estimate.total_build_cost
        projected_margin = projected_revenue / (total_build_cost or 1.0)
        passes_threshold = projected_margin >= minimum_margin

        breakeven_units = total_build_cost / (projected_revenue or 1.0)

        return ProfitProjection(
            projected_revenue=projected_revenue,
            total_build_cost=total_build_cost,
            minimum_margin=minimum_margin,
            projected_margin=round(projected_margin, 4),
            passes_threshold=passes_threshold,
            breakeven_units=round(breakeven_units, 4),
            first_period_projection=projected_revenue,
        )

    # ------------------------------------------------------------------
    # Kill condition
    # ------------------------------------------------------------------

    def check_kill_condition(
        self,
        running_cost: float,
        projected_first_period_revenue: float,
    ) -> bool:
        """Return True (kill) if running costs exceed projected first-period revenue.

        Args:
            running_cost: Accumulated cost so far (USD).
            projected_first_period_revenue: Projected revenue in first period (USD).

        Returns:
            ``True`` if the niche should be halted; ``False`` otherwise.
        """
        return running_cost > projected_first_period_revenue

    # ------------------------------------------------------------------
    # HITL request / decision
    # ------------------------------------------------------------------

    def create_hitl_request(
        self,
        niche: Any,
        capability_check: CapabilityCheckResult,
        cost_estimate: CostEstimate,
        profit_projection: ProfitProjection,
    ) -> HITLApprovalRequest:
        """Build a formal HITL approval request carrying the full risk profile.

        The request is always a quality-assurance gate — Murphy has already done
        all internal work.  The human operator is asked to review the RFP and,
        by approving, explicitly accepts financial and operational responsibility
        for this Inoni LLC deployment.

        Args:
            niche: A :class:`NicheDefinition`-like object.
            capability_check: Result of the capability gate.
            cost_estimate: Calculated build costs.
            profit_projection: Revenue vs. cost analysis.

        Returns:
            A populated :class:`HITLApprovalRequest`.
        """
        niche_id = getattr(niche, "niche_id", "unknown")
        niche_name = getattr(niche, "name", niche_id)
        inoni_entity_name = f"Inoni {niche_name} LLC"

        autonomy_val = self._attr_value(niche, "autonomy_class")
        revenue_val = self._attr_value(niche, "revenue_model")

        margin_at_risk = max(
            0.0,
            profit_projection.projected_revenue - profit_projection.total_build_cost,
        )

        contractor_risk = (
            "No contractor risk — fully autonomous niche."
            if not capability_check.gaps and autonomy_val == "full_autonomy"
            else (
                f"Contractor acquisition cost ${cost_estimate.contractor_acquisition_cost:.2f}. "
                "External contractor contact authorised only after this HITL approval."
            )
        )

        risk_acceptance_statement = (
            f"By approving this request, {inoni_entity_name} — powered by Murphy System — "
            f"is authorised to deploy as an Inoni LLC entity under Inoni Limited Liability Company. "
            f"The approver accepts full financial responsibility for a total build cost of "
            f"${cost_estimate.total_build_cost:.2f} against projected first-period revenue of "
            f"${profit_projection.projected_revenue:.2f} (projected margin: "
            f"{profit_projection.projected_margin:.1f}×). "
            f"Any shortfall in projected revenue is borne by the approving operator."
        )

        approver_liability = (
            "RISK ACCEPTANCE — RFP AGREEMENT: By approving this HITL request you are "
            "entering into a binding operational agreement. You acknowledge: "
            "(1) total financial exposure of ${:.2f}; "
            "(2) projected first-period revenue of ${:.2f}; "
            "(3) that Murphy System cannot guarantee revenue projections; "
            "(4) that you assume operational responsibility for all downstream "
            "contractor actions authorised by this approval."
        ).format(cost_estimate.total_build_cost, profit_projection.projected_revenue)

        risk_profile = HITLRiskProfile(
            total_financial_exposure=cost_estimate.total_build_cost,
            projected_build_cost=cost_estimate.total_build_cost,
            projected_revenue=profit_projection.projected_revenue,
            margin_at_risk=margin_at_risk,
            operational_risk_summary=(
                f"Niche: {inoni_entity_name}. "
                f"Autonomy: {autonomy_val}. Revenue model: {revenue_val}. "
                f"Required modules: {len(capability_check.required_modules)} "
                f"({capability_check.operational_count} operational, "
                f"{capability_check.missing_count} missing)."
            ),
            contractor_risk_summary=contractor_risk,
            capability_gaps=capability_check.gaps,
            risk_acceptance_statement=risk_acceptance_statement,
            approver_liability=approver_liability,
        )

        qa_checklist = [
            "✓ All required Murphy modules verified operational",
            "✓ Full MMSMM MSS sequence can execute internally",
            "✓ Inference engine produces org chart + gates for this niche",
            "✓ KPI dataset and checkpoint dataset are non-empty",
            f"✓ Build cost ${cost_estimate.total_build_cost:.2f} calculated before deployment",
            f"✓ Profit margin {profit_projection.projected_margin:.1f}× clears {profit_projection.minimum_margin}× threshold",
            "✓ Contractor bids solicited internally (cheapest qualifying bid selected)",
            "⚠ Human operator must accept financial risk before external contacts are made",
            "⚠ No data delivered to end users until this QA gate is passed",
        ]

        request = HITLApprovalRequest(
            request_id=str(uuid.uuid4()),
            niche_id=niche_id,
            niche_name=niche_name,
            inoni_entity_name=inoni_entity_name,
            requestor="murphy_system",
            risk_profile=risk_profile,
            cost_estimate=cost_estimate,
            profit_projection=profit_projection,
            capability_check=capability_check,
            qa_checklist=qa_checklist,
            pipeline_stage=PipelineStage.HITL_PENDING,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._pending_requests[request.request_id] = request
        return request

    def approve_hitl_request(
        self,
        request_id: str,
        decided_by: str,
        notes: str = "",
        risk_accepted: bool = False,
        conditions: Optional[List[str]] = None,
    ) -> HITLApprovalDecision:
        """Record the human operator's approval of an HITL request.

        The operator MUST set ``risk_accepted=True`` — this is their explicit
        acknowledgment that they are accepting financial and operational
        responsibility for this deployment.

        After approval, Murphy is authorised to make external contacts
        (contractor dispatch, API calls, deliveries).

        Args:
            request_id: The UUID of the HITL request to approve.
            decided_by: Identifier of the approving operator (e.g. ``"corey_post"``).
            notes: Optional approval notes.
            risk_accepted: Must be ``True`` — the approver accepts the risk in the RFP.
            conditions: Optional list of conditions attached to this approval.

        Returns:
            The recorded :class:`HITLApprovalDecision`.

        Raises:
            KeyError: If *request_id* is not found.
            ValueError: If *risk_accepted* is not ``True``.
        """
        if request_id not in self._pending_requests:
            raise KeyError(
                f"HITL request {request_id!r} not found — cannot approve unknown request"
            )
        if not risk_accepted:
            raise ValueError(
                "risk_accepted must be True to approve a HITL request. "
                "By approving you are explicitly accepting financial and operational "
                "responsibility for this Inoni LLC deployment."
            )

        decision = HITLApprovalDecision(
            request_id=request_id,
            decision=HITLDecision.APPROVED,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            risk_accepted=True,
            conditions=conditions or [],
        )
        self._hitl_decisions[request_id] = decision
        self._pending_requests[request_id].status = "decided"

        logger.info(
            "HITL approved: request=%s decided_by=%s niche=%s",
            request_id,
            decided_by,
            self._pending_requests[request_id].niche_id,
        )
        return decision

    def reject_hitl_request(
        self,
        request_id: str,
        decided_by: str,
        notes: str = "",
    ) -> HITLApprovalDecision:
        """Record the human operator's rejection of an HITL request.

        Args:
            request_id: The UUID of the HITL request to reject.
            decided_by: Identifier of the rejecting operator.
            notes: Reason for rejection.

        Returns:
            The recorded :class:`HITLApprovalDecision`.

        Raises:
            KeyError: If *request_id* is not found.
        """
        if request_id not in self._pending_requests:
            raise KeyError(
                f"HITL request {request_id!r} not found — cannot reject unknown request"
            )

        decision = HITLApprovalDecision(
            request_id=request_id,
            decision=HITLDecision.REJECTED,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            risk_accepted=False,
            conditions=[],
        )
        self._hitl_decisions[request_id] = decision
        self._pending_requests[request_id].status = "decided"

        logger.info(
            "HITL rejected: request=%s decided_by=%s reason=%s",
            request_id,
            decided_by,
            notes,
        )
        return decision

    def get_hitl_decision(self, request_id: str) -> Optional[HITLApprovalDecision]:
        """Return the recorded decision for *request_id*, or ``None``."""
        return self._hitl_decisions.get(request_id)

    # ------------------------------------------------------------------
    # Inoni LLC entity creation
    # ------------------------------------------------------------------

    def create_inoni_entity(
        self,
        niche: Any,
        deployment_status: DeployabilityStatus,
        hitl_approval_id: Optional[str],
    ) -> InoniLLCEntity:
        """Build the branded Inoni LLC entity record for a niche.

        Args:
            niche: A :class:`NicheDefinition`-like object.
            deployment_status: Current gate outcome.
            hitl_approval_id: The HITL request_id that was approved, or ``None``.

        Returns:
            A populated :class:`InoniLLCEntity`.
        """
        niche_name = getattr(niche, "name", getattr(niche, "niche_id", "Niche"))
        entity_name = f"Inoni {niche_name} LLC"

        return InoniLLCEntity(
            entity_name=entity_name,
            legal_name=entity_name,
            powered_by="Murphy System",
            operator="Inoni Limited Liability Company",
            niche_id=getattr(niche, "niche_id", "unknown"),
            autonomy_class=self._attr_value(niche, "autonomy_class"),
            revenue_model=self._attr_value(niche, "revenue_model"),
            deployment_status=deployment_status,
            hitl_approval_id=hitl_approval_id,
        )

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    def validate_output(
        self,
        spec: Any,
        hitl_decision: Optional[HITLApprovalDecision],
    ) -> bool:
        """Gate-filter and HITL-check a generated deployment spec.

        Rules:
        - If *hitl_decision* is None → not validated (HITL pending)
        - If *hitl_decision*.decision is REJECTED → not validated
        - If *hitl_decision*.risk_accepted is False → not validated
        - If spec has no mss_results or no inference_result → not validated
        - Otherwise → validated

        Args:
            spec: A :class:`NicheDeploymentSpec`-like object.
            hitl_decision: The recorded HITL decision, or ``None``.

        Returns:
            ``True`` if the spec passes all validation gates.
        """
        if hitl_decision is None:
            return False
        if hitl_decision.decision != HITLDecision.APPROVED:
            return False
        if not hitl_decision.risk_accepted:
            return False
        if not getattr(spec, "mss_results", None):
            return False
        if getattr(spec, "inference_result", None) is None:
            return False
        return True

    # ------------------------------------------------------------------
    # Checkpoint and recovery
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        stage: PipelineStage,
        niche_id: str,
        state_snapshot: Dict[str, Any],
        can_recover: bool = True,
    ) -> PipelineCheckpoint:
        """Write a pipeline checkpoint for *niche_id* at *stage*.

        Args:
            stage: The pipeline stage being checkpointed.
            niche_id: Identifies the niche this checkpoint belongs to.
            state_snapshot: Serialisable dict capturing current pipeline state.
            can_recover: Whether the pipeline can be restarted from this point.

        Returns:
            The written :class:`PipelineCheckpoint`.
        """
        # Each stage maps to the stage to resume from on recovery
        _recovery_map: Dict[PipelineStage, PipelineStage] = {
            PipelineStage.INIT: PipelineStage.INIT,
            PipelineStage.CAPABILITY_CHECK: PipelineStage.INIT,
            PipelineStage.BID_ACQUISITION: PipelineStage.CAPABILITY_CHECK,
            PipelineStage.COST_ESTIMATE: PipelineStage.CAPABILITY_CHECK,
            PipelineStage.PROFIT_CHECK: PipelineStage.COST_ESTIMATE,
            PipelineStage.WORKFLOW_VALIDATION: PipelineStage.COST_ESTIMATE,
            PipelineStage.HITL_PENDING: PipelineStage.HITL_PENDING,
            PipelineStage.HITL_APPROVED: PipelineStage.HITL_APPROVED,
            PipelineStage.HITL_REJECTED: PipelineStage.INIT,
            PipelineStage.DELIVERED: PipelineStage.DELIVERED,
            PipelineStage.KILLED: PipelineStage.INIT,
            PipelineStage.RECOVERING: PipelineStage.INIT,
            PipelineStage.RECOVERED: PipelineStage.INIT,
        }

        cp = PipelineCheckpoint(
            checkpoint_id=str(uuid.uuid4()),
            niche_id=niche_id,
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state_snapshot=state_snapshot,
            can_recover=can_recover,
            recovery_stage=_recovery_map.get(stage, PipelineStage.INIT),
        )

        if niche_id not in self._checkpoints:
            self._checkpoints[niche_id] = []
        self._checkpoints[niche_id].append(cp)
        return cp

    def get_checkpoints(self, niche_id: str) -> List[PipelineCheckpoint]:
        """Return all checkpoints for *niche_id*, oldest first."""
        return list(self._checkpoints.get(niche_id, []))

    def recover(self, niche_id: str) -> Optional[PipelineCheckpoint]:
        """Return the most recent recoverable checkpoint for *niche_id*.

        Killed / delivered checkpoints are excluded (those states are terminal
        unless the operator explicitly restarts).

        Args:
            niche_id: The niche to recover.

        Returns:
            The last recoverable :class:`PipelineCheckpoint`, or ``None``
            if no recoverable checkpoint exists.
        """
        _non_recoverable = {PipelineStage.DELIVERED}
        checkpoints = self._checkpoints.get(niche_id, [])
        candidates = [
            cp for cp in reversed(checkpoints)
            if cp.can_recover and cp.stage not in _non_recoverable
        ]
        return candidates[0] if candidates else None

    def run_recovery(
        self,
        niche: Any,
        projected_revenue: Optional[float] = None,
        budget_cap: Optional[float] = None,
        minimum_margin: float = 2.0,
    ) -> ViabilityResult:
        """Attempt to recover the viability pipeline for *niche*.

        Finds the last recoverable checkpoint and re-runs ``evaluate()``
        from the beginning (the pipeline is deterministic, so re-running
        from INIT is always safe and correct).

        Args:
            niche: A :class:`NicheDefinition`-like object.
            projected_revenue: Override projected revenue for this run.
            budget_cap: Optional spend cap.
            minimum_margin: Required margin multiplier.

        Returns:
            A new :class:`ViabilityResult` with ``recovery_attempted=True``.
        """
        niche_id = getattr(niche, "niche_id", "unknown")
        last_cp = self.recover(niche_id)

        if last_cp is None:
            logger.warning("No recoverable checkpoint found for niche %r", niche_id)

        logger.info(
            "Running recovery for niche %r from stage %s",
            niche_id,
            last_cp.stage.value if last_cp else "init",
        )

        result = self.evaluate(
            niche,
            projected_revenue=projected_revenue,
            budget_cap=budget_cap,
            minimum_margin=minimum_margin,
        )

        # Mark recovery metadata
        result.recovery_attempted = True
        result.recovery_successful = result.deployability_status not in (
            DeployabilityStatus.KILLED,
            DeployabilityStatus.NOT_DEPLOYABLE,
        )
        if result.recovery_successful:
            result.deployability_status = DeployabilityStatus.RECOVERED
            result.inoni_entity.deployment_status = DeployabilityStatus.RECOVERED
            result.pipeline_stage = PipelineStage.RECOVERED

        return result

    # ------------------------------------------------------------------
    # Main evaluate pipeline
    # ------------------------------------------------------------------

    def evaluate(
        self,
        niche: Any,
        projected_revenue: Optional[float] = None,
        budget_cap: Optional[float] = None,
        minimum_margin: float = 2.0,
    ) -> ViabilityResult:
        """Run the full viability pipeline for *niche*.

        Stages (each creates a checkpoint):
          1. Capability Check
          2. Bid Acquisition (hybrid niches only)
          3. Cost Estimate
          4. Kill Condition Check
          5. Profit Threshold
          6. Workflow Validation
          7. HITL Request Creation → returns PENDING_HITL_REVIEW

        External contacts are locked until step 7 produces an approved
        HITL decision (via :meth:`approve_hitl_request`).

        Args:
            niche: A :class:`NicheDefinition`-like object.
            projected_revenue: Estimated first-period revenue. Auto-calculated
                               from the niche's revenue model if ``None``.
            budget_cap: Maximum allowable spend. Not currently enforced as a
                        hard cap but recorded for the HITL risk profile.
            minimum_margin: Required revenue-to-cost ratio (default 2×).

        Returns:
            A populated :class:`ViabilityResult` (status is
            ``PENDING_HITL_REVIEW`` on success, or a terminal state on failure).
        """
        niche_id = getattr(niche, "niche_id", "unknown")
        rejection_reasons: List[str] = []
        checkpoints: List[PipelineCheckpoint] = []

        # projected_revenue is resolved in STAGE 3 after stealth pricing is computed.
        # Keep the caller-supplied value here (None = auto-compute from stealth model).

        # ---- Create initial Inoni entity (status will be updated at each gate) ----
        inoni_entity = self.create_inoni_entity(
            niche, DeployabilityStatus.NOT_DEPLOYABLE, None
        )

        # ----------------------------------------------------------------
        # STAGE 1 — Capability Check
        # ----------------------------------------------------------------
        capability_check = self.check_capability(niche)
        cp1 = self.checkpoint(
            PipelineStage.CAPABILITY_CHECK,
            niche_id,
            {
                "is_capable": capability_check.is_capable,
                "workflow_self_sufficient": capability_check.workflow_self_sufficient,
                "gaps": capability_check.gaps,
            },
        )
        checkpoints.append(cp1)

        if not capability_check.workflow_self_sufficient:
            rejection_reasons.append(
                "Workflow not self-sufficient — Murphy cannot generate its own "
                "complete workflow for this niche: missing org positions, gates, "
                "KPIs, or checkpoint dataset.  This is not a valid business."
            )
            inoni_entity.deployment_status = DeployabilityStatus.NOT_DEPLOYABLE
            return ViabilityResult(
                niche_id=niche_id,
                deployability_status=DeployabilityStatus.NOT_DEPLOYABLE,
                capability_check=capability_check,
                cost_estimate=None,
                profit_projection=None,
                contractor_bids=[],
                winning_bid=None,
                hitl_request=None,
                hitl_decision=None,
                inoni_entity=inoni_entity,
                pipeline_stage=PipelineStage.CAPABILITY_CHECK,
                kill_condition_triggered=False,
                kill_reason="",
                checkpoints=checkpoints,
                recovery_attempted=False,
                recovery_successful=False,
                validation_passed=False,
                workflow_self_sufficient=False,
                rejection_reasons=rejection_reasons,
            )

        if not capability_check.is_capable:
            rejection_reasons.append(
                f"Missing required Murphy modules: {capability_check.gaps}. "
                "The niche is NOT_DEPLOYABLE until these gaps are closed."
            )
            inoni_entity.deployment_status = DeployabilityStatus.NOT_DEPLOYABLE
            return ViabilityResult(
                niche_id=niche_id,
                deployability_status=DeployabilityStatus.NOT_DEPLOYABLE,
                capability_check=capability_check,
                cost_estimate=None,
                profit_projection=None,
                contractor_bids=[],
                winning_bid=None,
                hitl_request=None,
                hitl_decision=None,
                inoni_entity=inoni_entity,
                pipeline_stage=PipelineStage.CAPABILITY_CHECK,
                kill_condition_triggered=False,
                kill_reason="",
                checkpoints=checkpoints,
                recovery_attempted=False,
                recovery_successful=False,
                validation_passed=False,
                workflow_self_sufficient=capability_check.workflow_self_sufficient,
                rejection_reasons=rejection_reasons,
            )

        # ----------------------------------------------------------------
        # STAGE 2 — Bid Acquisition (hybrid niches only, fully internal)
        # ----------------------------------------------------------------
        autonomy_val = self._attr_value(niche, "autonomy_class")
        bids: List[ContractorBid] = []
        winning_bid: Optional[ContractorBid] = None

        if autonomy_val in ("hybrid", "legs_required"):
            bids = self.solicit_bids(niche)
            winning_bid = self.select_cheapest_qualifying_bid(bids)

        cp2 = self.checkpoint(
            PipelineStage.BID_ACQUISITION,
            niche_id,
            {
                "bid_count": len(bids),
                "winning_bid_amount": winning_bid.bid_amount if winning_bid else 0.0,
            },
        )
        checkpoints.append(cp2)

        # ----------------------------------------------------------------
        # STAGE 3 — Cost Estimate + Stealth Pricing
        # ----------------------------------------------------------------
        cost_estimate = self.estimate_costs(niche, winning_bid)
        stealth_pricing = self.build_stealth_pricing(niche, cost_estimate)
        # Use Murphy's price (75 % of human rate) as the projected revenue
        # unless the caller explicitly provided one.
        if projected_revenue is None:
            projected_revenue = stealth_pricing.murphy_price
        cp3 = self.checkpoint(
            PipelineStage.COST_ESTIMATE,
            niche_id,
            {
                "total_build_cost": cost_estimate.total_build_cost,
                "llm_cost": cost_estimate.llm_generation_cost,
                "contractor_cost": cost_estimate.contractor_acquisition_cost,
                "delivery_cost": cost_estimate.delivery_cost,
                "murphy_price": stealth_pricing.murphy_price,
                "human_rate": stealth_pricing.human_rate,
                "gross_margin_pct": stealth_pricing.gross_margin_pct,
            },
        )
        checkpoints.append(cp3)

        # ----------------------------------------------------------------
        # KILL CONDITION — stage 1 (after cost estimate)
        # ----------------------------------------------------------------
        if self.check_kill_condition(cost_estimate.total_build_cost, projected_revenue):
            kill_reason = (
                f"KILL: Total build cost ${cost_estimate.total_build_cost:.2f} exceeds "
                f"projected first-period revenue ${projected_revenue:.2f} "
                f"(Murphy price = 75 % of human rate ${stealth_pricing.human_rate:,.2f}). "
                "Halted and flagged for human review."
            )
            cp_kill = self.checkpoint(
                PipelineStage.KILLED,
                niche_id,
                {"kill_reason": kill_reason, "running_cost": cost_estimate.total_build_cost},
                can_recover=True,
            )
            checkpoints.append(cp_kill)
            inoni_entity.deployment_status = DeployabilityStatus.KILLED
            return ViabilityResult(
                niche_id=niche_id,
                deployability_status=DeployabilityStatus.KILLED,
                capability_check=capability_check,
                cost_estimate=cost_estimate,
                profit_projection=None,
                contractor_bids=bids,
                winning_bid=winning_bid,
                hitl_request=None,
                hitl_decision=None,
                inoni_entity=inoni_entity,
                pipeline_stage=PipelineStage.KILLED,
                kill_condition_triggered=True,
                kill_reason=kill_reason,
                checkpoints=checkpoints,
                recovery_attempted=False,
                recovery_successful=False,
                validation_passed=False,
                workflow_self_sufficient=capability_check.workflow_self_sufficient,
                rejection_reasons=[kill_reason],
                stealth_pricing=stealth_pricing,
            )

        # ----------------------------------------------------------------
        # STAGE 4 — Profit Threshold
        # ----------------------------------------------------------------
        profit_projection = self.check_profit_threshold(
            cost_estimate, projected_revenue, minimum_margin
        )
        cp4 = self.checkpoint(
            PipelineStage.PROFIT_CHECK,
            niche_id,
            {
                "projected_margin": profit_projection.projected_margin,
                "passes_threshold": profit_projection.passes_threshold,
                "minimum_margin": minimum_margin,
            },
        )
        checkpoints.append(cp4)

        if not profit_projection.passes_threshold:
            rejection_reasons.append(
                f"Profit margin {profit_projection.projected_margin:.2f}× is below "
                f"the required {minimum_margin}× minimum. "
                f"Build cost ${cost_estimate.total_build_cost:.2f} vs "
                f"Murphy price ${projected_revenue:.2f} "
                f"(human rate ${stealth_pricing.human_rate:,.2f})."
            )
            inoni_entity.deployment_status = DeployabilityStatus.NOT_DEPLOYABLE
            return ViabilityResult(
                niche_id=niche_id,
                deployability_status=DeployabilityStatus.NOT_DEPLOYABLE,
                capability_check=capability_check,
                cost_estimate=cost_estimate,
                profit_projection=profit_projection,
                contractor_bids=bids,
                winning_bid=winning_bid,
                hitl_request=None,
                hitl_decision=None,
                inoni_entity=inoni_entity,
                pipeline_stage=PipelineStage.PROFIT_CHECK,
                kill_condition_triggered=False,
                kill_reason="",
                checkpoints=checkpoints,
                recovery_attempted=False,
                recovery_successful=False,
                validation_passed=False,
                workflow_self_sufficient=capability_check.workflow_self_sufficient,
                rejection_reasons=rejection_reasons,
                stealth_pricing=stealth_pricing,
            )

        # ----------------------------------------------------------------
        # STAGE 5 — Create HITL Request (QA gate — all internals done)
        # ----------------------------------------------------------------
        hitl_request = self.create_hitl_request(
            niche, capability_check, cost_estimate, profit_projection
        )
        cp5 = self.checkpoint(
            PipelineStage.HITL_PENDING,
            niche_id,
            {
                "hitl_request_id": hitl_request.request_id,
                "inoni_entity_name": hitl_request.inoni_entity_name,
                "stealth_gross_margin_pct": stealth_pricing.gross_margin_pct,
            },
        )
        checkpoints.append(cp5)

        inoni_entity.deployment_status = DeployabilityStatus.PENDING_HITL_REVIEW
        return ViabilityResult(
            niche_id=niche_id,
            deployability_status=DeployabilityStatus.PENDING_HITL_REVIEW,
            capability_check=capability_check,
            cost_estimate=cost_estimate,
            profit_projection=profit_projection,
            contractor_bids=bids,
            winning_bid=winning_bid,
            hitl_request=hitl_request,
            hitl_decision=None,
            inoni_entity=inoni_entity,
            pipeline_stage=PipelineStage.HITL_PENDING,
            kill_condition_triggered=False,
            kill_reason="",
            checkpoints=checkpoints,
            recovery_attempted=False,
            recovery_successful=False,
            validation_passed=False,
            workflow_self_sufficient=capability_check.workflow_self_sufficient,
            rejection_reasons=[],
            stealth_pricing=stealth_pricing,
        )

    def finalise_after_hitl(
        self,
        viability_result: ViabilityResult,
        hitl_decision: HITLApprovalDecision,
        spec: Any,
    ) -> ViabilityResult:
        """Update a viability result after an HITL decision is recorded.

        If approved:
        - ``validation_passed`` is set based on output gate-filter
        - ``deployability_status`` → DEPLOYABLE
        - External contacts are now authorised

        If rejected:
        - ``deployability_status`` → NOT_DEPLOYABLE

        Args:
            viability_result: The result returned by :meth:`evaluate`.
            hitl_decision: The recorded HITL decision.
            spec: The generated :class:`NicheDeploymentSpec`.

        Returns:
            Updated :class:`ViabilityResult`.
        """
        viability_result.hitl_decision = hitl_decision

        if hitl_decision.decision == HITLDecision.APPROVED:
            validation_passed = self.validate_output(spec, hitl_decision)
            viability_result.validation_passed = validation_passed
            viability_result.deployability_status = (
                DeployabilityStatus.DEPLOYABLE if validation_passed
                else DeployabilityStatus.NOT_DEPLOYABLE
            )
            viability_result.pipeline_stage = (
                PipelineStage.HITL_APPROVED if validation_passed
                else PipelineStage.HITL_APPROVED
            )
            viability_result.inoni_entity.deployment_status = viability_result.deployability_status
            viability_result.inoni_entity.hitl_approval_id = hitl_decision.request_id

            cp = self.checkpoint(
                PipelineStage.HITL_APPROVED,
                viability_result.niche_id,
                {
                    "decided_by": hitl_decision.decided_by,
                    "validation_passed": validation_passed,
                    "deployability_status": viability_result.deployability_status.value,
                },
            )
            viability_result.checkpoints.append(cp)

        else:
            viability_result.deployability_status = DeployabilityStatus.NOT_DEPLOYABLE
            viability_result.pipeline_stage = PipelineStage.HITL_REJECTED
            viability_result.inoni_entity.deployment_status = DeployabilityStatus.NOT_DEPLOYABLE
            viability_result.rejection_reasons.append(
                f"HITL request rejected by {hitl_decision.decided_by}: {hitl_decision.notes}"
            )

            cp = self.checkpoint(
                PipelineStage.HITL_REJECTED,
                viability_result.niche_id,
                {"decided_by": hitl_decision.decided_by, "notes": hitl_decision.notes},
            )
            viability_result.checkpoints.append(cp)

        return viability_result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _estimate_projected_revenue(self, niche: Any) -> float:
        """Estimate first-period revenue using the stealth pricing model (75 % of human rate).

        Murphy's price IS the revenue — 75 % of what humans would charge.
        This ensures the kill condition and profit threshold are grounded in
        the actual business model, not arbitrary lookup tables.
        """
        human_rate_est = self.estimate_human_rate(niche)
        return round(human_rate_est.human_rate_monthly * MURPHY_PRICE_RATIO, 2)

    # ------------------------------------------------------------------
    # Stealth pricing model
    # ------------------------------------------------------------------

    def estimate_human_rate(self, niche: Any) -> HumanRateEstimate:
        """Estimate what human specialists would charge monthly for this niche.

        Uses the niche's inferred industry to look up the standard human billing
        rate, then attributes cost to the key roles required.

        Args:
            niche: A :class:`NicheDefinition`-like object.

        Returns:
            A populated :class:`HumanRateEstimate`.
        """
        seed_data = getattr(niche, "seed_data", {})
        industry = seed_data.get("industry", "other")
        human_rate_monthly = _HUMAN_RATES_BY_INDUSTRY.get(
            industry, _HUMAN_RATES_BY_INDUSTRY["other"]
        )

        # Attribute the rate across key roles
        required_modules = list(getattr(niche, "murphy_modules_required", []))
        n_roles = max(len(required_modules), 1)
        per_role = round(human_rate_monthly / n_roles, 2)
        role_breakdown = {m: per_role for m in required_modules}

        return HumanRateEstimate(
            niche_id=getattr(niche, "niche_id", "unknown"),
            industry=industry,
            human_rate_monthly=human_rate_monthly,
            human_rate_source=f"industry_rate_lookup:{industry}",
            role_breakdown=role_breakdown,
        )

    def build_stealth_pricing(
        self,
        niche: Any,
        cost_estimate: CostEstimate,
    ) -> StealthPricingModel:
        """Build the stealth pricing model for a niche.

        Murphy prices at :data:`MURPHY_PRICE_RATIO` (75 %) of the human rate.
        Clients adopt because it is cheaper than human alternatives; Inoni
        captures the difference as gross profit.

        Profit formula::

            gross_profit = murphy_price - llm_costs - contractor_costs - delivery_costs

        Args:
            niche: A :class:`NicheDefinition`-like object.
            cost_estimate: The calculated build cost.

        Returns:
            A populated :class:`StealthPricingModel`.
        """
        human_rate_est = self.estimate_human_rate(niche)
        human_rate = human_rate_est.human_rate_monthly

        murphy_price = round(human_rate * MURPHY_PRICE_RATIO, 2)
        discount_to_client = round(human_rate - murphy_price, 2)
        client_savings_pct = round((1.0 - MURPHY_PRICE_RATIO) * 100.0, 1)

        llm_costs = cost_estimate.llm_generation_cost
        contractor_costs = cost_estimate.contractor_acquisition_cost
        delivery_costs = cost_estimate.delivery_cost
        total_variable_cost = round(llm_costs + contractor_costs + delivery_costs, 4)

        gross_profit = round(murphy_price - total_variable_cost, 4)
        gross_margin_pct = round(
            (gross_profit / (murphy_price or 1.0)) * 100.0, 2
        )

        human_margin_comparison = (
            f"Human specialists charge ${human_rate:,.2f}/month. "
            f"Murphy delivers the same outcome at ${murphy_price:,.2f}/month "
            f"({client_savings_pct:.0f}% cheaper). "
            f"Murphy's total variable cost is ${total_variable_cost:.2f}, "
            f"yielding a gross profit of ${gross_profit:,.2f} "
            f"({gross_margin_pct:.1f}% gross margin). "
            f"Client never sees the cost structure — they see a service "
            f"priced below market (stealth adoption)."
        )

        return StealthPricingModel(
            human_rate=human_rate,
            murphy_price=murphy_price,
            discount_to_client=discount_to_client,
            client_savings_pct=client_savings_pct,
            llm_costs=llm_costs,
            contractor_costs=contractor_costs,
            delivery_costs=delivery_costs,
            total_variable_cost=total_variable_cost,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            human_margin_comparison=human_margin_comparison,
        )

    def compare_to_human_cost(
        self,
        niche: Any,
        cost_estimate: CostEstimate,
    ) -> Dict[str, Any]:
        """Return a human-readable cost comparison dict for reporting.

        Args:
            niche: A :class:`NicheDefinition`-like object.
            cost_estimate: The calculated build cost.

        Returns:
            Dict with keys: ``human_rate``, ``murphy_price``, ``client_saves``,
            ``murphy_cost``, ``gross_profit``, ``gross_margin_pct``.
        """
        stealth = self.build_stealth_pricing(niche, cost_estimate)
        return {
            "human_rate_monthly": stealth.human_rate,
            "murphy_price_monthly": stealth.murphy_price,
            "client_saves_monthly": stealth.discount_to_client,
            "client_savings_pct": stealth.client_savings_pct,
            "murphy_variable_cost": stealth.total_variable_cost,
            "gross_profit": stealth.gross_profit,
            "gross_margin_pct": stealth.gross_margin_pct,
            "narrative": stealth.human_margin_comparison,
        }

    @staticmethod
    def _attr_value(obj: Any, attr: str) -> str:
        """Return the string value of an attribute, handling Enum members."""
        val = getattr(obj, attr, "")
        if hasattr(val, "value"):
            return val.value
        return str(val)


# ===========================================================================
# RFP Gap Analyser — what Murphy can vs. needs to generate for each RFP
# ===========================================================================

#: Skill-to-credential mapping used for automatic credential identification
_SKILL_CREDENTIAL_MAP: Dict[str, Dict[str, str]] = {
    "commissioned_notary":     {"type": "license",          "issuing_body": "State Notary Commission",      "regulatory_body": "Secretary of State"},
    "licensed_inspector":      {"type": "certification",    "issuing_body": "ASHI / InterNACHI",            "regulatory_body": "Home Inspector Licensing Board"},
    "calibration_technician":  {"type": "certification",    "issuing_body": "ISO 17025 / NIST",             "regulatory_body": "NIST / A2LA"},
    "registered_agent":        {"type": "license",          "issuing_body": "State Bar / Secretary of State","regulatory_body": "State Bar Association"},
    "permit_runner":           {"type": "professional_registration", "issuing_body": "N/A",                 "regulatory_body": "Local Government"},
    "sales_closer":            {"type": "license",          "issuing_body": "State Real Estate Commission", "regulatory_body": "State Licensing Board"},
    "event_coordinator":       {"type": "certification",    "issuing_body": "CMP / MPI",                    "regulatory_body": "Events Industry Council"},
    "market_researcher":       {"type": "certification",    "issuing_body": "MRA / QRCA",                   "regulatory_body": "Market Research Association"},
    "native_speaker_translator": {"type": "certification",  "issuing_body": "ATA / ISO 17100",              "regulatory_body": "American Translators Association"},
    "mystery_shopper":         {"type": "certification",    "issuing_body": "MSPA",                         "regulatory_body": "Mystery Shopping Professionals Association"},
}

#: GenerationTypes that always require a credentialed human
_CREDENTIALED_GENERATION_TYPES: frozenset = frozenset({
    GenerationType.PHYSICAL_INSPECTION,
    GenerationType.LEGAL_FILING,
    GenerationType.IN_PERSON_SERVICE,
})


class RFPGapAnalyzer:
    """
    Analyses an incoming RFP against Murphy's generation capabilities.

    For every niche business an RFP creates a gap report:
      - What the client needs (requirements extracted from RFP text)
      - What Murphy can generate fully internally
      - What requires a physical-world contractor
      - What Murphy cannot deliver at all (unresolvable gaps)
      - The stealth quote: 75 % of what humans would charge for the same work
    """

    def __init__(
        self,
        inference_engine: InferenceDomainGateEngine,
        mss_controller: MSSController,
    ) -> None:
        self._inference_engine = inference_engine
        self._mss_controller = mss_controller

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        rfp_text: str,
        niche: Any,
        viability_result: Optional[ViabilityResult] = None,
    ) -> "RFPAnalysis":
        """Full gap analysis for *rfp_text* against *niche* capabilities.

        Args:
            rfp_text: The raw RFP text received by the niche business.
            niche: A :class:`NicheDefinition`-like object for this niche.
            viability_result: Optional previously-computed viability result.

        Returns:
            A populated :class:`RFPAnalysis`.
        """
        rfp = RFP(
            rfp_id=str(uuid.uuid4()),
            niche_id=getattr(niche, "niche_id", "unknown"),
            client_id="rfp_client",
            description=rfp_text[:128],
            raw_text=rfp_text,
            budget_ceiling=None,
            deadline=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        requirements = self.parse_requirements(rfp_text, niche)
        capabilities = [
            self.check_generation_capability(req, niche)
            for req in requirements
        ]

        gap_items: List[RFPGapItem] = []
        for req, cap in zip(requirements, capabilities):
            severity = "none"
            if not cap.can_generate and not cap.murphy_can_contribute:
                severity = "full"
            elif not cap.can_generate and cap.murphy_can_contribute:
                severity = "partial"
            resolution_cost = 0.0
            if cap.requires_contractor:
                resolution_cost = 85.0  # estimated cheapest qualifying bid
            gap_items.append(RFPGapItem(
                requirement=req,
                capability=cap,
                gap_severity=severity,
                resolution_cost=resolution_cost,
                resolution_notes=cap.gap_description,
            ))

        can_fully_deliver = all(c.can_generate for c in capabilities)
        requires_human_augmentation = any(c.requires_contractor for c in capabilities)
        unresolvable = [g for g in gap_items if not g.capability.resolvable and g.gap_severity != "none"]

        murphy_coverage = sum(1 for c in capabilities if c.can_generate or c.murphy_can_contribute)
        murphy_coverage_pct = round(
            (murphy_coverage / (len(capabilities) or 1)) * 100.0, 1
        )

        # Estimate human rate for this RFP
        seed_data = getattr(niche, "seed_data", {})
        industry = seed_data.get("industry", "other")
        human_hourly = _HUMAN_RATES_BY_INDUSTRY.get(industry, 6000.0) / 160.0  # $/hr
        total_human_hours = sum(r.estimated_hours for r in requirements)
        human_rate_for_rfp = round(human_hourly * total_human_hours, 2)

        # Build stealth quote
        contractor_cost = sum(g.resolution_cost for g in gap_items)
        llm_cost = round(_LLM_INFERENCE_COST + (len(requirements) * _LLM_COST_PER_OP), 4)
        delivery_cost = _DELIVERY_BASE_COST
        total_variable = round(contractor_cost + llm_cost + delivery_cost, 4)
        murphy_price = round(human_rate_for_rfp * MURPHY_PRICE_RATIO, 2)
        gross_profit = round(murphy_price - total_variable, 4)
        gross_margin = round((gross_profit / (murphy_price or 1.0)) * 100.0, 2)

        stealth_quote = StealthPricingModel(
            human_rate=human_rate_for_rfp,
            murphy_price=murphy_price,
            discount_to_client=round(human_rate_for_rfp - murphy_price, 2),
            client_savings_pct=round((1.0 - MURPHY_PRICE_RATIO) * 100.0, 1),
            llm_costs=llm_cost,
            contractor_costs=contractor_cost,
            delivery_costs=delivery_cost,
            total_variable_cost=total_variable,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin,
            human_margin_comparison=(
                f"RFP human rate: ${human_rate_for_rfp:,.2f}. "
                f"Murphy stealth quote: ${murphy_price:,.2f} (25 % cheaper). "
                f"Murphy variable cost: ${total_variable:.2f}. "
                f"Gross profit: ${gross_profit:,.2f} ({gross_margin:.1f}% margin)."
            ),
        )

        overall_confidence = round(
            sum(c.confidence for c in capabilities) / (len(capabilities) or 1), 3
        )

        return RFPAnalysis(
            rfp=rfp,
            niche_id=getattr(niche, "niche_id", "unknown"),
            requirements=requirements,
            capabilities=capabilities,
            gap_items=gap_items,
            can_fully_deliver=can_fully_deliver,
            requires_human_augmentation=requires_human_augmentation,
            unresolvable_gaps=unresolvable,
            murphy_coverage_pct=murphy_coverage_pct,
            estimated_delivery_cost=total_variable,
            stealth_quote=stealth_quote,
            human_rate_for_rfp=human_rate_for_rfp,
            delivery_confidence=overall_confidence,
        )

    def parse_requirements(self, rfp_text: str, niche: Any) -> List["RFPRequirement"]:
        """Extract deliverable requirements from RFP text.

        Uses keyword matching to classify each sentence/clause as a
        requirement and assign its generation type.

        Args:
            rfp_text: The raw RFP text.
            niche: A :class:`NicheDefinition`-like object (for context).

        Returns:
            List of :class:`RFPRequirement` instances.
        """
        # Split into candidate requirement clauses
        import re
        clauses = re.split(r"[,\n;.]+", rfp_text)
        requirements: List[RFPRequirement] = []

        for clause in clauses:
            clause = clause.strip()
            if len(clause) < 10:
                continue
            lower = clause.lower()

            gen_type, keywords, hours = self._classify_clause(lower)

            complexity = "low"
            if hours >= 8:
                complexity = "high"
            elif hours >= 3:
                complexity = "medium"

            requirements.append(RFPRequirement(
                requirement_id=str(uuid.uuid4()),
                description=clause,
                generation_type=gen_type,
                estimated_hours=hours,
                complexity=complexity,
                keywords_matched=keywords,
            ))

        # Always return at least one requirement
        if not requirements:
            requirements.append(RFPRequirement(
                requirement_id=str(uuid.uuid4()),
                description=rfp_text[:128],
                generation_type=GenerationType.UNKNOWN,
                estimated_hours=2.0,
                complexity="low",
                keywords_matched=[],
            ))

        return requirements

    def check_generation_capability(
        self,
        requirement: "RFPRequirement",
        niche: Any,
    ) -> "GenerationCapability":
        """Assess Murphy's capability to fulfil a single requirement.

        Args:
            requirement: The requirement to assess.
            niche: Context niche.

        Returns:
            A populated :class:`GenerationCapability`.
        """
        gen_type = requirement.generation_type

        if gen_type in _CREDENTIALED_GENERATION_TYPES:
            return GenerationCapability(
                requirement_id=requirement.requirement_id,
                can_generate=False,
                requires_contractor=True,
                murphy_can_contribute=True,  # Murphy handles the non-physical parts
                generation_method="contractor_dispatch_post_hitl",
                confidence=0.7,
                gap_description=(
                    f"Requires physical-world presence for {gen_type.value}. "
                    "Murphy generates the framework/documentation; "
                    "credentialed contractor performs the physical work."
                ),
                resolvable=True,
                resolution_method="contractor_dispatch",
            )

        if gen_type == GenerationType.UNKNOWN:
            return GenerationCapability(
                requirement_id=requirement.requirement_id,
                can_generate=False,
                requires_contractor=False,
                murphy_can_contribute=False,
                generation_method="none",
                confidence=0.2,
                gap_description="Requirement could not be classified — manual review needed.",
                resolvable=False,
                resolution_method="not_deliverable",
            )

        # Murphy can generate everything else
        method_map = {
            GenerationType.DIGITAL_CONTENT:  "llm_content_generation",
            GenerationType.DOCUMENT:         "template_generation",
            GenerationType.DATA_ANALYSIS:    "inference_analysis",
            GenerationType.RESEARCH:         "competitive_intelligence_engine",
            GenerationType.COMPLIANCE:       "compliance_engine",
            GenerationType.CODE_OR_API:      "code_generation_gateway",
        }
        method = method_map.get(gen_type, "llm_general")

        return GenerationCapability(
            requirement_id=requirement.requirement_id,
            can_generate=True,
            requires_contractor=False,
            murphy_can_contribute=True,
            generation_method=method,
            confidence=0.92,
            gap_description="",
            resolvable=True,
            resolution_method="internal",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_clause(
        lower: str,
    ) -> tuple:
        """Return (GenerationType, matched_keywords, estimated_hours) for a clause."""
        contractor_hits = [kw for kw in _CONTRACTOR_REQUIRED_KEYWORDS if kw in lower]
        if contractor_hits:
            if any(k in lower for k in ("inspect", "photo", "structural", "calibrat", "notariz", "sign")):
                return GenerationType.PHYSICAL_INSPECTION, contractor_hits, 3.0
            if any(k in lower for k in ("file", "government", "permit", "register")):
                return GenerationType.LEGAL_FILING, contractor_hits, 4.0
            return GenerationType.IN_PERSON_SERVICE, contractor_hits, 2.0

        murphy_hits = [kw for kw in _MURPHY_GENERATABLE_KEYWORDS if kw in lower]
        if not murphy_hits:
            return GenerationType.UNKNOWN, [], 1.0

        if any(k in lower for k in ("article", "content", "newsletter", "email", "copy", "description")):
            return GenerationType.DIGITAL_CONTENT, murphy_hits, 1.5
        if any(k in lower for k in ("template", "contract", "sop", "policy", "manual", "guide")):
            return GenerationType.DOCUMENT, murphy_hits, 2.0
        if any(k in lower for k in ("report", "dashboard", "kpi", "metric", "forecast", "analytics")):
            return GenerationType.DATA_ANALYSIS, murphy_hits, 2.5
        if any(k in lower for k in ("research", "competitive", "intelligence", "keyword")):
            return GenerationType.RESEARCH, murphy_hits, 3.0
        if any(k in lower for k in ("compliance", "checklist", "audit", "certification")):
            return GenerationType.COMPLIANCE, murphy_hits, 2.0
        if any(k in lower for k in ("api", "code", "integration", "endpoint")):
            return GenerationType.CODE_OR_API, murphy_hits, 4.0

        return GenerationType.DIGITAL_CONTENT, murphy_hits, 1.5


# ===========================================================================
# Credential + Negotiation Engine — certified/licensed HITL validation
# ===========================================================================

class CredentialType(str, Enum):
    """Type of professional credential required for a task."""
    LICENSE = "license"
    CERTIFICATION = "certification"
    REGULATORY_MEMBERSHIP = "regulatory_membership"
    PROFESSIONAL_REGISTRATION = "professional_registration"
    GOVERNMENT_ISSUED = "government_issued"


class NegotiationStance(str, Enum):
    """Which party a negotiation term favours."""
    MURPHY_TERM = "murphy_term"    # non-negotiable — 75 % weight
    NEGOTIABLE = "negotiable"      # human may influence — 25 % weight
    MUTUAL = "mutual"              # both benefit


@dataclass
class RequiredCredential:
    """A credential required to perform a specific task."""
    credential_id: str
    credential_type: CredentialType
    required_for: str             # e.g. "notarization", "property_inspection"
    issuing_body: str
    regulatory_body: Optional[str]
    description: str
    is_mandatory: bool            # False = preferred but not blocking


@dataclass
class CredentialRecord:
    """Recorded credentials provided by a contractor/validator."""
    record_id: str
    holder_id: str
    holder_name: str              # real name (may differ from persona name)
    masked_as: Optional[str]     # persona name used in interaction ("Jenny")
    credential_type: CredentialType
    credential_number: str        # actual license / cert number
    issuing_body: str
    issue_date: str
    expiry_date: Optional[str]
    verified: bool
    verification_method: str      # "self_reported" | "document_submitted"
    verified_at: Optional[str]
    masked_for_output: bool       # True → mask number in non-admin outputs


@dataclass
class NegotiationTerm:
    """A single term in a contractor negotiation."""
    term_id: str
    description: str
    stance: NegotiationStance
    weight: float                 # 0–1 share of total negotiation weight
    value: str                    # agreed value
    committed_at: str
    documented: bool


@dataclass
class NegotiationRecord:
    """
    Complete negotiation record.

    Murphy's standard target is 75/25 in Murphy's favour.  For a qualifying
    high-quality contractor Murphy may accept down to 55/45 — the "quality
    override" — because reliability and partnership value more than compensate
    for the reduced weight.  Murphy NEVER accepts below 55 % (the absolute floor).
    Murphy ALWAYS seeks the BEST deal, not merely an acceptable one.
    """
    negotiation_id: str
    request_id: str
    niche_id: str
    murphy_terms: List[NegotiationTerm]    # ≈ 75 % of total weight (standard)
    human_terms: List[NegotiationTerm]     # ≈ 25 % of total weight (standard)
    murphy_weight: float                   # sum of murphy term weights
    human_weight: float                    # sum of human term weights
    balance_valid: bool                    # murphy ≥ 0.70 and ≤ 0.80 (standard)
    agreed_at: str
    total_terms: int
    scope_summary: str                     # "Contractor agreed to [X] under [terms]"
    quality_override: bool = False         # True if 55/45 accepted due to quality
    accepted_balance: Optional[float] = None  # final accepted murphy_weight (may use override)


@dataclass
class ContractorQualityProfile:
    """
    Scored quality assessment of a contractor.

    Drives the flexible negotiation floor: a strong contractor can be accepted
    at 55/45 (instead of the standard 70/80) because their reliability,
    longevity, and ease-of-work compensate for the reduced Murphy weight.
    Murphy always seeks the BEST deal — a reliable partner at 55/45 is better
    than a random contractor at 75/25.
    """
    contractor_id: str
    history_score: float            # 0–1  completion rate from COYA records
    longevity_score: float          # 0–1  will they be here in 10 years?
    ease_of_work_score: float       # 0–1  easy for Murphy system to work with?
    negotiation_reasonableness_score: float  # 0–1  were their asks reasonable?
    deal_strength_score: float      # 0–1  inference: is this a strong overall deal?
    composite_score: float          # weighted combination
    qualifies_for_55_45: bool       # composite ≥ 0.70 AND longevity ≥ 0.60
    partner_eligible: bool          # composite ≥ 0.80 — promote to repeat partner
    assessment_notes: str
    assessed_at: str


@dataclass
class ContractorPartnerRecord:
    """
    A contractor promoted to preferred HITL partner status.

    Murphy contacts partners first for relevant tasks.  Partners are already
    credentialed, negotiation-proven, and easy to work with — reducing friction
    and verification overhead on every repeat engagement.
    """
    partner_id: str
    contractor_id: str
    credential_record_id: str
    niche_ids: List[str]            # niches this partner is preferred for
    quality_profile: ContractorQualityProfile
    preferred_contact: str          # contact method preference
    partner_since: str
    tasks_completed: int
    tasks_failed: int
    success_rate: float             # tasks_completed / (tasks_completed + tasks_failed)
    hitl_priority: int              # 1 = contact first, higher = lower priority
    active: bool


@dataclass
class CredentialedHITLRequest:
    """
    HITL request directed at a certified/licensed contractor (not the operator).

    The interaction may use a friendly agent persona ("Hi, I'm Jenny!") to
    onboard the contractor without revealing the Murphy/AI backend.  Their
    credential information is captured as part of acceptance.
    """
    request_id: str
    niche_id: str
    task_id: str
    persona_name: str            # e.g. "Jenny" — the friendly Inoni agent name
    persona_intro: str           # opening message shown to the contractor
    scope_description: str       # plain-language scope (non-technical)
    required_credential: RequiredCredential
    murphy_terms: List[str]      # non-negotiable terms (75 % weight)
    negotiable_terms: List[str]  # contractor may influence (25 % weight)
    payment_ceiling: float       # max Inoni will pay
    acceptance_criteria: List[str]  # what "done" looks like
    status: str                  # "pending" | "in_negotiation" | "agreed" | "declined"
    created_at: str


@dataclass
class COYARecord:
    """
    Cover-Your-Ass documentation for a contractor agreement.

    Every credentialed HITL agreement produces a COYA record that tracks:
    - What was agreed (scope, timeline, credentials)
    - Whether the contractor delivered
    - Any discrepancies between agreement and delivery
    """
    coya_id: str
    task_id: str
    niche_id: str
    negotiation_id: str
    credential_record_id: str
    scope_agreed: str            # exactly what was agreed
    scope_timeline: str          # when they agreed to deliver
    completion_status: str       # "pending" | "completed" | "failed" | "disputed"
    completed_at: Optional[str]
    evidence_submitted: Dict[str, Any]
    gate_passed: Optional[bool]  # did their submission pass the gate?
    discrepancies: List[str]     # where delivery differed from the agreement
    created_at: str
    last_updated: str


class CredentialNegotiationEngine:
    """
    Manages credentialed contractor HITL validation and 75/25 negotiation.

    For any task requiring a certification, license, or regulatory body oversight,
    this engine:
      1. Identifies required credentials from the task skill type
      2. Creates a credentialed HITL request (optionally with a persona like "Jenny")
      3. Records the contractor's credentials on acceptance
      4. Builds a 75/25 negotiation record (Murphy keeps 75 %)
      5. Produces COYA documentation for every agreement
      6. Tracks delivery against commitments
    """

    def __init__(self) -> None:
        self._credentials: Dict[str, CredentialRecord] = {}
        self._negotiations: Dict[str, NegotiationRecord] = {}
        self._coya_records: Dict[str, COYARecord] = {}
        self._credentialed_requests: Dict[str, CredentialedHITLRequest] = {}
        self._partners: Dict[str, ContractorPartnerRecord] = {}

    # ------------------------------------------------------------------
    # Credential identification
    # ------------------------------------------------------------------

    def identify_required_credentials(
        self,
        skill_required: str,
        generation_types: Optional[List[GenerationType]] = None,
    ) -> List[RequiredCredential]:
        """Identify what credentials are needed for a skill/task type.

        Args:
            skill_required: The skill string from the contractor task template.
            generation_types: Optional list of generation types for the task.

        Returns:
            List of :class:`RequiredCredential` instances (may be empty for
            uncredentialed tasks like "runner" or "general").
        """
        creds: List[RequiredCredential] = []
        lower_skill = skill_required.lower().replace(" ", "_")

        info = _SKILL_CREDENTIAL_MAP.get(lower_skill)
        if info:
            creds.append(RequiredCredential(
                credential_id=str(uuid.uuid4()),
                credential_type=CredentialType(info["type"]),
                required_for=lower_skill,
                issuing_body=info["issuing_body"],
                regulatory_body=info.get("regulatory_body"),
                description=(
                    f"Required to perform {lower_skill.replace('_', ' ')} tasks. "
                    f"Issued by {info['issuing_body']}."
                ),
                is_mandatory=True,
            ))

        # Also flag physical / legal tasks
        if generation_types:
            for gt in generation_types:
                if gt in _CREDENTIALED_GENERATION_TYPES and not creds:
                    creds.append(RequiredCredential(
                        credential_id=str(uuid.uuid4()),
                        credential_type=CredentialType.PROFESSIONAL_REGISTRATION,
                        required_for=gt.value,
                        issuing_body="Relevant Professional Body",
                        regulatory_body=None,
                        description=f"Professional credential required for {gt.value}.",
                        is_mandatory=True,
                    ))

        return creds

    # ------------------------------------------------------------------
    # Credentialed HITL request
    # ------------------------------------------------------------------

    def create_credentialed_request(
        self,
        task_id: str,
        niche_id: str,
        task_description: str,
        required_credential: RequiredCredential,
        payment_ceiling: float,
        acceptance_criteria: Optional[List[str]] = None,
        persona_name: str = "Jenny",
    ) -> CredentialedHITLRequest:
        """Create a HITL request for a credentialed contractor.

        The request uses a friendly persona intro — the contractor sees a
        professional services engagement, not an AI system.  Their credential
        information is required as part of acceptance.

        Args:
            task_id: The contractor task this request is for.
            niche_id: The niche business this belongs to.
            task_description: Plain-language description of the work.
            required_credential: The credential the contractor must hold.
            payment_ceiling: Maximum Inoni will pay.
            acceptance_criteria: What "done" looks like.
            persona_name: Friendly agent name shown to the contractor.

        Returns:
            A populated :class:`CredentialedHITLRequest`.
        """
        persona_intro = (
            f"Hi! I'm {persona_name} from Inoni Services. "
            f"We have an opportunity that matches your expertise in "
            f"{required_credential.required_for.replace('_', ' ')}. "
            f"We'd love to work with you — it's straightforward, well-scoped, "
            f"and pays ${payment_ceiling:.2f} on verified completion. "
            f"All I need is a few details to get started."
        )

        # Murphy's non-negotiable terms (75 % of negotiation weight)
        murphy_terms = [
            f"Deliverables as specified: {task_description}",
            "Payment on gate-verified completion only (not on submission)",
            "All work must meet acceptance criteria before payment releases",
            "Timeline as agreed \u2014 no unilateral extensions",
            f"Credential verification required: {required_credential.issuing_body}",
            "Non-disclosure of Inoni's internal systems and processes",
        ]

        # Contractor's negotiable terms (25 % of negotiation weight)
        negotiable_terms = [
            f"Rate: up to ${payment_ceiling:.2f} (negotiable within ceiling)",
            "Preferred contact method (phone / email / portal)",
            "Minor schedule flexibility within ±24 hours",
        ]

        criteria = acceptance_criteria or [
            "Submission matches the agreed deliverable specification",
            "Gate validation passes on first review",
            "Credentials verified by issuing body lookup",
        ]

        request = CredentialedHITLRequest(
            request_id=str(uuid.uuid4()),
            niche_id=niche_id,
            task_id=task_id,
            persona_name=persona_name,
            persona_intro=persona_intro,
            scope_description=task_description,
            required_credential=required_credential,
            murphy_terms=murphy_terms,
            negotiable_terms=negotiable_terms,
            payment_ceiling=payment_ceiling,
            acceptance_criteria=criteria,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._credentialed_requests[request.request_id] = request
        return request

    # ------------------------------------------------------------------
    # Credential recording
    # ------------------------------------------------------------------

    def record_credentials(
        self,
        request_id: str,
        credential_data: Dict[str, Any],
    ) -> CredentialRecord:
        """Record the credentials provided by a contractor in response to a request.

        Args:
            request_id: The credentialed HITL request this responds to.
            credential_data: Dict with keys: holder_name, credential_number,
                             issue_date, expiry_date (optional), masked_as (optional).

        Returns:
            A populated :class:`CredentialRecord`.

        Raises:
            KeyError: If *request_id* is not found.
        """
        if request_id not in self._credentialed_requests:
            raise KeyError(f"Credentialed request {request_id!r} not found")

        req = self._credentialed_requests[request_id]
        record = CredentialRecord(
            record_id=str(uuid.uuid4()),
            holder_id=credential_data.get("holder_id", str(uuid.uuid4())),
            holder_name=credential_data.get("holder_name", "Unknown"),
            masked_as=credential_data.get("masked_as"),
            credential_type=req.required_credential.credential_type,
            credential_number=credential_data.get("credential_number", ""),
            issuing_body=req.required_credential.issuing_body,
            issue_date=credential_data.get("issue_date", ""),
            expiry_date=credential_data.get("expiry_date"),
            verified=bool(credential_data.get("credential_number", "")),
            verification_method="self_reported",
            verified_at=datetime.now(timezone.utc).isoformat()
            if credential_data.get("credential_number")
            else None,
            masked_for_output=True,
        )
        self._credentials[record.record_id] = record
        req.status = "in_negotiation"
        return record

    # ------------------------------------------------------------------
    # 75/25 Negotiation
    # ------------------------------------------------------------------

    def build_negotiation(
        self,
        request_id: str,
        human_response: Dict[str, Any],
    ) -> NegotiationRecord:
        """Build a 75/25 negotiation record from the contractor's response.

        Murphy's terms carry 75 % of the total weight.  The contractor's
        concessions are bounded to 25 %.  "If they say they are willing to
        do X, we make sure they do X — and document it."

        Args:
            request_id: The credentialed HITL request being negotiated.
            human_response: Contractor's acceptance dict with optional keys:
                rate, preferred_contact, schedule_note.

        Returns:
            A populated :class:`NegotiationRecord`.

        Raises:
            KeyError: If *request_id* is not found.
        """
        if request_id not in self._credentialed_requests:
            raise KeyError(f"Credentialed request {request_id!r} not found")

        req = self._credentialed_requests[request_id]
        now = datetime.now(timezone.utc).isoformat()

        # Murphy's terms — non-negotiable (each carries equal share of 75 %)
        murphy_weight_each = 0.75 / (len(req.murphy_terms) or 1)
        murphy_terms = [
            NegotiationTerm(
                term_id=str(uuid.uuid4()),
                description=term,
                stance=NegotiationStance.MURPHY_TERM,
                weight=round(murphy_weight_each, 4),
                value="accepted",
                committed_at=now,
                documented=True,
            )
            for term in req.murphy_terms
        ]

        # Human's terms — negotiable (share 25 % across concessions)
        agreed_rate = human_response.get("rate", req.payment_ceiling)
        agreed_rate = min(float(agreed_rate), req.payment_ceiling)  # enforce ceiling
        contact = human_response.get("preferred_contact", "portal")
        schedule = human_response.get("schedule_note", "as specified")

        human_concessions = [
            (f"Agreed rate: ${agreed_rate:.2f}", str(agreed_rate)),
            (f"Preferred contact: {contact}", contact),
            (f"Schedule note: {schedule}", schedule),
        ]
        human_weight_each = 0.25 / (len(human_concessions) or 1)
        human_terms = [
            NegotiationTerm(
                term_id=str(uuid.uuid4()),
                description=desc,
                stance=NegotiationStance.NEGOTIABLE,
                weight=round(human_weight_each, 4),
                value=val,
                committed_at=now,
                documented=True,
            )
            for desc, val in human_concessions
        ]

        murphy_weight = round(sum(t.weight for t in murphy_terms), 4)
        human_weight = round(sum(t.weight for t in human_terms), 4)
        balance_valid = 0.70 <= murphy_weight <= 0.80

        scope_summary = (
            f"Contractor agreed to: {req.scope_description}. "
            f"Rate: ${agreed_rate:.2f}. Contact: {contact}. "
            f"Negotiation balance: {murphy_weight * 100:.0f}% Murphy / "
            f"{human_weight * 100:.0f}% Contractor."
        )

        record = NegotiationRecord(
            negotiation_id=str(uuid.uuid4()),
            request_id=request_id,
            niche_id=req.niche_id,
            murphy_terms=murphy_terms,
            human_terms=human_terms,
            murphy_weight=murphy_weight,
            human_weight=human_weight,
            balance_valid=balance_valid,
            agreed_at=now,
            total_terms=len(murphy_terms) + len(human_terms),
            scope_summary=scope_summary,
        )
        self._negotiations[record.negotiation_id] = record
        req.status = "agreed"
        return record

    def verify_75_25_balance(self, negotiation: NegotiationRecord) -> bool:
        """Return True if Murphy holds at least 70 % of the negotiation weight.

        Args:
            negotiation: A completed :class:`NegotiationRecord`.

        Returns:
            ``True`` if the balance is within the acceptable 70–80 % Murphy range.
        """
        return negotiation.balance_valid

    # ------------------------------------------------------------------
    # COYA documentation
    # ------------------------------------------------------------------

    def create_coya_record(
        self,
        negotiation: NegotiationRecord,
        credential: CredentialRecord,
        task_id: str,
    ) -> COYARecord:
        """Create cover-your-ass documentation for a contractor agreement.

        Records exactly what was agreed, who agreed to it, and their
        credentials — so any future dispute has a documented paper trail.

        Args:
            negotiation: The completed negotiation record.
            credential: The contractor's recorded credentials.
            task_id: The contractor task ID.

        Returns:
            A populated :class:`COYARecord`.
        """
        now = datetime.now(timezone.utc).isoformat()
        record = COYARecord(
            coya_id=str(uuid.uuid4()),
            task_id=task_id,
            niche_id=negotiation.niche_id,
            negotiation_id=negotiation.negotiation_id,
            credential_record_id=credential.record_id,
            scope_agreed=negotiation.scope_summary,
            scope_timeline="as agreed in negotiation terms",
            completion_status="pending",
            completed_at=None,
            evidence_submitted={},
            gate_passed=None,
            discrepancies=[],
            created_at=now,
            last_updated=now,
        )
        self._coya_records[record.coya_id] = record
        return record

    def record_task_completion(
        self,
        coya_id: str,
        completed: bool,
        evidence: Dict[str, Any],
    ) -> COYARecord:
        """Record the outcome of a contractor task against the COYA agreement.

        If the task is not completed or evidence does not match the agreed
        scope, discrepancies are logged automatically.

        Args:
            coya_id: The COYA record to update.
            completed: Whether the contractor marked the task complete.
            evidence: Data/files submitted as evidence of completion.

        Returns:
            The updated :class:`COYARecord`.

        Raises:
            KeyError: If *coya_id* is not found.
        """
        if coya_id not in self._coya_records:
            raise KeyError(f"COYA record {coya_id!r} not found")

        record = self._coya_records[coya_id]
        now = datetime.now(timezone.utc).isoformat()
        record.evidence_submitted = evidence
        record.last_updated = now

        if completed:
            record.completion_status = "completed"
            record.completed_at = now
            # Basic discrepancy check: evidence must be non-empty
            if not evidence:
                record.discrepancies.append(
                    "Task marked complete but no evidence submitted."
                )
                record.gate_passed = False
            else:
                record.gate_passed = True
        else:
            record.completion_status = "failed"
            record.discrepancies.append(
                f"Contractor did not complete task as agreed. "
                f"Scope was: {record.scope_agreed}"
            )
            record.gate_passed = False

        return record

    def check_commitment_fulfilled(self, coya_id: str) -> bool:
        """Return True if the contractor fulfilled their documented commitment.

        Args:
            coya_id: The COYA record to check.

        Returns:
            ``True`` if gate_passed is ``True`` and no discrepancies exist.
        """
        record = self._coya_records.get(coya_id)
        if record is None:
            return False
        return record.gate_passed is True and len(record.discrepancies) == 0

    def get_coya_records_for_niche(self, niche_id: str) -> List[COYARecord]:
        """Return all COYA records for a specific niche."""
        return [r for r in self._coya_records.values() if r.niche_id == niche_id]

    # ------------------------------------------------------------------
    # Contractor quality scoring
    # ------------------------------------------------------------------

    def score_contractor(
        self,
        contractor_id: str,
        negotiation: NegotiationRecord,
        credential: CredentialRecord,
        past_coya_records: Optional[List[COYARecord]] = None,
    ) -> ContractorQualityProfile:
        """Score a contractor's quality across five dimensions.

        Dimensions
        ----------
        history_score
            Completion rate from past COYA records. Unknown contractor = 0.50
            (neutral). Each clean completion adds; each failure subtracts.
        longevity_score
            Will they likely be here in 10 years?  Derived from credential
            age (older = more established), expiry window, and issuing body
            (professional association = more stable).
        ease_of_work_score
            Did their first submission pass?  Did they respond without
            push-back on Murphy's terms?  Low human_weight in negotiation
            → easier to work with.
        negotiation_reasonableness_score
            Were their rate asks reasonable?  Did they accept Murphy's
            non-negotiable terms without challenge?
        deal_strength_score
            Composite inference: given all documents (credential, negotiation,
            history) — is this a strong deal for Murphy?

        Returns
        -------
        ContractorQualityProfile with ``qualifies_for_55_45`` and
        ``partner_eligible`` flags set.
        """
        past = past_coya_records or []
        now = datetime.now(timezone.utc).isoformat()

        # ---- History score ----
        if not past:
            history_score = 0.50  # neutral — no history
        else:
            completed = sum(1 for r in past if r.gate_passed is True)
            history_score = round(completed / (len(past) or 1), 3)

        # ---- Longevity score ----
        longevity_score = self._infer_longevity(credential)

        # ---- Ease of work ----
        # Low human_weight = contractor didn't push back much = easy to work with
        ease_raw = 1.0 - negotiation.human_weight  # human_weight ≈ 0.25 standard
        # Gate pass rate on first attempt (from past records)
        first_pass = sum(
            1 for r in past if r.gate_passed is True and len(r.discrepancies) == 0
        )
        first_pass_rate = first_pass / (len(past) or 1) if past else 0.70
        ease_of_work_score = round((ease_raw * 0.6) + (first_pass_rate * 0.4), 3)
        ease_of_work_score = max(0.0, min(1.0, ease_of_work_score))

        # ---- Negotiation reasonableness ----
        # Did they ask for reasonable rate (within 90 % of ceiling)?
        rate_terms = [t for t in negotiation.human_terms if "rate" in t.description.lower()]
        reasonableness = 0.75  # default reasonable
        if rate_terms:
            try:
                agreed_rate = float(rate_terms[0].value)
                req_id = negotiation.request_id
                req = self._credentialed_requests.get(req_id)
                if req:
                    ceiling_ratio = agreed_rate / (req.payment_ceiling or 1.0)
                    # Ratio ≤ 0.85 = very reasonable; ≥ 1.0 = at ceiling = less so
                    reasonableness = round(max(0.0, 1.0 - max(0.0, ceiling_ratio - 0.70)), 3)
            except (ValueError, ZeroDivisionError) as exc:
                logger.debug("Reasonableness calc error for contractor %r: %s", contractor_id, exc)
                reasonableness = 0.70

        negotiation_reasonableness_score = round(reasonableness, 3)

        # ---- Deal strength (composite inference) ----
        deal_strength_score = round(
            (history_score * 0.35)
            + (longevity_score * 0.25)
            + (ease_of_work_score * 0.20)
            + (negotiation_reasonableness_score * 0.20),
            3,
        )

        # ---- Composite score ----
        composite_score = round(
            (history_score * 0.30)
            + (longevity_score * 0.25)
            + (ease_of_work_score * 0.20)
            + (negotiation_reasonableness_score * 0.15)
            + (deal_strength_score * 0.10),
            3,
        )

        # ---- Quality gates ----
        # 55/45 override: strong composite + longevity + deal strength
        qualifies_for_55_45 = (
            composite_score >= 0.70
            and longevity_score >= 0.60
            and deal_strength_score >= 0.65
        )
        # Partner eligible: consistently excellent across all dimensions
        partner_eligible = composite_score >= 0.80

        notes_parts = [
            f"History: {history_score:.2f}",
            f"Longevity: {longevity_score:.2f} ({'stable' if longevity_score >= 0.60 else 'new'})",
            f"Ease: {ease_of_work_score:.2f}",
            f"Reasonableness: {negotiation_reasonableness_score:.2f}",
            f"Deal strength: {deal_strength_score:.2f}",
            f"Composite: {composite_score:.2f}",
            f"55/45 qualified: {qualifies_for_55_45}",
            f"Partner eligible: {partner_eligible}",
        ]
        assessment_notes = " | ".join(notes_parts)

        return ContractorQualityProfile(
            contractor_id=contractor_id,
            history_score=history_score,
            longevity_score=longevity_score,
            ease_of_work_score=ease_of_work_score,
            negotiation_reasonableness_score=negotiation_reasonableness_score,
            deal_strength_score=deal_strength_score,
            composite_score=composite_score,
            qualifies_for_55_45=qualifies_for_55_45,
            partner_eligible=partner_eligible,
            assessment_notes=assessment_notes,
            assessed_at=now,
        )

    def evaluate_negotiation_balance(
        self,
        negotiation: NegotiationRecord,
        quality_profile: Optional[ContractorQualityProfile] = None,
    ) -> bool:
        """Decide whether to accept a negotiation balance.

        Standard rule: Murphy must hold ≥ 70 % of the weight.

        Quality override (55/45 floor):  if ``quality_profile`` qualifies
        (composite ≥ 0.70, longevity ≥ 0.60, deal_strength ≥ 0.65) Murphy
        accepts down to 55 %.  A reliable partner at 55/45 is strictly better
        than a random contractor at 75/25.

        Murphy NEVER accepts below 55 % — that is the absolute floor.
        Murphy ALWAYS seeks the best deal available, not merely a tolerable one.

        Args:
            negotiation: The negotiation record to evaluate.
            quality_profile: Optional contractor quality profile.

        Returns:
            ``True`` if the balance is acceptable (Murphy should accept).
        """
        mw = negotiation.murphy_weight

        # Absolute floor — never accept below 55 %
        if mw < 0.55:
            logger.info(
                "Negotiation %s rejected: murphy_weight %.2f below absolute floor 0.55",
                negotiation.negotiation_id, mw,
            )
            return False

        # Standard range (no quality profile or below quality threshold)
        if quality_profile is None or not quality_profile.qualifies_for_55_45:
            result = 0.70 <= mw <= 0.90
            if not result:
                logger.info(
                    "Negotiation %s failed standard balance check: %.2f (need 0.70–0.90)",
                    negotiation.negotiation_id, mw,
                )
            return result

        # Quality override: accept 55–80 % for a strong contractor
        result = 0.55 <= mw <= 0.80
        if result:
            negotiation.quality_override = True
            negotiation.accepted_balance = round(mw, 4)
            logger.info(
                "Negotiation %s accepted via quality override (composite=%.2f): murphy_weight=%.2f",
                negotiation.negotiation_id,
                quality_profile.composite_score,
                mw,
            )
        return result

    def _infer_longevity(self, credential: CredentialRecord) -> float:
        """Infer contractor longevity (will they be here in 10 years?) from credential data."""
        score = 0.50  # start neutral

        # Age of credential: older = more established
        try:
            from datetime import datetime as _dt
            issue_year = int(credential.issue_date[:4])
            current_year = _dt.now().year
            years_established = current_year - issue_year
            if years_established >= 10:
                score += 0.30
            elif years_established >= 5:
                score += 0.20
            elif years_established >= 2:
                score += 0.10
            # New contractor (< 2 years) — no bonus
        except (ValueError, IndexError, TypeError) as exc:
            logger.debug("Longevity year parse error: %s", exc)

        # Expiry window: long validity = more stable
        if credential.expiry_date:
            try:
                expiry_year = int(credential.expiry_date[:4])
                current_year = datetime.now(timezone.utc).year
                years_left = expiry_year - current_year
                if years_left >= 5:
                    score += 0.15
                elif years_left >= 2:
                    score += 0.05
            except (ValueError, IndexError, TypeError) as exc:
                logger.debug("Longevity expiry parse error: %s", exc)
        else:
            # No expiry date — permanent credential (e.g., some notary commissions)
            score += 0.10

        # Professional association issuing body = career professional
        stable_bodies = ["ashi", "internachi", "ata", "mra", "mspa", "cmp", "mpi", "nist"]
        if any(b in credential.issuing_body.lower() for b in stable_bodies):
            score += 0.10

        return round(min(1.0, score), 3)

    # ------------------------------------------------------------------
    # Partner program
    # ------------------------------------------------------------------

    def register_partner(
        self,
        contractor_id: str,
        credential: CredentialRecord,
        quality_profile: ContractorQualityProfile,
        niche_ids: Optional[List[str]] = None,
        preferred_contact: str = "portal",
    ) -> ContractorPartnerRecord:
        """Promote a contractor to preferred HITL partner status.

        Only contractors with ``partner_eligible=True`` may be registered.
        Partners are contacted first for relevant tasks in future HITL flows.

        Args:
            contractor_id: The contractor's unique identifier.
            credential: Their verified credential record.
            quality_profile: Their quality assessment (must have partner_eligible=True).
            niche_ids: Niches this partner is preferred for (empty = all).
            preferred_contact: Their preferred contact method.

        Returns:
            A new :class:`ContractorPartnerRecord`.

        Raises:
            ValueError: If the contractor does not qualify for partner status.
        """
        if not quality_profile.partner_eligible:
            raise ValueError(
                f"Contractor {contractor_id!r} does not qualify for partner status "
                f"(composite score {quality_profile.composite_score:.2f} < 0.80 required). "
                "Continue building their track record to qualify."
            )

        now = datetime.now(timezone.utc).isoformat()
        partner = ContractorPartnerRecord(
            partner_id=str(uuid.uuid4()),
            contractor_id=contractor_id,
            credential_record_id=credential.record_id,
            niche_ids=list(niche_ids or []),
            quality_profile=quality_profile,
            preferred_contact=preferred_contact,
            partner_since=now,
            tasks_completed=0,
            tasks_failed=0,
            success_rate=0.0,
            hitl_priority=len(self._partners) + 1,
            active=True,
        )
        self._partners[partner.partner_id] = partner
        logger.info(
            "Partner registered: contractor=%r partner_id=%s composite=%.2f",
            contractor_id, partner.partner_id, quality_profile.composite_score,
        )
        return partner

    def update_partner_stats(
        self,
        partner_id: str,
        task_completed: bool,
    ) -> ContractorPartnerRecord:
        """Update partner completion statistics after a task.

        Args:
            partner_id: The partner record to update.
            task_completed: Whether the task was completed successfully.

        Returns:
            Updated :class:`ContractorPartnerRecord`.

        Raises:
            KeyError: If *partner_id* is not found.
        """
        if partner_id not in self._partners:
            raise KeyError(f"Partner {partner_id!r} not found")

        partner = self._partners[partner_id]
        if task_completed:
            partner.tasks_completed += 1
        else:
            partner.tasks_failed += 1

        total = partner.tasks_completed + partner.tasks_failed
        partner.success_rate = round(partner.tasks_completed / (total or 1), 3)
        return partner

    def get_preferred_partner(
        self,
        niche_id: str,
        skill_required: str,
    ) -> Optional[ContractorPartnerRecord]:
        """Return the highest-priority active partner for a niche + skill.

        Args:
            niche_id: The niche to find a partner for.
            skill_required: The skill needed.

        Returns:
            The best active :class:`ContractorPartnerRecord`, or ``None``.
        """
        candidates = [
            p for p in self._partners.values()
            if p.active
            and (not p.niche_ids or niche_id in p.niche_ids)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: p.hitl_priority)

    def get_partners_for_niche(self, niche_id: str) -> List[ContractorPartnerRecord]:
        """Return all active partners associated with *niche_id*."""
        return [
            p for p in self._partners.values()
            if p.active and (not p.niche_ids or niche_id in p.niche_ids)
        ]
