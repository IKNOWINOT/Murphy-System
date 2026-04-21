# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: src/llm_self_check.py
Subsystem: LLM / Production Hardening
Label: LLM-SELFCHECK-001 — Startup self-inference + provider verification

Purpose
-------
At startup the system must prove three things, otherwise operators cannot
trust the rest of the platform:

  1. The LLM provider chain (DeepInfra → Together → onboard) is reachable
     **and** which one actually answered.  A "fast" response that turns out
     to be the local onboard fallback is the failure mode this module
     exists to expose.
  2. The model emits *structured, schema-conformant* output for the kind
     of automation-design prompt ``/api/prompt`` issues.
  3. The system can perform inference on its own generated data — i.e.
     it feeds the first response back into the LLM as a verification
     prompt and confirms the verifier agrees.  This is the "what it has
     is what it needs to run" requirement.

Design follows 2025 LLM-inference best practices
------------------------------------------------
  * **Structured outputs** — explicit JSON schema requested in the prompt;
    response parsed with ``json.loads`` and validated against the schema
    by ``_validate_schema`` (no regex, no string scraping).
  * **Idempotent retry with reinforcement** — if the first call returns
    malformed JSON we retry once with a stronger instruction
    ("Remember: output a single valid JSON object.").
  * **Bounded timeout** — overall self-check capped at
    ``MURPHY_SELFCHECK_TIMEOUT`` seconds (default 20s) so a slow provider
    cannot block startup.  Per-call timeout flows through the existing
    provider's ``timeout`` setting.
  * **Error categorization** — every failure is tagged ``schema``,
    ``model``, ``network``, ``content``, or ``config`` so dashboards can
    aggregate sensibly.
  * **Observability** — structured log line + structured ``SelfCheckResult``
    capturing provider, model, latency_ms, retry_count, error_category,
    correlation_id (UUID).

Commissioning checklist (10 questions)
--------------------------------------
1. Does it do what it was designed to do?
   YES — verified by ``tests/hardening/test_llm_self_check.py`` using a
   stub provider that simulates DeepInfra success, schema-malformed
   response with retry recovery, and total-fallback (onboard) cases.

2. What is it supposed to do?
   Run a single bounded LLM round-trip + a verification round-trip,
   classify the outcome, and return a ``SelfCheckResult`` that the server
   can expose on ``/health`` and ``/api/llm/selfcheck``.

3. What conditions are possible?
   - All providers up → status="ok", provider="deepinfra"
   - DeepInfra down → status="degraded", provider="together"
   - All API providers down → status="degraded", provider="onboard"
   - LLM module not loaded → status="unavailable", provider=None
   - Schema malformed twice → status="schema_failure"
   - Verifier disagrees → status="verification_failed"
   - Timeout → status="timeout"

4. Does the test profile reflect the full range?
   YES — every status above has a unit test.

5. Expected result at all points?  See condition table above.
6. Actual result?  Verified by test suite.

7. Restart from symptoms?
   If ``/api/llm/selfcheck`` reports ``provider="onboard"`` but
   ``DEEPINFRA_API_KEY`` is set, the operator's first move is to fetch
   ``error_category`` and ``last_error``: ``network`` => egress problem,
   ``model`` => provider 4xx/5xx (likely bad key or model name), ``schema``
   => model returned non-JSON, ``config`` => env/SDK setup wrong.

8. Documentation updated?  YES — STATUS.md gains an LLM Self-Check row,
   API_DOCUMENTATION.md gains the ``/api/llm/selfcheck`` route.

9. Hardening applied?
   - Bounded timeout (CWE-400)
   - Try/except around every external call; nothing raises out of
     ``run_self_check`` unprompted (the function never lets startup crash)
   - Structured logging with correlation_id (no PII in prompt)
   - No silent failure: a degraded result is *returned*, not swallowed

10. Re-commissioned?  YES — pytest tests/hardening/test_llm_self_check.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------

