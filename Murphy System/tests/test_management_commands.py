"""
Tests for management_systems.management_commands module.

Covers all 9 command handlers wired into the Matrix command dispatcher:
  1. board    — list, create, view, kanban, add-item, delete
  2. status   — list, create
  3. timeline — view, add, milestones, critical-path, auto-schedule
  4. recipe   — list, create, templates, delete
  5. workspace — list, bootstrap, show
  6. dashboard — standup, weekly, project, widget
  7. sync     — status, rules, run, history
  8. form     — list, start
  9. doc      — list, create, view, search, versions, link
"""

import os


import pytest
from types import SimpleNamespace

from management_systems.management_commands import (
    MANAGEMENT_COMMAND_HANDLERS,
    handle_board,
    handle_dashboard,
    handle_doc,
    handle_form,
    handle_recipe,
    handle_status,
    handle_sync,
    handle_timeline,
    handle_workspace,
    reset_engines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmd(subcommand=None, args=None, sender="@tester:localhost", room_id="!room:test"):
    """Build a minimal ParsedCommand-like namespace for testing."""
    return SimpleNamespace(
        prefix="!murphy",
        command="",
        subcommand=subcommand,
        args=args or [],
        kwargs={},
        raw="",
        sender=sender,
        room_id=room_id,
        timestamp="2026-01-01T00:00:00Z",
    )


DISPATCHER = None  # handlers accept dispatcher but don't depend on it for management commands


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_engines():
    """Reset all engine singletons between tests."""
    reset_engines()
    yield
    reset_engines()


# ---------------------------------------------------------------------------
# Board handler
# ---------------------------------------------------------------------------


class TestHandleBoard:
    def test_list_empty(self):
        resp = handle_board(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No boards found" in resp.message

    def test_create_board(self):
        resp = handle_board(DISPATCHER, _cmd("create", ["Sprint 1"]))
        assert resp.success
        assert "Sprint 1" in resp.message

    def test_create_then_list(self):
        handle_board(DISPATCHER, _cmd("create", ["My Board"]))
        resp = handle_board(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "My Board" in resp.message

    def test_view_missing(self):
        resp = handle_board(DISPATCHER, _cmd("view", ["nonexistent"]))
        assert not resp.success
        assert "not found" in resp.message

    def test_view_no_args(self):
        resp = handle_board(DISPATCHER, _cmd("view"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_kanban_no_args(self):
        resp = handle_board(DISPATCHER, _cmd("kanban"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_add_item_no_args(self):
        resp = handle_board(DISPATCHER, _cmd("add-item"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_delete_no_args(self):
        resp = handle_board(DISPATCHER, _cmd("delete"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_delete_missing(self):
        resp = handle_board(DISPATCHER, _cmd("delete", ["nonexistent"]))
        assert not resp.success
        assert "not found" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_board(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message

    def test_default_subcommand_is_list(self):
        resp = handle_board(DISPATCHER, _cmd())
        assert resp.success
        assert "Boards" in resp.message


# ---------------------------------------------------------------------------
# Status handler
# ---------------------------------------------------------------------------


class TestHandleStatus:
    def test_list_empty(self):
        resp = handle_status(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No status columns" in resp.message

    def test_create_column(self):
        resp = handle_status(DISPATCHER, _cmd("create", ["Priority"]))
        assert resp.success
        assert "Priority" in resp.message

    def test_create_then_list(self):
        handle_status(DISPATCHER, _cmd("create", ["Priority"]))
        resp = handle_status(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "Priority" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_status(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Timeline handler
# ---------------------------------------------------------------------------


class TestHandleTimeline:
    def test_view_empty(self):
        resp = handle_timeline(DISPATCHER, _cmd("view"))
        assert resp.success
        assert "No timeline items" in resp.message

    def test_add_item(self):
        resp = handle_timeline(DISPATCHER, _cmd("add", ["Task1", "2026-01-01", "2026-01-10"]))
        assert resp.success
        assert "Task1" in resp.message

    def test_add_then_view(self):
        handle_timeline(DISPATCHER, _cmd("add", ["Task1", "2026-01-01", "2026-01-10"]))
        resp = handle_timeline(DISPATCHER, _cmd("view"))
        assert resp.success
        assert "Timeline" in resp.message

    def test_add_no_args(self):
        resp = handle_timeline(DISPATCHER, _cmd("add"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_milestones_empty(self):
        resp = handle_timeline(DISPATCHER, _cmd("milestones"))
        assert resp.success
        assert "No milestones" in resp.message

    def test_critical_path_empty(self):
        resp = handle_timeline(DISPATCHER, _cmd("critical-path"))
        assert resp.success
        assert "Critical Path" in resp.message

    def test_auto_schedule_no_args(self):
        resp = handle_timeline(DISPATCHER, _cmd("auto-schedule"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_timeline(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Recipe handler
# ---------------------------------------------------------------------------


class TestHandleRecipe:
    def test_list_empty(self):
        resp = handle_recipe(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No recipes" in resp.message or "No manual recipes" in resp.message

    def test_create_recipe(self):
        resp = handle_recipe(DISPATCHER, _cmd("create", ["Auto-Status"]))
        assert resp.success
        assert "Auto-Status" in resp.message

    def test_create_then_list(self):
        handle_recipe(DISPATCHER, _cmd("create", ["My Recipe"]))
        resp = handle_recipe(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "My Recipe" in resp.message

    def test_delete_no_args(self):
        resp = handle_recipe(DISPATCHER, _cmd("delete"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_delete_missing(self):
        resp = handle_recipe(DISPATCHER, _cmd("delete", ["nonexistent"]))
        assert not resp.success

    def test_run_no_args(self):
        resp = handle_recipe(DISPATCHER, _cmd("run"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_templates(self):
        resp = handle_recipe(DISPATCHER, _cmd("templates"))
        assert resp.success
        assert "Template" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_recipe(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Workspace handler
# ---------------------------------------------------------------------------


class TestHandleWorkspace:
    def test_list_empty(self):
        resp = handle_workspace(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No workspaces" in resp.message or "Workspace" in resp.message

    def test_bootstrap(self):
        resp = handle_workspace(DISPATCHER, _cmd("bootstrap"))
        assert resp.success
        assert "Bootstrapped" in resp.message

    def test_bootstrap_then_list(self):
        handle_workspace(DISPATCHER, _cmd("bootstrap"))
        resp = handle_workspace(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "Workspace" in resp.message

    def test_show_no_args(self):
        resp = handle_workspace(DISPATCHER, _cmd("show"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_show_missing(self):
        resp = handle_workspace(DISPATCHER, _cmd("show", ["nonexistent"]))
        assert not resp.success
        assert "not found" in resp.message

    def test_show_after_bootstrap(self):
        handle_workspace(DISPATCHER, _cmd("bootstrap"))
        resp = handle_workspace(DISPATCHER, _cmd("show", ["ai_ml_pipeline"]))
        assert resp.success
        assert "ai_ml_pipeline" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_workspace(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Dashboard handler
# ---------------------------------------------------------------------------


class TestHandleDashboard:
    def test_standup(self):
        resp = handle_dashboard(DISPATCHER, _cmd("standup"))
        assert resp.success

    def test_standup_with_team(self):
        resp = handle_dashboard(DISPATCHER, _cmd("standup", ["Platform"]))
        assert resp.success

    def test_weekly(self):
        resp = handle_dashboard(DISPATCHER, _cmd("weekly"))
        assert resp.success

    def test_project_no_args(self):
        resp = handle_dashboard(DISPATCHER, _cmd("project"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_widget(self):
        resp = handle_dashboard(DISPATCHER, _cmd("widget"))
        assert resp.success
        assert "Template" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_dashboard(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Sync handler
# ---------------------------------------------------------------------------


class TestHandleSync:
    def test_status(self):
        resp = handle_sync(DISPATCHER, _cmd("status"))
        assert resp.success
        assert "Sync" in resp.message or "Status" in resp.message

    def test_rules_empty(self):
        resp = handle_sync(DISPATCHER, _cmd("rules"))
        assert resp.success
        assert "No rules" in resp.message or "Rule" in resp.message

    def test_run_bootstrap(self):
        resp = handle_sync(DISPATCHER, _cmd("run"))
        assert resp.success
        assert "Bootstrapped" in resp.message

    def test_run_then_rules(self):
        handle_sync(DISPATCHER, _cmd("run"))
        resp = handle_sync(DISPATCHER, _cmd("rules"))
        assert resp.success
        assert "Sync Rules" in resp.message

    def test_history_empty(self):
        resp = handle_sync(DISPATCHER, _cmd("history"))
        assert resp.success
        assert "No sync events" in resp.message or "History" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_sync(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Form handler
# ---------------------------------------------------------------------------


class TestHandleForm:
    def test_list_empty(self):
        resp = handle_form(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No forms" in resp.message or "Form" in resp.message

    def test_start_no_args(self):
        resp = handle_form(DISPATCHER, _cmd("start"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_start_invalid_template(self):
        resp = handle_form(DISPATCHER, _cmd("start", ["nonexistent_type"]))
        assert not resp.success
        assert "Unknown form template" in resp.message

    def test_start_bug_report(self):
        resp = handle_form(DISPATCHER, _cmd("start", ["bug_report"]))
        assert resp.success
        assert "started" in resp.message.lower() or "Bug" in resp.message

    def test_submit_no_args(self):
        resp = handle_form(DISPATCHER, _cmd("submit"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_responses_no_args(self):
        resp = handle_form(DISPATCHER, _cmd("responses"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_form(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Doc handler
# ---------------------------------------------------------------------------


class TestHandleDoc:
    def test_list_empty(self):
        resp = handle_doc(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "No documents" in resp.message

    def test_create_no_args(self):
        resp = handle_doc(DISPATCHER, _cmd("create"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_create_invalid_type(self):
        resp = handle_doc(DISPATCHER, _cmd("create", ["bad_type", "My Doc"]))
        assert not resp.success
        assert "Unknown doc type" in resp.message

    def test_create_meeting_notes(self):
        resp = handle_doc(DISPATCHER, _cmd("create", ["meeting_notes", "Sprint Review"]))
        assert resp.success
        assert "Sprint Review" in resp.message

    def test_create_then_list(self):
        handle_doc(DISPATCHER, _cmd("create", ["spec", "API Design"]))
        resp = handle_doc(DISPATCHER, _cmd("list"))
        assert resp.success
        assert "API Design" in resp.message

    def test_view_no_args(self):
        resp = handle_doc(DISPATCHER, _cmd("view"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_view_missing(self):
        resp = handle_doc(DISPATCHER, _cmd("view", ["nonexistent"]))
        assert not resp.success
        assert "not found" in resp.message

    def test_search_no_args(self):
        resp = handle_doc(DISPATCHER, _cmd("search"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_search_no_results(self):
        resp = handle_doc(DISPATCHER, _cmd("search", ["nonexistent_query"]))
        assert resp.success
        assert "No documents match" in resp.message

    def test_versions_no_args(self):
        resp = handle_doc(DISPATCHER, _cmd("versions"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_versions_missing(self):
        resp = handle_doc(DISPATCHER, _cmd("versions", ["nonexistent"]))
        assert not resp.success
        assert "not found" in resp.message

    def test_link_no_args(self):
        resp = handle_doc(DISPATCHER, _cmd("link"))
        assert not resp.success
        assert "Usage" in resp.message

    def test_unknown_subcommand(self):
        resp = handle_doc(DISPATCHER, _cmd("foobar"))
        assert not resp.success
        assert "Unknown" in resp.message


# ---------------------------------------------------------------------------
# Module-level exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_handler_dict_has_all_commands(self):
        expected = {"board", "status-label", "timeline", "recipe", "workspace",
                    "dashboard", "sync", "form", "doc", "onboard", "gate",
                    "setpoint", "schedule", "skm", "automation",
                    "production", "campaign"}
        assert set(MANAGEMENT_COMMAND_HANDLERS.keys()) == expected

    def test_all_handlers_callable(self):
        for name, handler in MANAGEMENT_COMMAND_HANDLERS.items():
            assert callable(handler), f"Handler for '{name}' is not callable"

    def test_reset_engines_callable(self):
        assert callable(reset_engines)
        reset_engines()  # should not raise


# ---------------------------------------------------------------------------
# Integration: command_dispatcher wiring
# ---------------------------------------------------------------------------


class TestDispatcherWiring:
    def test_dispatcher_has_management_commands(self):
        """CommandDispatcher registers all management command handlers."""
        from matrix_bridge.command_dispatcher import CommandDispatcher
        from matrix_bridge.config import build_default_config

        cfg = build_default_config("test.local")
        dispatcher = CommandDispatcher(cfg, None)
        commands = {c["command"] for c in dispatcher.list_commands()}
        for mgmt_cmd in ["board", "status-label", "timeline", "recipe",
                           "workspace", "dashboard", "sync", "form", "doc"]:
            assert mgmt_cmd in commands, f"Missing command: {mgmt_cmd}"

    def test_dispatch_board_list(self):
        """Full round-trip: parse + dispatch !murphy board list."""
        from matrix_bridge.command_dispatcher import CommandDispatcher
        from matrix_bridge.config import build_default_config

        cfg = build_default_config("test.local")
        dispatcher = CommandDispatcher(cfg, None)
        cmd = dispatcher.parse("!murphy board list", "@user:test", "!room:test")
        assert cmd is not None
        resp = dispatcher.dispatch(cmd)
        assert resp.success
        assert "Boards" in resp.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
