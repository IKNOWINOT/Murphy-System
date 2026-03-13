"""
Advanced Swarm System with Enhanced Generation and Gates
Combines powerful generative capabilities with Murphy-Free safety
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SwarmType(Enum):
    """Types of swarms for different generation strategies"""
    CREATIVE = "creative"  # Divergent thinking, novel solutions
    ANALYTICAL = "analytical"  # Systematic, logical approaches
    HYBRID = "hybrid"  # Combines creative + analytical
    ADVERSARIAL = "adversarial"  # Red team, find weaknesses
    SYNTHESIS = "synthesis"  # Combine multiple solutions
    OPTIMIZATION = "optimization"  # Refine and improve


class GenerationDomain(Enum):
    """Domains for specialized generation"""
    SOFTWARE = "software"
    BUSINESS = "business"
    RESEARCH = "research"
    CREATIVE_WRITING = "creative_writing"
    DATA_ANALYSIS = "data_analysis"
    SYSTEM_DESIGN = "system_design"
    PROBLEM_SOLVING = "problem_solving"
    EDUCATION = "education"


@dataclass
class SwarmCandidate:
    """Enhanced candidate with full metadata"""
    id: str
    content: Any
    swarm_type: SwarmType
    domain: GenerationDomain
    confidence: float
    novelty: float  # How novel/creative (0-1)
    feasibility: float  # How feasible (0-1)
    risk_score: float  # Murphy risk (0-1)
    dependencies: List[str]
    validation_requirements: List[str]
    metadata: Dict[str, Any]


@dataclass
class SafetyGate:
    """Enhanced safety gate with domain awareness"""
    id: str
    name: str
    check_fn: Callable
    severity: float
    domain: Optional[GenerationDomain]
    organizational_context: Optional[str]
    rationale: str
    auto_fix: Optional[Callable]  # Can automatically fix issues


class AdvancedSwarmGenerator:
    """
    Advanced swarm generator with multiple strategies

    Key features:
    1. Multiple swarm types (creative, analytical, hybrid, adversarial)
    2. Domain-specific generation
    3. Novelty vs feasibility balance
    4. Automatic gate synthesis
    5. Organizational context awareness
    """

    def __init__(self):
        self.swarm_types = list(SwarmType)
        self.domains = list(GenerationDomain)
        self.generation_history = []
        self.gate_library = self._initialize_gate_library()

    def _initialize_gate_library(self) -> Dict[str, SafetyGate]:
        """Initialize comprehensive gate library"""
        gates = {}

        # Universal gates (apply to all domains)
        gates['scope_creep'] = SafetyGate(
            id='scope_creep',
            name='Scope Creep Prevention',
            check_fn=lambda c: len(c.get('requirements', [])) < 20,
            severity=0.6,
            domain=None,
            organizational_context='project_management',
            rationale='Prevents unbounded scope expansion',
            auto_fix=lambda c: self._limit_scope(c, 15)
        )

        gates['resource_constraint'] = SafetyGate(
            id='resource_constraint',
            name='Resource Constraint Check',
            check_fn=lambda c: c.get('estimated_cost', 0) < 1000000,
            severity=0.7,
            domain=None,
            organizational_context='budget',
            rationale='Ensures solution is resource-feasible',
            auto_fix=None
        )

        gates['time_constraint'] = SafetyGate(
            id='time_constraint',
            name='Time Constraint Check',
            check_fn=lambda c: c.get('estimated_time_months', 0) < 24,
            severity=0.5,
            domain=None,
            organizational_context='timeline',
            rationale='Prevents unrealistic timelines',
            auto_fix=lambda c: self._adjust_timeline(c)
        )

        # Software domain gates
        gates['tech_debt'] = SafetyGate(
            id='tech_debt',
            name='Technical Debt Prevention',
            check_fn=lambda c: c.get('complexity_score', 0) < 0.8,
            severity=0.6,
            domain=GenerationDomain.SOFTWARE,
            organizational_context='engineering',
            rationale='Prevents accumulation of technical debt',
            auto_fix=lambda c: self._simplify_architecture(c)
        )

        gates['security_baseline'] = SafetyGate(
            id='security_baseline',
            name='Security Baseline',
            check_fn=lambda c: 'security' in str(c).lower(),
            severity=0.9,
            domain=GenerationDomain.SOFTWARE,
            organizational_context='security',
            rationale='Ensures security is considered',
            auto_fix=lambda c: self._add_security_requirements(c)
        )

        # Business domain gates
        gates['market_validation'] = SafetyGate(
            id='market_validation',
            name='Market Validation Required',
            check_fn=lambda c: c.get('market_research', False),
            severity=0.7,
            domain=GenerationDomain.BUSINESS,
            organizational_context='product',
            rationale='Ensures market demand exists',
            auto_fix=None
        )

        gates['roi_threshold'] = SafetyGate(
            id='roi_threshold',
            name='ROI Threshold',
            check_fn=lambda c: c.get('expected_roi', 0) > 0.15,
            severity=0.8,
            domain=GenerationDomain.BUSINESS,
            organizational_context='finance',
            rationale='Ensures financial viability',
            auto_fix=None
        )

        # Research domain gates
        gates['reproducibility'] = SafetyGate(
            id='reproducibility',
            name='Reproducibility Check',
            check_fn=lambda c: c.get('reproducible', False),
            severity=0.8,
            domain=GenerationDomain.RESEARCH,
            organizational_context='scientific',
            rationale='Ensures research can be reproduced',
            auto_fix=lambda c: self._add_reproducibility_requirements(c)
        )

        gates['peer_review'] = SafetyGate(
            id='peer_review',
            name='Peer Review Required',
            check_fn=lambda c: c.get('peer_reviewed', False),
            severity=0.7,
            domain=GenerationDomain.RESEARCH,
            organizational_context='academic',
            rationale='Ensures quality through peer review',
            auto_fix=None
        )

        return gates

    def generate_swarm(
        self,
        task: str,
        swarm_type: SwarmType,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int = 10
    ) -> List[SwarmCandidate]:
        """
        Generate a swarm of candidates

        Args:
            task: Task description
            swarm_type: Type of swarm to generate
            domain: Domain for specialized generation
            context: Additional context
            count: Number of candidates to generate

        Returns:
            List of candidates with full metadata
        """
        candidates = []

        if swarm_type == SwarmType.CREATIVE:
            candidates = self._generate_creative_swarm(task, domain, context, count)
        elif swarm_type == SwarmType.ANALYTICAL:
            candidates = self._generate_analytical_swarm(task, domain, context, count)
        elif swarm_type == SwarmType.HYBRID:
            candidates = self._generate_hybrid_swarm(task, domain, context, count)
        elif swarm_type == SwarmType.ADVERSARIAL:
            candidates = self._generate_adversarial_swarm(task, domain, context, count)
        elif swarm_type == SwarmType.SYNTHESIS:
            candidates = self._generate_synthesis_swarm(task, domain, context, count)
        elif swarm_type == SwarmType.OPTIMIZATION:
            candidates = self._generate_optimization_swarm(task, domain, context, count)

        # Store in history
        self.generation_history.append({
            'task': task,
            'swarm_type': swarm_type,
            'domain': domain,
            'count': len(candidates)
        })

        return candidates

    def _generate_creative_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate creative, divergent solutions"""
        candidates = []

        # Creative strategies
        strategies = [
            'analogical_thinking',  # Draw analogies from other domains
            'lateral_thinking',  # Approach from unexpected angles
            'combinatorial',  # Combine existing solutions
            'inversion',  # Invert the problem
            'extreme_scenarios',  # Push to extremes
            'random_stimuli',  # Use random associations
            'scamper',  # Substitute, Combine, Adapt, Modify, etc.
            'biomimicry',  # Learn from nature
            'constraint_removal',  # Remove assumed constraints
            'future_backwards'  # Work backwards from ideal future
        ]

        for i, strategy in enumerate(strategies[:count]):
            candidate = SwarmCandidate(
                id=f"creative_{i}",
                content=self._apply_creative_strategy(task, strategy, domain, context),
                swarm_type=SwarmType.CREATIVE,
                domain=domain,
                confidence=0.6,  # Creative solutions start with lower confidence
                novelty=0.9,  # High novelty
                feasibility=0.5,  # May need validation
                risk_score=0.4,  # Moderate risk
                dependencies=self._identify_dependencies(strategy, domain),
                validation_requirements=['prototype', 'user_testing', 'feasibility_study'],
                metadata={
                    'strategy': strategy,
                    'requires_validation': True,
                    'innovation_potential': 'high'
                }
            )
            candidates.append(candidate)

        return candidates

    def _generate_analytical_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate analytical, systematic solutions"""
        candidates = []

        # Analytical strategies
        strategies = [
            'decomposition',  # Break into sub-problems
            'first_principles',  # Build from fundamentals
            'systematic_enumeration',  # List all options
            'decision_tree',  # Tree-based analysis
            'cost_benefit',  # Analyze costs vs benefits
            'risk_analysis',  # Identify and mitigate risks
            'constraint_satisfaction',  # Satisfy all constraints
            'optimization',  # Find optimal solution
            'simulation',  # Model and simulate
            'benchmarking'  # Compare to existing solutions
        ]

        for i, strategy in enumerate(strategies[:count]):
            candidate = SwarmCandidate(
                id=f"analytical_{i}",
                content=self._apply_analytical_strategy(task, strategy, domain, context),
                swarm_type=SwarmType.ANALYTICAL,
                domain=domain,
                confidence=0.8,  # Analytical solutions have higher confidence
                novelty=0.4,  # Lower novelty
                feasibility=0.9,  # High feasibility
                risk_score=0.2,  # Low risk
                dependencies=self._identify_dependencies(strategy, domain),
                validation_requirements=['verification', 'testing'],
                metadata={
                    'strategy': strategy,
                    'systematic': True,
                    'proven_approach': True
                }
            )
            candidates.append(candidate)

        return candidates

    def _generate_hybrid_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate hybrid solutions (creative + analytical)"""
        # Generate half creative, half analytical
        creative_count = count // 2
        analytical_count = count - creative_count

        creative = self._generate_creative_swarm(task, domain, context, creative_count)
        analytical = self._generate_analytical_swarm(task, domain, context, analytical_count)

        # Combine and mark as hybrid
        candidates = creative + analytical
        for c in candidates:
            c.swarm_type = SwarmType.HYBRID
            c.confidence = (c.confidence + 0.7) / 2  # Balance confidence
            c.novelty = (c.novelty + 0.5) / 2  # Balance novelty
            c.feasibility = (c.feasibility + 0.7) / 2  # Balance feasibility

        return candidates

    def _generate_adversarial_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate adversarial candidates (red team, find weaknesses)"""
        candidates = []

        # Adversarial strategies
        attack_vectors = [
            'edge_cases',  # Test boundary conditions
            'failure_modes',  # Identify failure scenarios
            'security_vulnerabilities',  # Find security holes
            'scalability_limits',  # Test scale limits
            'resource_exhaustion',  # Test resource limits
            'race_conditions',  # Find timing issues
            'data_corruption',  # Test data integrity
            'user_errors',  # Test error handling
            'malicious_input',  # Test input validation
            'dependency_failures'  # Test external dependencies
        ]

        for i, vector in enumerate(attack_vectors[:count]):
            candidate = SwarmCandidate(
                id=f"adversarial_{i}",
                content={
                    'attack_vector': vector,
                    'description': self._describe_attack_vector(vector, domain),
                    'mitigation': self._suggest_mitigation(vector, domain),
                    'severity': self._assess_severity(vector, domain)
                },
                swarm_type=SwarmType.ADVERSARIAL,
                domain=domain,
                confidence=0.7,
                novelty=0.6,
                feasibility=0.8,
                risk_score=0.8,  # High risk if not addressed
                dependencies=[],
                validation_requirements=['penetration_testing', 'security_audit'],
                metadata={
                    'attack_vector': vector,
                    'defensive': True
                }
            )
            candidates.append(candidate)

        return candidates

    def _generate_synthesis_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate synthesis candidates (combine multiple solutions)"""
        # First generate diverse candidates
        creative = self._generate_creative_swarm(task, domain, context, 3)
        analytical = self._generate_analytical_swarm(task, domain, context, 3)

        candidates = []

        # Synthesize combinations
        for i in range(min(count, 10)):
            # Pick 2-3 candidates to combine
            to_combine = []
            if i % 2 == 0 and creative:
                to_combine.append(creative[i % len(creative)])
            if analytical:
                to_combine.append(analytical[i % len(analytical)])

            if len(to_combine) >= 2:
                candidate = SwarmCandidate(
                    id=f"synthesis_{i}",
                    content={
                        'synthesis_of': [c.id for c in to_combine],
                        'combined_approach': self._synthesize_approaches(to_combine),
                        'strengths': self._combine_strengths(to_combine),
                        'addresses_weaknesses': True
                    },
                    swarm_type=SwarmType.SYNTHESIS,
                    domain=domain,
                    confidence=0.75,
                    novelty=0.7,
                    feasibility=0.75,
                    risk_score=0.3,
                    dependencies=sum([c.dependencies for c in to_combine], []),
                    validation_requirements=['integration_testing', 'validation'],
                    metadata={
                        'synthesized_from': len(to_combine),
                        'hybrid_approach': True
                    }
                )
                candidates.append(candidate)

        return candidates

    def _generate_optimization_swarm(
        self,
        task: str,
        domain: GenerationDomain,
        context: Dict[str, Any],
        count: int
    ) -> List[SwarmCandidate]:
        """Generate optimization candidates (refine existing solutions)"""
        candidates = []

        # Optimization dimensions
        dimensions = [
            'performance',
            'cost',
            'quality',
            'time',
            'scalability',
            'maintainability',
            'usability',
            'security',
            'reliability',
            'flexibility'
        ]

        for i, dimension in enumerate(dimensions[:count]):
            candidate = SwarmCandidate(
                id=f"optimization_{i}",
                content={
                    'optimize_for': dimension,
                    'approach': self._get_optimization_approach(dimension, domain),
                    'trade_offs': self._identify_trade_offs(dimension),
                    'expected_improvement': f"20-50% improvement in {dimension}"
                },
                swarm_type=SwarmType.OPTIMIZATION,
                domain=domain,
                confidence=0.8,
                novelty=0.3,
                feasibility=0.9,
                risk_score=0.2,
                dependencies=[],
                validation_requirements=['benchmarking', 'measurement'],
                metadata={
                    'optimization_target': dimension,
                    'incremental': True
                }
            )
            candidates.append(candidate)

        return candidates

    def synthesize_gates_from_candidates(
        self,
        candidates: List[SwarmCandidate],
        domain: GenerationDomain,
        organizational_context: Dict[str, Any]
    ) -> List[SafetyGate]:
        """
        Synthesize safety gates from candidates

        Key insight: Gates are discovered from risks in candidates,
        not predefined
        """
        gates = []

        # Analyze candidates for risks
        risks = self._extract_risks_from_candidates(candidates)

        # Create gates for each risk
        for risk in risks:
            gate = self._create_gate_from_risk(risk, domain, organizational_context)
            if gate:
                gates.append(gate)

        # Add domain-specific gates
        domain_gates = self._get_domain_gates(domain)
        gates.extend(domain_gates)

        # Add organizational gates
        org_gates = self._get_organizational_gates(organizational_context)
        gates.extend(org_gates)

        return gates

    def _apply_creative_strategy(
        self,
        task: str,
        strategy: str,
        domain: GenerationDomain,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a creative strategy to generate solution"""
        # LLM/rule-based generation deferred; returns static default
        return {
            'strategy': strategy,
            'approach': f"Apply {strategy} to: {task}",
            'description': f"Creative solution using {strategy}",
            'domain': domain.value,
            'novelty': 'high'
        }

    def _apply_analytical_strategy(
        self,
        task: str,
        strategy: str,
        domain: GenerationDomain,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply an analytical strategy to generate solution"""
        return {
            'strategy': strategy,
            'approach': f"Systematic {strategy} for: {task}",
            'description': f"Analytical solution using {strategy}",
            'domain': domain.value,
            'systematic': True
        }

    def _identify_dependencies(self, strategy: str, domain: GenerationDomain) -> List[str]:
        """Identify dependencies for a strategy"""
        # Simplified dependency identification
        deps = []
        if 'prototype' in strategy:
            deps.append('prototyping_tools')
        if 'simulation' in strategy:
            deps.append('simulation_environment')
        if domain == GenerationDomain.SOFTWARE:
            deps.append('development_environment')
        return deps

    def _describe_attack_vector(self, vector: str, domain: GenerationDomain) -> str:
        """Describe an attack vector"""
        descriptions = {
            'edge_cases': 'Test boundary conditions and extreme inputs',
            'failure_modes': 'Identify scenarios where system fails',
            'security_vulnerabilities': 'Find potential security weaknesses',
            'scalability_limits': 'Test system under extreme load',
            'resource_exhaustion': 'Test resource limit handling'
        }
        return descriptions.get(vector, f"Test {vector}")

    def _suggest_mitigation(self, vector: str, domain: GenerationDomain) -> str:
        """Suggest mitigation for attack vector"""
        return f"Implement safeguards against {vector}"

    def _assess_severity(self, vector: str, domain: GenerationDomain) -> str:
        """Assess severity of attack vector"""
        high_severity = ['security_vulnerabilities', 'data_corruption', 'resource_exhaustion']
        return 'high' if vector in high_severity else 'medium'

    def _synthesize_approaches(self, candidates: List[SwarmCandidate]) -> str:
        """Synthesize multiple approaches"""
        strategies = [c.metadata.get('strategy', 'unknown') for c in candidates]
        return f"Hybrid approach combining: {', '.join(strategies)}"

    def _combine_strengths(self, candidates: List[SwarmCandidate]) -> List[str]:
        """Combine strengths from multiple candidates"""
        strengths = []
        for c in candidates:
            if c.novelty > 0.7:
                strengths.append('innovative')
            if c.feasibility > 0.7:
                strengths.append('practical')
            if c.confidence > 0.7:
                strengths.append('reliable')
        return list(set(strengths))

    def _get_optimization_approach(self, dimension: str, domain: GenerationDomain) -> str:
        """Get optimization approach for dimension"""
        approaches = {
            'performance': 'Profile and optimize hotspots',
            'cost': 'Reduce resource usage and waste',
            'quality': 'Increase testing and validation',
            'time': 'Parallelize and streamline processes'
        }
        return approaches.get(dimension, f"Optimize {dimension}")

    def _identify_trade_offs(self, dimension: str) -> List[str]:
        """Identify trade-offs for optimization"""
        trade_offs = {
            'performance': ['May increase complexity', 'May reduce maintainability'],
            'cost': ['May reduce quality', 'May increase time'],
            'quality': ['May increase cost', 'May increase time']
        }
        return trade_offs.get(dimension, ['Trade-offs exist'])

    def _extract_risks_from_candidates(self, candidates: List[SwarmCandidate]) -> List[Dict[str, Any]]:
        """Extract risks from candidates"""
        risks = []
        for c in candidates:
            if c.risk_score > 0.5:
                risks.append({
                    'source': c.id,
                    'risk_score': c.risk_score,
                    'description': f"Risk from {c.swarm_type.value} candidate",
                    'mitigation_needed': True
                })
        return risks

    def _create_gate_from_risk(
        self,
        risk: Dict[str, Any],
        domain: GenerationDomain,
        organizational_context: Dict[str, Any]
    ) -> Optional[SafetyGate]:
        """Create a safety gate from identified risk"""
        if risk['risk_score'] > 0.7:
            return SafetyGate(
                id=f"gate_{risk['source']}",
                name=f"Mitigate {risk['description']}",
                check_fn=lambda c: c.get('risk_mitigation', False),
                severity=risk['risk_score'],
                domain=domain,
                organizational_context=organizational_context.get('context', 'general'),
                rationale=f"Prevent {risk['description']}",
                auto_fix=None
            )
        return None

    def _get_domain_gates(self, domain: GenerationDomain) -> List[SafetyGate]:
        """Get domain-specific gates"""
        domain_gates = []
        for gate_id, gate in self.gate_library.items():
            if gate.domain == domain or gate.domain is None:
                domain_gates.append(gate)
        return domain_gates

    def _get_organizational_gates(self, context: Dict[str, Any]) -> List[SafetyGate]:
        """Get organization-specific gates"""
        org_gates = []
        org_context = context.get('organizational_context', '')

        for gate_id, gate in self.gate_library.items():
            if gate.organizational_context and gate.organizational_context in org_context:
                org_gates.append(gate)

        return org_gates

    # Auto-fix functions
    def _limit_scope(self, candidate: Dict[str, Any], max_items: int) -> Dict[str, Any]:
        """Limit scope to prevent scope creep"""
        if 'requirements' in candidate:
            candidate['requirements'] = candidate['requirements'][:max_items]
        return candidate

    def _adjust_timeline(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust timeline to be more realistic"""
        if 'estimated_time_months' in candidate:
            candidate['estimated_time_months'] = min(candidate['estimated_time_months'], 18)
        return candidate

    def _simplify_architecture(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Simplify architecture to reduce complexity"""
        if 'components' in candidate:
            candidate['components'] = candidate['components'][:5]
        return candidate

    def _add_security_requirements(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Add security requirements"""
        if 'requirements' not in candidate:
            candidate['requirements'] = []
        candidate['requirements'].append('Security audit required')
        candidate['requirements'].append('OWASP compliance')
        return candidate

    def _add_reproducibility_requirements(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Add reproducibility requirements"""
        if 'requirements' not in candidate:
            candidate['requirements'] = []
        candidate['requirements'].append('Reproducible methodology')
        candidate['requirements'].append('Open data and code')
        return candidate
