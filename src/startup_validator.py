"""
Startup Validator for Murphy System.

Design Label: SV-001 — Boot-Time System Validation

Validates on boot that all required environment variables are set,
all required files exist, all required ports are available, and all
required dependencies are importable.  Fails fast with clear error
messages when any prerequisite is missing.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    category: str  # "env", "file", "port", "dependency"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class StartupReport:
    """Aggregated report of all validation checks."""

    results: List[ValidationResult] = field(default_factory=list)
    passed: bool = True
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def failures(self) -> List[ValidationResult]:
        """Return only failed checks."""
        return [r for r in self.results if not r.passed]

    @property
    def summary(self) -> Dict[str, Any]:
        """Return a summary dict suitable for JSON serialisation."""
        return {
            "passed": self.passed,
            "total_checks": len(self.results),
            "failures": len(self.failures),
            "checked_at": self.checked_at,
            "details": [
                {"name": r.name, "passed": r.passed, "message": r.message}
                for r in self.results
            ],
        }


# ---------------------------------------------------------------------------
# Startup Validator
# ---------------------------------------------------------------------------

class StartupValidator:
    """Validates system prerequisites at boot time.

    Usage::

        validator = StartupValidator()
        validator.add_required_env("MURPHY_ENV")
        validator.add_required_file(Path("src/state_schema.py"))
        validator.add_required_dependency("flask")
        report = validator.validate()
        if not report.passed:
            for f in report.failures:
                logger.error("FAIL: %s — %s", f.name, f.message)
    """

    def __init__(self) -> None:
        self._env_vars: List[str] = []
        self._files: List[Path] = []
        self._ports: List[int] = []
        self._dependencies: List[str] = []

    # -- registration helpers ------------------------------------------------

    def add_required_env(self, var_name: str) -> None:
        """Register an environment variable that must be set."""
        capped_append(self._env_vars, var_name)

    def add_required_file(self, path: Path) -> None:
        """Register a file that must exist on disk."""
        capped_append(self._files, path)

    def add_required_port(self, port: int) -> None:
        """Register a TCP port that must be available (not in use)."""
        capped_append(self._ports, port)

    def add_required_dependency(self, module_name: str) -> None:
        """Register a Python package that must be importable."""
        capped_append(self._dependencies, module_name)

    # -- validation ----------------------------------------------------------

    def validate(self) -> StartupReport:
        """Run all registered checks and return a *StartupReport*."""
        report = StartupReport()

        for var in self._env_vars:
            report.results.append(self._check_env(var))

        for path in self._files:
            report.results.append(self._check_file(path))

        for port in self._ports:
            report.results.append(self._check_port(port))

        for dep in self._dependencies:
            report.results.append(self._check_dependency(dep))

        report.passed = all(r.passed for r in report.results)
        return report

    # -- individual checks ---------------------------------------------------

    @staticmethod
    def _check_env(var_name: str) -> ValidationResult:
        """Check whether an environment variable is set and non-empty."""
        value = os.environ.get(var_name)
        if value:
            return ValidationResult(
                name=f"env:{var_name}",
                passed=True,
                message=f"Environment variable {var_name} is set",
                category="env",
            )
        return ValidationResult(
            name=f"env:{var_name}",
            passed=False,
            message=f"Required environment variable {var_name} is not set",
            category="env",
        )

    @staticmethod
    def _check_file(path: Path) -> ValidationResult:
        """Check whether a file exists."""
        if path.exists():
            return ValidationResult(
                name=f"file:{path}",
                passed=True,
                message=f"File {path} exists",
                category="file",
            )
        return ValidationResult(
            name=f"file:{path}",
            passed=False,
            message=f"Required file {path} does not exist",
            category="file",
        )

    @staticmethod
    def _check_port(port: int) -> ValidationResult:
        """Check whether a TCP port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                bind_host = "127.0.0.1"  # default localhost for port check
                sock.bind((bind_host, port))
            return ValidationResult(
                name=f"port:{port}",
                passed=True,
                message=f"Port {port} is available",
                category="port",
            )
        except OSError as exc:
            return ValidationResult(
                name=f"port:{port}",
                passed=False,
                message=f"Port {port} is not available: {exc}",
                category="port",
            )

    @staticmethod
    def _check_dependency(module_name: str) -> ValidationResult:
        """Check whether a Python module is importable."""
        try:
            importlib.import_module(module_name)
            return ValidationResult(
                name=f"dep:{module_name}",
                passed=True,
                message=f"Dependency {module_name} is importable",
                category="dependency",
            )
        except ImportError as exc:
            return ValidationResult(
                name=f"dep:{module_name}",
                passed=False,
                message=f"Dependency {module_name} is not importable: {exc}",
                category="dependency",
            )


# ---------------------------------------------------------------------------
# LLM Boot Validation
# ---------------------------------------------------------------------------

def validate_llm_boot_status() -> Dict[str, Any]:
    """Validate LLM configuration at boot time.

    This ensures the system can always respond (either via external LLM or onboard
    fallback). Returns a status dict describing the current LLM mode.

    The LLM subsystem is always operational:
    - If MURPHY_LLM_PROVIDER is set and has a valid API key -> external_api mode
    - Otherwise -> onboard mode (LocalLLMFallback or pattern matcher)

    Returns:
        Dict with keys:
        - mode: "external_api" | "onboard"
        - provider: The provider name ("groq", "openai", "anthropic", "onboard")
        - healthy: True if LLM can respond (always True since onboard is fallback)
        - note: Human-readable status message
    """
    provider = os.environ.get("MURPHY_LLM_PROVIDER", "").strip().lower()

    # Auto-detect provider from available API keys
    if not provider:
        if os.environ.get("GROQ_API_KEY", "").strip():
            provider = "groq"
        elif os.environ.get("OPENAI_API_KEY", "").strip():
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY", "").strip():
            provider = "anthropic"

    # Check if external provider has valid API key
    external_api_configured = False
    if provider == "groq" and os.environ.get("GROQ_API_KEY", "").strip():
        external_api_configured = True
    elif provider == "openai" and os.environ.get("OPENAI_API_KEY", "").strip():
        external_api_configured = True
    elif provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY", "").strip():
        external_api_configured = True

    if external_api_configured:
        return {
            "mode": "external_api",
            "provider": provider,
            "healthy": True,
            "note": f"LLM configured with {provider} provider",
        }

    return {
        "mode": "onboard",
        "provider": "onboard",
        "healthy": True,
        "note": (
            "LLM using onboard fallback (LocalLLMFallback). "
            "Add MURPHY_LLM_PROVIDER and API key for external LLM."
        ),
    }


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_default_validator(project_root: Optional[Path] = None) -> StartupValidator:
    """Create a validator pre-loaded with Murphy System's standard checks.

    Args:
        project_root: Path to the Murphy System project root.

    Returns:
        A *StartupValidator* ready to call ``validate()``.
    """
    v = StartupValidator()

    # Required env vars (MURPHY_ENV is the only hard requirement;
    # API keys are optional and checked at runtime by each integration)
    v.add_required_env("MURPHY_ENV")

    # Core dependencies that must be importable
    for dep in ("flask", "pydantic", "yaml"):
        v.add_required_dependency(dep)

    # Required files
    if project_root is not None:
        for rel in ("src/state_schema.py", "src/governance_kernel.py"):
            v.add_required_file(project_root / rel)

    return v
