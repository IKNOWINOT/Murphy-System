# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Bot Personas — named bot personalities for the Murphy Matrix integration.

Each :class:`Persona` defines:
- Rooms it monitors and responds to
- Commands it handles
- Subsystems it controls
- An optional custom message handler

Adapted from the original Discord bot blueprints (CADBot, SecurityBot,
EngineeringBot, KeyManagerBot) and extended for the full Murphy subsystem map.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MessagePair = Tuple[str, str]


# ---------------------------------------------------------------------------
# Persona dataclass
# ---------------------------------------------------------------------------

@dataclass
class Persona:
    """A named bot personality that handles a specific domain of Murphy.

    Parameters
    ----------
    name:
        Human-readable persona name, e.g. ``"SecurityBot"``.
    description:
        Short description shown in ``!murphy help``.
    monitored_rooms:
        List of subsystem room keys this persona monitors.
    commands:
        Dict of ``command_name → description`` pairs this persona handles.
    subsystems:
        List of Murphy subsystem identifiers this persona controls.
    handler:
        Optional async callable ``(user_id, command, args) → MessagePair``.
    """

    name: str
    description: str = ""
    monitored_rooms: List[str] = field(default_factory=list)
    commands: Dict[str, str] = field(default_factory=dict)
    subsystems: List[str] = field(default_factory=list)
    handler: Optional[Callable[..., Awaitable[MessagePair]]] = field(
        default=None, repr=False
    )


# ---------------------------------------------------------------------------
# BotPersonas registry
# ---------------------------------------------------------------------------

