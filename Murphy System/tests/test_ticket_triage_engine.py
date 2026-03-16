"""
Tests for SUP-001: TicketTriageEngine.

Validates severity classification, category classification, team routing,
TicketingAdapter integration, and EventBackbone event publishing.

Design Label: TEST-003 / SUP-001
Owner: QA Team
"""

import os
import pytest


from ticket_triage_engine import TicketTriageEngine, TriageResult
from ticketing_adapter import TicketingAdapter, TicketStatus
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def adapter():
    return TicketingAdapter()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def engine():
    return TicketTriageEngine()


@pytest.fixture
def wired_engine(adapter, backbone):
    return TicketTriageEngine(
        ticketing_adapter=adapter,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Severity classification
# ------------------------------------------------------------------

class TestSeverityClassification:
    def test_critical_keywords(self, engine):
        result = engine.triage(
            title="Production database outage",
            description="The main database cluster is completely down",
        )
        assert result.severity == "critical"

    def test_high_keywords(self, engine):
        result = engine.triage(
            title="Login error",
            description="Users are getting timeout errors on the login page",
        )
        assert result.severity == "high"

    def test_medium_default(self, engine):
        result = engine.triage(
            title="Something seems off",
            description="There is an issue with the reporting module",
        )
        assert result.severity == "medium"

    def test_low_keywords(self, engine):
        result = engine.triage(
            title="Feature request",
            description="Can we add dark mode? This is a minor enhancement.",
        )
        assert result.severity == "low"


# ------------------------------------------------------------------
# Category classification
# ------------------------------------------------------------------

class TestCategoryClassification:
    def test_incident_category(self, engine):
        result = engine.triage(
            title="Server crash",
            description="The API server crashed and is unresponsive",
        )
        assert result.category == "incident"

    def test_service_request_category(self, engine):
        result = engine.triage(
            title="New employee onboarding",
            description="Please setup access and provision accounts for new hire",
        )
        assert result.category == "service_request"

    def test_change_request_category(self, engine):
        result = engine.triage(
            title="Deploy new version",
            description="We need to deploy the latest release to production",
        )
        assert result.category == "change_request"

    def test_problem_category(self, engine):
        result = engine.triage(
            title="Recurring failure investigation",
            description="We need root cause analysis on the recurring pattern",
        )
        assert result.category == "problem"


# ------------------------------------------------------------------
# Team routing
# ------------------------------------------------------------------

class TestTeamRouting:
    def test_incident_routes_to_ops(self, engine):
        result = engine.triage(
            title="Server outage",
            description="Complete server crash detected",
        )
        assert result.suggested_team == "ops-engineering"

    def test_service_request_routes_to_desk(self, engine):
        result = engine.triage(
            title="Access request",
            description="Need to provision new user access",
        )
        assert result.suggested_team == "service-desk"


# ------------------------------------------------------------------
# TicketingAdapter integration
# ------------------------------------------------------------------

class TestAdapterIntegration:
    def test_creates_ticket_in_adapter(self, wired_engine, adapter):
        result = wired_engine.triage(
            title="Database error",
            description="Connection timeout errors in production",
            requester="ops@test.com",
        )
        assert result.ticket_id is not None
        ticket = adapter.get_ticket(result.ticket_id)
        assert ticket is not None
        assert ticket.requester == "ops@test.com"
        assert ticket.metadata.get("triage_severity") is not None

    def test_no_ticket_without_adapter(self, engine):
        result = engine.triage(
            title="Some issue",
            description="Details here",
        )
        assert result.ticket_id is None


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_publishes_learning_feedback(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.triage(
            title="Error detected",
            description="Something broken",
        )
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "ticket_triage_engine"


# ------------------------------------------------------------------
# Confidence scoring
# ------------------------------------------------------------------

class TestConfidence:
    def test_confidence_range(self, engine):
        result = engine.triage(
            title="Something happened",
            description="Not sure what",
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_high_confidence_on_clear_keywords(self, engine):
        result = engine.triage(
            title="Critical production outage emergency",
            description="The system is completely down and crashed",
        )
        assert result.confidence >= 0.4


# ------------------------------------------------------------------
# History / Status
# ------------------------------------------------------------------

class TestHistoryAndStatus:
    def test_history_accumulates(self, engine):
        engine.triage(title="T1", description="D1")
        engine.triage(title="T2", description="D2")
        history = engine.get_history()
        assert len(history) == 2

    def test_status_reflects_state(self, engine):
        engine.triage(title="Error crash", description="Server crash")
        status = engine.get_status()
        assert status["total_triaged"] == 1
        assert "critical" in status["severity_distribution"] or "high" in status["severity_distribution"]

    def test_triage_result_to_dict(self, engine):
        result = engine.triage(title="Test", description="Test desc")
        d = result.to_dict()
        assert "triage_id" in d
        assert "severity" in d
        assert "category" in d
        assert "suggested_team" in d
