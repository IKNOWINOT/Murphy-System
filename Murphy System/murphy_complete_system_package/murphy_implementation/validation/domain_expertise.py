"""
Domain Expertise Scoring System
Scores domain expertise to improve UA (Uncertainty in Assumptions) calculations.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import statistics


class ExpertiseLevel(str, Enum):
    """Levels of domain expertise."""
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    MASTER = "master"


class DomainCategory(str, Enum):
    """Categories of domains."""
    TECHNOLOGY = "technology"
    BUSINESS = "business"
    SCIENCE = "science"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    LEGAL = "legal"
    ENGINEERING = "engineering"
    EDUCATION = "education"
    GENERAL = "general"


class AssumptionType(str, Enum):
    """Types of assumptions."""
    TECHNICAL = "technical"
    BUSINESS_LOGIC = "business_logic"
    USER_BEHAVIOR = "user_behavior"
    DATA_QUALITY = "data_quality"
    SYSTEM_BEHAVIOR = "system_behavior"
    REGULATORY = "regulatory"


class DomainExpert(BaseModel):
    """Represents a domain expert."""
    id: str
    name: str
    expertise_level: ExpertiseLevel
    domains: List[str]
    domain_categories: List[DomainCategory]
    years_experience: int
    certifications: List[str] = Field(default_factory=list)
    verified: bool = False
    expertise_score: float = Field(ge=0.0, le=1.0, default=0.5)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssumptionValidation(BaseModel):
    """Validation of an assumption by an expert."""
    assumption_id: str
    expert_id: str
    is_valid: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DomainKnowledge(BaseModel):
    """Represents knowledge in a specific domain."""
    domain: str
    category: DomainCategory
    concepts: Set[str] = Field(default_factory=set)
    rules: List[str] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    common_pitfalls: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)


class ExpertiseScore(BaseModel):
    """Detailed expertise score breakdown."""
    overall_score: float = Field(ge=0.0, le=1.0)
    experience_score: float = Field(ge=0.0, le=1.0)
    certification_score: float = Field(ge=0.0, le=1.0)
    validation_history_score: float = Field(ge=0.0, le=1.0)
    domain_coverage_score: float = Field(ge=0.0, le=1.0)
    verification_status: bool
    components: Dict[str, float] = Field(default_factory=dict)


class DomainExpertRegistry:
    """
    Registry of domain experts.
    Manages expert profiles and their expertise areas.
    """
    
    def __init__(self):
        self.experts: Dict[str, DomainExpert] = {}
        self.domain_index: Dict[str, List[str]] = {}  # domain -> expert_ids
        self.category_index: Dict[DomainCategory, List[str]] = {}  # category -> expert_ids
    
    def register_expert(self, expert: DomainExpert) -> str:
        """Register a new expert."""
        self.experts[expert.id] = expert
        
        # Update domain index
        for domain in expert.domains:
            if domain not in self.domain_index:
                self.domain_index[domain] = []
            self.domain_index[domain].append(expert.id)
        
        # Update category index
        for category in expert.domain_categories:
            if category not in self.category_index:
                self.category_index[category] = []
            self.category_index[category].append(expert.id)
        
        return expert.id
    
    def get_expert(self, expert_id: str) -> Optional[DomainExpert]:
        """Get expert by ID."""
        return self.experts.get(expert_id)
    
    def find_experts_by_domain(self, domain: str) -> List[DomainExpert]:
        """Find experts for a specific domain."""
        expert_ids = self.domain_index.get(domain, [])
        return [self.experts[eid] for eid in expert_ids if eid in self.experts]
    
    def find_experts_by_category(self, category: DomainCategory) -> List[DomainExpert]:
        """Find experts for a domain category."""
        expert_ids = self.category_index.get(category, [])
        return [self.experts[eid] for eid in expert_ids if eid in self.experts]
    
    def get_top_experts(
        self,
        domain: Optional[str] = None,
        category: Optional[DomainCategory] = None,
        limit: int = 5
    ) -> List[DomainExpert]:
        """Get top experts by expertise score."""
        if domain:
            experts = self.find_experts_by_domain(domain)
        elif category:
            experts = self.find_experts_by_category(category)
        else:
            experts = list(self.experts.values())
        
        # Sort by expertise score
        sorted_experts = sorted(experts, key=lambda e: e.expertise_score, reverse=True)
        return sorted_experts[:limit]


class DomainKnowledgeBase:
    """
    Knowledge base for different domains.
    Stores domain-specific knowledge, rules, and best practices.
    """
    
    def __init__(self):
        self.knowledge: Dict[str, DomainKnowledge] = {}
    
    def add_domain_knowledge(self, knowledge: DomainKnowledge):
        """Add knowledge for a domain."""
        self.knowledge[knowledge.domain] = knowledge
    
    def get_domain_knowledge(self, domain: str) -> Optional[DomainKnowledge]:
        """Get knowledge for a domain."""
        return self.knowledge.get(domain)
    
    def check_assumption_against_knowledge(
        self,
        assumption: str,
        domain: str
    ) -> Dict[str, Any]:
        """
        Check an assumption against domain knowledge.
        
        Returns:
            Dictionary with validation result and confidence
        """
        knowledge = self.get_domain_knowledge(domain)
        if not knowledge:
            return {
                "is_valid": None,
                "confidence": 0.0,
                "reason": "No knowledge available for domain"
            }
        
        # Check against common pitfalls
        for pitfall in knowledge.common_pitfalls:
            if pitfall.lower() in assumption.lower():
                return {
                    "is_valid": False,
                    "confidence": 0.8,
                    "reason": f"Matches known pitfall: {pitfall}"
                }
        
        # Check against best practices
        for practice in knowledge.best_practices:
            if practice.lower() in assumption.lower():
                return {
                    "is_valid": True,
                    "confidence": 0.8,
                    "reason": f"Aligns with best practice: {practice}"
                }
        
        # Default: uncertain
        return {
            "is_valid": None,
            "confidence": 0.5,
            "reason": "No specific knowledge match found"
        }


class ExpertiseScorer:
    """
    Calculates expertise scores for domain experts.
    """
    
    def __init__(self):
        self.validation_history: Dict[str, List[AssumptionValidation]] = {}
    
    def calculate_expertise_score(self, expert: DomainExpert) -> ExpertiseScore:
        """
        Calculate comprehensive expertise score for an expert.
        
        Args:
            expert: The domain expert to score
            
        Returns:
            ExpertiseScore with detailed breakdown
        """
        # Experience score (0-1 based on years)
        experience_score = min(expert.years_experience / 20.0, 1.0)
        
        # Certification score
        certification_score = min(len(expert.certifications) / 5.0, 1.0)
        
        # Validation history score
        validation_history_score = self._calculate_validation_history_score(expert.id)
        
        # Domain coverage score
        domain_coverage_score = min(len(expert.domains) / 10.0, 1.0)
        
        # Verification bonus
        verification_bonus = 0.1 if expert.verified else 0.0
        
        # Weighted overall score
        overall_score = (
            0.3 * experience_score +
            0.2 * certification_score +
            0.3 * validation_history_score +
            0.2 * domain_coverage_score +
            verification_bonus
        )
        
        overall_score = min(overall_score, 1.0)
        
        return ExpertiseScore(
            overall_score=overall_score,
            experience_score=experience_score,
            certification_score=certification_score,
            validation_history_score=validation_history_score,
            domain_coverage_score=domain_coverage_score,
            verification_status=expert.verified,
            components={
                "experience": experience_score,
                "certifications": certification_score,
                "validation_history": validation_history_score,
                "domain_coverage": domain_coverage_score,
                "verification_bonus": verification_bonus
            }
        )
    
    def _calculate_validation_history_score(self, expert_id: str) -> float:
        """Calculate score based on validation history."""
        validations = self.validation_history.get(expert_id, [])
        
        if not validations:
            return 0.5  # Neutral score for no history
        
        # Calculate accuracy of past validations
        # In production, this would compare against actual outcomes
        avg_confidence = statistics.mean([v.confidence for v in validations])
        
        # Factor in number of validations (more = better)
        volume_factor = min(len(validations) / 50.0, 1.0)
        
        return 0.7 * avg_confidence + 0.3 * volume_factor
    
    def record_validation(self, validation: AssumptionValidation):
        """Record an assumption validation by an expert."""
        if validation.expert_id not in self.validation_history:
            self.validation_history[validation.expert_id] = []
        self.validation_history[validation.expert_id].append(validation)
    
    def get_expert_validation_history(
        self,
        expert_id: str,
        limit: int = 100
    ) -> List[AssumptionValidation]:
        """Get validation history for an expert."""
        validations = self.validation_history.get(expert_id, [])
        return validations[-limit:]


class UACalculator:
    """
    Calculates UA (Uncertainty in Assumptions) using domain expertise.
    Integrates with Murphy's uncertainty framework.
    """
    
    def __init__(
        self,
        expert_registry: DomainExpertRegistry,
        knowledge_base: DomainKnowledgeBase,
        expertise_scorer: ExpertiseScorer
    ):
        self.expert_registry = expert_registry
        self.knowledge_base = knowledge_base
        self.expertise_scorer = expertise_scorer
    
    def calculate_ua(
        self,
        assumption: str,
        domain: str,
        assumption_type: AssumptionType
    ) -> float:
        """
        Calculate UA score for an assumption.
        
        Args:
            assumption: The assumption to evaluate
            domain: Domain of the assumption
            assumption_type: Type of assumption
            
        Returns:
            UA score (0.0 to 1.0, where 0 = certain, 1 = highly uncertain)
        """
        # Check against knowledge base
        kb_result = self.knowledge_base.check_assumption_against_knowledge(
            assumption,
            domain
        )
        
        # Get domain experts
        experts = self.expert_registry.find_experts_by_domain(domain)
        
        if not experts:
            # No experts available - high uncertainty
            return 0.8
        
        # Calculate average expert confidence
        expert_scores = []
        for expert in experts[:5]:  # Top 5 experts
            expertise_score = self.expertise_scorer.calculate_expertise_score(expert)
            expert_scores.append(expertise_score.overall_score)
        
        avg_expert_confidence = statistics.mean(expert_scores) if expert_scores else 0.5
        
        # Combine knowledge base and expert confidence
        kb_confidence = kb_result.get("confidence", 0.5)
        
        # If knowledge base says invalid, increase uncertainty
        if kb_result.get("is_valid") is False:
            kb_confidence = 1.0 - kb_confidence
        
        # Weighted combination
        combined_confidence = 0.6 * avg_expert_confidence + 0.4 * kb_confidence
        
        # UA is inverse of confidence
        ua_score = 1.0 - combined_confidence
        
        return ua_score
    
    def calculate_ua_with_context(
        self,
        assumption: str,
        domain: str,
        assumption_type: AssumptionType,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate UA with detailed breakdown and context.
        
        Args:
            assumption: The assumption to evaluate
            domain: Domain of the assumption
            assumption_type: Type of assumption
            context: Additional context
            
        Returns:
            Dictionary with UA score and detailed breakdown
        """
        # Check knowledge base
        kb_result = self.knowledge_base.check_assumption_against_knowledge(
            assumption,
            domain
        )
        
        # Get experts
        experts = self.expert_registry.find_experts_by_domain(domain)
        expert_details = []
        
        for expert in experts[:5]:
            expertise_score = self.expertise_scorer.calculate_expertise_score(expert)
            expert_details.append({
                "expert_id": expert.id,
                "name": expert.name,
                "expertise_level": expert.expertise_level,
                "expertise_score": expertise_score.overall_score,
                "years_experience": expert.years_experience
            })
        
        # Calculate UA
        ua_score = self.calculate_ua(assumption, domain, assumption_type)
        
        return {
            "ua_score": ua_score,
            "assumption": assumption,
            "domain": domain,
            "assumption_type": assumption_type,
            "knowledge_base_check": kb_result,
            "experts_consulted": len(expert_details),
            "expert_details": expert_details,
            "confidence_breakdown": {
                "knowledge_base_confidence": kb_result.get("confidence", 0.5),
                "expert_confidence": 1.0 - ua_score
            }
        }


