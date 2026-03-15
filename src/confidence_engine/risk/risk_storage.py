"""
Risk Pattern Storage System
Advanced storage and retrieval for risk patterns with pattern matching.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("confidence_engine.risk.risk_storage")

from src.confidence_engine.risk.risk_database import (
    MitigationStrategy,
    RiskCategory,
    RiskDatabase,
    RiskIncident,
    RiskLikelihood,
    RiskPattern,
    RiskSeverity,
)


class PatternMatchType(str, Enum):
    """Types of pattern matching."""
    EXACT = "exact"
    KEYWORD = "keyword"
    FUZZY = "fuzzy"
    CONTEXT = "context"
    SEMANTIC = "semantic"


class PatternMatchResult(BaseModel):
    """Result of pattern matching."""
    pattern_id: str
    pattern_name: str
    match_score: float = Field(ge=0.0, le=1.0)
    match_type: PatternMatchType
    matched_keywords: List[str] = Field(default_factory=list)
    matched_contexts: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RiskPatternQuery(BaseModel):
    """Query for searching risk patterns."""
    text: Optional[str] = None
    category: Optional[RiskCategory] = None
    severity: Optional[RiskSeverity] = None
    min_risk_score: Optional[float] = None
    max_risk_score: Optional[float] = None
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    match_type: PatternMatchType = PatternMatchType.KEYWORD
    limit: int = 10


class RiskPatternMatcher:
    """
    Matches text against risk patterns using various algorithms.
    """

    def __init__(self, database: RiskDatabase):
        self.database = database

    def match_patterns(
        self,
        text: str,
        match_type: PatternMatchType = PatternMatchType.KEYWORD,
        min_score: float = 0.3
    ) -> List[PatternMatchResult]:
        """
        Match text against all risk patterns.

        Args:
            text: Text to match against patterns
            match_type: Type of matching to perform
            min_score: Minimum match score threshold

        Returns:
            List of PatternMatchResult sorted by score
        """
        results = []
        text_lower = text.lower()

        for pattern in self.database.risk_patterns.values():
            if match_type == PatternMatchType.EXACT:
                score = self._exact_match(text_lower, pattern)
            elif match_type == PatternMatchType.KEYWORD:
                score = self._keyword_match(text_lower, pattern)
            elif match_type == PatternMatchType.CONTEXT:
                score = self._context_match(text_lower, pattern)
            elif match_type == PatternMatchType.FUZZY:
                score = self._fuzzy_match(text_lower, pattern)
            else:
                score = self._keyword_match(text_lower, pattern)

            if score >= min_score:
                matched_keywords = [
                    kw for kw in pattern.keywords
                    if kw.lower() in text_lower
                ]

                matched_contexts = [
                    ctx for ctx in pattern.context_patterns
                    if ctx.lower() in text_lower
                ]

                results.append(PatternMatchResult(
                    pattern_id=pattern.id,
                    pattern_name=pattern.name,
                    match_score=score,
                    match_type=match_type,
                    matched_keywords=matched_keywords,
                    matched_contexts=matched_contexts,
                    confidence=score
                ))

        # Sort by match score
        results.sort(key=lambda r: r.match_score, reverse=True)
        return results

    def _exact_match(self, text: str, pattern: RiskPattern) -> float:
        """Exact string matching."""
        if pattern.name.lower() in text:
            return 1.0
        if pattern.description.lower() in text:
            return 0.8
        return 0.0

    def _keyword_match(self, text: str, pattern: RiskPattern) -> float:
        """Keyword-based matching."""
        if not pattern.keywords:
            return 0.0

        matched_keywords = sum(1 for kw in pattern.keywords if kw.lower() in text)
        score = matched_keywords / len(pattern.keywords)

        return score

    def _context_match(self, text: str, pattern: RiskPattern) -> float:
        """Context pattern matching."""
        keyword_score = self._keyword_match(text, pattern)

        if not pattern.context_patterns:
            return keyword_score

        matched_contexts = sum(1 for ctx in pattern.context_patterns if ctx.lower() in text)
        context_score = matched_contexts / len(pattern.context_patterns)

        # Weighted combination
        return 0.6 * keyword_score + 0.4 * context_score

    def _fuzzy_match(self, text: str, pattern: RiskPattern) -> float:
        """Fuzzy matching with partial word matches."""
        score = 0.0
        text_words = set(text.split())

        # Check keywords with fuzzy matching
        for keyword in pattern.keywords:
            keyword_words = set(keyword.lower().split())

            # Calculate word overlap
            overlap = len(text_words & keyword_words)
            if overlap > 0:
                score += overlap / len(keyword_words)

        if pattern.keywords:
            score = score / len(pattern.keywords)

        return min(score, 1.0)


class RiskPatternStorage:
    """
    Advanced storage system for risk patterns with indexing and caching.
    """

    def __init__(self, database: RiskDatabase):
        self.database = database
        self.matcher = RiskPatternMatcher(database)
        self.query_cache: Dict[str, Tuple[datetime, List[PatternMatchResult]]] = {}
        self.cache_ttl_seconds = 300  # 5 minutes

    def store_pattern(
        self,
        name: str,
        description: str,
        category: RiskCategory,
        severity: RiskSeverity,
        likelihood: RiskLikelihood,
        impact_score: float,
        keywords: List[str],
        context_patterns: Optional[List[str]] = None,
        mitigation_strategies: Optional[List[MitigationStrategy]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a new risk pattern.

        Args:
            name: Name of the risk pattern
            description: Detailed description
            category: Risk category
            severity: Severity level
            likelihood: Likelihood of occurrence
            impact_score: Impact score (0-10)
            keywords: Keywords for pattern matching
            context_patterns: Context patterns for matching
            mitigation_strategies: List of mitigation strategies
            tags: Tags for categorization
            metadata: Additional metadata

        Returns:
            Pattern ID
        """
        # Calculate probability from likelihood
        likelihood_map = {
            RiskLikelihood.VERY_HIGH: 0.9,
            RiskLikelihood.HIGH: 0.7,
            RiskLikelihood.MEDIUM: 0.5,
            RiskLikelihood.LOW: 0.3,
            RiskLikelihood.VERY_LOW: 0.1
        }
        probability_score = likelihood_map.get(likelihood, 0.5)

        pattern = RiskPattern(
            id=f"risk_{datetime.now(timezone.utc).timestamp()}",
            name=name,
            description=description,
            category=category,
            severity=severity,
            likelihood=likelihood,
            impact_score=impact_score,
            probability_score=probability_score,
            risk_score=impact_score * probability_score,
            keywords=set(keywords),
            context_patterns=context_patterns or [],
            mitigation_strategies=mitigation_strategies or [],
            tags=tags or [],
            metadata=metadata or {}
        )

        return self.database.add_risk_pattern(pattern)

    def get_pattern(self, pattern_id: str) -> Optional[RiskPattern]:
        """Retrieve a risk pattern by ID."""
        return self.database.get_risk_pattern(pattern_id)

    def update_pattern(
        self,
        pattern_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update a risk pattern.

        Args:
            pattern_id: ID of pattern to update
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        pattern = self.database.get_risk_pattern(pattern_id)
        if not pattern:
            return False

        # Update fields
        for key, value in updates.items():
            if hasattr(pattern, key):
                setattr(pattern, key, value)

        # Recalculate risk score if impact or probability changed
        if 'impact_score' in updates or 'probability_score' in updates:
            pattern.risk_score = pattern.calculate_risk_score()

        pattern.updated_at = datetime.now(timezone.utc)

        # Clear cache
        self.query_cache.clear()

        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a risk pattern."""
        if pattern_id in self.database.risk_patterns:
            del self.database.risk_patterns[pattern_id]
            self.query_cache.clear()
            return True
        return False

    def search_patterns(self, query: RiskPatternQuery) -> List[RiskPattern]:
        """
        Search for risk patterns using a query.

        Args:
            query: RiskPatternQuery with search criteria

        Returns:
            List of matching RiskPattern objects
        """
        # Check cache
        cache_key = self._get_cache_key(query)
        if cache_key in self.query_cache:
            cached_time, cached_results = self.query_cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).seconds < self.cache_ttl_seconds:
                # Return cached patterns
                return [
                    self.database.get_risk_pattern(r.pattern_id)
                    for r in cached_results[:query.limit]
                    if self.database.get_risk_pattern(r.pattern_id)
                ]

        # Perform search
        patterns = self.database.search_risk_patterns(
            category=query.category,
            severity=query.severity,
            keywords=query.keywords,
            tags=query.tags,
            min_risk_score=query.min_risk_score
        )

        # Apply max risk score filter
        if query.max_risk_score is not None:
            patterns = [p for p in patterns if p.risk_score <= query.max_risk_score]

        # Apply text matching if provided
        if query.text:
            match_results = self.matcher.match_patterns(
                query.text,
                query.match_type
            )

            # Cache results
            self.query_cache[cache_key] = (datetime.now(timezone.utc), match_results)

            # Filter patterns by match results
            matched_ids = {r.pattern_id for r in match_results}
            patterns = [p for p in patterns if p.id in matched_ids]

            # Sort by match score
            pattern_scores = {r.pattern_id: r.match_score for r in match_results}
            patterns.sort(key=lambda p: pattern_scores.get(p.id, 0), reverse=True)

        return patterns[:query.limit]

    def find_similar_patterns(
        self,
        pattern_id: str,
        limit: int = 5
    ) -> List[Tuple[RiskPattern, float]]:
        """
        Find patterns similar to a given pattern.

        Args:
            pattern_id: ID of the reference pattern
            limit: Maximum number of similar patterns to return

        Returns:
            List of (pattern, similarity_score) tuples
        """
        reference = self.database.get_risk_pattern(pattern_id)
        if not reference:
            return []

        similar = []

        for pattern in self.database.risk_patterns.values():
            if pattern.id == pattern_id:
                continue

            similarity = self._calculate_similarity(reference, pattern)
            if similarity > 0.3:  # Threshold
                similar.append((pattern, similarity))

        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:limit]

    def _calculate_similarity(
        self,
        pattern1: RiskPattern,
        pattern2: RiskPattern
    ) -> float:
        """Calculate similarity between two patterns."""
        score = 0.0

        # Category match
        if pattern1.category == pattern2.category:
            score += 0.3

        # Severity match
        if pattern1.severity == pattern2.severity:
            score += 0.2

        # Keyword overlap
        if pattern1.keywords and pattern2.keywords:
            overlap = len(pattern1.keywords & pattern2.keywords)
            total = len(pattern1.keywords | pattern2.keywords)
            if total > 0:
                score += 0.3 * (overlap / total)

        # Risk score similarity
        if pattern1.risk_score > 0 and pattern2.risk_score > 0:
            score_diff = abs(pattern1.risk_score - pattern2.risk_score)
            score += 0.2 * (1 - min(score_diff / 10.0, 1.0))

        return score

    def _get_cache_key(self, query: RiskPatternQuery) -> str:
        """Generate cache key for a query."""
        return f"{query.text}_{query.category}_{query.severity}_{query.match_type}"

    def get_patterns_by_risk_level(
        self,
        min_score: float = 0.0,
        max_score: float = 10.0
    ) -> Dict[str, List[RiskPattern]]:
        """
        Get patterns grouped by risk level.

        Args:
            min_score: Minimum risk score
            max_score: Maximum risk score

        Returns:
            Dictionary with risk levels as keys and pattern lists as values
        """
        patterns = [
            p for p in self.database.risk_patterns.values()
            if min_score <= p.risk_score <= max_score
        ]

        grouped = {
            "critical": [],  # 8-10
            "high": [],      # 6-8
            "medium": [],    # 4-6
            "low": [],       # 2-4
            "negligible": [] # 0-2
        }

        for pattern in patterns:
            if pattern.risk_score >= 8:
                grouped["critical"].append(pattern)
            elif pattern.risk_score >= 6:
                grouped["high"].append(pattern)
            elif pattern.risk_score >= 4:
                grouped["medium"].append(pattern)
            elif pattern.risk_score >= 2:
                grouped["low"].append(pattern)
            else:
                grouped["negligible"].append(pattern)

        return grouped

    def get_trending_risks(
        self,
        days: int = 30,
        limit: int = 10
    ) -> List[Tuple[RiskPattern, int]]:
        """
        Get trending risks based on recent incidents.

        Args:
            days: Number of days to look back
            limit: Maximum number of risks to return

        Returns:
            List of (pattern, incident_count) tuples
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Count incidents per pattern
        incident_counts = defaultdict(int)
        for incident in self.database.risk_incidents.values():
            if incident.occurred_at >= cutoff:
                incident_counts[incident.risk_pattern_id] += 1

        # Get patterns with counts
        trending = []
        for pattern_id, count in incident_counts.items():
            pattern = self.database.get_risk_pattern(pattern_id)
            if pattern:
                trending.append((pattern, count))

        # Sort by count
        trending.sort(key=lambda x: x[1], reverse=True)
        return trending[:limit]

    def export_patterns(
        self,
        category: Optional[RiskCategory] = None,
        severity: Optional[RiskSeverity] = None
    ) -> List[Dict[str, Any]]:
        """
        Export patterns as dictionaries.

        Args:
            category: Optional category filter
            severity: Optional severity filter

        Returns:
            List of pattern dictionaries
        """
        patterns = self.database.search_risk_patterns(
            category=category,
            severity=severity
        )

        return [p.model_dump() for p in patterns]

    def import_patterns(self, patterns_data: List[Dict[str, Any]]) -> List[str]:
        """
        Import patterns from dictionaries.

        Args:
            patterns_data: List of pattern dictionaries

        Returns:
            List of imported pattern IDs
        """
        imported_ids = []

        for data in patterns_data:
            try:
                pattern = RiskPattern(**data)
                pattern_id = self.database.add_risk_pattern(pattern)
                imported_ids.append(pattern_id)
            except Exception as exc:
                logger.info(f"Error importing pattern: {exc}")
                continue

        return imported_ids

    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored patterns."""
        stats = self.database.get_risk_statistics()

        # Add storage-specific stats
        stats["cache_size"] = len(self.query_cache)
        stats["total_keywords"] = sum(
            len(p.keywords) for p in self.database.risk_patterns.values()
        )
        stats["total_context_patterns"] = sum(
            len(p.context_patterns) for p in self.database.risk_patterns.values()
        )

        return stats


class RiskPatternStorageSystem:
    """
    Complete risk pattern storage system.
    Provides unified interface for pattern storage and retrieval.
    """

    def __init__(self):
        self.database = RiskDatabase()
        self.storage = RiskPatternStorage(self.database)

    def store_pattern(
        self,
        name: str,
        description: str,
        category: RiskCategory,
        severity: RiskSeverity,
        likelihood: RiskLikelihood,
        impact_score: float,
        keywords: List[str],
        **kwargs
    ) -> str:
        """Store a new risk pattern."""
        return self.storage.store_pattern(
            name, description, category, severity, likelihood,
            impact_score, keywords, **kwargs
        )

    def get_pattern(self, pattern_id: str) -> Optional[RiskPattern]:
        """Get a risk pattern."""
        return self.storage.get_pattern(pattern_id)

    def search_patterns(self, query: RiskPatternQuery) -> List[RiskPattern]:
        """Search for patterns."""
        return self.storage.search_patterns(query)

    def match_text_to_patterns(
        self,
        text: str,
        min_score: float = 0.3
    ) -> List[PatternMatchResult]:
        """Match text against all patterns."""
        return self.storage.matcher.match_patterns(text, min_score=min_score)

    def get_high_risk_patterns(self, threshold: float = 6.0) -> List[RiskPattern]:
        """Get all high-risk patterns."""
        return self.storage.database.search_risk_patterns(min_risk_score=threshold)

    def get_patterns_by_category(self, category: RiskCategory) -> List[RiskPattern]:
        """Get patterns by category."""
        return self.storage.database.search_risk_patterns(category=category)

    def get_trending_risks(self, days: int = 30) -> List[Tuple[RiskPattern, int]]:
        """Get trending risks."""
        return self.storage.get_trending_risks(days)

    def export_database(self, filepath: str):
        """Export entire database."""
        self.database.export_to_json(filepath)

    def import_database(self, filepath: str):
        """Import database from file."""
        self.database.import_from_json(filepath)
