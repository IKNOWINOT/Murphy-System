"""
Bot Governance Policy Mapper

Maps legacy bot-level quota, budget, and stability controls to Murphy runtime
execution profile policies and gate checks.

Assessment Section 15.3.4 identifies that legacy bot governance controls
(per-bot quotas, budget caps, circuit breakers) must be unified with Murphy's
execution profile and gate-check framework.  This module bridges that gap by
providing a registry of bot-level policies and translating them into Murphy-
compatible runtime profiles and pre-execution gate results.
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PolicyEnforcement(str, Enum):
    """How a mapped policy is enforced at the Murphy gate level."""
    ENFORCE = "enforce"
    WARN = "warn"
    AUDIT = "audit"


class BotStatus(str, Enum):
    """Operational status of a governed bot."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CIRCUIT_OPEN = "circuit_open"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BotQuotaPolicy:
    """Per-bot quota, budget, and stability policy."""
    bot_id: str
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_budget_per_task: float = 100.0
    max_total_budget: float = 10000.0
    stability_threshold: float = 0.8
    circuit_breaker_threshold: int = 5
    current_request_count: int = 0
    current_budget_used: float = 0.0
    is_active: bool = True
    # internal bookkeeping
    _consecutive_failures: int = field(default=0, repr=False)
    _created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), repr=False)

    def get_status(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "is_active": self.is_active,
            "current_request_count": self.current_request_count,
            "current_budget_used": self.current_budget_used,
            "budget_remaining": self.max_total_budget - self.current_budget_used,
            "quota_rpm": f"{self.current_request_count}/{self.max_requests_per_minute}",
            "consecutive_failures": self._consecutive_failures,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "stability_threshold": self.stability_threshold,
        }


@dataclass
class PolicyMapping:
    """Maps a single bot policy field to its Murphy execution profile counterpart."""
    mapping_id: str
    bot_policy_field: str
    murphy_policy_field: str
    transform_fn: Optional[Callable[[Any], Any]] = None
    description: str = ""

    def get_status(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "bot_policy_field": self.bot_policy_field,
            "murphy_policy_field": self.murphy_policy_field,
            "description": self.description,
        }


@dataclass
class GateCheckResult:
    """Result of a pre-execution gate check for a bot."""
    gate_name: str
    allowed: bool
    reason: str
    budget_remaining: float = 0.0
    quota_remaining: int = 0

    def get_status(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "allowed": self.allowed,
            "reason": self.reason,
            "budget_remaining": self.budget_remaining,
            "quota_remaining": self.quota_remaining,
        }


# ---------------------------------------------------------------------------
# Default transform helpers
# ---------------------------------------------------------------------------

def _stability_to_safety_level(value: float) -> str:
    """Map a 0-1 stability threshold to a Murphy safety level string."""
    if value >= 0.9:
        return "critical"
    if value >= 0.7:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _circuit_breaker_to_retry_policy(value: int) -> Dict[str, Any]:
    """Map circuit breaker threshold to Murphy retry policy."""
    return {
        "max_retries": max(1, value - 1),
        "circuit_breaker_after": value,
        "backoff_strategy": "exponential",
    }


# ---------------------------------------------------------------------------
# Default policy field mappings
# ---------------------------------------------------------------------------

