"""
PCR-053f — Shadow Loop Heartbeat

Every interval, scan accumulated shadow observations and update an
audit-trail row per role that records the current multi-dim N verdict.
This is the "always watching" piece — turns the org_compiler from a
pull-only API into a live continuous monitor.

What it does each tick:
  1. Iterate every role with telemetry in app.state.shadow_collector
  2. For each role, derive observed (window_days, distinct_operators,
     max_money_seen, regulations).
  3. Look up the regulatory floor for that role's (jurisdiction, industry).
     - jurisdiction comes from a per-role override map (PCR-053g will seed
       this from the onboarding form); falls back to a system default
     - if no floor is found, the tick records a fail-closed snapshot
       and emits a loud warning log
  4. Compute the multi-dim N verdict via evaluate_against_floor()
  5. Write a snapshot row into shadow_audit_snapshots so the founder
     can see the verdict history per role

Idempotent: scheduled with id='org_compiler_shadow_tick',
replace_existing=True. Calling register_heartbeat() twice is a no-op.

Fail-soft: any error in the tick is caught and logged at WARNING;
the scheduled job keeps running.

Locked defaults:
  - default_jurisdiction = "US-CA" (Corey, 2026-06-09)
  - default_industry     = "saas"  (Corey, 2026-06-09)
  - Any role override may set its own (jurisdiction, industry)
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("murphy.org_compiler_heartbeat")


# Locked defaults — see PCR-053f memory doc
DEFAULT_JURISDICTION = "US-CA"
DEFAULT_INDUSTRY     = "saas"

# Where audit snapshots get written.
DEFAULT_AUDIT_DB = os.environ.get(
    "MURPHY_SHADOW_AUDIT_DB",
    "/var/lib/murphy-production/murphy_audit.db",
)


# ──────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────


_SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_audit_snapshots (
    snapshot_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at                 REAL    NOT NULL,         -- unix seconds
    role                     TEXT    NOT NULL,
    role_family              TEXT    NOT NULL,
    jurisdiction             TEXT,
    industry                 TEXT,
    events_observed          INTEGER NOT NULL,
    observation_window_days  INTEGER NOT NULL,
    distinct_operators_seen  INTEGER NOT NULL,
    max_money_seen_usd       REAL    NOT NULL,
    floor_source             TEXT    NOT NULL,
    passes                   INTEGER NOT NULL,         -- 0/1
    fail_closed              INTEGER NOT NULL,         -- 0/1
    reasons_json             TEXT    NOT NULL,
    tick_id                  TEXT    NOT NULL          -- groups all rows from one tick
);
CREATE INDEX IF NOT EXISTS idx_shadow_audit_role     ON shadow_audit_snapshots(role);
CREATE INDEX IF NOT EXISTS idx_shadow_audit_taken_at ON shadow_audit_snapshots(taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_shadow_audit_tick     ON shadow_audit_snapshots(tick_id);
"""


def _ensure_schema(db_path: str) -> None:
    con = sqlite3.connect(db_path, timeout=15.0)
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


# ──────────────────────────────────────────────────────────────
# Per-role override map (PCR-053g will seed this from onboarding;
# for now expose a simple in-memory dict the founder can patch.)
# ──────────────────────────────────────────────────────────────


# role_name -> {"jurisdiction": str, "industry": str}
ROLE_OVERRIDES: Dict[str, Dict[str, str]] = {}


def set_role_jurisdiction(role: str, jurisdiction: str, industry: Optional[str] = None) -> None:
    """Caller (or PCR-053g seeder) sets a per-role jurisdiction override."""
    ROLE_OVERRIDES[role] = {
        "jurisdiction": jurisdiction,
        "industry":     industry or DEFAULT_INDUSTRY,
    }


# ──────────────────────────────────────────────────────────────
# The tick
# ──────────────────────────────────────────────────────────────


def _collect_roles_from_shadow(collector: Any) -> List[str]:
    """Walk TelemetryCollector flat-list storage and return unique role names.
    Mirrors the logic added in PCR-053d-fix."""
    roles: List[str] = []
    for ev_list_name in ("task_assignments", "approvals", "failures"):
        for ev in getattr(collector, ev_list_name, []) or []:
            rname = ev.get("role") if isinstance(ev, dict) else None
            if rname and rname not in roles:
                roles.append(rname)
    for h in getattr(collector, "handoffs", []) or []:
        for attr in ("from_role", "to_role"):
            rname = getattr(h, attr, None)
            if rname and rname not in roles:
                roles.append(rname)
    return roles


