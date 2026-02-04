# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Generative Decision Gate System
Dynamically generates decision gates based on context, business requirements, and sensor inputs
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Literal, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel, validator, Field
import json

logger = logging.getLogger(__name__)

# ============================================================================
# STANDARD TERMINOLOGY & NAMING CONVENTIONS
# ============================================================================

STANDARD_TERMS = {
    'agent': 'An autonomous entity that performs tasks',
    'sensor_agent': 'Agent that monitors and generates rules',
    'worker_agent': 'Agent that executes tasks',
    'task': 'A unit of work to be completed',
    'decision_gate': 'A checkpoint requiring evaluation',
    'confidence': 'Numeric measure of certainty (0.0-1.0)',
    'confidence_level': 'Categorical confidence (green/yellow/red)',
}

# ============================================================================
# TYPE SAFETY & VALIDATION (Pydantic Models)
# ============================================================================

class ConfidenceLevelEnum(str, Enum):
    """Strictly typed confidence levels"""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class GateTypeEnum(str, Enum):
    """Types of decision gates"""
    QUALITY = "quality"
    COMPLIANCE = "compliance"
    COST = "cost"
    SPEED = "speed"
    BRAND = "brand"
    SECURITY = "security"
    ACCURACY = "accuracy"
    CUSTOM = "custom"

class RuleModel(BaseModel):
    """Strictly typed rule"""
    rule_id: str
    rule_type: str
    condition: str
    action: str
    priority: int = Field(ge=1, le=10)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class GateSpecModel(BaseModel):
    """Strictly typed gate specification"""
    gate_id: str
    gate_type: GateTypeEnum
    question: str
    options: List[str] = Field(min_items=2)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    token_cost: int = Field(ge=0)
    revenue_impact: float = Field(ge=0.0)
    required: bool = True
    
    @validator('options')
    def validate_options(cls, v):
        if len(v) < 2:
            raise ValueError('Gate must have at least 2 options')
        return v

class ObservationModel(BaseModel):
    """Strictly typed observation from sensor"""
    sensor_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metric_name: str
    metric_value: float
    threshold: Optional[float] = None
    status: Literal['normal', 'warning', 'critical']
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# DEFENSIVE PROGRAMMING PATTERNS
# ============================================================================

class CapabilityRegistry:
    """Registry of actual system capabilities - prevents hallucination"""
    
    _capabilities = {
        'generate_content': True,
        'analyze_sentiment': True,
        'extract_entities': True,
        'translate_text': True,
        'summarize_document': True,
        'generate_code': True,
        'analyze_data': True,
        'create_visualization': True,
    }
    
    @classmethod
    def verify_capability(cls, capability: str) -> bool:
        """Check if capability actually exists"""
        return cls._capabilities.get(capability, False)
    
    @classmethod
    def suggest_alternatives(cls, requested: str) -> List[str]:
        """Suggest real alternatives to hallucinated capabilities"""
        # Simple string matching for suggestions
        alternatives = []
        for cap in cls._capabilities.keys():
            if any(word in cap for word in requested.split('_')):
                alternatives.append(cap)
        return alternatives[:3]  # Top 3 suggestions
    
    @classmethod
    def register_capability(cls, capability: str):
        """Register a new capability"""
        cls._capabilities[capability] = True
        logger.info(f"Registered new capability: {capability}")

class ReferenceValidator:
    """Validate all references before execution"""
    
    @staticmethod
    def validate_function_exists(func_name: str, module: Any) -> bool:
        """Ensure function exists before calling"""
        try:
            return hasattr(module, func_name) and callable(getattr(module, func_name))
        except Exception as e:
            logger.error(f"Error validating function {func_name}: {e}")
            return False
    
    @staticmethod
    def validate_variable_exists(var_name: str, scope: Dict) -> bool:
        """Ensure variable exists before accessing"""
        return var_name in scope

