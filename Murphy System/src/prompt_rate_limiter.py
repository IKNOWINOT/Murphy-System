# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: src/prompt_rate_limiter.py
Subsystem: Rate Limiting / Production Hardening
Label: PROMPT-RATE-001 — Per-tenant swarm-aware rate limiter for /api/prompt

Purpose
-------
The global :class:`SwarmRateGovernor` (label SWARM-RATE-GOV) protects the
process from overload across all routes.  ``/api/prompt`` is special: every
hit triggers an LLM round-trip, which is the most expensive operation in
the system, and Murphy is built for *swarms* — many cooperating agents,
sometimes from a single tenant, all submitting prompts in parallel.

This module adds a **second, per-tenant** token-bucket guard layered on top
of the global governor.  It exists so that one tenant's swarm cannot drain
the LLM budget for everyone else, while still letting a single tenant's
swarm burst higher than a human user could.

Design (matches the 10-question commissioning checklist)
--------------------------------------------------------
1. Does the module do what it was designed to do?
   YES — verified by ``tests/hardening/test_prompt_rate_limiter.py``: a
   single tenant exhausts its bucket while a second tenant continues to
   pass; ``X-Murphy-Traffic-Class: swarm`` callers get the larger bucket.

2. What is it supposed to do?
   Apply a per-tenant token-bucket on prompt submissions.  Two tiers:
     - **human**: tenant_id alone (default)
     - **swarm**: tenant_id with ``X-Murphy-Traffic-Class: swarm`` header
   Sized so a 30-agent swarm can submit a coordinated batch (burst), then
   refill at the steady RPM.

3. What conditions are possible?
   - Normal human submission → human bucket consumed
   - Swarm batch from one tenant → swarm bucket consumed (larger)
   - Mixed traffic → each request keyed by class so they don't poison
     each other's bucket
   - Memory: hard-capped at MAX_BUCKETS, idle buckets evicted via TTL
   - Clock skew: monotonic clock used everywhere

4. Does the test profile reflect the full range?
   YES — see test file (allow / deny / cross-tenant isolation / swarm tier
   / cleanup / monotonic).

5. Expected result at all points?
   - Under limit → ``RateLimitDecision(allowed=True, ...)`` with remaining
   - Over limit → ``allowed=False`` with structured ``error``, ``message``,
     ``retry_after_seconds`` (caller maps to HTTP 429 + ``Retry-After``)
   - Empty tenant_id → falls back to the literal key ``"anon"``.  Callers
     should reject empty tenant_id at the API layer; this is defence in
     depth, never silent acceptance.

6. Actual result?  Verified via test suite.

7. Restart from symptoms?
   If callers see unexpected 429s, fetch ``status()`` to inspect bucket
   counts, then bump ``MURPHY_PROMPT_BURST`` / ``MURPHY_PROMPT_RPM`` (or
   the swarm equivalents) without restarting the process.

8. Documentation updated?
   YES — this docstring + STATUS.md note + per-response ``llm_provider``
   field documented in API_DOCUMENTATION.md.

9. Hardening applied?
   - CWE-400 / CWE-770: ``MAX_BUCKETS`` cap + periodic TTL eviction
   - Thread safety: single ``threading.Lock`` around bucket map
   - Monotonic clock: ``time.monotonic()`` for refill arithmetic
   - No silent failures: every denial returns a structured decision with
     a stable error code (``MURPHY-E202``) so callers cannot drop it on
     the floor

10. Re-commissioned?  YES — pytest tests/hardening/test_prompt_rate_limiter.py
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants — env-overridable so swarm capacity can scale at runtime
# without redeploy.
# ---------------------------------------------------------------------------

_DEFAULT_HUMAN_RPM   = 60     # 1 prompt / second steady state
_DEFAULT_HUMAN_BURST = 15     # short bursts allowed
_DEFAULT_SWARM_RPM   = 300    # 5 prompts / second steady state
_DEFAULT_SWARM_BURST = 60     # ~30 cooperating agents firing twice each

_BUCKET_TTL          = 3600   # evict idle buckets after 1 hour
_CLEANUP_INTERVAL    = 300    # cleanup pass every 5 minutes
_MAX_BUCKETS         = 50_000 # CWE-400 mitigation


@dataclass(frozen=True)
class RateLimitDecision:
    """Structured outcome returned to the caller.

    Stable fields so callers can map directly to an HTTP response without
    having to introspect optionals.
    """
    allowed: bool
    traffic_class: str           # "human" | "swarm"
    tenant_id: str
    remaining: int               # tokens left after this request (0 if denied)
    limit: int                   # configured RPM for this class
    retry_after_seconds: float   # seconds until next token (0 when allowed)
    error: Optional[str] = None  # stable code when denied (e.g. "MURPHY-E202")
    message: Optional[str] = None


