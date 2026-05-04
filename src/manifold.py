"""
manifold.py — PATCH-181
Manifold Planning Engine.

Data hierarchy:
  Project
    └── CalendarBlock  (a week or date range on the calendar)
          └── Milestone  (a key deliverable within that block)
                └── DetailItem  (a specific task or question within a milestone)
                      └── ManifoldEntry  (a data snapshot: assumption | actual | info_gap)

ManifoldEntry has a dependency chain:
  "In order to know [this_fact], I first need to know [parent_fact]"

When any ManifoldEntry changes:
  - All children that depend on it are re-evaluated
  - Each propagation computes: financial_delta, change_type (change_order | credit | no_impact)
  - A ChangeEvent is logged with: what changed, who it affects, $delta, timestamp

This creates the difference engine: small upstream changes → large downstream implications.
Change orders cost the client. Credits improve the relationship.
"""

import sqlite3, json, uuid, logging, os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger("murphy.manifold")
DB_PATH = "/var/lib/murphy-production/manifold.db"


def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        -- Top-level project container
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            client TEXT,
            description TEXT,
            status TEXT DEFAULT 'active',
            budget_usd REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            color TEXT DEFAULT '#00d4ff',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Calendar blocks — a span on the calendar (week, sprint, phase)
        CREATE TABLE IF NOT EXISTS calendar_blocks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            block_type TEXT DEFAULT 'sprint',  -- sprint | phase | milestone_group
            status TEXT DEFAULT 'planned',      -- planned | active | complete | at_risk
            color TEXT,
            position INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- Milestones within a calendar block
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY,
            block_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'pending',   -- pending | in_progress | complete | blocked | at_risk
            priority TEXT DEFAULT 'medium',  -- critical | high | medium | low
            owner TEXT,
            estimated_hours REAL DEFAULT 0,
            actual_hours REAL DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            actual_cost_usd REAL DEFAULT 0,
            position INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (block_id) REFERENCES calendar_blocks(id)
        );

        -- Detail items within a milestone (tasks, questions, requirements)
        CREATE TABLE IF NOT EXISTS detail_items (
            id TEXT PRIMARY KEY,
            milestone_id TEXT NOT NULL,
            block_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            item_type TEXT DEFAULT 'task',   -- task | question | requirement | risk | decision
            description TEXT,
            status TEXT DEFAULT 'open',      -- open | answered | complete | blocked | deferred
            owner TEXT,
            due_date TEXT,
            estimated_hours REAL DEFAULT 0,
            actual_hours REAL DEFAULT 0,
            position INTEGER DEFAULT 0,
            parent_item_id TEXT,             -- for nested detail items
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (milestone_id) REFERENCES milestones(id)
        );

        -- Manifold entries — the knowledge/assumption/actual data layer
        -- One detail item can have many manifold entries (knowledge evolves over time)
        CREATE TABLE IF NOT EXISTS manifold_entries (
            id TEXT PRIMARY KEY,
            detail_item_id TEXT NOT NULL,
            milestone_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            entry_type TEXT NOT NULL,        -- assumption | actual | info_gap | decision | known_at
            title TEXT NOT NULL,
            body TEXT,                       -- the content / answer / data
            -- Dependency chain: "In order to know [title], I first need to know [depends_on_id]"
            depends_on_id TEXT,              -- foreign key to another manifold_entry
            -- Financial implication
            financial_impact_usd REAL DEFAULT 0,  -- positive = revenue/savings, negative = cost
            confidence REAL DEFAULT 0.5,     -- 0.0 - 1.0 how confident we are
            is_resolved BOOLEAN DEFAULT 0,
            resolved_by TEXT,
            resolved_at TEXT,
            -- Snapshot: what did we know and when?
            known_at TEXT DEFAULT (datetime('now')),
            known_by TEXT,                   -- person or agent who logged this
            superseded_by_id TEXT,           -- if this entry was updated, points to newer entry
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (detail_item_id) REFERENCES detail_items(id)
        );

        -- Change events — when an entry changes, what propagated downstream
        CREATE TABLE IF NOT EXISTS change_events (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_entry_id TEXT NOT NULL,   -- the manifold entry that changed
            affected_entry_id TEXT,          -- the downstream entry affected
            change_type TEXT NOT NULL,       -- change_order | credit | no_impact | info_update
            description TEXT,
            financial_delta_usd REAL DEFAULT 0,  -- positive = credit to client, negative = change order
            caused_by TEXT,                  -- who/what triggered the change
            propagation_depth INTEGER DEFAULT 0,  -- how many levels down the tree
            acknowledged BOOLEAN DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_cb_project ON calendar_blocks(project_id);
        CREATE INDEX IF NOT EXISTS idx_ms_block ON milestones(block_id);
        CREATE INDEX IF NOT EXISTS idx_di_milestone ON detail_items(milestone_id);
        CREATE INDEX IF NOT EXISTS idx_me_detail ON manifold_entries(detail_item_id);
        CREATE INDEX IF NOT EXISTS idx_me_depends ON manifold_entries(depends_on_id);
        CREATE INDEX IF NOT EXISTS idx_ce_project ON change_events(project_id);
        CREATE INDEX IF NOT EXISTS idx_ce_source ON change_events(source_entry_id);
    """)
    conn.commit()
    return conn


@contextmanager
def _db():
    conn = _init_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── ID generators ──────────────────────────────────────────────────────────────
def _id(prefix=""):
    return (prefix + "_" if prefix else "") + str(uuid.uuid4())[:10]


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Projects ───────────────────────────────────────────────────────────────────
def create_project(name: str, client: str = "", description: str = "",
                   budget_usd: float = 0, start_date: str = None,
                   end_date: str = None, color: str = "#00d4ff") -> Dict:
    pid = _id("prj")
    with _db() as conn:
        conn.execute(
            "INSERT INTO projects (id,name,client,description,budget_usd,start_date,end_date,color) VALUES (?,?,?,?,?,?,?,?)",
            (pid, name, client, description, budget_usd, start_date, end_date, color)
        )
    return get_project(pid)


def get_project(project_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(r) if r else None


def list_projects() -> List[Dict]:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY start_date, created_at").fetchall()
    return [dict(r) for r in rows]


def update_project(project_id: str, **kwargs) -> Dict:
    allowed = {"name","client","description","status","budget_usd","start_date","end_date","color"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_project(project_id)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _db() as conn:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id=?", (*fields.values(), project_id))
    return get_project(project_id)


# ── Calendar Blocks ────────────────────────────────────────────────────────────
def create_block(project_id: str, name: str, start_date: str, end_date: str,
                 block_type: str = "sprint", description: str = "",
                 color: str = None, position: int = 0) -> Dict:
    bid = _id("blk")
    with _db() as conn:
        conn.execute(
            "INSERT INTO calendar_blocks (id,project_id,name,description,start_date,end_date,block_type,color,position) VALUES (?,?,?,?,?,?,?,?,?)",
            (bid, project_id, name, description, start_date, end_date, block_type, color, position)
        )
    return get_block(bid)


def get_block(block_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM calendar_blocks WHERE id=?", (block_id,)).fetchone()
        if not r:
            return None
        b = dict(r)
        b["milestones"] = _get_milestones_for_block(conn, block_id, shallow=True)
    return b


def list_blocks(project_id: str = None) -> List[Dict]:
    with _db() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM calendar_blocks WHERE project_id=? ORDER BY start_date, position",
                (project_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM calendar_blocks ORDER BY start_date, position"
            ).fetchall()
        result = []
        for r in rows:
            b = dict(r)
            b["milestones"] = _get_milestones_for_block(conn, r["id"], shallow=True)
            b["milestone_count"] = len(b["milestones"])
            result.append(b)
    return result


def _get_milestones_for_block(conn, block_id: str, shallow: bool = False) -> List[Dict]:
    rows = conn.execute(
        "SELECT * FROM milestones WHERE block_id=? ORDER BY position, due_date",
        (block_id,)
    ).fetchall()
    result = []
    for r in rows:
        m = dict(r)
        if not shallow:
            m["detail_items"] = _get_details_for_milestone(conn, r["id"])
        result.append(m)
    return result


def _get_details_for_milestone(conn, milestone_id: str) -> List[Dict]:
    rows = conn.execute(
        "SELECT * FROM detail_items WHERE milestone_id=? ORDER BY position, created_at",
        (milestone_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Manifold entries for this detail item
        me_rows = conn.execute(
            "SELECT * FROM manifold_entries WHERE detail_item_id=? ORDER BY known_at DESC",
            (r["id"],)
        ).fetchall()
        d["manifold"] = [dict(me) for me in me_rows]
        result.append(d)
    return result


# ── Milestones ─────────────────────────────────────────────────────────────────
def create_milestone(block_id: str, name: str, project_id: str,
                     description: str = "", due_date: str = None,
                     priority: str = "medium", owner: str = "",
                     estimated_hours: float = 0, estimated_cost_usd: float = 0,
                     position: int = 0) -> Dict:
    mid = _id("ms")
    with _db() as conn:
        conn.execute(
            """INSERT INTO milestones
               (id,block_id,project_id,name,description,due_date,priority,owner,
                estimated_hours,estimated_cost_usd,position)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, block_id, project_id, name, description, due_date, priority,
             owner, estimated_hours, estimated_cost_usd, position)
        )
    return get_milestone(mid)


