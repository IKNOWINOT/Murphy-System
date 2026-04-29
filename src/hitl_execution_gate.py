# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
HITL Execution Gate — Murphy System

Wraps any execution step with a mandatory human-approval check **only when a
superior external-API model is being used**.  When the system is running on its
onboard/local models (LocalLLMFallback, Phi-2, Local-Medium, Ollama) no human
confirmation is required — the system executes automatically.

Design principle
────────────────
  - Onboard model  → auto-proceed  (HITL not required)
  - External API   → ask user first (HITL required by default, unless policy
                     says the confidence + risk profile is safe enough to skip)

This gives the best UX: the system is always responsive and always functional,
but a human is in the loop whenever a superior (paid/remote) model is about to
do something on their behalf.

Usage::

    gate = HITLExecutionGate(hitl_controller, policy_id="default")
    result = gate.gate_execution(
        step_description="Deploy microservice to production",
        confidence=0.92,
        risk_level=0.65,
        model_name="deepinfra_70b",       # triggers HITL
        execute_fn=my_deploy_fn,
        arg1, arg2,
    )

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Model names / providers that are considered "superior external API" models.
# When any of these is active, HITL approval is requested before execution.
_EXTERNAL_API_MODELS: Set[str] = {
    "deepinfra_70b",
    "deepinfra_llama",
    "deepinfra_fast",
    "deepinfra",
    "openai",
    "anthropic",
    "gpt",
    "claude",
    "gemini",
    "mfm",                  # Murphy Foundation Model in production mode
    "external_api",
}

# Onboard/local models — always auto-proceed without HITL
_ONBOARD_MODELS: Set[str] = {
    "local_small",
    "local_medium",
    "local_fallback",
    "onboard",
    "onboard_fallback",
    "ollama",
    "phi-2",
    "phi3",
    "phi",
    "llama3",        # local Ollama
    "mistral",       # local Ollama
}

_APPROVAL_BANNER = """\
╔══════════════════════════════════════════════════════╗
║  ✋  HITL APPROVAL REQUIRED                         ║
║  Step       : {description:<38} ║
║  Risk       : {risk:<38} ║
║  Cost est.  : {cost:<38} ║
║  Confidence : {confidence:<38} ║
║  Model      : {model:<38} ║
╚══════════════════════════════════════════════════════╝
  Proceed? [y/N]: """


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_external_api_model(model_name: str) -> bool:
    """Return True when *model_name* maps to a superior external-API provider.

    The check is case-insensitive and uses prefix/substring matching so that
    model identifiers like ``"deepinfra_meta-llama/Meta-Llama-3.1-70B-Instruct"`` still resolve correctly.
    """
    name = (model_name or "").lower().strip()
    if not name:
        return False
    # Exact membership first
    if name in _EXTERNAL_API_MODELS:
        return True
    # Substring / prefix check
    for ext in _EXTERNAL_API_MODELS:
        if name.startswith(ext) or ext in name:
            return True
    return False


def is_onboard_model(model_name: str) -> bool:
    """Return True when *model_name* maps to an onboard/local model."""
    return not is_external_api_model(model_name)


# ---------------------------------------------------------------------------
# HITLExecutionGate
# ---------------------------------------------------------------------------

