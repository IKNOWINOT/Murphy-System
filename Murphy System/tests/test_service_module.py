"""Tests for Phase 10 – Service Module."""

import sys, os

import pytest
from service_module.models import (
    CSATResponse, KBArticle, RoutingStrategy, SLAPolicy, SLAStatus,
    ServiceCatalogItem, Ticket, TicketPriority, TicketStatus,
)
from service_module.service_manager import ServiceManager


class TestModels:
    def test_catalog_item_to_dict(self):
        i = ServiceCatalogItem(name="Password Reset", category="IT")
        d = i.to_dict()
        assert d["name"] == "Password Reset"

    def test_ticket_to_dict(self):
        t = Ticket(title="Help", priority=TicketPriority.HIGH)
        d = t.to_dict()
        assert d["priority"] == "high"

    def test_kb_article_to_dict(self):
        a = KBArticle(title="How to reset", body="Step 1...")
        d = a.to_dict()
        assert d["published"] is False

    def test_csat_to_dict(self):
        r = CSATResponse(rating=5, ticket_id="t1")
        d = r.to_dict()
        assert d["rating"] == 5


class TestServiceManager:
    def test_create_catalog_item(self):
        mgr = ServiceManager()
        i = mgr.create_catalog_item("Reset", category="IT")
        assert i.name == "Reset"
        assert mgr.get_catalog_item(i.id) is i

    def test_list_catalog(self):
        mgr = ServiceManager()
        mgr.create_catalog_item("A", category="IT")
        mgr.create_catalog_item("B", category="HR")
        assert len(mgr.list_catalog()) == 2
        assert len(mgr.list_catalog("IT")) == 1

    def test_create_sla_policy(self):
        mgr = ServiceManager()
        p = mgr.create_sla_policy("Standard", response_hours=2, resolution_hours=8)
        assert p.response_hours == 2
        assert mgr.get_sla_policy(p.id) is p

    def test_create_ticket(self):
        mgr = ServiceManager()
        t = mgr.create_ticket("Help", requester_id="u1")
        assert t.status == TicketStatus.NEW
        assert mgr.get_ticket(t.id) is t

    def test_list_tickets(self):
        mgr = ServiceManager()
        mgr.create_ticket("A")
        mgr.create_ticket("B")
        assert len(mgr.list_tickets()) == 2

    def test_update_ticket_status(self):
        mgr = ServiceManager()
        t = mgr.create_ticket("X")
        mgr.update_ticket_status(t.id, TicketStatus.RESOLVED)
        assert t.status == TicketStatus.RESOLVED
        assert t.resolved_at != ""

    def test_assign_ticket(self):
        mgr = ServiceManager()
        t = mgr.create_ticket("X")
        mgr.assign_ticket(t.id, "agent1")
        assert t.assignee_id == "agent1"
        assert t.status == TicketStatus.OPEN

    def test_round_robin_routing(self):
        mgr = ServiceManager()
        mgr.register_agent("a1")
        mgr.register_agent("a2")
        t1 = mgr.create_ticket("T1")
        t2 = mgr.create_ticket("T2")
        mgr.auto_route(t1.id)
        mgr.auto_route(t2.id)
        assert t1.assignee_id == "a1"
        assert t2.assignee_id == "a2"

    def test_load_based_routing(self):
        mgr = ServiceManager()
        mgr.register_agent("a1")
        mgr.register_agent("a2")
        mgr.set_routing_strategy(RoutingStrategy.LOAD_BASED)
        t1 = mgr.create_ticket("T1")
        mgr.auto_route(t1.id)  # both at 0, picks a1
        t2 = mgr.create_ticket("T2")
        mgr.auto_route(t2.id)  # a1 has 1, a2 has 0 -> a2
        assert t2.assignee_id == "a2"

    def test_routing_no_agents(self):
        mgr = ServiceManager()
        t = mgr.create_ticket("X")
        with pytest.raises(ValueError):
            mgr.auto_route(t.id)

    def test_create_article(self):
        mgr = ServiceManager()
        a = mgr.create_article("How to", "Step 1...", category="IT")
        assert a.title == "How to"
        assert mgr.get_article(a.id) is a

    def test_publish_article(self):
        mgr = ServiceManager()
        a = mgr.create_article("X", "body")
        mgr.publish_article(a.id)
        assert a.published is True

    def test_article_views_and_helpful(self):
        mgr = ServiceManager()
        a = mgr.create_article("X", "body")
        mgr.record_article_view(a.id)
        mgr.record_article_view(a.id)
        mgr.mark_article_helpful(a.id)
        assert a.view_count == 2
        assert a.helpful_count == 1

    def test_list_articles_published_only(self):
        mgr = ServiceManager()
        a1 = mgr.create_article("A", "body")
        a2 = mgr.create_article("B", "body")
        mgr.publish_article(a1.id)
        assert len(mgr.list_articles(published_only=True)) == 1

    def test_submit_csat(self):
        mgr = ServiceManager()
        r = mgr.submit_csat("t1", 5, comment="Great")
        assert r.rating == 5

    def test_csat_invalid_rating(self):
        mgr = ServiceManager()
        with pytest.raises(ValueError):
            mgr.submit_csat("t1", 6)

    def test_csat_average(self):
        mgr = ServiceManager()
        mgr.submit_csat("t1", 5)
        mgr.submit_csat("t2", 3)
        assert mgr.csat_average() == 4.0

    def test_csat_average_empty(self):
        mgr = ServiceManager()
        assert mgr.csat_average() == 0.0

    def test_ticket_not_found(self):
        mgr = ServiceManager()
        with pytest.raises(KeyError):
            mgr.update_ticket_status("bad", TicketStatus.OPEN)


class TestAPIRouter:
    def test_create_router(self):
        from service_module.api import create_service_router
        router = create_service_router()
        assert router is not None
