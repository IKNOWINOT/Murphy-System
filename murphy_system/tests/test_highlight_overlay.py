"""
Tests for HighlightOverlay — desktop highlight management for shadow agent
automation suggestions with right-click accept/ignore actions.

Design Label: TEST-HIGHLIGHT-OVERLAY-001
Owner: QA Team
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


from highlight_overlay import (
    HighlightedSuggestion,
    OverlayManager,
    SuggestionCategory,
    SuggestionState,
    TextRegion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mgr():
    return OverlayManager()


@pytest.fixture
def suggestion(mgr):
    return mgr.add_suggestion(
        agent_id="sa1",
        user_id="u1",
        highlighted_text="pytest tests/",
        title="Automate test run",
        description="You run pytest manually — automate it?",
        category=SuggestionCategory.AUTOMATION,
        confidence=0.85,
        automation_spec={"type": "schedule", "command": "pytest tests/"},
    )


# ---------------------------------------------------------------------------
# HighlightedSuggestion model
# ---------------------------------------------------------------------------


class TestHighlightedSuggestion:
    def test_defaults(self):
        sug = HighlightedSuggestion()
        assert sug.state == SuggestionState.PENDING
        assert sug.suggestion_id
        assert sug.confidence == 0.5

    def test_to_dict_keys(self):
        sug = HighlightedSuggestion(agent_id="sa1", user_id="u1", title="T")
        d = sug.to_dict()
        for key in ["suggestion_id", "agent_id", "user_id", "state",
                    "title", "description", "confidence", "automation_spec"]:
            assert key in d

    def test_text_region_serialised(self):
        region = TextRegion(selector="#terminalOutput", start_offset=10, end_offset=25)
        sug = HighlightedSuggestion(region=region)
        d = sug.to_dict()
        assert d["region"]["selector"] == "#terminalOutput"


# ---------------------------------------------------------------------------
# Adding suggestions
# ---------------------------------------------------------------------------


class TestAddSuggestion:
    def test_add_returns_suggestion(self, mgr):
        sug = mgr.add_suggestion(
            agent_id="sa1", user_id="u1",
            highlighted_text="git push",
            title="Automate git push",
            description="Push on save?",
        )
        assert isinstance(sug, HighlightedSuggestion)
        assert sug.state == SuggestionState.PENDING

    def test_confidence_clamped_to_0_1(self, mgr):
        sug = mgr.add_suggestion("sa", "u", "x", "T", "D", confidence=5.0)
        assert sug.confidence == 1.0
        sug2 = mgr.add_suggestion("sa", "u", "x", "T", "D", confidence=-3.0)
        assert sug2.confidence == 0.0

    def test_suggestion_appears_in_pending(self, mgr, suggestion):
        pending = mgr.get_pending_suggestions()
        ids = [s.suggestion_id for s in pending]
        assert suggestion.suggestion_id in ids

    def test_user_id_filter_works(self, mgr):
        mgr.add_suggestion("sa", "user_a", "text", "T", "D")
        mgr.add_suggestion("sa", "user_b", "text", "T", "D")
        pending_a = mgr.get_pending_suggestions(user_id="user_a")
        assert all(s.user_id == "user_a" for s in pending_a)

    def test_marketplace_listing_id_stored(self, mgr):
        sug = mgr.add_suggestion(
            "sa", "u1", "text", "T", "D",
            marketplace_listing_id="listing-abc",
        )
        assert sug.marketplace_listing_id == "listing-abc"


# ---------------------------------------------------------------------------
# Accept (right-click → "Accept and automate")
# ---------------------------------------------------------------------------


class TestAcceptSuggestion:
    def test_accept_transitions_to_accepted(self, mgr, suggestion):
        result = mgr.accept_suggestion(suggestion.suggestion_id, resolved_by="alice")
        assert result is True
        updated = mgr.get_suggestion(suggestion.suggestion_id)
        assert updated.state == SuggestionState.ACCEPTED
        assert updated.resolved_by == "alice"
        assert updated.resolved_at

    def test_accepted_not_in_pending(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        pending = mgr.get_pending_suggestions()
        assert not any(s.suggestion_id == suggestion.suggestion_id for s in pending)

    def test_accepted_appears_in_accepted_list(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        accepted = mgr.get_accepted_suggestions()
        assert any(s.suggestion_id == suggestion.suggestion_id for s in accepted)

    def test_accept_unknown_returns_false(self, mgr):
        assert mgr.accept_suggestion("notexist") is False

    def test_double_accept_returns_false(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        assert mgr.accept_suggestion(suggestion.suggestion_id) is False

    def test_user_id_filter_for_accepted(self, mgr):
        s1 = mgr.add_suggestion("sa", "u1", "t", "T", "D")
        s2 = mgr.add_suggestion("sa", "u2", "t", "T", "D")
        mgr.accept_suggestion(s1.suggestion_id)
        mgr.accept_suggestion(s2.suggestion_id)
        accepted_u1 = mgr.get_accepted_suggestions(user_id="u1")
        assert all(s.user_id == "u1" for s in accepted_u1)


# ---------------------------------------------------------------------------
# Ignore (right-click → "Ignore this suggestion")
# ---------------------------------------------------------------------------


class TestIgnoreSuggestion:
    def test_ignore_transitions_to_ignored(self, mgr, suggestion):
        result = mgr.ignore_suggestion(suggestion.suggestion_id, resolved_by="bob")
        assert result is True
        updated = mgr.get_suggestion(suggestion.suggestion_id)
        assert updated.state == SuggestionState.IGNORED
        assert updated.resolved_by == "bob"

    def test_ignored_not_in_pending(self, mgr, suggestion):
        mgr.ignore_suggestion(suggestion.suggestion_id)
        pending = mgr.get_pending_suggestions()
        assert not any(s.suggestion_id == suggestion.suggestion_id for s in pending)

    def test_ignore_unknown_returns_false(self, mgr):
        assert mgr.ignore_suggestion("notexist") is False

    def test_cannot_ignore_accepted_suggestion(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        assert mgr.ignore_suggestion(suggestion.suggestion_id) is False


# ---------------------------------------------------------------------------
# Expire
# ---------------------------------------------------------------------------


class TestExpireSuggestion:
    def test_expire_transitions_to_expired(self, mgr, suggestion):
        result = mgr.expire_suggestion(suggestion.suggestion_id)
        assert result is True
        updated = mgr.get_suggestion(suggestion.suggestion_id)
        assert updated.state == SuggestionState.EXPIRED

    def test_expire_already_accepted_returns_false(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        assert mgr.expire_suggestion(suggestion.suggestion_id) is False


# ---------------------------------------------------------------------------
# Marketplace matches
# ---------------------------------------------------------------------------


class TestMarketplaceMatches:
    def test_returns_empty_when_no_listing(self, mgr, suggestion):
        matches = mgr.get_marketplace_matches(suggestion.suggestion_id)
        assert matches == []

    def test_returns_listing_id_when_linked(self, mgr):
        sug = mgr.add_suggestion(
            "sa", "u1", "text", "T", "D",
            marketplace_listing_id="listing-xyz",
        )
        matches = mgr.get_marketplace_matches(sug.suggestion_id)
        assert "listing-xyz" in matches

    def test_returns_empty_for_unknown_suggestion(self, mgr):
        assert mgr.get_marketplace_matches("bad-id") == []


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_counts_states(self, mgr):
        s1 = mgr.add_suggestion("sa", "u1", "t", "T", "D")
        s2 = mgr.add_suggestion("sa", "u1", "t", "T", "D")
        mgr.accept_suggestion(s1.suggestion_id)
        summary = mgr.summary(user_id="u1")
        assert summary["total"] == 2
        assert summary["by_state"]["pending"] == 1
        assert summary["by_state"]["accepted"] == 1

    def test_summary_no_filter(self, mgr):
        mgr.add_suggestion("sa", "u1", "t", "T", "D")
        mgr.add_suggestion("sa", "u2", "t", "T", "D")
        summary = mgr.summary()
        assert summary["total"] == 2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_add_and_accept(self, mgr):
        suggestions = []
        for i in range(20):
            s = mgr.add_suggestion("sa", f"u{i}", f"text{i}", f"T{i}", "D")
            suggestions.append(s)

        def accept_half(idx):
            if idx % 2 == 0:
                mgr.accept_suggestion(suggestions[idx].suggestion_id)
            else:
                mgr.ignore_suggestion(suggestions[idx].suggestion_id)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(accept_half, i) for i in range(20)]
            for f in futs:
                f.result()

        summary = mgr.summary()
        # All 20 should be resolved — none should still be pending
        assert summary["by_state"]["pending"] == 0
        assert summary["by_state"]["accepted"] == 10
        assert summary["by_state"]["ignored"] == 10


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_add_suggestion_audited(self, mgr):
        before = len(mgr.get_audit_log())
        mgr.add_suggestion("sa", "u1", "t", "T", "D")
        assert len(mgr.get_audit_log()) > before

    def test_accept_audited(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        actions = [e["action"] for e in mgr.get_audit_log()]
        assert "accept_suggestion" in actions

    def test_ignore_audited(self, mgr, suggestion):
        mgr.ignore_suggestion(suggestion.suggestion_id)
        actions = [e["action"] for e in mgr.get_audit_log()]
        assert "ignore_suggestion" in actions

    def test_audit_entries_have_timestamp(self, mgr, suggestion):
        mgr.accept_suggestion(suggestion.suggestion_id)
        for entry in mgr.get_audit_log():
            assert "timestamp" in entry
