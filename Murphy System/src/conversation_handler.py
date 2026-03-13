"""
Conversation Handler - Engages naturally with user questions
Clearly marks Generated vs Verified responses
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("conversation_handler")


class ConversationHandler:
    """Handles natural conversation with clear G/V markers"""

    def __init__(self):
        self.topics = self._load_topics()

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
        """
        Handle conversational input

        Returns:
            Dict with response, marker (G/V), and confidence
        """
        input_lower = user_input.lower()

        # Check for specific topics we have verified knowledge about
        for topic, data in self.topics.items():
            if topic in input_lower:
                return self._create_verified_response(topic, data, user_input)

        # Check for opinion/subjective questions
        if self._is_opinion_question(input_lower):
            return self._handle_opinion_question(user_input)

        # Check for capability questions
        if self._is_capability_question(input_lower):
            return self._handle_capability_question()

        # Check for greeting
        if self._is_greeting(input_lower):
            return self._handle_greeting()

        # Default: acknowledge and offer help
        return self._handle_general(user_input)

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
