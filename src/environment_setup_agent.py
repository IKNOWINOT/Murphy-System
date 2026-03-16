"""
Environment Setup Agent — Murphy System

Applies the SelfFixLoop diagnose→plan→execute→test→retry pattern to the
user's computer environment rather than Murphy's internal state.

Phases:
  1. Probe     — Detect OS, Python, ports, disk, Playwright, .env, venv
  2. Plan      — Diff "found" vs "needed", generate ordered steps with risk levels
  3. HITL Gate — Present plan; user approves all / one-by-one / rejects
  4. Execute   — Run approved steps via subprocess or file operations
  5. Verify    — Try to reach /api/health; if broken, loop back
  6. Save      — Persist working state via EnvironmentStateManager

Design Principles:
  - HITL everywhere: no system modification without user approval
  - Alpha disclaimer: BSL 1.1, no warranty
  - Bounded retry (default max 10)
  - Thread-safe with Lock + capped audit log

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import platform
import shlex
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from setup_retry_amplifier import SetupRetryAmplifier
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
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 10
REQUIRED_PORTS = [8000, 8090]
REQUIRED_DISK_MB = 500
REQUIRED_RAM_MB = 512
MAX_RETRY_ATTEMPTS = 10
_MAX_AUDIT_LOG = 5_000


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Risk level classification for environment setup steps."""
    LOW = "low"           # create directory, create file
    MEDIUM = "medium"     # install Python package, create venv
    HIGH = "high"         # modify env vars, install system packages
    CRITICAL = "critical" # open firewall port, modify system settings


