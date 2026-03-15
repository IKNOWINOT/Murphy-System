"""
INFINITY → DATA EXPANSION SYSTEM
(Exploration & Knowledge Carving Engine)

Purpose: Turn an underspecified task into a bounded, structured, verifiable knowledge space.
This is not search. This is progressive problem crystallization.

Integrated into the unified MFGC system as the exploratory band's core engine.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ExpansionAxis(Enum):
    """Orthogonal axes along which infinity is explored"""
    DOMAIN = "domain"  # engineering, legal, finance
    CONSTRAINTS = "constraints"  # safety, regulation, budget
    STAKEHOLDERS = "stakeholders"  # customer, regulators, ops
    FAILURE_MODES = "failure_modes"  # safety, cost, reputation
    TIME_HORIZONS = "time_horizons"  # immediate, lifecycle
    INTERFACES = "interfaces"  # APIs, contracts, hardware
    MARKET = "market"  # competition, demand, trends
    RESOURCES = "resources"  # budget, people, time
    COMPLIANCE = "compliance"  # legal, regulatory, standards


@dataclass
class ExpansionGoal:
    """What an explorer agent is trying to achieve"""
    axis: ExpansionAxis
    target: str  # What aspect to explore
    depth: int  # How deep to go (0-5)
    query_budget: int  # Max questions to ask


@dataclass
class ExplorerAgent:
    """
    Agent that explores one axis of infinity
    Their job is NOT to answer, but to surface unknowns
    """
    axis: ExpansionAxis
    profession: str  # From ProfessionAtom
    goal: ExpansionGoal
    queries_generated: List[str] = field(default_factory=list)
    unknowns_found: List[str] = field(default_factory=list)
    constraints_found: List[str] = field(default_factory=list)
    binding_variables: Dict[str, Any] = field(default_factory=dict)
    verification_sources: List[str] = field(default_factory=list)

    def explore(self, task: str) -> Dict[str, Any]:
        """
        Generate questions, not conclusions
        Returns structured uncertainty reduction
        """
        # Generate axis-specific questions
        questions = self._generate_questions(task)

        # Identify unknowns
        unknowns = self._identify_unknowns(task)

        # Find constraints
        constraints = self._find_constraints(task)

        # Propose verification sources
        sources = self._propose_sources(task)

        return {
            'axis': self.axis.value,
            'questions': questions,
            'unknowns': unknowns,
            'constraints': constraints,
            'sources': sources,
            'binding_variables': self.binding_variables
        }

    def _generate_questions(self, task: str) -> List[str]:
        """Generate axis-specific questions"""
        questions = []

        if self.axis == ExpansionAxis.DOMAIN:
            questions = [
                f"What domain expertise is required for: {task}?",
                "What are the key technical concepts involved?",
                "What domain-specific standards apply?"
            ]

        elif self.axis == ExpansionAxis.CONSTRAINTS:
            questions = [
                "What are the hard constraints (cannot be violated)?",
                "What are the soft constraints (preferences)?",
                "What are the resource limits (time, budget, people)?"
            ]

        elif self.axis == ExpansionAxis.STAKEHOLDERS:
            questions = [
                "Who are the primary stakeholders?",
                "Who has veto power?",
                "Who will be impacted by this?"
            ]

        elif self.axis == ExpansionAxis.FAILURE_MODES:
            questions = [
                "What could go catastrophically wrong?",
                "What are the high-probability failure modes?",
                "What failures would be unrecoverable?"
            ]

        elif self.axis == ExpansionAxis.TIME_HORIZONS:
            questions = [
                "What is the immediate timeline?",
                "What is the lifecycle timeline?",
                "What are the maintenance requirements?"
            ]

        elif self.axis == ExpansionAxis.INTERFACES:
            questions = [
                "What systems must this interface with?",
                "What are the interface contracts?",
                "What are the integration points?"
            ]

        elif self.axis == ExpansionAxis.MARKET:
            questions = [
                "What is the market context?",
                "Who are the competitors?",
                "What is the demand signal?"
            ]

        elif self.axis == ExpansionAxis.RESOURCES:
            questions = [
                "What resources are available?",
                "What resources are critical path?",
                "What resources are fungible?"
            ]

        elif self.axis == ExpansionAxis.COMPLIANCE:
            questions = [
                "What regulations apply?",
                "What standards must be met?",
                "What certifications are required?"
            ]

        return questions[:self.goal.query_budget]

    def _identify_unknowns(self, task: str) -> List[str]:
        """Identify what we don't know"""
        unknowns = []

        # Check for underspecified aspects
        if "design" in task.lower() and self.axis == ExpansionAxis.DOMAIN:
            unknowns.append("Technical architecture not specified")
            unknowns.append("Technology stack not defined")

        if self.axis == ExpansionAxis.CONSTRAINTS:
            unknowns.append("Budget constraints not specified")
            unknowns.append("Timeline constraints not specified")

        if self.axis == ExpansionAxis.STAKEHOLDERS:
            unknowns.append("Decision makers not identified")
            unknowns.append("User personas not defined")

        return unknowns

    def _find_constraints(self, task: str) -> List[str]:
        """Find constraint regimes"""
        constraints = []

        if self.axis == ExpansionAxis.CONSTRAINTS:
            constraints.append("Must comply with safety regulations")
            constraints.append("Must be cost-effective")
            constraints.append("Must be maintainable")

        if self.axis == ExpansionAxis.FAILURE_MODES:
            constraints.append("Must have failure recovery")
            constraints.append("Must have monitoring")
            constraints.append("Must have rollback capability")

        return constraints

    def _propose_sources(self, task: str) -> List[str]:
        """Propose verification sources"""
        sources = []

        if self.axis == ExpansionAxis.DOMAIN:
            sources.append("Domain experts")
            sources.append("Technical documentation")
            sources.append("Industry standards")

        if self.axis == ExpansionAxis.COMPLIANCE:
            sources.append("Regulatory bodies")
            sources.append("Legal counsel")
            sources.append("Compliance databases")

        return sources


