"""PCR-070 Stage 3 — Scheduled perspective re-distillation heartbeat.

Pattern mirrors PCR-053f (shadow tick):
  - register_heartbeat(app, interval_minutes) attempts to add a job to
    the app's APScheduler.
  - If scheduler not yet attached, spawn a background polling thread
    that registers the job once the scheduler appears.
  - Self-deferring, idempotent, non-blocking on startup.

Tick behavior:
  - List all distinct (role_id, jurisdiction, tenant_id) tuples from
    accumulated practitioner data.
  - For each tuple, re-distill and persist.
  - Per L160 + Stage 1 design: old perspective rows are not deleted,
    they're marked superseded_at — full audit history preserved.

Default cadence: every 60 minutes. Configurable via env var
PCR070_HEARTBEAT_INTERVAL_MIN.
"""
from __future__ import annotations
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("pcr070.heartbeat")
ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"

DEFAULT_INTERVAL_MIN = int(os.environ.get("PCR070_HEARTBEAT_INTERVAL_MIN", "60"))
JOB_ID = "pcr070_perspective_tick"


def _find_scheduler(app: Any) -> Optional[Any]:
    """Locate the canonical APScheduler — mirrors PCR-053f.2 lookup exactly.

    PCR-053f.2 lessons:
      - The canonical singleton lives in src.swarm_scheduler as module-level
        _scheduler.  Check that FIRST.
      - app.state.scheduler may be added later.
      - murphy is a module-level local in src.runtime.app — reach it via
        sys.modules, not importlib.import_module (the module is loaded
        once and not re-importable in the standard path).
    """
    import sys
    # Try 0 — canonical SwarmScheduler singleton
    try:
        from src.swarm_scheduler import _scheduler as _sched_mod  # type: ignore
        inner = getattr(_sched_mod, "_scheduler", None)
        if inner is not None:
            return inner
    except Exception:
        pass
    # Try 1 — app.state.scheduler
    if app is not None:
        sched = getattr(getattr(app, "state", None), "scheduler", None)
        if sched is not None:
            return sched
    # Try 2 — walk murphy var in src.runtime.app via sys.modules
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
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is not None:
            return sched
    return None



def discover_tuples() -> List[Tuple[str, str, Optional[str]]]:
    """Find all (role_id, jurisdiction, tenant_id) tuples to distill.

    Pulls distinct tuples from:
      - practitioner_corpus_entries  (role_id, jurisdiction, tenant_id)
      - engagement_folders           (role_id, jurisdiction_required, tenant_id)
    """
    tuples = set()
    try:
        c = sqlite3.connect(f"file:{ENGAGEMENT_DB}?mode=ro", uri=True, timeout=2.0)
        try:
            for r in c.execute(
                "SELECT DISTINCT role_id, jurisdiction, tenant_id "
                "FROM practitioner_corpus_entries"
            ).fetchall():
                tuples.add((r[0], r[1], r[2]))
            for r in c.execute(
                "SELECT DISTINCT role_id, jurisdiction_required, tenant_id "
                "FROM engagement_folders WHERE jurisdiction_required IS NOT NULL"
            ).fetchall():
                tuples.add((r[0], r[1], r[2]))
        finally:
            c.close()
    except Exception as e:
        LOG.warning("PCR-070 discovery failed: %s", e)
    return sorted(tuples)


def perspective_tick(audit_db_path: Optional[str] = None) -> Dict[str, Any]:
    """One heartbeat tick — re-distill all known (role, jur, tenant) tuples.

    Returns a status dict for observability.
    """
    start = time.time()
    result = {
        "started_at": start,
        "tuples_seen": 0,
        "distilled": 0,
        "skipped_empty": 0,
        "errors": [],
    }
    try:
        from pcr070_perspective_distiller import distill_and_persist
    except Exception as e:
        result["errors"].append(f"distiller_import: {e}")
        return result

    tuples = discover_tuples()
    result["tuples_seen"] = len(tuples)
    for role_id, jur, tenant in tuples:
        try:
            vid, p = distill_and_persist(role_id, jur, tenant)
            srcs = p.get("sources") or {}
            total = sum(int(v or 0) for v in srcs.values())
            if total == 0:
                result["skipped_empty"] += 1
            else:
                result["distilled"] += 1
        except Exception as e:
            result["errors"].append(f"{role_id}/{jur}/{tenant}: {e}")

    result["elapsed_s"] = round(time.time() - start, 2)
    LOG.info(
        "PCR-070 tick: %d tuples, %d distilled, %d empty, %d errors, %.2fs",
        result["tuples_seen"], result["distilled"], result["skipped_empty"],
        len(result["errors"]), result["elapsed_s"],
    )
    return result


def _do_add_job(scheduler: Any, interval_minutes: int) -> None:
    """Add the perspective tick job to the scheduler. Idempotent."""
    try:
        existing = scheduler.get_job(JOB_ID)
        if existing:
            return  # already scheduled
    except Exception:
        pass
    scheduler.add_job(
        perspective_tick,
        trigger="interval",
        minutes=interval_minutes,
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def register_heartbeat(app: Any, interval_minutes: int = DEFAULT_INTERVAL_MIN) -> Dict[str, Any]:
    """Register the PCR-070 perspective tick — self-deferring if scheduler
    isn't ready yet."""
    status = {
        "scheduled": False,
        "scheduler_present": False,
        "deferred": False,
        "interval_minutes": interval_minutes,
        "errors": [],
    }

    scheduler = _find_scheduler(app)
    if scheduler is not None:
        status["scheduler_present"] = True
        try:
            _do_add_job(scheduler, interval_minutes)
            status["scheduled"] = True
            LOG.info("PCR-070 heartbeat scheduled (interval=%dm)", interval_minutes)
        except Exception as e:
            LOG.warning("PCR-070 immediate registration failed: %s", e)
            status["errors"].append(f"register: {e}")
        return status

    # Defer — spawn a polling thread that registers when the scheduler appears
    status["deferred"] = True

    def _poll_and_register():
        for _ in range(60):  # 60 * 5s = 5 min max wait
            time.sleep(5)
            sched = _find_scheduler(app)
            if sched is not None:
                try:
                    _do_add_job(sched, interval_minutes)
                    LOG.info("PCR-070 heartbeat scheduled after defer (interval=%dm)", interval_minutes)
                    return
                except Exception as e:
                    LOG.warning("PCR-070 deferred registration failed: %s", e)
                    return
        LOG.warning("PCR-070 deferred registration timed out — scheduler never appeared")

    t = threading.Thread(target=_poll_and_register, name="pcr070-defer", daemon=True)
    t.start()
    return status
