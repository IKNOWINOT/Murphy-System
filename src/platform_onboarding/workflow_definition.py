# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Workflow definition: encode all onboarding tasks as a WorkflowDefinition for the DAG engine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.workflow_dag_engine import WorkflowDefinition, StepDefinition
from .task_catalog import TASK_CATALOG


def create_onboarding_workflow() -> WorkflowDefinition:
    """Create the platform onboarding DAG from TASK_CATALOG."""
    steps = []
    for task in TASK_CATALOG:
        steps.append(StepDefinition(
            step_id=task.task_id,
            name=task.title,
            action=f"onboarding_{task.task_type}",
            depends_on=task.depends_on,
            condition=task.condition if task.is_conditional else None,
            metadata={
                "url": task.target_url,
                "time_estimate": task.time_estimate_minutes,
                "category": task.category,
                "value": task.estimated_value,
                "hitl_level": task.hitl_level,
                "wait_days": task.external_wait_days,
                "section": task.section,
                "description": task.description,
                "why": task.why,
                "value_type": task.value_type,
                "recurrence": task.recurrence,
                "prefill_fields": task.prefill_fields,
            }
        ))
    task_count = len(steps)
    return WorkflowDefinition(
        workflow_id="murphy_platform_onboarding_v1",
        name="Murphy Platform Onboarding — Full Business Infrastructure Setup",
        description=f"{task_count}-task DAG that bootstraps Murphy's complete business infrastructure",
        steps=steps,
    )
