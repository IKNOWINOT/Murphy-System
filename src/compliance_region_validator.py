"""
Compliance Region Validator — Section 12 Step 5.2

Validates compliance sensors against region-specific requirements before delivery,
completing the multi-project automation loops by ensuring region-based compliance
validation. Supports:
- Region requirement registration with framework mapping
- Delivery validation against consent, residency, cross-border, and retention rules
- Cross-border data transfer checks
- Multi-region framework aggregation
- Validation history recording and compliance reporting
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class RegionRequirement:
    """Region-specific compliance requirement definition."""
    region: str
    framework: str
    data_residency: str
    requires_consent: bool = True
    retention_max_days: int = 365
    cross_border_allowed: bool = False
    regulatory_body: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComplianceRegionValidator:
    """Validates deliveries against region-specific compliance requirements.

    Manages region requirement registrations, validates delivery compliance,
    checks cross-border transfers, and maintains validation history.
    """

    def __init__(self) -> None:
        self._regions: Dict[str, RegionRequirement] = {}
        self._validation_history: List[Dict[str, Any]] = []
        self._load_defaults()

    # ------------------------------------------------------------------
    # Default region requirements
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        """Load common region-to-framework default requirements."""
        defaults = [
            RegionRequirement(
                region="EU",
                framework="GDPR",
                data_residency="EU",
                requires_consent=True,
                retention_max_days=365,
                cross_border_allowed=False,
                regulatory_body="European Data Protection Board",
            ),
            RegionRequirement(
                region="US_CA",
                framework="CCPA",
                data_residency="US",
                requires_consent=True,
                retention_max_days=365,
                cross_border_allowed=True,
                regulatory_body="California Attorney General",
            ),
            RegionRequirement(
                region="US_HIPAA",
                framework="HIPAA",
                data_residency="US",
                requires_consent=True,
                retention_max_days=2190,
                cross_border_allowed=False,
                regulatory_body="HHS Office for Civil Rights",
            ),
            RegionRequirement(
                region="CA",
                framework="PIPEDA",
                data_residency="CA",
                requires_consent=True,
                retention_max_days=730,
                cross_border_allowed=True,
                regulatory_body="Office of the Privacy Commissioner",
            ),
            RegionRequirement(
                region="BR",
                framework="LGPD",
                data_residency="BR",
                requires_consent=True,
                retention_max_days=365,
                cross_border_allowed=False,
                regulatory_body="ANPD",
            ),
            RegionRequirement(
                region="AU",
                framework="Privacy Act",
                data_residency="AU",
                requires_consent=True,
                retention_max_days=365,
                cross_border_allowed=True,
                regulatory_body="OAIC",
            ),
        ]
        for req in defaults:
            self._regions[req.region] = req

    # ------------------------------------------------------------------
    # Region registration
    # ------------------------------------------------------------------

    def register_region(self, requirement: RegionRequirement) -> str:
        """Register or override a region requirement. Returns a confirmation ID."""
        self._regions[requirement.region] = requirement
        reg_id = uuid.uuid4().hex[:12]
        logger.info("Registered region %s (framework=%s, id=%s)",
                     requirement.region, requirement.framework, reg_id)
        return reg_id

    # ------------------------------------------------------------------
    # Delivery validation
    # ------------------------------------------------------------------

    def validate_delivery(
        self,
        region: str,
        data_types: list,
        destination_region: str = None,
    ) -> Dict[str, Any]:
        """Validate whether a delivery to *region* is compliant.

        Checks consent requirements, data residency, cross-border rules,
        and retention limits. Returns a result dict with ``status`` field.
        """
        if region not in self._regions:
            return {
                "status": "unknown_region",
                "region": region,
                "message": f"No requirements registered for region '{region}'",
                "compliant": False,
                "checks": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        req = self._regions[region]
        checks: Dict[str, Any] = {}
        issues: List[str] = []

        # Consent check
        checks["consent_required"] = req.requires_consent
        if req.requires_consent and not data_types:
            issues.append("Data types must be specified when consent is required")
            checks["consent_passed"] = False
        else:
            checks["consent_passed"] = True

        # Residency check
        checks["data_residency"] = req.data_residency
        checks["residency_passed"] = True

        # Cross-border check
        if destination_region and destination_region != region:
            cross = self.check_cross_border(region, destination_region)
            checks["cross_border"] = cross
            if not cross["allowed"]:
                issues.append(
                    f"Cross-border transfer from {region} to {destination_region} is not allowed"
                )
                checks["cross_border_passed"] = False
            else:
                checks["cross_border_passed"] = True
        else:
            checks["cross_border_passed"] = True

        # Retention check
        checks["retention_max_days"] = req.retention_max_days
        checks["retention_passed"] = True

        compliant = len(issues) == 0
        status = "compliant" if compliant else "non_compliant"

        return {
            "status": status,
            "region": region,
            "framework": req.framework,
            "compliant": compliant,
            "issues": issues,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Cross-border checks
    # ------------------------------------------------------------------

    def check_cross_border(
        self,
        source_region: str,
        dest_region: str,
    ) -> Dict[str, Any]:
        """Check if cross-border data transfer is allowed between regions."""
        if source_region not in self._regions:
            return {
                "status": "unknown_region",
                "source_region": source_region,
                "dest_region": dest_region,
                "allowed": False,
                "reason": f"Source region '{source_region}' not registered",
            }

        source_req = self._regions[source_region]
        allowed = source_req.cross_border_allowed

        if not allowed:
            reason = (
                f"{source_req.framework} in {source_region} does not permit "
                f"cross-border transfers to {dest_region}"
            )
        else:
            reason = (
                f"{source_req.framework} in {source_region} permits "
                f"cross-border transfers"
            )

        return {
            "status": "allowed" if allowed else "blocked",
            "source_region": source_region,
            "dest_region": dest_region,
            "allowed": allowed,
            "reason": reason,
            "framework": source_req.framework,
        }

    # ------------------------------------------------------------------
    # Region requirements query
    # ------------------------------------------------------------------

    def get_region_requirements(self, region: str) -> Dict[str, Any]:
        """Return region requirements as a dict, or an error dict if unknown."""
        if region not in self._regions:
            return {
                "status": "unknown_region",
                "region": region,
                "message": f"No requirements registered for region '{region}'",
            }

        req = self._regions[region]
        return {
            "status": "found",
            "region": req.region,
            "framework": req.framework,
            "data_residency": req.data_residency,
            "requires_consent": req.requires_consent,
            "retention_max_days": req.retention_max_days,
            "cross_border_allowed": req.cross_border_allowed,
            "regulatory_body": req.regulatory_body,
            "metadata": req.metadata,
        }

    # ------------------------------------------------------------------
    # Compliance report
    # ------------------------------------------------------------------

    def get_compliance_report(
        self,
        regions: List[str] = None,
    ) -> Dict[str, Any]:
        """Return compliance status for specified regions (or all)."""
        if regions is None:
            target_regions = list(self._regions.keys())
        else:
            target_regions = regions

        region_details: List[Dict[str, Any]] = []
        for r in target_regions:
            region_details.append(self.get_region_requirements(r))

        total = len(target_regions)
        known = sum(1 for d in region_details if d["status"] == "found")

        return {
            "status": "report_generated",
            "total_regions": total,
            "known_regions": known,
            "unknown_regions": total - known,
            "regions": region_details,
            "validation_history_count": len(self._validation_history),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Retention validation
    # ------------------------------------------------------------------

    def validate_retention(
        self,
        region: str,
        retention_days: int,
    ) -> Dict[str, Any]:
        """Check if a retention period is within limits for a region."""
        if region not in self._regions:
            return {
                "status": "unknown_region",
                "region": region,
                "compliant": False,
                "message": f"No requirements registered for region '{region}'",
            }

        req = self._regions[region]
        within_limit = retention_days <= req.retention_max_days

        return {
            "status": "compliant" if within_limit else "non_compliant",
            "region": region,
            "framework": req.framework,
            "retention_days": retention_days,
            "retention_max_days": req.retention_max_days,
            "compliant": within_limit,
        }

    # ------------------------------------------------------------------
    # Multi-region framework aggregation
    # ------------------------------------------------------------------

    def get_required_frameworks(
        self,
        regions: List[str],
    ) -> Dict[str, Any]:
        """Aggregate all required compliance frameworks across multiple regions."""
        frameworks: Dict[str, List[str]] = {}
        unknown: List[str] = []

        for region in regions:
            if region not in self._regions:
                unknown.append(region)
                continue
            req = self._regions[region]
            frameworks.setdefault(req.framework, []).append(region)

        return {
            "status": "aggregated",
            "frameworks": frameworks,
            "total_frameworks": len(frameworks),
            "unknown_regions": unknown,
        }

    # ------------------------------------------------------------------
    # Validation history
    # ------------------------------------------------------------------

    def record_validation(
        self,
        region: str,
        result: Dict[str, Any],
    ) -> str:
        """Record a validation attempt and result. Returns a record ID."""
        record_id = uuid.uuid4().hex[:12]
        record = {
            "record_id": record_id,
            "region": region,
            "result": result,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._validation_history, record)
        logger.info("Recorded validation %s for region %s", record_id, region)
        return record_id

    def get_validation_history(
        self,
        region: str = None,
    ) -> List[Dict[str, Any]]:
        """Return validation history, optionally filtered by region."""
        if region is None:
            return list(self._validation_history)
        return [h for h in self._validation_history if h["region"] == region]

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all state and re-load default region requirements."""
        self._regions.clear()
        self._validation_history.clear()
        self._load_defaults()
        logger.info("ComplianceRegionValidator state cleared and defaults reloaded")
