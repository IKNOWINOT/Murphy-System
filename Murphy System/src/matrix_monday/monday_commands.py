"""
Monday Commands — Chat command handlers for Matrix Monday.

Provides handler functions that wire ``!murphy`` chat commands to the
actual :mod:`matrix_monday` engines (BoardEngine, StatusEngine,
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
    global _form_builder, _doc_manager
    _board_engine = None
    _status_engine = None
    _timeline_engine = None
    _recipe_engine = None
    _workspace_manager = None
    _dashboard_generator = None
    _integration_bridge = None
    _form_builder = None
    _doc_manager = None


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
        if not cp.items:
            return _make_response(True, "## Critical Path\n\nNo items on the critical path (add dependencies first).")
        lines = ["## Critical Path\n"]
        lines.append(f"**Total duration:** {cp.total_duration} days\n")
        for item in cp.items:
            lines.append(f"- {item.name} ({item.start_date} → {item.end_date})")
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
# !murphy workspace monday [list|show DOMAIN|bootstrap]
# ---------------------------------------------------------------------------

def handle_workspace(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy workspace monday`` commands."""
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    mgr = _get_workspace_manager()

    if sub == "list":
        workspaces = mgr.list_workspaces()
        if not workspaces:
            return _make_response(
                True,
                "## Workspaces\n\nNo workspaces. Use `!murphy workspace monday bootstrap` to initialise all Murphy domain workspaces.",
            )
        lines = ["## Workspaces\n"]
        lines.append("| Name | Domain | Modules | Boards |")
        lines.append("|------|--------|---------|--------|")
        for ws in workspaces:
            lines.append(
                f"| {ws.name} | `{ws.domain_key}` | {len(ws.modules)} | {len(ws.board_ids)} |"
            )
        return _make_response(True, "\n".join(lines))

    if sub == "show":
        domain = args[0] if args else None
        if not domain:
            return _make_response(False, "Usage: `!murphy workspace monday show <domain-key>`")
        ws = mgr.get_workspace_by_domain(domain)
        if not ws:
            return _make_response(False, f"Workspace domain `{domain}` not found.")
        mod_list = ", ".join(f"`{m}`" for m in ws.modules[:10])
        extra = f" … +{len(ws.modules) - 10} more" if len(ws.modules) > 10 else ""
        return _make_response(
            True,
            f"## Workspace: {ws.name}\n\n"
            f"- **Domain:** `{ws.domain_key}`\n"
            f"- **Modules ({len(ws.modules)}):** {mod_list}{extra}\n"
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
# All handlers (for registration convenience)
# ---------------------------------------------------------------------------

MONDAY_COMMAND_HANDLERS = {
    "board": handle_board,
    "status-label": handle_status,
    "timeline": handle_timeline,
    "recipe": handle_recipe,
    "workspace": handle_workspace,
    "dashboard": handle_dashboard,
    "sync": handle_sync,
    "form": handle_form,
    "doc": handle_doc,
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
    "reset_engines",
    "MONDAY_COMMAND_HANDLERS",
]
