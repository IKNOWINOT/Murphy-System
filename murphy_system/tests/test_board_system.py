"""
Tests for the Board System (Phase 1 of management systems parity).

Covers all architectural layers:
  1. Models & serialization
  2. Column type validation
  3. Permission management
  4. View rendering (Table, Kanban, Calendar, Timeline, Chart)
  5. Board manager CRUD (boards, groups, items, columns, cells, views)
  6. Activity log
  7. API router (requires FastAPI)
"""

import os


import pytest

from board_system.models import (
    ActivityAction,
    ActivityLogEntry,
    Board,
    BoardKind,
    BoardPermission,
    CellValue,
    ColumnDefinition,
    ColumnType,
    Group,
    Item,
    Permission,
    ViewConfig,
    ViewType,
)
from board_system.column_types import (
    COLUMN_VALIDATORS,
    default_value,
    validate_cell_value,
)
from board_system.permissions import PermissionManager
from board_system.views import (
    apply_filters,
    apply_sort,
    render_chart_view,
    render_calendar_view,
    render_kanban_view,
    render_table_view,
    render_timeline_view,
    render_view,
)
from board_system.board_manager import BoardManager


# ===================================================================
# 1. Models & serialization
# ===================================================================

class TestModels:
    def test_board_to_dict(self):
        board = Board(name="Test Board", kind=BoardKind.PRIVATE, owner_id="u1")
        d = board.to_dict()
        assert d["name"] == "Test Board"
        assert d["kind"] == "private"
        assert d["owner_id"] == "u1"
        assert isinstance(d["columns"], list)
        assert isinstance(d["groups"], list)

    def test_column_definition_to_dict(self):
        col = ColumnDefinition(title="Status", column_type=ColumnType.STATUS)
        d = col.to_dict()
        assert d["title"] == "Status"
        assert d["column_type"] == "status"

    def test_item_set_and_get_cell(self):
        item = Item(name="Task 1")
        item.set_cell("col1", "hello", "hello")
        cell = item.get_cell("col1")
        assert cell is not None
        assert cell.value == "hello"
        assert cell.display_value == "hello"

    def test_item_get_cell_missing(self):
        item = Item(name="Task")
        assert item.get_cell("nonexistent") is None

    def test_group_add_and_remove_item(self):
        grp = Group(title="Sprint 1", board_id="b1")
        item = Item(name="Task A")
        grp.add_item(item)
        assert len(grp.items) == 1
        assert grp.items[0].group_id == grp.id
        assert grp.items[0].board_id == "b1"

        removed = grp.remove_item(item.id)
        assert removed is not None
        assert len(grp.items) == 0

    def test_group_remove_missing_item(self):
        grp = Group(title="G")
        assert grp.remove_item("nope") is None

    def test_board_add_column(self):
        board = Board(name="B")
        col = ColumnDefinition(title="Name", column_type=ColumnType.TEXT)
        board.add_column(col)
        assert len(board.columns) == 1
        assert board.get_column(col.id) is col

    def test_board_remove_column(self):
        board = Board(name="B")
        col = ColumnDefinition(title="X")
        board.add_column(col)
        removed = board.remove_column(col.id)
        assert removed is col
        assert len(board.columns) == 0

    def test_board_remove_column_missing(self):
        board = Board(name="B")
        assert board.remove_column("nope") is None

    def test_board_add_group(self):
        board = Board(name="B")
        grp = Group(title="G1")
        board.add_group(grp)
        assert len(board.groups) == 1
        assert grp.board_id == board.id

    def test_board_get_group(self):
        board = Board(name="B")
        grp = Group(title="G1")
        board.add_group(grp)
        assert board.get_group(grp.id) is grp
        assert board.get_group("missing") is None

    def test_board_remove_group(self):
        board = Board(name="B")
        grp = Group(title="G1")
        board.add_group(grp)
        removed = board.remove_group(grp.id)
        assert removed is grp
        assert board.remove_group("missing") is None

    def test_board_all_items(self):
        board = Board(name="B")
        g1 = Group(title="G1")
        g2 = Group(title="G2")
        board.add_group(g1)
        board.add_group(g2)
        g1.add_item(Item(name="A"))
        g2.add_item(Item(name="B"))
        g2.add_item(Item(name="C"))
        assert len(board.all_items()) == 3

    def test_board_add_and_get_view(self):
        board = Board(name="B")
        view = ViewConfig(name="Kanban", view_type=ViewType.KANBAN)
        board.add_view(view)
        assert board.get_view(view.id) is view
        assert board.get_view("nope") is None

    def test_cell_value_to_dict(self):
        cv = CellValue(column_id="c1", value=42, display_value="42")
        d = cv.to_dict()
        assert d["column_id"] == "c1"
        assert d["value"] == 42

    def test_board_permission_to_dict(self):
        bp = BoardPermission(user_id="u1", permission=Permission.EDIT)
        d = bp.to_dict()
        assert d["permission"] == "edit"

    def test_activity_log_entry_to_dict(self):
        entry = ActivityLogEntry(
            board_id="b1",
            action=ActivityAction.ITEM_CREATED,
            entity_type="item",
            entity_id="i1",
            user_id="u1",
        )
        d = entry.to_dict()
        assert d["action"] == "item_created"

    def test_view_config_to_dict(self):
        vc = ViewConfig(name="Table", view_type=ViewType.TABLE)
        d = vc.to_dict()
        assert d["view_type"] == "table"

    def test_item_to_dict_with_subitems(self):
        parent = Item(name="Parent")
        child = Item(name="Child")
        parent.subitems.append(child)
        d = parent.to_dict()
        assert len(d["subitems"]) == 1
        assert d["subitems"][0]["name"] == "Child"