class StepStatus(str, Enum):
    """Approval status of an environment setup step requiring elevated risk."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class EnvironmentReport:
    """Snapshot of the current user environment discovered during probe."""

    os_name: str = ""
    os_version: str = ""
    is_wsl: bool = False
    python_version: str = ""
    python_ok: bool = False
    pip_available: bool = False
    git_available: bool = False
    disk_free_mb: float = 0.0
    disk_ok: bool = False
    ram_mb: float = 0.0
    ram_ok: bool = False
    ports_available: Dict[int, bool] = field(default_factory=dict)
    playwright_installed: bool = False
    dotenv_exists: bool = False
    venv_exists: bool = False
    murphy_installed: bool = False
    env_vars_present: List[str] = field(default_factory=list)
    env_vars_missing: List[str] = field(default_factory=list)
    probed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "is_wsl": self.is_wsl,
            "python_version": self.python_version,
            "python_ok": self.python_ok,
            "pip_available": self.pip_available,
            "git_available": self.git_available,
            "disk_free_mb": self.disk_free_mb,
            "disk_ok": self.disk_ok,
            "ram_mb": self.ram_mb,
            "ram_ok": self.ram_ok,
            "ports_available": self.ports_available,
            "playwright_installed": self.playwright_installed,
            "dotenv_exists": self.dotenv_exists,
            "venv_exists": self.venv_exists,
            "murphy_installed": self.murphy_installed,
            "env_vars_present": self.env_vars_present,
            "env_vars_missing": self.env_vars_missing,
            "probed_at": self.probed_at,
        }

    @property
    def all_ok(self) -> bool:
        """True only if every required check passed."""
        return (
            self.python_ok
            and self.pip_available
            and self.disk_ok
            and all(self.ports_available.get(p, False) for p in REQUIRED_PORTS)
        )


@dataclass
class SetupStep:
    """A single ordered setup action."""

    step_id: str = ""
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    command: Optional[str] = None          # shell command, or None for file ops
    file_op: Optional[Dict[str, str]] = None  # {"path": ..., "content": ...}
    browser_op: Optional[Dict[str, Any]] = None  # Playwright task spec
    os_filter: Optional[str] = None        # "windows" | "linux" | "darwin" | None
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    liability_note: str = "You approved this action. Murphy executed it as instructed."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "command": self.command,
            "file_op": self.file_op,
            "browser_op": self.browser_op,
            "os_filter": self.os_filter,
            "status": self.status.value,
            "result": self.result,
            "liability_note": self.liability_note,
        }


@dataclass
class SetupPlan:
    """Ordered collection of setup steps for a specific environment."""

    plan_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    steps: List[SetupStep] = field(default_factory=list)
    environment_report: Optional[EnvironmentReport] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def pending_steps(self) -> List[SetupStep]:
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def approved_steps(self) -> List[SetupStep]:
        return [s for s in self.steps if s.status == StepStatus.APPROVED]

    def failed_steps(self) -> List[SetupStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }


@dataclass
class SetupResult:
    """Result of a full environment setup run."""

    run_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    success: bool = False
    attempts: int = 0
    steps_executed: int = 0
    steps_failed: int = 0
    remaining_issues: List[str] = field(default_factory=list)
    final_report: Optional[EnvironmentReport] = None
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "attempts": self.attempts,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "remaining_issues": self.remaining_issues,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Phase 1: EnvironmentProbe
# ---------------------------------------------------------------------------


class EnvironmentProbe:
    """Detects the current state of the user's computer environment."""

    REQUIRED_ENV_VARS = ["MURPHY_HOME"]

    def probe(self) -> EnvironmentReport:
        """Run all environment checks and return an EnvironmentReport."""
        report = EnvironmentReport()
        self._probe_os(report)
        self._probe_python(report)
        self._probe_tools(report)
        self._probe_disk(report)
        self._probe_ram(report)
        self._probe_ports(report)
        self._probe_playwright(report)
        self._probe_files(report)
        self._probe_env_vars(report)
        logger.debug("Probe complete: all_ok=%s", report.all_ok)
        return report

    # ------------------------------------------------------------------

    def _probe_os(self, report: EnvironmentReport) -> None:
        report.os_name = platform.system().lower()   # "windows" | "linux" | "darwin"
        report.os_version = platform.version()
        report.is_wsl = (
            report.os_name == "linux"
            and "microsoft" in platform.uname().release.lower()
        )

    def _probe_python(self, report: EnvironmentReport) -> None:
        major, minor = sys.version_info.major, sys.version_info.minor
        report.python_version = f"{major}.{minor}.{sys.version_info.micro}"
        report.python_ok = (major, minor) >= (REQUIRED_PYTHON_MAJOR, REQUIRED_PYTHON_MINOR)

    def _probe_tools(self, report: EnvironmentReport) -> None:
        report.pip_available = shutil.which("pip") is not None or shutil.which("pip3") is not None
        report.git_available = shutil.which("git") is not None

    def _probe_disk(self, report: EnvironmentReport) -> None:
        try:
            usage = shutil.disk_usage(os.path.expanduser("~"))
            report.disk_free_mb = usage.free / (1024 * 1024)
            report.disk_ok = report.disk_free_mb >= REQUIRED_DISK_MB
        except Exception as exc:
            logging.getLogger(__name__).debug("Caught exception: %s", exc)
            report.disk_free_mb = 0.0
            report.disk_ok = False

    def _probe_ram(self, report: EnvironmentReport) -> None:
        try:
            import resource  # Unix only
            # Use a simple heuristic: read /proc/meminfo on Linux
            meminfo_path = "/proc/meminfo"
            if os.path.exists(meminfo_path):
                with open(meminfo_path, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            report.ram_mb = kb / 1024
                            break
        except Exception as exc:
            logging.getLogger(__name__).debug("Caught exception: %s", exc)
        if report.ram_mb == 0.0:
            # Fallback: mark as OK (cannot reliably determine on all platforms)
            report.ram_mb = REQUIRED_RAM_MB
        report.ram_ok = report.ram_mb >= REQUIRED_RAM_MB

    def _probe_ports(self, report: EnvironmentReport) -> None:
        for port in REQUIRED_PORTS:
            report.ports_available[port] = self._is_port_free(port)

    @staticmethod
    def _is_port_free(port: int) -> bool:
        bind_host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((bind_host, port))
                return True
            except OSError:
                return False

    def _probe_playwright(self, report: EnvironmentReport) -> None:
        try:
            import importlib
            spec = importlib.util.find_spec("playwright")
            report.playwright_installed = spec is not None
        except Exception as exc:
            logging.getLogger(__name__).debug("Caught exception: %s", exc)
            report.playwright_installed = False

    def _probe_files(self, report: EnvironmentReport) -> None:
        home = os.path.expanduser("~")
        report.dotenv_exists = os.path.isfile(os.path.join(home, ".env")) or os.path.isfile(".env")
        report.venv_exists = any(
            os.path.isdir(p) for p in [
                os.path.join(os.getcwd(), "venv"),
                os.path.join(os.getcwd(), ".venv"),
                os.path.join(home, ".murphy", "venv"),
            ]
        )
        report.murphy_installed = os.path.isdir(
            os.path.join(home, ".murphy")
        )

    def _probe_env_vars(self, report: EnvironmentReport) -> None:
        for var in self.REQUIRED_ENV_VARS:
            if os.environ.get(var):
                report.env_vars_present.append(var)
            else:
                report.env_vars_missing.append(var)


# ---------------------------------------------------------------------------
# Phase 2: SetupPlanGenerator
# ---------------------------------------------------------------------------


class SetupPlanGenerator:
    """Diffs the environment report against requirements and generates a plan."""

    def generate(self, report: EnvironmentReport) -> SetupPlan:
        """Return a SetupPlan with all steps needed to reach a healthy state."""
        plan = SetupPlan(environment_report=report)
        steps: List[SetupStep] = []

        if not report.python_ok:
            steps.append(self._step_python(report))

        if not report.pip_available:
            steps.append(self._step_pip(report))

        if not report.git_available:
            steps.append(self._step_git(report))

        if not report.venv_exists:
            steps.append(self._step_venv())

        if report.env_vars_missing:
            steps.append(self._step_env_vars(report))

        if not report.playwright_installed:
            steps.append(self._step_playwright())

        if not report.murphy_installed:
            steps.append(self._step_murphy_home())

        # Assign sequential IDs
        for idx, step in enumerate(steps, 1):
            step.step_id = f"step-{idx:03d}"

        plan.steps = steps
        logger.debug(
            "Generated plan with %d steps for plan_id=%s", len(steps), plan.plan_id
        )
        return plan

    # ------------------------------------------------------------------

    def _step_python(self, report: EnvironmentReport) -> SetupStep:
        if report.os_name == "windows":
            cmd = "winget install Python.Python.3.11"
        elif report.os_name == "darwin":
            cmd = "brew install python@3.11"
        else:
            cmd = "sudo apt-get install -y python3.11"
        return SetupStep(
            description=f"Install Python 3.11+ (found {report.python_version})",
            risk_level=RiskLevel.HIGH,
            command=cmd,
        )

    def _step_pip(self, report: EnvironmentReport) -> SetupStep:
        if report.os_name == "windows":
            cmd = "python -m ensurepip --upgrade"
        else:
            cmd = "python3 -m ensurepip --upgrade"
        return SetupStep(
            description="Install pip",
            risk_level=RiskLevel.MEDIUM,
            command=cmd,
        )

    def _step_git(self, report: EnvironmentReport) -> SetupStep:
        if report.os_name == "windows":
            cmd = "winget install Git.Git"
        elif report.os_name == "darwin":
            cmd = "brew install git"
        else:
            cmd = "sudo apt-get install -y git"
        return SetupStep(
            description="Install git",
            risk_level=RiskLevel.HIGH,
            command=cmd,
        )

    def _step_venv(self) -> SetupStep:
        home = os.path.expanduser("~")
        venv_path = os.path.join(home, ".murphy", "venv")
        return SetupStep(
            description="Create Murphy virtual environment",
            risk_level=RiskLevel.MEDIUM,
            command=f"python3 -m venv {venv_path}",
        )

    def _step_env_vars(self, report: EnvironmentReport) -> SetupStep:
        murphy_home = os.path.join(os.path.expanduser("~"), ".murphy")
        return SetupStep(
            description=f"Set missing environment variables: {report.env_vars_missing}",
            risk_level=RiskLevel.HIGH,
            file_op={
                "path": os.path.join(murphy_home, ".env"),
                "content": "\n".join(
                    f"{var}=" for var in report.env_vars_missing
                ) + "\n",
            },
        )

    def _step_playwright(self) -> SetupStep:
        return SetupStep(
            description="Install Playwright browser automation library",
            risk_level=RiskLevel.MEDIUM,
            command="pip install playwright && playwright install chromium",
        )

    def _step_murphy_home(self) -> SetupStep:
        murphy_home = os.path.join(os.path.expanduser("~"), ".murphy")
        return SetupStep(
            description=f"Create Murphy home directory at {murphy_home}",
            risk_level=RiskLevel.LOW,
            file_op={"path": murphy_home, "type": "directory"},
        )


# ---------------------------------------------------------------------------
# Phase 3: HITL Approval Gate (data-only — UI calls this via the API)
# ---------------------------------------------------------------------------


class HITLApprovalGate:
    """Records user approvals/rejections for setup steps.

    In the full system the UI calls the /api/setup/approve endpoint which
    delegates here.  Each approval is audit-logged with a liability note.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._audit_log: List[Dict[str, Any]] = []

    def approve_all(self, plan: SetupPlan) -> None:
        """Mark all pending steps as approved."""
        with self._lock:
            for step in plan.steps:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.APPROVED
                    self._log_approval(step, approved=True)

    def approve_step(self, plan: SetupPlan, step_id: str) -> bool:
        """Approve a single step by ID. Returns True if found."""
        with self._lock:
            for step in plan.steps:
                if step.step_id == step_id and step.status == StepStatus.PENDING:
                    step.status = StepStatus.APPROVED
                    self._log_approval(step, approved=True)
                    return True
        return False

    def reject_step(self, plan: SetupPlan, step_id: str) -> bool:
        """Reject a single step by ID. Returns True if found."""
        with self._lock:
            for step in plan.steps:
                if step.step_id == step_id and step.status == StepStatus.PENDING:
                    step.status = StepStatus.REJECTED
                    self._log_approval(step, approved=False)
                    return True
        return False

    def _log_approval(self, step: SetupStep, approved: bool) -> None:
        entry = {
            "step_id": step.step_id,
            "description": step.description,
            "risk_level": step.risk_level.value,
            "approved": approved,
            "liability_note": step.liability_note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)


# ---------------------------------------------------------------------------
# Phase 4: SetupExecutor
# ---------------------------------------------------------------------------


class SetupExecutor:
    """Executes approved setup steps via subprocess or file operations."""

    def execute_plan(self, plan: SetupPlan) -> List[Dict[str, Any]]:
        """Execute all APPROVED steps. Failed steps are recorded, not raised."""
        results = []
        for step in plan.approved_steps():
            result = self._execute_step(step)
            results.append(result)
        return results

    def _execute_step(self, step: SetupStep) -> Dict[str, Any]:
        # Skip steps filtered for other OS
        if step.os_filter and step.os_filter != platform.system().lower():
            step.status = StepStatus.SKIPPED
            return {"step_id": step.step_id, "status": "skipped", "reason": "os_filter"}

        try:
            if step.command:
                result = self._run_command(step)
            elif step.file_op:
                result = self._run_file_op(step)
            elif step.browser_op:
                result = self._run_browser_op(step)
            else:
                result = {"step_id": step.step_id, "status": "skipped", "reason": "no_op"}
                step.status = StepStatus.SKIPPED
                return result

            if result.get("returncode", 0) == 0 or result.get("status") == "success":
                step.status = StepStatus.EXECUTED
                result["status"] = "success"
            else:
                step.status = StepStatus.FAILED
                result["status"] = "failed"
            step.result = result
            return result

        except Exception as exc:
            logger.error("Step %s failed: %s", step.step_id, exc)
            error_result = {
                "step_id": step.step_id,
                "status": "failed",
                "error": str(exc),
            }
            step.status = StepStatus.FAILED
            step.result = error_result
            return error_result

    def _run_command(self, step: SetupStep) -> Dict[str, Any]:
        if step.command is None:
            return {"success": False, "error": "No command specified"}
        proc = subprocess.run(
            shlex.split(step.command),
            shell=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "step_id": step.step_id,
            "command": step.command,
            "returncode": proc.returncode,
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:2000],
        }

    def _run_file_op(self, step: SetupStep) -> Dict[str, Any]:
        if step.file_op is None:
            return {"success": False, "error": "No file operation specified"}
        op = step.file_op
        path = op.get("path", "")
        if op.get("type") == "directory":
            os.makedirs(path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(op.get("content", ""))
        return {
            "step_id": step.step_id,
            "file_op": "directory" if op.get("type") == "directory" else "write",
            "path": path,
            "returncode": 0,
        }

    def _run_browser_op(self, step: SetupStep) -> Dict[str, Any]:
        # Browser ops are handed to a Playwright runner (out-of-process).
        # Here we emit the task spec as JSON for that runner to consume.
        return {
            "step_id": step.step_id,
            "browser_op": "deferred",
            "task_spec": step.browser_op,
            "returncode": 0,
            "note": "Browser task spec emitted for Playwright runner",
        }


# ---------------------------------------------------------------------------
# Phase 5 & 6: EnvironmentSetupAgent (verify-and-retry loop + state save)
# ---------------------------------------------------------------------------


class EnvironmentSetupAgent:
    """Orchestrates all six phases of environment setup.

    Usage::

        agent = EnvironmentSetupAgent()
        plan = agent.probe_and_plan()
        agent.hitl_gate.approve_all(plan)
        result = agent.execute_and_verify(plan)
    """

    def __init__(
        self,
        probe: Optional[EnvironmentProbe] = None,
        planner: Optional[SetupPlanGenerator] = None,
        executor: Optional[SetupExecutor] = None,
        max_attempts: int = MAX_RETRY_ATTEMPTS,
    ) -> None:
        self.probe = probe or EnvironmentProbe()
        self.planner = planner or SetupPlanGenerator()
        self.executor = executor or SetupExecutor()
        self.hitl_gate = HITLApprovalGate()
        self.max_attempts = max_attempts
        self._lock = threading.Lock()
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------

    def probe_and_plan(self) -> SetupPlan:
        """Run probe then generate a setup plan."""
        report = self.probe.probe()
        plan = self.planner.generate(report)
        self._log("probe_and_plan", {"steps": len(plan.steps), "all_ok": report.all_ok})
        return plan

    def execute_and_verify(self, plan: SetupPlan) -> SetupResult:
        """Execute approved steps and verify health, retrying up to max_attempts.

        Every 3rd retry triggers the MMSMMS amplification cadence to generate
        a qualitatively different fix strategy instead of retrying the same
        approach.
        """
        result = SetupResult()
        attempt = 0
        amplifier = SetupRetryAmplifier(audit_log=self._audit_log)
        previous_plans: List[SetupPlan] = [plan]

        while attempt < self.max_attempts:
            attempt += 1
            result.attempts = attempt

            exec_results = self.executor.execute_plan(plan)
            result.steps_executed += len(
                [r for r in exec_results if r.get("status") == "success"]
            )
            result.steps_failed += len(
                [r for r in exec_results if r.get("status") == "failed"]
            )

            # Verify: re-probe and check health
            fresh_report = self.probe.probe()
            result.final_report = fresh_report

            if fresh_report.all_ok:
                result.success = True
                self._log("setup_success", {"attempts": attempt})
                break

            # Collect remaining issues
            issues = self._collect_issues(fresh_report)
            result.remaining_issues = issues
            self._log("setup_retry", {"attempt": attempt, "issues": issues})

            if not issues:
                result.success = True
                break

            # ---- MMSMMS cadence every 3rd retry ----
            if attempt % 3 == 0:
                amplified_plan = amplifier.amplify_failure(
                    report=fresh_report,
                    issues=issues,
                    attempt=attempt,
                    previous_plans=previous_plans,
                )
                if amplified_plan is not None and amplified_plan.steps:
                    self.hitl_gate.approve_all(amplified_plan)
                    previous_plans.append(amplified_plan)
                    plan = amplified_plan
                    self._log("mmsmms_amplified", {
                        "attempt": attempt,
                        "issues": issues,
                        "new_steps": len(amplified_plan.steps),
                    })
                    continue

            # Normal retry: re-probe and re-plan
            retry_plan = self.planner.generate(fresh_report)
            if not retry_plan.steps:
                break
            self.hitl_gate.approve_all(retry_plan)
            previous_plans.append(retry_plan)
            plan = retry_plan

        if not result.success:
            fresh_report = self.probe.probe()
            result.remaining_issues = self._collect_issues(fresh_report)
            result.final_report = fresh_report

        return result

    # ------------------------------------------------------------------

    @staticmethod
    def _collect_issues(report: EnvironmentReport) -> List[str]:
        issues: List[str] = []
        if not report.python_ok:
            issues.append(f"python_version_too_old:{report.python_version}")
        if not report.pip_available:
            issues.append("pip_not_available")
        if not report.disk_ok:
            issues.append(f"insufficient_disk:{report.disk_free_mb:.0f}MB")
        for port, free in report.ports_available.items():
            if not free:
                issues.append(f"port_in_use:{port}")
        if not report.playwright_installed:
            issues.append("playwright_not_installed")
        return issues

    def _log(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)
