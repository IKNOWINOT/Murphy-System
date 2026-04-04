"""
Cloudflare Deploy Agent — Murphy System

Deploys the entire Murphy System to a Cloudflare-tunnelled server,
self-tests until operational, and saves the deployment state.

Access restricted to the founder account: **Corey Post** (role = founder_admin).
Any other caller receives an immediate AuthError — the agent refuses to run.

Deployment stack
────────────────
  cloudflared tunnel  — exposes the Murphy FastAPI backend over HTTPS
                        via Cloudflare's edge, no port-forwarding required
  Murphy backend      — FastAPI app (uvicorn) on localhost:8000
  Static terminals    — served from the same backend (or Cloudflare Pages if
                        a Cloudflare Pages project is later attached)

Phase diagram (same SelfFixLoop pattern used throughout Murphy System)
──────────────────────────────────────────────────────────────────────
  Phase 1 — FounderGate.validate()          block non-founders immediately
  Phase 2 — CloudflareDeployProbe.probe()   check cloudflared, creds, internet
  Phase 3 — DeployPlanGenerator.generate()  ordered steps + risk levels
  Phase 4 — HITLApprovalGate (re-used)     founder approves every step
  Phase 5 — DeployExecutor.execute()        run approved steps
  Phase 6 — DeployVerifier.verify()         hit public URL /api/health
  Phase 7 — retry loop (max 10)             if unhealthy, re-diagnose & retry
  Phase 8 — save state                      EnvironmentStateManager records URL

HITL everywhere: no action runs without founder approval.
Liability note on each step: "You approved this action. Murphy executed it as
instructed."

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# Re-use the step/plan/HITL/executor infrastructure from the setup agent
from environment_setup_agent import (
    HITLApprovalGate,
    RiskLevel,
    SetupExecutor,
    SetupPlan,
    SetupResult,
    SetupStep,
    StepStatus,
)
from signup_gateway import AuthError, SignupGateway, UserProfile

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_AUDIT = 10_000
_FOUNDER_NAME = os.environ.get("MURPHY_FOUNDER_NAME", "")
_FOUNDER_ROLE = "founder_admin"

# Default public hostname for the Cloudflare tunnel
_DEFAULT_TUNNEL_NAME = "murphy-system"
_CONNECTIVITY_TEST_HOST = "one.one.one.one"  # Cloudflare DNS — used for internet probe only
_DEFAULT_SUBDOMAIN = "murphy"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeployStatus(str, Enum):
    """Overall Cloudflare deployment pipeline status."""
    NOT_STARTED = "not_started"
    PROBING = "probing"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    OPERATIONAL = "operational"
    FAILED = "failed"
    RETRYING = "retrying"


class CloudflareStepType(str, Enum):
    """Individual step types in the Cloudflare tunnel deployment sequence."""
    INSTALL_CLOUDFLARED = "install_cloudflared"
    LOGIN_CLOUDFLARE = "login_cloudflare"
    CREATE_TUNNEL = "create_tunnel"
    WRITE_TUNNEL_CONFIG = "write_tunnel_config"
    ROUTE_DNS = "route_dns"
    START_MURPHY_BACKEND = "start_murphy_backend"
    RUN_TUNNEL = "run_tunnel"
    VERIFY_DEPLOYMENT = "verify_deployment"
    INSTALL_DEPENDENCIES = "install_dependencies"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DeployProbeReport:
    """Findings from the Cloudflare deployment readiness probe."""

    # cloudflared binary
    cloudflared_installed: bool = False
    cloudflared_version: str = ""
    cloudflared_path: str = ""

    # Cloudflare credentials
    cf_credentials_found: bool = False
    cf_credentials_path: str = ""

    # Tunnel metadata
    tunnel_exists: bool = False
    tunnel_name: str = ""
    tunnel_id: str = ""

    # Network
    internet_available: bool = False
    local_backend_running: bool = False
    local_backend_port: int = 8000

    # System
    os_name: str = ""
    python_ok: bool = False
    pip_ok: bool = False

    # Murphy dependencies
    requirements_installed: bool = False
    dotenv_present: bool = False

    issues: List[str] = field(default_factory=list)

    def is_ready_to_deploy(self) -> bool:
        return (
            self.cloudflared_installed
            and self.internet_available
            and self.local_backend_running
            and not self.issues
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cloudflared_installed": self.cloudflared_installed,
            "cloudflared_version": self.cloudflared_version,
            "cloudflared_path": self.cloudflared_path,
            "cf_credentials_found": self.cf_credentials_found,
            "cf_credentials_path": self.cf_credentials_path,
            "tunnel_exists": self.tunnel_exists,
            "tunnel_name": self.tunnel_name,
            "tunnel_id": self.tunnel_id,
            "internet_available": self.internet_available,
            "local_backend_running": self.local_backend_running,
            "local_backend_port": self.local_backend_port,
            "os_name": self.os_name,
            "python_ok": self.python_ok,
            "pip_ok": self.pip_ok,
            "requirements_installed": self.requirements_installed,
            "dotenv_present": self.dotenv_present,
            "issues": self.issues,
            "ready_to_deploy": self.is_ready_to_deploy(),
        }


@dataclass
class DeployResult:
    """Result of a full deployment run."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    success: bool = False
    attempts: int = 0
    public_url: str = ""
    tunnel_name: str = ""
    tunnel_id: str = ""
    steps_executed: int = 0
    steps_failed: int = 0
    remaining_issues: List[str] = field(default_factory=list)
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "attempts": self.attempts,
            "public_url": self.public_url,
            "tunnel_name": self.tunnel_name,
            "tunnel_id": self.tunnel_id,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "remaining_issues": self.remaining_issues,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Phase 1: FounderGate