class BotPersonas:
    """Registry of all Murphy bot personas.

    Personas are built-in at construction time and can be extended via
    :meth:`register`.

    Usage::

        personas = BotPersonas()
        security_persona = personas.get("SecurityBot")
    """

    def __init__(self) -> None:
        self._personas: Dict[str, Persona] = {}
        self._build_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, persona: Persona) -> None:
        """Register a custom persona (or override a built-in)."""
        self._personas[persona.name] = persona
        logger.debug("Persona registered: %s", persona.name)

    def get(self, name: str) -> Optional[Persona]:
        """Return the :class:`Persona` with *name*, or ``None``."""
        return self._personas.get(name)

    def all(self) -> List[Persona]:
        """Return all registered personas."""
        return list(self._personas.values())

    def names(self) -> List[str]:
        """Return all persona names."""
        return list(self._personas.keys())

    def persona_for_room(self, room_key: str) -> Optional[Persona]:
        """Return the first persona that monitors *room_key*."""
        for persona in self._personas.values():
            if room_key in persona.monitored_rooms:
                return persona
        return None

    def persona_for_subsystem(self, subsystem: str) -> Optional[Persona]:
        """Return the first persona responsible for *subsystem*."""
        for persona in self._personas.values():
            if subsystem in persona.subsystems:
                return persona
        return None

    # ------------------------------------------------------------------
    # Built-in personas
    # ------------------------------------------------------------------

    def _build_defaults(self) -> None:
        personas = [
            Persona(
                name="TriageBot",
                description=(
                    "Routes incoming tasks to the correct Murphy subsystems. "
                    "Acts as the primary entry point for all !murphy commands."
                ),
                monitored_rooms=["system-status", "hitl-approvals"],
                commands={
                    "status":   "Show Murphy system status",
                    "health":   "Show health of all subsystems",
                    "overview": "Show orchestrator overview",
                    "execute":  "Execute a Murphy command",
                    "chat":     "Chat with Murphy AI",
                    "help":     "Show command help",
                },
                subsystems=[
                    "execution-engine",
                    "execution-orchestrator",
                    "confidence-engine",
                    "librarian",
                    "system-status",
                ],
            ),
            Persona(
                name="SecurityBot",
                description=(
                    "Monitors security_plane, manages keys, and reports threats "
                    "to #murphy-security-alerts."
                ),
                monitored_rooms=["security-plane", "security-alerts", "security-audit-scanner"],
                commands={
                    "security scan":    "Run a security audit scan",
                    "security audit":   "Show latest security audit report",
                    "security keys":    "List managed key IDs",
                    "security rotate":  "Rotate a managed key",
                    "security status":  "Show security plane status",
                    "security permissions": "Show RBAC permissions",
                },
                subsystems=[
                    "security-plane",
                    "security-plane-adapter",
                    "security-audit-scanner",
                    "security-hardening-config",
                    "fastapi-security",
                    "flask-security",
                    "oauth-oidc-provider",
                    "secure-key-manager",
                    "murphy-credential-gate",
                    "key-harvester",
                    "groq-key-rotator",
                ],
            ),
            Persona(
                name="EngineeringBot",
                description=(
                    "Interfaces with murphy_engineering_toolbox, simulation_engine, "
                    "and domain_expert_system."
                ),
                monitored_rooms=["murphy-engineering-toolbox", "simulation-engine", "domain-expert-system"],
                commands={
                    "eng simulate":   "Run an engineering simulation",
                    "eng domain":     "Query domain expert system",
                    "eng toolbox":    "List engineering toolbox capabilities",
                    "eng twin":       "Interact with digital twin",
                    "eng vision":     "Run computer vision pipeline",
                    "eng sensor":     "Query sensor fusion data",
                    "eng perception": "Run autonomous perception",
                },
                subsystems=[
                    "murphy-engineering-toolbox",
                    "simulation-engine",
                    "domain-engine",
                    "domain-expert-system",
                    "domain-expert-integration",
                    "domain-gate-generator",
                    "dynamic-expert-generator",
                    "digital-twin-engine",
                    "computer-vision-pipeline",
                    "murphy-sensor-fusion",
                    "murphy-autonomous-perception",
                ],
            ),
            Persona(
                name="LibrarianBot",
                description=(
                    "Interfaces with system_librarian, knowledge_graph_builder, "
                    "and rag_vector_integration."
                ),
                monitored_rooms=["librarian", "knowledge-graph-builder", "rag-vector-integration"],
                commands={
                    "librarian query":        "Semantic query the Murphy knowledge base",
                    "librarian capabilities": "List librarian capabilities",
                    "librarian graph":        "Query the knowledge graph",
                    "librarian rag":          "Run RAG vector search",
                    "librarian kb":           "Query knowledge base",
                    "librarian gap":          "Show knowledge gap analysis",
                },
                subsystems=[
                    "librarian",
                    "knowledge-graph-builder",
                    "knowledge-base-manager",
                    "knowledge-gap-system",
                    "rag-vector-integration",
                    "generative-knowledge-builder",
                    "concept-graph-engine",
                    "concept-translation",
                ],
            ),
            Persona(
                name="CADBot",
                description=(
                    "Interfaces with murphy_drawing_engine, digital_twin_engine, "
                    "and image_generation_engine."
                ),
                monitored_rooms=["murphy-drawing-engine", "digital-twin-engine", "image-generation-engine"],
                commands={
                    "cad draw":       "Generate a technical drawing",
                    "cad twin":       "Render digital twin",
                    "cad image":      "Generate an image artifact",
                    "cad asset":      "Generate a digital asset",
                    "cad simulation": "Run CAD simulation",
                },
                subsystems=[
                    "murphy-drawing-engine",
                    "digital-twin-engine",
                    "image-generation-engine",
                    "digital-asset-generator",
                    "simulation-engine",
                ],
            ),
            Persona(
                name="KeyManagerBot",
                description=(
                    "Manages secure_key_manager, groq_key_rotator, and key_harvester."
                ),
                monitored_rooms=["secure-key-manager", "groq-key-rotator", "key-harvester"],
                commands={
                    "keys list":    "List all managed key IDs",
                    "keys rotate":  "Rotate a specific key",
                    "keys status":  "Show key manager status",
                    "keys harvest": "Run key harvester scan",
                    "keys groq":    "Show Groq key rotation status",
                },
                subsystems=[
                    "secure-key-manager",
                    "groq-key-rotator",
                    "key-harvester",
                    "murphy-credential-gate",
                    "credential-profile-system",
                ],
            ),
            Persona(
                name="ComplianceBot",
                description=(
                    "Interfaces with compliance_engine, governance_framework, "
                    "and gate_synthesis."
                ),
                monitored_rooms=["compliance-engine", "governance-framework", "gate-synthesis"],
                commands={
                    "compliance status":   "Show compliance posture",
                    "compliance report":   "Generate compliance report",
                    "compliance gates":    "Show gate synthesis status",
                    "compliance rbac":     "Show RBAC governance state",
                    "compliance audit":    "Run compliance audit",
                    "governance policies": "List governance policies",
                    "governance toggle":   "Toggle a governance rule",
                },
                subsystems=[
                    "compliance-engine",
                    "compliance-as-code-engine",
                    "compliance-monitoring",
                    "governance-framework",
                    "base-governance-runtime",
                    "rbac-governance",
                    "authority-gate",
                    "gate-bypass-controller",
                    "governance-kernel",
                    "governance-toggle",
                    "gate-synthesis",
                ],
            ),
            Persona(
                name="MonitoringBot",
                description=(
                    "Interfaces with health_monitor, telemetry_system, and "
                    "prometheus_metrics_exporter."
                ),
                monitored_rooms=["health-monitor", "telemetry-system", "prometheus-metrics-exporter", "monitoring"],
                commands={
                    "monitor health":    "Show full health dashboard",
                    "monitor metrics":   "Show Prometheus metrics snapshot",
                    "monitor telemetry": "Show telemetry status",
                    "monitor slo":       "Show SLO tracker report",
                    "monitor logs":      "Show recent log analysis",
                    "monitor alerts":    "Show active alert rules",
                    "monitor trace":     "Show Murphy trace snapshot",
                },
                subsystems=[
                    "health-monitor",
                    "heartbeat-liveness-protocol",
                    "activated-heartbeat-runner",
                    "prometheus-metrics-exporter",
                    "observability-counters",
                    "murphy-trace",
                    "bot-telemetry-normalizer",
                    "telemetry-adapter",
                    "telemetry-system",
                    "telemetry-learning",
                    "operational-slo-tracker",
                    "slo-remediation-bridge",
                    "log-analysis-engine",
                    "alert-rules-engine",
                    "causal-spike-analyzer",
                ],
            ),
            Persona(
                name="ExecutionBot",
                description=(
                    "Interfaces with execution_engine, execution_orchestrator, "
                    "and automation_scheduler."
                ),
                monitored_rooms=["execution-engine", "execution-orchestrator", "automation-scheduler"],
                commands={
                    "exec run":       "Execute a task",
                    "exec workflows": "List active workflows",
                    "exec schedule":  "Schedule a task",
                    "exec status":    "Show execution engine status",
                    "exec queue":     "Show task queue",
                    "exec cancel":    "Cancel a running task",
                    "exec history":   "Show execution history",
                },
                subsystems=[
                    "execution-engine",
                    "execution-orchestrator",
                    "execution-packet-compiler",
                    "execution",
                    "automation-scheduler",
                    "automation-scaler",
                    "automation-marketplace",
                    "automation-mode-controller",
                    "full-automation-controller",
                    "self-automation-orchestrator",
                    "murphy-native-automation",
                    "automation-integration-hub",
                    "automation-loop-connector",
                    "automation-rbac-controller",
                    "automation-readiness-evaluator",
                    "automation-type-registry",
                ],
            ),
            Persona(
                name="FinanceBot",
                description=(
                    "Interfaces with trading_bot_engine, financial_reporting_engine, "
                    "and invoice_processing_pipeline."
                ),
                monitored_rooms=["trading-bot-engine", "financial-reporting-engine", "finance"],
                commands={
                    "finance report":   "Generate financial report",
                    "finance invoices": "List recent invoices",
                    "finance trading":  "Show trading bot status",
                    "finance crypto":   "Show crypto portfolio",
                    "finance budget":   "Show budget status",
                    "finance costs":    "Show cost optimization report",
                },
                subsystems=[
                    "trading-bot-engine",
                    "trading-strategy-engine",
                    "trading-bot-lifecycle",
                    "trading-hitl-gateway",
                    "trading-shadow-learner",
                    "financial-reporting-engine",
                    "invoice-processing-pipeline",
                    "crypto-exchange-connector",
                    "crypto-portfolio-tracker",
                    "crypto-risk-manager",
                    "crypto-wallet-manager",
                    "coinbase-connector",
                    "budget-aware-processor",
                    "cost-optimization-advisor",
                    "cost-explosion-gate",
                    "market-data-feed",
                ],
            ),
            Persona(
                name="OnboardingBot",
                description=(
                    "Interfaces with onboarding_flow, agentic_onboarding_engine, "
                    "and setup_wizard."
                ),
                monitored_rooms=["onboarding-flow", "agentic-onboarding-engine"],
                commands={
                    "onboard start":   "Start onboarding flow",
                    "onboard status":  "Show onboarding progress",
                    "onboard team":    "Run team pipeline onboarding",
                    "onboard wizard":  "Launch setup wizard",
                },
                subsystems=[
                    "onboarding-flow",
                    "agentic-onboarding-engine",
                    "onboarding-automation-engine",
                    "onboarding-team-pipeline",
                ],
            ),
        ]
        for p in personas:
            self._personas[p.name] = p


__all__ = ["Persona", "BotPersonas"]
