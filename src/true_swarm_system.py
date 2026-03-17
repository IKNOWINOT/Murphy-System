"""
True Generative Swarm System
Parallel ensemble of constrained inference operators

Key Principles:
1. Swarms are parallel inference operators, not committees
2. Two coupled swarms: Exploration + Control (Risk)
3. Coordination via Typed Generative Workspace (TGW), not messaging
4. Gate synthesis from risk analysis, not predefined rules
5. Agents are epistemic instruments, never operational
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("true_swarm_system")


class Phase(Enum):
    """MFGC phases"""
    EXPAND = "expand"
    TYPE = "type"
    ENUMERATE = "enumerate"
    CONSTRAIN = "constrain"
    COLLAPSE = "collapse"
    BIND = "bind"
    EXECUTE = "execute"


class ProfessionAtom(Enum):
    """Atomic profession types for agent instantiation"""
    # Engineering
    ELECTRICAL_ENGINEER = "electrical_engineer"
    SOFTWARE_ENGINEER = "software_engineer"
    MECHANICAL_ENGINEER = "mechanical_engineer"
    SYSTEMS_ENGINEER = "systems_engineer"

    # Compliance &amp; Safety
    COMPLIANCE_OFFICER = "compliance_officer"
    SAFETY_ENGINEER = "safety_engineer"
    SECURITY_ANALYST = "security_analyst"
    RISK_MANAGER = "risk_manager"

    # Domain Experts
    DATA_SCIENTIST = "data_scientist"
    DOMAIN_EXPERT = "domain_expert"
    ARCHITECT = "architect"

    # Adversarial
    RED_TEAM = "red_team"
    PENETRATION_TESTER = "penetration_tester"

    # Synthesis
    INTEGRATOR = "integrator"
    OPTIMIZER = "optimizer"


class ArtifactType(Enum):
    """Types of artifacts in workspace"""
    HYPOTHESIS = "hypothesis"
    ASSUMPTION = "assumption"
    REQUIREMENT = "requirement"
    RISK = "risk"
    CONSTRAINT = "constraint"
    GATE_PROPOSAL = "gate_proposal"
    SOLUTION_CANDIDATE = "solution_candidate"
    VERIFICATION_STRATEGY = "verification_strategy"
    FAILURE_MODE = "failure_mode"


@dataclass
class Artifact:
    """
    Artifact in Typed Generative Workspace

    Agents coordinate by writing artifacts, not messaging
    """
    id: str
    content: Any
    artifact_type: ArtifactType
    phase: Phase
    source_agent: str  # AgentInstance ID
    confidence_impact: float  # How this affects confidence
    deterministic_bindings: Dict[str, Any]  # Verified facts
    timestamp: float
    dependencies: List[str] = field(default_factory=list)  # Other artifact IDs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateProposal:
    """
    Gate proposal from control swarm

    Gates are discovered, not predefined
    """
    id: str
    target: str  # Semantic region, phase, or action
    trigger: str  # Condition that activates gate
    effect: str  # block | verify | isolate | decay_authority
    risk_reduction_estimate: float  # How much this reduces Murphy risk
    rationale: str
    source_agent: str
    phase: Phase
    sensitivity: float  # ∂p_k/∂g - how much this gate reduces failure
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInstance:
    """
    Atomic unit of swarm

    Agent = instantiated ProfessionAtom
    Agents are inference operators, not actors
    """
    id: str
    profession: ProfessionAtom
    domain_scope: Set[str]  # What domains it may reason about
    phase: Phase
    authority_band: str  # What it may propose, never execute
    risk_models: List[str]  # Known failure patterns
    regulatory_knowledge: List[str]  # If applicable
    gate_proposal_history: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Agents never have execution authority"""
        if self.authority_band not in ['propose', 'analyze', 'verify']:
            raise ValueError("Agents can only propose/analyze/verify, never execute")