# ===================================================================
# 2. Column type validation
# ===================================================================

class TestColumnTypes:
    def test_validate_text(self):
        val, disp = validate_cell_value(ColumnType.TEXT, "hello")
        assert val == "hello"

    def test_validate_text_max_length(self):
        with pytest.raises(ValueError, match="max length"):
            validate_cell_value(ColumnType.TEXT, "x" * 200, {"max_length": 100})

    def test_validate_number(self):
        val, disp = validate_cell_value(ColumnType.NUMBER, 42)
        assert val == 42.0
        assert "42" in disp

    def test_validate_number_invalid(self):
        with pytest.raises(ValueError, match="Invalid number"):
            validate_cell_value(ColumnType.NUMBER, "abc")

    def test_validate_status(self):
        val, disp = validate_cell_value(ColumnType.STATUS, "Done",
                                        {"labels": {"0": "To Do", "1": "Done"}})
        assert val == "Done"

    def test_validate_status_invalid(self):
        with pytest.raises(ValueError, match="Invalid status"):
            validate_cell_value(ColumnType.STATUS, "Unknown",
                                {"labels": {"0": "To Do", "1": "Done"}})

    def test_validate_date_iso(self):
        val, disp = validate_cell_value(ColumnType.DATE, "2025-01-15")
        assert val == "2025-01-15"

    def test_validate_date_invalid(self):
        with pytest.raises(ValueError):
            validate_cell_value(ColumnType.DATE, "not-a-date")

    def test_validate_date_object(self):
        from datetime import date
        val, disp = validate_cell_value(ColumnType.DATE, date(2025, 6, 1))
        assert val == "2025-06-01"

    def test_validate_person_string(self):
        val, disp = validate_cell_value(ColumnType.PERSON, "user1")
        assert val == "user1"

    def test_validate_person_dict(self):
        val, disp = validate_cell_value(ColumnType.PERSON, {"id": "u1", "name": "Alice"})
        assert disp == "Alice"

    def test_validate_person_list(self):
        val, disp = validate_cell_value(ColumnType.PERSON, ["u1", "u2"])
        assert val == ["u1", "u2"]

    def test_validate_dropdown(self):
        val, disp = validate_cell_value(ColumnType.DROPDOWN, "Option A",
                                        {"options": ["Option A", "Option B"]})
        assert val == "Option A"

    def test_validate_dropdown_invalid(self):
        with pytest.raises(ValueError, match="Invalid option"):
            validate_cell_value(ColumnType.DROPDOWN, "Nope",
                                {"options": ["A", "B"]})

    def test_validate_checkbox(self):
        val, disp = validate_cell_value(ColumnType.CHECKBOX, True)
        assert val is True
        assert disp == "✓"

    def test_validate_checkbox_false(self):
        val, disp = validate_cell_value(ColumnType.CHECKBOX, False)
        assert val is False
        assert disp == ""

    def test_validate_link_string(self):
        val, disp = validate_cell_value(ColumnType.LINK, "https://example.com")
        assert val["url"] == "https://example.com"

    def test_validate_link_dict(self):
        val, disp = validate_cell_value(ColumnType.LINK,
                                        {"url": "https://x.com", "text": "X"})
        assert disp == "X"

    def test_validate_email_valid(self):
        val, disp = validate_cell_value(ColumnType.EMAIL, "a@b.com")
        assert val == "a@b.com"

    def test_validate_email_invalid(self):
        with pytest.raises(ValueError, match="Invalid email"):
            validate_cell_value(ColumnType.EMAIL, "notanemail")

    def test_validate_phone(self):
        val, disp = validate_cell_value(ColumnType.PHONE, "+1-555-1234")
        assert val == "+1-555-1234"

    def test_validate_rating(self):
        val, disp = validate_cell_value(ColumnType.RATING, 3)
        assert val == 3
        assert disp == "★★★"

    def test_validate_rating_out_of_range(self):
        with pytest.raises(ValueError, match="Rating must be"):
            validate_cell_value(ColumnType.RATING, 10, {"max": 5})

    def test_validate_color(self):
        val, disp = validate_cell_value(ColumnType.COLOR, "#ff0000")
        assert val == "#ff0000"

    def test_validate_color_invalid(self):
        with pytest.raises(ValueError, match="Invalid hex color"):
            validate_cell_value(ColumnType.COLOR, "red")

    def test_validate_tag_list(self):
        val, disp = validate_cell_value(ColumnType.TAG, ["bug", "urgent"])
        assert val == ["bug", "urgent"]

    def test_validate_tag_string(self):
        val, disp = validate_cell_value(ColumnType.TAG, "bug, urgent")
        assert val == ["bug", "urgent"]

    def test_validate_timeline(self):
        val, disp = validate_cell_value(ColumnType.TIMELINE,
                                        {"start": "2025-01-01", "end": "2025-01-31"})
        assert "→" in disp

    def test_validate_timeline_invalid(self):
        with pytest.raises(ValueError, match="Timeline requires"):
            validate_cell_value(ColumnType.TIMELINE, "not-dict")

    def test_validate_long_text(self):
        val, disp = validate_cell_value(ColumnType.LONG_TEXT, "A" * 200)
        assert len(val) == 200
        assert disp.endswith("…")

    def test_validate_dependency(self):
        val, disp = validate_cell_value(ColumnType.DEPENDENCY, ["item1", "item2"])
        assert val == ["item1", "item2"]

    def test_validate_file_dict(self):
        val, disp = validate_cell_value(ColumnType.FILE, {"name": "doc.pdf"})
        assert disp == "doc.pdf"

    def test_validate_auto_number(self):
        val, disp = validate_cell_value(ColumnType.AUTO_NUMBER, 42)
        assert val == 42

    def test_validate_auto_number_with_prefix(self):
        val, disp = validate_cell_value(ColumnType.AUTO_NUMBER, 7, {"prefix": "TASK-"})
        assert disp == "TASK-7"

    def test_default_value_text(self):
        assert default_value(ColumnType.TEXT) == ""

    def test_default_value_number(self):
        assert default_value(ColumnType.NUMBER) == 0

    def test_default_value_checkbox(self):
        assert default_value(ColumnType.CHECKBOX) is False

    def test_all_column_types_have_validators(self):
        for ct in ColumnType:
            assert ct in COLUMN_VALIDATORS, f"Missing validator for {ct}"