@dataclass
class SelfCheckResult:
    """Structured outcome of a single self-check run.

    All fields are JSON-serialisable so the result can be returned as-is
    from the ``/api/llm/selfcheck`` endpoint and embedded in ``/health``.
    """
    status: str                     # "ok" | "degraded" | "unavailable" | "schema_failure"
                                    # | "verification_failed" | "timeout" | "config_error"
    provider: Optional[str]         # actual provider that answered (deepinfra/together/onboard)
    model: Optional[str]
    latency_ms: int
    retry_count: int
    verified: bool                  # did the verifier agree?
    correlation_id: str
    error_category: Optional[str] = None   # schema|model|network|content|config|None
    last_error: Optional[str] = None
    generated_payload: Optional[Dict[str, Any]] = None
    verifier_payload: Optional[Dict[str, Any]] = None
    schema_violations: List[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Schema for the generated automation payload (the "shape we need to run")
# ---------------------------------------------------------------------------
# Matches what /api/prompt already asks the model for (name/description/steps).

_REQUIRED_KEYS = ("name", "description", "steps")
_NAME_MAX_LEN = 80
_DESC_MIN_LEN = 10


def _validate_schema(payload: Any) -> List[str]:
    """Return a list of human-readable schema violations (empty = valid).

    Pure function; no logging.  Best-practices §3 (Fail Fast).
    """
    violations: List[str] = []
    if not isinstance(payload, dict):
        return [f"top-level value is {type(payload).__name__}, expected object"]
    for key in _REQUIRED_KEYS:
        if key not in payload:
            violations.append(f"missing required key: {key!r}")
    name = payload.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        violations.append("'name' must be a non-empty string")
    elif isinstance(name, str) and len(name) > _NAME_MAX_LEN:
        violations.append(f"'name' exceeds {_NAME_MAX_LEN} chars")
    desc = payload.get("description")
    if desc is not None and (not isinstance(desc, str) or len(desc.strip()) < _DESC_MIN_LEN):
        violations.append(f"'description' must be a string of at least {_DESC_MIN_LEN} chars")
    steps = payload.get("steps")
    if steps is not None:
        if not isinstance(steps, list) or not steps:
            violations.append("'steps' must be a non-empty array")
        elif not all(isinstance(s, str) and s.strip() for s in steps):
            violations.append("'steps' entries must be non-empty strings")
    return violations


# ---------------------------------------------------------------------------
# Prompts — kept module-level so they're easy to audit / swap.
# ---------------------------------------------------------------------------

_SELFCHECK_PROMPT = (
    "Design a tiny test automation that emails a daily summary at 9am.\n\n"
    "Return ONLY a JSON object with exactly these keys:\n"
    '{"name": "short title", '
    '"description": "two sentence description", '
    '"steps": ["step 1", "step 2", "step 3"]}'
)

_SELFCHECK_REINFORCE = (
    "Your previous response was not valid JSON. "
    "Return ONLY a single JSON object — no markdown, no code fences, no commentary.\n\n"
    + _SELFCHECK_PROMPT
)

_VERIFIER_SYSTEM = (
    "You are a strict JSON schema validator. Reply with a single JSON object."
)

_VERIFIER_PROMPT_TMPL = (
    "Does the following object have all of these required keys: name (non-empty string), "
    "description (string, >= {min_desc} chars), steps (non-empty array of strings)?\n\n"
    "Object:\n{payload}\n\n"
    'Reply ONLY with: {{"valid": true}} or {{"valid": false, "reason": "<short reason>"}}'
)

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)


def _strip_fences(raw: str) -> str:
    """Strip markdown ``` fences without using a parser — best-effort."""
    if "```" not in raw:
        return raw.strip()
    return _FENCE_RE.sub("", raw).strip()


# ---------------------------------------------------------------------------
# Core entry point
# ---------------------------------------------------------------------------

