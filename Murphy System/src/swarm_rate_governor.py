# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: src/swarm_rate_governor.py
Subsystem: Rate Limiting / Production Hardening
Label: SWARM-RATE-GOV — Swarm-Native Global Rate Governor

Purpose
-------
Global rate limiting for Murphy System that understands the swarm-native
architecture.  Unlike simple per-IP token-bucket limiters, this governor
accounts for:

  • Multi-cursor browser sessions (up to 64 physical zones per build)
  • Dual-swarm execution (exploration + control swarm)
  • AI sensor streams (heartbeat, anomaly detection, telemetry)
  • Agent-to-agent RPC (internal coordination traffic)
  • HITL approval flows (must never be rate-limited)

The governor applies TIERED policies that distinguish between:
  1. Human API calls (browser, CLI, external integrations)
  2. Swarm-internal traffic (agent RPC, workspace writes)
  3. AI sensor / telemetry (heartbeat, anomaly, metric push)
  4. HITL / safety-critical paths (always allowed through)

Commissioning Answers
---------------------
1. Does this do what it was designed to do?
   YES — protects the server from overload while allowing legitimate swarm
   traffic to flow without artificial throttling.

2. What is it supposed to do?
   Apply per-client token-bucket rate limits to human API traffic, while
   classifying swarm-internal and sensor traffic under separate, higher
   limits.  Safety-critical paths (HITL, health) are never limited.

3. What conditions are possible?
   - Normal human traffic → standard limit (60/min default)
   - Swarm build in progress → swarm paths get swarm-tier limits (600/min)
   - AI sensor burst → sensor paths get sensor-tier limits (300/min)
   - HITL approval → always passes, never limited
   - Memory exhaustion → hard cap on bucket count (100k) with TTL eviction
   - Clock skew → monotonic time used for all bucket arithmetic

4. Does the test profile reflect the full range?
   YES — see tests/test_swarm_rate_governor.py

5. Expected result at all points?
   - Under limit: request passes, remaining count decremented
   - Over limit: HTTP 429 with Retry-After header and structured JSON
   - HITL/health: always passes regardless of bucket state
   - Cleanup runs every 5 min, evicts buckets idle > 1 hour

6. Actual result?  Verified via test suite.

7. Restart from symptoms?
   If 429 errors appear on legitimate swarm traffic, check:
   (a) X-Murphy-Traffic-Class header is set correctly by agent runtime
   (b) Swarm tier limit is sufficient for current build parallelism
   (c) Bucket TTL hasn't evicted a legitimate long-running session

8. Documentation updated?  YES — this docstring + GAP_CLOSURE_EXECUTION_PLAN.md

9. Hardening applied?
   - CWE-400: Bucket count hard-capped at MAX_BUCKETS
   - CWE-770: Periodic cleanup prevents unbounded memory growth
   - Thread-safe: threading.Lock on all mutable state
   - Monotonic clock: time.monotonic() for immune-to-NTP-skew arithmetic

10. Re-commissioned?  YES — after each change, run:
    pytest tests/test_swarm_rate_governor.py -v
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Traffic classification
# ---------------------------------------------------------------------------

class TrafficClass(str, Enum):
    """Traffic classes for rate limiting tiers."""
    HUMAN = "human"          # Browser, CLI, external API consumers
    SWARM = "swarm"          # Agent-to-agent, workspace RPC, swarm coordination
    SENSOR = "sensor"        # AI sensor streams, heartbeat, anomaly, telemetry
    SAFETY = "safety"        # HITL approvals, health checks — NEVER rate-limited


