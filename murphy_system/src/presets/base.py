"""
PRESET-BASE — Industry Preset Base System
==========================================

Core dataclasses, schema validation, and factory helpers for the Murphy System
industry preset framework. Every preset module builds on the types defined here.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Core dataclasses  (PRESET-BASE)
# ---------------------------------------------------------------------------

@dataclass
class AgentPersona:
    """PRESET-BASE — Agent Persona definition for an industry domain."""

    persona_id: str
    name: str
    role: str
    domain: str
    capabilities: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)


@dataclass
class WorkflowTemplate:
    """PRESET-BASE — Workflow template with ordered steps, triggers, and outputs."""

    template_id: str
    name: str
    description: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    # Each step dict should have: step_name, step_type, agent_persona,
    # integrations, compliance_gates, kpis
    triggers: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)


@dataclass
class ComplianceRule:
    """PRESET-BASE — A single compliance requirement tied to a standard."""

    rule_id: str
    standard: str
    description: str
    required_approvals: int = 1
    penalty_severity: str = "medium"   # low / medium / high / critical
    automated_check: bool = False


@dataclass
class KPIDefinition:
    """PRESET-BASE — Key Performance Indicator with measurement metadata."""

    kpi_id: str
    name: str
    description: str
    unit: str
    target_value: float
    warning_threshold: float
    critical_threshold: float
    measurement_method: str


@dataclass
class IntegrationMapping:
    """PRESET-BASE — Connector specification for a third-party integration."""

    connector_name: str
    connector_type: str          # crm / erp / comms / storage / payment / …
    required: bool
    config_template: Dict[str, Any] = field(default_factory=dict)
    purpose: str = ""


@dataclass
class IndustryPreset:
    """PRESET-BASE — Top-level container for a fully-described industry preset."""

    preset_id: str
    name: str
    industry: str
    sub_industry: str
    description: str
    version: str = "1.0.0"
    workflow_templates: List[WorkflowTemplate] = field(default_factory=list)
    agent_personas: List[AgentPersona] = field(default_factory=list)
    integration_mappings: List[IntegrationMapping] = field(default_factory=list)
    compliance_rules: List[ComplianceRule] = field(default_factory=list)
    kpi_definitions: List[KPIDefinition] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    compatible_with: List[str] = field(default_factory=list)   # preset_ids


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class PresetSchema:
    """PRESET-BASE — Validates an IndustryPreset instance for completeness."""

    REQUIRED_PRESET_FIELDS = ("preset_id", "name", "industry", "sub_industry", "description")
    REQUIRED_STEP_FIELDS = ("step_name", "step_type", "agent_persona")

    def validate(self, preset: IndustryPreset) -> List[str]:
        """Return a list of validation error strings; empty list means valid."""
        errors: List[str] = []

        for f in self.REQUIRED_PRESET_FIELDS:
            if not getattr(preset, f, None):
                errors.append(f"Preset missing required field: {f!r}")

        if not preset.workflow_templates:
            errors.append("Preset must define at least one workflow template.")

        for wt in preset.workflow_templates:
            if not wt.template_id:
                errors.append(f"WorkflowTemplate missing template_id in preset {preset.preset_id!r}")
            for step in wt.steps:
                for sf in self.REQUIRED_STEP_FIELDS:
                    if sf not in step:
                        errors.append(
                            f"Step in template {wt.template_id!r} missing required key {sf!r}"
                        )

        if not preset.agent_personas:
            errors.append("Preset must define at least one agent persona.")

        for persona in preset.agent_personas:
            if not persona.persona_id or not persona.name:
                errors.append("AgentPersona missing persona_id or name.")

        if not preset.kpi_definitions:
            errors.append("Preset must define at least one KPI.")

        for kpi in preset.kpi_definitions:
            if kpi.warning_threshold >= kpi.critical_threshold and kpi.critical_threshold != 0:
                errors.append(
                    f"KPI {kpi.kpi_id!r}: warning_threshold should be less severe than critical_threshold."
                )

        return errors


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_preset(**kwargs: Any) -> IndustryPreset:
    """PRESET-BASE — Construct an IndustryPreset with an auto-generated preset_id."""
    if "preset_id" not in kwargs or not kwargs["preset_id"]:
        kwargs["preset_id"] = f"preset-{uuid.uuid4().hex[:8]}"
    return IndustryPreset(**kwargs)
