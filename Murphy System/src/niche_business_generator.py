"""
Niche Business Generator — Takes any niche description, runs it through
InferenceDomainGateEngine.infer(), applies the optimal MMSMM sequence,
and outputs a fully operational, autonomous Murphy-powered business spec.
Design Label: NBG-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from end_user_agreement import EUAAcceptanceMethod, EUADocument, EUAGenerator
from inference_gate_engine import InferenceDomainGateEngine, InferenceResult
from mss_controls import MSSController, TransformationResult
from mss_sequence_optimizer import OPTIMAL_SEQUENCE, MSSSequenceOptimizer
from niche_viability_gate import (
    ContractorPartnerRecord,
    ContractorQualityProfile,
    COYARecord,
    CredentialNegotiationEngine,
    CredentialRecord,
    DeployabilityStatus,
    HITLApprovalDecision,
    InoniLLCEntity,
    NegotiationRecord,
    NicheViabilityGate,
    RFPAnalysis,
    RFPGapAnalyzer,
    ViabilityResult,
)
from prompt_amplifier import AMPLIFIER_SEQUENCE, AmplifiedPrompt, PromptAmplifier
from simulation_engine import SimulationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NicheAutonomyClass(str, Enum):
    """Degree to which the niche business can operate without human intervention."""
    FULL_AUTONOMY = "full_autonomy"
    HYBRID = "hybrid"
    LEGS_REQUIRED = "legs_required"


class NicheRevenueModel(str, Enum):
    """Primary revenue model for a niche business."""
    SUBSCRIPTION = "subscription"
    TRANSACTION = "transaction"
    LEAD_GEN = "lead_gen"
    LISTING_FEE = "listing_fee"
    API_ACCESS = "api_access"
    FREEMIUM = "freemium"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NicheDefinition:
    """Definition of a niche business that Murphy can operate or power."""

    niche_id: str
    name: str
    description: str
    autonomy_class: NicheAutonomyClass
    revenue_model: NicheRevenueModel
    estimated_industries: List[str] = field(default_factory=list)
    murphy_modules_required: List[str] = field(default_factory=list)
    seed_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractorTask:
    """A task dispatched to a human contractor for physical-world execution."""

    task_id: str
    niche_id: str
    description: str
    location_required: bool
    skill_required: str
    estimated_duration_hours: float
    payment_amount: float
    status: str  # "pending", "dispatched", "submitted", "verified", "paid"
    gate_name: str  # which gate validates the contractor's submission


@dataclass
class NicheDeploymentSpec:
    """Fully operational Murphy-powered business spec for a niche."""

    niche_id: str
    niche_name: str
    inference_result: InferenceResult
    mss_sequence_used: str
    mss_results: List[TransformationResult]
    final_confidence: float
    agent_roster: Dict[str, Any]
    kpi_dataset: List[str]
    checkpoint_dataset: List[str]
    contractor_tasks: List[ContractorTask]
    deployment_ready: bool
    simulation_result: Optional[SimulationResult]
    dataset: Dict[str, Any]
    # Viability gate results (always populated when gate is run)
    viability_result: Optional[ViabilityResult] = None
    # Inoni LLC entity created by the viability gate
    inoni_entity: Optional[InoniLLCEntity] = None
    # End User Agreement for this niche deployment
    eua: Optional[EUADocument] = None
    # The amplified (MMMS→Solidify) version of the niche description used internally
    amplified_description: Optional[str] = None


# ---------------------------------------------------------------------------
# Contractor dispatch interface
# ---------------------------------------------------------------------------

class ContractorDispatchInterface:
    """Manages the lifecycle of contractor tasks from creation to payment."""

    def __init__(self) -> None:
        self._tasks: Dict[str, ContractorTask] = {}

    def create_task(
        self,
        niche_id: str,
        description: str,
        location_required: bool,
        skill_required: str,
        duration: float,
        payment: float,
        gate_name: str,
    ) -> ContractorTask:
        """Create and queue a new contractor task.

        Args:
            niche_id: The niche this task belongs to.
            description: Human-readable task description.
            location_required: Whether the contractor must be on-site.
            skill_required: Required skill or certification.
            duration: Estimated hours to complete the task.
            payment: Payment amount in USD.
            gate_name: Name of the gate that validates submission.

        Returns:
            A new :class:`ContractorTask` with status ``"pending"``.
        """
        task_id = str(uuid.uuid4())
        task = ContractorTask(
            task_id=task_id,
            niche_id=niche_id,
            description=description,
            location_required=location_required,
            skill_required=skill_required,
            estimated_duration_hours=duration,
            payment_amount=payment,
            status="pending",
            gate_name=gate_name,
        )
        self._tasks[task_id] = task
        return task

    def dispatch_task(self, task_id: str) -> ContractorTask:
        """Mark a task as dispatched to a contractor.

        Args:
            task_id: The UUID of the task to dispatch.

        Returns:
            The updated :class:`ContractorTask`.

        Raises:
            KeyError: If *task_id* does not exist.
        """
        task = self._tasks[task_id]
        task.status = "dispatched"
        return task

    def submit_result(self, task_id: str, result_data: Dict[str, Any]) -> ContractorTask:
        """Record a contractor's submission for a task.

        Args:
            task_id: The UUID of the task being submitted.
            result_data: Data submitted by the contractor.

        Returns:
            The updated :class:`ContractorTask` with status ``"submitted"``.

        Raises:
            KeyError: If *task_id* does not exist.
        """
        task = self._tasks[task_id]
        task.status = "submitted"
        logger.debug("Task %s submitted with %d data keys", task_id, len(result_data))
        return task

    def verify_submission(self, task_id: str) -> bool:
        """Gate-check a submitted contractor task.

        If the task is in ``"submitted"`` status, marks it as
        ``"verified"`` and returns ``True``.

        Args:
            task_id: The UUID of the task to verify.

        Returns:
            ``True`` if the task passed gate verification, ``False`` otherwise.
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == "submitted":
            task.status = "verified"
            return True
        return False

    def get_pending_tasks(self) -> List[ContractorTask]:
        """Return all tasks with status ``"pending"``."""
        return [t for t in self._tasks.values() if t.status == "pending"]

    def get_tasks_for_niche(self, niche_id: str) -> List[ContractorTask]:
        """Return all tasks belonging to a specific niche.

        Args:
            niche_id: The niche identifier to filter by.
        """
        return [t for t in self._tasks.values() if t.niche_id == niche_id]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

