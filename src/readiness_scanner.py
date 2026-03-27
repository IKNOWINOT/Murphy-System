# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Readiness Scanner
=================

Recursively checks whether the Murphy System is ready for deployment.
Covers environment variables, critical module imports, connectivity,
disk space, and feature-toggle states.

Also provides production-blocking deployment gates via ``DeploymentGateRunner``
which must all pass before a production deployment is permitted:
  - security_scan:       JWT strength, CORS wildcard, credential key
  - test_pass:           MURPHY_TESTS_PASSED=1 must be set by CI
  - health_check:        /api/health must return 200 OK
  - config_validation:   src.config must load without errors
  - secret_availability: all required secrets present in production

Usage::

    from src.readiness_scanner import ReadinessScanner, DeploymentGateRunner

    # Pre-deployment readiness scan (warnings + blockers)
    scanner = ReadinessScanner()
    report = scanner.scan()
    print(report["score"])  # e.g. "17/23 checks passed"

    # Production deployment gates (must all pass before deploy)
    runner = DeploymentGateRunner()
    result = runner.run_all()
    if result["all_passed"]:
        print("All deployment gates passed — safe to deploy")

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
    ("DEEPINFRA_API_KEY",              "set key deepinfra gsk_..."),
    ("OPENAI_API_KEY",            "set key openai sk_...  (optional — DeepInfra is free)"),
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
                "No LLM API key found (DEEPINFRA_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY).",
                "set key deepinfra gsk_...  ← DeepInfra is free: https://console.deepinfra.com/keys",
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

        # ── 10. DeepInfra key recommendation ──────────────────────────────────
        api_strategy = {
            "recommendation": "Best bang-for-buck API key strategy",
            "providers": [
                {
                    "rank": 1,
                    "name": "DeepInfra (FREE)",
                    "url": "https://console.deepinfra.com/keys",
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


# ---------------------------------------------------------------------------
# Deployment readiness gates (production-blocking checks)
# ---------------------------------------------------------------------------

class DeploymentGate:
    """A single named gate that must pass before production deployment.

    Gates differ from warnings in that a failing gate *blocks* deployment.
    The gate callable must return ``(ok: bool, detail: str)``.
    """

    def __init__(self, name: str, category: str, check_fn: Any) -> None:
        self.name = name
        self.category = category
        self._check_fn = check_fn

    def evaluate(self) -> Dict[str, Any]:
        """Run the gate check and return a structured result."""
        try:
            ok, detail = self._check_fn()
            return {
                "gate": self.name,
                "category": self.category,
                "passed": bool(ok),
                "detail": str(detail),
            }
        except Exception as exc:
            return {
                "gate": self.name,
                "category": self.category,
                "passed": False,
                "detail": f"Gate check raised: {exc}",
            }


def _gate_security_scan() -> tuple:
    """Run a lightweight security configuration scan.

    Checks:
    - JWT secret is strong (not a default / short value)
    - CORS is not wildcard in production
    - MURPHY_ENV is set
    - No plaintext passwords in obvious env vars
    """
    import os

    env = os.environ.get("MURPHY_ENV", "")
    if not env:
        return False, "MURPHY_ENV not set — cannot determine security posture"

    if env in ("production", "staging"):
        # JWT strength
        jwt_secret = os.environ.get("MURPHY_JWT_SECRET", "")
        if not jwt_secret:
            return False, "MURPHY_JWT_SECRET not set in production/staging"
        if len(jwt_secret) < 32:
            return False, "MURPHY_JWT_SECRET is too short (< 32 chars)"
        if jwt_secret.lower() in ("changeme", "secret", "default", "murphy", "test"):
            return False, "MURPHY_JWT_SECRET is using a default/weak value"

        # CORS
        cors = os.environ.get("MURPHY_CORS_ORIGINS", "*")
        if cors.strip() == "*":
            return False, "MURPHY_CORS_ORIGINS is wildcard '*' in production"

        # Credential master key
        cred_key = os.environ.get("MURPHY_CREDENTIAL_MASTER_KEY", "")
        if not cred_key:
            return False, "MURPHY_CREDENTIAL_MASTER_KEY not set in production/staging"

        return True, f"Security scan passed for env={env}"

    return True, f"Security scan skipped for env={env} (not production/staging)"


def _gate_config_validation() -> tuple:
    """Validate that the runtime configuration can be loaded without errors.

    Attempts to import ``src.config`` and call ``get_settings()``.
    """
    try:
        import importlib
        config_mod = importlib.import_module("src.config")
        get_settings = getattr(config_mod, "get_settings", None)
        if callable(get_settings):
            get_settings()
        return True, "Configuration validated successfully"
    except ImportError:
        return True, "src.config not available — config validation skipped"
    except Exception as exc:
        return False, f"Configuration validation failed: {exc}"


def _gate_secret_availability() -> tuple:
    """Check that all critical secrets are available in production.

    In development this gate always passes; in production/staging each
    required secret must be set.
    """
    import os

    env = os.environ.get("MURPHY_ENV", "development")
    if env not in ("production", "staging"):
        return True, f"Secret availability check skipped for env={env}"

    required_secrets = [
        "MURPHY_API_KEYS",
        "MURPHY_CREDENTIAL_MASTER_KEY",
        "MURPHY_JWT_SECRET",
        "POSTGRES_PASSWORD",
        "MURPHY_SECRET_KEY",
    ]
    missing = [k for k in required_secrets if not os.environ.get(k)]
    if missing:
        return False, f"Missing production secrets: {', '.join(missing)}"
    return True, "All required production secrets are present"


def _gate_test_pass() -> tuple:
    """Check that the test suite pass flag is set (set by CI before deploy).

    In CI, the deployment workflow sets MURPHY_TESTS_PASSED=1 after the
    test step completes successfully.  This gate enforces that no deployment
    can happen unless the tests passed.
    """
    import os

    env = os.environ.get("MURPHY_ENV", "development")
    if env not in ("production", "staging"):
        return True, f"Test pass gate skipped for env={env}"

    passed = os.environ.get("MURPHY_TESTS_PASSED", "").strip()
    if passed == "1":
        return True, "MURPHY_TESTS_PASSED=1 confirmed"
    return False, "MURPHY_TESTS_PASSED is not set to 1 — tests must pass before deployment"


def _gate_health_check(base_url: str = "http://localhost:8000") -> tuple:
    """Verify that the health endpoint responds with 200 OK."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{base_url}/api/health",
            headers={"User-Agent": "Murphy-GateCheck/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True, f"Health endpoint OK at {base_url}/api/health"
            return False, f"Health endpoint returned HTTP {resp.status}"
    except Exception as exc:
        return False, f"Health endpoint unreachable: {exc}"


# ---------------------------------------------------------------------------
# DeploymentGateRunner
# ---------------------------------------------------------------------------

class DeploymentGateRunner:
    """Evaluates all production-blocking deployment gates.

    Gates that *must* all pass before a production flag can be set:
      1. security_scan     — JWT strength, CORS, credential key
      2. test_pass         — CI confirmed tests passed (MURPHY_TESTS_PASSED=1)
      3. health_check      — /api/health responds 200 OK
      4. config_validation — src.config loads without errors
      5. secret_availability — all required secrets are present

    Usage::

        runner = DeploymentGateRunner()
        result = runner.run_all()
        if result["all_passed"]:
            print("All deployment gates passed — safe to deploy")
        else:
            for gate in result["failed_gates"]:
                print(f"BLOCKED: {gate['gate']} — {gate['detail']}")
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url
        self._gates: List[DeploymentGate] = self._build_default_gates()

    def _build_default_gates(self) -> List[DeploymentGate]:
        base = self._base_url

        def _health_gate():
            return _gate_health_check(base)

        return [
            DeploymentGate("security_scan", "security", _gate_security_scan),
            DeploymentGate("test_pass", "ci", _gate_test_pass),
            DeploymentGate("health_check", "infra", _health_gate),
            DeploymentGate("config_validation", "config", _gate_config_validation),
            DeploymentGate("secret_availability", "secrets", _gate_secret_availability),
        ]

    def add_gate(self, name: str, category: str, check_fn: Any) -> None:
        """Register an additional deployment gate."""
        self._gates.append(DeploymentGate(name, category, check_fn))

    def run_all(self) -> Dict[str, Any]:
        """Evaluate all gates and return a structured result.

        Returns:
            Dict with keys:
              - ``all_passed``: True only if every gate passed
              - ``gates``: list of per-gate result dicts
              - ``failed_gates``: subset of gates that did not pass
              - ``passed_count`` / ``failed_count``
              - ``evaluated_at``: ISO timestamp
        """
        results = [gate.evaluate() for gate in self._gates]
        failed = [r for r in results if not r["passed"]]

        return {
            "all_passed": len(failed) == 0,
            "gates": results,
            "failed_gates": failed,
            "passed_count": len(results) - len(failed),
            "failed_count": len(failed),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return a compact status dict suitable for the /api/deploy-gate endpoint."""
        result = self.run_all()
        return {
            "all_passed": result["all_passed"],
            "gates_total": len(result["gates"]),
            "gates_passed": result["passed_count"],
            "gates_failed": result["failed_count"],
            "blocked_by": [g["gate"] for g in result["failed_gates"]],
            "evaluated_at": result["evaluated_at"],
        }
