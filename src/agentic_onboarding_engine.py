"""
Agentic Onboarding & Account Setup Engine for Murphy System.

Agentically onboards users, creates accounts across integrations,
reads their emails/requirements, builds systems, and deploys —
all without the user touching a single API key.

Capabilities:
  - OnboardingProfile dataclass capturing all onboarding state
  - BUSINESS_DEMOGRAPHICS catalog mapping business type to integrations
  - REGULATORY_ZONES mapping country codes to compliance frameworks
  - AgenticOnboardingEngine wiring SecureKeyManager, TelemetryAdapter,
    and GoldenPathBridge together
  - OnboardingOrchestrator managing the full onboarding lifecycle:
      intake → provisioning → building → deploying → active

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: profiles are never deleted, only status-updated
  - All timestamps UTC ISO format

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from golden_path_bridge import GoldenPathBridge
from secure_key_manager import retrieve_api_key, store_api_key
from telemetry_adapter import TelemetryAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Business demographics catalog
# ---------------------------------------------------------------------------

BUSINESS_DEMOGRAPHICS: Dict[str, Dict] = {
    "sole_proprietor": {"integrations": ["email", "invoicing", "scheduling", "crm_basic"]},
    "small_retail": {"integrations": ["pos", "inventory", "ecommerce", "shipping", "crm_basic"]},
    "restaurant": {"integrations": ["pos", "reservations", "delivery", "inventory", "scheduling"]},
    "professional_services": {"integrations": ["crm", "invoicing", "scheduling", "document_management", "time_tracking"]},
    "manufacturing": {"integrations": ["erp", "inventory", "quality_management", "supply_chain", "maintenance"]},
    "healthcare": {"integrations": ["ehr", "scheduling", "billing", "compliance", "telehealth"]},
    "construction": {"integrations": ["project_management", "estimating", "scheduling", "safety", "equipment_tracking"]},
    "logistics": {"integrations": ["fleet_management", "route_optimization", "warehouse", "shipping", "tracking"]},
    "real_estate": {"integrations": ["crm", "listings", "document_management", "scheduling", "virtual_tours"]},
    "education": {"integrations": ["lms", "scheduling", "communication", "grading", "enrollment"]},
    "nonprofit": {"integrations": ["donor_management", "volunteer_tracking", "grant_management", "communication"]},
    "agriculture": {"integrations": ["crop_management", "equipment_tracking", "weather", "market_prices", "compliance"]},
    "enterprise": {"integrations": ["erp", "crm", "hr", "finance", "analytics", "security", "compliance"]},
}

# ---------------------------------------------------------------------------
# Regulatory zone mapping
# ---------------------------------------------------------------------------

REGULATORY_ZONES: Dict[str, Dict] = {
    "US": {"zone": "us_federal_state", "frameworks": ["SOX", "HIPAA", "CCPA", "ADA"]},
    "GB": {"zone": "uk", "frameworks": ["GDPR_UK", "FCA", "HMRC"]},
    "DE": {"zone": "eu", "frameworks": ["GDPR", "BaFin", "DSGVO"]},
    "JP": {"zone": "apac", "frameworks": ["APPI", "J-SOX"]},
    "AU": {"zone": "apac", "frameworks": ["Privacy_Act", "APRA"]},
    "BR": {"zone": "latam", "frameworks": ["LGPD"]},
    "CA": {"zone": "canada", "frameworks": ["PIPEDA", "CASL"]},
    "IN": {"zone": "apac", "frameworks": ["IT_Act", "DPDP"]},
    "AE": {"zone": "mena", "frameworks": ["DIFC_DP", "ADGM"]},
    "default": {"zone": "international", "frameworks": ["ISO_27001"]},
}

# ---------------------------------------------------------------------------
# OnboardingProfile dataclass
# ---------------------------------------------------------------------------


@dataclass
class OnboardingProfile:
    """Complete state for a single business onboarding session."""

    profile_id: str
    business_name: str
    business_type: str  # key from BUSINESS_DEMOGRAPHICS
    industry: str
    country: str
    region: str
    language: str  # ISO 639-1 code
    regulatory_zone: str  # computed from country
    email: str
    requirements_extracted: List[str] = field(default_factory=list)
    integrations_needed: List[str] = field(default_factory=list)
    integrations_provisioned: Dict[str, str] = field(default_factory=dict)
    deployment_target: str = "cloudflare"  # cloudflare | aws | gcp | self_hosted
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "intake"  # intake | provisioning | building | deploying | active | failed


# ---------------------------------------------------------------------------
# AgenticOnboardingEngine — wires the three adapters together
# ---------------------------------------------------------------------------


class AgenticOnboardingEngine:
    """
    Core engine that wires SecureKeyManager, TelemetryAdapter, and
    GoldenPathBridge together to support agentic onboarding operations.
    """

    def __init__(
        self,
        telemetry: Optional[TelemetryAdapter] = None,
        golden_path: Optional[GoldenPathBridge] = None,
    ) -> None:
        self.telemetry: TelemetryAdapter = telemetry or TelemetryAdapter()
        self.golden_path: GoldenPathBridge = golden_path or GoldenPathBridge()

    # ------------------------------------------------------------------
    # Key management helpers
    # ------------------------------------------------------------------

    def store_key(self, name: str, value: str) -> str:
        """Store a credential agentically and return the backend used."""
        backend = store_api_key(name, value)
        self.telemetry.collect_metric(
            metric_type="system_events",
            metric_name="key_stored",
            value=1.0,
            labels={"key_name": name, "backend": backend},
        )
        return backend

    def retrieve_key(self, name: str) -> Optional[str]:
        """Retrieve a stored credential."""
        return retrieve_api_key(name)

    # ------------------------------------------------------------------
    # Telemetry helpers
    # ------------------------------------------------------------------

    def track_event(self, event_name: str, labels: Optional[Dict] = None) -> None:
        """Emit a telemetry event for observability."""
        self.telemetry.collect_metric(
            metric_type="system_events",
            metric_name=event_name,
            value=1.0,
            labels=labels or {},
        )

    # ------------------------------------------------------------------
    # Golden path helpers
    # ------------------------------------------------------------------

    def record_onboarding_path(
        self,
        business_type: str,
        execution_spec: Dict,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Record a successful onboarding path for future replay."""
        return self.golden_path.record_success(
            task_pattern=f"onboarding:{business_type}",
            domain="onboarding",
            execution_spec=execution_spec,
            metadata=metadata,
        )

    def replay_onboarding_path(self, path_id: str) -> Optional[Dict]:
        """Replay a proven onboarding path spec."""
        return self.golden_path.replay_path(path_id)


