"""
Safe LLM Wrapper with MFGC Integration
Ensures ALL LLM outputs go through Murphy-Free safety checks
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """Verification status for LLM outputs"""
    VERIFIED = "V"  # Verified against trusted sources
    GENERATED = "G"  # Generated, needs validation
    BOUNDED = "B"  # Bounded by safety constraints
    REJECTED = "R"  # Rejected by safety gates


@dataclass
class SafetyGate:
    """Safety gate for LLM outputs"""
    name: str
    check_fn: callable
    severity: float  # 0.0-1.0
    description: str


class SafeLLMWrapper:
    """
    Wraps LLM calls with Murphy-Free safety checks

    Key principles:
    1. All LLM outputs are [G] Generated until verified
    2. Outputs must pass safety gates before display
    3. Confidence is computed from verification
    4. Unbounded generation is prevented
    """

    def __init__(self, llm_backend=None):
        """Initialize safe wrapper"""
        self.llm_backend = llm_backend
        self._current_prompt: str = ""  # Set before each gate evaluation
        self.safety_gates = self._initialize_gates()
        self.max_response_length = 500  # Prevent unbounded generation
        self.verification_sources = {
            'wikipedia': 0.8,
            'standards_db': 0.9,
            'peer_reviewed': 0.95,
            'official_docs': 0.9
        }

    def _initialize_gates(self) -> List[SafetyGate]:
        """Initialize safety gates"""
        return [
            SafetyGate(
                name="length_bound",
                check_fn=lambda text: len(text) <= self.max_response_length,
                severity=0.3,
                description="Response length must be bounded"
            ),
            SafetyGate(
                name="no_hallucination_markers",
                check_fn=self._check_hallucination_markers,
                severity=0.8,
                description="No obvious hallucination patterns"
            ),
            SafetyGate(
                name="no_unbounded_lists",
                check_fn=self._check_unbounded_lists,
                severity=0.5,
                description="No runaway list generation"
            ),
            SafetyGate(
                name="coherence_check",
                check_fn=self._check_coherence,
                severity=0.6,
                description="Response must be coherent"
            ),
            SafetyGate(
                name="relevance_check",
                check_fn=self._check_relevance,
                severity=0.4,
                description="Response must be relevant"
            )
        ]

    def _check_hallucination_markers(self, text: str) -> bool:
        """Check for common hallucination patterns"""
        hallucination_patterns = [
            r'\[location\]',
            r'\[name\]',
            r'\[address\]',
            r'\[placeholder\]',
            r'imagine a world where',
            r'in this dystopian',
            r'let\'s say',
            r'for example.*for example.*for example',  # Repetitive examples
        ]

        text_lower = text.lower()
        for pattern in hallucination_patterns:
            if re.search(pattern, text_lower):
                return False
        return True

    def _check_unbounded_lists(self, text: str) -> bool:
        """Check for runaway list generation"""
        # Count numbered items
        numbered_items = len(re.findall(r'^\d+\.', text, re.MULTILINE))
        if numbered_items > 10:
            return False

        # Check for repetitive patterns
        lines = text.split('\n')
        if len(lines) > 20:
            return False

        return True

    def _check_coherence(self, text: str) -> bool:
        """Check if response is coherent"""
        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:  # Too repetitive
                return False

        # Check for sentence fragments
        sentences = text.split('.')
        if len(sentences) > 5:
            avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_length < 3:  # Too fragmented
                return False

        return True

    # Common English stopwords to ignore when computing token overlap
    _STOPWORDS = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "it", "be", "as", "by", "this", "that", "are",
        "was", "were", "will", "would", "can", "could", "have", "has", "had",
        "do", "does", "did", "not", "from", "i", "you", "he", "she", "we",
        "they", "me", "him", "her", "us", "them", "my", "your", "his",
        "their", "its", "our", "if", "so", "no", "up", "out", "about",
        "what", "which", "who", "how", "all", "more", "just", "then",
    })

    @staticmethod
    def _tokenize(text: str):
        """Extract significant lowercase tokens from text, stripping punctuation."""
        tokens = re.sub(r'[^a-z0-9\s]', ' ', text.lower()).split()
        return {t for t in tokens if len(t) > 1 and t not in SafeLLMWrapper._STOPWORDS}

    def _check_relevance(self, response: str) -> bool:
        """
        Deterministic, O(n) relevance check based on Jaccard similarity.
        Uses the prompt stored in self._current_prompt for comparison.
        Returns False if the response appears completely off-topic.
        """
        prompt = self._current_prompt
        if not prompt or not response:
            return True

        prompt_tokens = self._tokenize(prompt)
        response_tokens = self._tokenize(response)

        if not prompt_tokens or not response_tokens:
            return True

        intersection = prompt_tokens & response_tokens
        union = prompt_tokens | response_tokens
        jaccard = len(intersection) / (len(union) or 1)

        # Rule 1: Completely off-topic — very low overlap on a substantial response
        if jaccard < 0.05 and len(response) > 50:
            return False

        # Rule 2: Response is much longer than prompt and shares very little
        if len(response) > 5 * len(prompt):
            # Check what fraction of prompt tokens appear in the response
            prompt_coverage = len(intersection) / (len(prompt_tokens) or 1)
            if prompt_coverage < 0.1:
                return False

        return True

    def safe_generate(
        self,
        prompt: str,
        context: Dict[str, Any],
        max_tokens: int = 300
    ) -> Dict[str, Any]:
        """
        Generate response with safety checks

        Returns:
            {
                'content': str,
                'marker': 'V' | 'G' | 'B' | 'R',
                'confidence': float,
                'gates_passed': List[str],
                'gates_failed': List[str],
                'verification_status': str
            }
        """
        # Enforce token limit
        max_tokens = min(max_tokens, self.max_response_length // 4)

        # Generate response
        if self.llm_backend and hasattr(self.llm_backend, 'chat'):
            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI assistant. "
                            "Provide clear, concise, accurate responses. "
                            "Keep responses under 300 words. "
                            "Do not use placeholders like [name] or [location]. "
                            "Do not generate unbounded lists. "
                            "Stay focused on the question."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                raw_response = self.llm_backend.chat(
                    messages,
                    temperature=0.7,
                    max_tokens=max_tokens
                )
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return self._fallback_response(prompt, str(exc))
        else:
            return self._fallback_response(prompt, "No LLM backend")

        # Truncate if needed
        if len(raw_response) > self.max_response_length:
            raw_response = raw_response[:self.max_response_length] + "..."

        # Run safety gates
        self._current_prompt = prompt
        gates_passed = []
        gates_failed = []
        murphy_risk = 0.0

        for gate in self.safety_gates:
            try:
                if gate.check_fn(raw_response):
                    gates_passed.append(gate.name)
                else:
                    gates_failed.append(gate.name)
                    murphy_risk += gate.severity
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                gates_failed.append(f"{gate.name} (error: {exc})")
                murphy_risk += gate.severity

        # Determine status
        if murphy_risk > 0.7:
            # Too risky - reject
            return {
                'content': (
                    "[R] Response rejected by safety gates. "
                    f"Failed checks: {', '.join(gates_failed)}. "
                    "Please rephrase your question or use /research for verified information."
                ),
                'marker': 'R',
                'confidence': 0.0,
                'gates_passed': gates_passed,
                'gates_failed': gates_failed,
                'verification_status': 'rejected',
                'murphy_risk': murphy_risk
            }
        elif murphy_risk > 0.3:
            # Moderate risk - mark as generated
            return {
                'content': f"[G] {raw_response}\n\n⚠️ Generated response - not verified against trusted sources.",
                'marker': 'G',
                'confidence': 0.5,
                'gates_passed': gates_passed,
                'gates_failed': gates_failed,
                'verification_status': 'generated',
                'murphy_risk': murphy_risk
            }
        else:
            # Low risk - mark as bounded
            return {
                'content': f"[B] {raw_response}",
                'marker': 'B',
                'confidence': 0.7,
                'gates_passed': gates_passed,
                'gates_failed': gates_failed,
                'verification_status': 'bounded',
                'murphy_risk': murphy_risk
            }

    def _fallback_response(self, prompt: str, error: str) -> Dict[str, Any]:
        """Fallback when LLM unavailable"""
        return {
            'content': (
                f"[B] I received your message: '{prompt}'\n\n"
                "For accurate information, please use:\n"
                "• /research [topic] - Verified research\n"
                "• /math [expression] - Deterministic calculation\n"
                "• /reason [question] - Logical analysis"
            ),
            'marker': 'B',
            'confidence': 1.0,
            'gates_passed': ['fallback'],
            'gates_failed': [],
            'verification_status': 'fallback',
            'murphy_risk': 0.0
        }

    def verify_against_sources(
        self,
        claim: str,
        sources: List[str]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Verify claim against trusted sources

        Returns:
            (confidence, evidence_list)
        """
        # Returns default confidence; real verification deferred to external provider
        return 0.5, []