class DomainExpertiseSystem:
    """
    Complete domain expertise scoring system.
    Provides unified interface for expertise management and UA calculation.
    """
    
    def __init__(self):
        self.expert_registry = DomainExpertRegistry()
        self.knowledge_base = DomainKnowledgeBase()
        self.expertise_scorer = ExpertiseScorer()
        self.ua_calculator = UACalculator(
            self.expert_registry,
            self.knowledge_base,
            self.expertise_scorer
        )
        
        # Initialize with some default domain knowledge
        self._initialize_default_knowledge()
    
    def _initialize_default_knowledge(self):
        """Initialize with default domain knowledge."""
        # Technology domain
        tech_knowledge = DomainKnowledge(
            domain="software_development",
            category=DomainCategory.TECHNOLOGY,
            concepts={"api", "database", "authentication", "caching", "scalability"},
            best_practices=[
                "Use version control",
                "Write unit tests",
                "Follow SOLID principles",
                "Implement proper error handling",
                "Use dependency injection"
            ],
            common_pitfalls=[
                "Premature optimization",
                "Not handling edge cases",
                "Ignoring security",
                "Tight coupling",
                "No input validation"
            ],
            confidence_score=0.9
        )
        self.knowledge_base.add_domain_knowledge(tech_knowledge)
    
    def register_expert(
        self,
        name: str,
        expertise_level: ExpertiseLevel,
        domains: List[str],
        domain_categories: List[DomainCategory],
        years_experience: int,
        certifications: Optional[List[str]] = None,
        verified: bool = False
    ) -> str:
        """Register a new domain expert."""
        expert = DomainExpert(
            id=f"expert_{datetime.utcnow().timestamp()}",
            name=name,
            expertise_level=expertise_level,
            domains=domains,
            domain_categories=domain_categories,
            years_experience=years_experience,
            certifications=certifications or [],
            verified=verified
        )
        
        # Calculate initial expertise score
        expertise_score = self.expertise_scorer.calculate_expertise_score(expert)
        expert.expertise_score = expertise_score.overall_score
        
        return self.expert_registry.register_expert(expert)
    
    def add_domain_knowledge(
        self,
        domain: str,
        category: DomainCategory,
        best_practices: List[str],
        common_pitfalls: List[str]
    ):
        """Add knowledge for a domain."""
        knowledge = DomainKnowledge(
            domain=domain,
            category=category,
            best_practices=best_practices,
            common_pitfalls=common_pitfalls,
            confidence_score=0.8
        )
        self.knowledge_base.add_domain_knowledge(knowledge)
    
    def calculate_ua(
        self,
        assumption: str,
        domain: str,
        assumption_type: AssumptionType
    ) -> float:
        """Calculate UA score for an assumption."""
        return self.ua_calculator.calculate_ua(assumption, domain, assumption_type)
    
    def calculate_ua_detailed(
        self,
        assumption: str,
        domain: str,
        assumption_type: AssumptionType,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate UA with detailed breakdown."""
        return self.ua_calculator.calculate_ua_with_context(
            assumption,
            domain,
            assumption_type,
            context or {}
        )
    
    def validate_assumption(
        self,
        assumption_id: str,
        assumption: str,
        domain: str,
        expert_id: str,
        is_valid: bool,
        confidence: float,
        reasoning: str
    ):
        """Record an assumption validation by an expert."""
        validation = AssumptionValidation(
            assumption_id=assumption_id,
            expert_id=expert_id,
            is_valid=is_valid,
            confidence=confidence,
            reasoning=reasoning
        )
        self.expertise_scorer.record_validation(validation)
    
    def get_top_experts(
        self,
        domain: Optional[str] = None,
        category: Optional[DomainCategory] = None
    ) -> List[DomainExpert]:
        """Get top experts for a domain or category."""
        return self.expert_registry.get_top_experts(domain, category)