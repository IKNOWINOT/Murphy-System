"""Tests for Phase 8 – CRM Module."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from crm.models import (
    ActivityType, CRMActivity, Contact, ContactType,
    Deal, DealStage, Pipeline, Stage,
)
from crm.crm_manager import CRMManager


class TestModels:
    def test_contact_to_dict(self):
        c = Contact(name="Alice", email="a@b.com")
        d = c.to_dict()
        assert d["name"] == "Alice"
        assert d["contact_type"] == "lead"

    def test_deal_to_dict(self):
        d = Deal(title="Big Deal", value=50000)
        r = d.to_dict()
        assert r["value"] == 50000

    def test_pipeline_to_dict(self):
        p = Pipeline(name="Sales", stages=[Stage(name="Lead", order=0)])
        d = p.to_dict()
        assert len(d["stages"]) == 1

    def test_activity_to_dict(self):
        a = CRMActivity(activity_type=ActivityType.CALL, summary="Intro call")
        d = a.to_dict()
        assert d["activity_type"] == "call"


class TestCRMManager:
    def test_create_contact(self):
        mgr = CRMManager()
        c = mgr.create_contact("Alice", email="a@b.com")
        assert c.name == "Alice"

    def test_get_contact(self):
        mgr = CRMManager()
        c = mgr.create_contact("Alice")
        assert mgr.get_contact(c.id) is c
        assert mgr.get_contact("nope") is None

    def test_list_contacts(self):
        mgr = CRMManager()
        mgr.create_contact("A", owner_id="u1")
        mgr.create_contact("B", owner_id="u2")
        assert len(mgr.list_contacts()) == 2
        assert len(mgr.list_contacts(owner_id="u1")) == 1

    def test_update_contact(self):
        mgr = CRMManager()
        c = mgr.create_contact("Old")
        mgr.update_contact(c.id, name="New")
        assert c.name == "New"

    def test_update_contact_not_found(self):
        mgr = CRMManager()
        with pytest.raises(KeyError):
            mgr.update_contact("bad", name="X")

    def test_delete_contact(self):
        mgr = CRMManager()
        c = mgr.create_contact("X")
        assert mgr.delete_contact(c.id)
        assert not mgr.delete_contact(c.id)

    def test_create_pipeline(self):
        mgr = CRMManager()
        p = mgr.create_pipeline("Sales", [
            {"name": "Lead", "order": 0, "probability": 0.1},
            {"name": "Won", "order": 1, "probability": 1.0},
        ])
        assert len(p.stages) == 2

    def test_get_pipeline(self):
        mgr = CRMManager()
        p = mgr.create_pipeline("P")
        assert mgr.get_pipeline(p.id) is p

    def test_create_deal(self):
        mgr = CRMManager()
        d = mgr.create_deal("Big Sale", value=50000)
        assert d.title == "Big Sale"

    def test_get_deal(self):
        mgr = CRMManager()
        d = mgr.create_deal("D")
        assert mgr.get_deal(d.id) is d

    def test_list_deals(self):
        mgr = CRMManager()
        mgr.create_deal("A", pipeline_id="p1", stage="lead")
        mgr.create_deal("B", pipeline_id="p1", stage="won")
        mgr.create_deal("C", pipeline_id="p2", stage="proposal")
        assert len(mgr.list_deals()) == 3
        assert len(mgr.list_deals(pipeline_id="p1")) == 2
        assert len(mgr.list_deals(stage="lead")) == 1

    def test_update_deal(self):
        mgr = CRMManager()
        d = mgr.create_deal("Old", value=100)
        mgr.update_deal(d.id, title="New", value=200)
        assert d.title == "New"
        assert d.value == 200

    def test_move_deal(self):
        mgr = CRMManager()
        d = mgr.create_deal("D")
        mgr.move_deal(d.id, "closed_won")
        assert d.stage == "closed_won"
        assert d.closed_at != ""

    def test_delete_deal(self):
        mgr = CRMManager()
        d = mgr.create_deal("D")
        assert mgr.delete_deal(d.id)
        assert not mgr.delete_deal(d.id)

    def test_pipeline_value(self):
        mgr = CRMManager()
        mgr.create_deal("A", pipeline_id="p1", stage="lead", value=1000)
        mgr.create_deal("B", pipeline_id="p1", stage="lead", value=2000)
        mgr.create_deal("C", pipeline_id="p1", stage="won", value=5000)
        result = mgr.pipeline_value("p1")
        assert result["lead"] == 3000
        assert result["won"] == 5000

    def test_log_activity(self):
        mgr = CRMManager()
        a = mgr.log_activity(ActivityType.CALL, contact_id="c1", summary="Intro")
        assert a.activity_type == ActivityType.CALL

    def test_list_activities(self):
        mgr = CRMManager()
        mgr.log_activity(ActivityType.CALL, contact_id="c1")
        mgr.log_activity(ActivityType.EMAIL, contact_id="c1")
        mgr.log_activity(ActivityType.NOTE, contact_id="c2")
        assert len(mgr.list_activities()) == 3
        assert len(mgr.list_activities(contact_id="c1")) == 2


class TestAPIRouter:
    def test_create_router(self):
        from crm.api import create_crm_router
        router = create_crm_router()
        assert router is not None


# ===================================================================
# Phase 8 additions: Email tracking, Pipeline templates, CRM summary
# ===================================================================

class TestEmailInteractionTracking:
    def test_track_email_sent(self):
        from crm.models import EmailDirection, EmailInteraction
        mgr = CRMManager()
        ei = mgr.track_email(
            contact_id="c1", user_id="u1",
            direction=EmailDirection.SENT,
            subject="Hello", from_address="u@u.com",
            to_addresses=["c@c.com"],
        )
        assert ei.direction == EmailDirection.SENT
        assert ei.subject == "Hello"

    def test_track_email_received(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        ei = mgr.track_email(
            contact_id="c1", direction=EmailDirection.RECEIVED,
            subject="Re: Hello", from_address="c@c.com",
        )
        assert ei.direction == EmailDirection.RECEIVED

    def test_list_email_interactions_filter_by_contact(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        mgr.track_email(contact_id="c1", direction=EmailDirection.SENT, subject="A")
        mgr.track_email(contact_id="c2", direction=EmailDirection.SENT, subject="B")
        assert len(mgr.list_email_interactions(contact_id="c1")) == 1

    def test_list_email_interactions_filter_by_direction(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        mgr.track_email(contact_id="c1", direction=EmailDirection.SENT, subject="S")
        mgr.track_email(contact_id="c1", direction=EmailDirection.RECEIVED, subject="R")
        sent = mgr.list_email_interactions(direction=EmailDirection.SENT)
        assert all(e.direction == EmailDirection.SENT for e in sent)

    def test_mark_email_opened(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        ei = mgr.track_email(contact_id="c1", direction=EmailDirection.SENT, subject="T")
        updated = mgr.mark_email_opened(ei.id)
        assert updated is not None
        assert updated.opened_at != ""

    def test_mark_email_clicked(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        ei = mgr.track_email(contact_id="c1", direction=EmailDirection.SENT, subject="T")
        updated = mgr.mark_email_clicked(ei.id)
        assert updated is not None
        assert updated.clicked_at != ""

    def test_email_interaction_to_dict(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        ei = mgr.track_email(
            contact_id="c1", direction=EmailDirection.SENT,
            subject="Dict test", to_addresses=["x@x.com"],
        )
        d = ei.to_dict()
        assert d["subject"] == "Dict test"
        assert "direction" in d

    def test_body_preview_truncated(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        long_body = "x" * 1000
        ei = mgr.track_email(contact_id="c1", direction=EmailDirection.SENT,
                              body_preview=long_body)
        assert len(ei.body_preview) == 500


class TestPipelineTemplates:
    def test_list_pipeline_templates(self):
        mgr = CRMManager()
        templates = mgr.list_pipeline_templates()
        assert len(templates) >= 3

    def test_create_pipeline_from_template(self):
        mgr = CRMManager()
        pipeline = mgr.create_pipeline_from_template(0)
        assert pipeline.name != ""
        assert len(pipeline.stages) >= 4

    def test_create_enterprise_pipeline_template(self):
        mgr = CRMManager()
        pipeline = mgr.create_pipeline_from_template(1)
        assert len(pipeline.stages) >= 6

    def test_pipeline_template_out_of_range(self):
        mgr = CRMManager()
        with pytest.raises(IndexError):
            mgr.create_pipeline_from_template(999)

    def test_pipeline_probability_set(self):
        mgr = CRMManager()
        pipeline = mgr.create_pipeline_from_template(0)
        probs = [s.probability for s in pipeline.stages]
        assert 1.0 in probs  # closed_won = 100%


class TestCRMSummary:
    def test_crm_summary_empty(self):
        mgr = CRMManager()
        s = mgr.crm_summary()
        assert s["total_contacts"] == 0
        assert s["total_deals"] == 0

    def test_crm_summary_counts(self):
        from crm.models import EmailDirection
        mgr = CRMManager()
        mgr.create_contact("Alice")
        mgr.create_contact("Bob")
        p = mgr.create_pipeline("Sales", [{"name": "Lead", "order": 0}])
        mgr.create_deal("Deal A", contact_id="", pipeline_id=p.id, stage="lead", value=1000)
        mgr.create_deal("Deal B", contact_id="", pipeline_id=p.id,
                        stage="closed_won", value=500)
        mgr.track_email(direction=EmailDirection.SENT, subject="Hi")
        s = mgr.crm_summary()
        assert s["total_contacts"] == 2
        assert s["total_deals"] == 2
        assert s["won_deals"] == 1
        assert s["total_pipeline_value"] == 1500
        assert s["emails_sent"] == 1


class TestCRMDashboardWidget:
    def test_crm_summary_widget_type_exists(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from dashboards.models import WidgetType
        assert WidgetType.CRM_SUMMARY.value == "crm_summary"

    def test_render_crm_summary_widget(self):
        from dashboards.models import WidgetConfig, WidgetType, DataSource
        from dashboards.widgets import render_crm_summary_widget
        from dashboards.aggregation import AggregationEngine
        widget = WidgetConfig(
            widget_type=WidgetType.CRM_SUMMARY,
            title="CRM Overview",
            settings={"crm_summary": {"total_contacts": 5, "open_deals": 3}},
        )
        engine = AggregationEngine()
        result = render_crm_summary_widget(widget, engine)
        assert result["widget_type"] == "crm_summary"
        assert result["data"]["total_contacts"] == 5
        assert result["data"]["open_deals"] == 3