class NicheBusinessGenerator:
    """Meta-module that converts niche descriptions into fully operational
    Murphy-powered business specs.

    Args:
        mss_controller: A fully-initialised :class:`MSSController`.
        inference_engine: A fully-initialised :class:`InferenceDomainGateEngine`.
        sequence: The MSS sequence to use (default ``"MMSMM"``).
    """

    def __init__(
        self,
        mss_controller: MSSController,
        inference_engine: InferenceDomainGateEngine,
        sequence: str = OPTIMAL_SEQUENCE,
    ) -> None:
        self._controller = mss_controller
        self._engine = inference_engine
        self.sequence = sequence
        self._optimizer = MSSSequenceOptimizer(mss_controller)
        self._contractor_interface = ContractorDispatchInterface()
        # Viability gate — runs entirely internally using Murphy's own modules
        self._viability_gate = NicheViabilityGate(inference_engine, mss_controller)
        # RFP gap analyser — assesses what Murphy can vs. needs to generate per RFP
        self._rfp_analyzer = RFPGapAnalyzer(inference_engine, mss_controller)
        # Credential + negotiation engine — 75/25 COYA-documented contractor agreements
        self._credential_engine = CredentialNegotiationEngine()
        # Prompt amplifier — MMMS→Solidify filter on every incoming request
        self._prompt_amplifier = PromptAmplifier(mss_controller, inference_engine)
        # End user agreement generator
        self._eua_generator = EUAGenerator()
        self.NICHE_CATALOG: List[NicheDefinition] = self._build_catalog()

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def _build_catalog(self) -> List[NicheDefinition]:
        """Construct and return the 20-niche seed catalog."""
        return [
            # ---- Full autonomy niches (Murphy alone) ----
            NicheDefinition(
                niche_id="niche_seo_sites",
                name="SEO Content Site Generator",
                description=(
                    "SEO content site generator for niche industries, "
                    "auto-publishes optimized articles, monitors rankings"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["media", "marketing", "technology"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "seo_optimisation_engine", "content_pipeline_engine",
                    "adaptive_campaign_engine",
                ],
                seed_data={
                    "industry": "media",
                    "company_size": "small",
                    "primary_goal": "auto-publish SEO-optimized niche content",
                },
            ),
            NicheDefinition(
                niche_id="compliance_checklist",
                name="Compliance Checklist & Audit Platform",
                description=(
                    "Per-industry compliance checklist and audit platform, "
                    "auto-generated regulatory checklists for HIPAA SOX GDPR"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["legal", "healthcare", "finance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "compliance_engine", "form_intake", "governance_kernel",
                ],
                seed_data={
                    "industry": "legal",
                    "company_size": "small",
                    "primary_goal": "generate regulatory compliance checklists",
                },
            ),
            NicheDefinition(
                niche_id="niche_job_boards",
                name="Automated Niche Job Board Generator",
                description=(
                    "Automated niche job board generator, creates industry-specific "
                    "job boards with auto-generated listings and screening"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.LISTING_FEE,
                estimated_industries=["recruiting", "hr", "technology"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "onboarding_flow", "agent_action_builder",
                ],
                seed_data={
                    "industry": "recruiting",
                    "company_size": "small",
                    "primary_goal": "create and populate niche job boards automatically",
                },
            ),
            NicheDefinition(
                niche_id="kpi_dashboards",
                name="Industry-Specific KPI Dashboard Generator",
                description=(
                    "Industry-specific KPI monitoring dashboard generator, "
                    "auto-infers metrics per domain and builds tracking dashboards"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["technology", "manufacturing", "finance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "kpi_tracker", "analytics_dashboard", "agent_action_builder",
                ],
                seed_data={
                    "industry": "technology",
                    "company_size": "small",
                    "primary_goal": "infer and visualize domain-specific KPIs",
                },
            ),
            NicheDefinition(
                niche_id="newsletter_businesses",
                name="Automated Niche Newsletter Business",
                description=(
                    "Automated niche newsletter business, curates and writes "
                    "industry-specific newsletters with subscriber management"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["media", "marketing", "finance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "content_pipeline_engine", "adaptive_campaign_engine",
                    "sales_automation",
                ],
                seed_data={
                    "industry": "media",
                    "company_size": "small",
                    "primary_goal": "curate and distribute niche newsletters autonomously",
                },
            ),
            NicheDefinition(
                niche_id="template_generators",
                name="Niche Document and Template Generator",
                description=(
                    "Niche document and template generator, creates industry-specific "
                    "SOPs contracts policies and business templates"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["legal", "hr", "operations"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "agent_action_builder",
                ],
                seed_data={
                    "industry": "legal",
                    "company_size": "small",
                    "primary_goal": "generate niche-specific document templates",
                },
            ),
            NicheDefinition(
                niche_id="api_aggregators",
                name="Niche API Aggregation Platform",
                description=(
                    "Niche API aggregation platform, unifies industry-specific APIs "
                    "into single endpoints and sells access"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.API_ACCESS,
                estimated_industries=["technology", "finance", "healthcare"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "agentic_api_provisioner", "api_gateway_adapter",
                    "agent_action_builder",
                ],
                seed_data={
                    "industry": "technology",
                    "company_size": "small",
                    "primary_goal": "aggregate and resell niche API endpoints",
                },
            ),
            NicheDefinition(
                niche_id="niche_landing_pages",
                name="SaaS Landing Page Generator",
                description=(
                    "SaaS landing page generator for niche markets, creates optimized "
                    "marketing sites with A/B testing and lead capture"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.LEAD_GEN,
                estimated_industries=["marketing", "technology", "ecommerce"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "adaptive_campaign_engine", "sales_automation",
                    "competitive_intelligence_engine",
                ],
                seed_data={
                    "industry": "marketing",
                    "company_size": "small",
                    "primary_goal": "generate optimized niche landing pages with lead capture",
                },
            ),
            NicheDefinition(
                niche_id="onboarding_wizards",
                name="Industry-Specific Onboarding Wizard Generator",
                description=(
                    "Industry-specific business onboarding wizard generator, creates "
                    "guided setup flows for new businesses in any vertical"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.FREEMIUM,
                estimated_industries=["technology", "hr", "operations"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "onboarding_flow", "form_intake", "agent_action_builder",
                ],
                seed_data={
                    "industry": "technology",
                    "company_size": "small",
                    "primary_goal": "create guided onboarding flows for new vertical businesses",
                },
            ),
            NicheDefinition(
                niche_id="competitive_intel_sites",
                name="Automated Competitive Intelligence Platform",
                description=(
                    "Automated competitive intelligence platform per industry, "
                    "scrapes and analyzes competitor data and generates reports"
                ),
                autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["marketing", "technology", "finance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "competitive_intelligence_engine", "advanced_research",
                    "analytics_dashboard",
                ],
                seed_data={
                    "industry": "marketing",
                    "company_size": "small",
                    "primary_goal": "automate competitor data collection and analysis",
                },
            ),

            # ---- Hybrid niches (Murphy + contractors) ----
            NicheDefinition(
                niche_id="local_business_setup",
                name="Local Business Formation Service",
                description=(
                    "Local business formation service, Murphy generates business plans "
                    "and legal documents, contractors file paperwork at government offices"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["legal", "operations", "government"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "compliance_engine", "agent_action_builder",
                ],
                seed_data={
                    "industry": "legal",
                    "company_size": "small",
                    "primary_goal": "automate business formation with contractor filing",
                    "contractor_task_templates": [
                        {
                            "description": "File articles of incorporation at state office",
                            "location_required": True,
                            "skill_required": "registered_agent",
                            "duration_hours": 2.0,
                            "payment": 75.0,
                            "gate_name": "filing_confirmation_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="mystery_shopping",
                name="Mystery Shopping Network",
                description=(
                    "Mystery shopping network, Murphy designs audit criteria and "
                    "questionnaires, contractors perform in-person store visits and submit reports"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["retail", "hospitality", "quality_assurance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "agent_action_builder", "advanced_swarm_system",
                ],
                seed_data={
                    "industry": "retail",
                    "company_size": "small",
                    "primary_goal": "coordinate mystery shopping audits with field contractors",
                    "contractor_task_templates": [
                        {
                            "description": "Perform in-person mystery shop visit and submit report",
                            "location_required": True,
                            "skill_required": "mystery_shopper",
                            "duration_hours": 1.5,
                            "payment": 35.0,
                            "gate_name": "shop_report_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="market_research",
                name="Local Market Research Service",
                description=(
                    "Local market research service, Murphy designs surveys and analysis "
                    "frameworks, contractors gather field data through interviews and observations"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["marketing", "research", "consulting"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "advanced_research", "analytics_dashboard",
                ],
                seed_data={
                    "industry": "marketing",
                    "company_size": "small",
                    "primary_goal": "design and execute field market research via contractors",
                    "contractor_task_templates": [
                        {
                            "description": "Conduct field interviews and observations per research guide",
                            "location_required": True,
                            "skill_required": "market_researcher",
                            "duration_hours": 4.0,
                            "payment": 120.0,
                            "gate_name": "field_data_submission_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="property_inspection",
                name="Property and Asset Inspection Service",
                description=(
                    "Property and asset inspection service, Murphy generates checklists "
                    "and evaluation criteria, contractors inspect and photograph on-site"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["real_estate", "insurance", "construction"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "agent_action_builder", "compliance_engine",
                ],
                seed_data={
                    "industry": "real_estate",
                    "company_size": "small",
                    "primary_goal": "generate checklists and coordinate on-site property inspections",
                    "contractor_task_templates": [
                        {
                            "description": "Perform on-site property inspection and photo documentation",
                            "location_required": True,
                            "skill_required": "licensed_inspector",
                            "duration_hours": 3.0,
                            "payment": 150.0,
                            "gate_name": "inspection_report_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="lead_gen_with_closers",
                name="Lead Generation with In-Person Closers",
                description=(
                    "Lead generation with in-person closers, Murphy qualifies and scores "
                    "leads digitally, contractors close deals face-to-face"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.LEAD_GEN,
                estimated_industries=["sales", "real_estate", "insurance"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "sales_automation", "adaptive_campaign_engine",
                    "competitive_intelligence_engine",
                ],
                seed_data={
                    "industry": "sales",
                    "company_size": "small",
                    "primary_goal": "qualify leads digitally and dispatch closers for face-to-face conversion",
                    "contractor_task_templates": [
                        {
                            "description": "Visit qualified lead in person and close sale",
                            "location_required": True,
                            "skill_required": "sales_closer",
                            "duration_hours": 2.0,
                            "payment": 200.0,
                            "gate_name": "deal_closed_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="event_coordination",
                name="Niche Event Planning and Coordination",
                description=(
                    "Niche event planning and coordination, Murphy handles logistics "
                    "and scheduling, contractors execute on-site operations"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["events", "hospitality", "marketing"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "automation_scheduler", "agent_action_builder",
                    "advanced_swarm_system",
                ],
                seed_data={
                    "industry": "events",
                    "company_size": "small",
                    "primary_goal": "coordinate event logistics and dispatch on-site contractors",
                    "contractor_task_templates": [
                        {
                            "description": "Execute on-site event operations per Murphy logistics plan",
                            "location_required": True,
                            "skill_required": "event_coordinator",
                            "duration_hours": 8.0,
                            "payment": 300.0,
                            "gate_name": "event_completion_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="notary_network",
                name="Digital Notary Routing Network",
                description=(
                    "Digital notary routing network, Murphy manages document flow "
                    "and scheduling, notaries perform in-person witnessing"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["legal", "real_estate", "government"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "automation_scheduler", "agent_action_builder",
                ],
                seed_data={
                    "industry": "legal",
                    "company_size": "small",
                    "primary_goal": "route documents and schedule notaries for in-person signing",
                    "contractor_task_templates": [
                        {
                            "description": "Perform in-person notarization and return signed documents",
                            "location_required": True,
                            "skill_required": "commissioned_notary",
                            "duration_hours": 1.0,
                            "payment": 50.0,
                            "gate_name": "notarization_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="equipment_calibration",
                name="Equipment Calibration Scheduling Service",
                description=(
                    "Equipment calibration scheduling service, Murphy tracks schedules "
                    "and generates procedures, certified technicians perform calibration on-site"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.SUBSCRIPTION,
                estimated_industries=["manufacturing", "healthcare", "laboratory"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "automation_scheduler", "kpi_tracker", "compliance_engine",
                ],
                seed_data={
                    "industry": "manufacturing",
                    "company_size": "small",
                    "primary_goal": "automate calibration scheduling and dispatch certified technicians",
                    "contractor_task_templates": [
                        {
                            "description": "Perform on-site equipment calibration per Murphy-generated procedure",
                            "location_required": True,
                            "skill_required": "calibration_technician",
                            "duration_hours": 4.0,
                            "payment": 250.0,
                            "gate_name": "calibration_certificate_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="translation_verification",
                name="Translation Verification Service",
                description=(
                    "Translation verification service, LLM generates draft translations, "
                    "native speakers verify and localize content in person or remotely"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["media", "legal", "education"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "agent_action_builder", "true_swarm_system",
                ],
                seed_data={
                    "industry": "media",
                    "company_size": "small",
                    "primary_goal": "generate draft translations and route to native-speaker verifiers",
                    "contractor_task_templates": [
                        {
                            "description": "Review and verify LLM-generated translation for accuracy",
                            "location_required": False,
                            "skill_required": "native_speaker_translator",
                            "duration_hours": 2.0,
                            "payment": 80.0,
                            "gate_name": "translation_approval_gate",
                        }
                    ],
                },
            ),
            NicheDefinition(
                niche_id="permit_expediting",
                name="Government Permit Expediting Service",
                description=(
                    "Government permit expediting service, Murphy tracks requirements "
                    "and prepares applications, runners file at government offices"
                ),
                autonomy_class=NicheAutonomyClass.HYBRID,
                revenue_model=NicheRevenueModel.TRANSACTION,
                estimated_industries=["construction", "government", "legal"],
                murphy_modules_required=[
                    "inference_gate_engine", "mss_controls", "llm_controller",
                    "form_intake", "compliance_engine", "agent_action_builder",
                ],
                seed_data={
                    "industry": "construction",
                    "company_size": "small",
                    "primary_goal": "prepare permit applications and dispatch runners to file at government offices",
                    "contractor_task_templates": [
                        {
                            "description": "File permit application at government office and retrieve stamped copies",
                            "location_required": True,
                            "skill_required": "permit_runner",
                            "duration_hours": 3.0,
                            "payment": 100.0,
                            "gate_name": "permit_receipt_gate",
                        }
                    ],
                },
            ),
        ]

    # ------------------------------------------------------------------
    # Catalog access
    # ------------------------------------------------------------------

    def get_catalog(self) -> List[NicheDefinition]:
        """Return all niches in the catalog."""
        return list(self.NICHE_CATALOG)

    def get_niche(self, niche_id: str) -> Optional[NicheDefinition]:
        """Look up a niche by ID.

        Args:
            niche_id: The unique niche identifier.

        Returns:
            The matching :class:`NicheDefinition`, or ``None`` if not found.
        """
        for niche in self.NICHE_CATALOG:
            if niche.niche_id == niche_id:
                return niche
        return None

    # ------------------------------------------------------------------
    # Core generation pipeline
    # ------------------------------------------------------------------

    def generate_niche(
        self,
        niche: NicheDefinition,
        context: Optional[Dict[str, Any]] = None,
    ) -> NicheDeploymentSpec:
        """Run the full pipeline for a single niche and return its deployment spec.

        Pipeline:
          0. Amplify the niche description (MMMS→Solidify) — Murphy acts on the
             amplified version internally, not the raw description
          1. Viability gate (capability check, cost, profit, HITL request) — 100% internal
          2. Run ``inference_engine.infer(amplified_description, seed_data)``
          3. Call ``produce_dataset()`` for agent roster / KPIs / checkpoints
          4. Run the MMSMM sequence through the optimizer
          5. Generate contractor tasks for HYBRID / LEGS_REQUIRED niches
          6. Generate the End User Agreement for this niche
          7. Build and return a :class:`NicheDeploymentSpec` including viability result,
             Inoni LLC entity, and EUA

        ``deployment_ready`` is ``True`` only after the human operator has approved the
        HITL request via :meth:`approve_niche`.  Until then the spec is returned with
        ``deployment_ready=False`` so the operator can review and approve.

        Args:
            niche: The niche definition to generate a spec for.
            context: Optional context dictionary forwarded to MSS operations.

        Returns:
            A populated :class:`NicheDeploymentSpec`.
        """
        # ----------------------------------------------------------------
        # Step 0 — Amplify description (MMMS→Solidify filter)
        # Murphy always acts on the amplified version, never the raw prompt.
        # ----------------------------------------------------------------
        amplified = self._prompt_amplifier.amplify(niche.description, context)
        internal_description = amplified.amplified_prompt

        # ----------------------------------------------------------------
        # Step 1 — Viability gate (100% internal, no external contacts yet)
        # ----------------------------------------------------------------
        viability = self._viability_gate.evaluate(niche)

        # ----------------------------------------------------------------
        # Steps 2–5 — Full generation (always runs so the spec is ready for review)
        # ----------------------------------------------------------------

        # Step 2 — inference on the amplified description
        inference_result: InferenceResult = self._engine.infer(
            internal_description,
            existing_data=niche.seed_data,
        )

        # Step 3 — produce dataset
        dataset = inference_result.produce_dataset()
        agent_roster = dataset.get("agent_roster", [])
        kpi_dataset = [
            entry.get("metric", str(entry))
            for entry in dataset.get("kpi_dataset", [])
        ]
        checkpoint_dataset = [
            entry.get("gate_name", str(entry))
            for entry in dataset.get("checkpoint_dataset", [])
        ]

        # Step 4 — MMSMM sequence (on the amplified description)
        seq_result = self._optimizer.run_sequence(internal_description, self.sequence, context)
        mss_results = seq_result.steps + (
            [seq_result.final_result] if seq_result.final_result is not None else []
        )
        final_confidence = dataset.get("confidence", 0.6)
        simulation_result = (
            seq_result.final_result.simulation
            if seq_result.final_result is not None
            else None
        )

        # Step 5 — contractor tasks for hybrid niches
        contractor_tasks: List[ContractorTask] = []
        if niche.autonomy_class in (NicheAutonomyClass.HYBRID, NicheAutonomyClass.LEGS_REQUIRED):
            templates = niche.seed_data.get("contractor_task_templates", [])
            for tmpl in templates:
                task = self._contractor_interface.create_task(
                    niche_id=niche.niche_id,
                    description=tmpl.get("description", "Contractor task"),
                    location_required=tmpl.get("location_required", False),
                    skill_required=tmpl.get("skill_required", "general"),
                    duration=tmpl.get("duration_hours", 1.0),
                    payment=tmpl.get("payment", 50.0),
                    gate_name=tmpl.get("gate_name", "submission_gate"),
                )
                contractor_tasks.append(task)

        # Step 6 — End User Agreement
        autonomy_str = (
            niche.autonomy_class.value
            if hasattr(niche.autonomy_class, "value")
            else str(niche.autonomy_class)
        )
        revenue_str = (
            niche.revenue_model.value
            if hasattr(niche.revenue_model, "value")
            else str(niche.revenue_model)
        )
        requires_licensed = autonomy_str in ("hybrid", "legs_required")
        requires_physical = autonomy_str in ("hybrid", "legs_required")
        inoni_entity_name = (
            viability.inoni_entity.entity_name
            if viability.inoni_entity
            else f"Inoni {niche.name} LLC"
        )
        eua = self._eua_generator.generate(
            niche_id=niche.niche_id,
            niche_name=niche.name,
            inoni_entity_name=inoni_entity_name,
            autonomy_class=autonomy_str,
            revenue_model=revenue_str,
            murphy_modules_required=niche.murphy_modules_required,
            requires_licensed_professionals=requires_licensed,
            requires_physical_contractors=requires_physical,
        )

        # ----------------------------------------------------------------
        # Step 7 — Build spec
        # deployment_ready is True only if viability gate returned DEPLOYABLE,
        # which requires prior HITL approval with risk_accepted=True.
        # ----------------------------------------------------------------
        deployment_ready = (
            viability.deployability_status == DeployabilityStatus.DEPLOYABLE
        )

        return NicheDeploymentSpec(
            niche_id=niche.niche_id,
            niche_name=niche.name,
            inference_result=inference_result,
            mss_sequence_used=self.sequence,
            mss_results=mss_results,
            final_confidence=final_confidence,
            agent_roster={"agents": agent_roster},
            kpi_dataset=kpi_dataset,
            checkpoint_dataset=checkpoint_dataset,
            contractor_tasks=contractor_tasks,
            deployment_ready=deployment_ready,
            simulation_result=simulation_result,
            dataset=dataset,
            viability_result=viability,
            inoni_entity=viability.inoni_entity,
            eua=eua,
            amplified_description=internal_description,
        )

    def generate_all(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[NicheDeploymentSpec]:
        """Generate deployment specs for every niche in the catalog.

        Args:
            context: Optional context dictionary forwarded to each run.

        Returns:
            List of :class:`NicheDeploymentSpec`, one per niche.
        """
        specs: List[NicheDeploymentSpec] = []
        for niche in self.NICHE_CATALOG:
            try:
                spec = self.generate_niche(niche, context)
                specs.append(spec)
            except Exception as exc:
                logger.warning("Failed to generate niche %r: %s", niche.niche_id, exc)
        return specs

    def discover_niche(self, description: str) -> NicheDefinition:
        """Auto-create a :class:`NicheDefinition` from a free-text description.

        Pipeline:
          1. Use the inference engine to detect industry
          2. Score autonomy by counting physical-presence keywords
          3. Auto-assign revenue model based on industry

        Args:
            description: Free-text niche description.

        Returns:
            A new :class:`NicheDefinition` with inferred fields.
        """
        inference_result = self._engine.infer(description)
        industry = inference_result.inferred_industry

        # Score autonomy: count physical-presence indicators
        physical_keywords = [
            "on-site", "on site", "in-person", "in person", "physical",
            "location", "visit", "field", "inspect", "deliver", "install",
        ]
        lower_desc = description.lower()
        physical_score = sum(1 for kw in physical_keywords if kw in lower_desc)

        if physical_score >= 2:
            autonomy_class = NicheAutonomyClass.HYBRID
        else:
            autonomy_class = NicheAutonomyClass.FULL_AUTONOMY

        # Auto-assign revenue model
        industry_revenue_map: Dict[str, NicheRevenueModel] = {
            "technology": NicheRevenueModel.SUBSCRIPTION,
            "software": NicheRevenueModel.SUBSCRIPTION,
            "marketing": NicheRevenueModel.LEAD_GEN,
            "sales": NicheRevenueModel.TRANSACTION,
            "legal": NicheRevenueModel.TRANSACTION,
            "healthcare": NicheRevenueModel.SUBSCRIPTION,
            "finance": NicheRevenueModel.SUBSCRIPTION,
            "real_estate": NicheRevenueModel.TRANSACTION,
            "media": NicheRevenueModel.SUBSCRIPTION,
            "education": NicheRevenueModel.FREEMIUM,
        }
        revenue_model = industry_revenue_map.get(industry, NicheRevenueModel.TRANSACTION)

        niche_id = f"discovered_{str(uuid.uuid4())[:8]}"

        return NicheDefinition(
            niche_id=niche_id,
            name=description[:64].strip(),
            description=description,
            autonomy_class=autonomy_class,
            revenue_model=revenue_model,
            estimated_industries=[industry],
            murphy_modules_required=[
                "inference_gate_engine", "mss_controls", "llm_controller",
                "agent_action_builder",
            ],
            seed_data={
                "industry": industry,
                "company_size": "small",
                "primary_goal": description[:128],
            },
        )

    def validate_sequence(self, text: str) -> Dict[str, Any]:
        """Run the full test battery and return the ranking report.

        Use this to verify that MMSMM is still the optimal sequence.

        Args:
            text: Input text to run the battery against.

        Returns:
            A report dictionary with keys: ``winner``, ``top_5``, ``best_ratio``,
            ``best_family``, ``efficiency_winner``, ``diminishing_returns``.
        """
        results = self._optimizer.run_test_battery(text)
        return self._optimizer.generate_report(results)

    def get_contractor_interface(self) -> ContractorDispatchInterface:
        """Return the contractor dispatch interface."""
        return self._contractor_interface

    # ------------------------------------------------------------------
    # Viability gate access + HITL approval
    # ------------------------------------------------------------------

    def get_viability_gate(self) -> NicheViabilityGate:
        """Return the internal :class:`NicheViabilityGate` instance."""
        return self._viability_gate

    def approve_niche(
        self,
        request_id: str,
        decided_by: str,
        notes: str = "",
        risk_accepted: bool = False,
        conditions: Optional[List[str]] = None,
    ) -> HITLApprovalDecision:
        """Approve an HITL deployment request for a niche.

        The operator MUST set ``risk_accepted=True`` — this is their explicit
        acknowledgment that they accept financial and operational responsibility
        for this Inoni LLC deployment.  After approval Murphy is authorised to
        make external contacts (contractor dispatch, APIs, deliveries).

        Args:
            request_id: The HITL request UUID to approve.
            decided_by: Operator identifier (e.g. ``"corey_post"``).
            notes: Optional approval notes.
            risk_accepted: Must be ``True`` — the approver accepts the RFP risk.
            conditions: Optional list of conditions attached to the approval.

        Returns:
            The recorded :class:`HITLApprovalDecision`.
        """
        return self._viability_gate.approve_hitl_request(
            request_id=request_id,
            decided_by=decided_by,
            notes=notes,
            risk_accepted=risk_accepted,
            conditions=conditions,
        )

    # ------------------------------------------------------------------
    # RFP gap analysis
    # ------------------------------------------------------------------

    def analyze_rfp(
        self,
        rfp_text: str,
        niche_id: str,
    ) -> Optional[RFPAnalysis]:
        """Analyse an incoming RFP against the niche's generation capabilities.

        Determines what Murphy can generate fully, what needs a credentialed
        contractor, and what cannot be delivered.  Produces a stealth quote
        at 75 % of the human rate for the same work.

        Args:
            rfp_text: The raw RFP text received by the niche business.
            niche_id: The niche business receiving the RFP.

        Returns:
            A populated :class:`RFPAnalysis`, or ``None`` if the niche is not found.
        """
        niche = self.get_niche(niche_id)
        if niche is None:
            logger.warning("analyze_rfp: niche %r not found", niche_id)
            return None
        return self._rfp_analyzer.analyze(rfp_text, niche)

    # ------------------------------------------------------------------
    # Credential + negotiation engine (COYA)
    # ------------------------------------------------------------------

    def get_credential_engine(self) -> CredentialNegotiationEngine:
        """Return the internal :class:`CredentialNegotiationEngine`."""
        return self._credential_engine

    def negotiate_contractor(
        self,
        request_id: str,
        human_response: Dict[str, Any],
    ) -> NegotiationRecord:
        """Build a 75/25 negotiation record from a contractor's response.

        Args:
            request_id: The credentialed HITL request being negotiated.
            human_response: Dict with optional keys ``rate``, ``preferred_contact``,
                            ``schedule_note``.

        Returns:
            A populated :class:`NegotiationRecord`.
        """
        return self._credential_engine.build_negotiation(request_id, human_response)

    def record_contractor_credentials(
        self,
        request_id: str,
        credential_data: Dict[str, Any],
    ) -> CredentialRecord:
        """Record credentials provided by a contractor in response to an HITL request.

        Args:
            request_id: The credentialed HITL request this responds to.
            credential_data: Dict with keys ``holder_name``, ``credential_number``,
                             ``issue_date``, and optionally ``expiry_date``,
                             ``masked_as``.

        Returns:
            A populated :class:`CredentialRecord`.
        """
        return self._credential_engine.record_credentials(request_id, credential_data)

    def get_coya_records(self, niche_id: str) -> List[COYARecord]:
        """Return all COYA documentation records for a niche.

        Args:
            niche_id: The niche to retrieve records for.

        Returns:
            List of :class:`COYARecord` instances (may be empty).
        """
        return self._credential_engine.get_coya_records_for_niche(niche_id)

    # ------------------------------------------------------------------
    # Prompt amplifier (MMMS→Solidify filter)
    # ------------------------------------------------------------------

    def amplify_prompt(
        self,
        raw_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AmplifiedPrompt:
        """Amplify a raw prompt through the MMMS→Solidify filter.

        Every prompt Murphy acts on internally is amplified first.  This method
        exposes the amplifier for external callers (e.g., to preview what Murphy
        will actually process before committing to a generation run).

        Args:
            raw_prompt: The raw user prompt or request text.
            context: Optional context dict.

        Returns:
            An :class:`AmplifiedPrompt` — ``.amplified_prompt`` is what Murphy uses.
        """
        return self._prompt_amplifier.amplify(raw_prompt, context)

    # ------------------------------------------------------------------
    # End User Agreement
    # ------------------------------------------------------------------

    def get_eua(self, niche_id: str) -> Optional[EUADocument]:
        """Return the End User Agreement for a niche deployment spec.

        The EUA is generated as part of :meth:`generate_niche`.  This method
        provides a quick lookup by niche ID by generating a fresh EUA if one
        is not already attached to the spec.

        Args:
            niche_id: The niche to retrieve the EUA for.

        Returns:
            A :class:`EUADocument`, or ``None`` if the niche is not found.
        """
        niche = self.get_niche(niche_id)
        if niche is None:
            return None
        autonomy_str = (
            niche.autonomy_class.value
            if hasattr(niche.autonomy_class, "value")
            else str(niche.autonomy_class)
        )
        revenue_str = (
            niche.revenue_model.value
            if hasattr(niche.revenue_model, "value")
            else str(niche.revenue_model)
        )
        return self._eua_generator.generate(
            niche_id=niche.niche_id,
            niche_name=niche.name,
            inoni_entity_name=f"Inoni {niche.name} LLC",
            autonomy_class=autonomy_str,
            revenue_model=revenue_str,
            murphy_modules_required=niche.murphy_modules_required,
            requires_licensed_professionals=autonomy_str in ("hybrid", "legs_required"),
            requires_physical_contractors=autonomy_str in ("hybrid", "legs_required"),
        )

    # ------------------------------------------------------------------
    # Contractor quality scoring + partner program
    # ------------------------------------------------------------------

    def score_contractor(
        self,
        contractor_id: str,
        request_id: str,
        credential_record: Any,
        past_coya_niche_id: Optional[str] = None,
    ) -> ContractorQualityProfile:
        """Score a contractor's quality for negotiation and partner eligibility.

        Args:
            contractor_id: The contractor to score.
            request_id: The credentialed HITL request that has a negotiation.
            credential_record: The contractor's :class:`CredentialRecord`.
            past_coya_niche_id: If provided, include past COYA records from this niche.

        Returns:
            A :class:`ContractorQualityProfile`.
        """
        past_coya = []
        if past_coya_niche_id:
            past_coya = self._credential_engine.get_coya_records_for_niche(past_coya_niche_id)
        negotiation = self._credential_engine._negotiations.get(request_id)
        if negotiation is None:
            # No negotiation yet — create a minimal scoring based on credentials only
            from datetime import datetime, timezone

            from niche_viability_gate import NegotiationRecord, NegotiationStance, NegotiationTerm
            dummy_neg = NegotiationRecord(
                negotiation_id=f"dummy_{request_id}",
                request_id=request_id,
                niche_id="unknown",
                murphy_terms=[],
                human_terms=[],
                murphy_weight=0.75,
                human_weight=0.25,
                balance_valid=True,
                agreed_at=datetime.now(timezone.utc).isoformat(),
                total_terms=0,
                scope_summary="Pre-negotiation scoring",
            )
            negotiation = dummy_neg
        return self._credential_engine.score_contractor(
            contractor_id, negotiation, credential_record, past_coya
        )

    def promote_contractor_to_partner(
        self,
        contractor_id: str,
        credential_record: Any,
        quality_profile: ContractorQualityProfile,
        niche_ids: Optional[List[str]] = None,
    ) -> ContractorPartnerRecord:
        """Promote a qualified contractor to preferred HITL partner status.

        Args:
            contractor_id: The contractor to promote.
            credential_record: Their verified :class:`CredentialRecord`.
            quality_profile: Their :class:`ContractorQualityProfile`
                             (must have ``partner_eligible=True``).
            niche_ids: Niches this partner is preferred for.

        Returns:
            A new :class:`ContractorPartnerRecord`.
        """
        return self._credential_engine.register_partner(
            contractor_id, credential_record, quality_profile, niche_ids
        )

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
            The best :class:`ContractorPartnerRecord`, or ``None``.
        """
        return self._credential_engine.get_preferred_partner(niche_id, skill_required)
