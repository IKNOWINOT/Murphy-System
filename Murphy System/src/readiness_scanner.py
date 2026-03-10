# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Readiness Scanner
=================

Recursively checks whether the Murphy System is ready for deployment.
Covers environment variables, critical module imports, connectivity,
disk space, and feature-toggle states.

Usage::

    from src.readiness_scanner import ReadinessScanner

    scanner = ReadinessScanner()
    report = scanner.scan()
    print(report["score"])  # e.g. "17/23 checks passed"

The scanner is designed to be non-fatal — every check is wrapped in a
try/except so a broken subsystem doesn't prevent the report from being
generated.
"""

import importlib
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Check constants
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS: List[Tuple[str, str]] = [
    ("GROQ_API_KEY",              "set key groq gsk_..."),
    ("OPENAI_API_KEY",            "set key openai sk_...  (optional — Groq is free)"),
    ("ANTHROPIC_API_KEY",         "set key anthropic sk_... (optional)"),
]

_OPTIONAL_OAUTH_ENV_VARS: List[str] = [
    "MURPHY_OAUTH_GOOGLE_CLIENT_ID",
    "MURPHY_OAUTH_MICROSOFT_CLIENT_ID",
    "MURPHY_OAUTH_META_CLIENT_ID",
]

# Murphy System's 56 src packages to try-import
_CRITICAL_PACKAGES: List[str] = [
    "src.config",
    "src.test_mode_controller",
    "src.self_learning_toggle",
    "src.readiness_scanner",
    "src.account_management",
    "src.learning_engine",
    "src.murphy_foundation_model",
    "src.auar",
]

_DISK_WARN_BYTES = 1 * 1024 * 1024 * 1024    # 1 GB
_DISK_CRITICAL_BYTES = 100 * 1024 * 1024      # 100 MB


class ReadinessScanner:
    """
    Runs a suite of readiness checks and returns a structured report.
    """

    def scan(self, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
        """
        Execute all checks and return a structured readiness report.

        Parameters
        ----------
        base_url:
            The base URL of the running Murphy System API.  Used for
            connectivity checks.  Set to None to skip HTTP checks.
        """
        passed: List[str] = []
        blockers: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        def _pass(name: str) -> None:
            passed.append(name)

        def _block(check: str, detail: str, fix: str = "") -> None:
            entry: Dict[str, Any] = {"check": check, "status": "MISSING", "detail": detail}
            if fix:
                entry["fix"] = fix
            blockers.append(entry)

        def _warn(check: str, detail: str) -> None:
            warnings.append({"check": check, "status": "WARNING", "detail": detail})

        # ── 1. Environment variables ─────────────────────────────────────
        has_any_llm_key = False
        for env_var, fix in _REQUIRED_ENV_VARS:
            if os.environ.get(env_var, "").strip():
                _pass(env_var.lower())
                has_any_llm_key = True
            else:
                _warn(env_var.lower(), f"{env_var} is not set")

        if not has_any_llm_key:
            _block(
                "llm_api_key",
                "No LLM API key found (GROQ_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY).",
                "set key groq gsk_...  ← Groq is free: https://console.groq.com/keys",
            )
        else:
            _pass("llm_api_key_present")

        # ── 2. OAuth env vars (optional, warn only) ──────────────────────
        oauth_configured = all(
            os.environ.get(v, "").strip() for v in _OPTIONAL_OAUTH_ENV_VARS
        )
        if oauth_configured:
            _pass("oauth_env_vars")
        else:
            missing_oauth = [v for v in _OPTIONAL_OAUTH_ENV_VARS if not os.environ.get(v, "").strip()]
            _warn(
                "oauth_env_vars",
                f"OAuth not fully configured: {', '.join(missing_oauth)}. "
                "Account signup via OAuth will not work until these are set.",
            )

        # ── 3. Critical module imports ───────────────────────────────────
        for pkg in _CRITICAL_PACKAGES:
            try:
                importlib.import_module(pkg)
                _pass(f"import:{pkg}")
            except ImportError as exc:
                _warn(f"import:{pkg}", f"ImportError — {exc}")
            except Exception as exc:
                _warn(f"import:{pkg}", f"{type(exc).__name__} — {exc}")

        # ── 4. Test mode controller ──────────────────────────────────────
        try:
            from src.test_mode_controller import get_test_mode_controller
            ctrl = get_test_mode_controller()
            status = ctrl.get_status()
            _pass("test_mode_controller")
            if status.get("active"):
                _warn(
                    "test_mode_active",
                    f"Test mode is active — {status['calls_used']}/{status['max_calls']} calls used.",
                )
        except Exception as exc:
            _warn("test_mode_controller", f"Could not load: {exc}")

        # ── 5. Self-learning toggle ──────────────────────────────────────
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            sl_status = slt.get_status()
            _pass("self_learning_toggle")
            skipped = sl_status.get("skipped_operations", 0)
            if not sl_status.get("self_learning_enabled"):
                _warn(
                    "self_learning_disabled",
                    f"Self-learning is OFF — {skipped:,} operations skipped (disk writes avoided). "
                    "Enable with /toggle self-learning when storage is available.",
                )
        except Exception as exc:
            _warn("self_learning_toggle", f"Could not load: {exc}")

        # ── 6. Account management ────────────────────────────────────────
        try:
            from src.account_management import OAuthProviderRegistry
            registry = OAuthProviderRegistry()
            am_status = registry.get_status()
            configured = am_status.get("configured_providers", 0)
            if configured > 0:
                _pass("account_management_oauth")
            else:
                _warn(
                    "account_management_oauth",
                    f"Account management loaded but only {configured} OAuth provider(s) configured. "
                    "Set MURPHY_OAUTH_*_CLIENT_ID env vars to enable OAuth signup.",
                )
        except Exception as exc:
            _warn("account_management", f"Could not load: {exc}")

        # ── 7. Config loads without error ────────────────────────────────
        try:
            from src.config import get_settings
            cfg = get_settings()
            _pass("config_loads")
        except Exception as exc:
            _block("config_loads", f"src/config.py error: {exc}")

        # ── 8. Disk space ────────────────────────────────────────────────
        try:
            stat = shutil.disk_usage("/")
            free = stat.free
            if free < _DISK_CRITICAL_BYTES:
                _block(
                    "disk_space",
                    f"CRITICAL: only {free // (1024*1024)}MB free. "
                    "Self-learning and checkpointing will fail.",
                )
            elif free < _DISK_WARN_BYTES:
                _warn(
                    "disk_space",
                    f"Only {free // (1024*1024)}MB free. "
                    "Keep self-learning disabled to avoid filling disk.",
                )
            else:
                _pass("disk_space")
        except Exception as exc:
            _warn("disk_space", f"Could not check: {exc}")

        # ── 9. HTTP health check (non-blocking) ──────────────────────────
        if base_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{base_url}/api/health",
                    headers={"User-Agent": "Murphy-ReadinessScanner/1.0"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        _pass("health_endpoint")
                    else:
                        _warn("health_endpoint", f"Returned HTTP {resp.status}")
            except Exception:
                _warn(
                    "health_endpoint",
                    f"Could not reach {base_url}/api/health — is the server running?",
                )

        # ── 10. Groq key recommendation ──────────────────────────────────
        api_strategy = {
            "recommendation": "Best bang-for-buck API key strategy",
            "providers": [
                {
                    "rank": 1,
                    "name": "Groq (FREE)",
                    "url": "https://console.groq.com/keys",
                    "models": "Llama 3, Mixtral",
                    "note": (
                        "Best first choice. Free tier with generous rate limits, fast inference. "
                        "Register 2-3 keys for round-robin rotation (use_key_rotation=true)."
                    ),
                },
                {
                    "rank": 2,
                    "name": "OpenAI (Pay-as-you-go)",
                    "url": "https://platform.openai.com/api-keys",
                    "models": "GPT-4o-mini (very cheap)",
                    "note": "$5 minimum credit.",
                },
                {
                    "rank": 3,
                    "name": "Anthropic (Pay-as-you-go)",
                    "url": "https://console.anthropic.com/",
                    "models": "Claude 3 Haiku (cheap)",
                    "note": "$5 minimum credit.",
                },
            ],
        }

        # ── Summary ──────────────────────────────────────────────────────
        total = len(passed) + len(blockers) + len(warnings)
        ready = len(blockers) == 0
        score = f"{len(passed)}/{total} checks passed"

        return {
            "ready": ready,
            "score": score,
            "passed": passed,
            "blockers": blockers,
            "warnings": warnings,
            "api_key_strategy": api_strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def run_readiness_scan(base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Run a readiness scan and return the report dict."""
    return ReadinessScanner().scan(base_url=base_url)