_DEFAULT_MAPPINGS: List[Dict[str, Any]] = [
    {
        "bot_policy_field": "max_budget_per_task",
        "murphy_policy_field": "budget_constraints.per_task_limit",
        "transform_fn": None,
        "description": "Per-task budget cap mapped to Murphy budget constraint.",
    },
    {
        "bot_policy_field": "max_total_budget",
        "murphy_policy_field": "budget_constraints.total_limit",
        "transform_fn": None,
        "description": "Total budget cap mapped to Murphy budget constraint.",
    },
    {
        "bot_policy_field": "max_requests_per_minute",
        "murphy_policy_field": "rate_limits.requests_per_minute",
        "transform_fn": None,
        "description": "RPM quota mapped to Murphy rate limit.",
    },
    {
        "bot_policy_field": "max_requests_per_hour",
        "murphy_policy_field": "rate_limits.requests_per_hour",
        "transform_fn": None,
        "description": "RPH quota mapped to Murphy rate limit.",
    },
    {
        "bot_policy_field": "stability_threshold",
        "murphy_policy_field": "safety_level",
        "transform_fn": _stability_to_safety_level,
        "description": "Stability threshold mapped to Murphy safety level.",
    },
    {
        "bot_policy_field": "circuit_breaker_threshold",
        "murphy_policy_field": "retry_policy",
        "transform_fn": _circuit_breaker_to_retry_policy,
        "description": "Circuit breaker threshold mapped to Murphy retry policy.",
    },
]


# ---------------------------------------------------------------------------
# Main mapper
# ---------------------------------------------------------------------------

