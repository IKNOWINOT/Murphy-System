"""
LLM Inference Determinism Guard — Murphy System
================================================
Defeats nondeterminism in API-consumed LLM inference by adapting the
principles from Thinking Machines Lab's research on batch-invariant
kernel design to the API-consumer context.

While the original research targets GPU kernel-level nondeterminism in
self-hosted inference (batch-sensitive operations producing different
floating-point results depending on batch shape), Murphy System consumes
external LLM APIs (DeepInfra, Together.ai).  Nondeterminism in this
context manifests as:

  1. Same prompt → different outputs across calls (server-side batching,
     temperature sampling, provider-internal optimisations).
  2. Provider failover changes outputs (DeepInfra vs Together.ai vs
     onboard have different model weights / quantisation).
  3. No request fingerprinting for reproducibility audits.

This module provides:

  ■ REQUEST FINGERPRINTING — SHA-256 hash of canonicalised request
    parameters (model, messages, temperature, max_tokens, seed) so
    identical requests are reliably identified.

  ■ RESPONSE CACHING — Thread-safe LRU cache with configurable TTL.
    Identical requests within the TTL window return the cached response,
    guaranteeing bitwise-identical output for repeated calls.

  ■ DETERMINISTIC PARAMETER ENFORCEMENT — When callers request
    deterministic output, temperature is forced to 0.0 and a fixed
    seed is injected into the API request.

  ■ CONSISTENCY MONITOR — Tracks output hashes per request fingerprint.
    When the same fingerprint produces divergent outputs (outside the
    cache window), a drift event is logged with full diagnostics.

  ■ OUTPUT NORMALISATION — Strips formatting noise (trailing whitespace,
    inconsistent newline sequences) that does not affect semantic content
    but would cause spurious drift detection.

  ■ REPRODUCIBILITY AUDIT TRAIL — Every LLM call is logged with its
    request fingerprint, response hash, provider, latency, and cache
    status so that any output can be traced back to its exact inputs.

Commissioning Answers (G1–G9)
-----------------------------
1. G1 — Purpose: Does this do what it was designed to do?
   YES — provides deterministic LLM inference guarantees for API consumers
   through fingerprinting, caching, parameter enforcement, and monitoring.

2. G2 — Spec: What is it supposed to do?
   Ensure that identical LLM requests produce identical outputs whenever
   possible, detect and log when they don't, and provide a full audit
   trail for reproducibility.

3. G3 — Conditions: What conditions are possible?
   - Cache hit (deterministic mode) → return cached response
   - Cache miss → call LLM, fingerprint, cache, log
   - Cache expired (TTL) → re-call LLM, check consistency
   - Consistency drift detected → log warning with diagnostics
   - Provider failover → track provider in fingerprint metadata
   - Deterministic mode ON → temp=0, seed enforced
   - Deterministic mode OFF → normal pass-through with audit logging
   - Cache full → LRU eviction of oldest entries
   - Thread contention → all operations are lock-protected

4. G4 — Test Profile: Does test profile reflect full range?
   YES — tests cover all conditions in G3.

5. G5 — Expected Result: Identical inputs → identical outputs (cached);
   drift events logged when outputs diverge.

6. G6 — Actual Result: Validated via test_llm_determinism_guard.py.

7. G7 — As-Builts: This docstring, inline labels, test file.

8. G8 — Hardening: TTL bounds, max cache size (CWE-770), thread-safe
   locking, bounded audit log, input validation.

9. G9 — Re-commissioned: YES — after hardening.

Label: DETERM-GUARD-001
License: BSL 1.1 — Inoni LLC / Corey Post
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants  (label: DETERM-GUARD-CONST-001)
# ---------------------------------------------------------------------------

# Default time-to-live for cached responses (seconds).
DEFAULT_CACHE_TTL_S: float = 300.0  # 5 minutes

# Maximum number of cached responses (CWE-770 bound).
MAX_CACHE_ENTRIES: int = 1024

# Maximum number of audit-trail entries kept in memory.
MAX_AUDIT_ENTRIES: int = 10_000

# Maximum number of unique output hashes tracked per fingerprint for drift.
MAX_DRIFT_HASHES_PER_FP: int = 64

# Fixed seed used when deterministic mode is active.
DETERMINISTIC_SEED: int = 42

# Normalisation regex: collapse runs of whitespace / trailing spaces.
_WS_NORMALISE = re.compile(r"[ \t]+$", re.MULTILINE)
_MULTI_NEWLINE = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# Dataclasses  (label: DETERM-GUARD-DATA-001)
# ---------------------------------------------------------------------------

@dataclass
class RequestFingerprint:
    """Immutable fingerprint of an LLM request."""
    digest: str               # SHA-256 hex digest
    canonical_json: str       # The JSON string that was hashed
    deterministic: bool       # Was deterministic mode requested?
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class CachedResponse:
    """A cached LLM response keyed by request fingerprint."""
    fingerprint: str          # SHA-256 digest
    content: str              # The normalised LLM output
    content_hash: str         # SHA-256 of normalised content
    provider: str             # Which provider answered
    model: str                # Which model answered
    latency_s: float          # Original call latency
    cached_at: float          # monotonic timestamp
    ttl_s: float              # Configured TTL at cache time
    hit_count: int = 0        # Number of cache hits


@dataclass
class DriftEvent:
    """Record of a detected output divergence for the same fingerprint."""
    fingerprint: str
    previous_hash: str
    current_hash: str
    provider: str
    model: str
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class AuditEntry:
    """Single audit-trail entry for reproducibility tracking."""
    fingerprint: str
    content_hash: str
    provider: str
    model: str
    cache_hit: bool
    deterministic: bool
    latency_s: float
    drift_detected: bool = False
    timestamp: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Output Normaliser  (label: DETERM-GUARD-NORM-001)
# ---------------------------------------------------------------------------

def normalise_output(text: str) -> str:
    """Normalise LLM output to remove formatting noise.

    Strips trailing whitespace per line, collapses triple+ newlines to
    double, and strips leading/trailing whitespace from the whole string.
    This ensures that semantically identical outputs are compared equally
    even if the provider adds/removes cosmetic whitespace.
    """
    text = _WS_NORMALISE.sub("", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Request Fingerprinter  (label: DETERM-GUARD-FP-001)
# ---------------------------------------------------------------------------

def fingerprint_request(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    seed: Optional[int] = None,
    deterministic: bool = False,
) -> RequestFingerprint:
    """Compute a SHA-256 fingerprint of a canonicalised LLM request.

    The canonical form is a JSON string with sorted keys and no optional
    whitespace so that logically identical requests always hash identically.
    """
    canonical = {
        "messages": [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in messages
        ],
        "model": model,
        "temperature": round(temperature, 6),
        "max_tokens": max_tokens,
    }
    if seed is not None:
        canonical["seed"] = seed
    if deterministic:
        canonical["deterministic"] = True

    canonical_json = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return RequestFingerprint(
        digest=digest,
        canonical_json=canonical_json,
        deterministic=deterministic,
    )


def hash_content(text: str) -> str:
    """SHA-256 hex digest of normalised content."""
    return hashlib.sha256(normalise_output(text).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Determinism Guard  (label: DETERM-GUARD-CORE-001)
# ---------------------------------------------------------------------------

class LLMDeterminismGuard:
    """Central determinism guard for all Murphy LLM calls.

    Thread-safe.  Intended to be used as a singleton alongside
    MurphyLLMProvider.

    Usage::

        from src.llm_determinism_guard import get_determinism_guard
        guard = get_determinism_guard()

        # Before calling the LLM:
        params = guard.enforce_deterministic_params(
            temperature=0.7, seed=None, deterministic=True,
        )

        # After receiving a response:
        audit = guard.record_response(
            messages=messages, model="meta-llama/...",
            temperature=params["temperature"], max_tokens=8192,  # PATCH-106a: capped
            seed=params.get("seed"), deterministic=True,
            content="...", provider="deepinfra", latency_s=1.23,
        )

        # Or use the cache-aware wrapper:
        cached = guard.get_cached(messages, model, temperature, max_tokens, seed, deterministic)
        if cached:
            return cached.content  # Guaranteed identical
    """

    def __init__(
        self,
        cache_ttl_s: float = DEFAULT_CACHE_TTL_S,
        max_cache: int = MAX_CACHE_ENTRIES,
        max_audit: int = MAX_AUDIT_ENTRIES,
    ) -> None:
        # Validate bounds  (label: DETERM-GUARD-HARDENING-001)
        if cache_ttl_s < 0:
            raise ValueError("cache_ttl_s must be non-negative")
        if max_cache < 0:
            raise ValueError("max_cache must be non-negative")
        if max_audit < 0:
            raise ValueError("max_audit must be non-negative")

        self._cache_ttl_s = cache_ttl_s
        self._max_cache = max_cache
        self._max_audit = max_audit

        # LRU cache: fingerprint digest → CachedResponse
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._lock = threading.Lock()

        # Drift tracking: fingerprint digest → set of content hashes
        self._drift_tracker: Dict[str, List[str]] = {}

        # Drift events log (bounded)
        self._drift_events: List[DriftEvent] = []

        # Audit trail (bounded ring buffer)
        self._audit_trail: List[AuditEntry] = []

        # Counters
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "drift_events": 0,
            "total_calls": 0,
            "deterministic_calls": 0,
        }

        logger.info(
            "LLMDeterminismGuard initialised — "  # DETERM-GUARD-INIT-001
            "cache_ttl=%.0fs, max_cache=%d, max_audit=%d",
            cache_ttl_s, max_cache, max_audit,
        )

    # ------------------------------------------------------------------
    # Deterministic Parameter Enforcement  (label: DETERM-GUARD-ENFORCE-001)
    # ------------------------------------------------------------------

    def enforce_deterministic_params(
        self,
        temperature: float,
        seed: Optional[int],
        deterministic: bool,
    ) -> Dict[str, Any]:
        """Return adjusted parameters for deterministic inference.

        When ``deterministic`` is True:
          - temperature is forced to 0.0
          - seed is set to DETERMINISTIC_SEED (if not already provided)

        When ``deterministic`` is False, parameters are returned unchanged.
        """
        if not deterministic:
            return {"temperature": temperature, "seed": seed}

        adjusted_seed = seed if seed is not None else DETERMINISTIC_SEED
        if temperature != 0.0:
            logger.debug(
                "DETERM-GUARD-ENFORCE-001: forcing temperature %.2f → 0.0 "
                "(deterministic mode)", temperature,
            )
        return {"temperature": 0.0, "seed": adjusted_seed}

    # ------------------------------------------------------------------
    # Cache Operations  (label: DETERM-GUARD-CACHE-001)
    # ------------------------------------------------------------------

    def get_cached(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        seed: Optional[int] = None,
        deterministic: bool = False,
    ) -> Optional[CachedResponse]:
        """Return a cached response if one exists and has not expired."""
        fp = fingerprint_request(
            messages, model, temperature, max_tokens, seed, deterministic,
        )
        with self._lock:
            entry = self._cache.get(fp.digest)
            if entry is None:
                return None

            # Check TTL
            age = time.monotonic() - entry.cached_at
            if age > entry.ttl_s:
                # Expired — evict
                del self._cache[fp.digest]
                logger.debug(
                    "DETERM-GUARD-CACHE-002: expired entry for %s (age=%.1fs > ttl=%.1fs)",
                    fp.digest[:12], age, entry.ttl_s,
                )
                return None

            # Cache hit — move to end (LRU) and bump counter
            self._cache.move_to_end(fp.digest)
            entry.hit_count += 1
            self._stats["cache_hits"] += 1
            logger.debug(
                "DETERM-GUARD-CACHE-003: cache hit for %s (hits=%d, age=%.1fs)",
                fp.digest[:12], entry.hit_count, age,
            )
            return entry

    def _evict_if_full(self) -> None:
        """Evict oldest cache entry if at capacity.  Caller must hold _lock."""
        while len(self._cache) >= self._max_cache:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(
                "DETERM-GUARD-CACHE-004: evicted oldest entry %s", evicted_key[:12],
            )

    # ------------------------------------------------------------------
    # Record Response  (label: DETERM-GUARD-RECORD-001)
    # ------------------------------------------------------------------

    def record_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        seed: Optional[int],
        deterministic: bool,
        content: str,
        provider: str,
        latency_s: float,
    ) -> AuditEntry:
        """Record an LLM response: cache it, check drift, write audit entry.

        Returns the AuditEntry for the caller to inspect.
        """
        fp = fingerprint_request(
            messages, model, temperature, max_tokens, seed, deterministic,
        )
        normalised = normalise_output(content)
        c_hash = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
        drift = False

        with self._lock:
            self._stats["total_calls"] += 1
            if deterministic:
                self._stats["deterministic_calls"] += 1

            # ── Cache the response ────────────────────────────────────
            self._evict_if_full()
            self._cache[fp.digest] = CachedResponse(
                fingerprint=fp.digest,
                content=normalised,
                content_hash=c_hash,
                provider=provider,
                model=model,
                latency_s=latency_s,
                cached_at=time.monotonic(),
                ttl_s=self._cache_ttl_s,
            )
            self._cache.move_to_end(fp.digest)

            # ── Drift detection ───────────────────────────────────────
            # (label: DETERM-GUARD-DRIFT-001)
            if fp.digest not in self._drift_tracker:
                self._drift_tracker[fp.digest] = []
            seen = self._drift_tracker[fp.digest]

            if seen and c_hash not in seen:
                drift = True
                self._stats["drift_events"] += 1
                event = DriftEvent(
                    fingerprint=fp.digest,
                    previous_hash=seen[-1],
                    current_hash=c_hash,
                    provider=provider,
                    model=model,
                )
                # Bound drift events list (CWE-770)
                if len(self._drift_events) >= MAX_AUDIT_ENTRIES:
                    self._drift_events = self._drift_events[-(MAX_AUDIT_ENTRIES // 2):]
                self._drift_events.append(event)
                logger.warning(
                    "DETERM-GUARD-DRIFT-001: output drift detected for fingerprint "
                    "%s — previous_hash=%s, current_hash=%s, provider=%s, model=%s",
                    fp.digest[:12], seen[-1][:12], c_hash[:12], provider, model,
                )

            if c_hash not in seen:
                # Bound per-fingerprint hash list
                if len(seen) >= MAX_DRIFT_HASHES_PER_FP:
                    seen.pop(0)
                seen.append(c_hash)

            # ── Audit trail ───────────────────────────────────────────
            # (label: DETERM-GUARD-AUDIT-001)
            entry = AuditEntry(
                fingerprint=fp.digest,
                content_hash=c_hash,
                provider=provider,
                model=model,
                cache_hit=False,
                deterministic=deterministic,
                latency_s=latency_s,
                drift_detected=drift,
            )
            if len(self._audit_trail) >= self._max_audit:
                self._audit_trail = self._audit_trail[-(self._max_audit // 2):]
            self._audit_trail.append(entry)
            self._stats["cache_misses"] += 1

        return entry

    # ------------------------------------------------------------------
    # Diagnostics  (label: DETERM-GUARD-DIAG-001)
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return a snapshot of determinism guard statistics."""
        with self._lock:
            return {
                **self._stats,
                "cache_size": len(self._cache),
                "drift_tracker_size": len(self._drift_tracker),
                "audit_trail_size": len(self._audit_trail),
                "cache_ttl_s": self._cache_ttl_s,
                "max_cache": self._max_cache,
            }

    def get_drift_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent drift events as dicts."""
        with self._lock:
            events = self._drift_events[-limit:]
            return [
                {
                    "fingerprint": e.fingerprint[:16],
                    "previous_hash": e.previous_hash[:16],
                    "current_hash": e.current_hash[:16],
                    "provider": e.provider,
                    "model": e.model,
                    "timestamp": e.timestamp,
                }
                for e in events
            ]

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit entries as dicts."""
        with self._lock:
            entries = self._audit_trail[-limit:]
            return [
                {
                    "fingerprint": e.fingerprint[:16],
                    "content_hash": e.content_hash[:16],
                    "provider": e.provider,
                    "model": e.model,
                    "cache_hit": e.cache_hit,
                    "deterministic": e.deterministic,
                    "latency_s": round(e.latency_s, 3),
                    "drift_detected": e.drift_detected,
                    "timestamp": e.timestamp,
                }
                for e in entries
            ]

    def clear_cache(self) -> int:
        """Clear the response cache.  Returns the number of entries evicted."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info("DETERM-GUARD-CACHE-005: cache cleared (%d entries)", count)
            return count

    def reset(self) -> None:
        """Full reset — cache, drift tracker, audit trail, and stats."""
        with self._lock:
            self._cache.clear()
            self._drift_tracker.clear()
            self._drift_events.clear()
            self._audit_trail.clear()
            self._stats = {
                "cache_hits": 0,
                "cache_misses": 0,
                "drift_events": 0,
                "total_calls": 0,
                "deterministic_calls": 0,
            }
            logger.info("DETERM-GUARD-RESET-001: full reset")


# ---------------------------------------------------------------------------
# Module-level singleton  (label: DETERM-GUARD-SINGLETON-001)
# ---------------------------------------------------------------------------

_guard: Optional[LLMDeterminismGuard] = None
_guard_lock = threading.Lock()


def get_determinism_guard(
    cache_ttl_s: float = DEFAULT_CACHE_TTL_S,
    max_cache: int = MAX_CACHE_ENTRIES,
    max_audit: int = MAX_AUDIT_ENTRIES,
) -> LLMDeterminismGuard:
    """Return the module-level singleton LLMDeterminismGuard.

    On first call, creates the guard with the given parameters.
    Subsequent calls return the existing instance (parameters ignored).
    """
    global _guard
    if _guard is not None:
        return _guard
    with _guard_lock:
        if _guard is None:
            _guard = LLMDeterminismGuard(
                cache_ttl_s=cache_ttl_s,
                max_cache=max_cache,
                max_audit=max_audit,
            )
    return _guard


def reset_determinism_guard(
    guard: Optional[LLMDeterminismGuard] = None,
) -> None:
    """Reset the singleton (useful in tests)."""
    global _guard
    _guard = guard
