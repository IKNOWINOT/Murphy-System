"""
Self-Automation Bootstrap — Murphy System

Entry point that initialises and coordinates the three subsystems needed
for Murphy to begin autonomous operations and revenue generation:

  1. **Deployment Readiness**  — validates the environment is production-ready
  2. **Revenue Pipeline**      — wires up billing (PayPal/Crypto), subscription
     management, and the self-selling engine
  3. **Self-Automation Loop**  — starts the improvement orchestrator and
     full-automation controller with safe defaults

The bootstrap does **not** mutate external systems — it assembles local
instances, runs diagnostics, and returns a status report.  Actual execution
(deploying, selling, improving) requires explicit activation after the
bootstrap report passes.

Usage::

    from self_automation_bootstrap import SelfAutomationBootstrap

    boot = SelfAutomationBootstrap()
    report = boot.run()
    if report["stages"]["deployment"]["ready"]:
        print("Deployment stage ready")
    if report["stages"]["revenue"]["ready"]:
        print("Revenue stage ready")
    if report["stages"]["self_automation"]["ready"]:
        print("Self-automation stage ready")

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SelfAutomationBootstrap:
    """Coordinate deployment, revenue, and self-automation readiness.

    Instantiate, then call :meth:`run` to get a full diagnostic report.
    Each stage reports independently so partial readiness is visible.
    """

    def __init__(
        self,
        persistence_manager: Any = None,
        event_backbone: Any = None,
    ) -> None:
        self._persistence = persistence_manager
        self._backbone = event_backbone
        self._report: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Execute all bootstrap stages and return a combined report."""
        deployment = self._check_deployment_stage()
        revenue = self._check_revenue_stage()
        automation = self._check_self_automation_stage()

        all_ready = deployment["ready"] and revenue["ready"] and automation["ready"]

        self._report = {
            "bootstrap_version": "1.0.0",
            "all_ready": all_ready,
            "stages": {
                "deployment": deployment,
                "revenue": revenue,
                "self_automation": automation,
            },
            "next_steps": self._compute_next_steps(deployment, revenue, automation),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._report

    def get_status(self) -> Dict[str, Any]:
        """Return the last bootstrap report, or run one if none exists."""
        if self._report is None:
            self.run()
        return {
            "all_ready": self._report["all_ready"],
            "stages": {
                name: {"ready": stage["ready"], "issues": len(stage.get("issues", []))}
                for name, stage in self._report["stages"].items()
            },
            "next_steps_count": len(self._report["next_steps"]),
            "checked_at": self._report["checked_at"],
        }

    # ------------------------------------------------------------------
    # Stage 1: Deployment Readiness
    # ------------------------------------------------------------------

    def _check_deployment_stage(self) -> Dict[str, Any]:
        """Validate that the runtime environment is deployment-ready."""
        issues: List[str] = []
        components: Dict[str, bool] = {}

        # Dockerfile present
        components["dockerfile"] = os.path.isfile(
            os.environ.get("MURPHY_DOCKERFILE", "Dockerfile")
        )
        if not components["dockerfile"]:
            issues.append("Dockerfile not found — container build will fail")

        # Core environment variables
        for var in ("MURPHY_ENV", "DATABASE_URL"):
            present = bool(os.environ.get(var))
            components[var.lower()] = present
            if not present:
                issues.append(f"{var} not configured")

        # DeploymentReadinessChecker module
        try:
            from deployment_readiness import DeploymentReadinessChecker
            checker = DeploymentReadinessChecker()
            readiness = checker.run_all()
            components["readiness_checker"] = readiness["ready"]
            if not readiness["ready"]:
                for f in readiness["failures"]:
                    issues.append(f"Readiness check failed: {f['name']} — {f['detail']}")
        except ImportError:
            components["readiness_checker"] = False
            issues.append("deployment_readiness module not available")

        # DeploymentAutomationController module
        try:
            from deployment_automation_controller import DeploymentAutomationController
            ctrl = DeploymentAutomationController(
                persistence_manager=self._persistence,
                event_backbone=self._backbone,
            )
            components["deployment_controller"] = True
            components["deployment_controller_status"] = ctrl.get_status()
        except ImportError:
            components["deployment_controller"] = False
            issues.append("deployment_automation_controller module not available")

        ready = len(issues) == 0
        return {"ready": ready, "issues": issues, "components": components}

    # ------------------------------------------------------------------
    # Stage 2: Revenue Pipeline
    # ------------------------------------------------------------------

    def _check_revenue_stage(self) -> Dict[str, Any]:
        """Validate billing, subscriptions, and self-selling readiness."""
        issues: List[str] = []
        components: Dict[str, bool] = {}

        # SubscriptionManager
        try:
            from subscription_manager import PRICING_PLANS, SubscriptionManager
            mgr = SubscriptionManager()
            components["subscription_manager"] = True
            components["pricing_plans_count"] = len(PRICING_PLANS)
        except ImportError:
            components["subscription_manager"] = False
            issues.append("subscription_manager module not available")

        # PayPal credentials (primary provider)
        paypal_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        paypal_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        components["paypal_configured"] = bool(paypal_id and paypal_secret)
        if not components["paypal_configured"]:
            issues.append("PayPal credentials not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET)")

        # Coinbase Commerce (secondary / crypto)
        coinbase_key = os.environ.get("COINBASE_COMMERCE_API_KEY", "")
        components["coinbase_configured"] = bool(coinbase_key)
        # Coinbase is optional — no issue raised

        # Billing API router
        try:
            from billing.api import create_billing_router
            components["billing_api"] = True
        except ImportError:
            components["billing_api"] = False
            issues.append("billing.api module not available")

        # Self-selling engine
        try:
            from self_selling_engine._engine import ProspectProfile  # noqa: F401
            components["self_selling_engine"] = True
        except ImportError:
            components["self_selling_engine"] = False
            issues.append("self_selling_engine not available")

        ready = len(issues) == 0
        return {"ready": ready, "issues": issues, "components": components}

    # ------------------------------------------------------------------
    # Stage 3: Self-Automation Loop
    # ------------------------------------------------------------------

    def _check_self_automation_stage(self) -> Dict[str, Any]:
        """Validate the self-improvement and full-automation controllers."""
        issues: List[str] = []
        components: Dict[str, bool] = {}

        # SelfAutomationOrchestrator
        try:
            from self_automation_orchestrator import SelfAutomationOrchestrator
            orch = SelfAutomationOrchestrator(persistence_manager=self._persistence)
            status = orch.get_status()
            components["orchestrator"] = True
            components["orchestrator_status"] = status
        except ImportError:
            components["orchestrator"] = False
            issues.append("self_automation_orchestrator module not available")

        # FullAutomationController
        try:
            from full_automation_controller import FullAutomationController  # noqa: F401
            components["full_automation_controller"] = True
        except ImportError:
            components["full_automation_controller"] = False
            issues.append("full_automation_controller module not available")

        # Self-improvement engine (optional but desired)
        try:
            from self_improvement_engine import SelfImprovementEngine  # noqa: F401
            components["self_improvement_engine"] = True
        except ImportError:
            components["self_improvement_engine"] = False
            # Not a blocking issue — just a gap
            issues.append("self_improvement_engine not available (non-blocking)")

        ready = components.get("orchestrator", False) and components.get("full_automation_controller", False)
        return {"ready": ready, "issues": issues, "components": components}

    # ------------------------------------------------------------------
    # Next-step recommendations
    # ------------------------------------------------------------------

    def _compute_next_steps(
        self,
        deployment: Dict[str, Any],
        revenue: Dict[str, Any],
        automation: Dict[str, Any],
    ) -> List[str]:
        """Return ordered actionable next-step recommendations."""
        steps: List[str] = []

        # Deployment first
        if not deployment["ready"]:
            steps.append("Fix deployment issues before proceeding to revenue or automation")
            for issue in deployment["issues"]:
                steps.append(f"  → {issue}")
        else:
            steps.append("✓ Deployment stage is ready")

        # Revenue second
        if not revenue["ready"]:
            steps.append("Configure revenue pipeline:")
            for issue in revenue["issues"]:
                steps.append(f"  → {issue}")
        else:
            steps.append("✓ Revenue stage is ready — billing endpoints live")

        # Self-automation last
        if not automation["ready"]:
            steps.append("Enable self-automation:")
            for issue in automation["issues"]:
                steps.append(f"  → {issue}")
        else:
            steps.append("✓ Self-automation stage is ready — orchestrator and controller available")

        # Final activation step
        if deployment["ready"] and revenue["ready"] and automation["ready"]:
            steps.append("All stages ready — activate with: POST /api/automation/activate")

        return steps
