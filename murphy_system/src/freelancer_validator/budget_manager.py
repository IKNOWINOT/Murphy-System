"""
Freelancer Validator — Budget Manager

Manages per-organization budgets for freelance HITL tasks.
Ensures spend stays within monthly and per-task limits before any
task is posted to a platform.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from .models import BudgetConfig, BudgetLedger

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Tracks and enforces organization-level budgets for HITL tasks.

    Each organization has a ``BudgetConfig`` (limits) and a rolling
    ``BudgetLedger`` (actual spend).  The manager gates every task
    through ``authorize_spend`` before it may be posted.
    """

    def __init__(self) -> None:
        self._configs: Dict[str, BudgetConfig] = {}
        self._ledgers: Dict[str, BudgetLedger] = {}

    # ── Configuration ────────────────────────────────────────────────

    def register_org(self, config: BudgetConfig) -> None:
        """Register or update an organization's budget configuration."""
        self._configs[config.org_id] = config
        # Ensure a ledger exists for the current period
        self._ensure_ledger(config.org_id)
        logger.info(
            "Budget registered: org=%s monthly_limit=$%.2f per_task=$%.2f",
            config.org_id,
            config.monthly_limit_cents / 100,
            config.per_task_limit_cents / 100,
        )

    def get_config(self, org_id: str) -> Optional[BudgetConfig]:
        """Return budget config for an organization, or None."""
        return self._configs.get(org_id)

    # ── Authorization ────────────────────────────────────────────────

    def authorize_spend(self, org_id: str, amount_cents: int) -> bool:
        """
        Return True if the organization can afford *amount_cents*.

        Checks both the per-task limit and remaining monthly budget.
        Does **not** record the spend — call ``record_spend`` after
        the task is confirmed posted.
        """
        config = self._configs.get(org_id)
        if config is None:
            logger.warning("Budget auth failed: no config for org=%s", org_id)
            return False

        ledger = self._get_ledger(org_id)
        if not ledger.can_spend(amount_cents, config):
            logger.warning(
                "Budget auth failed: org=%s amount=%d remaining=%d per_task_max=%d",
                org_id,
                amount_cents,
                ledger.remaining_cents(config),
                config.per_task_limit_cents,
            )
            return False

        return True

    # ── Recording ────────────────────────────────────────────────────

    def record_spend(self, org_id: str, task_id: str, amount_cents: int) -> None:
        """Record an authorized spend.  Call after a task is posted."""
        ledger = self._get_ledger(org_id)
        ledger.record_spend(task_id, amount_cents)
        config = self._configs.get(org_id)
        if config:
            self._check_alert_threshold(org_id, ledger, config)
        logger.info(
            "Spend recorded: org=%s task=%s amount=$%.2f total=$%.2f",
            org_id,
            task_id,
            amount_cents / 100,
            ledger.total_spent_cents / 100,
        )

    # ── Reporting ────────────────────────────────────────────────────

    def get_balance(self, org_id: str) -> Dict[str, int]:
        """Return remaining and total spent for the current period."""
        config = self._configs.get(org_id)
        ledger = self._get_ledger(org_id)
        if config is None:
            return {"remaining_cents": 0, "total_spent_cents": 0, "task_count": 0}
        return {
            "remaining_cents": ledger.remaining_cents(config),
            "total_spent_cents": ledger.total_spent_cents,
            "task_count": ledger.task_count,
        }

    # ── Internals ────────────────────────────────────────────────────

    def _ensure_ledger(self, org_id: str) -> BudgetLedger:
        current_period = datetime.now(timezone.utc).strftime("%Y-%m")
        ledger = self._ledgers.get(org_id)
        if ledger is None or ledger.period != current_period:
            ledger = BudgetLedger(org_id=org_id, period=current_period)
            self._ledgers[org_id] = ledger
        return ledger

    def _get_ledger(self, org_id: str) -> BudgetLedger:
        return self._ensure_ledger(org_id)

    def _check_alert_threshold(
        self, org_id: str, ledger: BudgetLedger, config: BudgetConfig
    ) -> None:
        if config.monthly_limit_cents == 0:
            return
        usage_pct = ledger.total_spent_cents / config.monthly_limit_cents
        if usage_pct >= config.alert_threshold_pct:
            logger.warning(
                "Budget alert: org=%s usage=%.0f%% of $%.2f",
                org_id,
                usage_pct * 100,
                config.monthly_limit_cents / 100,
            )
