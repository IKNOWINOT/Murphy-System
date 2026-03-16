"""
Risk Lookup Service
Fast, intelligent risk identification and assessment service.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from src.confidence_engine.risk.risk_database import RiskCategory, RiskIncident, RiskPattern, RiskSeverity
from src.confidence_engine.risk.risk_storage import (
    PatternMatchResult,
    PatternMatchType,
    RiskPatternQuery,
    RiskPatternStorage,
)

logger = logging.getLogger(__name__)


class LookupContext(BaseModel):
    """Context for risk lookup."""
    operation: str
    domain: Optional[str] = None
    user_role: Optional[str] = None
    environment: str = "production"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskIdentificationResult(BaseModel):
    """Result of risk identification."""
    identified_risks: List[PatternMatchResult]
    total_risk_score: float = Field(ge=0.0, le=10.0)
    highest_severity: Optional[RiskSeverity] = None
    risk_count_by_severity: Dict[str, int] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    requires_human_review: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class RiskLookupCache:
    """
    Cache for risk lookup results to improve performance.
    """

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Tuple[datetime, RiskIdentificationResult]] = {}
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[RiskIdentificationResult]:
        """Get cached result if available and not expired."""
        if key in self.cache:
            cached_time, result = self.cache[key]
            if (datetime.now(timezone.utc) - cached_time).seconds < self.ttl_seconds:
                return result
            else:
                # Remove expired entry
                del self.cache[key]
        return None

    def set(self, key: str, result: RiskIdentificationResult):
        """Cache a result."""
        self.cache[key] = (datetime.now(timezone.utc), result)

    def clear(self):
        """Clear all cached results."""
        self.cache.clear()

    def get_cache_key(self, text: str, context: LookupContext) -> str:
        """Generate cache key."""
        return f"{text}_{context.operation}_{context.domain}_{context.environment}"


class RiskLookupService:
    """
    Service for looking up and identifying risks.
    """

    def __init__(self, storage: RiskPatternStorage):
        self.storage = storage
        self.cache = RiskLookupCache()

        # Severity ordering for comparison
        self.severity_order = {
            RiskSeverity.CRITICAL: 5,
            RiskSeverity.HIGH: 4,
            RiskSeverity.MEDIUM: 3,
            RiskSeverity.LOW: 2,
            RiskSeverity.NEGLIGIBLE: 1
        }

    def identify_risks(
        self,
        text: str,
        context: LookupContext,
        min_match_score: float = 0.3
    ) -> RiskIdentificationResult:
        """
        Identify risks in given text with context.

        Args:
            text: Text to analyze for risks
            context: Context for the analysis
            min_match_score: Minimum match score threshold

        Returns:
            RiskIdentificationResult with identified risks
        """
        # Check cache
        cache_key = self.cache.get_cache_key(text, context)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result

        # Perform pattern matching
        match_results = self.storage.matcher.match_patterns(
            text,
            match_type=PatternMatchType.CONTEXT,
            min_score=min_match_score
        )

        if not match_results:
            result = RiskIdentificationResult(
                identified_risks=[],
                total_risk_score=0.0,
                confidence=1.0
            )
            self.cache.set(cache_key, result)
            return result

        # Get full pattern details
        patterns = []
        for match in match_results:
            pattern = self.storage.get_pattern(match.pattern_id)
            if pattern:
                patterns.append((match, pattern))

        # Calculate total risk score (weighted by match confidence)
        total_risk_score = sum(
            pattern.risk_score * match.match_score
            for match, pattern in patterns
        )

        # Normalize to 0-10 scale
        if patterns:
            total_risk_score = min(total_risk_score / (len(patterns) or 1), 10.0)

        # Find highest severity
        highest_severity = None
        if patterns:
            highest_severity = max(
                (pattern.severity for _, pattern in patterns),
                key=lambda s: self.severity_order.get(s, 0)
            )

        # Count by severity
        severity_counts = {}
        for _, pattern in patterns:
            severity_str = pattern.severity.value
            severity_counts[severity_str] = severity_counts.get(severity_str, 0) + 1

        # Generate recommendations
        recommendations = self._generate_recommendations(patterns, context)

        # Determine if human review is required
        requires_review = self._requires_human_review(patterns, total_risk_score)

        # Calculate overall confidence
        confidence = sum(match.confidence for match in match_results) / (len(match_results) or 1)

        result = RiskIdentificationResult(
            identified_risks=match_results,
            total_risk_score=total_risk_score,
            highest_severity=highest_severity,
            risk_count_by_severity=severity_counts,
            recommendations=recommendations,
            requires_human_review=requires_review,
            confidence=confidence
        )

        # Cache result
        self.cache.set(cache_key, result)

        return result

    def lookup_by_category(
        self,
        category: RiskCategory,
        context: Optional[LookupContext] = None
    ) -> List[RiskPattern]:
        """
        Lookup risks by category.

        Args:
            category: Risk category to lookup
            context: Optional context for filtering

        Returns:
            List of matching risk patterns
        """
        query = RiskPatternQuery(
            category=category,
            limit=100
        )

        patterns = self.storage.search_patterns(query)

        # Apply context-based filtering if provided
        if context:
            patterns = self._filter_by_context(patterns, context)

        return patterns

    def lookup_by_severity(
        self,
        severity: RiskSeverity,
        context: Optional[LookupContext] = None
    ) -> List[RiskPattern]:
        """
        Lookup risks by severity.

        Args:
            severity: Risk severity to lookup
            context: Optional context for filtering

        Returns:
            List of matching risk patterns
        """
        query = RiskPatternQuery(
            severity=severity,
            limit=100
        )

        patterns = self.storage.search_patterns(query)

        if context:
            patterns = self._filter_by_context(patterns, context)

        return patterns

    def lookup_by_keywords(
        self,
        keywords: List[str],
        context: Optional[LookupContext] = None
    ) -> List[RiskPattern]:
        """
        Lookup risks by keywords.

        Args:
            keywords: Keywords to search for
            context: Optional context for filtering

        Returns:
            List of matching risk patterns
        """
        query = RiskPatternQuery(
            keywords=keywords,
            limit=100
        )

        patterns = self.storage.search_patterns(query)

        if context:
            patterns = self._filter_by_context(patterns, context)

        return patterns

    def lookup_high_risk_operations(
        self,
        operation: str,
        threshold: float = 6.0
    ) -> List[RiskPattern]:
        """
        Lookup high-risk patterns for a specific operation.

        Args:
            operation: Operation to check
            threshold: Risk score threshold

        Returns:
            List of high-risk patterns
        """
        context = LookupContext(operation=operation)
        result = self.identify_risks(operation, context)

        # Filter for high-risk patterns
        high_risk_ids = {
            match.pattern_id for match in result.identified_risks
            if self.storage.get_pattern(match.pattern_id).risk_score >= threshold
        }

        return [
            self.storage.get_pattern(pid)
            for pid in high_risk_ids
            if self.storage.get_pattern(pid)
        ]

    def get_risk_history(
        self,
        pattern_id: str,
        days: int = 30
    ) -> List[RiskIncident]:
        """
        Get historical incidents for a risk pattern.

        Args:
            pattern_id: Risk pattern ID
            days: Number of days to look back

        Returns:
            List of risk incidents
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        return self.storage.database.get_risk_incidents(
            pattern_id=pattern_id,
            start_date=start_date
        )

    def get_risk_trend(
        self,
        pattern_id: str,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get trend analysis for a risk pattern.

        Args:
            pattern_id: Risk pattern ID
            days: Number of days to analyze

        Returns:
            Dictionary with trend information
        """
        incidents = self.get_risk_history(pattern_id, days)

        if not incidents:
            return {
                "trend": "no_data",
                "incident_count": 0,
                "average_impact": 0.0
            }

        # Calculate trend
        mid = len(incidents) // 2
        first_half = incidents[:mid]
        second_half = incidents[mid:]

        trend = "stable"
        if len(second_half) > len(first_half) * 1.5:
            trend = "increasing"
        elif len(second_half) < len(first_half) * 0.5:
            trend = "decreasing"

        # Calculate average impact
        avg_impact = sum(i.actual_impact for i in incidents) / len(incidents)

        return {
            "trend": trend,
            "incident_count": len(incidents),
            "average_impact": avg_impact,
            "first_half_count": len(first_half),
            "second_half_count": len(second_half),
            "most_recent": incidents[-1].occurred_at.isoformat() if incidents else None
        }

    def _filter_by_context(
        self,
        patterns: List[RiskPattern],
        context: LookupContext
    ) -> List[RiskPattern]:
        """Filter patterns based on context."""
        filtered = patterns

        # Filter by domain if specified
        if context.domain:
            filtered = [
                p for p in filtered
                if context.domain.lower() in p.description.lower()
                or context.domain in p.tags
            ]

        # Filter by environment (production vs development)
        if context.environment == "production":
            # In production, show all risks
            pass
        else:
            # In development, filter out low-priority risks
            filtered = [
                p for p in filtered
                if p.severity not in [RiskSeverity.LOW, RiskSeverity.NEGLIGIBLE]
            ]

        return filtered

    def _generate_recommendations(
        self,
        patterns: List[Tuple[PatternMatchResult, RiskPattern]],
        context: LookupContext
    ) -> List[str]:
        """Generate recommendations based on identified risks."""
        recommendations = []

        # Check for critical risks
        critical_risks = [
            p for _, p in patterns
            if p.severity == RiskSeverity.CRITICAL
        ]

        if critical_risks:
            recommendations.append(
                f"CRITICAL: {len(critical_risks)} critical risk(s) identified - immediate action required"
            )

        # Check for high-risk operations
        high_risk = [
            p for _, p in patterns
            if p.risk_score >= 6.0
        ]

        if high_risk:
            recommendations.append(
                "High risk operation detected - consider implementing mitigation strategies"
            )

        # Check for multiple risks
        if len(patterns) > 3:
            recommendations.append(
                f"Multiple risks identified ({len(patterns)}) - review all before proceeding"
            )

        # Environment-specific recommendations
        if context.environment == "production":
            recommendations.append(
                "Production environment - ensure all mitigations are in place"
            )

        # Add pattern-specific recommendations
        for _, pattern in patterns[:3]:  # Top 3 risks
            if pattern.mitigation_strategies:
                strategy = pattern.mitigation_strategies[0]
                recommendations.append(
                    f"For {pattern.name}: Consider {strategy.name}"
                )

        return recommendations

    def _requires_human_review(
        self,
        patterns: List[Tuple[PatternMatchResult, RiskPattern]],
        total_risk_score: float
    ) -> bool:
        """Determine if human review is required."""
        # Require review for critical risks
        has_critical = any(
            p.severity == RiskSeverity.CRITICAL
            for _, p in patterns
        )

        # Require review for high total risk score
        high_total_risk = total_risk_score >= 7.0

        # Require review for multiple high-severity risks
        high_severity_count = sum(
            1 for _, p in patterns
            if p.severity in [RiskSeverity.CRITICAL, RiskSeverity.HIGH]
        )

        return has_critical or high_total_risk or high_severity_count >= 3


class RiskLookupAnalyzer:
    """
    Analyzes risk lookup results and provides insights.
    """

    def __init__(self, lookup_service: RiskLookupService):
        self.lookup_service = lookup_service

    def analyze_operation(
        self,
        operation: str,
        context: LookupContext
    ) -> Dict[str, Any]:
        """
        Perform comprehensive risk analysis for an operation.

        Args:
            operation: Operation to analyze
            context: Context for the analysis

        Returns:
            Dictionary with comprehensive analysis
        """
        # Identify risks
        result = self.lookup_service.identify_risks(operation, context)

        # Get detailed pattern information
        pattern_details = []
        for match in result.identified_risks:
            pattern = self.lookup_service.storage.get_pattern(match.pattern_id)
            if pattern:
                # Get historical trend
                trend = self.lookup_service.get_risk_trend(pattern.id)

                pattern_details.append({
                    "pattern_id": pattern.id,
                    "name": pattern.name,
                    "category": pattern.category.value,
                    "severity": pattern.severity.value,
                    "risk_score": pattern.risk_score,
                    "match_score": match.match_score,
                    "trend": trend["trend"],
                    "recent_incidents": trend["incident_count"],
                    "mitigation_count": len(pattern.mitigation_strategies)
                })

        # Calculate risk distribution
        risk_distribution = self._calculate_risk_distribution(result)

        # Generate executive summary
        summary = self._generate_executive_summary(result, pattern_details)

        return {
            "operation": operation,
            "context": context.model_dump(),
            "total_risk_score": result.total_risk_score,
            "confidence": result.confidence,
            "requires_human_review": result.requires_human_review,
            "identified_risks_count": len(result.identified_risks),
            "highest_severity": result.highest_severity.value if result.highest_severity else None,
            "risk_distribution": risk_distribution,
            "pattern_details": pattern_details,
            "recommendations": result.recommendations,
            "executive_summary": summary
        }

    def _calculate_risk_distribution(
        self,
        result: RiskIdentificationResult
    ) -> Dict[str, Any]:
        """Calculate risk distribution statistics."""
        return {
            "by_severity": result.risk_count_by_severity,
            "total_risks": len(result.identified_risks),
            "average_match_score": sum(
                r.match_score for r in result.identified_risks
            ) / (len(result.identified_risks) or 1) if result.identified_risks else 0.0
        }

    def _generate_executive_summary(
        self,
        result: RiskIdentificationResult,
        pattern_details: List[Dict[str, Any]]
    ) -> str:
        """Generate executive summary of risk analysis."""
        if not result.identified_risks:
            return "No significant risks identified for this operation."

        summary_parts = []

        # Overall assessment
        if result.total_risk_score >= 7.0:
            summary_parts.append("HIGH RISK operation identified.")
        elif result.total_risk_score >= 4.0:
            summary_parts.append("MEDIUM RISK operation identified.")
        else:
            summary_parts.append("LOW RISK operation identified.")

        # Risk count
        summary_parts.append(
            f"Total of {len(result.identified_risks)} risk(s) detected."
        )

        # Severity breakdown
        if result.highest_severity:
            summary_parts.append(
                f"Highest severity: {result.highest_severity.value.upper()}."
            )

        # Trending risks
        trending = [
            p for p in pattern_details
            if p.get("trend") == "increasing"
        ]
        if trending:
            summary_parts.append(
                f"{len(trending)} risk(s) showing increasing trend."
            )

        # Action required
        if result.requires_human_review:
            summary_parts.append("HUMAN REVIEW REQUIRED before proceeding.")

        return " ".join(summary_parts)


class RiskLookupSystem:
    """
    Complete risk lookup system.
    Provides unified interface for risk identification and analysis.
    """

    def __init__(self, storage: RiskPatternStorage):
        self.lookup_service = RiskLookupService(storage)
        self.analyzer = RiskLookupAnalyzer(self.lookup_service)

    def identify_risks(
        self,
        text: str,
        operation: str,
        domain: Optional[str] = None,
        environment: str = "production"
    ) -> RiskIdentificationResult:
        """Identify risks in text."""
        context = LookupContext(
            operation=operation,
            domain=domain,
            environment=environment
        )
        return self.lookup_service.identify_risks(text, context)

    def analyze_operation(
        self,
        operation: str,
        domain: Optional[str] = None,
        environment: str = "production"
    ) -> Dict[str, Any]:
        """Perform comprehensive risk analysis."""
        context = LookupContext(
            operation=operation,
            domain=domain,
            environment=environment
        )
        return self.analyzer.analyze_operation(operation, context)

    def lookup_by_category(self, category: RiskCategory) -> List[RiskPattern]:
        """Lookup risks by category."""
        return self.lookup_service.lookup_by_category(category)

    def lookup_by_severity(self, severity: RiskSeverity) -> List[RiskPattern]:
        """Lookup risks by severity."""
        return self.lookup_service.lookup_by_severity(severity)

    def get_high_risk_operations(self, operation: str) -> List[RiskPattern]:
        """Get high-risk patterns for operation."""
        return self.lookup_service.lookup_high_risk_operations(operation)

    def get_risk_trend(self, pattern_id: str, days: int = 90) -> Dict[str, Any]:
        """Get risk trend analysis."""
        return self.lookup_service.get_risk_trend(pattern_id, days)

    def clear_cache(self):
        """Clear lookup cache."""
        self.lookup_service.cache.clear()
