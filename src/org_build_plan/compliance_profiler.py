# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Compliance Profiler — Step 5 of the org_build_plan pipeline.

Maps the organization's declared regulatory frameworks to Murphy
compliance module IDs, derives the appropriate security level,
audit frequency, and data-residency requirements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .organization_intake import OrganizationIntakeProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework mapping table
# ---------------------------------------------------------------------------

FRAMEWORK_MAP: Dict[str, Dict[str, Any]] = {
    "HIPAA": {
        "security": "hardened",
        "audit": "quarterly",
        "modules": ["compliance_engine", "compliance_region_validator"],
        "data_residency": False,
    },
    "SOC2": {
        "security": "hardened",
        "audit": "annual",
        "modules": ["compliance_engine", "contractual_audit"],
        "data_residency": False,
    },
    "GDPR": {
        "security": "standard",
        "audit": "annual",
        "modules": ["compliance_engine", "compliance_region_validator"],
        "data_residency": True,
    },
    "PCI_DSS": {
        "security": "hardened",
        "audit": "quarterly",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "OSHA": {
        "security": "standard",
        "audit": "annual",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "EPA": {
        "security": "standard",
        "audit": "annual",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "ISO27001": {
        "security": "hardened",
        "audit": "annual",
        "modules": ["compliance_engine", "contractual_audit"],
        "data_residency": False,
    },
    "DOT": {
        "security": "standard",
        "audit": "annual",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "FMCSA": {
        "security": "standard",
        "audit": "quarterly",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "NERC": {
        "security": "hardened",
        "audit": "quarterly",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
    "CAN_SPAM": {
        "security": "standard",
        "audit": "annual",
        "modules": ["compliance_engine"],
        "data_residency": False,
    },
}

# Security level precedence: hardened > standard > basic
_SECURITY_PRECEDENCE: Dict[str, int] = {
    "basic": 0,
    "standard": 1,
    "hardened": 2,
}

# Audit frequency precedence: quarterly > monthly > annual
_AUDIT_PRECEDENCE: Dict[str, int] = {
    "annual": 0,
    "monthly": 1,
    "quarterly": 2,
}

# ---------------------------------------------------------------------------
# ComplianceProfileResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ComplianceProfileResult:
    """Result of the compliance profiling step."""

    frameworks_activated: List[str] = field(default_factory=list)
    security_level: str = "standard"
    audit_frequency: str = "annual"
    data_residency_required: bool = False
    compliance_modules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "frameworks_activated": list(self.frameworks_activated),
            "security_level": self.security_level,
            "audit_frequency": self.audit_frequency,
            "data_residency_required": self.data_residency_required,
            "compliance_modules": list(self.compliance_modules),
        }


# ---------------------------------------------------------------------------
# ComplianceProfiler class
# ---------------------------------------------------------------------------


class ComplianceProfiler:
    """Maps regulatory frameworks to Murphy compliance configuration.

    Takes the list of frameworks from the intake profile and produces
    the tightest possible combined security posture (highest security
    level, most frequent audit schedule, and data-residency flag if any
    framework requires it).
    """

    def __init__(self) -> None:
        pass

    def profile(self, intake: OrganizationIntakeProfile) -> ComplianceProfileResult:
        """Build a :class:`ComplianceProfileResult` from *intake*.

        If no frameworks are declared, sensible defaults are returned
        (``security_level="standard"``, ``audit_frequency="annual"``).
        """
        frameworks = intake.regulatory_frameworks
        activated: List[str] = []
        best_security = "standard"
        best_audit = "annual"
        data_residency = False
        modules_seen: set = set()

        for fw in frameworks:
            mapping = FRAMEWORK_MAP.get(fw)
            if mapping is None:
                logger.warning("Unknown framework '%s' — skipping", fw)
                continue

            activated.append(fw)

            # Ratchet security level up
            if _SECURITY_PRECEDENCE.get(mapping["security"], 0) > _SECURITY_PRECEDENCE.get(best_security, 0):
                best_security = mapping["security"]

            # Ratchet audit frequency up (quarterly beats annual)
            if _AUDIT_PRECEDENCE.get(mapping["audit"], 0) > _AUDIT_PRECEDENCE.get(best_audit, 0):
                best_audit = mapping["audit"]

            # GDPR triggers data residency
            if mapping.get("data_residency"):
                data_residency = True

            for mod in mapping.get("modules", []):
                modules_seen.add(mod)

        result = ComplianceProfileResult(
            frameworks_activated=activated,
            security_level=best_security,
            audit_frequency=best_audit,
            data_residency_required=data_residency,
            compliance_modules=sorted(modules_seen),
        )

        logger.info(
            "Compliance profile for '%s': security=%s, audit=%s, modules=%s",
            intake.org_name,
            best_security,
            best_audit,
            sorted(modules_seen),
        )
        return result


__all__ = [
    "ComplianceProfileResult",
    "ComplianceProfiler",
    "FRAMEWORK_MAP",
]
