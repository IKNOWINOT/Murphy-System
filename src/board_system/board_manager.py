"""
Board Manager — SQLite-backed persistent implementation.
PATCH-158: Replaces in-memory stub with SQLite backend.
Matches exact API signatures from board_system/api.py.
"""
from __future__ import annotations
import sqlite3, json, logging
from typing import Any, Dict, List, Optional
from .models import (Board, BoardKind, Group, Item, ColumnDefinition, ColumnType,
                     ViewType, ViewConfig, ActivityLogEntry, ActivityAction, CellValue,
                     _new_id, _now)

logger = logging.getLogger(__name__)
_DB = "/var/lib/murphy-production/boards.db"


def _conn():
    db = sqlite3.connect(_DB)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS boards (
        id TEXT PRIMARY KEY, name TEXT, description TEXT DEFAULT '',
        kind TEXT DEFAULT 'public', workspace_id TEXT DEFAULT '',
        owner_id TEXT DEFAULT '', created_at TEXT, updated_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS groups (
        id TEXT PRIMARY KEY, board_id TEXT, title TEXT,
        color TEXT DEFAULT '#579bfc', position INTEGER DEFAULT 0,
        collapsed INTEGER DEFAULT 0, created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY, board_id TEXT, group_id TEXT, name TEXT,
        cells TEXT DEFAULT '{}', position INTEGER DEFAULT 0,
        creator_id TEXT DEFAULT '', created_at TEXT, updated_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS columns (
        id TEXT PRIMARY KEY, board_id TEXT, title TEXT,
        column_type TEXT DEFAULT 'text', description TEXT DEFAULT '',
        settings TEXT DEFAULT '{}', position INTEGER DEFAULT 0, created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS views (
        id TEXT PRIMARY KEY, board_id TEXT, name TEXT,
        view_type TEXT DEFAULT 'table', settings TEXT DEFAULT '{}',
        board_id2 TEXT DEFAULT '', created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS activity_log (
        id TEXT PRIMARY KEY, board_id TEXT, user_id TEXT DEFAULT '',
        action TEXT DEFAULT 'create', entity_type TEXT DEFAULT '',
        entity_id TEXT DEFAULT '', details TEXT DEFAULT '{}', created_at TEXT)""")
    db.commit()
    return db


def _seed():
    db = _conn()
    if db.execute("SELECT COUNT(*) FROM boards").fetchone()[0] > 0:
        db.close(); return
    now = _now()
    bid = _new_id()
    db.execute("INSERT INTO boards VALUES (?,?,?,?,?,?,?,?)",
               (bid, "Murphy Platform", "Core platform development", "public", "", "founder", now, now))
    gids = {}
    for i, gname in enumerate(["To Do", "In Progress", "Review", "Done"]):
        gid = _new_id(); gids[gname] = gid
        db.execute("INSERT INTO groups VALUES (?,?,?,?,?,?,?)", (gid, bid, gname, "#579bfc", i, 0, now))
    tasks = [
        ("Audit all 48 UI pages",        "In Progress", "critical"),
        ("Wire ROI calendar live data",  "In Progress", "high"),
        ("Deploy Matrix chat UI",        "Review",      "medium"),
        ("PATCH-157 Matrix Chat",        "Done",        "low"),
        ("PATCH-156 Game Studio",        "Done",        "low"),
        ("Shield Wall audit",           "To Do",       "high"),
        ("Write PATCH-159 changelog",    "To Do",       "medium"),
    ]
    for title, status, prio in tasks:
        gid = gids.get(status, gids["To Do"]); iid = _new_id()
        db.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)",
                   (iid, bid, gid, title, json.dumps({"priority": prio, "assignee": "Murphy AI"}),
                    0, "founder", now, now))
    # Second and third boards
    for bname, bdesc in [("AI Research","AI safety & ethics"),("Growth & Ops","Marketing")]:
        b2id = _new_id()
        db.execute("INSERT INTO boards VALUES (?,?,?,?,?,?,?,?)",
                   (b2id, bname, bdesc, "public", "", "founder", now, now))
        for i, gname in enumerate(["To Do","In Progress","Done"]):
            db.execute("INSERT INTO groups VALUES (?,?,?,?,?,?,?)",
                       (_new_id(), b2id, gname, "#579bfc", i, 0, now))
    db.commit(); db.close()


def _build_board(db, r) -> Board:
    bid = r["id"]
    b = Board(id=bid, name=r["name"], description=r["description"] or "",
              workspace_id=r["workspace_id"] or "", owner_id=r["owner_id"] or "",
              created_at=r["created_at"] or "", updated_at=r["updated_at"] or "")
    try: b.kind = BoardKind(r["kind"])
    except: b.kind = BoardKind.PUBLIC
    # Load groups
    groups = db.execute("SELECT * FROM groups WHERE board_id=? ORDER BY position", (bid,)).fetchall()
    for g in groups:
        group = Group(id=g["id"], title=g["title"], color=g["color"] or "#579bfc",
                      board_id=bid, position=g["position"] or 0,
                      collapsed=bool(g["collapsed"]))
        items = db.execute("SELECT * FROM items WHERE group_id=? ORDER BY position", (g["id"],)).fetchall()
        for it in items:
            cells_raw = json.loads(it["cells"] or "{}")
            item = Item(id=it["id"], name=it["name"], group_id=g["id"], board_id=bid,
                        position=it["position"] or 0, creator_id=it["creator_id"] or "",
                        created_at=it["created_at"] or "", updated_at=it["updated_at"] or "")
            for col_id, val in cells_raw.items():
                item.cells[col_id] = CellValue(column_id=col_id, value=val, display_value=str(val))
            group.items.append(item)
        b.groups.append(group)
    # Load columns
    cols = db.execute("SELECT * FROM columns WHERE board_id=? ORDER BY position", (bid,)).fetchall()
    for col in cols:
        ct = ColumnType.TEXT
        try: ct = ColumnType(col["column_type"])
        except: pass
        b.columns.append(ColumnDefinition(
            id=col["id"], board_id=bid, title=col["title"],
            column_type=ct, description=col["description"] or "",
            settings=json.loads(col["settings"] or "{}"),
            position=col["position"] or 0, created_at=col["created_at"] or ""))
    return b


class BoardManager:
    def __init__(self): _seed()

    def create_board(self, *, name, description="", kind=BoardKind.PUBLIC,
                     workspace_id="", owner_id="system") -> Board:
        db = _conn(); now = _now(); bid = _new_id()
        kv = kind.value if isinstance(kind, BoardKind) else str(kind)
        db.execute("INSERT INTO boards VALUES (?,?,?,?,?,?,?,?)",
                   (bid, name, description, kv, workspace_id, owner_id, now, now))
        for i, gname in enumerate(["To Do", "In Progress", "Done"]):
            db.execute("INSERT INTO groups VALUES (?,?,?,?,?,?,?)",
                       (_new_id(), bid, gname, "#579bfc", i, 0, now))
        db.commit()
        b = _build_board(db, db.execute("SELECT * FROM boards WHERE id=?", (bid,)).fetchone())
        db.close(); return b

    def list_boards(self, workspace_id="") -> List[Board]:
        db = _conn()
        q = "SELECT * FROM boards ORDER BY created_at"
        params = []
        if workspace_id:
            q = "SELECT * FROM boards WHERE workspace_id=? ORDER BY created_at"; params = [workspace_id]
        rows = db.execute(q, params).fetchall()
        result = [_build_board(db, r) for r in rows]
        db.close(); return result

    def get_board(self, board_id: str) -> Optional[Board]:
        db = _conn(); r = db.execute("SELECT * FROM boards WHERE id=?", (board_id,)).fetchone()
        if not r: db.close(); return None
        b = _build_board(db, r); db.close(); return b

    def update_board(self, board_id, *, user_id="", name=None, description=None, kind=None) -> Board:
        db = _conn(); now = _now(); fields = ["updated_at=?"]; vals = [now]
        if name is not None: fields.append("name=?"); vals.append(name)
        if description is not None: fields.append("description=?"); vals.append(description)
        if kind is not None: fields.append("kind=?"); vals.append(kind.value if isinstance(kind, BoardKind) else str(kind))
        vals.append(board_id)
        db.execute(f"UPDATE boards SET {', '.join(fields)} WHERE id=?", vals); db.commit()
        b = _build_board(db, db.execute("SELECT * FROM boards WHERE id=?", (board_id,)).fetchone())
        db.close(); return b

    def delete_board(self, board_id: str, *, user_id="") -> bool:
        db = _conn()
        for t in ["items","groups","columns","views","activity_log"]:
            db.execute(f"DELETE FROM {t} WHERE board_id=?", (board_id,))
        db.execute("DELETE FROM boards WHERE id=?", (board_id,)); db.commit(); db.close(); return True

    def create_group(self, board_id, title="New Group", *, user_id="", color="#579bfc") -> Group:
        db = _conn(); now = _now(); gid = _new_id()
        pos = (db.execute("SELECT MAX(position) FROM groups WHERE board_id=?", (board_id,)).fetchone()[0] or 0) + 1
        db.execute("INSERT INTO groups VALUES (?,?,?,?,?,?,?)", (gid, board_id, title, color, pos, 0, now))
        db.commit(); db.close()
        return Group(id=gid, title=title, color=color, board_id=board_id, position=pos)

    def update_group(self, board_id, group_id, *, user_id="", title=None, color=None) -> Group:
        db = _conn(); fields = []; vals = []
        if title: fields.append("title=?"); vals.append(title)
        if color: fields.append("color=?"); vals.append(color)
        if fields: vals.append(group_id); db.execute(f"UPDATE groups SET {', '.join(fields)} WHERE id=?", vals); db.commit()
        r = db.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone(); db.close()
        return Group(id=r["id"], title=r["title"], color=r["color"] or "#579bfc",
                     board_id=board_id, position=r["position"] or 0)

    def delete_group(self, board_id, group_id, *, user_id="") -> bool:
        db = _conn(); db.execute("DELETE FROM items WHERE group_id=?", (group_id,))
        db.execute("DELETE FROM groups WHERE id=?", (group_id,)); db.commit(); db.close(); return True

    def create_item(self, board_id, group_id, name, *, user_id="", cell_values=None) -> Item:
        db = _conn(); now = _now(); iid = _new_id()
        cells = cell_values or {}
        db.execute("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)",
                   (iid, board_id, group_id, name, json.dumps(cells), 0, user_id or "system", now, now))
        db.commit(); db.close()
        item = Item(id=iid, name=name, group_id=group_id, board_id=board_id,
                    creator_id=user_id or "system", created_at=now, updated_at=now)
        for k, v in cells.items():
            item.cells[k] = CellValue(column_id=k, value=v, display_value=str(v))
        return item

    def get_item(self, board_id, item_id) -> Optional[Item]:
        db = _conn(); r = db.execute("SELECT * FROM items WHERE id=? AND board_id=?", (item_id, board_id)).fetchone(); db.close()
        if not r: return None
        item = Item(id=r["id"], name=r["name"], group_id=r["group_id"], board_id=r["board_id"],
                    position=r["position"] or 0, creator_id=r["creator_id"] or "",
                    created_at=r["created_at"] or "", updated_at=r["updated_at"] or "")
        for k, v in json.loads(r["cells"] or "{}").items():
            item.cells[k] = CellValue(column_id=k, value=v, display_value=str(v))
        return item

    def update_item(self, board_id, item_id, *, user_id="", name=None) -> Item:
        db = _conn(); now = _now()
        if name: db.execute("UPDATE items SET name=?, updated_at=? WHERE id=?", (name, now, item_id)); db.commit()
        db.close(); return self.get_item(board_id, item_id)

    def move_item(self, board_id, item_id, target_group_id, *, user_id="") -> Item:
        db = _conn(); now = _now()
        db.execute("UPDATE items SET group_id=?, updated_at=? WHERE id=?", (target_group_id, now, item_id))
        db.commit(); db.close(); return self.get_item(board_id, item_id)

    def delete_item(self, board_id, item_id, *, user_id="") -> bool:
        db = _conn(); db.execute("DELETE FROM items WHERE id=?", (item_id,)); db.commit(); db.close(); return True

    def update_cell(self, board_id, item_id, column_id, *, value, user_id="") -> Item:
        db = _conn(); now = _now()
        r = db.execute("SELECT cells FROM items WHERE id=?", (item_id,)).fetchone()
        if r:
            cells = json.loads(r["cells"] or "{}"); cells[column_id] = value
            db.execute("UPDATE items SET cells=?, updated_at=? WHERE id=?", (json.dumps(cells), now, item_id))
            db.commit()
        db.close(); return self.get_item(board_id, item_id)

    def create_column(self, board_id, *, title, column_type=ColumnType.TEXT, description="",
                      settings=None, user_id="") -> ColumnDefinition:
        db = _conn(); now = _now(); cid = _new_id()
        ct = column_type.value if isinstance(column_type, ColumnType) else str(column_type)
        pos = (db.execute("SELECT MAX(position) FROM columns WHERE board_id=?", (board_id,)).fetchone()[0] or 0) + 1
        db.execute("INSERT INTO columns VALUES (?,?,?,?,?,?,?,?)",
                   (cid, board_id, title, ct, description, json.dumps(settings or {}), pos, now))
        db.commit(); db.close()
        return ColumnDefinition(id=cid, board_id=board_id, title=title, column_type=column_type if isinstance(column_type, ColumnType) else ColumnType.TEXT,
                                description=description, settings=settings or {}, position=pos, created_at=now)

    def list_columns(self, board_id) -> List[ColumnDefinition]:
        db = _conn(); rows = db.execute("SELECT * FROM columns WHERE board_id=? ORDER BY position", (board_id,)).fetchall(); db.close()
        result = []
        for r in rows:
            ct = ColumnType.TEXT
            try: ct = ColumnType(r["column_type"])
            except: pass
            result.append(ColumnDefinition(id=r["id"], board_id=r["board_id"], title=r["title"],
                                           column_type=ct, description=r["description"] or "",
                                           settings=json.loads(r["settings"] or "{}"),
                                           position=r["position"] or 0, created_at=r["created_at"] or ""))
        return result

    def update_column(self, board_id, column_id, *, title=None, settings=None, user_id="") -> ColumnDefinition:
        db = _conn(); fields = []; vals = []
        if title: fields.append("title=?"); vals.append(title)
        if settings: fields.append("settings=?"); vals.append(json.dumps(settings))
        if fields: vals.append(column_id); db.execute(f"UPDATE columns SET {', '.join(fields)} WHERE id=?", vals); db.commit()
        r = db.execute("SELECT * FROM columns WHERE id=?", (column_id,)).fetchone()
        db.close()
        ct = ColumnType.TEXT
        try: ct = ColumnType(r["column_type"])
        except: pass
        return ColumnDefinition(id=r["id"], board_id=r["board_id"], title=r["title"], column_type=ct,
                                description=r["description"] or "", settings=json.loads(r["settings"] or "{}"),
                                position=r["position"] or 0, created_at=r["created_at"] or "")

    def delete_column(self, board_id, column_id, *, user_id="") -> bool:
        db = _conn(); db.execute("DELETE FROM columns WHERE id=?", (column_id,)); db.commit(); db.close(); return True

    def create_view(self, board_id, *, name, view_type=ViewType.TABLE, settings=None) -> ViewConfig:
        db = _conn(); now = _now(); vid = _new_id()
        vt = view_type.value if isinstance(view_type, ViewType) else str(view_type)
        db.execute("INSERT INTO views VALUES (?,?,?,?,?,?,?)",
                   (vid, board_id, name, vt, json.dumps(settings or {}), board_id, now))
        db.commit(); db.close()
        vtype = view_type if isinstance(view_type, ViewType) else ViewType.TABLE
        return ViewConfig(id=vid, board_id=board_id, name=name, view_type=vtype,
                          settings=settings or {}, created_at=now)

    def list_views(self, board_id) -> List[ViewConfig]:
        db = _conn(); rows = db.execute("SELECT * FROM views WHERE board_id=?", (board_id,)).fetchall(); db.close()
        result = []
        for r in rows:
            vt = ViewType.TABLE
            try: vt = ViewType(r["view_type"])
            except: pass
            result.append(ViewConfig(id=r["id"], board_id=r["board_id"], name=r["name"],
                                     view_type=vt, settings=json.loads(r["settings"] or "{}"),
                                     created_at=r["created_at"] or ""))
        return result

    def render_board_view(self, board_id, view_id) -> Dict[str, Any]:
        board = self.get_board(board_id)
        if not board: raise KeyError(f"Board {board_id!r} not found")
        return board.to_dict()

    def get_activity_log(self, board_id, *, limit=50) -> List[Dict[str, Any]]:
        db = _conn(); rows = db.execute(
            "SELECT * FROM activity_log WHERE board_id=? ORDER BY created_at DESC LIMIT ?",
            (board_id, limit)).fetchall(); db.close()
        return [dict(r) for r in rows]