class HITLExecutionGate:
    """Wraps execution steps with a conditional human-approval gate.

    Rules
    ─────
    1. **Onboard model** → auto-proceed, no prompt shown.
    2. **External API model + HITLAutonomyController says autonomous=True**
       (high confidence, low risk within policy) → auto-proceed.
    3. **External API model + requires_hitl=True** → show approval banner and
       block until the user types ``y`` / ``yes``.  Any other input skips the
       step with ``status="skipped_by_user"``.

    Thread safety: the approval prompt is protected by a threading.Lock so
    concurrent swarm threads queue up rather than interleaving console output.
    """

    def __init__(
        self,
        hitl_controller: Optional[Any] = None,
        policy_id: str = "default",
        *,
        auto_approve_onboard: bool = True,
        interactive: bool = True,
    ) -> None:
        """
        Args:
            hitl_controller:    Optional ``HITLAutonomyController`` instance.
                                When None, external-API steps always require
                                human approval (conservative default).
            policy_id:          Policy ID to pass to HITLAutonomyController.
            auto_approve_onboard: When True (default), onboard-model steps
                                  never ask for approval.
            interactive:        When False, approval is assumed granted (useful
                                 for automated tests / CI pipelines).
        """
        import threading
        self._hitl = hitl_controller
        self._policy_id = policy_id
        self._auto_approve_onboard = auto_approve_onboard
        self._interactive = interactive
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def gate_execution(
        self,
        step_description: str,
        confidence: float,
        risk_level: float,
        execute_fn: Callable,
        *args: Any,
        model_name: str = "onboard",
        estimated_cost: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluate the gate and optionally execute *execute_fn*.

        Args:
            step_description: Human-readable description of the step.
            confidence:       Model confidence score (0.0–1.0).
            risk_level:       Risk assessment (0.0 = safe, 1.0 = high risk).
            execute_fn:       Callable to invoke if approved.
            *args / **kwargs: Forwarded to *execute_fn*.
            model_name:       Name of the LLM model driving this step.
            estimated_cost:   Estimated API cost in USD.

        Returns:
            Dict with ``status`` (``"executed"`` | ``"skipped_by_user"`` |
            ``"auto_approved"``), ``result``, and ``gate_decision`` keys.
        """
        # 1. Onboard models always auto-proceed
        if self._auto_approve_onboard and is_onboard_model(model_name):
            result = _safe_call(execute_fn, *args, **kwargs)
            return {"status": "auto_approved", "reason": "onboard_model", "result": result}

        # 2. Consult HITLAutonomyController for external-API models
        if self._hitl is not None:
            try:
                decision = self._hitl.evaluate_autonomy(
                    task_type=step_description[:50],
                    confidence=confidence,
                    risk_level=risk_level,
                    policy_id=self._policy_id,
                )
                if decision.get("autonomous") and not decision.get("requires_hitl"):
                    result = _safe_call(execute_fn, *args, **kwargs)
                    return {
                        "status": "auto_approved",
                        "reason": decision.get("reason", "policy_approved"),
                        "result": result,
                    }
            except Exception as exc:
                logger.debug("HITLAutonomyController.evaluate_autonomy failed: %s", exc)

        # 3. Show approval banner and block for user input
        if not self._interactive:
            # Non-interactive mode (CI/tests) — auto-approve all
            result = _safe_call(execute_fn, *args, **kwargs)
            return {"status": "auto_approved", "reason": "non_interactive_mode", "result": result}

        with self._lock:
            banner = _APPROVAL_BANNER.format(
                description=step_description[:38],
                risk=f"{risk_level:.0%}",
                cost=f"${estimated_cost:.4f}",
                confidence=f"{confidence:.0%}",
                model=model_name[:38],
            )
            try:
                # PATCH-153: Notify via Matrix before blocking for input
                if _matrix_hitl_alert:
                    try:
                        _matrix_hitl_alert(
                            title=step_description[:80],
                            details=(
                                f"Risk: {risk_level:.0%}  Confidence: {confidence:.0%}\n"
                                f"Model: {model_name}\n"
                                f"Cost: ${estimated_cost:.4f}\n"
                                "Awaiting human approval on server console."
                            ),
                            severity="warn"
                        )
                    except Exception as _me:
                        logger.debug("Matrix HITL notify failed: %s", _me)
                answer = input(banner).strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"

        if answer in ("y", "yes"):
            result = _safe_call(execute_fn, *args, **kwargs)
            return {"status": "executed", "reason": "user_approved", "result": result}

        logger.info("HITL gate: step '%s' skipped by user", step_description)
        return {
            "status": "skipped_by_user",
            "reason": "user_declined",
            "result": None,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_call(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    """Call *fn* and return its result; propagate exceptions to the caller."""
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Re-export type hint used inside gate_execution
# ---------------------------------------------------------------------------
from typing import Dict  # noqa: E402  (needed for return annotation above)

# PATCH-153: Matrix HITL notifications
try:
    from matrix_client import send_hitl_alert as _matrix_hitl_alert
except ImportError:
    _matrix_hitl_alert = None


__all__ = [
    "HITLExecutionGate",
    "is_external_api_model",
    "is_onboard_model",
]
