"""
RosettaDocumentBuilder — builds a RosettaDocument from onboarding data.

The builder wires together the existing system components:
  - InferenceDomainGateEngine.infer_via_llm() or .infer() for domain locking
  - BusinessScalingEngine for revenue/unit-economics analysis
  - HITLAutonomyController for HITL toggle state
  - ShadowAgentIntegration for shadow agent binding
  - MSSController (magnify/simplify/solidify) for task pipeline construction

Usage::

    builder = RosettaDocumentBuilder()

    # Minimal — just a description, let the builder infer everything
    doc = builder.build(
        agent_id="acme-field-tech-01",
        agent_name="Field Technician Agent — Acme Plumbing",
        business_description="Plumbing and drain cleaning service in Austin TX",
        agent_type="shadow",
        role_title="Field Technician",
        shadowed_user_id="user_jsmith",
        shadowed_user_name="John Smith",
    )

    # Full — with business plan math and HITL models
    doc = builder.build(
        agent_id="acme-exec-01",
        agent_name="Executive Planning Agent — Acme Plumbing",
        business_description="Plumbing and drain cleaning service in Austin TX",
        agent_type="automation",
        role_title="Operations Director",
        management_layer="executive",
        revenue_goal=2_000_000.0,
        unit_price=5_000.0,
        annual_cost=600_000.0,
        timeline_months=12.0,
        conversion_rate_goal=0.9999,
        conversion_rate_actual=0.2999,
        hitl_task_types=[
            {"task_type": "work_order_approval", "base_tasks_per_day": 20.0,
             "validator_count": 2, "hitl_enabled": True},
            {"task_type": "invoice_review", "base_tasks_per_day": 30.0,
             "validator_count": 1, "hitl_enabled": True},
        ],
        raw_goals=[
            "Grow service area to cover all of Austin",
            "Reduce invoice collection lag below 14 days",
            "Hire 3 more field technicians by Q3",
        ],
    )

    # Read document before acting
    recommendation = doc.business_recommendation()
    for task in doc.next_tasks():
        summary = (task.title, task.success_metric)  # noqa: T201
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .rosetta_models import (
    AgentType,
    BusinessPlanMath,
    DayOfWeekFactor,
    EmployeeContract,
    HITLThroughputModel,
    Identity,
    IndustryTerminology,
    MagnifySimplifyTask,
    ManagementLayer,
    Metadata,
    RosettaAgentState,
    RosettaDocument,
    StateFeed,
    StateFeedEntry,
    TaskPipeline,
    TaskPipelineStage,
    TermDefinition,
    UnitEconomics,
)

logger = logging.getLogger(__name__)

# Maximum characters to store as the business_type description snapshot.
# Long free-text descriptions are truncated to keep the Rosetta document compact.
_MAX_BUSINESS_TYPE_LENGTH = 120

# ---------------------------------------------------------------------------
# Industry terminology banks
# Agents get this locked vocabulary at build time.  The LLM inference path
# enriches it further; this provides the deterministic baseline.
# ---------------------------------------------------------------------------

_TERMINOLOGY_BANKS: Dict[str, List[Dict[str, Any]]] = {
    "trade_services": [
        {"term": "work order", "definition": "An authorised job assigned to a field technician",
         "aliases": ["WO", "job ticket", "service ticket"], "category": "process"},
        {"term": "dispatch", "definition": "Scheduling and routing technicians to jobs",
         "aliases": ["scheduling", "routing"], "category": "process"},
        {"term": "estimate", "definition": "A pre-job cost breakdown provided to the customer",
         "aliases": ["quote", "proposal"], "category": "product"},
        {"term": "invoice", "definition": "Post-job billing document sent to the customer",
         "aliases": ["bill", "statement"], "category": "product"},
        {"term": "conversion rate", "definition": "Percentage of estimates that become paid jobs",
         "aliases": ["close rate", "win rate"], "category": "metric"},
        {"term": "pipeline", "definition": "Open estimates not yet converted to paid jobs",
         "aliases": ["open quotes", "pending jobs"], "category": "metric"},
    ],
    "professional_services": [
        {"term": "engagement", "definition": "A consulting project with a defined scope and fee",
         "aliases": ["project", "mandate"], "category": "process"},
        {"term": "SOW", "definition": "Statement of Work — defines deliverables and timeline",
         "aliases": ["scope document", "statement of work"], "category": "product"},
        {"term": "utilisation rate", "definition": "Billable hours as a percentage of available hours",
         "aliases": ["billable rate", "utilisation"], "category": "metric"},
        {"term": "retainer", "definition": "A monthly recurring fee for ongoing advisory services",
         "aliases": ["monthly fee", "monthly retainer"], "category": "product"},
    ],
    "technology": [
        {"term": "seat", "definition": "A per-user SaaS subscription unit",
         "aliases": ["license", "user license"], "category": "product"},
        {"term": "MRR", "definition": "Monthly Recurring Revenue",
         "aliases": ["monthly recurring revenue"], "category": "metric"},
        {"term": "ARR", "definition": "Annual Recurring Revenue",
         "aliases": ["annual recurring revenue"], "category": "metric"},
        {"term": "churn", "definition": "Customers who cancel their subscription in a period",
         "aliases": ["churn rate", "attrition"], "category": "metric"},
        {"term": "CAC", "definition": "Customer Acquisition Cost",
         "aliases": ["cost to acquire", "acquisition cost"], "category": "metric"},
        {"term": "LTV", "definition": "Lifetime Value of a customer",
         "aliases": ["lifetime value", "CLV", "customer lifetime value"], "category": "metric"},
    ],
    "construction": [
        {"term": "bid", "definition": "A competitive price proposal for a construction project",
         "aliases": ["proposal", "tender"], "category": "product"},
        {"term": "change order", "definition": "A formal amendment to the original contract scope or price",
         "aliases": ["CO", "variation"], "category": "process"},
        {"term": "punch list", "definition": "Final checklist of outstanding items before project closeout",
         "aliases": ["snag list", "closeout list"], "category": "process"},
        {"term": "job number", "definition": "Unique identifier for a construction project",
         "aliases": ["project number", "job ID"], "category": "process"},
    ],
    "healthcare": [
        {"term": "patient encounter", "definition": "A billable clinical visit or procedure",
         "aliases": ["visit", "appointment", "encounter"], "category": "process"},
        {"term": "prior authorisation", "definition": "Insurance approval required before delivering care",
         "aliases": ["prior auth", "PA"], "category": "process"},
        {"term": "claim", "definition": "A billing submission to an insurance payer",
         "aliases": ["insurance claim", "billing claim"], "category": "product"},
        {"term": "HIPAA", "definition": "US healthcare privacy and security regulation",
         "aliases": ["health privacy"], "category": "metric"},
    ],
    "general": [],
}

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "trade_services": [
        "plumbing", "hvac", "electrical", "roofing", "handyman", "drain", "pipe",
        "technician", "work order", "dispatch", "estimate", "invoice", "service call",
    ],
    "professional_services": [
        "consulting", "advisory", "engagement", "retainer", "utilisation", "billable",
        "SOW", "deliverable", "strategy", "analysis",
    ],
    "technology": [
        "saas", "software", "api", "cloud", "seat", "mrr", "arr", "churn", "ltv",
        "cac", "sprint", "deployment", "integration",
    ],
    "construction": [
        "bid", "contract", "subcontractor", "site", "blueprint", "permit", "inspection",
        "change order", "punch list", "job number", "project number",
    ],
    "healthcare": [
        "patient", "clinical", "diagnosis", "hipaa", "prior auth", "claim", "ehr",
        "medication", "appointment", "encounter",
    ],
    "general": [],
}


class RosettaDocumentBuilder:
    """
    Builds a RosettaDocument from onboarding data.

    Wires together:
      - InferenceDomainGateEngine  (domain + gate inference)
      - BusinessScalingEngine      (revenue / unit economics)
      - HITLAutonomyController     (HITL toggle state)
      - MSSController              (magnify/simplify/solidify for task list)
      - ShadowAgentIntegration     (shadow agent binding)

    Falls back gracefully when any dependency is unavailable.
    """

    def __init__(
        self,
        gate_engine: Any = None,
        scaling_engine: Any = None,
        hitl_controller: Any = None,
        mss_controller: Any = None,
        shadow_integration: Any = None,
        llm_backend: Any = None,
    ) -> None:
        self._gate_engine = gate_engine
        self._scaling = scaling_engine
        self._hitl_ctrl = hitl_controller
        self._mss = mss_controller
        self._shadow = shadow_integration
        self._llm = llm_backend

        # Lazy-load heavy dependencies only if not injected
        if self._gate_engine is None:
            try:
                from src.inference_gate_engine import InferenceDomainGateEngine
                self._gate_engine = InferenceDomainGateEngine()
            except Exception as exc:
                logger.warning("InferenceDomainGateEngine unavailable: %s", exc)

        if self._scaling is None:
            try:
                from business_scaling_engine import BusinessScalingEngine
                self._scaling = BusinessScalingEngine()
            except Exception as exc:
                logger.warning("BusinessScalingEngine unavailable: %s", exc)

        if self._hitl_ctrl is None:
            try:
                from hitl_autonomy_controller import HITLAutonomyController
                self._hitl_ctrl = HITLAutonomyController()
            except Exception as exc:
                logger.warning("HITLAutonomyController unavailable: %s", exc)

        if self._mss is None:
            try:
                from mss_controls import MSSController
                self._mss = MSSController()
            except Exception as exc:
                logger.warning("MSSController unavailable: %s", exc)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build(
        self,
        agent_id: str,
        agent_name: str,
        business_description: str,
        agent_type: str = "automation",
        role_title: str = "",
        role_description: str = "",
        management_layer: str = "individual",
        department: str = "",
        location: str = "",
        organisation_id: str = "",
        shadowed_user_id: Optional[str] = None,
        shadowed_user_name: Optional[str] = None,
        authorised_actions: Optional[List[str]] = None,
        work_order_scope: str = "assigned",
        reports_to: Optional[str] = None,
        direct_reports: Optional[List[str]] = None,
        # Business plan inputs
        revenue_goal: Optional[float] = None,
        unit_price: Optional[float] = None,
        annual_cost: float = 0.0,
        timeline_months: float = 12.0,
        conversion_rate_goal: float = 1.0,
        conversion_rate_actual: float = 1.0,
        current_quarter: int = 1,
        quarters_elapsed: float = 0.0,
        units_closed: float = 0.0,
        pipeline_units: float = 0.0,
        # HITL models
        hitl_task_types: Optional[List[Dict[str, Any]]] = None,
        # Initial goals for task pipeline seeding
        raw_goals: Optional[List[str]] = None,
        # Extra state feed entries
        initial_state: Optional[List[Dict[str, Any]]] = None,
    ) -> RosettaDocument:
        """
        Build and return a fully populated RosettaDocument.

        Parameters
        ----------
        agent_id, agent_name : str
            Unique identifier and display name for this agent.
        business_description : str
            Free-text description of the business (used for domain inference).
        agent_type : str
            "shadow" or "automation".
        role_title : str
            The agent's job title within the organisation.
        management_layer : str
            "executive", "middle", or "individual".
        shadowed_user_id, shadowed_user_name : str | None
            Required for shadow agents.
        revenue_goal, unit_price : float | None
            If both provided, BusinessPlanMath is computed and attached.
        hitl_task_types : list[dict] | None
            Each dict: task_type, base_tasks_per_day, validator_count,
            avg_task_duration_minutes, hitl_enabled, llm_peer_review_eligible.
        raw_goals : list[str] | None
            Plain-English goals that seed the task pipeline (Magnify×1 pass).
        initial_state : list[dict] | None
            Initial StateFeedEntry dicts: {metric_name, value, unit, target}.
        """
        _agent_type = AgentType(agent_type)
        _mgmt_layer = ManagementLayer(management_layer)

        # 1. Build EmployeeContract
        contract = EmployeeContract(
            agent_type=_agent_type,
            role_title=role_title or "Agent",
            role_description=role_description,
            management_layer=_mgmt_layer,
            department=department,
            location=location,
            organisation_id=organisation_id,
            shadowed_user_id=shadowed_user_id,
            shadowed_user_name=shadowed_user_name,
            authorised_actions=authorised_actions or [],
            work_order_scope=work_order_scope,
            reports_to=reports_to,
            direct_reports=direct_reports or [],
        )

        # 2. Infer industry + terminology
        terminology = self._build_terminology(business_description)

        # 3. Build StateFeed from initial_state entries
        state_feed = StateFeed()
        for entry_dict in (initial_state or []):
            state_feed.push(StateFeedEntry(**entry_dict))

        # 4. Build BusinessPlanMath if revenue inputs provided
        business_plan: Optional[BusinessPlanMath] = None
        if revenue_goal is not None and unit_price is not None and unit_price > 0:
            business_plan = self._build_business_plan(
                revenue_goal=revenue_goal,
                unit_price=unit_price,
                annual_cost=annual_cost,
                timeline_months=timeline_months,
                conversion_rate_goal=conversion_rate_goal,
                conversion_rate_actual=conversion_rate_actual,
                current_quarter=current_quarter,
                quarters_elapsed=quarters_elapsed,
                units_closed=units_closed,
                pipeline_units=pipeline_units,
            )

        # 5. Build HITLThroughputModels
        hitl_models = self._build_hitl_models(hitl_task_types or [])

        # 6. Seed task pipeline from raw goals
        task_pipeline = self._build_task_pipeline(
            raw_goals=raw_goals or [],
            role_title=role_title,
            management_layer=_mgmt_layer,
            terminology=terminology,
            business_plan=business_plan,
        )

        # 7. Build base RosettaAgentState (lightweight)
        base_state = RosettaAgentState(
            identity=Identity(
                agent_id=agent_id,
                name=agent_name,
                role=role_title,
                organisation=organisation_id,
            ),
            metadata=Metadata(),
        )

        return RosettaDocument(
            agent_id=agent_id,
            agent_name=agent_name,
            contract=contract,
            terminology=terminology,
            state_feed=state_feed,
            business_plan=business_plan,
            task_pipeline=task_pipeline,
            hitl_models=hitl_models,
            base_state=base_state,
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build_terminology(self, description: str) -> IndustryTerminology:
        """
        Derive IndustryTerminology from the business description.

        Primary path: InferenceDomainGateEngine.infer_via_llm() or .infer()
        Fallback: heuristic industry classification from description keywords.
        """
        industry = "general"
        if self._gate_engine is not None:
            try:
                if self._llm is not None and hasattr(self._gate_engine, "infer_via_llm"):
                    result = self._gate_engine.infer_via_llm(description, self._llm)
                else:
                    result = self._gate_engine.infer(description)
                industry = result.inferred_industry
            except Exception as exc:
                logger.warning("Gate engine inference failed (%s); using heuristic", exc)
                industry = self._heuristic_industry(description)
        else:
            industry = self._heuristic_industry(description)

        term_defs = [
            TermDefinition(**t)
            for t in _TERMINOLOGY_BANKS.get(industry, _TERMINOLOGY_BANKS["general"])
        ]
        domain_keywords = _DOMAIN_KEYWORDS.get(industry, [])

        return IndustryTerminology(
            industry=industry,
            business_type=description[:_MAX_BUSINESS_TYPE_LENGTH],
            domain_keywords=domain_keywords,
            terms=term_defs,
        )

    @staticmethod
    def _heuristic_industry(description: str) -> str:
        """Lightweight fallback — check description against keyword banks."""
        desc = description.lower()
        best_industry, best_score = "general", 0
        for industry, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in desc)
            if score > best_score:
                best_industry, best_score = industry, score
        return best_industry

    @staticmethod
    def _build_business_plan(
        revenue_goal: float,
        unit_price: float,
        annual_cost: float,
        timeline_months: float,
        conversion_rate_goal: float,
        conversion_rate_actual: float,
        current_quarter: int,
        quarters_elapsed: float,
        units_closed: float,
        pipeline_units: float,
    ) -> BusinessPlanMath:
        ue = UnitEconomics(
            revenue_goal_dollars=revenue_goal,
            unit_price_dollars=unit_price,
            annual_cost_dollars=annual_cost,
            timeline_months=timeline_months,
            conversion_rate_goal=conversion_rate_goal,
            conversion_rate_actual=conversion_rate_actual,
        )
        return BusinessPlanMath(
            unit_economics=ue,
            current_quarter=current_quarter,
            quarters_elapsed=quarters_elapsed,
            units_closed_to_date=units_closed,
            pipeline_units=pipeline_units,
        )

    @staticmethod
    def _build_hitl_models(
        hitl_task_types: List[Dict[str, Any]],
    ) -> List[HITLThroughputModel]:
        """
        Build HITLThroughputModel list from caller-supplied dicts.

        Each dict must have 'task_type' and 'base_tasks_per_day'.
        Optional: validator_count, avg_task_duration_minutes, hitl_enabled,
        llm_peer_review_eligible, llm_confidence_threshold.

        Default day-of-week factors are applied if not supplied:
          Monday (0): 0.85  — slower start of week
          Friday (4): 0.80  — end-of-week wind-down
          Saturday (5): 0.0 — weekend
          Sunday (6): 0.0   — weekend
        """
        _default_dow = [
            DayOfWeekFactor(day=0, factor=0.85, label="Monday"),
            DayOfWeekFactor(day=4, factor=0.80, label="Friday"),
            DayOfWeekFactor(day=5, factor=0.0, label="Saturday"),
            DayOfWeekFactor(day=6, factor=0.0, label="Sunday"),
        ]
        models = []
        for spec in hitl_task_types:
            models.append(HITLThroughputModel(
                task_type=spec["task_type"],
                base_tasks_per_day=float(spec["base_tasks_per_day"]),
                validator_count=int(spec.get("validator_count", 1)),
                avg_task_duration_minutes=float(spec.get("avg_task_duration_minutes", 15.0)),
                day_of_week_factors=spec.get("day_of_week_factors", _default_dow),
                holiday_buffer_days_per_month=float(
                    spec.get("holiday_buffer_days_per_month", 2.0)
                ),
                hitl_enabled=bool(spec.get("hitl_enabled", True)),
                llm_peer_review_eligible=bool(spec.get("llm_peer_review_eligible", False)),
                llm_confidence_threshold=float(
                    spec.get("llm_confidence_threshold", 0.85)
                ),
            ))
        return models

    def _build_task_pipeline(
        self,
        raw_goals: List[str],
        role_title: str,
        management_layer: ManagementLayer,
        terminology: IndustryTerminology,
        business_plan: Optional[BusinessPlanMath],
    ) -> TaskPipeline:
        """
        Convert raw goal strings into MagnifySimplifyTask entries.

        Pipeline stages applied here:
          MAGNIFY_1  — each raw goal is expanded into a task
          MAGNIFY_2  — business plan math is injected into relevant tasks
                       (success_value, success_unit derived from units_per_month)
          DOMAIN_FILTER — tasks are scored against IndustryTerminology.domain_keywords
          SOLIDIFY   — tasks that pass the domain filter are solidified

        In production, the MSSController drives the full 5-pass pipeline
        (Magnify×3, Simplify, Magnify×2).  Here we do a lightweight 3-pass
        using string heuristics so the builder works without a live LLM.
        The caller can upgrade by passing an mss_controller.
        """
        pipeline = TaskPipeline()

        for goal_text in raw_goals:
            task_id = f"task_{uuid.uuid4().hex[:10]}"

            # --- MAGNIFY_1: expand the raw goal into a concrete task ---
            expanded = self._magnify_goal(goal_text, role_title, terminology)

            task = MagnifySimplifyTask(
                task_id=task_id,
                title=expanded["title"],
                description=expanded["description"],
                stage=TaskPipelineStage.MAGNIFY_1,
                assigned_role=role_title,
                management_layer=management_layer,
                success_metric=expanded["success_metric"],
                success_value=expanded.get("success_value"),
                success_unit=expanded.get("success_unit", ""),
                priority=expanded.get("priority", 3),
                source_goal_id=None,
            )

            # --- MAGNIFY_2: inject business plan math into metric-bearing tasks ---
            if business_plan is not None:
                task = self._inject_business_math(task, business_plan)
                task.stage = TaskPipelineStage.MAGNIFY_2

            # --- DOMAIN_FILTER: score task against domain keywords ---
            task.domain_fit_score = self._score_domain_fit(task, terminology)

            if not task.is_on_domain:
                task.stage = TaskPipelineStage.REJECTED
                logger.debug("Task '%s' rejected by domain filter (score=%.2f)",
                             task.title, task.domain_fit_score)
                pipeline.add(task)
                continue

            # --- SOLIDIFY: lock the task ---
            task.stage = TaskPipelineStage.SOLIDIFIED
            task.solidified_at = datetime.now(timezone.utc)
            pipeline.add(task)

        return pipeline

    # -- Task expansion helpers ------------------------------------------

    @staticmethod
    def _magnify_goal(
        goal_text: str,
        role_title: str,
        terminology: IndustryTerminology,
    ) -> Dict[str, Any]:
        """
        Lightweight Magnify pass: extract a concrete task + success metric
        from a plain-English goal string.

        In production the MSSController.magnify() call replaces this.
        This deterministic version covers the builder's offline path.
        """
        goal_lower = goal_text.lower()

        # Revenue / sales / growth goals → quantified targets
        if any(kw in goal_lower for kw in ("revenue", "sales", "grow", "close", "customers", "seats")):
            return {
                "title": f"Grow revenue — {goal_text}",
                "description": goal_text,
                "success_metric": "units_per_month from business plan",
                "success_unit": "units",
                "priority": 2,
            }

        # Marketing / conversion / pipeline goals
        if any(kw in goal_lower for kw in ("market", "prospect", "convert", "lead", "pipeline")):
            return {
                "title": f"Marketing outreach — {goal_text}",
                "description": goal_text,
                "success_metric": "prospect_reach_needed_per_month from business plan",
                "success_unit": "prospects",
                "priority": 2,
            }

        # Operations / work order / field goals
        if any(kw in goal_lower for kw in ("work order", "dispatch", "schedule", "technician",
                                            "field", "invoice", "collect", "billing")):
            return {
                "title": f"Operations task — {goal_text}",
                "description": goal_text,
                "success_metric": "completion rate ≥ 95%",
                "success_unit": "percent",
                "priority": 3,
            }

        # Hiring / team goals
        if any(kw in goal_lower for kw in ("hire", "recruit", "staff", "onboard")):
            return {
                "title": f"Hiring / team — {goal_text}",
                "description": goal_text,
                "success_metric": "headcount added",
                "success_unit": "people",
                "priority": 3,
            }

        # Fallback
        return {
            "title": goal_text,
            "description": goal_text,
            "success_metric": f"complete: {goal_text}",
            "success_unit": "",
            "priority": 3,
        }

    @staticmethod
    def _inject_business_math(
        task: MagnifySimplifyTask,
        plan: BusinessPlanMath,
    ) -> MagnifySimplifyTask:
        """Inject concrete numbers from BusinessPlanMath into the task."""
        title_lower = task.title.lower()

        if any(kw in title_lower for kw in ("grow revenue", "close", "seats", "units")):
            task.success_value = plan.unit_economics.units_per_month
            task.success_unit = "units per month"
            task.success_metric = (
                f"close {plan.unit_economics.units_per_month:.4f} units per month "
                f"({plan.unit_economics.adjusted_units_needed:.4f} total over "
                f"{plan.unit_economics.timeline_months:.0f} months)"
            )

        elif any(kw in title_lower for kw in ("marketing", "prospect", "outreach")):
            task.success_value = plan.unit_economics.prospect_reach_needed_per_month
            task.success_unit = "prospects per month"
            task.success_metric = (
                f"reach {plan.unit_economics.prospect_reach_needed_per_month:.4f} "
                f"prospects per month to compensate for "
                f"{plan.unit_economics.conversion_rate_actual * 100:.4f}% "
                f"conversion rate (goal: "
                f"{plan.unit_economics.conversion_rate_goal * 100:.4f}%)"
            )

        return task

    @staticmethod
    def _score_domain_fit(
        task: MagnifySimplifyTask,
        terminology: IndustryTerminology,
    ) -> float:
        """
        Score how well a task's title+description fits the domain keywords.

        Returns 1.0 if no domain_keywords registered (open domain).
        Otherwise Jaccard-style: matching_keywords / total_keywords.
        """
        if not terminology.domain_keywords:
            return 1.0
        text = f"{task.title} {task.description}".lower()
        matches = sum(1 for kw in terminology.domain_keywords if kw.lower() in text)
        return matches / len(terminology.domain_keywords)