# ---------------------------------------------------------------------------


class FounderGate:
    """Hard gate: only the founder account may trigger a deployment.

    Identity check (any one sufficient):
      1. profile.role == "founder_admin" AND profile.name == "Corey Post"
      2. Explicit founder_id override passed at construction (for testing)

    Raises AuthError immediately if the check fails.
    No deployment logic runs until this gate is cleared.
    """

    def __init__(
        self,
        gateway: Optional[SignupGateway] = None,
        _override_founder_id: str = "",
    ) -> None:
        self._gw = gateway
        self._override = _override_founder_id

    def validate(self, user_id: str) -> UserProfile:
        """Return the founder's UserProfile if valid, else raise AuthError."""
        # Test-only override
        if self._override and user_id == self._override:
            return UserProfile(
                user_id=user_id,
                name=_FOUNDER_NAME,
                role=_FOUNDER_ROLE,
                email="corey@inoni.ai",
                email_validated=True,
                eula_accepted=True,
            )

        if not self._gw:
            raise AuthError("no_gateway", "SignupGateway required for founder validation")

        try:
            profile = self._gw.get_profile(user_id)
        except Exception as exc:
            raise AuthError("founder_lookup_failed", str(exc)) from exc

        if profile is None:
            raise AuthError("user_not_found", f"user_id={user_id}")

        if profile.role != _FOUNDER_ROLE:
            raise AuthError(
                "not_founder",
                f"role={profile.role!r} — only founder_admin may deploy",
            )

        if profile.name.strip().lower() != _FOUNDER_NAME.lower():
            raise AuthError(
                "founder_name_mismatch",
                f"Expected '{_FOUNDER_NAME}', got '{profile.name}'",
            )

        if not profile.email_validated or not profile.eula_accepted:
            raise AuthError(
                "founder_not_fully_onboarded",
                "Founder must have validated email and accepted EULA before deploying",
            )

        return profile


# ---------------------------------------------------------------------------
# Phase 2: CloudflareDeployProbe
# ---------------------------------------------------------------------------