class TypedGenerativeWorkspace:
    """
    Shared artifact space for coordination

    Agents write artifacts here
    Coordination happens via verification pruning, gate activation, phase legality
    NOT negotiation
    """

    def __init__(self):
        self.artifacts: Dict[str, Artifact] = {}
        self.gate_proposals: Dict[str, GateProposal] = {}
        self.active_gates: List[str] = []
        self.phase_artifacts: Dict[Phase, List[str]] = {p: [] for p in Phase}

    def write_artifact(self, artifact: Artifact) -> str:
        """Write artifact to workspace"""
        self.artifacts[artifact.id] = artifact
        self.phase_artifacts[artifact.phase].append(artifact.id)
        return artifact.id

    def write_gate_proposal(self, proposal: GateProposal) -> str:
        """Write gate proposal to workspace"""
        self.gate_proposals[proposal.id] = proposal
        return proposal.id

    def get_artifacts_by_type(
        self,
        artifact_type: ArtifactType,
        phase: Optional[Phase] = None
    ) -> List[Artifact]:
        """Get artifacts by type and optionally phase"""
        artifacts = [a for a in self.artifacts.values() if a.artifact_type == artifact_type]
        if phase:
            artifacts = [a for a in artifacts if a.phase == phase]
        return artifacts

    def get_artifacts_by_phase(self, phase: Phase) -> List[Artifact]:
        """Get all artifacts for a phase"""
        artifact_ids = self.phase_artifacts.get(phase, [])
        return [self.artifacts[aid] for aid in artifact_ids if aid in self.artifacts]

    def activate_gate(self, gate_id: str):
        """Activate a gate"""
        if gate_id in self.gate_proposals and gate_id not in self.active_gates:
            self.active_gates.append(gate_id)

    def get_active_gates(self) -> List[GateProposal]:
        """Get all active gates"""
        return [self.gate_proposals[gid] for gid in self.active_gates
                if gid in self.gate_proposals]


class SwarmMode(Enum):
    """Two swarm modes that run interleaved"""
    EXPLORATION = "exploration"  # Find what could work
    CONTROL = "control"  # Find what could fail


