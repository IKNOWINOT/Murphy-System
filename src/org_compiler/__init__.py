"""
Org Compiler & Shadow Learning System

This module provides safe organizational workflow learning and automation proposal
generation while maintaining strict human authority and safety gates.

Components:
- schemas: Core data models (RoleTemplate, TemplateProposal, etc.)
- parsers: Input data parsers (org charts, SOPs, tickets, etc.)
- compiler: RoleTemplate compiler
- shadow_learning: Observation-only learning agents
- substitution: Safety gate evaluation for automation
- visualization: Role → Work graph generation
"""

from .schemas import (
    ComplianceConstraint,
    EscalationPath,
    HandoffEvent,
    OrgChartNode,
    ProcessFlow,
    RoleMetrics,
    RoleTemplate,
    SubstitutionGate,
    TemplateProposalArtifact,
    WorkArtifact,
)

__all__ = [
    "RoleTemplate",
    "TemplateProposalArtifact",
    "OrgChartNode",
    "ProcessFlow",
    "WorkArtifact",
    "HandoffEvent",
    "SubstitutionGate",
    "EscalationPath",
    "ComplianceConstraint",
    "RoleMetrics",
]
