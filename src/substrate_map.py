"""
PATCH-R600 (2026-06-04) — Substrate spreadsheet

Walks /opt/Murphy-System and produces:
  - one row per python module
  - one row per systemd unit
  - one row per sqlite database

For modules: extracts AST imports (parents) and inverted index (children).
For systemd units: parses ExecStart to find which module they invoke.
For databases: cross-references which modules open it.

OUTPUT:
  /var/lib/murphy-production/substrate_map.db with tables:
    modules(path, name, lines, kind, last_modified, role)
    imports(from_module, to_module)   -- edge list
    units(unit, kind, exec_target)
    dbs(path, size_bytes, opened_by)  -- opened_by is comma-list of modules
    refresh_log(ts, modules, edges, units, dbs)

PUBLIC SURFACE:
  build_map() -> dict summary
  query(name) -> {parents, children, role, units, dbs}
"""
import ast
import os
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone

SRC = "/opt/Murphy-System/src"
SCRIPTS = "/opt/Murphy-System/scripts"
SYSTEMD = "/etc/systemd/system"
DBDIR = "/var/lib/murphy-production"
MAP_DB = "/var/lib/murphy-production/substrate_map.db"

# Role heuristics — substring -> role label
ROLE_PATTERNS = [
    (r"\b(runtime|app\.py|main\.py|server)\b",       "runtime"),
    (r"(scheduler|cron|cadence|timer|tick)",         "scheduler"),
    (r"(mind|learning|llm|inference|train|model)",   "ml"),
    (r"(inbound|outbound|email|mail|inbox)",         "mail"),
    (r"(sales|prospect|outreach|critic)",            "sales"),
    (r"(hitl|approve|founder|operator)",             "hitl"),
    (r"(payment|stripe|nowpayment|billing|invoice)", "billing"),
    (r"(audit|psm|ledger|self_mod)",                 "audit"),
    (r"(vendor|protection|gate)",                    "gates"),
    (r"(test|fixture|mock|stub)",                    "test"),
    (r"(shape|verify|verifier|journey)",             "verification"),
    (r"(robotics|hardware|edge)",                    "robotics"),
    (r"(persist|storage|db|cache)",                  "storage"),
    (r"(security|auth|token|oauth)",                 "security"),
    (r"(rosetta|swarm|conductor|router|dispatch)",   "orchestration"),
]

def _role(path: str) -> str:
    lp = path.lower()
    for pat, role in ROLE_PATTERNS:
        if re.search(pat, lp):
            return role
    return "misc"


def _is_excluded(p: str) -> bool:
    bad = ("/__pycache__/", "/.venv/", "/venv/", ".pre-r", ".pyc")
    return any(b in p for b in bad)


def _walk_modules() -> list:
    rows = []
    for root in (SRC, SCRIPTS):
        for dp, dn, fn in os.walk(root):
            if _is_excluded(dp):
                continue
            for f in fn:
                if not f.endswith(".py") or f.endswith(".pyc"):
                    continue
                full = os.path.join(dp, f)
                if _is_excluded(full):
                    continue
                try:
                    st = os.stat(full)
                    rows.append({
                        "path": full,
                        "name": f.replace(".py",""),
                        "lines": sum(1 for _ in open(full, "rb")),
                        "kind": "module" if root == SRC else "script",
                        "last_modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                        "size_bytes": st.st_size,
                        "role": _role(full),
                    })
                except Exception:
                    pass
    return rows


