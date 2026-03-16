"""
IP Classification & Trade Secret Protection Engine
====================================================
Manages intellectual property classification across three tiers:
  - Employee IP: Shadow agent learning data (employee's work patterns)
  - Business IP: Org chart and system interaction patterns
  - System IP: Automation metrics licensed to Murphy for improvement
Includes trade secret marking, protection, and licensing framework.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IPClassification(Enum):
    """IP ownership classification tiers."""
    EMPLOYEE_IP = "employee_ip"
    BUSINESS_IP = "business_ip"
    SYSTEM_IP = "system_ip"
    TRADE_SECRET = "trade_secret"
    PUBLIC = "public"


class ProtectionLevel(Enum):
    """Protection level for IP assets."""
    OPEN = "open"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TRADE_SECRET = "trade_secret"


class LicenseType(Enum):
    """License types for IP usage."""
    EXCLUSIVE = "exclusive"
    NON_EXCLUSIVE = "non_exclusive"
    SYSTEM_LICENSE = "system_license"
    EMPLOYEE_LICENSE = "employee_license"
    BUSINESS_LICENSE = "business_license"


@dataclass
class IPAsset:
    """Represents an intellectual property asset in the system."""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    classification: IPClassification = IPClassification.SYSTEM_IP
    protection_level: ProtectionLevel = ProtectionLevel.INTERNAL
    owner_id: str = ""
    owner_type: str = "system"  # employee, business, system
    content_hash: str = ""
    metadata: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    is_trade_secret: bool = False
    access_log: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "description": self.description,
            "classification": self.classification.value,
            "protection_level": self.protection_level.value,
            "owner_id": self.owner_id,
            "owner_type": self.owner_type,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "tags": self.tags,
            "is_trade_secret": self.is_trade_secret,
            "access_log_count": len(self.access_log),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class License:
    """License for IP usage between parties."""
    license_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    license_type: LicenseType = LicenseType.SYSTEM_LICENSE
    licensor: str = ""  # Who grants the license
    licensee: str = ""  # Who receives the license
    scope: str = ""
    terms: dict = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "license_id": self.license_id,
            "asset_id": self.asset_id,
            "license_type": self.license_type.value,
            "licensor": self.licensor,
            "licensee": self.licensee,
            "scope": self.scope,
            "terms": self.terms,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass
class TradeSecretRecord:
    """Record of a trade secret designation."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    designation_reason: str = ""
    designated_by: str = ""
    protection_measures: list = field(default_factory=list)
    access_restricted_to: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "asset_id": self.asset_id,
            "designation_reason": self.designation_reason,
            "designated_by": self.designated_by,
            "protection_measures": self.protection_measures,
            "access_restricted_to": self.access_restricted_to,
            "created_at": self.created_at,
        }


