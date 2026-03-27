"""
Risk Database System
Stores and manages risk patterns, historical incidents, and mitigation strategies.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskCategory(str, Enum):
    """Categories of risks."""
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    FINANCIAL = "financial"
    REPUTATIONAL = "reputational"
    DATA_QUALITY = "data_quality"
    RESOURCE = "resource"
    HUMAN_ERROR = "human_error"
    EXTERNAL = "external"


class RiskSeverity(str, Enum):
    """Severity levels for risks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class RiskLikelihood(str, Enum):
    """Likelihood of risk occurrence."""
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class RiskStatus(str, Enum):
    """Status of a risk."""
    ACTIVE = "active"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    TRANSFERRED = "transferred"
    AVOIDED = "avoided"
    MONITORING = "monitoring"


class MitigationStrategy(BaseModel):
    """Represents a risk mitigation strategy."""
    id: str
    name: str
    description: str
    effectiveness: float = Field(ge=0.0, le=1.0)
    cost: Optional[float] = None
    implementation_time_hours: Optional[float] = None
    prerequisites: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    success_rate: float = Field(ge=0.0, le=1.0, default=0.8)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskIndicator(BaseModel):
    """Indicators that suggest a risk may occur."""
    id: str
    name: str
    description: str
    detection_method: str
    threshold: Optional[float] = None
    current_value: Optional[float] = None
    is_triggered: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskPattern(BaseModel):
    """Represents a known risk pattern."""
    id: str
    name: str
    description: str
    category: RiskCategory
    severity: RiskSeverity
    likelihood: RiskLikelihood
    impact_score: float = Field(ge=0.0, le=10.0)
    probability_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=10.0)

    # Pattern matching
    keywords: Set[str] = Field(default_factory=set)
    context_patterns: List[str] = Field(default_factory=list)

    # Mitigation
    mitigation_strategies: List[MitigationStrategy] = Field(default_factory=list)

    # Indicators
    indicators: List[RiskIndicator] = Field(default_factory=list)

    # Historical data
    occurrence_count: int = 0
    last_occurred: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def calculate_risk_score(self) -> float:
        """Calculate overall risk score."""
        # Risk Score = Impact × Probability
        return self.impact_score * self.probability_score


