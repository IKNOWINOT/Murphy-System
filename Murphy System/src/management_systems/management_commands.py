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

from .automation_recipes import ActionType, AutomationTrigger, RecipeEngine, TriggerType
from .board_engine import BoardEngine, ColumnType, TemplateType, ViewType
from .dashboard_generator import DashboardGenerator, DashboardTemplateType
from .doc_manager import DocManager, DocType
from .form_builder import FormBuilder, FormTemplateType
from .integration_bridge import IntegrationBridge
from .status_engine import StatusEngine
from .timeline_engine import DependencyType, TimelineEngine
from .workspace_manager import WorkspaceManager

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

# Shared automation registry — populated by onboarding, consumed by other views.
# Each entry is a dict with keys: source, owner, owner_type, capability,
# ip_class, status, and optionally agent_id or position_id.
# Rebuilt on every call to _get_automation_registry() from onboarding state.
# Cleared on reset_engines().
_automation_registry: list[dict] = []

# ---------------------------------------------------------------------------
# Automation engine singletons (all lazy-initialised)
# ---------------------------------------------------------------------------

_automation_mode_controller: object | None = None
_automation_integration_hub: object | None = None
_automation_rbac_controller: object | None = None
_automation_readiness_evaluator: object | None = None
_automation_scaler: object | None = None
_automation_loop_connector: object | None = None
_automation_scheduler: object | None = None
_automation_marketplace: object | None = None
_murphy_native_runner: object | None = None
_self_automation_orchestrator: object | None = None
_onboarding_automation_engine: object | None = None
_building_automation_orchestrator: object | None = None
_manufacturing_automation_registry: object | None = None
_sales_automation_engine: object | None = None
_compliance_automation_bridge: object | None = None
_full_automation_controller: object | None = None
_deployment_automation_controller: object | None = None
_production_assistant: object | None = None
_campaign_planner: object | None = None


def _get_automation_registry() -> list[dict]:
    """Return the shared automation registry.

    Merges automations from onboarding shadow agents and org positions
    so that dashboard, workspace, recipe, schedule, and workflow views
    can all surface the same automation data.
    """
    global _automation_registry
    flow = _get_onboarding_flow()

    # Rebuild from onboarding state
    entries: list[dict] = []

    # From shadow agents (employee-level automations)
    for agent in flow.shadow_agents.values():
        for cap in agent.capabilities:
            entries.append({
                "source": "onboarding",
                "owner": agent.employee_id,
                "owner_type": "shadow_agent",
                "agent_id": agent.shadow_id,
                "capability": cap,
                "ip_class": agent.ip_classification,
                "status": "active",
            })

    # From org positions (position-level automation scope)
    for pos in flow.org_chart.positions.values():
        for scope in pos.automation_scope:
            entries.append({
                "source": "org_chart",
                "owner": pos.title,
                "owner_type": "position",
                "position_id": pos.position_id,
                "capability": scope,
                "ip_class": flow.org_chart.ip_classification,
                "status": "active",
            })

    _automation_registry = entries
    return _automation_registry


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


def _get_automation_mode_controller():
    global _automation_mode_controller
    if _automation_mode_controller is None:
        from automation_mode_controller import AutomationModeController
        _automation_mode_controller = AutomationModeController()
    return _automation_mode_controller


def _get_automation_integration_hub():
    global _automation_integration_hub
    if _automation_integration_hub is None:
        from automation_integration_hub import AutomationIntegrationHub
        _automation_integration_hub = AutomationIntegrationHub()
    return _automation_integration_hub


def _get_automation_rbac_controller():
    global _automation_rbac_controller
    if _automation_rbac_controller is None:
        from automation_rbac_controller import AutomationRBACController
        _automation_rbac_controller = AutomationRBACController()
    return _automation_rbac_controller


def _get_automation_readiness_evaluator():
    global _automation_readiness_evaluator
    if _automation_readiness_evaluator is None:
        from automation_readiness_evaluator import AutomationReadinessEvaluator
        _automation_readiness_evaluator = AutomationReadinessEvaluator()
    return _automation_readiness_evaluator


def _get_automation_scaler():
    global _automation_scaler
    if _automation_scaler is None:
        from automation_scaler import AutomationScaler
        _automation_scaler = AutomationScaler()
    return _automation_scaler


def _get_automation_loop_connector():
    global _automation_loop_connector
    if _automation_loop_connector is None:
        from automation_loop_connector import AutomationLoopConnector
        _automation_loop_connector = AutomationLoopConnector()
    return _automation_loop_connector


def _get_automation_scheduler():
    global _automation_scheduler
    if _automation_scheduler is None:
        from automation_scheduler import AutomationScheduler
        _automation_scheduler = AutomationScheduler()
    return _automation_scheduler


def _get_automation_marketplace():
    global _automation_marketplace
    if _automation_marketplace is None:
        from automation_marketplace import AutomationMarketplace
        _automation_marketplace = AutomationMarketplace()
    return _automation_marketplace


def _get_murphy_native_runner():
    global _murphy_native_runner
    if _murphy_native_runner is None:
        from murphy_native_automation import MurphyNativeRunner
        _murphy_native_runner = MurphyNativeRunner()
    return _murphy_native_runner


def _get_self_automation_orchestrator():
    global _self_automation_orchestrator
    if _self_automation_orchestrator is None:
        from self_automation_orchestrator import SelfAutomationOrchestrator
        _self_automation_orchestrator = SelfAutomationOrchestrator()
    return _self_automation_orchestrator


def _get_onboarding_automation_engine():
    global _onboarding_automation_engine
    if _onboarding_automation_engine is None:
        from onboarding_automation_engine import OnboardingAutomationEngine
        _onboarding_automation_engine = OnboardingAutomationEngine()
    return _onboarding_automation_engine


def _get_building_automation_orchestrator():
    global _building_automation_orchestrator
    if _building_automation_orchestrator is None:
        from building_automation_connectors import BuildingAutomationRegistry
        _building_automation_orchestrator = BuildingAutomationRegistry()
    return _building_automation_orchestrator


def _get_manufacturing_automation_registry():
    global _manufacturing_automation_registry
    if _manufacturing_automation_registry is None:
        from manufacturing_automation_standards import ManufacturingAutomationRegistry
        _manufacturing_automation_registry = ManufacturingAutomationRegistry()
    return _manufacturing_automation_registry


def _get_sales_automation_engine():
    global _sales_automation_engine
    if _sales_automation_engine is None:
        from sales_automation import SalesAutomationEngine
        _sales_automation_engine = SalesAutomationEngine()
    return _sales_automation_engine


def _get_compliance_automation_bridge():
    global _compliance_automation_bridge
    if _compliance_automation_bridge is None:
        from compliance_automation_bridge import ComplianceAutomationBridge
        _compliance_automation_bridge = ComplianceAutomationBridge()
    return _compliance_automation_bridge


def _get_full_automation_controller():
    global _full_automation_controller
    if _full_automation_controller is None:
        from full_automation_controller import FullAutomationController
        _full_automation_controller = FullAutomationController()
    return _full_automation_controller


def _get_deployment_automation_controller():
    global _deployment_automation_controller
    if _deployment_automation_controller is None:
        from deployment_automation_controller import DeploymentAutomationController
        _deployment_automation_controller = DeploymentAutomationController()
    return _deployment_automation_controller


def _get_production_assistant():
    global _production_assistant
    if _production_assistant is None:
        from production_assistant import ProductionAssistantEngine
        _production_assistant = ProductionAssistantEngine()
    return _production_assistant


def _get_campaign_planner():
    global _campaign_planner
    if _campaign_planner is None:
        from outreach_campaign_planner import CampaignPlannerEngine
        _campaign_planner = CampaignPlannerEngine()
    return _campaign_planner