# ===================================================================
# 3. Permission management
# ===================================================================

class TestPermissions:
    def test_owner_has_admin(self):
        board = Board(name="B", owner_id="owner1")
        assert PermissionManager.has_permission(board, "owner1", Permission.ADMIN)

    def test_no_permission_by_default(self):
        board = Board(name="B", owner_id="owner1")
        assert not PermissionManager.has_permission(board, "user2", Permission.VIEW)

    def test_grant_view(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, user_id="u2", permission=Permission.VIEW)
        assert PermissionManager.has_permission(board, "u2", Permission.VIEW)
        assert not PermissionManager.has_permission(board, "u2", Permission.EDIT)

    def test_grant_edit_includes_view(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, user_id="u2", permission=Permission.EDIT)
        assert PermissionManager.has_permission(board, "u2", Permission.VIEW)
        assert PermissionManager.has_permission(board, "u2", Permission.EDIT)

    def test_grant_replaces_previous(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, user_id="u2", permission=Permission.VIEW)
        PermissionManager.grant(board, user_id="u2", permission=Permission.ADMIN)
        assert PermissionManager.has_permission(board, "u2", Permission.ADMIN)

    def test_team_permission(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, team_id="team1", permission=Permission.EDIT)
        assert PermissionManager.has_permission(board, "u3", Permission.EDIT,
                                                user_teams=["team1"])

    def test_revoke(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, user_id="u2", permission=Permission.EDIT)
        assert PermissionManager.revoke(board, user_id="u2")
        assert not PermissionManager.has_permission(board, "u2", Permission.VIEW)

    def test_revoke_nonexistent(self):
        board = Board(name="B", owner_id="owner1")
        assert not PermissionManager.revoke(board, user_id="u999")

    def test_effective_permission_owner(self):
        board = Board(name="B", owner_id="owner1")
        assert PermissionManager.effective_permission(board, "owner1") == Permission.ADMIN

    def test_effective_permission_none(self):
        board = Board(name="B", owner_id="owner1")
        assert PermissionManager.effective_permission(board, "u999") is None

    def test_effective_permission_highest_wins(self):
        board = Board(name="B", owner_id="owner1")
        PermissionManager.grant(board, user_id="u2", permission=Permission.VIEW)
        PermissionManager.grant(board, team_id="t1", permission=Permission.EDIT)
        eff = PermissionManager.effective_permission(board, "u2", user_teams=["t1"])
        assert eff == Permission.EDIT