def _extract_imports(path: str) -> list:
    """Return list of imported names — best-effort, ignores syntax errors."""
    try:
        src = open(path, "r", encoding="utf-8", errors="ignore").read()
        tree = ast.parse(src, filename=path)
    except Exception:
        return []
    imps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imps.append(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imps.append(node.module.split(".")[0])
    return imps


def _walk_units() -> list:
    rows = []
    if not os.path.isdir(SYSTEMD):
        return rows
    for f in os.listdir(SYSTEMD):
        if not f.startswith("murphy"):
            continue
        if not (f.endswith(".service") or f.endswith(".timer")):
            continue
        full = os.path.join(SYSTEMD, f)
        try:
            content = open(full, "r", errors="ignore").read()
        except Exception:
            continue
        exec_start = ""
        m = re.search(r"ExecStart=(.+)", content)
        if m:
            exec_start = m.group(1).strip()
        rows.append({
            "unit": f,
            "kind": "timer" if f.endswith(".timer") else "service",
            "exec_target": exec_start,
        })
    return rows


def _walk_dbs() -> list:
    rows = []
    if not os.path.isdir(DBDIR):
        return rows
    for f in os.listdir(DBDIR):
        if not f.endswith(".db"):
            continue
        full = os.path.join(DBDIR, f)
        try:
            sz = os.path.getsize(full)
        except OSError:
            sz = 0
        rows.append({"path": full, "name": f, "size_bytes": sz})
    return rows


def _find_db_openers(db_basename: str, modules: list) -> list:
    """Grep modules for sqlite3.connect references to this db filename."""
    openers = []
    for m in modules:
        try:
            src = open(m["path"], "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if db_basename in src:
            openers.append(m["name"])
    return openers[:10]  # cap at 10


def build_map() -> dict:
    t0 = time.time()
    modules = _walk_modules()
    units = _walk_units()
    dbs = _walk_dbs()

    by_name = {m["name"]: m for m in modules}

    # edges: from_module -> to_module (only internal — to_module must exist as a known module)
    edges = []
    children = defaultdict(set)
    parents = defaultdict(set)
    for m in modules:
        for imp in _extract_imports(m["path"]):
            if imp in by_name and imp != m["name"]:
                edges.append((m["name"], imp))
                parents[m["name"]].add(imp)
                children[imp].add(m["name"])

    # db openers
    for d in dbs:
        d["opened_by"] = ",".join(_find_db_openers(d["name"], modules))

    # write to map db
    if os.path.exists(MAP_DB):
        os.remove(MAP_DB)
    c = sqlite3.connect(MAP_DB)
    c.executescript("""
      CREATE TABLE modules(path TEXT PRIMARY KEY, name TEXT, lines INT, kind TEXT,
                            last_modified TEXT, size_bytes INT, role TEXT,
                            parent_count INT, child_count INT);
      CREATE INDEX idx_mod_name ON modules(name);
      CREATE INDEX idx_mod_role ON modules(role);
      CREATE TABLE imports(from_module TEXT, to_module TEXT,
                            PRIMARY KEY(from_module, to_module));
      CREATE INDEX idx_imp_to ON imports(to_module);
      CREATE TABLE units(unit TEXT PRIMARY KEY, kind TEXT, exec_target TEXT);
      CREATE TABLE dbs(path TEXT PRIMARY KEY, name TEXT, size_bytes INT, opened_by TEXT);
      CREATE TABLE refresh_log(ts TEXT PRIMARY KEY, modules INT, edges INT, units INT, dbs INT, duration_s REAL);
    """)
    for m in modules:
        c.execute("""INSERT INTO modules(path,name,lines,kind,last_modified,size_bytes,role,parent_count,child_count)
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (m["path"], m["name"], m["lines"], m["kind"], m["last_modified"],
                   m["size_bytes"], m["role"],
                   len(parents.get(m["name"], set())),
                   len(children.get(m["name"], set()))))
    for fm, tm in edges:
        c.execute("INSERT OR IGNORE INTO imports VALUES (?,?)", (fm, tm))
    for u in units:
        c.execute("INSERT OR REPLACE INTO units VALUES (?,?,?)", (u["unit"], u["kind"], u["exec_target"]))
    for d in dbs:
        c.execute("INSERT OR REPLACE INTO dbs VALUES (?,?,?,?)",
                  (d["path"], d["name"], d["size_bytes"], d.get("opened_by","")))
    dur = round(time.time() - t0, 2)
    c.execute("INSERT INTO refresh_log VALUES (?,?,?,?,?,?)",
              (datetime.now(timezone.utc).isoformat(), len(modules), len(edges),
               len(units), len(dbs), dur))
    c.commit(); c.close()

    return {
        "ok": True,
        "modules": len(modules),
        "edges": len(edges),
        "units": len(units),
        "dbs": len(dbs),
        "duration_s": dur,
    }


def query(name: str) -> dict:
    c = sqlite3.connect(MAP_DB); c.row_factory = sqlite3.Row
    m = c.execute("SELECT * FROM modules WHERE name=?", (name,)).fetchone()
    if not m:
        return {"ok": False, "error": f"no module named '{name}'"}
    parents = [r[0] for r in c.execute("SELECT to_module FROM imports WHERE from_module=?", (name,)).fetchall()]
    children = [r[0] for r in c.execute("SELECT from_module FROM imports WHERE to_module=?", (name,)).fetchall()]
    units = [dict(r) for r in c.execute("SELECT * FROM units WHERE exec_target LIKE ?", (f"%{name}%",)).fetchall()]
    dbs = [dict(r) for r in c.execute("SELECT * FROM dbs WHERE opened_by LIKE ?", (f"%{name}%",)).fetchall()]
    c.close()
    return {
        "ok": True,
        "module": dict(m),
        "parents": parents,
        "children": children,
        "units_invoking": units,
        "dbs_used": dbs,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(build_map())
    elif len(sys.argv) > 1 and sys.argv[1] == "query":
        import json as _j
        print(_j.dumps(query(sys.argv[2]), indent=2, default=str))
    else:
        print("usage: substrate_map.py build|query <name>")
