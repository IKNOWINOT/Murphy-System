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
                    result = exec_admin.run_morning_brief(
                        account=signal.get("source", "cpost@murphy.systems")
                    )
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
        def drain_signals():
            try:
                from src.signal_collector import get_collector
                from src.rosetta_core import get_rosetta
                collector = get_collector()
                rosetta = get_rosetta()
                signals = collector.latest(limit=10)
                unprocessed = [s for s in signals if not s.get("processed")]
                for sig in unprocessed[:5]:
                    dag_id = rosetta.route_signal(sig)
                    if dag_id:
                        collector._db.mark_processed(sig["signal_id"], dag_id)
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
        def health_watchdog():
            try:
                from src.prod_ops_agent import get_prod_ops
                from src.signal_collector import get_collector
                result = get_prod_ops().health_watchdog()
                if result.get("overall") != "healthy":
                    get_collector().ingest(
                        signal_type="incident",
                        source="health_watchdog",
                        payload=result,
                        domain="prod_ops",
                        urgency="immediate",
                        stake="high",
                        intent_hint=f"Health degraded: {result.get('overall')}",
                    )
            except Exception as exc:
                logger.warning("Health watchdog error: %s", exc)

        self._scheduler.add_job(
            health_watchdog,
            trigger=IntervalTrigger(minutes=5),
            id="health_watchdog",
            name="ProdOps health watchdog",
            replace_existing=True,
            max_instances=1,
        )
        self._jobs["health_watchdog"] = {"name": "Health Watchdog", "interval": "5min", "type": "builtin"}

        # Job 3: Morning brief — daily at 08:00 UTC
        def morning_brief():
            try:
                from src.exec_admin_agent import get_exec_admin
                result = get_exec_admin().run_morning_brief(account="cpost@murphy.systems")
                logger.info("Morning brief complete: DAG=%s status=%s",
                            result.get("dag_id"), result.get("dag_status"))
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

        logger.info("SwarmScheduler: 3 built-in jobs registered")

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
        jobs = list(self._jobs.values())
        if self._scheduler:
            for job in self._scheduler.get_jobs():
                existing = next((j for j in jobs if j.get("id") == job.id), None)
                if not existing:
                    jobs.append({"id": job.id, "name": job.name, "next_run": str(job.next_run_time)})
        return jobs

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