def reset_engines() -> None:
    """Reset all engine singletons (useful for testing)."""
    global _board_engine, _status_engine, _timeline_engine, _recipe_engine
    global _workspace_manager, _dashboard_generator, _integration_bridge
    global _form_builder, _doc_manager, _onboarding_flow, _gate_generator
    global _automation_registry, _active_setpoints, _active_loops
    global _automation_mode_controller, _automation_integration_hub
    global _automation_rbac_controller, _automation_readiness_evaluator
    global _automation_scaler, _automation_loop_connector, _automation_scheduler
    global _automation_marketplace, _murphy_native_runner, _self_automation_orchestrator
    global _onboarding_automation_engine, _building_automation_orchestrator
    global _manufacturing_automation_registry, _sales_automation_engine
    global _compliance_automation_bridge, _full_automation_controller
    global _deployment_automation_controller
    global _production_assistant, _campaign_planner
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
    _automation_registry = []
    _active_setpoints = None
    _active_loops = None
    _automation_mode_controller = None
    _automation_integration_hub = None
    _automation_rbac_controller = None
    _automation_readiness_evaluator = None
    _automation_scaler = None
    _automation_loop_connector = None
    _automation_scheduler = None
    _automation_marketplace = None
    _murphy_native_runner = None
    _self_automation_orchestrator = None
    _onboarding_automation_engine = None
    _building_automation_orchestrator = None
    _manufacturing_automation_registry = None
    _sales_automation_engine = None
    _compliance_automation_bridge = None
    _full_automation_controller = None
    _deployment_automation_controller = None
    _production_assistant = None
    _campaign_planner = None


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
        lines = ["## Automation Recipes\n"]
        if recipes:
            lines.append("| Name | Trigger | Status | Executions |")
            lines.append("|------|---------|--------|------------|")
            for r in recipes:
                execs = len([e for e in engine.get_execution_log() if e.recipe_id == r.id])
                lines.append(f"| {r.name} | {r.trigger.trigger_type.value} | {r.status.value} | {execs} |")
        else:
            lines.append("No manual recipes defined. Use `!murphy recipe create <name>` or `!murphy recipe templates`.")

        # Show onboarding-derived automation capabilities
        automations = _get_automation_registry()
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        if shadow_auto:
            lines.append("\n### Onboarding-Derived Automations\n")
            lines.append("| Capability | Owner | Agent | Status |")
            lines.append("|------------|-------|-------|--------|")
            for a in shadow_auto:
                lines.append(
                    f"| {a['capability']} | {a['owner'][:16]} "
                    f"| `{a['agent_id']}` | {a['status']} |"
                )
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
        automations = _get_automation_registry()
        lines = ["## Workspaces\n"]
        if workspaces:
            lines.append("| Name | Domain | Modules | Boards |")
            lines.append("|------|--------|---------|--------|")
            for ws in workspaces:
                mod_count = len(mgr.list_modules_for_domain(ws.domain_key))
                lines.append(
                    f"| {ws.name} | `{ws.domain_key}` | {mod_count} | {len(ws.board_ids)} |"
                )
        else:
            lines.append("No workspaces. Use `!murphy workspace bootstrap` to initialise all Murphy domain workspaces.")
        if automations:
            pos_auto = [a for a in automations if a["owner_type"] == "position"]
            shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
            lines.append(f"\n**Automation assignments:** {len(pos_auto)} org-level, {len(shadow_auto)} employee-level")
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
        lines = [
            f"## Workspace: {ws.name}\n",
            f"- **Domain:** `{ws.domain_key}`",
            f"- **Modules ({len(modules)}):** {mod_list}{extra}",
            f"- **Boards:** {len(ws.board_ids)}",
        ]
        # Include automation capabilities active in this workspace
        automations = _get_automation_registry()
        if automations:
            caps = sorted({a["capability"] for a in automations})
            lines.append(f"\n### Active Automations ({len(caps)})")
            for cap in caps:
                owners = [a["owner"] for a in automations if a["capability"] == cap]
                lines.append(f"- **{cap}** — {', '.join(set(owners))}")
        return _make_response(True, "\n".join(lines))

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
        # Append automation and SKM loop status
        automations = _get_automation_registry()
        if automations:
            caps = sorted({a["capability"] for a in automations})
            report += f"\n\n### Automation Status ({len(automations)} active)\n"
            report += "Capabilities: " + ", ".join(caps[:8])
            if len(caps) > 8:
                report += f" +{len(caps) - 8} more"

        # SKM loop summary
        setpoints = _get_active_setpoints()
        loops = _get_active_loops()
        enabled_loops = sum(1 for l in loops.values() if l["enabled"])
        report += f"\n\n### SKM Loop: {enabled_loops}/{len(loops)} loops active"
        gate_gen = _get_gate_generator()
        gates = gate_gen.list_gates()
        if gates:
            passed = sum(1 for g in gates if g.get("status") == "passed")
            report += f" | {len(gates)} gates ({passed} passed)"
        return _make_response(True, report)

    if sub == "weekly":
        workspace = args[0] if args else "Murphy System"
        report = gen.generate_weekly_report(
            workspace_name=workspace,
            stats={"tasks_completed": 0, "tasks_in_progress": 0, "tasks_blocked": 0},
        )
        # Append automation and SKM loop summary for weekly
        automations = _get_automation_registry()
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]
        report += "\n\n### Weekly Automation Summary\n"
        report += f"- **Org-level automations:** {len(pos_auto)}\n"
        report += f"- **Employee-level automations:** {len(shadow_auto)}\n"

        setpoints = _get_active_setpoints()
        report += "\n### Setpoint Health\n"
        report += "| Dimension | Target | Range |\n|---|---|---|\n"
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            report += f"| {dim} | {sp['value']:.2f} | [{rng[0]:.1f}, {rng[1]:.1f}] |\n"

        loops = _get_active_loops()
        enabled = sum(1 for l in loops.values() if l["enabled"])
        report += f"\n### Business Loops: {enabled}/{len(loops)} active"
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
        lines = ["## ☠ Onboarding Started\n"]
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
            lines.append("\n**Last evaluation:**")
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

# Default PI control setpoints — each maps a dimension name to a dict with
# value (float), description (str), and range ([min, max]).
# Lazily deep-copied into _active_setpoints on first access.
# Cleared on reset_engines().
_DEFAULT_SETPOINTS = {
    "money": {"value": 0.5, "description": "Budget neutrality target", "range": [0.0, 1.0]},
    "time": {"value": 0.5, "description": "On-schedule target", "range": [0.0, 1.0]},
    "production": {"value": 1.0, "description": "Production pace target", "range": [0.0, 1.5]},
    "confidence": {"value": 1.0, "description": "Full confidence desired", "range": [0.0, 1.0]},
    "info_completeness": {"value": 1.0, "description": "Full information desired", "range": [0.0, 1.0]},
    "risk": {"value": 0.0, "description": "Zero risk desired", "range": [0.0, 1.0]},
}

# Mutable working copy; None until first _get_active_setpoints() call.
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

# Default business loop configurations — each maps a loop name to a dict
# with description (str), interval_seconds (int), range ([min, max] seconds),
# and enabled (bool).  Lazily deep-copied into _active_loops on first access.
# Cleared on reset_engines().
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

# Mutable working copy; None until first _get_active_loops() call.
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
        # SKM loop linkage
        automations = _get_automation_registry()
        if automations:
            caps = sorted({a["capability"] for a in automations})
            lines.append(f"\n### SKM Loop Automation Linkage ({len(caps)} capabilities)")
            lines.append("Loops feed the **Sense→Know→Model** cycle:")
            lines.append(f"- **SENSE:** heartbeat, production_pace → observe {len(caps)} automation capabilities")
            lines.append("- **KNOW:** compliance_check, risk_assessment → evaluate gates")
            lines.append("- **MODEL:** financial_review, stakeholder_reporting → adapt schedules")
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
# !murphy skm [status|sense|know|model|cycle]
# ---------------------------------------------------------------------------

