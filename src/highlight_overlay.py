"""
Highlight Overlay — Murphy System

Manages the shadow agent's "highlight" layer: a catalogue of in-context
automation suggestions surfaced as highlighted text regions.  The backend
tracks every suggestion so the frontend (murphy_overlay.js) can render
coloured highlights and right-click menus without any state stored only
in the browser.

Right-click behaviour (handled by murphy_overlay.js, data served here):
  - "Ignore this suggestion"  → ignore_suggestion(suggestion_id)
  - "Accept and automate"     → accept_suggestion(suggestion_id)
  - "View similar in marketplace" → get_marketplace_matches(suggestion_id)

Accepted suggestions are forwarded to the AutomationMarketplace for
community reuse tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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

_MAX_SUGGESTIONS = 5_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SuggestionState(str, Enum):
    """Lifecycle state of a UI suggestion shown in the highlight overlay."""
    PENDING = "pending"     # shown in overlay, awaiting user action
    ACCEPTED = "accepted"   # user accepted via right-click
    IGNORED = "ignored"     # user dismissed via right-click
    EXPIRED = "expired"     # no longer relevant


class SuggestionCategory(str, Enum):
    """Category of automation suggestion surfaced by the highlight overlay."""
    AUTOMATION = "automation"           # "automate this repeated action"
    API_CALL = "api_call"               # "fill and submit this API request"
    WORKFLOW = "workflow"               # "build a workflow from this pattern"
    DOCUMENTATION = "documentation"    # "document this process"
    MARKETPLACE = "marketplace"        # "this is already in the catalogue"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TextRegion:
    """The on-screen region associated with a highlight."""

    selector: str = ""          # CSS selector of the element containing the text
    start_offset: int = 0       # character offset within the element
    end_offset: int = 0         # character offset (exclusive)
    page_url: str = ""          # URL of the page where the highlight appears

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selector": self.selector,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "page_url": self.page_url,
        }


@dataclass
class HighlightedSuggestion:
    """A shadow agent suggestion surfaced as a desktop highlight."""

    suggestion_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""                          # shadow agent that created it
    user_id: str = ""
    category: SuggestionCategory = SuggestionCategory.AUTOMATION
    title: str = ""
    description: str = ""
    highlighted_text: str = ""                  # the text that is highlighted
    region: Optional[TextRegion] = None         # where on screen
    state: SuggestionState = SuggestionState.PENDING
    confidence: float = 0.5                     # 0.0-1.0 — how confident the agent is
    automation_spec: Optional[Dict[str, Any]] = None  # the proposed automation
    marketplace_listing_id: Optional[str] = None      # linked marketplace entry
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    resolved_at: str = ""
    resolved_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "highlighted_text": self.highlighted_text,
            "region": self.region.to_dict() if self.region else None,
            "state": self.state.value,
            "confidence": self.confidence,
            "automation_spec": self.automation_spec,
            "marketplace_listing_id": self.marketplace_listing_id,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }


# ---------------------------------------------------------------------------
# OverlayManager
# ---------------------------------------------------------------------------


class OverlayManager:
    """Backend state manager for the highlight overlay system.

    The frontend (murphy_overlay.js) polls/websocket-connects to get the
    current suggestion list and posts user actions (accept/ignore) back.

    Usage::

        mgr = OverlayManager()

        # Shadow agent surfaced a suggestion
        sug = mgr.add_suggestion(
            agent_id="sa1", user_id="u1",
            highlighted_text="run pytest",
            title="Automate test run",
            description="You run pytest manually every hour — automate it?",
            automation_spec={"type": "schedule", "command": "pytest"},
        )

        # User right-clicked → "Accept and automate"
        mgr.accept_suggestion(sug.suggestion_id, resolved_by="alice")

        # Collect accepted suggestions for the automation pipeline
        accepted = mgr.get_accepted_suggestions()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._suggestions: Dict[str, HighlightedSuggestion] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Adding suggestions
    # ------------------------------------------------------------------

    def add_suggestion(
        self,
        agent_id: str,
        user_id: str,
        highlighted_text: str,
        title: str,
        description: str,
        category: SuggestionCategory = SuggestionCategory.AUTOMATION,
        confidence: float = 0.5,
        automation_spec: Optional[Dict[str, Any]] = None,
        region: Optional[TextRegion] = None,
        marketplace_listing_id: Optional[str] = None,
    ) -> HighlightedSuggestion:
        """Create and store a new highlight suggestion."""
        suggestion = HighlightedSuggestion(
            agent_id=agent_id,
            user_id=user_id,
            category=category,
            title=title,
            description=description,
            highlighted_text=highlighted_text,
            region=region,
            confidence=min(max(confidence, 0.0), 1.0),
            automation_spec=automation_spec,
            marketplace_listing_id=marketplace_listing_id,
        )

        with self._lock:
            self._suggestions[suggestion.suggestion_id] = suggestion
            self._log_audit("add_suggestion", suggestion.suggestion_id, {
                "agent_id": agent_id,
                "user_id": user_id,
                "category": category.value,
            })

        logger.debug(
            "Overlay suggestion added: %s (%s) confidence=%.2f",
            suggestion.suggestion_id,
            title,
            confidence,
        )
        return suggestion

    # ------------------------------------------------------------------
    # User right-click actions
    # ------------------------------------------------------------------

    def accept_suggestion(
        self,
        suggestion_id: str,
        resolved_by: str = "user",
    ) -> bool:
        """User accepted the suggestion via right-click.

        Returns True if found and transitioned to ACCEPTED.
        """
        with self._lock:
            sug = self._suggestions.get(suggestion_id)
            if sug is None or sug.state != SuggestionState.PENDING:
                return False
            sug.state = SuggestionState.ACCEPTED
            sug.resolved_at = datetime.now(timezone.utc).isoformat()
            sug.resolved_by = resolved_by
            self._log_audit("accept_suggestion", suggestion_id, {"resolved_by": resolved_by})

        logger.info("Suggestion %s accepted by %s", suggestion_id, resolved_by)
        return True

    def ignore_suggestion(
        self,
        suggestion_id: str,
        resolved_by: str = "user",
    ) -> bool:
        """User ignored the suggestion via right-click.

        Returns True if found and transitioned to IGNORED.
        """
        with self._lock:
            sug = self._suggestions.get(suggestion_id)
            if sug is None or sug.state != SuggestionState.PENDING:
                return False
            sug.state = SuggestionState.IGNORED
            sug.resolved_at = datetime.now(timezone.utc).isoformat()
            sug.resolved_by = resolved_by
            self._log_audit("ignore_suggestion", suggestion_id, {"resolved_by": resolved_by})

        logger.info("Suggestion %s ignored by %s", suggestion_id, resolved_by)
        return True

    def expire_suggestion(self, suggestion_id: str) -> bool:
        """Mark a suggestion as expired (no longer relevant)."""
        with self._lock:
            sug = self._suggestions.get(suggestion_id)
            if sug is None or sug.state != SuggestionState.PENDING:
                return False
            sug.state = SuggestionState.EXPIRED
            sug.resolved_at = datetime.now(timezone.utc).isoformat()
            self._log_audit("expire_suggestion", suggestion_id, {})
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_pending_suggestions(self, user_id: Optional[str] = None) -> List[HighlightedSuggestion]:
        """Return all PENDING suggestions, optionally filtered by user."""
        with self._lock:
            return [
                s for s in self._suggestions.values()
                if s.state == SuggestionState.PENDING
                and (user_id is None or s.user_id == user_id)
            ]

    def get_accepted_suggestions(self, user_id: Optional[str] = None) -> List[HighlightedSuggestion]:
        """Return all ACCEPTED suggestions, ready for the automation pipeline."""
        with self._lock:
            return [
                s for s in self._suggestions.values()
                if s.state == SuggestionState.ACCEPTED
                and (user_id is None or s.user_id == user_id)
            ]

    def get_suggestion(self, suggestion_id: str) -> Optional[HighlightedSuggestion]:
        with self._lock:
            return self._suggestions.get(suggestion_id)

    def get_marketplace_matches(
        self,
        suggestion_id: str,
    ) -> List[str]:
        """Return marketplace listing IDs that are similar to this suggestion.

        In production this calls AutomationMarketplace.search(); here we
        return the directly linked listing (if any).
        """
        with self._lock:
            sug = self._suggestions.get(suggestion_id)
        if sug is None:
            return []
        if sug.marketplace_listing_id:
            return [sug.marketplace_listing_id]
        return []

    def summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Return a stats summary suitable for the overlay status bar."""
        with self._lock:
            relevant = [
                s for s in self._suggestions.values()
                if user_id is None or s.user_id == user_id
            ]
        counts = {state.value: 0 for state in SuggestionState}
        for s in relevant:
            counts[s.state.value] += 1
        return {
            "total": len(relevant),
            "by_state": counts,
            "pending": counts[SuggestionState.PENDING.value],
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_audit(self, action: str, suggestion_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "suggestion_id": suggestion_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        capped_append(self._audit_log, entry, max_size=_MAX_SUGGESTIONS)