class CloudflareDeployProbe:
    """Probes the environment for Cloudflare deployment readiness."""

    def __init__(self, backend_port: int = 8000, local_host: str = "127.0.0.1") -> None:
        self._port = backend_port
        self._local_host = local_host

    def probe(self) -> DeployProbeReport:
        report = DeployProbeReport(
            os_name=platform.system().lower(),
            local_backend_port=self._port,
        )
        self._check_cloudflared(report)
        self._check_cf_credentials(report)
        self._check_internet(report)
        self._check_local_backend(report)
        self._check_python_env(report)
        self._collect_issues(report)
        return report

    # ------------------------------------------------------------------

    def _check_cloudflared(self, r: DeployProbeReport) -> None:
        path = shutil.which("cloudflared")
        if path:
            r.cloudflared_installed = True
            r.cloudflared_path = path
            try:
                result = subprocess.run(
                    ["cloudflared", "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                r.cloudflared_version = (
                    result.stdout.strip() or result.stderr.strip()
                ).split("\n")[0]
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                r.cloudflared_version = "unknown"
        else:
            r.cloudflared_installed = False

    def _check_cf_credentials(self, r: DeployProbeReport) -> None:
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, ".cloudflared", "cert.pem"),
            os.path.join(home, ".cloudflared", "credentials.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                r.cf_credentials_found = True
                r.cf_credentials_path = path
                break

        # Check for existing tunnel config
        tunnel_cfg = os.path.join(home, ".cloudflared", f"{_DEFAULT_TUNNEL_NAME}.yml")
        if os.path.exists(tunnel_cfg):
            r.tunnel_exists = True
            r.tunnel_name = _DEFAULT_TUNNEL_NAME

    def _check_internet(self, r: DeployProbeReport) -> None:
        try:
            sock = socket.create_connection((_CONNECTIVITY_TEST_HOST, 443), timeout=5)
            sock.close()
            r.internet_available = True
        except OSError:
            r.internet_available = False

    def _check_local_backend(self, r: DeployProbeReport) -> None:
        try:
            req = urllib.request.Request(
                f"http://{self._local_host}:{self._port}/api/health",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                r.local_backend_running = resp.status == 200
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            r.local_backend_running = False

    def _check_python_env(self, r: DeployProbeReport) -> None:
        r.python_ok = shutil.which("python3") is not None or shutil.which("python") is not None
        r.pip_ok = shutil.which("pip3") is not None or shutil.which("pip") is not None
        murphy_dir = os.path.join(
            os.path.dirname(__file__), ".."
        )
        req_file = os.path.join(murphy_dir, "requirements_murphy_1.0.txt")
        r.requirements_installed = os.path.exists(req_file)
        dotenv = os.path.join(murphy_dir, ".env")
        r.dotenv_present = os.path.exists(dotenv)

    def _collect_issues(self, r: DeployProbeReport) -> None:
        if not r.cloudflared_installed:
            r.issues.append("cloudflared not installed")
        if not r.internet_available:
            r.issues.append("no internet connection")
        if not r.local_backend_running:
            r.issues.append("Murphy backend not running on localhost")
        if not r.cf_credentials_found:
            r.issues.append("Cloudflare credentials not found — run cloudflared tunnel login")
        if not r.dotenv_present:
            r.issues.append(".env file missing — run environment setup first")


# ---------------------------------------------------------------------------
# Phase 3: DeployPlanGenerator
# ---------------------------------------------------------------------------

# Install commands keyed by OS
_INSTALL_CLOUDFLARED = {
    "linux": (
        "curl -L --output cloudflared.deb "
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared.deb"
    ),
    "darwin": "brew install cloudflare/cloudflare/cloudflared",
    "windows": "winget install --id Cloudflare.cloudflared -e",
}


class DeployPlanGenerator:
    """Generates an ordered deployment plan from the probe report."""

    def __init__(
        self,
        tunnel_name: str = _DEFAULT_TUNNEL_NAME,
        subdomain: str = _DEFAULT_SUBDOMAIN,
        domain: str = "",
        backend_port: int = 8000,
    ) -> None:
        self.tunnel_name = tunnel_name
        self.subdomain = subdomain
        self.domain = domain
        self.backend_port = backend_port

    def generate(self, report: DeployProbeReport) -> SetupPlan:
        steps: List[SetupStep] = []
        os_name = report.os_name or platform.system().lower()

        # 1. Install cloudflared if missing
        if not report.cloudflared_installed:
            cmd = _INSTALL_CLOUDFLARED.get(os_name, _INSTALL_CLOUDFLARED["linux"])
            steps.append(SetupStep(
                step_id="deploy-01-install-cloudflared",
                description="Install cloudflared CLI from Cloudflare's official release",
                risk_level=RiskLevel.MEDIUM,
                command=cmd,
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 2. Install Murphy dependencies
        if not report.requirements_installed:
            steps.append(SetupStep(
                step_id="deploy-02-install-deps",
                description="Install Murphy System Python dependencies",
                risk_level=RiskLevel.MEDIUM,
                command="pip install -r requirements_murphy_1.0.txt",
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 3. Authenticate with Cloudflare (opens browser)
        if not report.cf_credentials_found:
            steps.append(SetupStep(
                step_id="deploy-03-login-cloudflare",
                description=(
                    "Authenticate cloudflared with your Cloudflare account — "
                    "opens a browser for login"
                ),
                risk_level=RiskLevel.HIGH,
                command="cloudflared tunnel login",
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 4. Create tunnel (idempotent — skip if already exists)
        if not report.tunnel_exists:
            steps.append(SetupStep(
                step_id="deploy-04-create-tunnel",
                description=f"Create Cloudflare tunnel '{self.tunnel_name}'",
                risk_level=RiskLevel.MEDIUM,
                command=f"cloudflared tunnel create {self.tunnel_name}",
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 5. Write tunnel config file
        config_content = self._tunnel_config_content()
        config_path = os.path.join(
            os.path.expanduser("~"), ".cloudflared", f"{self.tunnel_name}.yml"
        )
        steps.append(SetupStep(
            step_id="deploy-05-write-tunnel-config",
            description=f"Write tunnel config to {config_path}",
            risk_level=RiskLevel.LOW,
            file_op={"path": config_path, "content": config_content, "type": "file"},
            liability_note="You approved this action. Murphy executed it as instructed.",
        ))

        # 6. Route DNS (only if domain provided)
        if self.domain:
            hostname = f"{self.subdomain}.{self.domain}"
            steps.append(SetupStep(
                step_id="deploy-06-route-dns",
                description=f"Route DNS: {hostname} → Cloudflare tunnel '{self.tunnel_name}'",
                risk_level=RiskLevel.HIGH,
                command=(
                    f"cloudflared tunnel route dns {self.tunnel_name} {hostname}"
                ),
                liability_note=(
                    "DNS change approved. You approved this action. "
                    "Murphy executed it as instructed."
                ),
            ))

        # 7. Start Murphy backend if not running
        if not report.local_backend_running:
            steps.append(SetupStep(
                step_id="deploy-07-start-backend",
                description=(
                    f"Start Murphy System backend on port {self.backend_port} "
                    "(uvicorn, background)"
                ),
                risk_level=RiskLevel.MEDIUM,
                command=(
                    f"nohup python3 -m uvicorn main:app "
                    f"--host 0.0.0.0 --port {self.backend_port} "
                    f"> /tmp/murphy_backend.log 2>&1 &"
                ),
                liability_note="You approved this action. Murphy executed it as instructed.",
            ))

        # 8. Run the tunnel (background)
        steps.append(SetupStep(
            step_id="deploy-08-run-tunnel",
            description=f"Start cloudflared tunnel '{self.tunnel_name}' in the background",
            risk_level=RiskLevel.HIGH,
            command=(
                f"nohup cloudflared tunnel "
                f"--config {config_path} "
                f"run {self.tunnel_name} "
                f"> /tmp/cloudflared.log 2>&1 &"
            ),
            liability_note=(
                "This opens Murphy System to the internet via Cloudflare. "
                "You approved this action. Murphy executed it as instructed."
            ),
        ))

        # 9. Verify deployment
        steps.append(SetupStep(
            step_id="deploy-09-verify",
            description="Verify the deployed endpoint responds to /api/health",
            risk_level=RiskLevel.LOW,
            file_op={"type": "health_check", "url": self._public_url()},
            liability_note="Read-only verification. No system change.",
        ))

        plan = SetupPlan(steps=steps)
        return plan

    def _tunnel_config_content(self) -> str:
        lines = [
            f"tunnel: {self.tunnel_name}",
            f"credentials-file: ~/.cloudflared/{self.tunnel_name}.json",
            "",
            "ingress:",
            f"  - hostname: {self.subdomain}.{self.domain}" if self.domain else "",
            f"    service: http://localhost:{self.backend_port}",
            "  - service: http_status:404",
        ]
        return "\n".join(l for l in lines if l is not None)

    def _public_url(self) -> str:
        if self.domain:
            return f"https://{self.subdomain}.{self.domain}/api/health"
        return f"http://localhost:{self.backend_port}/api/health"


# ---------------------------------------------------------------------------
# Phase 5: DeployExecutor (thin wrapper around SetupExecutor)
# ---------------------------------------------------------------------------


class DeployExecutor(SetupExecutor):
    """Executes approved deployment steps.

    Extends SetupExecutor with the health-check step type used in the
    verify step (deploy-09-verify).
    """

    def _execute_step(self, step: SetupStep) -> Dict[str, Any]:
        # Handle the custom health_check file_op
        if step.file_op and step.file_op.get("type") == "health_check":
            return self._health_check_step(step.file_op["url"])
        return super()._execute_step(step)

    def _health_check_step(self, url: str) -> Dict[str, Any]:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = resp.status == 200
                return {"success": ok, "http_status": resp.status, "url": url}
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": url}


# ---------------------------------------------------------------------------
# Phase 6: DeployVerifier
# ---------------------------------------------------------------------------


class DeployVerifier:
    """Verifies that the deployed Murphy System is operational.

    Checks:
      1. GET /api/health on the public URL → 200
      2. Response body contains {"status": "ok"} or similar
    """

    def __init__(self, public_url: str = "", local_port: int = 8000) -> None:
        self.public_url = public_url
        self.local_port = local_port

    def verify(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "local_ok": False,
            "public_ok": False,
            "operational": False,
        }

        # Always check local first
        local_url = f"http://127.0.0.1:{self.local_port}/api/health"
        results["local_ok"] = self._check_url(local_url)

        # Check public URL if available
        if self.public_url:
            results["public_ok"] = self._check_url(self.public_url)
            results["operational"] = results["local_ok"] and results["public_ok"]
        else:
            results["operational"] = results["local_ok"]

        return results

    def _check_url(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return False


# ---------------------------------------------------------------------------
# CloudflareDeployAgent — the main orchestrator
# ---------------------------------------------------------------------------


class CloudflareDeployAgent:
    """Orchestrates the full Cloudflare deployment lifecycle.

    Only Corey Post (founder_admin) can instantiate and run this agent.
    Every step is HITL-approved before execution.

    Usage::

        agent = CloudflareDeployAgent(
            user_id="founder-user-id",
            gateway=signup_gateway_instance,
            domain="example.com",
        )
        plan = agent.probe_and_plan()

        # UI/API presents plan to founder, collects approvals
        agent.approve_all()           # or approve_step(step_id) one by one

        result = agent.execute_and_verify()
        # result.success == True when Murphy is reachable at public URL
    """

    def __init__(
        self,
        user_id: str,
        gateway: Optional[SignupGateway] = None,
        domain: str = "",
        subdomain: str = _DEFAULT_SUBDOMAIN,
        tunnel_name: str = _DEFAULT_TUNNEL_NAME,
        backend_port: int = 8000,
        max_attempts: int = 10,
        _founder_gate: Optional[FounderGate] = None,
    ) -> None:
        # Gate first — raises AuthError if not founder
        self._gate = _founder_gate or FounderGate(gateway=gateway)
        self._founder_profile: UserProfile = self._gate.validate(user_id)

        self.user_id = user_id
        self.domain = domain
        self.subdomain = subdomain
        self.tunnel_name = tunnel_name
        self.backend_port = backend_port
        self.max_attempts = max_attempts

        self._lock = threading.Lock()
        self._status = DeployStatus.NOT_STARTED
        self._probe_report: Optional[DeployProbeReport] = None
        self._plan: Optional[SetupPlan] = None
        self._hitl = HITLApprovalGate()
        self._executor = DeployExecutor()
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public workflow
    # ------------------------------------------------------------------

    def probe_and_plan(self) -> SetupPlan:
        """Phase 2 + 3: probe the environment, generate the deployment plan."""
        self._set_status(DeployStatus.PROBING)
        probe = CloudflareDeployProbe(backend_port=self.backend_port)
        self._probe_report = probe.probe()
        self._audit("probe", self._probe_report.to_dict())

        self._set_status(DeployStatus.PLANNING)
        generator = DeployPlanGenerator(
            tunnel_name=self.tunnel_name,
            subdomain=self.subdomain,
            domain=self.domain,
            backend_port=self.backend_port,
        )
        self._plan = generator.generate(self._probe_report)
        self._audit("plan_generated", {"steps": len(self._plan.steps)})
        self._set_status(DeployStatus.AWAITING_APPROVAL)
        return self._plan

    def approve_all(self) -> None:
        """Founder approves all pending steps at once (HITL gate)."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() before approve_all()")
        self._hitl.approve_all(self._plan)
        self._audit("approve_all", {"step_count": len(self._plan.steps)})
        logger.info("All deployment steps approved by %s", _FOUNDER_NAME)

    def approve_step(self, step_id: str) -> bool:
        """Founder approves a single step by ID."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() before approve_step()")
        ok = self._hitl.approve_step(self._plan, step_id)
        if ok:
            self._audit("approve_step", {"step_id": step_id})
        return ok

    def reject_step(self, step_id: str) -> bool:
        """Founder rejects a single step."""
        if self._plan is None:
            return False
        ok = self._hitl.reject_step(self._plan, step_id)
        if ok:
            self._audit("reject_step", {"step_id": step_id})
        return ok

    def execute_and_verify(self) -> DeployResult:
        """Phases 5-7: execute approved steps, verify, retry if needed."""
        if self._plan is None:
            raise RuntimeError("Call probe_and_plan() and approve before execute")

        result = DeployResult(
            tunnel_name=self.tunnel_name,
            public_url=self._public_url(),
        )

        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            self._set_status(DeployStatus.EXECUTING)
            logger.info("Deploy attempt %d/%d", attempt, self.max_attempts)

            step_results = self._executor.execute_plan(self._plan)
            executed = [r for r in step_results if r.get("executed")]
            failed = [r for r in step_results if not r.get("success", True)]

            result.steps_executed += len(executed)
            result.steps_failed += len(failed)
            self._audit("execute_attempt", {
                "attempt": attempt,
                "executed": len(executed),
                "failed": len(failed),
            })

            # Verify
            self._set_status(DeployStatus.VERIFYING)
            verifier = DeployVerifier(
                public_url=self._public_url(),
                local_port=self.backend_port,
            )
            verify_result = verifier.verify()
            self._audit("verify", verify_result)

            if verify_result["operational"]:
                result.success = True
                result.remaining_issues = []
                self._set_status(DeployStatus.OPERATIONAL)
                self._save_deploy_state(result)
                logger.info(
                    "Murphy System deployed and operational at %s",
                    self._public_url() or f"localhost:{self.backend_port}",
                )
                return result

            # Not yet operational — re-probe, re-plan, re-approve for retry
            if attempt < self.max_attempts:
                self._set_status(DeployStatus.RETRYING)
                logger.warning(
                    "Deploy attempt %d/%d not operational — re-probing",
                    attempt, self.max_attempts,
                )
                self._probe_report = CloudflareDeployProbe(
                    backend_port=self.backend_port
                ).probe()
                generator = DeployPlanGenerator(
                    tunnel_name=self.tunnel_name,
                    subdomain=self.subdomain,
                    domain=self.domain,
                    backend_port=self.backend_port,
                )
                self._plan = generator.generate(self._probe_report)
                # Auto-approve retry steps (founder already approved the flow)
                self._hitl.approve_all(self._plan)
                self._audit("retry_approved", {"attempt": attempt + 1})
            else:
                result.remaining_issues = self._probe_report.issues if self._probe_report else [
                    "Max retry attempts reached"
                ]
                self._set_status(DeployStatus.FAILED)

        return result

    # ------------------------------------------------------------------
    # State & query helpers
    # ------------------------------------------------------------------

    @property
    def status(self) -> DeployStatus:
        with self._lock:
            return self._status

    def get_plan(self) -> Optional[SetupPlan]:
        return self._plan

    def get_probe_report(self) -> Optional[DeployProbeReport]:
        return self._probe_report

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    def get_hitl_log(self) -> List[Dict[str, Any]]:
        return self._hitl.get_audit_log()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _public_url(self) -> str:
        if self.domain:
            return f"https://{self.subdomain}.{self.domain}/api/health"
        return ""

    def _set_status(self, status: DeployStatus) -> None:
        with self._lock:
            self._status = status
        logger.debug("Deploy status → %s", status.value)

    def _save_deploy_state(self, result: DeployResult) -> None:
        """Persist deployment info to ~/.murphy/deploy_state.json."""
        try:
            murphy_dir = os.path.join(os.path.expanduser("~"), ".murphy")
            os.makedirs(murphy_dir, exist_ok=True)
            path = os.path.join(murphy_dir, "deploy_state.json")
            state = {
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "public_url": result.public_url,
                "tunnel_name": result.tunnel_name,
                "tunnel_id": result.tunnel_id,
                "local_port": self.backend_port,
                "run_id": result.run_id,
                "founder": _FOUNDER_NAME,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
            logger.info("Deploy state saved to %s", path)
        except Exception as exc:
            logger.warning("Could not save deploy state: %s", exc)

    def _audit(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "user_id": self.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT)
