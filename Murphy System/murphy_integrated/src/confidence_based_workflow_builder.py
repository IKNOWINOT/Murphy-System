"""
Confidence-Based Workflow Builder
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import uuid


@dataclass
class WorkflowBuildResult:
    workflow_id: str
    steps: List[Dict[str, Any]]
    confidence: float


class ConfidenceBasedWorkflowBuilder:
    """
    Minimal workflow builder used by system workflow tests.
    """

    def build_workflow(self, prompt: str) -> WorkflowBuildResult:
        step = {
            "step_id": f"step-{uuid.uuid4()}",
            "description": prompt.strip().split("\n")[0] if prompt else "Workflow step",
        }
        return WorkflowBuildResult(
            workflow_id=f"workflow-{uuid.uuid4()}",
            steps=[step],
            confidence=0.8,
        )
