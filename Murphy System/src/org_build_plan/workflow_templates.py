# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Workflow Template Library — Step 6 of the org_build_plan pipeline.

Provides pre-built DAG workflow templates for each industry vertical
and converts them to :class:`WorkflowDefinition` objects that the
:class:`WorkflowDAGEngine` can execute.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WorkflowTemplate dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorkflowTemplate:
    """A portable, industry-tagged workflow template.

    Steps are stored as dicts until compiled into a :class:`WorkflowDefinition`
    for execution by the :class:`WorkflowDAGEngine`.
    """

    template_id: str
    name: str
    description: str
    industry: str
    category: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "industry": self.industry,
            "category": self.category,
            "steps": [s.copy() for s in self.steps],
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# WorkflowTemplateLibrary class
# ---------------------------------------------------------------------------


class WorkflowTemplateLibrary:
    """Registry of pre-built workflow templates, organised by industry.

    Templates from all industry presets are loaded on first access and
    can be supplemented with custom templates via :meth:`register_template`.
    """

    def __init__(self) -> None:
        self._templates: Dict[str, WorkflowTemplate] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazily load templates from all presets."""
        if self._loaded:
            return
        from .presets import INDUSTRY_PRESETS

        for preset in INDUSTRY_PRESETS.values():
            for tpl_data in preset.workflow_templates:
                tpl = WorkflowTemplate(
                    template_id=tpl_data.get("template_id", uuid.uuid4().hex[:10]),
                    name=tpl_data.get("name", ""),
                    description=tpl_data.get("description", ""),
                    industry=preset.industry,
                    category=tpl_data.get("category", "operations"),
                    steps=tpl_data.get("steps", []),
                    metadata={"preset_id": preset.preset_id},
                )
                self._templates[tpl.template_id] = tpl

        self._loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_templates_for_industry(self, industry: str) -> List[WorkflowTemplate]:
        """Return all templates whose ``industry`` matches *industry*."""
        self._ensure_loaded()
        return [t for t in self._templates.values() if t.industry == industry]

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Return the template with *template_id*, or ``None``."""
        self._ensure_loaded()
        return self._templates.get(template_id)

    def register_template(self, template: WorkflowTemplate) -> bool:
        """Register a custom *template*, returning ``True`` on success.

        Returns ``False`` if a template with the same ID already exists.
        """
        self._ensure_loaded()
        if template.template_id in self._templates:
            logger.warning(
                "Template '%s' already registered — skipping", template.template_id
            )
            return False
        self._templates[template.template_id] = template
        logger.info("Registered template '%s'", template.template_id)
        return True

    def list_all_templates(self) -> List[Dict[str, Any]]:
        """Return a summary list of all registered templates."""
        self._ensure_loaded()
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "industry": t.industry,
                "category": t.category,
                "description": t.description,
            }
            for t in self._templates.values()
        ]

    def compile_to_dag(self, template: WorkflowTemplate) -> Any:
        """Convert *template* into a :class:`WorkflowDefinition`.

        Each step dict is converted to a :class:`StepDefinition` so the
        result is directly consumable by :class:`WorkflowDAGEngine`.
        """
        try:
            from workflow_dag_engine import StepDefinition, WorkflowDefinition
        except ImportError:
            from src.workflow_dag_engine import StepDefinition, WorkflowDefinition  # type: ignore[no-reattr]

        step_defs = []
        for step in template.steps:
            step_def = StepDefinition(
                step_id=step.get("step_id", uuid.uuid4().hex[:8]),
                name=step.get("name", ""),
                action=step.get("action", "noop"),
                depends_on=step.get("depends_on", []),
                condition=step.get("condition"),
                metadata={
                    "description": step.get("description", ""),
                    "template_id": template.template_id,
                },
            )
            step_defs.append(step_def)

        workflow_def = WorkflowDefinition(
            workflow_id=f"wf_{template.template_id}",
            name=template.name,
            description=template.description,
            steps=step_defs,
            metadata={
                "industry": template.industry,
                "category": template.category,
                "template_id": template.template_id,
            },
        )
        return workflow_def


__all__ = [
    "WorkflowTemplate",
    "WorkflowTemplateLibrary",
]
