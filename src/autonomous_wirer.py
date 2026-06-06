#!/usr/bin/env python3
"""
Autonomous Wirer — discovers gaps the cyborg can't see across sessions.

Runs every hour via murphy-autowirer.timer. Each cycle:
  1. Re-crawl substrate (delta vs last cycle)
  2. Find architecture-flavored docs not yet referenced in canonical map
  3. Find new orphan modules
  4. Find regressions (was wired, now isn't)
  5. File HITL card per finding with proposed action
  6. Persist findings to wirer_findings.db
  7. Update /api/wirer/status

No auto-apply. All proposals go through HITL.
"""
import os, sys, json, sqlite3, time, hashlib, subprocess, re
from datetime import datetime, timezone
from pathlib import Path

DB = "/var/lib/murphy-production/wirer_findings.db"
SUBSTRATE = "/var/lib/murphy-production/substrate_map.db"
HITL_DB = "/var/lib/murphy-production/state/hitl_queue.db"
CANONICAL_MAP_PATH = "/opt/Murphy-System/documentation/architecture/canonical_map_index.md"
SEARCH_ROOTS = [
    "/opt/Murphy-System",
    "/var/lib/murphy-production",
]
DOC_GLOB_PATTERNS = ("*.md",)
ARCH_KEYWORDS = re.compile(
    r"\b(architecture|system\s*map|topology|layer|pipeline|orchestrat|"
    r"subsystem|component\s*diagram|data\s*flow|design\s*lock|design\s*system|"
    r"role\s*template|dispatch|rosetta|psm|aionmind|confidence_engine)\b",
    re.IGNORECASE,
)
DOC_MIN_LINES = 80          # ignore tiny notes
DOC_MAX_AGE_DAYS = 90       # focus on recent work
NOW = datetime.now(timezone.utc)

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_ts TEXT NOT NULL,
            kind TEXT NOT NULL,         -- new_doc / new_orphan / regression / contradiction
            path TEXT NOT NULL,
            details TEXT,               -- JSON
            severity TEXT NOT NULL,     -- info / warn / urgent
            hitl_card_id TEXT,
            status TEXT NOT NULL DEFAULT 'open'  -- open / acknowledged / resolved / ignored
        );
        CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
        CREATE INDEX IF NOT EXISTS idx_findings_kind ON findings(kind);

        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            n_findings INTEGER DEFAULT 0,
            n_new_docs INTEGER DEFAULT 0,
            n_new_orphans INTEGER DEFAULT 0,
            n_regressions INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS seen_docs (
            path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            line_count INTEGER,
            referenced_in_canonical INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS module_snapshots (
            cycle_id INTEGER NOT NULL,
            module_name TEXT NOT NULL,
            child_count INTEGER NOT NULL,
            kind TEXT,
            PRIMARY KEY (cycle_id, module_name)
        );
    """)
    return conn

def load_canonical_references():
    """Read the canonical map and extract referenced doc paths/module names."""
    refs = set()
    candidates = [
        "/opt/Murphy-System/documentation/architecture/README.md",
        # cyborg map is in workspace, accessed via the canonical_map_index.md mirror
        CANONICAL_MAP_PATH,
    ]
    for path in candidates:
        try:
            with open(path) as f:
                text = f.read()
            # quoted file references and module names
            for m in re.finditer(r"[`'\"]([\w/\-\.]+\.(md|py))[`'\"]", text):
                refs.add(m.group(1))
            for m in re.finditer(r"\b([a-z_][a-z0-9_]+)\.py\b", text):
                refs.add(m.group(1))
        except FileNotFoundError:
            pass
    return refs

def scan_docs():
    """Find every markdown doc with architecture-keywords + recent + non-trivial."""
    results = []
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        for pattern in DOC_GLOB_PATTERNS:
            for p in Path(root).rglob(pattern):
                # skip noise
                s = str(p)
                if any(x in s for x in ("venv/", "node_modules/", "__pycache__",
                                         ".git/", "/archive/", ".pre-", "backup")):
                    continue
                try:
                    stat = p.stat()
                    age_days = (time.time() - stat.st_mtime) / 86400
                    if age_days > DOC_MAX_AGE_DAYS:
                        continue
                    with open(p, errors="ignore") as f:
                        content = f.read()
                    lines = content.count("\n")
                    if lines < DOC_MIN_LINES:
                        continue
                    if not ARCH_KEYWORDS.search(content[:4000]):
                        continue
                    results.append({
                        "path": str(p),
                        "lines": lines,
                        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                    })
                except (OSError, IOError):
                    continue
    return results

def scan_substrate(conn_w):
    """Snapshot module wiring state for delta detection."""
    if not os.path.exists(SUBSTRATE):
        return [], []
    sub = sqlite3.connect(SUBSTRATE)
    rows = sub.execute(
        "SELECT name, child_count, kind, lines, role FROM modules"
    ).fetchall()
    sub.close()

    # current snapshot
    current = {r[0]: {"child_count": r[1], "kind": r[2], "lines": r[3], "role": r[4]}
               for r in rows}

    # previous snapshot
    last_cycle = conn_w.execute(
        "SELECT id FROM cycles ORDER BY id DESC LIMIT 1 OFFSET 1"
    ).fetchone()
    previous = {}
    if last_cycle:
        prev_rows = conn_w.execute(
            "SELECT module_name, child_count FROM module_snapshots WHERE cycle_id = ?",
            (last_cycle[0],)
        ).fetchall()
        previous = {r[0]: r[1] for r in prev_rows}

    new_orphans = []
    regressions = []
    for name, info in current.items():
        if name not in previous:
            if info["child_count"] == 0 and info["lines"] > 200 and info["role"] in (
                "sales","mail","hitl","billing","orchestration","gates",
                "verification","audit","ml","scheduler","storage"):
                new_orphans.append({"name": name, **info})
        else:
            # was wired, now isn't = regression
            if previous[name] > 0 and info["child_count"] == 0:
                regressions.append({
                    "name": name, "was_imports": previous[name],
                    "now_imports": 0, **info
                })
    return list(current.items()), new_orphans, regressions

def write_finding(conn, kind, path, details, severity):
    cur = conn.execute(
        "INSERT INTO findings (cycle_ts, kind, path, details, severity) VALUES (?, ?, ?, ?, ?)",
        (NOW.isoformat(), kind, path, json.dumps(details), severity)
    )
    return cur.lastrowid

def file_hitl_card(title, body, source_finding_id):
    """R42 (2026-06-05) no-op shim. file_hitl_card_DISABLED kill-switch
    was applied without updating callers, causing service crash. To
    re-enable card filing, restore body of file_hitl_card_DISABLED below
    and rename it to file_hitl_card."""
    return None  # callers check `if card:` — None correctly skips the UPDATE


def file_hitl_card_DISABLED(title, body, source_finding_id):
    """Best-effort HITL card insert. Tolerant if hitl_queue schema varies."""
    try:
        h = sqlite3.connect(HITL_DB)
        # discover the right table
        tables = [r[0] for r in h.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        target = None
        for candidate in ("hitl_jobs", "cards", "hitl_queue", "queue"):
            if candidate in tables:
                target = candidate
                break
        if not target:
            h.close()
            return None
        cols = [r[1] for r in h.execute(f"PRAGMA table_info({target})")]
        card_id = f"wirer_finding_{source_finding_id}_{int(time.time())}"
        fields, values = {}, {}
        if "id" in cols: fields["id"] = card_id
        if "card_id" in cols: fields["card_id"] = card_id
        if "title" in cols: fields["title"] = title
        if "subject" in cols: fields["subject"] = title
        if "body" in cols: fields["body"] = body
        if "summary" in cols: fields["summary"] = body[:500]
        if "status" in cols: fields["status"] = "pending"
        if "kind" in cols: fields["kind"] = "wirer_finding"
        if "source" in cols: fields["source"] = "autonomous_wirer"
        if "created_at" in cols: fields["created_at"] = NOW.isoformat()
        if "created_date" in cols: fields["created_date"] = NOW.isoformat()
        if not fields:
            h.close()
            return None
        keys = ",".join(fields)
        qs = ",".join("?" for _ in fields)
        h.execute(f"INSERT INTO {target} ({keys}) VALUES ({qs})", list(fields.values()))
        h.commit()
        h.close()
        return card_id
    except Exception as e:
        sys.stderr.write(f"hitl insert failed: {e}\n")
        return None

def run_cycle():
    conn = init_db()
    cycle_cur = conn.execute(
        "INSERT INTO cycles (started_at) VALUES (?)", (NOW.isoformat(),)
    )
    cycle_id = cycle_cur.lastrowid
    conn.commit()

    canonical_refs = load_canonical_references()
    n_new_docs = n_new_orphans = n_regressions = 0

    # ---- DOCS ----
    docs = scan_docs()
    for d in docs:
        seen = conn.execute(
            "SELECT content_hash, referenced_in_canonical FROM seen_docs WHERE path = ?",
            (d["path"],)
        ).fetchone()
        basename = os.path.basename(d["path"])
        is_referenced = any(basename in ref or d["path"].endswith(ref)
                           for ref in canonical_refs)
        if not seen:
            # NEW doc — never seen before
            conn.execute(
                "INSERT INTO seen_docs (path, content_hash, first_seen, last_seen, "
                "line_count, referenced_in_canonical) VALUES (?,?,?,?,?,?)",
                (d["path"], d["content_hash"], NOW.isoformat(), NOW.isoformat(),
                 d["lines"], 1 if is_referenced else 0)
            )
            if not is_referenced:
                fid = write_finding(
                    conn, "new_doc_unread", d["path"],
                    {"lines": d["lines"], "mtime": d["mtime"]},
                    "warn"
                )
                card = file_hitl_card(
                    title=f"Wirer: architecture doc not in canonical map — {basename}",
                    body=(f"Found architecture-flavored doc not referenced anywhere "
                          f"in the canonical map.\n\n"
                          f"Path: {d['path']}\nLines: {d['lines']}\n"
                          f"Last modified: {d['mtime']}\n\n"
                          f"Proposed action: add to canonical_map_index.md OR "
                          f"archive to documentation/architecture/archive/ if "
                          f"superseded."),
                    source_finding_id=fid
                )
                if card:
                    conn.execute(
                        "UPDATE findings SET hitl_card_id = ? WHERE id = ?", (card, fid)
                    )
                n_new_docs += 1
        else:
            conn.execute(
                "UPDATE seen_docs SET last_seen = ?, line_count = ?, content_hash = ?, "
                "referenced_in_canonical = ? WHERE path = ?",
                (NOW.isoformat(), d["lines"], d["content_hash"],
                 1 if is_referenced else 0, d["path"])
            )

    # ---- MODULES ----
    snapshot, new_orphans, regressions = scan_substrate(conn)
    for name, info in snapshot:
        conn.execute(
            "INSERT INTO module_snapshots (cycle_id, module_name, child_count, kind) "
            "VALUES (?, ?, ?, ?)",
            (cycle_id, name, info["child_count"], info["kind"])
        )

    for o in new_orphans:
        fid = write_finding(
            conn, "new_orphan", o["name"],
            {"role": o["role"], "lines": o["lines"], "kind": o["kind"]},
            "info"
        )
        n_new_orphans += 1

    for r in regressions:
        fid = write_finding(
            conn, "regression", r["name"],
            {"was_imports": r["was_imports"], "now_imports": 0,
             "role": r["role"], "lines": r["lines"]},
            "urgent"
        )
        card = file_hitl_card(
            title=f"Wirer: REGRESSION — {r['name']} was wired, now orphan",
            body=(f"Module {r['name']} ({r['lines']} lines, role={r['role']}) "
                  f"had {r['was_imports']} importers last cycle, now has 0.\n\n"
                  f"Either someone removed an import or the substrate map is "
                  f"stale. Investigate before next cycle."),
            source_finding_id=fid
        )
        if card:
            conn.execute("UPDATE findings SET hitl_card_id = ? WHERE id = ?",
                        (card, fid))
        n_regressions += 1

    conn.execute(
        "UPDATE cycles SET finished_at = ?, n_findings = ?, "
        "n_new_docs = ?, n_new_orphans = ?, n_regressions = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(),
         n_new_docs + n_new_orphans + n_regressions,
         n_new_docs, n_new_orphans, n_regressions, cycle_id)
    )
    conn.commit()
    conn.close()

    return {
        "cycle_id": cycle_id,
        "new_docs": n_new_docs,
        "new_orphans": n_new_orphans,
        "regressions": n_regressions,
    }

if __name__ == "__main__":
    result = run_cycle()
    print(json.dumps(result, indent=2))
