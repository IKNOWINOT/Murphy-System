"""
Murphy Terminal — Universal Command Registry
============================================

Maps every Murphy System module (200+) to:
  - A slash command  (e.g. ``/health``)
  - A chat command   (e.g. ``!murphy health``)
  - Natural-language aliases (e.g. ``["how is murphy", "system health"]``)

The registry is the single source of truth for the Librarian NLP router,
the Matrix command dispatcher, the terminal handler, and any future
REST-API auto-discovery endpoint.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommandCategory(str, Enum):
    """Top-level subsystem groupings."""

    SYSTEM = "system"
    GOVERNANCE = "governance"
    SECURITY = "security"
    EXECUTION = "execution"
    AUTOMATION = "automation"
    CONFIDENCE = "confidence"
    LLM = "llm"
    INTELLIGENCE = "intelligence"
    SWARM = "swarm"
    LEARNING = "learning"
    FINANCE = "finance"
    CRYPTO = "crypto"
    BUSINESS = "business"
    MARKETING = "marketing"
    CONTENT = "content"
    CRM = "crm"
    ORG = "org"
    ONBOARDING = "onboarding"
    INFRA = "infra"
    HEALTH = "health"
    IOT = "iot"
    RPA = "rpa"
    TELEMETRY = "telemetry"
    DASHBOARDS = "dashboards"
    ALERTS = "alerts"
    AUDIT = "audit"
    COMPLIANCE = "compliance"
    INTEGRATIONS = "integrations"
    COMMS = "comms"
    BOTS = "bots"
    DEV = "dev"
    DATA = "data"
    ML = "ml"
    MFGC = "mfgc"
    FOUNDATION = "foundation"
    RESEARCH = "research"
    TERMINAL = "terminal"
    MANAGEMENT_SYSTEMS = "management_systems"


# ---------------------------------------------------------------------------
# CommandDefinition
# ---------------------------------------------------------------------------


@dataclass
class CommandDefinition:
    """Describes a single Murphy module command."""

    module_name: str
    slash_command: str
    chat_command: str
    nl_aliases: list[str]
    category: CommandCategory
    description: str
    usage: str
    requires_args: bool = False
    min_role: str = "viewer"       # viewer | developer | operator | admin
    subcommands: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "slash_command": self.slash_command,
            "chat_command": self.chat_command,
            "nl_aliases": self.nl_aliases,
            "category": self.category.value,
            "description": self.description,
            "usage": self.usage,
            "requires_args": self.requires_args,
            "min_role": self.min_role,
            "subcommands": self.subcommands,
            "examples": self.examples,
        }


# ---------------------------------------------------------------------------
# Full command catalogue
# ---------------------------------------------------------------------------

MURPHY_COMMANDS: list[CommandDefinition] = [
    # ── SYSTEM ─────────────────────────────────────────────────────────────
    CommandDefinition("system_integrator", "/system integrate", "!murphy system integrate",
        ["integrate systems", "system integration", "run integrator"],
        CommandCategory.SYSTEM, "Run the system integrator", "/system integrate [--module NAME]",
        subcommands=["status", "run", "validate"],
        examples=["!murphy system integrate --module llm_controller"]),
    CommandDefinition("modular_runtime", "/runtime status", "!murphy runtime status",
        ["runtime status", "check runtime", "is runtime running"],
        CommandCategory.SYSTEM, "Query modular runtime state", "/runtime [status|reload|list]",
        subcommands=["status", "reload", "list"]),
    CommandDefinition("module_manager", "/modules", "!murphy modules",
        ["list modules", "show modules", "what modules", "module list"],
        CommandCategory.SYSTEM, "Module lifecycle management", "/modules [list|load|unload NAME]",
        subcommands=["list", "load", "unload", "reload"]),
    CommandDefinition("module_registry", "/modules registry", "!murphy modules registry",
        ["module registry", "registered modules"],
        CommandCategory.SYSTEM, "View registered module descriptors", "/modules registry [--filter STATUS]"),
    CommandDefinition("startup_feature_summary", "/startup features", "!murphy startup features",
        ["startup features", "feature summary", "boot features"],
        CommandCategory.SYSTEM, "Show features enabled at startup", "/startup features"),
    CommandDefinition("readiness_scanner", "/readiness", "!murphy readiness",
        ["readiness check", "is murphy ready", "check readiness"],
        CommandCategory.SYSTEM, "Scan system readiness", "/readiness [--verbose]"),
    # ── GOVERNANCE ─────────────────────────────────────────────────────────
    CommandDefinition("governance_kernel", "/governance", "!murphy governance",
        ["governance status", "check governance", "governance mode", "what is governance"],
        CommandCategory.GOVERNANCE, "Query governance kernel", "/governance [status|mode|check TASK]",
        subcommands=["status", "mode", "check", "report"]),
    CommandDefinition("governance_toggle", "/governance toggle", "!murphy governance toggle",
        ["toggle governance", "switch governance mode", "change governance"],
        CommandCategory.GOVERNANCE, "Toggle governance strict/permissive", "/governance toggle [strict|permissive]",
        min_role="operator"),
    CommandDefinition("gate_builder", "/gate build", "!murphy gate build",
        ["build gate", "create gate", "new gate"],
        CommandCategory.GOVERNANCE, "Build a governance gate", "/gate build <spec>",
        requires_args=True, min_role="operator"),
    CommandDefinition("gate_bypass_controller", "/gate bypass", "!murphy gate bypass",
        ["bypass gate", "request bypass", "gate override"],
        CommandCategory.GOVERNANCE, "Request gate bypass (triggers HITL approval)", "/gate bypass <gate_id>",
        requires_args=True, min_role="operator"),
    CommandDefinition("authority_gate", "/gate authority", "!murphy gate authority",
        ["authority gate", "authority check", "gate authority level"],
        CommandCategory.GOVERNANCE, "Check authority gate", "/gate authority <level>",
        subcommands=["check", "list"]),
    CommandDefinition("cost_explosion_gate", "/gate cost", "!murphy gate cost",
        ["cost gate", "cost limit", "budget gate", "cost explosion"],
        CommandCategory.GOVERNANCE, "Check cost explosion gate", "/gate cost [--limit N]"),
    CommandDefinition("inference_gate_engine", "/gate inference", "!murphy gate inference",
        ["inference gate", "gate inference", "inference check"],
        CommandCategory.GOVERNANCE, "Run inference gate engine", "/gate inference <task>",
        requires_args=True),
    CommandDefinition("bot_governance_policy_mapper", "/governance policies", "!murphy governance policies",
        ["bot policies", "governance policies", "policy map"],
        CommandCategory.GOVERNANCE, "Map bot governance policies", "/governance policies [--bot NAME]"),
    # ── SECURITY ───────────────────────────────────────────────────────────
    CommandDefinition("security_audit_scanner", "/security audit", "!murphy security audit",
        ["security audit", "audit security", "scan security", "run security scan"],
        CommandCategory.SECURITY, "Run security audit scanner", "/security audit [--module NAME]",
        min_role="admin"),
    CommandDefinition("security_hardening_config", "/security harden", "!murphy security harden",
        ["harden security", "apply hardening", "security hardening"],
        CommandCategory.SECURITY, "Apply security hardening config", "/security harden [--profile PROFILE]",
        min_role="admin"),
    CommandDefinition("rbac_governance", "/rbac", "!murphy rbac",
        ["rbac", "roles", "list roles", "check roles", "role management"],
        CommandCategory.SECURITY, "RBAC governance management", "/rbac [list|assign|revoke|check USER ROLE]",
        subcommands=["list", "assign", "revoke", "check"], min_role="admin"),
    CommandDefinition("oauth_oidc_provider", "/auth oidc", "!murphy auth oidc",
        ["oauth status", "oidc status", "auth provider"],
        CommandCategory.SECURITY, "OAuth/OIDC provider status", "/auth oidc [status|tokens]",
        min_role="admin"),
    CommandDefinition("murphy_credential_gate", "/credentials", "!murphy credentials",
        ["credential gate", "check credentials", "verify credentials"],
        CommandCategory.SECURITY, "Verify credentials gate", "/credentials [check|list]",
        min_role="operator"),
    CommandDefinition("key_harvester", "/keys harvest", "!murphy keys harvest",
        ["harvest keys", "key harvest", "collect keys"],
        CommandCategory.SECURITY, "Run key harvester", "/keys harvest [--dry-run]",
        min_role="admin"),
    CommandDefinition("secure_key_manager", "/keys", "!murphy keys",
        ["manage keys", "key manager", "key management", "secure keys"],
        CommandCategory.SECURITY, "Secure key manager", "/keys [list|rotate|create|delete NAME]",
        subcommands=["list", "rotate", "create", "delete"], min_role="admin"),
    # ── EXECUTION ──────────────────────────────────────────────────────────
    CommandDefinition("execution_compiler", "/compile", "!murphy compile",
        ["compile task", "compile execution", "run compiler"],
        CommandCategory.EXECUTION, "Compile execution spec", "/compile <spec>",
        requires_args=True, min_role="operator"),
    CommandDefinition("finish_line_controller", "/finish", "!murphy finish",
        ["finish task", "mark complete", "task done", "close task"],
        CommandCategory.EXECUTION, "Mark task complete", "/finish <task_id>",
        requires_args=True),
    CommandDefinition("full_automation_controller", "/full-auto", "!murphy full-auto",
        ["full automation", "full auto mode", "enable full automation"],
        CommandCategory.EXECUTION, "Toggle full automation mode", "/full-auto [start|stop|status]",
        subcommands=["start", "stop", "status"], min_role="operator"),
    CommandDefinition("murphy_action_engine", "/action", "!murphy action",
        ["dispatch action", "run action", "execute action"],
        CommandCategory.EXECUTION, "Dispatch a Murphy action", "/action <action_name> [args]",
        requires_args=True),
    CommandDefinition("deterministic_routing_engine", "/route", "!murphy route",
        ["route task", "deterministic route", "routing decision"],
        CommandCategory.EXECUTION, "Route task via deterministic engine", "/route <task>",
        requires_args=True),
    CommandDefinition("closure_engine", "/closure", "!murphy closure",
        ["closure", "close pipeline", "finalize"],
        CommandCategory.EXECUTION, "Run closure engine", "/closure <pipeline_id>",
        requires_args=True),
    CommandDefinition("resolution_scoring", "/resolution score", "!murphy resolution score",
        ["resolution score", "score resolution", "quality score"],
        CommandCategory.EXECUTION, "Score task resolution quality", "/resolution score <task_id>"),
    # ── AUTOMATION ─────────────────────────────────────────────────────────
    CommandDefinition("automation_scheduler", "/schedule", "!murphy schedule",
        ["schedule task", "schedule automation", "cron", "schedule a job"],
        CommandCategory.AUTOMATION, "Schedule an automation", "/schedule <cron> <action>",
        requires_args=True, min_role="operator"),
    CommandDefinition("automation_scaler", "/scale", "!murphy scale",
        ["scale automation", "scale service", "auto scale"],
        CommandCategory.AUTOMATION, "Scale automation service", "/scale <service> [--replicas N]",
        requires_args=True, min_role="operator"),
    CommandDefinition("automation_mode_controller", "/auto mode", "!murphy auto mode",
        ["automation mode", "auto mode", "set automation mode"],
        CommandCategory.AUTOMATION, "Control automation mode", "/auto mode [status|set MODE]",
        subcommands=["status", "set"]),
    CommandDefinition("automation_marketplace", "/automations market", "!murphy automations market",
        ["automation marketplace", "automation catalog", "browse automations"],
        CommandCategory.AUTOMATION, "Browse automation marketplace", "/automations market [list|install NAME]",
        subcommands=["list", "install"]),
    CommandDefinition("automation_readiness_evaluator", "/automations ready", "!murphy automations ready",
        ["automation readiness", "are automations ready", "readiness evaluation"],
        CommandCategory.AUTOMATION, "Evaluate automation readiness", "/automations ready"),
    # ── CONFIDENCE / HITL ──────────────────────────────────────────────────
    CommandDefinition("hitl_autonomy_controller", "/hitl", "!murphy hitl",
        ["hitl", "human in loop", "approval request", "hitl status", "autonomy policy"],
        CommandCategory.CONFIDENCE, "HITL autonomy controller", "/hitl [status|arm|disarm|approve ID|reject ID]",
        subcommands=["status", "arm", "disarm", "approve", "reject"], min_role="operator"),
    CommandDefinition("hitl_graduation_engine", "/hitl graduate", "!murphy hitl graduate",
        ["hitl graduation", "graduate policy", "autonomy graduation"],
        CommandCategory.CONFIDENCE, "Evaluate HITL graduation", "/hitl graduate [--policy NAME]",
        min_role="operator"),
    # ── LLM ────────────────────────────────────────────────────────────────
    CommandDefinition("llm_controller", "/llm", "!murphy llm",
        ["llm query", "ask llm", "query llm", "llm status", "language model"],
        CommandCategory.LLM, "LLM controller", "/llm [query PROMPT|status|providers]",
        subcommands=["query", "status", "providers", "validate"]),
    CommandDefinition("llm_integration_layer", "/llm route", "!murphy llm route",
        ["llm routing", "route llm", "llm provider routing"],
        CommandCategory.LLM, "LLM integration layer routing", "/llm route [status|test PROMPT]"),
    CommandDefinition("groq_key_rotator", "/groq rotate", "!murphy groq rotate",
        ["groq rotate", "rotate groq key", "key rotation"],
        CommandCategory.LLM, "Rotate Groq API key", "/groq rotate [--force]",
        min_role="admin"),
    CommandDefinition("openai_compatible_provider", "/llm openai", "!murphy llm openai",
        ["openai provider", "llm openai status", "openai compatible"],
        CommandCategory.LLM, "OpenAI-compatible provider status", "/llm openai [status|test]"),
    CommandDefinition("prompt_amplifier", "/prompt amplify", "!murphy prompt amplify",
        ["amplify prompt", "prompt amplifier", "enhance prompt"],
        CommandCategory.LLM, "Amplify a prompt", "/prompt amplify <text>", requires_args=True),
    CommandDefinition("local_inference_engine", "/inference local", "!murphy inference local",
        ["local inference", "run local inference", "local model inference"],
        CommandCategory.LLM, "Run local inference", "/inference local <prompt>", requires_args=True),
    # ── INTELLIGENCE ───────────────────────────────────────────────────────
    CommandDefinition("reasoning_engine", "/reason", "!murphy reason",
        ["reason about", "logical reasoning", "infer", "reason through"],
        CommandCategory.INTELLIGENCE, "Reasoning engine", "/reason <question>", requires_args=True),
    CommandDefinition("knowledge_graph_builder", "/kg build", "!murphy kg build",
        ["build knowledge graph", "update kg", "knowledge graph"],
        CommandCategory.INTELLIGENCE, "Build knowledge graph", "/kg [build|query|status]",
        subcommands=["build", "query", "status"], min_role="operator"),
    CommandDefinition("knowledge_base_manager", "/kb", "!murphy kb",
        ["knowledge base", "query kb", "search knowledge base"],
        CommandCategory.INTELLIGENCE, "Knowledge base management", "/kb [query TEXT|add|list]",
        subcommands=["query", "add", "list"]),
    CommandDefinition("rag_vector_integration", "/rag", "!murphy rag",
        ["rag search", "vector search", "semantic search", "rag query"],
        CommandCategory.INTELLIGENCE, "RAG vector search", "/rag search <query>", requires_args=True),
    CommandDefinition("large_action_model", "/lam", "!murphy lam",
        ["large action model", "lam execute", "run lam"],
        CommandCategory.INTELLIGENCE, "Large action model execution", "/lam execute <task>",
        requires_args=True, min_role="operator"),
    CommandDefinition("concept_graph_engine", "/concept map", "!murphy concept map",
        ["concept map", "concept graph", "map concepts"],
        CommandCategory.INTELLIGENCE, "Concept graph operations", "/concept [map|query|visualize]",
        subcommands=["map", "query", "visualize"]),
    # ── SWARM ──────────────────────────────────────────────────────────────
    CommandDefinition("durable_swarm_orchestrator", "/swarm", "!murphy swarm",
        ["start swarm", "swarm orchestrate", "run swarm", "swarm status"],
        CommandCategory.SWARM, "Durable swarm orchestrator", "/swarm [start|stop|status|list]",
        subcommands=["start", "stop", "status", "list"], min_role="operator"),
    CommandDefinition("murphy_crew_system", "/crew", "!murphy crew",
        ["crew system", "agent crew", "assign crew", "crew status"],
        CommandCategory.SWARM, "Murphy crew assignment", "/crew [list|assign|status]",
        subcommands=["list", "assign", "status"]),
    CommandDefinition("advanced_swarm_system", "/swarm advanced", "!murphy swarm advanced",
        ["advanced swarm", "swarm coordination", "multi-agent coordination"],
        CommandCategory.SWARM, "Advanced swarm coordination", "/swarm advanced [status|configure]",
        min_role="operator"),
    # ── LEARNING ───────────────────────────────────────────────────────────
    CommandDefinition("learning_system", "/learn", "!murphy learn",
        ["learning cycle", "run learning", "system learning", "start learning"],
        CommandCategory.LEARNING, "Trigger learning cycle", "/learn [cycle|status|toggle]",
        subcommands=["cycle", "status", "toggle"], min_role="operator"),
    CommandDefinition("murphy_shadow_trainer", "/shadow train", "!murphy shadow train",
        ["shadow training", "train shadow", "run shadow trainer"],
        CommandCategory.LEARNING, "Run shadow trainer", "/shadow train [--dry-run]",
        min_role="operator"),
    CommandDefinition("feedback_integrator", "/feedback", "!murphy feedback",
        ["integrate feedback", "feedback loop", "submit feedback"],
        CommandCategory.LEARNING, "Integrate feedback", "/feedback [submit TEXT|list|report]",
        subcommands=["submit", "list", "report"]),
    # ── FINANCE ────────────────────────────────────────────────────────────
    CommandDefinition("financial_reporting_engine", "/finance report", "!murphy finance report",
        ["finance report", "financial report", "generate finance report"],
        CommandCategory.FINANCE, "Generate financial report", "/finance report [--period PERIOD]"),
    CommandDefinition("invoice_processing_pipeline", "/invoice", "!murphy invoice",
        ["invoice", "process invoice", "create invoice", "invoicing"],
        CommandCategory.FINANCE, "Invoice processing pipeline", "/invoice [create|list|process ID]",
        subcommands=["create", "list", "process"]),
    CommandDefinition("kpi_tracker", "/kpi", "!murphy kpi",
        ["kpi tracker", "track kpi", "kpi status", "key performance"],
        CommandCategory.FINANCE, "KPI tracking", "/kpi [track|list|report]",
        subcommands=["track", "list", "report"]),
    CommandDefinition("budget_aware_processor", "/budget", "!murphy budget",
        ["budget check", "budget status", "spending budget"],
        CommandCategory.FINANCE, "Budget-aware processing", "/budget [check|status|set LIMIT]",
        subcommands=["check", "status", "set"]),
    CommandDefinition("cost_optimization_advisor", "/cost optimize", "!murphy cost optimize",
        ["optimize costs", "cost optimization", "reduce costs", "cost advisor"],
        CommandCategory.FINANCE, "Cost optimization advice", "/cost [optimize|report|analyze]",
        subcommands=["optimize", "report", "analyze"]),
    # ── CRYPTO ─────────────────────────────────────────────────────────────
    CommandDefinition("crypto_portfolio_tracker", "/crypto portfolio", "!murphy crypto portfolio",
        ["crypto portfolio", "portfolio tracker", "crypto holdings"],
        CommandCategory.CRYPTO, "Crypto portfolio tracker", "/crypto portfolio [view|rebalance]",
        subcommands=["view", "rebalance"]),
    CommandDefinition("crypto_exchange_connector", "/crypto exchange", "!murphy crypto exchange",
        ["crypto exchange", "exchange connector", "trading exchange"],
        CommandCategory.CRYPTO, "Crypto exchange connector", "/crypto exchange [connect|status|trade]",
        subcommands=["connect", "status", "trade"], min_role="operator"),
    CommandDefinition("coinbase_connector", "/coinbase", "!murphy coinbase",
        ["coinbase", "coinbase connector", "coinbase status"],
        CommandCategory.CRYPTO, "Coinbase connector", "/coinbase [status|connect|balance]",
        min_role="operator"),
    # ── BUSINESS ───────────────────────────────────────────────────────────
    CommandDefinition("niche_business_generator", "/niche generate", "!murphy niche generate",
        ["generate niche", "niche business", "new business idea", "generate business"],
        CommandCategory.BUSINESS, "Generate niche business ideas", "/niche generate [--market MARKET]"),
    CommandDefinition("business_scaling_engine", "/scale biz", "!murphy scale biz",
        ["scale business", "business scaling", "grow business"],
        CommandCategory.BUSINESS, "Business scaling engine", "/scale biz [analyze|plan|execute]",
        subcommands=["analyze", "plan", "execute"], min_role="operator"),
    CommandDefinition("executive_planning_engine", "/exec plan", "!murphy exec plan",
        ["executive planning", "strategic plan", "business plan", "exec plan"],
        CommandCategory.BUSINESS, "Executive planning engine", "/exec plan [create|list|review]",
        subcommands=["create", "list", "review"]),
    CommandDefinition("competitive_intelligence_engine", "/intel competitive", "!murphy intel competitive",
        ["competitive intelligence", "competitor analysis", "market intel"],
        CommandCategory.BUSINESS, "Competitive intelligence", "/intel competitive [scan|report|monitor]",
        subcommands=["scan", "report", "monitor"]),
    CommandDefinition("kfactor_calculator", "/kfactor", "!murphy kfactor",
        ["k factor", "kfactor", "viral coefficient", "growth factor"],
        CommandCategory.BUSINESS, "K-factor growth calculator", "/kfactor [calculate|report]"),
    # ── MARKETING ──────────────────────────────────────────────────────────
    CommandDefinition("marketing_analytics_aggregator", "/marketing analytics", "!murphy marketing analytics",
        ["marketing analytics", "analyze marketing", "marketing data"],
        CommandCategory.MARKETING, "Marketing analytics aggregation", "/marketing analytics [report|live]"),
    CommandDefinition("adaptive_campaign_engine", "/campaign adaptive", "!murphy campaign adaptive",
        ["adaptive campaign", "campaign optimization", "optimize campaign"],
        CommandCategory.MARKETING, "Adaptive campaign engine", "/campaign adaptive [status|optimize ID]",
        subcommands=["status", "optimize"]),
    CommandDefinition("campaign_orchestrator", "/campaign", "!murphy campaign",
        ["run campaign", "campaign run", "campaign orchestrate", "launch campaign"],
        CommandCategory.MARKETING, "Campaign orchestrator", "/campaign [run|stop|list|status ID]",
        subcommands=["run", "stop", "list", "status"]),
    CommandDefinition("seo_optimisation_engine", "/seo", "!murphy seo",
        ["seo optimize", "seo analysis", "search engine optimization"],
        CommandCategory.MARKETING, "SEO optimisation engine", "/seo [optimize URL|audit|report]",
        subcommands=["optimize", "audit", "report"]),
    # ── CONTENT ────────────────────────────────────────────────────────────
    CommandDefinition("content_pipeline_engine", "/content pipeline", "!murphy content pipeline",
        ["content pipeline", "run content pipeline", "content workflow"],
        CommandCategory.CONTENT, "Content pipeline engine", "/content pipeline [run|status|list]",
        subcommands=["run", "status", "list"]),
    CommandDefinition("image_generation_engine", "/image gen", "!murphy image gen",
        ["generate image", "image generation", "create image", "make image"],
        CommandCategory.CONTENT, "Image generation engine", "/image gen <prompt>", requires_args=True),
    CommandDefinition("video_packager", "/video pack", "!murphy video pack",
        ["video packager", "package video", "video packaging"],
        CommandCategory.CONTENT, "Video packager", "/video pack [create|list|status ID]",
        subcommands=["create", "list", "status"]),
    CommandDefinition("youtube_uploader", "/youtube upload", "!murphy youtube upload",
        ["upload youtube", "youtube upload", "upload video"],
        CommandCategory.CONTENT, "YouTube uploader", "/youtube upload <file>", requires_args=True,
        min_role="operator"),
    CommandDefinition("murphy_drawing_engine", "/draw", "!murphy draw",
        ["draw diagram", "murphy draw", "create drawing", "generate diagram"],
        CommandCategory.CONTENT, "Murphy drawing engine", "/draw <description>", requires_args=True),
    # ── CRM / ORG ──────────────────────────────────────────────────────────
    CommandDefinition("customer_communication_manager", "/customer comm", "!murphy customer comm",
        ["customer communication", "communicate customer", "customer msg"],
        CommandCategory.CRM, "Customer communication manager", "/customer comm [send|list|template]",
        subcommands=["send", "list", "template"]),
    CommandDefinition("organization_chart_system", "/org chart", "!murphy org chart",
        ["org chart", "organization chart", "show org chart", "team structure"],
        CommandCategory.ORG, "Organization chart system", "/org chart [view|update|export]",
        subcommands=["view", "update", "export"]),
    CommandDefinition("multi_tenant_workspace", "/workspace", "!murphy workspace",
        ["workspace", "tenant workspace", "multi tenant", "workspaces"],
        CommandCategory.ORG, "Multi-tenant workspace management", "/workspace [list|create|switch NAME]",
        subcommands=["list", "create", "switch"]),
    # ── ONBOARDING ─────────────────────────────────────────────────────────
    CommandDefinition("onboarding_flow", "/onboard", "!murphy onboard",
        ["onboard user", "start onboarding", "user onboarding", "onboarding flow"],
        CommandCategory.ONBOARDING, "Onboarding flow", "/onboard [start|status|complete USER]",
        subcommands=["start", "status", "complete"]),
    CommandDefinition("agentic_onboarding_engine", "/onboard agent", "!murphy onboard agent",
        ["agentic onboarding", "agent onboarding", "auto onboard"],
        CommandCategory.ONBOARDING, "Agentic onboarding engine", "/onboard agent [run|status]",
        min_role="operator"),
    CommandDefinition("setup_wizard", "/setup", "!murphy setup",
        ["setup wizard", "run setup", "initial setup", "configure murphy"],
        CommandCategory.ONBOARDING, "Setup wizard", "/setup [run|status|reset]",
        subcommands=["run", "status", "reset"], min_role="admin"),
    # ── INFRA ──────────────────────────────────────────────────────────────
    CommandDefinition("kubernetes_deployment", "/k8s", "!murphy k8s",
        ["kubernetes", "k8s deploy", "deploy kubernetes", "k8s status"],
        CommandCategory.INFRA, "Kubernetes deployment manager", "/k8s [deploy|status|scale|delete] <name>",
        subcommands=["deploy", "status", "scale", "delete", "rollback"], min_role="operator"),
    CommandDefinition("docker_containerization", "/docker", "!murphy docker",
        ["docker build", "docker deploy", "containerize", "docker status"],
        CommandCategory.INFRA, "Docker containerization", "/docker [build|run|stop|ps]",
        subcommands=["build", "run", "stop", "ps"], min_role="operator"),
    CommandDefinition("cloudflare_deploy", "/cloudflare deploy", "!murphy cloudflare deploy",
        ["cloudflare deploy", "deploy cloudflare", "cloudflare"],
        CommandCategory.INFRA, "Cloudflare deployment", "/cloudflare deploy [run|status|rollback]",
        min_role="operator"),
    CommandDefinition("hetzner_deploy", "/hetzner deploy", "!murphy hetzner deploy",
        ["hetzner deploy", "deploy hetzner", "hetzner"],
        CommandCategory.INFRA, "Hetzner deployment", "/hetzner deploy [run|status]",
        min_role="operator"),
    CommandDefinition("backup_disaster_recovery", "/backup", "!murphy backup",
        ["backup", "create backup", "disaster recovery", "backup now"],
        CommandCategory.INFRA, "Backup and disaster recovery", "/backup [create|list|restore ID]",
        subcommands=["create", "list", "restore"], min_role="operator"),
    CommandDefinition("emergency_stop_controller", "/emergency stop", "!murphy emergency stop",
        ["emergency stop", "kill all", "stop everything", "emergency halt"],
        CommandCategory.INFRA, "Emergency stop controller", "/emergency stop [--confirm]",
        requires_args=True, min_role="admin"),
    CommandDefinition("capacity_planning_engine", "/capacity plan", "!murphy capacity plan",
        ["capacity planning", "plan capacity", "resource capacity"],
        CommandCategory.INFRA, "Capacity planning", "/capacity plan [analyze|forecast|report]",
        subcommands=["analyze", "forecast", "report"]),
    # ── HEALTH ─────────────────────────────────────────────────────────────
    CommandDefinition("health_monitor", "/health", "!murphy health",
        ["health check", "system health", "how is murphy", "status check", "check health", "is murphy ok"],
        CommandCategory.HEALTH, "System health monitor", "/health [--verbose] [--module NAME]",
        examples=["!murphy health", "!murphy health --verbose", "!murphy health --module llm_controller"]),
    CommandDefinition("chaos_resilience_loop", "/chaos test", "!murphy chaos test",
        ["chaos test", "resilience test", "chaos engineering", "run chaos"],
        CommandCategory.HEALTH, "Chaos resilience loop", "/chaos test [run|status|report]",
        min_role="operator"),
    CommandDefinition("autonomous_repair_system", "/repair auto", "!murphy repair auto",
        ["auto repair", "autonomous repair", "self repair"],
        CommandCategory.HEALTH, "Autonomous repair system", "/repair auto [run|status|history]",
        min_role="operator"),
    CommandDefinition("self_healing_coordinator", "/heal", "!murphy heal",
        ["heal system", "self heal", "trigger healing", "repair murphy"],
        CommandCategory.HEALTH, "Self-healing coordinator", "/heal [run|status|history]",
        min_role="operator"),
    CommandDefinition("predictive_failure_engine", "/predict failures", "!murphy predict failures",
        ["predict failures", "failure prediction", "failure forecast"],
        CommandCategory.HEALTH, "Predictive failure engine", "/predict failures [run|report]"),
    CommandDefinition("murphy_code_healer", "/code heal", "!murphy code heal",
        ["code healer", "heal code", "fix code automatically"],
        CommandCategory.HEALTH, "Murphy code healer", "/code heal [run|status]", min_role="operator"),
    # ── IoT ────────────────────────────────────────────────────────────────
    CommandDefinition("digital_twin_engine", "/twin", "!murphy twin",
        ["digital twin", "create twin", "twin status", "device twin"],
        CommandCategory.IOT, "Digital twin engine", "/twin [create NAME|status|list|update ID]",
        subcommands=["create", "status", "list", "update"]),
    CommandDefinition("building_automation_connectors", "/building auto", "!murphy building auto",
        ["building automation", "building control", "smart building"],
        CommandCategory.IOT, "Building automation connectors", "/building auto [status|connect|list]"),
    CommandDefinition("murphy_sensor_fusion", "/sensor fuse", "!murphy sensor fuse",
        ["sensor fusion", "fuse sensors", "sensor data", "sensor status"],
        CommandCategory.IOT, "Murphy sensor fusion", "/sensor fuse [status|read|calibrate]",
        subcommands=["status", "read", "calibrate"]),
    CommandDefinition("computer_vision_pipeline", "/vision", "!murphy vision",
        ["computer vision", "vision pipeline", "image analysis", "visual analysis"],
        CommandCategory.IOT, "Computer vision pipeline", "/vision [run IMAGE|status]",
        requires_args=True),
    # ── TELEMETRY ──────────────────────────────────────────────────────────
    CommandDefinition("prometheus_metrics_exporter", "/metrics", "!murphy metrics",
        ["metrics", "prometheus metrics", "system metrics", "show metrics"],
        CommandCategory.TELEMETRY, "Prometheus metrics exporter", "/metrics [show|export|status]",
        subcommands=["show", "export", "status"]),
    CommandDefinition("logging_system", "/logs", "!murphy logs",
        ["logs", "show logs", "view logs", "system logs", "log output"],
        CommandCategory.TELEMETRY, "Logging system", "/logs [tail N|search TEXT|export]",
        subcommands=["tail", "search", "export"]),
    CommandDefinition("log_analysis_engine", "/logs analyze", "!murphy logs analyze",
        ["analyze logs", "log analysis", "log insights"],
        CommandCategory.TELEMETRY, "Log analysis engine", "/logs analyze [--hours N|--pattern TEXT]"),
    CommandDefinition("murphy_trace", "/trace", "!murphy trace",
        ["trace", "request trace", "murphy trace", "distributed trace"],
        CommandCategory.TELEMETRY, "Murphy trace", "/trace [show ID|list|export]",
        subcommands=["show", "list", "export"]),
    CommandDefinition("observability_counters", "/observe", "!murphy observe",
        ["observe", "observability", "system counters", "monitor counters"],
        CommandCategory.TELEMETRY, "Observability counters", "/observe [list|reset|export]"),
    # ── DASHBOARDS ─────────────────────────────────────────────────────────
    CommandDefinition("analytics_dashboard", "/analytics", "!murphy analytics",
        ["analytics", "show analytics", "analytics dashboard", "data analytics"],
        CommandCategory.DASHBOARDS, "Analytics dashboard", "/analytics [overview|module NAME|export]",
        subcommands=["overview", "module", "export"]),
    CommandDefinition("operational_slo_tracker", "/slo", "!murphy slo",
        ["slo tracker", "track slo", "service level objective", "slo status"],
        CommandCategory.DASHBOARDS, "SLO tracker", "/slo [track|report|alert]",
        subcommands=["track", "report", "alert"]),
    CommandDefinition("functionality_heatmap", "/heatmap", "!murphy heatmap",
        ["heatmap", "functionality heatmap", "usage heatmap"],
        CommandCategory.DASHBOARDS, "Functionality heatmap", "/heatmap [show|export]"),
    # ── ALERTS ─────────────────────────────────────────────────────────────
    CommandDefinition("alert_rules_engine", "/alerts", "!murphy alerts",
        ["alerts", "alert rules", "manage alerts", "list alerts"],
        CommandCategory.ALERTS, "Alert rules engine", "/alerts [list|create|delete ID|test ID]",
        subcommands=["list", "create", "delete", "test"]),
    # ── AUDIT ──────────────────────────────────────────────────────────────
    CommandDefinition("audit_logging_system", "/audit", "!murphy audit",
        ["audit log", "audit trail", "system audit", "view audit"],
        CommandCategory.AUDIT, "Audit logging system", "/audit [list|search TEXT|export]",
        subcommands=["list", "search", "export"]),
    CommandDefinition("blockchain_audit_trail", "/audit blockchain", "!murphy audit blockchain",
        ["blockchain audit", "immutable audit", "chain audit"],
        CommandCategory.AUDIT, "Blockchain audit trail", "/audit blockchain [status|verify|export]"),
    # ── COMPLIANCE ─────────────────────────────────────────────────────────
    CommandDefinition("compliance_engine", "/compliance", "!murphy compliance",
        ["compliance check", "run compliance", "compliance status", "regulatory compliance"],
        CommandCategory.COMPLIANCE, "Compliance engine", "/compliance [check|report|region CODE]",
        subcommands=["check", "report", "region"]),
    CommandDefinition("compliance_as_code_engine", "/compliance code", "!murphy compliance code",
        ["compliance as code", "codified compliance", "run compliance code"],
        CommandCategory.COMPLIANCE, "Compliance as code", "/compliance code [run|validate|list]"),
    CommandDefinition("compliance_region_validator", "/compliance region", "!murphy compliance region",
        ["compliance region", "validate region", "regional compliance"],
        CommandCategory.COMPLIANCE, "Compliance region validator", "/compliance region <code>",
        requires_args=True),
    CommandDefinition("regulation_ml_engine", "/regulation ml status", "!murphy regulation ml status",
        ["regulation ml status", "regulation ml", "regulation machine learning status"],
        CommandCategory.COMPLIANCE, "Regulation ML engine status", "/regulation ml status",
        subcommands=["status"]),
    CommandDefinition("regulation_ml_engine_train", "/regulation ml train", "!murphy regulation ml train",
        ["regulation ml train", "train regulation model", "regulation ml training"],
        CommandCategory.COMPLIANCE, "Train regulation ML engine", "/regulation ml train",
        subcommands=["train"], min_role="operator"),
    CommandDefinition("regulation_ml_engine_predict", "/regulation ml predict", "!murphy regulation ml predict",
        ["regulation ml predict", "predict regulations", "regulation prediction", "recommend toggles"],
        CommandCategory.COMPLIANCE,
        "Predict optimal regulation toggles for country+industry",
        "/regulation ml predict <country> <industry>",
        requires_args=True, subcommands=["predict"]),
    # ── INTEGRATIONS ───────────────────────────────────────────────────────
    CommandDefinition("integration_bus", "/bus", "!murphy bus",
        ["integration bus", "bus status", "event bus", "message bus"],
        CommandCategory.INTEGRATIONS, "Integration bus status", "/bus [status|subscribe|publish]",
        subcommands=["status", "subscribe", "publish"]),
    CommandDefinition("enterprise_integrations", "/integrations", "!murphy integrations",
        ["enterprise integrations", "list integrations", "third party integrations"],
        CommandCategory.INTEGRATIONS, "Enterprise integrations", "/integrations [list|connect NAME|status NAME]",
        subcommands=["list", "connect", "status"]),
    CommandDefinition("api_gateway_adapter", "/api gateway", "!murphy api gateway",
        ["api gateway", "gateway status", "api proxy"],
        CommandCategory.INTEGRATIONS, "API gateway adapter", "/api gateway [status|routes|test]"),
    CommandDefinition("graphql_api_layer", "/graphql", "!murphy graphql",
        ["graphql", "graphql api", "gql query"],
        CommandCategory.INTEGRATIONS, "GraphQL API layer", "/graphql [query TEXT|schema|status]",
        subcommands=["query", "schema", "status"]),
    # ── COMMS ──────────────────────────────────────────────────────────────
    CommandDefinition("email_integration", "/email", "!murphy email",
        ["send email", "email integration", "email status", "email system"],
        CommandCategory.COMMS, "Email integration", "/email [send|list|template NAME]",
        subcommands=["send", "list", "template"]),
    CommandDefinition("notification_system", "/notify", "!murphy notify",
        ["send notification", "notification", "push notification", "notify"],
        CommandCategory.COMMS, "Notification system", "/notify [send MSG|list|channels]",
        subcommands=["send", "list", "channels"]),
    CommandDefinition("webhook_dispatcher", "/webhook", "!murphy webhook",
        ["webhook", "dispatch webhook", "send webhook", "webhook status"],
        CommandCategory.COMMS, "Webhook dispatcher", "/webhook [send URL|list|test ID]",
        subcommands=["send", "list", "test"]),
    # ── DEV ────────────────────────────────────────────────────────────────
    CommandDefinition("code_generation_gateway", "/codegen", "!murphy codegen",
        ["generate code", "code generation", "codegen", "write code"],
        CommandCategory.DEV, "Code generation gateway", "/codegen <description>", requires_args=True),
    CommandDefinition("ab_testing_framework", "/ab test", "!murphy ab test",
        ["ab test", "a/b test", "split test", "run ab test"],
        CommandCategory.DEV, "A/B testing framework", "/ab test [create|run ID|results ID|list]",
        subcommands=["create", "run", "results", "list"]),
    CommandDefinition("auto_documentation_engine", "/docs generate", "!murphy docs generate",
        ["generate docs", "auto docs", "auto documentation", "document code"],
        CommandCategory.DEV, "Auto-documentation engine", "/docs generate [--module NAME|--all]"),
    CommandDefinition("architecture_evolution", "/arch evolve", "!murphy arch evolve",
        ["architecture evolution", "evolve architecture", "arch analysis"],
        CommandCategory.DEV, "Architecture evolution analysis", "/arch evolve [analyze|plan|report]"),
    # ── DATA ───────────────────────────────────────────────────────────────
    CommandDefinition("data_pipeline_orchestrator", "/data pipeline", "!murphy data pipeline",
        ["data pipeline", "run data pipeline", "pipeline orchestrate"],
        CommandCategory.DATA, "Data pipeline orchestrator", "/data pipeline [run|status|list|stop ID]",
        subcommands=["run", "status", "list", "stop"], min_role="operator"),
    CommandDefinition("data_archive_manager", "/data archive", "!murphy data archive",
        ["data archive", "archive data", "data archiving"],
        CommandCategory.DATA, "Data archive manager", "/data archive [create|list|restore ID]",
        subcommands=["create", "list", "restore"]),
    # ── ML ─────────────────────────────────────────────────────────────────
    CommandDefinition("ml_model_registry", "/ml models", "!murphy ml models",
        ["ml models", "model registry", "list ml models", "machine learning models"],
        CommandCategory.ML, "ML model registry", "/ml models [list|register NAME|status NAME|delete NAME]",
        subcommands=["list", "register", "status", "delete"]),
    CommandDefinition("ml_strategy_engine", "/ml strategy", "!murphy ml strategy",
        ["ml strategy", "machine learning strategy", "model strategy"],
        CommandCategory.ML, "ML strategy engine", "/ml strategy [analyze|plan|report]"),
    # ── MFGC ───────────────────────────────────────────────────────────────
    CommandDefinition("mfgc_core", "/mfgc", "!murphy mfgc",
        ["mfgc", "mfgc status", "mfgc core", "murphy foundation governance"],
        CommandCategory.MFGC, "MFGC core system", "/mfgc [status|report|validate]",
        subcommands=["status", "report", "validate"]),
    CommandDefinition("mfgc_metrics", "/mfgc metrics", "!murphy mfgc metrics",
        ["mfgc metrics", "foundation metrics"],
        CommandCategory.MFGC, "MFGC metrics", "/mfgc metrics [show|export]"),
    # ── FOUNDATION ─────────────────────────────────────────────────────────
    CommandDefinition("murphy_foundation_model", "/foundation", "!murphy foundation",
        ["foundation model", "mfm status", "murphy foundation model", "foundation model status"],
        CommandCategory.FOUNDATION, "Murphy Foundation Model", "/foundation [status|train|infer PROMPT|report]",
        subcommands=["status", "train", "infer", "report"]),
    # ── RESEARCH ───────────────────────────────────────────────────────────
    CommandDefinition("research_engine", "/research", "!murphy research",
        ["research", "do research", "research topic", "look up"],
        CommandCategory.RESEARCH, "Research engine", "/research <topic>", requires_args=True),
    CommandDefinition("advanced_research", "/research advanced", "!murphy research advanced",
        ["advanced research", "deep research", "thorough research"],
        CommandCategory.RESEARCH, "Advanced research engine", "/research advanced <topic>", requires_args=True),
    CommandDefinition("multi_source_research", "/research multi", "!murphy research multi",
        ["multi source research", "cross source research", "aggregate research"],
        CommandCategory.RESEARCH, "Multi-source research", "/research multi <topic>", requires_args=True),
    # ── TERMINAL ───────────────────────────────────────────────────────────
    CommandDefinition("murphy_repl", "/repl", "!murphy repl",
        ["murphy repl", "interactive terminal", "start repl", "python repl"],
        CommandCategory.TERMINAL, "Murphy REPL", "/repl [start|exit]"),
    CommandDefinition("natural_language_query", "/nlq", "!murphy nlq",
        ["natural language query", "nlq", "query natural language"],
        CommandCategory.TERMINAL, "Natural language query", "/nlq <question>", requires_args=True),
    CommandDefinition("voice_command_interface", "/voice", "!murphy voice",
        ["voice command", "voice interface", "speak command"],
        CommandCategory.TERMINAL, "Voice command interface", "/voice [enable|disable|status]"),
    CommandDefinition("dynamic_command_discovery", "/commands discover", "!murphy commands discover",
        ["discover commands", "auto discover commands", "command discovery"],
        CommandCategory.TERMINAL, "Dynamic command discovery", "/commands discover [--module NAME]"),
    # ── MANAGEMENT SYSTEMS ──────────────────────────────────────────────────
    CommandDefinition("board_engine", "/board", "!murphy board",
        ["board", "project board", "create board", "list boards", "task board"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Board management", "/board [list|create NAME|view ID|kanban ID]",
        subcommands=["list", "create", "view", "kanban", "add-item", "delete"]),
    CommandDefinition("status_engine", "/status-label", "!murphy status-label",
        ["status label", "workflow status", "set status color", "status workflow"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Status label management", "/status-label [list|create NAME|set ITEM STATUS]",
        subcommands=["list", "create", "set", "progress"]),
    CommandDefinition("timeline_engine", "/timeline", "!murphy timeline",
        ["timeline", "gantt chart", "project timeline", "task timeline", "milestone"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Timeline/Gantt engine", "/timeline [view BOARD|add ITEM|milestones|critical-path]",
        subcommands=["view", "add", "milestones", "critical-path", "auto-schedule"]),
    CommandDefinition("automation_recipes", "/recipe", "!murphy recipe",
        ["recipe", "automation recipe", "when x do y", "workflow recipe", "automation trigger"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Automation recipes", "/recipe [list|create|run ID|delete ID]",
        subcommands=["list", "create", "run", "delete", "templates"]),
    CommandDefinition("workspace_manager", "/workspace", "!murphy workspace",
        ["murphy workspace", "project workspace", "workspace list"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Workspace manager", "/workspace [list|show DOMAIN|bootstrap]",
        subcommands=["list", "show", "bootstrap"]),
    CommandDefinition("dashboard_generator", "/dashboard", "!murphy dashboard",
        ["dashboard", "project dashboard", "show dashboard", "generate dashboard", "standup"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Dashboard generator", "/dashboard [standup|weekly|project BOARD|widget]",
        subcommands=["standup", "weekly", "project", "widget"]),
    CommandDefinition("integration_bridge", "/sync", "!murphy sync",
        ["sync modules", "sync board", "integration sync", "bridge sync"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Integration bridge sync", "/sync [status|rules|run|history]",
        subcommands=["status", "rules", "run", "history"]),
    CommandDefinition("form_builder", "/form", "!murphy form",
        ["form", "create form", "intake form", "submit form", "bug report form"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Form builder", "/form [list|start TEMPLATE|submit ID|responses ID]",
        subcommands=["list", "start", "submit", "responses"]),
    CommandDefinition("doc_manager", "/doc", "!murphy doc",
        ["doc", "workdoc", "create doc", "meeting notes", "document", "list docs"],
        CommandCategory.MANAGEMENT_SYSTEMS, "Document manager", "/doc [list|create TYPE TITLE|view ID|search TEXT]",
        subcommands=["list", "create", "view", "search", "link", "versions"]),
]


# ---------------------------------------------------------------------------
# CommandRegistry
# ---------------------------------------------------------------------------


class CommandRegistry:
    """
    Central registry for all Murphy System commands.

    Provides O(1) lookup by slash command, chat command, and fuzzy
    natural-language alias matching.
    """

    def __init__(self) -> None:
        self._by_slash: dict[str, CommandDefinition] = {}
        self._by_chat: dict[str, CommandDefinition] = {}
        self._by_module: dict[str, CommandDefinition] = {}
        self._by_category: dict[CommandCategory, list[CommandDefinition]] = {
            cat: [] for cat in CommandCategory
        }
        self._nl_index: list[tuple[str, CommandDefinition]] = []

    def register(self, cmd: CommandDefinition) -> None:
        """Register a command definition."""
        self._by_slash[cmd.slash_command.lower()] = cmd
        self._by_chat[cmd.chat_command.lower()] = cmd
        self._by_module[cmd.module_name] = cmd
        self._by_category[cmd.category].append(cmd)
        for alias in cmd.nl_aliases:
            capped_append(self._nl_index, (alias.lower(), cmd))
        logger.debug("Registered command: %s → %s", cmd.module_name, cmd.slash_command)

    def lookup_by_slash(self, slash: str) -> CommandDefinition | None:
        return self._by_slash.get(slash.lower())

    def lookup_by_chat(self, chat: str) -> CommandDefinition | None:
        return self._by_chat.get(chat.lower())

    def lookup_by_module(self, module_name: str) -> CommandDefinition | None:
        return self._by_module.get(module_name)

    def lookup_by_nl(self, text: str) -> CommandDefinition | None:
        """Return best-matching command for natural language input."""
        norm = text.lower().strip()
        best: CommandDefinition | None = None
        best_score = 0
        for alias, cmd in self._nl_index:
            if alias in norm:
                score = len(alias)
                if score > best_score:
                    best_score = score
                    best = cmd
        # fallback: word overlap
        if best is None:
            words = set(norm.split())
            for alias, cmd in self._nl_index:
                overlap = len(words & set(alias.split()))
                if overlap > best_score:
                    best_score = overlap
                    best = cmd
        return best

    def get_by_category(self, cat: CommandCategory) -> list[CommandDefinition]:
        return list(self._by_category.get(cat, []))

    def get_by_module(self, module_name: str) -> CommandDefinition | None:
        return self._by_module.get(module_name)

    def all_commands(self) -> list[CommandDefinition]:
        return list(self._by_module.values())

    def suggest(self, text: str, n: int = 3) -> list[str]:
        """Return up to *n* slash-command suggestions closest to *text*."""
        norm = text.lower()
        scored: list[tuple[int, str]] = []
        for slash, cmd in self._by_slash.items():
            score = sum(1 for w in norm.split() if w in slash or w in cmd.description.lower())
            if score:
                scored.append((score, cmd.slash_command))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:n]]

    def to_help_text(self, category: CommandCategory | None = None) -> str:
        """Return Markdown-formatted help text."""
        lines = ["# Murphy System Commands\n"]
        cats = [category] if category else list(CommandCategory)
        for cat in cats:
            cmds = self.get_by_category(cat)
            if not cmds:
                continue
            lines.append(f"\n## {cat.value.replace('_', ' ').title()}\n")
            lines.append("| Command | Description | Role |")
            lines.append("|---------|-------------|------|")
            for cmd in cmds:
                lines.append(f"| `{cmd.slash_command}` | {cmd.description} | {cmd.min_role} |")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"commands": [c.to_dict() for c in self.all_commands()]}

    def bootstrap(self) -> "CommandRegistry":
        """Register all built-in Murphy commands and return self."""
        for cmd in MURPHY_COMMANDS:
            self.register(cmd)
        logger.info("CommandRegistry bootstrapped: %d commands", len(self._by_module))
        return self


def build_registry() -> CommandRegistry:
    """Create and return a fully bootstrapped :class:`CommandRegistry`."""
    return CommandRegistry().bootstrap()
