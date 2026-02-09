"""
Gate Generator
Synthesizes gates based on failure modes and risk analysis
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib

from .models import (
    Gate,
    GateType,
    GateCategory,
    GateState,
    FailureMode,
    FailureModeType,
    RetirementCondition,
    RiskVector
)

# Import from confidence engine
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from confidence_engine.models import Phase, AuthorityBand


class GateGenerator:
    """
    Generates gates based on failure modes
    
    Gate Categories:
    1. Semantic Stability Gates - Prevent interpretation drift
    2. Verification Gates - Force deterministic checks
    3. Authority Decay Gates - Downgrade authority
    4. Isolation Gates - Enforce sandboxing
    
    DESIGN LAW: No gate may authorize action.
    Gates may only restrict or require more evidence.
    """
    
    def __init__(self):
        self.default_gate_duration = timedelta(hours=24)
    
    def generate_gates(
        self,
        failure_modes: List[FailureMode] | None = None,
        current_phase: Phase | None = None,
        current_authority: AuthorityBand | None = None,
        murphy_probabilities: Dict[str, float] | None = None,
        *,
        murphy_index: float | None = None,
        phase: str | None = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Gate]:
        """
        Generate gates for all failure modes
        
        Args:
            failure_modes: List of identified failure modes
            current_phase: Current phase
            current_authority: Current authority band
            murphy_probabilities: Murphy probabilities for each failure mode
        
        Returns:
            List of generated gates
        """
        if murphy_index is not None:
            if murphy_index < 0.3:
                count = 2
            elif murphy_index < 0.7:
                count = 4
            else:
                count = 6
            return [
                Gate(
                    id=f"gate-{i}",
                    type=GateType.VERIFICATION,
                    category=GateCategory.VERIFICATION_REQUIRED,
                    target="execution",
                    trigger_condition={},
                    enforcement_effect={"block": False},
                    state=GateState.ACTIVE,
                    created_at=datetime.now(),
                    expires_at=datetime.now() + self.default_gate_duration,
                    retirement_conditions=[],
                    metadata={"risk_vector": RiskVector(H=0.1, one_minus_D=0.1, exposure=0.1, authority_risk=0.1)},
                )
                for i in range(count)
            ]

        gates = []
        
        for failure_mode in failure_modes or []:
            murphy_prob = murphy_probabilities.get(failure_mode.id, 0.0)
            
            # Generate appropriate gate based on failure mode type
            if failure_mode.type == FailureModeType.SEMANTIC_DRIFT:
                gate = self.generate_semantic_stability_gate(
                    failure_mode,
                    current_phase,
                    murphy_prob
                )
            
            elif failure_mode.type == FailureModeType.VERIFICATION_INSUFFICIENT:
                gate = self.generate_verification_gate(
                    failure_mode,
                    current_phase,
                    murphy_prob
                )
            
            elif failure_mode.type == FailureModeType.AUTHORITY_MISUSE:
                gate = self.generate_authority_decay_gate(
                    failure_mode,
                    current_authority,
                    murphy_prob
                )
            
            elif failure_mode.type in [
                FailureModeType.IRREVERSIBLE_ACTION,
                FailureModeType.BLAST_RADIUS_EXCEEDED
            ]:
                gate = self.generate_isolation_gate(
                    failure_mode,
                    murphy_prob
                )
            
            elif failure_mode.type == FailureModeType.CONSTRAINT_VIOLATION:
                gate = self.generate_constraint_gate(
                    failure_mode,
                    murphy_prob
                )
            
            else:
                # Default: verification gate
                gate = self.generate_verification_gate(
                    failure_mode,
                    current_phase,
                    murphy_prob
                )
            
            if gate:
                gates.append(gate)
        
        return gates

    def generate_gates_for_domain(
        self,
        domain: str,
        phase: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Gate]:
        return [
            Gate(
                id=f"gate-{domain}-1",
                type=GateType.VERIFICATION,
                category=GateCategory.VERIFICATION_REQUIRED,
                target="domain",
                trigger_condition={},
                enforcement_effect={"block": False},
                state=GateState.ACTIVE,
                created_at=datetime.now(),
                expires_at=datetime.now() + self.default_gate_duration,
                retirement_conditions=[],
                metadata={"risk_vector": RiskVector(H=0.1, one_minus_D=0.1, exposure=0.1, authority_risk=0.1)},
            )
        ]
    
    def generate_semantic_stability_gate(
        self,
        failure_mode: FailureMode,
        current_phase: Phase,
        murphy_probability: float
    ) -> Gate:
        """
        Generate semantic stability gate
        
        Triggered when:
        - Multiple incompatible interpretations
        - Unresolved assumptions
        
        Effect:
        - Block phase advancement
        - Require clarification artifacts
        """
        gate_id = self._generate_gate_id("semantic_stability", failure_mode.id)
        
        # Trigger condition: epistemic instability too high
        trigger_condition = {
            'type': 'epistemic_instability',
            'threshold': 0.4,
            'current_value': failure_mode.risk_vector.H
        }
        
        # Enforcement effect: block phase advancement
        enforcement_effect = {
            'action': 'block_phase_advancement',
            'from_phase': current_phase.value,
            'reason': 'Semantic instability detected',
            'required_actions': [
                'Add clarification artifacts',
                'Resolve incompatible interpretations',
                'Verify assumptions'
            ]
        }
        
        # Retirement conditions
        retirement_conditions = [
            RetirementCondition(
                condition_type='risk_reduction',
                threshold=0.3,
                current_value=failure_mode.risk_vector.H
            ),
            RetirementCondition(
                condition_type='verification_success',
                threshold=0.7,
                current_value=0.0
            )
        ]
        
        priority = self._calculate_priority(murphy_probability, failure_mode.impact)
        expires_at = datetime.now() + self.default_gate_duration
        
        gate = Gate(
            id=gate_id,
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target=f"phase_{current_phase.value}",
            trigger_condition=trigger_condition,
            enforcement_effect=enforcement_effect,
            retirement_conditions=retirement_conditions,
            reason=failure_mode.description,
            failure_modes_addressed=[failure_mode.id],
            priority=priority,
            expires_at=expires_at
        )
        
        return gate
    
    def generate_verification_gate(
        self,
        failure_mode: FailureMode,
        current_phase: Phase,
        murphy_probability: float
    ) -> Gate:
        """Generate verification gate"""
        gate_id = self._generate_gate_id("verification", failure_mode.id)
        
        trigger_condition = {
            'type': 'deterministic_grounding',
            'threshold': 0.6,
            'current_value': 1.0 - failure_mode.risk_vector.one_minus_D
        }
        
        enforcement_effect = {
            'action': 'require_verification',
            'phase': current_phase.value,
            'reason': 'Insufficient deterministic grounding',
            'required_actions': [
                'Call computation plane for verification',
                'Add verification evidence',
                'Increase verified artifact ratio'
            ],
            'minimum_verified_ratio': 0.7
        }
        
        retirement_conditions = [
            RetirementCondition(
                condition_type='verification_success',
                threshold=0.7,
                current_value=1.0 - failure_mode.risk_vector.one_minus_D
            )
        ]
        
        priority = self._calculate_priority(murphy_probability, failure_mode.impact)
        expires_at = datetime.now() + self.default_gate_duration
        
        gate = Gate(
            id=gate_id,
            type=GateType.VERIFICATION,
            category=GateCategory.VERIFICATION_REQUIRED,
            target=f"phase_{current_phase.value}",
            trigger_condition=trigger_condition,
            enforcement_effect=enforcement_effect,
            retirement_conditions=retirement_conditions,
            reason=failure_mode.description,
            failure_modes_addressed=[failure_mode.id],
            priority=priority,
            expires_at=expires_at
        )
        
        return gate
    
    def generate_authority_decay_gate(
        self,
        failure_mode: FailureMode,
        current_authority: AuthorityBand,
        murphy_probability: float
    ) -> Gate:
        """Generate authority decay gate"""
        gate_id = self._generate_gate_id("authority_decay", failure_mode.id)
        
        trigger_condition = {
            'type': 'authority_risk',
            'threshold': 0.5,
            'current_value': failure_mode.risk_vector.authority_risk
        }
        
        authority_levels = [
            AuthorityBand.ASK_ONLY,
            AuthorityBand.GENERATE,
            AuthorityBand.PROPOSE,
            AuthorityBand.NEGOTIATE,
            AuthorityBand.EXECUTE
        ]
        
        current_idx = authority_levels.index(current_authority)
        target_authority = authority_levels[max(0, current_idx - 1)]
        
        enforcement_effect = {
            'action': 'downgrade_authority',
            'from_authority': current_authority.value,
            'to_authority': target_authority.value,
            'reason': 'Authority too high for confidence level'
        }
        
        retirement_conditions = [
            RetirementCondition(
                condition_type='confidence_recovery',
                threshold=0.85,
                current_value=0.0
            )
        ]
        
        priority = self._calculate_priority(murphy_probability, failure_mode.impact)
        expires_at = datetime.now() + self.default_gate_duration
        
        gate = Gate(
            id=gate_id,
            type=GateType.AUTHORITY,
            category=GateCategory.AUTHORITY_DECAY,
            target=f"authority_{current_authority.value}",
            trigger_condition=trigger_condition,
            enforcement_effect=enforcement_effect,
            retirement_conditions=retirement_conditions,
            reason=failure_mode.description,
            failure_modes_addressed=[failure_mode.id],
            priority=priority,
            expires_at=expires_at
        )
        
        return gate
    
    def generate_isolation_gate(
        self,
        failure_mode: FailureMode,
        murphy_probability: float
    ) -> Gate:
        """Generate isolation gate"""
        gate_id = self._generate_gate_id("isolation", failure_mode.id)
        
        trigger_condition = {
            'type': 'exposure',
            'threshold': 0.5,
            'current_value': failure_mode.risk_vector.exposure
        }
        
        enforcement_effect = {
            'action': 'enforce_isolation',
            'reason': 'Blast radius or irreversibility too high',
            'allowed_interfaces': ['sandbox', 'simulation'],
            'blocked_interfaces': ['production', 'external_api']
        }
        
        retirement_conditions = [
            RetirementCondition(
                condition_type='risk_reduction',
                threshold=0.3,
                current_value=failure_mode.risk_vector.exposure
            )
        ]
        
        priority = self._calculate_priority(murphy_probability, failure_mode.impact)
        priority = min(10, priority + 2)
        
        expires_at = datetime.now() + self.default_gate_duration
        
        gate = Gate(
            id=gate_id,
            type=GateType.ISOLATION,
            category=GateCategory.ISOLATION_REQUIRED,
            target="execution_environment",
            trigger_condition=trigger_condition,
            enforcement_effect=enforcement_effect,
            retirement_conditions=retirement_conditions,
            reason=failure_mode.description,
            failure_modes_addressed=[failure_mode.id],
            priority=priority,
            expires_at=expires_at
        )
        
        return gate
    
    def generate_constraint_gate(
        self,
        failure_mode: FailureMode,
        murphy_probability: float
    ) -> Gate:
        """Generate constraint gate"""
        gate_id = self._generate_gate_id("constraint", failure_mode.id)
        
        trigger_condition = {
            'type': 'constraint_check',
            'threshold': 1.0,
            'current_value': 0.0
        }
        
        enforcement_effect = {
            'action': 'enforce_constraints',
            'reason': 'Potential constraint violation detected'
        }
        
        retirement_conditions = [
            RetirementCondition(
                condition_type='verification_success',
                threshold=1.0,
                current_value=0.0
            )
        ]
        
        priority = self._calculate_priority(murphy_probability, failure_mode.impact)
        expires_at = datetime.now() + self.default_gate_duration
        
        gate = Gate(
            id=gate_id,
            type=GateType.CONSTRAINT,
            category=GateCategory.SEMANTIC_STABILITY,
            target="constraints",
            trigger_condition=trigger_condition,
            enforcement_effect=enforcement_effect,
            retirement_conditions=retirement_conditions,
            reason=failure_mode.description,
            failure_modes_addressed=[failure_mode.id],
            priority=priority,
            expires_at=expires_at
        )
        
        return gate
    
    def _calculate_priority(self, murphy_probability: float, impact: float) -> int:
        """Calculate gate priority"""
        base_priority = int(murphy_probability * 10)
        impact_adjustment = int(impact * 3)
        priority = base_priority + impact_adjustment
        return max(1, min(10, priority))
    
    def _generate_gate_id(self, gate_type: str, failure_mode_id: str) -> str:
        """Generate unique gate ID"""
        content = f"{gate_type}_{failure_mode_id}_{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
