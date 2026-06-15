#!/usr/bin/env python3
"""
Ship 31cb — Autonomy Risk-Band Policy

Layered ON TOP of existing CITL toggle (citl_31bi).
While CITL is ON and posture is AUTONOMOUS:
  LOW risk      → auto-apply (no founder wait)
  MEDIUM risk   → draft to /api/self/proposals (founder reviews later)
  HIGH risk     → HITL email immediately
  CRITICAL risk → HITL + slack-style alarm

Hard rails (NEVER bypassed, regardless of toggle state):
  - Money operations → always HIGH (founder)
  - Outbound email to NEW third party → always HIGH (founder)
  - Legal/binding → always CRITICAL (founder)
  - Source-code edits to /src/runtime/app.py → always HIGH (founder)
  - Compliance rule changes → always CRITICAL (founder)

The whole policy is OFF by default. Founder toggles at /os/autonomy.
"""
from __future__ import annotations
import sqlite3, json, os
from datetime import datetime, timezone
from typing import Optional

_DB = "/var/lib/murphy-production/autonomy_policy.db"

def _init():
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("""CREATE TABLE IF NOT EXISTS posture_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        changed_at TEXT NOT NULL,
        posture TEXT NOT NULL,
        set_by TEXT,
        reason TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS auto_decision_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decided_at TEXT NOT NULL,
        proposal_id TEXT,
        risk_level TEXT,
        decision TEXT,
        reasoning TEXT,
        kind TEXT,
        amount_usd REAL DEFAULT 0
    )""")
    c.commit(); c.close()


# ── posture management ──

def get_posture() -> str:
    """Returns 'OFF' | 'ASSIST' | 'AUTONOMOUS'. Default 'OFF'."""
    _init()
    # env override for emergencies
    env = os.environ.get("MURPHY_AUTONOMY_POSTURE", "")
    if env in ("OFF","ASSIST","AUTONOMOUS"): return env
    c = sqlite3.connect(_DB, timeout=10.0)
    r = c.execute("SELECT posture FROM posture_state ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return r[0] if r else "OFF"


def set_posture(posture: str, set_by: str = "api", reason: str = "") -> dict:
    if posture not in ("OFF","ASSIST","AUTONOMOUS"):
        return {"ok": False, "error": f"invalid posture: {posture}"}
    _init()
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("INSERT INTO posture_state (changed_at, posture, set_by, reason) VALUES (?,?,?,?)",
              (datetime.now(timezone.utc).isoformat(), posture, set_by, reason))
    c.commit(); c.close()
    return {"ok": True, "posture": posture, "set_by": set_by}


# ── hard rails (never bypassed) ──

HARD_RAIL_KEYWORDS = {
    "money":      ["payment","invoice","charge","refund","stripe","nowpay","payout","wire","transfer","spend","purchase","buy","subscribe"],
    "new_email":  ["new outreach","cold email","cold outbound","first-touch","prospect"],
    "legal":      ["contract","sign","signature","agreement","tos","terms of service","privacy policy","dpa","msa","nda"],
    "kernel":     ["src/runtime/app.py","app.py","_runtime.py","conductor_service.py"],
    "compliance": ["canspam","gdpr","ccpa","compliance rule","reserved_slug","FOUNDER_ONLY"],
}

def _hit_hard_rail(text: str) -> Optional[str]:
    t = (text or "").lower()
    for rail, kws in HARD_RAIL_KEYWORDS.items():
        for kw in kws:
            if kw in t: return rail
    return None


# ── the decision ──

def decide(proposal: dict) -> dict:
    """
    Given a proposal {risk_level, kind, symptom, diagnosis, affected_file, amount_usd},
    return {decision: 'auto_apply' | 'draft' | 'hitl' | 'hitl_critical', reasoning, rail_hit}

    NEVER auto-applies if posture is OFF.
    NEVER auto-applies if a hard rail is hit.
    NEVER auto-applies if risk is HIGH/CRITICAL.
    """
    posture = get_posture()
    risk = (proposal.get("risk_level") or "HIGH").upper()
    amount = float(proposal.get("amount_usd", 0) or 0)
    text = " ".join(str(proposal.get(k,"")) for k in
                    ("symptom","diagnosis","affected_file","proposed_change","kind"))

    # rail check first — overrides everything
    rail = _hit_hard_rail(text)
    if rail:
        result = {"decision": "hitl_critical" if rail in ("legal","compliance") else "hitl",
                  "reasoning": f"hard rail hit: {rail}", "rail_hit": rail,
                  "posture": posture, "risk": risk}
        _log_decision(proposal, result)
        return result

    # money always HITL regardless of posture
    if amount > 0:
        result = {"decision": "hitl", "reasoning": f"money: ${amount}",
                  "rail_hit": "money", "posture": posture, "risk": risk}
        _log_decision(proposal, result)
        return result

    # posture gates
    if posture == "OFF":
        decision = "hitl" if risk in ("HIGH","CRITICAL") else "draft"
        result = {"decision": decision, "reasoning": "posture OFF — fallback to draft/hitl",
                  "rail_hit": None, "posture": posture, "risk": risk}
        _log_decision(proposal, result)
        return result

    # ASSIST posture: draft everything, never auto-apply
    if posture == "ASSIST":
        result = {"decision": "hitl" if risk in ("HIGH","CRITICAL") else "draft",
                  "reasoning": "posture ASSIST — drafts for review",
                  "rail_hit": None, "posture": posture, "risk": risk}
        _log_decision(proposal, result)
        return result

    # AUTONOMOUS posture: full risk-band logic
    if risk == "LOW":
        decision = "auto_apply"
    elif risk == "MEDIUM":
        decision = "draft"
    elif risk == "HIGH":
        decision = "hitl"
    else:  # CRITICAL
        decision = "hitl_critical"
    result = {"decision": decision,
              "reasoning": f"posture AUTONOMOUS, risk {risk} → {decision}",
              "rail_hit": None, "posture": posture, "risk": risk}
    _log_decision(proposal, result)
    return result


def _log_decision(proposal: dict, result: dict):
    try:
        c = sqlite3.connect(_DB, timeout=10.0)
        c.execute("""INSERT INTO auto_decision_log
            (decided_at, proposal_id, risk_level, decision, reasoning, kind, amount_usd)
            VALUES (?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(),
             proposal.get("proposal_id") or proposal.get("id",""),
             result.get("risk"), result.get("decision"), result.get("reasoning"),
             proposal.get("kind",""), float(proposal.get("amount_usd",0) or 0)))
        c.commit(); c.close()
    except Exception: pass


# ── stats ──

def get_stats(hours: int = 24) -> dict:
    _init()
    c = sqlite3.connect(_DB, timeout=10.0)
    try:
        rows = c.execute("""
            SELECT decision, COUNT(*) FROM auto_decision_log
            WHERE decided_at > datetime('now', ?) GROUP BY decision
        """, (f"-{hours} hours",)).fetchall()
        return {"posture": get_posture(),
                "decisions_last_{}h".format(hours): dict(rows),
                "total_decisions_logged": c.execute("SELECT COUNT(*) FROM auto_decision_log").fetchone()[0]}
    finally:
        c.close()
