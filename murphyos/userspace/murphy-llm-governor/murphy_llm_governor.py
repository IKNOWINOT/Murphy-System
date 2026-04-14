# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_llm_governor.py — MurphyOS LLM Resource Governor
========================================================
OS-level governance for LLM workloads: token-budget tracking, rate limiting,
GPU memory governance, provider health monitoring, and cost circuit breakers.

Designed for integration with Murphy System's LLM subsystem
(``llm_provider.py``, ``llm_controller.py``, ``llm_output_validator.py``,
``safe_llm_wrapper.py``, ``groq_key_rotator.py``).
"""
from __future__ import annotations

import collections
import dataclasses
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG = logging.getLogger("murphy.llm_governor")

# ---------------------------------------------------------------------------
# Error Codes
# ---------------------------------------------------------------------------
MURPHY_LLM_GOV_ERR_001 = "MURPHY-LLM-GOV-ERR-001"  # config load failure
MURPHY_LLM_GOV_ERR_002 = "MURPHY-LLM-GOV-ERR-002"  # state persistence write failed
MURPHY_LLM_GOV_ERR_003 = "MURPHY-LLM-GOV-ERR-003"  # state persistence read failed
MURPHY_LLM_GOV_ERR_004 = "MURPHY-LLM-GOV-ERR-004"  # budget exceeded (daily)
MURPHY_LLM_GOV_ERR_005 = "MURPHY-LLM-GOV-ERR-005"  # budget exceeded (hourly)
MURPHY_LLM_GOV_ERR_006 = "MURPHY-LLM-GOV-ERR-006"  # rate limit exceeded (RPM)
MURPHY_LLM_GOV_ERR_007 = "MURPHY-LLM-GOV-ERR-007"  # rate limit exceeded (TPM)
MURPHY_LLM_GOV_ERR_008 = "MURPHY-LLM-GOV-ERR-008"  # GPU OOM prevention triggered
MURPHY_LLM_GOV_ERR_009 = "MURPHY-LLM-GOV-ERR-009"  # GPU temperature limit exceeded
MURPHY_LLM_GOV_ERR_010 = "MURPHY-LLM-GOV-ERR-010"  # nvidia-smi execution failed
MURPHY_LLM_GOV_ERR_011 = "MURPHY-LLM-GOV-ERR-011"  # provider health degraded
MURPHY_LLM_GOV_ERR_012 = "MURPHY-LLM-GOV-ERR-012"  # circuit breaker open

# ---------------------------------------------------------------------------
# Default Configuration
# ---------------------------------------------------------------------------
_DEFAULT_STATE_FILE = Path("/var/lib/murphy/llm-governor.json")

_DEFAULT_BUDGETS: Dict[str, Any] = {
    "daily_total_usd": 50.0,
    "hourly_total_usd": 10.0,
    "per_provider": {},
}

_DEFAULT_GPU: Dict[str, Any] = {
    "oom_threshold_percent": 90,
    "temperature_limit_celsius": 85,
}

_DEFAULT_HEALTH: Dict[str, Any] = {
    "error_rate_threshold": 0.05,
    "latency_p99_threshold_ms": 30000,
    "window_seconds": 300,
}


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class UsageRecord:
    """Single token-usage event."""

    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: float = dataclasses.field(default_factory=time.time)


@dataclasses.dataclass
class LatencyRecord:
    """Single provider-latency sample."""

    latency_ms: float
    success: bool
    timestamp: float = dataclasses.field(default_factory=time.time)


@dataclasses.dataclass
class GPUStats:
    """Snapshot of GPU state."""

    memory_used_mb: float
    memory_total_mb: float
    utilization_percent: float
    temperature_celsius: float


# ---------------------------------------------------------------------------
# Token-bucket rate limiter
# ---------------------------------------------------------------------------
class _TokenBucket:
    """Thread-safe token-bucket for rate limiting."""

    def __init__(self, capacity: float, refill_rate: float) -> None:
        self._capacity = capacity
        self._tokens = capacity
        self._refill_rate = refill_rate  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, count: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= count:
                self._tokens -= count
                return True
            return False

    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def reset_time(self) -> float:
        """Seconds until the bucket is fully refilled."""
        with self._lock:
            self._refill()
            deficit = self._capacity - self._tokens
            if deficit <= 0 or self._refill_rate <= 0:
                return 0.0
            return deficit / self._refill_rate

    # -- internal ----------------------------------------------------------
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


# ---------------------------------------------------------------------------
# LLMGovernor
# ---------------------------------------------------------------------------
class LLMGovernor:
    """OS-level governance for LLM workloads.

    All public methods are thread-safe.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._lock = threading.Lock()

        cfg = config or {}
        budgets = cfg.get("budgets", _DEFAULT_BUDGETS)
        gpu_cfg = cfg.get("gpu", _DEFAULT_GPU)
        health_cfg = cfg.get("health", _DEFAULT_HEALTH)

        # State file
        self._state_file = Path(
            cfg.get("state_file", str(_DEFAULT_STATE_FILE))
        )

        # Budget config
        self._daily_total_cap: float = float(budgets.get("daily_total_usd", 50.0))
        self._hourly_total_cap: float = float(budgets.get("hourly_total_usd", 10.0))
        self._provider_budgets: Dict[str, Dict[str, Any]] = budgets.get(
            "per_provider", {}
        )

        # GPU config
        self._oom_threshold: float = float(gpu_cfg.get("oom_threshold_percent", 90))
        self._temp_limit: float = float(
            gpu_cfg.get("temperature_limit_celsius", 85)
        )

        # Health config
        self._error_rate_threshold: float = float(
            health_cfg.get("error_rate_threshold", 0.05)
        )
        self._latency_p99_threshold: float = float(
            health_cfg.get("latency_p99_threshold_ms", 30000)
        )
        self._health_window: float = float(health_cfg.get("window_seconds", 300))

        # ---- mutable state (guarded by self._lock) -----------------------
        self._usage_records: List[UsageRecord] = []
        self._latency_records: Dict[str, Deque[LatencyRecord]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=10000))
        )

        # Rate limiters — keyed by provider
        self._rpm_buckets: Dict[str, _TokenBucket] = {}
        self._tpm_buckets: Dict[str, _TokenBucket] = {}
        self._init_rate_limiters()

        # Circuit breaker state
        self._circuit_open: Dict[str, bool] = {}
        self._circuit_reset_day: int = datetime.now(timezone.utc).day

        # Load persisted state (best-effort)
        self._load_state()

    # ------------------------------------------------------------------
    # Token Budget Tracking
    # ------------------------------------------------------------------
    def record_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        """Record a single LLM API call's token usage and cost."""
        record = UsageRecord(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )
        with self._lock:
            self._usage_records.append(record)
            self._maybe_trip_circuit(provider)
        self._persist_state()

    def get_usage(self, provider: str, period: str = "day") -> Dict[str, Any]:
        """Return token/cost stats for *provider* over *period* (``day`` | ``hour``).

        Returns dict with ``prompt_tokens``, ``completion_tokens``,
        ``total_tokens``, ``cost_usd``, ``request_count``.
        """
        cutoff = self._period_cutoff(period)
        with self._lock:
            recs = [
                r
                for r in self._usage_records
                if r.provider == provider and r.timestamp >= cutoff
            ]
        prompt = sum(r.prompt_tokens for r in recs)
        completion = sum(r.completion_tokens for r in recs)
        cost = sum(r.cost_usd for r in recs)
        return {
            "provider": provider,
            "period": period,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "cost_usd": round(cost, 6),
            "request_count": len(recs),
        }

    def check_budget(self, provider: str) -> bool:
        """Return ``True`` if *provider* is still within its daily budget."""
        daily = self.get_usage(provider, "day")
        cap = self._provider_daily_cap(provider)
        if cap is not None and daily["cost_usd"] >= cap:
            _LOG.warning(
                "%s Budget exceeded for provider=%s daily_cost=%.4f cap=%.4f",
                MURPHY_LLM_GOV_ERR_004,
                provider,
                daily["cost_usd"],
                cap,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Rate Limiting
    # ------------------------------------------------------------------
    def acquire(self, provider: str, estimated_tokens: int = 1) -> bool:
        """Try to acquire rate-limit tokens.  Returns ``True`` on success."""
        with self._lock:
            rpm = self._rpm_buckets.get(provider)
            tpm = self._tpm_buckets.get(provider)

        # If no limiters configured, allow
        if rpm is None and tpm is None:
            return True

        if rpm is not None and not rpm.acquire(1):
            _LOG.warning(
                "%s RPM limit hit for provider=%s",
                MURPHY_LLM_GOV_ERR_006,
                provider,
            )
            return False

        if tpm is not None and not tpm.acquire(float(estimated_tokens)):
            _LOG.warning(
                "%s TPM limit hit for provider=%s estimated_tokens=%d",
                MURPHY_LLM_GOV_ERR_007,
                provider,
                estimated_tokens,
            )
            return False

        return True

    def get_rate_status(self, provider: str) -> Dict[str, Any]:
        """Return current rate-limit status for *provider*."""
        with self._lock:
            rpm = self._rpm_buckets.get(provider)
            tpm = self._tpm_buckets.get(provider)
        return {
            "provider": provider,
            "rpm_available": rpm.available() if rpm else None,
            "rpm_reset_seconds": rpm.reset_time() if rpm else None,
            "tpm_available": tpm.available() if tpm else None,
            "tpm_reset_seconds": tpm.reset_time() if tpm else None,
        }

    # ------------------------------------------------------------------
    # GPU Memory Governance
    # ------------------------------------------------------------------
    def get_gpu_stats(self) -> Optional[GPUStats]:
        """Read GPU stats via ``nvidia-smi``.

        Returns ``None`` if no NVIDIA GPU is detected.
        """
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                _LOG.debug(
                    "%s nvidia-smi returned code %d: %s",
                    MURPHY_LLM_GOV_ERR_010,
                    result.returncode,
                    result.stderr.strip(),
                )
                return self._try_sysfs_gpu()

            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                return None
            return GPUStats(
                memory_used_mb=float(parts[0]),
                memory_total_mb=float(parts[1]),
                utilization_percent=float(parts[2]),
                temperature_celsius=float(parts[3]),
            )
        except FileNotFoundError:
            # nvidia-smi not installed — MURPHY-LLM-GOV-ERR-010
            _LOG.debug(
                "%s nvidia-smi not found, trying sysfs fallback",
                MURPHY_LLM_GOV_ERR_010,
            )
            return self._try_sysfs_gpu()
        except Exception as exc:
            # MURPHY-LLM-GOV-ERR-010
            _LOG.warning(
                "%s GPU stats unavailable: %s", MURPHY_LLM_GOV_ERR_010, exc
            )
            return None

    def check_gpu_available(self, memory_required_mb: float) -> bool:
        """Return ``True`` if the GPU can accept a new inference workload."""
        stats = self.get_gpu_stats()
        if stats is None:
            return True  # no GPU detected — allow CPU inference

        # OOM prevention
        if stats.memory_total_mb > 0:
            usage_pct = (stats.memory_used_mb / stats.memory_total_mb) * 100.0
            if usage_pct >= self._oom_threshold:
                _LOG.warning(
                    "%s GPU memory %.1f%% >= threshold %.1f%%",
                    MURPHY_LLM_GOV_ERR_008,
                    usage_pct,
                    self._oom_threshold,
                )
                return False

            free_mb = stats.memory_total_mb - stats.memory_used_mb
            if free_mb < memory_required_mb:
                _LOG.warning(
                    "%s GPU free memory %.0f MB < required %.0f MB",
                    MURPHY_LLM_GOV_ERR_008,
                    free_mb,
                    memory_required_mb,
                )
                return False

        # Temperature guard
        if stats.temperature_celsius >= self._temp_limit:
            _LOG.warning(
                "%s GPU temperature %.1f°C >= limit %.1f°C",
                MURPHY_LLM_GOV_ERR_009,
                stats.temperature_celsius,
                self._temp_limit,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Provider Health Tracking
    # ------------------------------------------------------------------
    def record_latency(
        self, provider: str, latency_ms: float, success: bool
    ) -> None:
        """Record a single request latency sample for *provider*."""
        rec = LatencyRecord(latency_ms=latency_ms, success=success)
        with self._lock:
            self._latency_records[provider].append(rec)

    def get_provider_health(self, provider: str) -> Dict[str, Any]:
        """Return latency and error-rate stats for *provider*."""
        cutoff = time.time() - self._health_window
        with self._lock:
            recs = [
                r
                for r in self._latency_records.get(provider, [])
                if r.timestamp >= cutoff
            ]
        if not recs:
            return {
                "provider": provider,
                "request_count": 0,
                "error_rate": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "healthy": True,
            }
        total = len(recs)
        errors = sum(1 for r in recs if not r.success)
        error_rate = errors / total

        latencies = sorted(r.latency_ms for r in recs)
        p50 = self._percentile(latencies, 50)
        p95 = self._percentile(latencies, 95)
        p99 = self._percentile(latencies, 99)

        healthy = (
            error_rate < self._error_rate_threshold
            and p99 < self._latency_p99_threshold
        )

        return {
            "provider": provider,
            "request_count": total,
            "error_rate": round(error_rate, 4),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "healthy": healthy,
        }

    def is_provider_healthy(self, provider: str) -> bool:
        """Return ``True`` if *provider* error rate is below threshold."""
        health = self.get_provider_health(provider)
        if not health["healthy"]:
            _LOG.warning(
                "%s Provider %s unhealthy: error_rate=%.2f%% p99=%.0fms",
                MURPHY_LLM_GOV_ERR_011,
                provider,
                health["error_rate"] * 100,
                health["latency_p99_ms"],
            )
        return health["healthy"]

    # ------------------------------------------------------------------
    # Cost Circuit Breaker
    # ------------------------------------------------------------------
    def is_circuit_open(self, provider: str) -> bool:
        """Return ``True`` if the cost circuit breaker is tripped."""
        self._maybe_reset_circuits()
        with self._lock:
            is_open = self._circuit_open.get(provider, False)
        if is_open:
            _LOG.warning(
                "%s Circuit breaker OPEN for provider=%s",
                MURPHY_LLM_GOV_ERR_012,
                provider,
            )
        return is_open

    # ------------------------------------------------------------------
    # State Persistence
    # ------------------------------------------------------------------
    def _persist_state(self) -> None:
        """Atomically write governor state to disk."""
        try:
            state_dir = self._state_file.parent
            state_dir.mkdir(parents=True, exist_ok=True)

            with self._lock:
                payload = {
                    "version": 1,
                    "persisted_at": datetime.now(timezone.utc).isoformat(),
                    "usage_records": [
                        dataclasses.asdict(r) for r in self._usage_records
                    ],
                    "circuit_open": dict(self._circuit_open),
                }

            # Atomic write: tempfile in same directory + rename
            fd, tmp_path = tempfile.mkstemp(
                dir=str(state_dir), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as fh:
                    json.dump(payload, fh, indent=2)
                os.replace(tmp_path, str(self._state_file))
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            # MURPHY-LLM-GOV-ERR-002
            _LOG.error(
                "%s Failed to persist state: %s", MURPHY_LLM_GOV_ERR_002, exc
            )

    def _load_state(self) -> None:
        """Load previously-persisted state (best-effort)."""
        if not self._state_file.exists():
            return
        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            with self._lock:
                for rec_dict in data.get("usage_records", []):
                    self._usage_records.append(
                        UsageRecord(
                            provider=rec_dict["provider"],
                            model=rec_dict["model"],
                            prompt_tokens=rec_dict["prompt_tokens"],
                            completion_tokens=rec_dict["completion_tokens"],
                            cost_usd=rec_dict["cost_usd"],
                            timestamp=rec_dict.get("timestamp", 0.0),
                        )
                    )
                for prov, is_open in data.get("circuit_open", {}).items():
                    self._circuit_open[prov] = is_open
            _LOG.info("Loaded persisted state from %s", self._state_file)
        except Exception as exc:
            # MURPHY-LLM-GOV-ERR-003
            _LOG.warning(
                "%s Failed to load state: %s", MURPHY_LLM_GOV_ERR_003, exc
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _init_rate_limiters(self) -> None:
        """Create token-bucket rate limiters from provider config."""
        for provider, cfg in self._provider_budgets.items():
            rpm = cfg.get("rpm")
            tpm = cfg.get("tpm")
            if rpm:
                self._rpm_buckets[provider] = _TokenBucket(
                    capacity=float(rpm),
                    refill_rate=float(rpm) / 60.0,
                )
            if tpm:
                self._tpm_buckets[provider] = _TokenBucket(
                    capacity=float(tpm),
                    refill_rate=float(tpm) / 60.0,
                )

    def _provider_daily_cap(self, provider: str) -> Optional[float]:
        prov_cfg = self._provider_budgets.get(provider, {})
        cap = prov_cfg.get("daily_usd")
        return float(cap) if cap is not None else None

    def _maybe_trip_circuit(self, provider: str) -> None:
        """Trip circuit breaker if daily or hourly caps are exceeded.

        Must be called while holding ``self._lock``.
        """
        now = time.time()
        day_cutoff = self._period_cutoff("day")
        hour_cutoff = self._period_cutoff("hour")

        daily_cost = sum(
            r.cost_usd
            for r in self._usage_records
            if r.timestamp >= day_cutoff
        )
        hourly_cost = sum(
            r.cost_usd
            for r in self._usage_records
            if r.timestamp >= hour_cutoff
        )

        # Per-provider daily cap
        prov_cap = self._provider_daily_cap(provider)
        prov_daily = sum(
            r.cost_usd
            for r in self._usage_records
            if r.provider == provider and r.timestamp >= day_cutoff
        )
        if prov_cap is not None and prov_daily >= prov_cap:
            self._circuit_open[provider] = True
            _LOG.warning(
                "%s Circuit breaker tripped for %s: daily $%.4f >= $%.4f cap",
                MURPHY_LLM_GOV_ERR_004,
                provider,
                prov_daily,
                prov_cap,
            )

        # Global daily cap
        if daily_cost >= self._daily_total_cap:
            for p in self._provider_budgets:
                self._circuit_open[p] = True
            _LOG.warning(
                "%s Global daily budget exceeded: $%.4f >= $%.4f",
                MURPHY_LLM_GOV_ERR_004,
                daily_cost,
                self._daily_total_cap,
            )

        # Global hourly cap
        if hourly_cost >= self._hourly_total_cap:
            for p in self._provider_budgets:
                self._circuit_open[p] = True
            _LOG.warning(
                "%s Global hourly budget exceeded: $%.4f >= $%.4f",
                MURPHY_LLM_GOV_ERR_005,
                hourly_cost,
                self._hourly_total_cap,
            )

    def _maybe_reset_circuits(self) -> None:
        """Auto-reset circuit breakers at midnight UTC."""
        today = datetime.now(timezone.utc).day
        with self._lock:
            if self._circuit_reset_day != today:
                self._circuit_open.clear()
                self._circuit_reset_day = today
                # Prune usage records older than 48 h to bound memory
                cutoff = time.time() - 172800
                self._usage_records = [
                    r for r in self._usage_records if r.timestamp >= cutoff
                ]
                _LOG.info("Circuit breakers reset for new UTC day (%d)", today)

    @staticmethod
    def _period_cutoff(period: str) -> float:
        """Return epoch timestamp for start of current *period*."""
        now = datetime.now(timezone.utc)
        if period == "hour":
            start = now.replace(minute=0, second=0, microsecond=0)
        else:  # "day"
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp()

    @staticmethod
    def _percentile(sorted_values: List[float], pct: float) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * (pct / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_values):
            return sorted_values[-1]
        d = k - f
        return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])

    @staticmethod
    def _try_sysfs_gpu() -> Optional[GPUStats]:
        """Fallback: read AMD/Intel GPU info from sysfs (limited data)."""
        try:
            drm_root = Path("/sys/class/drm")
            if not drm_root.exists():
                return None
            for card in sorted(drm_root.iterdir()):
                mem_used_path = card / "device" / "mem_info_vram_used"
                mem_total_path = card / "device" / "mem_info_vram_total"
                if mem_used_path.exists() and mem_total_path.exists():
                    used = int(mem_used_path.read_text().strip()) / (1024 * 1024)
                    total = int(mem_total_path.read_text().strip()) / (1024 * 1024)
                    return GPUStats(
                        memory_used_mb=used,
                        memory_total_mb=total,
                        utilization_percent=0.0,
                        temperature_celsius=0.0,
                    )
        except Exception as exc:
            # MURPHY-LLM-GOV-ERR-010
            _LOG.debug(
                "%s sysfs GPU fallback failed: %s",
                MURPHY_LLM_GOV_ERR_010,
                exc,
            )
        return None


# ---------------------------------------------------------------------------
# Module-level convenience (singleton)
# ---------------------------------------------------------------------------
_governor: Optional[LLMGovernor] = None
_governor_lock = threading.Lock()


def get_governor(config: Optional[Dict[str, Any]] = None) -> LLMGovernor:
    """Return the module-level singleton :class:`LLMGovernor`."""
    global _governor
    with _governor_lock:
        if _governor is None:
            _governor = LLMGovernor(config)
        return _governor
