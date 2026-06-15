#!/usr/bin/env python3
"""
Ship 31cd — Auto-Rollback on Health Degrade

Compares current shape-of-complete score vs baseline.
If score drops > THRESHOLD within ROLLBACK_WINDOW minutes of any
ship_31* commit, identifies the most recent snapshot and proposes
a rollback (always to founder as HITL — never auto-rolls back).

Runs as cron-fed cycle. Drafts the rollback recommendation to
self_patch_proposals as HIGH risk → founder must approve.
"""
from __future__ import annotations
import sqlite3, json, subprocess, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/opt/Murphy-System")

DEGRADE_THRESHOLD_PCT = 15  # 15% drop = degrade
ROLLBACK_WINDOW_MIN = 60    # only roll back ships from last 60 min
SCORE_DB = "/var/lib/murphy-production/health_score.db"

def _init():
    c = sqlite3.connect(SCORE_DB, timeout=10.0)
    c.execute("""CREATE TABLE IF NOT EXISTS health_score (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        measured_at TEXT NOT NULL,
        overall_score REAL,
        compliance_score REAL,
        gates_a REAL, gates_b REAL, gates_c REAL, gates_d REAL, gates_e REAL,
        details TEXT
    )""")
    c.commit(); c.close()


def _fetch_compliance_score() -> float:
    """Pull current compliance score from local API."""
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8000/api/health/compliance", timeout=8)
        d = json.loads(r.read().decode())
        return float(d.get("overall_pct", 0))
    except Exception:
        return -1.0


def record_score() -> dict:
    _init()
    score = _fetch_compliance_score()
    if score < 0:
        return {"ok": False, "error": "could not fetch score"}
    c = sqlite3.connect(SCORE_DB, timeout=10.0)
    c.execute("INSERT INTO health_score (measured_at, overall_score, compliance_score, details) "
              "VALUES (?,?,?,?)",
              (datetime.now(timezone.utc).isoformat(), score, score, "{}"))
    c.commit()
    # baseline = avg of last 12 scores excluding the freshest
    rows = c.execute("SELECT overall_score FROM health_score ORDER BY id DESC LIMIT 13").fetchall()
    c.close()
    if len(rows) < 4: return {"ok": True, "score": score, "baseline": None}
    baseline_rows = rows[1:]  # exclude latest
    baseline = sum(r[0] for r in baseline_rows) / len(baseline_rows)
    return {"ok": True, "score": score, "baseline": baseline,
            "drop_pct": (baseline - score) / baseline * 100 if baseline else 0}


def detect_degrade() -> dict:
    r = record_score()
    if not r.get("ok") or r.get("baseline") is None:
        return {"degraded": False, **r}
    drop = r.get("drop_pct", 0)
    return {"degraded": drop > DEGRADE_THRESHOLD_PCT, **r}


def _recent_ships(window_min: int = ROLLBACK_WINDOW_MIN) -> list[dict]:
    """git log of ship_31* commits in the last window_min minutes."""
    try:
        out = subprocess.check_output(
            ["git", "log", f"--since={window_min} minutes ago",
             "--pretty=format:%H|%s|%ai", "--grep=Ship 31"],
            cwd="/opt/Murphy-System", timeout=15).decode()
        ships = []
        for line in out.strip().split("\n"):
            if not line: continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                ships.append({"sha": parts[0], "subject": parts[1], "at": parts[2]})
        return ships
    except Exception:
        return []


def propose_rollback_if_degraded() -> dict:
    d = detect_degrade()
    if not d.get("degraded"): return {"action": "noop", **d}
    recent = _recent_ships()
    if not recent: return {"action": "degrade_no_recent_ship", **d}
    most_recent = recent[0]
    # File HIGH-risk proposal for founder approval
    try:
        from src.murphy_self_patch_loop import PatchProposal, PatchKind, add_proposal, _save_store
        pp = PatchProposal(
            symptom=f"Health degrade: {d['drop_pct']:.1f}% drop after ship {most_recent['subject']}",
            diagnosis=f"compliance/score baseline was {d['baseline']:.1f}, now {d['score']:.1f}",
            affected_file="N/A — rollback recommendation",
            affected_function="git revert / SnapshotManager.restore",
            patch_kind=PatchKind.CODE_DIFF,
            proposed_change=f"RECOMMEND ROLLBACK of {most_recent['sha'][:10]} ({most_recent['subject']})\n\n"
                            f"Health score dropped {d['drop_pct']:.1f}% within {ROLLBACK_WINDOW_MIN}min.\n"
                            f"Threshold: {DEGRADE_THRESHOLD_PCT}%.\n\n"
                            f"Rollback command: cd /opt/Murphy-System && git revert {most_recent['sha']}\n"
                            f"Or restore from snapshot in /var/lib/murphy-production/backups/\n",
            unified_diff="",
            rationale="Auto-detected by autonomy_rollback_31cd",
            risk_level="HIGH",
            requires_human_review=True,
        )
        add_proposal(pp); _save_store()
        return {"action": "rollback_proposed", "proposal_id": pp.proposal_id, **d}
    except Exception as e:
        return {"action": "filing_failed", "error": str(e), **d}


if __name__ == "__main__":
    print(json.dumps(propose_rollback_if_degraded(), indent=2))
