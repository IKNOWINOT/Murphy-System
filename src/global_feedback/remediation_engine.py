# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: global_feedback/remediation_engine.py
Subsystem: Global Feedback System
Design Label: GFB-003
Purpose: Analyse feedback submissions against the seven guiding-principle
         questions and produce structured remediation plans.
Status: Production

Guiding Principles (commissioning questions):
    Q1  Does the module do what it was designed to do?
    Q2  What exactly is the module supposed to do (design-intent clarity)?
    Q3  What conditions are possible based on the module?
    Q4  Does the test profile reflect the full range of capabilities?
    Q5  What is the expected result at all points of operation?
    Q6  What is the actual result?
    Q7  If problems remain, how do we restart from symptoms back through
        validation?  Has ancillary code / docs been updated?  Has hardening
        been applied?  Has the module been recommissioned?
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .models import (
    FeedbackSeverity,
    GlobalFeedbackSubmission,
    RemediationPlan,
    RemediationStep,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword → subsystem mapping for automated triage
# ---------------------------------------------------------------------------
_SUBSYSTEM_KEYWORDS: Dict[str, List[str]] = {
    "ui_frontend": ["button", "page", "css", "layout", "render", "display",
                     "widget", "modal", "toast", "form", "click", "hover",
                     "responsive", "theme", "font", "colour", "color"],
    "api_backend": ["endpoint", "api", "request", "response", "500", "404",
                    "timeout", "cors", "json", "payload", "header"],
    "authentication": ["login", "logout", "password", "token", "jwt",
                       "session", "auth", "permission", "access denied"],
    "automation": ["workflow", "automation", "trigger", "schedule", "cron",
                   "loop", "tick", "campaign", "milestone"],
    "data_persistence": ["database", "sql", "query", "migration", "data",
                         "storage", "cache", "redis", "lost data"],
    "integration": ["llm", "ai", "model", "connector", "webhook", "matrix",
                    "email", "smtp", "external service"],
    "security": ["vulnerability", "xss", "injection", "csrf", "exploit",
                 "unsafe", "certificate", "encryption"],
    "performance": ["slow", "latency", "memory", "cpu", "leak", "freeze",
                    "hang", "unresponsive", "timeout"],
}

# ---------------------------------------------------------------------------
# Severity escalation keywords
# ---------------------------------------------------------------------------
_SEVERITY_ESCALATORS: Dict[FeedbackSeverity, List[str]] = {
    FeedbackSeverity.CRITICAL: ["crash", "data loss", "security breach",
                                "production down", "exploit", "vulnerability"],
    FeedbackSeverity.HIGH: ["broken", "cannot", "blocker", "error 500",
                            "regression", "fails every time"],
}


class RemediationEngine:
    """Analyses feedback and produces remediation plans.

    Design Label: GFB-003

    The engine applies each of the seven guiding questions to the feedback
    content and builds a structured :class:`RemediationPlan` with concrete
    steps, root-cause hypothesis, and hardening recommendations.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(self, submission: GlobalFeedbackSubmission) -> RemediationPlan:
        """Run full analysis on *submission* and return a remediation plan.

        Steps:
            1. Identify affected subsystem via keyword matching.
            2. Assess / escalate severity.
            3. Answer each guiding question.
            4. Generate remediation steps.
            5. Build the plan object.
        """
        subsystem = self._identify_subsystem(submission)
        severity = self._assess_severity(submission)
        guiding = self._answer_guiding_questions(submission, subsystem)
        steps = self._generate_steps(submission, subsystem, guiding)
        conditions = self._identify_conditions(submission)

        expected_vs_actual = None
        if submission.expected_behavior and submission.actual_behavior:
            expected_vs_actual = (
                f"Expected: {submission.expected_behavior}  |  "
                f"Actual: {submission.actual_behavior}"
            )

        plan = RemediationPlan(
            feedback_id=submission.id,
            root_cause=guiding.get("Q1", "Under investigation"),
            affected_subsystem=subsystem,
            severity_assessment=severity,
            conditions_identified=conditions,
            expected_vs_actual=expected_vs_actual,
            steps=steps,
            hardening_applied=False,
            documentation_updated=False,
            recommission_required=severity in (
                FeedbackSeverity.CRITICAL, FeedbackSeverity.HIGH),
            guiding_answers=guiding,
        )

        logger.info(
            "Remediation plan %s generated for feedback %s (subsystem=%s, severity=%s, steps=%d)",
            plan.id, submission.id, subsystem, severity.value, len(steps),
        )
        return plan

    # ------------------------------------------------------------------
    # Subsystem identification
    # ------------------------------------------------------------------

    def _identify_subsystem(self, sub: GlobalFeedbackSubmission) -> str:
        """Return best-guess subsystem from content keywords."""
        if sub.affected_modules:
            return sub.affected_modules[0]

        text = f"{sub.title} {sub.description}".lower()
        if sub.component:
            text += f" {sub.component}".lower()

        scores: Dict[str, int] = {}
        for subsystem, keywords in _SUBSYSTEM_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[subsystem] = score

        if not scores:
            return "unclassified"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Severity assessment
    # ------------------------------------------------------------------

    def _assess_severity(
        self, sub: GlobalFeedbackSubmission,
    ) -> FeedbackSeverity:
        """Re-assess severity based on content — may escalate."""
        text = f"{sub.title} {sub.description}".lower()
        for sev, keywords in _SEVERITY_ESCALATORS.items():
            if any(kw in text for kw in keywords):
                # Escalate if the keyword-implied severity is worse
                if _sev_rank(sev) > _sev_rank(sub.severity):
                    logger.debug(
                        "Severity escalated from %s to %s for %s",
                        sub.severity.value, sev.value, sub.id,
                    )
                    return sev
        return sub.severity

    # ------------------------------------------------------------------
    # Guiding-question answers
    # ------------------------------------------------------------------

    def _answer_guiding_questions(
        self,
        sub: GlobalFeedbackSubmission,
        subsystem: str,
    ) -> Dict[str, str]:
        """Produce an answer dict keyed Q1 … Q7."""
        answers: Dict[str, str] = {}

        # Q1 — Does the module do what it was designed to do?
        if sub.actual_behavior:
            answers["Q1"] = (
                f"The {subsystem} module is not performing as designed. "
                f"Observed behaviour: {sub.actual_behavior}"
            )
        else:
            answers["Q1"] = (
                f"Reported deviation in {subsystem}: {sub.title}"
            )

        # Q2 — What exactly is the module supposed to do?
        if sub.expected_behavior:
            answers["Q2"] = f"Design intent: {sub.expected_behavior}"
        else:
            answers["Q2"] = (
                f"Design intent for {subsystem} must be verified against "
                "spec documentation before remediation."
            )

        # Q3 — What conditions are possible?
        conditions = self._identify_conditions(sub)
        answers["Q3"] = (
            f"Conditions identified: {', '.join(conditions)}"
            if conditions
            else "No specific conditions identified; manual review required."
        )

        # Q4 — Does the test profile reflect the full range?
        answers["Q4"] = (
            "Test profile must be audited to verify coverage of the "
            f"reported condition in {subsystem}. "
            "Add regression test for this specific scenario."
        )

        # Q5 — Expected result at all points?
        if sub.expected_behavior:
            answers["Q5"] = f"Expected: {sub.expected_behavior}"
        else:
            answers["Q5"] = "Expected result not specified by reporter."

        # Q6 — Actual result?
        if sub.actual_behavior:
            answers["Q6"] = f"Actual: {sub.actual_behavior}"
        else:
            answers["Q6"] = f"Actual result described as: {sub.description[:200]}"

        # Q7 — Restart, ancillary, hardening, recommission?
        answers["Q7"] = (
            "After fix: (a) re-validate from symptom through root-cause, "
            "(b) update ancillary code and documentation, "
            "(c) apply hardening (input validation, rate limits), "
            "(d) recommission the module with full test suite."
        )

        return answers

    # ------------------------------------------------------------------
    # Condition identification
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_conditions(sub: GlobalFeedbackSubmission) -> List[str]:
        """Extract testable conditions from the submission."""
        conditions: List[str] = []
        if sub.steps_to_reproduce:
            conditions.append("reproducible_via_steps")
        if sub.console_errors:
            conditions.append("console_errors_present")
        if sub.severity in (FeedbackSeverity.CRITICAL, FeedbackSeverity.HIGH):
            conditions.append("high_severity")
        if sub.page_url:
            conditions.append("page_specific")
        if sub.component:
            conditions.append("component_specific")
        if sub.screenshot_refs:
            conditions.append("visual_evidence")
        return conditions

    # ------------------------------------------------------------------
    # Step generation
    # ------------------------------------------------------------------

    def _generate_steps(
        self,
        sub: GlobalFeedbackSubmission,
        subsystem: str,
        guiding: Dict[str, str],
    ) -> List[RemediationStep]:
        """Build ordered remediation steps from the analysis."""
        steps: List[RemediationStep] = []
        step_num = 0

        # Step 1 — Reproduce
        step_num += 1
        repro_action = (
            f"Reproduce the issue in {subsystem}"
        )
        if sub.steps_to_reproduce:
            repro_action += f" using reported steps: {sub.steps_to_reproduce[:200]}"
        steps.append(RemediationStep(
            step_number=step_num,
            action=repro_action,
            rationale="Confirm the defect before investing in a fix.",
            guiding_question="Q1",
            estimated_impact="high",
        ))

        # Step 2 — Root-cause analysis
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action=f"Trace root cause in {subsystem}: {sub.title}",
            rationale=guiding.get("Q1", "Determine design-vs-actual gap."),
            guiding_question="Q2",
            estimated_impact="high",
        ))

        # Step 3 — Implement fix
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action=f"Implement corrective patch for {subsystem}.",
            rationale="Address the root cause identified in step 2.",
            guiding_question="Q3",
            estimated_impact="high",
        ))

        # Step 4 — Expand test coverage
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action="Add regression test covering the reported scenario and edge cases.",
            rationale=guiding.get("Q4", "Ensure test profile covers this condition."),
            guiding_question="Q4",
            estimated_impact="medium",
        ))

        # Step 5 — Validate expected vs actual
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action="Verify expected result matches actual result at all operation points.",
            rationale=guiding.get("Q5", "Confirm fix produces correct output."),
            guiding_question="Q5",
            estimated_impact="medium",
        ))

        # Step 6 — Hardening
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action="Apply hardening: input validation, error boundaries, rate limits.",
            rationale="Prevent recurrence and similar class of defects.",
            guiding_question="Q7",
            estimated_impact="medium",
        ))

        # Step 7 — Documentation & recommission
        step_num += 1
        steps.append(RemediationStep(
            step_number=step_num,
            action="Update ancillary code, documentation, and as-builts. Recommission module.",
            rationale=guiding.get("Q7", "Complete the commissioning cycle."),
            guiding_question="Q7",
            estimated_impact="low",
        ))

        return steps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sev_rank(sev: FeedbackSeverity) -> int:
    """Return an integer rank for severity comparison (higher = worse)."""
    return {
        FeedbackSeverity.INFO: 0,
        FeedbackSeverity.LOW: 1,
        FeedbackSeverity.MEDIUM: 2,
        FeedbackSeverity.HIGH: 3,
        FeedbackSeverity.CRITICAL: 4,
    }.get(sev, 2)
