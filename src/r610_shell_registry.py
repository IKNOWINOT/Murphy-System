#!/usr/bin/env python3
"""
R610 — Brainless Shell Registry
================================

The "spreadsheet" the founder asked for. Tracks 4 reusable agent shells
in a single DB table. Each shell can be loaded with any Rosetta soul +
DLF data + org position, locked while running, unloaded when done.

LIFECYCLE per founder canon:
    unlock → load (soul + DLF + position) → lock → utilize → unlock

The shell registry is the SEPARATION layer:
- Old pattern: subject matter and capability baked together (R603 v2)
- New pattern: shell + soul + DLF + position assembled per cycle

Murphy approved: extend agent_souls with shell binding fields, don't
duplicate. Build a small registry table next to it for shell tracking.

This file:
- Creates the shell_registry table (4 rows, idempotent)
- Provides claim/release/inspect functions for the orchestrator
- Standalone CLI: r610_shell_registry.py [status|claim|release|reset]
"""
import sys, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DB = "/var/lib/murphy-production/agent_substrate.db"
NOW = lambda: datetime.now(timezone.utc).isoformat()

SHELL_COUNT = 4  # founder canon: 4 brainless spots


def _conn():
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_registry():
    """Create the spreadsheet. 4 shells start in idle/unlocked state."""
    c = _conn()
    c.execute("""CREATE TABLE IF NOT EXISTS shell_registry (
        shell_id          TEXT PRIMARY KEY,
        slot_index        INTEGER UNIQUE NOT NULL,
        state             TEXT NOT NULL DEFAULT 'idle',
        -- state values: idle, loading, locked, unloading, error

        current_soul_id   TEXT,
        current_position  TEXT,
        current_dlf_pkg   TEXT,
        current_task      TEXT,

        lock_token        TEXT,
        locked_by         TEXT,
        locked_at         TEXT,
        utilize_until     TEXT,

        last_unlocked_at  TEXT,
        total_utilizations INTEGER DEFAULT 0,
        last_utilized_at  TEXT,

        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL
    )""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_shell_state
                 ON shell_registry(state)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_shell_position
                 ON shell_registry(current_position)""")
    # Audit log of every load/unload
    c.execute("""CREATE TABLE IF NOT EXISTS shell_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        shell_id TEXT NOT NULL,
        action TEXT NOT NULL,
        from_state TEXT,
        to_state TEXT,
        soul_id TEXT,
        position TEXT,
        dlf_pkg TEXT,
        task TEXT,
        actor TEXT,
        notes TEXT
    )""")
    # Seed exactly SHELL_COUNT shells if missing
    have = c.execute("SELECT count(*) FROM shell_registry").fetchone()[0]
    if have < SHELL_COUNT:
        for i in range(SHELL_COUNT):
            sid = f"shell_{i+1:02d}"
            c.execute("""INSERT OR IGNORE INTO shell_registry
                (shell_id, slot_index, state, created_at, updated_at)
                VALUES (?, ?, 'idle', ?, ?)""",
                (sid, i + 1, NOW(), NOW()))
    c.commit(); c.close()


def status():
    """Spreadsheet snapshot — what the founder reads."""
    c = _conn()
    rows = c.execute("""SELECT shell_id, slot_index, state, current_position,
        current_soul_id, current_task, locked_by, locked_at, total_utilizations,
        last_utilized_at FROM shell_registry ORDER BY slot_index""").fetchall()
    c.close()
    out = []
    for r in rows:
        out.append({
            "shell_id": r[0], "slot": r[1], "state": r[2],
            "position": r[3] or "(empty)", "soul_id": r[4] or "(no soul)",
            "task": (r[5] or "")[:60], "locked_by": r[6],
            "locked_at": r[7], "utilizations": r[8], "last_used": r[9],
        })
    return out


def claim(position, soul_id=None, dlf_pkg=None, task=None,
          locked_by="orchestrator", ttl_seconds=900):
    """Pick an idle shell, load it, lock it. Returns shell_id + token."""
    c = _conn()
    # Find first idle shell
    row = c.execute("SELECT shell_id, slot_index FROM shell_registry "
                    "WHERE state='idle' ORDER BY last_utilized_at NULLS FIRST, "
                    "slot_index LIMIT 1").fetchone()
    if not row:
        # No idle shells — return None so caller can decide (queue or fail)
        c.close()
        return None
    sid, slot = row[0], row[1]
    token = uuid.uuid4().hex[:16]
    locked_at = NOW()
    from datetime import timedelta
    util_until = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()

    c.execute("""UPDATE shell_registry SET
        state='locked', current_soul_id=?, current_position=?,
        current_dlf_pkg=?, current_task=?, lock_token=?, locked_by=?,
        locked_at=?, utilize_until=?, updated_at=?
        WHERE shell_id=?""",
        (soul_id, position, dlf_pkg, task, token, locked_by,
         locked_at, util_until, locked_at, sid))
    c.execute("""INSERT INTO shell_audit
        (ts, shell_id, action, from_state, to_state, soul_id, position,
         dlf_pkg, task, actor, notes)
        VALUES (?,?,'claim','idle','locked',?,?,?,?,?,?)""",
        (locked_at, sid, soul_id, position, dlf_pkg, task, locked_by,
         f"ttl={ttl_seconds}s"))
    c.commit(); c.close()
    return {"shell_id": sid, "slot": slot, "lock_token": token,
            "utilize_until": util_until}