# ---------------------------------------------------------------------------
# OnboardingOrchestrator — full lifecycle manager
# ---------------------------------------------------------------------------


class OnboardingOrchestrator:
    """
    Manages the complete agentic onboarding lifecycle from intake through
    deployment.

    Lifecycle:  intake → provisioning → building → deploying → active
    """

    def __init__(self, engine: Optional[AgenticOnboardingEngine] = None) -> None:
        self._engine: AgenticOnboardingEngine = engine or AgenticOnboardingEngine()
        self._profiles: Dict[str, OnboardingProfile] = {}
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_regulatory_zone(country: str) -> str:
        entry = REGULATORY_ZONES.get(country, REGULATORY_ZONES["default"])
        return entry["zone"]

    @staticmethod
    def _integrations_for_type(business_type: str) -> List[str]:
        demo = BUSINESS_DEMOGRAPHICS.get(business_type, {})
        return list(demo.get("integrations", []))

    @staticmethod
    def _parse_requirements(text: str) -> List[str]:
        """
        Very lightweight NLP-free requirements extractor.

        Splits on sentence boundaries and common list markers then
        filters out short/empty tokens.
        """
        if not text or not text.strip():
            return []

        # Replace common list markers with a consistent delimiter
        import re
        normalised = re.sub(r"[\r\n]+", "\n", text)
        normalised = re.sub(r"[•·*\-]\s+", "\n", normalised)
        normalised = re.sub(r"\d+\.\s+", "\n", normalised)

        candidates = []
        for sentence in re.split(r"[;\n]", normalised):
            sentence = sentence.strip().strip(".")
            if len(sentence) >= 5:
                candidates.append(sentence)
        return candidates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_onboarding(
        self,
        business_name: str,
        business_type: str,
        industry: str,
        country: str,
        language: str,
        email: str,
        requirements_text: str = "",
        region: str = "",
    ) -> OnboardingProfile:
        """
        Create a new OnboardingProfile and kick off the intake phase.

        Returns the newly created profile.
        """
        profile_id = f"onb-{uuid.uuid4().hex[:12]}"
        regulatory_zone = self._resolve_regulatory_zone(country)
        integrations_needed = self._integrations_for_type(business_type)
        requirements_extracted = self._parse_requirements(requirements_text)

        profile = OnboardingProfile(
            profile_id=profile_id,
            business_name=business_name,
            business_type=business_type,
            industry=industry,
            country=country,
            region=region,
            language=language,
            regulatory_zone=regulatory_zone,
            email=email,
            requirements_extracted=requirements_extracted,
            integrations_needed=integrations_needed,
            status="intake",
        )

        with self._lock:
            self._profiles[profile_id] = profile

        self._engine.track_event(
            "onboarding_started",
            {
                "profile_id": profile_id,
                "business_type": business_type,
                "country": country,
            },
        )
        logger.info("Started onboarding for %s (%s)", business_name, profile_id)
        return profile

    def extract_requirements(self, profile_id: str, text: str) -> List[str]:
        """
        Parse an email or free-text intake form into structured requirements
        and attach them to the profile.
        """
        requirements = self._parse_requirements(text)

        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise KeyError(f"Profile not found: {profile_id}")
            # Merge without duplicates
            existing = set(profile.requirements_extracted)
            for req in requirements:
                if req not in existing:
                    profile.requirements_extracted.append(req)
                    existing.add(req)

        self._engine.track_event(
            "requirements_extracted",
            {"profile_id": profile_id, "count": str(len(requirements))},
        )
        return requirements

    def provision_integrations(self, profile_id: str) -> Dict[str, str]:
        """
        Agentically simulate account creation for every integration needed.

        Transitions: pending → provisioning → active | failed
        Stores generated credentials via SecureKeyManager.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise KeyError(f"Profile not found: {profile_id}")
            profile.status = "provisioning"
            integrations = list(profile.integrations_needed)

        status_map: Dict[str, str] = {}

        for integration in integrations:
            status_map[integration] = "pending"

        # Simulate the provisioning flow for each integration
        for integration in integrations:
            status_map[integration] = "provisioning"
            try:
                # Generate a synthetic API credential for this integration
                synthetic_key = f"murph_{profile_id}_{integration}_{uuid.uuid4().hex[:8]}"
                key_name = f"{profile_id}:{integration}:api_key"
                self._engine.store_key(key_name, synthetic_key)
                status_map[integration] = "active"
            except Exception as exc:
                logger.error(
                    "Provisioning failed for %s/%s: %s", profile_id, integration, exc
                )
                status_map[integration] = "failed"

        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is not None:
                profile.integrations_provisioned = dict(status_map)
                all_ok = all(v == "active" for v in status_map.values())
                profile.status = "building" if all_ok else "failed"

        self._engine.track_event(
            "integrations_provisioned",
            {"profile_id": profile_id, "count": str(len(integrations))},
        )
        return status_map

    def build_system(self, profile_id: str) -> Dict:
        """
        Generate the Murphy system configuration from the onboarding profile.

        Returns a configuration dict describing the system to be built.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise KeyError(f"Profile not found: {profile_id}")

        regulatory_info = REGULATORY_ZONES.get(
            profile.country, REGULATORY_ZONES["default"]
        )

        config = {
            "profile_id": profile_id,
            "business_name": profile.business_name,
            "business_type": profile.business_type,
            "industry": profile.industry,
            "language": profile.language,
            "regulatory_zone": profile.regulatory_zone,
            "frameworks": regulatory_info.get("frameworks", []),
            "integrations": profile.integrations_needed,
            "provisioned": profile.integrations_provisioned,
            "requirements": profile.requirements_extracted,
            "murphy_version": "1.0",
            "built_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is not None and profile.status not in ("failed",):
                profile.status = "deploying"

        # Record as a golden path for future reuse
        self._engine.record_onboarding_path(
            business_type=profile.business_type,
            execution_spec={"config": config},
            metadata={"profile_id": profile_id},
        )

        self._engine.track_event(
            "system_built", {"profile_id": profile_id, "business_type": profile.business_type}
        )
        logger.info("Built system config for %s", profile_id)
        return config

    def deploy(self, profile_id: str, target: str = "cloudflare") -> Dict:
        """
        Generate a deployment manifest for the specified target platform.

        Supported targets: cloudflare, aws, gcp, self_hosted
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                raise KeyError(f"Profile not found: {profile_id}")
            profile.deployment_target = target

        manifest: Dict = {}

        if target == "cloudflare":
            manifest = {
                "platform": "cloudflare",
                "type": "workers",
                "wrangler_config": {
                    "name": f"murphy-{profile_id}",
                    "main": "src/index.js",
                    "compatibility_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "account_id": f"<account_id_for_{profile_id}>",
                    "routes": [{"pattern": f"murphy-{profile.business_name.lower().replace(' ', '-')}.*"}],
                    "vars": {
                        "PROFILE_ID": profile_id,
                        "BUSINESS_TYPE": profile.business_type,
                        "REGULATORY_ZONE": profile.regulatory_zone,
                    },
                },
            }
        elif target == "aws":
            manifest = {
                "platform": "aws",
                "type": "lambda",
                "function_name": f"murphy-{profile_id}",
                "runtime": "python3.11",
                "handler": "handler.main",
                "environment": {
                    "PROFILE_ID": profile_id,
                    "BUSINESS_TYPE": profile.business_type,
                    "REGULATORY_ZONE": profile.regulatory_zone,
                },
                "tags": {"murphy_profile": profile_id},
            }
        elif target == "gcp":
            manifest = {
                "platform": "gcp",
                "type": "cloud_run",
                "service_name": f"murphy-{profile_id}",
                "image": "gcr.io/murphy-system/runtime:latest",
                "env_vars": {
                    "PROFILE_ID": profile_id,
                    "BUSINESS_TYPE": profile.business_type,
                    "REGULATORY_ZONE": profile.regulatory_zone,
                },
            }
        else:
            # self_hosted / generic
            manifest = {
                "platform": "self_hosted",
                "type": "docker_compose",
                "service_name": f"murphy-{profile_id}",
                "image": "murphy-system/runtime:latest",
                "environment": {
                    "PROFILE_ID": profile_id,
                    "BUSINESS_TYPE": profile.business_type,
                    "REGULATORY_ZONE": profile.regulatory_zone,
                },
            }

        manifest["deployed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["profile_id"] = profile_id

        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is not None and profile.status not in ("failed",):
                profile.status = "active"

        self._engine.track_event(
            "deployment_generated", {"profile_id": profile_id, "target": target}
        )
        logger.info("Generated deployment manifest for %s → %s", profile_id, target)
        return manifest

    def get_profile(self, profile_id: str) -> Optional[OnboardingProfile]:
        """Return a profile by ID, or None if not found."""
        with self._lock:
            return self._profiles.get(profile_id)

    def list_profiles(self, status: Optional[str] = None) -> List[OnboardingProfile]:
        """Return all profiles, optionally filtered by status."""
        with self._lock:
            profiles = list(self._profiles.values())
        if status is not None:
            profiles = [p for p in profiles if p.status == status]
        return profiles

    def get_onboarding_status(self) -> Dict:
        """Return summary statistics across all onboarding sessions."""
        with self._lock:
            all_profiles = list(self._profiles.values())

        total = len(all_profiles)
        by_status: Dict[str, int] = {}
        by_business_type: Dict[str, int] = {}

        for profile in all_profiles:
            by_status[profile.status] = by_status.get(profile.status, 0) + 1
            by_business_type[profile.business_type] = (
                by_business_type.get(profile.business_type, 0) + 1
            )

        active = by_status.get("active", 0)
        success_rate = active / (total or 1)

        return {
            "total_profiles": total,
            "by_status": by_status,
            "by_business_type": by_business_type,
            "active_count": active,
            "success_rate": round(success_rate, 4),
            "telemetry_summary": self._engine.telemetry.get_telemetry_summary(),
        }
