"""
Self-Aware Knowledge Gap System
The chatbot detects what it doesn't know and actively seeks information
through clarifying questions, research, and hypothesis testing
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("knowledge_gap_system")


class KnowledgeGapDetector:
    """
    Detects when the chatbot lacks sufficient information to answer
    and determines what additional information is needed
    """

    def __init__(self):
        self.confidence_threshold = 0.7  # Below this, we need more info
        self.ambiguity_indicators = [
            'unclear', 'ambiguous', 'vague', 'unspecified', 'depends on',
            'could mean', 'might refer to', 'not enough context'
        ]

    def analyze_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze if we have enough information to answer the query

        Returns:
            {
                'has_sufficient_info': bool,
                'missing_information': List[str],
                'clarifying_questions': List[str],
                'ambiguities': List[str],
                'confidence': float
            }
        """
        result = {
            'has_sufficient_info': True,
            'missing_information': [],
            'clarifying_questions': [],
            'ambiguities': [],
            'confidence': 1.0
        }

        # Check for pronouns without clear referents
        ambiguous_pronouns = self._detect_ambiguous_pronouns(query)
        if ambiguous_pronouns:
            result['has_sufficient_info'] = False
            result['ambiguities'].extend(ambiguous_pronouns)
            result['clarifying_questions'].append(
                f"What does '{ambiguous_pronouns[0]}' refer to?"
            )

        # Check for underspecified parameters
        underspecified = self._detect_underspecified_params(query)
        if underspecified:
            result['has_sufficient_info'] = False
            result['missing_information'].extend(underspecified)
            for param in underspecified:
                result['clarifying_questions'].append(
                    f"What is the value/specification for: {param}?"
                )

        # Check for domain-specific knowledge gaps
        knowledge_gaps = self._detect_knowledge_gaps(query, context)
        if knowledge_gaps:
            result['missing_information'].extend(knowledge_gaps)
            result['clarifying_questions'].append(
                f"I need more information about: {', '.join(knowledge_gaps)}"
            )

        # Calculate confidence
        gap_count = len(result['missing_information']) + len(result['ambiguities'])
        result['confidence'] = max(0.0, 1.0 - (gap_count * 0.2))

        if result['confidence'] < self.confidence_threshold:
            result['has_sufficient_info'] = False

        return result

    def _detect_ambiguous_pronouns(self, query: str) -> List[str]:
        """Detect pronouns without clear referents"""
        ambiguous = []

        # Check for pronouns at start of query (no prior context)
        pronouns = ['it', 'this', 'that', 'they', 'them', 'these', 'those']
        words = query.lower().split()

        if words and words[0] in pronouns:
            ambiguous.append(words[0])

        return ambiguous

    def _detect_underspecified_params(self, query: str) -> List[str]:
        """Detect missing parameters or specifications"""
        underspecified = []

        # Check for incomplete comparisons
        if re.search(r'\b(better|worse|faster|slower|more|less)\b', query.lower()):
            if not re.search(r'\bthan\b', query.lower()):
                underspecified.append("comparison baseline (better/worse than what?)")

        # Check for unspecified quantities
        if re.search(r'\b(some|many|few|several)\b', query.lower()):
            underspecified.append("specific quantity")

        # Check for unspecified time frames
        if re.search(r'\b(recently|soon|later|eventually)\b', query.lower()):
            underspecified.append("specific time frame")

        return underspecified

    def _detect_knowledge_gaps(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Detect domain knowledge we might be missing"""
        gaps = []

        # Check for technical terms we might not know
        # This is a simplified check - in practice, would check against knowledge base
        technical_indicators = ['algorithm', 'protocol', 'framework', 'methodology']
        for indicator in technical_indicators:
            if indicator in query.lower():
                # Check if we have context about this
                if not context.get(f'{indicator}_knowledge'):
                    gaps.append(f"specific details about the {indicator} mentioned")

        return gaps


class HypothesisGenerator:
    """
    Generates hypotheses about what the user might mean
    and tests them through research or clarification
    """

    def __init__(self):
        self.research_engine = None  # Will be injected

    def generate_hypotheses(self, query: str, gaps: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate possible interpretations/hypotheses for ambiguous queries

        Returns:
            List of hypotheses with confidence scores
        """
        hypotheses = []

        # Generate hypotheses based on ambiguities
        if gaps.get('ambiguities'):
            for ambiguity in gaps['ambiguities']:
                hypotheses.extend(self._generate_referent_hypotheses(query, ambiguity))

        # Generate hypotheses for missing parameters
        if gaps.get('missing_information'):
            for missing in gaps['missing_information']:
                hypotheses.extend(self._generate_parameter_hypotheses(query, missing))

        return hypotheses

    def _generate_referent_hypotheses(self, query: str, pronoun: str) -> List[Dict[str, Any]]:
        """Generate hypotheses about what a pronoun refers to"""
        hypotheses = []

        # Extract potential referents from query
        words = query.split()
        nouns = self._extract_nouns(query)

        for noun in nouns:
            hypotheses.append({
                'type': 'referent',
                'hypothesis': f"'{pronoun}' refers to '{noun}'",
                'confidence': 0.5,
                'needs_verification': True
            })

        return hypotheses

    def _generate_parameter_hypotheses(self, query: str, parameter: str) -> List[Dict[str, Any]]:
        """Generate hypotheses about missing parameters"""
        hypotheses = []

        if 'comparison baseline' in parameter:
            hypotheses.append({
                'type': 'parameter',
                'hypothesis': 'Comparing to industry standard',
                'confidence': 0.4,
                'needs_verification': True
            })
            hypotheses.append({
                'type': 'parameter',
                'hypothesis': 'Comparing to previous version',
                'confidence': 0.4,
                'needs_verification': True
            })

        return hypotheses

    def _extract_nouns(self, text: str) -> List[str]:
        """Simple noun extraction (simplified)"""
        # In practice, would use NLP library
        # For now, just extract capitalized words and common nouns
        words = text.split()
        nouns = [w for w in words if w[0].isupper() or w in ['system', 'method', 'approach', 'model']]
        return nouns

    def test_hypothesis(self, hypothesis: Dict[str, Any], research_engine) -> Dict[str, Any]:
        """
        Test a hypothesis through research or logical verification

        Returns:
            {
                'hypothesis': original hypothesis,
                'verified': bool,
                'confidence': float,
                'evidence': str
            }
        """
        result = {
            'hypothesis': hypothesis['hypothesis'],
            'verified': False,
            'confidence': hypothesis['confidence'],
            'evidence': ''
        }

        # If hypothesis needs external verification, do research
        if hypothesis.get('needs_verification') and research_engine:
            # Extract key terms from hypothesis
            key_terms = self._extract_key_terms(hypothesis['hypothesis'])

            # Research the hypothesis
            research_result = research_engine.research_topic(' '.join(key_terms))

            if research_result and research_result.confidence > 0.6:
                result['verified'] = True
                result['confidence'] = research_result.confidence
                result['evidence'] = f"Research supports this interpretation (confidence: {research_result.confidence:.1%})"
            else:
                result['evidence'] = "Insufficient evidence to verify this hypothesis"

        return result

    def _extract_key_terms(self, hypothesis: str) -> List[str]:
        """Extract key terms from hypothesis for research"""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'to', 'of', 'in', 'for', 'is', 'refers'}
        words = hypothesis.lower().split()
        key_terms = [w for w in words if w not in stop_words and len(w) > 3]
        return key_terms


