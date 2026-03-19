"""
Ticketing / ITSM Integration Adapter for Murphy System Runtime

This module provides a unified ticketing interface that can work with
different ITSM back-ends (ServiceNow, Jira, Zendesk, custom), supporting:
- Ticket lifecycle management (create, update, close, escalate)
- Remote access provisioning requests
- Patch / rollback automation requests
- Thread-safe in-memory ticket store
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class TicketPriority(str, Enum):
    """Severity levels aligned with ITIL priority matrix."""
    P1_CRITICAL = "p1_critical"
    P2_HIGH = "p2_high"
    P3_MEDIUM = "p3_medium"
    P4_LOW = "p4_low"


class TicketStatus(str, Enum):
    """Lifecycle states a ticket can occupy."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class TicketType(str, Enum):
    """Categories of work items managed by the adapter."""
    INCIDENT = "incident"
    SERVICE_REQUEST = "service_request"
    CHANGE_REQUEST = "change_request"
    PROBLEM = "problem"
    REMOTE_ACCESS = "remote_access"
    PATCH_ROLLBACK = "patch_rollback"
    API_BUILD = "api_build"


PRIORITY_ORDER = {
    TicketPriority.P1_CRITICAL: 0,
    TicketPriority.P2_HIGH: 1,
    TicketPriority.P3_MEDIUM: 2,
    TicketPriority.P4_LOW: 3,
}


@dataclass
class Ticket:
    """Represents a single ticketing work item."""
    ticket_id: str
    title: str
    description: str
    ticket_type: TicketType
    priority: TicketPriority
    status: TicketStatus
    requester: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    assignee: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now


