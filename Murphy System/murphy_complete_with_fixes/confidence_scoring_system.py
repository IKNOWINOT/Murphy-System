"""
Murphy System - Phase 6: Confidence Scoring System
Confidence-based decision making and execution
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels"""
    VERY_HIGH = "very_high"    # > 0.95
    HIGH = "high"              # > 0.85
    MEDIUM = "medium"          # > 0.70
    LOW = "low"                # > 0.50
    VERY_LOW = "very_low"      # <= 0.50


class ExecutionPolicy(Enum):
    """Execution policies based on confidence"""
    AUTO_EXECUTE = "auto_execute"       # Very high confidence
    AUTO_CONFIRM = "auto_confirm"       # High confidence
    REQUIRE_CONFIRM = "require_confirm"  # Medium confidence
    REQUIRE_REVIEW = "require_review"    # Low confidence
    REJECT = "reject"                    # Very low confidence


@dataclass
class ConfidenceScore:
    """Confidence score with details"""
    value: float
    level: ConfidenceLevel
    factors: Dict[str, float]
    explanation: str
    timestamp: datetime


@dataclass
class ExecutionDecision:
    """Execution decision based on confidence"""
    should_execute: bool
    policy: ExecutionPolicy
    confidence: ConfidenceScore
    reason: str
    requires_human: bool


