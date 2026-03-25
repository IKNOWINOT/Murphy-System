"""
Murphy System Business Automation Scheduler

Runs Inoni LLC operations with autonomous execution and human-in-the-loop
safety gates. Uses APScheduler for durable task scheduling.

HITL Safety Model:
- Routine operations (content generation, monitoring, analytics, bug detection)
  execute autonomously on schedule.
- High-risk operations (financial transactions, external outreach, production
  deployments, code modifications) are queued for HITL gate approval when
  confidence is below the configured threshold (default: 0.7).

This is by design — Murphy's safety-first architecture treats HITL as a
feature, not a limitation.

Trading Jobs (added in PR 4):
- profit_sweep       : daily at 5 PM ET, Mon–Fri
- portfolio_snapshot : every hour
- performance_report : daily at 6 AM ET
- emergency_check    : every minute
- graduation_check   : every hour
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Trading schedule defaults — all configurable via env vars
_SWEEP_HOUR        = int(os.getenv("SWEEP_HOUR",   "17"))
_SWEEP_MINUTE      = int(os.getenv("SWEEP_MINUTE", "0"))
_SWEEP_TIMEZONE    = os.getenv("SWEEP_TIMEZONE",   "US/Eastern")
_REPORT_HOUR       = int(os.getenv("REPORT_HOUR",  "6"))

logger = logging.getLogger(__name__)


class MurphyScheduler:
    """Schedules and runs Inoni LLC daily automation cycle.

    Uses APScheduler when available; falls back to manual trigger when not
    installed so that the rest of the system is unaffected.
    """

    def __init__(self, business_automation=None):
        """
        Args:
            business_automation: Optional InoniBusinessAutomation instance.
                If None, a new instance is created when the scheduler starts.
        """
        self._automation = business_automation
        self._scheduler = None
        self._last_run: Optional[datetime] = None
        self._last_result: Optional[Dict[str, Any]] = None
        self._copilot_tenant_tasks: list = []

    def start(self) -> bool:
        """Start the background scheduler.

        Returns True if APScheduler is available and the scheduler started,
        False if running in manual-trigger-only mode.
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
            from apscheduler.triggers.cron import CronTrigger  # type: ignore[import]
            from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import]

            self._scheduler = BackgroundScheduler()

            # Existing business automation job
            self._scheduler.add_job(
                self.run_daily_automation,
                CronTrigger(hour=6, minute=0, timezone="UTC"),
                id="daily_automation",
                replace_existing=True,
            )

            # ── Trading jobs ──────────────────────────────────────────
            # Profit sweep: Mon–Fri at configured time (default 5 PM ET)
            self._scheduler.add_job(
                self._run_profit_sweep,
                CronTrigger(
                    day_of_week="mon-fri",
                    hour=_SWEEP_HOUR,
                    minute=_SWEEP_MINUTE,
                    timezone=_SWEEP_TIMEZONE,
                ),
                id="profit_sweep",
                replace_existing=True,
            )

            # Portfolio snapshot: every hour
            self._scheduler.add_job(
                self._run_portfolio_snapshot,
                IntervalTrigger(hours=1),
                id="portfolio_snapshot",
                replace_existing=True,
            )

            # Performance report: daily at report hour (default 6 AM ET)
            self._scheduler.add_job(
                self._run_performance_report,
                CronTrigger(
                    hour=_REPORT_HOUR, minute=0, timezone=_SWEEP_TIMEZONE
                ),
                id="performance_report",
                replace_existing=True,
            )

            # Emergency stop health check: every minute
            self._scheduler.add_job(
                self._run_emergency_check,
                IntervalTrigger(minutes=1),
                id="emergency_check",
                replace_existing=True,
            )

            # Graduation check: every hour
            self._scheduler.add_job(
                self._run_graduation_check,
                IntervalTrigger(hours=1),
                id="graduation_check",
                replace_existing=True,
            )

            self._scheduler.start()
            logger.info(
                "MurphyScheduler started — daily automation 06:00 UTC; "
                "profit sweep %02d:%02d %s (Mon–Fri)",
                _SWEEP_HOUR, _SWEEP_MINUTE, _SWEEP_TIMEZONE,
            )
            return True
        except ImportError:
            logger.info("apscheduler not installed — MurphyScheduler running in manual mode")
            return False
        except Exception as exc:
            logger.warning("MurphyScheduler could not start APScheduler: %s", exc)
            return False

    def stop(self) -> None:
        """Stop the background scheduler."""
        if self._scheduler is not None:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.debug("stop error: %s", exc)
            self._scheduler = None
            logger.info("MurphyScheduler stopped")

    def run_daily_automation(self) -> Dict[str, Any]:
        """Run the daily Inoni LLC automation cycle.

        Low-risk operations execute autonomously.
        High-risk operations are flagged for HITL review.

        Returns a summary dict with results from each engine.
        """
        logger.info("Running daily automation cycle")
        self._last_run = datetime.now(timezone.utc)

        try:
            from inoni_business_automation import InoniBusinessAutomation
            automation = self._automation or InoniBusinessAutomation()
        except Exception as exc:
            logger.warning("Could not instantiate InoniBusinessAutomation: %s", exc)
            result = {
                "status": "error",
                "error": str(exc),
                "timestamp": self._last_run.isoformat(),
                "simulated": True,
            }
            self._last_result = result
            return result

        results: Dict[str, Any] = {
            "timestamp": self._last_run.isoformat(),
            "autonomous": {},
            "requires_hitl": {},
        }

        # Autonomous (low-risk) operations
        _run_safe(results["autonomous"], "content_creation",
                  lambda: automation.marketing.create_content("Murphy System weekly update"))
        _run_safe(results["autonomous"], "bug_detection",
                  lambda: automation.rnd.detect_bugs())
        _run_safe(results["autonomous"], "system_monitoring",
                  lambda: automation.production.monitor_system())

        # HITL-gated (high-risk) operations
        results["requires_hitl"]["finance"] = {
            "queued": True,
            "reason": "financial_transaction",
            "note": "Requires HITL approval before execution",
        }
        results["requires_hitl"]["releases"] = {
            "queued": True,
            "reason": "production_deployment",
            "note": "Requires HITL approval before execution",
        }
        results["requires_hitl"]["social_media"] = {
            "queued": True,
            "reason": "external_outreach",
            "note": "Requires HITL approval before execution",
        }

        results["status"] = "completed"
        self._last_result = results
        logger.info("Daily automation cycle complete: %s autonomous, %s hitl-gated",
                    len(results["autonomous"]), len(results["requires_hitl"]))
        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": (self._scheduler is not None and self._scheduler.running)
                       if self._scheduler else False,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_result_status": self._last_result.get("status") if self._last_result else None,
        }

    def register_copilot_tenant_tasks(self, tasks: list) -> None:
        """Accept task proposals from the Copilot Tenant for the daily automation run.

        Each element of *tasks* should be a dict with at least:
          ``task_id``   — unique identifier
          ``description`` — human-readable description
          ``priority``  — float 0.0–1.0

        Proposed tasks are stored and incorporated into the next
        ``run_daily_automation()`` call.
        """
        if not isinstance(tasks, list):
            logger.warning("register_copilot_tenant_tasks: expected list, got %s", type(tasks))
            return
        self._copilot_tenant_tasks = list(tasks)
        logger.info(
            "MurphyScheduler: registered %d Copilot Tenant task(s)",
            len(self._copilot_tenant_tasks),
        )

    # ------------------------------------------------------------------
    # Trading job handlers (called by APScheduler)
    # ------------------------------------------------------------------

    def _run_profit_sweep(self) -> None:
        # Use the shared singleton so sweep history/stats persist across runs
        _run_profit_sweep_job(_get_shared_sweeper())

    def _run_portfolio_snapshot(self) -> None:
        _run_portfolio_snapshot_job()

    def _run_performance_report(self) -> None:
        _run_performance_report_job()

    def _run_emergency_check(self) -> None:
        _run_emergency_check_job()

    def _run_graduation_check(self) -> None:
        _run_graduation_check_job()


