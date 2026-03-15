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