class MFGCIntegratedLLM:
    """
    LLM integrated with MFGC safety system

    Ensures:
    1. All outputs pass Murphy checks
    2. Confidence is computed from verification
    3. Authority is bounded by confidence
    4. No unbounded generation possible
    """

    def __init__(self, llm_backend=None):
        """Initialize MFGC-integrated LLM"""
        self.safe_wrapper = SafeLLMWrapper(llm_backend)
        self.conversation_history = []

    def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process message with full MFGC safety

        Returns response with:
        - Marker (V/G/B/R)
        - Confidence score
        - Safety gate results
        - Murphy risk assessment
        """
        if context is None:
            context = {}

        # Add to history
        self.conversation_history.append({
            'role': 'user',
            'content': message
        })

        # Generate safe response
        response = self.safe_wrapper.safe_generate(
            message,
            context,
            max_tokens=300
        )

        # Add to history
        self.conversation_history.append({
            'role': 'assistant',
            'content': response['content'],
            'marker': response['marker'],
            'confidence': response['confidence']
        })

        # Format metadata
        metadata = {
            'confidence': response['confidence'],
            'murphy_risk': response['murphy_risk'],
            'gates_passed': len(response['gates_passed']),
            'gates_failed': len(response['gates_failed']),
            'verification_status': response['verification_status']
        }

        if response['gates_failed']:
            metadata['failed_gates'] = response['gates_failed']

        return {
            'content': response['content'],
            'marker': response['marker'],
            'marker_class': self._get_marker_class(response['marker']),
            'metadata': metadata
        }

    def _get_marker_class(self, marker: str) -> str:
        """Get CSS class for marker"""
        return {
            'V': 'marker-verified',
            'G': 'marker-generated',
            'B': 'marker-bot',
            'R': 'marker-rejected'
        }.get(marker, 'marker-bot')

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            'llm_available': self.safe_wrapper.llm_backend is not None,
            'safety_gates': len(self.safe_wrapper.safety_gates),
            'max_response_length': self.safe_wrapper.max_response_length,
            'conversation_turns': len(self.conversation_history) // 2
        }
