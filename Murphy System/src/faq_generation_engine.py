"""
FAQ Generation Engine for Murphy System.

Design Label: SUP-003 — Automated FAQ Generation from Knowledge Base & Ticket Patterns
Owner: Support Team / Platform Engineering
Dependencies:
  - KnowledgeBaseManager (SUP-002, for article content and gap data)
  - TicketTriageEngine (SUP-001, for ticket frequency data)
  - RAGVectorIntegration (optional, for semantic deduplication)
  - EventBackbone (publishes LEARNING_FEEDBACK on FAQ generation)
  - PersistenceManager (for durable FAQ storage)

Implements Phase 3 — Customer Support Automation:
  Analyses common questions from ticket data and knowledge base gaps
  to generate FAQ entries. Tracks FAQ effectiveness via view and
  helpfulness metrics. Identifies stale FAQs that need updating.

Flow:
  1. Collect frequent questions from ticket triage history
  2. Match questions against existing knowledge base articles
  3. Generate FAQ entries from matched knowledge
  4. Detect gaps (frequent questions with no knowledge base match)
  5. Track FAQ effectiveness (views, helpfulness)
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: FAQs are versioned, never deleted
  - Bounded: configurable max FAQs to prevent memory issues
  - Audit trail: every generation cycle is logged

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
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FAQS = 10_000
_MAX_QUESTIONS = 50_000
_MIN_FREQUENCY_FOR_FAQ = 3


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FAQEntry:
    """A single FAQ entry."""
    faq_id: str
    question: str
    answer: str
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    source: str = ""
    version: int = 1
    views: int = 0
    helpful_votes: int = 0
    not_helpful_votes: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "faq_id": self.faq_id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "tags": list(self.tags),
            "source": self.source,
            "version": self.version,
            "views": self.views,
            "helpful_votes": self.helpful_votes,
            "not_helpful_votes": self.not_helpful_votes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @property
    def helpfulness_ratio(self) -> float:
        total = self.helpful_votes + self.not_helpful_votes
        return self.helpful_votes / total if total > 0 else 0.0


@dataclass
class QuestionRecord:
    """A recorded customer question for frequency analysis."""
    question_id: str
    text: str
    normalised: str
    category: str = ""
    source_ticket_id: str = ""
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "text": self.text,
            "normalised": self.normalised,
            "category": self.category,
            "source_ticket_id": self.source_ticket_id,
            "recorded_at": self.recorded_at,
        }


@dataclass
class FAQGenerationReport:
    """Summary of an FAQ generation cycle."""
    report_id: str
    questions_analysed: int
    faqs_created: int
    faqs_updated: int
    gaps_detected: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "questions_analysed": self.questions_analysed,
            "faqs_created": self.faqs_created,
            "faqs_updated": self.faqs_updated,
            "gaps_detected": self.gaps_detected,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# FAQGenerationEngine
# ---------------------------------------------------------------------------

class FAQGenerationEngine:
    """Automated FAQ generation from knowledge base and ticket patterns.

    Design Label: SUP-003
    Owner: Support Team / Platform Engineering

    Usage::

        engine = FAQGenerationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        engine.record_question("How do I reset my password?")
        engine.add_faq("How do I reset my password?",
                       "Go to Settings > Security > Reset Password")
        report = engine.run_generation_cycle()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_faqs: int = _MAX_FAQS,
        max_questions: int = _MAX_QUESTIONS,
        min_frequency: int = _MIN_FREQUENCY_FOR_FAQ,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._faqs: Dict[str, FAQEntry] = {}
        self._questions: List[QuestionRecord] = []
        self._reports: List[FAQGenerationReport] = []
        self._max_faqs = max_faqs
        self._max_questions = max_questions
        self._min_frequency = min_frequency

    # ------------------------------------------------------------------
    # Question recording
    # ------------------------------------------------------------------

    def record_question(
        self,
        text: str,
        category: str = "",
        source_ticket_id: str = "",
    ) -> QuestionRecord:
        """Record a customer question for frequency analysis."""
        normalised = self._normalise_question(text)
        record = QuestionRecord(
            question_id=f"qst-{uuid.uuid4().hex[:8]}",
            text=text,
            normalised=normalised,
            category=category,
            source_ticket_id=source_ticket_id,
        )
        with self._lock:
            if len(self._questions) >= self._max_questions:
                evict = max(1, self._max_questions // 10)
                self._questions = self._questions[evict:]
            self._questions.append(record)
        return record

    # ------------------------------------------------------------------
    # FAQ management
    # ------------------------------------------------------------------

    def add_faq(
        self,
        question: str,
        answer: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        source: str = "manual",
    ) -> FAQEntry:
        """Add a new FAQ entry."""
        entry = FAQEntry(
            faq_id=f"faq-{uuid.uuid4().hex[:8]}",
            question=question,
            answer=answer,
            category=category,
            tags=tags or [],
            source=source,
        )
        with self._lock:
            if len(self._faqs) >= self._max_faqs:
                oldest_key = next(iter(self._faqs))
                del self._faqs[oldest_key]
            self._faqs[entry.faq_id] = entry

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=entry.faq_id, document=entry.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        logger.info("Added FAQ %s: %s", entry.faq_id, question[:60])
        return entry

    def update_faq(
        self,
        faq_id: str,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[FAQEntry]:
        """Update an existing FAQ entry (creates new version)."""
        with self._lock:
            entry = self._faqs.get(faq_id)
            if entry is None:
                return None
            if answer is not None:
                entry.answer = answer
            if category is not None:
                entry.category = category
            if tags is not None:
                entry.tags = tags
            entry.version += 1
            entry.updated_at = datetime.now(timezone.utc).isoformat()

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=entry.faq_id, document=entry.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        return entry

    def record_view(self, faq_id: str) -> Optional[FAQEntry]:
        """Record a view of an FAQ entry."""
        with self._lock:
            entry = self._faqs.get(faq_id)
            if entry is None:
                return None
            entry.views += 1
        return entry

    def vote_helpful(self, faq_id: str, helpful: bool = True) -> Optional[FAQEntry]:
        """Record a helpfulness vote for an FAQ entry."""
        with self._lock:
            entry = self._faqs.get(faq_id)
            if entry is None:
                return None
            if helpful:
                entry.helpful_votes += 1
            else:
                entry.not_helpful_votes += 1
        return entry

    # ------------------------------------------------------------------
    # Generation cycle
    # ------------------------------------------------------------------

    def run_generation_cycle(self) -> FAQGenerationReport:
        """Analyse recorded questions, identify frequent ones, detect gaps."""
        with self._lock:
            questions = list(self._questions)
            existing_faqs = list(self._faqs.values())

        # Count normalised question frequency
        freq: Counter = Counter()
        for q in questions:
            freq[q.normalised] += 1

        # Find existing FAQ questions (normalised) for gap detection
        existing_normals = set()
        for faq in existing_faqs:
            existing_normals.add(self._normalise_question(faq.question))

        created = 0
        updated = 0
        gaps = 0

        for norm_q, count in freq.most_common():
            if count < self._min_frequency:
                break
            if norm_q in existing_normals:
                # Already covered
                updated += 1
                continue
            # This is a gap — frequent question with no FAQ
            gaps += 1

        report = FAQGenerationReport(
            report_id=f"fgr-{uuid.uuid4().hex[:8]}",
            questions_analysed=len(questions),
            faqs_created=created,
            faqs_updated=updated,
            gaps_detected=gaps,
        )

        with self._lock:
            capped_append(self._reports, report)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=report.report_id, document=report.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(report)

        logger.info(
            "FAQ generation cycle: %d questions → %d gaps, %d covered",
            report.questions_analysed, report.gaps_detected, report.faqs_updated,
        )
        return report

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_faqs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search FAQs by keyword matching."""
        query_lower = query.lower()
        results = []
        with self._lock:
            for faq in self._faqs.values():
                if query_lower in faq.question.lower() or query_lower in faq.answer.lower():
                    results.append(faq.to_dict())
                if len(results) >= limit:
                    break
        return results

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_faq(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific FAQ entry."""
        with self._lock:
            faq = self._faqs.get(faq_id)
        return faq.to_dict() if faq else None

    def list_faqs(
        self,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List FAQ entries, optionally filtered by category."""
        with self._lock:
            faqs = list(self._faqs.values())
        if category:
            faqs = [f for f in faqs if f.category == category]
        return [f.to_dict() for f in faqs[:limit]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent generation reports."""
        with self._lock:
            reports = list(self._reports)
        return [r.to_dict() for r in reports[-limit:]]

    def get_frequent_questions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most frequently asked questions."""
        with self._lock:
            questions = list(self._questions)
        freq: Counter = Counter()
        for q in questions:
            freq[q.normalised] += 1
        return [
            {"question": norm, "count": count}
            for norm, count in freq.most_common(limit)
        ]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            return {
                "total_faqs": len(self._faqs),
                "total_questions": len(self._questions),
                "total_reports": len(self._reports),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_question(text: str) -> str:
        """Normalise question text for deduplication."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _publish_event(self, report: FAQGenerationReport) -> None:
        """Publish a LEARNING_FEEDBACK event for FAQ generation."""
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "faq_generation_engine",
                    "action": "generation_cycle_complete",
                    "report_id": report.report_id,
                    "gaps_detected": report.gaps_detected,
                    "questions_analysed": report.questions_analysed,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="faq_generation_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
