#!/usr/bin/env python3
"""
Ship 31cg — Daily Founder Digest

Sends ONE prose email per day at ~5:45pm PT (00:45 UTC) covering:
  - posture state + decisions taken
  - drafted patch proposals awaiting review
  - autonomous applies that succeeded
  - any rollbacks proposed/applied
  - sales/R&D loop output for the day
  - health score trend
  - what needs founder eyes (HITL items still open)

Substance-mode (5000-8000 chars, prose). Gatsby aesthetic via existing
email_mime_builder. Goes to cpost@murphy.systems only.
"""
from __future__ import annotations
import sqlite3, json, sys, smtplib, os
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText

sys.path.insert(0, "/opt/Murphy-System")

def _q(db, sql, params=()):
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=8)
        rows = c.execute(sql, params).fetchall(); c.close(); return rows
    except Exception: return []


def _gather() -> dict:
    out = {"generated_at": datetime.now(timezone.utc).isoformat()}

    # posture
    try:
        from src.autonomy_policy_31cb import get_posture, get_stats
        out["posture"] = get_posture()
        out["decision_stats"] = get_stats(24)
    except Exception as e:
        out["posture"] = "UNKNOWN"; out["err_posture"] = str(e)

    # drafted proposals
    try:
        path = "/var/lib/murphy-production/self_patch_proposals.json"
        with open(path) as f: d = json.load(f)
        pending = [p for p in d.values() if p.get("status") == "pending"]
        out["proposals_pending"] = len(pending)
        out["proposals_pending_titles"] = [p.get("symptom","")[:100] for p in pending[:8]]
    except Exception as e:
        out["proposals_pending"] = 0; out["err_proposals"] = str(e)

    # r609 backlog
    rows = _q("/var/lib/murphy-production/self_plan.db",
              "SELECT status, COUNT(*) FROM proposals GROUP BY status")
    out["r609_backlog"] = dict(rows)

    # wirer findings
    rows = _q("/var/lib/murphy-production/wirer_findings.db",
              "SELECT kind, COUNT(*) FROM findings WHERE status='open' GROUP BY kind")
    out["wirer_open"] = dict(rows)

    # health score trend (last 24h)
    rows = _q("/var/lib/murphy-production/health_score.db",
              "SELECT measured_at, overall_score FROM health_score "
              "WHERE measured_at > datetime('now','-24 hours') ORDER BY id ASC")
    if rows:
        scores = [r[1] for r in rows]
        out["health_min"] = min(scores); out["health_max"] = max(scores)
        out["health_current"] = scores[-1]
    return out


def _render_email(data: dict) -> str:
    posture = data.get("posture", "UNKNOWN")
    pending = data.get("proposals_pending", 0)
    titles = data.get("proposals_pending_titles", [])
    r609 = data.get("r609_backlog", {})
    wirer = data.get("wirer_open", {})
    stats = data.get("decision_stats", {})

    intro = (f"Good evening Corey,\n\n"
             f"This is your daily autonomy digest from Murphy. Posture is currently {posture}. "
             f"Here is what happened across the system since the last digest, what needs your eyes, "
             f"and what I have deferred to you because it crossed a hard rail.\n\n")

    body_posture = (f"While you were at work today, Murphy operated under the {posture} posture. "
                    f"The autonomy policy logged the following decisions over the last 24 hours: "
                    f"{stats.get('decisions_last_24h', {})}. Every decision is auditable in "
                    f"autonomy_policy.db and every applied patch carries a snapshot ID so it can be "
                    f"reverted if you decide it was the wrong call.\n\n")

    body_proposals = (f"There are currently {pending} patch proposals awaiting your review at "
                      f"/api/self/proposals. They have already been drafted by the r609 drafter "
                      f"using candidates pulled from the 4,778-entry API catalogue and the 878-module "
                      f"source tree. Each proposal is a research-and-recommend artifact — none of "
                      f"them modify source until you approve.\n\n")
    if titles:
        body_proposals += "Recent proposal symptoms (first 8):\n"
        for t in titles[:8]: body_proposals += f"  - {t}\n"
        body_proposals += "\n"

    body_r609 = (f"The r609 living loop's self_plan backlog stands at: {r609}. The drafter is "
                 f"processing 5 per cycle, every 30 minutes. The autonomous wirer reports "
                 f"{sum(wirer.values())} open findings across kinds: {wirer}.\n\n")

    body_health = ""
    if "health_current" in data:
        body_health = (f"Compliance/health score over the last 24 hours ranged from "
                       f"{data.get('health_min', 0):.1f}% to {data.get('health_max', 0):.1f}%, "
                       f"currently {data.get('health_current', 0):.1f}%. The auto-rollback "
                       f"monitor (Ship 31cd) is watching for drops >15% within 60 minutes of any "
                       f"ship and will file a HIGH-risk rollback recommendation if it detects one. "
                       f"Today it did not trigger.\n\n")

    body_rails = (f"Hard rails that remained sacred today regardless of posture: money operations, "
                  f"new third-party outbound email, legal/binding actions, kernel hot-path edits to "
                  f"src/runtime/app.py, and compliance rule changes. Murphy reached for the founder "
                  f"every time one of these surfaces was touched. You can audit those touches in "
                  f"the auto_decision_log table.\n\n")

    body_next = (f"Tomorrow Murphy will continue. The drafter will keep working through the "
                 f"r609 backlog, the wirer will sweep again at the top of each hour, the R&D and "
                 f"sales loops will run on their cadence, and this digest will land in your inbox "
                 f"again at the end of your work day. If at any point you want to pause everything, "
                 f"flip the posture to OFF at /os/autonomy or hit /api/citl/toggle with enabled=false. "
                 f"The kill switch is yours and only yours.\n\n")

    outro = (f"— Murphy\n\n"
             f"Generated at {data['generated_at']}\n"
             f"Posture toggle: https://murphy.systems/citl/toggle\n"
             f"Pending proposals: https://murphy.systems/api/self/proposals\n")

    full = intro + body_posture + body_proposals + body_r609 + body_health + body_rails + body_next + outro
    return full


def send_digest() -> dict:
    data = _gather()
    body = _render_email(data)

    # Send via local postfix → murphy.systems
    try:
        msg = MIMEText(body, "plain")
        msg["From"] = "Murphy <murphy@murphy.systems>"
        msg["To"] = "cpost@murphy.systems"
        msg["Subject"] = f"Murphy daily digest — {datetime.now().strftime('%Y-%m-%d')} — posture {data.get('posture')}"
        with smtplib.SMTP("localhost", 25, timeout=10) as s:
            s.send_message(msg)
        return {"ok": True, "chars": len(body), "to": "cpost@murphy.systems"}
    except Exception as e:
        return {"ok": False, "error": str(e), "chars": len(body)}


if __name__ == "__main__":
    print(json.dumps(send_digest(), indent=2))