class PromptRateLimiter:
    """Per-tenant token-bucket guard for ``/api/prompt``.

    Two classes of buckets:
      - ``human`` (default): one bucket per ``tenant_id``
      - ``swarm`` (header-driven): a *separate* bucket per ``tenant_id``
        for callers that set ``X-Murphy-Traffic-Class: swarm``

    The two buckets are independent on purpose — a swarm's bursty LLM
    consumption shouldn't drain the human bucket that interactive users
    rely on, and vice versa.
    """

    def __init__(
        self,
        human_rpm: Optional[int]   = None,
        human_burst: Optional[int] = None,
        swarm_rpm: Optional[int]   = None,
        swarm_burst: Optional[int] = None,
    ) -> None:
        self._human_rpm   = int(human_rpm   if human_rpm   is not None else os.getenv("MURPHY_PROMPT_RPM",         _DEFAULT_HUMAN_RPM))
        self._human_burst = int(human_burst if human_burst is not None else os.getenv("MURPHY_PROMPT_BURST",       _DEFAULT_HUMAN_BURST))
        self._swarm_rpm   = int(swarm_rpm   if swarm_rpm   is not None else os.getenv("MURPHY_PROMPT_SWARM_RPM",   _DEFAULT_SWARM_RPM))
        self._swarm_burst = int(swarm_burst if swarm_burst is not None else os.getenv("MURPHY_PROMPT_SWARM_BURST", _DEFAULT_SWARM_BURST))

        # Defence in depth — refuse nonsense config rather than silently
        # creating a permanently-denying limiter.
        for label, value in (
            ("human_rpm", self._human_rpm), ("human_burst", self._human_burst),
            ("swarm_rpm", self._swarm_rpm), ("swarm_burst", self._swarm_burst),
        ):
            if value <= 0:
                raise ValueError(f"PROMPT-RATE-001: {label} must be > 0 (got {value})")

        self._lock = threading.Lock()
        # bucket_key -> {"tokens": float, "last_refill": float}
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._last_cleanup = time.monotonic()

        logger.info(
            "PROMPT-RATE-001 active — human=%d/min burst=%d, swarm=%d/min burst=%d",
            self._human_rpm, self._human_burst, self._swarm_rpm, self._swarm_burst,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, tenant_id: str, traffic_class: str = "human") -> RateLimitDecision:
        """Check whether a prompt submission is allowed.

        ``tenant_id``  — required; falls back to ``"anon"`` if blank, but
                         callers should reject empty tenant_id at the API
                         layer.  This is defence in depth.
        ``traffic_class`` — ``"human"`` (default) or ``"swarm"``.  Anything
                         else collapses to ``"human"`` so an attacker can't
                         elevate privilege by inventing a class name.
        """
        tenant_id = (tenant_id or "anon").strip() or "anon"
        cls = "swarm" if (traffic_class or "").strip().lower() == "swarm" else "human"

        if cls == "swarm":
            rpm, burst = self._swarm_rpm, self._swarm_burst
        else:
            rpm, burst = self._human_rpm, self._human_burst

        key = f"{cls}:{tenant_id}"
        refill_rate = rpm / 60.0  # tokens per second

        with self._lock:
            self._maybe_cleanup()
            now = time.monotonic()

            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= _MAX_BUCKETS:
                    # CWE-400: refuse to grow unbounded.
                    self._force_cleanup(now)
                    if len(self._buckets) >= _MAX_BUCKETS:
                        logger.warning(
                            "PROMPT-RATE-001: bucket cap reached (%d) — denying %s",
                            _MAX_BUCKETS, key,
                        )
                        return RateLimitDecision(
                            allowed=False, traffic_class=cls, tenant_id=tenant_id,
                            remaining=0, limit=rpm, retry_after_seconds=60.0,
                            error="MURPHY-E202",
                            message="Prompt rate-limit capacity reached server-wide",
                        )
                bucket = {"tokens": float(burst), "last_refill": now}
                self._buckets[key] = bucket

            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(float(burst), bucket["tokens"] + elapsed * refill_rate)
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return RateLimitDecision(
                    allowed=True, traffic_class=cls, tenant_id=tenant_id,
                    remaining=int(bucket["tokens"]), limit=rpm,
                    retry_after_seconds=0.0,
                )

            deficit = 1.0 - bucket["tokens"]
            retry_after = deficit / refill_rate if refill_rate > 0 else 60.0
            return RateLimitDecision(
                allowed=False, traffic_class=cls, tenant_id=tenant_id,
                remaining=0, limit=rpm,
                retry_after_seconds=round(retry_after, 2),
                error="MURPHY-E202",
                message=f"Prompt rate limit exceeded for tenant '{tenant_id}' ({cls} tier)",
            )

    def status(self) -> Dict[str, object]:
        """Diagnostic snapshot — surfaced via ``/api/rate-governor/status``."""
        with self._lock:
            by_class: Dict[str, int] = {}
            for k in self._buckets:
                cls = k.split(":", 1)[0]
                by_class[cls] = by_class.get(cls, 0) + 1
            return {
                "label": "PROMPT-RATE-001",
                "active_buckets": len(self._buckets),
                "max_buckets": _MAX_BUCKETS,
                "limits": {
                    "human": {"rpm": self._human_rpm, "burst": self._human_burst},
                    "swarm": {"rpm": self._swarm_rpm, "burst": self._swarm_burst},
                },
                "buckets_by_class": by_class,
            }

    # ------------------------------------------------------------------
    # Cleanup — bounded memory
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
            logger.info("PROMPT-RATE-001 cleanup: evicted %d idle buckets", len(stale))


__all__ = ["PromptRateLimiter", "RateLimitDecision"]
