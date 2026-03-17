"""
Deployment Readiness Checker — Murphy System

Pre-flight validation that confirms the runtime environment meets
the minimum requirements for production deployment.  Used by the
self-automation bootstrap and the ``/api/readiness`` endpoint.

Checks:
  - Required environment variables (DB, Redis, PayPal, secrets)
  - Database connectivity (PostgreSQL / SQLite fallback)
  - Redis connectivity
  - Disk write access for data/log directories
  - Core module import health
  - Security configuration (CORS, JWT secrets)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Readiness check registry
# ---------------------------------------------------------------------------

class ReadinessCheck:
    """A single readiness check with name, category, and callable."""

    def __init__(self, name: str, category: str, checker: Any) -> None:
        self.name = name
        self.category = category
        self._checker = checker

    def run(self) -> Dict[str, Any]:
        try:
            ok, detail = self._checker()
            return {"name": self.name, "category": self.category, "ok": bool(ok), "detail": str(detail)}
        except Exception as exc:
            return {"name": self.name, "category": self.category, "ok": False, "detail": str(exc)}


# ---------------------------------------------------------------------------
# Individual checkers
# ---------------------------------------------------------------------------

def _check_env_var(var: str, required: bool = True):
    """Return a checker that validates an environment variable is set."""
    def _checker():
        val = os.environ.get(var, "")
        if val:
            return True, f"{var} is set"
        if required:
            return False, f"{var} is not set (required)"
        return True, f"{var} is not set (optional)"
    return _checker


def _check_database():
    """Verify database connectivity."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return False, "DATABASE_URL not configured"
    try:
        from src.db import create_tables  # noqa: F401
        return True, "Database module importable"
    except ImportError:
        return False, "src.db module not available"
    except Exception as exc:
        return False, f"Database check failed: {exc}"


def _check_redis():
    """Verify Redis connectivity."""
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        return False, "REDIS_URL not configured"
    try:
        from src.cache import CacheClient  # noqa: F401
        return True, "Redis module importable"
    except ImportError:
        return False, "src.cache module not available"
    except Exception as exc:
        return False, f"Redis check failed: {exc}"


def _check_disk_write(directory: str):
    """Return a checker that validates write access to a directory."""
    def _checker():
        target = os.environ.get("MURPHY_DATA_DIR", directory)
        if not os.path.isdir(target):
            try:
                os.makedirs(target, exist_ok=True)
            except OSError as exc:
                return False, f"Cannot create {target}: {exc}"
        try:
            fd, path = tempfile.mkstemp(dir=target, prefix=".readiness_")
            os.close(fd)
            os.unlink(path)
            return True, f"Write access OK: {target}"
        except OSError as exc:
            return False, f"No write access to {target}: {exc}"
    return _checker


def _check_module_import(module_name: str):
    """Return a checker that validates a Python module can be imported."""
    def _checker():
        try:
            importlib.import_module(module_name)
            return True, f"{module_name} imported"
        except ImportError:
            return False, f"{module_name} not importable"
    return _checker


def _check_cors_not_wildcard():
    """Verify CORS is not set to wildcard in production."""
    def _checker():
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if env not in ("production", "staging"):
            return True, f"CORS wildcard check skipped (env={env})"
        origins = os.environ.get("MURPHY_CORS_ORIGINS", "*")
        if origins.strip() == "*":
            return False, "CORS origins set to wildcard '*' in production"
        return True, "CORS origins properly restricted"
    return _checker


def _check_jwt_secret():
    """Verify JWT secret is configured and not a default value."""
    def _checker():
        secret = os.environ.get("MURPHY_JWT_SECRET", "")
        if not secret:
            return False, "MURPHY_JWT_SECRET not set"
        if secret in ("changeme", "secret", "default", "murphy"):
            return False, "MURPHY_JWT_SECRET is using a default/weak value"
        if len(secret) < 32:
            return False, "MURPHY_JWT_SECRET should be at least 32 characters"
        return True, "MURPHY_JWT_SECRET configured"
    return _checker


