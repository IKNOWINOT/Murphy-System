# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: global_feedback/dispatcher.py
Subsystem: Global Feedback System
Design Label: GFB-002
Purpose: Orchestrates the full feedback lifecycle — collection, validation,
         categorisation, remediation planning, and GitHub repository_dispatch
         for automated patch creation.
Status: Production
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional httpx for GitHub API calls — graceful fallback when unavailable
try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

from .models import (
    FeedbackSeverity,
    FeedbackSource,
    GitHubPatchPayload,
    GlobalFeedbackStatus,
    GlobalFeedbackSubmission,
    RemediationPlan,
)
from .remediation_engine import RemediationEngine


class GlobalFeedbackDispatcher:
    """Orchestrates the global feedback pipeline.

    Design Label: GFB-002

    Lifecycle:
        submit → validate → categorise → analyse (remediation) →
        dispatch to GitHub → track resolution
    """

    def __init__(
        self,
        *,
        github_token: Optional[str] = None,
        github_owner: Optional[str] = None,
        github_repo: Optional[str] = None,
        max_store_size: int = 10_000,
    ) -> None:
        self._engine = RemediationEngine()
        self._store: Dict[str, GlobalFeedbackSubmission] = {}
        self._plans: Dict[str, RemediationPlan] = {}
        self._max_store = max_store_size

        # GitHub configuration — read from env with explicit overrides
        self._github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self._github_owner = github_owner or os.environ.get(
            "MURPHY_GITHUB_OWNER", "IKNOWINOT")
        self._github_repo = github_repo or os.environ.get(
            "MURPHY_GITHUB_REPO", "Murphy-System")

    # ------------------------------------------------------------------
    # 1. Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        *,
        user_id: str,
        title: str,
        description: str,
        severity: str = "medium",
        source: str = "website_widget",
        page_url: Optional[str] = None,
        component: Optional[str] = None,
        steps_to_reproduce: Optional[str] = None,
        expected_behavior: Optional[str] = None,
        actual_behavior: Optional[str] = None,
        console_errors: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> GlobalFeedbackSubmission:
        """Accept a new feedback submission and run the full pipeline.

        Returns the persisted :class:`GlobalFeedbackSubmission` with
        ``status`` updated through each pipeline stage.
        """
        submission = GlobalFeedbackSubmission(
            user_id=user_id,
            title=title,
            description=description,
            severity=FeedbackSeverity(severity),
            source=FeedbackSource(source),
            page_url=page_url,
            component=component,
            steps_to_reproduce=steps_to_reproduce,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            console_errors=console_errors,
            tags=tags or [],
            metadata=metadata or {},
            tenant_id=tenant_id,
            user_agent=user_agent,
        )

        # Evict oldest entries if store is full (CWE-770 bounded growth)
        if len(self._store) >= self._max_store:
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]

        self._store[submission.id] = submission
        logger.info("Feedback %s submitted by %s", submission.id, user_id)

        # Run pipeline stages
        submission.status = GlobalFeedbackStatus.VALIDATED
        plan = self._engine.analyse(submission)
        submission.status = GlobalFeedbackStatus.REMEDIATION_PLANNED
        submission.remediation_plan_id = plan.id
        self._plans[plan.id] = plan

        return submission

    # ------------------------------------------------------------------
    # 2. Dispatch to GitHub
    # ------------------------------------------------------------------

    def dispatch_to_github(self, feedback_id: str) -> Dict[str, Any]:
        """Trigger a ``repository_dispatch`` event on GitHub to begin patching.

        Returns a dict with dispatch status and metadata.
        """
        submission = self._store.get(feedback_id)
        if not submission:
            return {"success": False, "error": "Feedback not found"}

        plan_id = submission.remediation_plan_id
        plan = self._plans.get(plan_id) if plan_id else None
        if not plan:
            return {"success": False, "error": "No remediation plan for this feedback"}

        payload = GitHubPatchPayload(
            feedback_id=submission.id,
            remediation_plan_id=plan.id,
            title=submission.title,
            description=submission.description,
            severity=plan.severity_assessment,
            root_cause=plan.root_cause,
            affected_subsystem=plan.affected_subsystem,
            steps=[s.model_dump() for s in plan.steps],
            labels=self._compute_labels(submission, plan),
            metadata={
                "page_url": submission.page_url,
                "component": submission.component,
                "guiding_answers": plan.guiding_answers,
            },
        )

        # Attempt the actual GitHub API call
        dispatch_result = self._send_repository_dispatch(payload)

        if dispatch_result["success"]:
            submission.status = GlobalFeedbackStatus.DISPATCHED_TO_GITHUB
            logger.info(
                "Feedback %s dispatched to GitHub as repository_dispatch",
                feedback_id,
            )
        else:
            logger.warning(
                "GitHub dispatch failed for %s: %s",
                feedback_id, dispatch_result.get("error"),
            )

        return dispatch_result

    # ------------------------------------------------------------------
    # 3. Query helpers
    # ------------------------------------------------------------------

    def get(self, feedback_id: str) -> Optional[GlobalFeedbackSubmission]:
        """Retrieve a submission by ID."""
        return self._store.get(feedback_id)

    def get_plan(self, plan_id: str) -> Optional[RemediationPlan]:
        """Retrieve a remediation plan by ID."""
        return self._plans.get(plan_id)

    def get_plan_for_feedback(
        self, feedback_id: str,
    ) -> Optional[RemediationPlan]:
        """Retrieve the remediation plan associated with a feedback ID."""
        sub = self._store.get(feedback_id)
        if sub and sub.remediation_plan_id:
            return self._plans.get(sub.remediation_plan_id)
        return None

    def list_submissions(
        self,
        *,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent submissions as serialisable dicts."""
        items = list(self._store.values())
        if status:
            items = [i for i in items if i.status.value == status]
        if severity:
            items = [i for i in items if i.severity.value == severity]
        items = items[-limit:]
        return [
            {
                "id": i.id,
                "title": i.title,
                "severity": i.severity.value,
                "status": i.status.value,
                "submitted_at": i.submitted_at.isoformat(),
                "remediation_plan_id": i.remediation_plan_id,
                "github_issue_url": i.github_issue_url,
            }
            for i in items
        ]

    def stats(self) -> Dict[str, Any]:
        """Return aggregate statistics."""
        items = list(self._store.values())
        by_severity: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for i in items:
            by_severity[i.severity.value] = by_severity.get(
                i.severity.value, 0) + 1
            by_status[i.status.value] = by_status.get(
                i.status.value, 0) + 1
        return {
            "total": len(items),
            "by_severity": by_severity,
            "by_status": by_status,
            "plans_generated": len(self._plans),
        }

    def resolve(self, feedback_id: str, github_issue_url: Optional[str] = None) -> bool:
        """Mark feedback as resolved."""
        sub = self._store.get(feedback_id)
        if not sub:
            return False
        sub.status = GlobalFeedbackStatus.RESOLVED
        sub.resolved_at = datetime.now(timezone.utc)
        if github_issue_url:
            sub.github_issue_url = github_issue_url
        return True

    # ------------------------------------------------------------------
    # Internal: GitHub dispatch
    # ------------------------------------------------------------------

    def _send_repository_dispatch(
        self, payload: GitHubPatchPayload,
    ) -> Dict[str, Any]:
        """POST to GitHub ``/repos/{owner}/{repo}/dispatches``."""
        if not self._github_token:
            return {
                "success": False,
                "error": "GITHUB_TOKEN not configured",
                "payload": payload.model_dump(),
            }

        if not _HTTPX_AVAILABLE:
            logger.warning("httpx not installed — dispatch recorded but not sent")
            return {
                "success": True,
                "dispatched": False,
                "reason": "httpx_unavailable",
                "payload": payload.model_dump(),
            }

        url = (
            f"https://api.github.com/repos/"
            f"{self._github_owner}/{self._github_repo}/dispatches"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        body = {
            "event_type": "feedback_patch_request",
            "client_payload": payload.model_dump(),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=body, headers=headers)
            if resp.status_code in (200, 204):
                return {"success": True, "dispatched": True}
            return {
                "success": False,
                "error": f"GitHub API returned {resp.status_code}",
                "body": resp.text[:500],
            }
        except Exception as exc:
            logger.exception("GitHub dispatch failed for %s", payload.feedback_id)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal: label computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_labels(
        sub: GlobalFeedbackSubmission,
        plan: RemediationPlan,
    ) -> List[str]:
        """Derive GitHub issue labels from submission + plan."""
        labels = [
            "feedback-patch",
            f"severity:{plan.severity_assessment.value}",
            f"subsystem:{plan.affected_subsystem}",
        ]
        if sub.source:
            labels.append(f"source:{sub.source.value}")
        labels.extend(sub.tags[:5])  # cap imported tags
        return labels