class CircuitBreaker:
    """Prevent cascade failures"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time: Optional[float] = None
        self.state: Literal['closed', 'open', 'half-open'] = 'closed'
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        import time
        
        if self.state == 'open':
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
                logger.info("Circuit breaker entering half-open state")
            else:
                raise Exception("Circuit breaker is open - too many failures")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info("Circuit breaker closed - system recovered")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            raise

# ============================================================================
# FAIL-SAFE CONFIGURATION
# ============================================================================

class FailSafeConfig:
    """Configuration with safe defaults"""
    
    # Confidence thresholds
    DEFAULT_CONFIDENCE_THRESHOLD = 0.7
    GREEN_THRESHOLD = 0.95
    YELLOW_THRESHOLD = 0.70
    
    # Retry settings
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    
    # Timeout settings
    DEFAULT_TIMEOUT = 60
    GATE_EVALUATION_TIMEOUT = 5
    
    # Cost settings
    DEFAULT_TOKEN_BUDGET = 10000
    COST_WARNING_THRESHOLD = 0.8
    
    # Quality settings
    MIN_QUALITY_SCORE = 0.6
    TARGET_QUALITY_SCORE = 0.9
    
    @classmethod
    def get_config(cls, key: str, default: Any = None) -> Any:
        """Get config with safe default"""
        return getattr(cls, key, default)

# ============================================================================
# BASE CLASSES
# ============================================================================

class SensorAgent(ABC):
    """
    Base class for sensor agents that monitor and generate rules
    
    Sensor agents are the "eyes and ears" of the system:
    - Monitor specific aspects (quality, cost, compliance, etc.)
    - Generate rules based on observations
    - Create decision gates dynamically
    """
    
    def __init__(self, sensor_id: str, sensor_type: str):
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.observations: List[ObservationModel] = []
        self.rules: List[RuleModel] = []
        self.circuit_breaker = CircuitBreaker()
        logger.info(f"Initialized {sensor_type} sensor: {sensor_id}")
    
    @abstractmethod
    def monitor(self, context: Dict[str, Any]) -> List[ObservationModel]:
        """
        Monitor the system and return observations
        
        Args:
            context: Current system context (task, user, environment)
            
        Returns:
            List of observations with metrics and status
        """
        pass
    
    @abstractmethod
    def generate_rules(self, observations: List[ObservationModel]) -> List[RuleModel]:
        """
        Generate rules based on observations
        
        Args:
            observations: List of observations from monitoring
            
        Returns:
            List of rules to apply
        """
        pass
    
    @abstractmethod
    def create_gates(self, rules: List[RuleModel], context: Dict[str, Any]) -> List[GateSpecModel]:
        """
        Create decision gates based on rules
        
        Args:
            rules: List of rules to enforce
            context: Current system context
            
        Returns:
            List of gate specifications
        """
        pass
    
    def safe_monitor(self, context: Dict[str, Any]) -> List[ObservationModel]:
        """Monitor with circuit breaker protection"""
        try:
            return self.circuit_breaker.call(self.monitor, context)
        except Exception as e:
            logger.error(f"Sensor {self.sensor_id} monitoring failed: {e}")
            return []
    
    def get_status(self) -> Dict[str, Any]:
        """Get sensor status"""
        return {
            'sensor_id': self.sensor_id,
            'sensor_type': self.sensor_type,
            'observations_count': len(self.observations),
            'rules_count': len(self.rules),
            'circuit_breaker_state': self.circuit_breaker.state,
            'last_observation': self.observations[-1].dict() if self.observations else None
        }

@dataclass
class GateTemplate:
    """Template for generating gates"""
    gate_type: GateTypeEnum
    question_template: str
    options_generator: Callable[[Dict], List[str]]
    confidence_calculator: Callable[[Dict], float]
    reasoning_generator: Callable[[Dict], str]
    token_cost_estimator: Callable[[Dict], int] = lambda ctx: 100
    revenue_impact_estimator: Callable[[Dict], float] = lambda ctx: 0.0

# ============================================================================
# CONCRETE SENSOR IMPLEMENTATIONS
# ============================================================================

class QualitySensorAgent(SensorAgent):
    """
    Monitors quality metrics and generates quality gates
    
    Monitors:
    - Output quality scores
    - User feedback
    - Error rates
    - Consistency metrics
    """
    
    def __init__(self, sensor_id: str = "quality_sensor"):
        super().__init__(sensor_id, "quality")
        self.quality_threshold = FailSafeConfig.MIN_QUALITY_SCORE
        self.target_quality = FailSafeConfig.TARGET_QUALITY_SCORE
    
    def monitor(self, context: Dict[str, Any]) -> List[ObservationModel]:
        """Monitor quality metrics"""
        observations = []
        
        # Check if task has quality requirements
        task_type = context.get('task_type', 'unknown')
        
        # Estimate quality based on task complexity
        complexity = context.get('complexity', 'medium')
        quality_score = {
            'simple': 0.9,
            'medium': 0.75,
            'complex': 0.6
        }.get(complexity, 0.7)
        
        # Create observation
        status = 'normal' if quality_score >= self.quality_threshold else 'warning'
        if quality_score < 0.5:
            status = 'critical'
        
        obs = ObservationModel(
            sensor_id=self.sensor_id,
            metric_name='quality_score',
            metric_value=quality_score,
            threshold=self.quality_threshold,
            status=status,
            metadata={'task_type': task_type, 'complexity': complexity}
        )
        observations.append(obs)
        self.observations.append(obs)
        
        return observations
    
    def generate_rules(self, observations: List[ObservationModel]) -> List[RuleModel]:
        """Generate quality rules"""
        rules = []
        
        for obs in observations:
            if obs.status == 'critical':
                # Critical quality - require human review
                rule = RuleModel(
                    rule_id=f"quality_critical_{obs.timestamp.timestamp()}",
                    rule_type="quality_check",
                    condition=f"quality_score < {self.quality_threshold}",
                    action="require_human_review",
                    priority=10
                )
                rules.append(rule)
            elif obs.status == 'warning':
                # Warning - require peer review
                rule = RuleModel(
                    rule_id=f"quality_warning_{obs.timestamp.timestamp()}",
                    rule_type="quality_check",
                    condition=f"quality_score < {self.target_quality}",
                    action="require_peer_review",
                    priority=7
                )
                rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def create_gates(self, rules: List[RuleModel], context: Dict[str, Any]) -> List[GateSpecModel]:
        """Create quality gates"""
        gates = []
        
        for rule in rules:
            if rule.rule_type == "quality_check":
                gate = GateSpecModel(
                    gate_id=f"quality_gate_{rule.rule_id}",
                    gate_type=GateTypeEnum.QUALITY,
                    question="Does the output meet quality standards?",
                    options=["Exceeds Standards", "Meets Standards", "Below Standards", "Requires Revision"],
                    confidence=0.8,
                    reasoning=f"Quality check required: {rule.condition}",
                    token_cost=50,
                    revenue_impact=0.0,
                    required=True
                )
                gates.append(gate)
        
        return gates

class CostSensorAgent(SensorAgent):
    """
    Monitors cost metrics and generates cost gates
    
    Monitors:
    - Token usage
    - API costs
    - External service costs
    - Opportunity costs
    """
    
    def __init__(self, sensor_id: str = "cost_sensor"):
        super().__init__(sensor_id, "cost")
        self.token_budget = FailSafeConfig.DEFAULT_TOKEN_BUDGET
        self.cost_warning_threshold = FailSafeConfig.COST_WARNING_THRESHOLD
    
    def monitor(self, context: Dict[str, Any]) -> List[ObservationModel]:
        """Monitor cost metrics"""
        observations = []
        
        # Estimate token cost based on task
        task_complexity = context.get('complexity', 'medium')
        estimated_tokens = {
            'simple': 500,
            'medium': 2000,
            'complex': 5000
        }.get(task_complexity, 2000)
        
        # Calculate budget usage
        budget_usage = estimated_tokens / self.token_budget
        
        status = 'normal'
        if budget_usage >= self.cost_warning_threshold:
            status = 'warning'
        if budget_usage >= 1.0:
            status = 'critical'
        
        obs = ObservationModel(
            sensor_id=self.sensor_id,
            metric_name='token_cost',
            metric_value=estimated_tokens,
            threshold=self.token_budget * self.cost_warning_threshold,
            status=status,
            metadata={'budget_usage': budget_usage, 'budget': self.token_budget}
        )
        observations.append(obs)
        self.observations.append(obs)
        
        return observations
    
    def generate_rules(self, observations: List[ObservationModel]) -> List[RuleModel]:
        """Generate cost rules"""
        rules = []
        
        for obs in observations:
            if obs.status == 'critical':
                rule = RuleModel(
                    rule_id=f"cost_critical_{obs.timestamp.timestamp()}",
                    rule_type="cost_check",
                    condition=f"token_cost >= {self.token_budget}",
                    action="require_budget_approval",
                    priority=10
                )
                rules.append(rule)
            elif obs.status == 'warning':
                rule = RuleModel(
                    rule_id=f"cost_warning_{obs.timestamp.timestamp()}",
                    rule_type="cost_check",
                    condition=f"token_cost >= {self.token_budget * self.cost_warning_threshold}",
                    action="notify_cost_warning",
                    priority=7
                )
                rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def create_gates(self, rules: List[RuleModel], context: Dict[str, Any]) -> List[GateSpecModel]:
        """Create cost gates"""
        gates = []
        
        for rule in rules:
            if rule.rule_type == "cost_check":
                gate = GateSpecModel(
                    gate_id=f"cost_gate_{rule.rule_id}",
                    gate_type=GateTypeEnum.COST,
                    question="Is the cost justified for this task?",
                    options=["Proceed - Cost Justified", "Review - High Cost", "Reject - Too Expensive"],
                    confidence=0.85,
                    reasoning=f"Cost check required: {rule.condition}",
                    token_cost=25,
                    revenue_impact=0.0,
                    required=True
                )
                gates.append(gate)
        
        return gates

class ComplianceSensorAgent(SensorAgent):
    """
    Monitors compliance requirements and generates compliance gates
    
    Monitors:
    - Regulatory requirements
    - Industry standards
    - Legal constraints
    - Data privacy rules
    """
    
    def __init__(self, sensor_id: str = "compliance_sensor"):
        super().__init__(sensor_id, "compliance")
        self.compliance_requirements = []
    
    def monitor(self, context: Dict[str, Any]) -> List[ObservationModel]:
        """Monitor compliance metrics"""
        observations = []
        
        # Check if task involves sensitive data
        has_sensitive_data = context.get('has_sensitive_data', False)
        industry = context.get('industry', 'general')
        
        # Determine compliance level needed
        compliance_level = 'low'
        if has_sensitive_data:
            compliance_level = 'high'
        elif industry in ['healthcare', 'finance', 'legal']:
            compliance_level = 'high'
        elif industry in ['education', 'government']:
            compliance_level = 'medium'
        
        status = 'normal' if compliance_level == 'low' else 'warning'
        if compliance_level == 'high':
            status = 'critical'
        
        obs = ObservationModel(
            sensor_id=self.sensor_id,
            metric_name='compliance_level',
            metric_value={'low': 0.3, 'medium': 0.6, 'high': 0.9}[compliance_level],
            threshold=0.5,
            status=status,
            metadata={'industry': industry, 'has_sensitive_data': has_sensitive_data}
        )
        observations.append(obs)
        self.observations.append(obs)
        
        return observations
    
    def generate_rules(self, observations: List[ObservationModel]) -> List[RuleModel]:
        """Generate compliance rules"""
        rules = []
        
        for obs in observations:
            if obs.status == 'critical':
                rule = RuleModel(
                    rule_id=f"compliance_critical_{obs.timestamp.timestamp()}",
                    rule_type="compliance_check",
                    condition="high_compliance_required",
                    action="require_legal_review",
                    priority=10
                )
                rules.append(rule)
            elif obs.status == 'warning':
                rule = RuleModel(
                    rule_id=f"compliance_warning_{obs.timestamp.timestamp()}",
                    rule_type="compliance_check",
                    condition="medium_compliance_required",
                    action="require_compliance_check",
                    priority=8
                )
                rules.append(rule)
        
        self.rules.extend(rules)
        return rules
    
    def create_gates(self, rules: List[RuleModel], context: Dict[str, Any]) -> List[GateSpecModel]:
        """Create compliance gates"""
        gates = []
        
        for rule in rules:
            if rule.rule_type == "compliance_check":
                gate = GateSpecModel(
                    gate_id=f"compliance_gate_{rule.rule_id}",
                    gate_type=GateTypeEnum.COMPLIANCE,
                    question="Does this meet compliance requirements?",
                    options=["Fully Compliant", "Needs Minor Adjustments", "Requires Legal Review", "Non-Compliant"],
                    confidence=0.75,
                    reasoning=f"Compliance check required: {rule.condition}",
                    token_cost=75,
                    revenue_impact=0.0,
                    required=True
                )
                gates.append(gate)
        
        return gates

# ============================================================================
# GENERATIVE GATE SYSTEM
# ============================================================================

class GenerativeGateSystem:
    """
    Main system for generating decision gates dynamically
    
    This is the "brain" that:
    - Coordinates sensor agents
    - Analyzes tasks
    - Generates appropriate gates
    - Learns from outcomes
    """
    
    def __init__(self):
        self.sensors: List[SensorAgent] = []
        self.gate_templates: List[GateTemplate] = []
        self.historical_patterns: List[Dict] = []
        self.capability_registry = CapabilityRegistry()
        logger.info("Initialized Generative Gate System")
    
    def register_sensor(self, sensor: SensorAgent):
        """Register a sensor agent"""
        self.sensors.append(sensor)
        logger.info(f"Registered sensor: {sensor.sensor_id} ({sensor.sensor_type})")
    
    def analyze_task(self, task: Dict[str, Any], business_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze task and determine what gates are needed
        
        Args:
            task: Task details
            business_context: Business requirements and constraints
            
        Returns:
            Analysis with recommended gates
        """
        analysis = {
            'task_id': task.get('id', 'unknown'),
            'task_type': task.get('type', 'unknown'),
            'complexity': self._assess_complexity(task),
            'risk_level': self._assess_risk(task, business_context),
            'required_capabilities': self._identify_capabilities(task),
            'estimated_cost': self._estimate_cost(task),
            'estimated_duration': self._estimate_duration(task),
            'recommended_gates': []
        }
        
        # Verify all required capabilities exist
        missing_capabilities = []
        for cap in analysis['required_capabilities']:
            if not self.capability_registry.verify_capability(cap):
                missing_capabilities.append(cap)
                alternatives = self.capability_registry.suggest_alternatives(cap)
                logger.warning(f"Missing capability: {cap}. Alternatives: {alternatives}")
        
        if missing_capabilities:
            analysis['missing_capabilities'] = missing_capabilities
            analysis['risk_level'] = 'high'
        
        return analysis
    
    def generate_gates(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> List[GateSpecModel]:
        """
        Generate decision gates based on analysis
        
        Args:
            analysis: Task analysis
            context: Full context including business requirements
            
        Returns:
            List of gate specifications
        """
        all_gates = []
        
        # Run all sensors
        for sensor in self.sensors:
            try:
                # Monitor
                observations = sensor.safe_monitor(context)
                
                # Generate rules
                rules = sensor.generate_rules(observations)
                
                # Create gates
                gates = sensor.create_gates(rules, context)
                all_gates.extend(gates)
                
                logger.info(f"Sensor {sensor.sensor_id} generated {len(gates)} gates")
            except Exception as e:
                logger.error(f"Error in sensor {sensor.sensor_id}: {e}")
                continue
        
        # Sort gates by priority (derived from sensor rules)
        all_gates.sort(key=lambda g: g.required, reverse=True)
        
        return all_gates
    
    def learn_from_outcome(self, task_id: str, gates: List[GateSpecModel], 
                          outcome: Dict[str, Any]):
        """
        Learn from task outcomes to improve future gate generation
        
        Args:
            task_id: Task identifier
            gates: Gates that were used
            outcome: Task outcome (success, failure, metrics)
        """
        pattern = {
            'task_id': task_id,
            'gates_used': [g.dict() for g in gates],
            'outcome': outcome,
            'timestamp': datetime.now().isoformat()
        }
        self.historical_patterns.append(pattern)
        logger.info(f"Learned from task {task_id}: {outcome.get('status', 'unknown')}")
    
    def _assess_complexity(self, task: Dict[str, Any]) -> str:
        """Assess task complexity"""
        # Simple heuristic based on task description length and keywords
        description = task.get('description', '')
        
        if len(description) < 100:
            return 'simple'
        elif len(description) < 500:
            return 'medium'
        else:
            return 'complex'
    
    def _assess_risk(self, task: Dict[str, Any], business_context: Dict[str, Any]) -> str:
        """Assess task risk level"""
        risk_factors = 0
        
        # Check for sensitive data
        if task.get('has_sensitive_data', False):
            risk_factors += 2
        
        # Check for high-value task
        if task.get('value', 0) > 1000:
            risk_factors += 1
        
        # Check for external dependencies
        if task.get('external_dependencies', []):
            risk_factors += 1
        
        if risk_factors >= 3:
            return 'high'
        elif risk_factors >= 1:
            return 'medium'
        else:
            return 'low'
    
    def _identify_capabilities(self, task: Dict[str, Any]) -> List[str]:
        """Identify required capabilities for task"""
        capabilities = []
        
        task_type = task.get('type', '').lower()
        
        if 'content' in task_type or 'write' in task_type:
            capabilities.append('generate_content')
        if 'analyze' in task_type:
            capabilities.append('analyze_data')
        if 'code' in task_type or 'program' in task_type:
            capabilities.append('generate_code')
        if 'translate' in task_type:
            capabilities.append('translate_text')
        
        return capabilities
    
    def _estimate_cost(self, task: Dict[str, Any]) -> int:
        """Estimate token cost for task"""
        complexity = self._assess_complexity(task)
        base_costs = {
            'simple': 500,
            'medium': 2000,
            'complex': 5000
        }
        return base_costs.get(complexity, 2000)
    
    def _estimate_duration(self, task: Dict[str, Any]) -> int:
        """Estimate duration in seconds"""
        complexity = self._assess_complexity(task)
        base_durations = {
            'simple': 60,
            'medium': 300,
            'complex': 900
        }
        return base_durations.get(complexity, 300)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        return {
            'sensors': [sensor.get_status() for sensor in self.sensors],
            'total_sensors': len(self.sensors),
            'historical_patterns': len(self.historical_patterns),
            'capabilities': list(self.capability_registry._capabilities.keys())
        }

# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_default_generative_system() -> GenerativeGateSystem:
    """Create a generative gate system with default sensors"""
    system = GenerativeGateSystem()
    
    # Register default sensors
    system.register_sensor(QualitySensorAgent())
    system.register_sensor(CostSensorAgent())
    system.register_sensor(ComplianceSensorAgent())
    
    logger.info("Created default generative gate system with 3 sensors")
    return system

# Global instance
_generative_system = None

def get_generative_gate_system() -> GenerativeGateSystem:
    """Get or create the global generative gate system"""
    global _generative_system
    if _generative_system is None:
        _generative_system = create_default_generative_system()
    return _generative_system