@dataclass
class ExpansionResult:
    """
    Output of expansion phase
    Not answers - only structured uncertainty reduction
    """
    bound_variables: Dict[str, Any]
    remaining_unknowns: List[str]
    candidate_data_sources: List[str]
    risk_clusters: List[Dict[str, Any]]
    required_verifications: List[str]
    expansion_complete: bool
    confidence_contribution: float


class ExpansionControlLaw:
    """
    Controls when expansion stops

    Let:
    X = semantic space
    V(X) = unbound volume
    D(x) = deterministic grounding

    Expansion continues while:
    dD(x)/dt < τ and V(X) > V_min

    Meaning: keep expanding while grounding is not increasing fast enough
    and uncertainty volume remains large.
    """

    def __init__(self, tau: float = 0.1, v_min: float = 0.2):
        self.tau = tau  # Grounding rate threshold
        self.v_min = v_min  # Minimum uncertainty volume
        self.grounding_history: List[float] = []
        self.time_history: List[float] = []

    def should_continue_expansion(
        self,
        current_grounding: float,
        uncertainty_volume: float
    ) -> bool:
        """
        Determine if expansion should continue

        Returns True if:
        1. Grounding rate is too slow (dD/dt < tau)
        2. Uncertainty volume is still large (V > V_min)
        """
        current_time = time.time()

        # Record current state
        self.grounding_history.append(current_grounding)
        self.time_history.append(current_time)

        # Need at least 2 points to calculate rate
        if len(self.grounding_history) < 2:
            return True

        # Calculate grounding rate: dD/dt
        dt = self.time_history[-1] - self.time_history[-2]
        if dt == 0:
            dt = 0.001  # Avoid division by zero

        dD = self.grounding_history[-1] - self.grounding_history[-2]
        grounding_rate = dD / dt

        # Check both conditions
        slow_grounding = grounding_rate < self.tau
        high_uncertainty = uncertainty_volume > self.v_min

        return slow_grounding and high_uncertainty

    def reset(self):
        """Reset control law state"""
        self.grounding_history = []
        self.time_history = []


