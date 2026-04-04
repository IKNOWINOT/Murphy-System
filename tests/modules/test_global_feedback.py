# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: tests/test_global_feedback.py
Subsystem: Global Feedback System
Label: TEST-GFB — Commission tests for Global Feedback System

Commissioning Answers
---------------------
1. Does this do what it was designed to do?
   YES — validates models, remediation engine, dispatcher pipeline,
   severity escalation, subsystem classification, guiding questions,
   store eviction, resolution, and GitHub dispatch.

2. What is it supposed to do?
   Prove that the Global Feedback System correctly collects, validates,
   categorises, analyses, and dispatches feedback for automated patching.

3. What conditions are possible?
   - Valid/invalid submissions (title too short, desc too short)
   - All severity levels and sources
   - Keyword-based subsystem identification (UI, API, auth, etc.)
   - Severity escalation via content keywords
   - Remediation plan generation with 7 guiding questions
   - Dispatcher submit/get/list/stats/resolve lifecycle
   - Store eviction at max capacity (CWE-770)
   - GitHub dispatch without token, without httpx
   - Label computation from submission + plan

4. Does the test profile reflect the full range?
   YES — 40+ tests covering all paths.

5. Expected result?  All tests pass.
6. Actual result?  Verified locally.
7. Restart?  Run: pytest tests/test_global_feedback.py -v
8. Docs updated?  YES.
9. Hardening?  Input validation tested with boundary values.
10. Re-commissioned?  YES.
"""
from __future__ import annotations

import pytest

from src.global_feedback.models import (
    FeedbackSeverity,
    FeedbackSource,
    GlobalFeedbackStatus,
    GlobalFeedbackSubmission,
    GitHubPatchPayload,
    RemediationPlan,
    RemediationStep,
)
from src.global_feedback.remediation_engine import RemediationEngine, _sev_rank
from src.global_feedback.dispatcher import GlobalFeedbackDispatcher


# ==========================================================================
# Helpers
# ==========================================================================

def _make_submission(**overrides) -> GlobalFeedbackSubmission:
    """Create a valid submission with sensible defaults."""
    defaults = dict(
        user_id="tester@example.com",
        title="Button does not render correctly",
        description="The submit button on the feedback form is invisible on dark theme.",
        severity=FeedbackSeverity.MEDIUM,
        source=FeedbackSource.WEBSITE_WIDGET,
    )
    defaults.update(overrides)
    return GlobalFeedbackSubmission(**defaults)


# ==========================================================================
# GFB-001: Model tests
# ==========================================================================

class TestGlobalFeedbackModels:
    """G1: Models do what they were designed to do — validate & store feedback."""

    def test_submission_defaults(self):
        """G2: Submission auto-generates id, status, submitted_at."""
        sub = _make_submission()
        assert sub.id.startswith("gfb-")
        assert sub.status == GlobalFeedbackStatus.SUBMITTED
        assert sub.submitted_at is not None
        assert sub.remediation_plan_id is None

    def test_submission_custom_fields(self):
        """G3: All optional fields are settable."""
        sub = _make_submission(
            page_url="https://example.com/dashboard",
            component="DashboardWidget",
            steps_to_reproduce="1. Open dashboard\n2. Click button",
            expected_behavior="Button should be visible",
            actual_behavior="Button is invisible",
            console_errors="TypeError: null is not an object",
            tags=["ui", "dark-theme"],
            affected_modules=["ui_frontend"],
            tenant_id="tenant-001",
            user_agent="Mozilla/5.0",
            metadata={"build": "v3.1"},
        )
        assert sub.page_url == "https://example.com/dashboard"
        assert sub.component == "DashboardWidget"
        assert "dark-theme" in sub.tags
        assert sub.tenant_id == "tenant-001"

    def test_submission_title_too_short(self):
        """G3: Title validation rejects < 5 chars."""
        with pytest.raises(Exception):
            _make_submission(title="Hi")

    def test_submission_title_whitespace_strip(self):
        """G3: Title is stripped; fails if result < 5."""
        with pytest.raises(Exception):
            _make_submission(title="   ab   ")

    def test_submission_title_valid_after_strip(self):
        """G3: Title with leading/trailing whitespace passes if >= 5 after strip."""
        sub = _make_submission(title="  Valid Title  ")
        assert sub.title == "Valid Title"

    def test_submission_description_too_short(self):
        """G3: Description < 10 chars after strip fails."""
        with pytest.raises(Exception):
            _make_submission(description="Short")

    def test_severity_enum_values(self):
        """G2: All severity values are valid strings."""
        assert FeedbackSeverity.CRITICAL.value == "critical"
        assert FeedbackSeverity.INFO.value == "info"

    def test_source_enum_values(self):
        """G2: All source values present."""
        sources = [s.value for s in FeedbackSource]
        assert "website_widget" in sources
        assert "api_direct" in sources
        assert "cli" in sources

    def test_status_lifecycle_values(self):
        """G2: All lifecycle states present."""
        statuses = [s.value for s in GlobalFeedbackStatus]
        assert "submitted" in statuses
        assert "dispatched_to_github" in statuses
        assert "resolved" in statuses

    def test_remediation_step_model(self):
        """G2: RemediationStep holds step metadata."""
        step = RemediationStep(
            step_number=1,
            action="Fix the bug",
            rationale="It is broken",
            guiding_question="Q1",
            estimated_impact="high",
        )
        assert step.step_number == 1
        assert step.guiding_question == "Q1"

    def test_remediation_plan_defaults(self):
        """G2: RemediationPlan auto-generates id and timestamps."""
        plan = RemediationPlan(
            feedback_id="gfb-test123",
            root_cause="Missing CSS rule",
            affected_subsystem="ui_frontend",
            severity_assessment=FeedbackSeverity.MEDIUM,
        )
        assert plan.id.startswith("rem-")
        assert plan.created_at is not None
        assert plan.hardening_applied is False

    def test_github_patch_payload(self):
        """G2: GitHubPatchPayload serialises correctly."""
        payload = GitHubPatchPayload(
            feedback_id="gfb-abc",
            remediation_plan_id="rem-def",
            title="Fix button",
            description="Button invisible",
            severity=FeedbackSeverity.HIGH,
            root_cause="CSS z-index",
            affected_subsystem="ui_frontend",
            steps=[{"step_number": 1, "action": "fix"}],
            labels=["feedback-patch"],
        )
        assert payload.feedback_id == "gfb-abc"
        d = payload.model_dump()
        assert "feedback_id" in d
        assert isinstance(d["steps"], list)


# ==========================================================================
# GFB-003: Remediation Engine tests
# ==========================================================================

class TestRemediationEngine:
    """G1: Engine analyses feedback and produces remediation plans."""

    def setup_method(self):
        self.engine = RemediationEngine()

    def test_analyse_returns_plan(self):
        """G1: analyse() produces a RemediationPlan."""
        sub = _make_submission()
        plan = self.engine.analyse(sub)
        assert isinstance(plan, RemediationPlan)
        assert plan.feedback_id == sub.id

    def test_plan_has_7_steps(self):
        """G4: Standard analysis produces 7 remediation steps."""
        sub = _make_submission()
        plan = self.engine.analyse(sub)
        assert len(plan.steps) == 7

    def test_plan_has_guiding_answers(self):
        """G4: All 7 guiding questions answered."""
        sub = _make_submission()
        plan = self.engine.analyse(sub)
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]:
            assert q in plan.guiding_answers

    def test_subsystem_ui_keywords(self):
        """G3: UI keywords map to ui_frontend subsystem."""
        sub = _make_submission(title="Button render broken on page")
        plan = self.engine.analyse(sub)
        assert plan.affected_subsystem == "ui_frontend"

    def test_subsystem_api_keywords(self):
        """G3: API keywords map to api_backend subsystem."""
        sub = _make_submission(
            title="Endpoint returns 500 error",
            description="The /api/feedback endpoint fails with a timeout on every request.",
        )
        plan = self.engine.analyse(sub)
        assert plan.affected_subsystem == "api_backend"

    def test_subsystem_auth_keywords(self):
        """G3: Auth keywords map to authentication subsystem."""
        sub = _make_submission(
            title="Login fails with wrong password",
            description="When entering the correct password, login page says access denied.",
        )
        plan = self.engine.analyse(sub)
        assert plan.affected_subsystem == "authentication"

    def test_subsystem_unclassified(self):
        """G3: Unknown content maps to unclassified."""
        sub = _make_submission(
            title="Something is wrong with foobar",
            description="The foobar zygomorphic transducer is malfunctioning.",
        )
        plan = self.engine.analyse(sub)
        assert plan.affected_subsystem == "unclassified"

    def test_subsystem_from_affected_modules(self):
        """G3: If affected_modules set, use that directly."""
        sub = _make_submission(affected_modules=["custom_module"])
        plan = self.engine.analyse(sub)
        assert plan.affected_subsystem == "custom_module"

    def test_severity_escalation_critical(self):
        """G3: Content with 'crash' escalates to CRITICAL."""
        sub = _make_submission(
            severity=FeedbackSeverity.LOW,
            title="System crash on startup",
            description="The application crashes immediately when opened.",
        )
        plan = self.engine.analyse(sub)
        assert plan.severity_assessment == FeedbackSeverity.CRITICAL

    def test_severity_escalation_high(self):
        """G3: Content with 'broken' escalates to HIGH."""
        sub = _make_submission(
            severity=FeedbackSeverity.LOW,
            title="Feature is completely broken",
            description="The calendar feature cannot load any data.",
        )
        plan = self.engine.analyse(sub)
        assert plan.severity_assessment == FeedbackSeverity.HIGH

    def test_severity_no_escalation(self):
        """G3: Normal content doesn't escalate."""
        sub = _make_submission(
            severity=FeedbackSeverity.MEDIUM,
            title="Minor alignment issue",
            description="Text in the sidebar is slightly misaligned on mobile view.",
        )
        plan = self.engine.analyse(sub)
        assert plan.severity_assessment == FeedbackSeverity.MEDIUM

    def test_expected_vs_actual_populated(self):
        """G5/G6: When both expected and actual are provided, field is populated."""
        sub = _make_submission(
            expected_behavior="Button should be blue",
            actual_behavior="Button is red",
        )
        plan = self.engine.analyse(sub)
        assert plan.expected_vs_actual is not None
        assert "Expected:" in plan.expected_vs_actual
        assert "Actual:" in plan.expected_vs_actual

    def test_expected_vs_actual_none_when_missing(self):
        """G5/G6: When expected/actual not provided, field is None."""
        sub = _make_submission()
        plan = self.engine.analyse(sub)
        assert plan.expected_vs_actual is None

    def test_conditions_reproducible(self):
        """G3: Steps to reproduce adds condition."""
        sub = _make_submission(steps_to_reproduce="1. Click button")
        plan = self.engine.analyse(sub)
        assert "reproducible_via_steps" in plan.conditions_identified

    def test_conditions_console_errors(self):
        """G3: Console errors adds condition."""
        sub = _make_submission(console_errors="TypeError: null")
        plan = self.engine.analyse(sub)
        assert "console_errors_present" in plan.conditions_identified

    def test_conditions_high_severity(self):
        """G3: HIGH severity adds condition."""
        sub = _make_submission(severity=FeedbackSeverity.HIGH)
        plan = self.engine.analyse(sub)
        assert "high_severity" in plan.conditions_identified

    def test_recommission_required_for_critical(self):
        """G7: CRITICAL severity requires recommission."""
        sub = _make_submission(
            severity=FeedbackSeverity.LOW,
            title="Production crash data loss incident",
            description="Data loss occurred when the crash happened.",
        )
        plan = self.engine.analyse(sub)
        assert plan.recommission_required is True

    def test_sev_rank_ordering(self):
        """G2: _sev_rank gives correct ordering."""
        assert _sev_rank(FeedbackSeverity.INFO) < _sev_rank(FeedbackSeverity.LOW)
        assert _sev_rank(FeedbackSeverity.LOW) < _sev_rank(FeedbackSeverity.MEDIUM)
        assert _sev_rank(FeedbackSeverity.MEDIUM) < _sev_rank(FeedbackSeverity.HIGH)
        assert _sev_rank(FeedbackSeverity.HIGH) < _sev_rank(FeedbackSeverity.CRITICAL)


