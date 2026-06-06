#!/usr/bin/env python3
"""
memory_self_audit.py — Re-verify the top 10 facts from agent memory.md.

PATCH-MEMORY-SELF-AUDIT 2026-05-27
Author: Murphy + Corey

Why this exists:
The agent (Murphy's interactive shell) carries facts forward in memory.md
across sessions. Without re-verification, stale claims compound into
expensive errors (the $247K fake pipeline, the $9,065 fake revenue).

This script re-verifies the 10 most-quoted memory facts in <2 seconds.
Run at session start. Output is JSON for the agent to compare against memory.

Usage:
    python3 memory_self_audit.py            # full re-audit
    python3 memory_self_audit.py --quiet    # only fail-cases
"""
from __future__ import annotations
import json, os, sqlite3, subprocess, sys, time
from pathlib import Path

CRM_DB = "/var/lib/murphy-production/crm.db"
INBOUND_DB = "/var/lib/murphy-production/inbound_replies.db"
REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"
TENANTS_DB = "/var/lib/murphy-production/tenants.db"
SHAPE_STATE = "/var/lib/murphy-production/shape_state.json"
MURPHY_SRC = Path("/opt/Murphy-System/src")

def _q(db, sql):
    """Single-value SQL query."""
    try:
        with sqlite3.connect(db, timeout=3) as c:
            r = c.execute(sql).fetchone()
            return r[0] if r else None
    except Exception as e:
        return f"ERROR: {e}"

def _shape_state():
    try:
        return json.load(open(SHAPE_STATE))
    except Exception as e:
        return {"error": str(e)}

def _file_lines(path):
    try:
        return sum(1 for _ in open(path))
    except Exception as e:
        return f"ERROR: {e}"

def _file_exists(path):
    return Path(path).exists()

CHECKS = [
    # (key, description, current-value function, expected-from-memory)
    ("crm_total_deals",
        "Total deals in crm.db",
        lambda: _q(CRM_DB, "SELECT COUNT(*) FROM deals"),
        227),
    ("crm_real_active_leads",
        "Active deals tied to real-domain contacts",
        lambda: _q(CRM_DB,
            "SELECT COUNT(*) FROM deals d JOIN contacts c ON c.id=d.contact_id "
            "WHERE d.archived=0 "
            "AND c.contact_type NOT IN ('synthetic_seed','generated_persona')"),
        42),
    ("crm_real_prospect_stage",
        "Prospect-stage deals (post-desynth, should be 0)",
        lambda: _q(CRM_DB, "SELECT COUNT(*) FROM deals WHERE archived=0 AND stage='prospect'"),
        0),
    ("verifier_green",
        "Verifier green/total",
        lambda: f"{_shape_state().get('green','?')}/{_shape_state().get('total','?')}",
        "48/49"),
    ("verifier_red",
        "Verifier red gates",
        lambda: ",".join(_shape_state().get("red_keys", [])),
        "G.EXEC"),
    ("tenants_real",
        "Real (non-synthetic) tenants",
        lambda: _q(TENANTS_DB,
            "SELECT COUNT(*) FROM tenants WHERE state NOT IN ('synthetic_smoke_test','archived')"),
        0),
    ("routes_total",
        "Total registered routes",
        lambda: _q(REGISTRY_DB, "SELECT COUNT(*) FROM registry_routes"),
        1073),
    ("inbound_replies_total",
        "Inbound replies captured (grows over time)",
        lambda: _q(INBOUND_DB, "SELECT COUNT(*) FROM inbound_replies"),
        "≥1593"),
    ("lead_prospector_lines",
        "src/lead_prospector.py line count",
        lambda: _file_lines(MURPHY_SRC / "lead_prospector.py"),
        936),
    ("shape_verifier_exists",
        "shape_verifier.py exists at canonical path",
        lambda: _file_exists("/opt/Murphy-System/shape_verifier.py"),
        True),
    ("monolith_nrestarts_total",
        "Monolith cumulative restart count (systemd NRestarts; was 0 at session start)",
        lambda: int(subprocess.check_output(
            ["systemctl", "show", "murphy-production", "--property=NRestarts",
             "--value"]).decode().strip() or 0),
        "≥0"),
    ("cadence_would_send_count",
        "Leads cadence WOULD send to if unpaused (sanity floor)",
        lambda: _q(CRM_DB,
            "SELECT COUNT(*) FROM contacts c "
            "WHERE c.tags LIKE '%auto-prospected%' AND c.contact_type='lead'"),
        "≥0"),
    ("cadence_scheduler_paused",
        "Cadence scheduler pause state (True = won't auto-fire)",
        lambda: "next_run_time=None" in open(
            "/opt/Murphy-System/src/swarm_scheduler.py").read()
            .split('id="followup_cadence"')[1][:400],
        True),
    ("crm_lead_quality_tier_a",
        "Tier-A leads ready for HITL outreach",
        lambda: _q(CRM_DB,
            "SELECT COUNT(*) FROM contacts c JOIN deals d ON d.contact_id=c.id "
            "WHERE d.archived=0 AND c.contact_type='lead' "
            "AND c.tags LIKE '%quality:A%'"),
        "≥0"),  # any non-negative count is OK; drift = re-classification
    ("monolith_active_uptime_s",
        "Monolith uptime in seconds since last start (drift means recently restarted)",
        lambda: max(0, int(time.time() - float(subprocess.check_output(
            ["systemctl", "show", "murphy-production",
             "--property=ActiveEnterTimestampMonotonic",
             "--value"]).decode().strip() or 0) / 1e6)) if subprocess.check_output(
             ["systemctl", "show", "murphy-production",
              "--property=ActiveEnterTimestampMonotonic", "--value"]
             ).decode().strip() != "0" else 0,
        "≥60"),
    # PATCH-SELF-AUDIT-RESTART-001 (2026-05-28): watch restart cadence so
    # memory drift on restart frequency cannot stay invisible.
    # Uses systemctl NRestarts (no journal permission needed) — counts the
    # number of times systemd has restarted this service since last manual start.
    # Healthy: 0-2. Active cycle: >3.
    ("systemd_restart_count",
        "systemd NRestarts counter (resets on manual start)",
        lambda: int(subprocess.check_output(
            ["systemctl", "show", "murphy-production",
             "-p", "NRestarts", "--value"]).decode().strip() or 0),
        "≤2"),
]

