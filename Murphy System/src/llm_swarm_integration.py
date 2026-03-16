"""
LLM + Swarm Integration
Combines LLM capabilities with True Swarm System and Memory & Artifacts
"""

import logging

logger = logging.getLogger(__name__)
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from memory_artifact_system import ArtifactState, MemoryArtifactSystem, MemoryPlane

# Import existing systems
from true_swarm_system import ArtifactType, ProfessionAtom, SwarmMode, TrueSwarmSystem

# Try to import LLM
try:
    import requests
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class SwarmCommand(Enum):
    """Swarm control commands"""
    SWARM = "swarm"  # Manual swarm specification
    SWARMRUN = "swarmrun"  # Execute specific swarm
    SWARMMONITOR = "swarmmonitor"  # Monitor swarm execution
    SWARMAUTO = "swarmauto"  # Automatic swarm orchestration


@dataclass
class SwarmConfig:
    """Configuration for swarm execution"""
    swarm_modes: List[SwarmMode]
    profession_atoms: List[ProfessionAtom]
    auto_mode: bool = False
    confidence_threshold: float = 0.7


class LLMSwarmController:
    """
    Integrates LLM with Swarm System
    Provides command interface for swarm control
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.swarm_system = TrueSwarmSystem()
        self.memory_system = MemoryArtifactSystem()
        self.llm_available = self._check_llm()

        # Conversation memory
        self.conversation_history = []

        # Task type confidence tracking
        self.task_confidence = {
            'software': 0.1,
            'business': 0.1,
            'research': 0.1,
            'creative': 0.1,
            'data': 0.1,
            'system': 0.1,
            'problem': 0.1,
            'education': 0.1
        }

    def _check_llm(self) -> bool:
        """Check if LLM is available"""
        if not OLLAMA_AVAILABLE:
            return False
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return False

    def _call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """Call LLM with safety bounds"""
        if not self.llm_available:
            return self._rule_based_response(prompt)

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "tinyllama",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                return self._rule_based_response(prompt)

        except Exception as exc:
            logger.info(f"LLM error: {exc}")
            return self._rule_based_response(prompt)

    def _rule_based_response(self, prompt: str) -> str:
        """Fallback rule-based responses"""
        prompt_lower = prompt.lower()

        if any(word in prompt_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm the MFGC system with swarm capabilities. Use /swarm commands to control swarms, or ask me anything."

        if "capabilities" in prompt_lower or "what can you do" in prompt_lower:
            return """I have several capabilities:

1. **Swarm Commands**:
   - /swarm - Define custom swarm configuration
   - /swarmrun - Execute specific swarm type
   - /swarmmonitor - Monitor swarm execution
   - /swarmauto - Automatic swarm orchestration

2. **LLM Functions**: Natural language understanding and generation

3. **Memory System**: 4-plane memory (Sandbox → Working → Control → Execution)

4. **Domain Expertise**: Software, Business, Research, Creative Writing, Data Analysis, System Design, Problem Solving, Education

5. **Safety**: Dynamic gate synthesis and Murphy prevention

Try: /swarmauto [your task] for automatic swarm orchestration!"""

        if "memory" in prompt_lower:
            state = self.memory_system.get_memory_state()
            return f"""Memory System Status:
- Sandbox: {len(state.get('sandbox', []))} artifacts (exploration)
- Working: {len(state.get('working', []))} artifacts (structured)
- Control: {len(state.get('control', []))} artifacts (governance)
- Execution: {len(state.get('execution', []))} artifacts (committed)

