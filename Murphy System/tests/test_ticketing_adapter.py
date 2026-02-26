"""Tests for the Ticketing / ITSM Integration Adapter."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.ticketing_adapter import (
    Ticket,
    TicketingAdapter,
    TicketPriority,
    TicketStatus,
    TicketType,
)


@pytest.fixture
def adapter():
    return TicketingAdapter()


# ------------------------------------------------------------------
# Ticket creation
# ------------------------------------------------------------------

class TestTicketCreation:
    """Verify ticket creation for every ticket type."""

    @pytest.mark.parametrize("ttype", list(TicketType))
    def test_create_ticket_all_types(self, adapter, ttype):
        ticket = adapter.create_ticket(
            title=f"Test {ttype.value}",
            description="desc",
            ticket_type=ttype,
            priority=TicketPriority.P3_MEDIUM,
            requester="user@test.com",
        )
        assert isinstance(ticket, Ticket)
        assert ticket.ticket_type == ttype
        assert ticket.status == TicketStatus.OPEN
        assert ticket.ticket_id.startswith("TKT-")

    def test_create_ticket_with_tags_and_metadata(self, adapter):
        ticket = adapter.create_ticket(
            title="Tagged",
            description="d",
            ticket_type=TicketType.INCIDENT,
            priority=TicketPriority.P1_CRITICAL,
            requester="admin",
            tags=["urgent", "network"],
            metadata={"source": "monitoring"},
        )
        assert ticket.tags == ["urgent", "network"]
        assert ticket.metadata["source"] == "monitoring"

    def test_create_ticket_defaults(self, adapter):
        ticket = adapter.create_ticket(
            title="Defaults",
            description="d",
            ticket_type=TicketType.SERVICE_REQUEST,
            priority=TicketPriority.P4_LOW,
            requester="user",
        )
        assert ticket.tags == []
        assert ticket.assignee is None
        assert ticket.resolved_at is None
        assert ticket.created_at is not None
        assert ticket.updated_at is not None


# ------------------------------------------------------------------
# Ticket lifecycle
# ------------------------------------------------------------------

class TestTicketLifecycle:
    """Create → update → escalate → close flow."""

    def test_update_status_and_assignee(self, adapter):
        ticket = adapter.create_ticket("T", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        updated = adapter.update_ticket(ticket.ticket_id, status=TicketStatus.IN_PROGRESS, assignee="eng1")
        assert updated is not None
        assert updated.status == TicketStatus.IN_PROGRESS
        assert updated.assignee == "eng1"

    def test_update_with_notes(self, adapter):
        ticket = adapter.create_ticket("T", "d", TicketType.PROBLEM, TicketPriority.P3_MEDIUM, "u")
        updated = adapter.update_ticket(ticket.ticket_id, notes="investigating root cause")
        assert updated is not None
        assert len(updated.metadata["notes"]) == 1
        assert updated.metadata["notes"][0]["text"] == "investigating root cause"

    def test_update_nonexistent_ticket(self, adapter):
        assert adapter.update_ticket("FAKE-ID") is None

    def test_escalate_ticket(self, adapter):
        ticket = adapter.create_ticket("T", "d", TicketType.INCIDENT, TicketPriority.P1_CRITICAL, "u")
        escalated = adapter.escalate_ticket(ticket.ticket_id, "SLA breach")
        assert escalated is not None
        assert escalated.status == TicketStatus.ESCALATED
        assert escalated.metadata["escalation_reason"] == "SLA breach"

    def test_escalate_nonexistent_ticket(self, adapter):
        assert adapter.escalate_ticket("FAKE-ID", "reason") is None

    def test_close_ticket(self, adapter):
        ticket = adapter.create_ticket("T", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        closed = adapter.close_ticket(ticket.ticket_id, "Fixed in v2.1")
        assert closed is not None
        assert closed.status == TicketStatus.CLOSED
        assert closed.resolved_at is not None
        assert closed.metadata["resolution"] == "Fixed in v2.1"

    def test_close_nonexistent_ticket(self, adapter):
        assert adapter.close_ticket("FAKE-ID", "res") is None

    def test_full_lifecycle(self, adapter):
        ticket = adapter.create_ticket("LC", "d", TicketType.CHANGE_REQUEST, TicketPriority.P3_MEDIUM, "u")
        adapter.update_ticket(ticket.ticket_id, status=TicketStatus.IN_PROGRESS, assignee="eng")
        adapter.escalate_ticket(ticket.ticket_id, "needs manager approval")
        closed = adapter.close_ticket(ticket.ticket_id, "approved and deployed")
        assert closed.status == TicketStatus.CLOSED
        assert closed.resolved_at is not None


# ------------------------------------------------------------------
# Remote access request
# ------------------------------------------------------------------

class TestRemoteAccess:
    def test_request_remote_access(self, adapter):
        ticket = adapter.request_remote_access("prod-db-01", "ops@co.com", "emergency maintenance", 2)
        assert ticket.ticket_type == TicketType.REMOTE_ACCESS
        assert ticket.priority == TicketPriority.P2_HIGH
        assert "remote_access" in ticket.tags
        assert ticket.metadata["target_system"] == "prod-db-01"
        assert ticket.metadata["duration_hours"] == 2

    def test_request_remote_access_default_duration(self, adapter):
        ticket = adapter.request_remote_access("staging", "dev", "debugging")
        assert ticket.metadata["duration_hours"] == 4


# ------------------------------------------------------------------
# Patch / rollback request
# ------------------------------------------------------------------

class TestPatchRollback:
    def test_request_patch(self, adapter):
        ticket = adapter.request_patch_rollback("api-server", "3.2.1", "release-eng", action="patch")
        assert ticket.ticket_type == TicketType.PATCH_ROLLBACK
        assert "patch" in ticket.tags
        assert ticket.metadata["action"] == "patch"
        assert ticket.metadata["version"] == "3.2.1"

    def test_request_rollback(self, adapter):
        ticket = adapter.request_patch_rollback("api-server", "3.1.0", "release-eng", action="rollback")
        assert "rollback" in ticket.tags
        assert ticket.metadata["action"] == "rollback"
        assert "Rollback" in ticket.title


# ------------------------------------------------------------------
# Listing and filtering
# ------------------------------------------------------------------

class TestListTickets:
    def test_list_all(self, adapter):
        adapter.create_ticket("A", "d", TicketType.INCIDENT, TicketPriority.P3_MEDIUM, "u")
        adapter.create_ticket("B", "d", TicketType.PROBLEM, TicketPriority.P1_CRITICAL, "u")
        tickets = adapter.list_tickets()
        assert len(tickets) == 2
        # sorted by priority: P1 first
        assert tickets[0].priority == TicketPriority.P1_CRITICAL

    def test_filter_by_status(self, adapter):
        t1 = adapter.create_ticket("A", "d", TicketType.INCIDENT, TicketPriority.P3_MEDIUM, "u")
        adapter.create_ticket("B", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        adapter.close_ticket(t1.ticket_id, "done")
        open_tickets = adapter.list_tickets(status=TicketStatus.OPEN)
        assert len(open_tickets) == 1

    def test_filter_by_type(self, adapter):
        adapter.create_ticket("A", "d", TicketType.INCIDENT, TicketPriority.P3_MEDIUM, "u")
        adapter.create_ticket("B", "d", TicketType.PROBLEM, TicketPriority.P2_HIGH, "u")
        incidents = adapter.list_tickets(ticket_type=TicketType.INCIDENT)
        assert len(incidents) == 1
        assert incidents[0].ticket_type == TicketType.INCIDENT

    def test_filter_by_status_and_type(self, adapter):
        adapter.create_ticket("A", "d", TicketType.INCIDENT, TicketPriority.P3_MEDIUM, "u")
        t2 = adapter.create_ticket("B", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        adapter.close_ticket(t2.ticket_id, "done")
        result = adapter.list_tickets(status=TicketStatus.OPEN, ticket_type=TicketType.INCIDENT)
        assert len(result) == 1

    def test_get_ticket(self, adapter):
        ticket = adapter.create_ticket("G", "d", TicketType.INCIDENT, TicketPriority.P4_LOW, "u")
        fetched = adapter.get_ticket(ticket.ticket_id)
        assert fetched is not None
        assert fetched.ticket_id == ticket.ticket_id

    def test_get_ticket_not_found(self, adapter):
        assert adapter.get_ticket("NOPE") is None


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, adapter):
        status = adapter.get_status()
        assert status["total_tickets"] == 0
        assert status["tickets_by_status"] == {}
        assert status["tickets_by_type"] == {}
        assert status["history_events"] == 0

    def test_status_after_operations(self, adapter):
        t = adapter.create_ticket("S", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        adapter.close_ticket(t.ticket_id, "res")
        status = adapter.get_status()
        assert status["total_tickets"] == 1
        assert status["tickets_by_status"]["closed"] == 1
        assert status["tickets_by_type"]["incident"] == 1
        assert status["history_events"] == 2  # created + closed


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_ticket_creation(self, adapter):
        results = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(
                    adapter.create_ticket,
                    f"T-{i}", "d", TicketType.INCIDENT, TicketPriority.P3_MEDIUM, "u",
                )
                for i in range(50)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 50
        ids = {t.ticket_id for t in results}
        assert len(ids) == 50  # all unique
        assert adapter.get_status()["total_tickets"] == 50

    def test_concurrent_mixed_operations(self, adapter):
        ticket = adapter.create_ticket("Base", "d", TicketType.INCIDENT, TicketPriority.P2_HIGH, "u")
        errors = []

        def worker(i):
            try:
                if i % 3 == 0:
                    adapter.update_ticket(ticket.ticket_id, notes=f"note-{i}")
                elif i % 3 == 1:
                    adapter.list_tickets()
                else:
                    adapter.get_status()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