def _compare(expected, actual):
    """Compare expected vs actual. Handles ≥ and ≤ thresholds."""
    if isinstance(expected, str) and expected.startswith("≥"):
        try:
            threshold = int(expected[1:])
            return ("ok" if (isinstance(actual, int) and actual >= threshold) else "drift",
                    f"actual={actual} expected≥{threshold}")
        except ValueError:
            return ("error", f"bad threshold {expected}")
    if isinstance(expected, str) and expected.startswith("≤"):
        try:
            threshold = int(expected[1:])
            return ("ok" if (isinstance(actual, int) and actual <= threshold) else "drift",
                    f"actual={actual} expected≤{threshold}")
        except ValueError:
            return ("error", f"bad threshold {expected}")
    if expected == actual:
        return ("ok", f"actual={actual}")
    return ("drift", f"actual={actual} expected={expected}")

def run(quiet=False):
    t0 = time.time()
    results = []
    for key, desc, fn, expected in CHECKS:
        try:
            actual = fn()
        except Exception as e:
            actual = f"ERROR: {e}"
        status, detail = _compare(expected, actual)
        results.append({
            "key": key, "desc": desc, "expected": expected,
            "actual": actual, "status": status, "detail": detail,
        })
    elapsed_ms = int((time.time() - t0) * 1000)
    drifts = [r for r in results if r["status"] == "drift"]
    errors = [r for r in results if r["status"] == "error"]
    summary = {
        "ok": len(results) - len(drifts) - len(errors),
        "drift": len(drifts),
        "error": len(errors),
        "total": len(results),
        "elapsed_ms": elapsed_ms,
    }
    out = {"summary": summary, "results": results if not quiet else drifts + errors}
    return out

if __name__ == "__main__":
    quiet = "--quiet" in sys.argv
    out = run(quiet=quiet)
    print(json.dumps(out, indent=2, default=str))
    sys.exit(0 if out["summary"]["drift"] == 0 and out["summary"]["error"] == 0 else 1)
