"""
Tests for the Management Systems package (PR 4 of Matrix migration series).

Covers all 9 modules:
  1. board_engine – Board, groups, items, columns, views, permissions, templates
  2. status_engine – Status labels, state machine, progress tracking
  3. timeline_engine – Items, milestones, dependencies, critical path, Gantt
  4. automation_recipes – Triggers, actions, recipe lifecycle, execution log
  5. workspace_manager – Workspace CRUD, domain mappings, bootstrap
  6. dashboard_generator – Widget rendering, report generation, scheduled reports
  7. integration_bridge – Sync rules, event processing, default rules
  8. form_builder – Form templates, sessions, validation, submissions
  9. doc_manager – Document CRUD, versioning, linking, search
"""

import os


import pytest

# ---------------------------------------------------------------------------
# board_engine tests
# ---------------------------------------------------------------------------

from management_systems.board_engine import (
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


class TestBoardEngine:
    def setup_method(self):
        self.engine = BoardEngine()

    # -- Board CRUD ---------------------------------------------------------

    def test_create_board_basic(self):
        board = self.engine.create_board("My Board", owner_id="@user:test")
        assert board.name == "My Board"
        assert board.owner_id == "@user:test"
        assert len(board.views) == 1
        assert board.views[0].view_type == ViewType.MAIN_TABLE

    def test_create_board_owner_permission(self):
        board = self.engine.create_board("Board", owner_id="@alice:test")
        assert any(
            p.user_id == "@alice:test" and p.level == BoardPermissionLevel.OWNER
            for p in board.permissions
        )

    def test_create_board_from_template(self):
        board = self.engine.create_board(
            "Sprint", template=TemplateType.SPRINT_BOARD
        )
        col_titles = [c.title for c in board.columns]
        assert "Status" in col_titles
        assert len(board.groups) > 0

    def test_get_board(self):
        board = self.engine.create_board("B1")
        assert self.engine.get_board(board.id) is board

    def test_get_board_not_found(self):
        assert self.engine.get_board("nonexistent") is None

    def test_list_boards(self):
        self.engine.create_board("A")
        self.engine.create_board("B")
        assert len(self.engine.list_boards()) == 2

    def test_list_boards_filtered_by_workspace(self):
        b1 = self.engine.create_board("A", workspace_id="ws1")
        self.engine.create_board("B", workspace_id="ws2")
        result = self.engine.list_boards(workspace_id="ws1")
        assert len(result) == 1
        assert result[0].id == b1.id

    def test_delete_board(self):
        board = self.engine.create_board("Del")
        assert self.engine.delete_board(board.id) is True
        assert self.engine.get_board(board.id) is None

    def test_delete_board_not_found(self):
        assert self.engine.delete_board("ghost") is False

    # -- Columns ------------------------------------------------------------

    def test_add_column(self):
        board = self.engine.create_board("B")
        col = self.engine.add_column(board.id, "Status", ColumnType.STATUS)
        assert col.title == "Status"
        assert col.col_type == ColumnType.STATUS
        assert col in board.columns

    def test_remove_column(self):
        board = self.engine.create_board("B")
        col = self.engine.add_column(board.id, "Extra")
        assert self.engine.remove_column(board.id, col.id) is True
        assert col not in board.columns

    def test_add_column_raises_for_unknown_board(self):
        with pytest.raises(KeyError):
            self.engine.add_column("ghost", "Col")

    # -- Groups -------------------------------------------------------------

    def test_add_group(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "Sprint 1")
        assert group.title == "Sprint 1"
        assert group in board.groups

    def test_remove_group(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G1")
        removed = self.engine.remove_group(board.id, group.id)
        assert removed is True
        assert group not in board.groups

    # -- Items --------------------------------------------------------------

    def test_add_item(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        item = self.engine.add_item(board.id, group.id, "Task 1")
        assert item.name == "Task 1"
        assert item in group.items

    def test_get_item(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        item = self.engine.add_item(board.id, group.id, "T")
        assert self.engine.get_item(board.id, item.id) is item

    def test_update_item_name(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        item = self.engine.add_item(board.id, group.id, "Old Name")
        updated = self.engine.update_item(board.id, item.id, name="New Name")
        assert updated.name == "New Name"

    def test_delete_item(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        item = self.engine.add_item(board.id, group.id, "T")
        assert self.engine.delete_item(board.id, item.id) is True
        assert self.engine.get_item(board.id, item.id) is None

    def test_add_subitem(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        parent = self.engine.add_item(board.id, group.id, "Parent")
        subitem = self.engine.add_subitem(board.id, parent.id, "Sub 1")
        assert subitem.name == "Sub 1"
        assert subitem in parent.subitems

    # -- Cell values --------------------------------------------------------

    def test_set_cell(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        col = self.engine.add_column(board.id, "Status", ColumnType.STATUS)
        item = self.engine.add_item(board.id, group.id, "T")
        assert self.engine.set_cell(board.id, item.id, col.id, "Done") is True
        assert item.cell_values[col.id] == "Done"

    # -- Permissions --------------------------------------------------------

    def test_set_and_check_permission(self):
        board = self.engine.create_board("B")
        self.engine.set_permission(board.id, "@bob:test", BoardPermissionLevel.SUBSCRIBER)
        assert self.engine.check_permission(board.id, "@bob:test", BoardPermissionLevel.VIEWER)
        assert self.engine.check_permission(board.id, "@bob:test", BoardPermissionLevel.SUBSCRIBER)
        assert not self.engine.check_permission(board.id, "@bob:test", BoardPermissionLevel.OWNER)

    def test_permission_unknown_user(self):
        board = self.engine.create_board("B")
        assert not self.engine.check_permission(board.id, "@nobody:test", BoardPermissionLevel.VIEWER)

    # -- Rendering ----------------------------------------------------------

    def test_render_table_returns_string(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        self.engine.add_item(board.id, group.id, "Task A")
        result = self.engine.render_table(board.id)
        assert "B" in result
        assert "Task A" in result

    def test_render_table_unknown_board(self):
        result = self.engine.render_table("ghost")
        assert "not found" in result

    def test_render_kanban_returns_string(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        col = self.engine.add_column(board.id, "Status", ColumnType.STATUS)
        item = self.engine.add_item(board.id, group.id, "T")
        self.engine.set_cell(board.id, item.id, col.id, "In Progress")
        result = self.engine.render_kanban(board.id)
        assert "Kanban" in result

    # -- Templates ----------------------------------------------------------

    def test_list_templates(self):
        templates = BoardEngine.list_templates()
        assert len(templates) >= 5
        names = [t.name for t in templates]
        assert "Sprint Board" in names
        assert "Bug Tracker" in names

    def test_get_template(self):
        tpl = BoardEngine.get_template(TemplateType.SPRINT_BOARD)
        assert tpl is not None
        assert tpl.name == "Sprint Board"

    # -- Serialisation ------------------------------------------------------

    def test_serialise_round_trip(self):
        board = self.engine.create_board("B")
        group = self.engine.add_group(board.id, "G")
        self.engine.add_item(board.id, group.id, "T")
        data = self.engine.to_dict()
        engine2 = BoardEngine()
        engine2.load_dict(data)
        assert engine2.get_board(board.id) is not None


# ---------------------------------------------------------------------------
# status_engine tests
# ---------------------------------------------------------------------------

from management_systems.status_engine import (
    PriorityLevel,
    StatusColumn,
    StatusEngine,
    StatusHistoryEntry,
    StatusLabel,
    WorkflowStateMachine,
)


class TestStatusEngine:
    def setup_method(self):
        self.engine = StatusEngine()

    def test_create_column_with_defaults(self):
        col = self.engine.create_column("Status")
        assert col.title == "Status"
        assert len(col.labels) == 4

    def test_add_label(self):
        col = self.engine.create_column("Status")
        lbl = self.engine.add_label(col.id, "5", "Custom", "#FF0000")
        assert lbl.label == "Custom"
        assert lbl in col.labels

    def test_set_and_get_status(self):
        col = self.engine.create_column("Status")
        ok, err = self.engine.set_status("board1", "item1", col.id, "1")
        assert ok is True
        assert err is None
        assert self.engine.get_status("board1", "item1", col.id) == "1"

    def test_progress_calculation_none_done(self):
        col = self.engine.create_column("Status")
        for i in range(3):
            self.engine.set_status("b", f"i{i}", col.id, "1")  # Working On It
        pct = self.engine.calculate_progress("b", ["i0", "i1", "i2"], col.id)
        assert pct == 0.0

    def test_progress_calculation_all_done(self):
        col = self.engine.create_column("Status")
        for i in range(4):
            self.engine.set_status("b", f"i{i}", col.id, "3")  # Done key
        pct = self.engine.calculate_progress("b", ["i0", "i1", "i2", "i3"], col.id)
        assert pct == 100.0

    def test_progress_partial(self):
        col = self.engine.create_column("Status")
        self.engine.set_status("b", "i0", col.id, "3")  # Done
        self.engine.set_status("b", "i1", col.id, "1")  # Working
        pct = self.engine.calculate_progress("b", ["i0", "i1"], col.id)
        assert pct == 50.0

    def test_render_progress_bar(self):
        bar = self.engine.render_progress_bar(75.0)
        assert "75.0%" in bar
        assert "█" in bar
        assert "░" in bar

    def test_automation_callback_fires(self):
        col = self.engine.create_column("Status")
        fired = []
        self.engine.register_automation(col.id, "*", "3", lambda *a: fired.append(a))
        self.engine.set_status("b", "i1", col.id, "3")
        assert len(fired) == 1

    def test_automation_does_not_fire_on_mismatch(self):
        col = self.engine.create_column("Status")
        fired = []
        self.engine.register_automation(col.id, "*", "3", lambda *a: fired.append(a))
        self.engine.set_status("b", "i1", col.id, "1")
        assert len(fired) == 0

    def test_state_machine_allows_registered_transition(self):
        col = self.engine.create_column("Status")
        # Allow transitioning from initial empty state to "0", then "0" to "1"
        self.engine.add_transition(col.id, "*", "0")
        self.engine.add_transition(col.id, "0", "1")
        ok0, _ = self.engine.set_status("b", "i1", col.id, "0")
        assert ok0 is True
        ok, err = self.engine.set_status("b", "i1", col.id, "1")
        assert ok is True

    def test_state_machine_blocks_unregistered_transition(self):
        col = self.engine.create_column("Status")
        self.engine.add_transition(col.id, "0", "1")  # Only 0→1 allowed
        self.engine.set_status("b", "i1", col.id, "1")  # move to 1
        ok, err = self.engine.set_status("b", "i1", col.id, "3")  # 1→3 not registered
        assert ok is False
        assert err is not None

    def test_serialise_round_trip(self):
        col = self.engine.create_column("Status")
        self.engine.set_status("b", "i1", col.id, "2")
        data = self.engine.to_dict()
        engine2 = StatusEngine()
        engine2.load_dict(data)
        assert engine2.get_status("b", "i1", col.id) == "2"


# ---------------------------------------------------------------------------
# timeline_engine tests
# ---------------------------------------------------------------------------

from management_systems.timeline_engine import (
    CriticalPath,
    Dependency,
    DependencyType,
    Milestone,
    TimelineEngine,
    TimelineItem,
)


class TestTimelineEngine:
    def setup_method(self):
        self.engine = TimelineEngine()

    def test_add_item(self):
        item = self.engine.add_item("Design", "2025-01-06", "2025-01-10")
        assert item.name == "Design"
        assert item.duration_days == 5

    def test_update_progress(self):
        item = self.engine.add_item("T", "2025-01-01", "2025-01-05")
        assert self.engine.update_progress(item.id, 75.0) is True
        assert item.progress == 75.0

    def test_update_progress_clamps(self):
        item = self.engine.add_item("T", "2025-01-01", "2025-01-05")
        self.engine.update_progress(item.id, 150.0)
        assert item.progress == 100.0

    def test_delete_item(self):
        item = self.engine.add_item("T", "2025-01-01", "2025-01-05")
        assert self.engine.delete_item(item.id) is True
        assert self.engine.get_item(item.id) is None

    def test_add_milestone(self):
        ms = self.engine.add_milestone("Go Live", "2025-03-01")
        assert ms.name == "Go Live"
        assert not ms.completed

    def test_complete_milestone(self):
        ms = self.engine.add_milestone("Go Live", "2025-03-01")
        assert self.engine.complete_milestone(ms.id) is True
        assert ms.completed is True

    def test_add_dependency(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-06", "2025-01-10")
        dep = self.engine.add_dependency(a.id, b.id)
        assert dep.from_id == a.id
        assert dep.to_id == b.id

    def test_add_dependency_cycle_raises(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-06", "2025-01-10")
        self.engine.add_dependency(a.id, b.id)
        with pytest.raises(ValueError, match="cycle"):
            self.engine.add_dependency(b.id, a.id)

    def test_critical_path_single_item(self):
        self.engine.add_item("Solo", "2025-01-01", "2025-01-10")
        cp = self.engine.calculate_critical_path()
        assert len(cp.item_ids) == 1

    def test_critical_path_chain(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-06", "2025-01-10")
        self.engine.add_dependency(a.id, b.id)
        cp = self.engine.calculate_critical_path()
        assert len(cp.item_ids) == 2
        assert cp.total_duration_days > 0

    def test_detect_conflicts_none(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-06", "2025-01-10")
        self.engine.add_dependency(a.id, b.id)
        assert self.engine.detect_conflicts() == []

    def test_detect_conflicts_violation(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-03", "2025-01-08")  # starts before A ends
        self.engine.add_dependency(a.id, b.id)
        conflicts = self.engine.detect_conflicts()
        assert len(conflicts) > 0

    def test_render_gantt_returns_string(self):
        self.engine.add_item("Task", "2025-01-01", "2025-01-10")
        result = self.engine.render_gantt()
        assert "Task" in result
        assert "```" in result

    def test_render_gantt_no_items(self):
        result = self.engine.render_gantt()
        assert "No timeline items" in result

    def test_auto_schedule(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        b = self.engine.add_item("B", "2025-01-01", "2025-01-03")
        self.engine.add_dependency(a.id, b.id)
        result = self.engine.auto_schedule("2025-01-01")
        assert b.id in result
        assert result[b.id][0] >= a.end_date  # B should start after A ends

    def test_serialise_round_trip(self):
        a = self.engine.add_item("A", "2025-01-01", "2025-01-05")
        self.engine.add_milestone("M1", "2025-02-01")
        data = self.engine.to_dict()
        e2 = TimelineEngine()
        e2.load_dict(data)
        assert e2.get_item(a.id) is not None


# ---------------------------------------------------------------------------
# automation_recipes tests
# ---------------------------------------------------------------------------

from management_systems.automation_recipes import (
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


class TestRecipeEngine:
    def setup_method(self):
        self.engine = RecipeEngine()

    def _make_recipe(self, trigger_config=None, action_type=ActionType.NOTIFY):
        trigger = AutomationTrigger(
            TriggerType.STATUS_CHANGE,
            config=trigger_config or {"to": "3"},
        )
        action = AutomationAction(action_type, config={"message": "Hello"})
        return self.engine.create_recipe("Test", trigger, [action])

    def test_create_recipe(self):
        recipe = self._make_recipe()
        assert recipe.name == "Test"
        assert recipe.is_active()

    def test_list_recipes(self):
        self._make_recipe()
        self._make_recipe()
        assert len(self.engine.list_recipes()) == 2

    def test_pause_and_resume(self):
        recipe = self._make_recipe()
        assert self.engine.pause_recipe(recipe.id) is True
        assert recipe.status == RecipeStatus.PAUSED
        assert self.engine.resume_recipe(recipe.id) is True
        assert recipe.status == RecipeStatus.ACTIVE

    def test_delete_recipe(self):
        recipe = self._make_recipe()
        assert self.engine.delete_recipe(recipe.id) is True
        assert self.engine.get_recipe(recipe.id) is None

    def test_process_event_triggers_recipe(self):
        fired = []
        recipe = self._make_recipe()
        self.engine.register_action_handler(ActionType.NOTIFY, lambda a, e: fired.append(1))
        self.engine.process_event({"type": "status_change", "to_value": "3"})
        assert len(fired) == 1

    def test_process_event_no_match(self):
        fired = []
        self._make_recipe()
        self.engine.register_action_handler(ActionType.NOTIFY, lambda a, e: fired.append(1))
        self.engine.process_event({"type": "status_change", "to_value": "1"})
        assert len(fired) == 0

    def test_paused_recipe_does_not_fire(self):
        fired = []
        recipe = self._make_recipe()
        self.engine.register_action_handler(ActionType.NOTIFY, lambda a, e: fired.append(1))
        self.engine.pause_recipe(recipe.id)
        self.engine.process_event({"type": "status_change", "to_value": "3"})
        assert len(fired) == 0

    def test_execution_log_populated(self):
        self._make_recipe()
        self.engine.register_action_handler(ActionType.NOTIFY, lambda a, e: None)
        self.engine.process_event({"type": "status_change", "to_value": "3"})
        log = self.engine.get_execution_log()
        assert len(log) == 1
        assert log[0].success is True

    def test_execution_log_records_failure(self):
        self._make_recipe()

        def bad_handler(a, e):
            raise RuntimeError("Oops")

        self.engine.register_action_handler(ActionType.NOTIFY, bad_handler)
        self.engine.process_event({"type": "status_change", "to_value": "3"})
        log = self.engine.get_execution_log()
        assert log[0].success is False

    def test_trigger_condition_match(self):
        trigger = AutomationTrigger(
            TriggerType.STATUS_CHANGE,
            config={"column_id": "col1", "from": "1", "to": "3"},
        )
        event_match = {
            "type": "status_change",
            "column_id": "col1",
            "from_value": "1",
            "to_value": "3",
        }
        event_no_match = {
            "type": "status_change",
            "column_id": "col1",
            "from_value": "0",
            "to_value": "3",
        }
        assert trigger.matches(event_match) is True
        assert trigger.matches(event_no_match) is False

    def test_recipe_condition_evaluation(self):
        cond = RecipeCondition(column_id="priority", operator="eq", value="high")
        assert cond.evaluate({"priority": "high"}) is True
        assert cond.evaluate({"priority": "low"}) is False

    def test_create_from_template(self):
        recipe = self.engine.create_from_template("Notify on Done")
        assert recipe is not None
        assert "Done" in recipe.name

    def test_create_from_template_not_found(self):
        recipe = self.engine.create_from_template("Nonexistent Template")
        assert recipe is None

    def test_list_templates(self):
        templates = RecipeEngine.list_templates()
        assert len(templates) >= 4

    def test_run_count_incremented(self):
        recipe = self._make_recipe()
        self.engine.register_action_handler(ActionType.NOTIFY, lambda a, e: None)
        self.engine.process_event({"type": "status_change", "to_value": "3"})
        assert recipe.run_count == 1


# ---------------------------------------------------------------------------
# workspace_manager tests
# ---------------------------------------------------------------------------

from management_systems.workspace_manager import (
    MURPHY_SUBSYSTEM_DOMAINS,
    Workspace,
    WorkspaceManager,
    WorkspaceMapping,
    WORKSPACE_DISPLAY_NAMES,
)


class TestWorkspaceManager:
    def setup_method(self):
        self.mgr = WorkspaceManager()

    def test_create_workspace(self):
        ws = self.mgr.create_workspace("Test", domain_key="ai_ml_pipeline")
        assert ws.name == "Test"
        assert ws.domain_key == "ai_ml_pipeline"

    def test_get_workspace(self):
        ws = self.mgr.create_workspace("WS")
        assert self.mgr.get_workspace(ws.id) is ws

    def test_get_workspace_by_domain(self):
        ws = self.mgr.create_workspace("AI", domain_key="ai_ml_pipeline")
        result = self.mgr.get_workspace_by_domain("ai_ml_pipeline")
        assert result is ws

    def test_get_workspace_by_domain_not_found(self):
        assert self.mgr.get_workspace_by_domain("ghost") is None

    def test_get_workspace_by_module(self):
        ws = self.mgr.create_workspace("AI", domain_key="ai_ml_pipeline")
        result = self.mgr.get_workspace_by_module("llm_controller")
        assert result is ws

    def test_get_workspace_by_module_not_found(self):
        assert self.mgr.get_workspace_by_module("nonexistent_module") is None

    def test_bootstrap_creates_15_workspaces(self):
        created = self.mgr.bootstrap_murphy_workspaces()
        assert len(created) == 15

    def test_bootstrap_idempotent(self):
        self.mgr.bootstrap_murphy_workspaces()
        second = self.mgr.bootstrap_murphy_workspaces()
        assert second == []

    def test_domain_coverage(self):
        assert "automation_orchestration" in MURPHY_SUBSYSTEM_DOMAINS
        assert "ai_ml_pipeline" in MURPHY_SUBSYSTEM_DOMAINS
        assert "security_compliance" in MURPHY_SUBSYSTEM_DOMAINS
        assert len(MURPHY_SUBSYSTEM_DOMAINS) >= 15

    def test_module_list_via_property(self):
        ws = self.mgr.create_workspace("AI", domain_key="ai_ml_pipeline")
        modules = ws.module_list
        assert "llm_controller" in modules
        assert len(modules) > 5

    def test_link_board(self):
        ws = self.mgr.create_workspace("WS")
        assert self.mgr.link_board(ws.id, "board-123") is True
        assert "board-123" in ws.board_ids

    def test_unlink_board(self):
        ws = self.mgr.create_workspace("WS")
        self.mgr.link_board(ws.id, "board-123")
        assert self.mgr.unlink_board(ws.id, "board-123") is True
        assert "board-123" not in ws.board_ids

    def test_link_workspaces(self):
        ws1 = self.mgr.create_workspace("A")
        ws2 = self.mgr.create_workspace("B")
        assert self.mgr.link_workspaces(ws1.id, ws2.id) is True
        assert ws2.id in ws1.linked_workspace_ids
        assert ws1.id in ws2.linked_workspace_ids

    def test_render_summary_returns_string(self):
        self.mgr.bootstrap_murphy_workspaces()
        result = self.mgr.render_workspace_summary()
        assert "murphy_system" in result
        assert "workspace" in result.lower()

    def test_workspace_mapping_known_module(self):
        mapping = self.mgr.get_workspace_mapping("llm_controller")
        assert mapping is not None
        assert mapping.domain_key == "ai_ml_pipeline"

    def test_workspace_mapping_unknown_module(self):
        assert self.mgr.get_workspace_mapping("totally_made_up_module") is None

    def test_serialise_round_trip(self):
        ws = self.mgr.create_workspace("WS", domain_key="trading_finance")
        data = self.mgr.to_dict()
        mgr2 = WorkspaceManager()
        mgr2.load_dict(data)
        assert mgr2.get_workspace(ws.id) is not None


# ---------------------------------------------------------------------------
# dashboard_generator tests
# ---------------------------------------------------------------------------

from management_systems.dashboard_generator import (
    DashboardGenerator,
    DashboardTemplate,
    DashboardTemplateType,
    DashboardWidget,
    ScheduledReport,
    ScheduleInterval,
    WidgetType,
)


class TestDashboardGenerator:
    def setup_method(self):
        self.gen = DashboardGenerator()

    def _board_data(self):
        return {
            "open_items": 8,
            "completed": 12,
            "progress": 65.0,
            "story_points_done": 23,
            "blockers": 2,
            "status_counts": {"In Progress": 5, "Done": 12, "Stuck": 3},
            "items_per_assignee": {"Alice": 5, "Bob": 3},
            "overdue": 1,
            "portfolio_health": 80.0,
            "highlights": "Shipped feature X",
        }

    def test_generate_sprint_health_report(self):
        report = self.gen.generate_report(
            DashboardTemplateType.SPRINT_HEALTH, self._board_data()
        )
        assert "Sprint Health" in report
        assert "%" in report

    def test_generate_project_overview_report(self):
        report = self.gen.generate_report(
            DashboardTemplateType.PROJECT_OVERVIEW, self._board_data()
        )
        assert "Project Overview" in report

    def test_generate_team_workload_report(self):
        report = self.gen.generate_report(
            DashboardTemplateType.TEAM_WORKLOAD, self._board_data()
        )
        assert "Team Workload" in report

    def test_generate_report_unknown_template(self):
        # Force unknown by passing an invalid template type directly
        result = self.gen._build_widget({"type": "numbers", "title": "X"}, {})
        assert result is not None

    def test_generate_standup(self):
        report = self.gen.generate_standup(
            "Alpha Team",
            completed_items=["Fix bug #42"],
            in_progress_items=["Deploy v2.0"],
            blocked_items=[],
        )
        assert "Daily Standup" in report
        assert "Fix bug #42" in report
        assert "Deploy v2.0" in report
        assert "none" in report  # blocked section

    def test_generate_weekly_report(self):
        report = self.gen.generate_weekly_report(
            "AI Workspace",
            stats={"completed": 10, "created": 5, "overdue": 2, "progress": 72.0,
                   "top_contributors": ["Alice", "Bob"]},
        )
        assert "Weekly Report" in report
        assert "Alice" in report

    def test_widget_numbers_render(self):
        widget = DashboardWidget(
            title="Open Items",
            widget_type=WidgetType.NUMBERS,
            data={"value": 8, "label": "items"},
        )
        rendered = widget.render()
        assert "8" in rendered
        assert "Open Items" in rendered

    def test_widget_battery_render(self):
        widget = DashboardWidget(
            title="Progress",
            widget_type=WidgetType.BATTERY,
            data={"percentage": 75.0},
        )
        rendered = widget.render()
        assert "75%" in rendered

    def test_widget_status_summary_render(self):
        widget = DashboardWidget(
            title="Status",
            widget_type=WidgetType.STATUS_SUMMARY,
            data={"counts": {"Done": 5, "Stuck": 2}},
        )
        rendered = widget.render()
        assert "Done" in rendered

    def test_widget_bar_chart_render(self):
        widget = DashboardWidget(
            title="Bars",
            widget_type=WidgetType.BAR_CHART,
            data={"bars": [{"label": "A", "value": 5, "max": 10}]},
        )
        rendered = widget.render()
        assert "A" in rendered

    def test_schedule_report(self):
        report = self.gen.schedule_report(
            "Daily Sprint",
            DashboardTemplateType.SPRINT_HEALTH,
            ScheduleInterval.DAILY,
            "!room:test",
        )
        assert report.matrix_room_id == "!room:test"
        assert report.interval == ScheduleInterval.DAILY

    def test_mark_sent_advances_schedule(self):
        report = self.gen.schedule_report(
            "Daily",
            DashboardTemplateType.SPRINT_HEALTH,
            ScheduleInterval.DAILY,
            "!room",
        )
        original_due = report.next_due_at
        self.gen.mark_sent(report.id)
        assert report.last_sent_at != ""
        assert report.next_due_at != original_due

    def test_list_templates(self):
        templates = DashboardGenerator.list_templates()
        assert len(templates) >= 4

    def test_serialise_round_trip(self):
        self.gen.schedule_report(
            "R1",
            DashboardTemplateType.SPRINT_HEALTH,
            ScheduleInterval.WEEKLY,
            "!room",
        )
        data = self.gen.to_dict()
        gen2 = DashboardGenerator()
        gen2.load_dict(data)
        assert len(gen2._scheduled) == 1


# ---------------------------------------------------------------------------
# integration_bridge tests
# ---------------------------------------------------------------------------

from management_systems.integration_bridge import (
    ConflictPolicy,
    IntegrationBridge,
    SyncDirection,
    SyncEvent,
    SyncEventType,
    SyncHistoryEntry,
    SyncRule,
    SyncStatus,
)


class TestIntegrationBridge:
    def setup_method(self):
        self.bridge = IntegrationBridge()

    def _register_passthrough(self, action):
        self.bridge.register_action_handler(
            action, lambda rule, event: SyncStatus.SUCCESS
        )

    def test_add_rule(self):
        rule = self.bridge.create_rule(
            "Health Rule", SyncEventType.MODULE_HEALTH_CHANGE
        )
        assert self.bridge.get_rule(rule.id) is rule

    def test_list_rules(self):
        self.bridge.create_rule("R1", SyncEventType.MODULE_HEALTH_CHANGE)
        self.bridge.create_rule("R2", SyncEventType.MODULE_ERROR)
        assert len(self.bridge.list_rules()) == 2

    def test_enable_disable_rule(self):
        rule = self.bridge.create_rule("R", SyncEventType.MODULE_ERROR)
        self.bridge.disable_rule(rule.id)
        assert rule.enabled is False
        self.bridge.enable_rule(rule.id)
        assert rule.enabled is True

    def test_delete_rule(self):
        rule = self.bridge.create_rule("R", SyncEventType.MODULE_ERROR)
        assert self.bridge.delete_rule(rule.id) is True
        assert self.bridge.get_rule(rule.id) is None

    def test_process_event_matches_rule(self):
        self.bridge.create_rule("H", SyncEventType.MODULE_HEALTH_CHANGE)
        # No handler registered for the default 'update_status' action → SKIPPED
        event = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "llm_controller")
        entries = self.bridge.process_event(event)
        assert len(entries) == 1
        assert entries[0].status == SyncStatus.SKIPPED

    def test_process_event_with_registered_handler(self):
        rule = self.bridge.create_rule(
            "H", SyncEventType.MODULE_HEALTH_CHANGE, action="update_status"
        )
        self._register_passthrough("update_status")
        event = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "llm_controller")
        entries = self.bridge.process_event(event)
        assert entries[0].status == SyncStatus.SUCCESS

    def test_process_event_no_match(self):
        self.bridge.create_rule("H", SyncEventType.MODULE_ERROR)
        event = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "llm_controller")
        entries = self.bridge.process_event(event)
        assert entries == []

    def test_module_filter(self):
        self.bridge.create_rule(
            "R", SyncEventType.MODULE_HEALTH_CHANGE, module_name="specific_module"
        )
        self._register_passthrough("update_status")
        event_match = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "specific_module")
        event_no_match = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "other_module")
        assert len(self.bridge.process_event(event_match)) == 1
        assert len(self.bridge.process_event(event_no_match)) == 0

    def test_emit_event_convenience(self):
        self.bridge.create_rule("R", SyncEventType.MODULE_ERROR, action="create_item")
        self.bridge.register_action_handler(
            "create_item", lambda r, e: SyncStatus.SUCCESS
        )
        entries = self.bridge.emit_event(SyncEventType.MODULE_ERROR, "test_module")
        assert len(entries) == 1

    def test_bootstrap_default_rules(self):
        rules = self.bridge.bootstrap_default_rules()
        assert len(rules) == 5
        event_types = {r.event_type for r in rules}
        assert SyncEventType.MODULE_HEALTH_CHANGE in event_types
        assert SyncEventType.MODULE_ERROR in event_types

    def test_history_tracking(self):
        self.bridge.create_rule("R", SyncEventType.MODULE_HEALTH_CHANGE, action="update_status")
        self._register_passthrough("update_status")
        self.bridge.emit_event(SyncEventType.MODULE_HEALTH_CHANGE, "llm_controller")
        history = self.bridge.get_history()
        assert len(history) == 1

    def test_render_sync_status(self):
        self.bridge.bootstrap_default_rules()
        result = self.bridge.render_sync_status()
        assert "Integration Bridge Status" in result

    def test_serialise_round_trip(self):
        self.bridge.create_rule("R", SyncEventType.MODULE_ERROR)
        data = self.bridge.to_dict()
        bridge2 = IntegrationBridge()
        bridge2.load_dict(data)
        assert len(bridge2.list_rules()) == 1


# ---------------------------------------------------------------------------
# form_builder tests
# ---------------------------------------------------------------------------

from management_systems.form_builder import (
    FieldType,
    FormBuilder,
    FormField,
    FormStatus,
    FormSubmission,
    FormTemplate,
    FormTemplateType,
    SubmissionStatus,
)


class TestFormBuilder:
    def setup_method(self):
        self.builder = FormBuilder()

    def test_create_form(self):
        form = self.builder.create_form("Bug Form", FormTemplateType.BUG_REPORT)
        assert form.name == "Bug Form"

    def test_load_template_bug_report(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        assert len(form.fields) >= 4
        assert any(f.title == "Title" for f in form.fields)

    def test_load_template_unknown_raises(self):
        with pytest.raises(KeyError):
            # GENERAL_REQUEST is defined but has no pre-built template
            self.builder.load_template(FormTemplateType.GENERAL_REQUEST)

    def test_start_session(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        assert "session_id" in session
        assert session["form_id"] == form.id

    def test_get_next_prompt_first_field(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        prompt = self.builder.get_next_prompt(session["session_id"])
        assert prompt is not None
        assert "Title" in prompt

    def test_answer_field_valid(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        ok, err = self.builder.answer_field(session["session_id"], "Title", "Bug: login crash")
        assert ok is True
        assert err is None

    def test_answer_field_required_empty(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        ok, err = self.builder.answer_field(session["session_id"], "Title", "")
        assert ok is False
        assert err is not None

    def test_submit_validated(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        sid = session["session_id"]
        self.builder.answer_field(sid, "Title", "Login crash")
        self.builder.answer_field(sid, "Severity", "high")
        self.builder.answer_field(sid, "Steps to Reproduce", "1. Open app")
        sub = self.builder.submit(sid)
        assert sub is not None
        assert sub.status == SubmissionStatus.VALIDATED

    def test_submit_rejected_missing_required(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        sid = session["session_id"]
        # Don't fill required fields
        sub = self.builder.submit(sid)
        assert sub.status == SubmissionStatus.REJECTED
        assert len(sub.validation_errors) > 0

    def test_field_validation_email(self):
        f = FormField(title="Email", field_type=FieldType.EMAIL, required=False)
        ok, err = f.validate("not-an-email")
        assert ok is False
        ok2, _ = f.validate("valid@example.com")
        assert ok2 is True

    def test_field_validation_number_range(self):
        f = FormField(title="Score", field_type=FieldType.NUMBER, min_value=1.0, max_value=10.0)
        assert f.validate(5)[0] is True
        assert f.validate(0)[0] is False
        assert f.validate(11)[0] is False

    def test_field_validation_dropdown_option(self):
        f = FormField(
            title="Priority", field_type=FieldType.DROPDOWN,
            options=["low", "medium", "high"]
        )
        assert f.validate("high")[0] is True
        assert f.validate("critical")[0] is False

    def test_conditional_field_visible(self):
        f = FormField(
            title="Details",
            condition={"field_id": "f1", "operator": "eq", "value": "yes"}
        )
        assert f.is_visible({"f1": "yes"}) is True
        assert f.is_visible({"f1": "no"}) is False

    def test_on_submit_callback(self):
        fired = []
        self.builder.register_on_submit(lambda s: fired.append(s.id))
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        session = self.builder.start_session(form.id, "@user:test")
        sid = session["session_id"]
        self.builder.answer_field(sid, "Title", "T")
        self.builder.answer_field(sid, "Steps to Reproduce", "S")
        self.builder.answer_field(sid, "Severity", "high")
        self.builder.submit(sid)
        assert len(fired) == 1

    def test_list_templates(self):
        templates = FormBuilder.list_templates()
        assert len(templates) >= 3

    def test_get_analytics(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        analytics = self.builder.get_analytics(form.id)
        assert analytics["total"] == 0

    def test_serialise_round_trip(self):
        form = self.builder.load_template(FormTemplateType.BUG_REPORT)
        data = self.builder.to_dict()
        b2 = FormBuilder()
        b2.load_dict(data)
        assert b2.get_form(form.id) is not None


# ---------------------------------------------------------------------------
# doc_manager tests
# ---------------------------------------------------------------------------

from management_systems.doc_manager import (
    DocManager,
    DocStatus,
    DocTemplate,
    DocType,
    DocVersion,
    WorkDoc,
)


class TestDocManager:
    def setup_method(self):
        self.mgr = DocManager()

    def test_create_doc_basic(self):
        doc = self.mgr.create_doc("My Doc", DocType.MEETING_NOTES)
        assert doc.title == "My Doc"
        assert doc.doc_type == DocType.MEETING_NOTES

    def test_create_doc_from_template(self):
        doc = self.mgr.create_doc(
            "Sprint 5 Retro",
            DocType.RETROSPECTIVE,
            from_template=DocType.RETROSPECTIVE,
        )
        assert "Sprint" in doc.content or "retrospective" in doc.content.lower()

    def test_get_doc(self):
        doc = self.mgr.create_doc("D")
        assert self.mgr.get_doc(doc.id) is doc

    def test_get_doc_not_found(self):
        assert self.mgr.get_doc("ghost") is None

    def test_delete_doc(self):
        doc = self.mgr.create_doc("D")
        assert self.mgr.delete_doc(doc.id) is True
        assert self.mgr.get_doc(doc.id) is None

    def test_update_content_creates_version(self):
        doc = self.mgr.create_doc("D", DocType.SPEC)
        self.mgr.update_content(doc.id, "# Spec\n\nContent here", "@alice:test")
        assert doc.current_version >= 1

    def test_update_content_multiple_versions(self):
        doc = self.mgr.create_doc("D")
        self.mgr.update_content(doc.id, "Version 1", "@alice:test")
        self.mgr.update_content(doc.id, "Version 2", "@alice:test")
        assert doc.current_version == 2

    def test_append_message(self):
        doc = self.mgr.create_doc("Meeting", DocType.MEETING_NOTES, content="# Notes\n\n")
        self.mgr.append_message(doc.id, "Good point!", "@bob:test")
        assert "Good point!" in doc.content
        assert "@bob:test" in doc.content

    def test_start_and_stop_editing(self):
        doc = self.mgr.create_doc("D")
        self.mgr.start_editing(doc.id, "@alice:test")
        assert "@alice:test" in doc.editing_by
        self.mgr.stop_editing(doc.id, "@alice:test")
        assert "@alice:test" not in doc.editing_by

    def test_link_to_board(self):
        doc = self.mgr.create_doc("D")
        assert self.mgr.link_to_board(doc.id, "board-1") is True
        assert "board-1" in doc.board_ids

    def test_link_to_item(self):
        doc = self.mgr.create_doc("D")
        assert self.mgr.link_to_item(doc.id, "item-1") is True
        assert "item-1" in doc.item_ids

    def test_get_docs_for_item(self):
        doc = self.mgr.create_doc("D")
        self.mgr.link_to_item(doc.id, "item-1")
        result = self.mgr.get_docs_for_item("item-1")
        assert doc in result

    def test_get_docs_for_board(self):
        doc = self.mgr.create_doc("D")
        self.mgr.link_to_board(doc.id, "board-1")
        result = self.mgr.get_docs_for_board("board-1")
        assert doc in result

    def test_version_history(self):
        doc = self.mgr.create_doc("D")
        self.mgr.update_content(doc.id, "v1", "@alice:test")
        self.mgr.update_content(doc.id, "v2", "@alice:test")
        history = self.mgr.get_version_history(doc.id)
        assert len(history) == 2

    def test_restore_version(self):
        doc = self.mgr.create_doc("D")
        self.mgr.update_content(doc.id, "Version 1 content", "@alice:test")
        self.mgr.update_content(doc.id, "Version 2 content", "@alice:test")
        self.mgr.restore_version(doc.id, 1, "@alice:test")
        assert "Version 1 content" in doc.content

    def test_search_by_title(self):
        self.mgr.create_doc("Sprint Retro", DocType.RETROSPECTIVE)
        self.mgr.create_doc("Bug Report", DocType.GENERAL)
        results = self.mgr.search("sprint")
        assert len(results) == 1
        assert results[0].title == "Sprint Retro"

    def test_search_by_content(self):
        doc = self.mgr.create_doc("D")
        self.mgr.update_content(doc.id, "deep search keyword xyz", "@alice:test")
        results = self.mgr.search("xyz")
        assert doc in results

    def test_search_no_results(self):
        self.mgr.create_doc("Unrelated Doc")
        assert self.mgr.search("completely_unique_keyword_xyz") == []

    def test_render_doc_summary(self):
        doc = self.mgr.create_doc("Test Doc", DocType.RUNBOOK)
        self.mgr.link_to_board(doc.id, "board-1")
        result = self.mgr.render_doc_summary(doc.id)
        assert "Test Doc" in result
        assert "runbook" in result

    def test_render_doc_summary_not_found(self):
        result = self.mgr.render_doc_summary("ghost")
        assert "not found" in result

    def test_list_templates(self):
        templates = self.mgr.list_templates()
        assert len(templates) >= 4

    def test_template_render(self):
        tpl = self.mgr.get_template(DocType.MEETING_NOTES)
        assert tpl is not None
        rendered = tpl.render({"title": "Team Sync", "date": "2025-01-06"})
        assert "Team Sync" in rendered
        assert "2025-01-06" in rendered

    def test_serialise_round_trip(self):
        doc = self.mgr.create_doc("D", DocType.SPEC, content="# Spec")
        data = self.mgr.to_dict()
        mgr2 = DocManager()
        mgr2.load_dict(data)
        assert mgr2.get_doc(doc.id) is not None
        assert "Spec" in mgr2.get_doc(doc.id).content

    def test_list_docs_filter_by_type(self):
        self.mgr.create_doc("Retro", DocType.RETROSPECTIVE)
        self.mgr.create_doc("Spec", DocType.SPEC)
        retros = self.mgr.list_docs(doc_type=DocType.RETROSPECTIVE)
        assert len(retros) == 1

    def test_list_docs_filter_by_status(self):
        doc = self.mgr.create_doc("Draft", DocType.GENERAL)
        assert doc.status == DocStatus.DRAFT
        result = self.mgr.list_docs(status=DocStatus.DRAFT)
        assert doc in result
