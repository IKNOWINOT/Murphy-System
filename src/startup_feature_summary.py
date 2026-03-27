"""
Startup Feature-Availability Summary (INC-06 / H-01).

Prints a feature-availability summary based on environment variables at
server startup.  Each feature probe checks for the relevant env var
and reports whether the feature is enabled or disabled.

Usage::

    from startup_feature_summary import print_feature_summary
    print_feature_summary()

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature probe definitions
# ---------------------------------------------------------------------------

# Each tuple: (feature_name, env_var_to_check, description)
_FEATURE_PROBES: List[Tuple[str, str, str]] = [
    ("DeepInfra LLM", "DEEPINFRA_API_KEY", "DeepInfra cloud inference"),
    ("Together.ai LLM", "TOGETHER_API_KEY", "Together.ai fallback inference"),
    ("OpenAI LLM", "OPENAI_API_KEY", "OpenAI / compatible provider"),
    ("SendGrid Email", "SENDGRID_API_KEY", "SendGrid email delivery"),
    ("SMTP Email", "SMTP_HOST", "SMTP email relay"),
    ("PostgreSQL", "DATABASE_URL", "PostgreSQL persistence"),
    ("Redis", "REDIS_URL", "Redis cache / task queue"),
    ("Prometheus", "PROMETHEUS_ENABLED", "Metrics export"),
    ("Sentry", "SENTRY_DSN", "Error tracking"),
    ("JWT Auth", "MURPHY_JWT_SECRET", "JWT token authentication"),
    ("Webhook Secret", "WEBHOOK_SECRET", "Webhook signature verification"),
    ("Vector Store", "CHROMADB_PATH", "ChromaDB vector store"),
    ("IoT / Modbus", "MODBUS_HOST", "Industrial IoT sensor bridge"),
    ("Ollama Local", "OLLAMA_HOST", "Ollama local LLM inference"),
]


def get_feature_status() -> Dict[str, Dict[str, str]]:
    """Check all feature probes and return status dict.

    Returns:
        A dict mapping feature names to ``{"status": "enabled"|"disabled",
        "description": "...", "env_var": "..."}``.
    """
    results: Dict[str, Dict[str, str]] = {}
    for name, env_var, description in _FEATURE_PROBES:
        value = os.getenv(env_var)
        status = "enabled" if value else "disabled"
        results[name] = {
            "status": status,
            "description": description,
            "env_var": env_var,
        }
    return results


def print_feature_summary() -> str:
    """Print a feature-availability summary to stdout and return as string.

    This is called at server startup to give operators a quick overview
    of which integrations are active.

    Returns:
        The formatted summary string.
    """
    statuses = get_feature_status()
    enabled = [n for n, s in statuses.items() if s["status"] == "enabled"]
    disabled = [n for n, s in statuses.items() if s["status"] == "disabled"]

    lines = [
        "",
        "┌──────────────────────────────────────────────┐",
        "│  ☠  MURPHY SYSTEM — Feature Availability     │",
        "├──────────────────────────────────────────────┤",
    ]

    max_len = max(len(n) for n in statuses) if statuses else 20

    if enabled:
        for name in enabled:
            info = statuses[name]
            lines.append(f"│  ✅ {name:<{max_len}s} ({info['env_var']})")
    else:
        lines.append("│  (no optional features enabled)")

    if disabled:
        lines.append("├──────────────────────────────────────────────┤")
        for name in disabled:
            info = statuses[name]
            lines.append(f"│  ⬚  {name:<{max_len}s} ({info['env_var']})")

    lines.append("└──────────────────────────────────────────────┘")
    lines.append("")

    summary = "\n".join(lines)
    print(summary)

    logger.info(
        "Feature summary: %d enabled, %d disabled",
        len(enabled),
        len(disabled),
        extra={"enabled": enabled, "disabled": disabled},
    )

    # ── Security posture banner (DEF-019) ───────────────────────────────
    _SECURITY_PROBES = [
        ("API Key Auth", "MURPHY_API_KEY"),
        ("Auth Enabled", "MURPHY_AUTH_ENABLED"),
        ("CORS Origins", "MURPHY_CORS_ORIGINS"),
        ("JWT Secret", "MURPHY_JWT_SECRET"),
    ]
    _env_mode = os.getenv("MURPHY_ENV", "development").lower()
    sec_lines = [
        "",
        "┌──────────────────────────────────────────────┐",
        "│  🔒 MURPHY SYSTEM — Security Posture         │",
        "├──────────────────────────────────────────────┤",
        f"│  Environment: {_env_mode:<31s}│",
        "├──────────────────────────────────────────────┤",
    ]

    _warnings: List[str] = []
    for name, env_var in _SECURITY_PROBES:
        value = os.getenv(env_var)
        if value:
            sec_lines.append(f"│  ✅ {name:<20s} SET")
        else:
            sec_lines.append(f"│  ⬚  {name:<20s} NOT SET")

    if _env_mode in ("production", "staging"):
        if not os.getenv("MURPHY_API_KEY"):
            _warnings.append("API Key Auth NOT configured!")
        if not os.getenv("MURPHY_CORS_ORIGINS") and not os.getenv("MURPHY_ALLOWED_ORIGINS"):
            _warnings.append("CORS origins NOT set!")

    if _warnings:
        sec_lines.append("├──────────────────────────────────────────────┤")
        for w in _warnings:
            sec_lines.append(f"│  ⚠️  {w}")

    sec_lines.append("└──────────────────────────────────────────────┘")
    sec_lines.append("")

    sec_summary = "\n".join(sec_lines)
    print(sec_summary)

    if _warnings:
        for w in _warnings:
            logger.warning("SECURITY: %s", w)

    return summary + "\n" + sec_summary