# ===================================================================
# 4. View rendering
# ===================================================================

class TestViews:
    @staticmethod
    def _make_board_with_items():
        """Helper to create a board with status column, 2 groups, and 3 items."""
        board = Board(name="Project", owner_id="u1")
        col_status = ColumnDefinition(title="Status", column_type=ColumnType.STATUS)
        col_date = ColumnDefinition(title="Due", column_type=ColumnType.DATE)
        col_timeline = ColumnDefinition(title="Timeline", column_type=ColumnType.TIMELINE)
        board.add_column(col_status)
        board.add_column(col_date)
        board.add_column(col_timeline)

        g1 = Group(title="To Do")
        g2 = Group(title="Done")
        board.add_group(g1)
        board.add_group(g2)

        i1 = Item(name="Task A")
        i1.set_cell(col_status.id, "Working", "Working")
        i1.set_cell(col_date.id, "2025-06-01", "2025-06-01")
        i1.set_cell(col_timeline.id, {"start": "2025-06-01", "end": "2025-06-15"},
                    "2025-06-01 → 2025-06-15")
        g1.add_item(i1)

        i2 = Item(name="Task B")
        i2.set_cell(col_status.id, "Done", "Done")
        i2.set_cell(col_date.id, "2025-05-20", "2025-05-20")
        g2.add_item(i2)

        i3 = Item(name="Task C")
        i3.set_cell(col_status.id, "Working", "Working")
        g1.add_item(i3)

        return board, col_status, col_date, col_timeline

    def test_render_table_view(self):
        board, *_ = self._make_board_with_items()
        view = ViewConfig(name="Table", view_type=ViewType.TABLE, board_id=board.id)
        data = render_table_view(board, view)
        assert data["view_type"] == "table"
        assert data["total_items"] == 3

    def test_render_table_view_with_filter(self):
        board, col_status, *_ = self._make_board_with_items()
        view = ViewConfig(
            name="Filtered",
            view_type=ViewType.TABLE,
            board_id=board.id,
            filters=[{"column_id": col_status.id, "operator": "eq", "value": "Done"}],
        )
        data = render_table_view(board, view)
        assert data["total_items"] == 1

    def test_render_kanban_view(self):
        board, col_status, *_ = self._make_board_with_items()
        view = ViewConfig(
            name="Kanban",
            view_type=ViewType.KANBAN,
            board_id=board.id,
            settings={"kanban_column_id": col_status.id},
        )
        data = render_kanban_view(board, view)
        assert data["view_type"] == "kanban"
        assert "Working" in data["lanes"]
        assert "Done" in data["lanes"]
        assert len(data["lanes"]["Working"]) == 2

    def test_render_calendar_view(self):
        board, _, col_date, _ = self._make_board_with_items()
        view = ViewConfig(
            name="Calendar",
            view_type=ViewType.CALENDAR,
            board_id=board.id,
            settings={"calendar_date_column_id": col_date.id},
        )
        data = render_calendar_view(board, view)
        assert data["view_type"] == "calendar"
        assert data["total_items"] == 2  # only 2 items have dates

    def test_render_timeline_view(self):
        board, _, _, col_timeline = self._make_board_with_items()
        view = ViewConfig(
            name="Timeline",
            view_type=ViewType.TIMELINE,
            board_id=board.id,
            settings={"timeline_column_id": col_timeline.id},
        )
        data = render_timeline_view(board, view)
        assert data["view_type"] == "timeline"
        assert data["total_items"] == 1  # only 1 item has timeline

    def test_render_chart_view(self):
        board, col_status, *_ = self._make_board_with_items()
        view = ViewConfig(
            name="Chart",
            view_type=ViewType.CHART,
            board_id=board.id,
            settings={"chart_column_id": col_status.id},
        )
        data = render_chart_view(board, view)
        assert data["view_type"] == "chart"
        assert data["data"]["Working"] == 2
        assert data["data"]["Done"] == 1

    def test_render_view_dispatcher(self):
        board, *_ = self._make_board_with_items()
        view = ViewConfig(name="T", view_type=ViewType.TABLE, board_id=board.id)
        data = render_view(board, view)
        assert data["view_type"] == "table"

    def test_render_view_unsupported(self):
        board, *_ = self._make_board_with_items()
        view = ViewConfig(name="Map", view_type=ViewType.MAP, board_id=board.id)
        data = render_view(board, view)
        assert "error" in data

    def test_apply_filters_empty(self):
        items = [Item(name="A"), Item(name="B")]
        assert apply_filters(items, []) == items

    def test_apply_sort_empty(self):
        items = [Item(name="A")]
        assert apply_sort(items, []) == items

    def test_apply_filters_contains(self):
        i1 = Item(name="Alpha")
        i1.set_cell("c1", "hello world", "hello world")
        i2 = Item(name="Beta")
        i2.set_cell("c1", "goodbye", "goodbye")
        result = apply_filters([i1, i2],
                               [{"column_id": "c1", "operator": "contains", "value": "hello"}])
        assert len(result) == 1
        assert result[0].name == "Alpha"

    def test_apply_filters_is_empty(self):
        i1 = Item(name="A")
        i1.set_cell("c1", "", "")
        i2 = Item(name="B")
        i2.set_cell("c1", "val", "val")
        result = apply_filters([i1, i2],
                               [{"column_id": "c1", "operator": "is_empty"}])
        assert len(result) == 1

    def test_hidden_columns_in_table_view(self):
        board, col_status, col_date, col_timeline = self._make_board_with_items()
        view = ViewConfig(
            name="Minimal",
            view_type=ViewType.TABLE,
            board_id=board.id,
            hidden_columns=[col_date.id, col_timeline.id],
        )
        data = render_table_view(board, view)
        col_ids = [c["id"] for c in data["columns"]]
        assert col_status.id in col_ids
        assert col_date.id not in col_ids


