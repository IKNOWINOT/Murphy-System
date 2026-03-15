"""
Strategic Simulation Engine for Murphy System Runtime

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Result of a strategic simulation run against a proposed change."""

    scenario_id: str
    description: str
    cost_impact: float
    complexity_impact: float
    compliance_impact: float
    performance_impact: float
    overall_score: float
    risk_level: str
    recommended: bool
    warnings: List[str] = field(default_factory=list)
    estimated_engineering_hours: float = 0.0
    regulatory_implications: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)


class StrategicSimulationEngine:
    """Deterministic simulation engine for evaluating proposed system changes.

    Computes multi-dimensional impact scores (cost, complexity, compliance,
    performance) for proposed module creations and modifications, returning
    structured results that upstream callers such as MSSController can use
    to enforce solidify-gate rules.

    All constructor parameters are optional; the engine operates standalone.
    """

    _COMPLEXITY_BASE: Dict[str, float] = {
        "low": 1.5,
        "medium": 3.0,
        "high": 4.5,
    }

    _COMPLEXITY_HOURS: Dict[str, float] = {
        "low": 8.0,
        "medium": 24.0,
        "high": 80.0,
    }

    _MODIFICATION_FACTOR: float = 0.7

    def __init__(
        self,
        capability_map: Optional[Any] = None,
        compliance_engine: Optional[Any] = None,
        governance_kernel: Optional[Any] = None,
    ) -> None:
        """Initialise the simulation engine.

        Args:
            capability_map: Optional capability map instance for module lookups.
            compliance_engine: Optional compliance engine for domain validation.
            governance_kernel: Optional governance kernel for policy checks.
        """
        self._capability_map = capability_map
        self._compliance_engine = compliance_engine
        self._governance_kernel = governance_kernel
        self._lock = threading.Lock()
        logger.info("StrategicSimulationEngine initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate_module_creation(self, module_spec: Dict[str, Any]) -> SimulationResult:
        """Simulate the impact of creating a new module.

        Args:
            module_spec: Dictionary containing module specification with keys
                ``name``, ``description``, ``dependencies``, ``subsystem``,
                ``compliance_domains``, and ``estimated_complexity``.

        Returns:
            A :class:`SimulationResult` with computed impact scores.
        """
        with self._lock:
            return self._run_creation_simulation(module_spec)

    def simulate_module_modification(
        self, module_path: str, changes: Dict[str, Any]
    ) -> SimulationResult:
        """Simulate the impact of modifying an existing module.

        Impact scores are scaled by a modification factor (0.7) because
        modifications carry less risk than full module creation.

        Args:
            module_path: File-system path of the module being modified.
            changes: Dictionary with keys ``description``,
                ``added_dependencies``, ``removed_dependencies``, and
                ``compliance_domains``.

        Returns:
            A :class:`SimulationResult` with computed impact scores.
        """
        with self._lock:
            return self._run_modification_simulation(module_path, changes)

    def compare_scenarios(
        self, scenarios: List[Dict[str, Any]]
    ) -> List[SimulationResult]:
        """Compare multiple creation scenarios and rank them.

        Each element in *scenarios* is a ``module_spec`` dictionary suitable
        for :meth:`simulate_module_creation`.

        Args:
            scenarios: List of module specification dictionaries.

        Returns:
            List of :class:`SimulationResult` sorted by ``overall_score``
            ascending (lowest risk first).  Lower ``overall_score`` values
            indicate lower risk, so the first element is the safest option.
        """
        with self._lock:
            results = [self._run_creation_simulation(spec) for spec in scenarios]
        results.sort(key=lambda r: r.overall_score)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_creation_simulation(
        self, module_spec: Dict[str, Any]
    ) -> SimulationResult:
        """Core simulation logic for module creation."""
        name: str = module_spec.get("name", "unnamed_module")
        description: str = module_spec.get("description", "")
        dependencies: List[str] = list(module_spec.get("dependencies", []))
        compliance_domains: List[str] = list(
            module_spec.get("compliance_domains", [])
        )
        estimated_complexity: str = module_spec.get(
            "estimated_complexity", "medium"
        )

        dep_count = len(dependencies)
        domain_count = len(compliance_domains)

        cost_impact = self._compute_cost_impact(dep_count, domain_count)
        complexity_impact = self._compute_complexity_impact(
            estimated_complexity, dep_count
        )
        compliance_impact = self._compute_compliance_impact(domain_count)
        performance_impact = self._compute_performance_impact(dep_count)
        overall_score = self._compute_overall_score(
            cost_impact, complexity_impact, compliance_impact, performance_impact
        )
        risk_level = self._determine_risk_level(overall_score)
        recommended = overall_score < 4.0
        estimated_hours = self._compute_engineering_hours(
            estimated_complexity, dep_count
        )
        warnings = self._generate_warnings(
            risk_level, dep_count, compliance_impact
        )
        affected_modules = dependencies + [name]

        result = SimulationResult(
            scenario_id=uuid.uuid4().hex[:12],
            description=description,
            cost_impact=cost_impact,
            complexity_impact=complexity_impact,
            compliance_impact=compliance_impact,
            performance_impact=performance_impact,
            overall_score=overall_score,
            risk_level=risk_level,
            recommended=recommended,
            warnings=warnings,
            estimated_engineering_hours=estimated_hours,
            regulatory_implications=list(compliance_domains),
            affected_modules=affected_modules,
        )

        logger.info(
            "Simulation complete for '%s': score=%.2f risk=%s",
            name,
            overall_score,
            risk_level,
        )
        return result

    def _run_modification_simulation(
        self, module_path: str, changes: Dict[str, Any]
    ) -> SimulationResult:
        """Core simulation logic for module modification."""
        description: str = changes.get("description", "")
        added_deps: List[str] = list(changes.get("added_dependencies", []))
        removed_deps: List[str] = list(changes.get("removed_dependencies", []))
        compliance_domains: List[str] = list(
            changes.get("compliance_domains", [])
        )

        net_dependencies = added_deps
        dep_count = len(net_dependencies)
        domain_count = len(compliance_domains)

        name = module_path.rsplit("/", 1)[-1].replace(".py", "")

        cost_impact = min(
            self._compute_cost_impact(dep_count, domain_count)
            * self._MODIFICATION_FACTOR,
            6.0,
        )
        complexity_impact = min(
            self._compute_complexity_impact("medium", dep_count)
            * self._MODIFICATION_FACTOR,
            6.0,
        )
        compliance_impact = min(
            self._compute_compliance_impact(domain_count)
            * self._MODIFICATION_FACTOR,
            6.0,
        )
        performance_impact = min(
            self._compute_performance_impact(dep_count)
            * self._MODIFICATION_FACTOR,
            6.0,
        )
        overall_score = self._compute_overall_score(
            cost_impact, complexity_impact, compliance_impact, performance_impact
        )
        risk_level = self._determine_risk_level(overall_score)
        recommended = overall_score < 4.0
        estimated_hours = (
            self._compute_engineering_hours("medium", dep_count)
            * self._MODIFICATION_FACTOR
        )
        warnings = self._generate_warnings(
            risk_level, dep_count, compliance_impact
        )
        affected_modules = added_deps + removed_deps + [name]

        result = SimulationResult(
            scenario_id=uuid.uuid4().hex[:12],
            description=description,
            cost_impact=cost_impact,
            complexity_impact=complexity_impact,
            compliance_impact=compliance_impact,
            performance_impact=performance_impact,
            overall_score=overall_score,
            risk_level=risk_level,
            recommended=recommended,
            warnings=warnings,
            estimated_engineering_hours=estimated_hours,
            regulatory_implications=list(compliance_domains),
            affected_modules=affected_modules,
        )

        logger.info(
            "Modification simulation for '%s': score=%.2f risk=%s",
            module_path,
            overall_score,
            risk_level,
        )
        return result

    # ------------------------------------------------------------------
    # Scoring functions
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_cost_impact(dep_count: int, domain_count: int) -> float:
        """Compute cost impact from dependency and compliance domain counts.

        Args:
            dep_count: Number of module dependencies.
            domain_count: Number of compliance domains.

        Returns:
            Cost impact score capped at 6.0.
        """
        if dep_count == 0:
            base = 1.0
        elif dep_count <= 3:
            base = 2.0
        elif dep_count <= 6:
            base = 3.0
        elif dep_count <= 10:
            base = 4.0
        else:
            base = 5.0

        base += 0.5 * domain_count
        return min(base, 6.0)

    @classmethod
    def _compute_complexity_impact(
        cls, estimated_complexity: str, dep_count: int
    ) -> float:
        """Compute complexity impact from complexity level and dependencies.

        Args:
            estimated_complexity: One of ``"low"``, ``"medium"``, ``"high"``.
            dep_count: Number of module dependencies.

        Returns:
            Complexity impact score capped at 6.0.
        """
        base = cls._COMPLEXITY_BASE.get(estimated_complexity, 3.0)
        base += 0.3 * dep_count
        return min(base, 6.0)

    @staticmethod
    def _compute_compliance_impact(domain_count: int) -> float:
        """Compute compliance impact from the number of compliance domains.

        Args:
            domain_count: Number of compliance domains.

        Returns:
            Compliance impact score.
        """
        if domain_count == 0:
            return 0.5
        if domain_count == 1:
            return 2.0
        if domain_count == 2:
            return 3.0
        if domain_count == 3:
            return 4.0
        return 5.0

    @staticmethod
    def _compute_performance_impact(dep_count: int) -> float:
        """Compute performance impact based on affected module count.

        Args:
            dep_count: Number of dependencies (proxy for affected modules).

        Returns:
            Performance impact score.
        """
        if dep_count == 0:
            return 0.5
        if dep_count <= 3:
            return 1.5
        if dep_count <= 6:
            return 2.5
        if dep_count <= 10:
            return 3.5
        return 4.5

    @staticmethod
    def _compute_overall_score(
        cost: float,
        complexity: float,
        compliance: float,
        performance: float,
    ) -> float:
        """Compute the overall score as the average of four dimensions.

        Args:
            cost: Cost impact score.
            complexity: Complexity impact score.
            compliance: Compliance impact score.
            performance: Performance impact score.

        Returns:
            Overall score (average).
        """
        return (cost + complexity + compliance + performance) / 4.0

    @staticmethod
    def _determine_risk_level(overall_score: float) -> str:
        """Map an overall score to a human-readable risk level.

        Args:
            overall_score: The computed overall score (0–6).

        Returns:
            Risk level string.
        """
        if overall_score < 1.5:
            return "low"
        if overall_score < 3.0:
            return "moderate"
        if overall_score < 4.0:
            return "significant"
        if overall_score < 5.0:
            return "high"
        return "unacceptable"

    @classmethod
    def _compute_engineering_hours(
        cls, estimated_complexity: str, dep_count: int
    ) -> float:
        """Estimate engineering hours from complexity and dependency count.

        Args:
            estimated_complexity: One of ``"low"``, ``"medium"``, ``"high"``.
            dep_count: Number of module dependencies.

        Returns:
            Estimated engineering hours.
        """
        base_hours = cls._COMPLEXITY_HOURS.get(estimated_complexity, 24.0)
        return base_hours * (1.0 + 0.1 * dep_count)

    @staticmethod
    def _generate_warnings(
        risk_level: str, dep_count: int, compliance_impact: float
    ) -> List[str]:
        """Generate contextual warnings based on simulation results.

        Args:
            risk_level: The determined risk level string.
            dep_count: Number of module dependencies.
            compliance_impact: The computed compliance impact score.

        Returns:
            List of warning strings.
        """
        warnings: List[str] = []
        if risk_level in ("high", "unacceptable"):
            warnings.append(
                "High risk: simulation recommends review before proceeding"
            )
        if dep_count > 10:
            warnings.append(
                "High dependency count may increase maintenance burden"
            )
        if compliance_impact > 3.0:
            warnings.append("Significant compliance overhead expected")
        return warnings