class ConfidenceScoringSystem:
    """Confidence scoring and decision system"""
    
    def __init__(self):
        """Initialize confidence scoring system"""
        self.confidence_history: List[ConfidenceScore] = []
        self.thresholds = {
            ExecutionPolicy.AUTO_EXECUTE: 0.95,
            ExecutionPolicy.AUTO_CONFIRM: 0.85,
            ExecutionPolicy.REQUIRE_CONFIRM: 0.70,
            ExecutionPolicy.REQUIRE_REVIEW: 0.50,
            ExecutionPolicy.REJECT: 0.0
        }
        
        logger.info("Confidence Scoring System initialized")
    
    def calculate_confidence(
        self,
        operation: str,
        content: str,
        llm_response: str = None,
        verification_result: Dict = None,
        context: Dict = None
    ) -> ConfidenceScore:
        """
        Calculate confidence score for an operation
        
        Args:
            operation: Operation type
            content: Operation content
            llm_response: LLM response if available
            verification_result: Verification result if available
            context: Additional context
        
        Returns:
            ConfidenceScore object
        """
        factors = {}
        
        # Factor 1: Content quality (0-0.3)
        factors['content_quality'] = self._assess_content_quality(content)
        
        # Factor 2: LLM response quality (0-0.3)
        if llm_response:
            factors['llm_quality'] = self._assess_llm_quality(llm_response)
        else:
            factors['llm_quality'] = 0.5  # Neutral if no LLM
        
        # Factor 3: Verification confidence (0-0.3)
        if verification_result:
            factors['verification'] = verification_result.get('confidence', 0.5)
        else:
            factors['verification'] = 0.5  # Neutral if no verification
        
        # Factor 4: Context relevance (0-0.1)
        if context:
            factors['context_relevance'] = self._assess_context_relevance(context)
        else:
            factors['context_relevance'] = 0.5
        
        # Calculate weighted average
        weights = {
            'content_quality': 0.3,
            'llm_quality': 0.3,
            'verification': 0.3,
            'context_relevance': 0.1
        }
        
        confidence = sum(
            factors[factor] * weight
            for factor, weight in weights.items()
        )
        
        # Determine level
        level = self._get_confidence_level(confidence)
        
        # Generate explanation
        explanation = self._generate_explanation(factors, confidence, level)
        
        score = ConfidenceScore(
            value=confidence,
            level=level,
            factors=factors,
            explanation=explanation,
            timestamp=datetime.now()
        )
        
        # Log for history
        self.confidence_history.append(score)
        
        return score
    
    def _assess_content_quality(self, content: str) -> float:
        """Assess content quality (0-1)"""
        if not content:
            return 0.0
        
        score = 0.5  # Base score
        
        # Length factor
        length = len(content)
        if length >= 100:
            score += 0.2
        elif length >= 50:
            score += 0.1
        
        # Structure factor
        if '\n' in content:
            score += 0.1
        if any(marker in content for marker in ['•', '-', '1.', '2.', '3.']):
            score += 0.1
        
        # Coherence factor (simple check)
        sentences = content.split('.')
        meaningful_sentences = [s for s in sentences if len(s.strip()) > 10]
        if len(meaningful_sentences) >= 2:
            score += 0.1
        
        return min(score, 1.0)
    
    def _assess_llm_quality(self, response: str) -> float:
        """Assess LLM response quality (0-1)"""
        if not response:
            return 0.0
        
        score = 0.5
        
        # Length
        if len(response) >= 200:
            score += 0.2
        elif len(response) >= 100:
            score += 0.1
        
        # Structure
        if '\n\n' in response:
            score += 0.1
        if any(word in response.lower() for word in ['however', 'therefore', 'additionally', 'furthermore']):
            score += 0.1
        
        # Completeness
        if any(marker in response for marker in ['.', '!', '?']):
            score += 0.1
        
        return min(score, 1.0)
    
    def _assess_context_relevance(self, context: Dict) -> float:
        """Assess context relevance (0-1)"""
        if not context:
            return 0.5
        
        score = 0.5
        
        # Richness of context
        if len(context) >= 3:
            score += 0.2
        elif len(context) >= 2:
            score += 0.1
        
        # Specific context types
        if any(key in context for key in ['recent_commands', 'goals', 'preferences']):
            score += 0.2
        
        return min(score, 1.0)
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level from score"""
        if confidence >= 0.95:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.70:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.50:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _generate_explanation(
        self,
        factors: Dict[str, float],
        confidence: float,
        level: ConfidenceLevel
    ) -> str:
        """Generate explanation for confidence score"""
        explanation_parts = []
        
        # Add level
        explanation_parts.append(f"Confidence level: {level.value.replace('_', ' ').title()}")
        
        # Add strongest factors
        sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
        
        top_factors = sorted_factors[:2]
        for factor_name, value in top_factors:
            factor_display = factor_name.replace('_', ' ').title()
            explanation_parts.append(f"{factor_display}: {value:.2f}")
        
        # Add overall
        explanation_parts.append(f"Overall confidence: {confidence:.2f}")
        
        return " | ".join(explanation_parts)
    
    def make_execution_decision(
        self,
        confidence: ConfidenceScore,
        risk_level: str = "medium"
    ) -> ExecutionDecision:
        """
        Make execution decision based on confidence
        
        Args:
            confidence: Confidence score
            risk_level: Risk level of operation
        
        Returns:
            ExecutionDecision object
        """
        # Adjust confidence based on risk
        adjusted_confidence = confidence.value
        
        if risk_level == "high":
            adjusted_confidence -= 0.1
        elif risk_level == "critical":
            adjusted_confidence -= 0.2
        
        # Determine policy
        if adjusted_confidence >= self.thresholds[ExecutionPolicy.AUTO_EXECUTE]:
            policy = ExecutionPolicy.AUTO_EXECUTE
            should_execute = True
            requires_human = False
            reason = "Very high confidence - auto-executing"
        
        elif adjusted_confidence >= self.thresholds[ExecutionPolicy.AUTO_CONFIRM]:
            policy = ExecutionPolicy.AUTO_CONFIRM
            should_execute = True
            requires_human = False
            reason = "High confidence - executing with confirmation"
        
        elif adjusted_confidence >= self.thresholds[ExecutionPolicy.REQUIRE_CONFIRM]:
            policy = ExecutionPolicy.REQUIRE_CONFIRM
            should_execute = True
            requires_human = True
            reason = "Medium confidence - requires confirmation"
        
        elif adjusted_confidence >= self.thresholds[ExecutionPolicy.REQUIRE_REVIEW]:
            policy = ExecutionPolicy.REQUIRE_REVIEW
            should_execute = False
            requires_human = True
            reason = "Low confidence - requires review before execution"
        
        else:
            policy = ExecutionPolicy.REJECT
            should_execute = False
            requires_human = True
            reason = "Very low confidence - operation rejected"
        
        return ExecutionDecision(
            should_execute=should_execute,
            policy=policy,
            confidence=confidence,
            reason=reason,
            requires_human=requires_human
        )
    
    def get_confidence_trend(self, limit: int = 100) -> Dict:
        """
        Get confidence trend analysis
        
        Args:
            limit: Number of recent scores to analyze
        
        Returns:
            Trend analysis dictionary
        """
        recent_scores = self.confidence_history[-limit:]
        
        if not recent_scores:
            return {
                'trend': 'no_data',
                'average': 0.0,
                'count': 0
            }
        
        values = [s.value for s in recent_scores]
        avg = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        
        # Determine trend
        if len(recent_scores) >= 10:
            recent_avg = statistics.mean(values[-5:])
            earlier_avg = statistics.mean(values[:-5])
            
            if recent_avg > earlier_avg + 0.05:
                trend = 'improving'
            elif recent_avg < earlier_avg - 0.05:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'trend': trend,
            'average': avg,
            'std_dev': std,
            'count': len(recent_scores),
            'level_distribution': {
                level.value: sum(1 for s in recent_scores if s.level == level)
                for level in ConfidenceLevel
            }
        }


# Global confidence system instance
confidence_system = ConfidenceScoringSystem()


async def test_confidence_system():
    """Test confidence scoring system"""
    print("\n" + "="*60)
    print("CONFIDENCE SCORING SYSTEM TEST")
    print("="*60)
    
    # Test 1: High confidence operation
    print("\nTest 1: High Confidence Operation")
    try:
        confidence = confidence_system.calculate_confidence(
            operation="state_evolve",
            content="Evolving state with clear parameters and context",
            llm_response="The state evolution is well-defined with appropriate parameters...",
            context={'recent_commands': ['/state list', '/status']}
        )
        
        print(f"  Confidence: {confidence.value:.2f}")
        print(f"  Level: {confidence.level.value}")
        print(f"  Explanation: {confidence.explanation}")
        
        decision = confidence_system.make_execution_decision(confidence, "low")
        print(f"  Should Execute: {decision.should_execute}")
        print(f"  Policy: {decision.policy.value}")
        print(f"  Reason: {decision.reason}")
        print("✓ Test 1 passed")
    except Exception as e:
        print(f"✗ Test 1 failed: {str(e)}")
    
    # Test 2: Low confidence operation
    print("\nTest 2: Low Confidence Operation")
    try:
        confidence = confidence_system.calculate_confidence(
            operation="state_rollback",
            content="Short",
            llm_response=None,
            verification_result={'confidence': 0.4}
        )
        
        print(f"  Confidence: {confidence.value:.2f}")
        print(f"  Level: {confidence.level.value}")
        print(f"  Explanation: {confidence.explanation}")
        
        decision = confidence_system.make_execution_decision(confidence, "high")
        print(f"  Should Execute: {decision.should_execute}")
        print(f"  Policy: {decision.policy.value}")
        print(f"  Reason: {decision.reason}")
        print("✓ Test 2 passed")
    except Exception as e:
        print(f"✗ Test 2 failed: {str(e)}")
    
    # Test 3: Confidence trend
    print("\nTest 3: Confidence Trend Analysis")
    try:
        # Add some scores
        for i in range(10):
            confidence_system.calculate_confidence(
                operation="test",
                content=f"Test content {i}",
                llm_response=f"Test response {i}",
                context={}
            )
        
        trend = confidence_system.get_confidence_trend()
        print(f"  Trend: {trend['trend']}")
        print(f"  Average: {trend['average']:.2f}")
        print(f"  Count: {trend['count']}")
        print(f"  Level Distribution: {trend['level_distribution']}")
        print("✓ Test 3 passed")
    except Exception as e:
        print(f"✗ Test 3 failed: {str(e)}")
    
    # Test 4: Risk adjustment
    print("\nTest 4: Risk Adjustment")
    try:
        confidence = confidence_system.calculate_confidence(
            operation="test",
            content="Test content",
            llm_response="Test response"
        )
        
        print(f"  Original Confidence: {confidence.value:.2f}")
        
        decision_low = confidence_system.make_execution_decision(confidence, "low")
        decision_high = confidence_system.make_execution_decision(confidence, "high")
        decision_critical = confidence_system.make_execution_decision(confidence, "critical")
        
        print(f"  Low Risk: {decision_low.policy.value} - {decision_low.should_execute}")
        print(f"  High Risk: {decision_high.policy.value} - {decision_high.should_execute}")
        print(f"  Critical Risk: {decision_critical.policy.value} - {decision_critical.should_execute}")
        print("✓ Test 4 passed")
    except Exception as e:
        print(f"✗ Test 4 failed: {str(e)}")
    
    print("\n" + "="*60)
    print("CONFIDENCE SYSTEM TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_confidence_system())