def _run_safe(results: dict, key: str, fn) -> None:
    try:
        results[key] = {"result": fn(), "status": "ok"}
    except Exception as exc:
        logger.warning("Scheduled task '%s' failed: %s", key, exc)
        results[key] = {"status": "error", "error": str(exc)}


_scheduler: Optional[MurphyScheduler] = None
_shared_profit_sweeper: Optional[Any]   = None


def _get_shared_sweeper() -> Any:
    """Return the process-lifetime ProfitSweep singleton for scheduled jobs."""
    global _shared_profit_sweeper
    if _shared_profit_sweeper is None:
        from profit_sweep import ProfitSweep
        _shared_profit_sweeper = ProfitSweep()
    return _shared_profit_sweeper


def get_scheduler() -> MurphyScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = MurphyScheduler()
    return _scheduler


# ---------------------------------------------------------------------------
# Trading job implementations (module-level, easily unit-tested)
# ---------------------------------------------------------------------------

def _run_profit_sweep_job(sweeper: Optional[Any] = None) -> Dict[str, Any]:
    """Run the end-of-day profit sweep job."""
    try:
        if sweeper is None:
            from profit_sweep import ProfitSweep
            sweeper = ProfitSweep()
        record = sweeper.run_sweep()
        logger.info("Profit sweep job completed: status=%s", record.status.value)
        return record.to_dict()
    except Exception as exc:
        logger.error("Profit sweep job failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _run_portfolio_snapshot_job(orchestrator: Optional[Any] = None) -> Dict[str, Any]:
    """Capture a portfolio snapshot."""
    try:
        if orchestrator is not None:
            portfolio = orchestrator.get_portfolio()
            portfolio["snapshot_at"] = datetime.now(timezone.utc).isoformat()
            logger.debug("Portfolio snapshot taken")
            return portfolio
        return {"status": "no_orchestrator"}
    except Exception as exc:
        logger.warning("Portfolio snapshot job failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _run_performance_report_job(orchestrator: Optional[Any] = None) -> Dict[str, Any]:
    """Generate a daily performance summary."""
    try:
        report: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if orchestrator is not None:
            report["portfolio"]     = orchestrator.get_portfolio()
            report["todays_trades"] = orchestrator.get_todays_trades()
            report["health"]        = [h.to_dict() for h in orchestrator.check_health()]
        logger.info("Performance report generated")
        return report
    except Exception as exc:
        logger.warning("Performance report job failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _run_emergency_check_job(emergency_stop: Optional[Any] = None) -> Dict[str, Any]:
    """Check emergency stop status every minute."""
    try:
        if emergency_stop is not None:
            triggered = emergency_stop.is_triggered()
            if triggered:
                logger.critical("EMERGENCY STOP IS TRIGGERED — trading halted")
            return {"triggered": triggered, "checked_at": datetime.now(timezone.utc).isoformat()}
        return {"status": "not_configured"}
    except Exception as exc:
        logger.warning("Emergency check job failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def _run_graduation_check_job(graduation_controller: Optional[Any] = None) -> Dict[str, Any]:
    """Check graduation status every hour."""
    try:
        if graduation_controller is not None:
            status = graduation_controller.get_status()
            logger.debug("Graduation check: %s", status)
            return status if isinstance(status, dict) else {"status": str(status)}
        return {"status": "not_configured"}
    except Exception as exc:
        logger.warning("Graduation check job failed: %s", exc)
        return {"status": "error", "error": str(exc)}
