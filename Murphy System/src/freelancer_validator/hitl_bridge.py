"""
Freelancer Validator — HITL Bridge

Connects the freelancer validation workflow to the existing
``HumanInTheLoopMonitor`` so that intervention requests can be
dispatched to freelance platforms and responses flow back as
``InterventionResponse`` objects the rest of the system already knows
how to consume.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .budget_manager import BudgetManager
from .credential_verifier import CredentialVerifier
from .criteria_engine import CriteriaEngine
from .models import (
    BudgetConfig,
    Credential,
    CredentialRequirement,
    FreelancerResponse,
    FreelancerTask,
    PlatformType,
    ResponseVerdict,
    TaskStatus,
    ValidationCriteria,
)
from .platform_client import (
    FiverrClient,
    FreelancerPlatformClient,
    GenericFreelancerClient,
    UpworkClient,
)

logger = logging.getLogger(__name__)


class FreelancerHITLBridge:
    """
    Orchestrates the full lifecycle:

    1. Receive an HITL ``InterventionRequest``
    2. Build structured criteria + task
    3. Check org budget
    4. Post to the selected freelance platform
    5. (Async) collect the freelancer's response
    6. Score the response against criteria
    7. Translate into an ``InterventionResponse`` and feed it back
       to the ``HumanInTheLoopMonitor``
    """

    def __init__(
        self,
        hitl_monitor: Any = None,
        default_platform: PlatformType = PlatformType.GENERIC,
    ) -> None:
        self.hitl_monitor = hitl_monitor
        self.budget_manager = BudgetManager()
        self.criteria_engine = CriteriaEngine()
        self.credential_verifier = CredentialVerifier()

        # Platform clients keyed by PlatformType
        self._clients: Dict[PlatformType, FreelancerPlatformClient] = {
            PlatformType.FIVERR: FiverrClient(),
            PlatformType.UPWORK: UpworkClient(),
            PlatformType.GENERIC: GenericFreelancerClient(),
        }
        self.default_platform = default_platform

        # Task registry
        self._tasks: Dict[str, FreelancerTask] = {}

    # ── Configuration ────────────────────────────────────────────────

    def register_org_budget(self, config: BudgetConfig) -> None:
        """Register an organization's budget for HITL tasks."""
        self.budget_manager.register_org(config)

    def register_platform_client(
        self, platform: PlatformType, client: FreelancerPlatformClient
    ) -> None:
        """Replace or add a platform client."""
        self._clients[platform] = client

    # ── Dispatch ─────────────────────────────────────────────────────

    async def dispatch_validation(
        self,
        hitl_request_id: str,
        org_id: str,
        title: str,
        instructions: str,
        payload: Dict[str, Any],
        criteria: ValidationCriteria,
        budget_cents: int = 1000,
        platform: Optional[PlatformType] = None,
        deadline_hours: int = 24,
        required_credentials: Optional[List[CredentialRequirement]] = None,
    ) -> FreelancerTask:
        """
        Create and post a validation task to a freelance platform.

        Raises ``ValueError`` if the budget check fails.
        """
        platform = platform or self.default_platform

        # Budget gate
        if not self.budget_manager.authorize_spend(org_id, budget_cents):
            raise ValueError(
                f"Budget exceeded for org={org_id} amount={budget_cents}"
            )

        task = FreelancerTask(
            hitl_request_id=hitl_request_id,
            org_id=org_id,
            platform=platform,
            title=title,
            instructions=instructions,
            payload=payload,
            criteria=criteria,
            budget_cents=budget_cents,
            deadline_hours=deadline_hours,
            required_credentials=required_credentials or [],
        )

        client = self._clients.get(platform)
        if client is None:
            raise ValueError(f"No client registered for platform={platform}")

        task = await client.post_task(task)

        # Record spend once successfully posted
        self.budget_manager.record_spend(org_id, task.task_id, budget_cents)

        self._tasks[task.task_id] = task
        logger.info(
            "Dispatched validation: task=%s platform=%s hitl=%s budget=$%.2f",
            task.task_id,
            platform.value,
            hitl_request_id,
            budget_cents / 100,
        )
        return task

    # ── Response ingestion ───────────────────────────────────────────

    async def ingest_response(
        self,
        response: FreelancerResponse,
        validator_credentials: Optional[List[Credential]] = None,
    ) -> Dict[str, Any]:
        """
        Receive a freelancer response, score it, and wire the result
        back into the HITL monitor as an ``InterventionResponse``.

        If the originating task has ``required_credentials``, the
        validator's credentials are checked before acceptance.

        Returns a summary dict with verdict, score, and HITL response ID.
        """
        task = self._tasks.get(response.task_id)
        if task is None:
            raise ValueError(f"Unknown task_id: {response.task_id}")

        # Credential gate
        credential_check: Optional[Dict[str, Any]] = None
        if task.required_credentials:
            creds = validator_credentials or []
            credential_check = await self.credential_verifier.verify_for_task(
                validator_id=response.validator_id,
                credentials=creds,
                requirements=task.required_credentials,
            )
            if not credential_check["eligible"]:
                logger.warning(
                    "Validator %s failed credential check for task %s: %s",
                    response.validator_id,
                    task.task_id,
                    credential_check["unmet"],
                )
                return {
                    "task_id": response.task_id,
                    "response_id": response.response_id,
                    "verdict": "credential_rejected",
                    "overall_score": 0.0,
                    "hitl_response_id": None,
                    "format_errors": [],
                    "credential_check": credential_check,
                }

        # Validate and score
        errors = CriteriaEngine.validate_response_format(
            response, task.criteria
        )
        if errors:
            logger.warning(
                "Response %s has format errors: %s",
                response.response_id,
                errors,
            )

        scored = self.criteria_engine.score_response(response, task.criteria)

        # Update task status
        task.status = TaskStatus.ACCEPTED
        task.updated_at = datetime.now(timezone.utc)

        # Wire into HITL monitor
        hitl_response_id = None
        if self.hitl_monitor is not None:
            try:
                hitl_resp = self.hitl_monitor.respond_to_intervention(
                    request_id=scored.hitl_request_id,
                    approved=(scored.verdict == ResponseVerdict.PASS),
                    decision=scored.verdict.value,
                    responded_by=f"freelancer:{scored.validator_id}",
                    feedback=scored.feedback,
                    corrections=None,
                    modifications=scored.evidence,
                )
                hitl_response_id = hitl_resp.response_id
                logger.info(
                    "HITL response wired: hitl_resp=%s verdict=%s score=%.2f",
                    hitl_response_id,
                    scored.verdict.value,
                    scored.overall_score,
                )
            except Exception as exc:
                logger.error("Failed to wire HITL response: %s", exc)

        return {
            "task_id": response.task_id,
            "response_id": response.response_id,
            "verdict": scored.verdict.value,
            "overall_score": scored.overall_score,
            "hitl_response_id": hitl_response_id,
            "format_errors": errors,
            "credential_check": credential_check,
        }

    # ── Query ────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[FreelancerTask]:
        """Look up a dispatched task."""
        return self._tasks.get(task_id)

    def list_tasks(
        self, org_id: Optional[str] = None, status: Optional[TaskStatus] = None
    ) -> List[FreelancerTask]:
        """List tasks, optionally filtered by org and/or status."""
        tasks = list(self._tasks.values())
        if org_id:
            tasks = [t for t in tasks if t.org_id == org_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_budget_balance(self, org_id: str) -> Dict[str, int]:
        """Return the org's current budget balance."""
        return self.budget_manager.get_balance(org_id)
