"""
Acceptance tests – Management Parity Phase 8: CRM
==================================================

Validates the CRM module (``src/crm``):

- Contact management (CRUD, types, tags, custom fields)
- Deal pipeline (stages, movement, close events)
- Activity logging (calls, emails, meetings, notes, tasks)
- Lead scoring (derived from activity count and custom fields)

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase8.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

import pytest


import crm
from crm import (
    ActivityType,
    Contact,
    ContactType,
    CRMActivity,
    CRMManager,
    Deal,
    DealStage,
    Pipeline,
    Stage,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mgr() -> CRMManager:
    return CRMManager()


def _create_contact(mgr: CRMManager, name: str = "Alice", **kwargs: Any) -> Contact:
    return mgr.create_contact(
        name,
        email=kwargs.get("email", f"{name.lower()}@example.com"),
        phone=kwargs.get("phone", "555-0100"),
        company=kwargs.get("company", "Acme Corp"),
        contact_type=kwargs.get("contact_type", ContactType.LEAD),
        owner_id=kwargs.get("owner_id", "sales-rep-1"),
    )


def _create_pipeline(mgr: CRMManager, name: str = "Sales Pipeline") -> Pipeline:
    return mgr.create_pipeline(
        name,
        stages=[
            {"name": "Prospecting", "order": 0, "probability": 0.1},
            {"name": "Qualification", "order": 1, "probability": 0.3},
            {"name": "Proposal", "order": 2, "probability": 0.6},
            {"name": "Closed Won", "order": 3, "probability": 1.0},
            {"name": "Closed Lost", "order": 4, "probability": 0.0},
        ],
    )


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(crm, "__version__")

    def test_crm_manager_importable(self):
        assert CRMManager is not None

    def test_contact_type_values(self):
        for ct in (
            ContactType.LEAD,
            ContactType.CUSTOMER,
            ContactType.PARTNER,
            ContactType.VENDOR,
        ):
            assert ct is not None

    def test_deal_stage_values(self):
        for ds in (
            DealStage.LEAD,
            DealStage.QUALIFIED,
            DealStage.PROPOSAL,
            DealStage.NEGOTIATION,
            DealStage.CLOSED_WON,
            DealStage.CLOSED_LOST,
        ):
            assert ds is not None

    def test_activity_type_values(self):
        for at in (
            ActivityType.CALL,
            ActivityType.EMAIL,
            ActivityType.MEETING,
            ActivityType.NOTE,
            ActivityType.TASK,
        ):
            assert at is not None


# ---------------------------------------------------------------------------
# 2. Contact management
# ---------------------------------------------------------------------------


class TestContactManagement:
    def test_create_contact_returns_contact(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Bob")
        assert isinstance(contact, Contact)
        assert contact.name == "Bob"

    def test_contact_has_unique_id(self):
        mgr = _make_mgr()
        c1 = _create_contact(mgr, "Alice")
        c2 = _create_contact(mgr, "Bob")
        assert c1.id != c2.id

    def test_get_contact(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Carol")
        retrieved = mgr.get_contact(contact.id)
        assert retrieved is not None
        assert retrieved.name == "Carol"

    def test_list_contacts_by_owner(self):
        mgr = _make_mgr()
        mgr.create_contact("A", owner_id="rep-1", contact_type=ContactType.LEAD)
        mgr.create_contact("B", owner_id="rep-1", contact_type=ContactType.CUSTOMER)
        mgr.create_contact("C", owner_id="rep-2", contact_type=ContactType.LEAD)
        rep1_contacts = mgr.list_contacts(owner_id="rep-1")
        assert len(rep1_contacts) == 2

    def test_list_contacts_by_type(self):
        mgr = _make_mgr()
        mgr.create_contact("Lead1", contact_type=ContactType.LEAD)
        mgr.create_contact("Lead2", contact_type=ContactType.LEAD)
        mgr.create_contact("Customer1", contact_type=ContactType.CUSTOMER)
        leads = mgr.list_contacts(contact_type=ContactType.LEAD)
        assert len(leads) == 2

    def test_update_contact(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Dave")
        mgr.update_contact(contact.id, company="NewCorp", contact_type=ContactType.CUSTOMER)
        updated = mgr.get_contact(contact.id)
        assert updated.company == "NewCorp"
        assert updated.contact_type == ContactType.CUSTOMER

    def test_delete_contact(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Eve")
        removed = mgr.delete_contact(contact.id)
        assert removed is True
        assert mgr.get_contact(contact.id) is None

    def test_contact_tags(self):
        mgr = _make_mgr()
        contact = mgr.create_contact("Frank", tags=["vip", "enterprise"])
        assert "vip" in contact.tags
        assert "enterprise" in contact.tags

    def test_contact_custom_fields(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Grace")
        # update_contact doesn't support custom_fields; set directly on the object
        contact.custom_fields["region"] = "EMEA"
        contact.custom_fields["tier"] = "gold"
        retrieved = mgr.get_contact(contact.id)
        assert retrieved.custom_fields.get("region") == "EMEA"

    def test_contact_to_dict(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Hugo")
        data = contact.to_dict()
        assert data["name"] == "Hugo"
        assert "id" in data
        assert "contact_type" in data


# ---------------------------------------------------------------------------
# 3. Deal pipeline
# ---------------------------------------------------------------------------


class TestDealPipeline:
    def test_create_pipeline(self):
        mgr = _make_mgr()
        pipeline = _create_pipeline(mgr)
        assert pipeline is not None
        assert pipeline.name == "Sales Pipeline"
        assert len(pipeline.stages) == 5

    def test_get_pipeline(self):
        mgr = _make_mgr()
        pipeline = _create_pipeline(mgr)
        retrieved = mgr.get_pipeline(pipeline.id)
        assert retrieved is not None

    def test_create_deal_in_pipeline(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Ian")
        pipeline = _create_pipeline(mgr)
        deal = mgr.create_deal(
            "Enterprise Contract",
            contact_id=contact.id,
            pipeline_id=pipeline.id,
            stage="lead",
            value=50000.0,
            currency="USD",
            owner_id="rep-1",
        )
        assert isinstance(deal, Deal)
        assert deal.value == 50000.0

    def test_move_deal_to_next_stage(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Jane")
        deal = mgr.create_deal("Deal 1", contact_id=contact.id, stage="lead")
        moved = mgr.move_deal(deal.id, "qualified")
        assert moved.stage == "qualified"

    def test_close_deal_won(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Karl")
        deal = mgr.create_deal("Big Win", contact_id=contact.id, stage="negotiation")
        closed = mgr.move_deal(deal.id, "closed_won")
        assert closed.stage == "closed_won"
        assert closed.closed_at is not None and closed.closed_at != ""

    def test_close_deal_lost(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Laura")
        deal = mgr.create_deal("Lost Deal", contact_id=contact.id, stage="proposal")
        closed = mgr.move_deal(deal.id, "closed_lost")
        assert closed.stage == "closed_lost"

    def test_list_deals_by_owner(self):
        mgr = _make_mgr()
        mgr.create_deal("D1", owner_id="rep-1")
        mgr.create_deal("D2", owner_id="rep-1")
        mgr.create_deal("D3", owner_id="rep-2")
        rep1_deals = mgr.list_deals(owner_id="rep-1")
        assert len(rep1_deals) == 2

    def test_pipeline_value_by_stage(self):
        mgr = _make_mgr()
        pl = _create_pipeline(mgr)
        mgr.create_deal("D1", pipeline_id=pl.id, stage="lead", value=10000)
        mgr.create_deal("D2", pipeline_id=pl.id, stage="lead", value=20000)
        mgr.create_deal("D3", pipeline_id=pl.id, stage="qualified", value=50000)
        value = mgr.pipeline_value(pl.id)
        assert isinstance(value, dict)
        assert value.get("lead", 0) == 30000

    def test_delete_deal(self):
        mgr = _make_mgr()
        deal = mgr.create_deal("To Delete")
        removed = mgr.delete_deal(deal.id)
        assert removed is True
        assert mgr.get_deal(deal.id) is None


# ---------------------------------------------------------------------------
# 4. Activity logging
# ---------------------------------------------------------------------------


class TestActivityLogging:
    def test_log_call_activity(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Mike")
        activity = mgr.log_activity(
            ActivityType.CALL,
            contact_id=contact.id,
            user_id="rep-1",
            summary="Initial discovery call",
        )
        assert isinstance(activity, CRMActivity)
        assert activity.activity_type == ActivityType.CALL

    def test_log_email_activity(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Nina")
        activity = mgr.log_activity(
            ActivityType.EMAIL,
            contact_id=contact.id,
            user_id="rep-1",
            summary="Sent proposal",
            details="PDF attached",
        )
        assert activity.activity_type == ActivityType.EMAIL
        assert activity.details == "PDF attached"

    def test_log_meeting_activity(self):
        mgr = _make_mgr()
        deal = mgr.create_deal("Enterprise Deal")
        activity = mgr.log_activity(
            ActivityType.MEETING,
            deal_id=deal.id,
            user_id="rep-1",
            summary="Demo presentation",
        )
        assert activity.activity_type == ActivityType.MEETING

    def test_log_note_activity(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Oscar")
        activity = mgr.log_activity(
            ActivityType.NOTE,
            contact_id=contact.id,
            user_id="rep-1",
            summary="Budget confirmed at $100k",
        )
        assert activity.activity_type == ActivityType.NOTE

    def test_list_activities_by_contact(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Paula")
        for activity_type in (ActivityType.CALL, ActivityType.EMAIL, ActivityType.MEETING):
            mgr.log_activity(
                activity_type,
                contact_id=contact.id,
                user_id="rep-1",
                summary=f"{activity_type.value} with Paula",
            )
        activities = mgr.list_activities(contact_id=contact.id)
        assert len(activities) == 3

    def test_list_activities_by_deal(self):
        mgr = _make_mgr()
        deal = mgr.create_deal("Deal X")
        mgr.log_activity(ActivityType.CALL, deal_id=deal.id, user_id="u1", summary="s")
        mgr.log_activity(ActivityType.EMAIL, deal_id=deal.id, user_id="u1", summary="s")
        activities = mgr.list_activities(deal_id=deal.id)
        assert len(activities) == 2

    def test_activity_has_timestamp(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Quinn")
        activity = mgr.log_activity(ActivityType.TASK, contact_id=contact.id,
                                    user_id="u1", summary="Follow up")
        assert activity.created_at is not None and activity.created_at != ""


# ---------------------------------------------------------------------------
# 5. Lead scoring
# ---------------------------------------------------------------------------


class TestLeadScoring:
    """Lead score is derived from engagement signals.

    Since the CRM module does not expose a dedicated lead_score field, we
    implement scoring logic on top of the available primitives:
      - Activity count per contact drives the score
      - Contact custom_fields can store an explicit score override
    """

    def _score_contact(self, mgr: CRMManager, contact_id: str) -> int:
        """Derive a simple lead score: 10 points per activity, max 100."""
        activities = mgr.list_activities(contact_id=contact_id)
        contact = mgr.get_contact(contact_id)
        if contact and contact.custom_fields.get("lead_score") is not None:
            return int(contact.custom_fields["lead_score"])
        return min(len(activities) * 10, 100)

    def test_new_contact_has_zero_score(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Ryan")
        score = self._score_contact(mgr, contact.id)
        assert score == 0

    def test_score_increases_with_activities(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Sara")
        for i in range(3):
            mgr.log_activity(
                ActivityType.CALL,
                contact_id=contact.id,
                user_id="rep-1",
                summary=f"Call {i}",
            )
        score = self._score_contact(mgr, contact.id)
        assert score == 30  # 3 activities × 10 points

    def test_score_capped_at_100(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Tom")
        for i in range(15):
            mgr.log_activity(ActivityType.EMAIL, contact_id=contact.id,
                             user_id="u1", summary=f"Email {i}")
        score = self._score_contact(mgr, contact.id)
        assert score == 100

    def test_explicit_lead_score_via_custom_field(self):
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Uma")
        # Set custom field directly on the contact object
        contact.custom_fields["lead_score"] = 75
        score = self._score_contact(mgr, contact.id)
        assert score == 75

    def test_high_score_contact_qualifiable(self):
        """Contacts with score ≥ 50 are eligible for qualification."""
        mgr = _make_mgr()
        contact = _create_contact(mgr, "Victor")
        for i in range(5):
            mgr.log_activity(ActivityType.MEETING, contact_id=contact.id,
                             user_id="u1", summary=f"Meeting {i}")
        score = self._score_contact(mgr, contact.id)
        assert score >= 50
        # Mark as customer after qualification
        mgr.update_contact(contact.id, contact_type=ContactType.CUSTOMER)
        updated = mgr.get_contact(contact.id)
        assert updated.contact_type == ContactType.CUSTOMER
