"""Bot-specific and swarm-level resource quota enforcement."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class QuotaStatus(str, Enum):
    """Status of a bot's quota standing."""

    ACTIVE = "active"
    WARNING = "warning"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ViolationType(str, Enum):
    """Categories of quota violations."""

    BOT_MEMORY_EXCEEDED = "bot_memory_exceeded"
    BOT_CPU_EXCEEDED = "bot_cpu_exceeded"
    BOT_API_CALLS_EXCEEDED = "bot_api_calls_exceeded"
    BOT_BUDGET_EXCEEDED = "bot_budget_exceeded"
    SWARM_AGGREGATE_EXCEEDED = "swarm_aggregate_exceeded"
    SWARM_BOT_COUNT_EXCEEDED = "swarm_bot_count_exceeded"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BotQuota:
    """Per-bot resource limits."""

    bot_id: str
    tenant_id: str
    max_memory_mb: float = 512.0
    max_cpu_seconds: float = 300.0
    max_api_calls: int = 1000
    max_budget_usd: float = 50.0
    status: QuotaStatus = QuotaStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "tenant_id": self.tenant_id,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_seconds": self.max_cpu_seconds,
            "max_api_calls": self.max_api_calls,
            "max_budget_usd": self.max_budget_usd,
            "status": self.status.value,
        }


@dataclass
class BotUsage:
    """Tracked resource consumption for a single bot."""

    bot_id: str
    memory_mb: float = 0.0
    cpu_seconds: float = 0.0
    api_calls: int = 0
    budget_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "memory_mb": self.memory_mb,
            "cpu_seconds": self.cpu_seconds,
            "api_calls": self.api_calls,
            "budget_usd": self.budget_usd,
        }


@dataclass
class SwarmQuota:
    """Aggregate resource limits for all bots in a swarm."""

    swarm_id: str
    tenant_id: str
    max_total_memory_mb: float = 4096.0
    max_total_cpu_seconds: float = 3600.0
    max_total_api_calls: int = 10000
    max_total_budget_usd: float = 500.0
    max_bot_count: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swarm_id": self.swarm_id,
            "tenant_id": self.tenant_id,
            "max_total_memory_mb": self.max_total_memory_mb,
            "max_total_cpu_seconds": self.max_total_cpu_seconds,
            "max_total_api_calls": self.max_total_api_calls,
            "max_total_budget_usd": self.max_total_budget_usd,
            "max_bot_count": self.max_bot_count,
        }


@dataclass
class QuotaViolation:
    """Record of a single quota violation event."""

    violation_id: str
    bot_id: str
    swarm_id: Optional[str]
    violation_type: ViolationType
    current_value: float
    limit_value: float
    timestamp: datetime
    auto_action: str  # "suspended" or "warned"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "bot_id": self.bot_id,
            "swarm_id": self.swarm_id,
            "violation_type": self.violation_type.value,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "timestamp": self.timestamp.isoformat(),
            "auto_action": self.auto_action,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

WARNING_THRESHOLD = 0.8  # 80 % of limit triggers a warning


