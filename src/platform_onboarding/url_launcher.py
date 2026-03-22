# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""URL launcher: provides navigation context and prefill hints for onboarding tasks."""

from __future__ import annotations

from typing import Dict

from .task_catalog import OnboardingTask


class URLLauncher:
    """Provides navigation context and prefill hints for onboarding tasks."""

    def launch(self, task: OnboardingTask) -> Dict:
        """Return a navigation context dict for opening the task URL."""
        return {
            "task_id": task.task_id,
            "url": task.target_url,
            "title": task.title,
            "instructions": self._build_instructions(task),
            "prefill_fields": task.prefill_fields,
            "time_estimate_minutes": task.time_estimate_minutes,
            "hitl_level": task.hitl_level,
        }

    def get_navigation_context(self, task: OnboardingTask) -> Dict:
        """Return detailed instructions for the user/agent completing this task."""
        return {
            "task_id": task.task_id,
            "title": task.title,
            "url": task.target_url,
            "description": task.description,
            "why": task.why,
            "instructions": self._build_instructions(task),
            "task_type": task.task_type,
            "hitl_level": task.hitl_level,
            "category": task.category,
            "estimated_value": task.estimated_value,
            "time_estimate_minutes": task.time_estimate_minutes,
            "external_wait_days": task.external_wait_days,
            "depends_on": task.depends_on,
        }

    def get_prefill_hints(self, task: OnboardingTask, session_data: Dict) -> Dict:
        """Return fields the agent can help pre-fill from session data."""
        hints: Dict[str, str] = {}
        for form_field, session_key in task.prefill_fields.items():
            value = session_data.get(session_key)
            if value:
                hints[form_field] = value
        return hints

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build_instructions(self, task: OnboardingTask) -> str:
        base = f"Navigate to {task.target_url} and complete: {task.description}."
        if task.task_type == "human_required":
            base += " Human action required — this cannot be automated."
        elif task.task_type == "agent_assisted":
            base += " Murphy can assist with form filling and data preparation."
        elif task.task_type == "agent_auto":
            base += " Murphy can complete this automatically."
        elif task.task_type == "recurring":
            recurrence = task.recurrence or "periodically"
            base += f" This task recurs {recurrence}."
        if task.external_wait_days:
            base += f" Expect {task.external_wait_days} business days for external processing."
        return base
