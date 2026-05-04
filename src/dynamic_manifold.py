"""
dynamic_manifold.py — PATCH-184
Dynamic Manifold Engine.

From patch184_principles_gate.md:
  Scans knowledge state → classifies gaps → scores risk →
  generates prescriptions → dispatches corrections →
  tracks resolution → escalates when reckless to auto-resolve.

Gap types:
  KNOWLEDGE  — we don't know something we need to know
  COMPLIANCE — a regulatory/policy requirement is unmet
  FINANCIAL  — a cost/revenue assumption is unconfirmed
  RISK       — a threat exists without a mitigation plan

Risk score formula (deterministic, auditable):
  base     = 1 - confidence
  impact   = min(abs(financial_impact) / 5000, 0.4)
  deps     = min(downstream_count * 0.1, 0.3)
  age      = min(days_old / 30, 0.2)
  score    = min(base * 0.4 + impact + deps + age, 1.0)

Dispatch rules:
  score < 0.4  → LOW    → auto work_order
  score 0.4-0.7→ MEDIUM → work_order + review flag
  score > 0.7  → HIGH   → HITL escalation + freeze downstream
"""

import sqlite3, json, uuid, logging, os, math
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger("murphy.dynamic_manifold")
MANIFOLD_DB = "/var/lib/murphy-production/manifold.db"
GAP_DB      = "/var/lib/murphy-production/manifold.db"  # same DB, new tables


# ── Gap type classifier ────────────────────────────────────────────────────────

COMPLIANCE_KEYWORDS = [
    "gdpr", "hipaa", "pci", "soc2", "iso", "ccpa", "sox", "nist",
    "consent", "regulation", "regulatory", "compliance", "audit",
    "breach", "notify", "notification", "dpa", "data protection",
]
FINANCIAL_KEYWORDS = [
    "cost", "price", "pricing", "budget", "invoice", "payment",
    "billing", "revenue", "contract", "fee", "rate", "charge",
    "estimate", "quote", "scope", "change order", "credit",
]
RISK_KEYWORDS = [
    "risk", "threat", "vulnerability", "exposure", "failure", "down",
    "block", "depend", "critical", "blocker", "unknown", "uncertain",
]

def classify_gap(entry: Dict) -> str:
    text = ((entry.get("title") or "") + " " + (entry.get("body") or "")).lower()
    compliance_hits = sum(1 for kw in COMPLIANCE_KEYWORDS if kw in text)
    financial_hits  = sum(1 for kw in FINANCIAL_KEYWORDS  if kw in text)
    risk_hits       = sum(1 for kw in RISK_KEYWORDS        if kw in text)
    impact = abs(entry.get("financial_impact_usd") or 0)
    if compliance_hits >= 2:                return "COMPLIANCE"
    if financial_hits >= 2 or impact > 500: return "FINANCIAL"
    if risk_hits >= 2:                      return "RISK"
    return "KNOWLEDGE"


def score_risk(entry: Dict, downstream_count: int = 0) -> float:
    """Deterministic risk score 0.0–1.0. Formula in module docstring."""
    confidence = float(entry.get("confidence") or 0.5)
    impact     = abs(float(entry.get("financial_impact_usd") or 0))
    created_at = entry.get("created_at") or entry.get("known_at") or ""

    # Age factor
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - created).days
    except Exception:
        days_old = 0

    base    = (1.0 - confidence) * 0.40
    imp_f   = min(impact / 5000.0, 0.40)
    deps_f  = min(downstream_count * 0.10, 0.30)
    age_f   = min(days_old / 30.0, 0.20)
    score   = min(base + imp_f + deps_f + age_f, 1.0)
    return round(score, 3)


def risk_tier(score: float) -> str:
    if score >= 0.70: return "HIGH"
    if score >= 0.40: return "MEDIUM"
    return "LOW"


# ── Prescription generator ─────────────────────────────────────────────────────

