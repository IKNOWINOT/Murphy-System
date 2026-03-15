"""
Validation Engine Implementation

Validates system configuration against governance requirements and identifies
gaps in control implementation and artifact availability.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

from .preset_manager import EnforcementMode, GovernancePreset, GovernanceRequirement

logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """Compliance status levels"""
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class GapType(Enum):
    """Types of compliance gaps"""
    MISSING_CONTROL = "missing_control"
    MISSING_ARTIFACT = "missing_artifact"
    CONFIGURATION_ERROR = "configuration_error"
    ENFORCEMENT_DISABLED = "enforcement_disabled"
    DEPENDENCY_UNMET = "dependency_unmet"


@dataclass
class ComplianceGap:
    """Specific compliance gap identified"""
    gap_id: str
    gap_type: GapType
    requirement_id: str
    preset_id: str
    description: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    remedy: str
    can_configure: bool = True

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type.value,
            "requirement_id": self.requirement_id,
            "preset_id": self.preset_id,
            "description": self.description,
            "severity": self.severity,
            "remedy": self.remedy,
            "can_configure": self.can_configure
        }


@dataclass
class ValidationResult:
    """Result of compliance validation"""
    validation_id: str
    timestamp: datetime
    overall_status: ComplianceStatus
    total_requirements: int
    satisfied_requirements: int
    gaps: List[ComplianceGap] = field(default_factory=list)
    risk_assessment: str = ""

    def get_compliance_percentage(self) -> float:
        """Calculate compliance percentage"""
        if self.total_requirements == 0:
            return 100.0
        return (self.satisfied_requirements / self.total_requirements) * 100.0

    def get_critical_gaps(self) -> List[ComplianceGap]:
        """Get all critical gaps"""
        return [gap for gap in self.gaps if gap.severity == "CRITICAL"]

    def has_blocking_gaps(self) -> bool:
        """Check if any gaps block system activation"""
        return any(gap.gap_type == GapType.MISSING_CONTROL and
                  gap.severity in ["CRITICAL", "HIGH"]
                  for gap in self.gaps)


class ValidationEngine:
    """Validates system configuration against governance requirements"""

    def __init__(self):
        self.system_capabilities = self._discover_system_capabilities()
        self.artifact_registry = self._initialize_artifact_registry()

    def _discover_system_capabilities(self) -> Dict[str, Any]:
        """Discover current system capabilities"""
        # Check Murphy System components
        capabilities = {
            "controls": set(),
            "services": set(),
            "frameworks": set(),
            "features": set()
        }

        # Core governance components (from our implementation)
        capabilities["controls"].update([
            "agent_descriptor", "authority_mapper", "stability_controller",
            "refusal_handler", "governance_scheduler", "artifact_validator"
        ])

        # Security plane components
        capabilities["controls"].update([
            "access_control", "authentication", "authorization", "audit_logging",
            "data_leak_prevention", "integrity_validation", "encryption"
        ])

        # Confidence engine components
        capabilities["controls"].update([
            "confidence_calculator", "risk_assessment", "murphy_index",
            "gate_synthesis", "phase_controller"
        ])

        # Services (from existing implementation)
        capabilities["services"].update([
            "confidence_engine", "gate_synthesis_engine", "security_plane",
            "execution_orchestrator", "deterministic_compute_plane"
        ])

        # Framework compliance
        capabilities["frameworks"].update([
            "governance_framework", "security_framework", "stability_framework"
        ])

        return capabilities

    def _initialize_artifact_registry(self) -> Dict[str, Any]:
        """Initialize artifact registry with available artifacts"""
        # This would connect to the artifact ingestion system
        return {
            "policies": ["data_protection_policy", "access_control_policy"],
            "certifications": ["soc2_type2", "iso27001"],
            "attestations": ["privacy_training", "security_training"],
            "contracts": ["vendor_agreements", "sla_documents"]
        }

    def validate_configuration(self, enabled_presets: List[GovernancePreset]) -> ValidationResult:
        """Validate current system configuration against enabled presets"""

        validation_id = f"validation_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Collect all requirements
        all_requirements = []
        for preset in enabled_presets:
            for req in preset.requirements:
                all_requirements.append((req, preset.preset_id))

        total_requirements = len(all_requirements)
        satisfied_requirements = 0
        gaps = []

        # Validate each requirement
        for requirement, preset_id in all_requirements:
            gap = self._validate_requirement(requirement, preset_id)
            if gap:
                gaps.append(gap)
                if not gap.can_configure and requirement.mandatory:
                    # Mark as unsatisfied for mandatory unconfigurable gaps
                    pass
                else:
                    satisfied_requirements += 1
            else:
                satisfied_requirements += 1

        # Determine overall status
        if not gaps:
            overall_status = ComplianceStatus.COMPLIANT
        elif any(gap.severity == "CRITICAL" and not gap.can_configure for gap in gaps):
            overall_status = ComplianceStatus.NON_COMPLIANT
        else:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT

        return ValidationResult(
            validation_id=validation_id,
            timestamp=datetime.now(timezone.utc),
            overall_status=overall_status,
            total_requirements=total_requirements,
            satisfied_requirements=satisfied_requirements,
            gaps=gaps,
            risk_assessment=self._generate_risk_assessment(gaps)
        )

    def _validate_requirement(self, requirement: GovernanceRequirement, preset_id: str) -> Optional[ComplianceGap]:
        """Validate individual requirement"""

        # Check if required controls are available
        missing_controls = []
        for control in requirement.controls_required:
            if control not in self.system_capabilities["controls"]:
                missing_controls.append(control)

        if missing_controls:
            return ComplianceGap(
                gap_id=f"gap_control_{preset_id}_{requirement.requirement_id}",
                gap_type=GapType.MISSING_CONTROL,
                requirement_id=requirement.requirement_id,
                preset_id=preset_id,
                description=f"Missing required controls: {', '.join(missing_controls)}",
                severity="CRITICAL" if requirement.mandatory else "HIGH",
                remedy=f"Implement missing controls: {', '.join(missing_controls)}",
                can_configure=False
            )

        # Check if required artifacts are available
        missing_artifacts = []
        for artifact in requirement.artifacts_required:
            found = False
            for artifact_list in self.artifact_registry.values():
                if artifact in artifact_list:
                    found = True
                    break
            if not found:
                missing_artifacts.append(artifact)

        if missing_artifacts:
            return ComplianceGap(
                gap_id=f"gap_artifact_{preset_id}_{requirement.requirement_id}",
                gap_type=GapType.MISSING_ARTIFACT,
                requirement_id=requirement.requirement_id,
                preset_id=preset_id,
                description=f"Missing required artifacts: {', '.join(missing_artifacts)}",
                severity="HIGH" if requirement.mandatory else "MEDIUM",
                remedy=f"Obtain missing artifacts: {', '.join(missing_artifacts)}",
                can_configure=True
            )

        # Check dependencies
        for dep_id in requirement.depends_on:
            # This would check if dependent requirements are satisfied
            pass

        # No gaps found
        return None

    def _generate_risk_assessment(self, gaps: List[ComplianceGap]) -> str:
        """Generate risk assessment based on gaps"""
        critical_count = len([g for g in gaps if g.severity == "CRITICAL"])
        high_count = len([g for g in gaps if g.severity == "HIGH"])

        if critical_count > 0:
            return f"CRITICAL: {critical_count} critical gaps requiring immediate attention"
        elif high_count > 3:
            return f"HIGH: {high_count} high-priority gaps identified"
        elif len(gaps) > 0:
            return f"MEDIUM: {len(gaps)} gaps found, system operational with limitations"
        else:
            return "LOW: No compliance gaps detected"

    def check_mandatory_baseline_controls(self) -> ValidationResult:
        """Check mandatory baseline controls are present"""

        mandatory_controls = [
            "authority_mapper",          # Explicit authority scoping
            "deterministic_compute",     # Deterministic execution gating
            "refusal_handler",          # Refusal as valid outcome
            "audit_logging",            # Immutable audit logging
            "stability_controller",     # Separation of proposal/enforcement
            "governance_scheduler",     # Bounded execution and retry limits
            "escalation_handler"        # Explicit escalation paths
        ]

        missing_mandatory = []
        for control in mandatory_controls:
            if control not in self.system_capabilities["controls"]:
                missing_mandatory.append(control)

        if missing_mandatory:
            return ValidationResult(
                validation_id="mandatory_baseline_check",
                timestamp=datetime.now(timezone.utc),
                overall_status=ComplianceStatus.NON_COMPLIANT,
                total_requirements=len(mandatory_controls),
                satisfied_requirements=len(mandatory_controls) - len(missing_mandatory),
                gaps=[
                    ComplianceGap(
                        gap_id="mandatory_baseline_missing",
                        gap_type=GapType.MISSING_CONTROL,
                        requirement_id="mandatory_baseline",
                        preset_id="system_baseline",
                        description=f"Missing mandatory controls: {', '.join(missing_mandatory)}",
                        severity="CRITICAL",
                        remedy="System is non-deployable - implement all mandatory baseline controls",
                        can_configure=False
                    )
                ],
                risk_assessment="CRITICAL: System cannot be deployed without mandatory baseline controls"
            )

        return ValidationResult(
            validation_id="mandatory_baseline_check",
            timestamp=datetime.now(timezone.utc),
            overall_status=ComplianceStatus.COMPLIANT,
            total_requirements=len(mandatory_controls),
            satisfied_requirements=len(mandatory_controls),
            gaps=[],
            risk_assessment="LOW: All mandatory baseline controls present"
        )