def handle_skm(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy skm`` — Sense-Know-Model loop.

    The SKM loop is the core operating cycle that wires together
    observation, evaluation, and adaptation:

      SENSE  → Read setpoints, metrics, and automation telemetry.
      KNOW   → Evaluate state against gates and thresholds.
      MODEL  → Adapt automations, schedules, and recipes based on outcomes.

    Subcommands:
        status   — Full SKM loop overview
        sense    — Show what the system is observing (setpoints + automations)
        know     — Show gate evaluations and threshold checks
        model    — Show adaptation actions and loop adjustments
        cycle    — Run a virtual SKM cycle and show results
    """
    sub = getattr(cmd, "subcommand", None) or "status"
    args = getattr(cmd, "args", [])

    automations = _get_automation_registry()
    setpoints = _get_active_setpoints()
    loops = _get_active_loops()
    gate_gen = _get_gate_generator()
    gates = gate_gen.list_gates()
    flow = _get_onboarding_flow()

    if sub == "status":
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]
        enabled_loops = sum(1 for l in loops.values() if l["enabled"])
        passed_gates = sum(1 for g in gates if g.get("status") == "passed")
        failed_gates = sum(1 for g in gates if g.get("status") == "failed")
        pending_gates = sum(1 for g in gates if g.get("status") == "pending")

        lines = ["## ☠ Sense-Know-Model Loop Status\n"]
        lines.append("```")
        lines.append("  ┌──────────┐      ┌──────────┐      ┌──────────┐")
        lines.append("  │  SENSE   │ ───► │   KNOW   │ ───► │  MODEL   │")
        lines.append("  │ observe  │      │ evaluate │      │  adapt   │")
        lines.append("  └──────────┘      └──────────┘      └──────────┘")
        lines.append("       ▲                                    │")
        lines.append("       └────────────────────────────────────┘")
        lines.append("```\n")

        lines.append("### SENSE (Observation)")
        lines.append(f"- **Setpoints:** {len(setpoints)} dimensions configured")
        lines.append(f"- **Automations observed:** {len(automations)} "
                     f"({len(pos_auto)} org, {len(shadow_auto)} employee)")
        lines.append(f"- **Business loops:** {enabled_loops}/{len(loops)} active\n")

        lines.append("### KNOW (Evaluation)")
        lines.append(f"- **Gates total:** {len(gates)}")
        lines.append(f"- **Passed:** {passed_gates} | **Failed:** {failed_gates} | **Pending:** {pending_gates}")
        objectives = sorted({g.get("objective_id", "?") for g in gates})
        if objectives:
            lines.append(f"- **Objectives covered:** {', '.join(objectives)}\n")

        lines.append("### MODEL (Adaptation)")
        caps = sorted({a["capability"] for a in automations})
        lines.append(f"- **Automation capabilities:** {len(caps)}")
        if caps:
            lines.append(f"  {', '.join(caps)}")
        sessions = flow.list_sessions()
        completed = [s for s in sessions if s.get("phase") == "completed"]
        lines.append(f"- **Onboarded employees:** {len(completed)}/{len(sessions)}")
        lines.append(f"- **Shadow agents:** {len(flow.get_shadow_agents())}")

        return _make_response(True, "\n".join(lines))

    if sub == "sense":
        lines = ["## ☠ SKM → SENSE Phase\n"]
        lines.append("The SENSE phase observes the current system state.\n")
        lines.append("### Setpoints")
        lines.append("| Dimension | Value | Range |")
        lines.append("|-----------|-------|-------|")
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            lines.append(f"| {dim} | {sp['value']:.2f} | [{rng[0]:.1f}, {rng[1]:.1f}] |")

        lines.append("\n### Observed Automations")
        if automations:
            lines.append("| Capability | Source | Owner | Status |")
            lines.append("|------------|--------|-------|--------|")
            for a in automations[:20]:
                lines.append(
                    f"| {a['capability']} | {a['source']} "
                    f"| {a['owner'][:20]} | {a['status']} |"
                )
            if len(automations) > 20:
                lines.append(f"\n… +{len(automations) - 20} more")
        else:
            lines.append("No automations observed. Run `!murphy onboard init` and complete onboarding.")

        lines.append("\n### Active Loops (sensors)")
        for name, cfg in loops.items():
            if cfg["enabled"]:
                lines.append(f"- **{name}** every {cfg['interval_seconds']}s — {cfg['description']}")
        return _make_response(True, "\n".join(lines))

    if sub == "know":
        lines = ["## ☠ SKM → KNOW Phase\n"]
        lines.append("The KNOW phase evaluates state against gates and thresholds.\n")
        if gates:
            lines.append("### Gate Evaluations")
            lines.append("| Gate | Objective | Type | Threshold | Status |")
            lines.append("|------|-----------|------|-----------|--------|")
            for g in gates:
                lines.append(
                    f"| `{g['gate_id']}` | {g['objective_id']} "
                    f"| {g['gate_type']} | {g['threshold']} | {g['status']} |"
                )
        else:
            lines.append("No gates configured. Use `!murphy gate create` to define gates.")

        lines.append("\n### Setpoint Thresholds")
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            in_range = rng[0] <= sp["value"] <= rng[1]
            status = "✅ OK" if in_range else "⚠️ OUT OF RANGE"
            lines.append(f"- **{dim}**: {sp['value']:.2f} ({status})")
        return _make_response(True, "\n".join(lines))

    if sub == "model":
        lines = ["## ☠ SKM → MODEL Phase\n"]
        lines.append("The MODEL phase adapts the system based on evaluation results.\n")

        lines.append("### Automation Capabilities")
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]
        if shadow_auto:
            lines.append("\n**Employee-level (shadow agents):**")
            for a in shadow_auto:
                lines.append(f"- `{a['agent_id']}` → {a['capability']}")
        if pos_auto:
            lines.append("\n**Org-level (positions):**")
            seen = set()
            for a in pos_auto:
                key = f"{a['owner']}:{a['capability']}"
                if key not in seen:
                    seen.add(key)
                    lines.append(f"- {a['owner']} → {a['capability']}")

        lines.append("\n### Loop Schedule Adaptations")
        for name, cfg in loops.items():
            state = "🟢" if cfg["enabled"] else "🔴"
            lines.append(f"- {state} **{name}** → {cfg['interval_seconds']}s")

        # Model the impact: which gates are driven by which loops
        lines.append("\n### Gate-Loop Mapping")
        lines.append("| Loop | Drives Gate Types |")
        lines.append("|------|-------------------|")
        lines.append("| heartbeat | PI control → all dimensions |")
        lines.append("| financial_review | budget_gate, roi_gate |")
        lines.append("| compliance_check | compliance_gate, approval_gate |")
        lines.append("| risk_assessment | risk_gate |")
        lines.append("| production_pace | timeline_gate |")
        lines.append("| stakeholder_reporting | executive dashboards |")

        return _make_response(True, "\n".join(lines))

    if sub == "cycle":
        lines = ["## ☠ SKM Cycle Execution\n"]

        # SENSE
        lines.append("### 1. SENSE — Observing state")
        lines.append(f"  📡 Reading {len(setpoints)} setpoint dimensions")
        lines.append(f"  📡 Observing {len(automations)} automation capabilities")
        enabled_loops = sum(1 for l in loops.values() if l["enabled"])
        lines.append(f"  📡 {enabled_loops} business loops active\n")

        # KNOW
        lines.append("### 2. KNOW — Evaluating gates")
        passed = sum(1 for g in gates if g.get("status") == "passed")
        failed = sum(1 for g in gates if g.get("status") == "failed")
        pending = sum(1 for g in gates if g.get("status") == "pending")
        lines.append(f"  🔍 {len(gates)} gates evaluated: {passed}✅ {failed}❌ {pending}⏳")

        # Check setpoint health
        healthy = 0
        for dim, sp in setpoints.items():
            rng = sp.get("range", [0, 1])
            if rng[0] <= sp["value"] <= rng[1]:
                healthy += 1
        lines.append(f"  🔍 Setpoint health: {healthy}/{len(setpoints)} in range\n")

        # MODEL
        lines.append("### 3. MODEL — Adaptation recommendations")
        if failed > 0:
            lines.append(f"  ⚡ {failed} gate(s) FAILED → consider adjusting setpoints or loop intervals")
        if pending > 0:
            lines.append(f"  ⏳ {pending} gate(s) PENDING → evaluate with `!murphy gate evaluate`")
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        if not shadow_auto:
            lines.append("  💡 No employee automations — complete onboarding to populate")
        else:
            lines.append(f"  ✅ {len(shadow_auto)} employee automation(s) active")
        if not gates:
            lines.append("  💡 No gates defined — create with `!murphy gate create`")
        else:
            lines.append(f"  ✅ {len(gates)} gate(s) configured across "
                        f"{len({g.get('objective_id') for g in gates})} objective(s)")

        lines.append(f"\n**Cycle complete.** SKM loop healthy: "
                     f"{'✅ YES' if (healthy == len(setpoints) and failed == 0) else '⚠️ NEEDS ATTENTION'}")
        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown skm subcommand `{sub}`. "
                          "Try: status, sense, know, model, cycle.")


# ---------------------------------------------------------------------------
# !murphy automation [list|summary]
# ---------------------------------------------------------------------------

def handle_automation(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy automation`` — unified automation view.

    Shows all automations from onboarding, org chart, and recipes
    in a single consolidated view.

    Subcommands:
        list     — list all automation capabilities and their sources
        summary  — high-level summary of automation coverage
    """
    sub = getattr(cmd, "subcommand", None) or "list"
    automations = _get_automation_registry()

    if sub == "list":
        lines = ["## ☠ Automation Registry\n"]
        if not automations:
            lines.append("No automations configured. Complete onboarding to populate.")
            lines.append("\nUse `!murphy onboard init` → `!murphy onboard start` to begin.")
            return _make_response(True, "\n".join(lines))

        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]

        if shadow_auto:
            lines.append("### Employee Automations (Shadow Agents)\n")
            lines.append("| Capability | Agent | Owner | IP Class |")
            lines.append("|------------|-------|-------|----------|")
            for a in shadow_auto:
                lines.append(
                    f"| {a['capability']} | `{a['agent_id']}` "
                    f"| {a['owner'][:16]} | {a['ip_class']} |"
                )

        if pos_auto:
            lines.append("\n### Org-Level Automations (Positions)\n")
            lines.append("| Capability | Position | IP Class |")
            lines.append("|------------|----------|----------|")
            seen = set()
            for a in pos_auto:
                key = f"{a['owner']}:{a['capability']}"
                if key not in seen:
                    seen.add(key)
                    lines.append(
                        f"| {a['capability']} | {a['owner']} | {a['ip_class']} |"
                    )

        return _make_response(True, "\n".join(lines))

    if sub == "summary":
        lines = ["## ☠ Automation Summary\n"]
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]
        all_caps = sorted({a["capability"] for a in automations})

        lines.append(f"**Total automations:** {len(automations)}")
        lines.append(f"**Unique capabilities:** {len(all_caps)}")
        lines.append(f"**Org-level:** {len(pos_auto)}")
        lines.append(f"**Employee-level:** {len(shadow_auto)}\n")

        if all_caps:
            lines.append("### Capability Coverage")
            for cap in all_caps:
                owners = [a["owner"] for a in automations if a["capability"] == cap]
                lines.append(f"- **{cap}** ({len(owners)} source{'s' if len(owners) != 1 else ''})")

        # Cross-reference with SKM loop
        loops = _get_active_loops()
        enabled = sum(1 for l in loops.values() if l["enabled"])
        gates = _get_gate_generator().list_gates()
        lines.append("\n### SKM Loop Integration")
        lines.append(f"- Business loops: {enabled}/{len(loops)} active")
        lines.append(f"- Gates: {len(gates)} configured")
        lines.append(f"- Setpoints: {len(_get_active_setpoints())} dimensions")

        return _make_response(True, "\n".join(lines))

    return _make_response(False, f"Unknown automation subcommand `{sub}`. Try: list, summary.")


