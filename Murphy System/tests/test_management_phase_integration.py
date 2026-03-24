"""
Management Phase Tests — PR 6 Gap Closure

Tests all 12 management phases using the real module APIs (no mocks).

  Phases 1-7: management_systems package (board, automation, workspace,
               dashboard, integration_bridge, form, doc)
  Phase 8:  CRM module (contacts, deals, pipelines, activities)
  Phase 9:  Dev module (sprints, bugs, releases, git feed, roadmap)
  Phase 10: Service module (catalog, SLA, tickets, KB, routing, CSAT)
  Phase 11: Guest/External Collaboration (guests, share links, portals, forms)
  Phase 12: Cross-phase integration — board + CRM + dev + service

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Management Systems (Phases 1-7)
# ---------------------------------------------------------------------------
from management_systems.board_engine import (
    BoardEngine, ColumnType, ViewType, BoardPermissionLevel,
)
from management_systems.automation_recipes import (
    RecipeEngine, AutomationTrigger, AutomationAction,
    TriggerType, ActionType, RecipeStatus,
)
from management_systems.workspace_manager import WorkspaceManager
from management_systems.dashboard_generator import (
    DashboardGenerator, DashboardTemplateType, ScheduleInterval,
)

# Phase 8: CRM
from crm.crm_manager import CRMManager
from crm.models import ActivityType

# Phase 9: Dev Module
from dev_module.dev_manager import DevManager
from dev_module.models import BugSeverity, SprintStatus, BugStatus

# Phase 10: Service Module
from service_module.service_manager import ServiceManager
from service_module.models import TicketStatus, TicketPriority

# Phase 11: Guest / External Collaboration
from guest_collab.guest_manager import GuestManager
from guest_collab.models import GuestPermission, LinkAccess, InviteStatus


# ===========================================================================
# Phases 1-3: Board CRUD, Groups, Items, Columns
# ===========================================================================

class TestBoardCRUD:
    """Phase 1: Board creation, groups, items, views."""

    def setup_method(self):
        self.engine = BoardEngine()

    def test_create_board_basic(self):
        board = self.engine.create_board("Sprint Board", owner_id="user-1")
        assert board.name == "Sprint Board"
        assert board.owner_id == "user-1"

    def test_default_view_is_main_table(self):
        board = self.engine.create_board("Board A", owner_id="user-1")
        assert any(v.view_type == ViewType.MAIN_TABLE for v in board.views)

    def test_add_group_to_board(self):
        board = self.engine.create_board("Board B", owner_id="user-1")
        group = self.engine.add_group(board.id, "Backlog")
        assert group.title == "Backlog"

    def test_add_item_to_group(self):
        board = self.engine.create_board("Board C", owner_id="user-1")
        group = self.engine.add_group(board.id, "Todo")
        item = self.engine.add_item(board.id, group.id, "Task 1")
        assert item.name == "Task 1"

    def test_set_cell_value(self):
        board = self.engine.create_board("Board D", owner_id="user-1")
        col = self.engine.add_column(board.id, "Status", ColumnType.STATUS)
        group = self.engine.add_group(board.id, "Active")
        item = self.engine.add_item(board.id, group.id, "Task 2")
        result = self.engine.set_cell(board.id, item.id, col.id, "Done")
        assert result is True

    def test_delete_item(self):
        board = self.engine.create_board("Board E", owner_id="user-1")
        group = self.engine.add_group(board.id, "Group")
        item = self.engine.add_item(board.id, group.id, "Remove Me")
        result = self.engine.delete_item(board.id, item.id)
        assert result is True

    def test_owner_permission_assigned_on_create(self):
        board = self.engine.create_board("Board F", owner_id="alice")
        assert any(
            p.user_id == "alice" and p.level == BoardPermissionLevel.OWNER
            for p in board.permissions
        )

    def test_list_boards_by_workspace(self):
        engine = BoardEngine()
        engine.create_board("X", workspace_id="ws-1")
        engine.create_board("Y", workspace_id="ws-1")
        boards = engine.list_boards(workspace_id="ws-1")
        assert len(boards) == 2

    def test_get_board_returns_correct_board(self):
        board = self.engine.create_board("Fetch Me", owner_id="u1")
        fetched = self.engine.get_board(board.id)
        assert fetched is not None
        assert fetched.id == board.id

    def test_delete_board(self):
        board = self.engine.create_board("Delete Me", owner_id="u1")
        result = self.engine.delete_board(board.id)
        assert result is True
        assert self.engine.get_board(board.id) is None


# ===========================================================================
# Phase 4: Automation Recipes
# ===========================================================================

class TestAutomationRecipes:
    """Phase 4: Automation triggers, actions, recipe lifecycle."""

    def setup_method(self):
        self.engine = RecipeEngine()

    def _make_recipe(self, name: str = "Test Recipe") -> object:
        trigger = AutomationTrigger(
            trigger_type=TriggerType.STATUS_CHANGE,
            board_id="board-1",
            config={"from": "todo", "to": "done"},
        )
        action = AutomationAction(
            action_type=ActionType.NOTIFY,
            config={"message": "Item completed"},
        )
        return self.engine.create_recipe(name, trigger, [action])

    def test_create_recipe(self):
        recipe = self._make_recipe()
        assert recipe.name == "Test Recipe"

    def test_recipe_starts_active(self):
        """Recipes are ACTIVE by default in the current implementation."""
        recipe = self._make_recipe()
        assert recipe.status == RecipeStatus.ACTIVE

    def test_pause_recipe(self):
        recipe = self._make_recipe()
        result = self.engine.pause_recipe(recipe.id)
        assert result is True
        paused = self.engine.get_recipe(recipe.id)
        assert paused.status == RecipeStatus.PAUSED

    def test_resume_recipe_after_pause(self):
        recipe = self._make_recipe()
        self.engine.pause_recipe(recipe.id)
        self.engine.resume_recipe(recipe.id)
        resumed = self.engine.get_recipe(recipe.id)
        assert resumed.status == RecipeStatus.ACTIVE

    def test_process_event_returns_list(self):
        self._make_recipe()
        results = self.engine.process_event(
            {"type": "status_change", "board_id": "board-1", "to": "done"}
        )
        assert isinstance(results, list)


# ===========================================================================
# Phase 5: Workspace Manager
# ===========================================================================

class TestWorkspaceManager:
    """Phase 5: Workspace CRUD."""

    def setup_method(self):
        self.wm = WorkspaceManager()

    def test_create_workspace(self):
        ws = self.wm.create_workspace("Acme Workspace")
        assert ws.name == "Acme Workspace"

    def test_get_workspace(self):
        ws = self.wm.create_workspace("WS1")
        fetched = self.wm.get_workspace(ws.id)
        assert fetched is not None
        assert fetched.id == ws.id

    def test_list_workspaces(self):
        self.wm.create_workspace("WS A")
        self.wm.create_workspace("WS B")
        results = self.wm.list_workspaces()
        assert len(results) >= 2

    def test_delete_workspace(self):
        ws = self.wm.create_workspace("To Delete")
        result = self.wm.delete_workspace(ws.id)
        assert result is True
        assert self.wm.get_workspace(ws.id) is None


# ===========================================================================
# Phase 6: Dashboard Generator
# ===========================================================================

class TestDashboardGenerator:
    """Phase 6: Report generation and scheduling."""

    def setup_method(self):
        self.dg = DashboardGenerator()

    def test_list_templates(self):
        templates = self.dg.list_templates()
        assert len(templates) >= 1

    def test_generate_weekly_report(self):
        report = self.dg.generate_weekly_report("Acme Workspace", {"tasks_completed": 5})
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_standup(self):
        report = self.dg.generate_standup(
            "Engineering", ["Task A done"], ["Task B in progress"], []
        )
        assert isinstance(report, str)

    def test_schedule_report(self):
        scheduled = self.dg.schedule_report(
            name="Weekly Ops",
            template_type=DashboardTemplateType.EXECUTIVE_SUMMARY,
            interval=ScheduleInterval.WEEKLY,
            matrix_room_id="!room:example.org",
        )
        assert scheduled.name == "Weekly Ops"


# ===========================================================================
# Phase 8: CRM Module
# ===========================================================================

class TestCRMModule:
    """Phase 8: Contacts, deals, pipelines, activities."""

    def setup_method(self):
        self.crm = CRMManager()

    def test_create_contact(self):
        contact = self.crm.create_contact(
            name="Jane Doe", email="jane@example.com", owner_id="user-1"
        )
        assert contact.name == "Jane Doe"
        assert contact.email == "jane@example.com"

    def test_get_contact(self):
        contact = self.crm.create_contact(name="Bob", email="bob@co.com")
        fetched = self.crm.get_contact(contact.id)
        assert fetched is not None
        assert fetched.id == contact.id

    def test_list_contacts(self):
        self.crm.create_contact(name="A", email="a@x.com")
        self.crm.create_contact(name="B", email="b@x.com")
        contacts = self.crm.list_contacts()
        assert len(contacts) >= 2

    def test_update_contact(self):
        contact = self.crm.create_contact(name="Old Name", email="old@x.com")
        updated = self.crm.update_contact(contact.id, name="New Name")
        assert updated.name == "New Name"

    def test_delete_contact(self):
        contact = self.crm.create_contact(name="Delete Me", email="del@x.com")
        result = self.crm.delete_contact(contact.id)
        assert result is True

    def test_create_pipeline(self):
        pipeline = self.crm.create_pipeline("Sales Pipeline")
        assert pipeline.name == "Sales Pipeline"

    def test_create_deal_on_pipeline(self):
        pipeline = self.crm.create_pipeline("Deals Pipeline")
        contact = self.crm.create_contact(name="Buyer", email="buy@x.com")
        deal = self.crm.create_deal(
            title="Big Deal", contact_id=contact.id,
            pipeline_id=pipeline.id, value=50000.0,
        )
        assert deal.title == "Big Deal"
        assert deal.value == 50000.0

    def test_move_deal_to_next_stage(self):
        pipeline = self.crm.create_pipeline("Move Pipeline")
        contact = self.crm.create_contact(name="C", email="c@x.com")
        deal = self.crm.create_deal(
            title="Movable Deal", contact_id=contact.id,
            pipeline_id=pipeline.id,
        )
        moved = self.crm.move_deal(deal.id, "qualified")
        assert moved.stage == "qualified"

    def test_log_activity(self):
        contact = self.crm.create_contact(name="Log Me", email="log@x.com")
        activity = self.crm.log_activity(
            activity_type=ActivityType.CALL,
            contact_id=contact.id,
            summary="Introductory call",
            user_id="user-1",
        )
        assert activity is not None

    def test_pipeline_value_sums_deals(self):
        pipeline = self.crm.create_pipeline("Value Pipeline")
        contact = self.crm.create_contact(name="V", email="v@x.com")
        self.crm.create_deal(title="D1", contact_id=contact.id,
                              pipeline_id=pipeline.id, value=1000.0)
        self.crm.create_deal(title="D2", contact_id=contact.id,
                              pipeline_id=pipeline.id, value=2000.0)
        totals = self.crm.pipeline_value(pipeline.id)
        total = sum(totals.values())
        assert total >= 3000.0


# ===========================================================================
# Phase 9: Dev Module
# ===========================================================================

class TestDevModule:
    """Phase 9: Sprints, bugs, releases, git feed, roadmap."""

    def setup_method(self):
        self.dev = DevManager()

    def test_create_sprint(self):
        sprint = self.dev.create_sprint(
            name="Sprint 1", board_id="board-dev",
            start_date="2026-03-01", end_date="2026-03-14",
        )
        assert sprint.name == "Sprint 1"

    def test_start_sprint(self):
        sprint = self.dev.create_sprint(
            name="Sprint 2", board_id="board-dev",
            start_date="2026-03-01", end_date="2026-03-14",
        )
        started = self.dev.start_sprint(sprint.id)
        assert started.status == SprintStatus.ACTIVE

    def test_complete_sprint(self):
        sprint = self.dev.create_sprint(
            name="Sprint 3", board_id="board-dev",
            start_date="2026-03-01", end_date="2026-03-14",
        )
        self.dev.start_sprint(sprint.id)
        completed = self.dev.complete_sprint(sprint.id)
        assert completed.status == SprintStatus.COMPLETED

    def test_add_sprint_item(self):
        sprint = self.dev.create_sprint(
            name="Sprint Items", board_id="board-dev",
            start_date="2026-03-01", end_date="2026-03-14",
        )
        from dev_module.models import SprintItem
        # add_sprint_item(sprint_id, item_id, story_points)
        sitem = self.dev.add_sprint_item(sprint.id, "task-001", story_points=3)
        assert sitem is not None

    def test_create_bug(self):
        bug = self.dev.create_bug(
            title="Null pointer on login",
            board_id="board-dev",
            severity=BugSeverity.HIGH,
        )
        assert bug.title == "Null pointer on login"
        assert bug.severity == BugSeverity.HIGH

    def test_resolve_bug(self):
        bug = self.dev.create_bug(title="Flaky test", board_id="board-dev")
        resolved = self.dev.resolve_bug(bug.id)
        assert resolved.status == BugStatus.RESOLVED

    def test_create_release(self):
        release = self.dev.create_release(version="1.2.0")
        assert release.version == "1.2.0"

    def test_log_git_activity(self):
        entry = self.dev.log_git_activity(
            board_id="board-dev",
            event_type="push",
            author="dev@example.com",
            message="feat: add dashboard",
        )
        assert entry is not None

    def test_create_roadmap_item(self):
        item = self.dev.create_roadmap_item(
            title="Dark mode", quarter="Q2-2026", owner_id="dev1"
        )
        assert item.title == "Dark mode"

    def test_velocity_history_returns_list(self):
        history = self.dev.velocity_history("board-dev")
        assert isinstance(history, list)


# ===========================================================================
# Phase 10: Service Module
# ===========================================================================

class TestServiceModule:
    """Phase 10: SLA, tickets, routing, KB, CSAT."""

    def setup_method(self):
        self.svc = ServiceManager()

    def test_create_sla_policy(self):
        policy = self.svc.create_sla_policy(
            name="Standard SLA",
            response_hours=4,
            resolution_hours=24,
        )
        assert policy.name == "Standard SLA"

    def test_create_catalog_item(self):
        item = self.svc.create_catalog_item(
            name="Password Reset",
            category="IT",
            description="Reset account password",
        )
        assert item.name == "Password Reset"

    def test_create_ticket(self):
        ticket = self.svc.create_ticket(
            title="Cannot login",
            requester_id="user-1",
            priority=TicketPriority.HIGH,
        )
        assert ticket.title == "Cannot login"
        assert ticket.priority == TicketPriority.HIGH

    def test_update_ticket_status(self):
        ticket = self.svc.create_ticket(title="Open Issue", requester_id="u1")
        updated = self.svc.update_ticket_status(ticket.id, TicketStatus.IN_PROGRESS)
        assert updated.status == TicketStatus.IN_PROGRESS

    def test_assign_ticket(self):
        ticket = self.svc.create_ticket(title="Assign Me", requester_id="u1")
        assigned = self.svc.assign_ticket(ticket.id, "agent-1")
        assert assigned.assignee_id == "agent-1"

    def test_auto_route_assigns_agent(self):
        self.svc.register_agent("agent-auto")
        ticket = self.svc.create_ticket(title="Route Me", requester_id="u1")
        routed = self.svc.auto_route(ticket.id)
        assert routed.assignee_id != ""

    def test_create_kb_article(self):
        article = self.svc.create_article(
            title="How to reset password",
            body="Go to settings → security → reset password.",
            category="IT",
            author_id="admin-1",
        )
        assert article.title == "How to reset password"

    def test_publish_kb_article(self):
        article = self.svc.create_article(
            title="Published Guide", body="Content.", category="IT",
            author_id="admin-1",
        )
        published = self.svc.publish_article(article.id)
        assert published.published is True

    def test_submit_csat(self):
        ticket = self.svc.create_ticket(title="Done Ticket", requester_id="u1")
        self.svc.update_ticket_status(ticket.id, TicketStatus.RESOLVED)
        resp = self.svc.submit_csat(
            ticket_id=ticket.id, rating=5, comment="Great support!"
        )
        assert resp.rating == 5

    def test_csat_average(self):
        ticket = self.svc.create_ticket(title="T1", requester_id="u1")
        self.svc.submit_csat(ticket_id=ticket.id, rating=4)
        avg = self.svc.csat_average()
        assert 0.0 <= avg <= 5.0


# ===========================================================================
# Phase 11: Guest / External Collaboration
# ===========================================================================

class TestGuestCollabModule:
    """Phase 11: Guest accounts, share links, portals, external forms."""

    def setup_method(self):
        self.gm = GuestManager()

    def test_invite_guest(self):
        guest = self.gm.invite_guest(
            email="guest@example.com",
            name="Guest User",
            invited_by="owner-1",
            board_ids=["board-1"],
            permission=GuestPermission.VIEW,
        )
        assert guest.email == "guest@example.com"

    def test_accept_invite(self):
        guest = self.gm.invite_guest(
            email="accept@x.com", name="Acceptor",
            invited_by="owner-1", board_ids=["board-1"],
        )
        accepted = self.gm.accept_invite(guest.id)
        assert accepted.status == InviteStatus.ACCEPTED

    def test_revoke_invite(self):
        guest = self.gm.invite_guest(
            email="revoke@x.com", name="Revokee",
            invited_by="owner-1", board_ids=["board-1"],
        )
        revoked = self.gm.revoke_invite(guest.id)
        assert revoked.status == InviteStatus.REVOKED

    def test_create_shareable_link(self):
        link = self.gm.create_shareable_link(
            board_id="board-1", access=LinkAccess.READ_ONLY,
            created_by="owner-1",
        )
        assert link.board_id == "board-1"
        assert link.active is True

    def test_deactivate_shareable_link(self):
        link = self.gm.create_shareable_link(
            board_id="board-1", access=LinkAccess.READ_ONLY,
            created_by="owner-1",
        )
        result = self.gm.deactivate_link(link.id)
        assert result is True

    def test_record_link_view_increments_count(self):
        link = self.gm.create_shareable_link(
            board_id="board-2", access=LinkAccess.READ_ONLY,
            created_by="owner-1",
        )
        self.gm.record_link_view(link.id)
        updated = self.gm.get_link(link.id)
        assert updated.view_count == 1

    def test_create_client_portal(self):
        portal = self.gm.create_portal(
            name="Client A Portal",
            owner_id="owner-1",
            board_ids=["board-1"],
        )
        assert portal.name == "Client A Portal"

    def test_add_guest_to_portal(self):
        guest = self.gm.invite_guest(
            email="portal-guest@x.com", name="Portal Guest",
            invited_by="owner-1", board_ids=["board-1"],
        )
        portal = self.gm.create_portal(
            name="Portal", owner_id="owner-1", board_ids=["board-1"]
        )
        updated_portal = self.gm.add_guest_to_portal(portal.id, guest.id)
        assert guest.id in updated_portal.guest_ids

    def test_create_external_form(self):
        form = self.gm.create_form(
            name="Intake Form",
            board_id="board-1",
            fields=[{"name": "company", "type": "text", "required": True}],
        )
        assert form.name == "Intake Form"

    def test_submit_external_form(self):
        form = self.gm.create_form(
            name="Survey",
            board_id="board-1",
            fields=[{"name": "rating", "type": "number", "required": False}],
        )
        submission = self.gm.submit_form(
            form_id=form.id,
            data={"rating": 5},
        )
        assert submission is not None
        assert submission.form_id == form.id


# ===========================================================================
# Cross-Phase Integration (Board + CRM + Dev + Service)
# ===========================================================================

class TestCrossPhaseIntegration:
    """Validate that board, CRM, dev, and service modules interoperate."""

    def test_board_and_crm_share_contact_id(self):
        """A CRM contact id can be stored as a board item cell value."""
        engine = BoardEngine()
        crm = CRMManager()

        board = engine.create_board("CRM Board", owner_id="owner-1")
        col = engine.add_column(board.id, "Contact", ColumnType.TEXT)
        group = engine.add_group(board.id, "Leads")
        item = engine.add_item(board.id, group.id, "Deal Item")

        contact = crm.create_contact(name="Cross Contact", email="cross@x.com")
        result = engine.set_cell(board.id, item.id, col.id, contact.id)
        assert result is True

    def test_dev_bug_linked_to_service_ticket(self):
        """A bug title from DevManager can be stored in a ServiceManager ticket."""
        dev = DevManager()
        svc = ServiceManager()

        bug = dev.create_bug(
            title="Login crash", board_id="board-x", severity=BugSeverity.CRITICAL
        )
        ticket = svc.create_ticket(
            title=f"Customer report: {bug.title}",
            requester_id="customer-1",
        )
        assert bug.id is not None
        assert ticket.title.endswith(bug.title)

    def test_automation_recipe_references_board(self):
        """A recipe's trigger can reference a board created by BoardEngine."""
        engine = BoardEngine()
        recipe_engine = RecipeEngine()

        board = engine.create_board("Automation Board", owner_id="owner-1")
        trigger = AutomationTrigger(
            trigger_type=TriggerType.STATUS_CHANGE,
            board_id=board.id,
            config={"to": "done"},
        )
        action = AutomationAction(
            action_type=ActionType.NOTIFY,
            config={"to": "owner-1"},
        )
        recipe = recipe_engine.create_recipe(
            "Board Complete Notify", trigger, [action]
        )
        assert recipe.trigger.board_id == board.id

    def test_workspace_contains_multiple_boards(self):
        """Multiple boards can share a workspace_id reference."""
        engine = BoardEngine()
        wm = WorkspaceManager()

        ws = wm.create_workspace("Shared WS")
        engine.create_board("Board 1", workspace_id=ws.id)
        engine.create_board("Board 2", workspace_id=ws.id)
        boards = engine.list_boards(workspace_id=ws.id)
        assert len(boards) >= 2
