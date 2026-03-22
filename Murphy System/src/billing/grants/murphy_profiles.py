"""
Murphy Grant Profiles — Tenant-specific grant application profiles.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProfileFlavor(str, Enum):
    RD = "rd"
    ENERGY = "energy"
    MANUFACTURING = "manufacturing"
    GENERAL = "general"


@dataclass
class MurphyGrantProfile:
    flavor: ProfileFlavor
    company_name: str = ""
    ein: str = ""
    uei: str = ""
    cage_code: str = ""
    address: Dict[str, str] = field(default_factory=dict)
    naics_codes: List[str] = field(default_factory=list)
    employee_count: int = 0
    annual_revenue_usd: float = 0.0
    formation_date: str = ""
    company_type: str = ""
    poc_name: str = ""
    poc_email: str = ""
    poc_phone: str = ""
    technical_focus: str = ""
    rd_description: str = ""
    energy_focus: str = ""
    manufacturing_capabilities: str = ""
    mvp_modules: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)


_PROGRAM_FLAVOR_MAP: Dict[str, ProfileFlavor] = {
    "sbir": ProfileFlavor.RD,
    "sttr": ProfileFlavor.RD,
    "nsf": ProfileFlavor.RD,
    "arpa": ProfileFlavor.ENERGY,
    "doe": ProfileFlavor.ENERGY,
    "cesmii": ProfileFlavor.MANUFACTURING,
    "nist": ProfileFlavor.MANUFACTURING,
    "eda": ProfileFlavor.MANUFACTURING,
    "sba": ProfileFlavor.GENERAL,
    "usda": ProfileFlavor.GENERAL,
    "energy_trust": ProfileFlavor.ENERGY,
}

_MVP_MODULES: Dict[ProfileFlavor, List[str]] = {
    ProfileFlavor.RD: [
        "AI Research Assistant",
        "Technical Writing Engine",
        "Grant Intelligence",
        "Innovation Tracker",
    ],
    ProfileFlavor.ENERGY: [
        "Energy Analytics",
        "Sustainability Dashboard",
        "Carbon Tracker",
        "Utility Integration",
    ],
    ProfileFlavor.MANUFACTURING: [
        "Operations Intelligence",
        "Supply Chain Optimizer",
        "Quality Management",
        "Production Scheduler",
    ],
    ProfileFlavor.GENERAL: [
        "Business Intelligence",
        "Financial Analytics",
        "CRM Integration",
        "Workflow Automation",
    ],
}


class MurphyProfileManager:
    def __init__(self) -> None:
        self._profiles: Dict[str, MurphyGrantProfile] = {}
        self._tenant_sessions: Dict[str, str] = {}

    def _key(self, session_id: str, flavor: ProfileFlavor) -> str:
        return f"{session_id}:{flavor.value}"

    def create_profile(
        self,
        session_id: str,
        tenant_id: str,
        flavor: ProfileFlavor,
        data: Dict[str, Any],
    ) -> MurphyGrantProfile:
        self._tenant_sessions[session_id] = tenant_id
        profile = MurphyGrantProfile(
            flavor=flavor,
            company_name=data.get("company_name", ""),
            ein=data.get("ein", ""),
            uei=data.get("uei", ""),
            cage_code=data.get("cage_code", ""),
            address=data.get("address", {}),
            naics_codes=data.get("naics_codes", []),
            employee_count=int(data.get("employee_count", 0)),
            annual_revenue_usd=float(data.get("annual_revenue_usd", 0.0)),
            formation_date=data.get("formation_date", ""),
            company_type=data.get("company_type", ""),
            poc_name=data.get("poc_name", ""),
            poc_email=data.get("poc_email", ""),
            poc_phone=data.get("poc_phone", ""),
            technical_focus=data.get("technical_focus", ""),
            rd_description=data.get("rd_description", ""),
            energy_focus=data.get("energy_focus", ""),
            manufacturing_capabilities=data.get("manufacturing_capabilities", ""),
            mvp_modules=data.get("mvp_modules", self.get_mvp_modules(flavor)),
            custom_fields=data.get("custom_fields", {}),
        )
        self._profiles[self._key(session_id, flavor)] = profile
        return profile

    def get_profile(
        self,
        session_id: str,
        tenant_id: str,
        flavor: ProfileFlavor,
    ) -> Optional[MurphyGrantProfile]:
        stored_tenant = self._tenant_sessions.get(session_id)
        if stored_tenant is not None and stored_tenant != tenant_id:
            return None
        return self._profiles.get(self._key(session_id, flavor))

    def get_best_profile_for_program(
        self,
        session_id: str,
        tenant_id: str,
        program_id: str,
    ) -> Optional[MurphyGrantProfile]:
        flavor = self._resolve_flavor(program_id)
        profile = self.get_profile(session_id, tenant_id, flavor)
        if profile is None and flavor != ProfileFlavor.GENERAL:
            profile = self.get_profile(session_id, tenant_id, ProfileFlavor.GENERAL)
        return profile

    def _resolve_flavor(self, program_id: str) -> ProfileFlavor:
        pid_lower = program_id.lower()
        for prefix, flavor in _PROGRAM_FLAVOR_MAP.items():
            if prefix in pid_lower:
                return flavor
        return ProfileFlavor.GENERAL

    def to_form_data(self, profile: MurphyGrantProfile) -> Dict[str, Any]:
        addr = profile.address or {}
        data: Dict[str, Any] = {
            "company_name": profile.company_name,
            "company_legal_name": profile.company_name,
            "ein": profile.ein,
            "uei": profile.uei,
            "cage_code": profile.cage_code,
            "address_street": addr.get("street", ""),
            "address_city": addr.get("city", ""),
            "address_state": addr.get("state", ""),
            "address_zip": addr.get("zip", ""),
            "address_country": addr.get("country", "US"),
            "naics_codes": ", ".join(profile.naics_codes),
            "naics_code": profile.naics_codes[0] if profile.naics_codes else "",
            "employee_count": profile.employee_count,
            "annual_revenue_usd": profile.annual_revenue_usd,
            "annual_revenue": profile.annual_revenue_usd,
            "formation_date": profile.formation_date,
            "company_type": profile.company_type,
            "poc_name": profile.poc_name,
            "pi_name": profile.poc_name,
            "poc_email": profile.poc_email,
            "pi_email": profile.poc_email,
            "poc_phone": profile.poc_phone,
            "pi_phone": profile.poc_phone,
            "technical_focus": profile.technical_focus,
            "rd_description": profile.rd_description,
            "energy_focus": profile.energy_focus,
            "manufacturing_capabilities": profile.manufacturing_capabilities,
            "organization_name": profile.company_name,
            "legal_business_name": profile.company_name,
            "business_name": profile.company_name,
        }
        data.update(profile.custom_fields)
        return {k: v for k, v in data.items() if v not in (None, "", [], {})}

    def get_mvp_modules(self, flavor: ProfileFlavor) -> List[str]:
        return list(_MVP_MODULES.get(flavor, _MVP_MODULES[ProfileFlavor.GENERAL]))
