"""
Service Module – Service Manager
==================================

Service catalog, SLA tracking, ticket routing, knowledge base, and CSAT.

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
    CSATResponse,
    KBArticle,
    RoutingStrategy,
    ServiceCatalogItem,
    SLAPolicy,
    SLAStatus,
    Ticket,
    TicketPriority,
    TicketStatus,
    _now,
)

logger = logging.getLogger(__name__)


class ServiceManager:
    """In-memory service module manager."""

    def __init__(self) -> None:
        self._catalog: Dict[str, ServiceCatalogItem] = {}
        self._sla_policies: Dict[str, SLAPolicy] = {}
        self._tickets: Dict[str, Ticket] = {}
        self._articles: Dict[str, KBArticle] = {}
        self._csat_responses: List[CSATResponse] = []
        self._agents: List[str] = []
        self._agent_loads: Dict[str, int] = {}
        self._routing_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
        self._rr_index: int = 0

    # -- Service catalog ----------------------------------------------------

    def create_catalog_item(
        self,
        name: str,
        *,
        description: str = "",
        category: str = "",
        form_fields: Optional[List[Dict[str, Any]]] = None,
        sla_hours: int = 24,
    ) -> ServiceCatalogItem:
        item = ServiceCatalogItem(
            name=name,
            description=description,
            category=category,
            form_fields=form_fields or [],
            sla_hours=sla_hours,
        )
        self._catalog[item.id] = item
        logger.info("Catalog item created: %s (%s)", name, item.id)
        return item

    def get_catalog_item(self, item_id: str) -> Optional[ServiceCatalogItem]:
        return self._catalog.get(item_id)

    def list_catalog(self, category: str = "") -> List[ServiceCatalogItem]:
        items = [i for i in self._catalog.values() if i.enabled]
        if category:
            items = [i for i in items if i.category == category]
        return items

    # -- SLA policies -------------------------------------------------------

    def create_sla_policy(
        self,
        name: str,
        *,
        response_hours: int = 4,
        resolution_hours: int = 24,
        escalation_email: str = "",
        priority: TicketPriority = TicketPriority.NORMAL,
    ) -> SLAPolicy:
        policy = SLAPolicy(
            name=name,
            response_hours=response_hours,
            resolution_hours=resolution_hours,
            escalation_email=escalation_email,
            priority=priority,
        )
        self._sla_policies[policy.id] = policy
        return policy

    def get_sla_policy(self, policy_id: str) -> Optional[SLAPolicy]:
        return self._sla_policies.get(policy_id)

    def list_sla_policies(self) -> List[SLAPolicy]:
        return list(self._sla_policies.values())

    # -- Ticket CRUD --------------------------------------------------------

    def create_ticket(
        self,
        title: str,
        *,
        description: str = "",
        requester_id: str = "",
        catalog_item_id: str = "",
        priority: TicketPriority = TicketPriority.NORMAL,
        form_data: Optional[Dict[str, Any]] = None,
    ) -> Ticket:
        ticket = Ticket(
            title=title,
            description=description,
            requester_id=requester_id,
            catalog_item_id=catalog_item_id,
            priority=priority,
            form_data=form_data or {},
        )
        self._tickets[ticket.id] = ticket
        logger.info("Ticket created: %s (%s)", title, ticket.id)
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def list_tickets(
        self,
        *,
        status: Optional[TicketStatus] = None,
        assignee_id: str = "",
        priority: Optional[TicketPriority] = None,
    ) -> List[Ticket]:
        tickets = list(self._tickets.values())
        if status is not None:
            tickets = [t for t in tickets if t.status == status]
        if assignee_id:
            tickets = [t for t in tickets if t.assignee_id == assignee_id]
        if priority is not None:
            tickets = [t for t in tickets if t.priority == priority]
        return tickets

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise KeyError(f"Ticket not found: {ticket_id!r}")
        ticket.status = status
        if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            ticket.resolved_at = _now()
        return ticket

    def assign_ticket(self, ticket_id: str, assignee_id: str) -> Ticket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise KeyError(f"Ticket not found: {ticket_id!r}")
        ticket.assignee_id = assignee_id
        if ticket.status == TicketStatus.NEW:
            ticket.status = TicketStatus.OPEN
        self._agent_loads[assignee_id] = self._agent_loads.get(assignee_id, 0) + 1
        return ticket

    # -- Auto-routing -------------------------------------------------------

    def register_agent(self, agent_id: str) -> None:
        if agent_id not in self._agents:
            capped_append(self._agents, agent_id)
            self._agent_loads.setdefault(agent_id, 0)

    def set_routing_strategy(self, strategy: RoutingStrategy) -> None:
        self._routing_strategy = strategy

    def auto_route(self, ticket_id: str) -> Ticket:
        if not self._agents:
            raise ValueError("No agents registered for routing")
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise KeyError(f"Ticket not found: {ticket_id!r}")

        if self._routing_strategy == RoutingStrategy.ROUND_ROBIN:
            agent = self._agents[self._rr_index % len(self._agents)]
            self._rr_index += 1
        elif self._routing_strategy == RoutingStrategy.LOAD_BASED:
            agent = min(self._agents, key=lambda a: self._agent_loads.get(a, 0))
        else:
            agent = self._agents[0]

        return self.assign_ticket(ticket_id, agent)

    # -- Knowledge base -----------------------------------------------------

    def create_article(
        self,
        title: str,
        body: str,
        *,
        category: str = "",
        author_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> KBArticle:
        article = KBArticle(
            title=title,
            body=body,
            category=category,
            author_id=author_id,
            tags=tags or [],
        )
        self._articles[article.id] = article
        return article

    def get_article(self, article_id: str) -> Optional[KBArticle]:
        return self._articles.get(article_id)

    def list_articles(self, category: str = "", published_only: bool = False) -> List[KBArticle]:
        articles = list(self._articles.values())
        if category:
            articles = [a for a in articles if a.category == category]
        if published_only:
            articles = [a for a in articles if a.published]
        return articles

    def publish_article(self, article_id: str) -> KBArticle:
        article = self._articles.get(article_id)
        if article is None:
            raise KeyError(f"Article not found: {article_id!r}")
        article.published = True
        article.updated_at = _now()
        return article

    def record_article_view(self, article_id: str) -> None:
        article = self._articles.get(article_id)
        if article is not None:
            article.view_count += 1

    def mark_article_helpful(self, article_id: str) -> None:
        article = self._articles.get(article_id)
        if article is not None:
            article.helpful_count += 1

    # -- CSAT ---------------------------------------------------------------

    def submit_csat(
        self,
        ticket_id: str,
        rating: int,
        *,
        comment: str = "",
        respondent_id: str = "",
    ) -> CSATResponse:
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        resp = CSATResponse(
            ticket_id=ticket_id,
            rating=rating,
            comment=comment,
            respondent_id=respondent_id,
        )
        capped_append(self._csat_responses, resp)
        return resp

    def csat_average(self) -> float:
        if not self._csat_responses:
            return 0.0
        return sum(r.rating for r in self._csat_responses) / len(self._csat_responses)

    def list_csat(self, ticket_id: str = "") -> List[CSATResponse]:
        resps = self._csat_responses
        if ticket_id:
            resps = [r for r in resps if r.ticket_id == ticket_id]
        return resps