class BotGovernancePolicyMapper:
    """
    Registry and mapper for legacy bot governance policies.

    Translates per-bot quota / budget / stability controls into Murphy
    runtime execution profiles and provides pre-execution gate checks.
    Thread-safe for concurrent access.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._policies: Dict[str, BotQuotaPolicy] = {}
        self._mappings: List[PolicyMapping] = []
        self._gate_history: List[Dict[str, Any]] = []
        self._load_default_mappings()

    # -- bootstrap ----------------------------------------------------------

    def _load_default_mappings(self) -> None:
        for entry in _DEFAULT_MAPPINGS:
            mapping = PolicyMapping(
                mapping_id=str(uuid.uuid4()),
                bot_policy_field=entry["bot_policy_field"],
                murphy_policy_field=entry["murphy_policy_field"],
                transform_fn=entry["transform_fn"],
                description=entry["description"],
            )
            capped_append(self._mappings, mapping)
        logger.info("Loaded %d default policy mappings", len(self._mappings))

    # -- policy registration ------------------------------------------------

    def register_bot_policy(
        self,
        bot_id: str,
        max_rpm: int = 60,
        max_rph: int = 1000,
        max_budget_task: float = 100.0,
        max_total_budget: float = 10000.0,
        stability_threshold: float = 0.8,
        circuit_breaker_threshold: int = 5,
    ) -> BotQuotaPolicy:
        """Register or update a bot's governance policy."""
        with self._lock:
            policy = BotQuotaPolicy(
                bot_id=bot_id,
                max_requests_per_minute=max_rpm,
                max_requests_per_hour=max_rph,
                max_budget_per_task=max_budget_task,
                max_total_budget=max_total_budget,
                stability_threshold=stability_threshold,
                circuit_breaker_threshold=circuit_breaker_threshold,
            )
            self._policies[bot_id] = policy
            logger.info("Registered governance policy for bot %s", bot_id)
            return policy

    # -- profile mapping ----------------------------------------------------

    def map_to_murphy_profile(self, bot_id: str) -> Dict[str, Any]:
        """Convert a bot's quota policy to a Murphy runtime execution profile."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")

            profile: Dict[str, Any] = {
                "bot_id": bot_id,
                "is_active": policy.is_active,
            }
            for mapping in self._mappings:
                raw_value = getattr(policy, mapping.bot_policy_field, None)
                if raw_value is None:
                    continue
                value = mapping.transform_fn(raw_value) if mapping.transform_fn else raw_value
                _set_nested(profile, mapping.murphy_policy_field, value)

            logger.debug("Mapped bot %s to Murphy profile", bot_id)
            return profile

    # -- gate checks --------------------------------------------------------

    def check_gate(self, bot_id: str, cost: float = 0.0) -> GateCheckResult:
        """
        Pre-execution gate check.

        Evaluates quota, budget, stability, and activation status.  Returns a
        GateCheckResult indicating whether execution should proceed.
        """
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                result = GateCheckResult(
                    gate_name="bot_governance",
                    allowed=False,
                    reason=f"No policy registered for bot '{bot_id}'",
                )
                self._record_gate(bot_id, result)
                return result

            # activation check
            if not policy.is_active:
                result = GateCheckResult(
                    gate_name="bot_activation",
                    allowed=False,
                    reason="Bot is deactivated",
                    budget_remaining=policy.max_total_budget - policy.current_budget_used,
                    quota_remaining=policy.max_requests_per_minute - policy.current_request_count,
                )
                self._record_gate(bot_id, result)
                return result

            # circuit breaker check
            if policy._consecutive_failures >= policy.circuit_breaker_threshold:
                result = GateCheckResult(
                    gate_name="circuit_breaker",
                    allowed=False,
                    reason=(
                        f"Circuit breaker open: {policy._consecutive_failures} "
                        f"consecutive failures (threshold {policy.circuit_breaker_threshold})"
                    ),
                    budget_remaining=policy.max_total_budget - policy.current_budget_used,
                    quota_remaining=policy.max_requests_per_minute - policy.current_request_count,
                )
                self._record_gate(bot_id, result)
                return result

            # quota check (RPM)
            if policy.current_request_count >= policy.max_requests_per_minute:
                result = GateCheckResult(
                    gate_name="quota_rpm",
                    allowed=False,
                    reason=(
                        f"RPM quota exhausted: {policy.current_request_count}"
                        f"/{policy.max_requests_per_minute}"
                    ),
                    budget_remaining=policy.max_total_budget - policy.current_budget_used,
                    quota_remaining=0,
                )
                self._record_gate(bot_id, result)
                return result

            # budget check
            if cost > 0.0:
                if policy.current_budget_used + cost > policy.max_total_budget:
                    result = GateCheckResult(
                        gate_name="budget_total",
                        allowed=False,
                        reason=(
                            f"Total budget exceeded: {policy.current_budget_used + cost:.2f}"
                            f" > {policy.max_total_budget:.2f}"
                        ),
                        budget_remaining=policy.max_total_budget - policy.current_budget_used,
                        quota_remaining=policy.max_requests_per_minute - policy.current_request_count,
                    )
                    self._record_gate(bot_id, result)
                    return result

                if cost > policy.max_budget_per_task:
                    result = GateCheckResult(
                        gate_name="budget_per_task",
                        allowed=False,
                        reason=(
                            f"Per-task budget exceeded: {cost:.2f}"
                            f" > {policy.max_budget_per_task:.2f}"
                        ),
                        budget_remaining=policy.max_total_budget - policy.current_budget_used,
                        quota_remaining=policy.max_requests_per_minute - policy.current_request_count,
                    )
                    self._record_gate(bot_id, result)
                    return result

            # all checks passed
            result = GateCheckResult(
                gate_name="bot_governance",
                allowed=True,
                reason="All governance checks passed",
                budget_remaining=policy.max_total_budget - policy.current_budget_used,
                quota_remaining=policy.max_requests_per_minute - policy.current_request_count,
            )
            self._record_gate(bot_id, result)
            return result

    def _record_gate(self, bot_id: str, result: GateCheckResult) -> None:
        capped_append(self._gate_history, {
            "bot_id": bot_id,
            "gate_name": result.gate_name,
            "allowed": result.allowed,
            "reason": result.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # -- usage recording ----------------------------------------------------

    def record_usage(self, bot_id: str, cost: float = 0.0) -> None:
        """Record a request and optional cost against a bot's quotas."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")
            policy.current_request_count += 1
            policy.current_budget_used += cost
            logger.debug(
                "Recorded usage for bot %s: requests=%d, budget=%.2f",
                bot_id, policy.current_request_count, policy.current_budget_used,
            )

    def record_failure(self, bot_id: str) -> None:
        """Record a consecutive failure for circuit breaker tracking."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")
            policy._consecutive_failures += 1
            logger.info(
                "Bot %s failure count: %d/%d",
                bot_id, policy._consecutive_failures, policy.circuit_breaker_threshold,
            )

    def record_success(self, bot_id: str) -> None:
        """Reset consecutive failure counter on success."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")
            policy._consecutive_failures = 0

    # -- quota management ---------------------------------------------------

    def reset_quotas(self, bot_id: Optional[str] = None) -> None:
        """Reset request counts.  If *bot_id* is ``None``, reset all bots."""
        with self._lock:
            targets = [bot_id] if bot_id else list(self._policies.keys())
            for bid in targets:
                policy = self._policies.get(bid)
                if policy is not None:
                    policy.current_request_count = 0
                    logger.info("Reset quota for bot %s", bid)

    # -- activation ---------------------------------------------------------

    def deactivate_bot(self, bot_id: str) -> None:
        """Deactivate a bot, preventing further gate approvals."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")
            policy.is_active = False
            logger.info("Deactivated bot %s", bot_id)

    def activate_bot(self, bot_id: str) -> None:
        """Activate a bot, allowing gate approvals to proceed."""
        with self._lock:
            policy = self._policies.get(bot_id)
            if policy is None:
                raise KeyError(f"No policy registered for bot '{bot_id}'")
            policy.is_active = True
            policy._consecutive_failures = 0
            logger.info("Activated bot %s", bot_id)

    # -- reporting ----------------------------------------------------------

    def get_budget_report(self, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """Return budget utilisation report for one or all bots."""
        with self._lock:
            targets = (
                {bot_id: self._policies[bot_id]}
                if bot_id and bot_id in self._policies
                else dict(self._policies)
            )
            bots: List[Dict[str, Any]] = []
            for bid, policy in targets.items():
                remaining = policy.max_total_budget - policy.current_budget_used
                utilisation = (
                    (policy.current_budget_used / policy.max_total_budget * 100.0)
                    if policy.max_total_budget > 0 else 0.0
                )
                bots.append({
                    "bot_id": bid,
                    "max_total_budget": policy.max_total_budget,
                    "max_budget_per_task": policy.max_budget_per_task,
                    "current_budget_used": policy.current_budget_used,
                    "budget_remaining": remaining,
                    "utilisation_pct": round(utilisation, 2),
                })
            return {
                "report": "budget",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "bots": bots,
            }

    def get_stability_report(self, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """Return stability and circuit breaker status for one or all bots."""
        with self._lock:
            targets = (
                {bot_id: self._policies[bot_id]}
                if bot_id and bot_id in self._policies
                else dict(self._policies)
            )
            bots: List[Dict[str, Any]] = []
            for bid, policy in targets.items():
                circuit_open = (
                    policy._consecutive_failures >= policy.circuit_breaker_threshold
                )
                status = BotStatus.CIRCUIT_OPEN if circuit_open else (
                    BotStatus.ACTIVE if policy.is_active else BotStatus.INACTIVE
                )
                bots.append({
                    "bot_id": bid,
                    "status": status.value,
                    "stability_threshold": policy.stability_threshold,
                    "circuit_breaker_threshold": policy.circuit_breaker_threshold,
                    "consecutive_failures": policy._consecutive_failures,
                    "circuit_open": circuit_open,
                    "is_active": policy.is_active,
                })
            return {
                "report": "stability",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "bots": bots,
            }

    # -- mapping introspection ----------------------------------------------

    def get_policy_mappings(self) -> List[Dict[str, Any]]:
        """List all registered policy field mappings."""
        with self._lock:
            return [m.get_status() for m in self._mappings]

    # -- status -------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total_bots = len(self._policies)
            active_bots = sum(1 for p in self._policies.values() if p.is_active)
            total_gate_checks = len(self._gate_history)
            total_mappings = len(self._mappings)
        return {
            "total_bots": total_bots,
            "active_bots": active_bots,
            "total_policy_mappings": total_mappings,
            "total_gate_checks": total_gate_checks,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_nested(target: Dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using a dot-separated key path."""
    keys = dotted_key.split(".")
    for key in keys[:-1]:
        target = target.setdefault(key, {})
    target[keys[-1]] = value
