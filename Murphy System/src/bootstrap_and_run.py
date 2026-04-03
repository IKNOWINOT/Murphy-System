"""Murphy System — Full Bootstrap & Copilot Tenant Launch

Runs the complete four-stage Founder Bootstrap Orchestrator and then
starts the Copilot Tenant in Observer mode, hooking it into the Murphy
Scheduler for continuous operation.

Usage::

    python src/bootstrap_and_run.py

    # Run a specific bootstrap stage only:
    python src/bootstrap_and_run.py --stage 0
    python src/bootstrap_and_run.py --stage 1
    python src/bootstrap_and_run.py --stage 2
    python src/bootstrap_and_run.py --stage 3

    # Start the Copilot Tenant without re-running bootstrap:
    python src/bootstrap_and_run.py --copilot-only

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bootstrap_and_run")


# ---------------------------------------------------------------------------
# Stage mapping
# ---------------------------------------------------------------------------

_STAGE_MAP = {
    0: "stage_0_core_runtime",
    1: "stage_1_self_operation",
    2: "stage_2_integration_growth",
    3: "stage_3_hitl_graduation",
}


def _run_bootstrap(stage: int | None = None) -> bool:
    """Run the bootstrap orchestrator for the given stage (or all stages)."""
    from founder_bootstrap_orchestrator import (
        BootstrapStage,
        FounderBootstrapOrchestrator,
    )

    orchestrator = FounderBootstrapOrchestrator()

    if stage is None:
        logger.info("Running full bootstrap (all stages)…")
        result = orchestrator.run_full_bootstrap()
    else:
        stage_value = _STAGE_MAP.get(stage)
        if stage_value is None:
            logger.error("Unknown stage: %d (valid: 0–3)", stage)
            return False
        target_stage = BootstrapStage(stage_value)
        logger.info("Running bootstrap stage %d (%s)…", stage, stage_value)
        result = orchestrator.run_stage(target_stage)

    status = result.get("status", "unknown")
    logger.info("Bootstrap result: %s", status)
    if status not in ("completed", "partial"):
        logger.error("Bootstrap failed: %s", result)
        return False
    return True


def _start_copilot_tenant() -> None:
    """Instantiate and start the Copilot Tenant in Observer mode."""
    from copilot_tenant.tenant_agent import CopilotTenant, CopilotTenantMode

    tenant = CopilotTenant(founder_email="cpost@murphy.systems")
    logger.info("Starting Copilot Tenant in %s mode…", tenant.get_mode().value)
    tenant.start()

    # Hook into the scheduler
    try:
        from scheduler import get_scheduler
        sched = get_scheduler()
        sched.start()
        logger.info("MurphyScheduler started")
    except Exception as exc:
        logger.warning("Could not start MurphyScheduler: %s", exc)

    logger.info("Copilot Tenant is running.  Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
            status = tenant.get_status()
            logger.info(
                "Tenant status — mode=%s cycles=%d corpus=%d",
                status["mode"],
                status["cycles_run"],
                status["corpus_size"],
            )
    except KeyboardInterrupt:
        logger.info("Shutting down…")
        tenant.stop()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Murphy System — Full Bootstrap & Copilot Tenant Launch",
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[0, 1, 2, 3],
        help="Run a specific bootstrap stage (0–3) instead of all stages.",
    )
    parser.add_argument(
        "--copilot-only",
        action="store_true",
        help="Start the Copilot Tenant without re-running the bootstrap.",
    )
    args = parser.parse_args(argv)

    if not args.copilot_only:
        ok = _run_bootstrap(stage=args.stage)
        if not ok:
            return 1
        if args.stage is not None:
            # Single stage requested — don't start the tenant automatically
            return 0

    _start_copilot_tenant()
    return 0


if __name__ == "__main__":
    sys.exit(main())
