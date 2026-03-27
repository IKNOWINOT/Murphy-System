"""
Governance Runtime Implementation

Main orchestration layer for base governance and compliance in the Murphy System.
Coordinates preset management, validation, and compliance monitoring.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

from .compliance_monitor import ComplianceMonitor, ComplianceReport
from .preset_manager import EnforcementMode, GovernancePreset, PresetManager
from .validation_engine import ComplianceStatus, ValidationEngine, ValidationResult


class RuntimeStatus(Enum):
    """Governance runtime status"""
    INACTIVE = "INACTIVE"
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


@dataclass
class RuntimeConfig:
    """Configuration for governance runtime"""
    enable_auto_validation: bool = True
    validation_interval_minutes: int = 60
    require_operator_acknowledgement: bool = True
    auto_enable_presets: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    compliance_reporting_enabled: bool = True
    strict_mode: bool = False


class GovernanceRuntime:
    """Main governance runtime orchestrator"""

    def __init__(self, config: RuntimeConfig = None):
        self.config = config or RuntimeConfig()
        self.status = RuntimeStatus.INACTIVE

        # Initialize components
        self.preset_manager = PresetManager()
        self.validation_engine = ValidationEngine()
        self.compliance_monitor = ComplianceMonitor()

        # Runtime state
        self.initialization_time = None
        self.last_validation_time = None
        self.operator_acknowledgements: Dict[str, datetime] = {}

        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Runtime state tracking
        self.runtime_metrics = {
            "validations_performed": 0,
            "gaps_identified": 0,
            "presets_enabled": 0,
            "last_status_change": datetime.now(timezone.utc)
        }

    def initialize(self) -> ValidationResult:
        """Initialize the governance runtime"""
        self.logger.info("Initializing governance runtime...")
        self.status = RuntimeStatus.INITIALIZING

        try:
            # Check mandatory baseline controls first
            baseline_check = self.validation_engine.check_mandatory_baseline_controls()

            if baseline_check.has_blocking_gaps():
                self.status = RuntimeStatus.BLOCKED
                self.logger.critical("System blocked - missing mandatory baseline controls")
                return baseline_check

            # Auto-enable configured presets
            for preset_id in self.config.auto_enable_presets:
                if self.preset_manager.enable_preset(preset_id):
                    self.logger.info(f"Auto-enabled preset: {preset_id}")

            # Perform initial validation
            enabled_presets = self.preset_manager.get_enabled_presets()
            initial_validation = self.validation_engine.validate_configuration(enabled_presets)

            # Store validation result
            self.compliance_monitor.record_validation_result(initial_validation)

            # Determine final status
            if initial_validation.overall_status == ComplianceStatus.COMPLIANT:
                self.status = RuntimeStatus.ACTIVE
                self.logger.info("Governance runtime active and compliant")
            elif initial_validation.overall_status == ComplianceStatus.PARTIALLY_COMPLIANT:
                if self.config.strict_mode:
                    self.status = RuntimeStatus.BLOCKED
                    self.logger.warning("Runtime blocked in strict mode due to compliance gaps")
                else:
                    self.status = RuntimeStatus.DEGRADED
                    self.logger.warning("Runtime active but degraded due to compliance gaps")
            else:
                self.status = RuntimeStatus.ERROR
                self.logger.error("Runtime failed initialization - non-compliant")

            self.initialization_time = datetime.now(timezone.utc)
            self.last_validation_time = datetime.now(timezone.utc)
            self.runtime_metrics["presets_enabled"] = len(enabled_presets)

            return initial_validation

        except Exception as exc:
            self.status = RuntimeStatus.ERROR
            self.logger.error(f"Runtime initialization failed: {exc}")
            raise

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        compliance_summary = self.compliance_monitor.get_compliance_summary()

        return {
            "runtime_status": self.status.value,
            "initialized_at": self.initialization_time.isoformat() if self.initialization_time else None,
            "last_validation": self.last_validation_time.isoformat() if self.last_validation_time else None,
            "compliance_status": compliance_summary,
            "active_presets": [p.preset_id for p in self.preset_manager.get_enabled_presets()],
            "available_presets": [p.preset_id for p in self.preset_manager.list_presets()],
            "runtime_metrics": self.runtime_metrics,
            "blocking_gaps": len(self.compliance_monitor.check_blocking_gaps()),
            "can_activate": self._can_activate_system()
        }

    def _can_activate_system(self) -> bool:
        """Check if system can be activated"""
        if self.status in [RuntimeStatus.INACTIVE, RuntimeStatus.ERROR, RuntimeStatus.BLOCKED]:
            return False

        blocking_gaps = self.compliance_monitor.check_blocking_gaps()
        if blocking_gaps:
            return False

        return True
