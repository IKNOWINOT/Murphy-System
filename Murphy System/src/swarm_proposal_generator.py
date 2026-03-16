"""
Swarm Proposal Generator for Murphy System
Generates swarm proposals similar to RLM paper structure
Tailored for Murphy System's safety gates and confidence engine
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from llm_controller import LLMController, LLMModel, LLMRequest, ModelCapability
from murphy_repl import MurphyREPL

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class SwarmType(Enum):
    """Types of swarm configurations"""
    SINGLE_AGENT = "single_agent"
    HIERARCHICAL = "hierarchical"
    COLLABORATIVE = "collaborative"
    PIPELINE = "pipeline"
    HYBRID = "hybrid"


@dataclass
class SwarmAgent:
    """Individual agent in the swarm"""
    id: str
    name: str
    role: str
    capabilities: List[str]
    model: LLMModel
    confidence_threshold: float
    safety_gates: List[str] = field(default_factory=list)


@dataclass
class SwarmStep:
    """Step in swarm execution plan"""
    step_id: int
    description: str
    agent_ids: List[str]
    input_sources: List[str]
    output_destination: str
    estimated_time: float
    dependencies: List[int] = field(default_factory=list)


@dataclass
class SafetyGate:
    """Safety gate for swarm execution"""
    gate_id: str
    name: str
    description: str
    check_point: str
    severity: float
    action: str  # 'block', 'warn', 'log'
    confidence_threshold: float


@dataclass
class SwarmProposal:
    """Complete swarm proposal"""
    proposal_id: str
    task_description: str
    task_complexity: TaskComplexity
    swarm_type: SwarmType
    agents: List[SwarmAgent]
    execution_plan: List[SwarmStep]
    safety_gates: List[SafetyGate]
    resource_estimates: Dict[str, Any]
    cost_estimate: float
    confidence_estimate: float
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmExecutionResult:
    """Result of executing a swarm proposal"""
    proposal_id: str
    status: str  # "completed", "failed", "partial"
    step_results: Dict[int, Dict[str, Any]]  # step_id -> {status, output, error, duration_ms}
    total_cost: float
    confidence: float
    execution_time_ms: float
    failed_steps: List[int]
    blocked_by_safety_gate: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SwarmProposalGenerator:
    """
    Generates swarm proposals for Murphy System

    Based on RLM pattern from paper:
    - Recursive decomposition of tasks
    - Code generation for task execution
    - Safety gate integration
    - Confidence-based routing
    """

    def __init__(self, llm_controller: LLMController):
        self.llm_controller = llm_controller
        self.repl = MurphyREPL(llm_controller)
        self.proposal_history: List[SwarmProposal] = []

    async def generate_proposal(
        self,
        task_description: str,
        context: Optional[str] = None
    ) -> SwarmProposal:
        """
        Generate a complete swarm proposal for a task

        Process:
        1. Analyze task complexity
        2. Determine optimal swarm configuration
        3. Design agents and their roles
        4. Create execution plan
        5. Add safety gates
        6. Estimate resources and costs
        """

        # Step 1: Analyze task
        task_analysis = await self._analyze_task(task_description, context)

        # Step 2: Determine swarm type
        swarm_type = self._determine_swarm_type(task_analysis)

        # Step 3: Generate agents
        agents = self._generate_agents(task_analysis, swarm_type)

        # Step 4: Create execution plan
        execution_plan = await self._create_execution_plan(
            task_description,
            agents,
            swarm_type
        )

        # Step 5: Add safety gates
        safety_gates = self._add_safety_gates(execution_plan, task_analysis)

        # Step 6: Estimate resources
        resource_estimates = self._estimate_resources(
            agents,
            execution_plan
        )

        # Step 7: Calculate cost and confidence
        cost_estimate = self._estimate_cost(agents, execution_plan)
        confidence_estimate = self._estimate_confidence(
            task_analysis,
            agents,
            safety_gates
        )

        # Create proposal
        proposal = SwarmProposal(
            proposal_id=f"prop_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            task_description=task_description,
            task_complexity=task_analysis['complexity'],
            swarm_type=swarm_type,
            agents=agents,
            execution_plan=execution_plan,
            safety_gates=safety_gates,
            resource_estimates=resource_estimates,
            cost_estimate=cost_estimate,
            confidence_estimate=confidence_estimate,
            created_at=datetime.now(timezone.utc),
            metadata={
                'task_analysis': task_analysis,
                'context_provided': context is not None,
                'context_length': len(context) if context else 0
            }
        )

        self.proposal_history.append(proposal)
        return proposal

    async def _analyze_task(
        self,
        task_description: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze the task to understand requirements"""

        # Use LLM to analyze task
        analysis_prompt = f"""
Analyze this task and provide a structured analysis:

Task: {task_description}

Provide a JSON response with these fields:
- complexity: (simple|medium|complex|very_complex)
- task_type: (web_app|data_system|ai_system|control_system|general)
- main_components: list of main components needed
- estimated_steps: estimated number of steps
- potential_risks: list of potential risks
- required_capabilities: list of required capabilities (reasoning, code_generation, context_processing, etc.)
"""

        request = LLMRequest(
            prompt=analysis_prompt,
            context=context,
            temperature=0.3,
            max_tokens=1000,
            require_capabilities=[ModelCapability.REASONING]
        )

        response = await self.llm_controller.query_llm(request)

        try:
            analysis = json.loads(response.content)
        except Exception as exc:
            # Fallback analysis
            logger.debug("Suppressed exception: %s", exc)
            analysis = self._fallback_analysis(task_description)

        # Map complexity string to enum
        complexity_mapping = {
            'simple': TaskComplexity.SIMPLE,
            'medium': TaskComplexity.MEDIUM,
            'complex': TaskComplexity.COMPLEX,
            'very_complex': TaskComplexity.VERY_COMPLEX
        }

        analysis['complexity'] = complexity_mapping.get(
            analysis.get('complexity', 'medium'),
            TaskComplexity.MEDIUM
        )

        return analysis

    def _fallback_analysis(self, task_description: str) -> Dict[str, Any]:
        """Fallback analysis when LLM fails"""
        task_lower = task_description.lower()

        # Determine complexity
        if any(word in task_lower for word in ['simple', 'basic', 'easy']):
            complexity = 'simple'
        elif any(word in task_lower for word in ['complex', 'advanced', 'enterprise']):
            complexity = 'complex'
        else:
            complexity = 'medium'

        # Determine task type
        if any(word in task_lower for word in ['app', 'web', 'website']):
            task_type = 'web_app'
        elif any(word in task_lower for word in ['data', 'analytics']):
            task_type = 'data_system'
        elif any(word in task_lower for word in ['ai', 'ml', 'model']):
            task_type = 'ai_system'
        else:
            task_type = 'general'

        return {
            'complexity': complexity,
            'task_type': task_type,
            'main_components': ['core'],
            'estimated_steps': 5,
            'potential_risks': ['complexity_risk'],
            'required_capabilities': ['reasoning']
        }

    def _determine_swarm_type(
        self,
        task_analysis: Dict[str, Any]
    ) -> SwarmType:
        """Determine optimal swarm configuration"""

        complexity = task_analysis['complexity']
        components = task_analysis.get('main_components', [])

        if complexity == TaskComplexity.SIMPLE:
            return SwarmType.SINGLE_AGENT
        elif complexity == TaskComplexity.MEDIUM:
            if len(components) > 2:
                return SwarmType.COLLABORATIVE
            else:
                return SwarmType.HIERARCHICAL
        elif complexity == TaskComplexity.COMPLEX:
            return SwarmType.PIPELINE
        else:  # VERY_COMPLEX
            return SwarmType.HYBRID

    def _generate_agents(
        self,
        task_analysis: Dict[str, Any],
        swarm_type: SwarmType
    ) -> List[SwarmAgent]:
        """Generate agents for the swarm"""

        agents = []
        required_capabilities = task_analysis.get('required_capabilities', [])

        # Base agent always present
        base_agent = SwarmAgent(
            id="agent_0",
            name="Coordinator",
            role="coordinate_swarm",
            capabilities=["coordination", "planning"],
            model=LLMModel.GROQ_LLAMA,
            confidence_threshold=0.85,
            safety_gates=["task_validation", "output_verification"]
        )
        agents.append(base_agent)

        # Add specialized agents based on swarm type
        if swarm_type in [SwarmType.COLLABORATIVE, SwarmType.HIERARCHICAL]:
            # Add reasoning agent
            reasoning_agent = SwarmAgent(
                id="agent_1",
                name="Reasoning Specialist",
                role="complex_reasoning",
                capabilities=["reasoning", "analysis"],
                model=LLMModel.GROQ_LLAMA,
                confidence_threshold=0.90,
                safety_gates=["logical_consistency"]
            )
            agents.append(reasoning_agent)

        if swarm_type in [SwarmType.PIPELINE, SwarmType.HYBRID]:
            # Add code generation agent
            code_agent = SwarmAgent(
                id="agent_2",
                name="Code Generator",
                role="code_generation",
                capabilities=["code_generation", "implementation"],
                model=LLMModel.GROQ_MIXTRAL,
                confidence_threshold=0.85,
                safety_gates=["code_quality", "security_check"]
            )
            agents.append(code_agent)

        if swarm_type == SwarmType.HYBRID:
            # Add context processing agent
            context_agent = SwarmAgent(
                id="agent_3",
                name="Context Processor",
                role="context_analysis",
                capabilities=["context_processing", "summarization"],
                model=LLMModel.GROQ_GEMMA,
                confidence_threshold=0.80,
                safety_gates=["information_loss"]
            )
            agents.append(context_agent)

        return agents

    async def _create_execution_plan(
        self,
        task_description: str,
        agents: List[SwarmAgent],
        swarm_type: SwarmType
    ) -> List[SwarmStep]:
        """Create step-by-step execution plan"""

        plan_prompt = f"""
Create an execution plan for this task:

Task: {task_description}
Swarm Type: {swarm_type.value}
Available Agents: {[agent.name for agent in agents]}

Provide a JSON response with a 'steps' array, where each step has:
- step_id: integer
- description: what the step does
- agent_ids: list of agent IDs to use
- input_sources: where input comes from
- output_destination: where output goes
- estimated_time: estimated time in minutes
- dependencies: list of step IDs this depends on

Format: {{"steps": [...]}}
"""

        request = LLMRequest(
            prompt=plan_prompt,
            temperature=0.5,
            max_tokens=1500,
            require_capabilities=[ModelCapability.SWARM_PLANNING]
        )

        response = await self.llm_controller.query_llm(request)

        try:
            plan_data = json.loads(response.content)
            steps_data = plan_data.get('steps', [])
        except Exception as exc:
            # Fallback to simple plan
            logger.debug("Suppressed exception: %s", exc)
            steps_data = self._fallback_execution_plan(agents)

        # Convert to SwarmStep objects
        steps = []
        for step_data in steps_data:
            step = SwarmStep(
                step_id=step_data.get('step_id', len(steps)),
                description=step_data.get('description', ''),
                agent_ids=step_data.get('agent_ids', []),
                input_sources=step_data.get('input_sources', []),
                output_destination=step_data.get('output_destination', ''),
                estimated_time=step_data.get('estimated_time', 5.0),
                dependencies=step_data.get('dependencies', [])
            )
            steps.append(step)

        return steps

    def _fallback_execution_plan(self, agents: List[SwarmAgent]) -> List[Dict[str, Any]]:
        """Fallback execution plan"""
        steps = [
            {
                'step_id': 0,
                'description': 'Initialize task and validate requirements',
                'agent_ids': [agents[0].id],
                'input_sources': ['user_input'],
                'output_destination': 'task_context',
                'estimated_time': 2.0,
                'dependencies': []
            }
        ]

        if len(agents) > 1:
            steps.append({
                'step_id': 1,
                'description': 'Analyze requirements and plan implementation',
                'agent_ids': [agents[0].id, agents[1].id],
                'input_sources': ['task_context'],
                'output_destination': 'implementation_plan',
                'estimated_time': 10.0,
                'dependencies': [0]
            })

        if len(agents) > 2:
            steps.append({
                'step_id': 2,
                'description': 'Generate and implement solution',
                'agent_ids': [agents[2].id],
                'input_sources': ['implementation_plan'],
                'output_destination': 'final_solution',
                'estimated_time': 15.0,
                'dependencies': [1]
            })

        return steps

    def _add_safety_gates(
        self,
        execution_plan: List[SwarmStep],
        task_analysis: Dict[str, Any]
    ) -> List[SafetyGate]:
        """Add safety gates to the execution plan"""

        gates = []

        # Gate 1: Task validation
        gates.append(SafetyGate(
            gate_id="gate_0",
            name="Task Validation",
            description="Validate task requirements and constraints",
            check_point="before_step_0",
            severity=0.9,
            action="block",
            confidence_threshold=0.80
        ))

        # Gate 2: Input validation
        gates.append(SafetyGate(
            gate_id="gate_1",
            name="Input Validation",
            description="Validate all inputs are safe and appropriate",
            check_point="before_step_1",
            severity=0.85,
            action="block",
            confidence_threshold=0.75
        ))

        # Gate 3: Output verification
        gates.append(SafetyGate(
            gate_id="gate_2",
            name="Output Verification",
            description="Verify outputs meet quality and safety standards",
            check_point="after_last_step",
            severity=0.95,
            action="block",
            confidence_threshold=0.85
        ))

        # Add gates for potential risks
        potential_risks = task_analysis.get('potential_risks', [])

        if 'security' in potential_risks:
            gates.append(SafetyGate(
                gate_id="gate_security",
                name="Security Check",
                description="Check for security vulnerabilities",
                check_point="during_implementation",
                severity=0.95,
                action="block",
                confidence_threshold=0.90
            ))

        return gates

    def _estimate_resources(
        self,
        agents: List[SwarmAgent],
        execution_plan: List[SwarmStep]
    ) -> Dict[str, Any]:
        """Estimate resource requirements for a swarm proposal.

        Cost model:
        - Base compute: ``$0.10 / minute`` of total estimated execution time.
        - Parallel steps get a coordination overhead multiplier because
          concurrent agents require state synchronisation, message passing,
          and additional compute for the orchestrator.
        """

        total_time = sum(step.estimated_time for step in execution_plan)
        parallel_steps = [s for s in execution_plan if not s.dependencies]

        # Base compute cost
        base_cost = total_time * 0.1  # $0.10 per minute average

        # Swarm coordination overhead — scales with agent count and
        # parallelism. Each concurrent agent adds ~$0.02/min of
        # coordination cost (message routing, state sync, health checks).
        agent_count = len(agents)
        parallel_count = len(parallel_steps)
        coordination_cost_per_min = agent_count * 0.02
        coordination_cost = coordination_cost_per_min * (
            sum(s.estimated_time for s in parallel_steps) if parallel_steps
            else 0
        )

        estimated_cost = base_cost + coordination_cost

        return {
            'estimated_time_minutes': total_time,
            'estimated_cost_usd': estimated_cost,
            'base_compute_cost_usd': base_cost,
            'coordination_overhead_usd': round(coordination_cost, 4),
            'agent_count': agent_count,
            'step_count': len(execution_plan),
            'parallel_steps': parallel_count,
        }

    def _estimate_cost(
        self,
        agents: List[SwarmAgent],
        execution_plan: List[SwarmStep]
    ) -> float:
        """Estimate total cost of proposal execution.

        Cost breakdown:
        - **Base compute** — ``$0.10/min × execution time``
        - **Coordination overhead** — ``$0.02/min × agents × parallel time``
        - **Safety gate overhead** — ``$0.05 × number of steps``
        - **Confidence overhead** — ``10%`` of base + coordination cost
        """

        resource_estimates = self._estimate_resources(agents, execution_plan)
        base_cost = resource_estimates['estimated_cost_usd']

        # Safety gate overhead — each step goes through MFGC gates
        safety_gate_cost = len(execution_plan) * 0.05

        # Confidence overhead — margin for re-runs / retries
        confidence_overhead = base_cost * 0.1

        total_cost = base_cost + safety_gate_cost + confidence_overhead

        return round(total_cost, 2)

    def _estimate_confidence(
        self,
        task_analysis: Dict[str, Any],
        agents: List[SwarmAgent],
        safety_gates: List[SafetyGate]
    ) -> float:
        """Estimate confidence level of proposal"""

        # Base confidence from task complexity
        complexity = task_analysis['complexity']
        complexity_confidence = {
            TaskComplexity.SIMPLE: 0.95,
            TaskComplexity.MEDIUM: 0.85,
            TaskComplexity.COMPLEX: 0.75,
            TaskComplexity.VERY_COMPLEX: 0.65
        }.get(complexity, 0.80)

        # Confidence from agent quality
        avg_agent_confidence = sum(
            agent.confidence_threshold for agent in agents
        ) / (len(agents) or 1)

        # Confidence from safety gates
        safety_confidence = 0.85 + (len(safety_gates) * 0.01)

        # Combine confidences
        final_confidence = (
            complexity_confidence * 0.4 +
            avg_agent_confidence * 0.4 +
            safety_confidence * 0.2
        )

        return round(min(final_confidence, 1.0), 2)

    def format_proposal_for_display(self, proposal: SwarmProposal) -> str:
        """Format proposal for display in terminal UI"""

        lines = []
        lines.append("# " + "="*60)
        lines.append("# SWARM PROPOSAL")
        lines.append("# " + "="*60)
        lines.append("")
        lines.append(f"**Proposal ID:** {proposal.proposal_id}")
        lines.append(f"**Task:** {proposal.task_description}")
        lines.append(f"**Complexity:** {proposal.task_complexity.value.upper()}")
        lines.append(f"**Swarm Type:** {proposal.swarm_type.value.replace('_', ' ').title()}")
        lines.append(f"**Confidence:** {proposal.confidence_estimate*100:.1f}%")
        lines.append(f"**Estimated Cost:** ${proposal.cost_estimate:.2f}")
        lines.append(f"**Estimated Time:** {proposal.resource_estimates['estimated_time_minutes']:.1f} minutes")
        lines.append("")

        lines.append("## Agents")
        lines.append("")
        for agent in proposal.agents:
            lines.append(f"- **{agent.name}** (ID: {agent.id})")
            lines.append(f"  - Role: {agent.role}")
            lines.append(f"  - Model: {agent.model.value}")
            lines.append(f"  - Confidence Threshold: {agent.confidence_threshold*100:.1f}%")
            lines.append(f"  - Safety Gates: {', '.join(agent.safety_gates)}")
            lines.append("")

        lines.append("## Execution Plan")
        lines.append("")
        for step in proposal.execution_plan:
            deps = f" (depends on: {step.dependencies})" if step.dependencies else ""
            lines.append(f"**Step {step.step_id}:** {step.description}{deps}")
            lines.append(f"- Agents: {', '.join(step.agent_ids)}")
            lines.append(f"- Estimated Time: {step.estimated_time:.1f} min")
            lines.append("")

        lines.append("## Safety Gates")
        lines.append("")
        for gate in proposal.safety_gates:
            lines.append(f"- **{gate.name}** (Severity: {gate.severity*100:.0f}%)")
            lines.append(f"  - {gate.description}")
            lines.append(f"  - Action: {gate.action.upper()}")
            lines.append(f"  - Confidence Threshold: {gate.confidence_threshold*100:.1f}%")
            lines.append("")

        return "\n".join(lines)

    def get_proposal_history(self) -> List[Dict[str, Any]]:
        """Get history of generated proposals"""
        return [
            {
                'proposal_id': p.proposal_id,
                'task_description': p.task_description,
                'complexity': p.task_complexity.value,
                'confidence': p.confidence_estimate,
                'cost': p.cost_estimate,
                'created_at': p.created_at.isoformat()
            }
            for p in self.proposal_history
        ]

    def execute_proposal(
        self,
        proposal: SwarmProposal,
        budget: float = 100.0
    ) -> SwarmExecutionResult:
        """Execute a swarm proposal synchronously, respecting safety gates and budget.

        Execution steps:
        1. Validate inputs (proposal must not be None; budget must be > 0).
        2. Check all safety gates — any gate with action="block" and
           severity >= 0.7 halts execution immediately.
        3. Build a dependency-ordered execution sequence via topological sort.
        4. Simulate each step and accumulate cost; skip remaining steps if
           the budget is exhausted mid-execution.
        5. Return a ``SwarmExecutionResult`` with per-step outcomes.

        Args:
            proposal: The ``SwarmProposal`` to execute.
            budget:   Maximum cost in USD allowed for this run (default 100.0).

        Returns:
            A ``SwarmExecutionResult`` describing outcomes for every step.

        Raises:
            ValueError: If ``proposal`` is None or ``budget`` is <= 0.
        """
        if proposal is None:
            raise ValueError("proposal must not be None")
        if budget <= 0:
            raise ValueError("budget must be greater than 0")

        wall_start = time.monotonic()

        # Safety gate check — block before executing any step
        for gate in proposal.safety_gates:
            if gate.action == "block" and gate.severity >= 0.7:
                logger.warning(
                    "Execution blocked by safety gate '%s' (severity=%.2f)",
                    gate.gate_id,
                    gate.severity,
                )
                return SwarmExecutionResult(
                    proposal_id=proposal.proposal_id,
                    status="failed",
                    step_results={},
                    total_cost=0.0,
                    confidence=proposal.confidence_estimate,
                    execution_time_ms=(time.monotonic() - wall_start) * 1000,
                    failed_steps=[],
                    blocked_by_safety_gate=gate.gate_id,
                )

        # Topological sort — respects step.dependencies
        # Uses iterative Kahn's algorithm with cycle detection to avoid stack overflow.
        step_map: Dict[int, SwarmStep] = {s.step_id: s for s in proposal.execution_plan}
        ordered: List[SwarmStep] = []
        visited: set[int] = set()

        # Build in-degree map
        in_degree: Dict[int, int] = {s.step_id: 0 for s in proposal.execution_plan}
        for s in proposal.execution_plan:
            for dep_id in s.dependencies:
                if dep_id in step_map:
                    in_degree[s.step_id] = in_degree.get(s.step_id, 0) + 1

        # Kahn's algorithm: start from nodes with no dependencies
        from collections import deque
        queue: deque = deque(
            s for s in proposal.execution_plan if in_degree[s.step_id] == 0
        )
        while queue:
            s = queue.popleft()
            if s.step_id in visited:
                continue
            visited.add(s.step_id)
            ordered.append(s)
            # Decrease in-degree of steps that depend on s
            for candidate in proposal.execution_plan:
                if s.step_id in candidate.dependencies and candidate.step_id not in visited:
                    in_degree[candidate.step_id] -= 1
                    if in_degree[candidate.step_id] <= 0:
                        queue.append(candidate)

        # If not all steps are visited, there is a cycle — append remaining in original order
        if len(ordered) < len(proposal.execution_plan):
            logger.warning(
                "execute_proposal: dependency cycle detected in proposal '%s'; "
                "appending remaining steps in original order.",
                proposal.proposal_id,
            )
            for s in proposal.execution_plan:
                if s.step_id not in visited:
                    ordered.append(s)

        # Per-step cost share
        step_count = len(ordered) or 1
        cost_per_step = proposal.cost_estimate / step_count

        step_results: Dict[int, Dict[str, Any]] = {}
        failed_steps: List[int] = []
        accumulated_cost = 0.0
        overall_status = "completed"

        for i, step in enumerate(ordered):
            if accumulated_cost + cost_per_step > budget:
                # Budget exhausted — mark this and all remaining steps as skipped
                overall_status = "partial"
                for remaining in ordered[i:]:
                    step_results[remaining.step_id] = {
                        "status": "skipped",
                        "reason": "budget_exhausted",
                    }
                    logger.info(
                        "Step %d skipped: budget exhausted (accumulated=%.4f, budget=%.4f)",
                        remaining.step_id,
                        accumulated_cost,
                        budget,
                    )
                break

            step_start = time.monotonic()
            # Simulation-only stub: actual execution delegates to assigned agents
            # via DurableSwarmOrchestrator in the CollaborativeTaskOrchestrator layer.
            stub_output: Dict[str, Any] = {
                "output": f"result_for_step_{step.step_id}",
                "agent_ids": step.agent_ids,
            }
            duration_ms = (time.monotonic() - step_start) * 1000
            accumulated_cost += cost_per_step

            step_results[step.step_id] = {
                "status": "completed",
                "output": stub_output,
                "error": None,
                "duration_ms": duration_ms,
            }
            logger.debug(
                "Step %d completed in %.2f ms (cost so far: %.4f)",
                step.step_id,
                duration_ms,
                accumulated_cost,
            )

        return SwarmExecutionResult(
            proposal_id=proposal.proposal_id,
            status=overall_status,
            step_results=step_results,
            total_cost=round(accumulated_cost, 4),
            confidence=proposal.confidence_estimate,
            execution_time_ms=(time.monotonic() - wall_start) * 1000,
            failed_steps=failed_steps,
            metadata={
                "budget_used": round(accumulated_cost, 4),
                "budget_limit": budget,
                "steps_executed": sum(
                    1 for r in step_results.values() if r.get("status") == "completed"
                ),
                "steps_skipped": sum(
                    1 for r in step_results.values() if r.get("status") == "skipped"
                ),
            },
        )