class RiskIncident(BaseModel):
    """Represents an actual risk incident that occurred."""
    id: str
    risk_pattern_id: str
    title: str
    description: str
    occurred_at: datetime
    detected_at: datetime
    resolved_at: Optional[datetime] = None

    # Impact
    actual_impact: float = Field(ge=0.0, le=10.0)
    affected_systems: List[str] = Field(default_factory=list)
    affected_users: int = 0
    financial_impact: Optional[float] = None

    # Response
    mitigation_applied: Optional[str] = None
    mitigation_effectiveness: Optional[float] = None
    lessons_learned: List[str] = Field(default_factory=list)

    # Status
    status: str = "open"

    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    """Assessment of risk for a specific context."""
    id: str
    context: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Identified risks
    identified_risks: List[str] = Field(default_factory=list)  # Risk pattern IDs

    # Scores
    overall_risk_score: float = Field(ge=0.0, le=10.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)

    # Recommendations
    recommended_mitigations: List[str] = Field(default_factory=list)
    required_actions: List[str] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskDatabaseSchema:
    """
    Schema definition for the risk database.
    In production, this would map to actual database tables.
    """

    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get the complete database schema."""
        return {
            "risk_patterns": {
                "description": "Known risk patterns and their characteristics",
                "fields": {
                    "id": "string (primary key)",
                    "name": "string",
                    "description": "text",
                    "category": "enum (RiskCategory)",
                    "severity": "enum (RiskSeverity)",
                    "likelihood": "enum (RiskLikelihood)",
                    "impact_score": "float (0-10)",
                    "probability_score": "float (0-1)",
                    "risk_score": "float (0-10)",
                    "keywords": "json (set of strings)",
                    "context_patterns": "json (list of strings)",
                    "mitigation_strategies": "json (list of MitigationStrategy)",
                    "indicators": "json (list of RiskIndicator)",
                    "occurrence_count": "integer",
                    "last_occurred": "timestamp",
                    "created_at": "timestamp",
                    "updated_at": "timestamp",
                    "tags": "json (list of strings)",
                    "metadata": "json"
                },
                "indexes": [
                    "category",
                    "severity",
                    "risk_score",
                    "keywords",
                    "tags"
                ]
            },
            "risk_incidents": {
                "description": "Historical risk incidents",
                "fields": {
                    "id": "string (primary key)",
                    "risk_pattern_id": "string (foreign key)",
                    "title": "string",
                    "description": "text",
                    "occurred_at": "timestamp",
                    "detected_at": "timestamp",
                    "resolved_at": "timestamp",
                    "actual_impact": "float (0-10)",
                    "affected_systems": "json (list of strings)",
                    "affected_users": "integer",
                    "financial_impact": "float",
                    "mitigation_applied": "string",
                    "mitigation_effectiveness": "float (0-1)",
                    "lessons_learned": "json (list of strings)",
                    "status": "string",
                    "metadata": "json"
                },
                "indexes": [
                    "risk_pattern_id",
                    "occurred_at",
                    "status",
                    "actual_impact"
                ]
            },
            "mitigation_strategies": {
                "description": "Risk mitigation strategies",
                "fields": {
                    "id": "string (primary key)",
                    "name": "string",
                    "description": "text",
                    "effectiveness": "float (0-1)",
                    "cost": "float",
                    "implementation_time_hours": "float",
                    "prerequisites": "json (list of strings)",
                    "steps": "json (list of strings)",
                    "success_rate": "float (0-1)",
                    "metadata": "json"
                },
                "indexes": [
                    "effectiveness",
                    "cost"
                ]
            },
            "risk_assessments": {
                "description": "Risk assessments for specific contexts",
                "fields": {
                    "id": "string (primary key)",
                    "context": "text",
                    "assessed_at": "timestamp",
                    "identified_risks": "json (list of risk pattern IDs)",
                    "overall_risk_score": "float (0-10)",
                    "uncertainty_score": "float (0-1)",
                    "recommended_mitigations": "json (list of strings)",
                    "required_actions": "json (list of strings)",
                    "metadata": "json"
                },
                "indexes": [
                    "assessed_at",
                    "overall_risk_score"
                ]
            },
            "risk_indicators": {
                "description": "Risk indicators and their current states",
                "fields": {
                    "id": "string (primary key)",
                    "name": "string",
                    "description": "text",
                    "detection_method": "string",
                    "threshold": "float",
                    "current_value": "float",
                    "is_triggered": "boolean",
                    "metadata": "json"
                },
                "indexes": [
                    "is_triggered",
                    "current_value"
                ]
            }
        }


class RiskDatabase:
    """
    In-memory risk database implementation.
    In production, this would use a real database (PostgreSQL, MongoDB, etc.).
    """

    def __init__(self):
        self.risk_patterns: Dict[str, RiskPattern] = {}
        self.risk_incidents: Dict[str, RiskIncident] = {}
        self.mitigation_strategies: Dict[str, MitigationStrategy] = {}
        self.risk_assessments: Dict[str, RiskAssessment] = {}
        self.risk_indicators: Dict[str, RiskIndicator] = {}

        # Indexes for fast lookup
        self.category_index: Dict[RiskCategory, List[str]] = {}
        self.severity_index: Dict[RiskSeverity, List[str]] = {}
        self.keyword_index: Dict[str, List[str]] = {}
        self.tag_index: Dict[str, List[str]] = {}

        # Initialize with default risk patterns
        self._initialize_default_patterns()

    def _initialize_default_patterns(self):
        """Initialize database with common risk patterns."""
        default_patterns = [
            RiskPattern(
                id="risk_001",
                name="Data Loss",
                description="Risk of losing critical data due to system failure or human error",
                category=RiskCategory.TECHNICAL,
                severity=RiskSeverity.CRITICAL,
                likelihood=RiskLikelihood.MEDIUM,
                impact_score=9.0,
                probability_score=0.3,
                risk_score=2.7,
                keywords={"data loss", "deletion", "corruption", "backup failure"},
                context_patterns=["delete", "remove", "drop", "truncate"],
                tags=["data", "critical"]
            ),
            RiskPattern(
                id="risk_002",
                name="Security Breach",
                description="Unauthorized access to systems or data",
                category=RiskCategory.SECURITY,
                severity=RiskSeverity.CRITICAL,
                likelihood=RiskLikelihood.MEDIUM,
                impact_score=10.0,
                probability_score=0.4,
                risk_score=4.0,
                keywords={"breach", "unauthorized", "hack", "intrusion"},
                context_patterns=["authentication", "authorization", "access control"],
                tags=["security", "critical"]
            ),
            RiskPattern(
                id="risk_003",
                name="Resource Exhaustion",
                description="Running out of critical resources (CPU, memory, storage)",
                category=RiskCategory.RESOURCE,
                severity=RiskSeverity.HIGH,
                likelihood=RiskLikelihood.HIGH,
                impact_score=7.0,
                probability_score=0.6,
                risk_score=4.2,
                keywords={"out of memory", "disk full", "cpu overload", "quota exceeded"},
                context_patterns=["resource", "capacity", "limit"],
                tags=["resources", "performance"]
            ),
            RiskPattern(
                id="risk_004",
                name="Compliance Violation",
                description="Violation of regulatory or compliance requirements",
                category=RiskCategory.COMPLIANCE,
                severity=RiskSeverity.HIGH,
                likelihood=RiskLikelihood.LOW,
                impact_score=8.0,
                probability_score=0.2,
                risk_score=1.6,
                keywords={"gdpr", "hipaa", "pci", "compliance", "regulation"},
                context_patterns=["personal data", "sensitive information", "audit"],
                tags=["compliance", "legal"]
            ),
            RiskPattern(
                id="risk_005",
                name="API Rate Limit Exceeded",
                description="Exceeding API rate limits causing service disruption",
                category=RiskCategory.OPERATIONAL,
                severity=RiskSeverity.MEDIUM,
                likelihood=RiskLikelihood.HIGH,
                impact_score=5.0,
                probability_score=0.7,
                risk_score=3.5,
                keywords={"rate limit", "throttle", "quota", "429 error"},
                context_patterns=["api call", "request", "external service"],
                tags=["api", "external"]
            )
        ]

        for pattern in default_patterns:
            self.add_risk_pattern(pattern)

    def add_risk_pattern(self, pattern: RiskPattern) -> str:
        """Add a risk pattern to the database."""
        self.risk_patterns[pattern.id] = pattern

        # Update indexes
        if pattern.category not in self.category_index:
            self.category_index[pattern.category] = []
        self.category_index[pattern.category].append(pattern.id)

        if pattern.severity not in self.severity_index:
            self.severity_index[pattern.severity] = []
        self.severity_index[pattern.severity].append(pattern.id)

        for keyword in pattern.keywords:
            if keyword not in self.keyword_index:
                self.keyword_index[keyword] = []
            self.keyword_index[keyword].append(pattern.id)

        for tag in pattern.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(pattern.id)

        return pattern.id

    def get_risk_pattern(self, pattern_id: str) -> Optional[RiskPattern]:
        """Get a risk pattern by ID."""
        return self.risk_patterns.get(pattern_id)

    def search_risk_patterns(
        self,
        category: Optional[RiskCategory] = None,
        severity: Optional[RiskSeverity] = None,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        min_risk_score: Optional[float] = None
    ) -> List[RiskPattern]:
        """Search for risk patterns matching criteria."""
        patterns = list(self.risk_patterns.values())

        if category:
            pattern_ids = self.category_index.get(category, [])
            patterns = [p for p in patterns if p.id in pattern_ids]

        if severity:
            pattern_ids = self.severity_index.get(severity, [])
            patterns = [p for p in patterns if p.id in pattern_ids]

        if keywords:
            matching_ids = set()
            for keyword in keywords:
                matching_ids.update(self.keyword_index.get(keyword.lower(), []))
            patterns = [p for p in patterns if p.id in matching_ids]

        if tags:
            matching_ids = set()
            for tag in tags:
                matching_ids.update(self.tag_index.get(tag, []))
            patterns = [p for p in patterns if p.id in matching_ids]

        if min_risk_score is not None:
            patterns = [p for p in patterns if p.risk_score >= min_risk_score]

        return patterns

    def add_risk_incident(self, incident: RiskIncident) -> str:
        """Record a risk incident."""
        self.risk_incidents[incident.id] = incident

        # Update pattern occurrence count
        pattern = self.risk_patterns.get(incident.risk_pattern_id)
        if pattern:
            pattern.occurrence_count += 1
            pattern.last_occurred = incident.occurred_at

        return incident.id

    def get_risk_incidents(
        self,
        pattern_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[RiskIncident]:
        """Get risk incidents with filters."""
        incidents = list(self.risk_incidents.values())

        if pattern_id:
            incidents = [i for i in incidents if i.risk_pattern_id == pattern_id]

        if status:
            incidents = [i for i in incidents if i.status == status]

        if start_date:
            incidents = [i for i in incidents if i.occurred_at >= start_date]

        if end_date:
            incidents = [i for i in incidents if i.occurred_at <= end_date]

        return incidents

    def add_mitigation_strategy(self, strategy: MitigationStrategy) -> str:
        """Add a mitigation strategy."""
        self.mitigation_strategies[strategy.id] = strategy
        return strategy.id

    def get_mitigation_strategy(self, strategy_id: str) -> Optional[MitigationStrategy]:
        """Get a mitigation strategy by ID."""
        return self.mitigation_strategies.get(strategy_id)

    def add_risk_assessment(self, assessment: RiskAssessment) -> str:
        """Record a risk assessment."""
        self.risk_assessments[assessment.id] = assessment
        return assessment.id

    def get_risk_statistics(self) -> Dict[str, Any]:
        """Get overall risk statistics."""
        total_patterns = len(self.risk_patterns)
        total_incidents = len(self.risk_incidents)

        # Category breakdown
        category_counts = {}
        for category in RiskCategory:
            category_counts[category.value] = len(self.category_index.get(category, []))

        # Severity breakdown
        severity_counts = {}
        for severity in RiskSeverity:
            severity_counts[severity.value] = len(self.severity_index.get(severity, []))

        # Average risk score
        risk_scores = [p.risk_score for p in self.risk_patterns.values()]
        avg_risk_score = sum(risk_scores) / (len(risk_scores) or 1) if risk_scores else 0.0

        return {
            "total_patterns": total_patterns,
            "total_incidents": total_incidents,
            "category_breakdown": category_counts,
            "severity_breakdown": severity_counts,
            "average_risk_score": avg_risk_score,
            "highest_risk_patterns": sorted(
                self.risk_patterns.values(),
                key=lambda p: p.risk_score,
                reverse=True
            )[:5]
        }

    def export_to_json(self, filepath: str):
        """Export database to JSON file."""
        data = {
            "risk_patterns": [p.model_dump() for p in self.risk_patterns.values()],
            "risk_incidents": [i.model_dump() for i in self.risk_incidents.values()],
            "mitigation_strategies": [s.model_dump() for s in self.mitigation_strategies.values()],
            "risk_assessments": [a.model_dump() for a in self.risk_assessments.values()]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    def import_from_json(self, filepath: str):
        """Import database from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for pattern_data in data.get("risk_patterns", []):
            pattern = RiskPattern(**pattern_data)
            self.add_risk_pattern(pattern)

        for incident_data in data.get("risk_incidents", []):
            incident = RiskIncident(**incident_data)
            self.add_risk_incident(incident)

        for strategy_data in data.get("mitigation_strategies", []):
            strategy = MitigationStrategy(**strategy_data)
            self.add_mitigation_strategy(strategy)

        for assessment_data in data.get("risk_assessments", []):
            assessment = RiskAssessment(**assessment_data)
            self.add_risk_assessment(assessment)
