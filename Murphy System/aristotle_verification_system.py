"""
Murphy System - Phase 3: Aristotle Verification System
Deterministic verification for critical operations
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for operations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationResult(Enum):
    """Verification result types"""
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"
    PENDING = "pending"


class OperationType(Enum):
    """Types of operations to verify"""
    STATE_EVOLVE = "state_evolve"
    STATE_ROLLBACK = "state_rollback"
    AGENT_ASSIGNMENT = "agent_assignment"
    GATE_CREATION = "gate_creation"
    SWARM_EXECUTION = "swarm_execution"
    DOCUMENT_GENERATION = "document_generation"
    SYSTEM_INITIALIZATION = "system_initialization"


@dataclass
class VerificationRequest:
    """Verification request data"""
    operation: OperationType
    risk_level: RiskLevel
    content: str
    criteria: str
    context: Dict
    timestamp: datetime


@dataclass
class VerificationResponse:
    """Verification response data"""
    result: VerificationResult
    confidence: float
    explanation: str
    verified_by: str
    verification_time: float
    timestamp: datetime


class AristotleVerificationSystem:
    """Aristotle verification system"""
    
    def __init__(self):
        """Initialize verification system"""
        self.verification_history: List[Dict] = []
        self.high_risk_threshold = 0.8
        self.medium_risk_threshold = 0.6
        self.auto_verify_threshold = 0.9
        
        # Define operations requiring verification
        self.high_risk_operations = {
            OperationType.STATE_ROLLBACK,
            OperationType.SWARM_EXECUTION,
            OperationType.GATE_CREATION
        }
        
        self.medium_risk_operations = {
            OperationType.STATE_EVOLVE,
            OperationType.AGENT_ASSIGNMENT,
            OperationType.DOCUMENT_GENERATION
        }
        
        logger.info("Aristotle Verification System initialized")
    
    def get_risk_level(self, operation: OperationType) -> RiskLevel:
        """
        Get risk level for operation
        
        Args:
            operation: Operation type
        
        Returns:
            Risk level
        """
        if operation in self.high_risk_operations:
            return RiskLevel.HIGH
        elif operation in self.medium_risk_operations:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def requires_verification(self, operation: OperationType) -> bool:
        """
        Check if operation requires verification
        
        Args:
            operation: Operation type
        
        Returns:
            True if verification required
        """
        risk_level = self.get_risk_level(operation)
        return risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    async def verify_operation(
        self,
        operation: OperationType,
        content: str,
        context: Dict = None,
        custom_criteria: str = None
    ) -> VerificationResponse:
        """
        Verify an operation using Aristotle
        
        Args:
            operation: Operation type
            content: Content to verify
            context: Additional context
            custom_criteria: Custom verification criteria
        
        Returns:
            VerificationResponse object
        """
        from aristotle_client import AristotleClient
        
        # Get risk level
        risk_level = self.get_risk_level(operation)
        
        # Generate verification criteria
        if custom_criteria:
            criteria = custom_criteria
        else:
            criteria = self._generate_criteria(operation, context)
        
        # Get Aristotle client
        aristotle = None
        try:
            from llm_integration_manager import llm_manager, LLMProvider
            aristotle = llm_manager.providers.get(LLMProvider.ARISTOTLE)
        except ImportError:
            pass
        
        if not aristotle:
            logger.warning("Aristotle client not available, skipping verification")
            return VerificationResponse(
                result=VerificationResult.PENDING,
                confidence=0.0,
                explanation="Verification system unavailable",
                verified_by="none",
                verification_time=0.0,
                timestamp=datetime.now()
            )
        
        # Perform verification
        start_time = datetime.now()
        
        try:
            is_valid, confidence, explanation = await aristotle.verify(
                content=content,
                criteria=criteria,
                max_tokens=1024
            )
            
            verification_time = (datetime.now() - start_time).total_seconds()
            
            # Determine result based on confidence and validity
            result = self._determine_result(is_valid, confidence, risk_level)
            
            # Log verification
            self._log_verification(operation, result, confidence, explanation)
            
            return VerificationResponse(
                result=result,
                confidence=confidence,
                explanation=explanation,
                verified_by="aristotle",
                verification_time=verification_time,
                timestamp=datetime.now()
            )
        
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            
            return VerificationResponse(
                result=VerificationResult.REQUIRES_REVIEW,
                confidence=0.0,
                explanation=f"Verification error: {str(e)}",
                verified_by="error",
                verification_time=(datetime.now() - start_time).total_seconds(),
                timestamp=datetime.now()
            )
    
    def _generate_criteria(self, operation: OperationType, context: Dict) -> str:
        """Generate verification criteria for operation"""
        criteria_templates = {
            OperationType.STATE_EVOLVE: """
Verify state evolution operation:
1. State transition is logical and valid
2. Child states are properly structured
3. Confidence levels are appropriate
4. No circular dependencies introduced
5. State evolution follows system rules
""",
            OperationType.STATE_ROLLBACK: """
Verify state rollback operation:
1. Rollback target is valid ancestor
2. No orphaned child states will be created
3. Rollback is reversible
4. System integrity maintained
5. No critical data will be lost
""",
            OperationType.AGENT_ASSIGNMENT: """
Verify agent assignment operation:
1. Agent has required capabilities
2. Assignment is appropriate for agent role
3. No conflicting assignments
4. Resource constraints respected
5. Assignment aligns with system goals
""",
            OperationType.GATE_CREATION: """
Verify gate creation operation:
1. Gate criteria are clear and measurable
2. Gate type is appropriate for purpose
3. Gate doesn't create circular dependencies
4. Gate validation logic is sound
5. Gate aligns with system architecture
""",
            OperationType.SWARM_EXECUTION: """
