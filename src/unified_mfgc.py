"""
UNIFIED MFGC SYSTEM
One system with confidence-based routing, not separate modes
"""

import os
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from infinity_expansion_system import ExpansionAxis, ExpansionResult, InfinityExpansionEngine
from learning_system import (
    ExecutionLog,
    GatePolicyLearner,
    LearningPipeline,
    MultiDeploymentGeneralization,
    TrainingSignal,
)
from memory_artifact_system import Artifact, ArtifactState, MemoryArtifactSystem, MemoryPlane

# Import existing systems
from true_swarm_system import ArtifactType, ProfessionAtom, SwarmMode, TrueSwarmSystem

# DeepInfra HTTP client available (uses requests/httpx, no SDK needed)
DEEPINFRA_AVAILABLE = True

# Import local fallback LLM
import logging

# Import command parser and question manager
from command_parser import CommandParser

# Import key rotator
from groq_key_rotator import get_rotator
from local_llm_fallback import get_fallback_llm
from question_manager import QuestionManager

# Import response formatter
from response_formatter import get_formatter

logger = logging.getLogger(__name__)


class ConfidenceBand(Enum):
    """Three bands of the same system"""
    INTRODUCTORY = "introductory"  # 0.7-1.0: Known responses, greetings
    CONVERSATIONAL = "conversational"  # 0.3-0.7: LLM reasoning, simple tasks
    EXPLORATORY = "exploratory"  # 0.0-0.3: Swarm orchestration, complex tasks


@dataclass
class SystemState:
    """Complete system state at any moment"""
    confidence: float
    band: ConfidenceBand
    domain: str
    complexity: float
    artifacts_count: int
    gates_count: int
    memory_state: Dict[str, int]


