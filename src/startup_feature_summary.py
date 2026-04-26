"""
PATCH-093c — Shield Wall
Murphy System 1.0 — Boot Integrity Protocol

"What can go wrong, will go wrong." — Murphy's Law

This is the north star of murphy.systems.
Our vow: shield humanity from every failure AI can cause
by anticipating it, naming it, and standing in front of it.

Shield Wall replaces the old startup feature summary.
It names every protection layer explicitly — you should always
know what is standing between the system and harm.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NORTH STAR
# ---------------------------------------------------------------------------

NORTH_STAR = (
    "Murphy's Law is not a joke. It is a vow.\n"
    "Everything that can go wrong will go wrong — unless something stands in the way.\n"
    "Murphy System is that something.\n"
    "Every module, every gate, every check exists to shield humanity\n"
    "from the failures that AI will inevitably face.\n"
    "We do not prevent failure by hoping for the best.\n"
    "We prevent it by naming every way it can happen\n"
    "and building a wall in front of each one."
)

# ---------------------------------------------------------------------------
# SHIELD LAYERS — named protection functions, in order of activation
# ---------------------------------------------------------------------------
# Each tuple: (layer_name, shield_function, what_it_blocks, env_var_or_None)

SHIELD_LAYERS: List[Tuple[str, str, str, str | None]] = [
    (
        "OIDCAuthMiddleware",
        "auth_middleware.OIDCAuthMiddleware.dispatch()",
        "Unauthenticated access — every request checked before routing",
        "MURPHY_JWT_SECRET",
    ),
    (
        "SecurityHeadersMiddleware",
        "auth_middleware.SecurityHeadersMiddleware.dispatch()",
        "XSS, clickjacking, MIME sniffing — injected on every response",
        None,
    ),
    (
        "HoneypotMiddleware",
        "honeypot_middleware — 37 traps",
        "Scanners, bots, recon — passive fingerprint + suspicion score",
        None,
    ),
    (
        "AntiSurveillanceEngine",
        "security_plane.anti_surveillance — opacity injection",
        "Metadata leakage, timing attacks, side-channel exfiltration",
        None,
    ),
    (
        "RSC StabilityGate",
        "rsc_unified_sink.enforce() + check_gate()",
        "Unstable AI dispatch — S(t) scalar blocks action when system unsettled",
        None,
    ),
    (
        "HITLExecutionGate",
        "hitl_execution_gate.HITLExecutionGate",
        "Autonomous action beyond confidence threshold — routes to human",
        None,
    ),
    (
        "CausalitySandbox",
        "causality_sandbox.CausalitySandboxEngine._simulate_action()",
        "Harmful side effects — every action simulated before execution",
        None,
    ),
    (
        "DeepInfra LLM",
        "llm_provider.MurphyLLMProvider._complete_with_fallback()",
        "AI blindness — primary inference with Together.ai fallback",
        "DEEPINFRA_API_KEY",
    ),
    (
        "MoralFiberScorer",
        "character_network_engine.MoralFiberScore",
        "Value drift — 8-pillar character assessment on every agent action",
        None,
    ),
    (
        "CredentialVault",
        "credential_vault — Fernet + HMAC + rotation tracking",
        "Key exposure — encrypted at rest, SHA-256 hash verification",
        None,
    ),
    (
        "SendGrid Email",
        "murphy_mail — authenticated delivery",
        "Unauthenticated outbound comms",
        "SENDGRID_API_KEY",
    ),
    (
        "JWT Auth",
        "auth_middleware — token validation",
        "Session forgery",
        "MURPHY_JWT_SECRET",
    ),
    (
        "ModelTeam",
        "model_team.MurphyReferee.deliberate() — 4 models under RoE",
        "Single-model blind spots — Triage, Analyst, Specialist, Sentinel",
        "DEEPINFRA_API_KEY",
    ),
]

# ---------------------------------------------------------------------------
# SHIELD WALL BOOT PROTOCOL
# ---------------------------------------------------------------------------

def raise_shield_wall() -> str:
    """
    PATCH-093c: Shield Wall boot protocol.

    Prints the named protection layers at startup so operators always know
    what is standing between the system and harm.

    Called instead of the old print_feature_summary() at boot.
    Returns the formatted banner string.
    """
    lines = []

    lines += [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║          ⚔  MURPHY SYSTEM — SHIELD WALL RAISED  ⚔           ║",
        "║                                                              ║",
        "║  Murphy's Law: What can go wrong, will go wrong.            ║",
        "║  Our vow: stand in front of every failure before it lands.  ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║  PROTECTION LAYERS — named, active, commissioned:           ║",
        "╠══════════════════════════════════════════════════════════════╣",
    ]

    active = []
    dormant = []

    for layer_name, shield_fn, blocks, env_var in SHIELD_LAYERS:
        # Layer is active if no env_var required, or if env_var is set
        is_active = (env_var is None) or bool(os.getenv(env_var))
        entry = (layer_name, shield_fn, blocks, env_var, is_active)
        if is_active:
            active.append(entry)
        else:
            dormant.append(entry)

    for layer_name, shield_fn, blocks, env_var, _ in active:
        lines.append(f"║  ⚔  {layer_name:<24s} ACTIVE                        ║")
        lines.append(f"║     fn: {shield_fn[:52]:<52s}  ║")
        lines.append(f"║     blocks: {blocks[:48]:<48s}  ║")
        lines.append( "║                                                              ║")

    if dormant:
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║  DORMANT (env var not set):                                  ║")
        for layer_name, shield_fn, blocks, env_var, _ in dormant:
            lines.append(f"║  ○  {layer_name:<24s} needs: {(env_var or ''):<22s}  ║")

    lines += [
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  ACTIVE: {len(active):<2d}  DORMANT: {len(dormant):<2d}                                   ║",
        "╠══════════════════════════════════════════════════════════════╣",
        "║  NORTH STAR:                                                 ║",
        "║  Shield humanity from AI failure by anticipating it,        ║",
        "║  naming every way it can happen, and standing in front.     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
    ]

    banner = "\n".join(lines)
    print(banner)
    logger.info(
        "Shield Wall raised: %d layers active, %d dormant",
        len(active), len(dormant),
        extra={"active_layers": [e[0] for e in active], "dormant_layers": [e[0] for e in dormant]},
    )
    return banner


# ---------------------------------------------------------------------------
# BACKWARD COMPAT — old name still works
# ---------------------------------------------------------------------------

def get_feature_status() -> Dict[str, Dict[str, str]]:
    """Legacy compat: returns status dict keyed by layer name."""
    return {
        layer_name: {
            "status": "enabled" if (env_var is None or os.getenv(env_var)) else "disabled",
            "description": blocks,
            "env_var": env_var or "",
            "shield_function": shield_fn,
        }
        for layer_name, shield_fn, blocks, env_var in SHIELD_LAYERS
    }


def print_feature_summary() -> str:
    """Legacy entry point — now raises the Shield Wall."""
    return raise_shield_wall()
