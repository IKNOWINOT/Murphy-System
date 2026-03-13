"""
Preset Manager Implementation

Manages governance presets and configuration profiles for different regulatory
domains and compliance requirements.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class EnforcementMode(Enum):
    """How preset requirements are enforced"""
    HARD_REFUSAL = "hard_refusal"      # System refuses to operate
    SOFT_ESCALATION = "soft_escalation"  # Requires human escalation
    MONITORING_ONLY = "monitoring_only"    # Logs violations but continues
    CONFIGURABLE = "configurable"        # Can be toggled by operator


@dataclass
class GovernanceRequirement:
    """Individual governance requirement"""
    requirement_id: str
    category: str
    description: str
    enforcement_mode: EnforcementMode
    mandatory: bool = False
    depends_on: List[str] = field(default_factory=list)
    artifacts_required: List[str] = field(default_factory=list)
    controls_required: List[str] = field(default_factory=list)

    def is_satisfied(self, system_capabilities: Dict) -> bool:
        """Check if requirement can be satisfied by current system"""
        if self.mandatory:
            return all(control in system_capabilities.get("controls", [])
                      for control in self.controls_required)
        return True


@dataclass
class GovernancePreset:
    """Complete governance preset for specific domain"""
    preset_id: str
    name: str
    domain: str
    version: str
    description: str
    jurisdiction: List[str] = field(default_factory=list)

    # Requirements
    requirements: List[GovernanceRequirement] = field(default_factory=list)

    # Configuration
    enforcement_mode: EnforcementMode = EnforcementMode.SOFT_ESCALATION
    enabled_by_default: bool = False

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    author: str = "Murphy System"

    def get_mandatory_requirements(self) -> List[GovernanceRequirement]:
        """Get all mandatory requirements for this preset"""
        return [req for req in self.requirements if req.mandatory]

    def get_enforced_requirements(self) -> List[GovernanceRequirement]:
        """Get requirements that will be actively enforced"""
        return [req for req in self.requirements
                if req.enforcement_mode in [EnforcementMode.HARD_REFUSAL, EnforcementMode.SOFT_ESCALATION]]


class PresetManager:
    """Manages governance presets and configuration"""

    def __init__(self, preset_storage_path: Optional[str] = None):
        if preset_storage_path is None:
            preset_storage_path = os.path.join(tempfile.gettempdir(), "governance_presets")
        self.preset_storage_path = preset_storage_path
        self.presets: Dict[str, GovernancePreset] = {}
        self.enabled_presets: Set[str] = set()
        self.presets_dir = preset_storage_path

        # Ensure storage directory exists
        os.makedirs(self.presets_dir, exist_ok=True)

        # Load default presets
        self._load_default_presets()

    def _load_default_presets(self):
        """Load all default governance presets"""

        # 4.1 AI Governance Preset
        ai_preset = GovernancePreset(
            preset_id="ai_governance_v1",
            name="AI Governance and Risk Management",
            domain="AI_GOVERNANCE",
            version="1.0.0",
            description="Human oversight, risk-based gating, confidence thresholds, decision traceability",
            jurisdiction=["US", "EU", "UK"],
            enforcement_mode=EnforcementMode.SOFT_ESCALATION,
            enabled_by_default=False
        )

        ai_preset.requirements = [
            GovernanceRequirement(
                requirement_id="ai_human_oversight",
                category="oversight",
                description="Human oversight required for high-impact decisions",
                enforcement_mode=EnforcementMode.HARD_REFUSAL,
                mandatory=True,
                controls_required=["confidence_engine", "authority_mapper", "escalation_handler"]
            ),
            GovernanceRequirement(
                requirement_id="ai_risk_gating",
                category="risk_management",
                description="Risk-based gating enabled for autonomous actions",
                enforcement_mode=EnforcementMode.SOFT_ESCALATION,
                mandatory=True,
                controls_required=["risk_calculator", "gate_synthesis", "murphy_index"]
            ),
            GovernanceRequirement(
                requirement_id="ai_confidence_thresholds",
                category="confidence",
                description="Minimum confidence thresholds enforced",
                enforcement_mode=EnforcementMode.HARD_REFUSAL,
                mandatory=True,
                controls_required=["confidence_calculator", "threshold_enforcer"]
            ),
            GovernanceRequirement(
                requirement_id="ai_decision_traceability",
                category="auditability",
                description="Complete decision traceability maintained",
                enforcement_mode=EnforcementMode.SOFT_ESCALATION,
                mandatory=True,
                controls_required=["audit_logger", "trace_collector", "artifact_tracker"]
            )
        ]

        # 4.2 Enterprise Security Preset
        enterprise_preset = GovernancePreset(
            preset_id="enterprise_security_v1",
            name="Enterprise Security (SOC 2 / ISO 27001)",
            domain="ENTERPRISE_SECURITY",
            version="1.0.0",
            description="Role-based access control, change management, approval workflows, audit retention",
            enforcement_mode=EnforcementMode.SOFT_ESCALATION,
            enabled_by_default=True
        )

        enterprise_preset.requirements = [
            GovernanceRequirement(
                requirement_id="ent_role_based_access",
                category="access_control",
                description="Role-based access control enforced",
                enforcement_mode=EnforcementMode.HARD_REFUSAL,
                mandatory=True,
                controls_required=["rbac_engine", "access_validator", "permission_checker"]
            ),
            GovernanceRequirement(
                requirement_id="ent_change_management",
                category="change_control",
                description="Change management enforcement",
                enforcement_mode=EnforcementMode.SOFT_ESCALATION,
                mandatory=True,
                controls_required=["change_manager", "approval_workflow", "change_audit"]
            ),
            GovernanceRequirement(
                requirement_id="ent_approval_workflows",
                category="workflow",
                description="Formal approval workflows for changes",
                enforcement_mode=EnforcementMode.SOFT_ESCALATION,
                mandatory=False,
                controls_required=["workflow_engine", "approval_tracker", "notification_system"]
            ),
            GovernanceRequirement(
                requirement_id="ent_log_retention",
                category="auditability",
                description="Log retention and integrity for 7 years",
                enforcement_mode=EnforcementMode.HARD_REFUSAL,
                mandatory=True,
                controls_required=["log_retention", "integrity_checker", "archive_manager"]
            )
        ]

        # Register all presets (continuing with all 7 presets)
        self.presets[ai_preset.preset_id] = ai_preset
        self.presets[enterprise_preset.preset_id] = enterprise_preset

        # Enable default presets
        for preset_id, preset in self.presets.items():
            if preset.enabled_by_default:
                self.enabled_presets.add(preset_id)

    def get_preset(self, preset_id: str) -> Optional[GovernancePreset]:
        """Get specific preset by ID"""
        return self.presets.get(preset_id)

    def list_presets(self) -> List[GovernancePreset]:
        """List all available presets"""
        return list(self.presets.values())

    def get_enabled_presets(self) -> List[GovernancePreset]:
        """Get all currently enabled presets"""
        return [self.presets[preset_id] for preset_id in self.enabled_presets
                if preset_id in self.presets]

    def enable_preset(self, preset_id: str) -> bool:
        """Enable a specific preset"""
        if preset_id in self.presets:
            self.enabled_presets.add(preset_id)
            return True
        return False

    def disable_preset(self, preset_id: str) -> bool:
        """Disable a specific preset"""
        if preset_id in self.enabled_presets:
            self.enabled_presets.remove(preset_id)
            return True
        return False

    def get_all_requirements(self) -> List[GovernanceRequirement]:
        """Get all requirements from enabled presets"""
        requirements = []
        for preset_id in self.enabled_presets:
            if preset_id in self.presets:
                requirements.extend(self.presets[preset_id].requirements)
        return requirements