PRESCRIPTION_RULES = {
    "COMPLIANCE": {
        "record_type":    "audit_record",
        "chain_template": "chain_client_onboarding",
        "action":         "Run a compliance audit on this item",
        "who":            "auditor",
        "question":       "What compliance framework governs this, and is the requirement met?",
    },
    "FINANCIAL": {
        "record_type":    "decision_record",
        "chain_template": "chain_revenue_driver",
        "action":         "Confirm the financial assumption with the client or stakeholder",
        "who":            "exec_admin",
        "question":       "What is the confirmed cost/price/budget for this item?",
    },
    "RISK": {
        "record_type":    "risk_register_entry",
        "chain_template": "chain_change_order",
        "action":         "Create a risk register entry and assign a mitigation owner",
        "who":            "auditor",
        "question":       "What is the probability and impact, and what mitigates it?",
    },
    "KNOWLEDGE": {
        "record_type":    "work_order",
        "chain_template": "chain_feature_delivery",
        "action":         "Assign a work order to research and answer this question",
        "who":            "executor",
        "question":       "What do we need to find out, and who can answer it?",
    },
}

def generate_prescription(entry: Dict, gap_type: str, risk_score: float,
                           downstream_count: int) -> Dict:
    rule  = PRESCRIPTION_RULES[gap_type]
    tier  = risk_tier(risk_score)
    title = (entry.get("title") or "")[:80]
    impact = float(entry.get("financial_impact_usd") or 0)

    dispatch_action = {
        "LOW":    "auto_work_order",
        "MEDIUM": "work_order_flagged",
        "HIGH":   "hitl_escalation",
    }[tier]

    reason_parts = []
    if (1.0 - float(entry.get("confidence") or 0.5)) * 0.4 > 0.2:
        reason_parts.append(f"low confidence ({int(float(entry.get('confidence',0.5))*100)}%)")
    if abs(impact) > 500:
        reason_parts.append(f"financial exposure ${abs(impact):,.0f}")
    if downstream_count > 0:
        reason_parts.append(f"{downstream_count} downstream dependents")

    return {
        "gap_type":        gap_type,
        "risk_score":      risk_score,
        "risk_tier":       tier,
        "record_type":     rule["record_type"],
        "chain_template":  rule["chain_template"],
        "action":          rule["action"],
        "who":             rule["who"],
        "question":        rule["question"],
        "dispatch_action": dispatch_action,
        "reason":          " | ".join(reason_parts) if reason_parts else "standard gap",
        "financial_exposure_usd": abs(impact),
        "downstream_count": downstream_count,
        "entry_title":     title,
    }


# ── DB init ────────────────────────────────────────────────────────────────────