# Paths that are NEVER rate-limited (safety-critical)
_EXEMPT_PATHS: Set[str] = {
    "/health",
    "/api/hitl/queue",
    "/api/hitl/",              # prefix match handled separately
    "/api/errors/catalog",
    "/api/errors/",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Path prefixes that indicate swarm-internal traffic
_SWARM_PATH_PREFIXES = (
    "/api/swarm/",
    "/api/workspace/",
    "/api/agent/",
    "/module-instances/",
)

# Path prefixes that indicate AI sensor / telemetry traffic
_SENSOR_PATH_PREFIXES = (
    "/api/heartbeat/",
    "/api/telemetry/",
    "/api/anomaly/",
    "/api/metrics/",
)

# ---------------------------------------------------------------------------
# Per-class rate limits (requests_per_minute, burst_size)
# ---------------------------------------------------------------------------

_CLASS_LIMITS: Dict[TrafficClass, tuple] = {
    TrafficClass.HUMAN:  (60,  15),    # 60 req/min, burst 15
    TrafficClass.SWARM:  (600, 100),   # 600 req/min, burst 100 (swarm-native)
    TrafficClass.SENSOR: (300, 50),    # 300 req/min, burst 50 (sensor streams)
    TrafficClass.SAFETY: (-1,  -1),    # unlimited — never limited
}

# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------

_BUCKET_TTL = 3600         # evict idle buckets after 1 hour
_CLEANUP_INTERVAL = 300    # run cleanup every 5 minutes
_MAX_BUCKETS = 100_000     # hard cap — CWE-400 mitigation

# ---------------------------------------------------------------------------
# Core governor
# ---------------------------------------------------------------------------

class SwarmRateGovernor:
    """Swarm-native global rate governor.

    Classifies each request by traffic class and applies per-class token-bucket
    rate limiting.  Safety-critical paths always pass.

    Usage in FastAPI middleware::

        governor = SwarmRateGovernor()

        @app.middleware("http")
        async def rate_limit_middleware(request, call_next):
            result = governor.check(request)
            if not result["allowed"]:
                return JSONResponse(status_code=429, content=result)
            return await call_next(request)
    """

    def __init__(
        self,
        human_rpm: int = 60,
        human_burst: int = 15,
        swarm_rpm: int = 600,
        swarm_burst: int = 100,
        sensor_rpm: int = 300,
        sensor_burst: int = 50,
    ) -> None:
        self._lock = threading.Lock()
        # Bucket storage: key → {"tokens": float, "last_refill": float, "class": str}
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup = time.monotonic()

        # Allow runtime override of per-class limits
        self._limits: Dict[TrafficClass, tuple] = {
            TrafficClass.HUMAN:  (human_rpm, human_burst),
            TrafficClass.SWARM:  (swarm_rpm, swarm_burst),
            TrafficClass.SENSOR: (sensor_rpm, sensor_burst),
            TrafficClass.SAFETY: (-1, -1),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, request: Any) -> Dict[str, Any]:
        """Check whether the request should be allowed.

        Returns a dict with at minimum ``{"allowed": bool, "traffic_class": str}``.
        If denied, also includes ``retry_after_seconds`` and an error message.
        """
        path = _get_path(request)
        traffic_class = self._classify(request, path)

        # Safety-critical — always allow
        if traffic_class == TrafficClass.SAFETY:
            return {"allowed": True, "traffic_class": traffic_class.value, "remaining": -1}

        rpm, burst = self._limits[traffic_class]
        if rpm == -1:
            return {"allowed": True, "traffic_class": traffic_class.value, "remaining": -1}

        client_key = self._client_key(request, traffic_class)

        with self._lock:
            self._maybe_cleanup()
            now = time.monotonic()

            bucket = self._buckets.get(client_key)
            if bucket is None:
                if len(self._buckets) >= _MAX_BUCKETS:
                    self._force_cleanup(now)
                    if len(self._buckets) >= _MAX_BUCKETS:
                        logger.warning("Rate governor: bucket hard cap reached (%d)", _MAX_BUCKETS)
                        return {
                            "allowed": False,
                            "traffic_class": traffic_class.value,
                            "error": "MURPHY-E201",
                            "message": "Server rate limit capacity reached",
                            "retry_after_seconds": 60,
                        }
                bucket = {"tokens": float(burst), "last_refill": now, "class": traffic_class.value}
                self._buckets[client_key] = bucket

            # Refill tokens
            elapsed = now - bucket["last_refill"]
            refill_rate = rpm / 60.0  # tokens per second
            bucket["tokens"] = min(float(burst), bucket["tokens"] + elapsed * refill_rate)
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                remaining = int(bucket["tokens"])
                return {
                    "allowed": True,
                    "traffic_class": traffic_class.value,
                    "remaining": remaining,
                    "limit": rpm,
                }
            else:
                # Denied — compute retry delay
                deficit = 1.0 - bucket["tokens"]
                retry_after = deficit / refill_rate if refill_rate > 0 else 60
                return {
                    "allowed": False,
                    "traffic_class": traffic_class.value,
                    "error": "MURPHY-E201",
                    "message": f"Rate limit exceeded for {traffic_class.value} traffic",
                    "retry_after_seconds": round(retry_after, 1),
                    "limit": rpm,
                    "remaining": 0,
                }

    def status(self) -> Dict[str, Any]:
        """Return governor status for diagnostics."""
        with self._lock:
            class_counts: Dict[str, int] = {}
            for b in self._buckets.values():
                cls = b.get("class", "unknown")
                class_counts[cls] = class_counts.get(cls, 0) + 1
            return {
                "active_buckets": len(self._buckets),
                "max_buckets": _MAX_BUCKETS,
                "limits": {tc.value: {"rpm": l[0], "burst": l[1]} for tc, l in self._limits.items()},
                "buckets_by_class": class_counts,
            }

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, request: Any, path: str) -> TrafficClass:
        """Classify request into a traffic class."""
        # 1) Exempt paths → safety
        if path in _EXEMPT_PATHS:
            return TrafficClass.SAFETY
        for exempt in _EXEMPT_PATHS:
            if exempt.endswith("/") and path.startswith(exempt):
                return TrafficClass.SAFETY

        # 2) Explicit header override (agents set this)
        headers = getattr(request, "headers", {}) or {}
        explicit = (headers.get("X-Murphy-Traffic-Class") or "").strip().lower()
        if explicit == "swarm":
            return TrafficClass.SWARM
        if explicit == "sensor":
            return TrafficClass.SENSOR
        if explicit == "safety":
            return TrafficClass.SAFETY

        # 3) Path-based classification
        for prefix in _SWARM_PATH_PREFIXES:
            if path.startswith(prefix):
                return TrafficClass.SWARM
        for prefix in _SENSOR_PATH_PREFIXES:
            if path.startswith(prefix):
                return TrafficClass.SENSOR

        # 4) Default → human
        return TrafficClass.HUMAN

    def _client_key(self, request: Any, traffic_class: TrafficClass) -> str:
        """Build a bucket key from request identity + traffic class."""
        headers = getattr(request, "headers", {}) or {}
        user_id = (headers.get("X-User-ID") or "").strip()
        if user_id:
            return f"{traffic_class.value}:{user_id}"
        # Fall back to IP
        fwd = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        client = getattr(request, "client", None)
        ip = fwd or (client.host if client else "unknown")
        return f"{traffic_class.value}:ip:{ip}"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._force_cleanup(now)

    def _force_cleanup(self, now: float) -> None:
        stale = [k for k, v in self._buckets.items() if now - v["last_refill"] > _BUCKET_TTL]
        for k in stale:
            del self._buckets[k]
        self._last_cleanup = now
        if stale:
            logger.info("Rate governor cleanup: evicted %d idle buckets", len(stale))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_path(request: Any) -> str:
    """Extract URL path from various request-like objects."""
    # FastAPI/Starlette Request
    url = getattr(request, "url", None)
    if url is not None:
        return getattr(url, "path", str(url))
    # dict-like
    if isinstance(request, dict):
        return request.get("path", "/")
    return "/"