def _derive_dimensions(collector: Any, role: str) -> Tuple[int, int, int, float]:
    """Return (events, window_days, distinct_operators, max_money_seen_usd)."""
    t = collector.get_telemetry_for_role(role)
    tasks = t.get("task_assignments", [])
    events = sum(len(v) if isinstance(v, list) else 0 for v in t.values())

    distinct_ops = len({
        (ev.get("metadata") or {}).get("operator", "unknown")
        for ev in tasks
    }) or 1

    if tasks:
        timestamps = [ev.get("timestamp") for ev in tasks
                      if isinstance(ev.get("timestamp"), datetime)]
        span_days = ((max(timestamps) - min(timestamps)).days + 1) if timestamps else 0
    else:
        span_days = 0

    max_money = 0.0
    for ev in tasks:
        m = (ev.get("metadata") or {}).get("deal_size_usd")
        if isinstance(m, (int, float)) and m > max_money:
            max_money = float(m)

    return events, span_days, distinct_ops, max_money


def run_tick(
    collector: Any,
    db_path: str = DEFAULT_AUDIT_DB,
    tick_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one heartbeat tick. Returns a summary dict for logging.

    This is the function the scheduler fires. It is also unit-testable
    on its own — passes collector + db_path directly, no globals.
    """
    import json
    from org_compiler.regulatory_floor import evaluate_against_floor

    if tick_id is None:
        tick_id = f"tick_{int(time.time())}"

    _ensure_schema(db_path)
    taken_at = time.time()

    summary = {
        "tick_id":          tick_id,
        "roles_processed":  0,
        "verdicts_passed":  0,
        "verdicts_blocked": 0,
        "fail_closed":      0,
        "errors":           [],
    }

    try:
        roles = _collect_roles_from_shadow(collector)
    except Exception as e:
        LOG.warning("PCR-053f tick collector scan failed: %s", e)
        summary["errors"].append(f"collector_scan: {e}")
        return summary

    if not roles:
        LOG.debug("PCR-053f tick %s: no roles observed yet", tick_id)
        return summary

    con = sqlite3.connect(db_path, timeout=15.0)
    try:
        for role in roles:
            try:
                events, span_days, distinct_ops, max_money = _derive_dimensions(collector, role)
                role_family = role.lower().replace(" ", "_")

                override = ROLE_OVERRIDES.get(role, {})
                jurisdiction = override.get("jurisdiction", DEFAULT_JURISDICTION)
                industry     = override.get("industry", DEFAULT_INDUSTRY)

                verdict = evaluate_against_floor(
                    jurisdiction=jurisdiction,
                    industry=industry,
                    role_family=role_family,
                    observation_window_days=span_days,
                    distinct_operators_observed=distinct_ops,
                    decision_ceiling_usd=max_money if max_money > 0 else None,
                    compliance_regulations=("audit_trail",),
                )

                con.execute(
                    "INSERT INTO shadow_audit_snapshots ("
                    " taken_at, role, role_family, jurisdiction, industry,"
                    " events_observed, observation_window_days, distinct_operators_seen,"
                    " max_money_seen_usd, floor_source, passes, fail_closed, reasons_json,"
                    " tick_id"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        taken_at, role, role_family, jurisdiction, industry,
                        events, span_days, distinct_ops, max_money,
                        verdict.floor_source,
                        1 if verdict.passes else 0,
                        1 if verdict.fail_closed else 0,
                        json.dumps(list(verdict.reasons)),
                        tick_id,
                    ),
                )

                summary["roles_processed"] += 1
                if verdict.passes:
                    summary["verdicts_passed"] += 1
                else:
                    summary["verdicts_blocked"] += 1
                if verdict.fail_closed:
                    summary["fail_closed"] += 1
                    LOG.warning(
                        "PCR-053f: fail-closed verdict for role=%r (j=%s i=%s)",
                        role, jurisdiction, industry,
                    )
            except Exception as e:
                LOG.warning("PCR-053f tick role=%r failed: %s", role, e)
                summary["errors"].append(f"{role}: {e}")
        con.commit()
    finally:
        con.close()

    LOG.info(
        "PCR-053f tick %s: roles=%d passed=%d blocked=%d fail_closed=%d errors=%d",
        tick_id,
        summary["roles_processed"],
        summary["verdicts_passed"],
        summary["verdicts_blocked"],
        summary["fail_closed"],
        len(summary["errors"]),
    )
    return summary


# ──────────────────────────────────────────────────────────────
# Registration with the running APScheduler
# ──────────────────────────────────────────────────────────────


def _find_scheduler(app):
    """Find the canonical APScheduler instance. Returns None if not ready yet.

    PCR-053f-fix-v2: murphy is a module-level local in src.runtime.app
    (line ~4111), not a class with a get_*() helper. The way other code
    reaches it (e.g. forge_rate_limiter) is via sys.modules.
    """
    import sys
    # PCR-053f.2: Try 0 — the canonical SwarmScheduler singleton lives in
    # src.swarm_scheduler as module-level _scheduler, accessed via
    # get_scheduler(). This is the path that actually has the running
    # APScheduler instance in production. Checked FIRST.
    try:
        from src.swarm_scheduler import get_scheduler as _gs, _scheduler as _sched_mod
        if _sched_mod is not None and getattr(_sched_mod, "_scheduler", None) is not None:
            return _sched_mod._scheduler
    except Exception:
        pass
    # Try 1: app.state.scheduler (canonical attachment, may be added later)
    sched = getattr(getattr(app, "state", None), "scheduler", None)
    if sched is not None:
        return sched
    # Try 2: murphy var in src.runtime.app
    for mod_name in ("src.runtime.app", "runtime.app"):
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        murphy = getattr(mod, "murphy", None)
        if murphy is None:
            continue
        ss = getattr(murphy, "swarm_scheduler", None)
        if ss is None:
            continue
        sched = getattr(ss, "_scheduler", None)
        if sched is not None:
            return sched
        # Some MurphySystem variants expose .scheduler directly
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is not None:
            return sched
    return None


def _do_add_job(scheduler, app, interval_minutes, db_path):
    """Build the tick closure and add it to the scheduler. Idempotent."""
    def _run_shadow_tick():
        try:
            collector = getattr(getattr(app, "state", None), "shadow_collector", None)
            if collector is None:
                LOG.debug("PCR-053f: no shadow_collector on app.state — skipping tick")
                return
            run_tick(collector, db_path=db_path)
        except Exception as e:
            LOG.warning("PCR-053f tick threw (caught): %s", e)

    try:
        from apscheduler.triggers.interval import IntervalTrigger
        trigger = IntervalTrigger(minutes=interval_minutes)
    except Exception:
        trigger = None

    scheduler.add_job(
        _run_shadow_tick,
        trigger,
        id="org_compiler_shadow_tick",
        name=f"PCR-053f shadow tick (every {interval_minutes}m)",
        replace_existing=True,
    )
    LOG.info("PCR-053f: shadow tick registered, interval=%dm", interval_minutes)


def register_heartbeat(
    app: Any,
    interval_minutes: int = 10,
    db_path: str = DEFAULT_AUDIT_DB,
) -> Dict[str, Any]:
    """Register the shadow tick on the app's APScheduler. Idempotent.

    PCR-053f-fix: self-deferring. If the scheduler isn't attached to
    murphy_system yet (lifespan order issue), spawn a background thread
    that polls every 5s (up to 5 min) and registers the job the moment
    the scheduler appears. Returns immediately so startup is not blocked.
    """
    status = {
        "scheduled":         False,
        "scheduler_present": False,
        "deferred":          False,
        "interval_minutes":  interval_minutes,
        "errors":            [],
    }

    scheduler = _find_scheduler(app)
    if scheduler is not None:
        status["scheduler_present"] = True
        try:
            _do_add_job(scheduler, app, interval_minutes, db_path)
            status["scheduled"] = True
        except Exception as e:
            LOG.warning("PCR-053f immediate registration failed: %s", e)
            status["errors"].append(f"register: {e}")
        return status

    # Defer
    import threading
    def _waiter():
        for attempt in range(60):  # 60 * 5s = 5 min (PCR-053f.2: lookup fixed, defer rarely fires)
            time.sleep(5)
            sched = _find_scheduler(app)
            if sched is not None:
                try:
                    _do_add_job(sched, app, interval_minutes, db_path)
                    LOG.info("PCR-053f: deferred registration succeeded after %d attempts", attempt + 1)
                except Exception as e:
                    LOG.warning("PCR-053f deferred registration failed: %s", e)
                return
        LOG.warning("PCR-053f: scheduler never appeared after 5 min, giving up")

    threading.Thread(target=_waiter, name="pcr053f-deferred-register", daemon=True).start()
    status["deferred"] = True
    LOG.info("PCR-053f: scheduler not yet available; deferring registration to background thread")
    return status


__all__ = [
    "run_tick",
    "register_heartbeat",
    "set_role_jurisdiction",
    "ROLE_OVERRIDES",
    "DEFAULT_JURISDICTION",
    "DEFAULT_INDUSTRY",
    "DEFAULT_AUDIT_DB",
]
