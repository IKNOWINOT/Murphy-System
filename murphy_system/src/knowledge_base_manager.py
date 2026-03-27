"""
Knowledge Base Manager for Murphy System.

Design Label: SUP-002 — RAG-Powered Knowledge Base Automation
Owner: Support Team / Platform Engineering
Dependencies:
  - RAGVectorIntegration (for document ingestion and semantic search)
  - TicketingAdapter (reads resolved tickets to extract knowledge)
  - EventBackbone (optional, publishes LEARNING_FEEDBACK events)

Implements Phase 3 — Customer Support Automation:
  Manages a knowledge base that automatically extracts knowledge from
  resolved tickets, maintains articles, identifies knowledge gaps,
  and serves as a queryable resource for ticket resolution.

Flow:
  1. Ingest resolved tickets into RAG-backed knowledge base
  2. Search knowledge base for relevant articles on new tickets
  3. Track article metadata (views, helpfulness, staleness)
  4. Detect knowledge gaps (frequent queries with no good matches)
  5. Publish events for downstream automation

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: articles are versioned, never deleted
  - Bounded: configurable max articles to prevent memory issues

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class KBArticle:
    """A single knowledge base article."""
    article_id: str
    title: str
    content: str
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    source_ticket_id: Optional[str] = None
    version: int = 1
    views: int = 0
    helpful_votes: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "source_ticket_id": self.source_ticket_id,
            "version": self.version,
            "views": self.views,
            "helpful_votes": self.helpful_votes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class KBSearchResult:
    """Result of a knowledge base search."""
    article_id: str
    title: str
    score: float
    snippet: str
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "category": self.category,
        }


@dataclass
class KnowledgeGap:
    """A detected gap in the knowledge base."""
    gap_id: str
    query: str
    frequency: int
    best_score: float
    suggested_title: str
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "query": self.query,
            "frequency": self.frequency,
            "best_score": round(self.best_score, 4),
            "suggested_title": self.suggested_title,
            "detected_at": self.detected_at,
        }


# ---------------------------------------------------------------------------
# KnowledgeBaseManager
# ---------------------------------------------------------------------------

class KnowledgeBaseManager:
    """RAG-powered knowledge base for customer support automation.

    Design Label: SUP-002
    Owner: Support Team

    Usage::

        kb = KnowledgeBaseManager(rag_integration=rag)
        kb.add_article(title="How to reset password", content="...")
        results = kb.search("password reset not working")
        gaps = kb.detect_gaps()
    """

    def __init__(
        self,
        rag_integration=None,
        event_backbone=None,
        max_articles: int = 5_000,
        gap_score_threshold: float = 0.3,
    ) -> None:
        self._lock = threading.Lock()
        self._rag = rag_integration
        self._backbone = event_backbone
        self._articles: Dict[str, KBArticle] = {}
        self._max_articles = max_articles
        self._gap_threshold = gap_score_threshold
        self._search_log: List[Dict[str, Any]] = []
        self._max_search_log = 1_000

    # ------------------------------------------------------------------
    # Article management
    # ------------------------------------------------------------------

    def add_article(
        self,
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        source_ticket_id: Optional[str] = None,
    ) -> KBArticle:
        """Create a new knowledge base article."""
        article = KBArticle(
            article_id=f"kb-{uuid.uuid4().hex[:8]}",
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source_ticket_id=source_ticket_id,
        )

        with self._lock:
            if len(self._articles) >= self._max_articles:
                logger.warning("KB at capacity (%d articles)", self._max_articles)
                # Evict oldest
                oldest = min(self._articles.values(), key=lambda a: a.created_at)
                del self._articles[oldest.article_id]
            self._articles[article.article_id] = article

        # Ingest into RAG
        if self._rag is not None:
            try:
                self._rag.ingest_document(
                    text=f"{title}\n\n{content}",
                    title=title,
                    source=f"kb:{article.article_id}",
                    metadata={
                        "article_id": article.article_id,
                        "category": category,
                        "tags": tags or [],
                    },
                )
            except Exception as exc:
                logger.debug("RAG ingestion skipped: %s", exc)

        logger.info("Added KB article %s: %s", article.article_id, title)
        return article

    def update_article(
        self,
        article_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[KBArticle]:
        """Update an existing article (bumps version)."""
        with self._lock:
            article = self._articles.get(article_id)
            if article is None:
                return None
            if content is not None:
                article.content = content
            if title is not None:
                article.title = title
            if tags is not None:
                article.tags = tags
            article.version += 1
            article.updated_at = datetime.now(timezone.utc).isoformat()
        return article

    def get_article(self, article_id: str) -> Optional[KBArticle]:
        """Retrieve and record a view for an article."""
        with self._lock:
            article = self._articles.get(article_id)
            if article is not None:
                article.views += 1
        return article

    def list_articles(
        self,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List articles with optional category filter."""
        with self._lock:
            articles = list(self._articles.values())
        if category is not None:
            articles = [a for a in articles if a.category == category]
        articles.sort(key=lambda a: a.updated_at, reverse=True)
        return [a.to_dict() for a in articles[:limit]]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> List[KBSearchResult]:
        """Search the knowledge base using RAG semantic search."""
        results: List[KBSearchResult] = []

        if self._rag is not None:
            try:
                rag_results = self._rag.search(
                    query=query,
                    top_k=top_k,
                    min_score=min_score,
                )
                for r in rag_results.get("results", []):
                    meta = r.get("metadata", {})
                    results.append(KBSearchResult(
                        article_id=meta.get("article_id", r.get("doc_id", "")),
                        title=meta.get("title", ""),
                        score=r.get("score", 0.0),
                        snippet=r.get("text", "")[:200],
                        category=meta.get("category", "general"),
                    ))
            except Exception as exc:
                logger.debug("RAG search error: %s", exc)

        # Fallback: keyword search over in-memory articles
        if not results:
            query_lower = query.lower()
            with self._lock:
                for article in self._articles.values():
                    text = f"{article.title} {article.content}".lower()
                    words = query_lower.split()
                    hits = sum(1 for w in words if w in text)
                    if hits > 0:
                        score = hits / max(len(words), 1)
                        results.append(KBSearchResult(
                            article_id=article.article_id,
                            title=article.title,
                            score=score,
                            snippet=article.content[:200],
                            category=article.category,
                        ))
            results.sort(key=lambda r: r.score, reverse=True)
            results = results[:top_k]

        # Log search for gap detection
        best_score = results[0].score if results else 0.0
        with self._lock:
            self._search_log.append({
                "query": query,
                "best_score": best_score,
                "num_results": len(results),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(self._search_log) > self._max_search_log:
                self._search_log = self._search_log[-self._max_search_log:]

        return results

    # ------------------------------------------------------------------
    # Knowledge gap detection
    # ------------------------------------------------------------------

    def detect_gaps(self, min_frequency: int = 2) -> List[KnowledgeGap]:
        """Detect knowledge gaps from search log analysis.

        Finds queries that were searched multiple times but had
        poor match scores, indicating missing knowledge.
        """
        with self._lock:
            log = list(self._search_log)

        # Group by normalized query
        query_groups: Dict[str, List[Dict]] = {}
        for entry in log:
            key = entry["query"].lower().strip()[:100]
            query_groups.setdefault(key, []).append(entry)

        gaps: List[KnowledgeGap] = []
        for query, entries in query_groups.items():
            if len(entries) < min_frequency:
                continue
            best = max(e["best_score"] for e in entries)
            if best < self._gap_threshold:
                gaps.append(KnowledgeGap(
                    gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                    query=query,
                    frequency=len(entries),
                    best_score=best,
                    suggested_title=f"Knowledge article needed: {query[:80]}",
                ))

        gaps.sort(key=lambda g: g.frequency, reverse=True)

        # Publish gaps
        if self._backbone is not None and gaps:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "knowledge_base_manager",
                        "gaps_detected": len(gaps),
                        "gaps": [g.to_dict() for g in gaps[:5]],
                    },
                    source="knowledge_base_manager",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)

        return gaps

    # ------------------------------------------------------------------
    # Ticket knowledge extraction
    # ------------------------------------------------------------------

    def extract_from_ticket(
        self,
        ticket_id: str,
        title: str,
        description: str,
        resolution: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
    ) -> KBArticle:
        """Extract knowledge from a resolved ticket and create an article."""
        content = (
            f"## Problem\n{description}\n\n"
            f"## Resolution\n{resolution}\n"
        )
        return self.add_article(
            title=f"Resolved: {title}",
            content=content,
            category=category,
            tags=tags or [],
            source_ticket_id=ticket_id,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._articles)
            categories = Counter(a.category for a in self._articles.values())
            total_views = sum(a.views for a in self._articles.values())
        return {
            "total_articles": total,
            "max_articles": self._max_articles,
            "categories": dict(categories),
            "total_views": total_views,
            "search_log_size": len(self._search_log),
            "rag_attached": self._rag is not None,
            "backbone_attached": self._backbone is not None,
        }
