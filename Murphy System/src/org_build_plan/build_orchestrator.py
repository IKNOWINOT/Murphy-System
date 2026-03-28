# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Build Orchestrator — Master coordinator for the org_build_plan pipeline.

Executes all six build phases in sequence: intake validation, tenant
provisioning, org chart construction, connector selection, compliance
profiling, and workflow template loading.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .organization_intake import DepartmentSpec, OrganizationIntakeProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BuildPhase enum
# ---------------------------------------------------------------------------


class BuildPhase(Enum):
    """Enumeration of the sequential build phases."""

    INTAKE = "intake"
    PROVISIONING = "provisioning"
    ORG_CHART = "org_chart"
    CONNECTORS = "connectors"
    COMPLIANCE = "compliance"
    WORKFLOWS = "workflows"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# BuildResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class BuildResult:
    """Complete result of an organization build run."""

    build_id: str
    org_name: str
    phase: BuildPhase = BuildPhase.INTAKE
    tenant_id: Optional[str] = None
    intake_profile: Optional[Dict[str, Any]] = None
    provision_result: Optional[Dict[str, Any]] = None
    org_chart_result: Optional[Dict[str, Any]] = None
    connector_result: Optional[Dict[str, Any]] = None
    compliance_result: Optional[Dict[str, Any]] = None
    workflow_result: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "build_id": self.build_id,
            "org_name": self.org_name,
            "phase": self.phase.value,
            "tenant_id": self.tenant_id,
            "intake_profile": self.intake_profile,
            "provision_result": self.provision_result,
            "org_chart_result": self.org_chart_result,
            "connector_result": self.connector_result,
            "compliance_result": self.compliance_result,
            "workflow_result": self.workflow_result,
            "errors": list(self.errors),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# OrganizationBuildOrchestrator class
# ---------------------------------------------------------------------------


class OrganizationBuildOrchestrator:
    """Master orchestrator that drives the six-phase org build pipeline.

    Maintains an in-memory store of all past builds for retrieval.
    Each call to :meth:`build_organization` is thread-safe.
    """

    def __init__(self) -> None:
        self._builds: Dict[str, BuildResult] = {}
        self._lock = threading.Lock()

        # Lazy-init sub-components
        from .compliance_profiler import ComplianceProfiler
        from .connector_selector import ConnectorSelector
        from .org_chart_builder import OrgChartBuilder
        from .tenant_provisioner import TenantProvisioner
        from .workflow_templates import WorkflowTemplateLibrary

        self._provisioner = TenantProvisioner()
        self._chart_builder = OrgChartBuilder()
        self._connector_selector = ConnectorSelector()
        self._compliance_profiler = ComplianceProfiler()
        self._template_library = WorkflowTemplateLibrary()

    # ------------------------------------------------------------------
    # Core build pipeline
    # ------------------------------------------------------------------

    def build_organization(self, intake: OrganizationIntakeProfile) -> BuildResult:
        """Execute the full 6-phase build for *intake* and return :class:`BuildResult`.

        Phases run in order; any exception halts the pipeline and sets
        ``phase=FAILED`` with the error captured in ``errors``.
        """
        build_id = uuid.uuid4().hex[:12]
        result = BuildResult(
            build_id=build_id,
            org_name=intake.org_name,
        )

        # --- Phase 1: Validate intake ---
        result.phase = BuildPhase.INTAKE
        try:
            from .organization_intake import OrganizationIntake
            intake_obj = OrganizationIntake()
            intake_obj._profile = intake  # inject the already-built profile
            validation = intake_obj.validate_profile()
            result.intake_profile = intake.to_dict()
            if not validation["valid"]:
                result.errors.extend(validation["issues"])
                result.phase = BuildPhase.FAILED
                with self._lock:
                    self._builds[build_id] = result
                logger.warning("Build %s failed intake validation: %s", build_id, validation["issues"])
                return result
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Intake validation error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- Phase 2: Provision tenant workspace ---
        result.phase = BuildPhase.PROVISIONING
        try:
            provision = self._provisioner.provision(intake)
            result.tenant_id = provision.tenant_id
            result.provision_result = provision.to_dict()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Provisioning error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- Phase 3: Build org chart ---
        result.phase = BuildPhase.ORG_CHART
        try:
            chart = self._chart_builder.build_from_intake(intake)
            result.org_chart_result = chart.to_dict()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Org chart error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- Phase 4: Select connectors ---
        result.phase = BuildPhase.CONNECTORS
        try:
            connectors = self._connector_selector.select_connectors(intake)
            result.connector_result = connectors.to_dict()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Connector selection error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- Phase 5: Profile compliance ---
        result.phase = BuildPhase.COMPLIANCE
        try:
            compliance = self._compliance_profiler.profile(intake)
            result.compliance_result = compliance.to_dict()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Compliance profiling error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- Phase 6: Load workflow templates ---
        result.phase = BuildPhase.WORKFLOWS
        try:
            templates = self._template_library.get_templates_for_industry(intake.industry)
            result.workflow_result = {
                "industry": intake.industry,
                "templates_loaded": len(templates),
                "templates": [t.to_dict() for t in templates],
            }
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Workflow template error: {exc}")
            result.phase = BuildPhase.FAILED
            with self._lock:
                self._builds[build_id] = result
            return result

        # --- All phases succeeded ---
        result.phase = BuildPhase.COMPLETED
        result.completed_at = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._builds[build_id] = result

        logger.info(
            "Build %s completed for '%s' (tenant=%s)",
            build_id,
            intake.org_name,
            result.tenant_id,
        )
        return result

    def build_from_preset(
        self,
        preset_id: str,
        org_name: str,
        departments: Optional[List[DepartmentSpec]] = None,
    ) -> BuildResult:
        """Shortcut: load a preset, optionally override departments, then build.

        Constructs an :class:`OrganizationIntakeProfile` from the preset
        and calls :meth:`build_organization`.
        """
        from .organization_intake import OrganizationIntake
        from .presets import get_preset

        preset = get_preset(preset_id)
        if preset is None:
            build_id = uuid.uuid4().hex[:12]
            result = BuildResult(
                build_id=build_id,
                org_name=org_name,
                phase=BuildPhase.FAILED,
                errors=[f"Unknown preset '{preset_id}'"],
            )
            with self._lock:
                self._builds[build_id] = result
            return result

        intake_obj = OrganizationIntake()
        intake_obj._profile.org_name = org_name
        intake_obj.apply_preset(preset_id)
        # Override industry explicitly to ensure it's set
        intake_obj._profile.industry = preset.industry

        if departments:
            intake_obj._profile.departments = departments

        return self.build_organization(intake_obj.get_profile())

    # ------------------------------------------------------------------
    # Build registry
    # ------------------------------------------------------------------

    def get_build(self, build_id: str) -> Optional[BuildResult]:
        """Return the :class:`BuildResult` for *build_id*, or ``None``."""
        with self._lock:
            return self._builds.get(build_id)

    def list_builds(self) -> List[Dict[str, Any]]:
        """Return a summary list of all builds."""
        with self._lock:
            return [
                {
                    "build_id": r.build_id,
                    "org_name": r.org_name,
                    "phase": r.phase.value,
                    "tenant_id": r.tenant_id,
                    "errors": list(r.errors),
                    "created_at": r.created_at,
                    "completed_at": r.completed_at,
                }
                for r in self._builds.values()
            ]

    def get_available_presets(self) -> List[Dict[str, Any]]:
        """Return the list of available industry presets."""
        from .presets import list_presets

        return list_presets()


__all__ = [
    "BuildPhase",
    "BuildResult",
    "OrganizationBuildOrchestrator",
]
