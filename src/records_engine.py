"""
records_engine.py — PATCH-182
Assembly Records Engine.

Guiding Principles applied (see patch182_principles_gate.md):
  Admin lane  = governance records (decisions, approvals, audits, change orders, credits)
  Production lane = execution records (build logs, test results, deliveries, specs, handoffs)

A Record is a structured knowledge artifact — it captures what was known,
by whom, when, under what assumptions, and with what financial implications.

A Product is a deliverable that requires a specific set of approved records
before it can be marked complete and shipped.

Every record write:
  1. Saves to records_assembly.db
  2. Auto-creates a Manifold entry (knowledge layer) if project_id present
  3. If financial_impact changes on an approved record → fires change propagation
"""

import sqlite3, json, uuid, logging, os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger("murphy.records_engine")
DB_PATH = "/var/lib/murphy-production/records_assembly.db"


# ── Record Type Catalog ────────────────────────────────────────────────────────
# These are the seed definitions. Never deleted. Fields define the assembly form.
# field schema: {"key": str, "label": str, "type": input|textarea|select|date|number|boolean,
#                "required": bool, "options": [...], "placeholder": str}

RECORD_TYPE_CATALOG = {
    # ── ADMIN LANE ─────────────────────────────────────────────────────────────
    "decision_record": {
        "id": "decision_record",
        "lane": "admin",
        "name": "Decision Record",
        "icon": "⚖️",
        "description": "Documents a key decision — what was decided, by whom, why, and what it cost",
        "color": "#ffb400",
        "requires_approval": True,
        "fields": [
            {"key": "decision_statement", "label": "Decision Statement",      "type": "textarea",  "required": True,  "placeholder": "We decided to…"},
            {"key": "decided_by",         "label": "Decided By",              "type": "input",     "required": True,  "placeholder": "Name / role"},
            {"key": "decision_date",      "label": "Decision Date",           "type": "date",      "required": True},
            {"key": "rationale",          "label": "Rationale",               "type": "textarea",  "required": True,  "placeholder": "Because…"},
            {"key": "alternatives",       "label": "Alternatives Considered", "type": "textarea",  "required": False, "placeholder": "We also considered…"},
            {"key": "financial_impact",   "label": "Financial Impact ($)",    "type": "number",    "required": False, "placeholder": "0"},
            {"key": "reversible",         "label": "Reversible?",             "type": "select",    "required": True,  "options": ["Yes","No","Partially"]},
            {"key": "affects_client",     "label": "Affects Client?",         "type": "select",    "required": True,  "options": ["Yes","No"]},
            {"key": "linked_items",       "label": "Linked Items / IDs",      "type": "input",     "required": False, "placeholder": "ms_xxx, di_xxx"},
        ]
    },
    "approval_record": {
        "id": "approval_record",
        "lane": "admin",
        "name": "Approval Record",
        "icon": "✅",
        "description": "Formal approval of a deliverable, change, or expenditure",
        "color": "#ffb400",
        "requires_approval": True,
        "fields": [
            {"key": "what_is_approved",   "label": "What Is Being Approved",  "type": "textarea",  "required": True},
            {"key": "approved_by",        "label": "Approved By",             "type": "input",     "required": True},
            {"key": "approval_date",      "label": "Approval Date",           "type": "date",      "required": True},
            {"key": "conditions",         "label": "Conditions / Caveats",    "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Approved Amount ($)",     "type": "number",    "required": False, "placeholder": "0"},
            {"key": "expires",            "label": "Approval Expires",        "type": "date",      "required": False},
            {"key": "scope_locked",       "label": "Scope Locked?",           "type": "select",    "required": True,  "options": ["Yes","No"]},
        ]
    },
    "audit_record": {
        "id": "audit_record",
        "lane": "admin",
        "name": "Audit Record",
        "icon": "📋",
        "description": "Audit findings — what was checked, what was found, risk level, remediation",
        "color": "#ffb400",
        "requires_approval": False,
        "fields": [
            {"key": "audit_scope",        "label": "Audit Scope",             "type": "textarea",  "required": True},
            {"key": "auditor",            "label": "Auditor",                 "type": "input",     "required": True},
            {"key": "audit_date",         "label": "Audit Date",              "type": "date",      "required": True},
            {"key": "findings",           "label": "Findings",                "type": "textarea",  "required": True},
            {"key": "risk_level",         "label": "Risk Level",              "type": "select",    "required": True,  "options": ["Critical","High","Medium","Low","None"]},
            {"key": "remediation",        "label": "Remediation Required",    "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Financial Exposure ($)",  "type": "number",    "required": False},
            {"key": "next_audit_date",    "label": "Next Audit Date",         "type": "date",      "required": False},
        ]
    },
    "change_order": {
        "id": "change_order",
        "lane": "admin",
        "name": "Change Order",
        "icon": "🔄",
        "description": "Formal change order — what changed from scope, cost impact, client acknowledgment",
        "color": "#ff4466",
        "requires_approval": True,
        "fields": [
            {"key": "change_description", "label": "What Changed",            "type": "textarea",  "required": True},
            {"key": "original_scope",     "label": "Original Scope",          "type": "textarea",  "required": True},
            {"key": "new_scope",          "label": "New / Amended Scope",     "type": "textarea",  "required": True},
            {"key": "reason",             "label": "Reason for Change",       "type": "textarea",  "required": True},
            {"key": "financial_impact",   "label": "Additional Cost ($)",     "type": "number",    "required": True,  "placeholder": "positive = client pays more"},
            {"key": "time_impact_days",   "label": "Schedule Impact (days)",  "type": "number",    "required": False},
            {"key": "raised_by",          "label": "Raised By",               "type": "input",     "required": True},
            {"key": "client_acknowledged","label": "Client Acknowledged?",    "type": "select",    "required": True,  "options": ["Pending","Yes","No","Disputed"]},
            {"key": "acknowledgment_date","label": "Acknowledgment Date",     "type": "date",      "required": False},
        ]
    },
    "credit_memo": {
        "id": "credit_memo",
        "lane": "admin",
        "name": "Credit Memo",
        "icon": "💚",
        "description": "Credit to client — value returned, goodwill, over-delivery. Improves the relationship.",
        "color": "#00ff88",
        "requires_approval": True,
        "fields": [
            {"key": "credit_description", "label": "What Is Being Credited",  "type": "textarea",  "required": True},
            {"key": "credit_reason",      "label": "Reason for Credit",       "type": "textarea",  "required": True,  "placeholder": "We came in under budget / delivered ahead of schedule…"},
            {"key": "credit_amount",      "label": "Credit Amount ($)",       "type": "number",    "required": True,  "placeholder": "negative = client pays less"},
            {"key": "financial_impact",   "label": "Net Financial Impact ($)","type": "number",    "required": True},
            {"key": "raised_by",          "label": "Raised By",               "type": "input",     "required": True},
            {"key": "client_notified",    "label": "Client Notified?",        "type": "select",    "required": True,  "options": ["Pending","Yes","No"]},
            {"key": "goodwill_note",      "label": "Goodwill Note to Client", "type": "textarea",  "required": False},
        ]
    },
    "risk_register_entry": {
        "id": "risk_register_entry",
        "lane": "admin",
        "name": "Risk Register Entry",
        "icon": "⚠️",
        "description": "A risk that has been identified, assessed, and assigned a mitigation",
        "color": "#ffb400",
        "requires_approval": False,
        "fields": [
            {"key": "risk_title",         "label": "Risk Title",              "type": "input",     "required": True},
            {"key": "risk_description",   "label": "Risk Description",        "type": "textarea",  "required": True},
            {"key": "likelihood",         "label": "Likelihood",              "type": "select",    "required": True,  "options": ["Near Certain","Likely","Possible","Unlikely","Rare"]},
            {"key": "impact",             "label": "Impact",                  "type": "select",    "required": True,  "options": ["Catastrophic","Major","Moderate","Minor","Negligible"]},
            {"key": "financial_impact",   "label": "Financial Exposure ($)",  "type": "number",    "required": False},
            {"key": "mitigation",         "label": "Mitigation Strategy",     "type": "textarea",  "required": True},
            {"key": "owner",              "label": "Risk Owner",              "type": "input",     "required": True},
            {"key": "review_date",        "label": "Review Date",             "type": "date",      "required": False},
        ]
    },
    # ── PRODUCTION LANE ────────────────────────────────────────────────────────
    "build_log": {
        "id": "build_log",
        "lane": "production",
        "name": "Build Log",
        "icon": "🔨",
        "description": "What was built, how, how long it took, and what was produced",
        "color": "#00d4ff",
        "requires_approval": False,
        "fields": [
            {"key": "what_was_built",     "label": "What Was Built",          "type": "textarea",  "required": True},
            {"key": "method",             "label": "Method / Approach",       "type": "textarea",  "required": True},
            {"key": "built_by",           "label": "Built By",                "type": "input",     "required": True},
            {"key": "build_date",         "label": "Build Date",              "type": "date",      "required": True},
            {"key": "time_spent_hours",   "label": "Time Spent (hours)",      "type": "number",    "required": True,  "placeholder": "0.0"},
            {"key": "output_artifact",    "label": "Output / Artifact URL",   "type": "input",     "required": False, "placeholder": "https://… or file path"},
            {"key": "financial_impact",   "label": "Cost ($)",                "type": "number",    "required": False, "placeholder": "labour + materials"},
            {"key": "blockers",           "label": "Blockers Encountered",    "type": "textarea",  "required": False},
            {"key": "next_step",          "label": "Next Step",               "type": "input",     "required": False},
        ]
    },
    "test_result": {
        "id": "test_result",
        "lane": "production",
        "name": "Test Result",
        "icon": "🧪",
        "description": "What was tested, the result, evidence, and whether it passes",
        "color": "#00d4ff",
        "requires_approval": False,
        "fields": [
            {"key": "what_was_tested",    "label": "What Was Tested",         "type": "textarea",  "required": True},
            {"key": "test_method",        "label": "Test Method",             "type": "textarea",  "required": True},
            {"key": "tested_by",          "label": "Tested By",               "type": "input",     "required": True},
            {"key": "test_date",          "label": "Test Date",               "type": "date",      "required": True},
            {"key": "result",             "label": "Result",                  "type": "select",    "required": True,  "options": ["Pass","Fail","Pass with conditions","Deferred"]},
            {"key": "evidence",           "label": "Evidence / Screenshot URL","type":"input",     "required": False},
            {"key": "conditions",         "label": "Conditions / Notes",      "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Rework Cost ($)",         "type": "number",    "required": False, "placeholder": "0 if pass"},
        ]
    },
    "delivery_note": {
        "id": "delivery_note",
        "lane": "production",
        "name": "Delivery Note",
        "icon": "📦",
        "description": "What was delivered, to whom, when, and whether it was accepted",
        "color": "#00d4ff",
        "requires_approval": False,
        "fields": [
            {"key": "what_was_delivered", "label": "What Was Delivered",      "type": "textarea",  "required": True},
            {"key": "delivered_to",       "label": "Delivered To",            "type": "input",     "required": True},
            {"key": "delivery_date",      "label": "Delivery Date",           "type": "date",      "required": True},
            {"key": "delivery_method",    "label": "Delivery Method",         "type": "input",     "required": False, "placeholder": "email / deploy / handoff"},
            {"key": "acceptance_status",  "label": "Acceptance Status",       "type": "select",    "required": True,  "options": ["Pending","Accepted","Rejected","Accepted with conditions"]},
            {"key": "financial_impact",   "label": "Billable Value ($)",      "type": "number",    "required": False},
            {"key": "rejection_reason",   "label": "Rejection Reason",        "type": "textarea",  "required": False},
        ]
    },
    "spec_sheet": {
        "id": "spec_sheet",
        "lane": "production",
        "name": "Spec Sheet",
        "icon": "📐",
        "description": "What the product must do — requirements and acceptance criteria",
        "color": "#00d4ff",
        "requires_approval": True,
        "fields": [
            {"key": "product_name",       "label": "Product / Feature Name",  "type": "input",     "required": True},
            {"key": "purpose",            "label": "Purpose / Problem Solved", "type": "textarea", "required": True},
            {"key": "requirements",       "label": "Requirements (one per line)","type":"textarea", "required": True},
            {"key": "acceptance_criteria","label": "Acceptance Criteria",     "type": "textarea",  "required": True},
            {"key": "out_of_scope",       "label": "Out of Scope",            "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Estimated Build Cost ($)","type": "number",    "required": False},
            {"key": "approved_by",        "label": "Approved By",             "type": "input",     "required": False},
        ]
    },
    "work_order": {
        "id": "work_order",
        "lane": "production",
        "name": "Work Order",
        "icon": "📋",
        "description": "A task assigned to a person or agent — deadline, dependencies, done criteria",
        "color": "#00d4ff",
        "requires_approval": False,
        "fields": [
            {"key": "task_title",         "label": "Task Title",              "type": "input",     "required": True},
            {"key": "task_description",   "label": "Full Description",        "type": "textarea",  "required": True},
            {"key": "assigned_to",        "label": "Assigned To",             "type": "input",     "required": True},
            {"key": "assigned_by",        "label": "Assigned By",             "type": "input",     "required": True},
            {"key": "due_date",           "label": "Due Date",                "type": "date",      "required": True},
            {"key": "priority",           "label": "Priority",                "type": "select",    "required": True,  "options": ["Critical","High","Medium","Low"]},
            {"key": "estimated_hours",    "label": "Estimated Hours",         "type": "number",    "required": False},
            {"key": "financial_impact",   "label": "Labour Cost ($)",         "type": "number",    "required": False},
            {"key": "done_when",          "label": "Done When…",              "type": "textarea",  "required": True,  "placeholder": "This task is complete when…"},
            {"key": "dependencies",       "label": "Depends On",              "type": "input",     "required": False},
        ]
    },
    "handoff_record": {
        "id": "handoff_record",
        "lane": "production",
        "name": "Handoff Record",
        "icon": "🤝",
        "description": "State at the moment of handoff between agents or people",
        "color": "#00d4ff",
        "requires_approval": False,
        "fields": [
            {"key": "from_agent",         "label": "Handed From",             "type": "input",     "required": True},
            {"key": "to_agent",           "label": "Handed To",               "type": "input",     "required": True},
            {"key": "handoff_date",       "label": "Handoff Date",            "type": "date",      "required": True},
            {"key": "what_was_passed",    "label": "What Was Passed",         "type": "textarea",  "required": True},
            {"key": "state_at_handoff",   "label": "State at Handoff",        "type": "textarea",  "required": True,  "placeholder": "What was done, what is still open…"},
            {"key": "open_items",         "label": "Open Items / Risks",      "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Value at Handoff ($)",    "type": "number",    "required": False},
            {"key": "accepted_by_receiver","label": "Accepted by Receiver?",  "type": "select",    "required": True,  "options": ["Yes","No","Pending"]},
        ]
    },
    "sign_off_record": {
        "id": "sign_off_record",
        "lane": "production",
        "name": "Client Sign-Off",
        "icon": "✍️",
        "description": "Client acceptance of a deliverable — the final gate before closure",
        "color": "#00ff88",
        "requires_approval": True,
        "fields": [
            {"key": "deliverable",        "label": "Deliverable Signed Off",  "type": "textarea",  "required": True},
            {"key": "signed_by",          "label": "Signed By (Client)",      "type": "input",     "required": True},
            {"key": "sign_off_date",      "label": "Sign-Off Date",           "type": "date",      "required": True},
            {"key": "conditions",         "label": "Conditions / Punch List", "type": "textarea",  "required": False},
            {"key": "financial_impact",   "label": "Billable on Sign-Off ($)","type": "number",    "required": False},
            {"key": "warranty_period",    "label": "Warranty / Support Period","type":"input",     "required": False},
            {"key": "next_milestone",     "label": "Triggers Next Milestone", "type": "input",     "required": False},
        ]
    },
}


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            record_type_id TEXT NOT NULL,
            lane TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft',   -- draft | in_review | approved | superseded | rejected
            project_id TEXT,
            block_id TEXT,
            milestone_id TEXT,
            detail_item_id TEXT,
            product_id TEXT,
            fields_json TEXT DEFAULT '{}',
            financial_impact_usd REAL DEFAULT 0,
            version INTEGER DEFAULT 1,
            previous_version_id TEXT,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            approved_by TEXT,
            approved_at TEXT,
            has_open_gaps INTEGER DEFAULT 0,
            manifold_entry_id TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            project_id TEXT,
            block_id TEXT,
            milestone_id TEXT,
            status TEXT DEFAULT 'assembling',  -- assembling | review | complete | shipped | rejected
            completion_pct REAL DEFAULT 0,
            total_financial_impact_usd REAL DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            shipped_at TEXT,
            shipped_by TEXT
        );

        CREATE TABLE IF NOT EXISTS product_requirements (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            record_type_id TEXT NOT NULL,
            required INTEGER DEFAULT 1,
            fulfilled_by_record_id TEXT,
            fulfilled_at TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS assembly_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            event_type TEXT,
            record_id TEXT,
            product_id TEXT,
            agent_id TEXT,
            message TEXT,
            data_json TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_rec_type ON records(record_type_id);
        CREATE INDEX IF NOT EXISTS idx_rec_project ON records(project_id);
        CREATE INDEX IF NOT EXISTS idx_rec_product ON records(product_id);
        CREATE INDEX IF NOT EXISTS idx_prod_project ON products(project_id);
        CREATE INDEX IF NOT EXISTS idx_pr_product ON product_requirements(product_id);
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


def _id(prefix=""):
    return (prefix + "_" if prefix else "") + str(uuid.uuid4())[:10]


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Record Type Catalog ────────────────────────────────────────────────────────

def get_record_types(lane: str = None) -> List[Dict]:
    if lane:
        return [v for v in RECORD_TYPE_CATALOG.values() if v["lane"] == lane]
    return list(RECORD_TYPE_CATALOG.values())


def get_record_type(type_id: str) -> Optional[Dict]:
    return RECORD_TYPE_CATALOG.get(type_id)


# ── Records ────────────────────────────────────────────────────────────────────

def create_record(record_type_id: str, title: str, fields: Dict,
                  created_by: str = "system", project_id: str = None,
                  block_id: str = None, milestone_id: str = None,
                  detail_item_id: str = None, product_id: str = None) -> Dict:
    """Create a new record in draft status."""
    rt = get_record_type(record_type_id)
    if not rt:
        return {"error": f"Unknown record type: {record_type_id}"}

    rid = _id("rec")
    lane = rt["lane"]
    financial_impact = float(fields.get("financial_impact", 0) or 0)

    # Check for open info gaps — fields left blank that are required
    missing_required = [
        f["key"] for f in rt["fields"]
        if f.get("required") and not fields.get(f["key"])
    ]
    has_gaps = 1 if missing_required else 0

    with _db() as conn:
        conn.execute(
            """INSERT INTO records
               (id,record_type_id,lane,title,status,project_id,block_id,
                milestone_id,detail_item_id,product_id,fields_json,
                financial_impact_usd,created_by,has_open_gaps)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, record_type_id, lane, title, "draft", project_id, block_id,
             milestone_id, detail_item_id, product_id,
             json.dumps(fields), financial_impact, created_by, has_gaps)
        )
        conn.execute(
            """INSERT INTO assembly_log (event_type,record_id,product_id,agent_id,message)
               VALUES (?,?,?,?,?)""",
            ("record_created", rid, product_id, created_by,
             f"[{lane.upper()}] {rt['name']}: '{title}' created as draft")
        )
        # Fulfill product requirement if linked
        if product_id:
            conn.execute(
                """UPDATE product_requirements
                   SET fulfilled_by_record_id=?, fulfilled_at=?
                   WHERE product_id=? AND record_type_id=? AND fulfilled_by_record_id IS NULL""",
                (rid, _now(), product_id, record_type_id)
            )
            _recalc_product_completion(conn, product_id)

    # Write to Manifold if project linked
    if project_id and detail_item_id:
        try:
            from src.manifold import add_manifold_entry as _ame
            me = _ame(detail_item_id, "actual" if not has_gaps else "assumption",
                     f"[{rt['name']}] {title}",
                     body=json.dumps(fields, indent=2)[:500],
                     financial_impact_usd=financial_impact,
                     confidence=0.9 if not has_gaps else 0.5,
                     known_by=created_by)
            with _db() as conn:
                conn.execute("UPDATE records SET manifold_entry_id=? WHERE id=?",
                             (me.get("id"), rid))
        except Exception as e:
            logger.debug("Manifold link skipped: %s", e)

    logger.info("Record %s created: [%s] %s", rid, record_type_id, title)
    return get_record(rid)


def get_record(record_id: str) -> Optional[Dict]:
    with _db() as conn:
        r = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["fields"] = json.loads(d.get("fields_json", "{}"))
    d["record_type"] = get_record_type(d["record_type_id"])
    return d


def list_records(project_id: str = None, lane: str = None,
                 record_type_id: str = None, status: str = None,
                 product_id: str = None, limit: int = 100) -> List[Dict]:
    with _db() as conn:
        clauses, params = [], []
        if project_id:   clauses.append("project_id=?");    params.append(project_id)
        if lane:         clauses.append("lane=?");           params.append(lane)
        if record_type_id: clauses.append("record_type_id=?"); params.append(record_type_id)
        if status:       clauses.append("status=?");         params.append(status)
        if product_id:   clauses.append("product_id=?");    params.append(product_id)
        q = "SELECT * FROM records"
        if clauses: q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["fields"] = json.loads(d.get("fields_json", "{}"))
        d["record_type"] = get_record_type(d["record_type_id"])
        result.append(d)
    return result


def update_record(record_id: str, fields: Dict = None,
                  title: str = None, status: str = None,
                  approved_by: str = None) -> Dict:
    """Update a record. If fields change on an approved record, creates amendment."""
    with _db() as conn:
        existing = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        if not existing:
            return {"error": "Record not found"}
        old_impact = existing["financial_impact_usd"]

    updates = {"updated_at": _now()}
    if title: updates["title"] = title
    if status: updates["status"] = status
    if status == "approved":
        updates["approved_by"] = approved_by or "system"
        updates["approved_at"] = _now()

    if fields:
        rt = get_record_type(existing["record_type_id"])
        missing = [f["key"] for f in (rt["fields"] if rt else [])
                   if f.get("required") and not fields.get(f["key"])]
        updates["fields_json"] = json.dumps(fields)
        updates["has_open_gaps"] = 1 if missing else 0
        new_impact = float(fields.get("financial_impact", 0) or 0)
        updates["financial_impact_usd"] = new_impact

        # Propagate if approved and impact changed
        if existing["status"] == "approved" and abs(new_impact - old_impact) > 0.01:
            _fire_financial_change(existing, old_impact, new_impact)

    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _db() as conn:
        conn.execute(f"UPDATE records SET {set_clause} WHERE id=?",
                     (*updates.values(), record_id))
        if existing["product_id"]:
            _recalc_product_completion(conn, existing["product_id"])

    return get_record(record_id)


def _fire_financial_change(record: Any, old_impact: float, new_impact: float):
    """When a record's financial impact changes, fire to Manifold propagation."""
    delta = new_impact - old_impact
    if record["manifold_entry_id"]:
        try:
            from src.manifold import resolve_entry as _re
            _re(record["manifold_entry_id"], record["created_by"],
                new_financial_impact=new_impact)
        except Exception as e:
            logger.debug("Manifold propagation: %s", e)
    logger.info("Financial change on record %s: $%.2f → $%.2f (Δ$%.2f)",
                record["id"], old_impact, new_impact, delta)


def amend_record(record_id: str, fields: Dict, amended_by: str,
                 reason: str = "") -> Dict:
    """Create a new version of a record. Old version marked superseded."""
    old = get_record(record_id)
    if not old:
        return {"error": "Record not found"}

    new_rid = _id("rec")
    with _db() as conn:
        # Supersede old
        conn.execute("UPDATE records SET status='superseded', updated_at=? WHERE id=?",
                     (_now(), record_id))
        # Create new version
        conn.execute(
            """INSERT INTO records
               (id,record_type_id,lane,title,status,project_id,block_id,
                milestone_id,detail_item_id,product_id,fields_json,
                financial_impact_usd,created_by,version,previous_version_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (new_rid, old["record_type_id"], old["lane"], old["title"],
             "draft", old["project_id"], old["block_id"],
             old["milestone_id"], old["detail_item_id"], old["product_id"],
             json.dumps(fields),
             float(fields.get("financial_impact", 0) or 0),
             amended_by, (old.get("version") or 1) + 1, record_id)
        )
        conn.execute(
            """INSERT INTO assembly_log (event_type,record_id,agent_id,message)
               VALUES (?,?,?,?)""",
            ("record_amended", new_rid, amended_by,
             f"Amendment of {record_id}: {reason}")
        )
        if old["product_id"]:
            # Update requirement fulfillment to new record
            conn.execute(
                """UPDATE product_requirements
                   SET fulfilled_by_record_id=?, fulfilled_at=?
                   WHERE product_id=? AND fulfilled_by_record_id=?""",
                (new_rid, _now(), old["product_id"], record_id)
            )
            _recalc_product_completion(conn, old["product_id"])

    return get_record(new_rid)


# ── Products ───────────────────────────────────────────────────────────────────

def create_product(name: str, description: str = "",
                   project_id: str = None, block_id: str = None,
                   milestone_id: str = None, created_by: str = "system",
                   required_record_types: List[str] = None) -> Dict:
    pid = _id("prd")
    with _db() as conn:
        conn.execute(
            """INSERT INTO products
               (id,name,description,project_id,block_id,milestone_id,created_by)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, name, description, project_id, block_id, milestone_id, created_by)
        )
        for rt_id in (required_record_types or []):
            conn.execute(
                "INSERT INTO product_requirements (id,product_id,record_type_id) VALUES (?,?,?)",
                (_id("pr"), pid, rt_id)
            )
    return get_product(pid)


def get_product(product_id: str) -> Optional[Dict]:
    with _db() as conn:
        p = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not p:
            return None
        prod = dict(p)
        reqs = conn.execute(
            "SELECT * FROM product_requirements WHERE product_id=?", (product_id,)
        ).fetchall()
        prod["requirements"] = []
        for r in reqs:
            req = dict(r)
            req["record_type"] = get_record_type(r["record_type_id"])
            if r["fulfilled_by_record_id"]:
                rec = conn.execute(
                    "SELECT id,title,status,created_at,financial_impact_usd FROM records WHERE id=?",
                    (r["fulfilled_by_record_id"],)
                ).fetchone()
                req["fulfilled_record"] = dict(rec) if rec else None
            else:
                req["fulfilled_record"] = None
            prod["requirements"].append(req)
        prod["can_ship"] = all(r["fulfilled_by_record_id"] is not None for r in reqs if dict(r)["required"])
        prod["completion_pct"] = prod["completion_pct"]
    return prod


def list_products(project_id: str = None) -> List[Dict]:
    with _db() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM products WHERE project_id=? ORDER BY created_at DESC",
                (project_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
    return [get_product(r["id"]) for r in rows]


def ship_product(product_id: str, shipped_by: str) -> Dict:
    prod = get_product(product_id)
    if not prod:
        return {"error": "Product not found"}
    if not prod["can_ship"]:
        missing = [r["record_type"]["name"] for r in prod["requirements"]
                   if not r["fulfilled_by_record_id"] and r["required"]]
        return {"error": f"Cannot ship — missing records: {', '.join(missing)}"}
    with _db() as conn:
        conn.execute(
            "UPDATE products SET status='shipped',shipped_at=?,shipped_by=? WHERE id=?",
            (_now(), shipped_by, product_id)
        )
        conn.execute(
            """INSERT INTO assembly_log (event_type,product_id,agent_id,message)
               VALUES (?,?,?,?)""",
            ("product_shipped", product_id, shipped_by,
             f"Product '{prod['name']}' shipped by {shipped_by}")
        )
    return get_product(product_id)


def _recalc_product_completion(conn, product_id: str):
    reqs = conn.execute(
        "SELECT required, fulfilled_by_record_id FROM product_requirements WHERE product_id=?",
        (product_id,)
    ).fetchall()
    if not reqs:
        return
    total = sum(1 for r in reqs if r["required"])
    done  = sum(1 for r in reqs if r["required"] and r["fulfilled_by_record_id"])
    pct   = round(done / max(total, 1) * 100, 1)
    impact = conn.execute(
        """SELECT SUM(r.financial_impact_usd) FROM records r
           JOIN product_requirements pr ON pr.fulfilled_by_record_id=r.id
           WHERE pr.product_id=?""", (product_id,)
    ).fetchone()[0] or 0
    conn.execute(
        "UPDATE products SET completion_pct=?,total_financial_impact_usd=?,updated_at=? WHERE id=?",
        (pct, impact, _now(), product_id)
    )


def get_assembly_log(product_id: str = None, limit: int = 100) -> List[Dict]:
    with _db() as conn:
        if product_id:
            rows = conn.execute(
                "SELECT * FROM assembly_log WHERE product_id=? ORDER BY timestamp DESC LIMIT ?",
                (product_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assembly_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


# ── Status endpoint ────────────────────────────────────────────────────────────
def get_status() -> Dict:
    try:
        with _db() as conn:
            records_total = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            products_total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            shipped = conn.execute("SELECT COUNT(*) FROM products WHERE status='shipped'").fetchone()[0]
            admin_records = conn.execute("SELECT COUNT(*) FROM records WHERE lane='admin'").fetchone()[0]
            prod_records = conn.execute("SELECT COUNT(*) FROM records WHERE lane='production'").fetchone()[0]
        return {
            "records_total": records_total,
            "admin_records": admin_records,
            "production_records": prod_records,
            "products_total": products_total,
            "products_shipped": shipped,
            "record_types": len(RECORD_TYPE_CATALOG),
        }
    except Exception as e:
        return {"error": str(e)}