class InfinityExpansionEngine:
    """
    Main engine for progressive problem crystallization
    Integrated into unified MFGC system
    """

    def __init__(self):
        self.control_law = ExpansionControlLaw()
        self.expansion_history: List[ExpansionResult] = []

    def expand_task(
        self,
        task: str,
        max_iterations: int = 5
    ) -> ExpansionResult:
        """
        Expand underspecified task into bounded knowledge space

        Process:
        1. Spawn explorer agents across all axes
        2. Collect questions, unknowns, constraints
        3. Calculate grounding and uncertainty
        4. Check control law
        5. Iterate until expansion complete
        """
        # Initialize
        self.control_law.reset()
        iteration = 0

        # Track state
        all_questions = []
        all_unknowns = []
        all_constraints = []
        all_sources = []
        bound_variables = {}

        while iteration < max_iterations:
            iteration += 1

            # Spawn explorer agents for each axis
            explorers = self._spawn_explorers(task, iteration)

            # Execute exploration
            for explorer in explorers:
                result = explorer.explore(task)

                all_questions.extend(result['questions'])
                all_unknowns.extend(result['unknowns'])
                all_constraints.extend(result['constraints'])
                all_sources.extend(result['sources'])
                bound_variables.update(result['binding_variables'])

            # Calculate metrics
            grounding = self._calculate_grounding(bound_variables, all_constraints)
            uncertainty = self._calculate_uncertainty(all_unknowns)

            # Check control law
            should_continue = self.control_law.should_continue_expansion(
                grounding, uncertainty
            )

            if not should_continue:
                break

        # Build final result
        result = ExpansionResult(
            bound_variables=bound_variables,
            remaining_unknowns=list(set(all_unknowns)),
            candidate_data_sources=list(set(all_sources)),
            risk_clusters=self._cluster_risks(all_constraints),
            required_verifications=self._identify_verifications(all_unknowns),
            expansion_complete=not should_continue,
            confidence_contribution=grounding
        )

        self.expansion_history.append(result)
        return result

    def _spawn_explorers(self, task: str, depth: int) -> List[ExplorerAgent]:
        """Spawn explorer agents for each axis"""
        explorers = []

        # Map axes to professions
        axis_professions = {
            ExpansionAxis.DOMAIN: "domain_expert",
            ExpansionAxis.CONSTRAINTS: "systems_engineer",
            ExpansionAxis.STAKEHOLDERS: "business_analyst",
            ExpansionAxis.FAILURE_MODES: "risk_manager",
            ExpansionAxis.TIME_HORIZONS: "project_manager",
            ExpansionAxis.INTERFACES: "integration_architect",
            ExpansionAxis.MARKET: "market_analyst",
            ExpansionAxis.RESOURCES: "resource_planner",
            ExpansionAxis.COMPLIANCE: "compliance_officer"
        }

        for axis, profession in axis_professions.items():
            goal = ExpansionGoal(
                axis=axis,
                target=task,
                depth=depth,
                query_budget=3  # 3 questions per axis
            )

            explorer = ExplorerAgent(
                axis=axis,
                profession=profession,
                goal=goal
            )

            explorers.append(explorer)

        return explorers

    def _calculate_grounding(
        self,
        bound_variables: Dict[str, Any],
        constraints: List[str]
    ) -> float:
        """
        Calculate deterministic grounding D(x)

        Grounding increases as:
        - More variables are bound
        - More constraints are identified
        """
        variable_score = len(bound_variables) * 0.1
        constraint_score = len(constraints) * 0.05

        return min(variable_score + constraint_score, 1.0)

    def _calculate_uncertainty(self, unknowns: List[str]) -> float:
        """
        Calculate uncertainty volume V(X)

        Uncertainty decreases as unknowns are resolved
        """
        # Start with maximum uncertainty
        base_uncertainty = 1.0

        # Each unknown reduces uncertainty slightly
        # (paradoxically, identifying unknowns reduces uncertainty)
        reduction = len(unknowns) * 0.02

        return max(base_uncertainty - reduction, 0.0)

    def _cluster_risks(self, constraints: List[str]) -> List[Dict[str, Any]]:
        """Cluster constraints into risk categories"""
        clusters = {
            'safety': [],
            'cost': [],
            'reputation': [],
            'compliance': [],
            'technical': []
        }

        for constraint in constraints:
            constraint_lower = constraint.lower()

            if any(word in constraint_lower for word in ['safety', 'hazard', 'danger']):
                clusters['safety'].append(constraint)
            elif any(word in constraint_lower for word in ['cost', 'budget', 'expensive']):
                clusters['cost'].append(constraint)
            elif any(word in constraint_lower for word in ['reputation', 'brand', 'trust']):
                clusters['reputation'].append(constraint)
            elif any(word in constraint_lower for word in ['compliance', 'regulation', 'legal']):
                clusters['compliance'].append(constraint)
            else:
                clusters['technical'].append(constraint)

        return [
            {'category': cat, 'risks': risks}
            for cat, risks in clusters.items()
            if risks
        ]

    def _identify_verifications(self, unknowns: List[str]) -> List[str]:
        """Identify what needs to be verified"""
        verifications = []

        for unknown in unknowns:
            verifications.append(f"Verify: {unknown}")

        return verifications

    def get_expansion_summary(self) -> Dict[str, Any]:
        """Get summary of expansion process"""
        if not self.expansion_history:
            return {
                'iterations': 0,
                'final_grounding': 0.0,
                'unknowns_remaining': 0,
                'expansion_complete': False
            }

        final = self.expansion_history[-1]

        return {
            'iterations': len(self.expansion_history),
            'final_grounding': final.confidence_contribution,
            'unknowns_remaining': len(final.remaining_unknowns),
            'expansion_complete': final.expansion_complete,
            'bound_variables': len(final.bound_variables),
            'risk_clusters': len(final.risk_clusters),
            'verifications_required': len(final.required_verifications)
        }
