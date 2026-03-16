"""
Murphy System Base Governance & Compliance Runtime

This module implements the base governance and compliance framework for the Murphy System,
providing preset-based configuration, validation, and enforcement across multiple domains.

Components:
- Preset Manager: Configuration and preset management
- Validation Engine: Requirement validation and gap analysis
- Compliance Monitor: Continuous compliance monitoring
- Governance API: REST API for governance operations
"""

from .api_server import GovernanceAPI
from .compliance_monitor import ComplianceMonitor, ComplianceReport
from .governance_runtime import GovernanceRuntime, RuntimeConfig
from .preset_manager import EnforcementMode, GovernancePreset, PresetManager
from .validation_engine import ComplianceStatus, ValidationEngine, ValidationResult

__version__ = "1.0.0"
__all__ = [
    "PresetManager",
    "GovernancePreset",
    "EnforcementMode",
    "ValidationEngine",
    "ValidationResult",
    "ComplianceStatus",
    "ComplianceMonitor",
    "ComplianceReport",
    "GovernanceRuntime",
    "RuntimeConfig",
    "GovernanceAPI"
]
