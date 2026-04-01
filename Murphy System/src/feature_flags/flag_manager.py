"""
Feature Flag Manager — runtime evaluation with per-tenant control.

Design Label: FF-003

Provides:
  • Flag registration and lifecycle management
  • Per-tenant evaluation with overrides
  • Percentage-based rollout (deterministic hashing)
  • MRR-gated features
  • A/B testing support via flag variants
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from src.feature_flags.models import (
    FeatureFlag,
    FlagEvaluation,
    FlagStatus,
    FlagType,
    RolloutConfig,
    TenantOverride,
)

logger = logging.getLogger(__name__)

_MAX_FLAGS = 1000
_MAX_EVALUATION_LOG = 500


class FeatureFlagManager:
    """Thread-safe feature flag manager.

    Supports boolean flags, percentage rollout, MRR-gated features,
    and per-tenant overrides.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags: Dict[str, FeatureFlag] = {}
        self._evaluation_log: Deque[FlagEvaluation] = deque(
            maxlen=_MAX_EVALUATION_LOG,
        )
        self._tenant_mrr: Dict[str, float] = {}  # tenant_id → current MRR

    # ------------------------------------------------------------------
    # Flag management
    # ------------------------------------------------------------------

    def create_flag(self, flag: FeatureFlag) -> None:
        """Create or update a feature flag."""
        with self._lock:
            if len(self._flags) >= _MAX_FLAGS and flag.flag_id not in self._flags:
                raise RuntimeError(f"Maximum flags ({_MAX_FLAGS}) reached")
            self._flags[flag.flag_id] = flag
            logger.info("Feature flag created: %s (%s) [%s]",
                        flag.flag_id, flag.name, flag.flag_type.value)

    def delete_flag(self, flag_id: str) -> FeatureFlag:
        """Remove a feature flag.  Raises KeyError if not found."""
        with self._lock:
            flag = self._flags.pop(flag_id)
            logger.info("Feature flag deleted: %s", flag_id)
            return flag

    def get_flag(self, flag_id: str) -> FeatureFlag:
        """Get a flag by ID.  Raises KeyError if not found."""
        with self._lock:
            return self._flags[flag_id]

    def list_flags(
        self,
        *,
        status: Optional[FlagStatus] = None,
        tag: Optional[str] = None,
    ) -> List[FeatureFlag]:
        """List all flags, optionally filtered."""
        with self._lock:
            results: List[FeatureFlag] = []
            for flag in self._flags.values():
                if status and flag.status != status:
                    continue
                if tag and tag not in flag.tags:
                    continue
                results.append(flag)
            return results

    def activate_flag(self, flag_id: str) -> None:
        """Set a flag to ACTIVE status."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag:
                flag.status = FlagStatus.ACTIVE
                flag.updated_at = datetime.now(timezone.utc)

    def pause_flag(self, flag_id: str) -> None:
        """Set a flag to PAUSED status."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag:
                flag.status = FlagStatus.PAUSED
                flag.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def is_enabled(
        self,
        flag_id: str,
        tenant_id: str,
        *,
        default: bool = False,
    ) -> bool:
        """Evaluate whether a feature flag is enabled for a tenant.

        This is the primary API for checking feature flags.
        """
        evaluation = self.evaluate(flag_id, tenant_id)
        if evaluation is None:
            return default
        return evaluation.enabled

    def evaluate(
        self,
        flag_id: str,
        tenant_id: str,
    ) -> Optional[FlagEvaluation]:
        """Full evaluation of a flag for a tenant.  Returns None if flag not found."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if not flag:
                return None

            # Inactive flags are always off
            if flag.status != FlagStatus.ACTIVE:
                result = FlagEvaluation(
                    flag_id=flag_id,
                    tenant_id=tenant_id,
                    enabled=False,
                    reason=f"flag_status_{flag.status.value}",
                )
                self._evaluation_log.append(result)
                return result

            # Check per-tenant override first
            override = flag.tenant_overrides.get(tenant_id)
            if override:
                result = FlagEvaluation(
                    flag_id=flag_id,
                    tenant_id=tenant_id,
                    enabled=override.enabled,
                    reason=f"tenant_override: {override.reason}",
                )
                self._evaluation_log.append(result)
                return result

            # Check blocked list
            if tenant_id in flag.rollout.blocked_tenants:
                result = FlagEvaluation(
                    flag_id=flag_id,
                    tenant_id=tenant_id,
                    enabled=False,
                    reason="tenant_blocked",
                )
                self._evaluation_log.append(result)
                return result

            # Evaluate by flag type
            enabled, reason = self._evaluate_by_type(flag, tenant_id)

            result = FlagEvaluation(
                flag_id=flag_id,
                tenant_id=tenant_id,
                enabled=enabled,
                reason=reason,
            )
            self._evaluation_log.append(result)
            return result

    def _evaluate_by_type(
        self,
        flag: FeatureFlag,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """Evaluate flag based on its type.  Called while holding lock."""
        if flag.flag_type == FlagType.BOOLEAN:
            return flag.default_enabled, "boolean_default"

        if flag.flag_type == FlagType.TENANT_LIST:
            if tenant_id in flag.rollout.allowed_tenants:
                return True, "tenant_in_allowlist"
            return False, "tenant_not_in_allowlist"

        if flag.flag_type == FlagType.PERCENTAGE:
            bucket = self._hash_to_percentage(flag.flag_id, tenant_id)
            enabled = bucket < flag.rollout.percentage
            return enabled, f"percentage_rollout_{bucket:.1f}%_vs_{flag.rollout.percentage}%"

        if flag.flag_type == FlagType.MRR_GATED:
            mrr = self._tenant_mrr.get(tenant_id, 0.0)
            enabled = mrr >= flag.rollout.mrr_threshold_usd
            return enabled, f"mrr_gate_{mrr:.2f}_vs_{flag.rollout.mrr_threshold_usd:.2f}"

        return flag.default_enabled, "unknown_type_fallback"

    # ------------------------------------------------------------------
    # Per-tenant overrides
    # ------------------------------------------------------------------

    def set_tenant_override(
        self,
        flag_id: str,
        tenant_id: str,
        enabled: bool,
        reason: str = "",
    ) -> None:
        """Set a per-tenant override for a flag."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if not flag:
                raise KeyError(f"Flag {flag_id} not found")
            flag.tenant_overrides[tenant_id] = TenantOverride(
                tenant_id=tenant_id,
                enabled=enabled,
                reason=reason,
            )
            flag.updated_at = datetime.now(timezone.utc)

    def remove_tenant_override(
        self,
        flag_id: str,
        tenant_id: str,
    ) -> None:
        """Remove a per-tenant override."""
        with self._lock:
            flag = self._flags.get(flag_id)
            if flag and tenant_id in flag.tenant_overrides:
                del flag.tenant_overrides[tenant_id]

    # ------------------------------------------------------------------
    # MRR tracking
    # ------------------------------------------------------------------

    def update_tenant_mrr(self, tenant_id: str, mrr_usd: float) -> None:
        """Update the MRR value for a tenant (for MRR-gated flags)."""
        with self._lock:
            self._tenant_mrr[tenant_id] = mrr_usd

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Number of registered flags."""
        with self._lock:
            return len(self._flags)

    def get_evaluation_log(self) -> List[FlagEvaluation]:
        """Return recent evaluation records."""
        return list(self._evaluation_log)

    def get_status_summary(self) -> Dict[str, Any]:
        """Summary of the flag system state."""
        with self._lock:
            status_counts: Dict[str, int] = {}
            type_counts: Dict[str, int] = {}
            for flag in self._flags.values():
                s = flag.status.value
                t = flag.flag_type.value
                status_counts[s] = status_counts.get(s, 0) + 1
                type_counts[t] = type_counts.get(t, 0) + 1
            return {
                "total_flags": len(self._flags),
                "status_distribution": status_counts,
                "type_distribution": type_counts,
                "tenants_with_mrr": len(self._tenant_mrr),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_to_percentage(flag_id: str, tenant_id: str) -> float:
        """Deterministic hash of (flag_id, tenant_id) to 0-100 range.

        Ensures consistent bucketing: same tenant always gets the same
        result for the same flag.
        """
        key = f"{flag_id}:{tenant_id}"
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return (int(h[:8], 16) % 10000) / 100.0
