# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""org_build_plan — Generic on-ramp for any external organization joining Murphy.

This package orchestrates the six-phase build pipeline that takes an
organization from "I want to use Murphy" to "fully operational tenant":

  1. Organization Intake   — collect org profile via questionnaire
  2. Tenant Provisioning   — create isolated workspace
  3. Org Chart Building    — build corporate hierarchy
  4. Connector Selection   — wire industry-appropriate platform connectors
  5. Compliance Profiling  — map regulatory frameworks to Murphy modules
  6. Workflow Templates    — load pre-built DAG templates for the industry

Public exports
--------------
OrganizationIntakeProfile, OrganizationIntake,
TenantProvisioner,
OrgChartBuilder,
ConnectorSelector,
ComplianceProfiler,
WorkflowTemplateLibrary,
OrganizationBuildOrchestrator, BuildResult, BuildPhase
"""

from __future__ import annotations

from .organization_intake import (
    DepartmentSpec,
    OrganizationIntake,
    OrganizationIntakeProfile,
)
from .tenant_provisioner import ProvisionResult, TenantProvisioner
from .org_chart_builder import OrgChartBuilder, OrgChartResult
from .connector_selector import ConnectorSelectionResult, ConnectorSelector
from .compliance_profiler import ComplianceProfileResult, ComplianceProfiler
from .workflow_templates import WorkflowTemplate, WorkflowTemplateLibrary
from .build_orchestrator import BuildPhase, BuildResult, OrganizationBuildOrchestrator

__version__ = "0.1.0"

__all__ = [
    # Intake
    "DepartmentSpec",
    "OrganizationIntakeProfile",
    "OrganizationIntake",
    # Provisioning
    "ProvisionResult",
    "TenantProvisioner",
    # Org chart
    "OrgChartResult",
    "OrgChartBuilder",
    # Connectors
    "ConnectorSelectionResult",
    "ConnectorSelector",
    # Compliance
    "ComplianceProfileResult",
    "ComplianceProfiler",
    # Workflow templates
    "WorkflowTemplate",
    "WorkflowTemplateLibrary",
    # Orchestrator
    "BuildPhase",
    "BuildResult",
    "OrganizationBuildOrchestrator",
]