# ==========================================================================
# GFB-002: Dispatcher tests
# ==========================================================================

class TestGlobalFeedbackDispatcher:
    """G1: Dispatcher orchestrates the full feedback lifecycle."""

    def setup_method(self):
        self.dispatcher = GlobalFeedbackDispatcher(
            github_token="",  # no real calls
            max_store_size=100,
        )

    def test_submit_returns_submission(self):
        """G1: submit() returns a valid submission."""
        sub = self.dispatcher.submit(
            user_id="user1",
            title="Button not clickable",
            description="The submit button on the feedback form does not respond to clicks.",
        )
        assert sub.id.startswith("gfb-")
        assert sub.status == GlobalFeedbackStatus.REMEDIATION_PLANNED
        assert sub.remediation_plan_id is not None

    def test_get_retrieves_submission(self):
        """G1: get() returns previously submitted feedback."""
        sub = self.dispatcher.submit(
            user_id="user2",
            title="Dashboard loading slowly",
            description="The main dashboard takes over 30 seconds to render completely.",
        )
        retrieved = self.dispatcher.get(sub.id)
        assert retrieved is not None
        assert retrieved.id == sub.id

    def test_get_nonexistent_returns_none(self):
        """G3: get() returns None for missing ID."""
        assert self.dispatcher.get("gfb-nonexistent") is None

    def test_get_plan_for_feedback(self):
        """G1: get_plan_for_feedback() returns the associated plan."""
        sub = self.dispatcher.submit(
            user_id="user3",
            title="Calendar shows wrong dates",
            description="The calendar component displays dates that are one day off.",
        )
        plan = self.dispatcher.get_plan_for_feedback(sub.id)
        assert plan is not None
        assert plan.feedback_id == sub.id

    def test_list_submissions_empty(self):
        """G3: list_submissions() on empty store returns []."""
        d = GlobalFeedbackDispatcher(github_token="")
        assert d.list_submissions() == []

    def test_list_submissions_with_data(self):
        """G1: list_submissions() returns submitted items."""
        self.dispatcher.submit(
            user_id="u1",
            title="Issue one is here",
            description="First issue description that is long enough.",
        )
        self.dispatcher.submit(
            user_id="u2",
            title="Issue two is here",
            description="Second issue description that is long enough.",
        )
        items = self.dispatcher.list_submissions()
        assert len(items) == 2

    def test_list_submissions_filter_severity(self):
        """G3: list_submissions() filters by severity."""
        self.dispatcher.submit(
            user_id="u1",
            title="Low severity issue placeholder",
            description="This is a low severity feedback submission test.",
            severity="low",
        )
        self.dispatcher.submit(
            user_id="u2",
            title="High severity issue placeholder",
            description="This is a high severity feedback submission test.",
            severity="high",
        )
        items = self.dispatcher.list_submissions(severity="low")
        assert all(i["severity"] == "low" for i in items)

    def test_stats(self):
        """G1: stats() returns aggregate counts."""
        self.dispatcher.submit(
            user_id="u1",
            title="Stats test issue one",
            description="Testing statistics aggregation for feedback.",
        )
        st = self.dispatcher.stats()
        assert st["total"] == 1
        assert st["plans_generated"] == 1

    def test_resolve_marks_resolved(self):
        """G1: resolve() transitions status to RESOLVED."""
        sub = self.dispatcher.submit(
            user_id="u1",
            title="Resolvable issue here",
            description="This issue will be resolved in the test.",
        )
        result = self.dispatcher.resolve(sub.id, github_issue_url="https://github.com/issue/1")
        assert result is True
        retrieved = self.dispatcher.get(sub.id)
        assert retrieved.status == GlobalFeedbackStatus.RESOLVED
        assert retrieved.github_issue_url == "https://github.com/issue/1"
        assert retrieved.resolved_at is not None

    def test_resolve_nonexistent_returns_false(self):
        """G3: resolve() returns False for missing ID."""
        assert self.dispatcher.resolve("gfb-noexist") is False

    def test_store_eviction(self):
        """G9: Store evicts oldest when at max capacity (CWE-770)."""
        small = GlobalFeedbackDispatcher(github_token="", max_store_size=3)
        ids = []
        for i in range(5):
            sub = small.submit(
                user_id=f"user{i}",
                title=f"Eviction test item number {i}",
                description=f"This is eviction test submission number {i} for store.",
            )
            ids.append(sub.id)
        # Only 3 should remain (most recent)
        remaining = small.list_submissions(limit=100)
        assert len(remaining) == 3
        # First two evicted
        assert small.get(ids[0]) is None
        assert small.get(ids[1]) is None
        # Last three still present
        assert small.get(ids[2]) is not None

    def test_dispatch_no_token(self):
        """G3: dispatch without token returns failure or deferred (httpx unavailable)."""
        sub = self.dispatcher.submit(
            user_id="u1",
            title="Dispatch test without token",
            description="Testing GitHub dispatch without a valid token.",
        )
        result = self.dispatcher.dispatch_to_github(sub.id)
        # Without httpx, dispatch is recorded but not sent (success=True, dispatched=False)
        # With httpx but no token, success=False with GITHUB_TOKEN error
        if result.get("dispatched") is False:
            # httpx unavailable path
            assert result["success"] is True
            assert result["reason"] == "httpx_unavailable"
        else:
            # token missing path
            assert result["success"] is False
            assert "GITHUB_TOKEN" in result["error"]

    def test_dispatch_nonexistent(self):
        """G3: dispatch for missing feedback returns failure."""
        result = self.dispatcher.dispatch_to_github("gfb-noexist")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_label_computation(self):
        """G2: Labels include severity, subsystem, source."""
        sub = _make_submission(tags=["ui", "dark-theme"])
        plan = RemediationPlan(
            feedback_id=sub.id,
            root_cause="test",
            affected_subsystem="ui_frontend",
            severity_assessment=FeedbackSeverity.HIGH,
        )
        labels = GlobalFeedbackDispatcher._compute_labels(sub, plan)
        assert "feedback-patch" in labels
        assert "severity:high" in labels
        assert "subsystem:ui_frontend" in labels
        assert "source:website_widget" in labels
        assert "ui" in labels
        assert "dark-theme" in labels

    def test_submit_with_all_sources(self):
        """G3: All FeedbackSource values accepted."""
        for source in FeedbackSource:
            sub = self.dispatcher.submit(
                user_id="u1",
                title=f"Source test for {source.value}",
                description=f"Testing feedback source {source.value} submission.",
                source=source.value,
            )
            assert sub.source == source

    def test_submit_with_all_severities(self):
        """G3: All FeedbackSeverity values accepted."""
        for sev in FeedbackSeverity:
            sub = self.dispatcher.submit(
                user_id="u1",
                title=f"Severity test for {sev.value}",
                description=f"Testing feedback severity {sev.value} submission.",
                severity=sev.value,
            )
            assert sub.severity == sev
