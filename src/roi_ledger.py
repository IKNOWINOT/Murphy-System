"""
roi_ledger.py — PATCH-180b
Time-Money-Action ROI Ledger.

Every agent action has three dimensions:
  1. TIME   — how long it took (seconds)
  2. MONEY  — what it cost OR generated ($)
  3. ACTION — what type of work was done

Production logic vs Admin logic separation:
  PRODUCTION: Collector, Translator, Executor, ProdOps, Scheduler
    → These generate value: lead captured, content published, API activated, task done
    → ROI = revenue_impact / time_cost

  ADMIN: ExecAdmin, Auditor, Rosetta, HITL
    → These govern value: compliance verified, decision made, breach blocked, soul check
    → ROI = risk_avoided / oversight_cost

Every workflow step logs to this ledger.
The ledger rolls up to:
  - Per-agent ROI score
  - Per-workflow ROI score
  - Business plan targets vs actual
  - Daily/weekly P&L equivalent
"""

import sqlite3, json, uuid, logging, os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger("murphy.roi_ledger")

DB_PATH = "/var/lib/murphy-production/roi_ledger.db"

# ── Action taxonomy ────────────────────────────────────────────────────────────
# Each action type has: default_time_cost_s, money_value_usd, logic_lane
# money_value_usd: positive = revenue/value generated, negative = cost

ACTION_CATALOG = {
    # ── PRODUCTION lane ────────────────────────────────────────────────────────
    "lead_captured":          {"time_s": 30,   "value": 25.00,   "lane": "production", "icon": "💰"},
    "lead_qualified":         {"time_s": 600,  "value": 150.00,  "lane": "production", "icon": "💰"},
    "outreach_sent":          {"time_s": 120,  "value": 45.00,   "lane": "production", "icon": "📨"},
    "customer_converted":     {"time_s": 300,  "value": 500.00,  "lane": "production", "icon": "🎉"},
    "content_published":      {"time_s": 1800, "value": 80.00,   "lane": "production", "icon": "📝"},
    "api_activated":          {"time_s": 900,  "value": 120.00,  "lane": "production", "icon": "⚡"},
    "task_executed":          {"time_s": 180,  "value": 20.00,   "lane": "production", "icon": "✅"},
    "onboarding_completed":   {"time_s": 600,  "value": 200.00,  "lane": "production", "icon": "🚀"},
    "signal_collected":       {"time_s": 10,   "value": 5.00,    "lane": "production", "icon": "📡"},
    "workflow_automated":     {"time_s": 60,   "value": 60.00,   "lane": "production", "icon": "⚙️"},
    "revenue_directive_fired":{"time_s": 300,  "value": 250.00,  "lane": "production", "icon": "📈"},
    "morning_brief_delivered":{"time_s": 120,  "value": 30.00,   "lane": "production", "icon": "☀️"},
    # ── ADMIN lane ─────────────────────────────────────────────────────────────
    "compliance_verified":    {"time_s": 900,  "value": 500.00,  "lane": "admin",      "icon": "🛡️"},
    "breach_blocked":         {"time_s": 120,  "value": 5000.00, "lane": "admin",      "icon": "🚨"},
    "soul_check_passed":      {"time_s": 30,   "value": 100.00,  "lane": "admin",      "icon": "🌐"},
    "hitl_decision_made":     {"time_s": 3600, "value": 800.00,  "lane": "admin",      "icon": "🔴"},
    "audit_completed":        {"time_s": 600,  "value": 300.00,  "lane": "admin",      "icon": "📋"},
    "incident_resolved":      {"time_s": 7200, "value": 3000.00, "lane": "admin",      "icon": "🔥"},
    "risk_flagged":           {"time_s": 60,   "value": 200.00,  "lane": "admin",      "icon": "⚠️"},
    "roi_reported":           {"time_s": 120,  "value": 50.00,   "lane": "admin",      "icon": "📊"},
    "patch_deployed":         {"time_s": 1200, "value": 400.00,  "lane": "admin",      "icon": "🔧"},
    # ── COST events (negative value) ──────────────────────────────────────────
    "llm_call":               {"time_s": 3,    "value": -0.05,   "lane": "production", "icon": "🤖"},
    "email_sent":             {"time_s": 5,    "value": -0.001,  "lane": "production", "icon": "📧"},
    "external_api_call":      {"time_s": 1,    "value": -0.01,   "lane": "production", "icon": "🌐"},
    "storage_write":          {"time_s": 0.1,  "value": -0.001,  "lane": "production", "icon": "💾"},
}

