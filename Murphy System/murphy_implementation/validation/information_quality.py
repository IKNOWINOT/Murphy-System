"""
Information Quality Metrics System
Measures information quality to improve UI (Uncertainty in Information) calculations.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field
import re
from collections import Counter


class InformationSource(str, Enum):
    """Types of information sources."""
    OFFICIAL_DOCUMENTATION = "official_documentation"
    PEER_REVIEWED = "peer_reviewed"
    EXPERT_OPINION = "expert_opinion"
    USER_GENERATED = "user_generated"
    NEWS_MEDIA = "news_media"
    SOCIAL_MEDIA = "social_media"
    INTERNAL_DATA = "internal_data"
    THIRD_PARTY_API = "third_party_api"
    UNKNOWN = "unknown"


class InformationQualityDimension(str, Enum):
    """Dimensions of information quality."""
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    RELEVANCE = "relevance"
    CREDIBILITY = "credibility"
    OBJECTIVITY = "objectivity"
    VERIFIABILITY = "verifiability"


class InformationMetrics(BaseModel):
    """Metrics for a piece of information."""
    accuracy: float = Field(ge=0.0, le=1.0, default=0.5)
    completeness: float = Field(ge=0.0, le=1.0, default=0.5)
    consistency: float = Field(ge=0.0, le=1.0, default=0.5)
    timeliness: float = Field(ge=0.0, le=1.0, default=0.5)
    relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    credibility: float = Field(ge=0.0, le=1.0, default=0.5)
    objectivity: float = Field(ge=0.0, le=1.0, default=0.5)
    verifiability: float = Field(ge=0.0, le=1.0, default=0.5)
    overall_quality: float = Field(ge=0.0, le=1.0, default=0.5)
    
    def calculate_overall(self) -> float:
        """Calculate overall quality score."""
        metrics = [
            self.accuracy,
            self.completeness,
            self.consistency,
            self.timeliness,
            self.relevance,
            self.credibility,
            self.objectivity,
            self.verifiability
        ]
        return sum(metrics) / len(metrics)


class InformationItem(BaseModel):
    """Represents a piece of information."""
    id: str
    content: str
    source: InformationSource
    source_url: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    retrieved_date: datetime = Field(default_factory=datetime.utcnow)
    metrics: InformationMetrics = Field(default_factory=InformationMetrics)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def age_in_days(self) -> float:
        """Calculate age of information in days."""
        if not self.published_date:
            return 0.0
        return (datetime.utcnow() - self.published_date).days


class InformationQualityAssessment(BaseModel):
    """Assessment result for information quality."""
    information_id: str
    metrics: InformationMetrics
    quality_score: float = Field(ge=0.0, le=1.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    assessed_at: datetime = Field(default_factory=datetime.utcnow)


class SourceCredibilityScorer:
    """
    Scores the credibility of information sources.
    """
    
    # Source credibility weights (0.0 to 1.0)
    SOURCE_CREDIBILITY = {
        InformationSource.OFFICIAL_DOCUMENTATION: 0.95,
        InformationSource.PEER_REVIEWED: 0.90,
        InformationSource.EXPERT_OPINION: 0.80,
        InformationSource.INTERNAL_DATA: 0.75,
        InformationSource.THIRD_PARTY_API: 0.70,
        InformationSource.NEWS_MEDIA: 0.60,
        InformationSource.USER_GENERATED: 0.40,
        InformationSource.SOCIAL_MEDIA: 0.30,
        InformationSource.UNKNOWN: 0.20
    }
    
    def score_source(self, source: InformationSource) -> float:
        """Get credibility score for a source type."""
        return self.SOURCE_CREDIBILITY.get(source, 0.5)
    
    def score_source_with_context(
        self,
        source: InformationSource,
        context: Dict[str, Any]
    ) -> float:
        """
        Score source credibility with additional context.
        
        Context can include:
        - author_verified: bool
        - citations_count: int
        - peer_reviews: int
        - domain_authority: float
        """
        base_score = self.score_source(source)
        
        # Adjust based on context
        if context.get("author_verified"):
            base_score += 0.1
        
        citations = context.get("citations_count", 0)
        if citations > 10:
            base_score += 0.05
        
        peer_reviews = context.get("peer_reviews", 0)
        if peer_reviews > 0:
            base_score += 0.05
        
        domain_authority = context.get("domain_authority", 0.5)
        base_score = 0.7 * base_score + 0.3 * domain_authority
        
        return min(base_score, 1.0)


class ContentAnalyzer:
    """
    Analyzes content to assess quality metrics.
    """
    
    def analyze_completeness(self, content: str, required_elements: Optional[List[str]] = None) -> float:
        """
        Analyze completeness of content.
        
        Args:
            content: The content to analyze
            required_elements: Optional list of required elements
            
        Returns:
            Completeness score (0.0 to 1.0)
        """
        if not content:
            return 0.0
        
        # Basic completeness checks
        has_sufficient_length = len(content) > 100
        has_structure = any(marker in content for marker in ['\n\n', '. ', '- ', '* '])
        
        score = 0.5
        
        if has_sufficient_length:
            score += 0.25
        
        if has_structure:
            score += 0.25
        
        # Check for required elements if provided
        if required_elements:
            found_elements = sum(1 for elem in required_elements if elem.lower() in content.lower())
            element_score = found_elements / len(required_elements)
            score = 0.5 * score + 0.5 * element_score
        
        return min(score, 1.0)
    
    def analyze_consistency(self, content: str) -> float:
        """
        Analyze internal consistency of content.
        
        Checks for contradictions, consistent terminology, etc.
        """
        if not content:
            return 0.0
        
        # Simple consistency checks
        sentences = content.split('. ')
        
        # Check for contradictory words
        contradictions = ['but', 'however', 'although', 'despite', 'nevertheless']
        contradiction_count = sum(1 for sent in sentences if any(word in sent.lower() for word in contradictions))
        
        # High contradiction ratio suggests inconsistency
        if len(sentences) > 0:
            contradiction_ratio = contradiction_count / len(sentences)
            consistency_score = 1.0 - min(contradiction_ratio * 2, 1.0)
        else:
            consistency_score = 0.5
        
        return consistency_score
    
    def analyze_objectivity(self, content: str) -> float:
        """
        Analyze objectivity of content.
        
        Checks for subjective language, emotional words, etc.
        """
        if not content:
            return 0.0
        
        # Subjective indicators
        subjective_words = [
            'i think', 'i believe', 'in my opinion', 'probably', 'maybe',
            'seems', 'appears', 'might', 'could', 'should'
        ]
        
        # Emotional words
        emotional_words = [
            'amazing', 'terrible', 'awful', 'fantastic', 'horrible',
            'love', 'hate', 'best', 'worst'
        ]
        
        content_lower = content.lower()
        
        subjective_count = sum(1 for word in subjective_words if word in content_lower)
        emotional_count = sum(1 for word in emotional_words if word in content_lower)
        
        total_indicators = subjective_count + emotional_count
        
        # Calculate objectivity (inverse of subjectivity)
        word_count = len(content.split())
        if word_count > 0:
            subjectivity_ratio = total_indicators / (word_count / 100)  # per 100 words
            objectivity_score = 1.0 - min(subjectivity_ratio, 1.0)
        else:
            objectivity_score = 0.5
        
        return objectivity_score
    
    def analyze_verifiability(self, content: str) -> float:
        """
        Analyze verifiability of content.
        
        Checks for citations, references, specific facts, etc.
        """
        if not content:
            return 0.0
        
        score = 0.5
        
        # Check for URLs (citations)
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, content)
        if urls:
            score += 0.2
        
        # Check for specific numbers/dates (facts)
        number_pattern = r'\b\d+\b'
        numbers = re.findall(number_pattern, content)
        if len(numbers) > 3:
            score += 0.15
        
        # Check for references section
        if 'reference' in content.lower() or 'citation' in content.lower():
            score += 0.15
        
        return min(score, 1.0)


class TimelinessAnalyzer:
    """
    Analyzes timeliness of information.
    """
    
    def analyze_timeliness(
        self,
        published_date: Optional[datetime],
        context: Dict[str, Any]
    ) -> float:
        """
        Analyze timeliness of information.
        
        Args:
            published_date: When the information was published
            context: Additional context (e.g., topic_volatility)
            
        Returns:
            Timeliness score (0.0 to 1.0)
        """
        if not published_date:
            return 0.5  # Unknown date = neutral score
        
        age_days = (datetime.utcnow() - published_date).days
        
        # Get topic volatility (how quickly information becomes outdated)
        # High volatility = information becomes outdated quickly
        topic_volatility = context.get("topic_volatility", 0.5)
        
        # Calculate decay based on volatility
        if topic_volatility > 0.8:  # High volatility (e.g., breaking news)
            half_life_days = 7
        elif topic_volatility > 0.5:  # Medium volatility (e.g., technology)
            half_life_days = 90
        else:  # Low volatility (e.g., historical facts)
            half_life_days = 365
        
        # Exponential decay
        timeliness = 2 ** (-age_days / half_life_days)
        
        return min(timeliness, 1.0)


class RelevanceAnalyzer:
    """
    Analyzes relevance of information to a query or context.
    """
    
    def analyze_relevance(
        self,
        content: str,
        query: str,
        context: Dict[str, Any]
    ) -> float:
        """
        Analyze relevance of content to a query.
        
        Args:
            content: The content to analyze
            query: The query or topic
            context: Additional context
            
        Returns:
            Relevance score (0.0 to 1.0)
        """
        if not content or not query:
            return 0.0
        
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Extract keywords from query
        query_words = set(query_lower.split())
        
        # Count keyword matches
        matches = sum(1 for word in query_words if word in content_lower)
        
        if len(query_words) > 0:
            keyword_score = matches / len(query_words)
        else:
            keyword_score = 0.0
        
        # Check for exact phrase match
        phrase_match = query_lower in content_lower
        
        # Calculate relevance
        relevance = 0.7 * keyword_score
        if phrase_match:
            relevance += 0.3
        
        return min(relevance, 1.0)


class InformationQualityAnalyzer:
    """
    Main analyzer that coordinates all quality assessments.
    """
    
    def __init__(self):
        self.credibility_scorer = SourceCredibilityScorer()
        self.content_analyzer = ContentAnalyzer()
        self.timeliness_analyzer = TimelinessAnalyzer()
        self.relevance_analyzer = RelevanceAnalyzer()
    
    def assess_information(
        self,
        information: InformationItem,
        context: Optional[Dict[str, Any]] = None
    ) -> InformationQualityAssessment:
        """
        Perform comprehensive quality assessment.
        
        Args:
            information: The information to assess
            context: Additional context for assessment
            
        Returns:
            InformationQualityAssessment with detailed metrics
        """
        context = context or {}
        
        # Assess each dimension
        metrics = InformationMetrics()
        
        # Credibility (based on source)
        metrics.credibility = self.credibility_scorer.score_source_with_context(
            information.source,
            context
        )
        
        # Content-based metrics
        metrics.completeness = self.content_analyzer.analyze_completeness(
            information.content,
            context.get("required_elements")
        )
        
        metrics.consistency = self.content_analyzer.analyze_consistency(
            information.content
        )
        
        metrics.objectivity = self.content_analyzer.analyze_objectivity(
            information.content
        )
        
        metrics.verifiability = self.content_analyzer.analyze_verifiability(
            information.content
        )
        
        # Timeliness
        metrics.timeliness = self.timeliness_analyzer.analyze_timeliness(
            information.published_date,
            context
        )
        
        # Relevance
        query = context.get("query", "")
        metrics.relevance = self.relevance_analyzer.analyze_relevance(
            information.content,
            query,
            context
        )
        
        # Accuracy (requires external validation, default to credibility)
        metrics.accuracy = metrics.credibility
        
        # Calculate overall quality
        metrics.overall_quality = metrics.calculate_overall()
        
        # Identify issues
        issues = self._identify_issues(metrics)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, issues)
        
        # Calculate uncertainty (inverse of quality)
        uncertainty_score = 1.0 - metrics.overall_quality
        
        return InformationQualityAssessment(
            information_id=information.id,
            metrics=metrics,
            quality_score=metrics.overall_quality,
            uncertainty_score=uncertainty_score,
            issues=issues,
            recommendations=recommendations
        )
    
    def _identify_issues(self, metrics: InformationMetrics) -> List[str]:
        """Identify quality issues based on metrics."""
        issues = []
        
        threshold = 0.6
        
        if metrics.accuracy < threshold:
            issues.append("Low accuracy score - verify information")
        
        if metrics.completeness < threshold:
            issues.append("Incomplete information - missing key elements")
        
        if metrics.consistency < threshold:
            issues.append("Internal inconsistencies detected")
        
        if metrics.timeliness < threshold:
            issues.append("Information may be outdated")
        
        if metrics.relevance < threshold:
            issues.append("Low relevance to query")
        
        if metrics.credibility < threshold:
            issues.append("Low source credibility")
        
        if metrics.objectivity < threshold:
            issues.append("Subjective or biased content")
        
        if metrics.verifiability < threshold:
            issues.append("Difficult to verify - lacks citations")
        
        return issues
    
    def _generate_recommendations(
        self,
        metrics: InformationMetrics,
        issues: List[str]
    ) -> List[str]:
        """Generate recommendations based on issues."""
        recommendations = []
        
        if metrics.credibility < 0.6:
            recommendations.append("Seek additional sources with higher credibility")
        
        if metrics.completeness < 0.6:
            recommendations.append("Gather additional information to fill gaps")
        
        if metrics.timeliness < 0.6:
            recommendations.append("Look for more recent information")
        
        if metrics.verifiability < 0.6:
            recommendations.append("Cross-reference with verifiable sources")
        
        if metrics.overall_quality < 0.5:
            recommendations.append("CRITICAL: Information quality is poor - use with caution")
        
        return recommendations


class UICalculator:
    """
    Calculates UI (Uncertainty in Information) using quality metrics.
    Integrates with Murphy's uncertainty framework.
    """
    
    def __init__(self, analyzer: InformationQualityAnalyzer):
        self.analyzer = analyzer
    
    def calculate_ui(
        self,
        information: InformationItem,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate UI score for information.
        
        Args:
            information: The information to assess
            context: Additional context
            
        Returns:
            UI score (0.0 to 1.0, where 0 = certain, 1 = highly uncertain)
        """
        assessment = self.analyzer.assess_information(information, context)
        return assessment.uncertainty_score
    
    def calculate_ui_detailed(
        self,
        information: InformationItem,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate UI with detailed breakdown.
        
        Args:
            information: The information to assess
            context: Additional context
            
        Returns:
            Dictionary with UI score and detailed breakdown
        """
        assessment = self.analyzer.assess_information(information, context)
        
        return {
            "ui_score": assessment.uncertainty_score,
            "quality_score": assessment.quality_score,
            "metrics": {
                "accuracy": assessment.metrics.accuracy,
                "completeness": assessment.metrics.completeness,
                "consistency": assessment.metrics.consistency,
                "timeliness": assessment.metrics.timeliness,
                "relevance": assessment.metrics.relevance,
                "credibility": assessment.metrics.credibility,
                "objectivity": assessment.metrics.objectivity,
                "verifiability": assessment.metrics.verifiability
            },
            "issues": assessment.issues,
            "recommendations": assessment.recommendations,
            "source": information.source,
            "age_days": information.age_in_days()
        }


class InformationQualitySystem:
    """
    Complete information quality metrics system.
    Provides unified interface for quality assessment and UI calculation.
    """
    
    def __init__(self):
        self.analyzer = InformationQualityAnalyzer()
        self.ui_calculator = UICalculator(self.analyzer)
        self.information_store: Dict[str, InformationItem] = {}
    
    def add_information(
        self,
        content: str,
        source: InformationSource,
        source_url: Optional[str] = None,
        author: Optional[str] = None,
        published_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add information to the system."""
        info = InformationItem(
            id=f"info_{datetime.utcnow().timestamp()}",
            content=content,
            source=source,
            source_url=source_url,
            author=author,
            published_date=published_date,
            metadata=metadata or {}
        )
        self.information_store[info.id] = info
        return info.id
    
    def assess_information(
        self,
        information_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> InformationQualityAssessment:
        """Assess information quality."""
        info = self.information_store.get(information_id)
        if not info:
            raise ValueError(f"Information {information_id} not found")
        
        return self.analyzer.assess_information(info, context)
    
    def calculate_ui(
        self,
        information_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calculate UI score."""
        info = self.information_store.get(information_id)
        if not info:
            raise ValueError(f"Information {information_id} not found")
        
        return self.ui_calculator.calculate_ui(info, context)
    
    def calculate_ui_detailed(
        self,
        information_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate UI with detailed breakdown."""
        info = self.information_store.get(information_id)
        if not info:
            raise ValueError(f"Information {information_id} not found")
        
        return self.ui_calculator.calculate_ui_detailed(info, context)