class TicketingAdapter:
    """Unified ITSM adapter that manages tickets in an in-memory store.

    Provides lifecycle operations (create, update, escalate, close) as well
    as domain-specific helpers for remote-access and patch/rollback requests.
    All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickets: Dict[str, Ticket] = {}
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Ticket lifecycle
    # ------------------------------------------------------------------

    def create_ticket(
        self,
        title: str,
        description: str,
        ticket_type: TicketType,
        priority: TicketPriority,
        requester: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Ticket:
        """Create a new ticket and return it."""
        ticket = Ticket(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            status=TicketStatus.OPEN,
            requester=requester,
            tags=tags or [],
            metadata=metadata or {},
        )

        with self._lock:
            self._tickets[ticket.ticket_id] = ticket
            self._record_event(ticket.ticket_id, "created", {
                "title": title,
                "ticket_type": ticket_type.value,
                "priority": priority.value,
            })

        logger.info("Created ticket %s: %s", ticket.ticket_id, title)
        return ticket

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[TicketStatus] = None,
        assignee: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Ticket]:
        """Update fields on an existing ticket. Returns the ticket or None."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                logger.warning("Ticket %s not found for update", ticket_id)
                return None

            changes: Dict[str, Any] = {}
            if status is not None:
                changes["status"] = {"from": ticket.status.value, "to": status.value}
                ticket.status = status
            if assignee is not None:
                changes["assignee"] = {"from": ticket.assignee, "to": assignee}
                ticket.assignee = assignee
            if notes is not None:
                ticket.metadata.setdefault("notes", [])
                ticket.metadata["notes"].append({
                    "text": notes,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                changes["notes_added"] = True

            ticket.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(ticket_id, "updated", changes)

        logger.info("Updated ticket %s", ticket_id)
        return ticket

    def escalate_ticket(self, ticket_id: str, reason: str) -> Optional[Ticket]:
        """Escalate a ticket by setting its status and recording the reason."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                logger.warning("Ticket %s not found for escalation", ticket_id)
                return None

            previous_status = ticket.status
            ticket.status = TicketStatus.ESCALATED
            ticket.updated_at = datetime.now(timezone.utc).isoformat()
            ticket.metadata["escalation_reason"] = reason
            self._record_event(ticket_id, "escalated", {
                "previous_status": previous_status.value,
                "reason": reason,
            })

        logger.info("Escalated ticket %s: %s", ticket_id, reason)
        return ticket

    def close_ticket(self, ticket_id: str, resolution: str) -> Optional[Ticket]:
        """Close a ticket with a resolution note."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                logger.warning("Ticket %s not found for close", ticket_id)
                return None

            now = datetime.now(timezone.utc).isoformat()
            ticket.status = TicketStatus.CLOSED
            ticket.updated_at = now
            ticket.resolved_at = now
            ticket.metadata["resolution"] = resolution
            self._record_event(ticket_id, "closed", {"resolution": resolution})

        logger.info("Closed ticket %s", ticket_id)
        return ticket

    # ------------------------------------------------------------------
    # Ticket retrieval
    # ------------------------------------------------------------------

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Retrieve a single ticket by ID."""
        with self._lock:
            return self._tickets.get(ticket_id)

    def list_tickets(
        self,
        status: Optional[TicketStatus] = None,
        ticket_type: Optional[TicketType] = None,
    ) -> List[Ticket]:
        """List tickets with optional status and type filters."""
        with self._lock:
            tickets = list(self._tickets.values())

        if status is not None:
            tickets = [t for t in tickets if t.status == status]
        if ticket_type is not None:
            tickets = [t for t in tickets if t.ticket_type == ticket_type]

        tickets.sort(key=lambda t: PRIORITY_ORDER.get(t.priority, 99))
        return tickets

    # ------------------------------------------------------------------
    # Domain-specific requests
    # ------------------------------------------------------------------

    def request_remote_access(
        self,
        target_system: str,
        requester: str,
        justification: str,
        duration_hours: int = 4,
    ) -> Ticket:
        """Create a remote-access provisioning request ticket."""
        return self.create_ticket(
            title=f"Remote Access Request: {target_system}",
            description=(
                f"Requesting remote access to {target_system} for {duration_hours}h. "
                f"Justification: {justification}"
            ),
            ticket_type=TicketType.REMOTE_ACCESS,
            priority=TicketPriority.P2_HIGH,
            requester=requester,
            tags=["remote_access", "provisioning"],
            metadata={
                "target_system": target_system,
                "duration_hours": duration_hours,
                "justification": justification,
            },
        )

    def request_patch_rollback(
        self,
        target_system: str,
        version: str,
        requester: str,
        action: str = "patch",
    ) -> Ticket:
        """Create a patch or rollback automation request ticket."""
        label = "Patch" if action == "patch" else "Rollback"
        return self.create_ticket(
            title=f"{label} Request: {target_system} -> {version}",
            description=(
                f"{label} {target_system} to version {version}. "
                f"Requested by {requester}."
            ),
            ticket_type=TicketType.PATCH_ROLLBACK,
            priority=TicketPriority.P2_HIGH,
            requester=requester,
            tags=["patch_rollback", action],
            metadata={
                "target_system": target_system,
                "version": version,
                "action": action,
            },
        )

    def request_api_build(
        self,
        api_name: str,
        category: str,
        requester: str,
        description: str = "",
        env_var: str = "",
        provider: str = "",
        auto_scaffold: bool = False,
    ) -> Ticket:
        """Create an API capability build request ticket.

        Used by the WingmanSystem when validation detects that an artifact
        references live data (banking, email, stock, currency, fuel/material
        costs, etc.) that requires an external API not yet available in the
        system.

        Parameters
        ----------
        api_name:     Human-readable API name (e.g. "Plaid Bank API").
        category:     Domain category (e.g. "banking", "stock", "currency").
        requester:    User or agent that triggered the ticket.
        description:  Optional extended description of why this API is needed.
        env_var:      Suggested environment variable name for the API key.
        provider:     Suggested external provider (e.g. "Plaid", "Alpha Vantage").
        auto_scaffold: Whether the builder has already auto-generated a stub.
        """
        title = f"[API BUILD] {api_name} — {category}"
        body = (
            f"Murphy System detected that an artifact references live data in the "
            f"'{category}' domain but no corresponding API capability exists.\n\n"
            f"Required API: {api_name}\n"
            f"Suggested provider: {provider or 'TBD'}\n"
            f"Env var: {env_var or 'TBD'}\n"
            f"Auto-scaffold generated: {'yes' if auto_scaffold else 'no'}\n\n"
            f"Context: {description or 'N/A'}\n\n"
            "ACTION REQUIRED (FOUNDER/OWNER level):\n"
            "  1. Review the auto-generated stub (if present) in src/api_capabilities/.\n"
            "  2. Approve or reject this ticket via POST /api/wingman/api-gaps/build.\n"
            "  3. Once approved Murphy will complete wiring without HITL for the\n"
            "     remaining scaffold steps."
        )
        return self.create_ticket(
            title=title,
            description=body,
            ticket_type=TicketType.API_BUILD,
            priority=TicketPriority.P2_HIGH,
            requester=requester,
            tags=["api_build", category, "wingman_detected"],
            metadata={
                "api_name": api_name,
                "category": category,
                "env_var": env_var,
                "provider": provider,
                "auto_scaffold": auto_scaffold,
                "requires_owner_approval": True,
            },
        )

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current adapter status."""
        with self._lock:
            total = len(self._tickets)
            by_status: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for t in self._tickets.values():
                by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
                by_type[t.ticket_type.value] = by_type.get(t.ticket_type.value, 0) + 1
            history_size = len(self._history)

        return {
            "total_tickets": total,
            "tickets_by_status": by_status,
            "tickets_by_type": by_type,
            "history_events": history_size,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_event(self, ticket_id: str, action: str, details: Dict[str, Any]) -> None:
        """Append an audit event (caller must hold self._lock)."""
        capped_append(self._history, {
            "ticket_id": ticket_id,
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