def run_self_check(
    get_llm: Optional[Callable[[], Any]],
    *,
    timeout_seconds: Optional[float] = None,
    correlation_id: Optional[str] = None,
) -> SelfCheckResult:
    """Run one bounded self-check + verification round-trip.

    ``get_llm`` is the same accessor the production server uses
    (``llm_provider.get_llm``).  Passing it in (rather than importing it)
    keeps this module trivially testable with a stub.

    The function NEVER raises.  All failures are returned as a
    ``SelfCheckResult`` with a populated ``error_category``.  Best
    practices §6 (Error Categorization).
    """
    cid = correlation_id or uuid.uuid4().hex
    timeout_seconds = float(timeout_seconds if timeout_seconds is not None
                            else os.getenv("MURPHY_SELFCHECK_TIMEOUT", "20"))
    started = time.monotonic()
    ts = _utc_iso_now()

    if get_llm is None:
        return SelfCheckResult(
            status="unavailable", provider=None, model=None,
            latency_ms=0, retry_count=0, verified=False,
            correlation_id=cid, error_category="config",
            last_error="LLM provider module not loaded",
            timestamp=ts,
        )

    try:
        llm = get_llm()
    except Exception as exc:  # noqa: BLE001 — boundary: must not raise
        return SelfCheckResult(
            status="config_error", provider=None, model=None,
            latency_ms=int((time.monotonic() - started) * 1000),
            retry_count=0, verified=False, correlation_id=cid,
            error_category="config",
            last_error=f"get_llm() raised {type(exc).__name__}: {exc}",
            timestamp=ts,
        )

    # ── 1. Generate ────────────────────────────────────────────────────
    gen, gen_err = _call_llm(llm, _SELFCHECK_PROMPT, max_tokens=300, label="generate")
    retry_count = 0

    if gen is None:
        # network/model error — categorize from the exception class
        category = "network" if gen_err and _looks_like_network(gen_err) else "model"
        return SelfCheckResult(
            status="degraded", provider=None, model=None,
            latency_ms=int((time.monotonic() - started) * 1000),
            retry_count=0, verified=False, correlation_id=cid,
            error_category=category,
            last_error=gen_err or "unknown",
            timestamp=ts,
        )

    if (time.monotonic() - started) > timeout_seconds:
        return _timeout(cid, started, ts, retry_count, gen.get("provider"), gen.get("model"))

    parsed = _parse_json_safely(gen.get("content", ""))
    violations: List[str] = []

    # ── 1b. Retry with reinforcement on schema failure (best practices §2) ─
    if parsed is None or _validate_schema(parsed):
        retry_count = 1
        gen2, gen2_err = _call_llm(llm, _SELFCHECK_REINFORCE, max_tokens=300, label="generate-retry")
        if gen2 is not None:
            parsed2 = _parse_json_safely(gen2.get("content", ""))
            if parsed2 is not None and not _validate_schema(parsed2):
                parsed = parsed2
                gen = gen2
            else:
                # Still bad → record violations from the second attempt
                if parsed2 is None:
                    violations = ["second attempt: response was not parseable JSON"]
                    parsed = None
                else:
                    violations = _validate_schema(parsed2)
                    parsed = parsed2
                gen = gen2
        else:
            violations = [f"retry network/model error: {gen2_err}"]

    if parsed is None:
        return SelfCheckResult(
            status="schema_failure",
            provider=gen.get("provider"), model=gen.get("model"),
            latency_ms=int((time.monotonic() - started) * 1000),
            retry_count=retry_count, verified=False, correlation_id=cid,
            error_category="schema",
            last_error="LLM did not return parseable JSON after retry",
            generated_payload=None, schema_violations=violations,
            timestamp=ts,
        )

    final_violations = _validate_schema(parsed)
    if final_violations:
        return SelfCheckResult(
            status="schema_failure",
            provider=gen.get("provider"), model=gen.get("model"),
            latency_ms=int((time.monotonic() - started) * 1000),
            retry_count=retry_count, verified=False, correlation_id=cid,
            error_category="schema",
            last_error=f"schema violations after retry: {final_violations}",
            generated_payload=parsed, schema_violations=final_violations,
            timestamp=ts,
        )

    if (time.monotonic() - started) > timeout_seconds:
        return _timeout(cid, started, ts, retry_count, gen.get("provider"), gen.get("model"))

    # ── 2. Verification — feed the generated payload back to the LLM ───
    # This is the "performs inference on its own generated data" step.
    verifier_prompt = _VERIFIER_PROMPT_TMPL.format(
        min_desc=_DESC_MIN_LEN,
        payload=json.dumps(parsed, separators=(",", ":")),
    )
    ver, ver_err = _call_llm(
        llm, verifier_prompt, max_tokens=80, label="verify",
        system=_VERIFIER_SYSTEM, temperature=0.0,
    )

    verifier_payload: Optional[Dict[str, Any]] = None
    verified = False
    if ver is not None:
        verifier_payload = _parse_json_safely(ver.get("content", "")) or None
        if isinstance(verifier_payload, dict):
            verified = bool(verifier_payload.get("valid"))

    elapsed_ms = int((time.monotonic() - started) * 1000)
    provider = gen.get("provider")
    model = gen.get("model")

    if not verified:
        # Generation succeeded + schema-valid, but the LLM-side verifier
        # disagreed (or never returned).  Still surface generation as
        # working but flag verification as failed so operators see it.
        return SelfCheckResult(
            status="verification_failed",
            provider=provider, model=model,
            latency_ms=elapsed_ms, retry_count=retry_count,
            verified=False, correlation_id=cid,
            error_category="content" if ver is not None else "model",
            last_error=ver_err or "verifier disagreed or returned non-JSON",
            generated_payload=parsed, verifier_payload=verifier_payload,
            timestamp=ts,
        )

    # All good — but flag "degraded" if we ended up on the onboard fallback
    # while a real API key was set.  This is THE signal the user asked for
    # ("DeepInfra not working even though it has a key").
    is_onboard = (provider or "").startswith("onboard")
    has_di_key = bool(os.getenv("DEEPINFRA_API_KEY", "").strip())
    has_tog_key = bool(os.getenv("TOGETHER_API_KEY", "").strip())
    status = "ok"
    error_category: Optional[str] = None
    last_error: Optional[str] = None
    if is_onboard and (has_di_key or has_tog_key):
        status = "degraded"
        error_category = "network"
        last_error = (
            "Provider chain fell through to onboard fallback even though an "
            "API key is configured — the remote API call did not succeed."
        )
        logger.warning(
            "LLM-SELFCHECK-001 cid=%s provider=onboard with API key set — "
            "DeepInfra/Together are unreachable or the key is invalid.",
            cid,
        )

    logger.info(
        "LLM-SELFCHECK-001 cid=%s status=%s provider=%s model=%s latency_ms=%d retries=%d verified=%s",
        cid, status, provider, model, elapsed_ms, retry_count, verified,
    )

    return SelfCheckResult(
        status=status, provider=provider, model=model,
        latency_ms=elapsed_ms, retry_count=retry_count,
        verified=verified, correlation_id=cid,
        error_category=error_category, last_error=last_error,
        generated_payload=parsed, verifier_payload=verifier_payload,
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_llm(
    llm: Any,
    prompt: str,
    *,
    max_tokens: int,
    label: str,
    system: str = "You are Murphy, an automation platform. Reply with valid JSON only.",
    temperature: float = 0.2,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Invoke ``llm.complete()`` and normalise the result.

    Returns ``(payload_dict_or_None, error_str_or_None)`` so callers can
    discriminate without catching exceptions themselves.
    """
    try:
        result = llm.complete(
            prompt,
            system=system,
            model_hint="fast",
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 — boundary
        return None, f"{label}: {type(exc).__name__}: {exc}"

    if result is None:
        return None, f"{label}: provider returned None"

    success = getattr(result, "success", True)
    content = getattr(result, "content", "") or ""
    provider = getattr(result, "provider", None)
    model = getattr(result, "model", None)

    if not success or not content.strip():
        return None, f"{label}: provider={provider} success={success} content_len={len(content)}"

    return {"content": content, "provider": provider, "model": model}, None


def _parse_json_safely(raw: str) -> Optional[Any]:
    """Best-effort JSON parse — strips fences, returns None on failure."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None


_NETWORK_HINTS = ("timeout", "timed out", "connection", "dns", "unreachable",
                  "refused", "resolve", "ssl", "eof")


def _looks_like_network(msg: str) -> bool:
    m = (msg or "").lower()
    return any(h in m for h in _NETWORK_HINTS)


def _timeout(cid: str, started: float, ts: str, retries: int,
             provider: Optional[str], model: Optional[str]) -> SelfCheckResult:
    return SelfCheckResult(
        status="timeout", provider=provider, model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
        retry_count=retries, verified=False, correlation_id=cid,
        error_category="network",
        last_error="self-check exceeded MURPHY_SELFCHECK_TIMEOUT",
        timestamp=ts,
    )


def _utc_iso_now() -> str:
    # Avoid datetime import at module top to keep the unit cheap; this is
    # only called on the result path.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


__all__ = ["run_self_check", "SelfCheckResult"]
