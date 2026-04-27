"""
Murphy System ? MSS Transformation Controls
Design Label: MSS-001
Copyright ? 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.concept_translation import ConceptTranslationEngine, TechnicalAnalogue
from src.information_quality import InformationQuality, InformationQualityEngine
from src.resolution_scoring import ResolutionLevel
from src.simulation_engine import SimulationResult, StrategicSimulationEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ordered resolution levels used for arithmetic on RM indices
# ---------------------------------------------------------------------------
_RM_ORDERED: List[str] = [
    ResolutionLevel.RM0.value,
    ResolutionLevel.RM1.value,
    ResolutionLevel.RM2.value,
    ResolutionLevel.RM3.value,
    ResolutionLevel.RM4.value,
    ResolutionLevel.RM5.value,
]


def _rm_index(level: str) -> int:
    """Return the zero-based index for a resolution level string."""
    for i, rm in enumerate(_RM_ORDERED):
        if rm == level:
            return i
    return 0


def _clamp(value: int, low: int = 0, high: int = 5) -> int:
    """Clamp *value* between *low* and *high* inclusive."""
    return max(low, min(high, value))


def _describe_output(output: Dict[str, Any]) -> str:
    """Build a single text description from all string values in *output*."""
    parts: List[str] = []
    for value in output.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    return " ".join(parts)


def _estimate_scope(component_count: int) -> str:
    """Map component count to a scope label."""
    if component_count <= 2:
        return "small"
    if component_count <= 5:
        return "medium"
    return "large"


def _estimate_cost_tier(complexity_impact: float) -> str:
    """Map a 0-6 complexity score to a cost tier label."""
    if complexity_impact < 2.0:
        return "low"
    if complexity_impact < 4.0:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class TransformationResult:
    """Immutable record of a single MSS transformation."""

    operator: str
    input_text: str
    output: Dict[str, Any]
    input_quality: InformationQuality
    output_quality: InformationQuality
    target_rm: str
    qc_metadata: Dict[str, str]
    simulation: Optional[SimulationResult]
    governance_status: str
    resolution_level: str = "RM0"  # PATCH-109a: added — assess() sets this; RM0=unknown/default


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
class MSSController:
    """Orchestrates Magnify, Simplify, and Solidify transformations.

    Each public method accepts raw text, runs it through the quality,
    translation, and simulation pipelines, then returns a fully-populated
    ``TransformationResult`` with pre- and post-transformation quality
    metrics, QC metadata, and governance status.
    """

    def __init__(
        self,
        iqe: InformationQualityEngine,
        cte: ConceptTranslationEngine,
        sim: StrategicSimulationEngine,
        gov: Optional[Any] = None,
    ) -> None:
        """Initialise the MSS controller.

        Args:
            iqe: Information quality scoring engine.
            cte: Concept translation engine.
            sim: Strategic simulation engine.
            gov: Optional governance kernel for policy enforcement.
        """
        self._iqe = iqe
        self._cte = cte
        self._sim = sim
        self._gov = gov
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_qc_metadata(
        self,
        operator: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Construct the mandatory QC metadata dictionary."""
        owner = "murphy_system"
        if context:
            owner = context.get("owner", "murphy_system")
        return {
            "who": owner,
            "what": f"{operator} transformation of input text",
            "when": datetime.now(timezone.utc).isoformat(),
            "where": "murphy_system/mss_controls",
            "why": f"Resolution {operator} requested for quality improvement",
            "how": f"Automated {operator} via MSS pipeline with quality scoring",
        }

    def _resolve_governance_status(
        self,
        operator: str,
        input_quality: InformationQuality,
        simulation: Optional[SimulationResult],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Determine the governance status for a transformation.

        Rules (evaluated in order):
        1. If solidify and simulation risk is high/unacceptable ? blocked.
        2. If input_quality recommendation is block ? blocked.
        3. If input_quality recommendation is clarify ? conditional.
        4. If a governance kernel is available, attempt enforcement.
        5. Otherwise ? approved.
        """
        if (
            operator == "solidify"
            and simulation is not None
            and simulation.risk_level in ("high", "unacceptable")
        ):
            return "blocked"

        if input_quality.recommendation == "block":
            return "blocked"

        if input_quality.recommendation == "clarify":
            return "conditional"

        if self._gov is not None:
            try:
                result = self._gov.enforce(
                    caller_id="mss_controls",
                    department_id=context.get("department_id", "default")
                    if context
                    else "default",
                    tool_name=f"mss_{operator}",
                    estimated_cost=0.0,
                    context=context,
                )
                if hasattr(result, "action"):
                    action_value = (
                        result.action.value
                        if hasattr(result.action, "value")
                        else str(result.action)
                    )
                    if action_value == "deny":
                        return "blocked"
                    if action_value == "escalate":
                        return "conditional"
            except Exception as exc:
                logger.warning(
                    "Governance enforcement failed; defaulting to approved: %s",
                    exc,
                    exc_info=True,
                )

        return "approved"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def magnify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TransformationResult:
        """Increase the resolution of *text* by two RM levels (cap RM5).

        Expands the input into concrete components, explicit processes,
        and measurable outcomes.

        Args:
            text: Raw input text to magnify.
            context: Optional context dictionary.

        Returns:
            A ``TransformationResult`` with the magnified output.
        """
        with self._lock:
            input_quality: InformationQuality = self._iqe.assess(text, context)
            analogue: TechnicalAnalogue = self._cte.translate(text, context)

            current_idx = _rm_index(input_quality.resolution_level)
            target_idx = _clamp(current_idx + 2)
            target_rm = _RM_ORDERED[target_idx]

            components = analogue.system_model.get("components", [])
            data_flows = analogue.system_model.get("data_flows", [])
            control_logic = analogue.system_model.get("control_logic", [])
            validation = analogue.system_model.get("validation_methods", [])

            requirements: List[str] = []
            for concept in analogue.extracted_concepts:
                goal = concept.get("goal", "")
                action = concept.get("action", "")
                if goal:
                    requirements.append(f"{action} ? {goal}" if action else goal)

            compliance = list(analogue.regulatory_frameworks)

            dep_count = len(components)
            cost_complexity = _estimate_cost_tier(
                2.0 if dep_count <= 3 else (3.5 if dep_count <= 6 else 5.0)
            )

            output: Dict[str, Any] = {
                "concept_overview": analogue.original_text,
                "functional_requirements": requirements
                or [f"Requirement inferred from {analogue.reasoning_method} analysis"],
                "technical_components": components
                or [m.get("technical_analogue", m.get("nontechnical", "component"))
                    for m in analogue.technical_mapping]
                or ["general_component"],
                "compliance_considerations": compliance or ["none_detected"],
                "cost_complexity_estimate": cost_complexity,
                "architecture_mapping": {
                    "components": components,
                    "data_flows": data_flows,
                    "control_logic": control_logic,
                    "validation_methods": validation,
                },
                "resolution_progression": (
                    f"RM{current_idx} \u2192 RM{target_idx}"
                ),
            }

            output_quality = self._iqe.assess(
                _describe_output(output), context
            )

            qc = self._build_qc_metadata("magnify", context)
            gov_status = self._resolve_governance_status(
                "magnify", input_quality, None, context
            )

            return TransformationResult(
                operator="magnify",
                input_text=text,
                output=output,
                input_quality=input_quality,
                output_quality=output_quality,
                target_rm=target_rm,
                qc_metadata=qc,
                simulation=None,
                governance_status=gov_status,
            )

    def simplify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TransformationResult:
        """Decrease the resolution of *text* by two RM levels (floor RM0).

        Distils the input into its core objective, key components, and
        essential metadata.

        Args:
            text: Raw input text to simplify.
            context: Optional context dictionary.

        Returns:
            A ``TransformationResult`` with the simplified output.
        """
        with self._lock:
            input_quality: InformationQuality = self._iqe.assess(text, context)
            analogue: TechnicalAnalogue = self._cte.translate(text, context)

            current_idx = _rm_index(input_quality.resolution_level)
            target_idx = _clamp(current_idx - 2)
            target_rm = _RM_ORDERED[target_idx]

            components = analogue.system_model.get("components", [])
            key_components = components[:5] if components else [
                m.get("technical_analogue", m.get("nontechnical", "component"))
                for m in analogue.technical_mapping[:5]
            ] or ["core_component"]

            objective_parts: List[str] = []
            for concept in analogue.extracted_concepts:
                goal = concept.get("goal", "")
                action = concept.get("action", "")
                if goal or action:
                    objective_parts.append(
                        f"{action} {goal}".strip()
                    )
            objective = (
                "; ".join(objective_parts)
                if objective_parts
                else analogue.original_text
            )

            compliance = list(analogue.regulatory_frameworks) or ["none_detected"]
            scope = _estimate_scope(len(key_components))

            dep_count = len(components)
            cost_tier = _estimate_cost_tier(
                2.0 if dep_count <= 3 else (3.5 if dep_count <= 6 else 5.0)
            )

            data_flows = analogue.system_model.get("data_flows", [])
            impact_summary = (
                f"Affects {len(components)} component(s) with "
                f"{len(data_flows)} data flow(s)"
            )

            output: Dict[str, Any] = {
                "objective": objective,
                "key_components": key_components,
                "estimated_scope": scope,
                "cost_tier": cost_tier,
                "regulatory_category": compliance,
                "system_impact": impact_summary,
                "resolution_progression": (
                    f"RM{current_idx} \u2192 RM{target_idx}"
                ),
            }

            output_quality = self._iqe.assess(
                _describe_output(output), context
            )

            qc = self._build_qc_metadata("simplify", context)
            gov_status = self._resolve_governance_status(
                "simplify", input_quality, None, context
            )

            return TransformationResult(
                operator="simplify",
                input_text=text,
                output=output,
                input_quality=input_quality,
                output_quality=output_quality,
                target_rm=target_rm,
                qc_metadata=qc,
                simulation=None,
                governance_status=gov_status,
            )

    def solidify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TransformationResult:
        """Convert *text* into an RM5 implementation plan.

        Runs a strategic simulation **before** building the module plan.
        If the simulation risk is high or unacceptable the governance
        status is set to ``"blocked"``.

        Args:
            text: Raw input text to solidify.
            context: Optional context dictionary.

        Returns:
            A ``TransformationResult`` with the implementation plan.
        """
        with self._lock:
            input_quality: InformationQuality = self._iqe.assess(text, context)
            analogue: TechnicalAnalogue = self._cte.translate(text, context)

            current_idx = _rm_index(input_quality.resolution_level)
            target_rm = _RM_ORDERED[5]

            components = analogue.system_model.get("components", [])
            data_flows = analogue.system_model.get("data_flows", [])
            control_logic = analogue.system_model.get("control_logic", [])
            validation = analogue.system_model.get("validation_methods", [])
            compliance = list(analogue.regulatory_frameworks)

            module_name = (
                components[0].lower().replace(" ", "_")
                if components
                else "new_module"
            )

            module_spec: Dict[str, Any] = {
                "name": module_name,
                "description": analogue.original_text,
                "dependencies": components[1:] if len(components) > 1 else [],
                "subsystem": "murphy_system",
                "compliance_domains": compliance,
                "estimated_complexity": (
                    "low" if len(components) <= 2
                    else "medium" if len(components) <= 5
                    else "high"
                ),
            }

            simulation: SimulationResult = self._sim.simulate_module_creation(
                module_spec
            )

            capability = (
                f"Create {module_name} module to {analogue.original_text}"
            )

            existing_overlap = (
                f"Overlaps with {len(components) - 1} existing component(s)"
                if len(components) > 1
                else "No existing module overlap detected"
            )

            interfaces: List[str] = []
            for flow in data_flows:
                interfaces.append(f"data_interface: {flow}")
            for logic in control_logic:
                interfaces.append(f"control_interface: {logic}")

            full_module_specification: Dict[str, Any] = {
                "name": module_name,
                "purpose": analogue.original_text,
                "dependencies": module_spec["dependencies"],
                "interfaces": interfaces or ["default_interface"],
            }

            dep_count = len(module_spec["dependencies"])
            architecture_placement = (
                f"{module_name} integrated into murphy_system "
                f"with {dep_count} dependency link(s)"
            )

            implementation_steps: List[str] = [
                f"1. Define {module_name} module structure and interfaces",
                f"2. Implement core logic based on {analogue.reasoning_method} analysis",
            ]
            step = 3
            for comp in components[:5]:
                implementation_steps.append(
                    f"{step}. Integrate with {comp}"
                )
                step += 1
            implementation_steps.append(
                f"{step}. Validate against compliance requirements"
            )
            step += 1
            implementation_steps.append(
                f"{step}. Deploy and monitor"
            )

            testing_strategy: List[str] = [
                f"Unit tests for {module_name} core logic",
                "Integration tests for component interfaces",
            ]
            for domain in compliance:
                testing_strategy.append(
                    f"Compliance validation for {domain}"
                )
            for method in validation:
                testing_strategy.append(f"Validation: {method}")

            iteration_plan = (
                f"Phase 1: Core {module_name} implementation "
                f"({simulation.estimated_engineering_hours:.0f}h estimated). "
                f"Phase 2: Integration and compliance validation. "
                f"Phase 3: Production deployment and monitoring."
            )

            documentation_updates: List[str] = [
                f"Module specification for {module_name}",
                "Architecture diagram update",
                "API reference documentation",
            ]
            for domain in compliance:
                documentation_updates.append(
                    f"Compliance documentation for {domain}"
                )

            output: Dict[str, Any] = {
                "capability_definition": capability,
                "existing_module_analysis": existing_overlap,
                "module_specification": full_module_specification,
                "architecture_placement": architecture_placement,
                "implementation_steps": implementation_steps,
                "testing_strategy": testing_strategy,
                "iteration_plan": iteration_plan,
                "documentation_updates": documentation_updates,
                "resolution_progression": (
                    f"RM{current_idx} \u2192 RM5"
                ),
            }

            output_quality = self._iqe.assess(
                _describe_output(output), context
            )

            qc = self._build_qc_metadata("solidify", context)
            gov_status = self._resolve_governance_status(
                "solidify", input_quality, simulation, context
            )

            return TransformationResult(
                operator="solidify",
                input_text=text,
                output=output,
                input_quality=input_quality,
                output_quality=output_quality,
                target_rm=target_rm,
                qc_metadata=qc,
                simulation=simulation,
                governance_status=gov_status,
            )

    def assess(self, intent, context=None):
        """Assess resolution level of an intent string (RM1-RM5).

        LCM calls this before routing through the full pipeline.
        Returns a TransformationResult with resolution_level set.
        Lightweight - no full transformation is performed.
        """
        if not intent or not intent.strip():
            return TransformationResult(
                operator="assess",
                input_text=intent or "",
                output={"resolution_level": "RM2", "assessed": True},
                input_quality=None,
                output_quality=None,
                target_rm="RM2",
                qc_metadata=self._build_qc_metadata("assess", context),
                simulation=None,
                governance_status="approved",
                resolution_level="RM2",
            )

        try:
            input_quality = self._iqe.assess(intent, context)
        except Exception:
            input_quality = None

        score = 0.5
        if input_quality is not None:
            try:
                score = float(getattr(input_quality, "overall_score",
                              getattr(input_quality, "score", 0.5)))
            except Exception:
                pass

        if score >= 0.85:
            rm = "RM5"
        elif score >= 0.70:
            rm = "RM4"
        elif score >= 0.50:
            rm = "RM3"
        elif score >= 0.30:
            rm = "RM2"
        else:
            rm = "RM1"

        return TransformationResult(
            operator="assess",
            input_text=intent,
            output={"resolution_level": rm, "quality_score": score, "assessed": True},
            input_quality=input_quality,
            output_quality=None,
            target_rm=rm,
            qc_metadata=self._build_qc_metadata("assess", context),
            simulation=None,
            governance_status="approved",
            resolution_level=rm,
        )

