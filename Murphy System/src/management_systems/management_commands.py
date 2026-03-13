"""
Management Commands — Chat command handlers for Management Systems.

Provides handler functions that wire ``!murphy`` chat commands to the
actual :mod:`management_systems` engines (BoardEngine, StatusEngine,
TimelineEngine, RecipeEngine, WorkspaceManager, DashboardGenerator,
IntegrationBridge, FormBuilder, DocManager).

Each handler follows the ``(dispatcher, parsed_command) → response``
pattern used by :class:`~matrix_bridge.command_dispatcher.CommandDispatcher`.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .board_engine import BoardEngine, ColumnType, TemplateType, ViewType
from .status_engine import StatusEngine
from .timeline_engine import TimelineEngine, DependencyType
from .automation_recipes import RecipeEngine, AutomationTrigger, TriggerType, ActionType
from .workspace_manager import WorkspaceManager
from .dashboard_generator import DashboardGenerator, DashboardTemplateType
from .integration_bridge import IntegrationBridge
from .form_builder import FormBuilder, FormTemplateType
from .doc_manager import DocManager, DocType

if TYPE_CHECKING:
    from matrix_bridge.command_dispatcher import CommandDispatcher, CommandResponse, ParsedCommand

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared engine singletons (lazy-initialised)
# ---------------------------------------------------------------------------

_board_engine: BoardEngine | None = None
_status_engine: StatusEngine | None = None
_timeline_engine: TimelineEngine | None = None
_recipe_engine: RecipeEngine | None = None
_workspace_manager: WorkspaceManager | None = None
_dashboard_generator: DashboardGenerator | None = None
_integration_bridge: IntegrationBridge | None = None
_form_builder: FormBuilder | None = None
_doc_manager: DocManager | None = None
_onboarding_flow: "OnboardingFlow | None" = None
_gate_generator: "BusinessGateGenerator | None" = None


def _get_onboarding_flow():
    global _onboarding_flow
    if _onboarding_flow is None:
        from onboarding_flow import OnboardingFlow
        _onboarding_flow = OnboardingFlow()
    return _onboarding_flow


def _get_gate_generator():
    global _gate_generator
    if _gate_generator is None:
        from executive_planning_engine import BusinessGateGenerator
        _gate_generator = BusinessGateGenerator()
    return _gate_generator


def _get_board_engine() -> BoardEngine:
    global _board_engine
    if _board_engine is None:
        _board_engine = BoardEngine()
    return _board_engine


def _get_status_engine() -> StatusEngine:
    global _status_engine
    if _status_engine is None:
        _status_engine = StatusEngine()
    return _status_engine


def _get_timeline_engine() -> TimelineEngine:
    global _timeline_engine
    if _timeline_engine is None:
        _timeline_engine = TimelineEngine()
    return _timeline_engine


def _get_recipe_engine() -> RecipeEngine:
    global _recipe_engine
    if _recipe_engine is None:
        _recipe_engine = RecipeEngine()
    return _recipe_engine


def _get_workspace_manager() -> WorkspaceManager:
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager


def _get_dashboard_generator() -> DashboardGenerator:
    global _dashboard_generator
    if _dashboard_generator is None:
        _dashboard_generator = DashboardGenerator()
    return _dashboard_generator


def _get_integration_bridge() -> IntegrationBridge:
    global _integration_bridge
    if _integration_bridge is None:
        _integration_bridge = IntegrationBridge()
    return _integration_bridge


def _get_form_builder() -> FormBuilder:
    global _form_builder
    if _form_builder is None:
        _form_builder = FormBuilder()
    return _form_builder


def _get_doc_manager() -> DocManager:
    global _doc_manager
    if _doc_manager is None:
        _doc_manager = DocManager()
    return _doc_manager


def reset_engines() -> None:
    """Reset all engine singletons (useful for testing)."""
    global _board_engine, _status_engine, _timeline_engine, _recipe_engine
    global _workspace_manager, _dashboard_generator, _integration_bridge
    global _form_builder, _doc_manager, _onboarding_flow, _gate_generator
    _board_engine = None
    _status_engine = None
    _timeline_engine = None
    _recipe_engine = None
    _workspace_manager = None
    _dashboard_generator = None
    _integration_bridge = None
    _form_builder = None
    _doc_manager = None
    _onboarding_flow = None
    _gate_generator = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_response(success: bool, message: str, **kwargs):
    """Create a CommandResponse without importing at module level."""
    from matrix_bridge.command_dispatcher import CommandResponse
    return CommandResponse(success=success, message=message, format="markdown", **kwargs)


# ---------------------------------------------------------------------------
# !murphy board [list|create NAME|view ID|kanban ID|add-item|delete]
# ---------------------------------------------------------------------------

def handle_board(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy board`` commands.

    Subcommands:
        list           — list all boards
        create <name>  — create a new board
        view <id>      — render a board as an ASCII table
        kanban <id>    — render board in Kanban view
        add-item <board_id> <group_id> <name> — add an item
        delete <id>    — delete a board
    """
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    sender = getattr(cmd, "sender", "unknown")
    engine = _get_board_engine()

    if sub == "list":
        boards = engine.list_boards()
        if not boards:
            return _make_response(True, "## Boards\n\nNo boards found. Use `!murphy board create <name>` to create one.")
        lines = ["## Boards\n"]
        lines.append("| Name | ID | Items | Owner |")
        lines.append("|------|-----|-------|-------|")
        for b in boards:
            item_count = sum(len(g.items) for g in b.groups)
            lines.append(f"| {b.name} | `{b.id[:8]}` | {item_count} | {b.owner_id or '—'} |")
        return _make_response(True, "\n".join(lines))

    if sub == "create":
        name = " ".join(args) if args else "Untitled Board"
        board = engine.create_board(name, owner_id=sender)
        return _make_response(True, f"✅ Board **{board.name}** created (`{board.id[:8]}`).")

    if sub == "view":
        board_id = args[0] if args else None
        if not board_id:
            return _make_response(False, "Usage: `!murphy board view <board-id>`")
        board = _find_board(engine, board_id)
        if not board:
            return _make_response(False, f"Board `{board_id}` not found.")
        table = engine.render_table(board.id)
        return _make_response(True, f"## {board.name}\n\n```\n{table}\n```")

    if sub == "kanban":
        board_id = args[0] if args else None
        if not board_id:
            return _make_response(False, "Usage: `!murphy board kanban <board-id>`")
        board = _find_board(engine, board_id)
        if not board:
            return _make_response(False, f"Board `{board_id}` not found.")
        kanban = engine.render_kanban(board.id)
        return _make_response(True, f"## {board.name} — Kanban\n\n```\n{kanban}\n```")

    if sub == "add-item":
        if len(args) < 3:
            return _make_response(False, "Usage: `!murphy board add-item <board-id> <group-id> <name>`")
        board_id, group_id = args[0], args[1]
        item_name = " ".join(args[2:])
        board = _find_board(engine, board_id)
        if not board:
            return _make_response(False, f"Board `{board_id}` not found.")
        item = engine.add_item(board.id, group_id, item_name)
        return _make_response(True, f"✅ Item **{item.name}** added (`{item.id[:8]}`).")

    if sub == "delete":
        board_id = args[0] if args else None
        if not board_id:
            return _make_response(False, "Usage: `!murphy board delete <board-id>`")
        board = _find_board(engine, board_id)
        if not board:
            return _make_response(False, f"Board `{board_id}` not found.")
        engine.delete_board(board.id)
        return _make_response(True, f"🗑️ Board `{board_id}` deleted.")

    return _make_response(False, f"Unknown board subcommand `{sub}`. Try: list, create, view, kanban, add-item, delete.")


