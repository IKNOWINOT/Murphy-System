"""
Setup Wizard — Agentic configuration wizard for Murphy System.

Enables Murphy System to configure itself by walking users through
a series of questions that determine which modules, bots, and
capabilities to activate.

Can be imported as a library or run from the command line:
    python -m src.setup_wizard
"""

import copy
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile dataclass
# ---------------------------------------------------------------------------

VALID_COMPANY_SIZES = ["small", "medium", "enterprise"]
VALID_AUTOMATION_TYPES = [
    "factory_iot", "content", "data", "system", "agent", "business",
]
VALID_SECURITY_LEVELS = ["basic", "standard", "hardened"]
VALID_ROBOTICS_PROTOCOLS = [
    "spot", "universal_robot", "ros2", "modbus", "bacnet",
    "opcua", "fanuc", "kuka", "abb", "dji", "clearpath", "mqtt",
]
VALID_LLM_PROVIDERS = ["local", "groq", "openai", "anthropic", "azure"]
VALID_COMPLIANCE_FRAMEWORKS = [
    "SOC2", "HIPAA", "GDPR", "PCI_DSS", "ISO27001", "none",
]
VALID_DEPLOYMENT_MODES = ["local", "docker", "kubernetes"]
VALID_INDUSTRIES = [
    "manufacturing", "technology", "finance", "healthcare",
    "retail", "energy", "media", "other",
]

# World Model integrations available during onboarding (free-tier first)
VALID_INTEGRATIONS = [
    # No credentials required (fully public APIs)
    "yahoo_finance",    # Market data — no API key required
    # Industrial (local network hardware — no cloud subscription)
    "scada",            # SCADA / ICS — requires local Modbus/BACnet/OPC UA hardware
    # Free tier (API key required — no cost to sign up)
    "openweathermap",   # Weather — free tier API key
    "discord",          # Communication bot
    "telegram",         # Communication bot
    "trello",           # Project management
    "asana",            # Project management
    "hubspot",          # CRM
    "mailchimp",        # Email marketing
    "google_drive",     # Cloud storage
    "dropbox",          # Cloud storage
    "stripe",           # Payments (free API key, pay-per-transaction)
    "google_analytics", # Analytics
    "twitter",          # Social media
    "supabase",         # Database
    "firebase",         # Database
    "datadog",          # Monitoring (free tier)
    "cloudflare",       # DNS / CDN (free tier)
    # Requires paid account or existing store
    "shopify",          # E-commerce (requires Shopify store)
    "openai",           # AI/ML (paid per-token API)
    "anthropic",        # AI/ML (paid per-token API)
]