# Agent → logic lane mapping
AGENT_LANE = {
    "collector":  "production",
    "translator": "production",
    "executor":   "production",
    "prod_ops":   "production",
    "scheduler":  "production",
    "exec_admin": "admin",
    "auditor":    "admin",
    "rosetta":    "admin",
    "hitl":       "admin",
}

# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS roi_entries (
            id TEXT PRIMARY KEY,
            timestamp TEXT DEFAULT (datetime('now')),
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            logic_lane TEXT NOT NULL,
            workflow_id TEXT,
            workflow_name TEXT,
            step_name TEXT,
            time_spent_s REAL DEFAULT 0,
            money_value_usd REAL DEFAULT 0,
            roi_score REAL DEFAULT 0,
            notes TEXT,
            context_json TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS roi_targets (
            id TEXT PRIMARY KEY,
            period TEXT NOT NULL,
            target_name TEXT NOT NULL,
            target_value_usd REAL DEFAULT 0,
            actual_value_usd REAL DEFAULT 0,
            target_time_s REAL DEFAULT 0,
            actual_time_s REAL DEFAULT 0,
            logic_lane TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_roi_agent ON roi_entries(agent_id);
        CREATE INDEX IF NOT EXISTS idx_roi_ts ON roi_entries(timestamp);
        CREATE INDEX IF NOT EXISTS idx_roi_lane ON roi_entries(logic_lane);
        CREATE INDEX IF NOT EXISTS idx_roi_wf ON roi_entries(workflow_id);
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


# ── Core logging function ──────────────────────────────────────────────────────

def log_action(agent_id: str, action_type: str,
               workflow_id: str = None, workflow_name: str = None,
               step_name: str = None, time_spent_s: float = None,
               money_value_usd: float = None, notes: str = "",
               context: Dict = None) -> Dict:
    """Log a time-money-action event to the ROI ledger."""
    cat = ACTION_CATALOG.get(action_type, {})
    lane = AGENT_LANE.get(agent_id, cat.get("lane", "production"))
    t_spent = time_spent_s if time_spent_s is not None else cat.get("time_s", 0)
    m_val   = money_value_usd if money_value_usd is not None else cat.get("value", 0)

    # ROI score: value_per_hour for production, risk_avoided for admin
    if t_spent > 0:
        roi = round(m_val / (t_spent / 3600), 2)  # $/hour equivalent
    else:
        roi = m_val

    entry_id = str(uuid.uuid4())[:12]
    with _db() as conn:
        conn.execute(
            """INSERT INTO roi_entries
               (id, agent_id, action_type, logic_lane, workflow_id, workflow_name,
                step_name, time_spent_s, money_value_usd, roi_score, notes, context_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entry_id, agent_id, action_type, lane, workflow_id, workflow_name,
             step_name, t_spent, m_val, roi, notes, json.dumps(context or {}))
        )

    logger.debug("ROI: %s/%s → $%.2f in %.0fs (ROI=%.0f/hr)", agent_id, action_type, m_val, t_spent, roi)
    return {"id": entry_id, "roi_score": roi, "money_value_usd": m_val, "time_spent_s": t_spent, "lane": lane}


def log_workflow_step_complete(workflow_id: str, workflow_name: str,
                               step_name: str, agent_id: str,
                               duration_s: float, putdown_data: Dict = None) -> Dict:
    """Auto-called when a workflow step completes — infers action type and logs ROI."""
    # Map step names to action types
    STEP_ACTION_MAP = {
        "signal collection":       "signal_collected",
        "intent translation":      "lead_qualified",
        "executive qualification": "lead_qualified",
        "outreach execution":      "outreach_sent",
        "audit & close":           "audit_completed",
        "brief creation":          "task_executed",
        "content production":      "content_published",
        "publish":                 "content_published",
        "compliance check":        "compliance_verified",
        "scan trigger":            "compliance_verified",
        "soul gate review":        "soul_check_passed",
        "hitl escalation":         "hitl_decision_made",
        "remediation dispatch":    "task_executed",
        "blocker scan":            "revenue_directive_fired",
        "directive generation":    "revenue_directive_fired",
        "execution":               "task_executed",
        "roi audit":               "roi_reported",
        "detection & triage":      "hitl_decision_made",
        "compliance assessment":   "compliance_verified",
        "containment & ops":       "incident_resolved",
        "resolution & close":      "incident_resolved",
        "signup collection":       "lead_captured",
        "onboarding schedule":     "task_executed",
        "activation execution":    "onboarding_completed",
        "onboarding audit":        "audit_completed",
        "discovery":               "signal_collected",
        "acquisition & test":      "api_activated",
        "integration audit":       "audit_completed",
        "signal aggregation":      "signal_collected",
        "executive summary":       "morning_brief_delivered",
        "soul review":             "soul_check_passed",
        "delivery":                "email_sent",
        "gap identification":      "risk_flagged",
        "code generation":         "workflow_automated",
        "critic gate":             "audit_completed",
        "deploy & commission":     "patch_deployed",
    }
    action = STEP_ACTION_MAP.get(step_name.lower(), "task_executed")
    return log_action(
        agent_id=agent_id, action_type=action,
        workflow_id=workflow_id, workflow_name=workflow_name,
        step_name=step_name, time_spent_s=duration_s,
        notes=f"Auto-logged from workflow step completion",
        context=putdown_data or {}
    )


# ── Summary queries ────────────────────────────────────────────────────────────

def get_summary(days: int = 7) -> Dict:
    """Full ROI summary: production vs admin, by agent, by workflow."""
    with _db() as conn:
        # Overall
        overall = conn.execute("""
            SELECT
                COUNT(*) as total_actions,
                SUM(time_spent_s) as total_time_s,
                SUM(money_value_usd) as total_value_usd,
                SUM(CASE WHEN money_value_usd > 0 THEN money_value_usd ELSE 0 END) as gross_revenue,
                SUM(CASE WHEN money_value_usd < 0 THEN money_value_usd ELSE 0 END) as total_cost,
                AVG(roi_score) as avg_roi_score
            FROM roi_entries
            WHERE timestamp > datetime('now', ? || ' days')
        """, (f"-{days}",)).fetchone()

        # By lane
        by_lane = conn.execute("""
            SELECT logic_lane,
                COUNT(*) as actions,
                SUM(time_spent_s) as time_s,
                SUM(money_value_usd) as value_usd,
                AVG(roi_score) as avg_roi
            FROM roi_entries
            WHERE timestamp > datetime('now', ? || ' days')
            GROUP BY logic_lane
        """, (f"-{days}",)).fetchall()

        # By agent
        by_agent = conn.execute("""
            SELECT agent_id, logic_lane,
                COUNT(*) as actions,
                SUM(time_spent_s) as time_s,
                SUM(money_value_usd) as value_usd,
                AVG(roi_score) as avg_roi,
                MAX(timestamp) as last_action
            FROM roi_entries
            WHERE timestamp > datetime('now', ? || ' days')
            GROUP BY agent_id
            ORDER BY value_usd DESC
        """, (f"-{days}",)).fetchall()

        # By workflow
        by_workflow = conn.execute("""
            SELECT workflow_name,
                COUNT(*) as steps,
                SUM(time_spent_s) as time_s,
                SUM(money_value_usd) as value_usd,
                AVG(roi_score) as avg_roi
            FROM roi_entries
            WHERE workflow_id IS NOT NULL
              AND timestamp > datetime('now', ? || ' days')
            GROUP BY workflow_name
            ORDER BY value_usd DESC
            LIMIT 20
        """, (f"-{days}",)).fetchall()

        # Top actions
        top_actions = conn.execute("""
            SELECT action_type, logic_lane,
                COUNT(*) as count,
                SUM(money_value_usd) as total_value,
                AVG(time_spent_s) as avg_time_s
            FROM roi_entries
            WHERE timestamp > datetime('now', ? || ' days')
            GROUP BY action_type
            ORDER BY total_value DESC
            LIMIT 10
        """, (f"-{days}",)).fetchall()

        # Daily trend (last 7 days)
        daily = conn.execute("""
            SELECT date(timestamp) as day,
                SUM(CASE WHEN logic_lane='production' THEN money_value_usd ELSE 0 END) as prod_value,
                SUM(CASE WHEN logic_lane='admin' THEN money_value_usd ELSE 0 END) as admin_value,
                COUNT(*) as actions
            FROM roi_entries
            WHERE timestamp > datetime('now', '-7 days')
            GROUP BY date(timestamp)
            ORDER BY day
        """).fetchall()

    ov = dict(overall) if overall else {}
    return {
        "period_days": days,
        "overall": ov,
        "by_lane": [dict(r) for r in by_lane],
        "by_agent": [dict(r) for r in by_agent],
        "by_workflow": [dict(r) for r in by_workflow],
        "top_actions": [dict(r) for r in top_actions],
        "daily_trend": [dict(r) for r in daily],
        "action_catalog": ACTION_CATALOG,
        "agent_lane_map": AGENT_LANE,
    }


def get_recent_entries(limit: int = 100) -> List[Dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM roi_entries ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_target(period: str, name: str, target_value_usd: float,
               target_time_s: float = 0, lane: str = None) -> Dict:
    """Set a business target for the period."""
    entry_id = f"tgt_{period}_{name.replace(' ','_')[:20]}"
    with _db() as conn:
        existing = conn.execute("SELECT id FROM roi_targets WHERE id=?", (entry_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE roi_targets SET target_value_usd=?,target_time_s=?,logic_lane=?,updated_at=datetime('now') WHERE id=?",
                (target_value_usd, target_time_s, lane, entry_id)
            )
        else:
            conn.execute(
                "INSERT INTO roi_targets (id,period,target_name,target_value_usd,target_time_s,logic_lane) VALUES (?,?,?,?,?,?)",
                (entry_id, period, name, target_value_usd, target_time_s, lane)
            )
    return {"id": entry_id, "period": period, "target": name, "value": target_value_usd}


def get_targets_vs_actual(period: str = None) -> List[Dict]:
    """Compare targets vs actual ROI."""
    with _db() as conn:
        if period:
            targets = conn.execute(
                "SELECT * FROM roi_targets WHERE period=? ORDER BY target_value_usd DESC",
                (period,)
            ).fetchall()
        else:
            targets = conn.execute(
                "SELECT * FROM roi_targets ORDER BY period DESC, target_value_usd DESC"
            ).fetchall()

        result = []
        for t in targets:
            tdict = dict(t)
            # Get actual for this period
            period_filter = t["period"]  # e.g. "2026-05" or "2026-W18"
            actual = conn.execute("""
                SELECT SUM(money_value_usd) as actual, SUM(time_spent_s) as actual_time
                FROM roi_entries
                WHERE strftime('%Y-%m', timestamp) = ?
                  AND (? IS NULL OR logic_lane = ?)
            """, (period_filter[:7], t["logic_lane"], t["logic_lane"])).fetchone()
            tdict["actual_value_usd"] = round(actual["actual"] or 0, 2)
            tdict["actual_time_s"]    = round(actual["actual_time"] or 0, 0)
            tdict["variance_usd"]     = round(tdict["actual_value_usd"] - tdict["target_value_usd"], 2)
            tdict["pct_achieved"]     = round(tdict["actual_value_usd"] / max(tdict["target_value_usd"], 1) * 100, 1)
            result.append(tdict)
    return result


# ── Seed default targets ───────────────────────────────────────────────────────
def _seed_targets():
    from datetime import datetime
    period = datetime.now().strftime("%Y-%m")
    defaults = [
        ("Monthly Revenue Target",  5000.0, "production"),
        ("Compliance Value Target",  2000.0, "admin"),
        ("Leads Captured Value",    1500.0, "production"),
        ("Content Value Target",     800.0, "production"),
        ("Risk Avoided Target",     3000.0, "admin"),
    ]
    for name, val, lane in defaults:
        try:
            set_target(period, name, val, lane=lane)
        except Exception:
            pass


try:
    _seed_targets()
except Exception as e:
    logger.warning("ROI seed error: %s", e)
