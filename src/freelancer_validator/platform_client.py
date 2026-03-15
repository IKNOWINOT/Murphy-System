"""
Freelancer Validator — Platform Clients

Abstract client interface plus concrete adapters for Fiverr, Upwork,
and a generic fallback.  Each adapter translates FreelancerTask into
the platform's posting format and polls/receives deliverables.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from .models import (
    FreelancerResponse,
    FreelancerTask,
    PlatformType,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class FreelancerPlatformClient(ABC):
    """
    Abstract client for posting tasks and retrieving responses
    from a freelance marketplace.

    Concrete subclasses implement the actual HTTP/API layer for each
    platform.  In development/test mode the base class can be
    instantiated directly and will operate in *dry-run* mode.
    """

    platform: PlatformType = PlatformType.GENERIC

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._api_key: Optional[str] = self.config.get("api_key")
        self._base_url: str = self.config.get("base_url", "")
        self._posted_tasks: Dict[str, FreelancerTask] = {}

    # ── Public interface ─────────────────────────────────────────────

    @abstractmethod
    async def post_task(self, task: FreelancerTask) -> FreelancerTask:
        """
        Post a validation task to the platform.

        Returns the task with ``platform_task_id`` and ``status`` updated.
        """

    @abstractmethod
    async def check_status(self, task: FreelancerTask) -> TaskStatus:
        """Poll the platform for the current task status."""

    @abstractmethod
    async def retrieve_response(
        self, task: FreelancerTask
    ) -> Optional[FreelancerResponse]:
        """
        Retrieve the validator's structured response once the task is
        marked *submitted* on the platform.
        """

    @abstractmethod
    async def cancel_task(self, task: FreelancerTask) -> bool:
        """Cancel a posted task.  Returns True on success."""

    # ── Helpers ──────────────────────────────────────────────────────

    def _build_posting_payload(self, task: FreelancerTask) -> Dict[str, Any]:
        """Build the platform-agnostic posting payload."""
        criteria_text = "\n".join(
            f"- [{c.criterion_id}] {c.name}: {c.description} "
            f"(type={c.scoring_type}, required={c.required})"
            for c in task.criteria.items
        )
        return {
            "title": task.title,
            "description": (
                f"{task.instructions}\n\n"
                f"## Evaluation Criteria\n{criteria_text}\n\n"
                f"## Response Format\n"
                "Return a JSON object with:\n"
                '  "verdict": "pass" | "fail" | "needs_revision" | "inconclusive",\n'
                '  "criterion_scores": [{criterion_id, value, notes}],\n'
                '  "feedback": "...",\n'
                '  "evidence": {...}\n'
            ),
            "budget_cents": task.budget_cents,
            "deadline_hours": task.deadline_hours,
            "payload": task.payload,
            "metadata": {
                "murphy_task_id": task.task_id,
                "hitl_request_id": task.hitl_request_id,
            },
        }


# ── Fiverr adapter ───────────────────────────────────────────────────────


class FiverrClient(FreelancerPlatformClient):
    """Adapter for the Fiverr Business API."""

    platform = PlatformType.FIVERR

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._base_url = self.config.get(
            "base_url", "https://api.fiverr.com/v1"
        )

    async def post_task(self, task: FreelancerTask) -> FreelancerTask:
        payload = self._build_posting_payload(task)
        logger.info("Fiverr: posting task %s — %s", task.task_id, task.title)

        # In production this calls the Fiverr Business API.
        # For now we simulate a successful post.
        task.platform_task_id = f"fvr_{uuid4().hex[:10]}"
        task.status = TaskStatus.POSTED
        task.updated_at = datetime.now(timezone.utc)
        self._posted_tasks[task.task_id] = task
        return task

    async def check_status(self, task: FreelancerTask) -> TaskStatus:
        logger.debug("Fiverr: checking status for %s", task.task_id)
        return task.status

    async def retrieve_response(
        self, task: FreelancerTask
    ) -> Optional[FreelancerResponse]:
        if task.status != TaskStatus.SUBMITTED:
            return None
        # In production: GET /orders/{platform_task_id}/delivery
        return None  # pragma: no cover — production path

    async def cancel_task(self, task: FreelancerTask) -> bool:
        logger.info("Fiverr: cancelling task %s", task.task_id)
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        return True


# ── Upwork adapter ───────────────────────────────────────────────────────


class UpworkClient(FreelancerPlatformClient):
    """Adapter for the Upwork API."""

    platform = PlatformType.UPWORK

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._base_url = self.config.get(
            "base_url", "https://www.upwork.com/api/v3"
        )

    async def post_task(self, task: FreelancerTask) -> FreelancerTask:
        payload = self._build_posting_payload(task)
        logger.info("Upwork: posting task %s — %s", task.task_id, task.title)

        task.platform_task_id = f"upw_{uuid4().hex[:10]}"
        task.status = TaskStatus.POSTED
        task.updated_at = datetime.now(timezone.utc)
        self._posted_tasks[task.task_id] = task
        return task

    async def check_status(self, task: FreelancerTask) -> TaskStatus:
        logger.debug("Upwork: checking status for %s", task.task_id)
        return task.status

    async def retrieve_response(
        self, task: FreelancerTask
    ) -> Optional[FreelancerResponse]:
        if task.status != TaskStatus.SUBMITTED:
            return None
        return None  # pragma: no cover — production path

    async def cancel_task(self, task: FreelancerTask) -> bool:
        logger.info("Upwork: cancelling task %s", task.task_id)
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        return True


# ── Generic / fallback adapter ───────────────────────────────────────────


class GenericFreelancerClient(FreelancerPlatformClient):
    """
    Fallback client that stores tasks locally.

    Useful for testing, self-hosted validation queues, or platforms
    without a public API.
    """

    platform = PlatformType.GENERIC

    async def post_task(self, task: FreelancerTask) -> FreelancerTask:
        logger.info("Generic: posting task %s locally", task.task_id)
        task.platform_task_id = f"gen_{uuid4().hex[:10]}"
        task.status = TaskStatus.POSTED
        task.updated_at = datetime.now(timezone.utc)
        self._posted_tasks[task.task_id] = task
        return task

    async def check_status(self, task: FreelancerTask) -> TaskStatus:
        return task.status

    async def retrieve_response(
        self, task: FreelancerTask
    ) -> Optional[FreelancerResponse]:
        if task.status != TaskStatus.SUBMITTED:
            return None
        return None

    async def cancel_task(self, task: FreelancerTask) -> bool:
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        return True