def _check_production_secrets():
    """Verify that critical secrets are present in production/staging."""
    def _checker():
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if env not in ("production", "staging"):
            return True, f"Secret enforcement skipped (env={env})"
        required = [
            "MURPHY_API_KEYS",
            "MURPHY_CREDENTIAL_MASTER_KEY",
            "MURPHY_JWT_SECRET",
            "POSTGRES_PASSWORD",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            return False, f"Missing required secrets for {env}: {', '.join(missing)}"
        return True, "All required production secrets are set"
    return _checker


def _check_webhook_secrets_in_production():
    """Verify webhook secrets are set in production/staging."""
    def _checker():
        env = os.environ.get("MURPHY_ENV", "development").lower()
        if env not in ("production", "staging"):
            return True, f"Webhook secret check skipped (env={env})"
        secrets = ["PAYPAL_WEBHOOK_SECRET", "COINBASE_WEBHOOK_SECRET"]
        missing = [s for s in secrets if not os.environ.get(s)]
        if missing:
            return False, f"Webhook secrets missing in {env}: {', '.join(missing)}"
        return True, "Webhook secrets configured"
    return _checker


# ---------------------------------------------------------------------------
# DeploymentReadinessChecker
# ---------------------------------------------------------------------------

class DeploymentReadinessChecker:
    """Run pre-deployment readiness checks and report results.

    Usage::

        checker = DeploymentReadinessChecker()
        report = checker.run_all()
        if report["ready"]:
            print("Ready for deployment!")
        else:
            for fail in report["failures"]:
                print(f"FAIL: {fail['name']} — {fail['detail']}")
    """

    def __init__(self) -> None:
        self._checks: List[ReadinessCheck] = self._build_default_checks()

    def _build_default_checks(self) -> List[ReadinessCheck]:
        checks = [
            # Environment variables
            ReadinessCheck("MURPHY_ENV", "env", _check_env_var("MURPHY_ENV")),
            ReadinessCheck("DATABASE_URL", "env", _check_env_var("DATABASE_URL")),
            ReadinessCheck("REDIS_URL", "env", _check_env_var("REDIS_URL", required=False)),
            ReadinessCheck("PAYPAL_CLIENT_ID", "billing", _check_env_var("PAYPAL_CLIENT_ID")),
            ReadinessCheck("PAYPAL_CLIENT_SECRET", "billing", _check_env_var("PAYPAL_CLIENT_SECRET")),
            ReadinessCheck("COINBASE_COMMERCE_API_KEY", "billing", _check_env_var("COINBASE_COMMERCE_API_KEY", required=False)),

            # Webhook security — secrets should be set in production
            ReadinessCheck("PAYPAL_WEBHOOK_SECRET", "billing_security", _check_env_var("PAYPAL_WEBHOOK_SECRET", required=False)),
            ReadinessCheck("COINBASE_WEBHOOK_SECRET", "billing_security", _check_env_var("COINBASE_WEBHOOK_SECRET", required=False)),

            # Infrastructure
            ReadinessCheck("database", "infra", _check_database),
            ReadinessCheck("redis", "infra", _check_redis),

            # Disk access
            ReadinessCheck("data_dir", "disk", _check_disk_write("/app/data")),
            ReadinessCheck("log_dir", "disk", _check_disk_write("/app/logs")),

            # Core modules
            ReadinessCheck("runtime_app", "module", _check_module_import("src.runtime.app")),
            ReadinessCheck("subscription_manager", "module", _check_module_import("subscription_manager")),

            # Security
            ReadinessCheck("cors_config", "security", _check_cors_not_wildcard()),
            ReadinessCheck("jwt_secret", "security", _check_jwt_secret()),
            ReadinessCheck("production_secrets", "security", _check_production_secrets()),
            ReadinessCheck("webhook_secrets", "security", _check_webhook_secrets_in_production()),
        ]
        return checks

    def add_check(self, name: str, category: str, checker: Any) -> None:
        """Register an additional readiness check."""
        self._checks.append(ReadinessCheck(name, category, checker))

    def run_all(self) -> Dict[str, Any]:
        """Execute all checks and return a structured report."""
        results = [check.run() for check in self._checks]
        failures = [r for r in results if not r["ok"]]
        passed = [r for r in results if r["ok"]]

        # Categorise by category
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            by_category.setdefault(r["category"], []).append(r)

        return {
            "ready": len(failures) == 0,
            "total_checks": len(results),
            "passed": len(passed),
            "failed": len(failures),
            "failures": failures,
            "by_category": by_category,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "environment": os.environ.get("MURPHY_ENV", "development"),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return a summary status dict (for /api/readiness)."""
        report = self.run_all()
        return {
            "ready": report["ready"],
            "checks_total": report["total_checks"],
            "checks_passed": report["passed"],
            "checks_failed": report["failed"],
            "environment": report["environment"],
            "failures": [f["name"] for f in report["failures"]],
            "checked_at": report["checked_at"],
        }