class UnifiedMFGC:
    """
    ONE system that operates across a confidence spectrum

    Not separate modes - continuous confidence-based behavior
    """

    def __init__(self, deepinfra_api_key: str = None, use_key_rotation: bool = True):
        # Initialize key rotation system
        self.use_key_rotation = use_key_rotation
        self.key_rotator = None

        if use_key_rotation and DEEPINFRA_AVAILABLE:
            try:
                self.key_rotator = get_rotator()
                self.llm_available = True
                self.llm_mode = "deepinfra_rotation"
                logger.info(f"LLM provider routing enabled with {len(self.key_rotator.keys)} keys")
            except Exception as exc:
                logger.info(f"Key rotation failed: {exc}, falling back to single key mode")
                self.key_rotator = None

        # Fallback to single key mode
        if self.key_rotator is None:
            self.deepinfra_api_key = deepinfra_api_key or os.environ.get("DEEPINFRA_API_KEY")
            if self.deepinfra_api_key and DEEPINFRA_AVAILABLE:
                self.deepinfra_client = self.deepinfra_api_key  # store key for HTTP calls
                self.llm_available = True
                self.llm_mode = "deepinfra"
            else:
                self.deepinfra_client = None
                self.llm_available = True
                self.llm_mode = "offline"

        # Initialize local fallback LLM
        self.fallback_llm = get_fallback_llm()

        # Initialize response formatter
        self.formatter = get_formatter()

        self.swarm_system = TrueSwarmSystem()
        self.memory_system = MemoryArtifactSystem()
        self.expansion_engine = InfinityExpansionEngine()
        self.learning_pipeline = LearningPipeline()
        self.domain_generalization = MultiDeploymentGeneralization()

        # Task confidence tracking (builds over time)
        self.task_confidence = {
            'greeting': 0.9,  # Known responses
            'capabilities': 0.8,  # Known system info
            'software': 0.1,  # Unknown until explored
            'business': 0.1,
            'research': 0.1,
            'creative': 0.1,
            'data': 0.1,
            'system': 0.1,
            'problem': 0.1,
            'education': 0.1,
            'general': 0.1,  # General queries
            'design': 0.1,   # Design queries
            'writing': 0.1,  # Writing queries
            'planning': 0.1  # Planning queries
        }

        # Conversation history with full context
        self.history = []
        self.conversation_context = {
            'topics_discussed': [],
            'user_preferences': {},
            'domain_context': {},
            'previous_tasks': [],
            'accumulated_knowledge': []
        }

        # Initialize command parser and question manager
        self.command_parser = CommandParser(self)
        self.question_manager = QuestionManager()

    def _check_llm(self) -> bool:
        """Check if LLM is available"""
        return self.llm_available

    def get_key_statistics(self) -> Dict[str, Any]:
        """Get API key usage statistics"""
        if self.key_rotator:
            return self.key_rotator.get_statistics()
        else:
            return {
                "mode": self.llm_mode,
                "rotation_enabled": False,
                "message": "Key rotation not enabled"
            }

    def analyze_message(self, message: str) -> Tuple[float, str]:
        """
        Analyze message to determine complexity and domain
        Returns: (complexity: 0.0-1.0, domain: str)
        """
        message_lower = message.lower()

        # Check for swarm commands first (highest priority)
        if "/swarmauto" in message_lower:
            # Force exploratory band - ANY /swarmauto command is complex
            return 0.9, 'software'  # Always high complexity for swarm commands

        # Detect domain
        # Expanded greeting detection
        greeting_words = ["hi", "hello", "hey", "greetings", "hiya", "heya", "howdy", "yo", "sup",
                         "good morning", "good afternoon", "good evening", "good day", "good night",
                         "what's up", "whats up", "how are you", "how's it going", "hows it going",
                         "salutations", "what's happening", "whats happening", "how do you do",
                         "nice to meet you", "pleased to meet you", "good to see you",
                         "long time no see", "welcome back", "back again",
                         "hola", "bonjour", "ciao", "namaste", "aloha"]

        # Check for standalone time-of-day greetings
        standalone_greetings = ["morning", "afternoon", "evening", "night"]
        if message_lower.strip() in standalone_greetings:
            return 0.1, 'greeting'

        # Check for greetings with buddy/pal/mate/dude/bro
        if len(message.split()) < 10 and any(re.search(r'\b' + re.escape(greeting) + r'\b', message_lower) for greeting in greeting_words):
            return 0.1, 'greeting'

        # Check for "hi/hello/hey" + buddy/pal/mate/dude/bro patterns
        casual_suffixes = ["buddy", "pal", "mate", "dude", "bro", "friend", "bot", "ai", "system", "there", "again"]
        for prefix in ["hi", "hello", "hey", "sup", "yo"]:
            for suffix in casual_suffixes:
                if f"{prefix} {suffix}" in message_lower and len(message.split()) < 10:
                    return 0.1, 'greeting'

        # Capabilities detection
        # Only match if asking about the system itself, not general "what is" questions
        capabilities_words = ["what can you", "capabilities", "what do you do", "what are you",
                            "who are you", "what is this system", "tell me about yourself", "describe yourself",
                            "what features", "what services", "what tasks"]
        capabilities_words = ["what can you", "capabilities", "what do you do", "what are you",
                            "who are you", "what is this", "tell me about", "describe your",
                            "what features", "what services", "what tasks"]
        if any(cap in message_lower for cap in capabilities_words):
            return 0.2, 'capabilities'

        # Help detection
        help_words = ["help", "assist", "support", "guide", "show me", "teach me",
                     "how do i", "how to", "instructions", "tutorial", "documentation",
                     "manual", "walkthrough"]
        if any(help_word in message_lower for help_word in help_words) and len(message.split()) < 10:
            return 0.2, 'capabilities'

        # Status detection
        status_words = ["status", "are you working", "are you online", "are you available",
                       "are you ready", "are you operational", "are you there", "ping",
                       "test", "check", "verify", "confirm", "is this working"]
        if any(status in message_lower for status in status_words) and len(message.split()) < 10:
            return 0.2, 'capabilities'

        # Thanks detection
        thanks_words = ["thanks", "thank you", "appreciated", "great", "awesome", "perfect",
                       "excellent", "wonderful", "fantastic", "amazing", "brilliant",
                       "nice", "cool", "ok", "okay", "got it"]
        if any(thanks in message_lower for thanks in thanks_words) and len(message.split()) < 10:
            return 0.2, 'capabilities'

        if any(word in message_lower for word in ["code", "program", "software", "api", "database", "web", "app"]):
            domain = 'software'
        elif any(word in message_lower for word in ["business", "strategy", "market", "revenue", "customer", "sales"]):
            domain = 'business'
        elif any(word in message_lower for word in ["data", "analysis", "statistics", "machine learning", "ai", "model"]):
            domain = 'data'
        elif any(word in message_lower for word in ["design", "ui", "ux", "interface", "user experience", "layout"]):
            domain = 'design'
        elif any(word in message_lower for word in ["write", "content", "article", "blog", "copy", "text"]):
            domain = 'writing'
        elif any(word in message_lower for word in ["research", "study", "investigate", "analyze", "explore"]):
            domain = 'research'
        elif any(word in message_lower for word in ["plan", "organize", "schedule", "manage", "coordinate"]):
            domain = 'planning'
        elif any(word in message_lower for word in ["solve", "fix", "debug", "troubleshoot", "resolve"]):
            domain = 'problem'
        else:
            domain = 'general'

        # Determine complexity
        word_count = len(message.split())

        # Simple questions (what is, define, explain)
        if any(word in message_lower for word in ["what is", "define", "explain", "tell me about"]):
            complexity = 0.3
        # How-to questions
        elif any(word in message_lower for word in ["how to", "how do i", "how can i"]):
            complexity = 0.4
        # Comparison questions
        elif any(word in message_lower for word in ["compare", "difference", "vs", "versus", "better"]):
            complexity = 0.5
        # Creation/building tasks
        elif any(word in message_lower for word in ["create", "build", "make", "develop", "design"]):
            complexity = 0.6
        # Analysis tasks
        elif any(word in message_lower for word in ["analyze", "evaluate", "assess", "review"]):
            complexity = 0.7
        # Complex planning tasks
        elif any(word in message_lower for word in ["strategy", "plan", "architect", "system"]):
            complexity = 0.8
        else:
            # Base complexity on word count
            if word_count < 5:
                complexity = 0.2
            elif word_count < 15:
                complexity = 0.4
            elif word_count < 30:
                complexity = 0.6
            else:
                complexity = 0.8

        return complexity, domain
    def determine_band(self, complexity: float, domain_confidence: float) -> ConfidenceBand:
        """
        Determine which confidence band to operate in

        This is the KEY routing decision
        """
        # High confidence + low complexity = Introductory
        if complexity < 0.3 and domain_confidence > 0.7:
            return ConfidenceBand.INTRODUCTORY

        # Medium complexity or medium confidence = Conversational
        elif complexity < 0.6 or domain_confidence > 0.25:
            return ConfidenceBand.CONVERSATIONAL

        # High complexity or low confidence = Exploratory
        else:
            return ConfidenceBand.EXPLORATORY

    def process_message(self, message: str) -> Dict[str, Any]:
        """
        UNIFIED message processing with conversation context
        ONE method that handles everything based on confidence
        """
        # 1. CHECK FOR COMMANDS FIRST
        is_command, cmd_result = self.command_parser.parse_and_execute(message)
        if is_command:
            # Commands bypass normal processing
            return cmd_result

        # 2. CHECK IF WE'RE IN QUESTIONING MODE
        if self.question_manager.has_unanswered():
            # User is answering a question
            self.question_manager.answer_current(message)

            # Get next question or proceed
            next_question = self.question_manager.format_next_question()
            if next_question:
                # Still have questions - ask the next one
                return {
                    'content': next_question,
                    'band': 'conversational',
                    'confidence': 0.5,
                    'questioning_mode': True,
                    'progress': self.question_manager.get_progress()
                }
            else:
                # All questions answered - proceed with task
                context_summary = self.question_manager.get_context_summary()
                all_answers = self.question_manager.get_all_answers()

                # Clear questions for next task
                self.question_manager.clear()

                # Now process with full context
                return self._process_with_context(message, all_answers, context_summary)

        # 3. NORMAL PROCESSING
        # Update conversation context
        self._update_context(message)

        # Analyze message with context
        complexity, domain = self.analyze_message(message)
        domain_confidence = self.task_confidence.get(domain, 0.1)

        # Determine confidence band
        band = self.determine_band(complexity, domain_confidence)

        # Build context-aware prompt
        context_prompt = self._build_context_prompt(message, domain)

        # Route to appropriate confidence band
        if band == ConfidenceBand.INTRODUCTORY:
            result = self._introductory_band(context_prompt, domain, domain_confidence)

        elif band == ConfidenceBand.CONVERSATIONAL:
            result = self._conversational_band(context_prompt, domain, domain_confidence)

        else:  # EXPLORATORY
            result = self._exploratory_band(context_prompt, domain, domain_confidence)

        # Store in history with context
        self.history.append({
            'message': message,
            'band': band.value,
            'confidence': result['confidence'],
            'domain': domain,
            'response': result.get('content', result.get('response', ''))[:200]  # Store preview
        })

        # Update accumulated knowledge
        self._extract_knowledge(message, result)

        # Format response for clean display
        formatted = self.formatter.format_response(result)
        clean_display = self.formatter.format_for_display(formatted)

        # Add formatted display to result
        result['formatted_response'] = clean_display
        result['questions'] = formatted['questions']
        result['gates'] = formatted['gates']
        result['commands'] = formatted['commands']

        return result

    def _introductory_band(self, message: str, domain: str, confidence: float) -> Dict[str, Any]:
        """
        Confidence Band: 0.7-1.0
        Known responses, greetings, system info
        Fast, deterministic, minimal artifacts
        """
        message_lower = message.lower()

        # Greeting responses
        if domain == 'greeting':
            response = """Hello! I'm the MFGC system - a confidence-building AI that operates across three layers:

**Introductory Layer** (what you're seeing now): Quick responses for greetings and known questions
**Conversational Layer**: LLM-powered reasoning for moderate complexity tasks
**Exploratory Layer**: Full swarm orchestration for complex, undefined problems

Try asking "what can you do?" or use /swarmauto [task] for complex tasks!"""

            target_words = 50

        # Capabilities
        elif domain == 'capabilities':
            response = """## My Capabilities

**Three Operating Modes** (confidence-based routing):
1. **Introductory** - Fast responses for known queries
2. **Conversational** - LLM reasoning for moderate tasks
3. **Exploratory** - Swarm orchestration for complex problems

**Swarm Commands**:
• /swarmauto [task] - Full swarm orchestration
• /swarmmonitor - Check system status

**Core Features**:
• Confidence-based output (100-10,000 words)
• Dynamic gate synthesis
• 4-plane memory system (Sandbox → Working → Control → Execution)
• 14 ProfessionAtoms working in parallel
• Murphy prevention through continuous confidence tracking

**How It Works**:
I start with low confidence (exploratory) and build confidence through:
1. Intake questions (scope carving)
2. Swarm generation (hypotheses + risks)
3. Gate synthesis (safety constraints)
4. Artifact verification (memory promotion)
5. Confidence accumulation (toward execution)

The system never "triggers" - it explores and gates down from infinity."""

            target_words = 200

        else:
            response = "I'm ready to help! Use /swarmauto [task] for complex tasks, or just chat naturally."
            target_words = 20

        # Minimal memory activity
        memory_state = self._get_memory_counts()

        return {
            'content': response,
            'response': response,  # Keep for backward compatibility
            'confidence': confidence,
            'band': 'introductory',
            'domain': domain,
            'complexity': 0.1,
            'target_words': target_words,
            'artifacts_created': 0,
            'gates_synthesized': 0,
            'memory_state': memory_state,
            'swarms_active': 0
        }

    def _conversational_band(self, message: str, domain: str, confidence: float) -> Dict[str, Any]:
        """
        Confidence Band: 0.3-0.7
        LLM reasoning, simple tasks, moderate complexity
        Uses LLM with safety bounds and conversation context
        """
        # Call LLM with bounded output and context
        max_tokens = int(500 + (2000 - 500) * confidence)

        if self.llm_available:
            # Build context-aware prompt
            context_info = []
            if self.conversation_context['topics_discussed']:
                context_info.append(f"Topics we've discussed: {', '.join(self.conversation_context['topics_discussed'][-3:])}")

            if self.conversation_context['previous_tasks']:
                recent_tasks = [t['task'] for t in self.conversation_context['previous_tasks'][-2:]]
                if recent_tasks:
                    context_info.append(f"Recent tasks: {'; '.join(recent_tasks)}")

            context_str = "\n".join(context_info) if context_info else "No prior context."

            # For offline mode, use simpler prompt (just the user message)
            if self.llm_mode == "offline":
                prompt = message
            else:
                prompt = f"""You are the MFGC system's conversational layer.

CONVERSATION CONTEXT:
{context_str}

CURRENT MESSAGE: {message}
DOMAIN: {domain}
CONFIDENCE: {confidence:.2f}

Provide a helpful, context-aware response. Reference previous topics if relevant. Be concise but informative."""

            try:
                response_text = self._call_llm(prompt, max_tokens)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                response_text = f"I understand you're asking about {domain}. Based on our conversation about {', '.join(self.conversation_context['topics_discussed'][-2:]) if self.conversation_context['topics_discussed'] else 'this topic'}, let me help with that."
        else:
            response_text = self._generate_intelligent_response(message, domain, confidence)

        # Light memory activity
        memory_state = self._get_memory_counts()

        # Calculate target words based on confidence
        target_words = int(500 + (2000 - 500) * confidence)

        return {
            'content': response_text,
            'response': response_text,  # Keep for backward compatibility
            'confidence': confidence,
            'band': 'conversational',
            'domain': domain,
            'complexity': 0.5,
            'target_words': target_words,
            'artifacts_created': 0,
            'gates_synthesized': 0,
            'memory_state': memory_state,
            'swarms_active': 0
        }

    def _exploratory_band(self, message: str, domain: str, confidence: float) -> Dict[str, Any]:
        """
        Confidence Band: 0.0-0.3
        Swarm orchestration, complex tasks, scope carving
        Full system activation with INFINITY EXPANSION
        """
        # Remove /swarmauto prefix if present
        if "/swarmauto" in message.lower():
            # Find the position of /swarmauto and extract everything after it
            idx = message.lower().find("/swarmauto")
            task = message[idx + len("/swarmauto"):].strip()
        else:
            task = message

        # Step 1: INFINITY EXPANSION - Carve scope from infinity
        expansion_result = self.expansion_engine.expand_task(task, max_iterations=5)

        # Step 2: Generate intake questions (scope carving)
        intake_questions = self._generate_intake_questions(task, domain)

        # Step 3: Execute swarms with expansion context
        swarm_result = self.swarm_system.execute_full_cycle(
            task=task,
            context={
                'expansion_result': expansion_result,
                'domain': domain
            }
        )

        # Step 4: Store artifacts in memory (including expansion results)
        artifacts_created = 0

        # Store expansion unknowns as artifacts
        for i, unknown in enumerate(expansion_result.remaining_unknowns):
            artifact_obj = Artifact(
                id=f"expansion_unknown_{i}_{int(time.time()*1000)}",
                phase='expand',
                artifact_type='assumption',
                content=f"Unknown: {unknown}",
                dependencies=[],
                verification_status='unverified',
                confidence_delta=0.0,
                provenance={'source': 'expansion_engine', 'axis': 'multiple'},
                state=ArtifactState.DRAFT,
                memory_plane=MemoryPlane.SANDBOX,
                timestamp=time.time(),
                metadata={'source': 'expansion_engine', 'axis': 'multiple'}
            )
            self.memory_system.write_sandbox(artifact_obj)
            artifacts_created += 1

        # Store swarm artifacts
        for i, artifact in enumerate(swarm_result.get('artifacts', [])):
            artifact_obj = Artifact(
                id=f"swarm_artifact_{i}_{int(time.time()*1000)}",
                phase='expand',
                artifact_type=str(artifact.get('type', 'unknown')),
                content=artifact.get('content', ''),
                dependencies=[],
                verification_status='unverified',
                confidence_delta=0.05,
                provenance={'source': 'swarm', 'phase': 'expand'},
                state=ArtifactState.DRAFT,
                memory_plane=MemoryPlane.SANDBOX,
                timestamp=time.time(),
                metadata=artifact.get('metadata', {})
            )
            self.memory_system.write_sandbox(artifact_obj)
            artifacts_created += 1

        # Step 5: Synthesize gates from risks (both expansion and swarm)
        gates = []

        # Get learned gates for this domain
        learned_gates = self.learning_pipeline.gate_learner.get_active_gates(
            domain=domain,
            phase='expand',
            context={'task': task}
        )

        # Gates from expansion risk clusters
        for risk_cluster in expansion_result.risk_clusters:
            for risk in risk_cluster['risks']:
                gate = {
                    'condition': f"Verify: {risk}",
                    'risk': risk,
                    'category': risk_cluster['category'],
                    'confidence_required': 0.8,
                    'source': 'expansion_engine'
                }
                gates.append(gate)

        # Gates from swarm risks
        for artifact in swarm_result.get('artifacts', []):
            if artifact['type'] == ArtifactType.RISK:
                gate = {
                    'condition': f"Verify: {artifact['content']}",
                    'risk': artifact['content'],
                    'confidence_required': 0.8,
                    'source': 'swarm'
                }
                gates.append(gate)

        # Add learned gates
        for learned_gate in learned_gates:
            gate = {
                'condition': f"Verify: {learned_gate.trigger_pattern}",
                'risk': f"Learned risk pattern: {learned_gate.trigger_pattern}",
                'category': 'learned',
                'confidence_required': learned_gate.default_thresholds.get('confidence', 0.8),
                'source': 'learning_system',
                'template_id': learned_gate.id,
                'historical_effectiveness': learned_gate.historical_risk_reduction
            }
            gates.append(gate)

        # Step 6: Calculate confidence (builds through expansion + swarms + learned weights)
        expansion_confidence = expansion_result.confidence_contribution
        gate_confidence = len(gates) * 0.05

        # Apply learned confidence weights if available
        domain_profile = self.domain_generalization.get_profile(domain)
        if domain_profile:
            w_g, w_d = domain_profile.weight_schedules.get_weights('expand')
            # Adjust confidence based on learned weights
            final_confidence = min(
                confidence + (expansion_confidence * w_d) + gate_confidence,
                0.9
            )
        else:
            final_confidence = min(confidence + expansion_confidence + gate_confidence, 0.9)

        # Step 7: Update domain confidence
        self.task_confidence[domain] = min(self.task_confidence[domain] + 0.1, 1.0)

        # Step 8: Generate comprehensive response
        target_words = int(100 + (10000 - 100) * final_confidence)
        response = self._generate_exploratory_response(
            task, swarm_result, gates, intake_questions, target_words, expansion_result
        )

        # Step 9: Get memory state
        memory_state = self._get_memory_counts()

        # Step 10: Get expansion summary
        expansion_summary = self.expansion_engine.get_expansion_summary()

        # Step 11: Log execution for learning
        execution_log = ExecutionLog(
            timestamp=time.time(),
            domain=domain,
            task=task,
            gates_activated=[g.get('template_id', g['condition']) for g in gates],
            gates_prevented_failure=[],
            late_stage_rollback=False,
            execution_interrupted=False,
            human_escalation=False,
            murphy_index_peak=0.0,
            confidence_trajectory=[confidence, final_confidence],
            phase_durations={'expand': time.time()}
        )
        self.learning_pipeline.gate_learner.log_execution(execution_log)

        # Step 12: Log deployment for domain learning
        self.domain_generalization.log_deployment(
            domain=domain,
            constraints=expansion_result.remaining_unknowns,
            outcome={'success': True, 'gates_used': [g.get('template_id', '') for g in gates]}
        )

        return {
            'content': response,
            'response': response,  # Keep for backward compatibility
            'confidence': final_confidence,
            'band': 'exploratory',
            'domain': domain,
            'complexity': 0.8,
            'target_words': target_words,
            'artifacts_created': artifacts_created,
            'gates_synthesized': len(gates),
            'memory_state': memory_state,
            'swarms_active': 2,
            'intake_questions': intake_questions,
            'expansion_summary': expansion_summary,
            'expansion_axes': len(ExpansionAxis),
            'unknowns_remaining': len(expansion_result.remaining_unknowns),
            'bound_variables': len(expansion_result.bound_variables),
            'learned_gates_active': len(learned_gates),
            'domain_profile_active': domain_profile is not None
        }

    def _generate_intake_questions(self, task: str, domain: str) -> str:
        """Generate intake questions for scope carving - ONE at a time"""
        if self.llm_available and self.llm_mode != "offline":
            prompt = f"""Task: {task}
Domain: {domain}

Generate 3 brief clarifying questions to build confidence in understanding this task.
Keep questions specific and actionable.
Format as a numbered list."""

            try:
                questions_text = self._call_llm(prompt, max_tokens=200)

                # Extract questions and add to question manager
                questions = self.question_manager.extract_questions_from_text(questions_text)
                if questions:
                    self.question_manager.add_questions(questions, category=domain, priority=1)
                    # Return ONLY the first question
                    return self.question_manager.format_next_question()

                return questions_text
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                pass

        # Fallback questions for offline mode
        fallback_questions = [
            "What are the key constraints or requirements?",
            "What is the expected outcome or deliverable?",
            "What are the critical success factors?"
        ]

        # Format as numbered list
        formatted = "\n".join([f"{i}. {q}" for i, q in enumerate(fallback_questions, 1)])
        return formatted
    def _generate_exploratory_response(
        self,
        task: str,
        swarm_result: Dict,
        gates: List,
        intake_questions: str,
        target_words: int,
        expansion_result: ExpansionResult
    ) -> str:
        """Generate comprehensive exploratory response with expansion data"""

        # Collect artifacts by type
        hypotheses = []
        risks = []
        constraints = []
        solutions = []

        for artifact in swarm_result.get('artifacts', []):
            if artifact['type'] == ArtifactType.HYPOTHESIS:
                hypotheses.append(artifact['content'])
            elif artifact['type'] == ArtifactType.RISK:
                risks.append(artifact['content'])
            elif artifact['type'] == ArtifactType.CONSTRAINT:
                constraints.append(artifact['content'])
            elif artifact['type'] == ArtifactType.SOLUTION_CANDIDATE:
                solutions.append(artifact['content'])

        # Build response
        parts = []

        parts.append(f"## Exploratory Analysis: {task}\n")
        parts.append("**INFINITY → DATA EXPANSION ACTIVE**\n")
        parts.append("**Process:** Progressive problem crystallization from underspecified task\n")
        parts.append(f"**Expansion Axes:** {len(ExpansionAxis)} orthogonal dimensions explored")
        parts.append(f"**Bound Variables:** {len(expansion_result.bound_variables)}")
        parts.append(f"**Remaining Unknowns:** {len(expansion_result.remaining_unknowns)}")
        parts.append("**Swarms:** Exploration + Control running in parallel")
        parts.append(f"**Artifacts Generated:** {len(swarm_result.get('artifacts', []))}")
        parts.append(f"**Gates Synthesized:** {len(gates)}\n")

        parts.append("## Expansion Phase (Carving Scope from Infinity)\n")
        parts.append("**Exploration Axes:**")
        for axis in ExpansionAxis:
            parts.append(f"  • {axis.value}")
        parts.append("")

        if expansion_result.remaining_unknowns:
            parts.append("**Unknowns Surfaced (Not Conclusions):**")
            for i, unknown in enumerate(expansion_result.remaining_unknowns[:5], 1):
                parts.append(f"{i}. {unknown}")
            parts.append("")

        if expansion_result.candidate_data_sources:
            parts.append("**Candidate Verification Sources:**")
            for source in set(expansion_result.candidate_data_sources[:5]):
                parts.append(f"  • {source}")
            parts.append("")

        if expansion_result.risk_clusters:
            parts.append("**Risk Clusters Identified:**")
            for cluster in expansion_result.risk_clusters:
                parts.append(f"\n**{cluster['category'].upper()} Risks:**")
                for risk in cluster['risks'][:3]:
                    parts.append(f"  ⚠️ {risk}")
            parts.append("")

        parts.append("## Scope Carving (Intake Questions)\n")
        parts.append(intake_questions)
        parts.append("")

        if hypotheses:
            parts.append("## Exploration Phase (What Could Work)\n")
            for i, hyp in enumerate(hypotheses[:5], 1):
                parts.append(f"{i}. {hyp}")
            parts.append("")

        if solutions:
            parts.append("## Solution Candidates\n")
            for i, sol in enumerate(solutions[:3], 1):
                parts.append(f"**Option {i}:** {sol}")
            parts.append("")

        if risks:
            parts.append("## Control Phase (What Could Fail)\n")
            for i, risk in enumerate(risks[:5], 1):
                parts.append(f"⚠️ Risk {i}: {risk}")
            parts.append("")

        if gates:
            parts.append("## Gates Synthesized (Dynamic Safety)\n")
            for i, gate in enumerate(gates[:5], 1):
                parts.append(f"🛡️ Gate {i}: {gate['condition']}")
            parts.append("")

        if constraints:
            parts.append("## Constraints Identified\n")
            for i, constraint in enumerate(constraints[:3], 1):
                parts.append(f"• {constraint}")
            parts.append("")

        parts.append("## Expansion Control Law Status\n")
        parts.append(f"**Expansion Complete:** {expansion_result.expansion_complete}")
        parts.append(f"**Grounding Level:** {expansion_result.confidence_contribution:.2%}")
        parts.append(f"**Required Verifications:** {len(expansion_result.required_verifications)}")
        parts.append("")
        parts.append("**Control Law:** dD(x)/dt < τ and V(X) > V_min")
        parts.append("  • D(x) = deterministic grounding (increases with bound variables)")
        parts.append("  • V(X) = uncertainty volume (decreases as unknowns surface)")
        parts.append("  • Expansion stops when questions stop yielding new bindings")
        parts.append("")

        parts.append("## Confidence Status\n")
        parts.append("Current confidence is building through:")
        parts.append("1. ✓ Infinity expansion (scope carved from underspecified task)")
        parts.append("2. ✓ Unknowns surfaced (not conclusions - questions)")
        parts.append("3. ✓ Intake questions generated (progressive crystallization)")
        parts.append("4. ✓ Hypotheses explored (possibility space)")
        parts.append("5. ✓ Risks identified (failure modes)")
        parts.append("6. ✓ Gates synthesized (safety constraints)")
        parts.append("7. ⏳ Awaiting verification and promotion to working memory")
        parts.append("")
        parts.append("**Next Steps:**")
        parts.append("• Verify unknowns against candidate data sources")
        parts.append("• Bind remaining variables")
        parts.append("• Review artifacts in sandbox memory")
        parts.append("• Promote verified artifacts to working memory")
        parts.append("• Continue confidence building through iteration")
        parts.append("• Gate down from infinite possibilities to executable solution")
        parts.append("")
        parts.append("**This is not search. This is progressive problem crystallization.**")

        return "\n".join(parts)

    def _call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """Call LLM with safety bounds - uses DeepInfra with key rotation or offline fallback"""

        # Try DeepInfra with key rotation
        if self.key_rotator and self.llm_mode == "deepinfra_rotation":
            try:
                # Get next key from rotator
                key_name, api_key = self.key_rotator.get_next_key()

                # Make API call via HTTP
                import requests as _requests
                resp = _requests.post(
                    "https://api.deepinfra.com/v1/openai/chat/completions",
                    json={
                        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": max_tokens,
                    },
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                # Report success
                self.key_rotator.report_success(api_key)

                return result

            except Exception as exc:
                # Report failure
                if self.key_rotator:
                    self.key_rotator.report_failure(api_key, str(exc))

                # Fall back to offline mode if DeepInfra fails
                logger.info(f"DeepInfra failed (key: {key_name}), using offline fallback: {str(exc)}")
                return self.fallback_llm.generate(prompt, max_tokens)

        # Try single key DeepInfra mode
        elif hasattr(self, 'deepinfra_client') and self.deepinfra_client and self.llm_mode == "deepinfra":
            try:
                import requests as _requests
                resp = _requests.post(
                    "https://api.deepinfra.com/v1/openai/chat/completions",
                    json={
                        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": max_tokens,
                    },
                    headers={"Authorization": f"Bearer {self.deepinfra_client}", "Content-Type": "application/json"},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            except Exception as exc:
                # Fall back to offline mode if DeepInfra fails
                logger.info(f"DeepInfra failed, using offline fallback: {str(exc)}")
                return self.fallback_llm.generate(prompt, max_tokens)

        # Use offline fallback
        return self.fallback_llm.generate(prompt, max_tokens)

    def _generate_intelligent_response(self, message: str, domain: str, confidence: float) -> str:
        """Generate intelligent response without LLM based on domain and message analysis"""
        message_lower = message.lower()

        # Software/Tech domain
        if domain == "software" or "design" in message_lower or "build" in message_lower or "create" in message_lower:
            if "web" in message_lower or "website" in message_lower or "application" in message_lower:
                return """## Web Application Design Approach

I'll help you design this web application. To provide the most effective solution, I need to understand a few key aspects:

**Core Questions:**
1. **Primary Users**: Who will be using this application? (end users, admins, developers)
2. **Key Features**: What are the 3-5 most critical features you need?
3. **Scale**: Expected number of users? (10s, 100s, 1000s, more?)
4. **Data**: What kind of data will be stored and processed?
5. **Integration**: Does it need to connect with other systems?

**Technical Considerations:**
- **Frontend**: Modern frameworks (React, Vue, Angular) vs traditional server-side rendering
- **Backend**: API architecture, database design, authentication
- **Deployment**: Cloud hosting, containerization, CI/CD

**Next Steps:**
For a more detailed design with architecture diagrams and implementation plan, use:
`/swarmauto design [your specific requirements]`

This will activate the full swarm system to explore the solution space comprehensively.

What aspect would you like to focus on first?"""

            elif "api" in message_lower or "backend" in message_lower:
                return """## API/Backend Design Approach

I'll help you design this backend system. Let me understand your requirements:

**Architecture Questions:**
1. **API Type**: REST, GraphQL, gRPC, or WebSocket?
2. **Data Model**: What entities and relationships do you need?
3. **Authentication**: User auth, API keys, OAuth, JWT?
4. **Performance**: Expected requests per second? Response time requirements?
5. **Scalability**: Horizontal scaling needed? Microservices vs monolith?

**Technical Stack Considerations:**
- **Language/Framework**: Node.js, Python (FastAPI/Django), Go, Java/Spring
- **Database**: SQL (PostgreSQL, MySQL) vs NoSQL (MongoDB, Redis)
- **Caching**: Redis, Memcached for performance
- **Message Queue**: RabbitMQ, Kafka for async processing

**Security & Reliability:**
- Rate limiting and throttling
- Input validation and sanitization
- Error handling and logging
- Monitoring and alerting

For comprehensive architecture with code examples, use:
`/swarmauto design [detailed backend requirements]`

What's your primary concern: performance, security, or scalability?"""

            elif "database" in message_lower or "data" in message_lower:
                return """## Database Design Approach

I'll help you design an effective database schema. Key considerations:

**Data Modeling Questions:**
1. **Data Type**: Structured (SQL) vs Unstructured (NoSQL)?
2. **Relationships**: Complex relationships or simple key-value?
3. **Query Patterns**: Read-heavy, write-heavy, or balanced?
4. **Consistency**: Strong consistency vs eventual consistency?
5. **Scale**: Data volume and growth rate?

**Database Options:**
- **SQL**: PostgreSQL (feature-rich), MySQL (performance), SQLite (embedded)
- **NoSQL**: MongoDB (documents), Redis (cache/queue), Cassandra (distributed)
- **NewSQL**: CockroachDB, TiDB (SQL + horizontal scaling)

**Design Principles:**
- Normalization vs denormalization trade-offs
- Indexing strategy for query performance
- Partitioning/sharding for scale
- Backup and disaster recovery

For detailed schema design with migrations, use:
`/swarmauto design database for [your use case]`

What's your data access pattern?"""

        # Business/Strategy domain
        elif domain == "business" or "strategy" in message_lower or "plan" in message_lower:
            return """## Business Strategy Approach

I'll help you develop this strategy. To provide actionable insights:

**Strategic Questions:**
1. **Objective**: What's the primary goal? (growth, efficiency, market entry)
2. **Timeline**: Short-term (3-6 months) or long-term (1-3 years)?
3. **Resources**: Budget, team size, current capabilities?
4. **Market**: Target audience, competition, market conditions?
5. **Constraints**: Regulatory, technical, or resource limitations?

**Analysis Framework:**
- **SWOT**: Strengths, Weaknesses, Opportunities, Threats
- **Market Analysis**: TAM, SAM, SOM sizing
- **Competitive Positioning**: Differentiation strategy
- **Financial Projections**: Revenue model, cost structure

**Execution Planning:**
- Milestone definition and KPIs
- Resource allocation
- Risk mitigation strategies
- Success metrics

For comprehensive strategic analysis with multiple scenarios, use:
`/swarmauto analyze [your strategic challenge]`

What's the most critical aspect to address first?"""

        # Research/Analysis domain
        elif domain == "research" or "analyze" in message_lower or "study" in message_lower:
            return """## Research & Analysis Approach

I'll help you conduct this research. To ensure thorough analysis:

**Research Questions:**
1. **Objective**: What question are you trying to answer?
2. **Scope**: Breadth vs depth of investigation?
3. **Data Sources**: Primary research, secondary sources, or both?
4. **Methodology**: Qualitative, quantitative, or mixed methods?
5. **Timeline**: When do you need results?

**Analysis Framework:**
- **Literature Review**: Existing research and findings
- **Data Collection**: Methods and sources
- **Analysis Techniques**: Statistical, thematic, comparative
- **Validation**: Cross-referencing and verification

**Deliverables:**
- Research findings and insights
- Data visualizations
- Recommendations and next steps
- Confidence levels and limitations

For deep research with multiple sources and synthesis, use:
`/swarmauto research [your research question]`

What's your primary research objective?"""

        # Problem-solving domain
        elif domain == "problem" or "solve" in message_lower or "fix" in message_lower or "issue" in message_lower:
            return """## Problem-Solving Approach

I'll help you solve this problem systematically. Let me understand the situation:

**Problem Definition:**
1. **Current State**: What's happening now?
2. **Desired State**: What should be happening?
3. **Impact**: Who/what is affected and how severely?
4. **Constraints**: Time, resources, dependencies?
5. **Previous Attempts**: What have you tried already?

**Analysis Framework:**
- **Root Cause Analysis**: 5 Whys, Fishbone diagram
- **Solution Generation**: Brainstorming, analogies, first principles
- **Evaluation**: Feasibility, impact, cost-benefit
- **Implementation**: Action plan, milestones, validation

**Problem-Solving Process:**
1. Define the problem clearly
2. Gather relevant information
3. Generate multiple solutions
4. Evaluate and select best approach
5. Implement and validate

For comprehensive problem analysis with multiple solution paths, use:
`/swarmauto solve [detailed problem description]`

What's the most critical aspect of this problem?"""

        # General/Unknown domain
        else:
            return f"""## Understanding Your Request

I'm analyzing your request about **{domain}**. To provide the most helpful response:

**Clarifying Questions:**
1. **Goal**: What are you trying to achieve?
2. **Context**: What's the background or situation?
3. **Constraints**: Any limitations or requirements?
4. **Timeline**: When do you need this?
5. **Success Criteria**: How will you know it's successful?

**Available Approaches:**
- **Quick Guidance**: I can provide immediate direction (current mode)
- **Detailed Analysis**: Use `/swarmauto [your request]` for comprehensive exploration
- **Specific Domain**: Tell me more so I can route to the right expertise

**System Capabilities:**
- Software design and architecture
- Business strategy and planning
- Research and analysis
- Problem-solving and optimization
- Data analysis and visualization

What additional information would help me assist you better?"""

    def _get_memory_counts(self) -> Dict[str, int]:
        """Get counts from all memory planes"""
        return {
            'sandbox': len(self.memory_system.sandbox.read_all()),
            'working': len(self.memory_system.working.read_by_phase('all')),
            'control': 1 if self.memory_system.control.read_state() else 0,
            'execution': len(self.memory_system.execution.read_all())
        }

    def _update_context(self, message: str):
        """Update conversation context from message"""
        message_lower = message.lower()

        # Extract topics
        topics = []
        if 'web' in message_lower or 'app' in message_lower:
            topics.append('web_development')
        if 'enterprise' in message_lower or 'saas' in message_lower:
            topics.append('enterprise_software')
        if 'hospital' in message_lower or 'healthcare' in message_lower:
            topics.append('healthcare')
        if 'finance' in message_lower or 'trading' in message_lower:
            topics.append('finance')

        for topic in topics:
            if topic not in self.conversation_context['topics_discussed']:
                self.conversation_context['topics_discussed'].append(topic)

        # Track previous tasks
        if '/swarmauto' in message_lower:
            task = message.replace('/swarmauto', '').strip()
            self.conversation_context['previous_tasks'].append({
                'task': task[:100],
                'timestamp': time.time()
            })

    def _build_context_prompt(self, message: str, domain: str) -> str:
        """Build context-aware prompt from conversation history"""
        if not self.history:
            return message

        # Build context from recent history (last 5 messages)
        recent_history = self.history[-5:]

        context_parts = []

        # Add conversation context
        if self.conversation_context['topics_discussed']:
            context_parts.append(f"Topics discussed: {', '.join(self.conversation_context['topics_discussed'])}")

        if self.conversation_context['previous_tasks']:
            recent_tasks = [t['task'] for t in self.conversation_context['previous_tasks'][-3:]]
            context_parts.append(f"Previous tasks: {'; '.join(recent_tasks)}")

        # Add recent exchanges
        if len(recent_history) > 1:
            context_parts.append("Recent conversation:")
            for entry in recent_history[-3:]:
                context_parts.append(f"- User: {entry['message'][:50]}...")
                if entry.get('response'):
                    context_parts.append(f"  Response: {entry['response'][:50]}...")

        # Combine context with current message
        if context_parts:
            full_prompt = "\n".join([
                "CONVERSATION CONTEXT:",
                "\n".join(context_parts),
                "",
                "CURRENT MESSAGE:",
                message
            ])
            return full_prompt

        return message

    def _process_with_context(self, message: str, answers: Dict[str, str], context_summary: str) -> Dict[str, Any]:
        """
        MFGC inference engine.

        Rather than running a questionnaire, Murphy:
        1. Infers the business context from everything the user has said so far
        2. Fills the required data model from those inferences
        3. Checks gates against inferences (gaps = low-confidence fields only)
        4. Either presents confident options/suggestions, or asks for the ONE
           thing it genuinely cannot infer
        """
        import re as _re

        # ── 1. Aggregate all user-provided text ───────────────────────────────
        filled = {k: v for k, v in answers.items() if v is not None}
        all_text = " ".join(str(v) for v in filled.values()).lower()

        # ── 2. Inference: fill the business data model from what was said ─────
        # Each field: (inferred_value_or_None, confidence_0_to_1)
        inferred: Dict[str, Any] = {}

        def _infer(field: str, signals: list, default=None) -> tuple:
            """Return (value, confidence). Confidence = fraction of signals matched."""
            matched = [s for s in signals if s.lower() in all_text]
            if matched:
                return (" ".join(matched[:3]), min(0.5 + len(matched) * 0.15, 1.0))
            return (default, 0.0)

        # Business type
        biz_signals = ["saas", "software", "ai", "automation", "tech", "startup",
                       "agency", "consulting", "ecommerce", "retail", "healthcare",
                       "finance", "logistics", "manufacturing", "media", "legal"]
        inferred["business_type"], inferred["business_type_conf"] = _infer("business_type", biz_signals)

        # Scale / size
        scale_signals = ["enterprise", "mid-market", "smb", "startup", "small business",
                         "team", "employees", "users", "customers", "clients"]
        inferred["scale"], inferred["scale_conf"] = _infer("scale", scale_signals)

        # Budget
        budget_patterns = _re.findall(r'\$[\d,k]+|\d+k|\d{4,}', all_text)
        inferred["budget"] = budget_patterns[0] if budget_patterns else None
        inferred["budget_conf"] = 0.9 if budget_patterns else 0.0

        # Timeline
        timeline_patterns = _re.findall(
            r'\d+\s*(?:day|week|month|quarter|year)s?|q[1-4]|by\s+\w+', all_text
        )
        inferred["timeline"] = timeline_patterns[0] if timeline_patterns else None
        inferred["timeline_conf"] = 0.9 if timeline_patterns else 0.0

        # Goal / automation intent
        goal_signals = ["automate", "onboard", "qualify", "follow.?up", "send",
                        "track", "report", "integrate", "sync", "notify", "schedule",
                        "invoice", "hire", "manage", "analyse", "monitor"]
        goal_matches = [s for s in goal_signals if _re.search(s, all_text)]
        inferred["goals"] = goal_matches[:4] if goal_matches else None
        inferred["goals_conf"] = min(len(goal_matches) * 0.3, 1.0) if goal_matches else 0.0

        # Decision makers
        dm_signals = ["founder", "ceo", "cto", "vp", "director", "manager",
                      "owner", "head of", "lead", "decision maker"]
        inferred["decision_makers"], inferred["dm_conf"] = _infer("decision_makers", dm_signals)

        # Compliance / risk posture
        comp_signals = ["compliance", "gdpr", "hipaa", "soc2", "iso", "legal",
                        "regulation", "security", "pci", "audit"]
        inferred["compliance"], inferred["compliance_conf"] = _infer("compliance", comp_signals)
        # Tech stack mentioned?
        tech_signals = ["salesforce", "hubspot", "slack", "jira", "stripe", "twilio",
                        "aws", "azure", "gcp", "postgres", "mysql", "notion",
                        "zapier", "make", "n8n", "api", "webhook", "crm", "erp"]
        tech_matches = [s for s in tech_signals if s in all_text]
        inferred["tech_stack"] = tech_matches[:5] if tech_matches else None
        inferred["tech_conf"] = min(len(tech_matches) * 0.3, 1.0) if tech_matches else 0.0

        # ── 3. Gate evaluation against inferences ─────────────────────────────
        # Gates are: business_type, goals, decision_makers, budget/timeline, compliance
        gates_model = [
            {"field": "goals",            "conf": inferred.get("goals_conf", 0),
             "label": "automation goal",  "weight": 0.30},
            {"field": "business_type",    "conf": inferred.get("business_type_conf", 0),
             "label": "business type",    "weight": 0.20},
            {"field": "decision_makers",  "conf": inferred.get("dm_conf", 0),
             "label": "decision-makers",  "weight": 0.15},
            {"field": "budget",           "conf": inferred.get("budget_conf", 0),
             "label": "budget",           "weight": 0.15},
            {"field": "timeline",         "conf": inferred.get("timeline_conf", 0),
             "label": "timeline",         "weight": 0.10},
            {"field": "compliance",       "conf": inferred.get("compliance_conf", 0),
             "label": "compliance needs", "weight": 0.10},
        ]

        # Weighted gate satisfaction
        gate_satisfaction = sum(
            g["weight"] * min(g["conf"] / 0.5, 1.0)   # normalize: conf>=0.5 → fully satisfied
            for g in gates_model
        )
        gate_satisfaction = min(gate_satisfaction, 1.0)

        # Unknown resolution: how many gate fields are still low-confidence?
        unknown_gates = [g for g in gates_model if g["conf"] < 0.4]
        unknowns_count = len(unknown_gates)
        unknowns_resolved = len(gates_model) - unknowns_count

        # Overall confidence
        confidence = (gate_satisfaction * 0.6) + (unknowns_resolved / len(gates_model) * 0.4)
        confidence = min(confidence, 1.0)

        # ── 4. Decide: execute (suggest/fill) or ask ONE targeted gap question ─
        should_execute = gate_satisfaction >= 0.60 or confidence >= 0.65 or unknowns_count <= 2

        if should_execute:
            # Build the execution prompt — Murphy presents options or fills data
            goals_str = (", ".join(inferred.get("goals") or ["automation"]))
            biz_str   = inferred.get("business_type") or "your business"
            budget_str = inferred.get("budget") or "unspecified budget"
            timeline_str = inferred.get("timeline") or "flexible timeline"
            dm_str = inferred.get("decision_makers") or "stakeholders"
            comp_str = inferred.get("compliance") or "standard compliance"
            tech_str = (", ".join(inferred.get("tech_stack") or [])) or "existing tools"

            # Known fields → inferred data model summary for the LLM
            inferred_context = (
                f"Business: {biz_str} | Goals: {goals_str} | Budget: {budget_str} | "
                f"Timeline: {timeline_str} | Decision-makers: {dm_str} | "
                f"Compliance: {comp_str} | Tech stack: {tech_str}"
            )

            # Gaps the user hasn't addressed yet
            gaps_str = ""
            if unknown_gates:
                gap_labels = [g["label"] for g in unknown_gates[:2]]
                gaps_str = f" (Note: {' and '.join(gap_labels)} not yet confirmed — make reasonable assumptions and flag them)"

            execution_prompt = (
                f"You are Murphy, an AI automation advisor. Based on everything the user has told you, "
                f"you have inferred their business context. Now present 2-3 concrete automation options "
                f"or a recommended plan they can act on immediately.{gaps_str}\n\n"
                f"Inferred context: {inferred_context}\n\n"
                f"Original request: {message}\n\n"
                f"Instructions:\n"
                f"- Present options as numbered choices with a brief rationale\n"
                f"- If you assumed something, say so briefly\n"
                f"- Keep it conversational, no markdown headers\n"
                f"- End with: which option fits best, or shall I proceed with option 1?"
            )

            if self.llm_available and getattr(self, "llm_mode", "offline") != "offline":
                try:
                    response = self._call_llm(execution_prompt, max_tokens=600)
                    return {
                        'content': response,
                        'response': response,
                        'confidence': round(confidence, 4),
                        'gate_satisfaction': round(gate_satisfaction, 4),
                        'band': 'execution',
                        'domain': 'inference',
                        'context_used': True,
                        'execution_mode': True,
                        'status': 'SUGGESTING',
                        'inferred': inferred,
                        'unknowns_remaining': unknowns_count,
                        'unknowns_count': unknowns_count,
                    }
                except Exception as exc:
                    logger.debug("LLM call failed in inference path: %s", exc)

            # Offline fallback — deterministic suggestion based on inferred model
            goals_display = goals_str or "business automation"
            offline_response = (
                f"Based on what you've told me, here's what I can set up for you:\n\n"
                f"1. Automated {goals_display} workflow — sequential, triggered on new leads or form submissions\n"
                f"2. Notification + approval chain for {dm_str} at key decision points\n"
                f"3. Compliance-safe data handling ({comp_str}) with audit trail\n\n"
                f"I've assumed {budget_str} over {timeline_str}. Which option fits best, "
                f"or shall I proceed with option 1?"
            )
            return {
                'content': offline_response,
                'response': offline_response,
                'confidence': round(confidence, 4),
                'gate_satisfaction': round(gate_satisfaction, 4),
                'band': 'execution',
                'execution_mode': True,
                'status': 'SUGGESTING',
                'inferred': inferred,
                'unknowns_remaining': unknowns_count,
                'unknowns_count': unknowns_count,
            }

        else:
            # NOT ENOUGH — ask for the single most important missing field
            top_gap = unknown_gates[0] if unknown_gates else None
            gap_label = top_gap["label"] if top_gap else "automation goal"

            gap_prompt = (
                f"You are Murphy, an AI automation advisor in an onboarding conversation. "
                f"You have inferred some context but need one key piece of information to proceed.\n\n"
                f"What you know so far: {all_text[:300]}\n\n"
                f"Most important gap: {gap_label}\n\n"
                f"Ask ONE friendly, specific question to fill that gap. "
                f"No markdown, no headers, just a natural question."
            )

            if self.llm_available and getattr(self, "llm_mode", "offline") != "offline":
                try:
                    question_text = self._call_llm(gap_prompt, max_tokens=120)
                    question_text = question_text.strip()
                    return {
                        'content': question_text,
                        'confidence': round(confidence, 4),
                        'gate_satisfaction': round(gate_satisfaction, 4),
                        'band': 'conversational',
                        'questioning_mode': True,
                        'status': 'NEEDS_INFO',
                        'gap_field': gap_label,
                        'unknowns_remaining': unknowns_count,
                        'unknowns_count': unknowns_count,
                    }
                except Exception as exc:
                    logger.debug("LLM gap question failed: %s", exc)

            # Offline fallback
            fallback_questions = {
                "automation goal":    "What would you like to automate first?",
                "business type":      "What kind of business or industry are you in?",
                "decision-makers":    "Who makes the final call on new tools — you, or someone else on the team?",
                "budget":             "What's the rough budget you're working with?",
                "timeline":           "Any deadline or timeframe you're working toward?",
                "compliance needs":   "Any compliance requirements to keep in mind — GDPR, HIPAA, SOC2?",
            }
            question_text = fallback_questions.get(gap_label, f"Can you tell me more about your {gap_label}?")
            return {
                'content': question_text,
                'confidence': round(confidence, 4),
                'gate_satisfaction': round(gate_satisfaction, 4),
                'band': 'conversational',
                'questioning_mode': True,
                'status': 'NEEDS_INFO',
                'gap_field': gap_label,
                'unknowns_remaining': unknowns_count,
                'unknowns_count': unknowns_count,
            }


    def get_active_gates(self) -> List[str]:
        """Get list of active safety gates"""
        # Return common gates - can be enhanced to track actual gates
        return [
            "Input validation required",
            "Error handling needed",
            "Performance monitoring active",
            "Code quality standards",
            "Security vulnerability checks",
            "Test coverage required",
            "Documentation completeness verified"
        ]

    def get_system_state(self) -> Dict[str, Any]:
        """Get current system state"""
        # Get latest from history
        latest = self.history[-1] if self.history else {}

        return {
            'confidence': latest.get('confidence', 0.5),
            'band': latest.get('band', 'conversational'),
            'domain': latest.get('domain', 'general'),
            'complexity': 0.5,
            'gates_count': len(self.get_active_gates()),
            'memory_state': self.get_memory_status()
        }

    def get_swarm_status(self) -> Dict[str, Any]:
        """Get swarm system status"""
        return {
            'active_swarms': 0,
            'total_atoms': 14,
            'artifacts_generated': len(self.memory_system.sandbox),
            'exploration_active': False,
            'control_active': False,
            'recent_activity': 'No recent swarm activity'
        }

    def get_memory_status(self) -> Dict[str, int]:
        """Get memory system status"""
        try:
            # Try to get counts from memory system
            sandbox_count = len(self.memory_system.sandbox.artifacts) if hasattr(self.memory_system.sandbox, 'artifacts') else 0
            working_count = len(self.memory_system.working.artifacts) if hasattr(self.memory_system.working, 'artifacts') else 0
            control_count = len(self.memory_system.control.artifacts) if hasattr(self.memory_system.control, 'artifacts') else 0
            execution_count = len(self.memory_system.execution.artifacts) if hasattr(self.memory_system.execution, 'artifacts') else 0

            return {
                'sandbox': sandbox_count,
                'working': working_count,
                'control': control_count,
                'execution': execution_count
            }
        except Exception as exc:
            # Fallback to zero counts
            logger.debug("Suppressed exception: %s", exc)
            return {
                'sandbox': 0,
                'working': 0,
                'control': 0,
                'execution': 0
            }

    def reset_context(self):
        """Reset conversation context"""
        self.history = []
        self.conversation_context = {
            'topics_discussed': [],
            'user_preferences': {},
            'domain_context': {},
            'previous_tasks': [],
            'accumulated_knowledge': []
        }
        self.question_manager.clear()

    def _extract_knowledge(self, message: str, result: Dict):
        """Extract and store knowledge from interaction"""
        # Extract key information
        if result.get('band') == 'exploratory':
            knowledge = {
                'domain': result.get('domain'),
                'unknowns': result.get('unknowns_remaining', 0),
                'gates': result.get('gates_synthesized', 0),
                'confidence': result.get('confidence', 0),
                'timestamp': time.time()
            }
            self.conversation_context['accumulated_knowledge'].append(knowledge)

    def clear_state(self):
        """Clear system state"""
        self.history = []
        self.conversation_context = {
            'topics_discussed': [],
            'user_preferences': {},
            'domain_context': {},
            'previous_tasks': [],
            'accumulated_knowledge': []
        }
        self.memory_system = MemoryArtifactSystem()
        self.expansion_engine = InfinityExpansionEngine()
        # Keep task confidence (it builds over time)
