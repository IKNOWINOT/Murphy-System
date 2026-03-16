"""
Tests for SUP-004: CustomerCommunicationManager.

Validates template management, rendering, interaction recording,
satisfaction tracking, persistence integration, and EventBackbone.

Design Label: TEST-015 / SUP-004
Owner: QA Team
"""

import os
import pytest


from customer_communication_manager import (
    CustomerCommunicationManager,
    ResponseTemplate,
    CustomerInteraction,
    SatisfactionSummary,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def mgr():
    return CustomerCommunicationManager()


@pytest.fixture
def wired_mgr(pm, backbone):
    return CustomerCommunicationManager(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Template management
# ------------------------------------------------------------------

class TestTemplateManagement:
    def test_create_template(self, mgr):
        tpl = mgr.create_template("greeting", "onboarding", "Hello {{name}}!")
        assert tpl.template_id.startswith("tpl-")
        assert "name" in tpl.variables

    def test_update_template(self, mgr):
        tpl = mgr.create_template("greet", "general", "Hi")
        updated = mgr.update_template(tpl.template_id, body="Hello {{who}}!")
        assert updated is not None
        assert updated.version == 2
        assert "who" in updated.variables

    def test_update_nonexistent(self, mgr):
        assert mgr.update_template("nope", body="x") is None

    def test_list_templates(self, mgr):
        mgr.create_template("a", "cat1", "body1")
        mgr.create_template("b", "cat2", "body2")
        assert len(mgr.list_templates()) == 2

    def test_list_by_category(self, mgr):
        mgr.create_template("a", "cat1", "body1")
        mgr.create_template("b", "cat2", "body2")
        assert len(mgr.list_templates(category="cat1")) == 1


# ------------------------------------------------------------------
# Template rendering
# ------------------------------------------------------------------

class TestRendering:
    def test_render_with_vars(self, mgr):
        tpl = mgr.create_template("welcome", "onboard", "Hello {{name}}, welcome to {{company}}!")
        result = mgr.render_template(tpl.template_id, {"name": "Alice", "company": "Inoni"})
        assert result == "Hello Alice, welcome to Inoni!"

    def test_render_increments_usage(self, mgr):
        tpl = mgr.create_template("greet", "gen", "Hi")
        mgr.render_template(tpl.template_id)
        mgr.render_template(tpl.template_id)
        status = mgr.list_templates()
        assert status[0]["usage_count"] == 2

    def test_render_nonexistent(self, mgr):
        assert mgr.render_template("nope") is None


# ------------------------------------------------------------------
# Interaction recording
# ------------------------------------------------------------------

class TestInteractions:
    def test_record_interaction(self, mgr):
        ix = mgr.record_interaction("cust-1", "email", "Help!", "Here you go")
        assert ix.interaction_id.startswith("ci-")
        assert ix.customer_id == "cust-1"

    def test_get_interactions(self, mgr):
        mgr.record_interaction("c1", "email", "q1", "a1")
        mgr.record_interaction("c2", "chat", "q2", "a2")
        assert len(mgr.get_interactions()) == 2
        assert len(mgr.get_interactions(customer_id="c1")) == 1


# ------------------------------------------------------------------
# Satisfaction tracking
# ------------------------------------------------------------------

class TestSatisfaction:
    def test_rate_interaction(self, mgr):
        ix = mgr.record_interaction("c1", "email", "q", "a")
        assert mgr.rate_interaction(ix.interaction_id, 5) is True
        assert mgr.rate_interaction("nonexistent", 3) is False

    def test_compute_satisfaction(self, mgr):
        ix1 = mgr.record_interaction("c1", "email", "q1", "a1", satisfaction_rating=5)
        ix2 = mgr.record_interaction("c2", "chat", "q2", "a2", satisfaction_rating=3)
        summary = mgr.compute_satisfaction()
        assert summary.rated_interactions == 2
        assert summary.average_rating == 4.0


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_template_persisted(self, wired_mgr, pm):
        tpl = wired_mgr.create_template("greet", "gen", "Hi")
        loaded = pm.load_document(tpl.template_id)
        assert loaded is not None


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, mgr):
        mgr.create_template("a", "b", "c")
        mgr.record_interaction("c1", "email", "q", "a")
        s = mgr.get_status()
        assert s["total_templates"] == 1
        assert s["total_interactions"] == 1
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_mgr):
        s = wired_mgr.get_status()
        assert s["persistence_attached"] is True