def _init_db():
    conn = sqlite3.connect(MANIFOLD_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS gap_prescriptions (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,         -- manifold_entry id
            project_id TEXT,
            gap_type TEXT NOT NULL,         -- KNOWLEDGE | COMPLIANCE | FINANCIAL | RISK
            risk_score REAL NOT NULL,
            risk_tier TEXT NOT NULL,        -- LOW | MEDIUM | HIGH
            prescription_json TEXT NOT NULL,
            dispatch_action TEXT NOT NULL,  -- auto_work_order | work_order_flagged | hitl_escalation
            status TEXT DEFAULT 'open',     -- open | dispatched | fulfilled | cancelled
            dispatched_at TEXT,
            fulfilled_at TEXT,
            downstream_count INTEGER DEFAULT 0,
            financial_exposure_usd REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entry_id) REFERENCES manifold_entries(id)
        );

        CREATE TABLE IF NOT EXISTS gap_escalations (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,
            prescription_id TEXT,
            project_id TEXT,
            risk_score REAL,
            risk_tier TEXT,
            reason TEXT,
            financial_exposure_usd REAL DEFAULT 0,
            status TEXT DEFAULT 'open',     -- open | acknowledged | resolved
            acknowledged_by TEXT,
            acknowledged_at TEXT,
            resolved_by TEXT,
            resolved_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gap_scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT DEFAULT (datetime('now')),
            project_id TEXT,
            entries_scanned INTEGER DEFAULT 0,
            gaps_found INTEGER DEFAULT 0,
            gaps_low INTEGER DEFAULT 0,
            gaps_medium INTEGER DEFAULT 0,
            gaps_high INTEGER DEFAULT 0,
            total_exposure_usd REAL DEFAULT 0,
            prescriptions_created INTEGER DEFAULT 0,
            escalations_created INTEGER DEFAULT 0,
            scan_duration_ms INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_gp_entry  ON gap_prescriptions(entry_id);
        CREATE INDEX IF NOT EXISTS idx_gp_status ON gap_prescriptions(status);
        CREATE INDEX IF NOT EXISTS idx_ge_entry  ON gap_escalations(entry_id);
        CREATE INDEX IF NOT EXISTS idx_ge_status ON gap_escalations(status);
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


# ── Dependency counter ─────────────────────────────────────────────────────────

def count_downstream(entry_id: str, conn, depth: int = 0, visited: set = None) -> int:
    """Count all downstream manifold entries that depend on this one."""
    if depth > 10: return 0
    if visited is None: visited = set()
    if entry_id in visited: return 0
    visited.add(entry_id)
    dependents = conn.execute(
        "SELECT id FROM manifold_entries WHERE depends_on_id=? AND superseded_by_id IS NULL",
        (entry_id,)
    ).fetchall()
    count = len(dependents)
    for dep in dependents:
        count += count_downstream(dep["id"], conn, depth + 1, visited)
    return count


# ── Core scan ─────────────────────────────────────────────────────────────────

def scan_project(project_id: str = None) -> Dict:
    """
    Main scan cycle.
    1. Find all unresolved manifold entries
    2. Classify + score each one
    3. Generate prescription
    4. Dispatch (create record / escalate)
    5. Log scan
    """
    import time
    start_ms = int(time.time() * 1000)

    results = {
        "scanned": 0, "gaps_found": 0,
        "low": 0, "medium": 0, "high": 0,
        "exposure_usd": 0.0,
        "prescriptions_created": 0, "escalations_created": 0,
        "prescriptions": [],
    }

    with _db() as conn:
        # Pull unresolved entries (info_gap + low-confidence assumptions)
        if project_id:
            entries = conn.execute("""
                SELECT me.*, di.milestone_id, di.block_id
                FROM manifold_entries me
                LEFT JOIN detail_items di ON di.id = me.detail_item_id
                WHERE me.project_id=? AND me.superseded_by_id IS NULL
                  AND me.is_resolved=0
                  AND (me.entry_type='info_gap'
                       OR (me.entry_type='assumption' AND me.confidence < 0.65))
                ORDER BY me.created_at
            """, (project_id,)).fetchall()
        else:
            entries = conn.execute("""
                SELECT me.*, di.milestone_id, di.block_id
                FROM manifold_entries me
                LEFT JOIN detail_items di ON di.id = me.detail_item_id
                WHERE me.superseded_by_id IS NULL
                  AND me.is_resolved=0
                  AND (me.entry_type='info_gap'
                       OR (me.entry_type='assumption' AND me.confidence < 0.65))
                ORDER BY me.project_id, me.created_at
            """).fetchall()

        results["scanned"] = len(entries)

        for row in entries:
            entry = dict(row)
            eid   = entry["id"]
            pid   = entry.get("project_id")

            # Check if already has an open prescription
            existing = conn.execute(
                "SELECT id FROM gap_prescriptions WHERE entry_id=? AND status='open'",
                (eid,)
            ).fetchone()
            if existing:
                # Update risk score but don't double-dispatch
                deps = count_downstream(eid, conn)
                score = score_risk(entry, deps)
                conn.execute(
                    "UPDATE gap_prescriptions SET risk_score=?,downstream_count=?,updated_at=? WHERE id=?",
                    (score, deps, _now(), existing["id"])
                )
                results["gaps_found"] += 1
                results["exposure_usd"] += abs(entry.get("financial_impact_usd") or 0)
                tier = risk_tier(score)
                results[tier.lower()] += 1
                continue

            # New gap — full analysis
            deps      = count_downstream(eid, conn)
            gap_type  = classify_gap(entry)
            score     = score_risk(entry, deps)
            tier      = risk_tier(score)
            presc     = generate_prescription(entry, gap_type, score, deps)
            pid_use   = pid or entry.get("project_id") or "unknown"
            presc_id  = _id("gp")

            conn.execute(
                """INSERT INTO gap_prescriptions
                   (id,entry_id,project_id,gap_type,risk_score,risk_tier,
                    prescription_json,dispatch_action,status,
                    downstream_count,financial_exposure_usd)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (presc_id, eid, pid_use, gap_type, score, tier,
                 json.dumps(presc), presc["dispatch_action"],
                 "open", deps, abs(entry.get("financial_impact_usd") or 0))
            )
            results["prescriptions_created"] += 1
            results["gaps_found"] += 1
            results["exposure_usd"] += abs(entry.get("financial_impact_usd") or 0)
            results[tier.lower()] += 1

            # Dispatch
            if tier == "HIGH":
                _dispatch_high(conn, entry, presc, presc_id, pid_use)
                results["escalations_created"] += 1
            elif tier == "MEDIUM":
                _dispatch_medium(conn, entry, presc, presc_id)
            else:
                _dispatch_low(conn, entry, presc, presc_id)

            presc["id"] = presc_id
            presc["entry_id"] = eid
            results["prescriptions"].append(presc)

        # Log the scan
        duration = int(time.time() * 1000) - start_ms
        conn.execute(
            """INSERT INTO gap_scan_log
               (project_id,entries_scanned,gaps_found,gaps_low,gaps_medium,gaps_high,
                total_exposure_usd,prescriptions_created,escalations_created,scan_duration_ms)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (project_id, results["scanned"], results["gaps_found"],
             results["low"], results["medium"], results["high"],
             results["exposure_usd"], results["prescriptions_created"],
             results["escalations_created"], duration)
        )

    logger.info("Gap scan: %d entries, %d gaps (L:%d M:%d H:%d) $%.0f exposure",
                results["scanned"], results["gaps_found"],
                results["low"], results["medium"], results["high"],
                results["exposure_usd"])
    return results


def _dispatch_low(conn, entry: Dict, presc: Dict, presc_id: str):
    """LOW risk: auto-create a work_order record."""
    try:
        from src.records_engine import create_record as _cr
        from datetime import date, timedelta
        due = (date.today() + timedelta(days=7)).isoformat()
        _cr("work_order",
            f"[AUTO] {presc['action'][:60]}",
            {
                "task_title":    f"Close gap: {entry.get('title','')[:60]}",
                "task_description": (
                    "Gap ID: {entry['id']} Type: {presc['gap_type']} Question: {presc['question']} Context: {entry.get('body','')[:300]}",
                ),
                "assigned_to":   presc["who"],
                "assigned_by":   "dynamic_manifold",
                "due_date":      due,
                "priority":      "Medium",
                "estimated_hours": "2",
                "done_when":     f"The gap '{entry.get('title','')[:50]}' is resolved with actual data",
                "financial_impact": str(abs(entry.get("financial_impact_usd") or 0)),
            },
            created_by="dynamic_manifold",
            project_id=entry.get("project_id"),
            detail_item_id=entry.get("detail_item_id"),
        )
        conn.execute(
            "UPDATE gap_prescriptions SET status='dispatched',dispatched_at=? WHERE id=?",
            (_now(), presc_id)
        )
        logger.info("LOW dispatch: work_order created for gap %s", entry["id"])
    except Exception as e:
        logger.warning("LOW dispatch failed: %s", e)


def _dispatch_medium(conn, entry: Dict, presc: Dict, presc_id: str):
    """MEDIUM risk: work_order + audit flag."""
    _dispatch_low(conn, entry, presc, presc_id)
    try:
        from src.records_engine import create_record as _cr
        gap_title = str(entry.get("title",""))[:60]
        findings_text = ("Medium-risk gap detected. Score:" + str(presc["risk_score"]) +
                         " Exposure:$" + str(round(presc["financial_exposure_usd"])) +
                         " Dependents:" + str(presc["downstream_count"]) +
                         " Action:" + presc["action"])
        _cr("audit_record",
            "[REVIEW FLAG] Medium-risk gap: " + gap_title,
            {
                "audit_scope":    "Gap review: " + gap_title,
                "auditor":        "dynamic_manifold",
                "audit_date":     date.today().isoformat(),
                "findings":       findings_text,
                "risk_level":     "Medium",
                "remediation":    presc["action"],
                "financial_impact": str(presc["financial_exposure_usd"]),
            },
            created_by="dynamic_manifold",
            project_id=entry.get("project_id"),
        )
        logger.info("MEDIUM dispatch: audit flag + work_order for gap %s", entry["id"])
    except Exception as e:
        logger.warning("MEDIUM audit flag failed: %s", e)


def _dispatch_high(conn, entry: Dict, presc: Dict, presc_id: str, project_id: str):
    """HIGH risk: HITL escalation + risk register entry + freeze signal."""
    esc_id = _id("ge")
    conn.execute(
        """INSERT INTO gap_escalations
           (id,entry_id,prescription_id,project_id,risk_score,risk_tier,
            reason,financial_exposure_usd)
           VALUES (?,?,?,?,?,?,?,?)""",
        (esc_id, entry["id"], presc_id, project_id,
         presc["risk_score"], "HIGH",
         presc["reason"], presc["financial_exposure_usd"])
    )
    conn.execute(
        "UPDATE gap_prescriptions SET status='dispatched',dispatched_at=? WHERE id=?",
        (_now(), presc_id)
    )
    try:
        from src.records_engine import create_record as _cr
        gap_title = str(entry.get("title",""))[:60]
        gap_body  = str(entry.get("body",""))[:200]
        risk_desc = ("HIGH RISK GAP - Immediate attention required. " +
                     "Gap:" + gap_title + " Body:" + gap_body +
                     " Score:" + str(round(presc["risk_score"],2)) +
                     " Reason:" + str(presc["reason"]))
        _cr("risk_register_entry",
            "[HIGH RISK GAP] " + gap_title,
            {
                "risk_title":       "Unresolved high-risk gap: " + gap_title,
                "risk_description": risk_desc,
                "likelihood":       "Likely",
                "impact":           "Major",
                "financial_impact": str(presc["financial_exposure_usd"]),
                "mitigation":       presc["action"],
                "owner":            "exec_admin",
                "review_date":      (date.today() + timedelta(days=2)).isoformat(),
            },
            created_by="dynamic_manifold",
            project_id=project_id,
        )
    except Exception as e:
        logger.warning("Risk register entry failed: %s", e)
    _freeze_downstream_chains(entry["id"], presc["reason"])
    logger.warning("HIGH dispatch: HITL escalation + risk register for gap %s (score=%.2f)",
                   entry["id"], presc["risk_score"])


def _freeze_downstream_chains(entry_id: str, reason: str):
    """Freeze any chain steps whose workflow is blocked by this gap."""
    try:
        chain_db = "/var/lib/murphy-production/chain_engine.db"
        if not os.path.exists(chain_db):
            return
        conn = sqlite3.connect(chain_db, timeout=5)
        # Tag active steps — mark as gated with freeze reason
        conn.execute("""
            UPDATE chain_steps SET gate_status='gated', gate_reason=?
            WHERE gate_status IN ('ready','pending')
            AND chain_id IN (SELECT id FROM chain_requests WHERE status='active')
        """, (f"Frozen: unresolved HIGH-risk gap {entry_id[:12]} — {reason[:100]}",))
        conn.commit()
        frozen = conn.total_changes
        conn.close()
        if frozen:
            logger.warning("FREEZE: %d chain steps frozen due to HIGH gap %s", frozen, entry_id)
    except Exception as e:
        logger.debug("Freeze chain steps: %s", e)


# ── Query functions ────────────────────────────────────────────────────────────

def get_gaps(project_id: str = None, status: str = "open",
             tier: str = None, limit: int = 100) -> List[Dict]:
    with _db() as conn:
        clauses, params = ["gp.status=?"], [status]
        if project_id:
            clauses.append("gp.project_id=?"); params.append(project_id)
        if tier:
            clauses.append("gp.risk_tier=?"); params.append(tier)
        q = """
            SELECT gp.*, me.title as entry_title, me.entry_type, me.body,
                   me.confidence, me.financial_impact_usd, me.known_at,
                   me.depends_on_id, di.name as detail_item_name
            FROM gap_prescriptions gp
            LEFT JOIN manifold_entries me ON me.id = gp.entry_id
            LEFT JOIN detail_items di ON di.id = me.detail_item_id
            WHERE """ + " AND ".join(clauses) + """
            ORDER BY gp.risk_score DESC LIMIT ?"""
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["prescription"] = json.loads(d.get("prescription_json") or "{}")
        result.append(d)
    return result


def get_gap_summary(project_id: str = None) -> Dict:
    with _db() as conn:
        base = "WHERE gp.status='open'" + (f" AND gp.project_id='{project_id}'" if project_id else "")
        by_tier = conn.execute(f"""
            SELECT risk_tier, COUNT(*) as count, SUM(financial_exposure_usd) as exposure
            FROM gap_prescriptions {base} GROUP BY risk_tier
        """).fetchall()
        by_type = conn.execute(f"""
            SELECT gap_type, COUNT(*) as count, SUM(financial_exposure_usd) as exposure
            FROM gap_prescriptions {base} GROUP BY gap_type
        """).fetchall()
        total = conn.execute(f"""
            SELECT COUNT(*) as c, SUM(financial_exposure_usd) as exp,
                   SUM(CASE WHEN risk_tier='HIGH' THEN 1 ELSE 0 END) as high,
                   SUM(CASE WHEN risk_tier='MEDIUM' THEN 1 ELSE 0 END) as medium,
                   SUM(CASE WHEN risk_tier='LOW' THEN 1 ELSE 0 END) as low
            FROM gap_prescriptions {base}
        """).fetchone()
        resolved = conn.execute(
            "SELECT COUNT(*) FROM gap_prescriptions WHERE status='fulfilled'"
            + (f" AND project_id='{project_id}'" if project_id else "")
        ).fetchone()[0]
        escalations = conn.execute(
            "SELECT COUNT(*) FROM gap_escalations WHERE status='open'"
            + (f" AND project_id='{project_id}'" if project_id else "")
        ).fetchone()[0]
        last_scan = conn.execute(
            "SELECT * FROM gap_scan_log ORDER BY scanned_at DESC LIMIT 1"
        ).fetchone()

    t = dict(total) if total else {}
    return {
        "open_gaps":     t.get("c", 0),
        "total_exposure_usd": round(t.get("exp") or 0, 2),
        "by_tier":       {"HIGH": t.get("high",0), "MEDIUM": t.get("medium",0), "LOW": t.get("low",0)},
        "by_type":       [dict(r) for r in by_type],
        "resolved_total": resolved,
        "open_escalations": escalations,
        "last_scan":     dict(last_scan) if last_scan else None,
        "resolution_rate": round(resolved / max((resolved + t.get("c", 0)), 1) * 100, 1),
    }


def close_gap(prescription_id: str, closed_by: str = "system",
              resolution_note: str = "") -> Dict:
    now = _now()
    with _db() as conn:
        gp = conn.execute(
            "SELECT * FROM gap_prescriptions WHERE id=?", (prescription_id,)
        ).fetchone()
        if not gp:
            return {"error": "Prescription not found"}
        conn.execute(
            "UPDATE gap_prescriptions SET status='fulfilled',fulfilled_at=?,updated_at=? WHERE id=?",
            (now, now, prescription_id)
        )
        # Also resolve the underlying manifold entry
        conn.execute(
            "UPDATE manifold_entries SET is_resolved=1,resolved_by=?,resolved_at=? WHERE id=?",
            (closed_by, now, gp["entry_id"])
        )
        # Propagate: re-scan dependents
        dependents = conn.execute(
            "SELECT id FROM manifold_entries WHERE depends_on_id=? AND is_resolved=0",
            (gp["entry_id"],)
        ).fetchall()

    logger.info("Gap %s closed by %s. %d dependents will re-scan.",
                prescription_id, closed_by, len(dependents))
    return {"status": "fulfilled", "id": prescription_id, "dependents_affected": len(dependents)}


def escalate_gap(prescription_id: str, reason: str = "",
                 escalated_by: str = "system") -> Dict:
    with _db() as conn:
        gp = conn.execute(
            "SELECT * FROM gap_prescriptions WHERE id=?", (prescription_id,)
        ).fetchone()
        if not gp:
            return {"error": "Not found"}
        esc_id = _id("ge")
        conn.execute(
            """INSERT INTO gap_escalations
               (id,entry_id,prescription_id,project_id,risk_score,risk_tier,reason,financial_exposure_usd)
               VALUES (?,?,?,?,?,?,?,?)""",
            (esc_id, gp["entry_id"], prescription_id, gp["project_id"],
             gp["risk_score"], "HIGH",
             reason or gp.get("risk_tier",""), gp["financial_exposure_usd"])
        )
        conn.execute(
            "UPDATE gap_prescriptions SET risk_tier='HIGH',updated_at=? WHERE id=?",
            (_now(), prescription_id)
        )
    return {"escalated": True, "escalation_id": esc_id}


def get_risk_exposure(project_id: str = None) -> Dict:
    """Full financial exposure picture across all open gaps."""
    with _db() as conn:
        base_where = "WHERE gp.status='open'" + (f" AND gp.project_id='{project_id}'" if project_id else "")
        rows = conn.execute(f"""
            SELECT gp.gap_type, gp.risk_tier, gp.risk_score,
                   gp.financial_exposure_usd, gp.downstream_count,
                   me.title, me.entry_type, me.confidence
            FROM gap_prescriptions gp
            LEFT JOIN manifold_entries me ON me.id = gp.entry_id
            {base_where}
            ORDER BY gp.risk_score DESC
        """).fetchall()
        total_exp = sum(float(r["financial_exposure_usd"] or 0) for r in rows)
        high_exp  = sum(float(r["financial_exposure_usd"] or 0) for r in rows if r["risk_tier"]=="HIGH")
    return {
        "total_exposure_usd": round(total_exp, 2),
        "high_risk_exposure_usd": round(high_exp, 2),
        "gap_count": len(rows),
        "gaps": [dict(r) for r in rows],
    }


def get_status() -> Dict:
    try:
        summary = get_gap_summary()
        return {
            "open_gaps": summary["open_gaps"],
            "total_exposure_usd": summary["total_exposure_usd"],
            "high_risk": summary["by_tier"].get("HIGH", 0),
            "escalations": summary["open_escalations"],
            "resolution_rate_pct": summary["resolution_rate"],
        }
    except Exception as e:
        return {"error": str(e)}
