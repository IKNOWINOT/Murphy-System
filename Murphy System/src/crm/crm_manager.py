"""
CRM – CRM Manager
===================

Central façade for contacts, deals, pipelines, and activities.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .models import (
    _BUILTIN_PIPELINE_TEMPLATES,
    ActivityType,
    Contact,
    ContactType,
    CRMActivity,
    Deal,
    DealStage,
    EmailDirection,
    EmailInteraction,
    Pipeline,
    Stage,
    _now,
)

logger = logging.getLogger(__name__)


class CRMManager:
    """In-memory CRM management engine."""

    def __init__(self) -> None:
        self._contacts: Dict[str, Contact] = {}
        self._deals: Dict[str, Deal] = {}
        self._pipelines: Dict[str, Pipeline] = {}
        self._activities: List[CRMActivity] = []
        self._email_interactions: List[EmailInteraction] = []

    # -- Contacts -----------------------------------------------------------

    def create_contact(
        self,
        name: str,
        *,
        email: str = "",
        phone: str = "",
        company: str = "",
        contact_type: ContactType = ContactType.LEAD,
        owner_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> Contact:
        contact = Contact(
            name=name, email=email, phone=phone,
            company=company, contact_type=contact_type,
            owner_id=owner_id, tags=tags or [],
        )
        self._contacts[contact.id] = contact
        logger.info("Contact created: %s (%s)", name, contact.id)
        return contact

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        return self._contacts.get(contact_id)

    def list_contacts(
        self, *, owner_id: str = "", contact_type: Optional[ContactType] = None,
    ) -> List[Contact]:
        contacts = list(self._contacts.values())
        if owner_id:
            contacts = [c for c in contacts if c.owner_id == owner_id]
        if contact_type is not None:
            contacts = [c for c in contacts if c.contact_type == contact_type]
        return contacts

    def update_contact(
        self,
        contact_id: str,
        *,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        contact_type: Optional[ContactType] = None,
    ) -> Contact:
        contact = self._contacts.get(contact_id)
        if contact is None:
            raise KeyError(f"Contact not found: {contact_id!r}")
        if name is not None:
            contact.name = name
        if email is not None:
            contact.email = email
        if phone is not None:
            contact.phone = phone
        if company is not None:
            contact.company = company
        if contact_type is not None:
            contact.contact_type = contact_type
        return contact

    def delete_contact(self, contact_id: str) -> bool:
        if contact_id in self._contacts:
            del self._contacts[contact_id]
            return True
        return False

    # -- Pipelines ----------------------------------------------------------

    def create_pipeline(
        self,
        name: str,
        stages: Optional[List[Dict[str, Any]]] = None,
    ) -> Pipeline:
        stage_objs = []
        for i, s in enumerate(stages or []):
            stage_objs.append(Stage(
                name=s.get("name", ""),
                order=s.get("order", i),
                probability=s.get("probability", 0.0),
            ))
        pipeline = Pipeline(name=name, stages=stage_objs)
        self._pipelines[pipeline.id] = pipeline
        return pipeline

    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> List[Pipeline]:
        return list(self._pipelines.values())

    # -- Deals --------------------------------------------------------------

    def create_deal(
        self,
        title: str,
        *,
        contact_id: str = "",
        pipeline_id: str = "",
        stage: str = "lead",
        value: float = 0.0,
        currency: str = "USD",
        owner_id: str = "",
        expected_close_date: str = "",
    ) -> Deal:
        deal = Deal(
            title=title, contact_id=contact_id,
            pipeline_id=pipeline_id, stage=stage,
            value=value, currency=currency,
            owner_id=owner_id, expected_close_date=expected_close_date,
        )
        self._deals[deal.id] = deal
        logger.info("Deal created: %s (%s)", title, deal.id)
        return deal

    def get_deal(self, deal_id: str) -> Optional[Deal]:
        return self._deals.get(deal_id)

    def list_deals(
        self,
        *,
        pipeline_id: str = "",
        stage: str = "",
        owner_id: str = "",
    ) -> List[Deal]:
        deals = list(self._deals.values())
        if pipeline_id:
            deals = [d for d in deals if d.pipeline_id == pipeline_id]
        if stage:
            deals = [d for d in deals if d.stage == stage]
        if owner_id:
            deals = [d for d in deals if d.owner_id == owner_id]
        return deals

    def update_deal(
        self,
        deal_id: str,
        *,
        title: Optional[str] = None,
        stage: Optional[str] = None,
        value: Optional[float] = None,
    ) -> Deal:
        deal = self._deals.get(deal_id)
        if deal is None:
            raise KeyError(f"Deal not found: {deal_id!r}")
        if title is not None:
            deal.title = title
        if stage is not None:
            deal.stage = stage
        if value is not None:
            deal.value = value
        deal.updated_at = _now()
        return deal

    def move_deal(self, deal_id: str, stage: str) -> Deal:
        deal = self._deals.get(deal_id)
        if deal is None:
            raise KeyError(f"Deal not found: {deal_id!r}")
        deal.stage = stage
        if stage in ("closed_won", "closed_lost"):
            deal.closed_at = _now()
        deal.updated_at = _now()
        return deal

    def delete_deal(self, deal_id: str) -> bool:
        if deal_id in self._deals:
            del self._deals[deal_id]
            return True
        return False

    # -- Pipeline metrics ---------------------------------------------------

    def pipeline_value(self, pipeline_id: str) -> Dict[str, float]:
        """Total deal value by stage."""
        result: Dict[str, float] = {}
        for deal in self.list_deals(pipeline_id=pipeline_id):
            result[deal.stage] = result.get(deal.stage, 0.0) + deal.value
        return result

    # -- Activities ---------------------------------------------------------

    def log_activity(
        self,
        activity_type: ActivityType,
        *,
        contact_id: str = "",
        deal_id: str = "",
        user_id: str = "",
        summary: str = "",
        details: str = "",
    ) -> CRMActivity:
        activity = CRMActivity(
            activity_type=activity_type,
            contact_id=contact_id,
            deal_id=deal_id,
            user_id=user_id,
            summary=summary,
            details=details,
        )
        capped_append(self._activities, activity)
        return activity

    def list_activities(
        self,
        *,
        contact_id: str = "",
        deal_id: str = "",
        limit: int = 50,
    ) -> List[CRMActivity]:
        acts = self._activities
        if contact_id:
            acts = [a for a in acts if a.contact_id == contact_id]
        if deal_id:
            acts = [a for a in acts if a.deal_id == deal_id]
        return list(reversed(acts[-limit:]))

    # -- Email interaction tracking -----------------------------------------

    def track_email(
        self,
        *,
        contact_id: str = "",
        deal_id: str = "",
        user_id: str = "",
        direction: EmailDirection = EmailDirection.SENT,
        subject: str = "",
        body_preview: str = "",
        from_address: str = "",
        to_addresses: Optional[List[str]] = None,
        message_id: str = "",
        thread_id: str = "",
    ) -> EmailInteraction:
        """Record a sent or received email interaction."""
        interaction = EmailInteraction(
            contact_id=contact_id,
            deal_id=deal_id,
            user_id=user_id,
            direction=direction,
            subject=subject,
            body_preview=body_preview[:500],
            from_address=from_address,
            to_addresses=to_addresses or [],
            message_id=message_id,
            thread_id=thread_id,
        )
        capped_append(self._email_interactions, interaction)
        logger.info("Email tracked: %s direction=%s", interaction.id, direction.value)
        return interaction

    def mark_email_opened(self, interaction_id: str) -> Optional[EmailInteraction]:
        """Record that a tracked email was opened."""
        for ei in self._email_interactions:
            if ei.id == interaction_id:
                if not ei.opened_at:
                    ei.opened_at = _now()
                return ei
        return None

    def mark_email_clicked(self, interaction_id: str) -> Optional[EmailInteraction]:
        """Record that a tracked email link was clicked."""
        for ei in self._email_interactions:
            if ei.id == interaction_id:
                if not ei.clicked_at:
                    ei.clicked_at = _now()
                return ei
        return None

    def list_email_interactions(
        self,
        *,
        contact_id: str = "",
        deal_id: str = "",
        direction: Optional[EmailDirection] = None,
        limit: int = 50,
    ) -> List[EmailInteraction]:
        """Return email interactions filtered by contact, deal, or direction."""
        items = self._email_interactions
        if contact_id:
            items = [e for e in items if e.contact_id == contact_id]
        if deal_id:
            items = [e for e in items if e.deal_id == deal_id]
        if direction is not None:
            items = [e for e in items if e.direction == direction]
        return list(reversed(items[-limit:]))

    # -- Pipeline templates -------------------------------------------------

    def list_pipeline_templates(self) -> List[Dict[str, Any]]:
        """Return the built-in pipeline templates."""
        return list(_BUILTIN_PIPELINE_TEMPLATES)

    def create_pipeline_from_template(self, template_index: int = 0) -> Pipeline:
        """Instantiate a new :class:`Pipeline` from a built-in template.

        *template_index* selects from ``_BUILTIN_PIPELINE_TEMPLATES`` (0-based).
        """
        if template_index < 0 or template_index >= len(_BUILTIN_PIPELINE_TEMPLATES):
            raise IndexError(f"No pipeline template at index {template_index}")
        tdef = _BUILTIN_PIPELINE_TEMPLATES[template_index]
        stages = [
            Stage(name=s["name"], order=s["order"], probability=s["probability"])
            for s in tdef["stages"]
        ]
        pipeline = Pipeline(name=tdef["name"], stages=stages)
        self._pipelines[pipeline.id] = pipeline
        logger.info("Pipeline created from template: %s", pipeline.name)
        return pipeline

    # -- CRM summary (for dashboard widgets) --------------------------------

    def crm_summary(self) -> Dict[str, Any]:
        """Return a high-level CRM summary suitable for dashboard widgets."""
        total_deals = len(self._deals)
        open_deals = [d for d in self._deals.values()
                      if d.stage not in ("closed_won", "closed_lost")]
        won_deals = [d for d in self._deals.values() if d.stage == "closed_won"]
        total_value = sum(d.value for d in self._deals.values())
        open_value = sum(d.value for d in open_deals)
        won_value = sum(d.value for d in won_deals)
        emails_sent = sum(
            1 for e in self._email_interactions
            if e.direction == EmailDirection.SENT
        )
        emails_received = sum(
            1 for e in self._email_interactions
            if e.direction == EmailDirection.RECEIVED
        )
        return {
            "total_contacts": len(self._contacts),
            "total_deals": total_deals,
            "open_deals": len(open_deals),
            "won_deals": len(won_deals),
            "total_pipeline_value": total_value,
            "open_pipeline_value": open_value,
            "won_revenue": won_value,
            "total_activities": len(self._activities),
            "emails_sent": emails_sent,
            "emails_received": emails_received,
        }