Verify swarm execution operation:
1. Swarm configuration is valid
2. Task is appropriate for swarm processing
3. Resource requirements are reasonable
4. Swarm won't cause system instability
5. Expected outcomes are realistic
""",
            OperationType.DOCUMENT_GENERATION: """
Verify document generation operation:
1. Document structure is valid
2. Content is appropriate for purpose
3. No sensitive data included
4. Formatting is consistent
5. Document meets quality standards
""",
            OperationType.SYSTEM_INITIALIZATION: """
Verify system initialization operation:
1. Initialization parameters are valid
2. Required resources are available
3. Initialization sequence is correct
4. No conflicts with existing state
5. Initialization is idempotent
"""
        }
        
        return criteria_templates.get(operation, "Verify operation meets quality and safety standards.")
    
    def _determine_result(
        self,
        is_valid: bool,
        confidence: float,
        risk_level: RiskLevel
    ) -> VerificationResult:
        """Determine verification result"""
        
        # High confidence and valid
        if is_valid and confidence >= self.auto_verify_threshold:
            return VerificationResult.VERIFIED
        
        # Invalid or low confidence for high-risk operations
        if not is_valid or confidence < self.medium_risk_threshold:
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                return VerificationResult.REJECTED
            else:
                return VerificationResult.REQUIRES_REVIEW
        
        # Medium confidence
        if confidence >= self.high_risk_threshold:
            return VerificationResult.VERIFIED
        elif confidence >= self.medium_risk_threshold:
            return VerificationResult.REQUIRES_REVIEW
        else:
            return VerificationResult.REJECTED
    
    def _log_verification(
        self,
        operation: OperationType,
        result: VerificationResult,
        confidence: float,
        explanation: str
    ):
        """Log verification for audit trail"""
        log_entry = {
            'operation': operation.value,
            'result': result.value,
            'confidence': confidence,
            'explanation': explanation,
            'timestamp': datetime.now().isoformat()
        }
        
        self.verification_history.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self.verification_history) > 1000:
            self.verification_history = self.verification_history[-1000:]
        
        logger.info(f"Verification logged: {operation.value} -> {result.value} ({confidence:.2f})")
    
    def get_verification_history(
        self,
        operation: Optional[OperationType] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get verification history
        
        Args:
            operation: Filter by operation type
            limit: Maximum number of entries
        
        Returns:
            List of verification entries
        """
        history = self.verification_history
        
        if operation:
            history = [e for e in history if e['operation'] == operation.value]
        
        return history[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get verification statistics"""
        total = len(self.verification_history)
        
        if total == 0:
            return {
                'total_verifications': 0,
                'verified_count': 0,
                'rejected_count': 0,
                'review_count': 0,
                'average_confidence': 0.0
            }
        
        verified = sum(1 for e in self.verification_history if e['result'] == 'verified')
        rejected = sum(1 for e in self.verification_history if e['result'] == 'rejected')
        review = sum(1 for e in self.verification_history if e['result'] == 'requires_review')
        
        avg_confidence = sum(e['confidence'] for e in self.verification_history) / total
        
        return {
            'total_verifications': total,
            'verified_count': verified,
            'rejected_count': rejected,
            'review_count': review,
            'average_confidence': avg_confidence,
            'verification_rate': verified / total if total > 0 else 0.0
        }


# Global verification system instance
verification_system = AristotleVerificationSystem()


async def test_verification_system():
    """Test verification system"""
    print("\n" + "="*60)
    print("ARISTOTLE VERIFICATION SYSTEM TEST")
    print("="*60)
    
    # Test 1: Verify state evolution
    print("\nTest 1: Verify State Evolution")
    try:
        response = await verification_system.verify_operation(
            operation=OperationType.STATE_EVOLVE,
            content="Evolving state_1 into child states with confidence 0.95",
            context={'parent_id': 'state_1', 'children': 3}
        )
        
        print(f"  Result: {response.result.value}")
        print(f"  Confidence: {response.confidence:.2f}")
        print(f"  Explanation: {response.explanation[:100]}...")
        print("✓ Test 1 passed")
    except Exception as e:
        print(f"✗ Test 1 failed: {str(e)}")
    
    # Test 2: Verify state rollback (high risk)
    print("\nTest 2: Verify State Rollback (High Risk)")
    try:
        response = await verification_system.verify_operation(
            operation=OperationType.STATE_ROLLBACK,
            content="Rolling back from state_1_child_1 to state_1",
            context={'from': 'state_1_child_1', 'to': 'state_1'}
        )
        
        print(f"  Result: {response.result.value}")
        print(f"  Confidence: {response.confidence:.2f}")
        print(f"  Explanation: {response.explanation[:100]}...")
        print("✓ Test 2 passed")
    except Exception as e:
        print(f"✗ Test 2 failed: {str(e)}")
    
    # Test 3: Get verification history
    print("\nTest 3: Get Verification History")
    try:
        history = verification_system.get_verification_history()
        print(f"  Total verifications: {len(history)}")
        print(f"  Latest: {history[-1] if history else 'None'}")
        print("✓ Test 3 passed")
    except Exception as e:
        print(f"✗ Test 3 failed: {str(e)}")
    
    # Test 4: Get statistics
    print("\nTest 4: Get Statistics")
    try:
        stats = verification_system.get_statistics()
        print(f"  Total: {stats['total_verifications']}")
        print(f"  Verified: {stats['verified_count']}")
        print(f"  Rejected: {stats['rejected_count']}")
        print(f"  Review: {stats['review_count']}")
        print(f"  Avg Confidence: {stats['average_confidence']:.2f}")
        print("✓ Test 4 passed")
    except Exception as e:
        print(f"✗ Test 4 failed: {str(e)}")
    
    print("\n" + "="*60)
    print("VERIFICATION SYSTEM TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_verification_system())