def _find_board(engine: BoardEngine, partial_id: str):
    """Look up a board by full ID or prefix match."""
    board = engine.get_board(partial_id)
    if board:
        return board
    for b in engine.list_boards():
        if b.id.startswith(partial_id):
            return b
    return None


# ---------------------------------------------------------------------------
# !murphy status-label [list|create NAME|set ITEM STATUS|progress]
# ---------------------------------------------------------------------------

def handle_status(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy status-label`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    engine = _get_status_engine()

    if sub == "list":
        columns = engine.list_columns()
        if not columns:
            return _make_response(True, "## Status Columns\n\nNo status columns. Use `!murphy status-label create <name>`.")
        lines = ["## Status Columns\n"]
        for col in columns:
            label_list = ", ".join(f"`{l.key}` ({l.color})" for l in col.labels)
            lines.append(f"- **{col.title}** (`{col.id[:8]}`): {label_list or 'no labels'}")
        return _make_response(True, "\n".join(lines))

    if sub == "create":
        name = " ".join(args) if args else "Status"
        col = engine.create_column(name)
        return _make_response(True, f"✅ Status column **{col.title}** created (`{col.id[:8]}`).")

    if sub == "set":
        if len(args) < 3:
            return _make_response(False, "Usage: `!murphy status-label set <board-id> <item-id> <column-id> <key>`")
        return _make_response(True, "Status set. *(Use board engine for item-level status changes.)*")

    if sub == "progress":
        return _make_response(True, "Progress tracking. *(Supply board-id and item-ids to calculate.)*")

    return _make_response(False, f"Unknown status-label subcommand `{sub}`. Try: list, create, set, progress.")


# ---------------------------------------------------------------------------
# !murphy timeline [view|add|milestones|critical-path|auto-schedule]
# ---------------------------------------------------------------------------

def handle_timeline(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy timeline`` commands."""
    sub = getattr(cmd, "subcommand", None) or "view"
    args = getattr(cmd, "args", [])
    engine = _get_timeline_engine()

    if sub == "view":
        items = engine.list_items()
        if not items:
            return _make_response(True, "## Timeline\n\nNo timeline items. Use `!murphy timeline add <name> <start> <end>`.")
        gantt = engine.render_gantt()
        return _make_response(True, f"## Timeline\n\n```\n{gantt}\n```")

    if sub == "add":
        if len(args) < 3:
            return _make_response(False, "Usage: `!murphy timeline add <name> <start-date> <end-date>`")
        name, start, end = args[0], args[1], args[2]
        item = engine.add_item(name, start, end)
        return _make_response(True, f"✅ Timeline item **{item.name}** added ({start} → {end}).")

    if sub == "milestones":
        milestones = engine.list_milestones()
        if not milestones:
            return _make_response(True, "## Milestones\n\nNo milestones defined.")
        lines = ["## Milestones\n"]
        for m in milestones:
            status = "✅" if m.completed else "◇"
            lines.append(f"- {status} **{m.name}** — {m.target_date}")
        return _make_response(True, "\n".join(lines))

    if sub == "critical-path":
        cp = engine.calculate_critical_path()
        if not cp.item_ids:
            return _make_response(True, "## Critical Path\n\nNo items on the critical path (add dependencies first).")
        lines = ["## Critical Path\n"]
        lines.append(f"**Total duration:** {cp.total_duration_days} days\n")
        for item_id in cp.item_ids:
            item = engine.get_item(item_id)
            if item:
                lines.append(f"- {item.name} ({item.start_date} → {item.end_date})")
            else:
                lines.append(f"- `{item_id}`")
        return _make_response(True, "\n".join(lines))

    if sub == "auto-schedule":
        start = args[0] if args else None
        if not start:
            return _make_response(False, "Usage: `!murphy timeline auto-schedule <project-start-date>`")
        schedule = engine.auto_schedule(start)
        if not schedule:
            return _make_response(True, "No items to schedule.")
        lines = ["## Auto-Schedule Results\n"]
        for item_id, (s, e) in schedule.items():
            lines.append(f"- `{item_id[:8]}`: {s} → {e}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown timeline subcommand `{sub}`. Try: view, add, milestones, critical-path, auto-schedule.")


# ---------------------------------------------------------------------------
# !murphy recipe [list|create|run ID|delete ID|templates]
# ---------------------------------------------------------------------------

def handle_recipe(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy recipe`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    engine = _get_recipe_engine()

    if sub == "list":
        recipes = engine.list_recipes()
        if not recipes:
            return _make_response(True, "## Automation Recipes\n\nNo recipes defined. Use `!murphy recipe create <name>` or `!murphy recipe templates`.")
        lines = ["## Automation Recipes\n"]
        lines.append("| Name | Trigger | Status | Executions |")
        lines.append("|------|---------|--------|------------|")
        for r in recipes:
            execs = len([e for e in engine.get_execution_log() if e.recipe_id == r.id])
            lines.append(f"| {r.name} | {r.trigger.trigger_type.value} | {r.status.value} | {execs} |")
        return _make_response(True, "\n".join(lines))

    if sub == "create":
        name = " ".join(args) if args else "New Recipe"
        trigger = AutomationTrigger(trigger_type=TriggerType.STATUS_CHANGE)
        recipe = engine.create_recipe(name, trigger)
        return _make_response(True, f"✅ Recipe **{recipe.name}** created (`{recipe.id[:8]}`).")

    if sub == "run":
        recipe_id = args[0] if args else None
        if not recipe_id:
            return _make_response(False, "Usage: `!murphy recipe run <recipe-id>`")
        recipe = engine.get_recipe(recipe_id)
        if not recipe:
            return _make_response(False, f"Recipe `{recipe_id}` not found.")
        results = engine.process_event({"recipe_id": recipe.id, "type": "manual_trigger"})
        return _make_response(True, f"⚡ Recipe **{recipe.name}** triggered. {len(results)} action(s) executed.")

    if sub == "delete":
        recipe_id = args[0] if args else None
        if not recipe_id:
            return _make_response(False, "Usage: `!murphy recipe delete <recipe-id>`")
        ok = engine.delete_recipe(recipe_id)
        if not ok:
            return _make_response(False, f"Recipe `{recipe_id}` not found.")
        return _make_response(True, f"🗑️ Recipe `{recipe_id}` deleted.")

    if sub == "templates":
        templates = RecipeEngine.list_templates()
        if not templates:
            return _make_response(True, "## Recipe Templates\n\nNo built-in templates available.")
        lines = ["## Recipe Templates\n"]
        for t in templates:
            lines.append(f"- **{t.get('name', 'unnamed')}** — {t.get('description', '')}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown recipe subcommand `{sub}`. Try: list, create, run, delete, templates.")


# ---------------------------------------------------------------------------
# !murphy workspace [list|show DOMAIN|bootstrap]
# ---------------------------------------------------------------------------

def handle_workspace(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy workspace`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    mgr = _get_workspace_manager()

    if sub == "list":
        workspaces = mgr.list_workspaces()
        if not workspaces:
            return _make_response(
                True,
                "## Workspaces\n\nNo workspaces. Use `!murphy workspace bootstrap` to initialise all Murphy domain workspaces.",
            )
        lines = ["## Workspaces\n"]
        lines.append("| Name | Domain | Modules | Boards |")
        lines.append("|------|--------|---------|--------|")
        for ws in workspaces:
            mod_count = len(mgr.list_modules_for_domain(ws.domain_key))
            lines.append(
                f"| {ws.name} | `{ws.domain_key}` | {mod_count} | {len(ws.board_ids)} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "show":
        domain = args[0] if args else None
        if not domain:
            return _make_response(False, "Usage: `!murphy workspace show <domain-key>`")
        ws = mgr.get_workspace_by_domain(domain)
        if not ws:
            return _make_response(False, f"Workspace domain `{domain}` not found.")
        modules = mgr.list_modules_for_domain(ws.domain_key)
        mod_list = ", ".join(f"`{m}`" for m in modules[:10])
        extra = f" … +{len(modules) - 10} more" if len(modules) > 10 else ""
        return _make_response(
            True,
            f"## Workspace: {ws.name}\n\n"
            f"- **Domain:** `{ws.domain_key}`\n"
            f"- **Modules ({len(modules)}):** {mod_list}{extra}\n"
            f"- **Boards:** {len(ws.board_ids)}\n",
        )

    if sub == "bootstrap":
        created = mgr.bootstrap_murphy_workspaces()
        return _make_response(True, f"✅ Bootstrapped **{len(created)}** Murphy domain workspaces.")

    return _make_response(False, f"Unknown workspace subcommand `{sub}`. Try: list, show, bootstrap.")


# ---------------------------------------------------------------------------
# !murphy dashboard [standup|weekly|project BOARD|widget]
# ---------------------------------------------------------------------------

def handle_dashboard(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy dashboard`` commands."""
    sub = getattr(cmd, "subcommand", None) or "standup"
    args = getattr(cmd, "args", [])
    gen = _get_dashboard_generator()

    if sub == "standup":
        team = args[0] if args else "Murphy Team"
        report = gen.generate_standup(
            team_name=team,
            completed_items=["(no items — connect a board)"],
            in_progress_items=[],
            blocked_items=[],
        )
        return _make_response(True, report)

    if sub == "weekly":
        workspace = args[0] if args else "Murphy System"
        report = gen.generate_weekly_report(
            workspace_name=workspace,
            stats={"tasks_completed": 0, "tasks_in_progress": 0, "tasks_blocked": 0},
        )
        return _make_response(True, report)

    if sub == "project":
        board_id = args[0] if args else None
        if not board_id:
            return _make_response(False, "Usage: `!murphy dashboard project <board-id>`")
        report = gen.generate_report(
            template_type=DashboardTemplateType.PROJECT_OVERVIEW,
            board_data={"board_id": board_id, "name": board_id},
        )
        return _make_response(True, report)

    if sub == "widget":
        templates = DashboardGenerator.list_templates()
        lines = ["## Dashboard Templates\n"]
        for t in templates:
            lines.append(f"- **{t.name}** — {t.description}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown dashboard subcommand `{sub}`. Try: standup, weekly, project, widget.")


# ---------------------------------------------------------------------------
# !murphy sync [status|rules|run|history]
# ---------------------------------------------------------------------------

def handle_sync(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy sync`` commands."""
    sub = getattr(cmd, "subcommand", None) or "status"
    args = getattr(cmd, "args", [])
    bridge = _get_integration_bridge()

    if sub == "status":
        status = bridge.render_sync_status()
        return _make_response(True, f"## Integration Sync Status\n\n{status}")

    if sub == "rules":
        rules = bridge.list_rules()
        if not rules:
            return _make_response(True, "## Sync Rules\n\nNo rules. Use `!murphy sync run` to bootstrap defaults.")
        lines = ["## Sync Rules\n"]
        lines.append("| Name | Event | Enabled |")
        lines.append("|------|-------|---------|")
        for r in rules:
            enabled = "✅" if r.enabled else "❌"
            lines.append(f"| {r.name} | {r.event_type.value} | {enabled} |")
        return _make_response(True, "\n".join(lines))

    if sub == "run":
        defaults = bridge.bootstrap_default_rules()
        return _make_response(True, f"✅ Bootstrapped **{len(defaults)}** default sync rules.")

    if sub == "history":
        history = bridge.get_history()
        if not history:
            return _make_response(True, "## Sync History\n\nNo sync events recorded yet.")
        lines = ["## Sync History (latest 10)\n"]
        for h in history[-10:]:
            lines.append(f"- `{h.rule_id[:8]}` → {h.status.value} @ {h.timestamp}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown sync subcommand `{sub}`. Try: status, rules, run, history.")


# ---------------------------------------------------------------------------
# !murphy form [list|start TEMPLATE|submit ID|responses ID]
# ---------------------------------------------------------------------------

def handle_form(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy form`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    sender = getattr(cmd, "sender", "unknown")
    builder = _get_form_builder()

    if sub == "list":
        forms = builder.list_forms()
        templates = FormBuilder.list_templates()
        lines = ["## Forms\n"]
        if templates:
            lines.append("**Templates:** " + ", ".join(f"`{t.name}`" for t in templates))
            lines.append("")
        if forms:
            for f in forms:
                lines.append(f"- **{f.name}** (`{f.id[:8]}`) — {f.template_type.value}")
        else:
            lines.append("No forms created yet. Use `!murphy form start <template>` to begin.")
        return _make_response(True, "\n".join(lines))

    if sub == "start":
        template_name = args[0] if args else None
        if not template_name:
            return _make_response(False, "Usage: `!murphy form start <template-type>`\nAvailable: bug_report, feature_request, client_intake, incident_report")
        try:
            ttype = FormTemplateType(template_name)
        except ValueError:
            return _make_response(False, f"Unknown form template `{template_name}`. Available: bug_report, feature_request, client_intake, incident_report")
        form = builder.load_template(ttype)
        session = builder.start_session(form.id, sender)
        prompt = builder.get_next_prompt(session["session_id"])
        return _make_response(
            True,
            f"📝 Form **{form.name}** started (session `{session['session_id'][:8]}`).\n\n"
            f"First question: {prompt or '(all fields answered)'}",
        )

    if sub == "submit":
        session_id = args[0] if args else None
        if not session_id:
            return _make_response(False, "Usage: `!murphy form submit <session-id>`")
        submission = builder.submit(session_id)
        if not submission:
            return _make_response(False, f"Session `{session_id}` not found or incomplete.")
        return _make_response(True, f"✅ Form submitted (`{submission.id[:8]}`).")

    if sub == "responses":
        form_id = args[0] if args else None
        if not form_id:
            return _make_response(False, "Usage: `!murphy form responses <form-id>`")
        submissions = builder.list_submissions()
        matched = [s for s in submissions if s.form_id == form_id or s.form_id.startswith(form_id)]
        if not matched:
            return _make_response(True, f"No responses for form `{form_id}`.")
        lines = [f"## Responses for `{form_id}`\n"]
        for s in matched:
            lines.append(f"- `{s.id[:8]}` by {s.user_id} — {s.status.value}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown form subcommand `{sub}`. Try: list, start, submit, responses.")


# ---------------------------------------------------------------------------
# !murphy doc [list|create TYPE TITLE|view ID|search TEXT|link|versions]
# ---------------------------------------------------------------------------

def handle_doc(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy doc`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    sender = getattr(cmd, "sender", "unknown")
    mgr = _get_doc_manager()

    if sub == "list":
        docs = mgr.list_docs()
        if not docs:
            return _make_response(True, "## Documents\n\nNo documents. Use `!murphy doc create <type> <title>` to create one.")
        lines = ["## Documents\n"]
        lines.append("| Title | Type | Status | ID |")
        lines.append("|-------|------|--------|----|")
        for d in docs:
            lines.append(f"| {d.title} | {d.doc_type.value} | {d.status.value} | `{d.id[:8]}` |")
        return _make_response(True, "\n".join(lines))

    if sub == "create":
        if len(args) < 2:
            return _make_response(False, "Usage: `!murphy doc create <type> <title>`\nTypes: meeting_notes, spec, runbook, retro, incident")
        type_str = args[0]
        title = " ".join(args[1:])
        try:
            dtype = DocType(type_str)
        except ValueError:
            return _make_response(False, f"Unknown doc type `{type_str}`. Available: meeting_notes, spec, runbook, retro, incident")
        doc = mgr.create_doc(title, dtype)
        return _make_response(True, f"📄 Document **{doc.title}** created (`{doc.id[:8]}`).")

    if sub == "view":
        doc_id = args[0] if args else None
        if not doc_id:
            return _make_response(False, "Usage: `!murphy doc view <doc-id>`")
        doc = mgr.get_doc(doc_id)
        if not doc:
            return _make_response(False, f"Document `{doc_id}` not found.")
        summary = mgr.render_doc_summary(doc.id)
        return _make_response(True, summary)

    if sub == "search":
        query = " ".join(args) if args else None
        if not query:
            return _make_response(False, "Usage: `!murphy doc search <text>`")
        results = mgr.search(query)
        if not results:
            return _make_response(True, f"No documents match `{query}`.")
        lines = [f"## Search: '{query}'\n"]
        for d in results:
            lines.append(f"- **{d.title}** ({d.doc_type.value}) — `{d.id[:8]}`")
        return _make_response(True, "\n".join(lines))

    if sub == "versions":
        doc_id = args[0] if args else None
        if not doc_id:
            return _make_response(False, "Usage: `!murphy doc versions <doc-id>`")
        doc = mgr.get_doc(doc_id)
        if not doc:
            return _make_response(False, f"Document `{doc_id}` not found.")
        history = mgr.get_version_history(doc.id)
        if not history:
            return _make_response(True, f"No version history for `{doc_id}`.")
        lines = [f"## Version History: {doc.title}\n"]
        for v in history:
            lines.append(f"- **v{v.version_number}** by {v.edited_by} @ {v.timestamp}")
        return _make_response(True, "\n".join(lines))

    if sub == "link":
        if len(args) < 2:
            return _make_response(False, "Usage: `!murphy doc link <doc-id> <board-id|item-id>`")
        doc_id, target = args[0], args[1]
        doc = mgr.get_doc(doc_id)
        if not doc:
            return _make_response(False, f"Document `{doc_id}` not found.")
        mgr.link_to_board(doc.id, target)
        return _make_response(True, f"🔗 Document `{doc_id[:8]}` linked to `{target[:8]}`.")

    return _make_response(False, f"Unknown doc subcommand `{sub}`. Try: list, create, view, search, versions, link.")


# ---------------------------------------------------------------------------
# !murphy onboard [init|start|questions|answer|assign|complete|status]
# ---------------------------------------------------------------------------

def handle_onboard(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy onboard`` commands.

    Subcommands:
        init                          — initialize org chart with default positions
        start <name> <email>          — start onboarding session for a new employee
        questions <session-id>        — list onboarding questions
        answer <session-id> <q-id> <answer> — answer an onboarding question
        assign <session-id> [pos-id]  — assign shadow agent to employee
        complete <session-id>         — complete onboarding, transition to workflow builder
        status [session-id]           — show onboarding status
    """
    sub = getattr(cmd, "subcommand", None) or "status"
    args = getattr(cmd, "args", [])
    flow = _get_onboarding_flow()

    if sub == "init":
        result = flow.initialize_org()
        lines = ["## ☠ Organization Initialized\n"]
        lines.append(f"✅ **{result['positions_created']} positions** created")
        lines.append(f"📋 Phase: `{result['phase']}`")
        lines.append(f"➡️ Next: `{result['next_phase']}`")
        chart = result.get("org_chart", {})
        lines.append(f"\n**Total positions:** {chart.get('total_positions', 0)}")
        lines.append(f"**IP classification:** {chart.get('ip_classification', 'N/A')}")
        for root in chart.get("hierarchy", []):
            lines.append(f"\n### {root.get('title', 'Unknown')}")
            lines.append(f"  Level: {root.get('level', '?')} | Dept: {root.get('department', '?')}")
            for child in root.get("children", []):
                lines.append(f"  └─ **{child.get('title', '?')}** ({child.get('level', '?')})")
                for gc in child.get("children", []):
                    lines.append(f"     └─ {gc.get('title', '?')} ({gc.get('level', '?')})")
        return _make_response(True, "\n".join(lines))

    if sub == "start":
        if len(args) < 2:
            return _make_response(False, "Usage: `!murphy onboard start <name> <email>`")
        name = args[0]
        email = args[1]
        session = flow.start_onboarding(name, email)
        lines = [f"## ☠ Onboarding Started\n"]
        lines.append(f"👤 **Employee:** {session.employee_name}")
        lines.append(f"📧 **Email:** {session.employee_email}")
        lines.append(f"🔑 **Session ID:** `{session.session_id}`")
        lines.append(f"📋 **Phase:** `{session.phase.value}`")
        lines.append(f"\n➡️ Next: Use `!murphy onboard questions {session.session_id}` to view questions")
        return _make_response(True, "\n".join(lines))

    if sub == "questions":
        session_id = args[0] if args else None
        if not session_id:
            return _make_response(False, "Usage: `!murphy onboard questions <session-id>`")
        questions = flow.get_questions(session_id)
        if not questions:
            return _make_response(False, f"Session `{session_id}` not found or no questions available.")
        lines = ["## ☠ Onboarding Questions\n"]
        for q in questions:
            required = "⭐" if q.get("required") else "  "
            lines.append(f"{required} **Q{q['order']}** (`{q['question_id']}`): {q['question']}")
            if q.get("options"):
                lines.append(f"   Options: {', '.join(q['options'])}")
            if q.get("help_text"):
                lines.append(f"   _{q['help_text']}_")
        lines.append(f"\n➡️ Answer with: `!murphy onboard answer {session_id} <question-id> <your-answer>`")
        return _make_response(True, "\n".join(lines))

    if sub == "answer":
        if len(args) < 3:
            return _make_response(False, "Usage: `!murphy onboard answer <session-id> <question-id> <answer>`")
        session_id = args[0]
        question_id = args[1]
        answer_text = " ".join(args[2:])
        result = flow.answer_question(session_id, question_id, answer_text)
        if "error" in result:
            return _make_response(False, f"Error: {result['error']}")
        lines = ["## ☠ Answer Recorded\n"]
        lines.append(f"✅ **Answered:** {result['questions_answered']}/{result['total_questions']}")
        lines.append(f"📋 **Required remaining:** {result['required_remaining']}")
        if result.get("all_required_complete"):
            lines.append("\n🎉 **All required questions answered!**")
            lines.append(f"➡️ Next: `!murphy onboard assign {session_id}`")
        else:
            lines.append(f"\n➡️ Continue answering questions for session `{session_id}`")
        return _make_response(True, "\n".join(lines))

    if sub == "assign":
        session_id = args[0] if args else None
        if not session_id:
            return _make_response(False, "Usage: `!murphy onboard assign <session-id> [position-id]`")
        position_id = args[1] if len(args) > 1 else None
        result = flow.assign_shadow_agent(session_id, position_id)
        if "error" in result:
            return _make_response(False, f"Error: {result['error']}")
        shadow = result.get("shadow_agent", {})
        lines = ["## ☠ Shadow Agent Assigned\n"]
        lines.append(f"🤖 **Agent ID:** `{shadow.get('shadow_id', 'N/A')}`")
        lines.append(f"👤 **Employee:** {shadow.get('employee_id', 'N/A')}")
        lines.append(f"🔐 **IP Classification:** {result.get('ip_classification', 'N/A')}")
        caps = shadow.get("capabilities", [])
        if caps:
            lines.append(f"⚡ **Capabilities:** {', '.join(caps)}")
        lines.append(f"\n{result.get('message', '')}")
        lines.append(f"\n➡️ Next: `!murphy onboard complete {session_id}`")
        return _make_response(True, "\n".join(lines))

    if sub == "complete":
        session_id = args[0] if args else None
        if not session_id:
            return _make_response(False, "Usage: `!murphy onboard complete <session-id>`")
        result = flow.transition_to_workflow_builder(session_id)
        if "error" in result:
            return _make_response(False, f"Error: {result['error']}")
        ctx = result.get("builder_context", {})
        lines = ["## ☠ Onboarding Complete!\n"]
        lines.append(f"✅ **Phase:** `{result.get('phase', 'completed')}`")
        lines.append(f"👤 **Employee:** {ctx.get('employee_name', 'N/A')}")
        if ctx.get("shadow_agent_id"):
            lines.append(f"🤖 **Shadow Agent:** `{ctx['shadow_agent_id']}`")
        if ctx.get("suggested_automations"):
            lines.append(f"⚡ **Suggested Automations:** {', '.join(ctx['suggested_automations'])}")
        lines.append(f"\n{result.get('message', '')}")
        return _make_response(True, "\n".join(lines))

    if sub == "status":
        session_id = args[0] if args else None
        if session_id:
            session = flow.get_session(session_id)
            if not session:
                return _make_response(False, f"Session `{session_id}` not found.")
            s = session.to_dict()
            lines = [f"## ☠ Onboarding Session: {s['employee_name']}\n"]
            lines.append(f"📋 **Phase:** `{s['phase']}`")
            lines.append(f"📧 **Email:** {s['employee_email']}")
            lines.append(f"📝 **Questions answered:** {len(s.get('questions_answered', {}))}")
            if s.get("shadow_agent"):
                lines.append(f"🤖 **Shadow Agent:** `{s['shadow_agent']['shadow_id']}`")
            return _make_response(True, "\n".join(lines))
        else:
            sessions = flow.list_sessions()
            org_chart = flow.org_chart.get_org_chart()
            lines = ["## ☠ Onboarding Status\n"]
            lines.append(f"**Org positions:** {org_chart.get('total_positions', 0)}")
            lines.append(f"**Active sessions:** {len(sessions)}")
            lines.append(f"**Shadow agents:** {len(flow.get_shadow_agents())}\n")
            if sessions:
                lines.append("| Employee | Phase | Questions |")
                lines.append("|----------|-------|-----------|")
                for s in sessions:
                    lines.append(f"| {s['employee_name']} | `{s['phase']}` | {len(s.get('questions_answered', {}))} |")
            else:
                lines.append("No onboarding sessions. Use `!murphy onboard init` to start.")
            return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown onboard subcommand `{sub}`. "
                          "Try: init, start, questions, answer, assign, complete, status.")


# ---------------------------------------------------------------------------
# !murphy gate [create|list|evaluate|status]
# ---------------------------------------------------------------------------

def handle_gate(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy gate`` commands.

    Subcommands:
        create <objective-id> <category> [--budget=N] [--roi=N] [--risk=N]
            — generate gates for a business objective
        list [objective-id]   — list all gates or gates for an objective
        evaluate <gate-id> <value>  — evaluate a gate against an actual value
        status <gate-id>      — show gate status
        update <gate-id> <status> — update gate status
    """
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    kwargs = getattr(cmd, "kwargs", {})
    gen = _get_gate_generator()

    if sub == "create":
        if len(args) < 2:
            return _make_response(
                False,
                "Usage: `!murphy gate create <objective-id> <category>` "
                "[--budget=N] [--roi=N] [--risk=N]\n\n"
                "Categories: revenue_target, cost_reduction, market_expansion, "
                "compliance_mandate, operational_efficiency",
            )
        objective_id = args[0]
        category = args[1]
        budget = float(kwargs.get("budget", 100000))
        roi = float(kwargs["roi"]) if "roi" in kwargs else None
        risk = float(kwargs["risk"]) if "risk" in kwargs else None
        try:
            gates = gen.generate_gates_for_objective(
                objective_id, category,
                budget_threshold=budget,
                roi_threshold=roi,
                risk_tolerance=risk,
            )
        except (ValueError, KeyError) as exc:
            return _make_response(False, f"Error generating gates: {exc}")
        lines = [f"## ☠ Gates Generated for `{objective_id}`\n"]
        lines.append(f"✅ **{len(gates)} gates** created for category `{category}`\n")
        lines.append("| Gate ID | Type | Threshold | Status |")
        lines.append("|---------|------|-----------|--------|")
        for g in gates:
            lines.append(
                f"| `{g['gate_id']}` | {g['gate_type']} "
                f"| {g['threshold']} | {g['status']} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "list":
        objective_id = args[0] if args else None
        if objective_id:
            gates = gen.get_gates_for_objective(objective_id)
        else:
            gates = gen.list_gates()
        if not gates:
            return _make_response(True, "## Gates\n\nNo gates found. Use `!murphy gate create` to generate gates.")
        lines = ["## ☠ Gate Registry\n"]
        lines.append("| Gate ID | Objective | Type | Threshold | Status |")
        lines.append("|---------|-----------|------|-----------|--------|")
        for g in gates:
            lines.append(
                f"| `{g['gate_id']}` | `{g['objective_id']}` "
                f"| {g['gate_type']} | {g['threshold']} | {g['status']} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "evaluate":
        if len(args) < 2:
            return _make_response(False, "Usage: `!murphy gate evaluate <gate-id> <actual-value>`")
        gate_id = args[0]
        try:
            actual = float(args[1])
        except ValueError:
            return _make_response(False, "Value must be a number.")
        result = gen.evaluate_gate(gate_id, actual)
        if "error" in result:
            return _make_response(False, f"Gate `{gate_id}` not found.")
        ev = result.get("evaluation_result", {})
        passed = "✅ PASSED" if ev.get("passed") else "❌ FAILED"
        lines = [f"## ☠ Gate Evaluation: `{gate_id}`\n"]
        lines.append(f"**Result:** {passed}")
        lines.append(f"**Actual:** {ev.get('actual_value')}")
        lines.append(f"**Threshold:** {ev.get('threshold')}")
        lines.append(f"**Type:** {result.get('gate_type')}")
        lines.append(f"**Status:** `{result.get('status')}`")
        return _make_response(True, "\n".join(lines))

    if sub == "status":
        gate_id = args[0] if args else None
        if not gate_id:
            return _make_response(False, "Usage: `!murphy gate status <gate-id>`")
        gate = gen.get_gate(gate_id)
        if not gate:
            return _make_response(False, f"Gate `{gate_id}` not found.")
        lines = [f"## ☠ Gate Status: `{gate_id}`\n"]
        lines.append(f"**Objective:** `{gate.get('objective_id')}`")
        lines.append(f"**Type:** {gate.get('gate_type')}")
        lines.append(f"**Threshold:** {gate.get('threshold')}")
        lines.append(f"**Status:** `{gate.get('status')}`")
        lines.append(f"**Approvers:** {', '.join(gate.get('approvers', []))}")
        if gate.get("evaluation_result"):
            ev = gate["evaluation_result"]
            lines.append(f"\n**Last evaluation:**")
            lines.append(f"  Actual: {ev.get('actual_value')} | Passed: {ev.get('passed')}")
        return _make_response(True, "\n".join(lines))

    if sub == "update":
        if len(args) < 2:
            return _make_response(
                False,
                "Usage: `!murphy gate update <gate-id> <status>`\n"
                "Statuses: pending, open, passed, failed, waived, blocked",
            )
        gate_id = args[0]
        status = args[1]
        try:
            result = gen.update_gate_status(gate_id, status)
        except ValueError as exc:
            return _make_response(False, f"Invalid status: {exc}")
        if "error" in result:
            return _make_response(False, f"Gate `{gate_id}` not found.")
        return _make_response(True, f"✅ Gate `{gate_id}` status updated to `{result['status']}`.")

    return _make_response(False, f"Unknown gate subcommand `{sub}`. "
                          "Try: create, list, evaluate, status, update.")


# ---------------------------------------------------------------------------
# !murphy setpoint [show|set|ranges]
# ---------------------------------------------------------------------------

_DEFAULT_SETPOINTS = {
    "money": {"value": 0.5, "description": "Budget neutrality target", "range": [0.0, 1.0]},
    "time": {"value": 0.5, "description": "On-schedule target", "range": [0.0, 1.0]},
    "production": {"value": 1.0, "description": "Production pace target", "range": [0.0, 1.5]},
    "confidence": {"value": 1.0, "description": "Full confidence desired", "range": [0.0, 1.0]},
    "info_completeness": {"value": 1.0, "description": "Full information desired", "range": [0.0, 1.0]},
    "risk": {"value": 0.0, "description": "Zero risk desired", "range": [0.0, 1.0]},
}

_active_setpoints: dict | None = None


def _get_active_setpoints() -> dict:
    global _active_setpoints
    if _active_setpoints is None:
        import copy
        _active_setpoints = copy.deepcopy(_DEFAULT_SETPOINTS)
    return _active_setpoints


def handle_setpoint(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy setpoint`` commands.

    Subcommands:
        show               — display current setpoints and their ranges
        set <dim> <value>  — override a setpoint value
        ranges             — display allowed ranges for all dimensions
        reset              — reset setpoints to defaults
    """
    sub = getattr(cmd, "subcommand", None) or "show"
    args = getattr(cmd, "args", [])
    setpoints = _get_active_setpoints()

    if sub == "show":
        lines = ["## ☠ Active Setpoints\n"]
        lines.append("| Dimension | Value | Range | Description |")
        lines.append("|-----------|-------|-------|-------------|")
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            lines.append(
                f"| {dim} | **{sp['value']:.2f}** "
                f"| [{rng[0]:.1f}, {rng[1]:.1f}] "
                f"| {sp['description']} |"
            )
        lines.append("\nSetpoints drive the PI control loop in the Activated Heartbeat Runner.")
        lines.append("Use `!murphy setpoint set <dimension> <value>` to adjust.")
        return _make_response(True, "\n".join(lines))

    if sub == "set":
        if len(args) < 2:
            return _make_response(
                False,
                "Usage: `!murphy setpoint set <dimension> <value>`\n"
                f"Dimensions: {', '.join(setpoints.keys())}",
            )
        dim = args[0]
        if dim not in setpoints:
            return _make_response(False, f"Unknown dimension `{dim}`. "
                                  f"Available: {', '.join(setpoints.keys())}")
        try:
            val = float(args[1])
        except ValueError:
            return _make_response(False, "Value must be a number.")
        rng = setpoints[dim].get("range", [0, 1])
        if not (rng[0] <= val <= rng[1]):
            return _make_response(False, f"Value {val} out of range [{rng[0]}, {rng[1]}] for `{dim}`.")
        old_val = setpoints[dim]["value"]
        setpoints[dim]["value"] = val
        return _make_response(
            True,
            f"✅ Setpoint `{dim}` updated: **{old_val:.2f}** → **{val:.2f}** (range [{rng[0]}, {rng[1]}])",
        )

    if sub == "ranges":
        lines = ["## ☠ Setpoint Ranges\n"]
        lines.append("| Dimension | Min | Max | Default | Description |")
        lines.append("|-----------|-----|-----|---------|-------------|")
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            default = _DEFAULT_SETPOINTS[dim]["value"]
            lines.append(
                f"| {dim} | {rng[0]:.1f} | {rng[1]:.1f} "
                f"| {default:.2f} | {sp['description']} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "reset":
        import copy
        global _active_setpoints
        _active_setpoints = copy.deepcopy(_DEFAULT_SETPOINTS)
        return _make_response(True, "✅ All setpoints reset to defaults.")

    return _make_response(False, f"Unknown setpoint subcommand `{sub}`. "
                          "Try: show, set, ranges, reset.")


# ---------------------------------------------------------------------------
# !murphy schedule [loops|configure|status]
# ---------------------------------------------------------------------------

_DEFAULT_BUSINESS_LOOPS = {
    "heartbeat": {
        "description": "Core PI control loop",
        "interval_seconds": 5,
        "range": [1, 60],
        "enabled": True,
    },
    "financial_review": {
        "description": "Budget and ROI gate evaluation cycle",
        "interval_seconds": 3600,
        "range": [300, 86400],
        "enabled": True,
    },
    "compliance_check": {
        "description": "Regulatory compliance gate sweep",
        "interval_seconds": 1800,
        "range": [600, 86400],
        "enabled": True,
    },
    "risk_assessment": {
        "description": "Risk exposure evaluation cycle",
        "interval_seconds": 900,
        "range": [60, 7200],
        "enabled": True,
    },
    "production_pace": {
        "description": "Production pace tracking and adjustment",
        "interval_seconds": 300,
        "range": [60, 3600],
        "enabled": True,
    },
    "stakeholder_reporting": {
        "description": "Executive dashboard refresh",
        "interval_seconds": 7200,
        "range": [1800, 86400],
        "enabled": True,
    },
}

_active_loops: dict | None = None


def _get_active_loops() -> dict:
    global _active_loops
    if _active_loops is None:
        import copy
        _active_loops = copy.deepcopy(_DEFAULT_BUSINESS_LOOPS)
    return _active_loops


def handle_schedule(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy schedule`` commands.

    Subcommands:
        loops                        — list all business loops and their schedules
        configure <loop> <seconds>   — set loop interval
        enable <loop>                — enable a loop
        disable <loop>               — disable a loop
        status                       — show scheduling summary
        reset                        — reset loops to defaults
    """
    sub = getattr(cmd, "subcommand", None) or "loops"
    args = getattr(cmd, "args", [])
    loops = _get_active_loops()

    if sub == "loops":
        lines = ["## ☠ Business Loop Schedule\n"]
        lines.append("| Loop | Interval | Range | Enabled | Description |")
        lines.append("|------|----------|-------|---------|-------------|")
        for name, cfg in loops.items():
            rng = cfg.get("range", [0, 86400])
            enabled = "✅" if cfg["enabled"] else "❌"
            interval = cfg["interval_seconds"]
            if interval >= 3600:
                interval_str = f"{interval / 3600:.1f}h"
            elif interval >= 60:
                interval_str = f"{interval / 60:.0f}m"
            else:
                interval_str = f"{interval}s"
            lines.append(
                f"| {name} | **{interval_str}** "
                f"| [{rng[0]}s, {rng[1]}s] "
                f"| {enabled} | {cfg['description']} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "configure":
        if len(args) < 2:
            return _make_response(
                False,
                "Usage: `!murphy schedule configure <loop-name> <interval-seconds>`\n"
                f"Loops: {', '.join(loops.keys())}",
            )
        loop_name = args[0]
        if loop_name not in loops:
            return _make_response(False, f"Unknown loop `{loop_name}`. "
                                  f"Available: {', '.join(loops.keys())}")
        try:
            secs = int(args[1])
        except ValueError:
            return _make_response(False, "Interval must be an integer (seconds).")
        rng = loops[loop_name].get("range", [0, 86400])
        if not (rng[0] <= secs <= rng[1]):
            return _make_response(False, f"Interval {secs}s out of range [{rng[0]}, {rng[1]}] for `{loop_name}`.")
        old = loops[loop_name]["interval_seconds"]
        loops[loop_name]["interval_seconds"] = secs
        return _make_response(
            True,
            f"✅ Loop `{loop_name}` interval updated: **{old}s** → **{secs}s**",
        )

    if sub in ("enable", "disable"):
        loop_name = args[0] if args else None
        if not loop_name or loop_name not in loops:
            return _make_response(False, f"Usage: `!murphy schedule {sub} <loop-name>`\n"
                                  f"Loops: {', '.join(loops.keys())}")
        loops[loop_name]["enabled"] = sub == "enable"
        return _make_response(True, f"✅ Loop `{loop_name}` {'enabled' if sub == 'enable' else 'disabled'}.")

    if sub == "status":
        enabled = sum(1 for l in loops.values() if l["enabled"])
        disabled = len(loops) - enabled
        lines = ["## ☠ Schedule Status\n"]
        lines.append(f"**Total loops:** {len(loops)}")
        lines.append(f"**Enabled:** {enabled}")
        lines.append(f"**Disabled:** {disabled}")
        for name, cfg in loops.items():
            state = "🟢 running" if cfg["enabled"] else "🔴 stopped"
            lines.append(f"- **{name}**: {state} (every {cfg['interval_seconds']}s)")
        return _make_response(True, "\n".join(lines))

    if sub == "reset":
        import copy
        global _active_loops
        _active_loops = copy.deepcopy(_DEFAULT_BUSINESS_LOOPS)
        return _make_response(True, "✅ All business loop schedules reset to defaults.")

    return _make_response(False, f"Unknown schedule subcommand `{sub}`. "
                          "Try: loops, configure, enable, disable, status, reset.")


# ---------------------------------------------------------------------------
# All handlers (for registration convenience)
# ---------------------------------------------------------------------------

MANAGEMENT_COMMAND_HANDLERS = {
    "board": handle_board,
    "status-label": handle_status,
    "timeline": handle_timeline,
    "recipe": handle_recipe,
    "workspace": handle_workspace,
    "dashboard": handle_dashboard,
    "sync": handle_sync,
    "form": handle_form,
    "doc": handle_doc,
    "onboard": handle_onboard,
    "gate": handle_gate,
    "setpoint": handle_setpoint,
    "schedule": handle_schedule,
}

__all__ = [
    "handle_board",
    "handle_status",
    "handle_timeline",
    "handle_recipe",
    "handle_workspace",
    "handle_dashboard",
    "handle_sync",
    "handle_form",
    "handle_doc",
    "handle_onboard",
    "handle_gate",
    "handle_setpoint",
    "handle_schedule",
    "reset_engines",
    "MANAGEMENT_COMMAND_HANDLERS",
]