class BotResourceQuotaManager:
    """Manages per-bot and per-swarm resource quotas."""

    def __init__(self, max_violations: int = 5000) -> None:
        self._lock = threading.Lock()
        self._bot_quotas: Dict[str, BotQuota] = {}
        self._bot_usage: Dict[str, BotUsage] = {}
        self._swarm_quotas: Dict[str, SwarmQuota] = {}
        # swarm_id -> set of bot_ids
        self._swarm_bots: Dict[str, Set[str]] = {}
        # bot_id -> swarm_id
        self._bot_swarm: Dict[str, str] = {}
        self._violations: List[QuotaViolation] = []
        self._max_violations = max_violations
        logger.info("BotResourceQuotaManager initialised (max_violations=%d)", max_violations)

    # -- registration -------------------------------------------------------

    def register_bot(self, quota: BotQuota) -> None:
        with self._lock:
            self._bot_quotas[quota.bot_id] = quota
            self._bot_usage.setdefault(quota.bot_id, BotUsage(bot_id=quota.bot_id))
            logger.info("Registered bot quota for %s (tenant=%s)", quota.bot_id, quota.tenant_id)

    def register_swarm(self, quota: SwarmQuota) -> None:
        with self._lock:
            self._swarm_quotas[quota.swarm_id] = quota
            self._swarm_bots.setdefault(quota.swarm_id, set())
            logger.info("Registered swarm quota for %s (tenant=%s)", quota.swarm_id, quota.tenant_id)

    def assign_bot_to_swarm(self, bot_id: str, swarm_id: str) -> None:
        with self._lock:
            if swarm_id not in self._swarm_quotas:
                logger.error("Swarm %s not registered", swarm_id)
                return
            if bot_id not in self._bot_quotas:
                logger.error("Bot %s not registered", bot_id)
                return
            self._swarm_bots[swarm_id].add(bot_id)
            self._bot_swarm[bot_id] = swarm_id
            logger.info("Assigned bot %s to swarm %s", bot_id, swarm_id)
            # Check bot-count limit immediately
            sq = self._swarm_quotas[swarm_id]
            count = len(self._swarm_bots[swarm_id])
            if count > sq.max_bot_count:
                self._add_violation(bot_id, swarm_id, ViolationType.SWARM_BOT_COUNT_EXCEEDED,
                                    float(count), float(sq.max_bot_count), "suspended")
                self._bot_quotas[bot_id].status = QuotaStatus.SUSPENDED

    # -- usage recording & checking -----------------------------------------

    def record_usage(
        self,
        bot_id: str,
        memory_mb: float = 0.0,
        cpu_seconds: float = 0.0,
        api_calls: int = 0,
        budget_usd: float = 0.0,
    ) -> None:
        """Record incremental resource usage for a bot and check quotas."""
        with self._lock:
            usage = self._bot_usage.get(bot_id)
            if usage is None:
                logger.warning("Usage recorded for unknown bot %s", bot_id)
                return
            quota = self._bot_quotas.get(bot_id)
            if quota and quota.status == QuotaStatus.SUSPENDED:
                logger.warning("Usage rejected — bot %s is suspended", bot_id)
                return
            usage.memory_mb += memory_mb
            usage.cpu_seconds += cpu_seconds
            usage.api_calls += api_calls
            usage.budget_usd += budget_usd
        # Check quotas outside inner lock section but still thread-safe
        self.check_bot_quota(bot_id)
        swarm_id = self._bot_swarm.get(bot_id)
        if swarm_id:
            self.check_swarm_quota(swarm_id)

    def check_bot_quota(self, bot_id: str) -> List[QuotaViolation]:
        violations: List[QuotaViolation] = []
        with self._lock:
            quota = self._bot_quotas.get(bot_id)
            usage = self._bot_usage.get(bot_id)
            if quota is None or usage is None:
                return violations
            swarm_id = self._bot_swarm.get(bot_id)
            checks = [
                (usage.memory_mb, quota.max_memory_mb, ViolationType.BOT_MEMORY_EXCEEDED),
                (usage.cpu_seconds, quota.max_cpu_seconds, ViolationType.BOT_CPU_EXCEEDED),
                (float(usage.api_calls), float(quota.max_api_calls), ViolationType.BOT_API_CALLS_EXCEEDED),
                (usage.budget_usd, quota.max_budget_usd, ViolationType.BOT_BUDGET_EXCEEDED),
            ]
            for current, limit, vtype in checks:
                if current > limit:
                    v = self._add_violation(bot_id, swarm_id, vtype, current, limit, "suspended")
                    quota.status = QuotaStatus.SUSPENDED
                    violations.append(v)
                elif current > limit * WARNING_THRESHOLD and quota.status == QuotaStatus.ACTIVE:
                    v = self._add_violation(bot_id, swarm_id, vtype, current, limit, "warned")
                    quota.status = QuotaStatus.WARNING
                    violations.append(v)
        return violations

    def check_swarm_quota(self, swarm_id: str) -> List[QuotaViolation]:
        violations: List[QuotaViolation] = []
        with self._lock:
            sq = self._swarm_quotas.get(swarm_id)
            bots = self._swarm_bots.get(swarm_id)
            if sq is None or bots is None:
                return violations
            total_mem = total_cpu = total_budget = 0.0
            total_api = 0
            for bid in bots:
                u = self._bot_usage.get(bid)
                if u:
                    total_mem += u.memory_mb
                    total_cpu += u.cpu_seconds
                    total_api += u.api_calls
                    total_budget += u.budget_usd
            agg_checks = [
                (total_mem, sq.max_total_memory_mb),
                (total_cpu, sq.max_total_cpu_seconds),
                (float(total_api), float(sq.max_total_api_calls)),
                (total_budget, sq.max_total_budget_usd),
            ]
            for current, limit in agg_checks:
                if current > limit:
                    v = self._add_violation("swarm", swarm_id, ViolationType.SWARM_AGGREGATE_EXCEEDED,
                                            current, limit, "suspended")
                    violations.append(v)
                    # Suspend every bot in the swarm
                    for bid in bots:
                        bq = self._bot_quotas.get(bid)
                        if bq and bq.status != QuotaStatus.SUSPENDED:
                            bq.status = QuotaStatus.SUSPENDED
                            logger.warning("Bot %s suspended due to swarm %s aggregate breach", bid, swarm_id)
        return violations

    # -- administrative actions ---------------------------------------------

    def suspend_bot(self, bot_id: str, reason: str) -> bool:
        with self._lock:
            quota = self._bot_quotas.get(bot_id)
            if quota is None:
                logger.error("Cannot suspend unknown bot %s", bot_id)
                return False
            quota.status = QuotaStatus.SUSPENDED
            logger.info("Bot %s suspended: %s", bot_id, reason)
            return True

    def resume_bot(self, bot_id: str) -> bool:
        with self._lock:
            quota = self._bot_quotas.get(bot_id)
            if quota is None:
                logger.error("Cannot resume unknown bot %s", bot_id)
                return False
            if quota.status not in (QuotaStatus.SUSPENDED, QuotaStatus.WARNING):
                logger.warning("Bot %s is not suspended or warned (status=%s)", bot_id, quota.status.value)
                return False
            quota.status = QuotaStatus.ACTIVE
            logger.info("Bot %s resumed", bot_id)
            return True

    # -- queries ------------------------------------------------------------

    def get_bot_usage(self, bot_id: str) -> Optional[BotUsage]:
        with self._lock:
            return self._bot_usage.get(bot_id)

    def get_violations(
        self,
        bot_id: Optional[str] = None,
        swarm_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[QuotaViolation]:
        with self._lock:
            results = self._violations
            if bot_id is not None:
                results = [v for v in results if v.bot_id == bot_id]
            if swarm_id is not None:
                results = [v for v in results if v.swarm_id == swarm_id]
            return results[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            status_counts: Dict[str, int] = {}
            for bq in self._bot_quotas.values():
                status_counts[bq.status.value] = status_counts.get(bq.status.value, 0) + 1
            return {
                "total_bots": len(self._bot_quotas),
                "total_swarms": len(self._swarm_quotas),
                "total_violations": len(self._violations),
                "bot_status_counts": status_counts,
            }

    # -- internal helpers ---------------------------------------------------

    def _add_violation(
        self,
        bot_id: str,
        swarm_id: Optional[str],
        vtype: ViolationType,
        current: float,
        limit: float,
        action: str,
    ) -> QuotaViolation:
        """Create, store, and return a new QuotaViolation (caller must hold lock)."""
        violation = QuotaViolation(
            violation_id=uuid.uuid4().hex,
            bot_id=bot_id,
            swarm_id=swarm_id,
            violation_type=vtype,
            current_value=current,
            limit_value=limit,
            timestamp=datetime.now(timezone.utc),
            auto_action=action,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_violations:
            self._violations = self._violations[-self._max_violations:]
        logger.warning(
            "Quota violation: type=%s bot=%s swarm=%s current=%.2f limit=%.2f action=%s",
            vtype.value, bot_id, swarm_id, current, limit, action,
        )
        return violation