@dataclass
class SetupProfile:
    """Stores all user configuration choices."""

    organization_name: str = ""
    industry: str = "other"
    company_size: str = "small"
    automation_types: List[str] = field(default_factory=list)
    security_level: str = "standard"
    robotics_enabled: bool = False
    robotics_protocols: List[str] = field(default_factory=list)
    avatar_enabled: bool = False
    avatar_connectors: List[str] = field(default_factory=list)
    llm_provider: str = "local"
    monitoring_enabled: bool = True
    compliance_frameworks: List[str] = field(default_factory=list)
    deployment_mode: str = "local"
    sales_automation_enabled: bool = False
    enabled_integrations: List[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Module / bot mapping tables
# ---------------------------------------------------------------------------

AUTOMATION_MODULE_MAP: Dict[str, List[str]] = {
    "factory_iot": [
        "building_automation_connectors",
        "manufacturing_automation_standards",
        "energy_management_connectors",
        "additive_manufacturing_connectors",
        "robotics",
    ],
    "content": [
        "content_creator_platform_modulator",
        "social_media_moderation",
        "digital_asset_generator",
    ],
    "data": [
        "cross_platform_data_sync",
        "analytics_dashboard",
        "ui_data_service",
    ],
    "system": [
        "full_automation_controller",
        "self_automation_orchestrator",
        "automation_scheduler",
    ],
    "agent": [
        "agentic_api_provisioner",
        "shadow_agent_integration",
        "advanced_swarm_system",
        "true_swarm_system",
        "domain_swarms",
    ],
    "business": [
        "trading_bot_engine",
        "executive_planning_engine",
        "workflow_template_marketplace",
    ],
}

INDUSTRY_BOT_MAP: Dict[str, List[str]] = {
    "manufacturing": [
        "factory_floor_bot", "quality_assurance_bot", "supply_chain_bot",
    ],
    "technology": [
        "devops_bot", "code_review_bot", "incident_response_bot",
    ],
    "finance": [
        "trading_bot", "compliance_bot", "risk_analysis_bot",
    ],
    "healthcare": [
        "patient_data_bot", "compliance_bot", "scheduling_bot",
    ],
    "retail": [
        "inventory_bot", "customer_service_bot", "pricing_bot",
    ],
    "energy": [
        "grid_monitor_bot", "energy_optimization_bot", "safety_bot",
    ],
    "media": [
        "content_generation_bot", "moderation_bot", "analytics_bot",
    ],
    "other": [
        "general_assistant_bot",
    ],
}

AUTOMATION_BOT_MAP: Dict[str, List[str]] = {
    "factory_iot": ["sensor_monitor_bot", "actuator_control_bot"],
    "content": ["content_creation_bot", "social_media_bot"],
    "data": ["data_pipeline_bot", "analytics_bot"],
    "system": ["system_admin_bot", "automation_bot"],
    "agent": ["swarm_coordinator_bot", "agent_manager_bot"],
    "business": ["trading_bot", "executive_assistant_bot"],
}

SALES_MODULES = [
    "workflow_template_marketplace",
    "executive_planning_engine",
]

SALES_BOTS = [
    "sales_outreach_bot", "lead_scoring_bot", "marketing_automation_bot",
]

MONITORING_MODULES = [
    "compliance_monitoring_completeness",
    "bot_telemetry_normalizer",
]

CORE_MODULES = [
    "config",
    "module_manager",
    "automation_type_registry",
    "command_parser",
    "command_system",
    "conversation_handler",
    "compliance_engine",
    "authority_gate",
    "capability_map",
]

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def _build_questions() -> List[Dict[str, Any]]:
    """Return the ordered list of setup questions."""
    return [
        {
            "id": "q1",
            "text": "What is your organization's name?",
            "field": "organization_name",
            "question_type": "text",
            "options": None,
            "default": "",
        },
        {
            "id": "q2",
            "text": "What industry does your organization operate in?",
            "field": "industry",
            "question_type": "choice",
            "options": VALID_INDUSTRIES,
            "default": "other",
        },
        {
            "id": "q3",
            "text": "What is the size of your company?",
            "field": "company_size",
            "question_type": "choice",
            "options": VALID_COMPANY_SIZES,
            "default": "small",
        },
        {
            "id": "q4",
            "text": "Which automation types would you like to enable?",
            "field": "automation_types",
            "question_type": "multi_choice",
            "options": VALID_AUTOMATION_TYPES,
            "default": [],
        },
        {
            "id": "q5",
            "text": "What security level do you require?",
            "field": "security_level",
            "question_type": "choice",
            "options": VALID_SECURITY_LEVELS,
            "default": "standard",
        },
        {
            "id": "q6",
            "text": "Do you want to enable robotics integration?",
            "field": "robotics_enabled",
            "question_type": "boolean",
            "options": None,
            "default": False,
        },
        {
            "id": "q7",
            "text": "Which robotics protocols should be enabled?",
            "field": "robotics_protocols",
            "question_type": "multi_choice",
            "options": VALID_ROBOTICS_PROTOCOLS,
            "default": [],
        },
        {
            "id": "q8",
            "text": "Do you want to enable avatar identity?",
            "field": "avatar_enabled",
            "question_type": "boolean",
            "options": None,
            "default": False,
        },
        {
            "id": "q9",
            "text": "Which LLM provider would you like to use?",
            "field": "llm_provider",
            "question_type": "choice",
            "options": VALID_LLM_PROVIDERS,
            "default": "local",
        },
        {
            "id": "q10",
            "text": "Which compliance frameworks apply to your organization?",
            "field": "compliance_frameworks",
            "question_type": "multi_choice",
            "options": VALID_COMPLIANCE_FRAMEWORKS,
            "default": [],
        },
        {
            "id": "q11",
            "text": "What is your preferred deployment mode?",
            "field": "deployment_mode",
            "question_type": "choice",
            "options": VALID_DEPLOYMENT_MODES,
            "default": "local",
        },
        {
            "id": "q12",
            "text": "Do you want to enable sales automation?",
            "field": "sales_automation_enabled",
            "question_type": "boolean",
            "options": None,
            "default": False,
        },
        {
            "id": "q13",
            "text": "Which external integrations would you like to enable?",
            "field": "enabled_integrations",
            "question_type": "multi_choice",
            "options": VALID_INTEGRATIONS,
            "default": [],
        },
    ]

# ---------------------------------------------------------------------------
# Wizard class
# ---------------------------------------------------------------------------

class SetupWizard:
    """
    Agentic setup wizard that walks users through Murphy System configuration.

    Can be driven programmatically (call apply_answer for each question) or
    interactively via the CLI entry-point.
    """

    def __init__(self) -> None:
        self._profile = SetupProfile()
        self._questions = _build_questions()
        self._question_index = {q["id"]: q for q in self._questions}

    # -- public API ---------------------------------------------------------

    def get_questions(self) -> List[Dict[str, Any]]:
        """Return the ordered list of setup questions."""
        return copy.deepcopy(self._questions)

    def apply_answer(self, question_id: str, answer: Any) -> Dict[str, Any]:
        """
        Validate and apply an answer for the given question.

        Returns a status dict: {"ok": bool, "error": str | None}
        """
        if question_id not in self._question_index:
            return {"ok": False, "error": f"Unknown question id: {question_id}"}

        question = self._question_index[question_id]
        qtype = question["question_type"]
        field_name = question["field"]
        options = question.get("options")

        # -- validation -----------------------------------------------------
        if qtype == "text":
            if not isinstance(answer, str):
                return {"ok": False, "error": "Expected a text string"}
        elif qtype == "choice":
            if answer not in (options or []):
                return {
                    "ok": False,
                    "error": f"Invalid choice '{answer}'. Options: {options}",
                }
        elif qtype == "multi_choice":
            if not isinstance(answer, list):
                return {"ok": False, "error": "Expected a list of choices"}
            invalid = [a for a in answer if a not in (options or [])]
            if invalid:
                return {
                    "ok": False,
                    "error": f"Invalid choices: {invalid}. Options: {options}",
                }
        elif qtype == "boolean":
            if not isinstance(answer, bool):
                return {"ok": False, "error": "Expected a boolean value"}
        else:
            return {"ok": False, "error": f"Unknown question type: {qtype}"}

        setattr(self._profile, field_name, answer)
        return {"ok": True, "error": None}

    def get_profile(self) -> SetupProfile:
        """Return the current profile."""
        return self._profile

    def generate_config(self, profile: SetupProfile) -> Dict[str, Any]:
        """Generate a complete Murphy System configuration dict."""
        modules = self.get_enabled_modules(profile)
        bots = self.get_recommended_bots(profile)

        config: Dict[str, Any] = {
            "organization": {
                "name": profile.organization_name,
                "industry": profile.industry,
                "company_size": profile.company_size,
            },
            "automation": {
                "enabled_types": profile.automation_types,
            },
            "security": {
                "level": profile.security_level,
                "compliance_frameworks": profile.compliance_frameworks,
            },
            "robotics": {
                "enabled": profile.robotics_enabled,
                "protocols": profile.robotics_protocols,
            },
            "avatar": {
                "enabled": profile.avatar_enabled,
                "connectors": profile.avatar_connectors,
            },
            "llm": {
                "provider": profile.llm_provider,
            },
            "monitoring": {
                "enabled": profile.monitoring_enabled,
            },
            "deployment": {
                "mode": profile.deployment_mode,
            },
            "sales_automation": {
                "enabled": profile.sales_automation_enabled,
            },
            "integrations": {
                "enabled": list(profile.enabled_integrations),
                "credentials_env_var_prefix": "MURPHY_",
            },
            "modules": modules,
            "bots": bots,
        }
        return config

    def get_enabled_modules(self, profile: SetupProfile) -> List[str]:
        """Return the list of modules that should be enabled."""
        modules = list(CORE_MODULES)

        for atype in profile.automation_types:
            for mod in AUTOMATION_MODULE_MAP.get(atype, []):
                if mod not in modules:
                    modules.append(mod)

        if profile.robotics_enabled:
            if "robotics" not in modules:
                modules.append("robotics")

        if profile.avatar_enabled:
            if "avatar" not in modules:
                modules.append("avatar")

        if profile.monitoring_enabled:
            for mod in MONITORING_MODULES:
                if mod not in modules:
                    modules.append(mod)

        if profile.sales_automation_enabled:
            for mod in SALES_MODULES:
                if mod not in modules:
                    modules.append(mod)

        if profile.compliance_frameworks:
            effective = [f for f in profile.compliance_frameworks if f != "none"]
            if effective:
                for mod in ["compliance_engine", "compliance_region_validator",
                            "contractual_audit"]:
                    if mod not in modules:
                        modules.append(mod)

        return modules

    def get_recommended_bots(self, profile: SetupProfile) -> List[str]:
        """Return recommended bots based on profile."""
        bots: List[str] = []

        for bot in INDUSTRY_BOT_MAP.get(profile.industry, []):
            if bot not in bots:
                bots.append(bot)

        for atype in profile.automation_types:
            for bot in AUTOMATION_BOT_MAP.get(atype, []):
                if bot not in bots:
                    bots.append(bot)

        if profile.sales_automation_enabled:
            for bot in SALES_BOTS:
                if bot not in bots:
                    bots.append(bot)

        return bots

    def validate_profile(self, profile: SetupProfile) -> Dict[str, Any]:
        """
        Validate profile completeness.

        Returns {"valid": bool, "issues": List[str]}
        """
        issues: List[str] = []

        if not profile.organization_name:
            issues.append("Organization name is required")

        if profile.industry not in VALID_INDUSTRIES:
            issues.append(f"Invalid industry: {profile.industry}")

        if profile.company_size not in VALID_COMPANY_SIZES:
            issues.append(f"Invalid company size: {profile.company_size}")

        if profile.security_level not in VALID_SECURITY_LEVELS:
            issues.append(f"Invalid security level: {profile.security_level}")

        if profile.llm_provider not in VALID_LLM_PROVIDERS:
            issues.append(f"Invalid LLM provider: {profile.llm_provider}")

        if profile.deployment_mode not in VALID_DEPLOYMENT_MODES:
            issues.append(f"Invalid deployment mode: {profile.deployment_mode}")

        if profile.robotics_enabled and not profile.robotics_protocols:
            issues.append(
                "Robotics is enabled but no protocols are selected"
            )

        for atype in profile.automation_types:
            if atype not in VALID_AUTOMATION_TYPES:
                issues.append(f"Invalid automation type: {atype}")

        return {"valid": len(issues) == 0, "issues": issues}

    # -- Tuning #1: cross-reference inference --------------------------------
    # If the user's automation_types or organization_name imply sales usage
    # but q12 (sales_automation_enabled) is still False, suggest enabling it.

    _SALES_HINT_KEYWORDS = frozenset([
        "sales", "pipeline", "lead", "crm", "outreach", "prospect",
        "revenue", "deal", "quota", "commission",
    ])

    def infer_sales_enabled(self, profile: Optional[SetupProfile] = None) -> Dict[str, Any]:
        """
        Cross-reference profile fields to infer whether sales automation
        should be enabled.

        Returns {"should_enable": bool, "reason": str}
        """
        profile = profile or self._profile
        if profile.sales_automation_enabled:
            return {"should_enable": False, "reason": "Already enabled"}

        # Check automation types for business/agent (common sales triggers)
        if "business" in profile.automation_types:
            return {
                "should_enable": True,
                "reason": "Automation type 'business' selected — sales modules recommended",
            }

        # Check organization name for sales-related keywords
        org_lower = profile.organization_name.lower()
        for kw in self._SALES_HINT_KEYWORDS:
            if kw in org_lower:
                return {
                    "should_enable": True,
                    "reason": f"Organization name contains '{kw}' — sales modules recommended",
                }

        return {"should_enable": False, "reason": "No sales indicators detected"}

    def export_config(self, config: Dict[str, Any], path: str) -> None:
        """Export configuration to a JSON file."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)

    def summarize(self, profile: SetupProfile) -> str:
        """Return a human-readable summary of the configuration."""
        lines = [
            "Murphy System Configuration Summary",
            "=" * 40,
            f"Organization : {profile.organization_name or '(not set)'}",
            f"Industry     : {profile.industry}",
            f"Company Size : {profile.company_size}",
            f"Automation   : {', '.join(profile.automation_types) or 'none'}",
            f"Security     : {profile.security_level}",
            f"Robotics     : {'enabled' if profile.robotics_enabled else 'disabled'}",
        ]
        if profile.robotics_enabled and profile.robotics_protocols:
            lines.append(
                f"  Protocols  : {', '.join(profile.robotics_protocols)}"
            )
        lines.extend([
            f"Avatar       : {'enabled' if profile.avatar_enabled else 'disabled'}",
            f"LLM Provider : {profile.llm_provider}",
            f"Monitoring   : {'enabled' if profile.monitoring_enabled else 'disabled'}",
            f"Compliance   : {', '.join(profile.compliance_frameworks) or 'none'}",
            f"Deployment   : {profile.deployment_mode}",
            f"Sales Auto   : {'enabled' if profile.sales_automation_enabled else 'disabled'}",
            f"Integrations : {', '.join(profile.enabled_integrations) or 'none'}",
        ])

        modules = self.get_enabled_modules(profile)
        bots = self.get_recommended_bots(profile)
        lines.append(f"Modules ({len(modules)}) : {', '.join(modules[:5])}{'...' if len(modules) > 5 else ''}")
        lines.append(f"Bots    ({len(bots)})    : {', '.join(bots[:5])}{'...' if len(bots) > 5 else ''}")

        return "\n".join(lines)

# ---------------------------------------------------------------------------
# Deployment preset profiles
# ---------------------------------------------------------------------------

PRESET_PROFILES: Dict[str, Dict[str, Any]] = {
    # ------------------------------------------------------------------
    # 1. Solo Operator — one-person owner-operator running everything
    # ------------------------------------------------------------------
    "solo_operator": {
        "id": "solo_operator",
        "name": "Solo Operator",
        "description": (
            "For a single owner-operator who wears every hat. "
            "Enables business automation, data dashboards, content tools, "
            "and sales outreach so one person can run an entire operation "
            "with HITL approval on all critical actions."
        ),
        "profile": {
            "organization_name": "",  # filled by user
            "industry": "other",
            "company_size": "small",
            "automation_types": ["business", "data", "content"],
            "security_level": "standard",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "groq",
            "monitoring_enabled": True,
            "compliance_frameworks": ["none"],
            "deployment_mode": "local",
            "sales_automation_enabled": True,
        },
    },

    # ------------------------------------------------------------------
    # 2. Personal Assistant — lightweight automations for individuals
    # ------------------------------------------------------------------
    "personal_assistant": {
        "id": "personal_assistant",
        "name": "Personal Assistant",
        "description": (
            "Minimal footprint for someone who wants a smart assistant. "
            "Enables data sync, basic system automation, and an AI avatar "
            "for day-to-day task support — no heavy infrastructure."
        ),
        "profile": {
            "organization_name": "",
            "industry": "other",
            "company_size": "small",
            "automation_types": ["data", "system"],
            "security_level": "basic",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "local",
            "monitoring_enabled": False,
            "compliance_frameworks": ["none"],
            "deployment_mode": "local",
            "sales_automation_enabled": False,
        },
    },

    # ------------------------------------------------------------------
    # 3. Org Onboarding — org chart mirroring with HR onboarding
    # ------------------------------------------------------------------
    "org_onboarding": {
        "id": "org_onboarding",
        "name": "Org Chart & Onboarding",
        "description": (
            "Mirrors a corporate org chart with shadow agents per role. "
            "Includes onboarding workflows with employment-offer letter "
            "generation, HITL approvals at every hiring stage, and form "
            "generation for new-hire paperwork."
        ),
        "profile": {
            "organization_name": "",
            "industry": "other",
            "company_size": "medium",
            "automation_types": ["business", "agent", "data"],
            "security_level": "standard",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "groq",
            "monitoring_enabled": True,
            "compliance_frameworks": ["SOC2"],
            "deployment_mode": "docker",
            "sales_automation_enabled": False,
        },
    },

    # ------------------------------------------------------------------
    # 4. Startup Growth (recommended) — scaling startup
    # ------------------------------------------------------------------
    "startup_growth": {
        "id": "startup_growth",
        "name": "Startup Growth",
        "description": (
            "Recommended for early-stage companies scaling fast. "
            "Combines sales automation with agentic swarms, data "
            "pipelines, and content generation — all with HITL gates "
            "so the founding team stays in control."
        ),
        "profile": {
            "organization_name": "",
            "industry": "technology",
            "company_size": "small",
            "automation_types": ["business", "agent", "data", "content"],
            "security_level": "standard",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "groq",
            "monitoring_enabled": True,
            "compliance_frameworks": ["SOC2"],
            "deployment_mode": "docker",
            "sales_automation_enabled": True,
        },
    },

    # ------------------------------------------------------------------
    # 5. Enterprise Compliance (recommended) — full compliance stack
    # ------------------------------------------------------------------
    "enterprise_compliance": {
        "id": "enterprise_compliance",
        "name": "Enterprise Compliance",
        "description": (
            "Recommended for regulated enterprises. Enables every "
            "automation type with hardened security, full compliance "
            "frameworks (SOC2, HIPAA, GDPR, ISO27001), and Kubernetes "
            "deployment for production-grade infrastructure."
        ),
        "profile": {
            "organization_name": "",
            "industry": "finance",
            "company_size": "enterprise",
            "automation_types": [
                "factory_iot", "content", "data", "system", "agent",
                "business",
            ],
            "security_level": "hardened",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "azure",
            "monitoring_enabled": True,
            "compliance_frameworks": ["SOC2", "HIPAA", "GDPR", "ISO27001"],
            "deployment_mode": "kubernetes",
            "sales_automation_enabled": True,
        },
    },

    # ------------------------------------------------------------------
    # 6. Agency Automation (recommended) — consultancies & agencies
    # ------------------------------------------------------------------
    "agency_automation": {
        "id": "agency_automation",
        "name": "Agency Automation",
        "description": (
            "Recommended for agencies, consultancies, and service firms. "
            "Focuses on content creation, client-facing sales outreach, "
            "agentic task delegation, and data analytics — with HITL "
            "checkpoints before any client-visible deliverable ships."
        ),
        "profile": {
            "organization_name": "",
            "industry": "media",
            "company_size": "medium",
            "automation_types": ["content", "agent", "data", "business"],
            "security_level": "standard",
            "robotics_enabled": False,
            "robotics_protocols": [],
            "avatar_enabled": True,
            "avatar_connectors": [],
            "llm_provider": "openai",
            "monitoring_enabled": True,
            "compliance_frameworks": ["GDPR"],
            "deployment_mode": "docker",
            "sales_automation_enabled": True,
        },
    },
}

def get_preset_profiles() -> Dict[str, Dict[str, Any]]:
    """Return all available deployment preset profiles.

    Each entry contains ``id``, ``name``, ``description``, and a ``profile``
    dict whose keys match the :class:`SetupProfile` fields.
    """
    return copy.deepcopy(PRESET_PROFILES)

def apply_preset(preset_id: str, organization_name: str = "") -> SetupProfile:
    """Instantiate a :class:`SetupProfile` from a named preset.

    Parameters
    ----------
    preset_id:
        Key into :data:`PRESET_PROFILES` (e.g. ``"solo_operator"``).
    organization_name:
        Optional override — presets ship with an empty org name so the
        caller can fill it in.

    Raises
    ------
    ValueError
        If *preset_id* is not a recognised preset.
    """
    if preset_id not in PRESET_PROFILES:
        raise ValueError(
            f"Unknown preset '{preset_id}'. "
            f"Available: {list(PRESET_PROFILES.keys())}"
        )
    data = copy.deepcopy(PRESET_PROFILES[preset_id]["profile"])
    if organization_name:
        data["organization_name"] = organization_name
    return SetupProfile(**data)

# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

_YES_WORDS = frozenset([
    "y", "yes", "true", "1", "sure", "yep", "yeah",
    "absolutely", "of course", "definitely",
])

_NO_WORDS = frozenset([
    "n", "no", "false", "0", "nah", "nope", "never",
])

_YES_PHRASES = (
    "yes please", "go ahead", "enable", "turn on",
    "i want", "i do", "let's do it",
)

_NO_PHRASES = (
    "not yet", "not now", "no thanks", "not right now",
    "maybe later", "skip", "none", "later",
)

_MULTI_SKIP_PHRASES = frozenset([
    "none", "skip", "later", "not yet", "not sure", "no idea",
    "i don't know", "i dont know", "i don't know yet", "i dont know yet",
])

def _parse_bool(raw: str) -> Optional[bool]:
    """Parse a yes/no string into a boolean.

    Handles natural-language responses such as "not yet", "sure", or "nah".
    """
    lower = raw.strip().lower()
    if lower in _YES_WORDS:
        return True
    if lower in _NO_WORDS:
        return False
    for phrase in _NO_PHRASES:
        if phrase in lower:
            return False
    for phrase in _YES_PHRASES:
        if phrase in lower:
            return True
    return None

def _fuzzy_match_choice(raw: str, options: List[str]) -> Optional[str]:
    """Try to extract a valid option from free-text input.

    For example, ``"local for now."`` matches ``"local"`` when
    ``options`` is ``["local", "groq", "openai", ...]``.
    """
    lower = raw.strip().lower()
    # Exact match (case-insensitive)
    for opt in options:
        if lower == opt.lower():
            return opt
    # The input starts with a valid option followed by non-alpha chars or space
    for opt in options:
        ol = opt.lower()
        if lower.startswith(ol) and (
            len(lower) == len(ol) or not lower[len(ol)].isalpha()
        ):
            return opt
    # A valid option appears as a standalone word in the input
    words = lower.replace(",", " ").replace(".", " ").split()
    for opt in options:
        if opt.lower() in words:
            return opt
    return None

def _fuzzy_match_multi_choice(raw: str, options: List[str]) -> Optional[List[str]]:
    """Try to extract valid options from free-text input.

    Recognises ``"all"``, ``"all of them"``, ``"all of those"`` as selecting
    every option.  Recognises uncertainty phrases like ``"I don't know"`` or
    ``"skip"`` as an empty selection.  Also attempts to find individual options
    mentioned in the user's response.
    """
    lower = raw.strip().lower()
    # "all" / "all of them" / "all of those" / "everything"
    if lower in ("all", "everything") or lower.startswith("all of"):
        return list(options)
    # "none" / uncertainty / deferral phrases → empty list (use default)
    if lower in _MULTI_SKIP_PHRASES:
        return []
    # Build a case-insensitive lookup for option matching
    options_lower = {opt.lower(): opt for opt in options}
    # Try comma-separated first (normal path)
    parts = [v.strip().lower() for v in raw.split(",") if v.strip()]
    valid = [options_lower[p] for p in parts if p in options_lower]
    if valid:
        return valid
    # Try to find individual options mentioned anywhere in the text
    words = lower.replace(",", " ").replace(".", " ").split()
    found = [opt for opt in options if opt.lower() in words]
    if found:
        return found
    return None

def run_cli() -> None:
    """Interactive CLI session that walks through all setup questions."""
    wizard = SetupWizard()
    questions = wizard.get_questions()

    print("\n🔧  Murphy System Setup Wizard")
    print("=" * 40)
    print("Answer the following questions to configure your system.\n")

    step = 0
    for q in questions:
        qid = q["id"]
        qtype = q["question_type"]
        field_name = q["field"]

        # Skip robotics protocols if robotics is disabled
        if qid == "q7" and not wizard.get_profile().robotics_enabled:
            wizard.apply_answer(qid, [])
            continue

        step += 1
        print(f"\n[Step {step}] {q['text']}")

        if qtype == "choice":
            print(f"  Options: {', '.join(q['options'])}")
            print(f"  Default: {q['default']}")
            raw = input("  > ").strip()
            if not raw:
                answer = q["default"]
            else:
                matched = _fuzzy_match_choice(raw, q["options"])
                answer = matched if matched is not None else raw

        elif qtype == "multi_choice":
            print(f"  Options: {', '.join(q['options'])}")
            print("  Enter comma-separated values, 'all', or press Enter for none:")
            raw = input("  > ").strip()
            if not raw:
                answer = q["default"] if q["default"] else []
            else:
                matched = _fuzzy_match_multi_choice(raw, q["options"])
                answer = matched if matched is not None else [v.strip() for v in raw.split(",") if v.strip()]

        elif qtype == "boolean":
            print("  (yes/no)")
            raw = input("  > ").strip()
            parsed = _parse_bool(raw)
            answer = parsed if parsed is not None else q["default"]

        else:  # text
            if q["default"]:
                print(f"  Default: {q['default']}")
            raw = input("  > ").strip()
            answer = raw if raw else q["default"]

        result = wizard.apply_answer(qid, answer)
        if not result["ok"]:
            print(f"  ⚠ {result['error']} — using default")
            wizard.apply_answer(qid, q["default"])

    profile = wizard.get_profile()
    validation = wizard.validate_profile(profile)

    print("\n" + wizard.summarize(profile))

    if not validation["valid"]:
        print("\n⚠ Validation issues:")
        for issue in validation["issues"]:
            print(f"  - {issue}")

    config = wizard.generate_config(profile)
    print(f"\nConfiguration ready with {len(config['modules'])} modules "
          f"and {len(config['bots'])} bots.")

    save = input("\nExport configuration to file? (y/n) > ").strip().lower()
    if save in ("y", "yes"):
        path = input("File path [murphy_config.json] > ").strip()
        path = path or "murphy_config.json"
        wizard.export_config(config, path)
        print(f"Configuration saved to {path}")

    print("\n✅  Setup complete.\n")

if __name__ == "__main__":
    run_cli()
