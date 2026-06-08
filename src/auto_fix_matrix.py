#!/usr/bin/env python3
"""
auto_fix_matrix.py — PCR-023 / Phase 6b.

Classifies bottleneck flags into AUTO_FIX_SAFE vs HITL_REQUIRED.

This module DOES NOT execute fixes. It only classifies and records a
proposed action. Actual execution happens (a) automatically for
AUTO_FIX_SAFE in a separate, future phase, or (b) by a human approving
a HITL ticket and a runbook applying the fix.

The split:
  AUTO_FIX_SAFE      restart_unit, rollback_last_deploy
                     (touches only internal state, no money, no users)
  HITL_REQUIRED      any code mutation, anything user-facing,
                     anything money-touching, schema change, secret access

Per the founder's directive: when in doubt, HITL.
"""

from __future__ import annotations
from typing import Any

# Action codes — the only ones the matrix is allowed to propose
AUTO_FIX_ACTIONS = {
    "restart_unit",          # systemctl restart a known service unit
    "rollback_last_deploy",  # git reset --hard HEAD~1 (then restart)
}

HITL_ACTIONS = {
    "patch_code",            # write a code change
    "patch_html",            # change a template/page
    "schema_change",         # migrate DB schema
    "credential_rotate",     # touch vault
    "send_message",          # email/SMS to a real human
    "execute_payment",       # any money operation
    "raise_alert",           # ping founder via voice/SMS
    "do_nothing",             # explicit no-op decision (still HITL)
}


def classify(flag: dict[str, Any]) -> dict[str, Any]:
    """Return {classification, proposed_action, reasoning}."""
    kind = (flag.get("kind") or "").lower()
    severity = (flag.get("severity") or "medium").lower()
    target = flag.get("target", "")
    flag_id = flag.get("flag_id", "")

    # Cost spikes — always HITL (could be runaway LLM cost, billing exposure)
    if kind == "cost_spike":
        return {
            "classification": "HITL_REQUIRED",
            "proposed_action": "do_nothing",
            "reasoning": (
                f"Cost spike for action '{target}' could indicate runaway "
                f"LLM usage, billing exposure, or pricing-tier breach. "
                f"Human must decide whether to throttle, refund, or accept."
            ),
        }

    # Error rate — depends on what failed
    if kind == "error_rate":
        # Auth or signup pipelines are user-facing → HITL
        target_low = target.lower()
        if any(s in target_low for s in ("auth", "signup", "verify",
                                         "payment", "billing", "checkout",
                                         "sms", "email", "matrix")):
            return {
                "classification": "HITL_REQUIRED",
                "proposed_action": "patch_code",
                "reasoning": (
                    f"Pipeline '{target}' is user-facing. Any patch must "
                    f"be reviewed by a human before deploy."
                ),
            }
        # Backend-only pipelines with high error rate → can try restart first
        if severity == "high":
            return {
                "classification": "AUTO_FIX_SAFE",
                "proposed_action": "restart_unit",
                "reasoning": (
                    f"Pipeline '{target}' is backend-only and showing "
                    f"high error rate. A unit restart is reversible and "
                    f"often clears transient state. If error rate "
                    f"persists after restart, this re-fires and escalates."
                ),
            }
        # Low-severity backend error → just flag, no action yet
        return {
            "classification": "HITL_REQUIRED",
            "proposed_action": "do_nothing",
            "reasoning": (
                f"Pipeline '{target}' is showing elevated but not "
                f"critical error rate. Suggest investigation before any "
                f"action."
            ),
        }

    # ROUTE_500 flags (when 6b's verify-email-style detector fires)
    if flag_id.startswith("ROUTE_500_"):
        return {
            "classification": "HITL_REQUIRED",
            "proposed_action": "patch_code",
            "reasoning": (
                "An HTTP route is returning 500. A code change is required. "
                "All code changes are HITL by policy."
            ),
        }

    # Default: HITL
    return {
        "classification": "HITL_REQUIRED",
        "proposed_action": "do_nothing",
        "reasoning": (
            f"Unrecognized flag kind '{kind}'. Default policy: HITL."
        ),
    }


def classify_all(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for f in flags:
        decision = classify(f)
        out.append({**f, "matrix_decision": decision})
    return out


if __name__ == "__main__":
    # Self-test
    test_flags = [
        {"flag_id": "HIGH_ERROR_auth", "kind": "error_rate", "target": "auth",
         "severity": "high"},
        {"flag_id": "HIGH_ERROR_scheduler", "kind": "error_rate",
         "target": "scheduler_worker", "severity": "high"},
        {"flag_id": "COST_SPIKE_llm_call", "kind": "cost_spike",
         "target": "llm_call", "severity": "high"},
        {"flag_id": "ROUTE_500_/api/auth/verify-email", "kind": "route_500",
         "target": "/api/auth/verify-email", "severity": "high"},
    ]
    for f in test_flags:
        d = classify(f)
        print(f"{f['flag_id']:50s} → {d['classification']:15s} action={d['proposed_action']}")