def release(shell_id, lock_token, outcome="ok", notes=""):
    """Unlock + clear the shell. Soul stays in agent_souls for audit."""
    c = _conn()
    row = c.execute("SELECT lock_token, current_soul_id, current_position, "
                    "total_utilizations FROM shell_registry "
                    "WHERE shell_id=?", (shell_id,)).fetchone()
    if not row:
        c.close()
        return {"ok": False, "error": "shell_not_found"}
    if row[0] != lock_token:
        c.close()
        return {"ok": False, "error": "token_mismatch"}
    soul_id, pos, util_count = row[1], row[2], row[3] or 0
    now = NOW()
    c.execute("""UPDATE shell_registry SET
        state='idle', current_soul_id=NULL, current_position=NULL,
        current_dlf_pkg=NULL, current_task=NULL, lock_token=NULL,
        locked_by=NULL, locked_at=NULL, utilize_until=NULL,
        last_unlocked_at=?, total_utilizations=?, last_utilized_at=?,
        updated_at=? WHERE shell_id=?""",
        (now, util_count + 1, now, now, shell_id))
    c.execute("""INSERT INTO shell_audit
        (ts, shell_id, action, from_state, to_state, soul_id, position, actor, notes)
        VALUES (?, ?, 'release', 'locked', 'idle', ?, ?, ?, ?)""",
        (now, shell_id, soul_id, pos, "orchestrator", f"outcome={outcome}; {notes}"))
    c.commit(); c.close()
    return {"ok": True, "shell_id": shell_id, "utilizations": util_count + 1}


def force_reset(shell_id=None):
    """Emergency: clear a stuck shell (or all). Audit logs the reset."""
    c = _conn()
    if shell_id:
        sids = [shell_id]
    else:
        sids = [r[0] for r in c.execute(
            "SELECT shell_id FROM shell_registry WHERE state != 'idle'").fetchall()]
    for sid in sids:
        c.execute("""UPDATE shell_registry SET
            state='idle', current_soul_id=NULL, current_position=NULL,
            current_dlf_pkg=NULL, current_task=NULL, lock_token=NULL,
            locked_by=NULL, locked_at=NULL, utilize_until=NULL,
            updated_at=? WHERE shell_id=?""", (NOW(), sid))
        c.execute("""INSERT INTO shell_audit
            (ts, shell_id, action, from_state, to_state, actor, notes)
            VALUES (?, ?, 'force_reset', 'unknown', 'idle', 'admin', 'manual reset')""",
            (NOW(), sid))
    c.commit(); c.close()
    return {"ok": True, "reset": sids}


def recent_audit(limit=10):
    c = _conn()
    rows = c.execute("""SELECT ts, shell_id, action, from_state, to_state,
        position, actor, notes FROM shell_audit ORDER BY id DESC LIMIT ?""",
        (limit,)).fetchall()
    c.close()
    return [{"ts": r[0], "shell": r[1], "action": r[2],
             "from": r[3], "to": r[4], "position": r[5],
             "actor": r[6], "notes": r[7]} for r in rows]


if __name__ == "__main__":
    init_registry()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        s = status()
        print(f"\n{'SHELL':10} {'STATE':10} {'POSITION':20} {'TASK':40} {'USES'}")
        print("─" * 95)
        for r in s:
            task = r["task"][:38] + ".." if len(r["task"]) > 40 else r["task"]
            print(f"{r['shell_id']:10} {r['state']:10} {r['position']:20} {task:40} {r['utilizations']}")
        print()
    elif cmd == "claim":
        pos = sys.argv[2] if len(sys.argv) > 2 else "platform_cto"
        task = sys.argv[3] if len(sys.argv) > 3 else "test task"
        result = claim(position=pos, task=task, locked_by="cli")
        print(json.dumps(result, indent=2))
    elif cmd == "release":
        sid, token = sys.argv[2], sys.argv[3]
        print(json.dumps(release(sid, token), indent=2))
    elif cmd == "reset":
        sid = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(force_reset(sid), indent=2))
    elif cmd == "audit":
        for r in recent_audit():
            print(f"  {r['ts'][:19]} {r['shell']:10} {r['action']:12} "
                  f"{r['from']}→{r['to']:8} {r['position'] or '-':20} {r['notes']}")
    else:
        print(f"unknown: {cmd}")
