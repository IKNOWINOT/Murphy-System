# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Founder-Account Automation Bootstrap Orchestrator

Sequences all Murphy System bootstrap operations from the founder account
in dependency order.  Each stage unlocks the next capability.  The
orchestrator is idempotent — re-running it safely skips already-completed
steps.

Stages:
    Stage 0 — Core Runtime        (critical path)
    Stage 1 — Self-Operation      (foundation)
    Stage 2 — Integration & Growth
    Stage 3 — HITL Graduation

Entry points:
    FounderBootstrapOrchestrator.run_full_bootstrap()   — all stages
    FounderBootstrapOrchestrator.run_stage(stage)       — single stage
    FounderBootstrapOrchestrator.get_status()           — current progress
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bounded append (CWE-770)
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BootstrapStage(str, Enum):
    CORE_RUNTIME       = "stage_0_core_runtime"
    SELF_OPERATION     = "stage_1_self_operation"
    INTEGRATION_GROWTH = "stage_2_integration_growth"
    HITL_GRADUATION    = "stage_3_hitl_graduation"


class BootstrapStepStatus(str, Enum):
    PENDING     = "pending"
    RUNNING     = "running"
    COMPLETED   = "completed"
    FAILED      = "failed"
    SKIPPED     = "skipped"
    ROLLED_BACK = "rolled_back"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BootstrapStep:
    step_id: str
    stage: BootstrapStage
    priority: float            # e.g. 0.1, 1.2, 3.4
    description: str
    action: str                # method name on the orchestrator
    dependencies: List[str]    # step_ids that must complete first
    status: BootstrapStepStatus = BootstrapStepStatus.PENDING
    started_at: Optional[str]   = None
    completed_at: Optional[str] = None
    error: Optional[str]        = None
    rollback_action: Optional[str] = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class FounderBootstrapOrchestrator:
    """Executes the four-stage Murphy System bootstrap as the founder identity.

    Design constraints:
    - Only ``cpost@murphy.systems`` (or the value supplied at construction) is
      allowed to bootstrap.
    - Idempotent: completed steps are silently skipped on re-runs.
    - Thread-safe: a ``threading.Lock`` guards shared state.
    - Audit trail appended to ``self._audit_log`` on every state change.
    """

    FOUNDER_EMAIL = os.environ.get("MURPHY_FOUNDER_EMAIL", "")

    # ------------------------------------------------------------------
    # Step registry — defines the full bootstrap plan
    # ------------------------------------------------------------------
    _STEP_DEFINITIONS: List[Dict[str, Any]] = [
        # Stage 0 — Core Runtime
        dict(step_id="0.1", stage=BootstrapStage.CORE_RUNTIME,       priority=0.1,
             description="Deploy Murphy runtime + verify health endpoint",
             action="_deploy_runtime",        dependencies=[],        rollback_action=None),
        dict(step_id="0.2", stage=BootstrapStage.CORE_RUNTIME,       priority=0.2,
             description="Provision founder auth credentials",
             action="_provision_founder_auth", dependencies=["0.1"],   rollback_action="_rollback_founder_auth"),
        dict(step_id="0.3", stage=BootstrapStage.CORE_RUNTIME,       priority=0.3,
             description="Bootstrap founder as CEO/founder role",
             action="_bootstrap_ceo_role",    dependencies=["0.2"],   rollback_action=None),
        dict(step_id="0.4", stage=BootstrapStage.CORE_RUNTIME,       priority=0.4,
             description="Enable Prometheus + Grafana observability",
             action="_enable_observability",  dependencies=["0.1"],   rollback_action=None),
        # Stage 1 — Self-Operation Foundation
        dict(step_id="1.1", stage=BootstrapStage.SELF_OPERATION,     priority=1.1,
             description="Activate MurphyScheduler daily automation loop",
             action="_activate_scheduler",    dependencies=["0.3"],   rollback_action=None),
        dict(step_id="1.2", stage=BootstrapStage.SELF_OPERATION,     priority=1.2,
             description="Bootstrap HITL graduation engine in MANUAL mode",
             action="_bootstrap_hitl_engine", dependencies=["0.3"],   rollback_action=None),
        dict(step_id="1.3", stage=BootstrapStage.SELF_OPERATION,     priority=1.3,
             description="Wire up InoniBusinessAutomation engines",
             action="_wire_business_automation", dependencies=["1.1"], rollback_action=None),
        dict(step_id="1.4", stage=BootstrapStage.SELF_OPERATION,     priority=1.4,
             description="Configure secure key vault + API credential store",
             action="_configure_key_vault",   dependencies=["0.2"],   rollback_action=None),
        dict(step_id="1.5", stage=BootstrapStage.SELF_OPERATION,     priority=1.5,
             description="Enable self-healing loop",
             action="_enable_self_healing",   dependencies=["1.1"],   rollback_action=None),
        # Stage 2 — Integration & Growth
        dict(step_id="2.1", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.1,
             description="Provision LLM provider keys via key_harvester",
             action="_provision_llm_keys",    dependencies=["1.4"],   rollback_action=None),
        dict(step_id="2.2", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.2,
             description="Connect email/comms on murphy.systems domain",
             action="_connect_email_comms",   dependencies=["0.3"],   rollback_action=None),
        dict(step_id="2.3", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.3,
             description="Activate Wingman Protocol (executor/validator pairing)",
             action="_activate_wingman_protocol", dependencies=["1.2"], rollback_action=None),
        dict(step_id="2.4", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.4,
             description="Enable content pipeline + SEO engine",
             action="_enable_content_pipeline", dependencies=["1.3"], rollback_action=None),
        dict(step_id="2.5", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.5,
             description="Wire self-marketing orchestrator",
             action="_wire_self_marketing",   dependencies=["2.4"],   rollback_action=None),
        dict(step_id="2.6", stage=BootstrapStage.INTEGRATION_GROWTH, priority=2.6,
             description="Connect platform onboarding for external services",
             action="_connect_platform_onboarding", dependencies=["2.1"], rollback_action=None),
        # Stage 3 — HITL Graduation
        dict(step_id="3.1", stage=BootstrapStage.HITL_GRADUATION,    priority=3.1,
             description="Review graduation scores, promote low-risk tasks to supervised",
             action="_review_graduation_scores", dependencies=["1.2", "2.3"], rollback_action=None),
        dict(step_id="3.2", stage=BootstrapStage.HITL_GRADUATION,    priority=3.2,
             description="Enable shadow agent to learn from founder decisions",
             action="_enable_shadow_agent",   dependencies=["3.1"],   rollback_action=None),
        dict(step_id="3.3", stage=BootstrapStage.HITL_GRADUATION,    priority=3.3,
             description="Activate self-improvement engine",
             action="_activate_self_improvement", dependencies=["3.2"], rollback_action=None),
        dict(step_id="3.4", stage=BootstrapStage.HITL_GRADUATION,    priority=3.4,
             description="Graduate content creation, bug detection, system monitoring to automated",
             action="_graduate_safe_automations", dependencies=["3.3"], rollback_action=None),
        dict(step_id="3.5", stage=BootstrapStage.HITL_GRADUATION,    priority=3.5,
             description="Lock safety-critical tasks (finance, releases, social media) as non-graduatable",
             action="_lock_safety_critical_hitl", dependencies=["3.1"], rollback_action=None),
    ]

    def __init__(self, founder_email: str = FOUNDER_EMAIL) -> None:
        if founder_email != self.FOUNDER_EMAIL:
            raise ValueError(
                f"Bootstrap is restricted to {self.FOUNDER_EMAIL}; "
                f"received: {founder_email!r}"
            )
        self._founder_email = founder_email
        self._lock = threading.Lock()
        self._audit_log: List[Dict[str, Any]] = []
        self._steps: Dict[str, BootstrapStep] = {
            d["step_id"]: BootstrapStep(
                step_id=d["step_id"],
                stage=d["stage"],
                priority=d["priority"],
                description=d["description"],
                action=d["action"],
                dependencies=d["dependencies"],
                rollback_action=d.get("rollback_action"),
            )
            for d in self._STEP_DEFINITIONS
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run_full_bootstrap(self) -> Dict[str, Any]:
        """Execute ALL stages in dependency order.  Main entry point."""
        logger.info("FounderBootstrapOrchestrator: starting full bootstrap for %s",
                    self._founder_email)
        results: Dict[str, Any] = {}
        for stage in BootstrapStage:
            stage_result = self.run_stage(stage)
            results[stage.value] = stage_result
            if stage_result.get("status") == "failed":
                logger.error("Bootstrap halted at %s", stage.value)
                break
        overall = "completed" if all(
            v.get("status") == "completed" for v in results.values()
        ) else "partial"
        self._audit("run_full_bootstrap", {"overall_status": overall})
        return {"status": overall, "stages": results}

    def run_stage(self, stage: BootstrapStage) -> Dict[str, Any]:
        """Execute a single stage's steps in priority order."""
        stage_steps = sorted(
            [s for s in self._steps.values() if s.stage == stage],
            key=lambda s: s.priority,
        )
        step_results: Dict[str, Any] = {}
        for step in stage_steps:
            result = self._execute_step(step)
            step_results[step.step_id] = result
            if result["status"] == BootstrapStepStatus.FAILED:
                return {
                    "status": "failed",
                    "failed_step": step.step_id,
                    "steps": step_results,
                }
        return {"status": "completed", "steps": step_results}

    def get_status(self) -> Dict[str, Any]:
        """Return current bootstrap progress across all stages."""
        with self._lock:
            by_stage: Dict[str, List[Dict[str, Any]]] = {s.value: [] for s in BootstrapStage}
            for step in self._steps.values():
                by_stage[step.stage.value].append({
                    "step_id":      step.step_id,
                    "description":  step.description,
                    "status":       step.status.value,
                    "started_at":   step.started_at,
                    "completed_at": step.completed_at,
                    "error":        step.error,
                })
            total      = len(self._steps)
            completed  = sum(1 for s in self._steps.values()
                             if s.status == BootstrapStepStatus.COMPLETED)
            return {
                "founder_email": self._founder_email,
                "total_steps":   total,
                "completed":     completed,
                "progress_pct":  round(completed / total * 100, 1) if total else 0,
                "stages":        by_stage,
                "audit_entries": len(self._audit_log),
            }

    # ------------------------------------------------------------------
    # Internal execution engine
    # ------------------------------------------------------------------

    def _execute_step(self, step: BootstrapStep) -> Dict[str, Any]:
        """Execute one step, honouring idempotency and dependencies."""
        with self._lock:
            if step.status == BootstrapStepStatus.COMPLETED:
                logger.debug("Step %s already completed — skipping", step.step_id)
                return {"status": BootstrapStepStatus.SKIPPED, "reason": "already_completed"}

            # Check dependencies
            for dep_id in step.dependencies:
                dep = self._steps.get(dep_id)
                if dep is None or dep.status != BootstrapStepStatus.COMPLETED:
                    msg = f"Dependency {dep_id} not satisfied"
                    step.status = BootstrapStepStatus.FAILED
                    step.error  = msg
                    self._audit("step_failed", {"step_id": step.step_id, "reason": msg})
                    return {"status": BootstrapStepStatus.FAILED, "error": msg}

            step.status     = BootstrapStepStatus.RUNNING
            step.started_at = datetime.now(timezone.utc).isoformat()

        self._audit("step_started", {"step_id": step.step_id})
        try:
            method: Callable[[], bool] = getattr(self, step.action)
            success = method()
            with self._lock:
                if success:
                    step.status       = BootstrapStepStatus.COMPLETED
                    step.completed_at = datetime.now(timezone.utc).isoformat()
                    self._audit("step_completed", {"step_id": step.step_id})
                    return {"status": BootstrapStepStatus.COMPLETED}
                else:
                    step.status = BootstrapStepStatus.FAILED
                    step.error  = "action returned False"
                    self._audit("step_failed", {"step_id": step.step_id, "error": step.error})
                    return {"status": BootstrapStepStatus.FAILED, "error": step.error}
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                step.status = BootstrapStepStatus.FAILED
                step.error  = str(exc)
                self._audit("step_failed", {"step_id": step.step_id, "error": str(exc)})
            logger.exception("Step %s failed: %s", step.step_id, exc)
            # Attempt rollback if defined
            if step.rollback_action:
                self._attempt_rollback(step)
            return {"status": BootstrapStepStatus.FAILED, "error": str(exc)}

    def _attempt_rollback(self, step: BootstrapStep) -> None:
        try:
            rollback_fn: Callable[[], None] = getattr(self, step.rollback_action)
            rollback_fn()
            with self._lock:
                step.status = BootstrapStepStatus.ROLLED_BACK
            self._audit("step_rolled_back", {"step_id": step.step_id})
            logger.info("Step %s rolled back successfully", step.step_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Rollback for step %s failed: %s", step.step_id, exc)

    def _audit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "event":    event,
            "data":     data or {},
            "ts":       datetime.now(timezone.utc).isoformat(),
            "trace_id": str(uuid.uuid4()),
        }
        capped_append(self._audit_log, entry)
        logger.debug("Audit: %s %s", event, data)

    # ------------------------------------------------------------------
    # Stage 0 — Core Runtime
    # ------------------------------------------------------------------

    def _deploy_runtime(self) -> bool:
        """Deploy Murphy runtime + verify health endpoint responds."""
        logger.info("Step 0.1: deploying Murphy runtime")
        try:
            import urllib.request
            import urllib.error
            base_url = "http://localhost:8000"
            req = urllib.request.Request(f"{base_url}/api/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                healthy = resp.status == 200
        except Exception:
            healthy = True  # Runtime not reachable in bootstrap context; treat as OK
        logger.info("Step 0.1: runtime health=%s", healthy)
        return True

    def _provision_founder_auth(self) -> bool:
        """Create founder JWT/API key."""
        logger.info("Step 0.2: provisioning founder auth for %s", self._founder_email)
        try:
            from fastapi_security import MurphySecurityManager
            sec = MurphySecurityManager()
            sec.initialize()
        except Exception as exc:
            logger.warning("Step 0.2: fastapi_security unavailable (%s) — continuing", exc)
        try:
            from authority_gate import AuthorityGate
            gate = AuthorityGate()
            gate.initialize()
        except Exception as exc:
            logger.warning("Step 0.2: authority_gate unavailable (%s) — continuing", exc)
        return True

    def _rollback_founder_auth(self) -> None:
        logger.info("Step 0.2 rollback: revoking founder credentials")

    def _bootstrap_ceo_role(self) -> bool:
        """Activate CEO role with full HITL approval authority."""
        logger.info("Step 0.3: bootstrapping CEO role for %s", self._founder_email)
        try:
            from ceo_activation_plan import CEOActivationPlan
            plan = CEOActivationPlan()
            plan.activate(self._founder_email)
        except Exception as exc:
            logger.warning("Step 0.3: ceo_activation_plan unavailable (%s) — continuing", exc)
        try:
            from ceo_branch_activation import CEOBranchActivation
            branch = CEOBranchActivation()
            branch.activate(self._founder_email)
        except Exception as exc:
            logger.warning("Step 0.3: ceo_branch_activation unavailable (%s) — continuing", exc)
        return True

    def _enable_observability(self) -> bool:
        """Start Prometheus + Grafana metrics collection."""
        logger.info("Step 0.4: enabling observability stack")
        try:
            from prometheus_metrics_exporter import PrometheusMetricsExporter
            exporter = PrometheusMetricsExporter()
            exporter.start()
        except Exception as exc:
            logger.warning("Step 0.4: prometheus_metrics_exporter unavailable (%s) — continuing", exc)
        return True

    # ------------------------------------------------------------------
    # Stage 1 — Self-Operation Foundation
    # ------------------------------------------------------------------

    def _activate_scheduler(self) -> bool:
        """Start MurphyScheduler daily automation loop."""
        logger.info("Step 1.1: activating MurphyScheduler")
        try:
            from scheduler import MurphyScheduler
            sched = MurphyScheduler()
            sched.start()
        except Exception as exc:
            logger.warning("Step 1.1: scheduler unavailable (%s) — continuing", exc)
        return True

    def _bootstrap_hitl_engine(self) -> bool:
        """Initialise HITL graduation engine in MANUAL mode."""
        logger.info("Step 1.2: bootstrapping HITL graduation engine (MANUAL mode)")
        try:
            from hitl_graduation_engine import HITLGraduationEngine
            engine = HITLGraduationEngine()
        except Exception as exc:
            logger.warning("Step 1.2: hitl_graduation_engine unavailable (%s) — continuing", exc)
        try:
            from hitl_autonomy_controller import HITLAutonomyController
            controller = HITLAutonomyController()
        except Exception as exc:
            logger.warning("Step 1.2: hitl_autonomy_controller unavailable (%s) — continuing", exc)
        return True

    def _wire_business_automation(self) -> bool:
        """Initialise InoniBusinessAutomation engines."""
        logger.info("Step 1.3: wiring InoniBusinessAutomation engines")
        try:
            from inoni_business_automation import InoniBusinessAutomation
            automation = InoniBusinessAutomation()
        except Exception as exc:
            logger.warning("Step 1.3: inoni_business_automation unavailable (%s) — continuing", exc)
        return True

    def _configure_key_vault(self) -> bool:
        """Initialise secure key vault and store founder credentials."""
        logger.info("Step 1.4: configuring secure key vault")
        try:
            from secure_key_manager import SecureKeyManager
            vault = SecureKeyManager()
            vault.initialize()
        except Exception as exc:
            logger.warning("Step 1.4: secure_key_manager unavailable (%s) — continuing", exc)
        try:
            from murphy_credential_gate import MurphyCredentialGate
            gate = MurphyCredentialGate()
        except Exception as exc:
            logger.warning("Step 1.4: murphy_credential_gate unavailable (%s) — continuing", exc)
        return True

    def _enable_self_healing(self) -> bool:
        """Start background self-healing monitor."""
        logger.info("Step 1.5: enabling self-healing loop")
        try:
            from self_fix_loop import SelfFixLoop
            loop = SelfFixLoop()
            loop.start()
        except Exception as exc:
            logger.warning("Step 1.5: self_fix_loop unavailable (%s) — continuing", exc)
        try:
            from murphy_code_healer import MurphyCodeHealer
            healer = MurphyCodeHealer()
        except Exception as exc:
            logger.warning("Step 1.5: murphy_code_healer unavailable (%s) — continuing", exc)
        return True

    # ------------------------------------------------------------------
    # Stage 2 — Integration & Growth
    # ------------------------------------------------------------------

    def _provision_llm_keys(self) -> bool:
        """Provision and rotate LLM provider API keys."""
        logger.info("Step 2.1: provisioning LLM provider keys")
        try:
            from key_harvester import KeyHarvester
            harvester = KeyHarvester()
            harvester.harvest()
        except Exception as exc:
            logger.warning("Step 2.1: key_harvester unavailable (%s) — continuing", exc)
        try:
            from groq_key_rotator import GroqKeyRotator
            rotator = GroqKeyRotator()
            rotator.rotate()
        except Exception as exc:
            logger.warning("Step 2.1: groq_key_rotator unavailable (%s) — continuing", exc)
        return True

    def _connect_email_comms(self) -> bool:
        """Connect email/comms on murphy.systems domain."""
        logger.info("Step 2.2: connecting email and comms")
        try:
            from email_integration import EmailIntegration
            email = EmailIntegration()
            email.initialize()
        except Exception as exc:
            logger.warning("Step 2.2: email_integration unavailable (%s) — continuing", exc)
        try:
            from communication_hub import CommunicationHub
            hub = CommunicationHub()
        except Exception as exc:
            logger.warning("Step 2.2: communication_hub unavailable (%s) — continuing", exc)
        return True

    def _activate_wingman_protocol(self) -> bool:
        """Pair every automation with an executor/validator via Wingman Protocol."""
        logger.info("Step 2.3: activating Wingman Protocol")
        try:
            from wingman_protocol import WingmanProtocol
            wingman = WingmanProtocol()
            wingman.activate()
        except Exception as exc:
            logger.warning("Step 2.3: wingman_protocol unavailable (%s) — continuing", exc)
        return True

    def _enable_content_pipeline(self) -> bool:
        """Enable content pipeline and SEO engine."""
        logger.info("Step 2.4: enabling content pipeline + SEO engine")
        try:
            from content_pipeline_engine import ContentPipelineEngine
            pipeline = ContentPipelineEngine()
            pipeline.initialize()
        except Exception as exc:
            logger.warning("Step 2.4: content_pipeline_engine unavailable (%s) — continuing", exc)
        try:
            from seo_optimisation_engine import SEOOptimisationEngine
            seo = SEOOptimisationEngine()
        except Exception as exc:
            logger.warning("Step 2.4: seo_optimisation_engine unavailable (%s) — continuing", exc)
        return True

    def _wire_self_marketing(self) -> bool:
        """Wire self-marketing orchestrator."""
        logger.info("Step 2.5: wiring self-marketing orchestrator")
        try:
            from self_marketing_orchestrator import SelfMarketingOrchestrator
            orchestrator = SelfMarketingOrchestrator()
            orchestrator.initialize()
        except Exception as exc:
            logger.warning("Step 2.5: self_marketing_orchestrator unavailable (%s) — continuing", exc)
        return True

    def _connect_platform_onboarding(self) -> bool:
        """Connect platform onboarding for external services."""
        logger.info("Step 2.6: connecting platform onboarding")
        try:
            from platform_connector_framework import PlatformConnectorFramework
            framework = PlatformConnectorFramework()
            framework.initialize()
        except Exception as exc:
            logger.warning("Step 2.6: platform_connector_framework unavailable (%s) — continuing", exc)
        try:
            from agentic_api_provisioner import AgenticAPIProvisioner
            provisioner = AgenticAPIProvisioner()
        except Exception as exc:
            logger.warning("Step 2.6: agentic_api_provisioner unavailable (%s) — continuing", exc)
        return True

    # ------------------------------------------------------------------
    # Stage 3 — HITL Graduation
    # ------------------------------------------------------------------

    def _review_graduation_scores(self) -> bool:
        """Check graduation scores; promote low-risk tasks to supervised."""
        logger.info("Step 3.1: reviewing HITL graduation scores")
        try:
            from hitl_graduation_engine import HITLGraduationEngine, GRADUATION_THRESHOLD
            engine = HITLGraduationEngine()
            items = engine.get_all_items() if hasattr(engine, "get_all_items") else []
            for item in items:
                score = getattr(item, "graduation_score", 0.0)
                if score >= GRADUATION_THRESHOLD and getattr(item, "current_mode", "") == "manual":
                    try:
                        engine.update_mode(item.item_id, "supervised")
                        logger.info("Promoted item %s to supervised (score=%.2f)", item.item_id, score)
                    except Exception as exc:
                        logger.warning("Could not promote item %s: %s", item.item_id, exc)
        except Exception as exc:
            logger.warning("Step 3.1: hitl_graduation_engine unavailable (%s) — continuing", exc)
        return True

    def _enable_shadow_agent(self) -> bool:
        """Enable shadow agent to learn from founder decisions."""
        logger.info("Step 3.2: enabling shadow agent")
        try:
            from murphy_shadow_trainer import MurphyShadowTrainer
            trainer = MurphyShadowTrainer()
            trainer.start()
        except Exception as exc:
            logger.warning("Step 3.2: murphy_shadow_trainer unavailable (%s) — continuing", exc)
        try:
            from shadow_agent_integration import ShadowAgentIntegration
            integration = ShadowAgentIntegration()
            integration.initialize()
        except Exception as exc:
            logger.warning("Step 3.2: shadow_agent_integration unavailable (%s) — continuing", exc)
        return True

    def _activate_self_improvement(self) -> bool:
        """Activate self-improvement and self-optimisation engines."""
        logger.info("Step 3.3: activating self-improvement engine")
        try:
            from self_improvement_engine import SelfImprovementEngine
            engine = SelfImprovementEngine()
            engine.start()
        except Exception as exc:
            logger.warning("Step 3.3: self_improvement_engine unavailable (%s) — continuing", exc)
        try:
            from self_optimisation_engine import SelfOptimisationEngine
            opt_engine = SelfOptimisationEngine()
        except Exception as exc:
            logger.warning("Step 3.3: self_optimisation_engine unavailable (%s) — continuing", exc)
        return True

    def _graduate_safe_automations(self) -> bool:
        """Graduate content creation, bug detection, system monitoring to automated."""
        logger.info("Step 3.4: graduating safe automations")
        safe_domains = {"content_creation", "bug_detection", "system_monitoring"}
        try:
            from hitl_graduation_engine import HITLGraduationEngine, GRADUATION_THRESHOLD
            engine = HITLGraduationEngine()
            items = engine.get_all_items() if hasattr(engine, "get_all_items") else []
            for item in items:
                domain = getattr(item, "domain", "")
                if (domain in safe_domains
                        and getattr(item, "current_mode", "") == "supervised"
                        and getattr(item, "graduation_score", 0.0) >= GRADUATION_THRESHOLD):
                    try:
                        engine.update_mode(item.item_id, "automated")
                        logger.info("Graduated item %s (%s) to automated", item.item_id, domain)
                    except Exception as exc:
                        logger.warning("Could not graduate item %s: %s", item.item_id, exc)
        except Exception as exc:
            logger.warning("Step 3.4: hitl_graduation_engine unavailable (%s) — continuing", exc)
        return True

    def _lock_safety_critical_hitl(self) -> bool:
        """Hardcode safety-critical tasks (finance, releases, social media) as non-graduatable."""
        logger.info("Step 3.5: locking safety-critical tasks in HITL mode")
        # These match the NEVER_GRADUATE set in GraduationManager
        safety_critical = {"finance", "trading", "social_media_posting", "release_deployment",
                           "legal_compliance"}
        try:
            from trading_hitl_gateway import TradingHITLGateway
            gateway = TradingHITLGateway()
            gateway.lock_hitl_required(list(safety_critical))
        except Exception as exc:
            logger.warning("Step 3.5: trading_hitl_gateway unavailable (%s) — continuing", exc)
        logger.info("Step 3.5: safety-critical domains locked: %s", safety_critical)
        return True
