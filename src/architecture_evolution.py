"""
Architecture Evolution Engine for Murphy System Runtime

Analyzes the current architecture topology, computes evolution indicators,
predicts future module needs, and detects architectural stress points.
Operates standalone with registered data or integrated with CapabilityMap
and GovernanceKernel when available.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
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


@dataclass
class EvolutionIndicators:
    """Aggregated architecture evolution metrics and predictions."""

    complexity_growth: float = 0.0
    """Indicator (0–6) reflecting dependency complexity."""

    module_demand: float = 0.0
    """Indicator (0–6) reflecting demand for new modules."""

    regulatory_expansion: float = 0.0
    """Indicator (0–6) reflecting compliance domain growth."""

    optimization_potential: float = 0.0
    """Indicator (0–6) reflecting optimisation headroom."""

    research_opportunity: float = 0.0
    """Indicator (0–6) reflecting unresolved concept / novel-pattern density."""

    es: float = 0.0
    """Evolution Score — arithmetic mean of the five indicators (0–6)."""

    dependency_ratio: float = 0.0
    """Total dependencies divided by total modules."""

    predicted_modules: List[Dict[str, str]] = field(default_factory=list)
    """List of dicts with keys: name, purpose, justification."""

    stress_warnings: List[str] = field(default_factory=list)
    """Human-readable stress-point descriptions."""

    recommended_actions: List[Dict[str, str]] = field(default_factory=list)
    """List of dicts with keys: action, priority, impact."""


@dataclass
class _RegisteredModule:
    """Internal record for a module registered with the engine."""

    name: str
    dependencies: List[str] = field(default_factory=list)
    subsystem: str = "default"
    utilized: bool = True


@dataclass
class _RegisteredGap:
    """Internal record for a capability gap."""

    gap_id: str
    description: str
    category: str = "general"


# ---------------------------------------------------------------------------
# Resolution Path Stages (R1 → R2 → R3 → Utopia)
# ---------------------------------------------------------------------------

RESOLUTION_PATH_STAGES: List[Dict[str, Any]] = [
    {
        "stage": "R1",
        "label": "Foundation",
        "description": "Core modules operational, basic automation enabled",
        "milestones": ["core_modules_deployed", "basic_governance_active", "initial_testing"],
        "min_es": 0.0,
        "max_es": 2.0,
    },
    {
        "stage": "R2",
        "label": "Integration",
        "description": "Cross-module orchestration, regulatory alignment, quality scoring",
        "milestones": ["cross_module_orchestration", "regulatory_domains_covered", "quality_scoring_active"],
        "min_es": 2.0,
        "max_es": 4.0,
    },
    {
        "stage": "R3",
        "label": "Optimization",
        "description": "Self-healing, predictive evolution, full compliance automation",
        "milestones": ["self_healing_active", "predictive_evolution", "full_compliance_automation"],
        "min_es": 4.0,
        "max_es": 5.5,
    },
    {
        "stage": "Utopia",
        "label": "Autonomous Excellence",
        "description": "Autonomous operation, zero-gap architecture, regenerative systems",
        "milestones": ["autonomous_operation", "zero_gap_architecture", "regenerative_systems"],
        "min_es": 5.5,
        "max_es": 6.0,
    },
]


class ArchitectureEvolutionEngine:
    """Evaluates architecture health and predicts evolution trajectories.

    Works in two modes:
    * **Integrated** — receives a ``capability_map`` and/or
      ``governance_kernel`` at construction time and derives data from them.
    * **Standalone** — data is fed via ``register_module``,
      ``register_gap``, and ``register_compliance_domain``.
    """

    def __init__(
        self,
        capability_map: Any = None,
        governance_kernel: Any = None,
    ) -> None:
        """Initialise the evolution engine.

        Args:
            capability_map: Optional CapabilityMap instance.  When provided
                the engine will attempt to call ``get_gap_analysis()`` and
                ``get_dependency_graph()`` for richer analysis.
            governance_kernel: Optional GovernanceKernel instance.  Reserved
                for future compliance-domain integration.
        """
        self._capability_map = capability_map
        self._governance_kernel = governance_kernel
        self._lock = threading.Lock()

        self._modules: Dict[str, _RegisteredModule] = {}
        self._gaps: Dict[str, _RegisteredGap] = {}
        self._compliance_domains: List[str] = []

        logger.info("ArchitectureEvolutionEngine initialised")

    # ------------------------------------------------------------------
    # Public registration helpers
    # ------------------------------------------------------------------

    def register_module(
        self,
        name: str,
        dependencies: List[str],
        subsystem: str = "default",
    ) -> None:
        """Register a module for standalone analysis.

        Args:
            name: Unique module identifier.
            dependencies: List of module names this module depends on.
            subsystem: Logical subsystem grouping.
        """
        with self._lock:
            self._modules[name] = _RegisteredModule(
                name=name,
                dependencies=list(dependencies),
                subsystem=subsystem,
            )
        logger.debug("Registered module: %s (subsystem=%s)", name, subsystem)

    def register_gap(
        self,
        gap_id: str,
        description: str,
        category: str = "general",
    ) -> None:
        """Register a capability gap for standalone analysis.

        Args:
            gap_id: Unique gap identifier.
            description: Human-readable gap description.
            category: Classification category for the gap.
        """
        with self._lock:
            self._gaps[gap_id] = _RegisteredGap(
                gap_id=gap_id,
                description=description,
                category=category,
            )
        logger.debug("Registered gap: %s", gap_id)

    def register_compliance_domain(self, domain: str) -> None:
        """Register a compliance domain for standalone analysis.

        Args:
            domain: Name of the compliance domain (e.g. "GDPR", "SOC2").
        """
        with self._lock:
            if domain not in self._compliance_domains:
                capped_append(self._compliance_domains, domain)
        logger.debug("Registered compliance domain: %s", domain)

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def analyze(self) -> EvolutionIndicators:
        """Run full architecture analysis and return evolution indicators.

        Returns:
            An ``EvolutionIndicators`` dataclass populated with the
            current state of the architecture.
        """
        with self._lock:
            gap_list = self._collect_gaps()
            dep_graph = self._collect_dependency_graph()
            modules = dict(self._modules)
            compliance_domains = list(self._compliance_domains)

        total_modules = max(len(dep_graph), 1)
        total_deps = sum(len(deps) for deps in dep_graph.values())
        dep_ratio = total_deps / total_modules

        complexity = self._compute_complexity_growth(dep_ratio)
        demand = self._compute_module_demand(len(gap_list))
        regulatory = self._compute_regulatory_expansion(
            len(compliance_domains),
        )
        optimization = self._compute_optimization_potential(
            dep_graph, modules,
        )
        research = self._compute_research_opportunity(gap_list)

        es = (
            complexity + demand + regulatory + optimization + research
        ) / 5.0

        predicted = self._build_predicted_modules(gap_list)
        stress = self._build_stress_warnings(dep_ratio, dep_graph, modules)
        actions = self._build_recommended_actions(
            complexity, demand, regulatory, optimization, research,
            dep_ratio, stress,
        )

        indicators = EvolutionIndicators(
            complexity_growth=complexity,
            module_demand=demand,
            regulatory_expansion=regulatory,
            optimization_potential=optimization,
            research_opportunity=research,
            es=round(es, 2),
            dependency_ratio=round(dep_ratio, 2),
            predicted_modules=predicted,
            stress_warnings=stress,
            recommended_actions=actions,
        )

        logger.info(
            "Architecture analysis complete — ES=%.2f, dep_ratio=%.2f",
            indicators.es,
            indicators.dependency_ratio,
        )
        return indicators

    def predict_future_modules(self) -> List[Dict[str, str]]:
        """Predict modules that should be added to the architecture.

        Returns:
            List of dicts each containing *name*, *purpose*, and
            *justification* keys.
        """
        with self._lock:
            gap_list = self._collect_gaps()
        return self._build_predicted_modules(gap_list)

    def detect_architecture_stress(self) -> List[str]:
        """Detect current architecture stress points.

        Returns:
            List of human-readable stress warning strings.
        """
        with self._lock:
            dep_graph = self._collect_dependency_graph()
            modules = dict(self._modules)

        total_modules = max(len(dep_graph), 1)
        total_deps = sum(len(deps) for deps in dep_graph.values())
        dep_ratio = total_deps / total_modules

        return self._build_stress_warnings(dep_ratio, dep_graph, modules)

    def assess_resolution_path_stage(self) -> Dict[str, Any]:
        """Evaluate current system against Resolution Path milestones.

        Runs a full analysis to compute the Evolution Score, then maps it
        to a Resolution Path stage (R1 → R2 → R3 → Utopia).

        Returns:
            Dict with ``stage``, ``label``, ``description``, ``es``,
            ``completed_milestones``, and ``next_milestones``.
        """
        indicators = self.analyze()
        es = indicators.es

        current_stage = RESOLUTION_PATH_STAGES[0]
        for stage in RESOLUTION_PATH_STAGES:
            if stage["min_es"] <= es < stage["max_es"]:
                current_stage = stage
                break
        else:
            # ES at or above 6.0 — Utopia
            if es >= RESOLUTION_PATH_STAGES[-1]["min_es"]:
                current_stage = RESOLUTION_PATH_STAGES[-1]

        # Find next stage
        stage_index = next(
            (i for i, s in enumerate(RESOLUTION_PATH_STAGES)
             if s["stage"] == current_stage["stage"]),
            0,
        )
        next_stage = (
            RESOLUTION_PATH_STAGES[stage_index + 1]
            if stage_index + 1 < len(RESOLUTION_PATH_STAGES)
            else None
        )

        result: Dict[str, Any] = {
            "stage": current_stage["stage"],
            "label": current_stage["label"],
            "description": current_stage["description"],
            "es": es,
            "milestones": current_stage["milestones"],
            "next_stage": next_stage["stage"] if next_stage else None,
            "next_milestones": next_stage["milestones"] if next_stage else [],
        }

        logger.info(
            "Resolution path assessment: stage=%s (ES=%.2f)",
            result["stage"], es,
        )
        return result

    # ------------------------------------------------------------------
    # Data collection (must be called inside self._lock)
    # ------------------------------------------------------------------

    def _collect_gaps(self) -> List[_RegisteredGap]:
        """Collect gap data from capability_map or internal registry."""
        gaps: List[_RegisteredGap] = []

        if self._capability_map is not None:
            try:
                raw = self._capability_map.get_gap_analysis()
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict):
                            gaps.append(
                                _RegisteredGap(
                                    gap_id=str(
                                        item.get("id", item.get("gap_id", "")),
                                    ),
                                    description=str(
                                        item.get("description", ""),
                                    ),
                                    category=str(
                                        item.get("category", "general"),
                                    ),
                                )
                            )
            except Exception as exc:
                logger.warning(
                    "capability_map.get_gap_analysis() unavailable; "
                    "falling back to internal gaps: %s", exc,
                )

        if not gaps:
            gaps = list(self._gaps.values())

        return gaps

    def _collect_dependency_graph(self) -> Dict[str, List[str]]:
        """Collect dependency graph from capability_map or internal modules."""
        graph: Dict[str, List[str]] = {}

        if self._capability_map is not None:
            try:
                raw = self._capability_map.get_dependency_graph()
                if isinstance(raw, dict):
                    for mod, deps in raw.items():
                        if isinstance(deps, list):
                            graph[str(mod)] = [str(d) for d in deps]
            except Exception as exc:
                logger.warning(
                    "capability_map.get_dependency_graph() unavailable; "
                    "falling back to internal modules: %s", exc,
                )

        if not graph:
            for mod in self._modules.values():
                graph[mod.name] = list(mod.dependencies)

        return graph

    # ------------------------------------------------------------------
    # Indicator computation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_complexity_growth(dependency_ratio: float) -> float:
        """Map dependency ratio to a 0–6 complexity indicator.

        Args:
            dependency_ratio: Total dependencies / total modules.

        Returns:
            Complexity growth score between 0.0 and 6.0.
        """
        if dependency_ratio < 1.0:
            return 1.0
        if dependency_ratio < 2.0:
            return 2.0
        if dependency_ratio < 3.0:
            return 3.0
        if dependency_ratio < 4.0:
            return 4.0
        if dependency_ratio < 5.0:
            return 5.0
        return 6.0

    @staticmethod
    def _compute_module_demand(gap_count: int) -> float:
        """Map gap count to a 0–6 module demand indicator.

        Args:
            gap_count: Number of identified capability gaps.

        Returns:
            Module demand score between 0.0 and 6.0.
        """
        if gap_count == 0:
            return 1.0
        if gap_count <= 3:
            return 2.0
        if gap_count <= 6:
            return 3.0
        if gap_count <= 10:
            return 4.0
        if gap_count <= 15:
            return 5.0
        return 6.0

    @staticmethod
    def _compute_regulatory_expansion(domain_count: int) -> float:
        """Map compliance domain count to a 0–6 regulatory indicator.

        Args:
            domain_count: Number of registered compliance domains.

        Returns:
            Regulatory expansion score between 0.0 and 6.0.
        """
        return min(float(domain_count), 6.0)

    @staticmethod
    def _compute_optimization_potential(
        dep_graph: Dict[str, List[str]],
        modules: Dict[str, _RegisteredModule],
    ) -> float:
        """Estimate optimisation headroom from underutilised modules.

        A module is considered *underutilised* when it has zero inbound
        dependencies (nothing depends on it) and is not the only module
        in its subsystem.

        Args:
            dep_graph: Module name → list of dependency names.
            modules: Registered module records keyed by name.

        Returns:
            Optimization potential score between 0.0 and 6.0.
        """
        if not dep_graph:
            return 1.0

        all_deps: set[str] = set()
        for deps in dep_graph.values():
            all_deps.update(deps)

        underutilized = 0
        for mod_name in dep_graph:
            if mod_name not in all_deps:
                underutilized += 1

        total = max(len(dep_graph), 1)
        ratio = underutilized / total

        if ratio <= 0.1:
            return 1.0
        if ratio <= 0.2:
            return 2.0
        if ratio <= 0.3:
            return 3.0
        if ratio <= 0.5:
            return 4.0
        if ratio <= 0.7:
            return 5.0
        return 6.0

    @staticmethod
    def _compute_research_opportunity(
        gaps: List[_RegisteredGap],
    ) -> float:
        """Estimate research opportunity from unresolved concept gaps.

        Gaps categorised as ``research``, ``novel``, or ``experimental``
        count towards this indicator.

        Args:
            gaps: Current gap list.

        Returns:
            Research opportunity score between 0.0 and 6.0.
        """
        research_keywords = {"research", "novel", "experimental"}
        research_count = sum(
            1 for g in gaps if g.category.lower() in research_keywords
        )

        if research_count == 0:
            return 1.0
        if research_count <= 2:
            return 2.0
        if research_count <= 4:
            return 3.0
        if research_count <= 6:
            return 4.0
        if research_count <= 8:
            return 5.0
        return 6.0

    # ------------------------------------------------------------------
    # Prediction / stress / action builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_predicted_modules(
        gaps: List[_RegisteredGap],
    ) -> List[Dict[str, str]]:
        """Generate predicted module entries from capability gaps.

        Args:
            gaps: Current gap list.

        Returns:
            List of prediction dicts with *name*, *purpose*, *justification*.
        """
        predictions: List[Dict[str, str]] = []
        for gap in gaps:
            safe_id = gap.gap_id.replace(" ", "_").lower()
            predictions.append(
                {
                    "name": f"{safe_id}_module",
                    "purpose": gap.description or f"Address gap: {gap.gap_id}",
                    "justification": (
                        f"Capability gap '{gap.gap_id}' in category "
                        f"'{gap.category}' is unresolved"
                    ),
                }
            )
        return predictions

    @staticmethod
    def _build_stress_warnings(
        dep_ratio: float,
        dep_graph: Dict[str, List[str]],
        modules: Dict[str, _RegisteredModule],
    ) -> List[str]:
        """Apply stress-detection rules to the current architecture.

        Args:
            dep_ratio: Total dependencies / total modules.
            dep_graph: Module name → list of dependency names.
            modules: Registered module records.

        Returns:
            List of human-readable warning strings.
        """
        warnings: List[str] = []

        if dep_ratio > 3.0:
            warnings.append(
                f"Architecture stress: high dependency density "
                f"(ratio: {dep_ratio:.2f})"
            )

        # Subsystem utilisation check
        subsystem_modules: Dict[str, List[str]] = defaultdict(list)
        for mod in modules.values():
            subsystem_modules[mod.subsystem].append(mod.name)

        all_deps: set[str] = set()
        for deps in dep_graph.values():
            all_deps.update(deps)

        for subsystem, mod_names in subsystem_modules.items():
            if not mod_names:
                continue
            unused_count = sum(
                1
                for m in mod_names
                if m not in all_deps and m in dep_graph
            )
            if unused_count / len(mod_names) > 0.5:
                warnings.append(f"Subsystem underutilized: {subsystem}")

        # Bottleneck detection — modules with > 10 inbound dependencies
        inbound_counts: Dict[str, int] = defaultdict(int)
        for deps in dep_graph.values():
            for dep in deps:
                inbound_counts[dep] += 1

        for mod_name, count in sorted(inbound_counts.items()):
            if count > 10:
                warnings.append(f"Bottleneck risk: {mod_name}")

        return warnings

    @staticmethod
    def _build_recommended_actions(
        complexity: float,
        demand: float,
        regulatory: float,
        optimization: float,
        research: float,
        dep_ratio: float,
        stress: List[str],
    ) -> List[Dict[str, str]]:
        """Derive actionable recommendations from the indicators.

        Args:
            complexity: Complexity growth indicator.
            demand: Module demand indicator.
            regulatory: Regulatory expansion indicator.
            optimization: Optimization potential indicator.
            research: Research opportunity indicator.
            dep_ratio: Current dependency ratio.
            stress: Already-detected stress warnings.

        Returns:
            List of recommendation dicts with *action*, *priority*, *impact*.
        """
        actions: List[Dict[str, str]] = []

        if complexity >= 4.0:
            actions.append(
                {
                    "action": "Refactor high-coupling modules to reduce "
                              "dependency density",
                    "priority": "high",
                    "impact": "Reduces architectural fragility and improves "
                              "maintainability",
                }
            )

        if demand >= 4.0:
            actions.append(
                {
                    "action": "Schedule module development sprint to address "
                              "capability gaps",
                    "priority": "high",
                    "impact": "Closes feature gaps and unblocks downstream "
                              "workflows",
                }
            )

        if regulatory >= 4.0:
            actions.append(
                {
                    "action": "Expand compliance automation coverage",
                    "priority": "medium",
                    "impact": "Reduces manual audit burden and regulatory risk",
                }
            )

        if optimization >= 3.0:
            actions.append(
                {
                    "action": "Review underutilized modules for consolidation "
                              "or deprecation",
                    "priority": "medium",
                    "impact": "Simplifies architecture and reduces maintenance "
                              "overhead",
                }
            )

        if research >= 3.0:
            actions.append(
                {
                    "action": "Allocate research capacity for novel pattern "
                              "exploration",
                    "priority": "low",
                    "impact": "Enables proactive capability expansion",
                }
            )

        if dep_ratio > 3.0:
            actions.append(
                {
                    "action": "Introduce dependency abstraction layers to "
                              "contain coupling",
                    "priority": "high",
                    "impact": "Mitigates cascading failure risk",
                }
            )

        for warning in stress:
            if "Bottleneck" in warning:
                actions.append(
                    {
                        "action": f"Address bottleneck — {warning}",
                        "priority": "high",
                        "impact": "Prevents single-point-of-failure scenarios",
                    }
                )

        return actions
