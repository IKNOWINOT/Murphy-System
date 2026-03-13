"""
Management Systems
==================

Project management and workflow automation features accessible through
Matrix chat commands.

This package provides a full project management layer that maps across
all Murphy System subsystems, delivering board-based task tracking,
workflow automation, Gantt timelines, dashboards, and document management
directly within Matrix rooms.

Architecture overview::

    management_systems/
    ├── board_engine.py        – Core board/project management
    ├── status_engine.py       – Status labels, workflow state machine
    ├── timeline_engine.py     – Gantt timelines, critical path, milestones
    ├── automation_recipes.py  – "When X, do Y" recipe automation engine
    ├── workspace_manager.py   – Workspaces mapped to Murphy subsystem domains
    ├── dashboard_generator.py – ASCII/Markdown dashboard reports for Matrix
    ├── integration_bridge.py  – Bidirectional Murphy module ↔ board sync
    ├── form_builder.py        – Intake forms that auto-create board items
    └── doc_manager.py         – Workdoc management linked to boards/items

Integration with prior Matrix PRs:

- **PR 1 (#205):** ``matrix_bot.py``, ``matrix_config.py`` – bot foundation
- **PR 2 (#206):** ``command_router.py``, ``event_bridge.py`` – commands & events
- **PR 3 (#207):** ``message_router.py``, ``matrix_event_handler.py`` – message delivery

Quick start::

    from management_systems import (
        BoardEngine, ColumnType,
        StatusEngine,
        TimelineEngine,
        RecipeEngine, AutomationTrigger, TriggerType, AutomationAction, ActionType,
        WorkspaceManager,
        DashboardGenerator, DashboardTemplateType,
        IntegrationBridge, SyncEventType,
        FormBuilder, FormTemplateType,
        DocManager, DocType,
    )

    # Create a workspace for AI & ML modules
    ws_mgr = WorkspaceManager()
    ws_mgr.bootstrap_murphy_workspaces()
    ws = ws_mgr.get_workspace_by_domain("ai_ml_pipeline")

    # Create a sprint board
    board_engine = BoardEngine()
    board = board_engine.create_board(
        "AI Sprint 1",
        workspace_id=ws.id,
        owner_id="@alice:example.com",
    )
    print(board_engine.render_table(board.id))

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.4.0"
__codename__ = "Management Systems"

# -- Board Engine -----------------------------------------------------------
# -- Automation Recipes -----------------------------------------------------
from .automation_recipes import (
    ActionType,
    AutomationAction,
    AutomationRecipe,
    AutomationTrigger,
    ExecutionLogEntry,
    RecipeCondition,
    RecipeEngine,
    RecipeStatus,
    TriggerType,
)
from .board_engine import (
    Board,
    BoardColumn,
    BoardEngine,
    BoardGroup,
    BoardItem,
    BoardPermission,
    BoardPermissionLevel,
    BoardTemplate,
    BoardView,
    ColumnType,
    TemplateType,
    ViewType,
)

# -- Dashboard Generator ----------------------------------------------------
from .dashboard_generator import (
    DashboardGenerator,
    DashboardTemplate,
    DashboardTemplateType,
    DashboardWidget,
    ScheduledReport,
    ScheduleInterval,
    WidgetType,
)

# -- Document Manager -------------------------------------------------------
from .doc_manager import (
    DocManager,
    DocStatus,
    DocTemplate,
    DocType,
    DocVersion,
    WorkDoc,
)

# -- Form Builder -----------------------------------------------------------
from .form_builder import (
    FieldType,
    FormBuilder,
    FormField,
    FormStatus,
    FormSubmission,
    FormTemplate,
    FormTemplateType,
    SubmissionStatus,
)

# -- Integration Bridge -----------------------------------------------------
from .integration_bridge import (
    ConflictPolicy,
    IntegrationBridge,
    SyncDirection,
    SyncEvent,
    SyncEventType,
    SyncHistoryEntry,
    SyncRule,
    SyncStatus,
)

# -- Management Commands ----------------------------------------------------
from .management_commands import (
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

# -- Status Engine ----------------------------------------------------------
from .status_engine import (
    PriorityLevel,
    StatusColumn,
    StatusEngine,
    StatusHistoryEntry,
    StatusLabel,
    WorkflowStateMachine,
    WorkflowTransition,
)

# -- Timeline Engine --------------------------------------------------------
from .timeline_engine import (
    CriticalPath,
    Dependency,
    DependencyType,
    Milestone,
    TimelineEngine,
    TimelineItem,
)

# -- Workspace Manager ------------------------------------------------------
from .workspace_manager import (
    MURPHY_SUBSYSTEM_DOMAINS,
    WORKSPACE_DISPLAY_NAMES,
    Workspace,
    WorkspaceManager,
    WorkspaceMapping,
)

__all__ = [
    # Board Engine
    "Board",
    "BoardColumn",
    "BoardEngine",
    "BoardGroup",
    "BoardItem",
    "BoardPermission",
    "BoardPermissionLevel",
    "BoardTemplate",
    "BoardView",
    "ColumnType",
    "TemplateType",
    "ViewType",
    # Status Engine
    "PriorityLevel",
    "StatusColumn",
    "StatusEngine",
    "StatusHistoryEntry",
    "StatusLabel",
    "WorkflowStateMachine",
    "WorkflowTransition",
    # Timeline Engine
    "CriticalPath",
    "Dependency",
    "DependencyType",
    "Milestone",
    "TimelineEngine",
    "TimelineItem",
    # Automation Recipes
    "ActionType",
    "AutomationAction",
    "AutomationRecipe",
    "AutomationTrigger",
    "ExecutionLogEntry",
    "RecipeCondition",
    "RecipeEngine",
    "RecipeStatus",
    "TriggerType",
    # Workspace Manager
    "Workspace",
    "WorkspaceManager",
    "WorkspaceMapping",
    "MURPHY_SUBSYSTEM_DOMAINS",
    "WORKSPACE_DISPLAY_NAMES",
    # Dashboard Generator
    "DashboardGenerator",
    "DashboardTemplate",
    "DashboardTemplateType",
    "DashboardWidget",
    "ScheduledReport",
    "ScheduleInterval",
    "WidgetType",
    # Integration Bridge
    "ConflictPolicy",
    "IntegrationBridge",
    "SyncDirection",
    "SyncEvent",
    "SyncEventType",
    "SyncHistoryEntry",
    "SyncRule",
    "SyncStatus",
    # Form Builder
    "FieldType",
    "FormBuilder",
    "FormField",
    "FormStatus",
    "FormSubmission",
    "FormTemplate",
    "FormTemplateType",
    "SubmissionStatus",
    # Document Manager
    "DocManager",
    "DocStatus",
    "DocTemplate",
    "DocType",
    "DocVersion",
    "WorkDoc",
    # Management Commands
    "MANAGEMENT_COMMAND_HANDLERS",
    "handle_board",
    "handle_dashboard",
    "handle_doc",
    "handle_form",
    "handle_recipe",
    "handle_status",
    "handle_sync",
    "handle_timeline",
    "handle_workspace",
    "reset_engines",
]