Memory flows unidirectionally: Sandbox → Working → Control → Execution"""

        return "I'm ready to help. Use /swarmauto [task] for automatic swarm orchestration, or ask me anything!"

    def parse_command(self, message: str) -> tuple[Optional[SwarmCommand], str]:
        """Parse swarm commands from message"""
        message = message.strip()

        if message.startswith("/swarm "):
            if message.startswith("/swarmauto "):
                return SwarmCommand.SWARMAUTO, message[11:].strip()
            elif message.startswith("/swarmrun "):
                return SwarmCommand.SWARMRUN, message[10:].strip()
            elif message.startswith("/swarmmonitor"):
                return SwarmCommand.SWARMMONITOR, ""
            else:
                return SwarmCommand.SWARM, message[7:].strip()

        return None, message

    def detect_domain(self, task: str) -> str:
        """Detect domain from task description"""
        task_lower = task.lower()

        # Software keywords
        if any(word in task_lower for word in ["code", "program", "software", "api", "database", "web", "app"]):
            return 'software'

        # Business keywords
        if any(word in task_lower for word in ["business", "strategy", "market", "revenue", "customer", "sales"]):
            return 'business'

        # Research keywords
        if any(word in task_lower for word in ["research", "study", "experiment", "hypothesis", "analysis"]):
            return 'research'

        # Creative keywords
        if any(word in task_lower for word in ["story", "write", "creative", "narrative", "character"]):
            return 'creative'

        # Data keywords
        if any(word in task_lower for word in ["data", "statistics", "analysis", "visualization", "dataset"]):
            return 'data'

        # System keywords
        if any(word in task_lower for word in ["system", "architecture", "design", "infrastructure", "scalable"]):
            return 'system'

        # Problem solving keywords
        if any(word in task_lower for word in ["solve", "problem", "optimize", "improve", "fix"]):
            return 'problem'

        # Education keywords
        if any(word in task_lower for word in ["teach", "learn", "explain", "tutorial", "course"]):
            return 'education'

        return 'problem'  # Default

    def analyze_complexity(self, task: str) -> float:
        """Analyze task complexity (0.0 to 1.0)"""
        complexity = 0.0

        # Length factor
        word_count = len(task.split())
        complexity += min(word_count / 100, 0.3)

        # Technical terms
        technical_terms = ["architecture", "scalable", "distributed", "security", "optimization", "algorithm"]
        complexity += sum(0.1 for term in technical_terms if term in task.lower())

        # Multiple requirements
        if any(word in task.lower() for word in ["and", "also", "additionally", "furthermore"]):
            complexity += 0.2

        return min(complexity, 1.0)

    def execute_swarmauto(self, task: str) -> Dict[str, Any]:
        """
        Automatic swarm orchestration
        Builds confidence through intake, then swarms generate gates and specs
        """
        # Step 1: Detect domain
        domain = self.detect_domain(task)

        # Step 2: Analyze complexity
        complexity = self.analyze_complexity(task)

        # Step 3: Build domain confidence through intake questions
        intake_prompt = f"""Task: {task}
Domain: {domain.value}
Complexity: {complexity:.2f}