# ===================================================================
# 5. Board manager CRUD
# ===================================================================

class TestBoardManager:
    def test_create_board(self):
        mgr = BoardManager()
        board = mgr.create_board("Sprint 1", owner_id="u1")
        assert board.name == "Sprint 1"
        assert board.owner_id == "u1"
        assert len(board.groups) == 1  # default group
        assert len(board.views) == 1   # default table view

    def test_get_board(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        assert mgr.get_board(board.id) is board
        assert mgr.get_board("missing") is None

    def test_list_boards(self):
        mgr = BoardManager()
        mgr.create_board("A", owner_id="u1", workspace_id="w1")
        mgr.create_board("B", owner_id="u1", workspace_id="w2")
        assert len(mgr.list_boards()) == 2
        assert len(mgr.list_boards(workspace_id="w1")) == 1

    def test_update_board(self):
        mgr = BoardManager()
        board = mgr.create_board("Old", owner_id="u1")
        updated = mgr.update_board(board.id, user_id="u1", name="New")
        assert updated.name == "New"

    def test_update_board_not_found(self):
        mgr = BoardManager()
        with pytest.raises(KeyError):
            mgr.update_board("missing", user_id="u1", name="X")

    def test_update_board_permission_denied(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        with pytest.raises(PermissionError):
            mgr.update_board(board.id, user_id="u_other", name="Hacked")

    def test_delete_board(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        assert mgr.delete_board(board.id, user_id="u1")
        assert mgr.get_board(board.id) is None

    def test_delete_board_not_found(self):
        mgr = BoardManager()
        assert not mgr.delete_board("missing", user_id="u1")

    def test_delete_board_permission_denied(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        with pytest.raises(PermissionError):
            mgr.delete_board(board.id, user_id="u_other")

    def test_create_group(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        group = mgr.create_group(board.id, "Sprint 2", user_id="u1")
        assert group.title == "Sprint 2"
        assert len(board.groups) == 2

    def test_update_group(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        updated = mgr.update_group(board.id, gid, user_id="u1", title="Renamed")
        assert updated.title == "Renamed"

    def test_delete_group(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        assert mgr.delete_group(board.id, gid, user_id="u1")
        assert len(board.groups) == 0

    def test_create_item(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "Task 1", user_id="u1")
        assert item.name == "Task 1"
        assert len(board.groups[0].items) == 1

    def test_create_item_with_cell_values(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "Priority", ColumnType.NUMBER, user_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "Task", user_id="u1",
                               cell_values={col.id: 5})
        cell = item.get_cell(col.id)
        assert cell is not None
        assert cell.value == 5.0

    def test_update_item(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "Old", user_id="u1")
        updated = mgr.update_item(board.id, item.id, user_id="u1", name="New")
        assert updated.name == "New"

    def test_update_item_not_found(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        with pytest.raises(KeyError):
            mgr.update_item(board.id, "missing", user_id="u1", name="X")

    def test_delete_item(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "T", user_id="u1")
        assert mgr.delete_item(board.id, item.id, user_id="u1")
        assert len(board.groups[0].items) == 0

    def test_delete_item_not_found(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        assert not mgr.delete_item(board.id, "missing", user_id="u1")

    def test_move_item(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        g2 = mgr.create_group(board.id, "G2", user_id="u1")
        g1_id = board.groups[0].id
        item = mgr.create_item(board.id, g1_id, "Task", user_id="u1")
        moved = mgr.move_item(board.id, item.id, g2.id, user_id="u1")
        assert moved.group_id == g2.id
        assert len(board.groups[0].items) == 0
        assert len(board.groups[1].items) == 1

    def test_move_item_not_found(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        g2 = mgr.create_group(board.id, "G2", user_id="u1")
        with pytest.raises(KeyError, match="Item not found"):
            mgr.move_item(board.id, "missing", g2.id, user_id="u1")

    def test_move_item_target_group_not_found(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "T", user_id="u1")
        with pytest.raises(KeyError, match="Target group"):
            mgr.move_item(board.id, item.id, "missing", user_id="u1")

    def test_create_column(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "Status", ColumnType.STATUS, user_id="u1")
        assert col.title == "Status"
        assert col.column_type == ColumnType.STATUS

    def test_update_column(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "X", user_id="u1")
        updated = mgr.update_column(board.id, col.id, user_id="u1", title="Y")
        assert updated.title == "Y"

    def test_delete_column(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "X", user_id="u1")
        assert mgr.delete_column(board.id, col.id, user_id="u1")
        assert len(board.columns) == 0

    def test_update_cell(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "Score", ColumnType.NUMBER, user_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "T", user_id="u1")
        updated = mgr.update_cell(board.id, item.id, col.id, 99, user_id="u1")
        cell = updated.get_cell(col.id)
        assert cell.value == 99.0

    def test_update_cell_validation_error(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        col = mgr.create_column(board.id, "Color", ColumnType.COLOR, user_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "T", user_id="u1")
        with pytest.raises(ValueError, match="Invalid hex color"):
            mgr.update_cell(board.id, item.id, col.id, "not-a-color", user_id="u1")

    def test_create_view(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        view = mgr.create_view(board.id, "Kanban", ViewType.KANBAN, user_id="u1")
        assert view.name == "Kanban"
        assert len(board.views) == 2  # default + new

    def test_render_board_view(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        vid = board.views[0].id
        data = mgr.render_board_view(board.id, vid)
        assert data["view_type"] == "table"

    def test_render_board_view_not_found(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        with pytest.raises(KeyError):
            mgr.render_board_view(board.id, "missing")


# ===================================================================
# 6. Activity log
# ===================================================================

class TestActivityLog:
    def test_activity_log_records_creation(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        log = mgr.get_activity_log(board.id)
        assert len(log) >= 1
        assert log[0]["action"] == "board_created"

    def test_activity_log_records_item_crud(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        item = mgr.create_item(board.id, gid, "T", user_id="u1")
        mgr.update_item(board.id, item.id, user_id="u1", name="T2")
        mgr.delete_item(board.id, item.id, user_id="u1")
        log = mgr.get_activity_log(board.id)
        actions = [e["action"] for e in log]
        assert "item_created" in actions
        assert "item_updated" in actions
        assert "item_deleted" in actions

    def test_activity_log_limit(self):
        mgr = BoardManager()
        board = mgr.create_board("B", owner_id="u1")
        gid = board.groups[0].id
        for i in range(10):
            mgr.create_item(board.id, gid, f"T{i}", user_id="u1")
        log = mgr.get_activity_log(board.id, limit=5)
        assert len(log) == 5


# ===================================================================
# 7. API router (integration)
# ===================================================================

class TestAPIRouter:
    def test_create_board_router(self):
        """Verify the router factory returns a valid APIRouter."""
        try:
            from board_system.api import create_board_router
            router = create_board_router()
            assert router is not None
            # Check routes exist
            paths = [r.path for r in router.routes]
            assert "" in paths or "/" in paths or any("/api/boards" in str(r) for r in router.routes)
        except ImportError:
            pytest.skip("FastAPI not available")

    def test_router_with_custom_manager(self):
        try:
            from board_system.api import create_board_router
            mgr = BoardManager()
            router = create_board_router(mgr)
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")
