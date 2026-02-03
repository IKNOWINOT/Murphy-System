# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Insurance Risk-Based Gate System
Uses actuarial risk assessment formulas to establish gate requirements dynamically

Based on insurance industry risk models:
- Probability of Loss (Frequency)
- Severity of Loss (Impact)
- Expected Loss = Frequency × Severity
- Risk Score = (Frequency × Severity) / Controls
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# INSURANCE RISK TERMINOLOGY
# ============================================================================

class RiskCategory(str, Enum):
    """Standard insurance risk categories"""
    OPERATIONAL = "operational"  # Day-to-day operations
    STRATEGIC = "strategic"      # Business strategy decisions
    FINANCIAL = "financial"      # Financial/cost risks
    COMPLIANCE = "compliance"    # Regulatory/legal risks
    REPUTATIONAL = "reputational"  # Brand/reputation risks
    TECHNICAL = "technical"      # Technology/system risks

class LossType(str, Enum):
    """Types of losses in insurance terms"""
    DIRECT = "direct"           # Direct monetary loss
    INDIRECT = "indirect"       # Consequential loss
    LIABILITY = "liability"     # Third-party liability
    OPPORTUNITY = "opportunity"  # Lost opportunity cost

class ControlEffectiveness(str, Enum):
    """Control effectiveness ratings"""
    STRONG = "strong"       # 90%+ effective
    ADEQUATE = "adequate"   # 70-89% effective
    WEAK = "weak"          # 50-69% effective
    ABSENT = "absent"      # <50% effective

# ============================================================================
# ACTUARIAL RISK MODELS
# ============================================================================

@dataclass
class RiskExposure:
    """
    Risk exposure in insurance terms
    
    Exposure = The amount at risk (e.g., token budget, revenue, reputation)
    """
    exposure_value: float  # Dollar value or token count at risk
    exposure_type: str     # What's at risk (tokens, revenue, reputation)
    time_period: int       # Time period in days
    
    def annual_exposure(self) -> float:
        """Convert to annual exposure"""
        return (self.exposure_value / self.time_period) * 365

@dataclass
class LossFrequency:
    """
    Frequency of loss events (actuarial term)
    
    Frequency = How often losses occur
    Measured as events per time period
    """
    historical_events: int  # Number of past events
    time_period: int        # Time period in days
    confidence_level: float  # Statistical confidence (0.0-1.0)
    
    def annual_frequency(self) -> float:
        """Calculate annual frequency"""
        if self.time_period == 0:
            return 0.0
        return (self.historical_events / self.time_period) * 365
    
    def probability(self) -> float:
        """Probability of at least one event"""
        freq = self.annual_frequency()
        # Poisson distribution: P(X >= 1) = 1 - P(X = 0) = 1 - e^(-λ)
        return 1 - math.exp(-freq) if freq > 0 else 0.0

@dataclass
class LossSeverity:
    """
    Severity of loss (actuarial term)
    
    Severity = Average loss amount when event occurs
    """
    average_loss: float      # Average loss per event
    maximum_loss: float      # Maximum possible loss
    loss_distribution: str   # Distribution type (normal, lognormal, pareto)
    
    def severity_ratio(self) -> float:
        """Ratio of average to maximum loss"""
        if self.maximum_loss == 0:
            return 0.0
        return self.average_loss / self.maximum_loss
    
    def tail_risk(self) -> float:
        """Tail risk (extreme loss probability)"""
        # Simple heuristic: higher ratio = lower tail risk
        return 1.0 - self.severity_ratio()