def get_milestone(milestone_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM milestones WHERE id=?", (milestone_id,)).fetchone()
        if not r:
            return None
        m = dict(r)
        m["detail_items"] = _get_details_for_milestone(conn, milestone_id)
    return m


def update_milestone(milestone_id: str, **kwargs) -> Dict:
    allowed = {"name","description","status","due_date","priority","owner",
               "estimated_hours","actual_hours","estimated_cost_usd","actual_cost_usd","position"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _db() as conn:
        conn.execute(f"UPDATE milestones SET {set_clause} WHERE id=?", (*fields.values(), milestone_id))
    return get_milestone(milestone_id)


# ── Detail Items ───────────────────────────────────────────────────────────────
def create_detail_item(milestone_id: str, name: str, project_id: str,
                       block_id: str, item_type: str = "task",
                       description: str = "", owner: str = "",
                       due_date: str = None, estimated_hours: float = 0,
                       position: int = 0, parent_item_id: str = None) -> Dict:
    did = _id("di")
    with _db() as conn:
        conn.execute(
            """INSERT INTO detail_items
               (id,milestone_id,block_id,project_id,name,item_type,description,
                owner,due_date,estimated_hours,position,parent_item_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (did, milestone_id, block_id, project_id, name, item_type,
             description, owner, due_date, estimated_hours, position, parent_item_id)
        )
    return get_detail_item(did)


def get_detail_item(item_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM detail_items WHERE id=?", (item_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        me_rows = conn.execute(
            "SELECT * FROM manifold_entries WHERE detail_item_id=? ORDER BY known_at DESC",
            (item_id,)
        ).fetchall()
        d["manifold"] = [dict(me) for me in me_rows]
    return d


def update_detail_item(item_id: str, **kwargs) -> Dict:
    allowed = {"name","item_type","description","status","owner","due_date",
               "estimated_hours","actual_hours","position"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with _db() as conn:
        conn.execute(f"UPDATE detail_items SET {set_clause} WHERE id=?", (*fields.values(), item_id))
    return get_detail_item(item_id)


# ── Manifold Entries ───────────────────────────────────────────────────────────
def add_manifold_entry(detail_item_id: str, entry_type: str, title: str,
                       body: str = "", depends_on_id: str = None,
                       financial_impact_usd: float = 0, confidence: float = 0.5,
                       known_by: str = "system", milestone_id: str = None,
                       project_id: str = None) -> Dict:
    """Add a knowledge entry to a detail item."""
    # Look up context if not provided
    with _db() as conn:
        di = conn.execute("SELECT * FROM detail_items WHERE id=?", (detail_item_id,)).fetchone()
        if not di:
            return {"error": "detail_item not found"}
        mid = milestone_id or di["milestone_id"]
        pid = project_id or di["project_id"]

    eid = _id("me")
    with _db() as conn:
        conn.execute(
            """INSERT INTO manifold_entries
               (id,detail_item_id,milestone_id,project_id,entry_type,title,body,
                depends_on_id,financial_impact_usd,confidence,known_by,version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
            (eid, detail_item_id, mid, pid, entry_type, title, body,
             depends_on_id, financial_impact_usd, confidence, known_by)
        )
    logger.info("ManifoldEntry %s added (%s): %s", eid, entry_type, title[:50])
    return get_manifold_entry(eid)


def get_manifold_entry(entry_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM manifold_entries WHERE id=?", (entry_id,)).fetchone()
    return dict(r) if r else None


def resolve_entry(entry_id: str, resolved_by: str, actual_body: str = None,
                  new_financial_impact: float = None) -> Dict:
    """Mark an info_gap or assumption as resolved — triggers change propagation."""
    now = _now()
    with _db() as conn:
        entry = conn.execute("SELECT * FROM manifold_entries WHERE id=?", (entry_id,)).fetchone()
        if not entry:
            return {"error": "not found"}
        old_impact = entry["financial_impact_usd"]
        update_vals = {"is_resolved": 1, "resolved_by": resolved_by, "resolved_at": now}
        if actual_body:
            update_vals["body"] = actual_body
        if new_financial_impact is not None:
            update_vals["financial_impact_usd"] = new_financial_impact
        set_clause = ", ".join(f"{k}=?" for k in update_vals)
        conn.execute(f"UPDATE manifold_entries SET {set_clause} WHERE id=?",
                     (*update_vals.values(), entry_id))

    # Propagate change downstream
    new_impact = new_financial_impact if new_financial_impact is not None else old_impact
    if new_impact != old_impact:
        _propagate_change(entry_id, old_impact, new_impact, resolved_by, depth=0)

    return get_manifold_entry(entry_id)


def _propagate_change(source_id: str, old_impact: float, new_impact: float,
                      caused_by: str, depth: int = 0):
    """Recursively find all entries that depend on source_id and log change events."""
    if depth > 10:  # safety cap
        return
    delta = new_impact - old_impact
    with _db() as conn:
        # Find all entries that directly depend on this one
        dependents = conn.execute(
            "SELECT * FROM manifold_entries WHERE depends_on_id=? AND superseded_by_id IS NULL",
            (source_id,)
        ).fetchall()

        for dep in dependents:
            # Determine change type
            if abs(delta) < 0.01:
                change_type = "no_impact"
            elif delta > 0:
                # Parent became more valuable/expensive — downstream is a change_order if cost
                change_type = "change_order" if dep["financial_impact_usd"] < 0 else "credit"
            else:
                # Parent became cheaper/less — downstream is a credit
                change_type = "credit"

            evt_id = _id("ce")
            conn.execute(
                """INSERT INTO change_events
                   (id,project_id,source_entry_id,affected_entry_id,change_type,
                    description,financial_delta_usd,caused_by,propagation_depth)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (evt_id, dep["project_id"], source_id, dep["id"], change_type,
                 f"Upstream '{dep['title'][:50]}' changed: ${old_impact:.2f}→${new_impact:.2f}",
                 delta, caused_by, depth)
            )
            logger.info("Change propagated: %s → %s (%s, $%.2f)", source_id, dep["id"], change_type, delta)
            # Recurse
            _propagate_change(dep["id"], dep["financial_impact_usd"],
                               dep["financial_impact_usd"] + delta * 0.8,  # dampening
                               caused_by, depth + 1)


# ── Change Events ──────────────────────────────────────────────────────────────
def get_change_events(project_id: str = None, unacknowledged_only: bool = False,
                      limit: int = 100) -> List[Dict]:
    with _db() as conn:
        q = "SELECT * FROM change_events"
        params = []
        clauses = []
        if project_id:
            clauses.append("project_id=?"); params.append(project_id)
        if unacknowledged_only:
            clauses.append("acknowledged=0")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def acknowledge_change(event_id: str, acknowledged_by: str) -> Dict:
    now = _now()
    with _db() as conn:
        conn.execute(
            "UPDATE change_events SET acknowledged=1,acknowledged_by=?,acknowledged_at=? WHERE id=?",
            (acknowledged_by, now, event_id)
        )
        r = conn.execute("SELECT * FROM change_events WHERE id=?", (event_id,)).fetchone()
    return dict(r) if r else {}


# ── Full project tree (for UI) ─────────────────────────────────────────────────
def get_project_tree(project_id: str) -> Dict:
    """Return full nested tree: project → blocks → milestones → details → manifold."""
    project = get_project(project_id)
    if not project:
        return {"error": "not found"}
    with _db() as conn:
        blocks = conn.execute(
            "SELECT * FROM calendar_blocks WHERE project_id=? ORDER BY start_date, position",
            (project_id,)
        ).fetchall()
        result_blocks = []
        for b in blocks:
            block = dict(b)
            block["milestones"] = _get_milestones_for_block(conn, b["id"], shallow=False)
            result_blocks.append(block)
    project["blocks"] = result_blocks

    # Change event summary
    with _db() as conn:
        ce = conn.execute(
            """SELECT change_type, COUNT(*) as c, SUM(ABS(financial_delta_usd)) as total
               FROM change_events WHERE project_id=? AND acknowledged=0
               GROUP BY change_type""", (project_id,)
        ).fetchall()
    project["pending_changes"] = [dict(r) for r in ce]
    return project


# ── Seed demo project ──────────────────────────────────────────────────────────
def _seed_demo():
    with _db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if existing > 0:
            return

    import datetime as dt
    today = dt.date.today()
    def d(offset_days):
        return (today + dt.timedelta(days=offset_days)).isoformat()

    p = create_project(
        name="Murphy Platform v2 Launch",
        client="Inoni LLC",
        description="Full platform launch: UI polish, billing, compliance, go-to-market",
        budget_usd=45000,
        start_date=d(0), end_date=d(90),
        color="#00d4ff"
    )
    pid = p["id"]

    # Block 1: Discovery & Scoping
    b1 = create_block(pid, "Discovery & Scoping", d(0), d(14),
                      block_type="phase", color="#a855f7", position=0)
    m1a = create_milestone(b1["id"], "Stakeholder Requirements", pid,
                           description="Define what each stakeholder needs from v2",
                           due_date=d(7), priority="critical",
                           estimated_hours=16, estimated_cost_usd=2400, position=0)
    m1b = create_milestone(b1["id"], "Tech Feasibility", pid,
                           description="Confirm backend can support all requirements",
                           due_date=d(12), priority="high",
                           estimated_hours=8, estimated_cost_usd=1200, position=1)

    di1a = create_detail_item(m1a["id"], "What does the client need in billing?",
                               pid, b1["id"], item_type="question",
                               description="Define billing requirements before any dev starts", position=0)
    add_manifold_entry(di1a["id"], "info_gap",
                       "In order to know billing scope, I first need to know: does client need per-seat or usage-based pricing?",
                       body="Currently unknown — client meeting scheduled for "+d(3),
                       financial_impact_usd=-800, confidence=0.3, known_by="cpost")
    add_manifold_entry(di1a["id"], "assumption",
                       "Assuming usage-based pricing (Stripe metered billing)",
                       body="Based on initial call notes — not confirmed",
                       financial_impact_usd=-1200, confidence=0.6, known_by="cpost")

    di1b = create_detail_item(m1a["id"], "GDPR consent flow required?",
                               pid, b1["id"], item_type="question",
                               description="Determines compliance scope", position=1)
    add_manifold_entry(di1b["id"], "assumption",
                       "Assuming EU customers present — GDPR applies",
                       body="Client has EU users per CRM data",
                       financial_impact_usd=-600, confidence=0.8, known_by="cpost")

    di1c = create_detail_item(m1b["id"], "API rate limits acceptable for swarm?",
                               pid, b1["id"], item_type="task",
                               description="Verify DeepInfra + NewsAPI limits under load", position=0)
    add_manifold_entry(di1c["id"], "actual",
                       "DeepInfra: 60 req/min confirmed — sufficient for current swarm",
                       body="Tested 2026-05-01. 9 agents × 1 req/30s = 18/min peak.",
                       financial_impact_usd=0, confidence=0.95, known_by="system")

    # Block 2: Build Sprint 1
    b2 = create_block(pid, "Build Sprint 1 — Core", d(14), d(35),
                      block_type="sprint", color="#00ff88", position=1)
    m2a = create_milestone(b2["id"], "Billing Integration", pid,
                           description="Stripe metered billing, tier enforcement",
                           due_date=d(28), priority="critical",
                           estimated_hours=24, estimated_cost_usd=3600, position=0)
    m2b = create_milestone(b2["id"], "WorkOps Center", pid,
                           description="Workflow pickup/putdown system with ROI tracking",
                           due_date=d(35), priority="high",
                           estimated_hours=20, estimated_cost_usd=3000, position=1)

    di2a = create_detail_item(m2a["id"], "Stripe webhook secret configured?",
                               pid, b2["id"], item_type="task",
                               description="Required before any billing tests", position=0)
    e_stripe = add_manifold_entry(di2a["id"], "actual",
                       "STRIPE_WEBHOOK_SECRET set in /etc/murphy-production/environment",
                       body="Set 2026-05-02. Both live and test secrets configured.",
                       financial_impact_usd=0, confidence=1.0, known_by="system")

    di2b = create_detail_item(m2a["id"], "Per-seat vs usage pricing decision",
                               pid, b2["id"], item_type="decision",
                               description="Blocks all Stripe product creation",
                               depends_on=di1a["id"], position=1)
    e_pricing = add_manifold_entry(di2b["id"], "info_gap",
                       "In order to know which Stripe products to create, I first need to know: pricing model decision from stakeholder meeting",
                       body="Blocked — waiting on "+d(3)+" meeting",
                       depends_on_id=e_stripe["id"],
                       financial_impact_usd=-2400, confidence=0.2, known_by="cpost")

    # Block 3: Go-to-Market
    b3 = create_block(pid, "Go-to-Market", d(60), d(90),
                      block_type="phase", color="#ffb400", position=2)
    m3a = create_milestone(b3["id"], "Launch Landing Page", pid,
                           description="Dynamic pricing + conversion copy",
                           due_date=d(75), priority="high",
                           estimated_hours=12, estimated_cost_usd=1800, position=0)
    di3a = create_detail_item(m3a["id"], "Final pricing confirmed for landing page?",
                               pid, b3["id"], item_type="question",
                               description="Landing page can't be finalized until pricing is locked", position=0)
    add_manifold_entry(di3a["id"], "info_gap",
                       "In order to know landing page pricing, I first need to know: per-seat vs usage decision",
                       body="Depends on billing decision — 2 levels up",
                       depends_on_id=e_pricing["id"],
                       financial_impact_usd=-1800, confidence=0.2, known_by="cpost")

    logger.info("Manifold: demo project seeded — %s", pid)


try:
    _seed_demo()
except Exception as e:
    logger.warning("Manifold seed error: %s", e)
