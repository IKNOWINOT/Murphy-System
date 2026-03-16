"""
Compliance Toggle Manager — Murphy System
Manages regulatory framework toggles per tenant, with location/industry
auto-detection and integration with the compliance engine.

Design Label: COMP-002
Owner: Platform Engineering
Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
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

_MAX_AUDIT_LOG = 5_000

# ---------------------------------------------------------------------------
# Framework Catalog
# ---------------------------------------------------------------------------

# All known compliance framework IDs.  These are the toggle keys exposed in
# the UI and stored in tenant configuration.

ALL_FRAMEWORKS: List[str] = [
    # Data Privacy
    "gdpr",
    "ccpa",
    "lgpd",
    "pipeda",
    "privacy_act_au",
    "appi",
    "popia",
    "pdpa",
    "coppa",
    "ferpa",
    "dsgvo",
    # Financial & Payment
    "pci_dss",
    "sox",
    "aml_kyc",
    "glba",
    "basel_iii",
    "mifid_ii",
    "psd2",
    "dora",
    # Healthcare
    "hipaa",
    "hitech",
    "fda_21_cfr_11",
    # Industry & Safety
    "iso_9001",
    "iso_14001",
    "iso_27001",
    "iso_45001",
    "osha",
    "ce_marking",
    "ul_certification",
    "isa_95",
    "iec_61131",
    "nfpa",
    # Government & Defense
    "fedramp",
    "cmmc",
    "nist_800_171",
    "itar",
    "nis2",
    # Security Frameworks
    "soc2",
    "soc1",
    "nist_csf",
    "cis_controls",
    "csa_star",
]

# Frameworks that map to native compliance_engine.py ComplianceFramework values.
COMPLIANCE_ENGINE_MAP: Dict[str, str] = {
    "gdpr": "gdpr",
    "soc2": "soc2",
    "hipaa": "hipaa",
    "pci_dss": "pci_dss",
    "iso_27001": "iso27001",
}

# ---------------------------------------------------------------------------
# Location → recommended frameworks
# ---------------------------------------------------------------------------

_COUNTRY_FRAMEWORKS: Dict[str, List[str]] = {
    # European Union (all member states)
    "AT": ["gdpr", "dsgvo", "nis2"],
    "BE": ["gdpr", "nis2"],
    "BG": ["gdpr", "nis2"],
    "HR": ["gdpr", "nis2"],
    "CY": ["gdpr", "nis2"],
    "CZ": ["gdpr", "nis2"],
    "DK": ["gdpr", "nis2"],
    "EE": ["gdpr", "nis2"],
    "FI": ["gdpr", "nis2"],
    "FR": ["gdpr", "nis2"],
    "DE": ["gdpr", "dsgvo", "nis2"],
    "GR": ["gdpr", "nis2"],
    "HU": ["gdpr", "nis2"],
    "IE": ["gdpr", "nis2"],
    "IT": ["gdpr", "nis2"],
    "LV": ["gdpr", "nis2"],
    "LT": ["gdpr", "nis2"],
    "LU": ["gdpr", "nis2"],
    "MT": ["gdpr", "nis2"],
    "NL": ["gdpr", "nis2"],
    "PL": ["gdpr", "nis2"],
    "PT": ["gdpr", "nis2"],
    "RO": ["gdpr", "nis2"],
    "SK": ["gdpr", "nis2"],
    "SI": ["gdpr", "nis2"],
    "ES": ["gdpr", "nis2"],
    "SE": ["gdpr", "nis2"],
    # UK (post-Brexit)
    "GB": ["gdpr"],
    # US (federal baseline)
    "US": ["sox", "ccpa", "coppa"],
    # US California (stricter)
    "US-CA": ["ccpa", "sox", "coppa"],
    # Brazil
    "BR": ["lgpd"],
    # Canada
    "CA": ["pipeda"],
    # Australia
    "AU": ["privacy_act_au"],
    # Japan
    "JP": ["appi"],
    # South Africa
    "ZA": ["popia"],
    # Singapore
    "SG": ["pdpa"],
    # Thailand
    "TH": ["pdpa"],
    # India (placeholder — PDPB pending)
    "IN": [],
    # China (PIPL)
    "CN": [],
}

# ---------------------------------------------------------------------------
# Industry → recommended frameworks
# ---------------------------------------------------------------------------

_INDUSTRY_FRAMEWORKS: Dict[str, List[str]] = {
    "healthcare": ["hipaa", "hitech", "soc2", "fda_21_cfr_11"],
    "finance": ["pci_dss", "sox", "aml_kyc", "glba", "soc2"],
    "banking": ["pci_dss", "sox", "aml_kyc", "glba", "basel_iii", "mifid_ii", "dora", "soc2"],
    "payments": ["pci_dss", "psd2", "aml_kyc", "soc2"],
    "government": ["fedramp", "nist_800_171", "cmmc", "nist_csf", "soc2"],
    "defense": ["cmmc", "itar", "nist_800_171", "fedramp"],
    "education": ["ferpa", "coppa", "soc2"],
    "retail": ["pci_dss", "ccpa", "soc2"],
    "manufacturing": ["iso_9001", "iso_14001", "iso_45001", "osha", "isa_95", "iec_61131"],
    "technology": ["soc2", "iso_27001", "nist_csf", "cis_controls"],
    "cloud": ["soc2", "iso_27001", "csa_star", "fedramp"],
    "legal": ["gdpr", "soc2", "iso_27001"],
    "hr": ["gdpr", "ccpa", "soc2"],
    "general": ["soc2"],
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class TenantFrameworkConfig:
    """Stores the enabled compliance framework toggles for one tenant."""
    tenant_id: str
    enabled_frameworks: List[str] = field(default_factory=list)
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "enabled_frameworks": self.enabled_frameworks,
            "last_updated": self.last_updated,
            "updated_by": self.updated_by,
        }


# ---------------------------------------------------------------------------
# ComplianceToggleManager
# ---------------------------------------------------------------------------


class ComplianceToggleManager:
    """Manages compliance framework toggles per tenant.

    Usage::

        mgr = ComplianceToggleManager()
        recommended = mgr.get_recommended_frameworks("DE", "finance")
        mgr.save_tenant_frameworks("tenant-abc", recommended)
        current = mgr.get_tenant_frameworks("tenant-abc")
        report = mgr.generate_compliance_report("tenant-abc")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: Dict[str, TenantFrameworkConfig] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recommended_frameworks(
        self,
        country_code: str,
        industry: str,
    ) -> List[str]:
        """Return recommended framework IDs for a given country and industry.

        Country codes follow ISO 3166-1 alpha-2 (e.g. "DE", "US", "GB").
        Use "US-CA" for California-specific recommendations.
        Industry must be one of the keys in _INDUSTRY_FRAMEWORKS, or
        "general" as a fallback.
        """
        country_upper = country_code.upper()
        industry_lower = industry.lower()

        country_fws = _COUNTRY_FRAMEWORKS.get(country_upper, [])
        # Also include EU-wide if we recognise the country code
        industry_fws = _INDUSTRY_FRAMEWORKS.get(industry_lower, _INDUSTRY_FRAMEWORKS["general"])

        # Merge, deduplicate, and return only valid framework IDs
        merged: List[str] = []
        seen: set = set()
        for fw in (country_fws + industry_fws):
            if fw in ALL_FRAMEWORKS and fw not in seen:
                merged.append(fw)
                seen.add(fw)

        logger.debug(
            "Recommended frameworks for %s / %s: %s",
            country_upper, industry_lower, merged,
        )
        return merged

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_tenant_frameworks(
        self,
        tenant_id: str,
        framework_ids: List[str],
        updated_by: str = "",
    ) -> TenantFrameworkConfig:
        """Persist the enabled framework list for a tenant.

        Unknown framework IDs are silently filtered out to prevent storage
        of arbitrary strings.  ``tenant_id`` must be a non-empty string.
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        validated = [f for f in framework_ids if f in ALL_FRAMEWORKS]
        invalid = set(framework_ids) - set(validated)
        if invalid:
            logger.warning("Ignoring unknown framework IDs for tenant %s: %s", tenant_id, invalid)

        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cfg = TenantFrameworkConfig(
                tenant_id=tenant_id,
                enabled_frameworks=list(validated),
                last_updated=now,
                updated_by=updated_by,
            )
            self._configs[tenant_id] = cfg
            self._audit("save_frameworks", tenant_id, {
                "count": len(validated),
                "updated_by": updated_by,
            })
        logger.info("Frameworks saved for tenant %s (%d frameworks)", tenant_id, len(validated))
        return cfg

    def get_tenant_frameworks(self, tenant_id: str) -> List[str]:
        """Return currently enabled framework IDs for a tenant."""
        with self._lock:
            cfg = self._configs.get(tenant_id)
        return list(cfg.enabled_frameworks) if cfg else []

    def get_tenant_config(self, tenant_id: str) -> Optional[TenantFrameworkConfig]:
        """Return the full tenant config object, or None if not configured."""
        with self._lock:
            return self._configs.get(tenant_id)

    # ------------------------------------------------------------------
    # Compliance Report
    # ------------------------------------------------------------------

    def generate_compliance_report(self, tenant_id: str) -> Dict[str, Any]:
        """Generate a compliance status summary across all enabled frameworks.

        For frameworks supported by the native compliance_engine.py, delegates
        to that engine.  All other frameworks are reported as "configured".
        """
        enabled = self.get_tenant_frameworks(tenant_id)
        framework_statuses: Dict[str, Any] = {}

        # Try to pull real scores from the compliance engine
        try:
            from compliance_engine import ComplianceEngine, ComplianceFramework
            engine = ComplianceEngine()
            engine._register_defaults()

            for fw_id in enabled:
                native_id = COMPLIANCE_ENGINE_MAP.get(fw_id)
                if native_id:
                    try:
                        ce_fw = ComplianceFramework(native_id)
                        report = engine.get_compliance_report(frameworks=[ce_fw])
                        breakdown = report.get("framework_breakdown", {}).get(native_id, {})
                        total = sum(breakdown.values()) or 1
                        passed = breakdown.get("passed", 0)
                        score = round((passed / total) * 100)
                        framework_statuses[fw_id] = {
                            "configured": True,
                            "score": score,
                            "breakdown": breakdown,
                        }
                    except Exception as exc:  # noqa: BLE001
                        framework_statuses[fw_id] = {"configured": True, "score": None}
                else:
                    framework_statuses[fw_id] = {"configured": True, "score": None}
        except ImportError:
            for fw_id in enabled:
                framework_statuses[fw_id] = {"configured": True, "score": None}

        total_enabled = len(enabled)
        scored = [v["score"] for v in framework_statuses.values() if v.get("score") is not None]
        overall_score = round(sum(scored) / (len(scored) or 1)) if scored else None

        return {
            "tenant_id": tenant_id,
            "enabled_count": total_enabled,
            "enabled_frameworks": enabled,
            "framework_statuses": framework_statuses,
            "overall_score": overall_score,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _audit(self, action: str, tenant_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "tenant_id": tenant_id,
            **details,
        }
        capped_append(self._audit_log, entry, _MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the audit log."""
        with self._lock:
            return list(self._audit_log)