@dataclass
class RiskControl:
    """
    Risk control measure (insurance term)
    
    Controls reduce either frequency or severity of losses
    """
    control_id: str
    control_type: str  # preventive, detective, corrective
    effectiveness: ControlEffectiveness
    cost: float  # Cost to implement/maintain
    
    def effectiveness_factor(self) -> float:
        """Convert effectiveness to reduction factor"""
        return {
            ControlEffectiveness.STRONG: 0.90,
            ControlEffectiveness.ADEQUATE: 0.75,
            ControlEffectiveness.WEAK: 0.55,
            ControlEffectiveness.ABSENT: 0.10
        }[self.effectiveness]
    
    def frequency_reduction(self) -> float:
        """How much this control reduces frequency"""
        if self.control_type == "preventive":
            return self.effectiveness_factor()
        return self.effectiveness_factor() * 0.3  # Less effective on frequency
    
    def severity_reduction(self) -> float:
        """How much this control reduces severity"""
        if self.control_type in ["detective", "corrective"]:
            return self.effectiveness_factor()
        return self.effectiveness_factor() * 0.3  # Less effective on severity

# ============================================================================
# ACTUARIAL FORMULAS
# ============================================================================

class ActuarialRiskCalculator:
    """
    Calculate risk using insurance actuarial formulas
    
    Key formulas:
    1. Expected Loss = Frequency × Severity
    2. Risk Score = Expected Loss / Controls
    3. Loss Ratio = Actual Loss / Expected Loss
    4. Combined Ratio = (Losses + Expenses) / Premium
    """
    
    @staticmethod
    def expected_loss(frequency: LossFrequency, severity: LossSeverity) -> float:
        """
        Calculate Expected Loss (EL)
        
        EL = Frequency × Severity
        
        This is the fundamental actuarial formula
        """
        return frequency.annual_frequency() * severity.average_loss
    
    @staticmethod
    def risk_score(expected_loss: float, controls: List[RiskControl]) -> float:
        """
        Calculate Risk Score with controls
        
        Risk Score = Expected Loss / (1 + Control Effectiveness)
        
        Lower score = better (controls are working)
        """
        if not controls:
            return expected_loss
        
        # Calculate combined control effectiveness
        total_effectiveness = sum(c.effectiveness_factor() for c in controls) / len(controls)
        
        # Risk score decreases with better controls
        return expected_loss / (1 + total_effectiveness)
    
    @staticmethod
    def value_at_risk(exposure: RiskExposure, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR)
        
        VaR = Maximum loss at given confidence level
        
        Used in insurance to determine capital requirements
        """
        # Simple VaR using normal distribution approximation
        # For 95% confidence: VaR ≈ Mean + 1.645 × StdDev
        # Assuming StdDev = 20% of exposure
        z_score = {
            0.90: 1.282,
            0.95: 1.645,
            0.99: 2.326
        }.get(confidence_level, 1.645)
        
        std_dev = exposure.exposure_value * 0.2
        return exposure.exposure_value + (z_score * std_dev)
    
    @staticmethod
    def loss_ratio(actual_loss: float, expected_loss: float) -> float:
        """
        Calculate Loss Ratio
        
        Loss Ratio = Actual Loss / Expected Loss
        
        > 1.0 = Worse than expected
        < 1.0 = Better than expected
        """
        if expected_loss == 0:
            return 0.0
        return actual_loss / expected_loss
    
    @staticmethod
    def combined_ratio(losses: float, expenses: float, premium: float) -> float:
        """
        Calculate Combined Ratio
        
        Combined Ratio = (Losses + Expenses) / Premium
        
        < 1.0 = Profitable
        > 1.0 = Unprofitable
        """
        if premium == 0:
            return float('inf')
        return (losses + expenses) / premium
    
    @staticmethod
    def retention_limit(exposure: RiskExposure, risk_appetite: float) -> float:
        """
        Calculate Retention Limit (self-insurance amount)
        
        Retention = Amount organization keeps (doesn't insure)
        
        Based on risk appetite (0.0 = risk averse, 1.0 = risk seeking)
        """
        return exposure.exposure_value * risk_appetite
    
    @staticmethod
    def premium_calculation(expected_loss: float, expense_ratio: float = 0.25,
                          profit_margin: float = 0.10) -> float:
        """
        Calculate Insurance Premium
        
        Premium = Expected Loss / (1 - Expense Ratio - Profit Margin)
        
        This is how insurers price policies
        """
        denominator = 1 - expense_ratio - profit_margin
        if denominator <= 0:
            return float('inf')
        return expected_loss / denominator

# ============================================================================
# RISK-BASED GATE GENERATOR
# ============================================================================

class InsuranceRiskGateGenerator:
    """
    Generate decision gates based on insurance risk assessment
    
    Uses actuarial formulas to determine:
    - Which gates are needed
    - Gate thresholds
    - Gate priority
    - Required controls
    """
    
    def __init__(self):
        self.calculator = ActuarialRiskCalculator()
        self.risk_appetite = 0.3  # Conservative (0.0-1.0)
        logger.info("Initialized Insurance Risk Gate Generator")
    
    def assess_task_risk(self, task: Dict, context: Dict) -> Dict:
        """
        Assess task risk using insurance methodology
        
        Returns complete risk assessment with actuarial metrics
        """
        # 1. Identify exposure
        exposure = self._calculate_exposure(task, context)
        
        # 2. Estimate frequency
        frequency = self._estimate_frequency(task, context)
        
        # 3. Estimate severity
        severity = self._estimate_severity(task, context)
        
        # 4. Identify existing controls
        controls = self._identify_controls(task, context)
        
        # 5. Calculate risk metrics
        expected_loss = self.calculator.expected_loss(frequency, severity)
        risk_score = self.calculator.risk_score(expected_loss, controls)
        var_95 = self.calculator.value_at_risk(exposure, 0.95)
        retention = self.calculator.retention_limit(exposure, self.risk_appetite)
        
        # 6. Determine risk category
        risk_category = self._categorize_risk(risk_score, expected_loss)
        
        assessment = {
            'exposure': {
                'value': exposure.exposure_value,
                'type': exposure.exposure_type,
                'annual': exposure.annual_exposure()
            },
            'frequency': {
                'annual': frequency.annual_frequency(),
                'probability': frequency.probability(),
                'confidence': frequency.confidence_level
            },
            'severity': {
                'average': severity.average_loss,
                'maximum': severity.maximum_loss,
                'tail_risk': severity.tail_risk()
            },
            'controls': {
                'count': len(controls),
                'effectiveness': sum(c.effectiveness_factor() for c in controls) / len(controls) if controls else 0.0
            },
            'metrics': {
                'expected_loss': expected_loss,
                'risk_score': risk_score,
                'value_at_risk_95': var_95,
                'retention_limit': retention,
                'transfer_amount': max(0, expected_loss - retention)
            },
            'category': risk_category,
            'requires_gates': risk_score > 100  # Threshold for gate requirement
        }
        
        return assessment
    
    def generate_gates_from_risk(self, risk_assessment: Dict, task: Dict) -> List[Dict]:
        """
        Generate decision gates based on risk assessment
        
        Gate requirements determined by actuarial risk levels
        """
        gates = []
        
        risk_score = risk_assessment['metrics']['risk_score']
        expected_loss = risk_assessment['metrics']['expected_loss']
        category = risk_assessment['category']
        
        # Gate 1: Risk Acceptance Gate (always required if risk > threshold)
        if risk_score > 100:
            gates.append({
                'gate_id': f"risk_acceptance_{task.get('id', 'unknown')}",
                'gate_type': 'risk_acceptance',
                'question': f"Accept risk score of {risk_score:.0f} with expected loss of ${expected_loss:.2f}?",
                'options': [
                    'Accept Risk - Proceed',
                    'Mitigate Risk - Add Controls',
                    'Transfer Risk - Seek Insurance',
                    'Avoid Risk - Reject Task'
                ],
                'threshold': risk_score,
                'reasoning': f"Risk category: {category}. Actuarial analysis shows significant exposure.",
                'required': True,
                'priority': 10
            })
        
        # Gate 2: Control Adequacy Gate (if controls are weak)
        control_effectiveness = risk_assessment['controls']['effectiveness']
        if control_effectiveness < 0.7:
            gates.append({
                'gate_id': f"control_adequacy_{task.get('id', 'unknown')}",
                'gate_type': 'control_adequacy',
                'question': f"Current controls are {control_effectiveness*100:.0f}% effective. Strengthen controls?",
                'options': [
                    'Strengthen Controls - Add Preventive Measures',
                    'Accept Current Controls',
                    'Implement Detective Controls',
                    'Add Corrective Controls'
                ],
                'threshold': control_effectiveness,
                'reasoning': f"Control effectiveness below 70% threshold. Insurance best practice requires stronger controls.",
                'required': risk_score > 500,
                'priority': 8
            })
        
        # Gate 3: Retention vs Transfer Gate (if expected loss > retention limit)
        retention_limit = risk_assessment['metrics']['retention_limit']
        transfer_amount = risk_assessment['metrics']['transfer_amount']
        
        if transfer_amount > 0:
            gates.append({
                'gate_id': f"retention_transfer_{task.get('id', 'unknown')}",
                'gate_type': 'retention_transfer',
                'question': f"Expected loss ${expected_loss:.2f} exceeds retention limit ${retention_limit:.2f}. Transfer ${transfer_amount:.2f}?",
                'options': [
                    f'Retain All Risk - Self-Insure ${expected_loss:.2f}',
                    f'Transfer Excess - Insure ${transfer_amount:.2f}',
                    'Increase Retention Limit',
                    'Reduce Exposure'
                ],
                'threshold': transfer_amount,
                'reasoning': f"Transfer amount exceeds risk appetite. Consider risk transfer mechanisms.",
                'required': transfer_amount > retention_limit * 0.5,
                'priority': 9
            })
        
        # Gate 4: Tail Risk Gate (if tail risk is high)
        tail_risk = risk_assessment['severity']['tail_risk']
        if tail_risk > 0.7:
            gates.append({
                'gate_id': f"tail_risk_{task.get('id', 'unknown')}",
                'gate_type': 'tail_risk',
                'question': f"Tail risk is {tail_risk*100:.0f}% - potential for extreme losses. Proceed?",
                'options': [
                    'Accept Tail Risk',
                    'Cap Maximum Loss',
                    'Require Excess Coverage',
                    'Reject Due to Tail Risk'
                ],
                'threshold': tail_risk,
                'reasoning': f"High tail risk indicates potential for catastrophic losses beyond average.",
                'required': tail_risk > 0.8,
                'priority': 10
            })
        
        # Gate 5: Value at Risk Gate (if VaR exceeds budget)
        var_95 = risk_assessment['metrics']['value_at_risk_95']
        budget = task.get('budget', float('inf'))
        
        if var_95 > budget:
            gates.append({
                'gate_id': f"var_budget_{task.get('id', 'unknown')}",
                'gate_type': 'value_at_risk',
                'question': f"95% VaR of ${var_95:.2f} exceeds budget of ${budget:.2f}. Approve?",
                'options': [
                    'Approve - Increase Budget',
                    'Reduce Scope - Lower VaR',
                    'Reject - Exceeds Budget',
                    'Seek Additional Funding'
                ],
                'threshold': var_95,
                'reasoning': f"Value at Risk exceeds available budget. 5% chance of loss > ${var_95:.2f}",
                'required': True,
                'priority': 10
            })
        
        # Sort gates by priority
        gates.sort(key=lambda g: g['priority'], reverse=True)
        
        logger.info(f"Generated {len(gates)} risk-based gates for task {task.get('id', 'unknown')}")
        return gates
    
    def _calculate_exposure(self, task: Dict, context: Dict) -> RiskExposure:
        """Calculate risk exposure for task"""
        # Estimate exposure value
        token_budget = context.get('token_budget', 10000)
        revenue_potential = task.get('revenue_potential', 0)
        
        # Exposure is the greater of cost or revenue at risk
        exposure_value = max(token_budget, revenue_potential)
        
        # Determine exposure type
        if revenue_potential > token_budget:
            exposure_type = "revenue"
        else:
            exposure_type = "tokens"
        
        # Time period (default 30 days)
        time_period = task.get('duration_days', 30)
        
        return RiskExposure(
            exposure_value=exposure_value,
            exposure_type=exposure_type,
            time_period=time_period
        )
    
    def _estimate_frequency(self, task: Dict, context: Dict) -> LossFrequency:
        """Estimate loss frequency based on historical data"""
        # Get historical failure rate
        task_type = task.get('type', 'unknown')
        historical_failures = context.get('historical_failures', {})
        
        # Default failure rates by task type
        default_rates = {
            'simple': 0.05,   # 5% failure rate
            'medium': 0.15,   # 15% failure rate
            'complex': 0.30   # 30% failure rate
        }
        
        complexity = task.get('complexity', 'medium')
        failure_rate = default_rates.get(complexity, 0.15)
        
        # Historical events (failures per year)
        historical_events = int(failure_rate * 100)  # Scale to annual events
        
        return LossFrequency(
            historical_events=historical_events,
            time_period=365,
            confidence_level=0.80
        )
    
    def _estimate_severity(self, task: Dict, context: Dict) -> LossSeverity:
        """Estimate loss severity"""
        # Average loss is typically 50% of exposure
        exposure_value = max(
            context.get('token_budget', 10000),
            task.get('revenue_potential', 0)
        )
        
        average_loss = exposure_value * 0.5
        maximum_loss = exposure_value  # Maximum is total exposure
        
        return LossSeverity(
            average_loss=average_loss,
            maximum_loss=maximum_loss,
            loss_distribution='lognormal'
        )
    
    def _identify_controls(self, task: Dict, context: Dict) -> List[RiskControl]:
        """Identify existing risk controls"""
        controls = []
        
        # Check for quality controls
        if context.get('has_quality_check', False):
            controls.append(RiskControl(
                control_id='quality_check',
                control_type='detective',
                effectiveness=ControlEffectiveness.ADEQUATE,
                cost=50
            ))
        
        # Check for approval controls
        if context.get('requires_approval', False):
            controls.append(RiskControl(
                control_id='approval_gate',
                control_type='preventive',
                effectiveness=ControlEffectiveness.STRONG,
                cost=25
            ))
        
        # Check for monitoring controls
        if context.get('has_monitoring', True):
            controls.append(RiskControl(
                control_id='monitoring',
                control_type='detective',
                effectiveness=ControlEffectiveness.ADEQUATE,
                cost=10
            ))
        
        return controls
    
    def _categorize_risk(self, risk_score: float, expected_loss: float) -> str:
        """Categorize risk level"""
        if risk_score < 100:
            return 'low'
        elif risk_score < 500:
            return 'medium'
        elif risk_score < 1000:
            return 'high'
        else:
            return 'critical'

# ============================================================================
# INTEGRATION WITH GENERATIVE GATE SYSTEM
# ============================================================================

class InsuranceRiskSensorAgent:
    """
    Sensor agent that uses insurance risk formulas
    
    This bridges the insurance risk model with the generative gate system
    """
    
    def __init__(self):
        self.sensor_id = "insurance_risk_sensor"
        self.sensor_type = "insurance_risk"
        self.risk_generator = InsuranceRiskGateGenerator()
        logger.info("Initialized Insurance Risk Sensor Agent")
    
    def analyze_and_generate_gates(self, task: Dict, context: Dict) -> Tuple[Dict, List[Dict]]:
        """
        Analyze task risk and generate gates
        
        Returns:
            (risk_assessment, gates)
        """
        # Assess risk using insurance formulas
        risk_assessment = self.risk_generator.assess_task_risk(task, context)
        
        # Generate gates based on risk
        gates = self.risk_generator.generate_gates_from_risk(risk_assessment, task)
        
        return risk_assessment, gates

# Global instance
_insurance_risk_sensor = None

def get_insurance_risk_sensor() -> InsuranceRiskSensorAgent:
    """Get or create the global insurance risk sensor"""
    global _insurance_risk_sensor
    if _insurance_risk_sensor is None:
        _insurance_risk_sensor = InsuranceRiskSensorAgent()
    return _insurance_risk_sensor