class IterativeReasoningEngine:
    """
    Performs iterative reasoning: ask questions, research, test hypotheses,
    and continue until solved or determined unsolvable
    """

    def __init__(self, research_engine=None):
        self.gap_detector = KnowledgeGapDetector()
        self.hypothesis_generator = HypothesisGenerator()
        self.hypothesis_generator.research_engine = research_engine
        self.research_engine = research_engine
        self.max_iterations = 5

    def reason_iteratively(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Iteratively reason about a query:
        1. Detect knowledge gaps
        2. Generate hypotheses or ask clarifying questions
        3. Research to fill gaps
        4. Test hypotheses
        5. Repeat until solved or unsolvable

        Returns:
            {
                'solved': bool,
                'answer': str,
                'reasoning_steps': List[str],
                'clarifying_questions': List[str],
                'hypotheses_tested': List[Dict],
                'confidence': float,
                'unsolvable_reason': Optional[str]
            }
        """
        context = context or {}
        result = {
            'solved': False,
            'answer': '',
            'reasoning_steps': [],
            'clarifying_questions': [],
            'hypotheses_tested': [],
            'confidence': 0.0,
            'unsolvable_reason': None
        }

        iteration = 0
        current_query = query

        while iteration < self.max_iterations:
            iteration += 1
            result['reasoning_steps'].append(f"**Iteration {iteration}:**")

            # Step 1: Analyze current state
            gap_analysis = self.gap_detector.analyze_query(current_query, context)
            result['reasoning_steps'].append(
                f"Gap Analysis: Confidence={gap_analysis['confidence']:.1%}, "
                f"Missing={len(gap_analysis['missing_information'])}"
            )

            # Step 2: If we have sufficient info, try to answer
            if gap_analysis['has_sufficient_info']:
                result['reasoning_steps'].append("✓ Sufficient information available")
                result['solved'] = True
                result['confidence'] = gap_analysis['confidence']
                break

            # Step 3: Generate clarifying questions
            if gap_analysis['clarifying_questions']:
                result['clarifying_questions'].extend(gap_analysis['clarifying_questions'])
                result['reasoning_steps'].append(
                    f"Generated {len(gap_analysis['clarifying_questions'])} clarifying questions"
                )

            # Step 4: Generate and test hypotheses
            hypotheses = self.hypothesis_generator.generate_hypotheses(current_query, gap_analysis)
            result['reasoning_steps'].append(f"Generated {len(hypotheses)} hypotheses")

            verified_any = False
            for hyp in hypotheses:
                test_result = self.hypothesis_generator.test_hypothesis(hyp, self.research_engine)
                result['hypotheses_tested'].append(test_result)

                if test_result['verified']:
                    verified_any = True
                    result['reasoning_steps'].append(f"✓ Verified: {test_result['hypothesis']}")
                    # Update context with verified hypothesis
                    context['verified_hypotheses'] = context.get('verified_hypotheses', [])
                    context['verified_hypotheses'].append(test_result)
                else:
                    result['reasoning_steps'].append(f"✗ Could not verify: {test_result['hypothesis']}")

            # Step 5: If we verified hypotheses, update query and continue
            if verified_any:
                result['reasoning_steps'].append("Continuing with verified information...")
                continue

            # Step 6: Try research to fill gaps
            if gap_analysis['missing_information'] and self.research_engine:
                result['reasoning_steps'].append("Attempting research to fill knowledge gaps...")

                for missing in gap_analysis['missing_information'][:2]:  # Limit research attempts
                    research_result = self.research_engine.research_topic(missing)

                    if research_result and research_result.confidence > 0.6:
                        result['reasoning_steps'].append(f"✓ Found information about: {missing}")
                        context[f'research_{missing}'] = research_result
                    else:
                        result['reasoning_steps'].append(f"✗ Could not find reliable information about: {missing}")

            # Step 7: Check if we made progress
            new_gap_analysis = self.gap_detector.analyze_query(current_query, context)

            if new_gap_analysis['confidence'] <= gap_analysis['confidence']:
                # No progress made
                result['reasoning_steps'].append("⚠ No progress made in this iteration")
                break

        # Final determination
        if not result['solved']:
            if result['clarifying_questions']:
                result['unsolvable_reason'] = (
                    "Cannot solve without additional information. "
                    "Please answer the clarifying questions above."
                )
            else:
                result['unsolvable_reason'] = (
                    "Unable to find sufficient reliable information to answer this query. "
                    f"Attempted {iteration} reasoning iterations."
                )

        return result

    def format_response(self, reasoning_result: Dict[str, Any], original_query: str) -> str:
        """Format the iterative reasoning result into a readable response"""

        response = f"# Reasoning Process for: {original_query}\n\n"

        # Show reasoning steps
        response += "## Reasoning Steps:\n\n"
        for step in reasoning_result['reasoning_steps']:
            response += f"{step}\n"

        response += "\n"

        # Show clarifying questions if any
        if reasoning_result['clarifying_questions']:
            response += "## ❓ Clarifying Questions Needed:\n\n"
            for i, q in enumerate(reasoning_result['clarifying_questions'], 1):
                response += f"{i}. {q}\n"
            response += "\n"

        # Show tested hypotheses
        if reasoning_result['hypotheses_tested']:
            response += "## 🔬 Hypotheses Tested:\n\n"
            for hyp in reasoning_result['hypotheses_tested']:
                status = "✓ Verified" if hyp['verified'] else "✗ Not verified"
                response += f"- {status}: {hyp['hypothesis']}\n"
                if hyp['evidence']:
                    response += f"  Evidence: {hyp['evidence']}\n"
            response += "\n"

        # Show final result
        if reasoning_result['solved']:
            response += "## ✅ Result:\n\n"
            response += "Successfully reasoned through the query.\n"
            response += f"**Confidence:** {reasoning_result['confidence']:.1%}\n"
        else:
            response += "## ⚠️ Unable to Solve:\n\n"
            response += f"{reasoning_result['unsolvable_reason']}\n\n"

            if reasoning_result['clarifying_questions']:
                response += "**To proceed, I need:**\n"
                for q in reasoning_result['clarifying_questions']:
                    response += f"- {q}\n"

        return response


# Example usage
if __name__ == "__main__":
    engine = IterativeReasoningEngine()

    # Test with ambiguous query
    result = engine.reason_iteratively("Is it better?")
    logger.info(engine.format_response(result, "Is it better?"))