class IPClassificationEngine:
    """
    Manages IP classification, protection, and licensing across the system.

    Three-tier IP model:
      1. Employee IP: Shadow agent data, learning patterns, work habits
      2. Business IP: Org chart interactions, process flows, system configs
      3. System IP: Aggregated metrics, automation patterns (licensed to Murphy)

    Trade secrets receive additional protection with access controls.
    """

    def __init__(self):
        self.assets: dict[str, IPAsset] = {}
        self.licenses: dict[str, License] = {}
        self.trade_secrets: dict[str, TradeSecretRecord] = {}
        self.max_assets = 10000

    def register_asset(
        self,
        name: str,
        description: str,
        classification: str,
        owner_id: str,
        owner_type: str = "system",
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list] = None,
        is_trade_secret: bool = False,
    ) -> IPAsset:
        """Register a new IP asset."""
        ip_class = IPClassification.SYSTEM_IP
        for c in IPClassification:
            if c.value == classification:
                ip_class = c
                break

        # Determine protection level from classification
        protection = self._determine_protection(ip_class, is_trade_secret)

        content_hash = ""
        if content:
            content_hash = hashlib.sha256(content.encode()).hexdigest()

        asset = IPAsset(
            name=name,
            description=description,
            classification=ip_class,
            protection_level=protection,
            owner_id=owner_id,
            owner_type=owner_type,
            content_hash=content_hash,
            metadata=metadata or {},
            tags=tags or [],
            is_trade_secret=is_trade_secret,
        )
        self.assets[asset.asset_id] = asset

        # If trade secret, create record
        if is_trade_secret:
            self._designate_trade_secret(asset, owner_id)

        # Auto-create system license for System IP
        if ip_class == IPClassification.SYSTEM_IP:
            self._create_system_license(asset)

        return asset

    def register_employee_ip(
        self,
        employee_id: str,
        shadow_agent_id: str,
        name: str,
        description: str,
        content: Optional[str] = None,
    ) -> IPAsset:
        """Register employee IP from shadow agent data."""
        return self.register_asset(
            name=name,
            description=description,
            classification="employee_ip",
            owner_id=employee_id,
            owner_type="employee",
            content=content,
            metadata={"shadow_agent_id": shadow_agent_id},
            tags=["shadow_agent", "employee_ip"],
        )

    def register_business_ip(
        self,
        business_id: str,
        name: str,
        description: str,
        content: Optional[str] = None,
        is_trade_secret: bool = False,
    ) -> IPAsset:
        """Register business IP from org chart/system interactions."""
        return self.register_asset(
            name=name,
            description=description,
            classification="business_ip",
            owner_id=business_id,
            owner_type="business",
            content=content,
            tags=["org_chart", "business_ip"],
            is_trade_secret=is_trade_secret,
        )

    def register_system_metrics_ip(
        self,
        name: str,
        description: str,
        metrics_data: Optional[str] = None,
    ) -> IPAsset:
        """Register system-level automation metrics IP."""
        asset = self.register_asset(
            name=name,
            description=description,
            classification="system_ip",
            owner_id="murphy_system",
            owner_type="system",
            content=metrics_data,
            tags=["automation_metrics", "system_ip", "licensed"],
        )
        return asset

    def designate_trade_secret(
        self,
        asset_id: str,
        reason: str,
        designated_by: str,
        access_restricted_to: Optional[list] = None,
    ) -> Optional[TradeSecretRecord]:
        """Designate an existing asset as a trade secret."""
        asset = self.assets.get(asset_id)
        if not asset:
            return None

        asset.is_trade_secret = True
        asset.protection_level = ProtectionLevel.TRADE_SECRET
        asset.metadata["original_classification"] = asset.classification.value
        asset.classification = IPClassification.TRADE_SECRET
        asset.updated_at = datetime.now(timezone.utc).isoformat()

        return self._designate_trade_secret(asset, designated_by, reason, access_restricted_to)

    def _designate_trade_secret(
        self,
        asset: IPAsset,
        designated_by: str,
        reason: str = "Auto-designated on creation",
        access_restricted_to: Optional[list] = None,
    ) -> TradeSecretRecord:
        """Internal: create trade secret record."""
        record = TradeSecretRecord(
            asset_id=asset.asset_id,
            designation_reason=reason,
            designated_by=designated_by,
            protection_measures=[
                "access_logging",
                "encryption_at_rest",
                "need_to_know_basis",
                "nda_required",
            ],
            access_restricted_to=access_restricted_to or [designated_by],
        )
        self.trade_secrets[record.record_id] = record
        return record

    def _determine_protection(self, classification: IPClassification, is_trade_secret: bool) -> ProtectionLevel:
        """Determine protection level from classification."""
        if is_trade_secret:
            return ProtectionLevel.TRADE_SECRET
        protection_map = {
            IPClassification.EMPLOYEE_IP: ProtectionLevel.CONFIDENTIAL,
            IPClassification.BUSINESS_IP: ProtectionLevel.RESTRICTED,
            IPClassification.SYSTEM_IP: ProtectionLevel.INTERNAL,
            IPClassification.TRADE_SECRET: ProtectionLevel.TRADE_SECRET,
            IPClassification.PUBLIC: ProtectionLevel.OPEN,
        }
        return protection_map.get(classification, ProtectionLevel.INTERNAL)

    def _create_system_license(self, asset: IPAsset) -> License:
        """Create automatic system license for metrics IP."""
        license_obj = License(
            asset_id=asset.asset_id,
            license_type=LicenseType.SYSTEM_LICENSE,
            licensor=asset.owner_id,
            licensee="murphy_system",
            scope="Aggregated automation metrics for system improvement",
            terms={
                "usage": "metrics_improvement",
                "anonymized": True,
                "aggregated": True,
                "no_individual_data": True,
            },
        )
        self.licenses[license_obj.license_id] = license_obj
        return license_obj

    def create_license(
        self,
        asset_id: str,
        license_type: str,
        licensor: str,
        licensee: str,
        scope: str,
        terms: Optional[dict] = None,
    ) -> Optional[License]:
        """Create a license for an IP asset."""
        asset = self.assets.get(asset_id)
        if not asset:
            return None

        lic_type = LicenseType.NON_EXCLUSIVE
        for lt in LicenseType:
            if lt.value == license_type:
                lic_type = lt
                break

        license_obj = License(
            asset_id=asset_id,
            license_type=lic_type,
            licensor=licensor,
            licensee=licensee,
            scope=scope,
            terms=terms or {},
        )
        self.licenses[license_obj.license_id] = license_obj
        return license_obj

    def check_access(self, asset_id: str, requester_id: str) -> dict:
        """Check if a requester has access to an IP asset."""
        asset = self.assets.get(asset_id)
        if not asset:
            return {"allowed": False, "reason": "Asset not found"}

        # Trade secrets have restricted access
        if asset.is_trade_secret:
            ts_records = [
                r for r in self.trade_secrets.values()
                if r.asset_id == asset_id
            ]
            for record in ts_records:
                if requester_id in record.access_restricted_to:
                    self._log_access(asset, requester_id, True)
                    return {"allowed": True, "reason": "Authorized trade secret access"}
            self._log_access(asset, requester_id, False)
            return {"allowed": False, "reason": "Trade secret - access restricted"}

        # Owner always has access
        if asset.owner_id == requester_id:
            self._log_access(asset, requester_id, True)
            return {"allowed": True, "reason": "Owner access"}

        # Check licenses
        relevant_licenses = [
            l for l in self.licenses.values()
            if l.asset_id == asset_id and l.licensee == requester_id and l.is_active
        ]
        if relevant_licenses:
            self._log_access(asset, requester_id, True)
            return {"allowed": True, "reason": "Licensed access"}

        # System IP is accessible to system
        if asset.classification == IPClassification.SYSTEM_IP and requester_id == "murphy_system":
            self._log_access(asset, requester_id, True)
            return {"allowed": True, "reason": "System license"}

        self._log_access(asset, requester_id, False)
        return {"allowed": False, "reason": "No access rights"}

    def _log_access(self, asset: IPAsset, requester_id: str, granted: bool):
        """Log an access attempt."""
        asset.access_log.append({
            "requester": requester_id,
            "granted": granted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep log bounded
        if len(asset.access_log) > 1000:
            asset.access_log = asset.access_log[-1000:]

    def get_asset(self, asset_id: str) -> Optional[dict]:
        """Get an IP asset by ID."""
        asset = self.assets.get(asset_id)
        return asset.to_dict() if asset else None

    def list_assets(
        self,
        classification: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> list[dict]:
        """List IP assets with optional filtering."""
        results = []
        for asset in self.assets.values():
            if classification and asset.classification.value != classification:
                continue
            if owner_id and asset.owner_id != owner_id:
                continue
            results.append(asset.to_dict())
        return results

    def list_trade_secrets(self) -> list[dict]:
        """List all trade secret records."""
        return [r.to_dict() for r in self.trade_secrets.values()]

    def list_licenses(self, asset_id: Optional[str] = None) -> list[dict]:
        """List licenses, optionally filtered by asset."""
        results = []
        for lic in self.licenses.values():
            if asset_id and lic.asset_id != asset_id:
                continue
            results.append(lic.to_dict())
        return results

    def get_ip_summary(self) -> dict:
        """Get a summary of all IP in the system."""
        by_class = {}
        by_protection = {}
        trade_secret_count = 0

        for asset in self.assets.values():
            cls = asset.classification.value
            by_class[cls] = by_class.get(cls, 0) + 1
            prot = asset.protection_level.value
            by_protection[prot] = by_protection.get(prot, 0) + 1
            if asset.is_trade_secret:
                trade_secret_count += 1

        return {
            "total_assets": len(self.assets),
            "by_classification": by_class,
            "by_protection_level": by_protection,
            "trade_secrets": trade_secret_count,
            "total_licenses": len(self.licenses),
            "active_licenses": sum(1 for l in self.licenses.values() if l.is_active),
        }