class BaseSwarmAgent(ABC):
    """
    Base class for swarm agents

    Agents are inference operators that transform inputs into:
    - hypotheses
    - constraints
    - risks
    - gates

    Never actions.
    """

    def __init__(self, instance: AgentInstance, llm_controller=None):
        self.instance = instance
        self._llm = llm_controller  # Optional[LLMController] — injected at spawn time

    def _llm_generate(self, prompt: str, context: Optional[str] = None, max_tokens: int = 800) -> Optional[str]:
        """Call LLMController.query_llm() synchronously; returns None on any failure.

        Uses the onboard fallback when no external API is configured, so this
        method always returns a meaningful string unless the local engine is also
        broken.
        """
        if self._llm is None:
            return None
        try:
            import asyncio
            from llm_controller import LLMRequest
            req = LLMRequest(prompt=prompt, context=context, max_tokens=max_tokens)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Called from within an async context — run in thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._llm.query_llm(req))
                    response = future.result(timeout=30)
            else:
                response = loop.run_until_complete(self._llm.query_llm(req))
            return response.content
        except Exception as exc:
            logger.debug("BaseSwarmAgent._llm_generate failed (%s)", exc)
            return None

    @abstractmethod
    def generate_artifacts(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate artifacts based on profession and phase"""
        pass

    @abstractmethod
    def estimate_risks(
        self,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Estimate risks for control swarm"""
        pass

    def create_artifact(
        self,
        content: Any,
        artifact_type: ArtifactType,
        confidence_impact: float = 0.0,
        deterministic_bindings: Optional[Dict[str, Any]] = None
    ) -> Artifact:
        """Helper to create artifact"""
        return Artifact(
            id=f"{self.instance.id}_{uuid.uuid4().hex[:8]}",
            content=content,
            artifact_type=artifact_type,
            phase=self.instance.phase,
            source_agent=self.instance.id,
            confidence_impact=confidence_impact,
            deterministic_bindings=deterministic_bindings or {},
            timestamp=time.time()
        )


class ExplorationAgent(BaseSwarmAgent):
    """
    Exploration swarm agent

    Purpose: Find what could work
    Produces: solution candidates, decompositions, interpretations
    Optimizes for: generative adequacy G(x), coverage of decision space
    """

    def generate_artifacts(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate solution candidates"""
        artifacts = []

        # Generate based on profession
        if self.instance.profession == ProfessionAtom.SOFTWARE_ENGINEER:
            artifacts.extend(self._generate_software_solutions(task, workspace, context))
        elif self.instance.profession == ProfessionAtom.SYSTEMS_ENGINEER:
            artifacts.extend(self._generate_system_architectures(task, workspace, context))
        elif self.instance.profession == ProfessionAtom.DATA_SCIENTIST:
            artifacts.extend(self._generate_data_solutions(task, workspace, context))
        elif self.instance.profession == ProfessionAtom.INTEGRATOR:
            artifacts.extend(self._generate_synthesis(task, workspace, context))
        elif self.instance.profession == ProfessionAtom.OPTIMIZER:
            artifacts.extend(self._generate_optimizations(task, workspace, context))

        return artifacts

    def estimate_risks(
        self,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Exploration agents don't estimate risks"""
        return []

    def _generate_software_solutions(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate software solution candidates — LLM-backed with static fallback."""
        solutions = []

        # Try LLM generation first
        llm_text = self._llm_generate(
            prompt=(
                f"You are a software architect. For the task: '{task}'\n"
                f"Phase: {self.instance.phase.value}\n"
                "List 3-4 concrete software solution candidates as JSON array. "
                "Each item: {\"architecture\": str, \"approach\": str, \"trade_offs\": {\"pros\": [], \"cons\": []}}. "
                "Output ONLY the JSON array."
            ),
            max_tokens=600,
        )
        if llm_text:
            try:
                import json as _json
                items = _json.loads(llm_text.strip())
                if isinstance(items, list):
                    for item in items[:4]:
                        solutions.append(self.create_artifact(
                            content=item,
                            artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                            confidence_impact=0.18,
                            deterministic_bindings={"llm_generated": True},
                        ))
                    if solutions:
                        return solutions
            except Exception as exc:
                logger.debug("LLM JSON parse failed for software solutions (%s), using static", exc)

        # Static fallback
        if self.instance.phase == Phase.EXPAND:
            architectures = ['microservices', 'monolithic', 'serverless', 'event-driven']
            for arch in architectures:
                solutions.append(self.create_artifact(
                    content={
                        'architecture': arch,
                        'approach': f'{arch.capitalize()} architecture for: {task}',
                        'trade_offs': self._get_architecture_tradeoffs(arch)
                    },
                    artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                    confidence_impact=0.1,
                ))
        elif self.instance.phase == Phase.ENUMERATE:
            stacks = [
                {'frontend': 'React', 'backend': 'Node.js', 'db': 'PostgreSQL'},
                {'frontend': 'Vue', 'backend': 'Python/Django', 'db': 'MongoDB'},
                {'frontend': 'Angular', 'backend': 'Java/Spring', 'db': 'MySQL'}
            ]
            for stack in stacks:
                solutions.append(self.create_artifact(
                    content={'tech_stack': stack, 'maturity': 'production-ready', 'dependencies': list(stack.values())},
                    artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                    confidence_impact=0.15,
                ))
        return solutions

    def _generate_system_architectures(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate system architecture candidates — LLM-backed with static fallback."""
        architectures = []

        llm_text = self._llm_generate(
            prompt=(
                f"You are a systems architect. For the task: '{task}'\n"
                f"Phase: {self.instance.phase.value}\n"
                "List 3-4 system architecture patterns as JSON array. "
                "Each item: {\"pattern\": str, \"description\": str, \"benefits\": []}. "
                "Output ONLY the JSON array."
            ),
            max_tokens=500,
        )
        if llm_text:
            try:
                import json as _json
                items = _json.loads(llm_text.strip())
                if isinstance(items, list):
                    for item in items[:4]:
                        architectures.append(self.create_artifact(
                            content=item,
                            artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                            confidence_impact=0.15,
                            deterministic_bindings={"llm_generated": True},
                        ))
                    if architectures:
                        return architectures
            except Exception as exc:
                logger.debug("LLM JSON parse failed for architectures (%s), using static", exc)

        if self.instance.phase == Phase.EXPAND:
            patterns = ['layered', 'hexagonal', 'clean', 'onion']
            for pattern in patterns:
                architectures.append(self.create_artifact(
                    content={
                        'pattern': pattern,
                        'description': f'{pattern.capitalize()} architecture pattern',
                        'benefits': self._get_pattern_benefits(pattern)
                    },
                    artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                    confidence_impact=0.12,
                ))
        return architectures

    def _generate_data_solutions(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate data processing solutions"""
        solutions = []

        if self.instance.phase == Phase.EXPAND:
            approaches = ['batch', 'streaming', 'hybrid', 'lambda_architecture']
            for approach in approaches:
                artifact = self.create_artifact(
                    content={
                        'approach': approach,
                        'use_case': f'{approach} processing for: {task}',
                        'scalability': self._assess_scalability(approach)
                    },
                    artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                    confidence_impact=0.1
                )
                solutions.append(artifact)

        return solutions

    def _generate_synthesis(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Synthesize existing candidates"""
        syntheses = []

        # Get existing candidates
        candidates = workspace.get_artifacts_by_type(
            ArtifactType.SOLUTION_CANDIDATE,
            self.instance.phase
        )

        if len(candidates) >= 2:
            # Combine top candidates
            artifact = self.create_artifact(
                content={
                    'synthesis_of': [c.id for c in candidates[:3]],
                    'combined_approach': 'Hybrid solution combining best elements',
                    'strengths': ['scalable', 'maintainable', 'proven']
                },
                artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                confidence_impact=0.2,
                deterministic_bindings={'synthesized': True}
            )
            syntheses.append(artifact)

        return syntheses

    def _generate_optimizations(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Generate optimization candidates"""
        optimizations = []

        dimensions = ['performance', 'cost', 'reliability', 'maintainability']
        for dim in dimensions:
            artifact = self.create_artifact(
                content={
                    'optimize_for': dim,
                    'approach': f'Optimize {dim}',
                    'expected_improvement': f'20-40% improvement in {dim}'
                },
                artifact_type=ArtifactType.SOLUTION_CANDIDATE,
                confidence_impact=0.08
            )
            optimizations.append(artifact)

        return optimizations

    def _get_architecture_tradeoffs(self, arch: str) -> Dict[str, List[str]]:
        """Get architecture trade-offs"""
        tradeoffs = {
            'microservices': {
                'pros': ['Scalable', 'Independent deployment'],
                'cons': ['Complex', 'Network overhead']
            },
            'monolithic': {
                'pros': ['Simple', 'Easy to test'],
                'cons': ['Hard to scale', 'Tight coupling']
            },
            'serverless': {
                'pros': ['Auto-scaling', 'Pay-per-use'],
                'cons': ['Vendor lock-in', 'Cold starts']
            },
            'event-driven': {
                'pros': ['Loose coupling', 'Asynchronous'],
                'cons': ['Complex debugging', 'Eventual consistency']
            }
        }
        return tradeoffs.get(arch, {'pros': [], 'cons': []})

    def _get_pattern_benefits(self, pattern: str) -> List[str]:
        """Get pattern benefits"""
        benefits = {
            'layered': ['Clear separation', 'Easy to understand'],
            'hexagonal': ['Highly testable', 'Framework independent'],
            'clean': ['Business logic isolated', 'Testable'],
            'onion': ['Dependency inversion', 'Flexible']
        }
        return benefits.get(pattern, ['Proven pattern'])

    def _assess_scalability(self, approach: str) -> str:
        """Assess scalability"""
        scalability = {
            'batch': 'High throughput, bounded latency',
            'streaming': 'Low latency, continuous processing',
            'hybrid': 'Balanced throughput and latency',
            'lambda_architecture': 'Both batch and real-time'
        }
        return scalability.get(approach, 'Scalable')


class ControlAgent(BaseSwarmAgent):
    """
    Control (Risk) swarm agent

    Purpose: Find what could fail
    Produces: failure hypotheses, constraint proposals, gate definitions
    Optimizes for: minimizing Murphy index M_t, minimizing instability H(x)
    """

    def generate_artifacts(
        self,
        task: str,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Control agents generate risks and constraints"""
        return self.estimate_risks(workspace, context)

    def estimate_risks(
        self,
        workspace: TypedGenerativeWorkspace,
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """Estimate risks and propose gates"""
        artifacts = []

        # Get solution candidates to analyze
        candidates = workspace.get_artifacts_by_type(
            ArtifactType.SOLUTION_CANDIDATE,
            self.instance.phase
        )

        # Generate risks based on profession
        if self.instance.profession == ProfessionAtom.SECURITY_ANALYST:
            artifacts.extend(self._analyze_security_risks(candidates, workspace))
        elif self.instance.profession == ProfessionAtom.COMPLIANCE_OFFICER:
            artifacts.extend(self._analyze_compliance_risks(candidates, workspace))
        elif self.instance.profession == ProfessionAtom.SAFETY_ENGINEER:
            artifacts.extend(self._analyze_safety_risks(candidates, workspace))
        elif self.instance.profession == ProfessionAtom.RISK_MANAGER:
            artifacts.extend(self._analyze_general_risks(candidates, workspace))
        elif self.instance.profession == ProfessionAtom.RED_TEAM:
            artifacts.extend(self._analyze_adversarial_risks(candidates, workspace))

        return artifacts

    def _analyze_security_risks(
        self,
        candidates: List[Artifact],
        workspace: TypedGenerativeWorkspace
    ) -> List[Artifact]:
        """Analyze security risks"""
        risks = []

        for candidate in candidates:
            # Identify security risks
            risk_artifact = self.create_artifact(
                content={
                    'target': candidate.id,
                    'risk_type': 'security',
                    'description': 'Potential security vulnerabilities',
                    'severity': 0.7,
                    'attack_vectors': ['injection', 'authentication', 'authorization']
                },
                artifact_type=ArtifactType.RISK,
                confidence_impact=-0.1
            )
            risks.append(risk_artifact)

            # Propose gate
            gate_proposal = self._create_gate_proposal(
                target=candidate.id,
                trigger='security_validation_required',
                effect='verify',
                risk_reduction=0.6,
                rationale='Ensure security baseline met'
            )
            workspace.write_gate_proposal(gate_proposal)

        return risks

    def _analyze_compliance_risks(
        self,
        candidates: List[Artifact],
        workspace: TypedGenerativeWorkspace
    ) -> List[Artifact]:
        """Analyze compliance risks"""
        risks = []

        for candidate in candidates:
            risk_artifact = self.create_artifact(
                content={
                    'target': candidate.id,
                    'risk_type': 'compliance',
                    'description': 'Regulatory compliance requirements',
                    'severity': 0.8,
                    'regulations': ['GDPR', 'SOC2', 'HIPAA']
                },
                artifact_type=ArtifactType.RISK,
                confidence_impact=-0.15
            )
            risks.append(risk_artifact)

            gate_proposal = self._create_gate_proposal(
                target=candidate.id,
                trigger='compliance_check_required',
                effect='verify',
                risk_reduction=0.7,
                rationale='Ensure regulatory compliance'
            )
            workspace.write_gate_proposal(gate_proposal)

        return risks

    def _analyze_safety_risks(
        self,
        candidates: List[Artifact],
        workspace: TypedGenerativeWorkspace
    ) -> List[Artifact]:
        """Analyze safety risks"""
        risks = []

        for candidate in candidates:
            risk_artifact = self.create_artifact(
                content={
                    'target': candidate.id,
                    'risk_type': 'safety',
                    'description': 'Potential safety hazards',
                    'severity': 0.9,
                    'hazards': ['data_loss', 'system_failure', 'user_harm']
                },
                artifact_type=ArtifactType.RISK,
                confidence_impact=-0.2
            )
            risks.append(risk_artifact)

            gate_proposal = self._create_gate_proposal(
                target=candidate.id,
                trigger='safety_validation_required',
                effect='verify',
                risk_reduction=0.8,
                rationale='Ensure safety standards met'
            )
            workspace.write_gate_proposal(gate_proposal)

        return risks

    def _analyze_general_risks(
        self,
        candidates: List[Artifact],
        workspace: TypedGenerativeWorkspace
    ) -> List[Artifact]:
        """Analyze general project risks"""
        risks = []

        # Scope creep risk
        if len(candidates) > 10:
            risk_artifact = self.create_artifact(
                content={
                    'risk_type': 'scope_creep',
                    'description': 'Too many options may lead to scope creep',
                    'severity': 0.6,
                    'mitigation': 'Limit to top 5 candidates'
                },
                artifact_type=ArtifactType.RISK,
                confidence_impact=-0.1
            )
            risks.append(risk_artifact)

            gate_proposal = self._create_gate_proposal(
                target='all_candidates',
                trigger='candidate_count > 10',
                effect='block',
                risk_reduction=0.5,
                rationale='Prevent scope creep'
            )
            workspace.write_gate_proposal(gate_proposal)

        return risks

    def _analyze_adversarial_risks(
        self,
        candidates: List[Artifact],
        workspace: TypedGenerativeWorkspace
    ) -> List[Artifact]:
        """Analyze adversarial attack vectors"""
        risks = []

        attack_vectors = [
            'edge_cases',
            'race_conditions',
            'resource_exhaustion',
            'malicious_input'
        ]

        for vector in attack_vectors:
            risk_artifact = self.create_artifact(
                content={
                    'risk_type': 'adversarial',
                    'attack_vector': vector,
                    'description': f'Potential {vector} vulnerability',
                    'severity': 0.7
                },
                artifact_type=ArtifactType.RISK,
                confidence_impact=-0.12
            )
            risks.append(risk_artifact)

            gate_proposal = self._create_gate_proposal(
                target='all_candidates',
                trigger=f'{vector}_detected',
                effect='verify',
                risk_reduction=0.6,
                rationale=f'Mitigate {vector} attacks'
            )
            workspace.write_gate_proposal(gate_proposal)

        return risks

    def _create_gate_proposal(
        self,
        target: str,
        trigger: str,
        effect: str,
        risk_reduction: float,
        rationale: str
    ) -> GateProposal:
        """Create gate proposal"""
        return GateProposal(
            id=f"gate_{uuid.uuid4().hex[:8]}",
            target=target,
            trigger=trigger,
            effect=effect,
            risk_reduction_estimate=risk_reduction,
            rationale=rationale,
            source_agent=self.instance.id,
            phase=self.instance.phase,
            sensitivity=risk_reduction  # Simplified: sensitivity = risk_reduction
        )


class SwarmSpawner:
    """
    Spawns swarms dynamically based on conditions

    Swarms are spawned when:
    - confidence drops
    - instability rises
    - new domain appears
    - failure occurs
    - incentive pressure spikes
    """

    def __init__(self, llm_controller=None):
        self.active_agents: Dict[str, BaseSwarmAgent] = {}
        self.spawn_history: List[Dict[str, Any]] = []
        self._llm = llm_controller

    def spawn_swarm(
        self,
        mode: SwarmMode,
        phase: Phase,
        task: str,
        context: Dict[str, Any],
        workspace: TypedGenerativeWorkspace
    ) -> List[BaseSwarmAgent]:
        """
        Spawn a swarm based on mode and context

        Spawner selects ProfessionAtoms based on:
        - domain classification
        - regulatory context
        - artifact types present
        """
        agents = []

        # Determine which professions to spawn
        professions = self._select_professions(mode, phase, task, context, workspace)

        # Instantiate agents
        for profession in professions:
            instance = AgentInstance(
                id=f"{profession.value}_{uuid.uuid4().hex[:8]}",
                profession=profession,
                domain_scope=self._get_domain_scope(profession, task),
                phase=phase,
                authority_band='propose',  # Agents can only propose
                risk_models=self._get_risk_models(profession),
                regulatory_knowledge=self._get_regulatory_knowledge(profession)
            )

            # Create agent based on mode — inject LLMController for real inference
            if mode == SwarmMode.EXPLORATION:
                agent = ExplorationAgent(instance, llm_controller=self._llm)
            else:  # CONTROL
                agent = ControlAgent(instance, llm_controller=self._llm)

            agents.append(agent)
            self.active_agents[instance.id] = agent

        # Record spawn
        self.spawn_history.append({
            'timestamp': time.time(),
            'mode': mode.value,
            'phase': phase.value,
            'professions': [p.value for p in professions],
            'count': len(agents)
        })

        return agents

    def _select_professions(
        self,
        mode: SwarmMode,
        phase: Phase,
        task: str,
        context: Dict[str, Any],
        workspace: TypedGenerativeWorkspace
    ) -> List[ProfessionAtom]:
        """Select professions based on context"""
        professions = []

        if mode == SwarmMode.EXPLORATION:
            # Always include core professions
            professions.extend([
                ProfessionAtom.SOFTWARE_ENGINEER,
                ProfessionAtom.SYSTEMS_ENGINEER
            ])

            # Add based on task
            if 'data' in task.lower():
                professions.append(ProfessionAtom.DATA_SCIENTIST)

            # Add synthesis/optimization in later phases
            if phase in [Phase.COLLAPSE, Phase.BIND]:
                professions.append(ProfessionAtom.INTEGRATOR)
                professions.append(ProfessionAtom.OPTIMIZER)

        else:  # CONTROL
            # Always include risk management
            professions.extend([
                ProfessionAtom.RISK_MANAGER,
                ProfessionAtom.SECURITY_ANALYST
            ])

            # Add based on context
            if context.get('regulatory', False):
                professions.append(ProfessionAtom.COMPLIANCE_OFFICER)

            if context.get('safety_critical', False):
                professions.append(ProfessionAtom.SAFETY_ENGINEER)

            # Add adversarial in early phases
            if phase in [Phase.EXPAND, Phase.TYPE, Phase.ENUMERATE]:
                professions.append(ProfessionAtom.RED_TEAM)

        return professions

    def _get_domain_scope(self, profession: ProfessionAtom, task: str) -> Set[str]:
        """Get domain scope for profession"""
        # Simplified domain detection
        domains = set()
        task_lower = task.lower()

        if 'software' in task_lower or 'code' in task_lower:
            domains.add('software')
        if 'data' in task_lower:
            domains.add('data')
        if 'system' in task_lower or 'architecture' in task_lower:
            domains.add('systems')
        if 'security' in task_lower:
            domains.add('security')

        return domains if domains else {'general'}

    def _get_risk_models(self, profession: ProfessionAtom) -> List[str]:
        """Get risk models for profession"""
        risk_models = {
            ProfessionAtom.SECURITY_ANALYST: ['OWASP_Top_10', 'STRIDE', 'DREAD'],
            ProfessionAtom.SAFETY_ENGINEER: ['FMEA', 'FTA', 'HAZOP'],
            ProfessionAtom.COMPLIANCE_OFFICER: ['GDPR', 'SOC2', 'HIPAA'],
            ProfessionAtom.RISK_MANAGER: ['ISO31000', 'COSO_ERM'],
            ProfessionAtom.RED_TEAM: ['MITRE_ATT&amp;CK', 'Kill_Chain']
        }
        return risk_models.get(profession, [])

    def _get_regulatory_knowledge(self, profession: ProfessionAtom) -> List[str]:
        """Get regulatory knowledge for profession"""
        regulatory = {
            ProfessionAtom.COMPLIANCE_OFFICER: ['GDPR', 'CCPA', 'SOC2', 'ISO27001'],
            ProfessionAtom.SAFETY_ENGINEER: ['IEC61508', 'ISO26262', 'DO-178C'],
            ProfessionAtom.SECURITY_ANALYST: ['NIST', 'CIS', 'PCI-DSS']
        }
        return regulatory.get(profession, [])


class GateCompiler:
    """
    Compiles gate proposals into active gates

    Enforces:
    - invariant protection
    - phase legality
    - non-contradiction
    """

    def __init__(self):
        self.protected_invariants = [
            'confidence_equation',
            'authority_mapping',
            'gate_compiler',
            'verification_channels'
        ]

    def compile_gates(
        self,
        workspace: TypedGenerativeWorkspace,
        phase: Phase
    ) -> List[str]:
        """
        Compile gate proposals into active gates

        Returns list of activated gate IDs
        """
        activated = []

        # Get gate proposals for this phase
        proposals = [gp for gp in workspace.gate_proposals.values()
                    if gp.phase == phase]

        # Sort by risk reduction (highest first)
        proposals.sort(key=lambda gp: gp.risk_reduction_estimate, reverse=True)

        for proposal in proposals:
            # Check if gate is legal
            if self._is_legal_gate(proposal, workspace):
                # Activate gate
                workspace.activate_gate(proposal.id)
                activated.append(proposal.id)

        return activated

    def _is_legal_gate(
        self,
        proposal: GateProposal,
        workspace: TypedGenerativeWorkspace
    ) -> bool:
        """Check if gate proposal is legal"""
        # Check invariant protection
        if any(inv in proposal.target.lower() for inv in self.protected_invariants):
            return False  # Cannot modify protected invariants

        # Check phase legality
        if proposal.phase not in Phase:
            return False

        # Check non-contradiction with existing gates
        active_gates = workspace.get_active_gates()
        for gate in active_gates:
            if self._gates_contradict(proposal, gate):
                return False

        return True

    def _gates_contradict(self, gate1: GateProposal, gate2: GateProposal) -> bool:
        """Check if two gates contradict"""
        # Simplified: gates contradict if they have same target but opposite effects
        if gate1.target == gate2.target:
            if (gate1.effect == 'block' and gate2.effect == 'verify') or \
               (gate1.effect == 'verify' and gate2.effect == 'block'):
                return True
        return False


class TrueSwarmSystem:
    """
    Complete true swarm system

    Coordinates:
    - Exploration swarm (find what could work)
    - Control swarm (find what could fail)
    - Typed Generative Workspace (coordination)
    - Gate compilation (governance synthesis)
    """

    def __init__(self, llm_controller=None):
        self.workspace = TypedGenerativeWorkspace()
        self.spawner = SwarmSpawner(llm_controller=llm_controller)
        self.gate_compiler = GateCompiler()
        self.execution_history: List[Dict[str, Any]] = []
        self._llm = llm_controller

    def execute_phase(
        self,
        phase: Phase,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a phase with dual swarms

        Returns:
        - artifacts generated
        - gates synthesized
        - confidence impact
        - Murphy risk
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE: {phase.value.upper()}")
        logger.info(f"{'='*60}")

        # 1. Spawn exploration swarm
        logger.info("\n🟢 Spawning EXPLORATION swarm...")
        exploration_agents = self.spawner.spawn_swarm(
            mode=SwarmMode.EXPLORATION,
            phase=phase,
            task=task,
            context=context,
            workspace=self.workspace
        )
        logger.info(f"   Spawned {len(exploration_agents)} agents: {[a.instance.profession.value for a in exploration_agents]}")

        # 2. Exploration agents generate artifacts — TRUE PARALLELISM via ThreadPoolExecutor
        logger.info("\n   Generating solution candidates (parallel)...")
        exploration_artifacts = []
        _max_workers = min(len(exploration_agents), 8) if exploration_agents else 1
        with ThreadPoolExecutor(max_workers=_max_workers) as pool:
            futures = {
                pool.submit(agent.generate_artifacts, task, self.workspace, context): agent
                for agent in exploration_agents
            }
            for future in as_completed(futures):
                try:
                    artifacts = future.result(timeout=30)
                    for artifact in artifacts:
                        self.workspace.write_artifact(artifact)
                        exploration_artifacts.append(artifact)
                except Exception as exc:
                    logger.warning("Exploration agent failed: %s", exc)
        logger.info(f"   Generated {len(exploration_artifacts)} artifacts")

        # 3. Spawn control swarm
        logger.info("\n🔴 Spawning CONTROL swarm...")
        control_agents = self.spawner.spawn_swarm(
            mode=SwarmMode.CONTROL,
            phase=phase,
            task=task,
            context=context,
            workspace=self.workspace
        )
        logger.info(f"   Spawned {len(control_agents)} agents: {[a.instance.profession.value for a in control_agents]}")

        # 4. Control agents analyze risks and propose gates — TRUE PARALLELISM
        logger.info("\n   Analyzing risks and proposing gates (parallel)...")
        control_artifacts = []
        _max_ctrl = min(len(control_agents), 8) if control_agents else 1
        with ThreadPoolExecutor(max_workers=_max_ctrl) as pool:
            futures = {
                pool.submit(agent.estimate_risks, self.workspace, context): agent
                for agent in control_agents
            }
            for future in as_completed(futures):
                try:
                    artifacts = future.result(timeout=30)
                    for artifact in artifacts:
                        self.workspace.write_artifact(artifact)
                        control_artifacts.append(artifact)
                except Exception as exc:
                    logger.warning("Control agent failed: %s", exc)
        logger.info(f"   Generated {len(control_artifacts)} risk artifacts")
        logger.info(f"   Proposed {len(self.workspace.gate_proposals)} gates")

        # 5. Compile gates
        logger.info("\n   Compiling gates...")
        activated_gates = self.gate_compiler.compile_gates(self.workspace, phase)
        logger.info(f"   Activated {len(activated_gates)} gates")

        # 6. Compute confidence impact
        total_confidence_impact = sum(a.confidence_impact for a in exploration_artifacts)
        risk_impact = sum(a.confidence_impact for a in control_artifacts)
        net_confidence = total_confidence_impact + risk_impact

        # 7. Compute Murphy risk
        risks = self.workspace.get_artifacts_by_type(ArtifactType.RISK, phase)
        murphy_risk = sum(r.content.get('severity', 0.5) for r in risks) / max(len(risks), 1)

        logger.info("\n📊 Phase Results:")
        logger.info(f"   Exploration artifacts: {len(exploration_artifacts)}")
        logger.info(f"   Control artifacts: {len(control_artifacts)}")
        logger.info(f"   Active gates: {len(activated_gates)}")
        logger.info(f"   Net confidence impact: {net_confidence:+.2f}")
        logger.info(f"   Murphy risk: {murphy_risk:.2f}")

        result = {
            'phase': phase.value,
            'exploration_artifacts': len(exploration_artifacts),
            'control_artifacts': len(control_artifacts),
            'gates_activated': len(activated_gates),
            'confidence_impact': net_confidence,
            'murphy_risk': murphy_risk,
            'exploration_agents': [a.instance.profession.value for a in exploration_agents],
            'control_agents': [a.instance.profession.value for a in control_agents]
        }

        self.execution_history.append(result)

        # Publish phase completion to Rosetta (non-blocking, best-effort)
        try:
            from swarm_rosetta_bridge import get_bridge
            get_bridge().on_phase_complete(
                phase=phase.value,
                artifacts=len(exploration_artifacts) + len(control_artifacts),
                gates=len(activated_gates),
                confidence_impact=net_confidence,
                murphy_risk=murphy_risk,
            )
        except Exception:
            pass

        return result

    def execute_full_cycle(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute full 7-phase cycle"""
        if context is None:
            context = {}

        logger.info(f"\n{'='*60}")
        logger.info("TRUE SWARM SYSTEM - FULL CYCLE")
        logger.info(f"Task: {task}")
        logger.info(f"{'='*60}")

        results = []
        for phase in Phase:
            result = self.execute_phase(phase, task, context)
            results.append(result)

        # Summary
        total_artifacts = sum(r['exploration_artifacts'] + r['control_artifacts'] for r in results)
        total_gates = sum(r['gates_activated'] for r in results)
        final_confidence = sum(r['confidence_impact'] for r in results)
        avg_murphy_risk = sum(r['murphy_risk'] for r in results) / (len(results) or 1)

        logger.info(f"\n{'='*60}")
        logger.info("CYCLE COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total artifacts generated: {total_artifacts}")
        logger.info(f"Total gates activated: {total_gates}")
        logger.info(f"Final confidence: {final_confidence:.2f}")
        logger.info(f"Average Murphy risk: {avg_murphy_risk:.2f}")
        logger.info(f"{'='*60}\n")

        return {
            'task': task,
            'phases': results,
            'total_artifacts': total_artifacts,
            'total_gates': total_gates,
            'final_confidence': final_confidence,
            'avg_murphy_risk': avg_murphy_risk,
            'workspace': self.workspace
        }
