"""
Conversation Handler - Engages naturally with user questions
Clearly marks Generated vs Verified responses

Stateful multi-turn support (Hero Flow Task 4): pass a
:class:`murphy_state_graph.GraphState` instance to enable context
carryover between turns (previous entities, commands, topics).
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("conversation_handler")


class ConversationHandler:
    """Handles natural conversation with clear G/V markers.

    Stateful multi-turn support
    ---------------------------
    Pass a :class:`murphy_state_graph.GraphState` instance as *state_graph*
    to enable context carryover between turns.  The handler stores:

    - ``_conv_topics``: topics discussed in this session
    - ``_conv_history``: list of ``{"role", "content", "marker"}`` dicts
    - ``_conv_entities``: entities (commands, topics) referenced so far

    When *state_graph* is ``None`` the handler falls back to stateless mode.
    """

    # Maximum stored history entries (CWE-770 guard)
    _MAX_HISTORY: int = 200

    def __init__(self, state_graph: Optional[Any] = None) -> None:
        self.topics = self._load_topics()
        self._state_graph = state_graph
        # Bootstrap in-memory state if no graph supplied
        if self._state_graph is None:
            self._local_history: List[Dict[str, Any]] = []
            self._local_entities: List[str] = []

    def _load_topics(self) -> Dict[str, Dict]:
        """Load verified knowledge on various topics"""
        return {
            'constitution': {
                'verified_facts': [
                    "The U.S. Constitution was ratified in 1788",
                    "It consists of 7 articles and 27 amendments",
                    "The first 10 amendments are called the Bill of Rights",
                    "It establishes three branches: Legislative, Executive, Judicial",
                    "It's the supreme law of the United States"
                ],
                'confidence': 1.0,
                'marker': 'V'
            },
            'capabilities': {
                'verified_capabilities': [
                    "Multi-source research with verification",
                    "Code generation (verified algorithms + templates)",
                    "Mathematical calculations with deterministic verification",
                    "Reasoning across 10+ categories",
                    "Command system (/research, /math, /reason, etc.)",
                    "Knowledge gap detection and clarification"
                ],
                'confidence': 1.0,
                'marker': 'V'
            }
        }

    def handle(self, user_input: str) -> Dict[str, Any]:
        """Handle conversational input with stateful context carryover.

        Reads previous conversation context from the state graph (or
        in-memory fallback), routes the input to the appropriate handler,
        then persists the result back to state.

        Returns
        -------
        Dict with keys: ``response``, ``marker`` (G/V), ``confidence``,
        ``topic``, and ``context`` (list of recent history entries).
        """
        input_lower = user_input.lower()

        # Resolve prior context from state graph
        prior_topics = self._get_state("_conv_topics") or []
        prior_entities = self._get_state("_conv_entities") or []

        # Check if user is referring back to a previous topic/entity
        enriched_input = self._apply_context(user_input, prior_topics, prior_entities)
        enriched_lower = enriched_input.lower()

        # Check for specific topics we have verified knowledge about
        result = None
        for topic, data in self.topics.items():
            if topic in enriched_lower:
                result = self._create_verified_response(topic, data, enriched_input)
                self._track_entity(topic)
                break

        if result is None:
            if self._is_opinion_question(enriched_lower):
                result = self._handle_opinion_question(enriched_input)
            elif self._is_capability_question(enriched_lower):
                result = self._handle_capability_question()
            elif self._is_greeting(enriched_lower):
                result = self._handle_greeting()
            else:
                result = self._handle_general(enriched_input)

        # Persist to state
        topic_hit = result.get("topic")
        if topic_hit and topic_hit not in prior_topics:
            prior_topics = prior_topics + [topic_hit]
        self._set_state("_conv_topics", prior_topics[-50:])

        history_entry = {
            "role": "user",
            "content": user_input,
            "marker": result.get("marker", "G"),
        }
        self._append_history(history_entry)
        result["context"] = self._get_recent_history(5)
        return result

    # ------------------------------------------------------------------
    # State graph integration helpers
    # ------------------------------------------------------------------

    def _get_state(self, key: str) -> Any:
        """Read *key* from state graph or in-memory fallback."""
        if self._state_graph is not None:
            try:
                return self._state_graph.get(key)
            except Exception:
                pass
        if key == "_conv_topics":
            return []
        if key == "_conv_entities":
            return self._local_entities if hasattr(self, "_local_entities") else []
        if key == "_conv_history":
            return self._local_history if hasattr(self, "_local_history") else []
        return None

    def _set_state(self, key: str, value: Any) -> None:
        """Write *key* = *value* to state graph or in-memory fallback."""
        if self._state_graph is not None:
            try:
                self._state_graph.set(key, value)
                return
            except Exception:
                pass
        if key == "_conv_topics":
            pass  # local topics are derived from history
        elif key == "_conv_entities":
            self._local_entities = value
        elif key == "_conv_history":
            self._local_history = value

    def _append_history(self, entry: Dict[str, Any]) -> None:
        """Append *entry* to conversation history (bounded)."""
        if self._state_graph is not None:
            try:
                history = self._state_graph.get("_conv_history") or []
                if len(history) >= self._MAX_HISTORY:
                    history = history[-(self._MAX_HISTORY // 2):]
                history.append(entry)
                self._state_graph.set("_conv_history", history)
                return
            except Exception:
                pass
        # Fallback to in-memory
        if not hasattr(self, "_local_history"):
            self._local_history = []
        if len(self._local_history) >= self._MAX_HISTORY:
            self._local_history = self._local_history[-(self._MAX_HISTORY // 2):]
        self._local_history.append(entry)

    def _get_recent_history(self, n: int) -> List[Dict[str, Any]]:
        """Return the last *n* history entries."""
        history = self._get_state("_conv_history") or []
        if not history and hasattr(self, "_local_history"):
            history = self._local_history
        return history[-n:] if history else []

    def _track_entity(self, entity: str) -> None:
        """Record *entity* as referenced in this conversation."""
        entities = self._get_state("_conv_entities") or []
        if not hasattr(self, "_local_entities"):
            self._local_entities = []
        if entity not in entities:
            entities = entities + [entity]
            self._set_state("_conv_entities", entities[-100:])
            if not self._state_graph:
                self._local_entities = entities[-100:]

    @staticmethod
    def _apply_context(
        user_input: str,
        prior_topics: List[str],
        prior_entities: List[str],
    ) -> str:
        """Enrich *user_input* with pronoun/reference resolution.

        When the user says "tell me more about it" or "what about that",
        append the most recent topic so downstream matchers can identify it.
        """
        reference_words = [
            "it", "that", "this", "the same", "the topic", "more about",
            "tell me more", "elaborate", "expand on",
        ]
        lower = user_input.lower()
        if any(ref in lower for ref in reference_words) and prior_topics:
            last_topic = prior_topics[-1]
            if last_topic not in lower:
                return f"{user_input} [{last_topic}]"
        return user_input

    def _is_opinion_question(self, text: str) -> bool:
        """Detect if user is asking for opinion"""
        opinion_patterns = [
            'what do you think',
            'your opinion',
            'do you like',
            'do you believe',
            'your thoughts on'
        ]
        return any(pattern in text for pattern in opinion_patterns)

    def _is_capability_question(self, text: str) -> bool:
        """Detect if user is asking about capabilities"""
        capability_patterns = [
            'what can you do',
            'what else can you',
            'your capabilities',
            'what are you able',
            'can you help'
        ]
        return any(pattern in text for pattern in capability_patterns)

    def _is_greeting(self, text: str) -> bool:
        """Detect greetings"""
        greetings = ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon']
        return any(greeting in text for greeting in greetings)

    def _create_verified_response(self, topic: str, data: Dict, original_question: str) -> Dict[str, Any]:
        """Create response from verified knowledge"""

        if topic == 'constitution':
            response = "**[V] The U.S. Constitution** - Verified Historical Facts\n\n"
            response += "I can share verified facts about the Constitution:\n\n"
            for fact in data['verified_facts']:
                response += f"• {fact}\n"
            response += "\n**Note:** As an AI system, I don't have personal opinions. "
            response += "I can provide verified facts, analyze constitutional text, or research specific amendments/articles.\n\n"
            response += "**Want to explore more?** Ask me to:\n"
            response += "- Research a specific amendment\n"
            response += "- Explain separation of powers\n"
            response += "- Compare constitutional provisions"

        return {
            'response': response,
            'marker': 'V',
            'confidence': data['confidence'],
            'topic': topic
        }

    def _handle_opinion_question(self, question: str) -> Dict[str, Any]:
        """Handle questions asking for opinions"""

        response = "**[V] System Design Note**\n\n"
        response += "I'm designed as a deterministic-gated system, which means:\n\n"
        response += "✓ I provide **verified facts** from trusted sources\n"
        response += "✓ I perform **deterministic calculations** with 100% confidence\n"
        response += "✓ I clearly mark **generated content** vs **verified content**\n\n"
        response += "I don't form personal opinions, but I can:\n"
        response += "• Research multiple perspectives on a topic\n"
        response += "• Analyze arguments and evidence\n"
        response += "• Present verified facts to inform your opinion\n\n"
        response += "**Want factual analysis instead?** Try:\n"
        response += "- `/research [topic]` - Get verified information\n"
        response += "- `/reason [question]` - Logical analysis\n"
        response += "- Ask for multiple perspectives on an issue"

        return {
            'response': response,
            'marker': 'V',
            'confidence': 1.0,
            'topic': 'system_design'
        }

    def _handle_capability_question(self) -> Dict[str, Any]:
        """Handle questions about capabilities"""

        response = "**[V] My Verified Capabilities**\n\n"
        response += "I'm a deterministic-gated AI system with these core abilities:\n\n"

        response += "**1. Research & Verification**\n"
        response += "• Multi-source research (Wikipedia, Standards DB, web)\n"
        response += "• Source trust ranking and verification\n"
        response += "• Fact compilation and synthesis\n"
        response += "• Command: `/research [topic]`\n\n"

        response += "**2. Code Generation**\n"
        response += "• [V] Verified algorithms (Fibonacci, factorial, primes, sorting)\n"
        response += "• [G] Generated templates (customizable starting points)\n"
        response += "• 10 languages: Python, JavaScript, Java, C++, C#, Go, Rust, TypeScript, Ruby, PHP\n"
        response += "• Automatic test generation\n\n"

        response += "**3. Mathematical Operations**\n"
        response += "• Deterministic calculations (100% confidence)\n"
        response += "• Symbolic math verification\n"
        response += "• Command: `/math [expression]`\n\n"

        response += "**4. Reasoning & Analysis**\n"
        response += "• 10+ reasoning categories\n"
        response += "• Knowledge gap detection\n"
        response += "• Iterative problem solving\n"
        response += "• Command: `/reason [question]`\n\n"

        response += "**5. Natural Conversation**\n"
        response += "• Context-aware responses\n"
        response += "• Clarifying questions when needed\n"
        response += "• Clear [V]erified vs [G]enerated markers\n\n"

        response += "**Legend:**\n"
        response += "• **[V]** = Verified (high confidence, deterministic)\n"
        response += "• **[G]** = Generated (requires validation, probabilistic)\n\n"

        response += "**Try asking me to:**\n"
        response += "• Generate Fibonacci code\n"
        response += "• Research quantum mechanics\n"
        response += "• Calculate complex expressions\n"
        response += "• Reason through logic puzzles"

        return {
            'response': response,
            'marker': 'V',
            'confidence': 1.0,
            'topic': 'capabilities'
        }

    def _handle_greeting(self) -> Dict[str, Any]:
        """Handle greetings"""

        response = "**[V] System Ready**\n\n"
        response += "Hello! I'm a deterministic-gated AI system.\n\n"
        response += "**Quick Start:**\n"
        response += "• Ask me to generate code (e.g., 'fibonacci function')\n"
        response += "• Request research (e.g., '/research quantum computing')\n"
        response += "• Perform calculations (e.g., '/math 2^10 + 5*3')\n"
        response += "• Ask questions (I'll provide verified facts)\n\n"
        response += "**Legend:** [V] = Verified | [G] = Generated\n\n"
        response += "What would you like to explore?"

        return {
            'response': response,
            'marker': 'V',
            'confidence': 1.0,
            'topic': 'greeting'
        }

    def _handle_general(self, user_input: str) -> Dict[str, Any]:
        """Handle general queries"""

        response = "**[G] Query Received**\n\n"
        response += f"I received: &quot;{user_input}&quot;\n\n"
        response += "To provide the most accurate response, please specify:\n\n"
        response += "**For Research:**\n"
        response += "• `/research [topic]` - Get verified information\n\n"
        response += "**For Code:**\n"
        response += "• 'Generate [language] code for [task]'\n"
        response += "• Example: 'Python function to calculate fibonacci'\n\n"
        response += "**For Math:**\n"
        response += "• `/math [expression]` - Deterministic calculation\n\n"
        response += "**For Reasoning:**\n"
        response += "• `/reason [question]` - Logical analysis\n\n"
        response += "**For Conversation:**\n"
        response += "• Ask specific questions\n"
        response += "• Request explanations\n"
        response += "• Explore topics\n\n"
        response += "What would you like to do?"

        return {
            'response': response,
            'marker': 'G',
            'confidence': 0.3,
            'topic': 'general'
        }


if __name__ == "__main__":
    # Test the handler
    handler = ConversationHandler()

    # Test various inputs
    tests = [
        "what do you think of the constitution",
        "what else can you do?",
        "hello",
        ".."
    ]

    for test in tests:
        logger.info(f"\nInput: {test}")
        result = handler.handle(test)
        logger.info(f"[{result['marker']}] {result['response'][:100]}...")