# ---------------------------------------------------------------------------
# !murphy automation [list|summary|types|mode|hub|rbac|readiness|scale|loop|
#                     scheduler|marketplace|native|self|onboard-engine|
#                     building|manufacturing|sales|compliance-bridge|full|deploy]
# ---------------------------------------------------------------------------

def handle_automation(dispatcher: object, cmd: object) -> object:
    """Handle ``!murphy automation`` — unified automation view and control.

    Subcommands:
        list             — list all automation capabilities and their sources
        summary          — high-level summary of automation coverage
        types            — list all automation categories from the type registry
        mode [show|set N|history]
                         — AutomationModeController: view or change HITL mode
        hub [status|modules|routes]
                         — AutomationIntegrationHub: integration routing
        rbac [roles|check USER|grant USER ROLE|revoke USER ROLE]
                         — AutomationRBACController: access control
        readiness [check|report]
                         — AutomationReadinessEvaluator: module readiness
        scale [status|up TYPE|down TYPE]
                         — AutomationScaler: expand/contract automation capacity
        loop [status|run|history]
                         — AutomationLoopConnector: SKM loop integration
        scheduler [queue|status]
                         — AutomationScheduler: project execution queue
        marketplace [list|popular|search QUERY]
                         — AutomationMarketplace: community automation listings
        native [status|list]
                         — MurphyNativeRunner: native task execution
        self [status|tasks|cycle]
                         — SelfAutomationOrchestrator: self-improvement tasks
        onboard-engine [list|status]
                         — OnboardingAutomationEngine: structured onboarding flows
        building [status|devices]
                         — BuildingAutomationOrchestrator: IoT/BMS connectors
        manufacturing [status|connectors|standards]
                         — ManufacturingAutomationRegistry: OT/ICS standards
        sales [pipeline|leads]
                         — SalesAutomationEngine: lead scoring and pipeline
        compliance-bridge [posture|history|check]
                         — ComplianceAutomationBridge: compliance check runner
        full [status|mode|risks|gaps]
                         — FullAutomationController: HITL graduation controls
        deploy [list|status]
                         — DeploymentAutomationController: deployment gates
    """
    sub = getattr(cmd, "subcommand", None) or "list"
    args = getattr(cmd, "args", [])
    action = args[0] if args else "show"
    automations = _get_automation_registry()

    # ── list ──────────────────────────────────────────────────────────────
    if sub == "list":
        lines = ["## ☠ Automation Registry\n"]
        if not automations:
            lines.append("No automations configured. Complete onboarding to populate.")
            lines.append("\nUse `!murphy onboard init` → `!murphy onboard start` to begin.")
            return _make_response(True, "\n".join(lines))

        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]

        if shadow_auto:
            lines.append("### Employee Automations (Shadow Agents)\n")
            lines.append("| Capability | Agent | Owner | IP Class |")
            lines.append("|------------|-------|-------|----------|")
            for a in shadow_auto:
                lines.append(
                    f"| {a['capability']} | `{a['agent_id']}` "
                    f"| {a['owner'][:16]} | {a['ip_class']} |"
                )

        if pos_auto:
            lines.append("\n### Org-Level Automations (Positions)\n")
            lines.append("| Capability | Position | IP Class |")
            lines.append("|------------|----------|----------|")
            seen = set()
            for a in pos_auto:
                key = f"{a['owner']}:{a['capability']}"
                if key not in seen:
                    seen.add(key)
                    lines.append(
                        f"| {a['capability']} | {a['owner']} | {a['ip_class']} |"
                    )

        return _make_response(True, "\n".join(lines))

    # ── summary ───────────────────────────────────────────────────────────
    if sub == "summary":
        lines = ["## ☠ Automation Summary\n"]
        shadow_auto = [a for a in automations if a["owner_type"] == "shadow_agent"]
        pos_auto = [a for a in automations if a["owner_type"] == "position"]
        all_caps = sorted({a["capability"] for a in automations})

        lines.append(f"**Total automations:** {len(automations)}")
        lines.append(f"**Unique capabilities:** {len(all_caps)}")
        lines.append(f"**Org-level:** {len(pos_auto)}")
        lines.append(f"**Employee-level:** {len(shadow_auto)}\n")

        if all_caps:
            lines.append("### Capability Coverage")
            for cap in all_caps:
                owners = [a["owner"] for a in automations if a["capability"] == cap]
                lines.append(f"- **{cap}** ({len(owners)} source{'s' if len(owners) != 1 else ''})")

        # Cross-reference with SKM loop
        loops = _get_active_loops()
        enabled = sum(1 for l in loops.values() if l["enabled"])
        gates = _get_gate_generator().list_gates()
        lines.append("\n### SKM Loop Integration")
        lines.append(f"- Business loops: {enabled}/{len(loops)} active")
        lines.append(f"- Gates: {len(gates)} configured")
        lines.append(f"- Setpoints: {len(_get_active_setpoints())} dimensions")

        return _make_response(True, "\n".join(lines))

    # ── types ─────────────────────────────────────────────────────────────
    if sub == "types":
        try:
            from automation_type_registry import DEFAULT_TEMPLATES, AutomationCategory
            lines = ["## Automation Type Categories\n"]
            for cat in AutomationCategory:
                templates = [t for t in DEFAULT_TEMPLATES if t.category == cat]
                lines.append(f"**{cat.value}** — {len(templates)} template(s)")
                for t in templates[:3]:
                    lines.append(f"  - `{t.template_id}` — {t.name}")
                if len(templates) > 3:
                    lines.append(f"  - *(+{len(templates) - 3} more)*")
            return _make_response(True, "\n".join(lines))
        except Exception as exc:
            return _make_response(False, f"Could not load automation type registry: {exc}")

    # ── mode ──────────────────────────────────────────────────────────────
    if sub == "mode":
        try:
            ctrl = _get_automation_mode_controller()
            if action in ("show", "status"):
                status = ctrl.get_status()
                lines = ["## Automation Mode\n",
                         f"**Current mode:** `{status.get('current_mode', 'unknown')}`",
                         f"**EMA score:** `{status.get('current_ema', 0):.3f}`",
                         f"**Total transitions:** {status.get('total_transitions', 0)}",
                         "\n*Modes: 0=FULL_MANUAL 1=HITL_REQUIRED 2=SHADOW 3=SUPERVISED 4=FULL_AUTO*"]
                return _make_response(True, "\n".join(lines))
            if action == "set" and len(args) >= 2:
                from automation_mode_controller import AutomationMode
                try:
                    mode_val = int(args[1])
                    transition = ctrl.set_mode(AutomationMode(mode_val), reason=f"matrix command by {getattr(cmd, 'sender', 'unknown')}")
                    return _make_response(True, f"Mode set to `{transition.to_mode}` — {transition.reason}")
                except (ValueError, KeyError):
                    return _make_response(False, f"Invalid mode value: {args[1]}. Use 0–4.")
            if action == "history":
                transitions = ctrl.get_transitions(limit=10)
                lines = ["## Mode Transition History\n"]
                for t in transitions:
                    lines.append(f"- `{t.get('from_mode')}` → `{t.get('to_mode')}` at {t.get('timestamp', '')[:19]}: {t.get('reason', '')}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Mode Transition History\n\nNo transitions recorded.")
            return _make_response(False, "Usage: `!murphy automation mode [show|set <0-4>|history]`")
        except Exception as exc:
            return _make_response(False, f"Automation mode error: {exc}")

    # ── hub ───────────────────────────────────────────────────────────────
    if sub == "hub":
        try:
            hub = _get_automation_integration_hub()
            if action in ("show", "status"):
                report = hub.generate_health_report()
                status = hub.get_status()
                lines = ["## Automation Integration Hub\n",
                         f"**Registered modules:** {status.get('registered_modules', 0)}",
                         f"**Routes processed:** {status.get('total_routes_processed', 0)}",
                         f"**Errors:** {status.get('total_errors', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "modules":
                mods = hub.list_modules()
                lines = ["## Hub Modules\n"]
                for m in mods:
                    phase = m.get("phase", "unknown")
                    label = m.get("design_label", "?")
                    lines.append(f"- `{label}` — phase: {phase}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Hub Modules\n\nNo modules registered.")
            if action == "routes":
                routes = hub.get_event_routes()
                lines = ["## Hub Event Routes\n"]
                for event_type, labels in routes.items():
                    lines.append(f"**{event_type}:** {', '.join(f'`{l}`' for l in labels)}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Hub Event Routes\n\nNo routes configured.")
            return _make_response(False, "Usage: `!murphy automation hub [status|modules|routes]`")
        except Exception as exc:
            return _make_response(False, f"Integration hub error: {exc}")

    # ── rbac ──────────────────────────────────────────────────────────────
    if sub == "rbac":
        try:
            rbac = _get_automation_rbac_controller()
            if action in ("show", "status"):
                status = rbac.get_status()
                lines = ["## Automation RBAC\n",
                         f"**Role assignments:** {status.get('total_assignments', 0)}",
                         f"**Audit entries:** {status.get('audit_log_size', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "roles" and len(args) >= 2:
                user_id = args[1]
                tenant_id = args[2] if len(args) >= 3 else "default"
                roles = rbac.get_roles(user_id, tenant_id)
                return _make_response(True, f"Roles for `{user_id}` in `{tenant_id}`: {', '.join(roles) or 'none'}")
            if action == "grant" and len(args) >= 3:
                from automation_rbac_controller import AutomationRole
                user_id, role_str = args[1], args[2]
                tenant_id = args[3] if len(args) >= 4 else "default"
                rbac.assign_role(user_id, tenant_id, AutomationRole(role_str))
                return _make_response(True, f"Granted role `{role_str}` to `{user_id}` in `{tenant_id}`.")
            if action == "revoke" and len(args) >= 3:
                from automation_rbac_controller import AutomationRole
                user_id, role_str = args[1], args[2]
                tenant_id = args[3] if len(args) >= 4 else "default"
                removed = rbac.revoke_role(user_id, tenant_id, AutomationRole(role_str))
                return _make_response(True, f"Revoked role `{role_str}` from `{user_id}`." if removed else f"Role `{role_str}` not found for `{user_id}`.")
            return _make_response(False, "Usage: `!murphy automation rbac [status|roles USER|grant USER ROLE|revoke USER ROLE]`")
        except Exception as exc:
            return _make_response(False, f"RBAC error: {exc}")

    # ── readiness ─────────────────────────────────────────────────────────
    if sub == "readiness":
        try:
            evaluator = _get_automation_readiness_evaluator()
            if action in ("check", "show"):
                report = evaluator.evaluate()
                status = evaluator.get_status()
                verdict = getattr(report, "verdict", None) or getattr(report, "overall_verdict", "unknown")
                verdict_val = verdict.value if hasattr(verdict, "value") else verdict
                lines = ["## Automation Readiness\n",
                         f"**Overall verdict:** `{verdict_val}`",
                         f"**Modules evaluated:** {len(getattr(report, 'phases', []))}",
                         f"**Reports generated:** {status.get('total_reports', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "report":
                reports = evaluator.get_reports(limit=5)
                lines = ["## Readiness Report History\n"]
                for r in reports:
                    v = r.get("verdict", r.get("overall_verdict", "?"))
                    lines.append(f"- `{v}` at {str(r.get('evaluated_at', ''))[:19]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Readiness Report History\n\nNo reports yet.")
            return _make_response(False, "Usage: `!murphy automation readiness [check|report]`")
        except Exception as exc:
            return _make_response(False, f"Readiness evaluator error: {exc}")

    # ── scale ─────────────────────────────────────────────────────────────
    if sub == "scale":
        try:
            scaler = _get_automation_scaler()
            if action in ("show", "status"):
                status = scaler.get_status() if hasattr(scaler, "get_status") else {"note": "Use sub-actions to evaluate specific types"}
                lines = ["## Automation Scaler\n"]
                for k, v in status.items():
                    lines.append(f"- **{k}:** {v}")
                return _make_response(True, "\n".join(lines))
            if action in ("up", "down") and len(args) >= 2:
                from automation_scaler import AutomationType
                try:
                    auto_type = AutomationType(args[1])
                    if action == "up":
                        event = scaler.scale_up(auto_type)
                    else:
                        event = scaler.scale_down(auto_type)
                    return _make_response(True, f"Scale `{action}` for `{auto_type.value}`: {event.to_dict().get('result', 'done')}")
                except Exception as se:
                    return _make_response(False, f"Scale error: {se}")
            if action == "evaluate" and len(args) >= 2:
                from automation_scaler import AutomationType
                try:
                    auto_type = AutomationType(args[1])
                    result = scaler.evaluate_scaling(auto_type)
                    lines = [f"## Scale Evaluation: {auto_type.value}\n"]
                    for k, v in result.items():
                        lines.append(f"- **{k}:** {v}")
                    return _make_response(True, "\n".join(lines))
                except Exception as se:
                    return _make_response(False, f"Evaluate error: {se}")
            return _make_response(False, "Usage: `!murphy automation scale [status|up TYPE|down TYPE|evaluate TYPE]`")
        except Exception as exc:
            return _make_response(False, f"Scaler error: {exc}")

    # ── loop ──────────────────────────────────────────────────────────────
    if sub == "loop":
        try:
            connector = _get_automation_loop_connector()
            if action in ("show", "status"):
                status = connector.get_status()
                lines = ["## Automation Loop Connector\n",
                         f"**Cycles run:** {status.get('total_cycles', 0)}",
                         f"**Last cycle:** {str(status.get('last_cycle_at', 'never'))[:19]}",
                         f"**Queued outcomes:** {status.get('queued_outcomes', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "run":
                result = connector.run_cycle()
                d = result.to_dict() if hasattr(result, "to_dict") else vars(result)
                lines = ["## Loop Cycle Complete\n",
                         f"**Proposals generated:** {d.get('proposals_generated', 0)}",
                         f"**Proposals applied:** {d.get('proposals_applied', 0)}",
                         f"**Errors:** {d.get('errors', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "history":
                history = connector.get_cycle_history(limit=5)
                lines = ["## Loop Cycle History\n"]
                for c in history:
                    lines.append(f"- `{c.get('cycle_id', '?')}` generated={c.get('proposals_generated', 0)} applied={c.get('proposals_applied', 0)}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Loop Cycle History\n\nNo cycles recorded.")
            return _make_response(False, "Usage: `!murphy automation loop [status|run|history]`")
        except Exception as exc:
            return _make_response(False, f"Loop connector error: {exc}")

    # ── scheduler ─────────────────────────────────────────────────────────
    if sub == "scheduler":
        try:
            scheduler = _get_automation_scheduler()
            if action in ("show", "status", "queue"):
                status = scheduler.get_status()
                queue = scheduler.get_queue_status()
                lines = ["## Automation Scheduler\n",
                         f"**Projects:** {status.get('total_projects', 0)}",
                         f"**Queued:** {queue.get('queued', 0)}",
                         f"**Running:** {queue.get('running', 0)}",
                         f"**Completed:** {queue.get('completed', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "next":
                batch = scheduler.get_next_batch(max_slots=5)
                lines = ["## Next Scheduled Executions\n"]
                for exe in batch:
                    lines.append(f"- `{exe.execution_id}` project=`{exe.project_id}` priority={exe.priority.value if hasattr(exe.priority, 'value') else exe.priority}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Next Scheduled Executions\n\nNothing queued.")
            return _make_response(False, "Usage: `!murphy automation scheduler [status|queue|next]`")
        except Exception as exc:
            return _make_response(False, f"Scheduler error: {exc}")

    # ── marketplace ───────────────────────────────────────────────────────
    if sub == "marketplace":
        try:
            market = _get_automation_marketplace()
            if action in ("show", "list"):
                popular = market.get_popular(limit=5)
                lines = ["## Automation Marketplace (Top 5)\n"]
                for listing in popular:
                    lines.append(f"- **{listing.name}** `{listing.listing_id}` — {listing.description[:60]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Automation Marketplace\n\nNo listings yet.")
            if action == "popular":
                popular = market.get_popular(limit=10)
                lines = ["## Most Popular Automations\n",
                         "| Name | Installs | Rating |",
                         "|------|----------|--------|"]
                for listing in popular:
                    lines.append(f"| {listing.name} | {listing.install_count} | {listing.average_rating:.1f}⭐ |")
                return _make_response(True, "\n".join(lines) if len(lines) > 3 else "## Most Popular Automations\n\nNo listings yet.")
            if action == "search" and len(args) >= 2:
                query = " ".join(args[1:])
                results = market.search(query=query)
                lines = [f"## Marketplace Search: \"{query}\"\n"]
                for listing in results[:10]:
                    lines.append(f"- **{listing.name}** — {listing.description[:60]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else f"No results for \"{query}\".")
            return _make_response(False, "Usage: `!murphy automation marketplace [list|popular|search QUERY]`")
        except Exception as exc:
            return _make_response(False, f"Marketplace error: {exc}")

    # ── native ────────────────────────────────────────────────────────────
    if sub == "native":
        try:
            runner = _get_murphy_native_runner()
            if action in ("show", "status"):
                run_log = runner.get_run_log()
                lines = ["## Murphy Native Automation\n",
                         f"**Tasks run:** {len(run_log)}",
                         f"**Last run:** {run_log[-1].get('started_at', 'never')[:19] if run_log else 'never'}"]
                return _make_response(True, "\n".join(lines))
            if action == "list":
                run_log = runner.get_run_log()
                lines = ["## Native Task Run Log\n"]
                for entry in run_log[-10:]:
                    lines.append(f"- `{entry.get('task_id', '?')}` — {entry.get('status', '?')} at {str(entry.get('started_at', ''))[:19]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Native Task Run Log\n\nNo tasks run yet.")
            return _make_response(False, "Usage: `!murphy automation native [status|list]`")
        except Exception as exc:
            return _make_response(False, f"Native runner error: {exc}")

    # ── self ──────────────────────────────────────────────────────────────
    if sub == "self":
        try:
            orch = _get_self_automation_orchestrator()
            if action in ("show", "status"):
                tasks = orch.list_tasks()
                pending = [t for t in tasks if getattr(t, "status", None) and t.status.value in ("pending", "in_progress")]
                lines = ["## Self-Improvement Orchestrator\n",
                         f"**Total tasks:** {len(tasks)}",
                         f"**Active:** {len(pending)}",
                         f"**Cycle history:** {len(orch.get_cycle_history())}"]
                return _make_response(True, "\n".join(lines))
            if action == "tasks":
                tasks = orch.list_tasks()
                lines = ["## Self-Improvement Tasks\n"]
                for t in tasks[:10]:
                    lines.append(f"- `{t.task_id}` [{t.status.value if hasattr(t.status, 'value') else t.status}] {t.title}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Self-Improvement Tasks\n\nNo tasks.")
            if action == "cycle":
                cycles = orch.get_cycle_history()
                lines = ["## Self-Improvement Cycle History\n"]
                for c in cycles[-5:]:
                    d = vars(c) if not isinstance(c, dict) else c
                    lines.append(f"- `{d.get('cycle_id', '?')}` started={str(d.get('started_at', ''))[:19]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Cycle History\n\nNo cycles recorded.")
            return _make_response(False, "Usage: `!murphy automation self [status|tasks|cycle]`")
        except Exception as exc:
            return _make_response(False, f"Self orchestrator error: {exc}")

    # ── onboard-engine ────────────────────────────────────────────────────
    if sub in ("onboard-engine", "onboard_engine"):
        try:
            engine = _get_onboarding_automation_engine()
            if action in ("show", "status", "list"):
                status = engine.get_status()
                profiles = engine.list_profiles()
                lines = ["## Onboarding Automation Engine\n",
                         f"**Active profiles:** {status.get('active_profiles', len(profiles))}",
                         f"**Total profiles:** {status.get('total_profiles', len(profiles))}"]
                for p in profiles[:5]:
                    d = p if isinstance(p, dict) else p.to_dict() if hasattr(p, "to_dict") else vars(p)
                    lines.append(f"  - `{d.get('profile_id', '?')}` {d.get('employee_name', '')} — {d.get('progress_pct', 0):.0f}%")
                return _make_response(True, "\n".join(lines))
            return _make_response(False, "Usage: `!murphy automation onboard-engine [status|list]`")
        except Exception as exc:
            return _make_response(False, f"Onboarding engine error: {exc}")

    # ── building ──────────────────────────────────────────────────────────
    if sub == "building":
        try:
            from building_automation_connectors import get_status as _bac_get_status
            registry = _get_building_automation_orchestrator()
            if action in ("show", "status"):
                status = _bac_get_status()
                lines = ["## Building Automation\n",
                         f"**Connectors:** {status.get('default_connectors', 0)}",
                         f"**Enabled:** {status.get('enabled_connectors', 0)}",
                         f"**Status:** {status.get('status', 'unknown')}",
                         f"**Protocols:** {', '.join(status.get('protocols', []))}",
                         f"**System categories:** {', '.join(status.get('system_categories', []))}"]
                return _make_response(True, "\n".join(lines))
            if action == "devices":
                connectors = registry.discover() if hasattr(registry, "discover") else []
                lines = ["## Building Automation Devices\n"]
                for c in connectors[:10]:
                    d = c if isinstance(c, dict) else vars(c) if hasattr(c, "__dict__") else {}
                    lines.append(f"- `{d.get('connector_id', d.get('name', d.get('vendor', '?')))}` — {d.get('status', '?')}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Building Automation Devices\n\nNo devices registered.")
            return _make_response(False, "Usage: `!murphy automation building [status|devices]`")
        except Exception as exc:
            return _make_response(False, f"Building automation error: {exc}")

    # ── manufacturing ─────────────────────────────────────────────────────
    if sub == "manufacturing":
        try:
            from manufacturing_automation_standards import get_status as mfg_status
            registry = _get_manufacturing_automation_registry()
            if action in ("show", "status"):
                status = mfg_status()
                lines = ["## Manufacturing Automation\n"]
                for k, v in status.items():
                    lines.append(f"- **{k}:** {v}")
                return _make_response(True, "\n".join(lines))
            if action in ("connectors", "standards"):
                discovered = registry.discover()
                lines = ["## Manufacturing Connectors/Standards\n",
                         "| Standard | Layer | Status |",
                         "|----------|-------|--------|"]
                for c in discovered[:10]:
                    lines.append(f"| {c.get('standard', '?')} | {c.get('layer', '?')} | {c.get('status', '?')} |")
                return _make_response(True, "\n".join(lines) if len(lines) > 3 else "## Manufacturing Connectors\n\nNone registered.")
            return _make_response(False, "Usage: `!murphy automation manufacturing [status|connectors|standards]`")
        except Exception as exc:
            return _make_response(False, f"Manufacturing automation error: {exc}")

    # ── sales ─────────────────────────────────────────────────────────────
    if sub == "sales":
        try:
            engine = _get_sales_automation_engine()
            if action in ("show", "pipeline"):
                summary = engine.get_pipeline_summary()
                lines = ["## Sales Automation Pipeline\n"]
                for stage, count in summary.get("by_stage", {}).items():
                    lines.append(f"- **{stage}:** {count} lead(s)")
                lines.append(f"\n**Total leads:** {summary.get('total_leads', 0)}")
                return _make_response(True, "\n".join(lines))
            if action == "leads":
                pipeline = engine.get_pipeline_summary()
                lines = ["## Sales Leads\n",
                         f"**Total:** {pipeline.get('total_leads', 0)}",
                         f"**By stage:** {pipeline.get('by_stage', {})}"]
                return _make_response(True, "\n".join(lines))
            return _make_response(False, "Usage: `!murphy automation sales [pipeline|leads]`")
        except Exception as exc:
            return _make_response(False, f"Sales automation error: {exc}")

    # ── compliance-bridge ─────────────────────────────────────────────────
    if sub in ("compliance-bridge", "compliance_bridge"):
        try:
            bridge = _get_compliance_automation_bridge()
            if action in ("show", "posture"):
                posture = bridge.get_compliance_posture()
                lines = ["## Compliance Automation Bridge\n",
                         f"**Total checks:** {posture.get('total_checks', 0)}",
                         f"**Violations tracked:** {posture.get('violations_tracked', 0)}",
                         f"**Frameworks active:** {posture.get('active_frameworks', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "history":
                history = bridge.get_history(limit=5)
                lines = ["## Compliance Check History\n"]
                for h in history:
                    lines.append(f"- `{h.get('check_id', '?')}` — {h.get('status', '?')} at {str(h.get('checked_at', ''))[:19]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Compliance Check History\n\nNo checks recorded.")
            if action == "check" and len(args) >= 2:
                deliverable_id = args[1]
                result = bridge.check_compliance(deliverable_id=deliverable_id)
                passed = result.get("passed", False)
                return _make_response(True, f"Compliance check `{deliverable_id}`: {'✅ PASSED' if passed else '❌ FAILED'}\n{result.get('summary', '')}")
            return _make_response(False, "Usage: `!murphy automation compliance-bridge [posture|history|check DELIVERABLE_ID]`")
        except Exception as exc:
            return _make_response(False, f"Compliance bridge error: {exc}")

    # ── full ──────────────────────────────────────────────────────────────
    if sub == "full":
        try:
            controller = _get_full_automation_controller()
            _tenant_id = getattr(cmd, "sender", "default-tenant")
            if action in ("show", "status"):
                metrics = controller.get_metrics(tenant_id=_tenant_id) or {}
                lines = ["## Full Automation Controller\n",
                         f"**Mode:** `{metrics.get('current_mode', 'unknown')}`",
                         f"**Actions evaluated:** {metrics.get('total_evaluated', 0)}",
                         f"**Auto-approved:** {metrics.get('auto_approved', 0)}",
                         f"**HITL required:** {metrics.get('hitl_required', 0)}",
                         f"**Active HITL gaps:** {metrics.get('active_hitl_gaps', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "mode" and len(args) >= 2:
                from full_automation_controller import AutomationMode as FAMode
                try:
                    mode = FAMode(args[1])
                    controller.set_automation_mode(tenant_id=_tenant_id, mode=mode, reason=f"matrix command by {getattr(cmd, 'sender', 'unknown')}")
                    return _make_response(True, f"Full automation mode set to `{mode.value}`.")
                except (ValueError, TypeError):
                    return _make_response(False, f"Invalid mode: {args[1]}. Options: {[m.value for m in FAMode]}")
            if action == "risks":
                gaps = controller.get_active_hitl_gaps(tenant_id=_tenant_id)
                lines = ["## Active HITL Gaps\n"]
                for g in gaps:
                    d = g if isinstance(g, dict) else vars(g)
                    lines.append(f"- `{d.get('gap_id', '?')}` risk={d.get('risk_level', '?')}: {d.get('description', '')[:60]}")
                return _make_response(True, "\n".join(lines) if len(lines) > 1 else "## Active HITL Gaps\n\nNo active gaps. 🎉")
            if action == "gaps":
                gaps = controller.get_active_hitl_gaps(tenant_id=_tenant_id)
                return _make_response(True, f"**Active HITL gaps:** {len(gaps)}")
            return _make_response(False, "Usage: `!murphy automation full [status|mode MODE|risks|gaps]`")
        except Exception as exc:
            return _make_response(False, f"Full automation controller error: {exc}")

    # ── deploy ────────────────────────────────────────────────────────────
    if sub == "deploy":
        try:
            dac = _get_deployment_automation_controller()
            if action in ("show", "list"):
                status = dac.get_status()
                lines = ["## Deployment Automation\n",
                         f"**Total deployments:** {status.get('total_deployments', 0)}",
                         f"**Running:** {status.get('running', 0)}",
                         f"**Completed:** {status.get('completed', 0)}",
                         f"**Failed/Rolled back:** {status.get('failed', 0) + status.get('rolled_back', 0)}"]
                return _make_response(True, "\n".join(lines))
            if action == "status" and len(args) >= 2:
                dep_id = args[1]
                dep = dac.get_deployment(dep_id)
                if dep is None:
                    return _make_response(False, f"Deployment `{dep_id}` not found.")
                lines = [f"## Deployment `{dep_id}`\n"]
                for k, v in dep.items():
                    lines.append(f"- **{k}:** {v}")
                return _make_response(True, "\n".join(lines))
            if action == "approve" and len(args) >= 2:
                dep_id = args[1]
                approver = getattr(cmd, "sender", "matrix-user")
                dep = dac.approve(dep_id, approver=approver)
                if dep:
                    return _make_response(True, f"Deployment `{dep_id}` approved by `{approver}`.")
                return _make_response(False, f"Deployment `{dep_id}` could not be approved.")
            return _make_response(False, "Usage: `!murphy automation deploy [list|status DEP_ID|approve DEP_ID]`")
        except Exception as exc:
            return _make_response(False, f"Deployment controller error: {exc}")

    return _make_response(
        False,
        "Unknown automation subcommand `" + sub + "`. "
        "Try: list, summary, types, mode, hub, rbac, readiness, scale, loop, "
        "scheduler, marketplace, native, self, onboard-engine, building, "
        "manufacturing, sales, compliance-bridge, full, deploy.",
    )


# ---------------------------------------------------------------------------
# All handlers (for registration convenience)
# ---------------------------------------------------------------------------


def handle_production(dispatcher: object, cmd: object) -> object:
    """``!murphy production <subcommand>`` — Production Assistant Engine (PROD-001).

    Subcommands:
      submit LOCATION INDUSTRY FUNCTIONS… SPEC — submit a new proposal
      validate PROPOSAL_ID                      — validate proposal at 99% confidence
      workorder PROPOSAL_ID DELIVERABLE         — submit a work order
      validate-wo WORK_ORDER_ID                 — validate work order deliverable
      advance PROFILE_ID STATE                  — advance lifecycle state
      profiles                                   — list all production profiles
      proposals                                  — list all proposals
      audit [LIMIT]                              — show audit log
    """
    args = list(getattr(cmd, "args", []))
    action = args[0].lower() if args else "profiles"

    try:
        pa = _get_production_assistant()

        if action in ("profiles", "list"):
            profiles = pa.list_profiles()
            lines = ["## Production Profiles\n"]
            if not profiles:
                lines.append("No profiles found.")
            for p in profiles[:20]:
                lines.append(
                    f"- `{p['profile_id']}` | lifecycle={p['lifecycle']} "
                    f"| proposal={p['proposal_id']}"
                )
            return _make_response(True, "\n".join(lines))

        if action == "proposals":
            proposals = pa.list_proposals()
            lines = ["## Production Proposals\n"]
            if not proposals:
                lines.append("No proposals found.")
            for p in proposals[:20]:
                lines.append(
                    f"- `{p['proposal_id']}` | status={p['status']} "
                    f"| confidence={p.get('confidence_score', 0):.3f} "
                    f"| {p.get('title') or p.get('regulatory_industry', '')}"
                )
            return _make_response(True, "\n".join(lines))

        if action == "validate" and len(args) >= 2:
            proposal_id = args[1]
            result = pa.validate_proposal(proposal_id)
            lines = [f"## Proposal Validation: `{proposal_id}`\n"]
            lines.append(f"**Passed:** {result.passed}")
            lines.append(f"**Confidence:** {result.confidence_score:.4f}")
            lines.append(f"**Regulatory OK:** {result.regulatory_ok}")
            lines.append(f"**Deliverable OK:** {result.deliverable_ok}")
            lines.append(f"**HITL OK:** {result.hitl_ok}")
            if result.failure_reasons:
                lines.append("\n**Failure reasons:**")
                for r in result.failure_reasons:
                    lines.append(f"- {r}")
            return _make_response(result.passed, "\n".join(lines))

        if action in ("validate-wo", "validate_wo") and len(args) >= 2:
            work_order_id = args[1]
            match = pa.validate_work_order(work_order_id)
            lines = [f"## Work Order Validation: `{work_order_id}`\n"]
            lines.append(f"**Passed:** {match.passed}")
            lines.append(f"**Confidence:** {match.confidence_score:.4f}")
            if match.missing_elements:
                lines.append(f"**Missing elements ({len(match.missing_elements)}):** "
                             + ", ".join(match.missing_elements[:10]))
            return _make_response(match.passed, "\n".join(lines))

        if action == "advance" and len(args) >= 3:
            profile_id = args[1]
            new_state_str = args[2].lower()
            from production_assistant import ProductionLifecycle
            try:
                new_state = ProductionLifecycle(new_state_str)
            except ValueError:
                return _make_response(
                    False,
                    f"Unknown lifecycle state `{new_state_str}`. "
                    f"Valid: {[s.value for s in ProductionLifecycle]}"
                )
            ok = pa.advance_lifecycle(profile_id, new_state)
            if ok:
                return _make_response(True, f"Profile `{profile_id}` advanced to `{new_state_str}`.")
            return _make_response(False, f"Cannot advance `{profile_id}` to `{new_state_str}`.")

        if action == "audit":
            limit = int(args[1]) if len(args) >= 2 else 10
            log = pa.get_audit_log(limit=limit)
            lines = [f"## Production Audit Log (last {limit})\n"]
            for entry in log:
                lines.append(f"- `{entry.get('action')}` at {entry.get('at', '')} — {entry.get('context', {})}")
            return _make_response(True, "\n".join(lines) if len(lines) > 1 else "No audit log entries.")

        return _make_response(
            False,
            "Usage: `!murphy production [profiles|proposals|validate PROPOSAL_ID"
            "|validate-wo WO_ID|advance PROFILE_ID STATE|audit [LIMIT]]`",
        )
    except Exception as exc:
        return _make_response(False, f"Production assistant error: {exc}")


def handle_campaign(dispatcher: object, cmd: object) -> object:
    """``!murphy campaign <subcommand>`` — Outreach Campaign Planner (CAMP-001).

    Subcommands:
      health                           — run compliance health check
      list                             — list all campaigns
      activate CAMPAIGN_ID             — activate a draft campaign
      pause CAMPAIGN_ID                — pause an active campaign
      suppress CONTACT_ID [REASON]     — add contact to suppression list
      suppressed CONTACT_ID            — check if contact is suppressed
      audit [LIMIT]                    — show audit log
    """
    args = list(getattr(cmd, "args", []))
    action = args[0].lower() if args else "list"

    try:
        cp = _get_campaign_planner()

        if action == "health":
            result = cp.campaign_health_check()
            lines = ["## Campaign Health Check\n"]
            lines.append(f"**Healthy:** {result.healthy}")
            lines.append(f"**Governor OK:** {result.governor_ok}")
            lines.append(f"**Compliance gate OK:** {result.compliance_gate_ok}")
            lines.append(f"**Suppression OK:** {result.suppression_ok}")
            lines.append(f"**Channel OK:** {result.channel_ok}")
            if result.issues:
                lines.append("\n**Issues:**")
                for issue in result.issues:
                    lines.append(f"- {issue}")
            return _make_response(result.healthy, "\n".join(lines))

        if action in ("list", "campaigns"):
            campaigns = cp.list_campaigns()
            lines = ["## Outreach Campaigns\n"]
            if not campaigns:
                lines.append("No campaigns found.")
            for c in campaigns[:20]:
                lines.append(
                    f"- `{c['campaign_id']}` | **{c['name']}** | "
                    f"status={c['status']} | sent={c['steps_executed']} "
                    f"blocked={c['steps_blocked']}"
                )
            return _make_response(True, "\n".join(lines))

        if action == "activate" and len(args) >= 2:
            campaign_id = args[1]
            ok = cp.activate_campaign(campaign_id)
            if ok:
                return _make_response(True, f"Campaign `{campaign_id}` is now ACTIVE.")
            return _make_response(False, f"Cannot activate campaign `{campaign_id}`.")

        if action == "pause" and len(args) >= 2:
            campaign_id = args[1]
            ok = cp.pause_campaign(campaign_id)
            if ok:
                return _make_response(True, f"Campaign `{campaign_id}` paused.")
            return _make_response(False, f"Cannot pause campaign `{campaign_id}`.")

        if action == "suppress" and len(args) >= 2:
            contact_id = args[1]
            reason = args[2] if len(args) >= 3 else "manual"
            cp.add_to_suppression(contact_id, reason)
            return _make_response(True, f"Contact `{contact_id}` added to suppression list (reason: {reason}).")

        if action == "suppressed" and len(args) >= 2:
            contact_id = args[1]
            is_sup = cp.is_suppressed(contact_id)
            return _make_response(
                True,
                f"Contact `{contact_id}` is {'**suppressed**' if is_sup else 'not suppressed'}.",
            )

        if action == "audit":
            limit = int(args[1]) if len(args) >= 2 else 10
            log = cp.get_audit_log(limit=limit)
            lines = [f"## Campaign Audit Log (last {limit})\n"]
            for entry in log:
                lines.append(f"- `{entry.get('action')}` at {entry.get('at', '')} — {entry.get('context', {})}")
            return _make_response(True, "\n".join(lines) if len(lines) > 1 else "No audit log entries.")

        return _make_response(
            False,
            "Usage: `!murphy campaign [health|list|activate CAMPAIGN_ID|pause CAMPAIGN_ID"
            "|suppress CONTACT_ID [REASON]|suppressed CONTACT_ID|audit [LIMIT]]`",
        )
    except Exception as exc:
        return _make_response(False, f"Campaign planner error: {exc}")


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
    "skm": handle_skm,
    "automation": handle_automation,
    "production": handle_production,
    "campaign": handle_campaign,
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
    "handle_skm",
    "handle_automation",
    "handle_production",
    "handle_campaign",
    "reset_engines",
    "MANAGEMENT_COMMAND_HANDLERS",
]
