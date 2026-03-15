"""
SEO Optimisation Engine for Murphy System.

Design Label: MKT-002 — SEO Keyword Analysis, Meta-Tag Generation & Content Scoring
Owner: Marketing Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable analysis storage)
  - EventBackbone (publishes LEARNING_FEEDBACK on analysis outcomes)
  - RAGVectorIntegration (optional, for semantic keyword expansion)

Implements Phase 4 — Marketing & Content Automation:
  Analyses text content for SEO quality, extracts keywords,
  generates meta-tag suggestions, and scores content against
  SEO best practices.

Flow:
  1. Submit content for SEO analysis (title, body, url)
  2. Extract keywords using frequency analysis
  3. Generate meta-tag suggestions (title, description, keywords)
  4. Score content against SEO best practices
  5. Persist analysis results
  6. Publish LEARNING_FEEDBACK events with SEO scores

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: analyses are append-only
  - Bounded: configurable max analyses to prevent memory issues
  - Audit trail: every analysis is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEO scoring constants
# ---------------------------------------------------------------------------

_MIN_TITLE_LENGTH = 30
_MAX_TITLE_LENGTH = 60
_MIN_BODY_LENGTH = 300
_LONG_BODY_LENGTH = 1000
_MIN_KEYWORDS = 3
_SCORE_POINTS = 20.0

# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "for", "and", "or", "but",
    "not", "with", "this", "that", "from", "into", "to", "in", "on", "at",
    "by", "of", "it", "its", "if", "so", "no", "than", "too", "very",
    "just", "about", "up", "out", "all", "also", "as", "more", "some",
    "any", "each", "which", "their", "there", "then", "them", "these",
    "those", "he", "she", "we", "they", "you", "i", "me", "my", "your",
    "our", "his", "her", "what", "when", "where", "how", "who", "whom",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SEOAnalysis:
    """Result of an SEO content analysis."""
    analysis_id: str
    url: str
    title: str
    content_length: int
    keyword_count: int
    top_keywords: List[Tuple[str, int]]
    meta_suggestions: Dict[str, str]
    seo_score: float
    issues: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "url": self.url,
            "title": self.title,
            "content_length": self.content_length,
            "keyword_count": self.keyword_count,
            "top_keywords": [[w, c] for w, c in self.top_keywords],
            "meta_suggestions": dict(self.meta_suggestions),
            "seo_score": round(self.seo_score, 2),
            "issues": list(self.issues),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# SEOOptimisationEngine
# ---------------------------------------------------------------------------

class SEOOptimisationEngine:
    """SEO keyword analysis, meta-tag generation, and content scoring.

    Design Label: MKT-002
    Owner: Marketing Team

    Usage::

        engine = SEOOptimisationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        analysis = engine.analyse_content(
            title="Best practices for Python testing",
            body="Long article body text ...",
            url="https://example.com/python-testing",
        )
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_analyses: int = 10_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._analyses: List[SEOAnalysis] = []
        self._max_analyses = max_analyses

    # ------------------------------------------------------------------
    # Content analysis
    # ------------------------------------------------------------------

    def analyse_content(
        self,
        title: str,
        body: str,
        url: str = "",
    ) -> SEOAnalysis:
        """Analyse content for SEO quality. Returns the created analysis."""
        keywords = self._extract_keywords(body, top_n=10)
        keyword_count = len(keywords)
        top_keyword_words = {w for w, _ in keywords}

        # Meta-tag suggestions
        meta_suggestions: Dict[str, str] = {
            "title_tag": title[:60],
            "description_tag": body[:160],
            "keyword_tags": ", ".join(w for w, _ in keywords[:5]),
        }

        # Scoring
        score: float = 0.0
        issues: List[str] = []

        if _MIN_TITLE_LENGTH <= len(title) <= _MAX_TITLE_LENGTH:
            score += _SCORE_POINTS
        else:
            if len(title) < _MIN_TITLE_LENGTH:
                issues.append("Title too short")

        if len(body) > _MIN_BODY_LENGTH:
            score += _SCORE_POINTS
        else:
            issues.append("Body too short for SEO")

        if keyword_count >= _MIN_KEYWORDS:
            score += _SCORE_POINTS
        else:
            if keyword_count == 0:
                issues.append("No keywords detected")

        title_lower = title.lower()
        if top_keyword_words and any(kw in title_lower for kw in top_keyword_words):
            score += _SCORE_POINTS
        else:
            issues.append("Title missing top keywords")

        if len(body) > _LONG_BODY_LENGTH:
            score += _SCORE_POINTS

        analysis = SEOAnalysis(
            analysis_id=f"seo-{uuid.uuid4().hex[:8]}",
            url=url,
            title=title,
            content_length=len(body),
            keyword_count=keyword_count,
            top_keywords=keywords,
            meta_suggestions=meta_suggestions,
            seo_score=score,
            issues=issues,
        )

        with self._lock:
            if len(self._analyses) >= self._max_analyses:
                evict = max(1, self._max_analyses // 10)
                self._analyses = self._analyses[evict:]
            self._analyses.append(analysis)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=analysis.analysis_id,
                    document=analysis.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(analysis)

        logger.info(
            "SEO analysis %s completed for %r — score %.1f",
            analysis.analysis_id,
            url or title,
            analysis.seo_score,
        )
        return analysis

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Return a single analysis by its ID, or None if not found."""
        with self._lock:
            for a in self._analyses:
                if a.analysis_id == analysis_id:
                    return a.to_dict()
        return None

    def list_analyses(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent analyses."""
        with self._lock:
            return [a.to_dict() for a in self._analyses[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            total = len(self._analyses)
            avg_score = (
                sum(a.seo_score for a in self._analyses) / total
                if total
                else 0.0
            )
            return {
                "total_analyses": total,
                "avg_seo_score": round(avg_score, 2),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_keywords(text: str, top_n: int = 10) -> List[Tuple[str, int]]:
        """Extract top keywords from *text* using frequency analysis."""
        words = re.findall(r"[a-zA-Z]+", text.lower())
        filtered = [w for w in words if w not in _STOPWORDS and len(w) > 1]
        counts = Counter(filtered)
        return counts.most_common(top_n)

    def _publish_event(self, analysis: SEOAnalysis) -> None:
        """Publish a LEARNING_FEEDBACK event with analysis summary."""
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "seo_optimisation_engine",
                    "analysis": analysis.to_dict(),
                },
                source="seo_optimisation_engine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