Generate 3 clarifying questions to build confidence in understanding this task.
Keep questions brief and specific."""

        intake_questions = self._call_llm(intake_prompt, max_tokens=200)

        # Step 4: Determine swarm configuration based on complexity
        if complexity < 0.3:
            swarm_modes = [SwarmMode.EXPLORATION]
            num_agents = 3
        elif complexity < 0.6:
            swarm_modes = [SwarmMode.EXPLORATION, SwarmMode.CONTROL]
            num_agents = 5
        else:
            swarm_modes = [SwarmMode.EXPLORATION, SwarmMode.CONTROL]
            num_agents = 7

        # Step 5: Execute swarms (both exploration and control)
        results = []
        for swarm_mode in swarm_modes:
            swarm_result = self.swarm_system.execute_dual_swarms(
                task=task,
                num_agents=num_agents
            )
            results.append(swarm_result)

        # Step 6: Store artifacts in memory
        for result in results:
            for artifact in result['artifacts']:
                self.memory_system.store_artifact(
                    artifact_type=artifact['type'],
                    content=artifact['content'],
                    metadata=artifact['metadata']
                )

        # Step 7: Synthesize gates from risks
        gates = []
        for result in results:
            for artifact in result['artifacts']:
                if artifact['type'] == ArtifactType.RISK:
                    gate = self._synthesize_gate_from_risk(artifact)
                    gates.append(gate)

        # Step 8: Update domain confidence
        self.task_confidence[domain] = min(
            self.task_confidence[domain] + 0.1,
            1.0
        )

        # Step 9: Generate deliverable specification
        deliverable_spec = self._generate_deliverable_spec(task, results, gates)

        # Step 10: Calculate confidence
        confidence = self._calculate_confidence(results, gates)

        # Step 11: Generate response based on confidence
        target_words = int(100 + (10000 - 100) * confidence)
        response = self._generate_response(task, results, gates, deliverable_spec, target_words)

        return {
            'response': response,
            'confidence': confidence,
            'domain': domain,
            'complexity': complexity,
            'intake_questions': intake_questions,
            'swarm_types': [sm.value for sm in swarm_modes],
            'artifacts_created': sum(len(r.get('artifacts', [])) for r in results),
            'gates_synthesized': len(gates),
            'deliverable_spec': deliverable_spec,
            'memory_state': self._get_memory_state(),
            'domain_confidence': self.task_confidence[domain]
        }

    def _synthesize_gate_from_risk(self, risk_artifact: Dict) -> Dict:
        """Synthesize a gate from a risk artifact"""
        return {
            'type': 'safety_gate',
            'risk': risk_artifact['content'],
            'condition': f"Verify: {risk_artifact['content']}",
            'action': 'Block if unverified',
            'confidence_required': 0.8
        }

    def _generate_deliverable_spec(self, task: str, results: List, gates: List) -> Dict:
        """Generate specification for deliverable"""
        return {
            'task': task,
            'format': 'structured_response',
            'sections': ['overview', 'analysis', 'recommendations', 'risks', 'next_steps'],
            'safety_gates': len(gates),
            'verification_required': len(gates) > 0
        }

    def _calculate_confidence(self, results: List, gates: List) -> float:
        """Calculate overall confidence"""
        # Base confidence from swarm results
        base_confidence = sum(r.get('confidence', 0.5) for r in results) / (len(results) or 1)

        # Boost from gates (more gates = more safety = higher confidence)
        gate_boost = min(len(gates) * 0.05, 0.3)

        return min(base_confidence + gate_boost, 1.0)

    def _generate_response(self, task: str, results: List, gates: List, spec: Dict, target_words: int) -> str:
        """Generate final response based on confidence level"""
        # Collect all artifacts
        hypotheses = []
        risks = []
        constraints = []
        solutions = []

        for result in results:
            for artifact in result['artifacts']:
                if artifact['type'] == ArtifactType.HYPOTHESIS:
                    hypotheses.append(artifact['content'])
                elif artifact['type'] == ArtifactType.RISK:
                    risks.append(artifact['content'])
                elif artifact['type'] == ArtifactType.CONSTRAINT:
                    constraints.append(artifact['content'])
                elif artifact['type'] == ArtifactType.SOLUTION_CANDIDATE:
                    solutions.append(artifact['content'])

        # Build response
        response_parts = []

        # Overview
        response_parts.append(f"## Task Analysis: {task}\n")
        response_parts.append(f"**Swarms Executed:** {len(results)}")
        response_parts.append(f"**Artifacts Generated:** {sum(len(r['artifacts']) for r in results)}")
        response_parts.append(f"**Safety Gates:** {len(gates)}\n")

        # Hypotheses
        if hypotheses:
            response_parts.append("## Exploration Phase\n")
            for i, hyp in enumerate(hypotheses[:3], 1):
                response_parts.append(f"{i}. {hyp}")
            response_parts.append("")

        # Solutions
        if solutions:
            response_parts.append("## Solution Candidates\n")
            for i, sol in enumerate(solutions[:3], 1):
                response_parts.append(f"**Option {i}:** {sol}")
            response_parts.append("")

        # Risks
        if risks:
            response_parts.append("## Risk Analysis\n")
            for i, risk in enumerate(risks[:3], 1):
                response_parts.append(f"⚠️ {risk}")
            response_parts.append("")

        # Gates
        if gates:
            response_parts.append("## Safety Gates Synthesized\n")
            for i, gate in enumerate(gates[:3], 1):
                response_parts.append(f"🛡️ Gate {i}: {gate['condition']}")
            response_parts.append("")

        # Constraints
        if constraints:
            response_parts.append("## Constraints\n")
            for i, constraint in enumerate(constraints[:3], 1):
                response_parts.append(f"• {constraint}")
            response_parts.append("")

        # Recommendations
        response_parts.append("## Recommendations\n")
        if solutions:
            response_parts.append(f"Based on swarm analysis, I recommend: {solutions[0]}")
        response_parts.append("\n**Next Steps:**")
        response_parts.append("1. Review safety gates and verify constraints")
        response_parts.append("2. Select solution candidate for implementation")
        response_parts.append("3. Execute with continuous monitoring")

        return "\n".join(response_parts)

    def process_message(self, message: str) -> Dict[str, Any]:
        """Process user message"""
        # Parse for commands
        command, content = self.parse_command(message)

        if command == SwarmCommand.SWARMAUTO:
            return self.execute_swarmauto(content)

        elif command == SwarmCommand.SWARMMONITOR:
            state = self.memory_system.get_memory_state()
            return {
                'response': f"""## Swarm Monitor

**Memory State:**
- Sandbox: {len(state.get('sandbox', []))} artifacts
- Working: {len(state.get('working', []))} artifacts
- Control: {len(state.get('control', []))} artifacts
- Execution: {len(state.get('execution', []))} artifacts

**Task Confidence:**
{chr(10).join(f'- {task_type}: {conf:.1%}' for task_type, conf in self.task_confidence.items() if conf > 0.1)}

Use /swarmauto [task] to execute swarms.""",
                'confidence': 1.0,
                'memory_state': state
            }

        else:
            # Regular conversation with LLM
            response = self._call_llm(message, max_tokens=500)

            return {
                'response': response,
                'confidence': 0.7 if self.llm_available else 0.5,
                'memory_state': self._get_memory_state()
            }

    def _get_memory_state(self) -> Dict[str, Any]:
        """Get memory state from all planes"""
        return {
            'sandbox': self.memory_system.sandbox.read_all(),
            'working': self.memory_system.working.read_by_phase('all'),
            'control': [self.memory_system.control.read_state()],
            'execution': self.memory_system.execution.read_all()
        }

    def clear_state(self):
        """Clear system state"""
        self.conversation_history = []
        self.memory_system = MemoryArtifactSystem()
        self.task_confidence = {
            'software': 0.1,
            'business': 0.1,
            'research': 0.1,
            'creative': 0.1,
            'data': 0.1,
            'system': 0.1,
            'problem': 0.1,
            'education': 0.1
        }
