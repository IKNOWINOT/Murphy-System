"""
PATCH-118 — src/swarm_scheduler.py
Murphy System — Swarm Rosetta Scheduler

APScheduler-backed scheduler that:
  1. Wires agent handlers into RosettraCore on startup
  2. Registers 3 built-in jobs:
     - Every 30s: drain unprocessed signals through Rosetta
     - Every 5min: ProdOps health watchdog
     - Every day 08:00 local: ExecAdmin morning brief
  3. Exposes dynamic job management: add/remove NL-triggered schedules

This is the module that ACTIVATES the swarm — nothing runs until this starts.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.swarm_scheduler")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    _APScheduler_available = True
except ImportError:
    _APScheduler_available = False
    logger.warning("APScheduler not available — SwarmScheduler will use threading.Timer fallback")


class SwarmScheduler:
    """
    PATCH-118: Scheduler backbone for the Swarm Rosetta.
    Wires handlers and registers built-in jobs on start().
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone="UTC") if _APScheduler_available else None
        self._jobs: Dict[str, Dict] = {}
        self._started = False
        self._lock = threading.Lock()

    def start(self):
        """Wire all agent handlers and start all built-in jobs."""
        if self._started:
            return
        self._started = True

        self._wire_agent_handlers()
        self._register_builtin_jobs()

        if self._scheduler:
            self._scheduler.start()
            logger.info("PATCH-118: SwarmScheduler started — %d built-in jobs registered", len(self._jobs))
        else:
            logger.warning("SwarmScheduler: APScheduler unavailable — built-in jobs skipped")

    def _wire_agent_handlers(self):
        """Register handler callbacks on the Rosetta for each domain agent."""
        try:
            from src.rosetta_core import get_rosetta
            from src.exec_admin_agent import get_exec_admin
            from src.prod_ops_agent import get_prod_ops

            rosetta = get_rosetta()
            exec_admin = get_exec_admin()
            prod_ops = get_prod_ops()

            # ExecAdmin handles exec_admin domain signals
            def exec_admin_handler(signal: Dict) -> Optional[str]:
                intent = signal.get("intent_hint", "")
                if "email" in intent.lower():
                    result = exec_admin.triage_email(signal.get("raw_payload", {}))
                elif "meeting" in intent.lower() or "schedule" in intent.lower():
                    result = exec_admin.schedule_meeting(
                        participants=signal.get("entities", []),
                        topic=intent[:60],
                        account=signal.get("source", "unknown")
                    )
                else:
                    # Don't fire morning_brief on random signals — morning_brief has its own scheduled job
                    result = {"dag_id": "noop", "status": "skipped", "reason": "no matching intent"}
                dag_id = result.get("dag_id", "none")
                return dag_id

            # ProdOps handles prod_ops domain signals
            def prod_ops_handler(signal: Dict) -> Optional[str]:
                signal_type = signal.get("signal_type", "")
                if signal_type == "git":
                    result = prod_ops.handle_git_event(signal)
                elif signal_type == "telemetry":
                    result = prod_ops.handle_incident(signal)
                else:
                    result = prod_ops.health_watchdog()
                return result.get("dag_id", None)

            rosetta.register_handler("exec_admin", exec_admin_handler)
            rosetta.register_handler("prod_ops", prod_ops_handler)
            logger.info("SwarmScheduler: exec_admin + prod_ops handlers wired into Rosetta")

        except Exception as exc:
            logger.error("SwarmScheduler: handler wiring failed: %s", exc)

    def _register_builtin_jobs(self):
        """Register the 3 built-in scheduled jobs."""
        if not self._scheduler:
            return

        # Job 1: Signal drain — every 30 seconds
        # PATCH-170a: route through SwarmCoordinator.dispatch() so soul gate fires
        def drain_signals():
            try:
                from src.signal_collector import get_collector
                from src.rosetta_core import get_swarm_coordinator
                from src.swarm_bus import publish_result, record_bus_event
                import uuid as _uuid
                collector = get_collector()
                coord = get_swarm_coordinator()
                unprocessed = collector._db.unprocessed(limit=10)
                for sig in unprocessed[:5]:
                    # Ensure signal has an id
                    if not sig.get("signal_id"):
                        sig["signal_id"] = str(_uuid.uuid4())
                    dag_id = coord.dispatch(sig)
                    if dag_id:
                        try:
                            collector._db.mark_processed(sig["signal_id"], dag_id)
                        except Exception:
                            pass
                    # Record to bus feed for UI
                    record_bus_event({
                        "type": "signal_drain",
                        "signal_id": sig.get("signal_id",""),
                        "domain": sig.get("domain","system"),
                        "intent": sig.get("intent_hint","")[:80],
                        "dag_id": dag_id,
                        "agent": sig.get("domain","system"),
                        "ts": __import__('datetime').datetime.utcnow().isoformat(),
                    })
            except Exception as exc:
                logger.warning("Signal drain error: %s", exc)

        self._scheduler.add_job(
            drain_signals,
            trigger=IntervalTrigger(seconds=30),
            id="signal_drain",
            name="Swarm signal drain",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["signal_drain"] = {"name": "Signal Drain", "interval": "30s", "type": "builtin"}

        # Job 2: Health watchdog — every 5 minutes
        # PATCH-170a: dispatch through coord so runs_total increments
        def health_watchdog():
            try:
                from src.rosetta_core import get_swarm_coordinator
                from src.swarm_bus import publish_result, record_bus_event
                import uuid as _uuid
                coord = get_swarm_coordinator()
                sig = {
                    "signal_id": str(_uuid.uuid4()),
                    "signal_type": "health_check",
                    "domain": "prod_ops",
                    "urgency": "scheduled",
                    "stake": "low",
                    "intent_hint": "Scheduled health watchdog",
                    "source": "swarm_scheduler",
                }
                dag_id = coord.dispatch(sig)
                record_bus_event({
                    "type": "health_watchdog",
                    "signal_id": sig["signal_id"],
                    "domain": "prod_ops",
                    "intent": "Scheduled health watchdog",
                    "dag_id": dag_id,
                    "agent": "prod_ops",
                    "ts": __import__('datetime').datetime.utcnow().isoformat(),
                })
            except Exception as exc:
                logger.warning("Health watchdog error: %s", exc)

        self._scheduler.add_job(
            health_watchdog,
            trigger=IntervalTrigger(minutes=30),
            id="health_watchdog",
            name="ProdOps health watchdog",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["health_watchdog"] = {"name": "Health Watchdog", "interval": "30min", "type": "builtin"}

        # Job 3: Morning brief — daily at 08:00 UTC
        # PATCH-170a: dispatch through coord
        def morning_brief():
            try:
                from src.rosetta_core import get_swarm_coordinator
                from src.swarm_bus import publish_result, record_bus_event
                import uuid as _uuid
                coord = get_swarm_coordinator()
                sig = {
                    "signal_id": str(_uuid.uuid4()),
                    "signal_type": "morning_brief",
                    "domain": "exec_admin",
                    "urgency": "scheduled",
                    "stake": "low",
                    "intent_hint": "Daily morning brief — generate and email",
                    "source": "cpost@murphy.systems",
                }
                dag_id = coord.dispatch(sig)
                record_bus_event({
                    "type": "morning_brief",
                    "signal_id": sig["signal_id"],
                    "domain": "exec_admin",
                    "intent": "Daily morning brief",
                    "dag_id": dag_id,
                    "agent": "exec_admin",
                    "ts": __import__('datetime').datetime.utcnow().isoformat(),
                })
                logger.info("PATCH-170a: morning_brief dispatched via coord, dag_id=%s", dag_id)
            except Exception as exc:
                logger.warning("Morning brief error: %s", exc)

        self._scheduler.add_job(
            morning_brief,
            trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
            id="morning_brief",
            name="Executive morning brief",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["morning_brief"] = {"name": "Morning Brief", "interval": "daily 08:00 UTC", "type": "builtin"}


        # Job 4: WorldCorpus collect — every 15 minutes
        # PATCH-170a: dispatch through coord (collector domain)
        def corpus_collect():
            try:
                from src.rosetta_core import get_swarm_coordinator
                from src.swarm_bus import record_bus_event
                import uuid as _uuid
                coord = get_swarm_coordinator()
                sig = {
                    "signal_id": str(_uuid.uuid4()),
                    "signal_type": "corpus_collect",
                    "domain": "collector",
                    "urgency": "scheduled",
                    "stake": "low",
                    "intent_hint": "WorldCorpus scheduled collection",
                    "source": "swarm_scheduler",
                }
                # collector agent handles corpus_collect
                # if collector not wired for this signal_type, call directly and record
                try:
                    dag_id = coord.dispatch(sig)
                except Exception:
                    dag_id = None
                if not dag_id:
                    from src.world_corpus import get_world_corpus
                    counts = get_world_corpus().collect_all()
                    logger.info("WorldCorpus collect (direct): %s", counts)
                record_bus_event({
                    "type": "corpus_collect",
                    "signal_id": sig["signal_id"],
                    "domain": "collector",
                    "intent": "WorldCorpus scheduled collection",
                    "dag_id": dag_id,
                    "agent": "collector",
                    "ts": __import__('datetime').datetime.utcnow().isoformat(),
                })
            except Exception as exc:
                logger.warning("WorldCorpus collect error: %s", exc)

        self._scheduler.add_job(
            corpus_collect,
            trigger=IntervalTrigger(minutes=15),
            id="corpus_collect",
            name="WorldCorpus data collection",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["corpus_collect"] = {"name": "WorldCorpus Collect", "interval": "15min", "type": "builtin"}

        # Job 5: Swarm heartbeat — every 5 minutes, all 9 agents get a status signal
        # PATCH-170: ensures every agent runs, soul gate fires, runs_total increments for all
        def swarm_heartbeat():
            try:
                from src.rosetta_core import get_swarm_coordinator
                from src.swarm_bus import record_bus_event
                import uuid as _uuid
                coord = get_swarm_coordinator()
                _ALL_DOMAINS = [
                    "collector", "translator", "scheduler", "executor",
                    "auditor", "exec_admin", "prod_ops", "hitl", "rosetta"
                ]
                _ts = __import__('datetime').datetime.utcnow().isoformat()
                for _dom in _ALL_DOMAINS:
                    _sid = str(_uuid.uuid4())
                    coord.dispatch({
                        "signal_id": _sid,
                        "signal_type": "heartbeat",
                        "domain": _dom,
                        "urgency": "scheduled",
                        "stake": "low",
                        "intent_hint": f"Swarm heartbeat — {_dom}",
                        "source": "swarm_scheduler",
                    })
                    record_bus_event({
                        "type": "heartbeat",
                        "signal_id": _sid,
                        "domain": _dom,
                        "agent_id": _dom,
                        "intent": f"Swarm heartbeat — {_dom}",
                        "ts": _ts,
                    })
            except Exception as exc:
                logger.warning("Swarm heartbeat error: %s", exc)

        self._scheduler.add_job(
            swarm_heartbeat,
            trigger=IntervalTrigger(minutes=5),
            id="swarm_heartbeat",
            name="Swarm-wide heartbeat",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["swarm_heartbeat"] = {"name": "Swarm Heartbeat", "interval": "30min", "type": "builtin"}

        # PATCH-173: Cognitive Executive — AionMind runs the executive every 30 minutes
        def revenue_driver_cycle():
            try:
                from src.cognitive_executive import run_cognitive_revenue_cycle
                result = run_cognitive_revenue_cycle()
                logger.info(
                    "Cognitive executive cycle: status=%s blockers=%d directives=%d",
                    result.get("cognitive_status", "?"),
                    result.get("blockers_found", 0),
                    result.get("directives_issued", 0),
                )
            except Exception as exc:
                logger.warning("Cognitive executive cycle error: %s", exc)

        self._scheduler.add_job(
            revenue_driver_cycle,
            trigger=IntervalTrigger(minutes=30),
            id="revenue_driver",
            name="Executive Revenue Driver",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["revenue_driver"] = {"name": "Revenue Driver", "interval": "30min", "type": "builtin"}

        # PATCH-174: Autonomous API Acquirer — runs every 6 hours
        def api_acquisition_cycle():
            try:
                from src.autonomous_api_acquirer import run_acquisition_cycle
                result = run_acquisition_cycle()
                logger.info(
                    "API Acquirer: %d active, %d pending, %d failed",
                    result.get("tier1_active", 0),
                    result.get("tier2_pending", 0),
                    result.get("failed", 0),
                )
            except Exception as exc:
                logger.warning("API acquisition cycle error: %s", exc)

        self._scheduler.add_job(
            api_acquisition_cycle,
            trigger=IntervalTrigger(hours=6),
            id="api_acquisition",
            name="Autonomous API Acquirer",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["api_acquisition"] = {"name": "API Acquirer", "interval": "6h", "type": "builtin"}

        logger.info("SwarmScheduler: 7 built-in jobs registered")

    def add_nl_job(self, nl_text: str, cron_expr: str, account: str = "unknown") -> str:
        """Add a dynamically-scheduled job from an NL-specified schedule."""
        import uuid
        if not self._scheduler:
            return "error: scheduler not available"

        job_id = f"nl-{uuid.uuid4().hex[:8]}"

        def nl_job():
            try:
                from src.rosetta_core import get_rosetta
                get_rosetta().translate(nl_text, account=account, execute=True)
            except Exception as exc:
                logger.warning("NL job %s error: %s", job_id, exc)

        try:
            parts = cron_expr.split()
            self._scheduler.add_job(
                nl_job,
                trigger=CronTrigger(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day=parts[2] if len(parts) > 2 else "*",
                    month=parts[3] if len(parts) > 3 else "*",
                    day_of_week=parts[4] if len(parts) > 4 else "*",
                ),
                id=job_id,
                name=nl_text[:60],
                replace_existing=True,
                max_instances=1,
            )
            self._jobs[job_id] = {"name": nl_text[:60], "cron": cron_expr, "account": account, "type": "nl"}
            logger.info("SwarmScheduler: NL job added %s [%s]", job_id, cron_expr)
            return job_id
        except Exception as exc:
            logger.error("SwarmScheduler: add_nl_job failed: %s", exc)
            return f"error: {exc}"

    def remove_job(self, job_id: str) -> bool:
        if self._scheduler and self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
            return True
        return False

    def list_jobs(self) -> List[Dict]:
        result = []
        for jid, jinfo in self._jobs.items():
            entry = {"id": jid, **jinfo}
            if self._scheduler:
                try:
                    apjob = self._scheduler.get_job(jid)
                    if apjob:
                        entry["next_run"] = str(apjob.next_run_time)
                except Exception:
                    pass
            result.append(entry)
        return result

    def status(self) -> Dict:
        return {
            "running": self._started,
            "apscheduler": _APScheduler_available,
            "jobs": len(self._jobs),
            "job_list": self.list_jobs(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_scheduler: Optional[SwarmScheduler] = None
_sched_lock = threading.Lock()

def get_scheduler() -> SwarmScheduler:
    global _scheduler
    if _scheduler is None:
        with _sched_lock:
            if _scheduler is None:
                _scheduler = SwarmScheduler()
    return _scheduler


def restore_workflow_schedules() -> int:
    """PATCH-140: Re-register all active cron workflow schedules from DB at boot.
    Source: nl_workflows.db blueprints table (data JSON field).
    """
    count = 0
    try:
        import sqlite3 as _sq, json as _json
        db_path = "/var/lib/murphy-production/nl_workflows.db"
        conn = _sq.connect(db_path)
        rows = conn.execute(
            "SELECT workflow_id, account_id, data FROM blueprints"
        ).fetchall()
        conn.close()
        # Convert to expected format: (blueprint_id, job_id, account_id, data_json)
        rows = [(r[0], f"wf_{r[0][:8]}", r[1], r[2]) for r in rows]

        sched = get_scheduler()
        _aps  = sched._scheduler
        if _aps is None:
            logger.warning("PATCH-140: restore_workflow_schedules — APScheduler not available")
            return 0

        for bp_id, job_id, account_id, data_json in rows:
            try:
                if not data_json:
                    continue
                blueprint = _json.loads(data_json)
                schedule  = blueprint.get("schedule", {})
                expr      = schedule.get("expr") or blueprint.get("trigger", {}).get("expr")
                label     = schedule.get("label", job_id)
                steps     = blueprint.get("steps", [])
                wf_id     = blueprint.get("workflow_id", bp_id)

                if not expr:
                    continue

                # Skip if already registered (survive multiple calls)
                if _aps.get_job(job_id):
                    continue

                from apscheduler.triggers.cron import CronTrigger as _CT

                def _make_runner(steps_=steps, wf_id_=wf_id, account_id_=account_id, job_id_=job_id):
                    def _run():
                        try:
                            from src.workflow_executor import execute_workflow
                            from src.automation_request import _save_run
                            ctx = execute_workflow(steps_, wf_id_, account_id_, {"cron_fired": True})
                            _save_run(ctx)
                        except Exception as e:
                            logger.error("Restored workflow job %s error: %s", job_id_, e)
                    return _run

                parts = expr.strip().split()
                if len(parts) == 5:
                    trigger = _CT(minute=parts[0], hour=parts[1], day=parts[2],
                                  month=parts[3], day_of_week=parts[4])
                else:
                    continue

                _aps.add_job(
                    _make_runner(), trigger=trigger, id=job_id,
                    name=f"wf: {label[:60]}", replace_existing=True, max_instances=1,
                )
                sched._jobs[job_id] = {
                    "name": label[:60], "cron": expr,
                    "account": account_id, "type": "workflow", "wf_id": wf_id,
                }
                count += 1
                logger.info("PATCH-140: restored workflow job %s [%s] cron=%s", job_id, wf_id[:8], expr)
            except Exception as e:
                logger.warning("PATCH-140: failed to restore job %s: %s", job_id, e)

    except Exception as e:
        logger.error("PATCH-140: restore_workflow_schedules error: %s", e)

    logger.info("PATCH-140: boot schedule restore complete — %d jobs re-registered", count)
    return count
