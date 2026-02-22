"""
Murphy System 1.0 - Complete Runtime

This is the main entry point for Murphy System 1.0, integrating:
- Original Murphy Runtime (319 files)
- Phase 1-5 Implementations (form intake, validation, correction, learning)
- Universal Control Plane (modular engines)
- Inoni Business Automation (5 engines)
- Integration Engine (GitHub ingestion with HITL)
- Two-Phase Orchestrator (generative setup → production execution)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

import sys
import os
import json
import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Literal, Set, TYPE_CHECKING
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
import logging
import asyncio
import time
import re
from uuid import uuid4
from threading import Lock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Core imports
from src.module_manager import module_manager
from src.modular_runtime import ModularRuntime

if TYPE_CHECKING:
    from src.compute_plane.service import ComputeService as ComputeServiceType
else:
    ComputeServiceType = Any

# Universal Control Plane
try:
    from universal_control_plane import UniversalControlPlane
except ImportError as e:
    print(f"⚠️  Warning: Could not import UniversalControlPlane: {e}")
    UniversalControlPlane = None

# Inoni Business Automation
try:
    from inoni_business_automation import InoniBusinessAutomation
except ImportError as e:
    print(f"⚠️  Warning: Could not import InoniBusinessAutomation: {e}")
    InoniBusinessAutomation = None

# Integration Engine
try:
    from src.integration_engine.unified_engine import UnifiedIntegrationEngine
except ImportError as e:
    print(f"⚠️  Warning: Could not import UnifiedIntegrationEngine: {e}")
    print(f"   This may be due to missing dependencies. Please ensure all requirements are installed.")
    UnifiedIntegrationEngine = None

# Two-Phase Orchestrator
try:
    from two_phase_orchestrator import TwoPhaseOrchestrator
except ImportError as e:
    print(f"⚠️  Warning: Could not import TwoPhaseOrchestrator: {e}")
    TwoPhaseOrchestrator = None

# Phase 1-5 Components (optional - may not all be available)
try:
    from src.form_intake.handlers import FormHandlerRegistry as FormHandler
except ImportError:
    try:
        from src.form_intake.handlers import PlanUploadFormHandler as FormHandler
    except ImportError:
        FormHandler = None

try:
    from src.confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
except ImportError:
    UnifiedConfidenceEngine = None

try:
    from src.execution_engine.integrated_form_executor import IntegratedFormExecutor
except ImportError:
    IntegratedFormExecutor = None

try:
    from src.learning_engine.integrated_correction_system import IntegratedCorrectionSystem
except ImportError:
    IntegratedCorrectionSystem = None

try:
    from src.supervisor_system.integrated_hitl_monitor import IntegratedHITLMonitor
except ImportError:
    IntegratedHITLMonitor = None

# Original Murphy Components
try:
    from src.system_librarian import SystemLibrarian
    from src.true_swarm_system import TrueSwarmSystem
    from src.governance_framework.scheduler import GovernanceScheduler, ScheduledAgent, PriorityLevel
    from src.governance_framework.agent_descriptor_complete import (
        AgentDescriptor,
        AuthorityBand as GovernanceAuthorityBand,
        ActionType as GovernanceActionType,
        ActionSet
    )
    from src.telemetry_learning.ingestion import TelemetryIngester, TelemetryBus
except ImportError as e:
    print(f"Warning: Some original Murphy components not available: {e}")
    SystemLibrarian = TrueSwarmSystem = GovernanceScheduler = TelemetryIngester = TelemetryBus = None
    ScheduledAgent = PriorityLevel = AgentDescriptor = GovernanceAuthorityBand = GovernanceActionType = ActionSet = None

# MFGC Adapter
try:
    from src.mfgc_adapter import MFGCAdapter, MFGCConfig
    from src.system_integrator import SystemIntegrator
except ImportError as e:
    print(f"Warning: MFGC adapter not available: {e}")
    MFGCAdapter = MFGCConfig = SystemIntegrator = None

# Adapter Framework
try:
    from src.adapter_framework.adapter_runtime import AdapterRuntime
except ImportError as e:
    print(f"Warning: Adapter runtime not available: {e}")
    AdapterRuntime = None

# Org Chart System
try:
    from src.organization_chart_system import OrganizationChart
except ImportError as e:
    print(f"Warning: Organization chart system not available: {e}")
    OrganizationChart = None

# FastAPI for REST API
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("Warning: FastAPI not installed. Install with: pip install fastapi uvicorn")
    FastAPI = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GOVERNANCE_AVAILABLE = all(
    component is not None
    for component in (
        GovernanceScheduler,
        ScheduledAgent,
        AgentDescriptor,
        GovernanceAuthorityBand,
        GovernanceActionType,
        ActionSet
    )
)


class LivingDocument:
    """
    Living document model used for block-command workflows.

    - magnify: expands domain depth to increase context coverage
    - simplify: reduces complexity to improve clarity
    - solidify: locks the document and triggers swarm task generation
    - block_tree: hierarchical representation of pending/complete actions
    - org_chart_plan: populated by activation previews with position mappings
    """

    def __init__(self, doc_id: str, title: str, content: str, doc_type: str):
        self.doc_id = doc_id
        self.title = title
        self.content = content
        self.doc_type = doc_type
        self.state = "INITIAL"
        self.confidence = 0.45
        self.domain_depth = 0
        self.history: List[Dict[str, Any]] = []
        self.children: List[Dict[str, Any]] = []
        self.parent_id: Optional[str] = None
        self.created_at = datetime.utcnow().isoformat()
        self.block_tree: Dict[str, Any] = {}
        self.gates: List[Dict[str, Any]] = []
        self.constraints: List[str] = []
        self.generated_tasks: List[Dict[str, Any]] = []
        self.gate_synthesis_gates: List[Dict[str, Any]] = []
        self.capability_tests: List[Dict[str, Any]] = []
        self.automation_summary: Dict[str, Any] = {}
        self.gate_policy: List[Dict[str, Any]] = []
        self.librarian_conditions: List[Dict[str, Any]] = []
        self.org_chart_plan: Dict[str, Any] = {}

    def magnify(self, domain: str) -> Dict[str, Any]:
        self.domain_depth += 15
        self.confidence = min(1.0, self.confidence + 0.1)
        self.history.append({
            "action": "magnify",
            "domain": domain,
            "timestamp": datetime.utcnow().isoformat()
        })
        return self.to_dict()

    def simplify(self) -> Dict[str, Any]:
        self.domain_depth = max(0, self.domain_depth - 10)
        self.confidence = min(1.0, self.confidence + 0.05)
        self.history.append({
            "action": "simplify",
            "timestamp": datetime.utcnow().isoformat()
        })
        return self.to_dict()

    def solidify(self) -> Dict[str, Any]:
        self.state = "SOLIDIFIED"
        self.confidence = min(1.0, self.confidence + 0.2)
        self.history.append({
            "action": "solidify",
            "timestamp": datetime.utcnow().isoformat()
        })
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "doc_type": self.doc_type,
            "state": self.state,
            "confidence": self.confidence,
            "domain_depth": self.domain_depth,
            "history": self.history,
            "children": self.children,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "block_tree": self.block_tree,
            "gates": self.gates,
            "constraints": self.constraints,
            "generated_tasks": self.generated_tasks,
            "gate_synthesis_gates": self.gate_synthesis_gates,
            "capability_tests": self.capability_tests,
            "automation_summary": self.automation_summary,
            "gate_policy": self.gate_policy,
            "librarian_conditions": self.librarian_conditions,
            "org_chart_plan": self.org_chart_plan
        }


class MurphySystem:
    """
    Murphy System 1.0 - Complete Runtime
    
    Integrates all Murphy components into a unified system:
    - Universal Control Plane (any automation type)
    - Inoni Business Automation (self-operation)
    - Integration Engine (self-integration)
    - Two-Phase Execution (setup → execute)
    - Phase 1-5 Implementations (forms, validation, correction, learning)
    - Original Murphy Runtime (319 files)
    """
    ACTIVATION_CONFIDENCE_THRESHOLD = 0.7
    AUTOMATION_EXECUTION_SUCCESS_THRESHOLD = 70.0
    REQUIREMENT_COVERAGE_TARGET = 0.99
    ACTIVATION_SOLIDIFIED_STATE = "SOLIDIFIED"
    GATE_OVERRIDE_VALUES = {"open", "blocked"}
    COMPLIANCE_BLOCKED_STATES = {"blocked", "failed", "denied"}
    COMPLIANCE_PENDING_STATES = {"pending", "review", "queued"}
    VALID_DELIVERY_CHANNELS = {"document", "email", "chat", "voice", "translation", "unknown"}
    DEFAULT_TRANSLATION_SOURCE_LOCALE = "auto"
    TRANSLATION_GAP_ACTION = "Provide target locale to queue the translation delivery."
    PERSISTENCE_DIR_ENV = "MURPHY_PERSISTENCE_DIR"
    PERSISTENCE_SNAPSHOT_PREFIX = "activation_snapshot"
    AUDIT_EXPORT_PREFIX = "audit_export"
    MAX_FAILURE_MODE_DESC_LENGTH = 80
    MAX_SAMPLE_GATES = 3
    DEFAULT_PHASE_VERBOSITY = 1
    DELIVERABLE_EXTRACTION_KEYS = ("description", "task", "name", "stage")  # Ordered keys for deliverable text.
    ORG_CHART_FALLBACK_POSITIONS = 2  # Positions used when keyword matching fails.
    REGION_ALIASES = {
        "north_america": ["north america", "usa", "us", "united states", "canada"],
        "europe": ["europe", "eu", "european", "uk", "united kingdom", "britain"],
        "apac": ["apac", "asia", "australia", "japan", "india", "singapore"],
        "latam": ["latam", "latin america", "brazil", "mexico"],
        "mea": ["middle east", "africa", "mea"],
        "global": ["global", "worldwide", "international"]
    }
    LLM_MODULE_CANDIDATES = (
        "src.llm_integration",
        "src.llm_controller",
        "src.local_llm_fallback"
    )
    MODULE_CATALOG = [
        {
            "name": "module_manager",
            "path": "src.module_manager",
            "description": "Module manager registry",
            "capabilities": ["module_registry", "capability_mapping"]
        },
        {
            "name": "modular_runtime",
            "path": "src.modular_runtime",
            "description": "Modular runtime core",
            "capabilities": ["runtime", "module_execution"]
        },
        {
            "name": "universal_control_plane",
            "path": "universal_control_plane",
            "description": "Universal control plane",
            "capabilities": ["control_plane", "execution_policy"]
        },
        {
            "name": "inoni_business_automation",
            "path": "inoni_business_automation",
            "description": "Business automation engines",
            "capabilities": ["business_automation", "executive_operations"]
        },
        {
            "name": "two_phase_orchestrator",
            "path": "two_phase_orchestrator",
            "description": "Two-phase orchestrator",
            "capabilities": ["orchestration", "handoff"]
        },
        {
            "name": "form_intake",
            "path": "src.form_intake.handlers",
            "description": "Form intake handlers",
            "capabilities": ["forms", "intake"]
        },
        {
            "name": "confidence_engine",
            "path": "src.confidence_engine.unified_confidence_engine",
            "description": "Confidence evaluation engine",
            "capabilities": ["confidence", "validation"]
        },
        {
            "name": "execution_engine",
            "path": "src.execution_engine.integrated_form_executor",
            "description": "Execution engine",
            "capabilities": ["execution", "actions"]
        },
        {
            "name": "learning_engine",
            "path": "src.learning_engine.integrated_correction_system",
            "description": "Learning and correction engine",
            "capabilities": ["learning", "correction"]
        },
        {
            "name": "hitl_monitor",
            "path": "src.supervisor_system.integrated_hitl_monitor",
            "description": "Human-in-the-loop monitor",
            "capabilities": ["hitl", "supervision"]
        },
        {
            "name": "governance_framework",
            "path": "src.governance_framework.scheduler",
            "description": "Governance scheduling framework",
            "capabilities": ["governance", "scheduling"]
        },
        {
            "name": "telemetry_ingestion",
            "path": "src.telemetry_learning.ingestion",
            "description": "Telemetry ingestion and analytics",
            "capabilities": ["telemetry", "analytics"]
        },
        {
            "name": "mfgc_adapter",
            "path": "src.mfgc_adapter",
            "description": "MFGC adapter",
            "capabilities": ["adapter", "execution_fallback"]
        },
        {
            "name": "system_integrator",
            "path": "src.system_integrator",
            "description": "System integrator bridge",
            "capabilities": ["integration", "adapter_bridge"]
        },
        {
            "name": "gate_synthesis",
            "path": "src.gate_synthesis",
            "description": "Gate synthesis engine",
            "capabilities": ["gates", "risk", "compliance"]
        },
        {
            "name": "true_swarm_system",
            "path": "src.true_swarm_system",
            "description": "Swarm execution planner",
            "capabilities": ["swarm", "task_expansion"]
        },
        {
            "name": "domain_swarms",
            "path": "src.domain_swarms",
            "description": "Domain swarm selection",
            "capabilities": ["domain_detection", "swarm_candidates"]
        },
        {
            "name": "system_librarian",
            "path": "src.system_librarian",
            "description": "Librarian knowledge and conditions",
            "capabilities": ["librarian", "conditions"]
        },
        {
            "name": "organization_chart_system",
            "path": "src.organization_chart_system",
            "description": "Org chart coverage and contracts",
            "capabilities": ["org_chart", "contracts"]
        },
        {
            "name": "compute_plane",
            "path": "src.compute_plane.service",
            "description": "Deterministic compute plane",
            "capabilities": ["deterministic_compute"]
        },
        {
            "name": "recursive_stability_controller",
            "path": "src.recursive_stability_controller.rsc_service",
            "description": "Recursive stability control",
            "capabilities": ["stability", "feedback"]
        },
        {
            "name": "integration_engine",
            "path": "src.integration_engine.unified_engine",
            "description": "Integration engine",
            "capabilities": ["integrations", "handoff"]
        },
        {
            "name": "adapter_framework",
            "path": "src.adapter_framework.adapter_runtime",
            "description": "Adapter execution runtime",
            "capabilities": ["adapter_runtime", "device_execution"]
        },
        {
            "name": "telemetry_adapter",
            "path": "src.telemetry_adapter",
            "description": "Telemetry adapter",
            "capabilities": ["telemetry"]
        },
        {
            "name": "module_compiler_adapter",
            "path": "src.module_compiler_adapter",
            "description": "Module compiler adapter",
            "capabilities": ["module_compiler"]
        },
        {
            "name": "librarian_adapter",
            "path": "src.librarian_adapter",
            "description": "Librarian adapter",
            "capabilities": ["librarian_adapter"]
        },
        {
            "name": "neuro_symbolic_adapter",
            "path": "src.neuro_symbolic_adapter",
            "description": "Neuro-symbolic adapter",
            "capabilities": ["neuro_symbolic"]
        },
        {
            "name": "security_plane_adapter",
            "path": "src.security_plane_adapter",
            "description": "Security plane adapter",
            "capabilities": ["security"]
        }
    ]
    MODULE_SCAN_EXCLUDED_DIRS = {"__pycache__", "tests", "test", "docs", "documentation", "examples"}
    MODULE_LOCAL_SCAN_EXCLUDED_DIRS = MODULE_SCAN_EXCLUDED_DIRS | {"src"}
    MODULE_VERSIONED_FILENAME_RE = re.compile(r"_\d+\.\d+(?:\.\d+)?_runtime$")
    MODULE_AUTO_SCAN_TAG = "auto_registered"
    MODULE_CATEGORY_PREFIX = "category:"
    MODULE_PATH_PREFIX = "module:"
    MODULE_CATEGORY_UNKNOWN = "unknown"
    COMPETITIVE_STATUS_AVAILABLE = "available"
    COMPETITIVE_STATUS_PARTIAL = "partial"
    COMPETITIVE_STATUS_MISSING = "missing"
    COMPETITIVE_FEATURE_STATUS_VALUES = {
        COMPETITIVE_STATUS_AVAILABLE,
        COMPETITIVE_STATUS_PARTIAL,
        COMPETITIVE_STATUS_MISSING
    }
    COMPETITIVE_FEATURES = [
        {
            "id": "workflow_orchestration",
            "label": "Workflow orchestration",
            "capabilities": ["orchestration", "handoff", "execution"],
            "description": "Coordinate multi-phase workflows across execution paths."
        },
        {
            "id": "event_driven_automation",
            "label": "Event-driven automation",
            "capabilities": ["scheduling", "governance"],
            "description": "Trigger automations from schedules and governance policies."
        },
        {
            "id": "adaptive_execution_routing",
            "label": "Adaptive execution routing",
            "capabilities": ["control_plane", "execution_policy", "confidence"],
            "description": "Route tasks across deterministic and LLM execution paths."
        },
        {
            "id": "connector_ecosystem",
            "label": "Connector ecosystem",
            "capabilities": ["integrations", "adapter_runtime"],
            "includes_integration_metrics": True,
            "description": "Integrate external systems, adapters, and delivery channels."
        },
        {
            "id": "multichannel_delivery",
            "label": "Multi-channel delivery",
            "capabilities": ["adapter_runtime", "integrations"],
            "description": "Deliver outputs across documents, email, chat, and voice."
        },
        {
            "id": "policy_as_code",
            "label": "Policy-as-code governance",
            "capabilities": ["governance", "compliance"],
            "description": "Encode governance policy checks and compliance assertions."
        },
        {
            "id": "governance_policy",
            "label": "Governance + HITL policy",
            "capabilities": ["governance", "hitl", "validation"],
            "description": "Enforce approvals and safety policies before execution."
        },
        {
            "id": "rbac_tenancy",
            "label": "RBAC + tenant governance",
            "capabilities": ["security", "governance"],
            "description": "Standardize role-based access controls and tenant policies."
        },
        {
            "id": "audit_compliance",
            "label": "Audit + compliance",
            "capabilities": ["telemetry", "risk", "compliance"],
            "description": "Audit automation actions with compliance gates and telemetry."
        },
        {
            "id": "persistent_memory",
            "label": "Persistent memory + replay",
            "capabilities": ["persistence", "audit"],
            "description": "Persist automation context and enable replayable approvals."
        },
        {
            "id": "observability_aiops",
            "label": "Observability + AIOps",
            "capabilities": ["telemetry", "analytics", "feedback"],
            "description": "Monitor runtime health with telemetry and feedback loops."
        },
        {
            "id": "monitoring_analytics",
            "label": "Monitoring + analytics",
            "capabilities": ["telemetry", "analytics"],
            "description": "Track execution metrics and performance analytics."
        },
        {
            "id": "ai_model_lifecycle",
            "label": "AI model lifecycle orchestration",
            "capabilities": ["learning", "analytics", "execution"],
            "description": "Coordinate model feedback, tuning signals, and runtime execution outcomes."
        },
        {
            "id": "low_code_automation",
            "label": "Low-code/no-code automation intake",
            "capabilities": ["forms", "intake", "governance"],
            "description": "Enable guided form-based automation setup with governance validation."
        },
        {
            "id": "self_healing",
            "label": "Self-healing automation",
            "capabilities": ["stability", "feedback", "governance"],
            "description": "Recover from failures with rollback and stabilization logic."
        },
        {
            "id": "self_improvement",
            "label": "Self-improvement",
            "capabilities": ["learning", "correction", "feedback", "telemetry"],
            "description": "Learn from corrections with feedback telemetry for self-optimization."
        },
        {
            "id": "knowledge_rag",
            "label": "Knowledge + RAG automation",
            "capabilities": ["librarian", "conditions", "learning"],
            "description": "Ground automation decisions in curated knowledge and conditions."
        },
        {
            "id": "swarm_expansion",
            "label": "Dynamic swarm expansion",
            "capabilities": ["swarm", "task_expansion"],
            "description": "Expand tasks into parallel execution swarms."
        },
        {
            "id": "connector_marketplace",
            "label": "Connector marketplace readiness",
            "capabilities": ["adapter_runtime", "module_compiler", "integrations"],
            "description": "Compose adapters and connectors for marketplace-grade integrations."
        },
        {
            "id": "security_hardening",
            "label": "Security hardening",
            "capabilities": ["security"],
            "description": "Protect automation runs with security controls."
        }
    ]
    INTEGRATION_CONNECTOR_CATALOG = [
        {
            "id": "document_delivery",
            "label": "Document delivery adapter",
            "channel": "document",
            "requires": "adapter_runtime"
        },
        {
            "id": "email_delivery",
            "label": "Email delivery adapter",
            "channel": "email",
            "requires": "adapter_runtime"
        },
        {
            "id": "chat_delivery",
            "label": "Chat delivery adapter",
            "channel": "chat",
            "requires": "adapter_runtime"
        },
        {
            "id": "voice_delivery",
            "label": "Voice delivery adapter",
            "channel": "voice",
            "requires": "adapter_runtime"
        },
        {
            "id": "ticketing_integration",
            "label": "Ticketing/CRM integration",
            "channel": "ticketing",
            "requires": "integration_engine"
        },
        {
            "id": "remote_access",
            "label": "Remote access onboarding",
            "channel": "remote_access",
            "requires": "integration_engine"
        },
        {
            "id": "patch_rollback",
            "label": "Patch and rollback automation",
            "channel": "operations",
            "requires": "governance_scheduler"
        }
    ]
    CORE_ADAPTER_CANDIDATES = [
        {
            "id": "telemetry_adapter",
            "label": "Telemetry adapter",
            "module": "src.telemetry_adapter",
            "channel": "telemetry"
        },
        {
            "id": "module_compiler_adapter",
            "label": "Module compiler adapter",
            "module": "src.module_compiler_adapter",
            "channel": "module_compiler"
        },
        {
            "id": "librarian_adapter",
            "label": "Librarian adapter",
            "module": "src.librarian_adapter",
            "channel": "librarian"
        },
        {
            "id": "neuro_symbolic_adapter",
            "label": "Neuro-symbolic adapter",
            "module": "src.neuro_symbolic_adapter",
            "channel": "neuro_symbolic"
        },
        {
            "id": "security_plane_adapter",
            "label": "Security plane adapter",
            "module": "src.security_plane_adapter",
            "channel": "security"
        }
    ]
    DELIVERY_ADAPTER_CANDIDATES = [
        {
            "id": "document_delivery",
            "label": "Document delivery adapter",
            "channel": "document",
            "module": "src.adapter_framework.adapters.http_adapter"
        },
        {
            "id": "email_delivery",
            "label": "Email delivery adapter",
            "channel": "email",
            "module": "src.adapter_framework.adapters.http_adapter"
        },
        {
            "id": "chat_delivery",
            "label": "Chat delivery adapter",
            "channel": "chat",
            "module": "src.adapter_framework.adapters.http_adapter"
        },
        {
            "id": "voice_delivery",
            "label": "Voice delivery adapter",
            "channel": "voice",
            "module": "src.adapter_framework.adapters.http_adapter"
        },
        {
            "id": "translation_delivery",
            "label": "Translation delivery adapter",
            "channel": "translation",
            "module": "src.adapter_framework.adapters.http_adapter"
        }
    ]
    COMPLETION_SNAPSHOT_AREAS = {
        "execution_wiring": 47,
        "deterministic_llm_routing": 40,
        "persistence_replay": 23,
        "multichannel_delivery": 58,
        "compliance_validation": 38,
        "operational_automation": 22,
        "ui_user_testing": 70,
        "dynamic_chain_test_coverage": 96
    }
    COMPLETION_REMEDIATION_THRESHOLD_PERCENT = 50
    # Phrase tokens intentionally rely on substring matching against normalized text.
    STRICT_EXECUTION_MODE_TOKENS = {"strict", "regulated", "compliance", "low risk", "conservative"}
    DYNAMIC_EXECUTION_MODE_TOKENS = {"dynamic", "high autonomy", "production mode", "fast mode"}
    DOCUMENT_PLACEHOLDER_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"
    EXTERNAL_SENSOR_CATALOG = {
        "marketing": [
            {
                "id": "gdelt_media_volume",
                "metric": "media_volume_index",
                "source": "GDELT 2.1 Events API",
                "url": "https://api.gdeltproject.org/api/v2/doc/doc",
                "regions": ["global"],
                "access": "free"
            },
            {
                "id": "wikimedia_pageviews",
                "metric": "interest_score",
                "source": "Wikimedia Pageviews API",
                "url": "https://wikimedia.org/api/rest_v1/",
                "regions": ["global"],
                "access": "free"
            }
        ],
        "finance": [
            {
                "id": "coingecko_prices",
                "metric": "crypto_price_change",
                "source": "CoinGecko API",
                "url": "https://api.coingecko.com/api/v3/",
                "regions": ["global"],
                "access": "free"
            },
            {
                "id": "stooq_equities",
                "metric": "equity_price",
                "source": "Stooq CSV API",
                "url": "https://stooq.com/q/l/",
                "regions": ["north_america", "europe", "global"],
                "access": "free"
            },
            {
                "id": "fred_macro_indicators",
                "metric": "macro_indicator",
                "source": "FRED API",
                "url": "https://api.stlouisfed.org/fred/",
                "regions": ["north_america"],
                "access": "free_api_key"
            },
            {
                "id": "ecb_fx_rates",
                "metric": "fx_rate",
                "source": "ECB SDW",
                "url": "https://sdw.ecb.europa.eu/",
                "regions": ["europe"],
                "access": "free"
            }
        ],
        "operations": [
            {
                "id": "open_meteo_ops",
                "metric": "weather_risk",
                "source": "Open-Meteo API",
                "url": "https://api.open-meteo.com/",
                "regions": ["global"],
                "access": "free"
            },
            {
                "id": "world_bank_logistics",
                "metric": "logistics_index",
                "source": "World Bank API",
                "url": "https://api.worldbank.org/v2/",
                "regions": ["global"],
                "access": "free"
            }
        ],
        "qa": [
            {
                "id": "nvd_cve_feed",
                "metric": "defect_risk",
                "source": "NVD CVE API",
                "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
                "regions": ["global"],
                "access": "free_api_key"
            }
        ],
        "compliance": [
            {
                "id": "govinfo_federal_law",
                "metric": "regulatory_update",
                "source": "GovInfo API",
                "url": "https://api.govinfo.gov/",
                "regions": ["north_america"],
                "access": "free_api_key"
            },
            {
                "id": "eur_lex_legislation",
                "metric": "regulatory_update",
                "source": "EUR-Lex",
                "url": "https://eur-lex.europa.eu/",
                "regions": ["europe"],
                "access": "free"
            },
            {
                "id": "uk_legislation",
                "metric": "regulatory_update",
                "source": "UK Legislation API",
                "url": "https://www.legislation.gov.uk/developer/",
                "regions": ["europe"],
                "access": "free"
            },
            {
                "id": "open_sanctions",
                "metric": "compliance_watchlist",
                "source": "OpenSanctions",
                "url": "https://www.opensanctions.org/",
                "regions": ["global"],
                "access": "free"
            },
            {
                "id": "world_bank_reg_quality",
                "metric": "regulatory_quality_index",
                "source": "World Bank API",
                "url": "https://api.worldbank.org/v2/",
                "regions": ["global"],
                "access": "free"
            }
        ],
        "general": [
            {
                "id": "open_meteo_general",
                "metric": "environment_risk",
                "source": "Open-Meteo API",
                "url": "https://api.open-meteo.com/",
                "regions": ["global"],
                "access": "free"
            }
        ]
    }

    OUTPUT_CHANNEL_TARGETS = [
        {"id": "document", "label": "Document report"},
        {"id": "email", "label": "Email summary"},
        {"id": "chat", "label": "Chat response"},
        {"id": "voice", "label": "Voice brief"},
        {"id": "api", "label": "Structured JSON output"}
    ]

    LEARNING_LOOP_VARIANTS = [
        {"id": "baseline", "focus": "Baseline requirements from onboarding"},
        {"id": "compliance", "focus": "Regulatory-focused requirements variant"},
        {"id": "growth", "focus": "Growth and marketing automation variant"}
    ]

    GOVERNANCE_OWNER_EXECUTIVE = "executive_branch"
    GOVERNANCE_OWNER_OPERATIONS = "operations_director"
    GOVERNANCE_OWNER_QA = "quality_assurance"

    DYNAMIC_IMPLEMENTATION_STAGES = [
        {
            "id": "requirements_identification",
            "label": "Requirements identification",
            "owner": "executive_branch",
            "info_reason": "Collect onboarding answers to finalize requirements."
        },
        {
            "id": "confidence_approval",
            "label": "Confidence & HITL approval",
            "owner": "hitl_manager",
            "info_reason": "Raise confidence or provide validation evidence; collect HITL approval."
        },
        {
            "id": "gate_alignment",
            "label": "Gate alignment & compliance",
            "owner": "governance",
            "info_reason": "Provide gate thresholds and compliance evidence."
        },
        {
            "id": "gate_sequencing",
            "label": "Gate sequencing & dependencies",
            "owner": "governance",
            "info_reason": "Define gate ordering and dependencies."
        },
        {
            "id": "compliance_review",
            "label": "Compliance review",
            "owner": "quality_assurance",
            "info_reason": "Attach regulatory evidence and QA sign-off checkpoints."
        },
        {
            "id": "workload_distribution",
            "label": "Workload distribution",
            "owner": "operations_director",
            "info_reason": "Allocate workload across org roles and contracts."
        },
        {
            "id": "execution_plan",
            "label": "Execution planning",
            "owner": "automation_engine",
            "wiring_reason": "Wire the orchestrator or MFGC adapter for live execution."
        },
        {
            "id": "swarm_generation",
            "label": "Swarm generation",
            "owner": "swarm_system",
            "wiring_reason": "Initialize the swarm system and seed swarm tasks."
        },
        {
            "id": "integration_wiring",
            "label": "Integration wiring",
            "owner": "integration_engine",
            "wiring_reason": "Configure integration engine connectors and handoff targets."
        },
        {
            "id": "automation_loop",
            "label": "Automation loop setup",
            "owner": "automation_engine",
            "loop": True,
            "wiring_reason": "Configure automation loop engine state and iteration storage.",
            "info_reason": "Define learning loop iterations and variants."
        },
        {
            "id": "multi_loop_schedule",
            "label": "Multi-loop scheduling",
            "owner": "automation_engine",
            "loop": True,
            "wiring_reason": "Wire multi-project scheduling and coordination service.",
            "info_reason": "Set multi-project loop cadence and dependencies."
        },
        {
            "id": "trigger_schedule",
            "label": "Timer & trigger schedule",
            "owner": "governance",
            "loop": True,
            "wiring_reason": "Connect the governance scheduler for timer/trigger automation.",
            "info_reason": "Specify trigger intervals, conditions, and automation rules."
        },
        {
            "id": "monitoring_feedback",
            "label": "Monitoring & feedback",
            "owner": "operations_director",
            "loop": True,
            "wiring_reason": "Attach monitoring sensors and compliance signals.",
            "info_reason": "Define monitoring metrics, thresholds, and alert rules."
        },
        {
            "id": "output_delivery",
            "label": "Output channel delivery",
            "owner": "delivery_engine",
            "info_reason": "Specify output channel templates and delivery rules."
        },
        {
            "id": "deliverable_review",
            "label": "Deliverable review",
            "owner": "quality_assurance",
            "info_reason": "Collect deliverable review evidence."
        },
        {
            "id": "rollback_plan",
            "label": "Rollback & recovery",
            "owner": "operations_director",
            "wiring_reason": "Define rollback and recovery automation steps."
        },
        {
            "id": "human_release",
            "label": "Human release & publishing",
            "owner": "hitl_manager",
            "info_reason": "Collect HITL approvals for release."
        }
    ]

    DYNAMIC_IMPLEMENTATION_FLEX_LINKS = [
        ("monitoring_feedback", "compliance_review"),
        ("trigger_schedule", "automation_loop"),
        ("output_delivery", "deliverable_review"),
        ("rollback_plan", "human_release")
    ]

    HIGH_CONFIDENCE_THRESHOLD = 0.75
    CONFIDENCE_DISPLAY_PRECISION = 3
    STAGE_CONFIDENCE_SCORES = {
        "ready": 0.9,
        "complete": 0.95,
        "pending": 0.5,
        "pending_approval": 0.45,
        "needs_info": 0.35,
        "needs_wiring": 0.25,
        "pending_compliance": 0.2,
        "blocked": 0.1,
        "needs_coverage": 0.3,
        "needs_compliance": 0.25,
        "unknown": 0.4
    }
    STAGE_TIME_ESTIMATES = {
        "ready": 5,
        "complete": 3,
        "pending": 30,
        "pending_approval": 40,
        "needs_info": 55,
        "needs_wiring": 65,
        "pending_compliance": 45,
        "blocked": 90,
        "needs_coverage": 50,
        "needs_compliance": 60,
        "unknown": 35
    }
    # Pass-through statuses reflect incomplete/blocked delivery states that should propagate directly.
    OUTPUT_STATUS_PASSTHROUGH = {
        "needs_wiring",
        "needs_coverage",
        "needs_compliance",
        "pending_compliance",
        "blocked"
    }
    CONFIDENCE_ENGINE_TASK_TYPES = {"confidence_engine", "confidence", "confidence_validation"}
    
    @classmethod
    def create_test_instance(cls) -> "MurphySystem":
        """Lightweight instance factory for unit tests.

        Initializes configuration defaults and leaves optional subsystems unset
        (integration_engine, governance_scheduler, inoni_automation) so tests can
        explicitly assert wiring behavior without running full initialization.
        """
        instance = cls.__new__(cls)
        instance.version = "1.0.0"
        instance.start_time = datetime.utcnow()
        instance._initialize_configuration_defaults()
        instance.execution_metrics = {"total": 0, "success": 0, "total_time": 0.0}
        instance.module_manager = module_manager
        instance.control_plane = None
        instance.integration_engine = None
        instance.governance_scheduler = None
        instance.inoni_automation = None
        instance.orchestrator = None
        instance.form_handler = None
        instance.confidence_engine = None
        instance.form_executor = None
        instance.correction_system = None
        instance.swarm_system = None
        instance.org_chart_system = None
        instance.hitl_monitor = None
        instance.librarian = None
        instance.telemetry_bus = None
        instance.telemetry_ingester = None
        instance.system_integrator = None
        instance.mfgc_adapter = None
        instance.integration_connectors = {}
        instance._adapter_availability = None
        instance.activation_usage = {}
        instance.sessions = {}
        instance.repositories = {}
        instance.active_automations = {}
        instance.form_submissions = {}
        instance.corrections = []
        instance.hitl_interventions = {}
        instance.chat_sessions = {}
        instance.living_documents = {}
        instance.document_sessions = {}
        instance._register_core_modules()
        return instance

    def _initialize_configuration_defaults(self) -> None:
        self.default_gate_policy = [
            {"name": "Magnify Gate", "threshold": 0.5, "stage": "discovery"},
            {"name": "Simplify Gate", "threshold": 0.6, "stage": "clarity"},
            {"name": "Solidify Gate", "threshold": 0.7, "stage": "commit"},
            {"name": "Executive Review Gate", "threshold": 0.65, "stage": "executive"},
            {"name": "Operations Director Gate", "threshold": 0.6, "stage": "operations"},
            {"name": "Marketing Strategy Gate", "threshold": 0.6, "stage": "marketing"},
            {"name": "QA Readiness Gate", "threshold": 0.75, "stage": "quality"},
            {"name": "HITL Contract Gate", "threshold": 0.7, "stage": "contracting"},
            {"name": "Execution Gate", "threshold": 0.8, "stage": "execution"}
        ]
        self.mfgc_config = {
            "enabled": False,
            "murphy_threshold": 0.3,
            "confidence_mode": "phase_locked",
            "authority_mode": "standard",
            "gate_synthesis": True,
            "emergency_gates": True,
            "audit_trail": True
        }
        self.mfgc_statistics = {
            "total_executions": 0,
            "success_rate": "0.0%",
            "average_execution_time": "0.000s"
        }
        self._compute_service: Optional[ComputeServiceType] = None
        self._compute_service_lock = Lock()
        self._session_lock = Lock()
        self.flow_steps = [
            {
                "stage": "signup",
                "prompt": "Collect signup details (company name, contact email, primary goal)."
            },
            {
                "stage": "region",
                "prompt": "Confirm the operating region/country for the automation. This is used for metric sensors."
            },
            {
                "stage": "setup",
                "prompt": "Gather setup requirements (data sources, integrations, auth requirements)."
            },
            {
                "stage": "automation_design",
                "prompt": "Define the automation workflow (trigger, actions, success criteria)."
            },
            {
                "stage": "automation_production",
                "prompt": "Confirm production rollout (monitoring, alerts, rollout window)."
            },
            {
                "stage": "billing",
                "prompt": "Select billing plan (usage tier, automation coverage, support level)."
            }
        ]

    def _create_mfgc_config(self, enabled_override: Optional[bool] = None) -> Optional["MFGCConfig"]:
        if not MFGCConfig:
            return None
        config_values = getattr(self, "mfgc_config", {})
        if enabled_override is not None:
            config_values = {**config_values, "enabled": enabled_override}
        return MFGCConfig(
            enabled=bool(config_values.get("enabled", False)),
            murphy_threshold=config_values.get("murphy_threshold", 0.3),
            confidence_mode=config_values.get("confidence_mode", "phase_locked"),
            authority_mode=config_values.get("authority_mode", "standard"),
            gate_synthesis=config_values.get("gate_synthesis", True),
            emergency_gates=config_values.get("emergency_gates", True),
            phase_verbosity=config_values.get("phase_verbosity", self.DEFAULT_PHASE_VERBOSITY),
            audit_trail=config_values.get("audit_trail", True)
        )

    def __init__(self):
        self.version = "1.0.0"
        self.start_time = datetime.utcnow()
        self._initialize_configuration_defaults()
        
        logger.info("="*80)
        logger.info(f"MURPHY SYSTEM {self.version} - INITIALIZING")
        logger.info("="*80)
        
        # Initialize core components
        logger.info("Initializing core components...")
        self.module_manager = module_manager
        self.modular_runtime = ModularRuntime()
        self._register_core_modules()
        
        # Initialize Universal Control Plane
        if UniversalControlPlane:
            logger.info("Initializing Universal Control Plane...")
            self.control_plane = UniversalControlPlane()
        else:
            logger.warning("Universal Control Plane not available")
            self.control_plane = None
        
        # Initialize Inoni Business Automation
        if InoniBusinessAutomation:
            logger.info("Initializing Inoni Business Automation...")
            self.inoni_automation = InoniBusinessAutomation()
        else:
            logger.warning("Inoni Business Automation not available")
            self.inoni_automation = None
        
        # Initialize Integration Engine
        if UnifiedIntegrationEngine:
            logger.info("Initializing Integration Engine...")
            self.integration_engine = UnifiedIntegrationEngine()
        else:
            logger.warning("Integration Engine not available (dependencies may be missing)")
            self.integration_engine = None
        
        # Initialize Two-Phase Orchestrator
        if TwoPhaseOrchestrator:
            logger.info("Initializing Two-Phase Orchestrator...")
            self.orchestrator = TwoPhaseOrchestrator()
        else:
            logger.warning("Two-Phase Orchestrator not available")
            self.orchestrator = None
        
        # Initialize Phase 1-5 Components
        logger.info("Initializing Phase 1-5 components...")
        self.form_handler = FormHandler() if FormHandler else None
        self.confidence_engine = UnifiedConfidenceEngine() if UnifiedConfidenceEngine else None
        self.form_executor = IntegratedFormExecutor() if IntegratedFormExecutor else None
        self.correction_system = IntegratedCorrectionSystem() if IntegratedCorrectionSystem else None
        self.hitl_monitor = IntegratedHITLMonitor() if IntegratedHITLMonitor else None
        
        # Initialize Original Murphy Components (if available)
        logger.info("Initializing original Murphy components...")
        try:
            self.librarian = SystemLibrarian() if SystemLibrarian else None
            self.swarm_system = TrueSwarmSystem() if TrueSwarmSystem else None
            self.governance_scheduler = GovernanceScheduler() if GovernanceScheduler else None
            self.org_chart_system = OrganizationChart() if OrganizationChart else None
            if TelemetryBus and TelemetryIngester:
                self.telemetry_bus = TelemetryBus()
                self.telemetry_ingester = TelemetryIngester(self.telemetry_bus)
            else:
                self.telemetry_bus = None
                self.telemetry_ingester = None
        except Exception as e:
            logger.warning(f"Some original components not available: {e}")
            self.org_chart_system = None

        # Initialize MFGC adapter for execution wiring
        if MFGCAdapter and SystemIntegrator:
            logger.info("Initializing MFGC adapter...")
            try:
                self.system_integrator = SystemIntegrator()
                config = self._create_mfgc_config()
                self.mfgc_adapter = MFGCAdapter(self.system_integrator, config)
            except Exception as exc:
                logger.warning("MFGC adapter initialization failed: %s", exc)
                self.system_integrator = None
                self.mfgc_adapter = None
        else:
            logger.warning("MFGC adapter not available")
            self.system_integrator = None
            self.mfgc_adapter = None
        
        # System state
        self.sessions: Dict[str, Dict] = {}
        self.repositories: Dict[str, Dict] = {}
        self.active_automations: Dict[str, Dict] = {}
        self.form_submissions: Dict[str, Dict] = {}
        self.corrections: List[Dict] = []
        self.hitl_interventions: Dict[str, Dict] = {}
        self.living_documents: Dict[str, LivingDocument] = {}
        self.document_sessions: Dict[str, str] = {}
        self.activation_usage: Dict[str, int] = {}
        self.integration_connectors: Dict[str, Dict[str, Any]] = {}
        self._adapter_availability: Optional[Dict[str, bool]] = None
        self.latest_activation_preview: Dict[str, Any] = {}
        self.execution_metrics = {"total": 0, "success": 0, "total_time": 0.0}
        self.chat_sessions: Dict[str, Dict] = {}

        logger.info("="*80)
        logger.info(f"MURPHY SYSTEM {self.version} - READY")
        logger.info("="*80)
    
    # ==================== CORE EXECUTION ====================

    def _prepare_activation_preview(
        self,
        task_description: str,
        task_type: str,
        session_id: Optional[str],
        parameters: Optional[Dict[str, Any]]
    ) -> Tuple[LivingDocument, Dict[str, Any]]:
        doc = self._ensure_document(task_description, task_type, session_id)
        self._update_document_tree(doc)
        onboarding_context = None
        if isinstance(parameters, dict):
            onboarding_context = parameters.get("onboarding_context")
        self._apply_delivery_connectors(parameters)
        activation_preview = self._build_activation_preview(
            doc,
            task_description=task_description,
            onboarding_context=onboarding_context
        )
        self.latest_activation_preview = activation_preview
        return doc, activation_preview

    def _apply_delivery_connectors(self, parameters: Optional[Dict[str, Any]]) -> None:
        if not isinstance(parameters, dict):
            return
        connector_entries = parameters.get("delivery_connectors")
        if connector_entries is None:
            return
        if not isinstance(connector_entries, list):
            logger.warning(
                "delivery_connectors must be a list; ignoring invalid value of type %s.",
                type(connector_entries).__name__
            )
            return
        valid_statuses = {"configured", "available", "unconfigured"}
        valid_channels = self.VALID_DELIVERY_CHANNELS
        for connector in connector_entries:
            if not isinstance(connector, dict):
                continue
            # Use "id" as the canonical connector identifier; "connector_id" remains for legacy inputs.
            connector_id = connector.get("id") or connector.get("connector_id")
            if not connector_id:
                continue
            status = connector.get("status", "unconfigured")
            if status not in valid_statuses:
                logger.warning(
                    "Unknown delivery connector status '%s' for %s; defaulting to 'unconfigured'.",
                    status,
                    connector_id
                )
                status = "unconfigured"
            channel = connector.get("channel", "unknown")
            if channel not in valid_channels:
                logger.warning(
                    "Unknown delivery connector channel '%s' for %s; defaulting to 'unknown'.",
                    channel,
                    connector_id
                )
                channel = "unknown"
            metadata = {
                key: value
                for key, value in connector.items()
                if key not in {"id", "connector_id", "status", "channel"}
            }
            self.integration_connectors[connector_id] = {
                "status": status,
                "channel": channel,
                "metadata": metadata
            }

    def _register_core_modules(self) -> None:
        if not getattr(self, "module_manager", None):
            return
        for module in self.MODULE_CATALOG:
            name = module["name"]
            if name in self.module_manager.available_modules:
                continue
            self.module_manager.register_module(
                name=name,
                module_path=module["path"],
                description=module["description"],
                capabilities=module["capabilities"]
            )
        self._register_src_inventory_modules()
        self._register_local_inventory_modules()

    def _register_src_inventory_modules(self) -> None:
        if not getattr(self, "module_manager", None):
            return
        src_root = Path(__file__).parent / "src"
        if not src_root.exists():
            return
        for module_path in self._collect_src_module_paths(src_root):
            if module_path in self.module_manager.available_modules:
                continue
            parts = module_path.split(".")
            category = parts[1] if len(parts) > 1 else "misc"
            capabilities = [
                self.MODULE_AUTO_SCAN_TAG,
                f"{self.MODULE_CATEGORY_PREFIX}{category}",
                f"{self.MODULE_PATH_PREFIX}{module_path}"
            ]
            self.module_manager.register_module(
                name=module_path,
                module_path=module_path,
                description=f"Auto-registered src module ({category})",
                capabilities=capabilities
            )

    def _register_local_inventory_modules(self) -> None:
        if not getattr(self, "module_manager", None):
            return
        root = Path(__file__).parent
        for module_path in self._collect_local_module_paths(root):
            if module_path in self.module_manager.available_modules:
                continue
            category = module_path.split(".")[0] if "." in module_path else "root"
            capabilities = [
                self.MODULE_AUTO_SCAN_TAG,
                f"{self.MODULE_CATEGORY_PREFIX}{category}",
                f"{self.MODULE_PATH_PREFIX}{module_path}"
            ]
            self.module_manager.register_module(
                name=module_path,
                module_path=module_path,
                description=f"Auto-registered local module ({category})",
                capabilities=capabilities
            )

    def _collect_src_module_paths(self, src_root: Path) -> List[str]:
        return self._collect_module_paths(src_root, "src")

    def _collect_local_module_paths(self, root: Path) -> List[str]:
        module_paths = set(self._collect_root_module_paths(root))
        for package_dir in root.iterdir():
            if not package_dir.is_dir():
                continue
            if package_dir.name in self.MODULE_LOCAL_SCAN_EXCLUDED_DIRS:
                continue
            if not (package_dir / "__init__.py").exists():
                continue
            module_paths.update(self._collect_module_paths(package_dir, package_dir.name))
        return sorted(module_paths)

    def _collect_root_module_paths(self, root: Path) -> List[str]:
        module_path_set: Set[str] = set()
        for py_file in root.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            if self.MODULE_VERSIONED_FILENAME_RE.search(py_file.stem):
                # Skip versioned module filenames (e.g., murphy_system_1.0_runtime.py).
                continue
            module_path_set.add(py_file.stem)
        return sorted(module_path_set)

    def _collect_module_paths(self, root: Path, prefix: str) -> List[str]:
        module_path_set: Set[str] = set()
        root_init = root / "__init__.py"
        for init_file in root.rglob("__init__.py"):
            if init_file == root_init:
                continue
            rel = init_file.parent.relative_to(root)
            if self._should_skip_module_path(rel.parts):
                continue
            module_path_set.add(f"{prefix}.{'.'.join(rel.parts)}")
        for py_file in root.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            rel = py_file.relative_to(root).with_suffix("")
            if self._should_skip_module_path(rel.parts):
                continue
            module_path_set.add(f"{prefix}.{'.'.join(rel.parts)}")
        return sorted(module_path_set)

    def _build_module_registry_summary(self) -> Dict[str, Any]:
        status = self.module_manager.get_module_status()
        modules = status.get("modules", {})
        auto_registered = [
            name
            for name, info in modules.items()
            if self.MODULE_AUTO_SCAN_TAG in info.get("capabilities", [])
        ]
        category_counts: Dict[str, int] = {}
        for info in modules.values():
            for capability in info.get("capabilities", []):
                if capability.startswith(self.MODULE_CATEGORY_PREFIX):
                    category = self._extract_category_from_capability(capability)
                    category_counts[category] = category_counts.get(category, 0) + 1
        core_names = {module["name"] for module in self.MODULE_CATALOG}
        missing_core = sorted(core_names - modules.keys())
        return {
            "total_available": status.get("total_available", len(modules)),
            "total_active": status.get("total_active", 0),
            "core_expected": len(core_names),
            "core_registered": len(core_names) - len(missing_core),
            "core_missing": missing_core,
            "auto_registered": len(auto_registered),
            "category_counts": category_counts
        }

    def _build_registry_health_snapshot(self) -> Dict[str, Any]:
        status = self.module_manager.get_module_status()
        summary = self._build_module_registry_summary()
        total_available = summary.get("total_available", 0)
        total_active = summary.get("total_active", 0)
        missing_core = summary.get("core_missing", [])
        reasons = []
        health = "healthy"
        if total_available == 0:
            health = "unavailable"
            reasons.append("No modules registered in module manager.")
        if missing_core:
            if health == "healthy":
                health = "needs_attention"
            reasons.append(f"Missing {len(missing_core)} core modules.")
        if total_available and total_active == 0:
            if health == "healthy":
                health = "needs_attention"
            reasons.append("No active modules reported.")
        if not reasons:
            reasons.append("Module registry healthy.")
        return {
            "status": health,
            "summary": summary,
            "reasons": reasons,
            "module_status": status
        }

    def _build_schema_drift_snapshot(self) -> Dict[str, Any]:
        drift_items = []
        persistence = self._build_persistence_status()
        if persistence.get("status") != "configured":
            drift_items.append({
                "area": "persistence",
                "status": persistence.get("status", "disabled"),
                "reason": persistence.get("reason", "Persistence path not configured.")
            })
        observability = self._build_observability_snapshot()
        if observability.get("status") != "available":
            drift_items.append({
                "area": "observability",
                "status": observability.get("status", "unavailable"),
                "reason": observability.get("reason", "Telemetry bus not initialized.")
            })
        delivery = self._build_delivery_adapter_snapshot()
        unconfigured = delivery.get("summary", {}).get("unconfigured", 0)
        if unconfigured:
            missing_adapters = [
                adapter["id"]
                for adapter in delivery.get("adapters", [])
                if not adapter.get("configured")
            ]
            drift_items.append({
                "area": "delivery_adapters",
                "status": "needs_integration",
                "count": unconfigured,
                "missing": missing_adapters
            })
        return {
            "status": "clear" if not drift_items else "drift_detected",
            "summary": {
                "total_issues": len(drift_items)
            },
            "issues": drift_items
        }

    def _extract_category_from_capability(self, capability: str) -> str:
        if not capability.startswith(self.MODULE_CATEGORY_PREFIX):
            return self.MODULE_CATEGORY_UNKNOWN
        parts = capability.split(":", 1)
        stripped = parts[1].strip()
        return stripped or self.MODULE_CATEGORY_UNKNOWN

    def _should_skip_module_path(self, parts: Tuple[str, ...]) -> bool:
        return any(part.startswith("__") or part in self.MODULE_SCAN_EXCLUDED_DIRS for part in parts)

    def _build_execution_policy(
        self,
        dynamic_implementation: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        params = parameters or {}
        enforce_policy = params.get("enforce_policy", True)
        if not dynamic_implementation:
            return {
                "status": "unavailable",
                "enforced": enforce_policy,
                "approval_required": False,
                "execution_blocked": True,
                "reason": "Dynamic implementation plan unavailable."
            }
        approval_policy = dynamic_implementation.get("approval_policy", {})
        approval_status = approval_policy.get("status", "needs_info")
        gate_status = dynamic_implementation.get("gate_status", "needs_info")
        execution_strategy = dynamic_implementation.get("execution_strategy", "simulation")
        overall_status = dynamic_implementation.get("status", "needs_info")
        if overall_status == "ready" and approval_status == "ready":
            status = "ready"
            reason = None
        elif execution_strategy == "simulation":
            status = "needs_wiring"
            reason = "Execution wiring unavailable; enable orchestrator integration or configure execution fallback."
        elif approval_status == "needs_info":
            status = "needs_info"
            reason = "Approval confidence below threshold; supply additional evidence."
        elif approval_status == "pending_approval":
            status = "pending_approval"
            reason = "HITL approval required before execution."
        elif gate_status in {"blocked", "pending"}:
            status = gate_status
            reason = "Compliance gates not cleared for execution."
        else:
            status = overall_status
            reason = f"Execution policy blocked by {overall_status} status."
        approval_required = approval_status == "pending_approval"
        execution_blocked = status != "ready"
        return {
            "status": status,
            "enforced": enforce_policy,
            "approval_required": approval_required,
            "execution_blocked": execution_blocked,
            "approval_status": approval_status,
            "gate_status": gate_status,
            "execution_strategy": execution_strategy,
            "reason": reason
        }

    def _get_persistence_dir(self) -> Optional[Path]:
        persistence_dir = os.getenv(self.PERSISTENCE_DIR_ENV)
        if not persistence_dir:
            return None
        return Path(persistence_dir)

    def _build_persistence_status(self) -> Dict[str, Any]:
        persistence_dir = self._get_persistence_dir()
        if not persistence_dir:
            disabled_reason = f"Set {self.PERSISTENCE_DIR_ENV} to enable persistence snapshots."
            return {
                "status": "disabled",
                "reason": disabled_reason,
                "audit_snapshot": {
                    "status": "disabled",
                    "reason": disabled_reason
                },
                "audit_export_snapshot": {
                    "status": "disabled",
                    "reason": disabled_reason,
                    "supported_formats": []
                },
                "replay_snapshot": {
                    "status": "disabled",
                    "reason": disabled_reason
                }
            }
        snapshot_index = self._build_persistence_snapshot_index(persistence_dir)
        audit_snapshot = self._build_audit_snapshot(persistence_dir, snapshot_index)
        audit_export_snapshot = self._build_audit_export_snapshot(persistence_dir, snapshot_index)
        replay_snapshot = self._build_persistence_replay_snapshot(snapshot_index)
        return {
            "status": "configured",
            "path": str(persistence_dir),
            "snapshot_index": snapshot_index,
            "audit_snapshot": audit_snapshot,
            "audit_export_snapshot": audit_export_snapshot,
            "replay_snapshot": replay_snapshot
        }

    def _build_audit_snapshot(
        self,
        persistence_dir: Path,
        snapshot_index: Dict[str, Any]
    ) -> Dict[str, Any]:
        status = snapshot_index.get("status", "missing")
        if status == "missing":
            return {
                "status": "missing",
                "reason": "Persistence directory not found for audit snapshots."
            }
        snapshots = snapshot_index.get("snapshots", [])
        latest_snapshot = snapshots[-1] if snapshots else None
        return {
            "status": "ready" if snapshots else "empty",
            "snapshot_count": snapshot_index.get("count", len(snapshots)),
            "latest_snapshot": latest_snapshot
        }

    def _build_audit_export_snapshot(
        self,
        persistence_dir: Path,
        snapshot_index: Dict[str, Any]
    ) -> Dict[str, Any]:
        supported_formats = ["json", "csv"]
        if not self.mfgc_config.get("audit_trail", True):
            return {
                "status": "disabled",
                "reason": "Audit trail disabled in configuration.",
                "supported_formats": []
            }
        status = snapshot_index.get("status", "missing")
        if status == "missing":
            return {
                "status": "missing",
                "reason": "Persistence directory not found for audit exports.",
                "supported_formats": supported_formats
            }
        export_files = sorted(
            persistence_dir.glob(f"{self.AUDIT_EXPORT_PREFIX}_*.*"),
            key=lambda path: path.name
        )
        latest_export = export_files[-1].name if export_files else None
        # Keep reason populated across all audit export states for consistent consumers.
        export_status = "ready" if export_files else "empty"
        reason = "Audit exports available." if export_files else "No audit exports available."
        snapshot = {
            "status": export_status,
            "supported_formats": supported_formats,
            "export_count": len(export_files),
            "latest_export": latest_export,
            "reason": reason
        }
        return snapshot

    def _build_persistence_replay_snapshot(self, snapshot_index: Dict[str, Any]) -> Dict[str, Any]:
        status = snapshot_index.get("status", "missing")
        if status == "missing":
            return {
                "status": "missing",
                "reason": "Persistence directory not found for replay snapshots."
            }
        snapshots = snapshot_index.get("snapshots", [])
        if not snapshots:
            return {
                "status": "empty",
                "reason": "No persistence snapshots available for replay."
            }
        latest_snapshot = snapshots[-1]
        return {
            "status": "ready",
            "snapshot_count": snapshot_index.get("count", len(snapshots)),
            "latest_snapshot": latest_snapshot,
            "available_snapshots": snapshots
        }

    def _build_persistence_snapshot_index(self, persistence_dir: Path) -> Dict[str, Any]:
        if not persistence_dir.exists():
            return {
                "status": "missing",
                "count": 0,
                "snapshots": [],
                "reason": "Persistence directory not found."
            }
        snapshots = sorted(
            persistence_dir.glob(f"{self.PERSISTENCE_SNAPSHOT_PREFIX}_*.json"),
            key=lambda path: path.name
        )
        return {
            "status": "ready" if snapshots else "empty",
            "count": len(snapshots),
            "snapshots": [path.name for path in snapshots]
        }

    def _build_observability_snapshot(self) -> Dict[str, Any]:
        if not self.telemetry_bus or not self.telemetry_ingester:
            return {
                "status": "unavailable",
                "reason": "Telemetry bus not initialized."
            }
        return {
            "status": "available",
            "telemetry_bus": self.telemetry_bus.get_stats(),
            "ingestion": dict(self.telemetry_ingester.stats)
        }

    def _persist_execution_snapshot(
        self,
        doc: LivingDocument,
        activation_preview: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        persistence_dir = self._get_persistence_dir()
        if not persistence_dir:
            return {
                "status": "disabled",
                "reason": f"Set {self.PERSISTENCE_DIR_ENV} to enable persistence snapshots."
            }
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        snapshot_id = f"{self.PERSISTENCE_SNAPSHOT_PREFIX}_{doc.doc_id}_{timestamp}.json"
        snapshot_path = persistence_dir / snapshot_id
        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.utcnow().isoformat(),
            "document": doc.to_dict(),
            "activation_preview": activation_preview,
            "metadata": metadata
        }
        try:
            persistence_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(snapshot, indent=2))
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "stored", "path": str(snapshot_path), "snapshot_id": snapshot_id}

    def _build_mfgc_fallback_response(self, task_description: str, success: bool) -> Dict[str, Any]:
        return {
            "request_id": "mfgc_fallback",
            "success": success,
            "data": {
                "summary": "MFGC execution completed without integrator response.",
                "task": task_description
            },
            "message": "MFGC execution completed with a fallback response payload.",
            "warnings": ["Integrator response unavailable; using fallback payload."],
            "triggers": [],
            "timestamp": datetime.utcnow().isoformat()
        }

    def _get_compute_service(self) -> Optional[ComputeServiceType]:
        """Return a cached compute service instance, or None if unavailable."""
        with self._compute_service_lock:
            if self._compute_service is None:
                try:
                    from src.compute_plane.service import ComputeService
                except ImportError:
                    return None
                self._compute_service = ComputeService(enable_caching=True)
            return self._compute_service

    def _resolve_compute_session(self, session_id: Optional[str]) -> Optional[str]:
        """Resolve a valid session ID for compute-plane validation."""
        with self._session_lock:
            if session_id and session_id in self.sessions:
                return session_id
            if session_id:
                logger.warning(
                    "Unknown session_id '%s' supplied for compute-plane validation; creating new session.",
                    session_id
                )
            session_payload = self.create_session()
            if session_payload is None:
                logger.warning(
                    "Compute-plane validation session creation failed; results will not be linked to a session."
                )
                return None
            return session_payload.get("session_id")

    def _is_compute_expression_candidate(self, value: Optional[str]) -> bool:
        """Return True when text appears to contain a deterministic compute expression."""
        if not isinstance(value, str):
            return False
        normalized = value.strip()
        if not normalized:
            return False
        return bool(
            re.search(r"(minimize:|maximize:|subject to|[=+\-*/^()]|<=|>=)", normalized, re.IGNORECASE)
        )

    def _first_non_empty_value(
        self,
        parameters: Dict[str, Any],
        keys: List[str],
        fallback: Optional[str] = None
    ) -> Optional[str]:
        """Return first non-empty value from parameters for the provided keys."""
        for key in keys:
            value = parameters.get(key)
            if isinstance(value, str):
                if value.strip():
                    return value
                continue
            if value is not None:
                return value
        return fallback

    def _execute_compute_plane_validation(
        self,
        parameters: Optional[Dict[str, Any]],
        task_description: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Run deterministic compute-plane validation when compute inputs are provided.

        ComputeService.validate_expression returns either a ValidationResult object or a dict,
        so the payload is normalized to a dictionary for consistent downstream usage.
        """
        input_parameters = parameters or {}
        compute_request = input_parameters.get("compute_request")
        deterministic_request = input_parameters.get("deterministic_request")
        deterministic_expression = (
            deterministic_request.get("expression")
            if isinstance(deterministic_request, dict)
            else None
        )
        deterministic_required_expression = input_parameters.get("compute_expression")
        route_source = "compute_request"
        if isinstance(compute_request, dict):
            compute_expression = compute_request.get("expression")
            should_use_deterministic = (
                not self._is_compute_expression_candidate(compute_expression)
                and (
                    self._is_compute_expression_candidate(deterministic_expression)
                    or (
                        input_parameters.get("deterministic_required")
                        and self._is_compute_expression_candidate(deterministic_required_expression)
                    )
                )
            )
            if should_use_deterministic:
                compute_request = None
        if not compute_request and deterministic_request:
            compute_request = deterministic_request
            if compute_request:
                route_source = "deterministic_request"
        if (
            not compute_request
            and input_parameters.get("deterministic_required")
            and isinstance(input_parameters.get("compute_expression"), str)
            and input_parameters.get("compute_expression").strip()
        ):
            compute_request = {
                "expression": input_parameters.get("compute_expression").strip(),
                "language": input_parameters.get("compute_language", "sympy")
            }
            route_source = "deterministic_required"
        if (
            not compute_request
            and input_parameters.get("confidence_required")
            and (input_parameters.get("confidence_expression") or input_parameters.get("compute_expression"))
        ):
            compute_request = {
                "expression": input_parameters.get("confidence_expression") or input_parameters.get("compute_expression"),
                "language": input_parameters.get("confidence_language", input_parameters.get("compute_language", "sympy"))
            }
            route_source = "confidence_required"
        if (
            not compute_request
            and (task_type or "").lower() in self.CONFIDENCE_ENGINE_TASK_TYPES
        ):
            description_expression = (
                task_description
                if self._is_compute_expression_candidate(task_description)
                else None
            )
            confidence_expression = self._first_non_empty_value(
                input_parameters,
                ["confidence_expression", "compute_expression", "expression"],
                fallback=description_expression
            )
            if confidence_expression:
                compute_request = {
                    "expression": confidence_expression,
                    "language": input_parameters.get(
                        "confidence_language",
                        input_parameters.get("compute_language", "sympy")
                    )
                }
                route_source = "confidence_task_type"
        if (
            not compute_request
            and (
                input_parameters.get("math_required")
                or (task_type or "").lower() in {"math", "calculation", "numeric", "symbolic"}
            )
        ):
            description_expression = (
                task_description
                if self._is_compute_expression_candidate(task_description)
                else None
            )
            math_expression = self._first_non_empty_value(
                input_parameters,
                ["math_expression", "equation", "formula", "compute_expression", "expression"],
                fallback=description_expression
            )
            if math_expression:
                compute_request = {
                    "expression": math_expression,
                    "language": input_parameters.get("math_language", input_parameters.get("compute_language", "sympy"))
                }
                route_source = "math_deterministic"
        if not compute_request:
            return None
        expression = compute_request.get("expression")
        language = compute_request.get("language", "sympy")
        if not expression:
            return {
                "status": "error",
                "language": language,
                "route_source": route_source,
                "error": "Missing compute expression."
            }
        service = self._get_compute_service()
        if service is None:
            return {
                "status": "unavailable",
                "language": language,
                "route_source": route_source,
                "error": "Compute plane unavailable: service not initialized."
            }
        try:
            validation = service.validate_expression(expression, language)
            validation_payload = (
                validation.to_dict() if hasattr(validation, "to_dict") else validation
            )
            status = "validated" if validation_payload.get("is_valid") else "invalid"
            return {
                "status": status,
                "language": language,
                "route_source": route_source,
                "validation": validation_payload
            }
        except Exception as exc:
            return {
                "status": "error",
                "language": language,
                "route_source": route_source,
                "error": str(exc)
            }
    
    async def execute_task(
        self,
        task_description: str,
        task_type: str = "general",
        parameters: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> Dict:
        """
        Execute a task using Murphy System.
        
        This is the main entry point for task execution.
        Uses two-phase orchestrator for complete workflow.
        
        Args:
            task_description: Natural language task description
            task_type: Type of task (general, automation, integration, etc.)
            parameters: Additional parameters
            session_id: Optional session ID (creates new if not provided)
        
        Returns:
            Execution result dictionary. Falls back to simulation mode when the
            Two-Phase Orchestrator is unavailable.
        """
        
        logger.info(f"\n{'='*80}")
        logger.info(f"EXECUTING TASK: {task_description}")
        logger.info(f"{'='*80}\n")

        # Activation preview is returned for both orchestrator and fallback responses.
        doc, activation_preview = self._prepare_activation_preview(
            task_description,
            task_type,
            session_id,
            parameters
        )
        persistence_snapshot = self._persist_execution_snapshot(
            doc,
            activation_preview,
            {
                "task_description": task_description,
                "task_type": task_type,
                "session_id": session_id
            }
        )
        if isinstance(activation_preview.get("persistence"), dict):
            activation_preview["persistence"]["snapshot"] = persistence_snapshot
        execution_wiring = activation_preview.get("execution_wiring")
        execution_policy = self._build_execution_policy(
            activation_preview.get("dynamic_implementation"),
            parameters
        )
        if execution_policy["enforced"] and execution_policy["status"] != "ready":
            blocked_session = session_id or self.create_session().get("session_id")
            return {
                "success": False,
                "status": "blocked",
                "session_id": blocked_session,
                "doc_id": doc.doc_id,
                "activation_preview": activation_preview,
                "execution_wiring": execution_wiring,
                "execution_policy": execution_policy,
                "persistence_snapshot": persistence_snapshot,
                "error": execution_policy.get("reason") or "Execution policy blocked."
            }

        if self.librarian:
            self.librarian.log_transcript(
                module="runtime",
                action="execute_task",
                details={
                    "task_description": task_description,
                    "task_type": task_type,
                    "parameters": parameters or {}
                },
                actor="user",
                success=True
            )

        swarm_execution = None
        if (parameters or {}).get("run_swarm_execution"):
            swarm_execution = self._attempt_true_swarm(
                task_description,
                {
                    "task_type": task_type,
                    "session_id": session_id,
                    "doc_id": doc.doc_id
                }
            )
        compute_parameters = parameters or {}
        normalized_task_type = (task_type or "").lower()
        confidence_expression_candidate = self._first_non_empty_value(
            compute_parameters,
            ["confidence_expression", "compute_expression", "expression"],
            fallback=task_description
        )
        math_expression_candidate = self._first_non_empty_value(
            compute_parameters,
            ["math_expression", "equation", "formula", "compute_expression", "expression"],
            fallback=task_description
        )
        requires_compute_validation = bool(
            compute_parameters.get("compute_request")
            or compute_parameters.get("deterministic_request")
            or (
                compute_parameters.get("confidence_required")
                and (
                    compute_parameters.get("confidence_expression")
                    or compute_parameters.get("compute_expression")
                )
            )
            or (
                normalized_task_type in self.CONFIDENCE_ENGINE_TASK_TYPES
                and self._is_compute_expression_candidate(confidence_expression_candidate)
            )
            or (
                compute_parameters.get("math_required")
                and self._is_compute_expression_candidate(math_expression_candidate)
            )
            or (
                normalized_task_type in {"math", "calculation", "numeric", "symbolic"}
                and self._is_compute_expression_candidate(math_expression_candidate)
            )
            or (
                compute_parameters.get("deterministic_required")
                and isinstance(compute_parameters.get("compute_expression"), str)
                and compute_parameters.get("compute_expression").strip()
            )
        )
        resolved_compute_session = None
        if requires_compute_validation:
            resolved_compute_session = self._resolve_compute_session(session_id)
        compute_plane_result = self._execute_compute_plane_validation(
            parameters,
            task_description=task_description,
            task_type=task_type
        )
        if compute_plane_result:
            status = compute_plane_result.get("status", "error")
            if status == "validated" and resolved_compute_session:
                with self._session_lock:
                    previous_doc = self.document_sessions.get(resolved_compute_session)
                    if previous_doc == doc.doc_id:
                        logger.debug(
                            "Compute-plane session %s already mapped to document %s",
                            resolved_compute_session,
                            doc.doc_id
                        )
                    else:
                        self.document_sessions[resolved_compute_session] = doc.doc_id
                        if previous_doc:
                            logger.info(
                                "Updated compute-plane session mapping %s: %s -> %s",
                                resolved_compute_session,
                                previous_doc,
                                doc.doc_id
                            )
                        else:
                            logger.info(
                                "Mapped compute-plane session %s to document %s",
                                resolved_compute_session,
                                doc.doc_id
                            )
            return {
                "success": status == "validated",
                "status": status,
                "session_id": resolved_compute_session,
                "doc_id": doc.doc_id,
                "activation_preview": activation_preview,
                "execution_wiring": execution_wiring,
                "execution_policy": execution_policy,
                "persistence_snapshot": persistence_snapshot,
                "compute_plane": {
                    **compute_plane_result,
                    "execution_wiring": execution_wiring,
                    "wiring_enforced": execution_policy.get("enforced", True)
                },
                "swarm_execution": swarm_execution,
                "metadata": {
                    "task_description": task_description,
                    "task_type": task_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "mode": "compute_plane_validation"
                }
            }
        
        if not self._is_orchestrator_available():
            logger.warning("Two-Phase Orchestrator unavailable; using MFGC fallback or simulation mode.")
            fallback = self._simulate_execution(task_description, task_type, parameters, session_id)
            fallback["activation_preview"] = activation_preview
            fallback["doc_id"] = doc.doc_id
            fallback["execution_wiring"] = execution_wiring
            fallback["execution_policy"] = execution_policy
            fallback["persistence_snapshot"] = persistence_snapshot
            fallback["swarm_execution"] = swarm_execution
            return fallback

        if not self._supports_async_orchestrator():
            return self._execute_two_phase_orchestrator(
                task_description,
                task_type,
                parameters,
                session_id,
                doc,
                activation_preview,
                execution_wiring,
                execution_policy,
                persistence_snapshot,
                swarm_execution
            )

        try:
            # Phase 1: Generative Setup
            logger.info("Phase 1: Generative Setup...")
            
            setup_result = await self.orchestrator.phase1_generative_setup(
                request_description=task_description,
                request_type=task_type,
                parameters=parameters or {}
            )
            
            if not setup_result.get('success'):
                return {
                    'success': False,
                    'error': setup_result.get('error', 'Setup failed'),
                    'phase': 'setup'
                }
            
            session_id = setup_result['session_id']
            execution_packet = setup_result['execution_packet']
            
            logger.info(f"✓ Setup complete. Session: {session_id}")
            
            # Phase 2: Production Execution
            logger.info("\nPhase 2: Production Execution...")
            
            execution_result = await self.orchestrator.phase2_production_execution(
                session_id=session_id
            )
            
            if not execution_result.get('success'):
                return {
                    'success': False,
                    'error': execution_result.get('error', 'Execution failed'),
                    'phase': 'execution',
                    'session_id': session_id
                }
            
            logger.info(f"✓ Execution complete")
            
            deliverables = self._append_document_deliverable(
                execution_result.get('deliverables', []),
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_email_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_chat_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_voice_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_translation_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            # Return complete result
            return {
                'success': True,
                'session_id': session_id,
                'execution_packet': execution_packet,
                'result': execution_result.get('result'),
                'deliverables': deliverables,
                'doc_id': doc.doc_id,
                'activation_preview': activation_preview,
                'execution_wiring': execution_wiring,
                'execution_policy': execution_policy,
                'persistence_snapshot': persistence_snapshot,
                'swarm_execution': swarm_execution,
                'metadata': {
                    'task_description': task_description,
                    'task_type': task_type,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def _simulate_execution(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict],
        session_id: Optional[str]
    ) -> Dict:
        """Fallback execution when orchestrator is unavailable."""
        start = time.perf_counter()
        mfgc_payload = self._execute_with_mfgc_adapter(task_description, task_type, parameters)
        if mfgc_payload:
            execution_time = mfgc_payload.get("execution_time")
            duration = 0.0
            if execution_time is not None:
                try:
                    duration = float(execution_time)
                except (TypeError, ValueError):
                    duration = 0.0
            success = bool(mfgc_payload.get("success"))
            self._record_execution(success=success, duration=duration)
            response_payload = (
                mfgc_payload.get("integrator_response")
                or self._build_mfgc_fallback_response(task_description, success)
            )
            deliverables = self._append_document_deliverable(
                [],
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_email_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_chat_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_voice_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_translation_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            return {
                "success": success,
                "session_id": session_id or self.create_session().get("session_id"),
                "result": response_payload,
                "deliverables": deliverables,
                "mfgc_execution": mfgc_payload,
                "metadata": {
                    "task_description": task_description,
                    "task_type": task_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "mode": "mfgc_fallback"
                }
            }
        summary = {
            "summary": "Simulation mode: orchestrator unavailable",
            "task": task_description,
            "task_type": task_type,
            "parameters": parameters or {},
            "next_steps": [
                "Install full runtime dependencies",
                "Re-run with Two-Phase Orchestrator enabled",
                "Validate outputs before production use"
            ]
        }
        duration = time.perf_counter() - start
        self._record_execution(success=True, duration=duration)
        deliverables = self._append_document_deliverable(
            [],
            task_description,
            task_type,
            parameters
        )
        deliverables = self._append_email_deliverable(
            deliverables,
            task_description,
            task_type,
            parameters
        )
        deliverables = self._append_chat_deliverable(
            deliverables,
            task_description,
            task_type,
            parameters
        )
        deliverables = self._append_voice_deliverable(
            deliverables,
            task_description,
            task_type,
            parameters
        )
        deliverables = self._append_translation_deliverable(
            deliverables,
            task_description,
            task_type,
            parameters
        )
        return {
            "success": True,
            "session_id": session_id or self.create_session().get("session_id"),
            "result": summary,
            "deliverables": deliverables,
            "metadata": {
                "task_description": task_description,
                "task_type": task_type,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": "simulation"
            }
        }

    def _get_orchestrator(self) -> Optional[Any]:
        return self.orchestrator

    def _supports_async_orchestrator(self) -> bool:
        orchestrator = self._get_orchestrator()
        return (
            orchestrator is not None
            and hasattr(orchestrator, "phase1_generative_setup")
            and hasattr(orchestrator, "phase2_production_execution")
        )

    def _supports_two_phase_orchestrator(self) -> bool:
        orchestrator = self._get_orchestrator()
        return (
            orchestrator is not None
            and hasattr(orchestrator, "create_automation")
            and hasattr(orchestrator, "run_automation")
        )

    def _resolve_orchestrator_session_id(self, session_id: Optional[str]) -> Optional[str]:
        if session_id:
            return session_id
        payload = self.create_session()
        if not payload or not payload.get("session_id"):
            logger.warning(
                "Two-Phase Orchestrator session creation failed; will fall back to automation_id for session tracking."
            )
            return None
        return payload["session_id"]

    def _is_orchestrator_available(self) -> bool:
        return self._supports_async_orchestrator() or self._supports_two_phase_orchestrator()

    def _execute_two_phase_orchestrator(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]],
        session_id: Optional[str],
        doc: LivingDocument,
        activation_preview: Dict[str, Any],
        execution_wiring: Optional[Dict[str, Any]],
        execution_policy: Dict[str, Any],
        persistence_snapshot: Optional[Dict[str, Any]],
        swarm_execution: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute the legacy two-phase orchestrator path (create + run automation)."""
        # If the domain is not provided, default to task_type to preserve compatibility with
        # legacy TwoPhaseOrchestrator create_automation(request, domain) call sites. Empty string
        # is treated as an explicit domain for legacy edge cases.
        requested_domain = None
        if parameters is not None and "domain" in parameters:
            requested_domain = parameters.get("domain")
        orchestration_domain = task_type if requested_domain is None else requested_domain
        try:
            orchestrator = self._get_orchestrator()
            if orchestrator is None:
                raise RuntimeError("Orchestrator unavailable for two-phase execution.")
            automation_id = orchestrator.create_automation(task_description, orchestration_domain)
            run_result = orchestrator.run_automation(automation_id)
            response_session = self._resolve_orchestrator_session_id(session_id)
            if response_session is None:
                response_session = automation_id
                session_id_source = "automation_id_fallback"
            else:
                session_id_source = "session_id"
            deliverables = self._append_document_deliverable(
                run_result.get("deliverables", []),
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_email_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_chat_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_voice_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            deliverables = self._append_translation_deliverable(
                deliverables,
                task_description,
                task_type,
                parameters
            )
            return {
                "success": True,
                "automation_id": automation_id,
                "session_id": response_session,
                "session_id_source": session_id_source,
                "result": run_result,
                "deliverables": deliverables,
                "doc_id": doc.doc_id,
                "activation_preview": activation_preview,
                "execution_wiring": execution_wiring,
                "execution_policy": execution_policy,
                "persistence_snapshot": persistence_snapshot,
                "swarm_execution": swarm_execution,
                "metadata": {
                    "task_description": task_description,
                    "task_type": task_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "mode": "two_phase_orchestrator"
                }
            }
        except Exception as exc:
            logger.error("Two-Phase Orchestrator execution failed: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "phase": "orchestrator",
                "activation_preview": activation_preview,
                "execution_wiring": execution_wiring,
                "execution_policy": execution_policy,
                "persistence_snapshot": persistence_snapshot,
                "swarm_execution": swarm_execution
            }

    def _execute_with_mfgc_adapter(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not self.mfgc_adapter:
            return None
        try:
            config = self._create_mfgc_config(enabled_override=True)
            if config:
                self.mfgc_adapter.update_config(config)
            phase_verbosity = config.phase_verbosity if config else self.DEFAULT_PHASE_VERBOSITY
            result = self.mfgc_adapter.execute_with_mfgc(
                user_input=task_description,
                request_type=task_type,
                parameters=parameters
            )
            self.mfgc_statistics = self.mfgc_adapter.get_statistics()
            return result.to_dict(phase_verbosity=phase_verbosity)
        except Exception as exc:
            logger.warning("MFGC adapter execution failed: %s", exc)
            return None

    @staticmethod
    def _component_status(component_instance: Optional[Any]) -> str:
        return "active" if component_instance else "inactive"

    def _create_document(self, title: str, content: str, doc_type: str, session_id: Optional[str] = None) -> LivingDocument:
        doc = LivingDocument(uuid4().hex, title, content, doc_type)
        doc.gate_policy = deepcopy(self.default_gate_policy)
        self.living_documents[doc.doc_id] = doc
        if session_id:
            self.document_sessions[session_id] = doc.doc_id
        self._update_document_tree(doc)
        return doc

    def _ensure_document(self, task_description: str, task_type: str, session_id: Optional[str]) -> LivingDocument:
        if session_id:
            doc_id = self.document_sessions.get(session_id)
            if doc_id:
                existing = self.living_documents.get(doc_id)
                if existing:
                    return existing
        title = " ".join(task_description.split()[:6]) or "Untitled Task"
        return self._create_document(title=title, content=task_description, doc_type=task_type, session_id=session_id)

    def _generate_swarm_tasks(self) -> List[Dict[str, Any]]:
        """
        Generate default swarm tasks from onboarding flow steps.

        Returns a list of dicts with keys: task_id, stage, description.
        """
        tasks = []
        for step in self.flow_steps:
            tasks.append({
                "task_id": uuid4().hex,
                "stage": step["stage"],
                "description": step["prompt"]
            })
        return tasks

    def _build_gate_chain(self, doc: LivingDocument) -> List[Dict[str, Any]]:
        gate_templates = doc.gate_policy or deepcopy(self.default_gate_policy)
        gates = []
        blocked_by = None
        for entry in gate_templates:
            name = entry.get("name", "Gate")
            threshold = entry.get("threshold", 0.5)
            validated_override = self._normalize_gate_override(entry.get("status_override"), name)
            # Manual overrides take precedence over confidence-based gating.
            status = validated_override or ("open" if doc.confidence >= threshold else "blocked")
            blocked_by_previous = blocked_by is not None
            if blocked_by_previous:
                status = "blocked"
            elif status == "blocked":
                blocked_by = name
            reason = self._determine_gate_reason(
                status,
                validated_override,
                blocked_by if blocked_by_previous else None
            )
            gates.append({
                "name": name,
                "threshold": threshold,
                "status": status,
                "reason": reason,
                "stage": entry.get("stage"),
                "blocked_by": blocked_by if status == "blocked" else None
            })
        return gates

    @staticmethod
    def _determine_gate_reason(
        status: Literal["open", "blocked"],
        override: Optional[str],
        blocked_by: Optional[str]
    ) -> Optional[str]:
        if blocked_by and status == "blocked":
            return f"Blocked by {blocked_by}"
        if status == "blocked":
            return "Manually blocked" if override == "blocked" else "Confidence below threshold"
        if status == "open":
            return "Manual override" if override == "open" else "Confidence meets threshold"
        return None

    def _build_block_tree(self, doc: LivingDocument) -> Dict[str, Any]:
        root = {
            "id": doc.doc_id,
            "label": doc.title,
            "state": doc.state,
            "confidence": doc.confidence,
            "constraints": doc.constraints,
            "gates": doc.gates,
            "children": []
        }

        history_actions = {entry["action"] for entry in doc.history}
        for action in ("magnify", "simplify", "solidify"):
            matching = [entry for entry in doc.history if entry["action"] == action]
            if matching:
                for entry in matching:
                    label = entry["action"].title()
                    if entry.get("domain"):
                        label = f"{label} ({entry['domain']})"
                    root["children"].append({
                        "id": uuid4().hex,
                        "label": label,
                        "action": entry["action"],
                        "status": "completed",
                        "timestamp": entry.get("timestamp")
                    })
            else:
                root["children"].append({
                    "id": uuid4().hex,
                    "label": action.title(),
                    "action": action,
                    "status": "pending"
                })

        if doc.generated_tasks:
            task_node = {
                "id": uuid4().hex,
                "label": "Generated Swarm Tasks",
                "action": "expand",
                "status": "ready",
                "children": []
            }
            for task in doc.generated_tasks:
                task_node["children"].append({
                    "id": task["task_id"],
                    "label": task["stage"].replace("_", " ").title(),
                    "action": "task",
                    "status": "pending",
                    "description": task["description"]
                })
            root["children"].append(task_node)

        return root

    def _update_document_tree(self, doc: LivingDocument) -> None:
        doc.constraints = []
        if doc.confidence < 0.6:
            doc.constraints.append("Low confidence: run magnify or simplify before solidify.")
        doc.gates = self._build_gate_chain(doc)
        if doc.state == "SOLIDIFIED":
            doc.generated_tasks = self._generate_swarm_tasks()
            doc.children = doc.generated_tasks
        doc.block_tree = self._build_block_tree(doc)

    @staticmethod
    def _result_status(record: Dict[str, Any]) -> str:
        result = record.get("result", {})
        results = result.get("results", []) if isinstance(result, dict) else []
        if results:
            return results[0].get("status", "unknown")
        return "unknown"

    def _summarize_business_automation(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        if not summary:
            return {}
        marketing = summary.get("marketing", {})
        business = summary.get("business", {})
        production = summary.get("production", {})
        return {
            "marketing": {
                "content_generated": bool(marketing.get("content", {}).get("content_generated")),
                "social_platforms": marketing.get("social", {}).get("platforms", []),
                "seo_keywords": marketing.get("seo", {}).get("keywords_researched", 0),
                "analytics_status": self._result_status(marketing.get("analytics", {}))
            },
            "operations_director": {
                "finance_status": self._result_status(business.get("finance", {})),
                "support_status": self._result_status(business.get("support", {})),
                "projects_status": self._result_status(business.get("projects", {})),
                "documentation_status": self._result_status(business.get("documentation", {}))
            },
            "qa": {
                "qa_passed": production.get("qa", {}).get("qa_passed"),
                "monitoring_uptime": production.get("monitoring", {}).get("uptime")
            }
        }

    def _build_executive_branch_plan(self, doc: LivingDocument) -> Dict[str, Any]:
        approvals = []
        for gate in doc.gates:
            name = gate.get("name", "")
            if any(keyword in name for keyword in ["Executive", "Operations Director", "Marketing Strategy", "QA", "HITL", "Execution"]):
                approvals.append({
                    "gate": name,
                    "status": gate.get("status"),
                    "threshold": gate.get("threshold"),
                    "stage": gate.get("stage"),
                    "blocked_by": gate.get("blocked_by")
                })
        return {
            "approvals": approvals,
            "decision_sequence": [approval["gate"] for approval in approvals]
        }

    def _build_executive_directive(
        self,
        task_description: str,
        operations_plan: List[Dict[str, Any]],
        delivery_readiness: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Summarize executive priorities.

        Args:
            task_description: The originating request summary.
            operations_plan: Planned operational tasks with assigned owners.
            delivery_readiness: Delivery readiness snapshot used for executive status.

        Returns:
            Dict with directive_summary, priority_actions, and delivery_readiness fields.
        """
        priority_actions = [
            task.get("description")
            for task in operations_plan
            if task.get("owner") == "executive_branch" and task.get("description")
        ]
        if not priority_actions:
            priority_actions = [
                task.get("description")
                for task in operations_plan
                if task.get("description")
            ][:3]
        return {
            "directive_summary": self._truncate_description(task_description),
            "priority_actions": priority_actions[:3],
            "delivery_readiness": delivery_readiness.get("status", "unknown")
        }

    def _build_operations_plan(self, doc: LivingDocument) -> List[Dict[str, Any]]:
        operations = []
        for task in doc.generated_tasks:
            stage = task.get("stage")
            owner = self.GOVERNANCE_OWNER_OPERATIONS
            if stage in {"automation_design", "billing"}:
                owner = self.GOVERNANCE_OWNER_EXECUTIVE
            elif stage == "automation_production":
                owner = self.GOVERNANCE_OWNER_QA
            operations.append({
                "stage": stage,
                "owner": owner,
                "description": task.get("description"),
                "status": task.get("status", "pending")
            })
        return operations

    @staticmethod
    def _build_workload_distribution(operations_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate task distribution across owners.

        Args:
            operations_plan: List of task dicts with owner assignments.

        Returns:
            Dict with total_tasks, by_owner counts, and share (ratio per owner).
        """
        totals: Dict[str, int] = {}
        for task in operations_plan:
            owner = task.get("owner", "unassigned")
            totals[owner] = totals.get(owner, 0) + 1
        total_tasks = len(operations_plan)
        share = {
            owner: round(count / total_tasks, 2) if total_tasks else 0.0
            for owner, count in totals.items()
        }
        return {
            "total_tasks": total_tasks,
            "by_owner": totals,
            "share": share
        }

    def _build_hitl_contract_plan(self, doc: LivingDocument) -> List[Dict[str, Any]]:
        contracts = []
        for gate in doc.gates:
            if "HITL" in gate.get("name", "") or "Contract" in gate.get("name", ""):
                contracts.append({
                    "gate": gate.get("name"),
                    "status": gate.get("status"),
                    "required_action": "Human approval required before execution.",
                    "blocked_by": gate.get("blocked_by")
                })
        return contracts

    def _build_delivery_readiness(
        self,
        doc: LivingDocument,
        org_chart_plan: Dict[str, Any],
        learning_loop: Dict[str, Any],
        sensor_plan: Dict[str, Any],
        hitl_contracts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess readiness for human review using coverage, compliance, and HITL status."""
        coverage_summary = org_chart_plan.get("coverage_summary", {})
        total_deliverables = coverage_summary.get("total_deliverables", 0)
        uncovered = coverage_summary.get("uncovered_deliverables", 0)
        coverage_ratio = (total_deliverables - uncovered) / total_deliverables if total_deliverables else 0.0
        coverage_percent = round(coverage_ratio * 100, 1)
        requirements_profile = learning_loop.get("requirements_identification", {})
        requirements_status = requirements_profile.get("status", "needs_info")
        hitl_contract_list = hitl_contracts or []
        # Minimum confidence required before HITL approval can release execution.
        # Defined as a class-level constant on this runtime.
        confidence_threshold = type(self).HIGH_CONFIDENCE_THRESHOLD
        logger = logging.getLogger(__name__)
        confidence_value_raw = getattr(doc, "confidence", None)
        confidence_value = None
        if confidence_value_raw is not None:
            try:
                confidence_value = float(confidence_value_raw)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid confidence value '%s' (expected float), defaulting to None.",
                    confidence_value_raw
                )
        hitl_required = bool(hitl_contract_list)
        if confidence_value is None or confidence_value < confidence_threshold:
            approval_status = "needs_info"
        elif hitl_required:
            # HITL approval is still required even when confidence meets the threshold.
            approval_status = "pending_approval"
        else:
            approval_status = "ready"
        precision = type(self).CONFIDENCE_DISPLAY_PRECISION
        confidence_display = None if confidence_value is None else round(confidence_value, precision)
        approval_policy = {
            "confidence": confidence_display,
            "threshold": confidence_threshold,
            "hitl_required": hitl_required,
            "status": approval_status
        }
        gate_states = [
            (gate.get("status") or gate.get("state") or "").lower()
            for gate in doc.gates
        ]
        blocked = any(state in self.COMPLIANCE_BLOCKED_STATES for state in gate_states)
        pending = any(state in self.COMPLIANCE_PENDING_STATES for state in gate_states)
        if blocked:
            compliance_status = "blocked"
        elif pending:
            compliance_status = "pending"
        else:
            compliance_status = "clear"
        meets_requirement_target = coverage_ratio >= self.REQUIREMENT_COVERAGE_TARGET
        hitl_required = bool(hitl_contracts)
        if requirements_status != "complete":
            status = "needs_info"
            gap_action = "Collect missing onboarding answers before delivery."
        elif compliance_status != "clear":
            status = "needs_compliance"
            gap_action = "Resolve compliance gates before human review."
        elif not meets_requirement_target:
            status = "needs_coverage"
            gap_action = "Expand deliverables or org chart coverage to reach target."
        else:
            status = "ready"
            gap_action = "Ready for human review once HITL approvals are satisfied."
        delivery_adapters = self._build_delivery_adapter_snapshot()
        connector_orchestration = self._build_connector_orchestration_snapshot(delivery_adapters)
        adapter_summary = delivery_adapters.get("summary", {})
        if status == "ready" and adapter_summary.get("configured", 0) < adapter_summary.get("total", 0):
            status = "needs_wiring"
            gap_action = "Configure delivery adapters for document/email/chat/voice outputs."
        connector_summary = connector_orchestration.get("summary", {})
        if status == "ready" and connector_summary.get("configured", 0) < connector_summary.get("total", 0):
            status = "needs_wiring"
            gap_action = connector_orchestration.get("gap_action", gap_action)
        return {
            "status": status,
            "requirements_status": requirements_status,
            "coverage_percent": coverage_percent,
            "requirements_target_percent": int(self.REQUIREMENT_COVERAGE_TARGET * 100),
            "meets_requirement_target": meets_requirement_target,
            "compliance_status": compliance_status,
            "hitl_required": hitl_required,
            "regulatory_source": sensor_plan.get("primary_regulatory_source", {}).get("id"),
            "approval_policy": approval_policy,
            "gap_action": gap_action,
            "delivery_adapters": delivery_adapters,
            "connector_orchestration": connector_orchestration
        }

    def _build_compliance_validation_snapshot(
        self,
        delivery_readiness: Optional[Dict[str, Any]],
        sensor_plan: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize compliance validation readiness from delivery readiness and sensor inputs."""
        readiness = delivery_readiness or {}
        compliance_status = readiness.get("compliance_status", "needs_info")
        regulatory_source = readiness.get("regulatory_source")
        if not regulatory_source and sensor_plan:
            regulatory_source = (sensor_plan.get("primary_regulatory_source") or {}).get("id")
        regulatory_sources = (sensor_plan or {}).get("regulatory_sources", [])
        if compliance_status == "clear":
            status = "ready"
            next_action = "Compliance gates clear; proceed with delivery approvals."
        elif (
            compliance_status in self.COMPLIANCE_BLOCKED_STATES
            or compliance_status in self.COMPLIANCE_PENDING_STATES
        ):
            status = "needs_compliance"
            next_action = "Resolve compliance gates before delivery release."
        else:
            status = "needs_info"
            next_action = "Attach compliance evidence and regulatory sources."
        return {
            "status": status,
            "compliance_status": compliance_status,
            "regulatory_source": regulatory_source,
            "regulatory_sources": regulatory_sources,
            "next_action": next_action
        }

    def _extract_deliverables(
        self,
        doc: LivingDocument,
        tasks_source: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """Extract deliverable text from tasks or fallback flow steps."""
        tasks = tasks_source or doc.generated_tasks or self._generate_swarm_tasks()
        if not isinstance(tasks, list):
            return []
        deliverables: List[str] = []
        seen = set()
        for task in tasks:
            for key in self.DELIVERABLE_EXTRACTION_KEYS:
                value = task.get(key)
                if value:
                    text = str(value)
                    if text not in seen:
                        seen.add(text)
                        deliverables.append(text)
                    break
        return deliverables

    def _map_deliverables_to_positions(
        self,
        deliverables: List[str],
        positions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        normalized_positions = []
        for position in positions:
            keywords = [
                position.get("title", ""),
                position.get("department", ""),
                position.get("level", "")
            ]
            keywords.extend(position.get("knowledge_domains", []))
            keywords.extend(position.get("skills", []))
            keywords.extend(position.get("typical_tasks", []))
            normalized_positions.append({
                "title": position.get("title"),
                "keywords": {keyword.lower() for keyword in keywords if keyword}
            })
        coverage = []
        for deliverable in deliverables:
            deliverable_lower = deliverable.lower()
            matched_positions = [
                position["title"]
                for position in normalized_positions
                if any(keyword in deliverable_lower for keyword in position["keywords"])
            ]
            mapping_method = "keyword"
            if not matched_positions and positions:
                fallback_source = sorted(
                    positions,
                    key=lambda item: (-len(item.get("skills", [])), item.get("title", ""))
                )
                fallback_positions = [
                    position.get("title")
                    for position in fallback_source[:self.ORG_CHART_FALLBACK_POSITIONS]
                ]
                mapping_method = "fallback"
                matched_positions = fallback_positions
                logger.warning(
                    "Org chart fallback applied for deliverable '%s' (positions=%d, fallback=%d)",
                    deliverable,
                    len(positions),
                    len(fallback_positions)
                )
            coverage.append({
                "deliverable": deliverable,
                "positions": matched_positions,
                "status": "covered" if matched_positions else "unassigned",
                "mapping_method": mapping_method
            })
        return coverage

    def _build_position_contracts(
        self,
        coverage: List[Dict[str, Any]],
        total_deliverables: int
    ) -> List[Dict[str, Any]]:
        """Build contract coverage for positions.

        Coverage status:
        - full: only one position covers all deliverables
        - overlap_full: multiple positions each cover all deliverables
        - partial: position covers a subset of deliverables
        """
        contract_map: Dict[str, List[str]] = {}
        for item in coverage:
            for position in item.get("positions", []):
                if not position:
                    continue
                contract_map.setdefault(position, []).append(item["deliverable"])
        contracts = []
        full_coverage_positions = sum(
            1
            for obligations in contract_map.values()
            if total_deliverables and len(obligations) == total_deliverables
        )
        for position, obligations in contract_map.items():
            if total_deliverables and len(obligations) == total_deliverables:
                coverage_status = "full" if full_coverage_positions == 1 else "overlap_full"
            else:
                coverage_status = "partial"
            coverage_ratio = len(obligations) / total_deliverables if total_deliverables else 0.0
            contracts.append({
                "position": position,
                "obligations": obligations,
                "coverage": coverage_status,
                "coverage_ratio": round(coverage_ratio, 2)
            })
        return contracts

    def _build_org_chart_plan(
        self,
        task_description: str,
        deliverables: List[str]
    ) -> Dict[str, Any]:
        if not self.org_chart_system:
            return {"status": "unavailable", "reason": "Organization chart system not initialized"}
        context = self.org_chart_system.get_knowledge_context_for_project(task_description)
        positions = context.get("required_positions", [])
        deliverable_coverage = self._map_deliverables_to_positions(deliverables, positions)
        position_contracts = self._build_position_contracts(deliverable_coverage, len(deliverables))
        uncovered = [item for item in deliverable_coverage if item["status"] != "covered"]
        return {
            "status": "ready",
            "required_positions": positions,
            "deliverables": deliverables,
            "deliverable_coverage": deliverable_coverage,
            "position_contracts": position_contracts,
            "coverage_summary": {
                "total_deliverables": len(deliverables),
                "uncovered_deliverables": len(uncovered),
                "positions_required": len(positions)
            }
        }

    def _build_librarian_context(
        self,
        doc: LivingDocument,
        task_description: str,
        planned_subsystems: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not self.librarian:
            return {"status": "unavailable", "reason": "System librarian not initialized"}
        # Filter to 4+ character tokens to reduce noise in librarian matching.
        tokens = set(re.findall(r"[a-z]{4,}", task_description.lower()))
        subsystem_ids = {item.get("id") for item in planned_subsystems}
        matches = []
        for knowledge in self.librarian.knowledge_base.values():
            haystack = f"{knowledge.topic} {knowledge.description} {knowledge.category}".lower()
            if tokens and any(token in haystack for token in tokens):
                matches.append(knowledge)
                continue
            if subsystem_ids and any(module in subsystem_ids for module in knowledge.related_modules):
                matches.append(knowledge)
        unique = []
        seen = set()
        for knowledge in matches:
            if knowledge.knowledge_id in seen:
                continue
            seen.add(knowledge.knowledge_id)
            unique.append(knowledge)
        selected = unique[:3]
        conditions = []
        for knowledge in selected:
            conditions.append({
                "id": knowledge.knowledge_id,
                "topic": knowledge.topic,
                "condition": f"Apply librarian guidance for {knowledge.topic}.",
                "requires_approval": True,
                "status": "proposed"
            })
        doc.librarian_conditions = conditions
        return {
            "status": "ready",
            "matched_topics": [knowledge.topic for knowledge in selected],
            "recommended_conditions": conditions,
            "knowledge_sources": [knowledge.to_dict() for knowledge in selected],
            "approval_required": bool(conditions)
        }

    def _build_requirements_profile(
        self,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        context = onboarding_context or {}
        answers = context.get("answers", {})
        identified = []
        missing = []
        for step in self.flow_steps:
            stage = step.get("stage")
            if not stage:
                continue
            response = answers.get(stage)
            if response:
                identified.append({"stage": stage, "response": response})
            else:
                missing.append({"stage": stage, "prompt": step.get("prompt")})
        status = "complete" if not missing else "needs_info"
        return {
            "status": status,
            "request_goal": self._truncate_description(task_description),
            "identified": identified,
            "missing": missing,
            "identified_count": len(identified),
            "missing_count": len(missing)
        }

    def _build_learning_loop_plan(
        self,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]],
        librarian_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        requirements_profile = self._build_requirements_profile(task_description, onboarding_context)
        requirements_complete = requirements_profile["status"] == "complete"
        swarm_ready = bool(self.swarm_system)
        # Loop readiness requires complete requirements and an initialized swarm instance.
        loop_ready = requirements_complete and swarm_ready
        iteration_status = "queued" if loop_ready else "pending_setup"
        iterations = [
            {
                "iteration": idx,
                "variant": variant["id"],
                "focus": variant["focus"],
                "status": iteration_status
            }
            for idx, variant in enumerate(self.LEARNING_LOOP_VARIANTS, start=1)
        ]
        if not requirements_complete:
            status = "needs_info"
            gap_action = "Provide missing onboarding answers to finalize requirements."
        elif not swarm_ready:
            status = "needs_wiring"
            gap_action = "Initialize swarm system and persistence to run iterative learning loops."
        else:
            status = "ready"
            gap_action = "Learning loop ready; execute multi-project iterations."
        return {
            "status": status,
            "requirements_identification": requirements_profile,
            "output_targets": self.OUTPUT_CHANNEL_TARGETS,
            "iterations": iterations,
            "librarian_conditions": librarian_context.get("recommended_conditions", []),
            "guideline_profile": {
                "confidence_mode": self.mfgc_config.get("confidence_mode"),
                "authority_mode": self.mfgc_config.get("authority_mode"),
                "gate_synthesis": self.mfgc_config.get("gate_synthesis"),
            "audit_trail": self.mfgc_config.get("audit_trail")
        },
        "gap_action": gap_action
    }

    def _build_dynamic_implementation_plan(
        self,
        doc: LivingDocument,
        task_description: str,
        planned_subsystems: List[Dict[str, Any]],
        learning_loop: Dict[str, Any],
        operations_plan: List[Dict[str, Any]],
        delivery_readiness: Dict[str, Any],
        hitl_contracts: List[Dict[str, Any]],
        sensor_plan: Dict[str, Any],
        org_chart_plan: Dict[str, Any],
        trigger_plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        requirements_profile = learning_loop.get("requirements_identification", {})
        requirements_status = requirements_profile.get("status", "needs_info")
        approval_policy = delivery_readiness.get("approval_policy", {})
        approval_status = approval_policy.get("status", "needs_info")
        gate_states = [
            (gate.get("status") or gate.get("state") or "").lower()
            for gate in doc.gates
        ]
        has_gates = bool(doc.gates)
        blocked = any(state in self.COMPLIANCE_BLOCKED_STATES for state in gate_states)
        pending = any(state in self.COMPLIANCE_PENDING_STATES for state in gate_states)
        if blocked:
            gate_status = "blocked"
        elif pending:
            gate_status = "pending"
        elif not has_gates:
            gate_status = "needs_info"
        else:
            gate_status = "ready"
        if self._is_orchestrator_available():
            execution_strategy = "orchestrator"
        elif self.mfgc_adapter:
            execution_strategy = "mfgc_fallback"
        else:
            execution_strategy = "simulation"
        requirements_stage_status = "complete" if requirements_status == "complete" else "needs_info"
        workload_status = "ready" if operations_plan else "pending"
        integration_status = (
            "ready"
            if self.system_integrator or self.integration_engine
            else "needs_wiring"
        )
        automation_loop_status = self._determine_automation_loop_status(
            requirements_stage_status,
            execution_strategy,
            learning_loop
        )
        iterations = learning_loop.get("iterations", [])
        if not has_gates:
            gate_sequence_status = "needs_info"
        elif gate_status == "blocked":
            gate_sequence_status = "blocked"
        elif gate_status == "pending":
            gate_sequence_status = "pending"
        else:
            gate_sequence_status = "ready"
        trigger_plan_status = trigger_plan.get("status") if trigger_plan else None
        if trigger_plan_status == "scheduled":
            trigger_status = "ready"
        elif trigger_plan_status in {"unavailable", "disabled"}:
            trigger_status = "needs_wiring"
        else:
            trigger_status = "pending"
        monitoring_status = (
            "ready"
            if sensor_plan.get("primary_sensor") or sensor_plan.get("primary_regulatory_source")
            else "needs_info"
        )
        if gate_status in {"blocked", "pending"}:
            compliance_review_status = gate_status
        elif monitoring_status == "needs_info":
            compliance_review_status = "needs_info"
        else:
            compliance_review_status = "ready"
        if execution_strategy == "simulation":
            execution_status = "needs_wiring"
        elif requirements_stage_status != "complete" or gate_status != "ready":
            execution_status = "blocked"
        else:
            execution_status = "ready"
        swarm_tasks = doc.generated_tasks or self._generate_swarm_tasks()
        if not self.swarm_system:
            swarm_status = "needs_wiring"
        elif swarm_tasks:
            swarm_status = "ready"
        else:
            swarm_status = "needs_info"
        deliverable_status = delivery_readiness.get("status", "unknown")
        human_release_status = (
            "pending_approval"
            if hitl_contracts
            else ("ready" if deliverable_status == "ready" else "blocked")
        )
        output_status = self._determine_output_status(requirements_stage_status, deliverable_status)
        rollback_status = self._determine_rollback_status(execution_strategy, deliverable_status)
        if automation_loop_status == "needs_wiring":
            multi_loop_status = "needs_wiring"
        elif requirements_stage_status != "complete":
            multi_loop_status = "needs_info"
        elif automation_loop_status != "ready":
            multi_loop_status = automation_loop_status
        elif len(iterations) <= 1:
            multi_loop_status = "pending"
        else:
            multi_loop_status = "ready"
        stage_statuses = {
            "requirements_identification": requirements_stage_status,
            "confidence_approval": approval_status,
            "gate_alignment": gate_status,
            "gate_sequencing": gate_sequence_status,
            "compliance_review": compliance_review_status,
            "workload_distribution": workload_status,
            "execution_plan": execution_status,
            "swarm_generation": swarm_status,
            "integration_wiring": integration_status,
            "automation_loop": automation_loop_status,
            "multi_loop_schedule": multi_loop_status,
            "trigger_schedule": trigger_status,
            "monitoring_feedback": monitoring_status,
            "output_delivery": output_status,
            "deliverable_review": deliverable_status,
            "rollback_plan": rollback_status,
            "human_release": human_release_status
        }
        stages = [
            {
                "id": stage["id"],
                "label": stage["label"],
                "owner": stage["owner"],
                "status": stage_statuses.get(stage["id"], "pending"),
                "loop": stage.get("loop", False)
            }
            for stage in self.DYNAMIC_IMPLEMENTATION_STAGES
        ]
        # Wiring gaps indicate missing infrastructure/connection wiring. Info gaps indicate
        # missing configuration or input data once the infrastructure exists.
        wiring_gaps = []
        information_gaps = []
        for stage in self.DYNAMIC_IMPLEMENTATION_STAGES:
            stage_id = stage["id"]
            status = stage_statuses.get(stage_id, "pending")
            if status == "needs_wiring":
                wiring_gaps.append({
                    "id": stage_id,
                    "label": stage["label"],
                    "owner": stage["owner"],
                    "reason": stage.get(
                        "wiring_reason",
                        "Missing wiring guidance; update stage definition."
                    )
                })
            elif status == "needs_info":
                information_gaps.append({
                    "id": stage_id,
                    "label": stage["label"],
                    "owner": stage["owner"],
                    "reason": stage.get(
                        "info_reason",
                        "Missing information guidance; update stage definition."
                    )
                })
        chain_plan = self._build_dynamic_chain_plan(stage_statuses)
        loop_chain = [
            {"id": stage["id"], "status": stage["status"]}
            for stage in stages
            if stage.get("loop")
        ]
        next_actions = []
        if requirements_status != "complete":
            next_actions.append("Collect missing onboarding answers to lock requirements.")
        if approval_status == "needs_info":
            next_actions.append("Increase confidence with supporting evidence and validation.")
        elif approval_status == "pending_approval":
            next_actions.append("Collect HITL approval before execution.")
        # When ready, no additional approval action is required.
        if gate_status in {"blocked", "pending"}:
            next_actions.append("Review and update gate policy to clear compliance.")
        if gate_sequence_status == "needs_info":
            next_actions.append("Define the gate chain sequence and dependencies.")
        if compliance_review_status != "ready":
            next_actions.append("Complete compliance review and attach regulatory evidence.")
        if execution_strategy == "simulation":
            next_actions.append("Wire the Two-Phase Orchestrator or MFGC adapter for live execution.")
        if swarm_status != "ready":
            next_actions.append("Initialize swarm system and seed swarm tasks.")
        if integration_status != "ready":
            next_actions.append("Wire integration engine connectors for external system handoff.")
        if automation_loop_status != "ready":
            next_actions.append("Configure multi-project automation loop iterations.")
        if multi_loop_status != "ready":
            next_actions.append("Define multi-loop scheduling and cross-project feedback cadence.")
        if trigger_status != "ready":
            next_actions.append("Schedule governance timers/triggers for automated delivery.")
        if monitoring_status != "ready":
            next_actions.append("Attach monitoring sensors for feedback and compliance signals.")
        if output_status != "ready":
            next_actions.append("Confirm output channel mapping and delivery templates.")
        if deliverable_status != "ready":
            next_actions.append(delivery_readiness.get("gap_action", "Resolve delivery readiness gaps."))
        if rollback_status != "ready":
            next_actions.append("Define rollback/recovery plan and release checkpoints.")
        if hitl_contracts:
            next_actions.append("Collect HITL approvals for contract gates.")
        unique_actions = list(dict.fromkeys(next_actions))
        llm_readiness = self._check_llm_readiness()
        deterministic_planned = any(item.get("id") == "compute_plane" for item in planned_subsystems)
        processing_balance = {
            "deterministic": "planned" if deterministic_planned else "not_requested",
            "llm": llm_readiness.get("status", "not_configured"),
            "summary": "balanced" if deterministic_planned and llm_readiness.get("status") == "available" else "partial"
        }
        if requirements_status != "complete":
            overall_status = "needs_info"
        elif approval_status in {"needs_info", "pending_approval"}:
            # Only block readiness when approval steps remain.
            overall_status = approval_status
        elif gate_status == "blocked":
            overall_status = "blocked"
        elif gate_status == "pending":
            overall_status = "pending_compliance"
        elif gate_sequence_status == "needs_info":
            overall_status = "needs_info"
        elif compliance_review_status == "blocked":
            overall_status = "blocked"
        elif compliance_review_status == "pending":
            overall_status = "pending_compliance"
        elif compliance_review_status == "needs_info":
            overall_status = "needs_info"
        elif execution_strategy == "simulation":
            overall_status = "needs_wiring"
        elif integration_status == "needs_wiring":
            overall_status = "needs_wiring"
        elif automation_loop_status in {"needs_wiring", "needs_info"}:
            overall_status = automation_loop_status
        elif multi_loop_status == "needs_wiring":
            overall_status = "needs_wiring"
        elif multi_loop_status in {"needs_info", "pending"}:
            overall_status = "needs_info"
        elif trigger_status == "needs_wiring":
            overall_status = "needs_wiring"
        elif monitoring_status == "needs_info":
            overall_status = "needs_info"
        elif output_status == "needs_info":
            overall_status = "needs_info"
        elif rollback_status == "needs_wiring":
            overall_status = "needs_wiring"
        elif deliverable_status != "ready":
            overall_status = deliverable_status
        else:
            overall_status = "ready"
        return {
            "status": overall_status,
            "execution_strategy": execution_strategy,
            "requirements_status": requirements_status,
            "approval_policy": approval_policy,
            "gate_status": gate_status,
            "delivery_status": deliverable_status,
            "processing_balance": processing_balance,
            "loop_iterations": iterations,
            "stages": stages,
            "chain_plan": chain_plan,
            "loop_chain": loop_chain,
            "wiring_gaps": wiring_gaps,
            "information_gaps": information_gaps,
            "edit_points": [
                {
                    "id": "onboarding_answers",
                    "description": "Update onboarding answers to refine requirements.",
                    "status": requirements_status
                },
                {
                    "id": "confidence_approval",
                    "description": "Raise confidence and confirm HITL approval for execution.",
                    "status": approval_status
                },
                {
                    "id": "gate_policy",
                    "description": "Update gate thresholds or overrides to adjust compliance.",
                    "status": gate_status
                },
                {
                    "id": "gate_sequence",
                    "description": "Adjust gate ordering and dependencies for compliance review.",
                    "status": gate_sequence_status
                },
                {
                    "id": "compliance_review",
                    "description": "Add regulatory evidence and QA sign-off checkpoints.",
                    "status": compliance_review_status
                },
                {
                    "id": "automation_loop",
                    "description": "Adjust learning loop variants and iteration scope.",
                    "status": automation_loop_status
                },
                {
                    "id": "swarm_generation",
                    "description": "Adjust swarm generation inputs and task seeding.",
                    "status": swarm_status
                },
                {
                    "id": "integration_wiring",
                    "description": "Configure integration connectors and handoff targets.",
                    "status": integration_status
                },
                {
                    "id": "multi_loop_schedule",
                    "description": "Define multi-project automation loop cadence.",
                    "status": multi_loop_status
                },
                {
                    "id": "trigger_schedule",
                    "description": "Update timer/trigger schedule for automated delivery windows.",
                    "status": trigger_status
                },
                {
                    "id": "output_delivery",
                    "description": "Configure output channels and delivery templates.",
                    "status": output_status
                },
                {
                    "id": "org_chart_roles",
                    "description": "Adjust org chart coverage and contract positions.",
                    "status": org_chart_plan.get("coverage_summary", {}).get("status", "unknown")
                },
                {
                    "id": "regional_sensors",
                    "description": "Edit region/regulatory sources for monitoring context.",
                    "status": monitoring_status
                },
                {
                    "id": "rollback_plan",
                    "description": "Update rollback and recovery plan checkpoints.",
                    "status": rollback_status
                }
            ],
            "next_actions": unique_actions,
            "request_summary": self._truncate_description(task_description)
        }

    def _build_dynamic_chain_plan(self, stage_statuses: Dict[str, str]) -> Dict[str, Any]:
        stage_ids = [stage["id"] for stage in self.DYNAMIC_IMPLEMENTATION_STAGES]
        stage_id_set = set(stage_ids)
        control_points = [
            stage_id
            for stage_id in stage_ids
            if stage_statuses.get(stage_id) not in {"ready", "complete"}
        ]
        links = []
        invalid_links = [
            {"from": source, "to": target}
            for source, target in self.DYNAMIC_IMPLEMENTATION_FLEX_LINKS
            if source not in stage_id_set or target not in stage_id_set
        ]
        if invalid_links:
            logger.warning("Invalid dynamic chain links detected: %s", invalid_links)
        if len(stage_ids) < 2:
            # A minimum of two stages required to form sequential chain links.
            if stage_ids:
                logger.warning(
                    "Dynamic chain plan has %s stage(s); sequential links disabled.",
                    len(stage_ids)
                )
            else:
                logger.warning("Dynamic chain plan has no stages; sequential links disabled.")
            training_patterns = self._build_training_patterns(stage_statuses, links)
            execution_routes = self._build_dynamic_chain_execution(stage_statuses, links)
            return {
                "mode": "adaptive",
                "primary_sequence": stage_ids,
                "control_points": control_points,
                "links": links,
                "invalid_links": invalid_links,
                "duplicate_links": [],
                "training_patterns": training_patterns,
                "execution_routes": execution_routes
            }
        link_pairs = set()
        for stage_id, next_id in zip(stage_ids, stage_ids[1:]):
            # Link readiness reflects whether the source stage is ready/complete before advancing.
            status = self._determine_chain_link_status(stage_statuses, stage_id)
            link_pairs.add((stage_id, next_id))
            links.append({
                "from": stage_id,
                "to": next_id,
                "mode": "sequential",
                "status": status
            })
        duplicate_links = []
        for source, target in self.DYNAMIC_IMPLEMENTATION_FLEX_LINKS:
            if source in stage_id_set and target in stage_id_set:
                if (source, target) in link_pairs:
                    duplicate_links.append({"from": source, "to": target})
                    continue
                links.append({
                    "from": source,
                    "to": target,
                    "mode": "adaptive",
                    "status": self._determine_chain_link_status(stage_statuses, source)
                })
        training_patterns = self._build_training_patterns(stage_statuses, links)
        execution_routes = self._build_dynamic_chain_execution(stage_statuses, links)
        return {
            "mode": "adaptive",
            "primary_sequence": stage_ids,
            "control_points": control_points,
            "links": links,
            "invalid_links": invalid_links,
            "duplicate_links": duplicate_links,
            "training_patterns": training_patterns,
            "execution_routes": execution_routes
        }

    def _build_dynamic_chain_execution(
        self,
        stage_statuses: Dict[str, str],
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        stage_metrics = []
        for stage in self.DYNAMIC_IMPLEMENTATION_STAGES:
            stage_id = stage["id"]
            status = stage_statuses.get(stage_id, "pending")
            confidence = self.STAGE_CONFIDENCE_SCORES.get(status, 0.4)
            estimated_seconds = self.STAGE_TIME_ESTIMATES.get(status, 35)
            priority_score = confidence / max(estimated_seconds, 1)
            stage_metrics.append({
                "id": stage_id,
                "status": status,
                "confidence": round(confidence, self.CONFIDENCE_DISPLAY_PRECISION),
                "estimated_seconds": estimated_seconds,
                "priority_score": round(priority_score, self.CONFIDENCE_DISPLAY_PRECISION)
            })
        priority_sequence = sorted(
            stage_metrics,
            key=lambda item: (-item["confidence"], item["estimated_seconds"])
        )
        ready_sequence = [
            item for item in priority_sequence if item["status"] in {"ready", "complete"}
        ]
        blocked_sequence = [
            item for item in stage_metrics if item["status"] not in {"ready", "complete"}
        ]
        adaptive_routes = [
            {
                "from": link["from"],
                "to": link["to"],
                "status": link["status"],
                "confidence": next(
                    (metric["confidence"] for metric in stage_metrics if metric["id"] == link["from"]),
                    self.STAGE_CONFIDENCE_SCORES.get("pending", 0.4)
                )
            }
            for link in links
        ]
        return {
            "priority_sequence": priority_sequence,
            "ready_sequence": ready_sequence,
            "blocked_sequence": blocked_sequence,
            "adaptive_routes": adaptive_routes,
            "summary": {
                "ready": len(ready_sequence),
                "blocked": len(blocked_sequence),
                "high_confidence_threshold": self.HIGH_CONFIDENCE_THRESHOLD
            }
        }

    def _build_training_patterns(
        self,
        stage_statuses: Dict[str, str],
        links: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        owner_map = {stage["id"]: stage["owner"] for stage in self.DYNAMIC_IMPLEMENTATION_STAGES}
        patterns = []
        for link in links:
            source = link["from"]
            status = stage_statuses.get(source, "pending")
            confidence = self._map_stage_confidence(status)
            estimated_seconds = self._estimate_stage_duration(status)
            patterns.append({
                "from": source,
                "to": link["to"],
                "mode": link["mode"],
                "status": status,
                "confidence": confidence,
                "estimated_seconds": estimated_seconds,
                "subject": owner_map.get(source, "unknown")
            })
        high_confidence = [
            pattern for pattern in patterns if pattern["confidence"] >= self.HIGH_CONFIDENCE_THRESHOLD
        ]
        sorted_by_speed = sorted(patterns, key=lambda item: item["estimated_seconds"])
        fastest_paths = sorted_by_speed[: max(1, len(sorted_by_speed) // 3)] if sorted_by_speed else []
        subject_ids = sorted({stage["owner"] for stage in self.DYNAMIC_IMPLEMENTATION_STAGES})
        avg_confidence = (
            sum(pattern["confidence"] for pattern in patterns) / len(patterns)
            if patterns
            else 0.0
        )
        total_time = sum(pattern["estimated_seconds"] for pattern in patterns)
        max_time = max((pattern["estimated_seconds"] for pattern in patterns), default=1)
        psychrometric_points = [
            {
                "id": f"{pattern['from']}→{pattern['to']}",
                "from": pattern["from"],
                "to": pattern["to"],
                "subject": pattern["subject"],
                "confidence": pattern["confidence"],
                "estimated_seconds": pattern["estimated_seconds"],
                "load_index": round(pattern["estimated_seconds"] / max_time, 3)
            }
            for pattern in patterns
        ]
        subject_summary = []
        for subject in subject_ids:
            subject_patterns = [pattern for pattern in patterns if pattern["subject"] == subject]
            if subject_patterns:
                avg_subject_confidence = sum(p["confidence"] for p in subject_patterns) / len(subject_patterns)
                avg_subject_time = sum(p["estimated_seconds"] for p in subject_patterns) / len(subject_patterns)
            else:
                avg_subject_confidence = 0.0
                avg_subject_time = 0.0
            subject_summary.append({
                "subject": subject,
                "paths": len(subject_patterns),
                "average_confidence": round(avg_subject_confidence, 3),
                "average_seconds": round(avg_subject_time, 1)
            })
        wingman_protocol = self._build_wingman_protocol(
            patterns,
            high_confidence,
            subject_summary
        )
        return {
            "model": "causal_path_confidence",
            "threshold": self.HIGH_CONFIDENCE_THRESHOLD,
            "patterns": patterns,
            "high_confidence_paths": high_confidence,
            "wingman_protocol": wingman_protocol,
            "graphing": {
                "subjects": subject_ids,
                "subject_summary": subject_summary,
                "time_unit": "seconds",
                "graphs": [
                    {
                        "id": "all_paths",
                        "label": "All chain paths",
                        "paths": patterns,
                        "average_confidence": round(avg_confidence, 3),
                        "estimated_total_seconds": total_time
                    },
                    {
                        "id": "high_confidence",
                        "label": "High-confidence paths",
                        "paths": high_confidence,
                        "threshold": self.HIGH_CONFIDENCE_THRESHOLD
                    },
                    {
                        "id": "fastest_paths",
                        "label": "Fastest estimated paths",
                        "paths": fastest_paths,
                        "criteria": "lowest_estimated_seconds"
                    },
                    {
                        "id": "subject_condensation",
                        "label": "Subject condensation map",
                        "purpose": "Condense subject matter across multiple subjects; chart style is optional.",
                        "axes": {
                            "x": "estimated_seconds",
                            "y": "confidence",
                            "humidity": "load_index"
                        },
                        "points": psychrometric_points
                    }
                ]
            }
        }

    def _build_wingman_protocol(
        self,
        patterns: List[Dict[str, Any]],
        high_confidence: List[Dict[str, Any]],
        subject_summary: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        validator_ready = bool(high_confidence)
        subjects = [entry["subject"] for entry in subject_summary]
        return {
            "status": "ready" if validator_ready else "needs_info",
            "action_side": {
                "role": "primary_executor",
                "focus": "Execute approved tasks and capture stage evidence.",
                "subjects": subjects
            },
            "validator_side": {
                "role": "deterministic_validator",
                "focus": "Verify outputs against gate criteria and deterministic checks.",
                "subjects": subjects
            },
            "training_sources": [
                "scripted_ui_screenshots",
                "gate_chain_outputs",
                "high_confidence_paths"
            ],
            "deterministic_checks": [
                "compute_plane_validation",
                "gate_policy_alignment",
                "delivery_readiness"
            ],
            "loop_notes": "Pair execution with validation feedback to train reusable runbooks per subject."
        }

    def _map_stage_confidence(self, status: str) -> float:
        return self.STAGE_CONFIDENCE_SCORES.get(status, 0.4)

    def _estimate_stage_duration(self, status: str) -> int:
        return self.STAGE_TIME_ESTIMATES.get(status, 35)

    @staticmethod
    def _determine_chain_link_status(stage_statuses: Dict[str, str], stage_id: str) -> str:
        return "open" if stage_statuses.get(stage_id) in {"ready", "complete"} else "gated"

    @staticmethod
    def _determine_output_status(requirements_stage_status: str, deliverable_status: str) -> str:
        if requirements_stage_status != "complete":
            return "needs_info"
        if deliverable_status in MurphySystem.OUTPUT_STATUS_PASSTHROUGH:
            return deliverable_status
        if deliverable_status == "ready":
            return "ready"
        # Treat the needs_info deliverable gap explicitly when requirements are complete but
        # delivery readiness still lacks supporting info (other gaps flow via passthrough set).
        if deliverable_status == "needs_info":
            return "needs_info"
        return "pending"

    @staticmethod
    def _determine_rollback_status(execution_strategy: str, deliverable_status: str) -> str:
        if execution_strategy == "simulation":
            return "needs_wiring"
        if deliverable_status == "ready":
            return "ready"
        return "pending"

    @staticmethod
    def _determine_automation_loop_status(
        requirements_stage_status: str,
        execution_strategy: str,
        learning_loop: Dict[str, Any]
    ) -> str:
        if requirements_stage_status != "complete":
            return "needs_info"
        if execution_strategy == "simulation":
            return "needs_wiring"
        loop_status = learning_loop.get("status")
        if loop_status and loop_status != "ready":
            return loop_status
        return "ready"

    def _build_timer_trigger_plan(self, task_description: str) -> Dict[str, Any]:
        if not GOVERNANCE_AVAILABLE:
            return {"status": "unavailable"}
        scheduler = GovernanceScheduler()
        now = datetime.utcnow()
        triggers = [
            {"id": "marketing_cycle", "label": "Marketing cadence", "offset_min": 30},
            {"id": "executive_review", "label": "Executive review", "offset_min": 60, "dependencies": ["marketing_cycle"]},
            {"id": "operations_director", "label": "Operations director sync", "offset_min": 90, "dependencies": ["executive_review"]},
            {"id": "qa_review", "label": "Quality assurance review", "offset_min": 120, "dependencies": ["operations_director"]},
            {"id": "hitl_contract", "label": "HITL contract approval", "offset_min": 150, "dependencies": ["qa_review"]},
            {"id": "execution_window", "label": "Execution window", "offset_min": 180, "dependencies": ["hitl_contract"]}
        ]
        schedule = []
        for trigger in triggers:
            descriptor = AgentDescriptor(
                agent_id=trigger["id"],
                version="1.0.0",
                authority_band=GovernanceAuthorityBand.MEDIUM,
                action_permissions=ActionSet(allowed_proposals=[GovernanceActionType.PROPOSE_ACTION])
            )
            scheduled_time = now + timedelta(minutes=trigger["offset_min"])
            agent = ScheduledAgent(
                agent_id=trigger["id"],
                descriptor=descriptor,
                priority=PriorityLevel.NORMAL,
                scheduled_time=scheduled_time,
                dependencies=trigger.get("dependencies", []),
                resource_requirements={"cpu": 1, "memory": 256}
            )
            decision = scheduler.schedule_agent(agent)
            schedule.append({
                "id": trigger["id"],
                "label": trigger["label"],
                "scheduled_time": scheduled_time.isoformat(),
                "decision": decision.value,
                "dependencies": trigger.get("dependencies", [])
            })
        return {
            "status": "scheduled",
            "summary": scheduler.get_system_status(),
            "triggers": schedule,
            "request": task_description
        }

    def update_gate_policy(
        self,
        doc: LivingDocument,
        updates: List[Dict[str, Any]],
        confidence: Optional[float] = None
    ) -> None:
        """Update gate policy entries and recompute gate statuses."""
        if confidence is not None:
            doc.confidence = max(0.0, min(1.0, confidence))
        policy = doc.gate_policy or deepcopy(self.default_gate_policy)
        for update in updates:
            name = (update.get("name") or "").strip()
            if not name:
                continue
            existing_gate = next((gate for gate in policy if gate.get("name", "").lower() == name.lower()), None)
            if not existing_gate:
                existing_gate = {"name": name, "threshold": update.get("threshold", 0.5)}
                policy.append(existing_gate)
            if "threshold" in update:
                existing_gate["threshold"] = update["threshold"]
            if "status" in update or "status_override" in update:
                override_value = self._normalize_gate_override(
                    update.get("status_override", update.get("status")),
                    name
                )
                if override_value:
                    existing_gate["status_override"] = override_value
            if update.get("clear_override"):
                existing_gate.pop("status_override", None)
            if "stage" in update:
                existing_gate["stage"] = update["stage"]
        doc.gate_policy = policy
        doc.capability_tests = []
        self._update_document_tree(doc)
        if self.librarian:
            self.librarian.log_transcript(
                module="governance",
                action="update_gate_policy",
                details={
                    "doc_id": doc.doc_id,
                    "updates": updates,
                    "confidence": doc.confidence
                },
                actor="user",
                success=True
            )

    def _record_activation_usage(self, subsystems: List[str]) -> None:
        for subsystem in subsystems:
            self.activation_usage[subsystem] = self.activation_usage.get(subsystem, 0) + 1

    def _should_activate_swarm_system(self, text: str, doc: LivingDocument) -> bool:
        """Decide when swarm expansion is needed for the request."""
        return "automation" in text or doc.state == self.ACTIVATION_SOLIDIFIED_STATE

    def _truncate_description(self, text: str) -> str:
        if len(text) <= self.MAX_FAILURE_MODE_DESC_LENGTH:
            return text
        return f"{text[:self.MAX_FAILURE_MODE_DESC_LENGTH]}..."

    def _normalize_gate_override(self, override: Optional[str], name: str) -> Optional[str]:
        if override not in {None, *self.GATE_OVERRIDE_VALUES}:
            logger.warning("Invalid gate override '%s' ignored for %s", override, name)
            return None
        return override

    def _summarize_gate(self, gate: Any) -> Dict[str, Any]:
        return {
            "id": getattr(gate, "id", None),
            "type": getattr(getattr(gate, "type", None), "value", getattr(gate, "type", None)),
            "category": getattr(getattr(gate, "category", None), "value", getattr(gate, "category", None)),
            "state": getattr(getattr(gate, "state", None), "value", getattr(gate, "state", None)),
            "target": getattr(gate, "target", None),
            "reason": getattr(gate, "reason", None)
        }

    def _normalize_region(self, region_input: Optional[str]) -> str:
        if not region_input:
            return "global"
        canonical = region_input.lower().strip()
        normalized = re.sub(r"\s+", " ", canonical.replace("_", " ")).strip()
        underscored = normalized.replace(" ", "_")
        if canonical in self.REGION_ALIASES:
            return canonical
        if underscored in self.REGION_ALIASES:
            return underscored
        for region, aliases in self.REGION_ALIASES.items():
            for alias in aliases:
                pattern = rf"\b{re.escape(alias)}\b"
                if re.search(pattern, normalized):
                    return region
        return "global"

    def _filter_sensors_for_region(self, sources: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
        return [
            {**sensor, "matched_region": region}
            for sensor in sources
            if region in sensor.get("regions", []) or "global" in sensor.get("regions", [])
        ]

    def _select_primary_sensor(self, sensors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not sensors:
            return None
        return next((sensor for sensor in sensors if sensor.get("access") == "free"), sensors[0])

    def _extract_region_from_context(
        self,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        context = onboarding_context or {}
        answers = context.get("answers", {})
        region_input = context.get("region_input")
        if region_input is None:
            region_input = context.get("region")
        if region_input is None:
            region_input = answers.get("region")
        source = "onboarding" if region_input else "task_description"
        region = self._normalize_region(region_input or task_description)
        return {
            "region": region,
            "source": source
        }

    def _build_external_sensor_plan(
        self,
        domain: str,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        region_info = self._extract_region_from_context(task_description, onboarding_context)
        region = region_info["region"]
        domain_sources = self.EXTERNAL_SENSOR_CATALOG.get(domain, [])
        general_sources = self.EXTERNAL_SENSOR_CATALOG.get("general", [])
        compliance_sources = self.EXTERNAL_SENSOR_CATALOG.get("compliance", [])
        sensors = self._filter_sensors_for_region(domain_sources + general_sources, region)
        regulatory_sources = self._filter_sensors_for_region(compliance_sources, region)
        primary_sensor = self._select_primary_sensor(sensors)
        primary_regulatory = self._select_primary_sensor(regulatory_sources)
        return {
            "region": region,
            "region_source": region_info,
            "domain": domain,
            "sensors": sensors,
            "regulatory_sources": regulatory_sources,
            "primary_sensor": primary_sensor,
            "primary_regulatory_source": primary_regulatory,
            "notes": "Sources are public/free; some require free API keys."
        }

    def _select_control_profile(self, task_description: str) -> Dict[str, Any]:
        profiles = [
            {
                "id": "marketing",
                "keywords": ["marketing", "campaign", "seo", "social", "brand"],
                "metric": "conversion_rate",
                "unit": "ratio",
                "setpoint": 0.12,
                "baseline": 0.08,
                "sensor": "marketing_engagement_api",
                "signal": "engagement_score"
            },
            {
                "id": "operations",
                "keywords": ["operations", "workflow", "logistics", "fulfillment"],
                "metric": "cycle_time_minutes",
                "unit": "minutes",
                "setpoint": 45,
                "baseline": 60,
                "sensor": "ops_latency_sensor",
                "signal": "cycle_time"
            },
            {
                "id": "qa",
                "keywords": ["qa", "quality", "defect", "test"],
                "metric": "defect_rate",
                "unit": "ratio",
                "setpoint": 0.02,
                "baseline": 0.05,
                "sensor": "qa_audit_sensor",
                "signal": "defect_rate"
            },
            {
                "id": "compliance",
                "keywords": ["compliance", "regulation", "legal", "law", "tax", "building code"],
                "metric": "compliance_risk",
                "unit": "ratio",
                "setpoint": 0.95,
                "baseline": 0.82,
                "sensor": "regulatory_compliance_api",
                "signal": "compliance_index"
            },
            {
                "id": "executive",
                "keywords": ["executive", "approval", "governance", "board"],
                "metric": "decision_latency_hours",
                "unit": "hours",
                "setpoint": 24,
                "baseline": 36,
                "sensor": "approval_queue_sensor",
                "signal": "decision_latency"
            },
            {
                "id": "finance",
                "keywords": ["billing", "finance", "revenue", "payments"],
                "metric": "collection_rate",
                "unit": "ratio",
                "setpoint": 0.95,
                "baseline": 0.88,
                "sensor": "billing_gateway_api",
                "signal": "collections_rate"
            },
            {
                "id": "execution",
                "keywords": ["automation", "execution", "deployment", "production"],
                "metric": "automation_success_rate",
                "unit": "ratio",
                "setpoint": 0.9,
                "baseline": 0.75,
                "sensor": "runtime_success_sensor",
                "signal": "execution_success"
            }
        ]
        lower_text = task_description.lower()
        return next(
            (item for item in profiles if any(keyword in lower_text for keyword in item["keywords"])),
            {
                "id": "general",
                "metric": "confidence_index",
                "unit": "ratio",
                "setpoint": 0.75,
                "baseline": 0.55,
                "sensor": "request_confidence_sensor",
                "signal": "confidence_index"
            }
        )

    def _build_gate_control_data(
        self,
        task_description: str,
        doc: LivingDocument,
        onboarding_context: Optional[Dict[str, Any]] = None,
        sensor_plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        profile = self._select_control_profile(task_description)
        risk_factor = round(max(0.0, 1.0 - doc.confidence), 3)
        baseline = profile["baseline"]
        setpoint = profile["setpoint"]
        sensor_value = round(baseline + (setpoint - baseline) * doc.confidence, 3)
        control_value = round(sensor_value * (1 - risk_factor), 3)
        # Defensive fallback for call sites that don't precompute sensor plans.
        if sensor_plan is None:
            sensor_plan = self._build_external_sensor_plan(profile["id"], task_description, onboarding_context)
        sensor_source = "generated_sensor"
        if profile["id"] == "compliance" and sensor_plan.get("primary_regulatory_source"):
            sensor_source = f"regulatory_plan:{sensor_plan['primary_regulatory_source']['id']}"
        elif sensor_plan.get("primary_sensor"):
            sensor_source = f"external_plan:{sensor_plan['primary_sensor']['id']}"
        return {
            "domain": profile["id"],
            "control_metric": {
                "name": profile["metric"],
                "unit": profile["unit"],
                "setpoint": setpoint,
                "control_value": control_value,
                "risk_factor": risk_factor,
                "formula": f"{profile['signal']} * (1 - risk_factor)"
            },
            "sensor_feedback": {
                "sensor": profile["sensor"],
                "signal": profile["signal"],
                "value": sensor_value,
                "source": sensor_source,
                "timestamp": datetime.utcnow().isoformat()
            },
            "external_api_sensors": sensor_plan,
            "control_effect": "If control_value < setpoint, magnify/simplify gates remain blocked."
        }

    def _apply_wired_capabilities(
        self,
        task_description: str,
        doc: LivingDocument,
        onboarding_context: Optional[Dict[str, Any]],
        sensor_plan: Optional[Dict[str, Any]] = None
    ) -> None:
        results = self._run_gap_solution_attempts(task_description, doc, onboarding_context, sensor_plan)
        existing_gate_ids = {gate.get("id") for gate in doc.gates if isinstance(gate, dict) and gate.get("id")}
        for result in results:
            if result.get("id") == "gate_synthesis" and result.get("status") == "ok":
                doc.gate_synthesis_gates = result.get("gates", [])
                synthesis_entries = []
                for gate in doc.gate_synthesis_gates:
                    if gate.get("id") in existing_gate_ids:
                        continue
                    synthesis_entries.append({
                        "name": f"Synthesis {gate.get('category', 'gate')}",
                        "status": gate.get("state", "proposed"),
                        "target": gate.get("target"),
                        "type": gate.get("type"),
                        "id": gate.get("id")
                    })
                doc.gates.extend(synthesis_entries)
            if result.get("id") == "true_swarm_system" and result.get("status") == "ok":
                if not doc.generated_tasks:
                    doc.generated_tasks = self._generate_swarm_tasks()
                    doc.children = doc.generated_tasks
            if result.get("id") == "inoni_business_automation" and result.get("status") == "ok":
                doc.automation_summary = result.get("summary", {})
        doc.block_tree = self._build_block_tree(doc)

    def _build_execution_wiring_snapshot(self, doc: LivingDocument) -> Dict[str, Any]:
        gate_synthesis = doc.gate_synthesis_gates or []
        swarm_tasks = doc.generated_tasks or []
        swarm_ready = bool(getattr(self, "swarm_system", None))
        return {
            "gate_synthesis": {
                "status": "ready" if gate_synthesis else "needs_wiring",
                "total_gates": len(gate_synthesis)
            },
            "swarm_tasks": {
                "status": "ready" if swarm_tasks else "needs_info",
                "total_tasks": len(swarm_tasks)
            },
            "swarm_system": {
                "status": "ready" if swarm_ready else "needs_wiring",
                "initialized": swarm_ready
            },
            "execution_ready": bool(gate_synthesis) and bool(swarm_tasks) and swarm_ready
        }

    def _build_orchestrator_readiness_snapshot(self) -> Dict[str, Any]:
        async_ready = self._supports_async_orchestrator()
        two_phase_ready = self._supports_two_phase_orchestrator()
        swarm_ready = bool(getattr(self, "swarm_system", None))
        components = {
            "async_orchestrator": {
                "status": "ready" if async_ready else "needs_wiring",
                "available": async_ready
            },
            "two_phase_orchestrator": {
                "status": "ready" if two_phase_ready else "needs_wiring",
                "available": two_phase_ready
            },
            "swarm_system": {
                "status": "ready" if swarm_ready else "needs_wiring",
                "available": swarm_ready
            }
        }
        ready_count = sum(1 for entry in components.values() if entry["status"] == "ready")
        preferred_path = "simulation"
        if async_ready:
            preferred_path = "async_orchestrator"
        elif two_phase_ready:
            preferred_path = "two_phase_orchestrator"
        return {
            "summary": {
                "total": len(components),
                "ready": ready_count,
                "needs_wiring": len(components) - ready_count
            },
            "components": components,
            "execution_ready": async_ready or two_phase_ready,
            "preferred_path": preferred_path
        }

    def _build_integration_capabilities(self) -> Dict[str, Any]:
        connectors = []
        for entry in self.INTEGRATION_CONNECTOR_CATALOG:
            requirement = entry.get("requires")
            available = False
            if requirement == "integration_engine":
                available = bool(self.integration_engine)
            elif requirement == "adapter_runtime":
                available = AdapterRuntime is not None
            elif requirement == "governance_scheduler":
                available = bool(self.governance_scheduler)
            registered = self.integration_connectors.get(entry["id"])
            if registered:
                status = registered.get("status", "configured")
            else:
                status = "available" if available else "needs_integration"
            connectors.append({
                **entry,
                "available": available,
                "status": status,
                "configured": bool(registered)
            })
        adapter_availability = self._get_adapter_availability()
        for adapter in self.CORE_ADAPTER_CANDIDATES:
            module_name = adapter["module"]
            available = adapter_availability.get(module_name, False)
            connectors.append({
                "id": adapter["id"],
                "label": adapter["label"],
                "channel": adapter["channel"],
                "requires": "module_available",
                "available": available,
                "configured": False,
                "status": "available" if available else "needs_integration",
                "module": module_name
            })
        ready_count = len([item for item in connectors if item["status"] in {"available", "configured"}])
        return {
            "summary": {
                "total": len(connectors),
                "ready": ready_count,
                "needs_integration": len(connectors) - ready_count
            },
            "connectors": connectors
        }

    def _build_adapter_execution_snapshot(self) -> Dict[str, Any]:
        adapter_availability = self._get_adapter_availability()
        configured_ids = {
            connector_id
            for connector_id, connector in self.integration_connectors.items()
            if connector.get("status") == "configured"
        }
        adapters = []
        for adapter in self.CORE_ADAPTER_CANDIDATES:
            module_name = adapter["module"]
            available = adapter_availability.get(module_name, False)
            configured = adapter["id"] in configured_ids
            if configured:
                status = "configured"
            elif available:
                status = "available"
            else:
                status = "needs_integration"
            adapters.append({
                **adapter,
                "available": available,
                "configured": configured,
                "status": status
            })
        configured_count = len([adapter for adapter in adapters if adapter["status"] == "configured"])
        available_count = len([adapter for adapter in adapters if adapter["status"] == "available"])
        total = len(adapters)
        return {
            "summary": {
                "total": total,
                "configured": configured_count,
                "available": available_count,
                "needs_integration": total - configured_count - available_count
            },
            "adapters": adapters
        }

    def _build_delivery_adapter_snapshot(self) -> Dict[str, Any]:
        configured_ids = {
            connector_id
            for connector_id, connector in self.integration_connectors.items()
            if connector.get("status") == "configured"
        }
        adapters = []
        for adapter in self.DELIVERY_ADAPTER_CANDIDATES:
            module_name = adapter["module"]
            available = False
            try:
                available = importlib.util.find_spec(module_name) is not None
            except (AttributeError, ImportError, ModuleNotFoundError):
                available = False
            configured = adapter["id"] in configured_ids
            if configured:
                status = "configured"
            elif available:
                status = "available"
            else:
                status = "needs_integration"
            adapters.append({
                **adapter,
                "available": available,
                "configured": configured,
                "status": status
            })
        ready_count = 0
        available_count = 0
        for adapter in adapters:
            if adapter["status"] == "configured":
                ready_count += 1
            elif adapter["status"] == "available":
                available_count += 1
        total = len(adapters)
        return {
            "summary": {
                "total": total,
                "configured": ready_count,
                "available": available_count,
                "unconfigured": total - ready_count
            },
            "adapters": adapters
        }

    def _build_connector_orchestration_snapshot(
        self,
        delivery_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if delivery_snapshot is None:
            delivery_snapshot = self._build_delivery_adapter_snapshot()
        channels = []
        for adapter in delivery_snapshot.get("adapters", []):
            channel = adapter.get("channel")
            configured_connectors = self._get_configured_delivery_connectors(channel) if channel else []
            connector_ids = [connector["id"] for connector in configured_connectors]
            if connector_ids:
                status = "configured"
            elif adapter.get("status") == "available":
                status = "available"
            else:
                status = "needs_integration"
            channels.append({
                "channel": channel,
                "adapter_id": adapter.get("id"),
                "adapter_status": adapter.get("status"),
                "configured_connectors": connector_ids,
                "status": status
            })
        configured = len([entry for entry in channels if entry["status"] == "configured"])
        available = len([entry for entry in channels if entry["status"] == "available"])
        total = len(channels)
        if total and configured == total:
            orchestration_status = "ready"
            gap_action = "All delivery channels configured."
        elif configured:
            orchestration_status = "partial"
            gap_action = "Configure remaining delivery channels for full coverage."
        else:
            orchestration_status = "needs_integration"
            gap_action = "Configure delivery connectors for document/email/chat/voice outputs."
        return {
            "status": orchestration_status,
            "summary": {
                "total": total,
                "configured": configured,
                "available": available,
                "needs_integration": total - configured - available
            },
            "channels": channels,
            "gap_action": gap_action
        }

    def _get_configured_delivery_connectors(self, channel: str) -> List[Dict[str, Any]]:
        connectors = []
        for connector_id, connector in self.integration_connectors.items():
            if connector.get("channel") != channel:
                continue
            if connector.get("status") != "configured":
                continue
            connectors.append({"id": connector_id, **connector})
        return connectors

    def _build_document_deliverable(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        connectors = self._get_configured_delivery_connectors("document")
        if not connectors:
            return None
        try:
            # Lazy import keeps DocumentGenerationEngine optional unless document delivery is requested.
            from src.execution.document_generation_engine import (
                DocumentGenerationEngine,
                DocumentTemplate,
                DocumentType
            )
        except ImportError:
            logger.warning("DocumentGenerationEngine not available; document delivery skipped.")
            return None
        params = parameters or {}
        template_id = params.get("document_template_id", "task_summary")
        template_content = params.get(
            "document_template",
            "Task: {task}\nSummary: {summary}\nDeliverable: {deliverable}"
        )
        placeholder_matches = re.findall(r"{([^}]+)}", template_content)
        placeholders = sorted(
            {
                match.strip()
                for match in placeholder_matches
                if re.fullmatch(self.DOCUMENT_PLACEHOLDER_PATTERN, match.strip())
            }
        )
        if not placeholders:
            placeholders = ["task", "summary", "deliverable"]
        context = dict(params.get("document_context") or {})
        context.setdefault("task", task_description)
        summary_text = params.get("document_summary")
        if not summary_text:
            # Reuse the standard summary truncation helper for document defaults.
            summary_text = self._truncate_description(task_description)
        context.setdefault("summary", summary_text)
        context.setdefault("deliverable", params.get("document_deliverable", task_type))
        connector_override = params.get("document_connector_id")
        if connector_override:
            connectors = [
                connector for connector in connectors if connector["id"] == connector_override
            ]
            if not connectors:
                logger.warning(
                    "Requested document connector '%s' not configured; skipping document delivery.",
                    connector_override
                )
                return None
        # Select the first connector alphabetically by ID for deterministic behavior.
        selected_connector = sorted(connectors, key=lambda connector: connector["id"])[0]
        engine = DocumentGenerationEngine()
        template = DocumentTemplate(
            template_id=template_id,
            template_type=DocumentType.MARKDOWN,
            content=template_content,
            placeholders=placeholders
        )
        engine.register_template(template)
        document = engine.generate_from_template(
            template_id,
            context,
            metadata={"task_type": task_type, "connector_id": selected_connector["id"]}
        )
        return {
            "type": "document",
            "status": "generated",
            "connector_id": selected_connector["id"],
            "document": document.to_dict()
        }

    def _build_email_deliverable(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        connectors = self._get_configured_delivery_connectors("email")
        if not connectors:
            return None
        params = parameters or {}
        connector_override = params.get("email_connector_id")
        if connector_override:
            connectors = [
                connector for connector in connectors if connector["id"] == connector_override
            ]
            if not connectors:
                logger.warning(
                    "Requested email connector '%s' not configured; skipping email delivery.",
                    connector_override
                )
                return None
        selected_connector = sorted(connectors, key=lambda connector: connector["id"])[0]
        recipients_raw = params.get("email_recipients") or []
        if isinstance(recipients_raw, list):
            recipients = [str(item) for item in recipients_raw if item]
        elif recipients_raw:
            recipients = [str(recipients_raw)]
        else:
            recipients = []
        subject = params.get("email_subject") or f"Automation update: {task_type}"
        summary_text = params.get("email_summary") or self._truncate_description(task_description)
        body = params.get("email_body") or f"{summary_text}\n\nTask: {task_description}"
        status = "queued" if recipients else "needs_info"
        deliverable = {
            "type": "email",
            "status": status,
            "connector_id": selected_connector["id"],
            "message": {
                "to": recipients,
                "subject": subject,
                "body": body
            }
        }
        if status == "needs_info":
            deliverable["gap_action"] = "Provide email recipients to queue the delivery."
        return deliverable

    def _build_chat_deliverable(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        connectors = self._get_configured_delivery_connectors("chat")
        if not connectors:
            return None
        params = parameters or {}
        connector_override = params.get("chat_connector_id")
        if connector_override:
            connectors = [
                connector for connector in connectors if connector["id"] == connector_override
            ]
            if not connectors:
                logger.warning(
                    "Requested chat connector '%s' not configured; skipping chat delivery.",
                    connector_override
                )
                return None
        selected_connector = sorted(connectors, key=lambda connector: connector["id"])[0]
        channel = params.get("chat_channel") or params.get("chat_room")
        message = params.get("chat_message") or params.get("chat_summary")
        if not message:
            message = self._truncate_description(task_description)
        status = "queued" if channel else "needs_info"
        deliverable = {
            "type": "chat",
            "status": status,
            "connector_id": selected_connector["id"],
            "message": {
                "channel": channel,
                "content": message
            }
        }
        if status == "needs_info":
            deliverable["gap_action"] = "Provide chat channel to queue the delivery."
        return deliverable

    def _build_voice_deliverable(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        connectors = self._get_configured_delivery_connectors("voice")
        if not connectors:
            return None
        params = parameters or {}
        connector_override = params.get("voice_connector_id")
        if connector_override:
            connectors = [
                connector for connector in connectors if connector["id"] == connector_override
            ]
            if not connectors:
                logger.warning(
                    "Requested voice connector '%s' not configured; skipping voice delivery.",
                    connector_override
                )
                return None
        selected_connector = sorted(connectors, key=lambda connector: connector["id"])[0]
        destination = params.get("voice_destination") or params.get("voice_number")
        script = params.get("voice_script") or params.get("voice_message")
        if not script:
            script = self._truncate_description(task_description)
        profile = params.get("voice_profile") or "default"
        status = "queued" if destination else "needs_info"
        deliverable = {
            "type": "voice",
            "status": status,
            "connector_id": selected_connector["id"],
            "script": {
                "text": script,
                "voice_profile": profile,
                "destination": destination
            }
        }
        if status == "needs_info":
            deliverable["gap_action"] = "Provide voice destination to queue the delivery."
        return deliverable

    def _build_translation_deliverable(
        self,
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        connectors = self._get_configured_delivery_connectors("translation")
        if not connectors:
            return None
        params = parameters or {}
        connector_override = params.get("translation_connector_id")
        if connector_override:
            connectors = [
                connector for connector in connectors if connector["id"] == connector_override
            ]
            if not connectors:
                logger.warning(
                    "Requested translation connector '%s' not configured; skipping translation delivery.",
                    connector_override
                )
                return None
        selected_connector = sorted(connectors, key=lambda connector: connector["id"])[0]
        connector_id = selected_connector["id"]
        # translation_locale is a legacy alias for target locale (predates translation_target_locale).
        legacy_locale_map = {
            "source_locale": "translation_source_locale",
            "target_locale": "translation_target_locale",
            "translation_locale": "translation_target_locale"
        }
        for legacy_key, preferred_key in legacy_locale_map.items():
            if preferred_key not in params and legacy_key in params:
                logger.debug(
                    "translation delivery detected legacy parameter %s for connector %s; will check %s in fallback resolution.",
                    legacy_key,
                    connector_id,
                    preferred_key
                )
        # Prefer translation_source_locale for clarity; source_locale remains as a legacy alias.
        source_locale = (
            params.get("translation_source_locale")
            or params.get("source_locale")
            or self.DEFAULT_TRANSLATION_SOURCE_LOCALE
        )
        target_locale = (
            params.get("translation_target_locale")
            or params.get("target_locale")
            or params.get("translation_locale")
        )
        if "translation_text" not in params and "translation_source" in params:
            logger.debug(
                "translation delivery received legacy translation_source; prefer translation_text."
            )
        # translation_source is a legacy alias for translation_text (content, not locale metadata).
        text = params.get("translation_text") or params.get("translation_source")
        if not text:
            text = self._truncate_description(task_description)
        status = "queued" if target_locale else "needs_info"
        translation_payload = {
            "text": text,
            "source_locale": source_locale
        }
        if target_locale:
            translation_payload["target_locale"] = target_locale
        deliverable = {
            "type": "translation",
            "status": status,
            "connector_id": selected_connector["id"],
            "translation": translation_payload
        }
        if status == "needs_info":
            deliverable["gap_action"] = self.TRANSLATION_GAP_ACTION
        return deliverable

    def _append_document_deliverable(
        self,
        deliverables: Optional[List[Dict[str, Any]]],
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        output = list(deliverables or [])
        if any(item.get("type") == "document" for item in output):
            return output
        document_delivery = self._build_document_deliverable(task_description, task_type, parameters)
        if document_delivery:
            output.append(document_delivery)
        return output

    def _append_email_deliverable(
        self,
        deliverables: Optional[List[Dict[str, Any]]],
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        output = list(deliverables or [])
        if any(item.get("type") == "email" for item in output):
            return output
        email_delivery = self._build_email_deliverable(task_description, task_type, parameters)
        if email_delivery:
            output.append(email_delivery)
        return output

    def _append_chat_deliverable(
        self,
        deliverables: Optional[List[Dict[str, Any]]],
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        output = list(deliverables or [])
        if any(item.get("type") == "chat" for item in output):
            return output
        chat_delivery = self._build_chat_deliverable(task_description, task_type, parameters)
        if chat_delivery:
            output.append(chat_delivery)
        return output

    def _append_voice_deliverable(
        self,
        deliverables: Optional[List[Dict[str, Any]]],
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        output = list(deliverables or [])
        if any(item.get("type") == "voice" for item in output):
            return output
        voice_delivery = self._build_voice_deliverable(task_description, task_type, parameters)
        if voice_delivery:
            output.append(voice_delivery)
        return output

    def _append_translation_deliverable(
        self,
        deliverables: Optional[List[Dict[str, Any]]],
        task_description: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        output = list(deliverables or [])
        if any(item.get("type") == "translation" for item in output):
            return output
        translation_delivery = self._build_translation_deliverable(task_description, task_type, parameters)
        if translation_delivery:
            output.append(translation_delivery)
        return output

    def _build_handoff_queue_snapshot(
        self,
        hitl_contracts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        pending_interventions = [
            item for item in self.hitl_interventions.values() if item.get("status") == "pending"
        ]
        contract_queue = hitl_contracts or []
        pending_contracts = []
        for contract in contract_queue:
            status = str(contract.get("status", "")).lower()
            # Approved/complete/ready/cleared indicate resolved HITL contracts.
            if status in {"approved", "complete", "ready", "cleared"}:
                continue
            pending_contracts.append(contract)
        total_pending = len(pending_interventions) + len(pending_contracts)
        monitor_ready = bool(self.hitl_monitor)
        if monitor_ready:
            queue_status = "pending_review" if total_pending else "clear"
        else:
            queue_status = "needs_wiring" if total_pending else "monitor_unavailable"
        if total_pending:
            gap_action = "Review pending HITL requests and contract approvals."
        elif monitor_ready:
            gap_action = "No HITL backlog; monitor ready for new approvals."
        else:
            gap_action = "Initialize HITL monitor to track approvals and handoff requests."
        return {
            "status": queue_status,
            "monitor_status": "ready" if monitor_ready else "needs_wiring",
            "summary": {
                "pending_interventions": len(pending_interventions),
                "pending_contracts": len(pending_contracts),
                "total_pending": total_pending
            },
            "pending_interventions": pending_interventions,
            "pending_contracts": pending_contracts,
            "gap_action": gap_action
        }

    @staticmethod
    def _normalize_governance_status(status: str) -> str:
        """Map raw governance status values to summary buckets.

        Examples:
        - ready/complete/clear/configured -> ready
        - pending/pending_review/pending_approval/blocked/needs_compliance -> pending (review required)
        - needs_wiring/monitor_unavailable/unavailable -> needs_wiring
        - needs_info -> needs_info
        - unknown values -> other

        Blocked/compliance statuses stay in the pending bucket to keep review visibility.
        """
        if status in {"ready", "complete", "clear", "configured"}:
            return "ready"
        if status in {"pending", "pending_review", "pending_approval", "blocked", "needs_compliance"}:
            return "pending"
        if status in {"needs_wiring", "monitor_unavailable", "unavailable"}:
            return "needs_wiring"
        if status == "needs_info":
            return "needs_info"
        return "other"

    @staticmethod
    def _resolve_plan_status(tasks: List[Dict[str, Any]]) -> str:
        """Return needs_wiring when empty, ready when all tasks ready/complete, else pending.

        Args:
            tasks: list of task dicts containing at least ``status`` (and often ``owner``).
        """
        if not tasks:
            return "needs_wiring"
        if all(task.get("status") in {"ready", "complete"} for task in tasks):
            return "ready"
        return "pending"

    def _build_governance_dashboard_snapshot(
        self,
        executive_directive: Optional[Dict[str, Any]],
        operations_plan: Optional[List[Dict[str, Any]]],
        delivery_readiness: Optional[Dict[str, Any]],
        handoff_queue: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize executive, operations, QA, and HITL readiness into one dashboard.

        Returns a dict with: status, summary, components, and gap_action.
        """
        operations_plan = operations_plan or []
        delivery_readiness = delivery_readiness or {}
        handoff_queue = handoff_queue or {}
        # Prefer executive directive readiness, fall back to delivery readiness, then needs_info.
        executive_status = (
            (executive_directive or {}).get("delivery_readiness")
            or delivery_readiness.get("status")
            or "needs_info"
        )
        delivery_status = delivery_readiness.get("status", "needs_info")
        compliance_status = delivery_readiness.get("compliance_status", "needs_wiring")
        hitl_status = handoff_queue.get("status", "needs_wiring")

        operations_status = self._resolve_plan_status(operations_plan)
        qa_tasks = [
            task for task in operations_plan if task.get("owner") == self.GOVERNANCE_OWNER_QA
        ]
        qa_status = self._resolve_plan_status(qa_tasks)

        components = {
            "executive": executive_status,
            "operations": operations_status,
            "quality_assurance": qa_status,
            "hitl": hitl_status,
            "delivery": delivery_status,
            "compliance": compliance_status
        }
        summary = {
            "total": len(components),
            "ready": 0,
            "pending": 0,
            "needs_info": 0,
            "needs_wiring": 0,
            "other": 0
        }
        normalized = {}
        # Normalize detailed statuses into summary buckets for governance readiness tracking.
        for component, status in components.items():
            normalized_status = self._normalize_governance_status(status)
            summary[normalized_status] += 1
            normalized[component] = {"status": status, "normalized_status": normalized_status}

        if summary["needs_wiring"]:
            overall_status = "needs_wiring"
            gap_action = "Initialize missing governance services and delivery connectors."
        elif summary["needs_info"]:
            overall_status = "needs_info"
            gap_action = "Collect missing governance inputs and compliance evidence."
        elif summary["pending"]:
            overall_status = "pending_review"
            gap_action = "Review pending approvals and QA checks."
        else:
            overall_status = "ready"
            gap_action = "Governance dashboard ready for execution."

        return {
            "status": overall_status,
            "summary": summary,
            "components": normalized,
            "gap_action": gap_action
        }

    def _build_learning_backlog_snapshot(
        self,
        learning_loop: Optional[Dict[str, Any]],
        training_patterns: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not learning_loop:
            return {
                "status": "unavailable",
                "reason": "Learning loop unavailable.",
                "summary": {"total_iterations": 0}
            }
        training_patterns = training_patterns or {}
        iterations = learning_loop.get("iterations", [])
        backlog = [
            {
                "iteration": entry.get("iteration"),
                "variant": entry.get("variant"),
                "focus": entry.get("focus"),
                "status": entry.get("status", "pending")
            }
            for entry in iterations
        ]
        queued = [entry for entry in backlog if entry["status"] in {"queued", "ready"}]
        pending = [entry for entry in backlog if entry["status"] not in {"queued", "ready"}]
        loop_status = learning_loop.get("status", "needs_info")
        if loop_status == "ready":
            status = "ready"
        elif loop_status == "needs_wiring":
            status = "needs_wiring"
        else:
            status = "needs_info"
        training_sources = (
            training_patterns.get("wingman_protocol", {}).get("training_sources", [])
            if training_patterns
            else []
        )
        return {
            "status": status,
            "requirements_status": learning_loop.get("requirements_identification", {}).get("status"),
            "summary": {
                "total_iterations": len(backlog),
                "queued_iterations": len(queued),
                "pending_iterations": len(pending)
            },
            "backlog": backlog,
            "routing": {
                "status": "ready" if status == "ready" else "pending",
                "training_sources": training_sources,
                "high_confidence_paths": len(training_patterns.get("high_confidence_paths", []))
            },
            "gap_action": learning_loop.get("gap_action")
        }

    def _build_self_improvement_snapshot(
        self,
        dynamic_implementation: Optional[Dict[str, Any]],
        capability_review: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not dynamic_implementation:
            return {
                "status": "unavailable",
                "reason": "Dynamic implementation plan unavailable.",
                "summary": {"total_backlog": 0}
            }
        backlog = []
        wiring_gaps = dynamic_implementation.get("wiring_gaps", [])
        info_gaps = dynamic_implementation.get("information_gaps", [])
        for gap in wiring_gaps:
            backlog.append({
                "id": gap.get("id"),
                "type": "wiring",
                "owner": gap.get("owner"),
                "reason": gap.get("reason")
            })
        for gap in info_gaps:
            backlog.append({
                "id": gap.get("id"),
                "type": "information",
                "owner": gap.get("owner"),
                "reason": gap.get("reason")
            })
        capability_review = capability_review or {}
        for gap in capability_review.get("gaps", []):
            backlog.append({
                "id": gap.get("id"),
                "type": "capability",
                "owner": "runtime",
                "reason": gap.get("issue")
            })
        remediation_actions = list(dict.fromkeys(dynamic_implementation.get("next_actions", [])))
        if capability_review.get("gaps") and "Review capability gaps and prioritize remediation." not in remediation_actions:
            remediation_actions.append("Review capability gaps and prioritize remediation.")
        if not remediation_actions and backlog:
            remediation_actions.append("Review self-improvement backlog and assign owners.")
        status = "ready" if not backlog else "needs_attention"
        return {
            "status": status,
            "summary": {
                "total_backlog": len(backlog),
                "wiring_gaps": len(wiring_gaps),
                "information_gaps": len(info_gaps),
                "capability_gaps": len(capability_review.get("gaps", [])),
                "corrections_logged": len(self.corrections)
            },
            "backlog": backlog,
            "remediation_actions": remediation_actions
        }

    def _apply_summary_consistency_remediation(
        self,
        self_improvement_snapshot: Dict[str, Any],
        summary_surface_consistency: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not summary_surface_consistency:
            return self_improvement_snapshot
        updated = dict(self_improvement_snapshot)
        updated["summary_surface_consistency"] = summary_surface_consistency
        backlog = list(updated.get("backlog", []))
        summary = dict(updated.get("summary", {}))
        summary["consistency_gaps"] = self._count_consistency_gaps(backlog)
        summary["total_backlog"] = len(backlog)
        updated["summary"] = summary
        if summary_surface_consistency.get("status") != "drift_detected":
            return updated
        checks = summary_surface_consistency.get("checks", {})
        failed_checks = [name for name, passed in checks.items() if not passed]
        if not failed_checks:
            return updated
        backlog.append({
            "id": "summary_surface_consistency",
            "type": "consistency",
            "owner": "runtime",
            "reason": "Summary surface consistency drift detected: " + ", ".join(sorted(failed_checks))
        })
        actions = []
        seen_actions: Set[str] = set()
        for action in updated.get("remediation_actions", []):
            if action in seen_actions:
                continue
            seen_actions.add(action)
            actions.append(action)
        drift_action = "Resolve summary surface consistency drift across preview/status/info outputs."
        if drift_action not in actions:
            actions.append(drift_action)
        summary["consistency_gaps"] = self._count_consistency_gaps(backlog)
        summary["total_backlog"] = len(backlog)
        updated["status"] = "needs_attention"
        updated["backlog"] = backlog
        updated["remediation_actions"] = actions
        updated["summary"] = summary
        return updated

    def _count_consistency_gaps(self, backlog: List[Dict[str, Any]]) -> int:
        return len([item for item in backlog if item.get("type") == "consistency"])

    def _count_completion_gaps(self, backlog: List[Dict[str, Any]]) -> int:
        return len([item for item in backlog if item.get("type") == "completion"])

    def _apply_completion_snapshot_remediation(
        self,
        self_improvement_snapshot: Dict[str, Any],
        completion_snapshot: Optional[Dict[str, Any]],
        threshold: int = 50
    ) -> Dict[str, Any]:
        if not completion_snapshot:
            return self_improvement_snapshot
        updated = dict(self_improvement_snapshot)
        updated["completion_snapshot"] = completion_snapshot
        backlog = list(updated.get("backlog", []))
        summary = dict(updated.get("summary", {}))
        threshold = int(
            completion_snapshot.get("summary", {}).get(
                "remediation_threshold_percent",
                self.COMPLETION_REMEDIATION_THRESHOLD_PERCENT
            )
        )
        summary["completion_remediation_threshold_percent"] = threshold
        summary["completion_average_percent"] = completion_snapshot.get("summary", {}).get(
            "average_percent",
            0.0
        )
        completion_gap_areas = [
            area for area in completion_snapshot.get("areas", [])
            if area.get("percent", 0) < threshold
        ]
        total_areas = int(completion_snapshot.get("summary", {}).get("total_areas", len(completion_snapshot.get("areas", []))))
        summary["completion_total_areas"] = total_areas
        summary["completion_gaps"] = len(completion_gap_areas)
        summary["completion_gap_areas"] = [area.get("area") for area in completion_gap_areas]
        summary["completion_coverage_ratio"] = (
            round((total_areas - len(completion_gap_areas)) / total_areas, 2)
            if total_areas > 0 else 0.0
        )
        if completion_gap_areas:
            for area in completion_gap_areas:
                backlog.append({
                    "id": f"completion_{area.get('area')}",
                    "type": "completion",
                    "owner": "runtime",
                    "reason": f"Completion area '{area.get('area')}' below threshold: {area.get('percent')}% < {threshold}%."
                })
            actions = list(updated.get("remediation_actions", []))
            completion_action = "Prioritize low completion areas and schedule remediation loops."
            if completion_action not in actions:
                actions.append(completion_action)
            updated["status"] = "needs_attention"
            updated["backlog"] = backlog
            updated["remediation_actions"] = actions
        summary["completion_backlog_items"] = self._count_completion_gaps(backlog)
        summary["total_backlog"] = len(backlog)
        summary["completion_backlog_ratio"] = (
            round(summary["completion_backlog_items"] / summary["total_backlog"], 2)
            if summary["total_backlog"] else 0.0
        )
        updated["summary"] = summary
        return updated

    def _build_competitive_feature_alignment(
        self,
        integration_capabilities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        log = logging.getLogger(__name__)
        status = self.module_manager.get_module_status()
        modules = status.get("modules", {})
        capability_set = {
            capability
            for info in modules.values()
            for capability in info.get("capabilities", [])
        }
        alignment = []
        integration_capabilities = integration_capabilities or self._build_integration_capabilities()
        for feature in self.COMPETITIVE_FEATURES:
            required = feature.get("capabilities", [])
            available = [cap for cap in required if cap in capability_set]
            missing = [cap for cap in required if cap not in capability_set]
            error = None
            if not required:
                coverage = 0.0
                status_value = self.COMPETITIVE_STATUS_MISSING
                error = (
                    "Configuration error: No required capabilities defined for feature "
                    f"\"{feature['id']}\". Add a \"capabilities\" list in COMPETITIVE_FEATURES."
                )
            else:
                coverage = len(available) / len(required)
                if coverage == 1.0:
                    status_value = self.COMPETITIVE_STATUS_AVAILABLE
                elif coverage == 0.0:
                    status_value = self.COMPETITIVE_STATUS_MISSING
                else:
                    status_value = self.COMPETITIVE_STATUS_PARTIAL
            entry = {
                "id": feature["id"],
                "label": feature["label"],
                "description": feature["description"],
                "status": status_value,
                "coverage": round(coverage, 2),
                "required_capabilities": required,
                "available_capabilities": available,
                "missing_capabilities": missing
            }
            if error:
                entry["error"] = error
                log.warning("Feature configuration error for %s: %s", feature["id"], error)
            if feature.get("includes_integration_metrics"):
                summary = integration_capabilities.get("summary", {})
                ready = summary.get("ready", 0)
                total = summary.get("total", 0)
                entry["integration_summary"] = summary
                if total:
                    entry["integration_coverage"] = round(ready / total, 2)
                    if ready == total:
                        entry["integration_status"] = self.COMPETITIVE_STATUS_AVAILABLE
                    elif ready == 0:
                        entry["integration_status"] = self.COMPETITIVE_STATUS_MISSING
                    else:
                        entry["integration_status"] = self.COMPETITIVE_STATUS_PARTIAL
            alignment.append(entry)
        summary = {
            "total": len(alignment),
            "available": len([f for f in alignment if f["status"] == self.COMPETITIVE_STATUS_AVAILABLE]),
            "partial": len([f for f in alignment if f["status"] == self.COMPETITIVE_STATUS_PARTIAL]),
            "missing": len([f for f in alignment if f["status"] == self.COMPETITIVE_STATUS_MISSING])
        }
        return {"summary": summary, "features": alignment}

    def _build_summary_surface_bundle(self) -> Dict[str, Any]:
        integration_capabilities = self._build_integration_capabilities()
        competitive_feature_alignment = self._build_competitive_feature_alignment(
            integration_capabilities
        )
        module_registry_summary = self._build_module_registry_summary()
        return {
            "integration_capabilities": integration_capabilities,
            "integration_capabilities_summary": integration_capabilities.get("summary", {}),
            "competitive_feature_alignment": competitive_feature_alignment,
            "competitive_feature_alignment_summary": competitive_feature_alignment.get("summary", {}),
            "module_registry_summary": module_registry_summary
        }

    def _build_completion_snapshot(self) -> Dict[str, Any]:
        areas = [
            {"area": key, "percent": value}
            for key, value in self.COMPLETION_SNAPSHOT_AREAS.items()
        ]
        threshold = self.COMPLETION_REMEDIATION_THRESHOLD_PERCENT
        low_completion_areas = sum(1 for area in areas if area["percent"] < threshold)
        return {
            "areas": areas,
            "summary": {
                "total_areas": len(areas),
                "average_percent": round(sum(item["percent"] for item in areas) / len(areas), 2) if areas else 0.0,
                "remediation_threshold_percent": threshold,
                "low_completion_areas": low_completion_areas,
                "low_completion_area_ids": [area["area"] for area in areas if area["percent"] < threshold]
            }
        }

    def _build_runtime_execution_profile(
        self,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        context = onboarding_context if isinstance(onboarding_context, dict) else {}
        answers = context.get("answers")
        # Dict-merge precedence: answer keys override context keys when both are present.
        source = {**context, **answers} if isinstance(answers, dict) else context
        execution_profile_source = "onboarding" if isinstance(onboarding_context, dict) else "default"
        text = f"{task_description} {source}".lower()
        explicit_mode = str(source.get("execution_mode", "")).lower()
        # risk_level is accepted as a legacy/synonym input for safety_level.
        safety_level = str(source.get("safety_level") or source.get("risk_level") or "standard").lower()
        risk_tolerance = str(source.get("risk_tolerance", "moderate")).lower()
        autonomy_level = str(source.get("autonomy_level", source.get("autonomy_preferences", "balanced"))).lower()
        strict_signal = (
            any(token in text for token in self.STRICT_EXECUTION_MODE_TOKENS)
            or safety_level in {"high", "strict"}
            or risk_tolerance in {"low", "conservative"}
        )
        dynamic_signal = (
            any(token in text for token in self.DYNAMIC_EXECUTION_MODE_TOKENS)
            or autonomy_level in {"high", "dynamic"}
        )
        if explicit_mode in {"strict", "balanced", "dynamic"}:
            mode = explicit_mode
        elif strict_signal:
            mode = "strict"
        elif dynamic_signal:
            mode = "dynamic"
        else:
            mode = "balanced"
        escalation_policy = source.get("escalation_policy")
        if not escalation_policy:
            escalation_policy = {
                "strict": "mandatory",
                "balanced": "selective",
                "dynamic": "on_exception"
            }.get(mode, "selective")
        audit_requirements = source.get("audit_requirements")
        if not audit_requirements:
            audit_requirements = {
                "strict": "full",
                "balanced": "standard",
                "dynamic": "minimal"
            }.get(mode, "standard")
        execution_enforcement_level = {
            "strict": "full_gate_enforcement",
            "balanced": "policy_guarded",
            "dynamic": "autonomy_accelerated"
        }.get(mode, "policy_guarded")
        control_plane_separation_state = {
            "strict": "enforced",
            "balanced": "adaptive",
            "dynamic": "relaxed"
        }.get(mode, "adaptive")
        self_improvement_rd_candidate = {
            "strict": "governed_policy_tuning_loop",
            "balanced": "hybrid_governance_feedback_loop",
            "dynamic": "autonomous_feedback_acceleration_loop"
        }.get(mode, "hybrid_governance_feedback_loop")
        approval_checkpoint_policy = {
            "strict": "mandatory",
            "balanced": "conditional",
            "dynamic": "on_demand"
        }.get(mode, "conditional")
        budget_enforcement_mode = {
            "strict": "hard_cap",
            "balanced": "soft_cap",
            "dynamic": "user_tunable"
        }.get(mode, "soft_cap")
        audit_logging_policy = {
            "strict": "immutable_full_stream",
            "balanced": "standard_governance_stream",
            "dynamic": "sampled_governance_stream"
        }.get(mode, "standard_governance_stream")
        escalation_routing_policy = {
            "strict": "mandatory_human_chain",
            "balanced": "policy_scored_chain",
            "dynamic": "exception_only_chain"
        }.get(mode, "policy_scored_chain")
        tool_mediation_policy = {
            "strict": "allowlist_mandatory_mediation",
            "balanced": "policy_guarded_mediation",
            "dynamic": "accelerated_mediation_with_guardrails"
        }.get(mode, "policy_guarded_mediation")
        deterministic_routing_policy = {
            "strict": "deterministic_only",
            "balanced": "deterministic_preferred",
            "dynamic": "deterministic_fallback"
        }.get(mode, "deterministic_preferred")
        compute_routing_policy = {
            "strict": "deterministic_compute_lane",
            "balanced": "hybrid_compute_lane",
            "dynamic": "adaptive_compute_lane"
        }.get(mode, "hybrid_compute_lane")
        policy_compiler_mode = {
            "strict": "locked_policy_compilation",
            "balanced": "guarded_policy_compilation",
            "dynamic": "adaptive_policy_compilation"
        }.get(mode, "guarded_policy_compilation")
        permission_validation_policy = {
            "strict": "explicit_role_validation",
            "balanced": "policy_guided_validation",
            "dynamic": "adaptive_validation_with_bounds"
        }.get(mode, "policy_guided_validation")
        delegation_scope_policy = {
            "strict": "role_bound_delegation_only",
            "balanced": "policy_bounded_delegation",
            "dynamic": "adaptive_delegation_with_caps"
        }.get(mode, "policy_bounded_delegation")
        execution_broker_policy = {
            "strict": "broker_hard_gate",
            "balanced": "broker_policy_guarded",
            "dynamic": "broker_adaptive_guardrailed"
        }.get(mode, "broker_policy_guarded")
        role_registry_policy = {
            "strict": "immutable_role_registry",
            "balanced": "governed_role_registry",
            "dynamic": "adaptive_role_registry_with_audit"
        }.get(mode, "governed_role_registry")
        authority_boundary_policy = {
            "strict": "hard_authority_boundaries",
            "balanced": "policy_scoped_authority_boundaries",
            "dynamic": "adaptive_authority_boundaries_with_audit"
        }.get(mode, "policy_scoped_authority_boundaries")
        cross_department_arbitration_policy = {
            "strict": "explicit_executive_arbitration",
            "balanced": "policy_scored_arbitration",
            "dynamic": "adaptive_arbitration_with_audit"
        }.get(mode, "policy_scored_arbitration")
        department_memory_isolation_policy = {
            "strict": "strict_department_isolation",
            "balanced": "policy_scoped_isolation",
            "dynamic": "adaptive_isolation_with_audit"
        }.get(mode, "policy_scoped_isolation")
        employee_contract_responsibility_policy = {
            "strict": "contract_bound_responsibilities_required",
            "balanced": "contract_guided_responsibilities",
            "dynamic": "contract_aware_adaptive_responsibilities"
        }.get(mode, "contract_guided_responsibilities")
        core_responsibility_scope = {
            "strict": "org_chart_role_and_contract_hard_boundaries",
            "balanced": "org_chart_role_and_contract_policy_boundaries",
            "dynamic": "org_chart_role_and_contract_adaptive_boundaries"
        }.get(mode, "org_chart_role_and_contract_policy_boundaries")
        shadow_agent_account_policy = {
            "strict": "identity_bound_shadow_accounts",
            "balanced": "policy_governed_shadow_accounts",
            "dynamic": "adaptive_shadow_accounts_with_audit"
        }.get(mode, "policy_governed_shadow_accounts")
        user_base_management_surface_policy = {
            "strict": "admin_ui_only",
            "balanced": "admin_ui_with_policy_api",
            "dynamic": "admin_ui_plus_delegated_api_with_audit"
        }.get(mode, "admin_ui_with_policy_api")
        employee_contract_change_authority_policy = {
            "strict": "hr_admin_approval_required",
            "balanced": "policy_scoped_manager_plus_hr_approval",
            "dynamic": "delegated_manager_updates_with_hr_audit"
        }.get(mode, "policy_scoped_manager_plus_hr_approval")
        employee_contract_management_surface_policy = {
            "strict": "hr_admin_ui_only",
            "balanced": "hr_admin_ui_with_policy_api",
            "dynamic": "hr_admin_ui_plus_delegated_api_with_audit"
        }.get(mode, "hr_admin_ui_with_policy_api")
        def _mode_policy(
            strict_value: str,
            balanced_value: str,
            dynamic_value: str
        ) -> str:
            return {
                "strict": strict_value,
                "balanced": balanced_value,
                "dynamic": dynamic_value
            }.get(mode, balanced_value)

        employee_contract_accountability_policy = _mode_policy(
            "contract_obligation_attestation_required",
            "contract_obligation_attestation_guided",
            "contract_obligation_attestation_adaptive"
        )
        shadow_agent_org_parity_policy = _mode_policy(
            "one_to_one_org_role_shadow_required",
            "policy_validated_org_role_shadowing",
            "adaptive_org_role_shadowing_with_audit"
        )
        shadow_agent_contract_binding_policy = _mode_policy(
            "contract_binding_mandatory",
            "contract_binding_policy_guided",
            "contract_binding_adaptive_with_audit"
        )
        user_base_access_governance_policy = _mode_policy(
            "rbac_and_tenant_controls_mandatory",
            "rbac_policy_governed_controls",
            "adaptive_rbac_controls_with_audit"
        )
        employee_contract_obligation_tracking_policy = _mode_policy(
            "obligation_tracking_required",
            "obligation_tracking_policy_guided",
            "obligation_tracking_adaptive_with_audit"
        )
        employee_contract_escalation_binding_policy = _mode_policy(
            "contract_escalation_binding_required",
            "contract_escalation_binding_policy_guided",
            "contract_escalation_binding_adaptive"
        )
        regulatory_context_binding_policy = _mode_policy(
            "regulatory_context_lockdown_required",
            "regulatory_context_policy_guided",
            "regulatory_context_adaptive_with_audit"
        )
        autonomy_preference_override_policy = _mode_policy(
            "autonomy_override_disabled",
            "autonomy_override_policy_scoped",
            "autonomy_override_user_tunable_with_audit"
        )
        risk_tolerance_enforcement_policy = _mode_policy(
            "low_risk_mandatory_enforcement",
            "risk_tolerance_policy_scored",
            "risk_tolerance_adaptive_with_caps"
        )
        safety_level_assurance_policy = _mode_policy(
            "safety_level_attestation_required",
            "safety_level_attestation_guided",
            "safety_level_attestation_adaptive"
        )
        delegation_comfort_governance_policy = _mode_policy(
            "delegation_comfort_hard_limits",
            "delegation_comfort_policy_bounds",
            "delegation_comfort_adaptive_bounds"
        )
        employee_contract_review_policy = _mode_policy(
            "hr_legal_review_mandatory",
            "hr_review_policy_guided",
            "adaptive_hr_review_with_audit"
        )
        employee_contract_versioning_policy = _mode_policy(
            "immutable_contract_version_history",
            "governed_contract_version_history",
            "adaptive_contract_version_history_with_audit"
        )
        shadow_agent_account_lifecycle_policy = _mode_policy(
            "hr_controlled_shadow_lifecycle",
            "policy_guided_shadow_lifecycle",
            "adaptive_shadow_lifecycle_with_audit"
        )
        user_base_ui_audit_policy = _mode_policy(
            "immutable_ui_audit_stream",
            "governed_ui_audit_stream",
            "sampled_ui_audit_stream_with_escalation"
        )
        org_chart_assignment_sync_policy = _mode_policy(
            "mandatory_org_chart_sync_before_execution",
            "policy_scoped_org_chart_sync",
            "adaptive_org_chart_sync_with_audit"
        )
        event_queue_durability_policy = _mode_policy(
            "durable_queue_required",
            "durable_queue_policy_guided",
            "durable_queue_adaptive_with_audit"
        )
        idempotency_key_enforcement_policy = _mode_policy(
            "idempotency_keys_mandatory",
            "idempotency_keys_policy_scoped",
            "idempotency_keys_adaptive_with_audit"
        )
        retry_backoff_policy = _mode_policy(
            "bounded_retry_with_manual_escalation",
            "policy_scoped_retry_backoff",
            "adaptive_retry_backoff_with_guardrails"
        )
        circuit_breaker_policy = _mode_policy(
            "circuit_breaker_hard_fail_closed",
            "circuit_breaker_policy_guarded",
            "circuit_breaker_adaptive_with_audit"
        )
        rollback_recovery_policy = _mode_policy(
            "rollback_required_on_policy_breach",
            "policy_scoped_rollback_recovery",
            "adaptive_rollback_recovery_with_audit"
        )
        planning_plane_decomposition_policy = _mode_policy(
            "hierarchical_decomposition_mandatory",
            "policy_guided_decomposition",
            "adaptive_decomposition_with_audit"
        )
        planning_plane_risk_simulation_policy = _mode_policy(
            "risk_simulation_required_before_execution",
            "risk_simulation_policy_guided",
            "adaptive_risk_simulation_with_audit"
        )
        execution_plane_permission_gate_policy = _mode_policy(
            "permission_gates_required",
            "permission_gates_policy_guided",
            "adaptive_permission_gates_with_audit"
        )
        execution_plane_budget_guardrail_policy = _mode_policy(
            "hard_budget_guardrails",
            "policy_scoped_budget_guardrails",
            "adaptive_budget_guardrails_with_audit"
        )
        execution_plane_audit_trail_integrity_policy = _mode_policy(
            "immutable_audit_trail_required",
            "governed_audit_trail_integrity",
            "adaptive_audit_trail_integrity_with_audit"
        )
        swarm_spawn_governance_policy = _mode_policy(
            "spawn_governance_preapproval_required",
            "spawn_governance_policy_scoped",
            "spawn_governance_adaptive_with_audit"
        )
        swarm_failure_containment_policy = _mode_policy(
            "failure_containment_hard_isolation",
            "failure_containment_policy_guided",
            "failure_containment_adaptive_with_audit"
        )
        swarm_budget_expansion_policy = _mode_policy(
            "swarm_budget_expansion_forbidden",
            "swarm_budget_expansion_policy_scoped",
            "swarm_budget_expansion_adaptive_with_caps"
        )
        shadow_reinforcement_signal_policy = _mode_policy(
            "shadow_reinforcement_signals_strictly_scoped",
            "shadow_reinforcement_signals_policy_guided",
            "shadow_reinforcement_signals_adaptive_with_audit"
        )
        behavioral_divergence_tracking_policy = _mode_policy(
            "behavioral_divergence_tracking_mandatory",
            "behavioral_divergence_tracking_policy_scoped",
            "behavioral_divergence_tracking_adaptive_with_audit"
        )
        planning_plane_gate_synthesis_policy = _mode_policy(
            "gate_synthesis_required_before_execution",
            "policy_guided_gate_synthesis",
            "adaptive_gate_synthesis_with_audit"
        )
        planning_plane_org_mapping_policy = _mode_policy(
            "org_mapping_lock_required",
            "policy_scoped_org_mapping",
            "adaptive_org_mapping_with_audit"
        )
        execution_plane_tool_permission_enforcement_policy = _mode_policy(
            "tool_permission_enforcement_mandatory",
            "policy_scoped_tool_permission_enforcement",
            "adaptive_tool_permission_enforcement_with_audit"
        )
        execution_plane_budget_ceiling_override_policy = _mode_policy(
            "budget_ceiling_override_forbidden",
            "budget_ceiling_override_policy_scoped",
            "budget_ceiling_override_adaptive_with_audit"
        )
        execution_plane_escalation_checkpoint_policy = _mode_policy(
            "escalation_checkpoint_required",
            "escalation_checkpoint_policy_guided",
            "escalation_checkpoint_adaptive_with_audit"
        )
        human_in_the_loop_enforcement_policy = _mode_policy(
            "human_in_the_loop_enforcement_mandatory",
            "human_in_the_loop_enforcement_policy_guided",
            "human_in_the_loop_enforcement_adaptive_with_audit"
        )
        regulatory_audit_retention_policy = _mode_policy(
            "regulatory_audit_retention_mandatory",
            "regulatory_audit_retention_policy_scoped",
            "regulatory_audit_retention_adaptive_with_audit"
        )
        tenant_boundary_enforcement_policy = _mode_policy(
            "tenant_boundary_enforcement_required",
            "tenant_boundary_enforcement_policy_scoped",
            "tenant_boundary_enforcement_adaptive_with_audit"
        )
        policy_exception_handling_policy = _mode_policy(
            "policy_exception_handling_manual_review_only",
            "policy_exception_handling_governed_review",
            "policy_exception_handling_adaptive_with_audit"
        )
        runtime_profile_refresh_policy = _mode_policy(
            "runtime_profile_refresh_pre_execution_required",
            "runtime_profile_refresh_policy_guided",
            "runtime_profile_refresh_adaptive_with_audit"
        )
        planning_plane_compliance_modeling_policy = _mode_policy(
            "compliance_modeling_required_before_execution",
            "compliance_modeling_policy_guided",
            "compliance_modeling_adaptive_with_audit"
        )
        planning_plane_proposal_generation_policy = _mode_policy(
            "proposal_generation_policy_gated",
            "proposal_generation_policy_scoped",
            "proposal_generation_adaptive_with_audit"
        )
        execution_plane_policy_compiler_enforcement_policy = _mode_policy(
            "execution_policy_compiler_enforcement_required",
            "execution_policy_compiler_enforcement_scoped",
            "execution_policy_compiler_enforcement_adaptive_with_audit"
        )
        execution_plane_deterministic_override_policy = _mode_policy(
            "deterministic_override_required_for_high_risk",
            "deterministic_override_policy_scoped",
            "deterministic_override_adaptive_with_audit"
        )
        hitl_escalation_requirement_policy = _mode_policy(
            "hitl_escalation_requirement_hard",
            "hitl_escalation_requirement_policy_guided",
            "hitl_escalation_requirement_adaptive_with_audit"
        )
        shadow_peer_role_enforcement_policy = _mode_policy(
            "shadow_peer_role_enforcement_mandatory",
            "shadow_peer_role_enforcement_policy_guided",
            "shadow_peer_role_enforcement_adaptive_with_audit"
        )
        shadow_account_user_binding_policy = _mode_policy(
            "shadow_account_user_binding_mandatory",
            "shadow_account_user_binding_policy_guided",
            "shadow_account_user_binding_adaptive_with_audit"
        )
        employee_contract_scope_enforcement_policy = _mode_policy(
            "employee_contract_scope_enforcement_required",
            "employee_contract_scope_enforcement_policy_guided",
            "employee_contract_scope_enforcement_adaptive_with_audit"
        )
        employee_contract_exception_review_policy = _mode_policy(
            "employee_contract_exception_review_mandatory",
            "employee_contract_exception_review_policy_guided",
            "employee_contract_exception_review_adaptive_with_audit"
        )
        user_base_tenant_boundary_policy = _mode_policy(
            "user_base_tenant_boundary_enforcement_required",
            "user_base_tenant_boundary_policy_scoped",
            "user_base_tenant_boundary_adaptive_with_audit"
        )
        compliance_event_escalation_policy = _mode_policy(
            "compliance_event_escalation_immediate",
            "compliance_event_escalation_policy_guided",
            "compliance_event_escalation_adaptive_with_audit"
        )
        regulatory_override_resolution_policy = _mode_policy(
            "regulatory_override_resolution_manual_only",
            "regulatory_override_resolution_policy_scoped",
            "regulatory_override_resolution_adaptive_with_audit"
        )
        budget_ceiling_revision_policy = _mode_policy(
            "budget_ceiling_revision_manual_approval_only",
            "budget_ceiling_revision_policy_scoped",
            "budget_ceiling_revision_adaptive_with_audit"
        )
        budget_consumption_alert_policy = _mode_policy(
            "budget_consumption_alert_realtime_required",
            "budget_consumption_alert_policy_guided",
            "budget_consumption_alert_adaptive_with_audit"
        )
        approval_checkpoint_timeout_policy = _mode_policy(
            "approval_checkpoint_timeout_hard_stop",
            "approval_checkpoint_timeout_policy_scoped",
            "approval_checkpoint_timeout_adaptive_with_audit"
        )
        compliance_sensor_event_policy = _mode_policy(
            "compliance_sensor_events_mandatory",
            "compliance_sensor_events_policy_scoped",
            "compliance_sensor_events_adaptive_with_audit"
        )
        policy_drift_detection_policy = _mode_policy(
            "policy_drift_detection_hard_gate",
            "policy_drift_detection_governed_review",
            "policy_drift_detection_adaptive_with_audit"
        )
        onboarding_profile_revalidation_policy = _mode_policy(
            "onboarding_profile_revalidation_required_before_execution",
            "onboarding_profile_revalidation_policy_scoped",
            "onboarding_profile_revalidation_adaptive_with_audit"
        )
        control_plane_mode_transition_policy = _mode_policy(
            "control_plane_mode_transition_manual_approval_required",
            "control_plane_mode_transition_policy_scoped",
            "control_plane_mode_transition_adaptive_with_audit"
        )
        user_autonomy_preference_ui_policy = _mode_policy(
            "user_autonomy_preference_ui_restricted",
            "user_autonomy_preference_ui_policy_scoped",
            "user_autonomy_preference_ui_adaptive_with_audit"
        )
        planning_execution_toggle_guard_policy = _mode_policy(
            "planning_execution_toggle_manual_approval_required",
            "planning_execution_toggle_policy_scoped",
            "planning_execution_toggle_adaptive_with_audit"
        )
        governance_exception_escalation_policy = _mode_policy(
            "governance_exception_escalation_immediate",
            "governance_exception_escalation_policy_guided",
            "governance_exception_escalation_adaptive_with_audit"
        )
        approval_sla_enforcement_policy = _mode_policy(
            "approval_sla_enforcement_hard_deadline",
            "approval_sla_enforcement_policy_scoped",
            "approval_sla_enforcement_adaptive_with_audit"
        )
        tenant_residency_control_policy = _mode_policy(
            "tenant_residency_control_hard_enforced",
            "tenant_residency_control_policy_scoped",
            "tenant_residency_control_adaptive_with_audit"
        )
        swarm_recursion_guard_policy = _mode_policy(
            "swarm_recursion_guard_hard_limit",
            "swarm_recursion_guard_policy_scoped",
            "swarm_recursion_guard_adaptive_with_audit"
        )
        contract_renewal_gate_policy = _mode_policy(
            "contract_renewal_gate_required",
            "contract_renewal_gate_policy_scoped",
            "contract_renewal_gate_adaptive_with_audit"
        )
        shadow_account_suspension_policy = _mode_policy(
            "shadow_account_suspension_manual_approval_required",
            "shadow_account_suspension_policy_scoped",
            "shadow_account_suspension_adaptive_with_audit"
        )
        user_base_offboarding_policy = _mode_policy(
            "user_base_offboarding_workflow_required",
            "user_base_offboarding_policy_scoped",
            "user_base_offboarding_adaptive_with_audit"
        )
        governance_kernel_heartbeat_policy = _mode_policy(
            "governance_kernel_heartbeat_hard_monitoring",
            "governance_kernel_heartbeat_policy_scoped",
            "governance_kernel_heartbeat_adaptive_with_audit"
        )
        policy_compiler_change_control_policy = _mode_policy(
            "policy_compiler_change_control_manual_review_required",
            "policy_compiler_change_control_policy_scoped",
            "policy_compiler_change_control_adaptive_with_audit"
        )
        replay_reconciliation_policy = _mode_policy(
            "replay_reconciliation_required",
            "replay_reconciliation_policy_scoped",
            "replay_reconciliation_adaptive_with_audit"
        )
        audit_artifact_retention_policy = _mode_policy(
            "audit_artifact_retention_required",
            "audit_artifact_retention_policy_scoped",
            "audit_artifact_retention_adaptive_with_audit"
        )
        event_backpressure_management_policy = _mode_policy(
            "event_backpressure_management_required",
            "event_backpressure_management_policy_scoped",
            "event_backpressure_management_adaptive_with_audit"
        )
        queue_health_slo_policy = _mode_policy(
            "queue_health_slo_hard_enforced",
            "queue_health_slo_policy_scoped",
            "queue_health_slo_adaptive_with_audit"
        )
        rollback_compensation_policy = _mode_policy(
            "rollback_compensation_required",
            "rollback_compensation_policy_scoped",
            "rollback_compensation_adaptive_with_audit"
        )
        durable_queue_replay_policy = _mode_policy(
            "durable_queue_replay_required",
            "durable_queue_replay_policy_scoped",
            "durable_queue_replay_adaptive_with_audit"
        )
        swarm_failure_domain_isolation_policy = _mode_policy(
            "swarm_failure_domain_isolation_required",
            "swarm_failure_domain_isolation_policy_scoped",
            "swarm_failure_domain_isolation_adaptive_with_audit"
        )
        idempotent_recovery_validation_policy = _mode_policy(
            "idempotent_recovery_validation_required",
            "idempotent_recovery_validation_policy_scoped",
            "idempotent_recovery_validation_adaptive_with_audit"
        )
        agent_spawn_budget_reconciliation_policy = _mode_policy(
            "agent_spawn_budget_reconciliation_required",
            "agent_spawn_budget_reconciliation_policy_scoped",
            "agent_spawn_budget_reconciliation_adaptive_with_audit"
        )
        audit_chain_export_policy = _mode_policy(
            "audit_chain_export_required",
            "audit_chain_export_policy_scoped",
            "audit_chain_export_adaptive_with_audit"
        )
        semantics_belief_state_policy = _mode_policy(
            "structured_spec_hypothesis_belief_required",
            "structured_spec_hypothesis_belief_policy_scoped",
            "structured_spec_hypothesis_belief_adaptive_with_audit"
        )
        semantics_loss_risk_policy = _mode_policy(
            "loss_and_cvar_risk_evaluation_required",
            "loss_and_cvar_risk_evaluation_policy_scoped",
            "loss_and_cvar_risk_evaluation_adaptive_with_audit"
        )
        semantics_voi_question_policy = _mode_policy(
            "voi_questioning_required_before_high_risk_action",
            "voi_questioning_policy_scoped",
            "voi_questioning_adaptive_with_audit"
        )
        semantics_invariance_boundary_policy = _mode_policy(
            "invariance_commutation_gate_required",
            "invariance_commutation_policy_scoped",
            "invariance_commutation_adaptive_with_audit"
        )
        semantics_verification_feedback_policy = _mode_policy(
            "verification_feedback_loop_required",
            "verification_feedback_policy_scoped",
            "verification_feedback_adaptive_with_audit"
        )
        semantics_hypothesis_update_policy = _mode_policy(
            "belief_hypothesis_posterior_update_required",
            "belief_hypothesis_posterior_update_policy_scoped",
            "belief_hypothesis_posterior_update_adaptive_with_audit"
        )
        semantics_likelihood_scoring_policy = _mode_policy(
            "answer_likelihood_scoring_required",
            "answer_likelihood_scoring_policy_scoped",
            "answer_likelihood_scoring_adaptive_with_audit"
        )
        semantics_rvoi_decision_policy = _mode_policy(
            "rvoi_question_decision_required",
            "rvoi_question_decision_policy_scoped",
            "rvoi_question_decision_adaptive_with_audit"
        )
        semantics_clarifying_question_budget_policy = _mode_policy(
            "clarifying_question_budget_enforced",
            "clarifying_question_budget_policy_scoped",
            "clarifying_question_budget_adaptive_with_audit"
        )
        semantics_invariance_retry_policy = _mode_policy(
            "invariance_retry_or_ask_required",
            "invariance_retry_or_ask_policy_scoped",
            "invariance_retry_or_ask_adaptive_with_audit"
        )
        semantics_hypothesis_distribution_policy = _mode_policy(
            "structured_hypothesis_distribution_required",
            "structured_hypothesis_distribution_policy_scoped",
            "structured_hypothesis_distribution_adaptive_with_audit"
        )
        semantics_cvar_risk_measure_policy = _mode_policy(
            "expected_loss_and_cvar_required",
            "expected_loss_and_cvar_policy_scoped",
            "expected_loss_and_cvar_adaptive_with_audit"
        )
        semantics_question_cost_policy = _mode_policy(
            "question_cost_and_voi_threshold_required",
            "question_cost_and_voi_threshold_policy_scoped",
            "question_cost_and_voi_threshold_adaptive_with_audit"
        )
        semantics_invariance_transform_set_policy = _mode_policy(
            "invariance_transform_set_required",
            "invariance_transform_set_policy_scoped",
            "invariance_transform_set_adaptive_with_audit"
        )
        semantics_verification_boundary_policy = _mode_policy(
            "verification_boundary_enforcement_required",
            "verification_boundary_enforcement_policy_scoped",
            "verification_boundary_enforcement_adaptive_with_audit"
        )
        runtime_telemetry_tokens_to_resolution_policy = _mode_policy(
            "telemetry_tokens_to_resolution_required",
            "telemetry_tokens_to_resolution_policy_scoped",
            "telemetry_tokens_to_resolution_adaptive_with_audit"
        )
        runtime_telemetry_question_count_policy = _mode_policy(
            "telemetry_question_count_required",
            "telemetry_question_count_policy_scoped",
            "telemetry_question_count_adaptive_with_audit"
        )
        runtime_telemetry_invariance_score_policy = _mode_policy(
            "telemetry_invariance_score_required",
            "telemetry_invariance_score_policy_scoped",
            "telemetry_invariance_score_adaptive_with_audit"
        )
        runtime_telemetry_risk_score_policy = _mode_policy(
            "telemetry_risk_score_required",
            "telemetry_risk_score_policy_scoped",
            "telemetry_risk_score_adaptive_with_audit"
        )
        runtime_telemetry_verification_feedback_policy = _mode_policy(
            "telemetry_verification_feedback_required",
            "telemetry_verification_feedback_policy_scoped",
            "telemetry_verification_feedback_adaptive_with_audit"
        )
        semantics_question_candidate_generation_policy = _mode_policy(
            "semantics_question_candidate_generation_required",
            "semantics_question_candidate_generation_policy_scoped",
            "semantics_question_candidate_generation_adaptive_with_audit"
        )
        semantics_answer_prediction_policy = _mode_policy(
            "semantics_answer_prediction_required",
            "semantics_answer_prediction_policy_scoped",
            "semantics_answer_prediction_adaptive_with_audit"
        )
        semantics_belief_normalization_policy = _mode_policy(
            "semantics_belief_normalization_required",
            "semantics_belief_normalization_policy_scoped",
            "semantics_belief_normalization_adaptive_with_audit"
        )
        semantics_verification_loss_injection_policy = _mode_policy(
            "semantics_verification_loss_injection_required",
            "semantics_verification_loss_injection_policy_scoped",
            "semantics_verification_loss_injection_adaptive_with_audit"
        )
        semantics_action_revision_policy = _mode_policy(
            "semantics_action_revision_required",
            "semantics_action_revision_policy_scoped",
            "semantics_action_revision_adaptive_with_audit"
        )
        legacy_orchestrator_discovery_policy = _mode_policy(
            "legacy_orchestrator_inventory_required",
            "legacy_orchestrator_inventory_policy_scoped",
            "legacy_orchestrator_inventory_adaptive_with_audit"
        )
        rubixcube_orchestrator_adapter_policy = _mode_policy(
            "rubixcube_adapter_wiring_required",
            "rubixcube_adapter_wiring_policy_scoped",
            "rubixcube_adapter_wiring_adaptive_with_audit"
        )
        triage_orchestrator_adapter_policy = _mode_policy(
            "triage_adapter_wiring_required",
            "triage_adapter_wiring_policy_scoped",
            "triage_adapter_wiring_adaptive_with_audit"
        )
        bot_catalog_capability_mapping_policy = _mode_policy(
            "bot_catalog_capability_mapping_required",
            "bot_catalog_capability_mapping_policy_scoped",
            "bot_catalog_capability_mapping_adaptive_with_audit"
        )
        legacy_orchestrator_wiring_priority_policy = _mode_policy(
            "legacy_orchestrator_wiring_priority_required",
            "legacy_orchestrator_wiring_priority_policy_scoped",
            "legacy_orchestrator_wiring_priority_adaptive_with_audit"
        )
        modern_arcana_clockwork_bridge_policy = _mode_policy(
            "modern_arcana_clockwork_bridge_required",
            "modern_arcana_clockwork_bridge_policy_scoped",
            "modern_arcana_clockwork_bridge_adaptive_with_audit"
        )
        legacy_orchestrator_compatibility_matrix_policy = _mode_policy(
            "legacy_orchestrator_compatibility_matrix_required",
            "legacy_orchestrator_compatibility_matrix_policy_scoped",
            "legacy_orchestrator_compatibility_matrix_adaptive_with_audit"
        )
        rubixcube_kaia_mix_scoring_policy = _mode_policy(
            "rubixcube_kaia_mix_scoring_required",
            "rubixcube_kaia_mix_scoring_policy_scoped",
            "rubixcube_kaia_mix_scoring_adaptive_with_audit"
        )
        triage_rollcall_selection_policy = _mode_policy(
            "triage_rollcall_selection_required",
            "triage_rollcall_selection_policy_scoped",
            "triage_rollcall_selection_adaptive_with_audit"
        )
        legacy_orchestrator_tooling_plan_policy = _mode_policy(
            "legacy_orchestrator_tooling_plan_required",
            "legacy_orchestrator_tooling_plan_policy_scoped",
            "legacy_orchestrator_tooling_plan_adaptive_with_audit"
        )
        clockwork_orchestrator_bridge_policy = _mode_policy(
            "clockwork_orchestrator_bridge_required",
            "clockwork_orchestrator_bridge_policy_scoped",
            "clockwork_orchestrator_bridge_adaptive_with_audit"
        )
        arcana_pipeline_compatibility_policy = _mode_policy(
            "arcana_pipeline_compatibility_required",
            "arcana_pipeline_compatibility_policy_scoped",
            "arcana_pipeline_compatibility_adaptive_with_audit"
        )
        rubixcube_evidence_engine_policy = _mode_policy(
            "rubixcube_evidence_engine_required",
            "rubixcube_evidence_engine_policy_scoped",
            "rubixcube_evidence_engine_adaptive_with_audit"
        )
        triage_rollcall_confidence_policy = _mode_policy(
            "triage_rollcall_confidence_required",
            "triage_rollcall_confidence_policy_scoped",
            "triage_rollcall_confidence_adaptive_with_audit"
        )
        golden_path_reuse_policy = _mode_policy(
            "golden_path_reuse_required",
            "golden_path_reuse_policy_scoped",
            "golden_path_reuse_adaptive_with_audit"
        )
        governance_review_cadence_policy = _mode_policy(
            "governance_review_cadence_required",
            "governance_review_cadence_policy_scoped",
            "governance_review_cadence_adaptive_with_audit"
        )
        section_status_reconciliation_policy = _mode_policy(
            "section_status_reconciliation_required",
            "section_status_reconciliation_policy_scoped",
            "section_status_reconciliation_adaptive_with_audit"
        )
        orchestrator_wiring_readiness_policy = _mode_policy(
            "orchestrator_wiring_readiness_required",
            "orchestrator_wiring_readiness_policy_scoped",
            "orchestrator_wiring_readiness_adaptive_with_audit"
        )
        verification_feedback_closure_policy = _mode_policy(
            "verification_feedback_closure_required",
            "verification_feedback_closure_policy_scoped",
            "verification_feedback_closure_adaptive_with_audit"
        )
        self_improvement_backlog_priority_policy = _mode_policy(
            "self_improvement_backlog_priority_required",
            "self_improvement_backlog_priority_policy_scoped",
            "self_improvement_backlog_priority_adaptive_with_audit"
        )
        assessment_section_coverage_policy = _mode_policy(
            "assessment_section_coverage_required",
            "assessment_section_coverage_policy_scoped",
            "assessment_section_coverage_adaptive_with_audit"
        )
        assessment_recommendation_acceptance_policy = _mode_policy(
            "assessment_recommendation_acceptance_required",
            "assessment_recommendation_acceptance_policy_scoped",
            "assessment_recommendation_acceptance_adaptive_with_audit"
        )
        assessment_standardization_governance_policy = _mode_policy(
            "assessment_standardization_governance_required",
            "assessment_standardization_governance_policy_scoped",
            "assessment_standardization_governance_adaptive_with_audit"
        )
        assessment_progression_loop_policy = _mode_policy(
            "assessment_progression_loop_required",
            "assessment_progression_loop_policy_scoped",
            "assessment_progression_loop_adaptive_with_audit"
        )
        assessment_readme_assessment_sync_policy = _mode_policy(
            "assessment_readme_assessment_sync_required",
            "assessment_readme_assessment_sync_policy_scoped",
            "assessment_readme_assessment_sync_adaptive_with_audit"
        )
        process_gate_iteration_policy = _mode_policy(
            "process_gate_iteration_required",
            "process_gate_iteration_policy_scoped",
            "process_gate_iteration_adaptive_with_audit"
        )
        process_followup_testing_loop_policy = _mode_policy(
            "process_followup_testing_loop_required",
            "process_followup_testing_loop_policy_scoped",
            "process_followup_testing_loop_adaptive_with_audit"
        )
        process_section_sync_audit_policy = _mode_policy(
            "process_section_sync_audit_required",
            "process_section_sync_audit_policy_scoped",
            "process_section_sync_audit_adaptive_with_audit"
        )
        process_readme_update_enforcement_policy = _mode_policy(
            "process_readme_update_enforcement_required",
            "process_readme_update_enforcement_policy_scoped",
            "process_readme_update_enforcement_adaptive_with_audit"
        )
        process_standardization_hygiene_policy = _mode_policy(
            "process_standardization_hygiene_required",
            "process_standardization_hygiene_policy_scoped",
            "process_standardization_hygiene_adaptive_with_audit"
        )
        full_section_coverage_audit_policy = _mode_policy(
            "full_section_coverage_audit_required",
            "full_section_coverage_audit_policy_scoped",
            "full_section_coverage_audit_adaptive_with_audit"
        )
        recommendation_acceptance_trace_policy = _mode_policy(
            "recommendation_acceptance_trace_required",
            "recommendation_acceptance_trace_policy_scoped",
            "recommendation_acceptance_trace_adaptive_with_audit"
        )
        iterative_test_loop_enforcement_policy = _mode_policy(
            "iterative_test_loop_enforcement_required",
            "iterative_test_loop_enforcement_policy_scoped",
            "iterative_test_loop_enforcement_adaptive_with_audit"
        )
        readme_assessment_consistency_policy = _mode_policy(
            "readme_assessment_consistency_required",
            "readme_assessment_consistency_policy_scoped",
            "readme_assessment_consistency_adaptive_with_audit"
        )
        standardization_terminology_lock_policy = _mode_policy(
            "standardization_terminology_lock_required",
            "standardization_terminology_lock_policy_scoped",
            "standardization_terminology_lock_adaptive_with_audit"
        )
        section_transition_handoff_policy = _mode_policy(
            "section_transition_handoff_required",
            "section_transition_handoff_policy_scoped",
            "section_transition_handoff_adaptive_with_audit"
        )
        section_evidence_traceability_policy = _mode_policy(
            "section_evidence_traceability_required",
            "section_evidence_traceability_policy_scoped",
            "section_evidence_traceability_adaptive_with_audit"
        )
        section_recommendation_closure_policy = _mode_policy(
            "section_recommendation_closure_required",
            "section_recommendation_closure_policy_scoped",
            "section_recommendation_closure_adaptive_with_audit"
        )
        section_quality_gate_policy = _mode_policy(
            "section_quality_gate_required",
            "section_quality_gate_policy_scoped",
            "section_quality_gate_adaptive_with_audit"
        )
        section_snapshot_publication_policy = _mode_policy(
            "section_snapshot_publication_required",
            "section_snapshot_publication_policy_scoped",
            "section_snapshot_publication_adaptive_with_audit"
        )
        all_section_review_coverage_policy = _mode_policy(
            "all_section_review_coverage_required",
            "all_section_review_coverage_policy_scoped",
            "all_section_review_coverage_adaptive_with_audit"
        )
        all_section_recommendation_acceptance_policy = _mode_policy(
            "all_section_recommendation_acceptance_required",
            "all_section_recommendation_acceptance_policy_scoped",
            "all_section_recommendation_acceptance_adaptive_with_audit"
        )
        all_section_progression_gate_policy = _mode_policy(
            "all_section_progression_gate_required",
            "all_section_progression_gate_policy_scoped",
            "all_section_progression_gate_adaptive_with_audit"
        )
        all_section_standardization_lock_policy = _mode_policy(
            "all_section_standardization_lock_required",
            "all_section_standardization_lock_policy_scoped",
            "all_section_standardization_lock_adaptive_with_audit"
        )
        all_section_reporting_sync_policy = _mode_policy(
            "all_section_reporting_sync_required",
            "all_section_reporting_sync_policy_scoped",
            "all_section_reporting_sync_adaptive_with_audit"
        )
        recommendation_acceptance_attestation_policy = _mode_policy(
            "recommendation_acceptance_attestation_required",
            "recommendation_acceptance_attestation_policy_scoped",
            "recommendation_acceptance_attestation_adaptive_with_audit"
        )
        recommendation_execution_checkpoint_policy = _mode_policy(
            "recommendation_execution_checkpoint_required",
            "recommendation_execution_checkpoint_policy_scoped",
            "recommendation_execution_checkpoint_adaptive_with_audit"
        )
        recommendation_test_evidence_policy = _mode_policy(
            "recommendation_test_evidence_required",
            "recommendation_test_evidence_policy_scoped",
            "recommendation_test_evidence_adaptive_with_audit"
        )
        recommendation_section_sync_policy = _mode_policy(
            "recommendation_section_sync_required",
            "recommendation_section_sync_policy_scoped",
            "recommendation_section_sync_adaptive_with_audit"
        )
        recommendation_completion_report_policy = _mode_policy(
            "recommendation_completion_report_required",
            "recommendation_completion_report_policy_scoped",
            "recommendation_completion_report_adaptive_with_audit"
        )
        section_1_to_14_continuity_policy = _mode_policy(
            "section_1_to_14_continuity_required",
            "section_1_to_14_continuity_policy_scoped",
            "section_1_to_14_continuity_adaptive_with_audit"
        )
        section_recommendation_acceptance_audit_policy = _mode_policy(
            "section_recommendation_acceptance_audit_required",
            "section_recommendation_acceptance_audit_policy_scoped",
            "section_recommendation_acceptance_audit_adaptive_with_audit"
        )
        section_recommendation_implementation_trace_policy = _mode_policy(
            "section_recommendation_implementation_trace_required",
            "section_recommendation_implementation_trace_policy_scoped",
            "section_recommendation_implementation_trace_adaptive_with_audit"
        )
        section_followup_test_loop_policy = _mode_policy(
            "section_followup_test_loop_required",
            "section_followup_test_loop_policy_scoped",
            "section_followup_test_loop_adaptive_with_audit"
        )
        section_readme_assessment_lockstep_policy = _mode_policy(
            "section_readme_assessment_lockstep_required",
            "section_readme_assessment_lockstep_policy_scoped",
            "section_readme_assessment_lockstep_adaptive_with_audit"
        )
        section_completion_delta_reporting_policy = _mode_policy(
            "section_completion_delta_reporting_required",
            "section_completion_delta_reporting_policy_scoped",
            "section_completion_delta_reporting_adaptive_with_audit"
        )
        section_micro_build_tracking_policy = _mode_policy(
            "section_micro_build_tracking_required",
            "section_micro_build_tracking_policy_scoped",
            "section_micro_build_tracking_adaptive_with_audit"
        )
        section_prompt_increment_logging_policy = _mode_policy(
            "section_prompt_increment_logging_required",
            "section_prompt_increment_logging_policy_scoped",
            "section_prompt_increment_logging_adaptive_with_audit"
        )
        section_recommendation_acceptance_evidence_policy = _mode_policy(
            "section_recommendation_acceptance_evidence_required",
            "section_recommendation_acceptance_evidence_policy_scoped",
            "section_recommendation_acceptance_evidence_adaptive_with_audit"
        )
        section_change_budget_tracking_policy = _mode_policy(
            "section_change_budget_tracking_required",
            "section_change_budget_tracking_policy_scoped",
            "section_change_budget_tracking_adaptive_with_audit"
        )
        section_test_result_reporting_policy = _mode_policy(
            "section_test_result_reporting_required",
            "section_test_result_reporting_policy_scoped",
            "section_test_result_reporting_adaptive_with_audit"
        )
        section_warning_budget_policy = _mode_policy(
            "section_warning_budget_enforced",
            "section_warning_budget_policy_scoped",
            "section_warning_budget_adaptive_with_audit"
        )
        section_retest_trigger_policy = _mode_policy(
            "section_retest_trigger_required",
            "section_retest_trigger_policy_scoped",
            "section_retest_trigger_adaptive_with_audit"
        )
        section_documentation_accuracy_policy = _mode_policy(
            "section_documentation_accuracy_required",
            "section_documentation_accuracy_policy_scoped",
            "section_documentation_accuracy_adaptive_with_audit"
        )
        section_loop_exit_criteria_policy = _mode_policy(
            "section_loop_exit_criteria_required",
            "section_loop_exit_criteria_policy_scoped",
            "section_loop_exit_criteria_adaptive_with_audit"
        )
        section_recommendation_priority_policy = _mode_policy(
            "section_recommendation_priority_required",
            "section_recommendation_priority_policy_scoped",
            "section_recommendation_priority_adaptive_with_audit"
        )
        section_recommendation_dependency_policy = _mode_policy(
            "section_recommendation_dependency_required",
            "section_recommendation_dependency_policy_scoped",
            "section_recommendation_dependency_adaptive_with_audit"
        )
        section_risk_escalation_policy = _mode_policy(
            "section_risk_escalation_required",
            "section_risk_escalation_policy_scoped",
            "section_risk_escalation_adaptive_with_audit"
        )
        section_completion_signoff_policy = _mode_policy(
            "section_completion_signoff_required",
            "section_completion_signoff_policy_scoped",
            "section_completion_signoff_adaptive_with_audit"
        )
        section_continuous_improvement_policy = _mode_policy(
            "section_continuous_improvement_required",
            "section_continuous_improvement_policy_scoped",
            "section_continuous_improvement_adaptive_with_audit"
        )
        section_recommendation_conflict_resolution_policy = _mode_policy(
            "section_recommendation_conflict_resolution_required",
            "section_recommendation_conflict_resolution_policy_scoped",
            "section_recommendation_conflict_resolution_adaptive_with_audit"
        )
        section_dependency_unblock_policy = _mode_policy(
            "section_dependency_unblock_required",
            "section_dependency_unblock_policy_scoped",
            "section_dependency_unblock_adaptive_with_audit"
        )
        section_regression_guard_policy = _mode_policy(
            "section_regression_guard_required",
            "section_regression_guard_policy_scoped",
            "section_regression_guard_adaptive_with_audit"
        )
        section_release_readiness_policy = _mode_policy(
            "section_release_readiness_required",
            "section_release_readiness_policy_scoped",
            "section_release_readiness_adaptive_with_audit"
        )
        section_traceability_index_policy = _mode_policy(
            "section_traceability_index_required",
            "section_traceability_index_policy_scoped",
            "section_traceability_index_adaptive_with_audit"
        )
        section_acceptance_criteria_enforcement_policy = _mode_policy(
            "section_acceptance_criteria_enforcement_required",
            "section_acceptance_criteria_enforcement_policy_scoped",
            "section_acceptance_criteria_enforcement_adaptive_with_audit"
        )
        section_artifact_quality_review_policy = _mode_policy(
            "section_artifact_quality_review_required",
            "section_artifact_quality_review_policy_scoped",
            "section_artifact_quality_review_adaptive_with_audit"
        )
        section_retest_on_change_policy = _mode_policy(
            "section_retest_on_change_required",
            "section_retest_on_change_policy_scoped",
            "section_retest_on_change_adaptive_with_audit"
        )
        section_documentation_trace_policy = _mode_policy(
            "section_documentation_trace_required",
            "section_documentation_trace_policy_scoped",
            "section_documentation_trace_adaptive_with_audit"
        )
        section_release_gate_attestation_policy = _mode_policy(
            "section_release_gate_attestation_required",
            "section_release_gate_attestation_policy_scoped",
            "section_release_gate_attestation_adaptive_with_audit"
        )
        section_dependency_health_policy = _mode_policy(
            "section_dependency_health_gate_required",
            "section_dependency_health_policy_scoped",
            "section_dependency_health_adaptive_with_audit"
        )
        section_recommendation_sla_policy = _mode_policy(
            "section_recommendation_sla_required",
            "section_recommendation_sla_policy_scoped",
            "section_recommendation_sla_adaptive_with_audit"
        )
        section_documentation_sync_policy = _mode_policy(
            "section_documentation_sync_required",
            "section_documentation_sync_policy_scoped",
            "section_documentation_sync_adaptive_with_audit"
        )
        section_validation_signal_policy = _mode_policy(
            "section_validation_signal_required",
            "section_validation_signal_policy_scoped",
            "section_validation_signal_adaptive_with_audit"
        )
        section_handoff_audit_policy = _mode_policy(
            "section_handoff_audit_required",
            "section_handoff_audit_policy_scoped",
            "section_handoff_audit_adaptive_with_audit"
        )

        section_change_control_policy = _mode_policy(
            "section_change_control_required",
            "section_change_control_policy_scoped",
            "section_change_control_adaptive_with_audit"
        )
        section_quality_drift_policy = _mode_policy(
            "section_quality_drift_monitoring_required",
            "section_quality_drift_policy_scoped",
            "section_quality_drift_adaptive_with_audit"
        )
        section_verification_retry_policy = _mode_policy(
            "section_verification_retry_required",
            "section_verification_retry_policy_scoped",
            "section_verification_retry_adaptive_with_audit"
        )
        section_governance_exception_budget_policy = _mode_policy(
            "section_governance_exception_budget_required",
            "section_governance_exception_budget_policy_scoped",
            "section_governance_exception_budget_adaptive_with_audit"
        )
        section_release_documentation_gate_policy = _mode_policy(
            "section_release_documentation_gate_required",
            "section_release_documentation_gate_policy_scoped",
            "section_release_documentation_gate_adaptive_with_audit"
        )
        section_contract_compliance_link_policy = _mode_policy(
            "section_contract_compliance_link_required",
            "section_contract_compliance_link_policy_scoped",
            "section_contract_compliance_link_adaptive_with_audit"
        )
        section_cost_center_attribution_policy = _mode_policy(
            "section_cost_center_attribution_required",
            "section_cost_center_attribution_policy_scoped",
            "section_cost_center_attribution_adaptive_with_audit"
        )
        section_unowned_work_throwback_policy = _mode_policy(
            "section_unowned_work_throwback_required",
            "section_unowned_work_throwback_policy_scoped",
            "section_unowned_work_throwback_adaptive_with_audit"
        )
        section_change_order_trigger_policy = _mode_policy(
            "section_change_order_trigger_required",
            "section_change_order_trigger_policy_scoped",
            "section_change_order_trigger_adaptive_with_audit"
        )
        section_manager_assignment_policy = _mode_policy(
            "section_manager_assignment_required",
            "section_manager_assignment_policy_scoped",
            "section_manager_assignment_adaptive_with_audit"
        )
        section_enterprise_operating_model_policy = _mode_policy(
            "section_enterprise_operating_model_alignment_required",
            "section_enterprise_operating_model_policy_scoped",
            "section_enterprise_operating_model_adaptive_with_audit"
        )
        section_unaccounted_work_classification_policy = _mode_policy(
            "section_unaccounted_work_classification_required",
            "section_unaccounted_work_classification_policy_scoped",
            "section_unaccounted_work_classification_adaptive_with_audit"
        )
        section_manager_throwback_routing_policy = _mode_policy(
            "section_manager_throwback_routing_required",
            "section_manager_throwback_routing_policy_scoped",
            "section_manager_throwback_routing_adaptive_with_audit"
        )
        section_scope_boundary_enforcement_policy = _mode_policy(
            "section_scope_boundary_enforcement_required",
            "section_scope_boundary_enforcement_policy_scoped",
            "section_scope_boundary_enforcement_adaptive_with_audit"
        )
        section_change_order_authority_policy = _mode_policy(
            "section_change_order_authority_gate_required",
            "section_change_order_authority_policy_scoped",
            "section_change_order_authority_adaptive_with_audit"
        )
        section_completion_verification_policy = _mode_policy(
            "section_completion_verification_required",
            "section_completion_verification_policy_scoped",
            "section_completion_verification_adaptive_with_audit"
        )
        section_recommendation_rollforward_policy = _mode_policy(
            "section_recommendation_rollforward_required",
            "section_recommendation_rollforward_policy_scoped",
            "section_recommendation_rollforward_adaptive_with_audit"
        )
        section_dependency_traceability_policy = _mode_policy(
            "section_dependency_traceability_required",
            "section_dependency_traceability_policy_scoped",
            "section_dependency_traceability_adaptive_with_audit"
        )
        section_operational_readiness_policy = _mode_policy(
            "section_operational_readiness_required",
            "section_operational_readiness_policy_scoped",
            "section_operational_readiness_adaptive_with_audit"
        )
        section_reporting_attestation_policy = _mode_policy(
            "section_reporting_attestation_required",
            "section_reporting_attestation_policy_scoped",
            "section_reporting_attestation_adaptive_with_audit"
        )
        section_governance_traceability_policy = _mode_policy(
            "section_governance_traceability_required",
            "section_governance_traceability_policy_scoped",
            "section_governance_traceability_adaptive_with_audit"
        )
        section_progress_checkpoint_policy = _mode_policy(
            "section_progress_checkpoint_required",
            "section_progress_checkpoint_policy_scoped",
            "section_progress_checkpoint_adaptive_with_audit"
        )
        section_acceptance_verification_policy = _mode_policy(
            "section_acceptance_verification_required",
            "section_acceptance_verification_policy_scoped",
            "section_acceptance_verification_adaptive_with_audit"
        )
        section_sync_integrity_policy = _mode_policy(
            "section_sync_integrity_required",
            "section_sync_integrity_policy_scoped",
            "section_sync_integrity_adaptive_with_audit"
        )
        section_lifecycle_reporting_policy = _mode_policy(
            "section_lifecycle_reporting_required",
            "section_lifecycle_reporting_policy_scoped",
            "section_lifecycle_reporting_adaptive_with_audit"
        )
        section_contractual_risk_alignment_policy = _mode_policy(
            "section_contractual_risk_alignment_required",
            "section_contractual_risk_alignment_policy_scoped",
            "section_contractual_risk_alignment_adaptive_with_audit"
        )
        section_compliance_rulepack_sync_policy = _mode_policy(
            "section_compliance_rulepack_sync_required",
            "section_compliance_rulepack_sync_policy_scoped",
            "section_compliance_rulepack_sync_adaptive_with_audit"
        )
        section_authoritative_source_integrity_policy = _mode_policy(
            "section_authoritative_source_integrity_required",
            "section_authoritative_source_integrity_policy_scoped",
            "section_authoritative_source_integrity_adaptive_with_audit"
        )
        section_budget_gate_reconciliation_policy = _mode_policy(
            "section_budget_gate_reconciliation_required",
            "section_budget_gate_reconciliation_policy_scoped",
            "section_budget_gate_reconciliation_adaptive_with_audit"
        )
        section_governance_override_hierarchy_policy = _mode_policy(
            "section_governance_override_hierarchy_required",
            "section_governance_override_hierarchy_policy_scoped",
            "section_governance_override_hierarchy_adaptive_with_audit"
        )
        section_policy_pack_versioning_policy = _mode_policy(
            "section_policy_pack_versioning_required",
            "section_policy_pack_versioning_policy_scoped",
            "section_policy_pack_versioning_adaptive_with_audit"
        )
        section_authority_delegation_revocation_policy = _mode_policy(
            "section_authority_delegation_revocation_required",
            "section_authority_delegation_revocation_policy_scoped",
            "section_authority_delegation_revocation_adaptive_with_audit"
        )
        section_evidence_immutability_policy = _mode_policy(
            "section_evidence_immutability_required",
            "section_evidence_immutability_policy_scoped",
            "section_evidence_immutability_adaptive_with_audit"
        )
        section_compute_plane_replay_attestation_policy = _mode_policy(
            "section_compute_plane_replay_attestation_required",
            "section_compute_plane_replay_attestation_policy_scoped",
            "section_compute_plane_replay_attestation_adaptive_with_audit"
        )
        section_swarm_isolation_boundary_policy = _mode_policy(
            "section_swarm_isolation_boundary_required",
            "section_swarm_isolation_boundary_policy_scoped",
            "section_swarm_isolation_boundary_adaptive_with_audit"
        )
        section_risk_tolerance_boundary_policy = _mode_policy(
            "section_risk_tolerance_boundary_required",
            "section_risk_tolerance_boundary_policy_scoped",
            "section_risk_tolerance_boundary_adaptive_with_audit"
        )
        section_approval_delegation_integrity_policy = _mode_policy(
            "section_approval_delegation_integrity_required",
            "section_approval_delegation_integrity_policy_scoped",
            "section_approval_delegation_integrity_adaptive_with_audit"
        )
        section_budget_anomaly_circuit_breaker_policy = _mode_policy(
            "section_budget_anomaly_circuit_breaker_required",
            "section_budget_anomaly_circuit_breaker_policy_scoped",
            "section_budget_anomaly_circuit_breaker_adaptive_with_audit"
        )
        section_compliance_evidence_freshness_policy = _mode_policy(
            "section_compliance_evidence_freshness_required",
            "section_compliance_evidence_freshness_policy_scoped",
            "section_compliance_evidence_freshness_adaptive_with_audit"
        )
        section_decision_packet_trace_policy = _mode_policy(
            "section_decision_packet_trace_required",
            "section_decision_packet_trace_policy_scoped",
            "section_decision_packet_trace_adaptive_with_audit"
        )
        section_exec_authority_gate_policy = _mode_policy(
            "section_exec_authority_gate_required",
            "section_exec_authority_gate_policy_scoped",
            "section_exec_authority_gate_adaptive_with_audit"
        )
        section_compute_plane_determinism_policy = _mode_policy(
            "section_compute_plane_determinism_required",
            "section_compute_plane_determinism_policy_scoped",
            "section_compute_plane_determinism_adaptive_with_audit"
        )
        section_change_order_budget_delta_policy = _mode_policy(
            "section_change_order_budget_delta_required",
            "section_change_order_budget_delta_policy_scoped",
            "section_change_order_budget_delta_adaptive_with_audit"
        )
        section_domain_swarm_accountability_policy = _mode_policy(
            "section_domain_swarm_accountability_required",
            "section_domain_swarm_accountability_policy_scoped",
            "section_domain_swarm_accountability_adaptive_with_audit"
        )
        section_audit_packet_release_policy = _mode_policy(
            "section_audit_packet_release_required",
            "section_audit_packet_release_policy_scoped",
            "section_audit_packet_release_adaptive_with_audit"
        )
        section_request_envelope_integrity_policy = _mode_policy(
            "section_request_envelope_integrity_required",
            "section_request_envelope_integrity_policy_scoped",
            "section_request_envelope_integrity_adaptive_with_audit"
        )
        section_gate_graph_compilation_policy = _mode_policy(
            "section_gate_graph_compilation_required",
            "section_gate_graph_compilation_policy_scoped",
            "section_gate_graph_compilation_adaptive_with_audit"
        )
        section_domain_swarm_routing_policy = _mode_policy(
            "section_domain_swarm_routing_required",
            "section_domain_swarm_routing_policy_scoped",
            "section_domain_swarm_routing_adaptive_with_audit"
        )
        section_compute_replay_consistency_policy = _mode_policy(
            "section_compute_replay_consistency_required",
            "section_compute_replay_consistency_policy_scoped",
            "section_compute_replay_consistency_adaptive_with_audit"
        )
        section_authority_scope_binding_policy = _mode_policy(
            "section_authority_scope_binding_required",
            "section_authority_scope_binding_policy_scoped",
            "section_authority_scope_binding_adaptive_with_audit"
        )
        section_request_envelope_auditability_policy = _mode_policy(
            "section_request_envelope_auditability_required",
            "section_request_envelope_auditability_policy_scoped",
            "section_request_envelope_auditability_adaptive_with_audit"
        )
        section_gate_dependency_replay_policy = _mode_policy(
            "section_gate_dependency_replay_required",
            "section_gate_dependency_replay_policy_scoped",
            "section_gate_dependency_replay_adaptive_with_audit"
        )
        section_domain_escalation_binding_policy = _mode_policy(
            "section_domain_escalation_binding_required",
            "section_domain_escalation_binding_policy_scoped",
            "section_domain_escalation_binding_adaptive_with_audit"
        )
        section_budget_variance_justification_policy = _mode_policy(
            "section_budget_variance_justification_required",
            "section_budget_variance_justification_policy_scoped",
            "section_budget_variance_justification_adaptive_with_audit"
        )
        section_release_packet_signoff_policy = _mode_policy(
            "section_release_packet_signoff_required",
            "section_release_packet_signoff_policy_scoped",
            "section_release_packet_signoff_adaptive_with_audit"
        )
        section_authority_chain_escalation_policy = _mode_policy(
            "section_authority_chain_escalation_required",
            "section_authority_chain_escalation_policy_scoped",
            "section_authority_chain_escalation_adaptive_with_audit"
        )
        section_gate_decision_replay_policy = _mode_policy(
            "section_gate_decision_replay_required",
            "section_gate_decision_replay_policy_scoped",
            "section_gate_decision_replay_adaptive_with_audit"
        )
        section_rulepack_refresh_attestation_policy = _mode_policy(
            "section_rulepack_refresh_attestation_required",
            "section_rulepack_refresh_attestation_policy_scoped",
            "section_rulepack_refresh_attestation_adaptive_with_audit"
        )
        section_domain_owner_ack_policy = _mode_policy(
            "section_domain_owner_ack_required",
            "section_domain_owner_ack_policy_scoped",
            "section_domain_owner_ack_adaptive_with_audit"
        )
        section_handoff_readiness_attestation_policy = _mode_policy(
            "section_handoff_readiness_attestation_required",
            "section_handoff_readiness_attestation_policy_scoped",
            "section_handoff_readiness_attestation_adaptive_with_audit"
        )
        section_execution_audit_trail_policy = _mode_policy(
            "section_execution_audit_trail_required",
            "section_execution_audit_trail_policy_scoped",
            "section_execution_audit_trail_adaptive_with_audit"
        )
        section_policy_enforcement_checkpoint_policy = _mode_policy(
            "section_policy_enforcement_checkpoint_required",
            "section_policy_enforcement_checkpoint_policy_scoped",
            "section_policy_enforcement_checkpoint_adaptive_with_audit"
        )
        section_change_scope_integrity_policy = _mode_policy(
            "section_change_scope_integrity_required",
            "section_change_scope_integrity_policy_scoped",
            "section_change_scope_integrity_adaptive_with_audit"
        )
        section_domain_handoff_chain_policy = _mode_policy(
            "section_domain_handoff_chain_required",
            "section_domain_handoff_chain_policy_scoped",
            "section_domain_handoff_chain_adaptive_with_audit"
        )
        section_release_attestation_packet_policy = _mode_policy(
            "section_release_attestation_packet_required",
            "section_release_attestation_packet_policy_scoped",
            "section_release_attestation_packet_adaptive_with_audit"
        )
        section_contract_scope_recheck_policy = _mode_policy(
            "section_contract_scope_recheck_required",
            "section_contract_scope_recheck_policy_scoped",
            "section_contract_scope_recheck_adaptive_with_audit"
        )
        section_proposal_change_order_trace_policy = _mode_policy(
            "section_proposal_change_order_trace_required",
            "section_proposal_change_order_trace_policy_scoped",
            "section_proposal_change_order_trace_adaptive_with_audit"
        )
        section_gate_graph_dependency_guard_policy = _mode_policy(
            "section_gate_graph_dependency_guard_required",
            "section_gate_graph_dependency_guard_policy_scoped",
            "section_gate_graph_dependency_guard_adaptive_with_audit"
        )
        section_evidence_store_attestation_policy = _mode_policy(
            "section_evidence_store_attestation_required",
            "section_evidence_store_attestation_policy_scoped",
            "section_evidence_store_attestation_adaptive_with_audit"
        )
        section_release_readout_integrity_policy = _mode_policy(
            "section_release_readout_integrity_required",
            "section_release_readout_integrity_policy_scoped",
            "section_release_readout_integrity_adaptive_with_audit"
        )
        section_governance_sla_policy = _mode_policy(
            "section_governance_sla_required",
            "section_governance_sla_policy_scoped",
            "section_governance_sla_adaptive_with_audit"
        )
        section_authority_chain_replay_policy = _mode_policy(
            "section_authority_chain_replay_required",
            "section_authority_chain_replay_policy_scoped",
            "section_authority_chain_replay_adaptive_with_audit"
        )
        section_change_order_scope_lock_policy = _mode_policy(
            "section_change_order_scope_lock_required",
            "section_change_order_scope_lock_policy_scoped",
            "section_change_order_scope_lock_adaptive_with_audit"
        )
        section_evidence_lineage_policy = _mode_policy(
            "section_evidence_lineage_required",
            "section_evidence_lineage_policy_scoped",
            "section_evidence_lineage_adaptive_with_audit"
        )
        section_decision_trace_attestation_policy = _mode_policy(
            "section_decision_trace_attestation_required",
            "section_decision_trace_attestation_policy_scoped",
            "section_decision_trace_attestation_adaptive_with_audit"
        )
        section_rulepack_activation_policy = _mode_policy(
            "section_rulepack_activation_required",
            "section_rulepack_activation_policy_scoped",
            "section_rulepack_activation_adaptive_with_audit"
        )
        section_gate_input_allowlist_policy = _mode_policy(
            "section_gate_input_allowlist_required",
            "section_gate_input_allowlist_policy_scoped",
            "section_gate_input_allowlist_adaptive_with_audit"
        )
        section_nte_change_order_policy = _mode_policy(
            "section_nte_change_order_required",
            "section_nte_change_order_policy_scoped",
            "section_nte_change_order_adaptive_with_audit"
        )
        section_approval_identity_binding_policy = _mode_policy(
            "section_approval_identity_binding_required",
            "section_approval_identity_binding_policy_scoped",
            "section_approval_identity_binding_adaptive_with_audit"
        )
        section_compute_reproducibility_window_policy = _mode_policy(
            "section_compute_reproducibility_window_required",
            "section_compute_reproducibility_window_policy_scoped",
            "section_compute_reproducibility_window_adaptive_with_audit"
        )
        section_refusal_reason_standard_policy = _mode_policy(
            "section_refusal_reason_standard_required",
            "section_refusal_reason_standard_policy_scoped",
            "section_refusal_reason_standard_adaptive_with_audit"
        )
        section_escalation_reason_code_policy = _mode_policy(
            "section_escalation_reason_code_required",
            "section_escalation_reason_code_policy_scoped",
            "section_escalation_reason_code_adaptive_with_audit"
        )
        section_authority_delegation_expiry_policy = _mode_policy(
            "section_authority_delegation_expiry_required",
            "section_authority_delegation_expiry_policy_scoped",
            "section_authority_delegation_expiry_adaptive_with_audit"
        )
        section_budget_tag_enforcement_policy = _mode_policy(
            "section_budget_tag_enforcement_required",
            "section_budget_tag_enforcement_policy_scoped",
            "section_budget_tag_enforcement_adaptive_with_audit"
        )
        section_evidence_snapshot_replay_policy = _mode_policy(
            "section_evidence_snapshot_replay_required",
            "section_evidence_snapshot_replay_policy_scoped",
            "section_evidence_snapshot_replay_adaptive_with_audit"
        )
        section_budget_circuit_breaker_policy = _mode_policy(
            "section_budget_circuit_breaker_required",
            "section_budget_circuit_breaker_policy_scoped",
            "section_budget_circuit_breaker_adaptive_with_audit"
        )
        section_change_order_authority_scope_policy = _mode_policy(
            "section_change_order_authority_scope_required",
            "section_change_order_authority_scope_policy_scoped",
            "section_change_order_authority_scope_adaptive_with_audit"
        )
        section_evidence_signature_policy = _mode_policy(
            "section_evidence_signature_required",
            "section_evidence_signature_policy_scoped",
            "section_evidence_signature_adaptive_with_audit"
        )
        section_domain_escalation_sla_policy = _mode_policy(
            "section_domain_escalation_sla_required",
            "section_domain_escalation_sla_policy_scoped",
            "section_domain_escalation_sla_adaptive_with_audit"
        )
        section_governance_override_precedence_policy = _mode_policy(
            "section_governance_override_precedence_required",
            "section_governance_override_precedence_policy_scoped",
            "section_governance_override_precedence_adaptive_with_audit"
        )
        section_gate_outcome_reason_integrity_policy = _mode_policy(
            "section_gate_outcome_reason_integrity_required",
            "section_gate_outcome_reason_integrity_policy_scoped",
            "section_gate_outcome_reason_integrity_adaptive_with_audit"
        )
        section_authority_signature_validation_policy = _mode_policy(
            "section_authority_signature_validation_required",
            "section_authority_signature_validation_policy_scoped",
            "section_authority_signature_validation_adaptive_with_audit"
        )
        section_compute_replay_snapshot_policy = _mode_policy(
            "section_compute_replay_snapshot_required",
            "section_compute_replay_snapshot_policy_scoped",
            "section_compute_replay_snapshot_adaptive_with_audit"
        )
        section_budget_control_trace_policy = _mode_policy(
            "section_budget_control_trace_required",
            "section_budget_control_trace_policy_scoped",
            "section_budget_control_trace_adaptive_with_audit"
        )
        section_release_evidence_bundle_policy = _mode_policy(
            "section_release_evidence_bundle_required",
            "section_release_evidence_bundle_policy_scoped",
            "section_release_evidence_bundle_adaptive_with_audit"
        )
        section_gate_evaluation_determinism_policy = _mode_policy(
            "section_gate_evaluation_determinism_required",
            "section_gate_evaluation_determinism_policy_scoped",
            "section_gate_evaluation_determinism_adaptive_with_audit"
        )
        section_authority_override_documentation_policy = _mode_policy(
            "section_authority_override_documentation_required",
            "section_authority_override_documentation_policy_scoped",
            "section_authority_override_documentation_adaptive_with_audit"
        )
        section_change_order_dependency_validation_policy = _mode_policy(
            "section_change_order_dependency_validation_required",
            "section_change_order_dependency_validation_policy_scoped",
            "section_change_order_dependency_validation_adaptive_with_audit"
        )
        section_budget_forecast_alignment_policy = _mode_policy(
            "section_budget_forecast_alignment_required",
            "section_budget_forecast_alignment_policy_scoped",
            "section_budget_forecast_alignment_adaptive_with_audit"
        )
        section_handoff_audit_completion_policy = _mode_policy(
            "section_handoff_audit_completion_required",
            "section_handoff_audit_completion_policy_scoped",
            "section_handoff_audit_completion_adaptive_with_audit"
        )
        section_gate_decision_signature_policy = _mode_policy(
            "section_gate_decision_signature_required",
            "section_gate_decision_signature_policy_scoped",
            "section_gate_decision_signature_adaptive_with_audit"
        )
        section_authority_scope_timeout_policy = _mode_policy(
            "section_authority_scope_timeout_required",
            "section_authority_scope_timeout_policy_scoped",
            "section_authority_scope_timeout_adaptive_with_audit"
        )
        section_change_order_cost_trace_policy = _mode_policy(
            "section_change_order_cost_trace_required",
            "section_change_order_cost_trace_policy_scoped",
            "section_change_order_cost_trace_adaptive_with_audit"
        )
        section_evidence_checkpoint_policy = _mode_policy(
            "section_evidence_checkpoint_required",
            "section_evidence_checkpoint_policy_scoped",
            "section_evidence_checkpoint_adaptive_with_audit"
        )
        section_release_packet_consistency_policy = _mode_policy(
            "section_release_packet_consistency_required",
            "section_release_packet_consistency_policy_scoped",
            "section_release_packet_consistency_adaptive_with_audit"
        )
        section_authority_recertification_policy = _mode_policy(
            "section_authority_recertification_required",
            "section_authority_recertification_policy_scoped",
            "section_authority_recertification_adaptive_with_audit"
        )
        section_budget_forecast_variance_policy = _mode_policy(
            "section_budget_forecast_variance_required",
            "section_budget_forecast_variance_policy_scoped",
            "section_budget_forecast_variance_adaptive_with_audit"
        )
        section_evidence_hash_chain_policy = _mode_policy(
            "section_evidence_hash_chain_required",
            "section_evidence_hash_chain_policy_scoped",
            "section_evidence_hash_chain_adaptive_with_audit"
        )
        section_gate_timeout_enforcement_policy = _mode_policy(
            "section_gate_timeout_enforcement_required",
            "section_gate_timeout_enforcement_policy_scoped",
            "section_gate_timeout_enforcement_adaptive_with_audit"
        )
        section_release_exception_register_policy = _mode_policy(
            "section_release_exception_register_required",
            "section_release_exception_register_policy_scoped",
            "section_release_exception_register_adaptive_with_audit"
        )
        section_domain_owner_escalation_policy = _mode_policy(
            "section_domain_owner_escalation_required",
            "section_domain_owner_escalation_policy_scoped",
            "section_domain_owner_escalation_adaptive_with_audit"
        )
        section_gate_dependency_trace_policy = _mode_policy(
            "section_gate_dependency_trace_required",
            "section_gate_dependency_trace_policy_scoped",
            "section_gate_dependency_trace_adaptive_with_audit"
        )
        section_budget_variance_escalation_policy = _mode_policy(
            "section_budget_variance_escalation_required",
            "section_budget_variance_escalation_policy_scoped",
            "section_budget_variance_escalation_adaptive_with_audit"
        )
        section_evidence_lineage_recheck_policy = _mode_policy(
            "section_evidence_lineage_recheck_required",
            "section_evidence_lineage_recheck_policy_scoped",
            "section_evidence_lineage_recheck_adaptive_with_audit"
        )
        section_release_authority_replay_policy = _mode_policy(
            "section_release_authority_replay_required",
            "section_release_authority_replay_policy_scoped",
            "section_release_authority_replay_adaptive_with_audit"
        )
        section_gate_reason_code_replay_policy = _mode_policy(
            "section_gate_reason_code_replay_required",
            "section_gate_reason_code_replay_policy_scoped",
            "section_gate_reason_code_replay_adaptive_with_audit"
        )
        section_approval_delegation_registry_policy = _mode_policy(
            "section_approval_delegation_registry_required",
            "section_approval_delegation_registry_policy_scoped",
            "section_approval_delegation_registry_adaptive_with_audit"
        )
        section_budget_cap_change_log_policy = _mode_policy(
            "section_budget_cap_change_log_required",
            "section_budget_cap_change_log_policy_scoped",
            "section_budget_cap_change_log_adaptive_with_audit"
        )
        section_evidence_attestation_signature_policy = _mode_policy(
            "section_evidence_attestation_signature_required",
            "section_evidence_attestation_signature_policy_scoped",
            "section_evidence_attestation_signature_adaptive_with_audit"
        )
        section_release_governance_manifest_policy = _mode_policy(
            "section_release_governance_manifest_required",
            "section_release_governance_manifest_policy_scoped",
            "section_release_governance_manifest_adaptive_with_audit"
        )
        section_governance_path_integrity_policy = _mode_policy(
            "section_governance_path_integrity_required",
            "section_governance_path_integrity_policy_scoped",
            "section_governance_path_integrity_adaptive_with_audit"
        )
        section_policy_exception_disposition_policy = _mode_policy(
            "section_policy_exception_disposition_required",
            "section_policy_exception_disposition_policy_scoped",
            "section_policy_exception_disposition_adaptive_with_audit"
        )
        section_budget_reforecast_attestation_policy = _mode_policy(
            "section_budget_reforecast_attestation_required",
            "section_budget_reforecast_attestation_policy_scoped",
            "section_budget_reforecast_attestation_adaptive_with_audit"
        )
        section_evidence_chain_custody_policy = _mode_policy(
            "section_evidence_chain_custody_required",
            "section_evidence_chain_custody_policy_scoped",
            "section_evidence_chain_custody_adaptive_with_audit"
        )
        section_release_authorization_token_policy = _mode_policy(
            "section_release_authorization_token_required",
            "section_release_authorization_token_policy_scoped",
            "section_release_authorization_token_adaptive_with_audit"
        )
        section_governance_checkpoint_replay_policy = _mode_policy(
            "section_governance_checkpoint_replay_required",
            "section_governance_checkpoint_replay_policy_scoped",
            "section_governance_checkpoint_replay_adaptive_with_audit"
        )
        section_authority_token_rotation_policy = _mode_policy(
            "section_authority_token_rotation_required",
            "section_authority_token_rotation_policy_scoped",
            "section_authority_token_rotation_adaptive_with_audit"
        )
        section_budget_spike_containment_policy = _mode_policy(
            "section_budget_spike_containment_required",
            "section_budget_spike_containment_policy_scoped",
            "section_budget_spike_containment_adaptive_with_audit"
        )
        section_evidence_bundle_hash_policy = _mode_policy(
            "section_evidence_bundle_hash_required",
            "section_evidence_bundle_hash_policy_scoped",
            "section_evidence_bundle_hash_adaptive_with_audit"
        )
        section_release_exception_revalidation_policy = _mode_policy(
            "section_release_exception_revalidation_required",
            "section_release_exception_revalidation_policy_scoped",
            "section_release_exception_revalidation_adaptive_with_audit"
        )
        section_governance_policy_reconciliation_policy = _mode_policy(
            "section_governance_policy_reconciliation_required",
            "section_governance_policy_reconciliation_policy_scoped",
            "section_governance_policy_reconciliation_adaptive_with_audit"
        )
        section_authority_chain_expiry_policy = _mode_policy(
            "section_authority_chain_expiry_required",
            "section_authority_chain_expiry_policy_scoped",
            "section_authority_chain_expiry_adaptive_with_audit"
        )
        section_budget_exception_audit_policy = _mode_policy(
            "section_budget_exception_audit_required",
            "section_budget_exception_audit_policy_scoped",
            "section_budget_exception_audit_adaptive_with_audit"
        )
        section_gate_signature_rotation_policy = _mode_policy(
            "section_gate_signature_rotation_required",
            "section_gate_signature_rotation_policy_scoped",
            "section_gate_signature_rotation_adaptive_with_audit"
        )
        section_release_packet_attestation_policy = _mode_policy(
            "section_release_packet_attestation_required",
            "section_release_packet_attestation_policy_scoped",
            "section_release_packet_attestation_adaptive_with_audit"
        )
        section_governance_rollup_consistency_policy = _mode_policy(
            "section_governance_rollup_consistency_required",
            "section_governance_rollup_consistency_policy_scoped",
            "section_governance_rollup_consistency_adaptive_with_audit"
        )
        section_authority_chain_snapshot_policy = _mode_policy(
            "section_authority_chain_snapshot_required",
            "section_authority_chain_snapshot_policy_scoped",
            "section_authority_chain_snapshot_adaptive_with_audit"
        )
        section_budget_envelope_audit_policy = _mode_policy(
            "section_budget_envelope_audit_required",
            "section_budget_envelope_audit_policy_scoped",
            "section_budget_envelope_audit_adaptive_with_audit"
        )
        section_evidence_manifest_replay_policy = _mode_policy(
            "section_evidence_manifest_replay_required",
            "section_evidence_manifest_replay_policy_scoped",
            "section_evidence_manifest_replay_adaptive_with_audit"
        )
        section_release_override_justification_policy = _mode_policy(
            "section_release_override_justification_required",
            "section_release_override_justification_policy_scoped",
            "section_release_override_justification_adaptive_with_audit"
        )
        section_governance_decision_envelope_policy = _mode_policy(
            "section_governance_decision_envelope_required",
            "section_governance_decision_envelope_policy_scoped",
            "section_governance_decision_envelope_adaptive_with_audit"
        )
        section_authority_recusal_trace_policy = _mode_policy(
            "section_authority_recusal_trace_required",
            "section_authority_recusal_trace_policy_scoped",
            "section_authority_recusal_trace_adaptive_with_audit"
        )
        section_budget_guardrail_replay_policy = _mode_policy(
            "section_budget_guardrail_replay_required",
            "section_budget_guardrail_replay_policy_scoped",
            "section_budget_guardrail_replay_adaptive_with_audit"
        )
        section_evidence_provenance_reconciliation_policy = _mode_policy(
            "section_evidence_provenance_reconciliation_required",
            "section_evidence_provenance_reconciliation_policy_scoped",
            "section_evidence_provenance_reconciliation_adaptive_with_audit"
        )
        section_release_attestation_chain_policy = _mode_policy(
            "section_release_attestation_chain_required",
            "section_release_attestation_chain_policy_scoped",
            "section_release_attestation_chain_adaptive_with_audit"
        )
        section_governance_trace_seal_policy = _mode_policy(
            "section_governance_trace_seal_required",
            "section_governance_trace_seal_policy_scoped",
            "section_governance_trace_seal_adaptive_with_audit"
        )
        section_authority_replay_token_policy = _mode_policy(
            "section_authority_replay_token_required",
            "section_authority_replay_token_policy_scoped",
            "section_authority_replay_token_adaptive_with_audit"
        )
        section_budget_exception_replay_policy = _mode_policy(
            "section_budget_exception_replay_required",
            "section_budget_exception_replay_policy_scoped",
            "section_budget_exception_replay_adaptive_with_audit"
        )
        section_evidence_freshness_recertification_policy = _mode_policy(
            "section_evidence_freshness_recertification_required",
            "section_evidence_freshness_recertification_policy_scoped",
            "section_evidence_freshness_recertification_adaptive_with_audit"
        )
        section_release_handoff_replay_policy = _mode_policy(
            "section_release_handoff_replay_required",
            "section_release_handoff_replay_policy_scoped",
            "section_release_handoff_replay_adaptive_with_audit"
        )
        section_governance_audit_recertification_policy = _mode_policy(
            "section_governance_audit_recertification_required",
            "section_governance_audit_recertification_policy_scoped",
            "section_governance_audit_recertification_adaptive_with_audit"
        )
        section_authority_scope_exception_policy = _mode_policy(
            "section_authority_scope_exception_required",
            "section_authority_scope_exception_policy_scoped",
            "section_authority_scope_exception_adaptive_with_audit"
        )
        section_budget_change_envelope_policy = _mode_policy(
            "section_budget_change_envelope_required",
            "section_budget_change_envelope_policy_scoped",
            "section_budget_change_envelope_adaptive_with_audit"
        )
        section_evidence_chain_seal_policy = _mode_policy(
            "section_evidence_chain_seal_required",
            "section_evidence_chain_seal_policy_scoped",
            "section_evidence_chain_seal_adaptive_with_audit"
        )
        section_release_gate_replay_policy = _mode_policy(
            "section_release_gate_replay_required",
            "section_release_gate_replay_policy_scoped",
            "section_release_gate_replay_adaptive_with_audit"
        )
        section_governance_exception_timeout_policy = _mode_policy(
            "section_governance_exception_timeout_required",
            "section_governance_exception_timeout_policy_scoped",
            "section_governance_exception_timeout_adaptive_with_audit"
        )
        section_authority_delegation_ledger_policy = _mode_policy(
            "section_authority_delegation_ledger_required",
            "section_authority_delegation_ledger_policy_scoped",
            "section_authority_delegation_ledger_adaptive_with_audit"
        )
        section_budget_burnrate_attestation_policy = _mode_policy(
            "section_budget_burnrate_attestation_required",
            "section_budget_burnrate_attestation_policy_scoped",
            "section_budget_burnrate_attestation_adaptive_with_audit"
        )
        section_evidence_snapshot_expiry_policy = _mode_policy(
            "section_evidence_snapshot_expiry_required",
            "section_evidence_snapshot_expiry_policy_scoped",
            "section_evidence_snapshot_expiry_adaptive_with_audit"
        )
        section_release_override_reconciliation_policy = _mode_policy(
            "section_release_override_reconciliation_required",
            "section_release_override_reconciliation_policy_scoped",
            "section_release_override_reconciliation_adaptive_with_audit"
        )
        section_governance_ledger_integrity_policy = _mode_policy(
            "section_governance_ledger_integrity_required",
            "section_governance_ledger_integrity_policy_scoped",
            "section_governance_ledger_integrity_adaptive_with_audit"
        )
        section_authority_chain_digest_policy = _mode_policy(
            "section_authority_chain_digest_required",
            "section_authority_chain_digest_policy_scoped",
            "section_authority_chain_digest_adaptive_with_audit"
        )
        section_budget_reconciliation_digest_policy = _mode_policy(
            "section_budget_reconciliation_digest_required",
            "section_budget_reconciliation_digest_policy_scoped",
            "section_budget_reconciliation_digest_adaptive_with_audit"
        )
        section_evidence_checkpoint_digest_policy = _mode_policy(
            "section_evidence_checkpoint_digest_required",
            "section_evidence_checkpoint_digest_policy_scoped",
            "section_evidence_checkpoint_digest_adaptive_with_audit"
        )
        section_release_chain_digest_policy = _mode_policy(
            "section_release_chain_digest_required",
            "section_release_chain_digest_policy_scoped",
            "section_release_chain_digest_adaptive_with_audit"
        )
        section_governance_policy_replay_lock_policy = _mode_policy(
            "section_governance_policy_replay_lock_required",
            "section_governance_policy_replay_lock_policy_scoped",
            "section_governance_policy_replay_lock_adaptive_with_audit"
        )
        section_authority_chain_nonce_policy = _mode_policy(
            "section_authority_chain_nonce_required",
            "section_authority_chain_nonce_policy_scoped",
            "section_authority_chain_nonce_adaptive_with_audit"
        )
        section_budget_override_attestation_policy = _mode_policy(
            "section_budget_override_attestation_required",
            "section_budget_override_attestation_policy_scoped",
            "section_budget_override_attestation_adaptive_with_audit"
        )
        section_evidence_packet_nonce_policy = _mode_policy(
            "section_evidence_packet_nonce_required",
            "section_evidence_packet_nonce_policy_scoped",
            "section_evidence_packet_nonce_adaptive_with_audit"
        )
        section_release_gate_override_policy = _mode_policy(
            "section_release_gate_override_required",
            "section_release_gate_override_policy_scoped",
            "section_release_gate_override_adaptive_with_audit"
        )
        section_governance_dependency_sequencing_policy = _mode_policy(
            "section_governance_dependency_sequencing_required",
            "section_governance_dependency_sequencing_policy_scoped",
            "section_governance_dependency_sequencing_adaptive_with_audit"
        )
        section_authority_scope_replay_attestation_policy = _mode_policy(
            "section_authority_scope_replay_attestation_required",
            "section_authority_scope_replay_attestation_policy_scoped",
            "section_authority_scope_replay_attestation_adaptive_with_audit"
        )
        section_budget_allocation_trace_policy = _mode_policy(
            "section_budget_allocation_trace_required",
            "section_budget_allocation_trace_policy_scoped",
            "section_budget_allocation_trace_adaptive_with_audit"
        )
        section_evidence_manifest_freshness_policy = _mode_policy(
            "section_evidence_manifest_freshness_required",
            "section_evidence_manifest_freshness_policy_scoped",
            "section_evidence_manifest_freshness_adaptive_with_audit"
        )
        section_release_override_chain_policy = _mode_policy(
            "section_release_override_chain_required",
            "section_release_override_chain_policy_scoped",
            "section_release_override_chain_adaptive_with_audit"
        )
        section_governance_verification_digest_policy = _mode_policy(
            "section_governance_verification_digest_required",
            "section_governance_verification_digest_policy_scoped",
            "section_governance_verification_digest_adaptive_with_audit"
        )
        section_authority_scope_nonce_rotation_policy = _mode_policy(
            "section_authority_scope_nonce_rotation_required",
            "section_authority_scope_nonce_rotation_policy_scoped",
            "section_authority_scope_nonce_rotation_adaptive_with_audit"
        )
        section_budget_forecast_lock_policy = _mode_policy(
            "section_budget_forecast_lock_required",
            "section_budget_forecast_lock_policy_scoped",
            "section_budget_forecast_lock_adaptive_with_audit"
        )
        section_evidence_bundle_canonicalization_policy = _mode_policy(
            "section_evidence_bundle_canonicalization_required",
            "section_evidence_bundle_canonicalization_policy_scoped",
            "section_evidence_bundle_canonicalization_adaptive_with_audit"
        )
        section_release_attestation_digest_policy = _mode_policy(
            "section_release_attestation_digest_required",
            "section_release_attestation_digest_policy_scoped",
            "section_release_attestation_digest_adaptive_with_audit"
        )
        section_governance_dependency_nonce_lock_policy = _mode_policy(
            "section_governance_dependency_nonce_lock_required",
            "section_governance_dependency_nonce_lock_policy_scoped",
            "section_governance_dependency_nonce_lock_adaptive_with_audit"
        )
        section_authority_override_recertification_policy = _mode_policy(
            "section_authority_override_recertification_required",
            "section_authority_override_recertification_policy_scoped",
            "section_authority_override_recertification_adaptive_with_audit"
        )
        section_budget_exception_rebind_policy = _mode_policy(
            "section_budget_exception_rebind_required",
            "section_budget_exception_rebind_policy_scoped",
            "section_budget_exception_rebind_adaptive_with_audit"
        )
        section_evidence_packet_reseal_policy = _mode_policy(
            "section_evidence_packet_reseal_required",
            "section_evidence_packet_reseal_policy_scoped",
            "section_evidence_packet_reseal_adaptive_with_audit"
        )
        section_release_gate_drift_policy = _mode_policy(
            "section_release_gate_drift_required",
            "section_release_gate_drift_policy_scoped",
            "section_release_gate_drift_adaptive_with_audit"
        )
        hitl_escalation_comfort_policy = hitl_escalation_requirement_policy
        return {
            "execution_mode": mode,
            "execution_profile_source": execution_profile_source,
            "execution_enforcement_level": execution_enforcement_level,
            "control_plane_separation_state": control_plane_separation_state,
            "self_improvement_rd_candidate": self_improvement_rd_candidate,
            "approval_checkpoint_policy": approval_checkpoint_policy,
            "budget_enforcement_mode": budget_enforcement_mode,
            "audit_logging_policy": audit_logging_policy,
            "escalation_routing_policy": escalation_routing_policy,
            "tool_mediation_policy": tool_mediation_policy,
            "deterministic_routing_policy": deterministic_routing_policy,
            "compute_routing_policy": compute_routing_policy,
            "policy_compiler_mode": policy_compiler_mode,
            "permission_validation_policy": permission_validation_policy,
            "delegation_scope_policy": delegation_scope_policy,
            "execution_broker_policy": execution_broker_policy,
            "role_registry_policy": role_registry_policy,
            "authority_boundary_policy": authority_boundary_policy,
            "cross_department_arbitration_policy": cross_department_arbitration_policy,
            "department_memory_isolation_policy": department_memory_isolation_policy,
            "employee_contract_responsibility_policy": employee_contract_responsibility_policy,
            "core_responsibility_scope": core_responsibility_scope,
            "shadow_agent_account_policy": shadow_agent_account_policy,
            "user_base_management_surface_policy": user_base_management_surface_policy,
            "employee_contract_change_authority_policy": employee_contract_change_authority_policy,
            "employee_contract_management_surface_policy": employee_contract_management_surface_policy,
            "employee_contract_accountability_policy": employee_contract_accountability_policy,
            "shadow_agent_org_parity_policy": shadow_agent_org_parity_policy,
            "shadow_agent_contract_binding_policy": shadow_agent_contract_binding_policy,
            "user_base_access_governance_policy": user_base_access_governance_policy,
            "employee_contract_obligation_tracking_policy": employee_contract_obligation_tracking_policy,
            "employee_contract_escalation_binding_policy": employee_contract_escalation_binding_policy,
            "regulatory_context_binding_policy": regulatory_context_binding_policy,
            "autonomy_preference_override_policy": autonomy_preference_override_policy,
            "risk_tolerance_enforcement_policy": risk_tolerance_enforcement_policy,
            "safety_level_assurance_policy": safety_level_assurance_policy,
            "delegation_comfort_governance_policy": delegation_comfort_governance_policy,
            "employee_contract_review_policy": employee_contract_review_policy,
            "employee_contract_versioning_policy": employee_contract_versioning_policy,
            "shadow_agent_account_lifecycle_policy": shadow_agent_account_lifecycle_policy,
            "user_base_ui_audit_policy": user_base_ui_audit_policy,
            "org_chart_assignment_sync_policy": org_chart_assignment_sync_policy,
            "event_queue_durability_policy": event_queue_durability_policy,
            "idempotency_key_enforcement_policy": idempotency_key_enforcement_policy,
            "retry_backoff_policy": retry_backoff_policy,
            "circuit_breaker_policy": circuit_breaker_policy,
            "rollback_recovery_policy": rollback_recovery_policy,
            "planning_plane_decomposition_policy": planning_plane_decomposition_policy,
            "planning_plane_risk_simulation_policy": planning_plane_risk_simulation_policy,
            "execution_plane_permission_gate_policy": execution_plane_permission_gate_policy,
            "execution_plane_budget_guardrail_policy": execution_plane_budget_guardrail_policy,
            "execution_plane_audit_trail_integrity_policy": execution_plane_audit_trail_integrity_policy,
            "swarm_spawn_governance_policy": swarm_spawn_governance_policy,
            "swarm_failure_containment_policy": swarm_failure_containment_policy,
            "swarm_budget_expansion_policy": swarm_budget_expansion_policy,
            "shadow_reinforcement_signal_policy": shadow_reinforcement_signal_policy,
            "behavioral_divergence_tracking_policy": behavioral_divergence_tracking_policy,
            "planning_plane_gate_synthesis_policy": planning_plane_gate_synthesis_policy,
            "planning_plane_org_mapping_policy": planning_plane_org_mapping_policy,
            "execution_plane_tool_permission_enforcement_policy": execution_plane_tool_permission_enforcement_policy,
            "execution_plane_budget_ceiling_override_policy": execution_plane_budget_ceiling_override_policy,
            "execution_plane_escalation_checkpoint_policy": execution_plane_escalation_checkpoint_policy,
            "human_in_the_loop_enforcement_policy": human_in_the_loop_enforcement_policy,
            "regulatory_audit_retention_policy": regulatory_audit_retention_policy,
            "tenant_boundary_enforcement_policy": tenant_boundary_enforcement_policy,
            "policy_exception_handling_policy": policy_exception_handling_policy,
            "runtime_profile_refresh_policy": runtime_profile_refresh_policy,
            "planning_plane_compliance_modeling_policy": planning_plane_compliance_modeling_policy,
            "planning_plane_proposal_generation_policy": planning_plane_proposal_generation_policy,
            "execution_plane_policy_compiler_enforcement_policy": execution_plane_policy_compiler_enforcement_policy,
            "execution_plane_deterministic_override_policy": execution_plane_deterministic_override_policy,
            "hitl_escalation_requirement_policy": hitl_escalation_requirement_policy,
            "shadow_peer_role_enforcement_policy": shadow_peer_role_enforcement_policy,
            "shadow_account_user_binding_policy": shadow_account_user_binding_policy,
            "employee_contract_scope_enforcement_policy": employee_contract_scope_enforcement_policy,
            "employee_contract_exception_review_policy": employee_contract_exception_review_policy,
            "user_base_tenant_boundary_policy": user_base_tenant_boundary_policy,
            "compliance_event_escalation_policy": compliance_event_escalation_policy,
            "regulatory_override_resolution_policy": regulatory_override_resolution_policy,
            "budget_ceiling_revision_policy": budget_ceiling_revision_policy,
            "budget_consumption_alert_policy": budget_consumption_alert_policy,
            "approval_checkpoint_timeout_policy": approval_checkpoint_timeout_policy,
            "compliance_sensor_event_policy": compliance_sensor_event_policy,
            "policy_drift_detection_policy": policy_drift_detection_policy,
            "onboarding_profile_revalidation_policy": onboarding_profile_revalidation_policy,
            "control_plane_mode_transition_policy": control_plane_mode_transition_policy,
            "user_autonomy_preference_ui_policy": user_autonomy_preference_ui_policy,
            "planning_execution_toggle_guard_policy": planning_execution_toggle_guard_policy,
            "governance_exception_escalation_policy": governance_exception_escalation_policy,
            "approval_sla_enforcement_policy": approval_sla_enforcement_policy,
            "tenant_residency_control_policy": tenant_residency_control_policy,
            "swarm_recursion_guard_policy": swarm_recursion_guard_policy,
            "contract_renewal_gate_policy": contract_renewal_gate_policy,
            "shadow_account_suspension_policy": shadow_account_suspension_policy,
            "user_base_offboarding_policy": user_base_offboarding_policy,
            "governance_kernel_heartbeat_policy": governance_kernel_heartbeat_policy,
            "policy_compiler_change_control_policy": policy_compiler_change_control_policy,
            "replay_reconciliation_policy": replay_reconciliation_policy,
            "audit_artifact_retention_policy": audit_artifact_retention_policy,
            "event_backpressure_management_policy": event_backpressure_management_policy,
            "queue_health_slo_policy": queue_health_slo_policy,
            "rollback_compensation_policy": rollback_compensation_policy,
            "durable_queue_replay_policy": durable_queue_replay_policy,
            "swarm_failure_domain_isolation_policy": swarm_failure_domain_isolation_policy,
            "idempotent_recovery_validation_policy": idempotent_recovery_validation_policy,
            "agent_spawn_budget_reconciliation_policy": agent_spawn_budget_reconciliation_policy,
            "audit_chain_export_policy": audit_chain_export_policy,
            "semantics_belief_state_policy": semantics_belief_state_policy,
            "semantics_loss_risk_policy": semantics_loss_risk_policy,
            "semantics_voi_question_policy": semantics_voi_question_policy,
            "semantics_invariance_boundary_policy": semantics_invariance_boundary_policy,
            "semantics_verification_feedback_policy": semantics_verification_feedback_policy,
            "semantics_hypothesis_update_policy": semantics_hypothesis_update_policy,
            "semantics_likelihood_scoring_policy": semantics_likelihood_scoring_policy,
            "semantics_rvoi_decision_policy": semantics_rvoi_decision_policy,
            "semantics_clarifying_question_budget_policy": semantics_clarifying_question_budget_policy,
            "semantics_invariance_retry_policy": semantics_invariance_retry_policy,
            "semantics_hypothesis_distribution_policy": semantics_hypothesis_distribution_policy,
            "semantics_cvar_risk_measure_policy": semantics_cvar_risk_measure_policy,
            "semantics_question_cost_policy": semantics_question_cost_policy,
            "semantics_invariance_transform_set_policy": semantics_invariance_transform_set_policy,
            "semantics_verification_boundary_policy": semantics_verification_boundary_policy,
            "runtime_telemetry_tokens_to_resolution_policy": runtime_telemetry_tokens_to_resolution_policy,
            "runtime_telemetry_question_count_policy": runtime_telemetry_question_count_policy,
            "runtime_telemetry_invariance_score_policy": runtime_telemetry_invariance_score_policy,
            "runtime_telemetry_risk_score_policy": runtime_telemetry_risk_score_policy,
            "runtime_telemetry_verification_feedback_policy": runtime_telemetry_verification_feedback_policy,
            "semantics_question_candidate_generation_policy": semantics_question_candidate_generation_policy,
            "semantics_answer_prediction_policy": semantics_answer_prediction_policy,
            "semantics_belief_normalization_policy": semantics_belief_normalization_policy,
            "semantics_verification_loss_injection_policy": semantics_verification_loss_injection_policy,
            "semantics_action_revision_policy": semantics_action_revision_policy,
            "legacy_orchestrator_discovery_policy": legacy_orchestrator_discovery_policy,
            "rubixcube_orchestrator_adapter_policy": rubixcube_orchestrator_adapter_policy,
            "triage_orchestrator_adapter_policy": triage_orchestrator_adapter_policy,
            "bot_catalog_capability_mapping_policy": bot_catalog_capability_mapping_policy,
            "legacy_orchestrator_wiring_priority_policy": legacy_orchestrator_wiring_priority_policy,
            "modern_arcana_clockwork_bridge_policy": modern_arcana_clockwork_bridge_policy,
            "legacy_orchestrator_compatibility_matrix_policy": legacy_orchestrator_compatibility_matrix_policy,
            "rubixcube_kaia_mix_scoring_policy": rubixcube_kaia_mix_scoring_policy,
            "triage_rollcall_selection_policy": triage_rollcall_selection_policy,
            "legacy_orchestrator_tooling_plan_policy": legacy_orchestrator_tooling_plan_policy,
            "clockwork_orchestrator_bridge_policy": clockwork_orchestrator_bridge_policy,
            "arcana_pipeline_compatibility_policy": arcana_pipeline_compatibility_policy,
            "rubixcube_evidence_engine_policy": rubixcube_evidence_engine_policy,
            "triage_rollcall_confidence_policy": triage_rollcall_confidence_policy,
            "golden_path_reuse_policy": golden_path_reuse_policy,
            "governance_review_cadence_policy": governance_review_cadence_policy,
            "section_status_reconciliation_policy": section_status_reconciliation_policy,
            "orchestrator_wiring_readiness_policy": orchestrator_wiring_readiness_policy,
            "verification_feedback_closure_policy": verification_feedback_closure_policy,
            "self_improvement_backlog_priority_policy": self_improvement_backlog_priority_policy,
            "assessment_section_coverage_policy": assessment_section_coverage_policy,
            "assessment_recommendation_acceptance_policy": assessment_recommendation_acceptance_policy,
            "assessment_standardization_governance_policy": assessment_standardization_governance_policy,
            "assessment_progression_loop_policy": assessment_progression_loop_policy,
            "assessment_readme_assessment_sync_policy": assessment_readme_assessment_sync_policy,
            "process_gate_iteration_policy": process_gate_iteration_policy,
            "process_followup_testing_loop_policy": process_followup_testing_loop_policy,
            "process_section_sync_audit_policy": process_section_sync_audit_policy,
            "process_readme_update_enforcement_policy": process_readme_update_enforcement_policy,
            "process_standardization_hygiene_policy": process_standardization_hygiene_policy,
            "full_section_coverage_audit_policy": full_section_coverage_audit_policy,
            "recommendation_acceptance_trace_policy": recommendation_acceptance_trace_policy,
            "iterative_test_loop_enforcement_policy": iterative_test_loop_enforcement_policy,
            "readme_assessment_consistency_policy": readme_assessment_consistency_policy,
            "standardization_terminology_lock_policy": standardization_terminology_lock_policy,
            "section_transition_handoff_policy": section_transition_handoff_policy,
            "section_evidence_traceability_policy": section_evidence_traceability_policy,
            "section_recommendation_closure_policy": section_recommendation_closure_policy,
            "section_quality_gate_policy": section_quality_gate_policy,
            "section_snapshot_publication_policy": section_snapshot_publication_policy,
            "all_section_review_coverage_policy": all_section_review_coverage_policy,
            "all_section_recommendation_acceptance_policy": all_section_recommendation_acceptance_policy,
            "all_section_progression_gate_policy": all_section_progression_gate_policy,
            "all_section_standardization_lock_policy": all_section_standardization_lock_policy,
            "all_section_reporting_sync_policy": all_section_reporting_sync_policy,
            "recommendation_acceptance_attestation_policy": recommendation_acceptance_attestation_policy,
            "recommendation_execution_checkpoint_policy": recommendation_execution_checkpoint_policy,
            "recommendation_test_evidence_policy": recommendation_test_evidence_policy,
            "recommendation_section_sync_policy": recommendation_section_sync_policy,
            "recommendation_completion_report_policy": recommendation_completion_report_policy,
            "section_1_to_14_continuity_policy": section_1_to_14_continuity_policy,
            "section_recommendation_acceptance_audit_policy": section_recommendation_acceptance_audit_policy,
            "section_recommendation_implementation_trace_policy": section_recommendation_implementation_trace_policy,
            "section_followup_test_loop_policy": section_followup_test_loop_policy,
            "section_readme_assessment_lockstep_policy": section_readme_assessment_lockstep_policy,
            "section_completion_delta_reporting_policy": section_completion_delta_reporting_policy,
            "section_micro_build_tracking_policy": section_micro_build_tracking_policy,
            "section_prompt_increment_logging_policy": section_prompt_increment_logging_policy,
            "section_recommendation_acceptance_evidence_policy": section_recommendation_acceptance_evidence_policy,
            "section_change_budget_tracking_policy": section_change_budget_tracking_policy,
            "section_test_result_reporting_policy": section_test_result_reporting_policy,
            "section_warning_budget_policy": section_warning_budget_policy,
            "section_retest_trigger_policy": section_retest_trigger_policy,
            "section_documentation_accuracy_policy": section_documentation_accuracy_policy,
            "section_loop_exit_criteria_policy": section_loop_exit_criteria_policy,
            "section_recommendation_priority_policy": section_recommendation_priority_policy,
            "section_recommendation_dependency_policy": section_recommendation_dependency_policy,
            "section_risk_escalation_policy": section_risk_escalation_policy,
            "section_completion_signoff_policy": section_completion_signoff_policy,
            "section_continuous_improvement_policy": section_continuous_improvement_policy,
            "section_recommendation_conflict_resolution_policy": section_recommendation_conflict_resolution_policy,
            "section_dependency_unblock_policy": section_dependency_unblock_policy,
            "section_regression_guard_policy": section_regression_guard_policy,
            "section_release_readiness_policy": section_release_readiness_policy,
            "section_traceability_index_policy": section_traceability_index_policy,
            "section_acceptance_criteria_enforcement_policy": section_acceptance_criteria_enforcement_policy,
            "section_artifact_quality_review_policy": section_artifact_quality_review_policy,
            "section_retest_on_change_policy": section_retest_on_change_policy,
            "section_documentation_trace_policy": section_documentation_trace_policy,
            "section_release_gate_attestation_policy": section_release_gate_attestation_policy,
            "section_dependency_health_policy": section_dependency_health_policy,
            "section_recommendation_sla_policy": section_recommendation_sla_policy,
            "section_documentation_sync_policy": section_documentation_sync_policy,
            "section_validation_signal_policy": section_validation_signal_policy,
            "section_handoff_audit_policy": section_handoff_audit_policy,
            "section_change_control_policy": section_change_control_policy,
            "section_quality_drift_policy": section_quality_drift_policy,
            "section_verification_retry_policy": section_verification_retry_policy,
            "section_governance_exception_budget_policy": section_governance_exception_budget_policy,
            "section_release_documentation_gate_policy": section_release_documentation_gate_policy,
            "section_contract_compliance_link_policy": section_contract_compliance_link_policy,
            "section_cost_center_attribution_policy": section_cost_center_attribution_policy,
            "section_unowned_work_throwback_policy": section_unowned_work_throwback_policy,
            "section_change_order_trigger_policy": section_change_order_trigger_policy,
            "section_manager_assignment_policy": section_manager_assignment_policy,
            "section_enterprise_operating_model_policy": section_enterprise_operating_model_policy,
            "section_unaccounted_work_classification_policy": section_unaccounted_work_classification_policy,
            "section_manager_throwback_routing_policy": section_manager_throwback_routing_policy,
            "section_scope_boundary_enforcement_policy": section_scope_boundary_enforcement_policy,
            "section_change_order_authority_policy": section_change_order_authority_policy,
            "section_completion_verification_policy": section_completion_verification_policy,
            "section_recommendation_rollforward_policy": section_recommendation_rollforward_policy,
            "section_dependency_traceability_policy": section_dependency_traceability_policy,
            "section_operational_readiness_policy": section_operational_readiness_policy,
            "section_reporting_attestation_policy": section_reporting_attestation_policy,
            "section_governance_traceability_policy": section_governance_traceability_policy,
            "section_progress_checkpoint_policy": section_progress_checkpoint_policy,
            "section_acceptance_verification_policy": section_acceptance_verification_policy,
            "section_sync_integrity_policy": section_sync_integrity_policy,
            "section_lifecycle_reporting_policy": section_lifecycle_reporting_policy,
            "section_contractual_risk_alignment_policy": section_contractual_risk_alignment_policy,
            "section_compliance_rulepack_sync_policy": section_compliance_rulepack_sync_policy,
            "section_authoritative_source_integrity_policy": section_authoritative_source_integrity_policy,
            "section_budget_gate_reconciliation_policy": section_budget_gate_reconciliation_policy,
            "section_governance_override_hierarchy_policy": section_governance_override_hierarchy_policy,
            "section_policy_pack_versioning_policy": section_policy_pack_versioning_policy,
            "section_authority_delegation_revocation_policy": section_authority_delegation_revocation_policy,
            "section_evidence_immutability_policy": section_evidence_immutability_policy,
            "section_compute_plane_replay_attestation_policy": section_compute_plane_replay_attestation_policy,
            "section_swarm_isolation_boundary_policy": section_swarm_isolation_boundary_policy,
            "section_risk_tolerance_boundary_policy": section_risk_tolerance_boundary_policy,
            "section_approval_delegation_integrity_policy": section_approval_delegation_integrity_policy,
            "section_budget_anomaly_circuit_breaker_policy": section_budget_anomaly_circuit_breaker_policy,
            "section_compliance_evidence_freshness_policy": section_compliance_evidence_freshness_policy,
            "section_decision_packet_trace_policy": section_decision_packet_trace_policy,
            "section_exec_authority_gate_policy": section_exec_authority_gate_policy,
            "section_compute_plane_determinism_policy": section_compute_plane_determinism_policy,
            "section_change_order_budget_delta_policy": section_change_order_budget_delta_policy,
            "section_domain_swarm_accountability_policy": section_domain_swarm_accountability_policy,
            "section_audit_packet_release_policy": section_audit_packet_release_policy,
            "section_request_envelope_integrity_policy": section_request_envelope_integrity_policy,
            "section_gate_graph_compilation_policy": section_gate_graph_compilation_policy,
            "section_domain_swarm_routing_policy": section_domain_swarm_routing_policy,
            "section_compute_replay_consistency_policy": section_compute_replay_consistency_policy,
            "section_authority_scope_binding_policy": section_authority_scope_binding_policy,
            "section_request_envelope_auditability_policy": section_request_envelope_auditability_policy,
            "section_gate_dependency_replay_policy": section_gate_dependency_replay_policy,
            "section_domain_escalation_binding_policy": section_domain_escalation_binding_policy,
            "section_budget_variance_justification_policy": section_budget_variance_justification_policy,
            "section_release_packet_signoff_policy": section_release_packet_signoff_policy,
            "section_authority_chain_escalation_policy": section_authority_chain_escalation_policy,
            "section_gate_decision_replay_policy": section_gate_decision_replay_policy,
            "section_rulepack_refresh_attestation_policy": section_rulepack_refresh_attestation_policy,
            "section_domain_owner_ack_policy": section_domain_owner_ack_policy,
            "section_handoff_readiness_attestation_policy": section_handoff_readiness_attestation_policy,
            "section_execution_audit_trail_policy": section_execution_audit_trail_policy,
            "section_policy_enforcement_checkpoint_policy": section_policy_enforcement_checkpoint_policy,
            "section_change_scope_integrity_policy": section_change_scope_integrity_policy,
            "section_domain_handoff_chain_policy": section_domain_handoff_chain_policy,
            "section_release_attestation_packet_policy": section_release_attestation_packet_policy,
            "section_contract_scope_recheck_policy": section_contract_scope_recheck_policy,
            "section_proposal_change_order_trace_policy": section_proposal_change_order_trace_policy,
            "section_gate_graph_dependency_guard_policy": section_gate_graph_dependency_guard_policy,
            "section_evidence_store_attestation_policy": section_evidence_store_attestation_policy,
            "section_release_readout_integrity_policy": section_release_readout_integrity_policy,
            "section_governance_sla_policy": section_governance_sla_policy,
            "section_authority_chain_replay_policy": section_authority_chain_replay_policy,
            "section_change_order_scope_lock_policy": section_change_order_scope_lock_policy,
            "section_evidence_lineage_policy": section_evidence_lineage_policy,
            "section_decision_trace_attestation_policy": section_decision_trace_attestation_policy,
            "section_rulepack_activation_policy": section_rulepack_activation_policy,
            "section_gate_input_allowlist_policy": section_gate_input_allowlist_policy,
            "section_nte_change_order_policy": section_nte_change_order_policy,
            "section_approval_identity_binding_policy": section_approval_identity_binding_policy,
            "section_compute_reproducibility_window_policy": section_compute_reproducibility_window_policy,
            "section_refusal_reason_standard_policy": section_refusal_reason_standard_policy,
            "section_escalation_reason_code_policy": section_escalation_reason_code_policy,
            "section_authority_delegation_expiry_policy": section_authority_delegation_expiry_policy,
            "section_budget_tag_enforcement_policy": section_budget_tag_enforcement_policy,
            "section_evidence_snapshot_replay_policy": section_evidence_snapshot_replay_policy,
            "section_budget_circuit_breaker_policy": section_budget_circuit_breaker_policy,
            "section_change_order_authority_scope_policy": section_change_order_authority_scope_policy,
            "section_evidence_signature_policy": section_evidence_signature_policy,
            "section_domain_escalation_sla_policy": section_domain_escalation_sla_policy,
            "section_governance_override_precedence_policy": section_governance_override_precedence_policy,
            "section_gate_outcome_reason_integrity_policy": section_gate_outcome_reason_integrity_policy,
            "section_authority_signature_validation_policy": section_authority_signature_validation_policy,
            "section_compute_replay_snapshot_policy": section_compute_replay_snapshot_policy,
            "section_budget_control_trace_policy": section_budget_control_trace_policy,
            "section_release_evidence_bundle_policy": section_release_evidence_bundle_policy,
            "section_gate_evaluation_determinism_policy": section_gate_evaluation_determinism_policy,
            "section_authority_override_documentation_policy": section_authority_override_documentation_policy,
            "section_change_order_dependency_validation_policy": section_change_order_dependency_validation_policy,
            "section_budget_forecast_alignment_policy": section_budget_forecast_alignment_policy,
            "section_handoff_audit_completion_policy": section_handoff_audit_completion_policy,
            "section_gate_decision_signature_policy": section_gate_decision_signature_policy,
            "section_authority_scope_timeout_policy": section_authority_scope_timeout_policy,
            "section_change_order_cost_trace_policy": section_change_order_cost_trace_policy,
            "section_evidence_checkpoint_policy": section_evidence_checkpoint_policy,
            "section_release_packet_consistency_policy": section_release_packet_consistency_policy,
            "section_authority_recertification_policy": section_authority_recertification_policy,
            "section_budget_forecast_variance_policy": section_budget_forecast_variance_policy,
            "section_evidence_hash_chain_policy": section_evidence_hash_chain_policy,
            "section_gate_timeout_enforcement_policy": section_gate_timeout_enforcement_policy,
            "section_release_exception_register_policy": section_release_exception_register_policy,
            "section_domain_owner_escalation_policy": section_domain_owner_escalation_policy,
            "section_gate_dependency_trace_policy": section_gate_dependency_trace_policy,
            "section_budget_variance_escalation_policy": section_budget_variance_escalation_policy,
            "section_evidence_lineage_recheck_policy": section_evidence_lineage_recheck_policy,
            "section_release_authority_replay_policy": section_release_authority_replay_policy,
            "section_gate_reason_code_replay_policy": section_gate_reason_code_replay_policy,
            "section_approval_delegation_registry_policy": section_approval_delegation_registry_policy,
            "section_budget_cap_change_log_policy": section_budget_cap_change_log_policy,
            "section_evidence_attestation_signature_policy": section_evidence_attestation_signature_policy,
            "section_release_governance_manifest_policy": section_release_governance_manifest_policy,
            "section_governance_path_integrity_policy": section_governance_path_integrity_policy,
            "section_policy_exception_disposition_policy": section_policy_exception_disposition_policy,
            "section_budget_reforecast_attestation_policy": section_budget_reforecast_attestation_policy,
            "section_evidence_chain_custody_policy": section_evidence_chain_custody_policy,
            "section_release_authorization_token_policy": section_release_authorization_token_policy,
            "section_governance_checkpoint_replay_policy": section_governance_checkpoint_replay_policy,
            "section_authority_token_rotation_policy": section_authority_token_rotation_policy,
            "section_budget_spike_containment_policy": section_budget_spike_containment_policy,
            "section_evidence_bundle_hash_policy": section_evidence_bundle_hash_policy,
            "section_release_exception_revalidation_policy": section_release_exception_revalidation_policy,
            "section_governance_policy_reconciliation_policy": section_governance_policy_reconciliation_policy,
            "section_authority_chain_expiry_policy": section_authority_chain_expiry_policy,
            "section_budget_exception_audit_policy": section_budget_exception_audit_policy,
            "section_gate_signature_rotation_policy": section_gate_signature_rotation_policy,
            "section_release_packet_attestation_policy": section_release_packet_attestation_policy,
            "section_governance_rollup_consistency_policy": section_governance_rollup_consistency_policy,
            "section_authority_chain_snapshot_policy": section_authority_chain_snapshot_policy,
            "section_budget_envelope_audit_policy": section_budget_envelope_audit_policy,
            "section_evidence_manifest_replay_policy": section_evidence_manifest_replay_policy,
            "section_release_override_justification_policy": section_release_override_justification_policy,
            "section_governance_decision_envelope_policy": section_governance_decision_envelope_policy,
            "section_authority_recusal_trace_policy": section_authority_recusal_trace_policy,
            "section_budget_guardrail_replay_policy": section_budget_guardrail_replay_policy,
            "section_evidence_provenance_reconciliation_policy": section_evidence_provenance_reconciliation_policy,
            "section_release_attestation_chain_policy": section_release_attestation_chain_policy,
            "section_governance_trace_seal_policy": section_governance_trace_seal_policy,
            "section_authority_replay_token_policy": section_authority_replay_token_policy,
            "section_budget_exception_replay_policy": section_budget_exception_replay_policy,
            "section_evidence_freshness_recertification_policy": section_evidence_freshness_recertification_policy,
            "section_release_handoff_replay_policy": section_release_handoff_replay_policy,
            "section_governance_audit_recertification_policy": section_governance_audit_recertification_policy,
            "section_authority_scope_exception_policy": section_authority_scope_exception_policy,
            "section_budget_change_envelope_policy": section_budget_change_envelope_policy,
            "section_evidence_chain_seal_policy": section_evidence_chain_seal_policy,
            "section_release_gate_replay_policy": section_release_gate_replay_policy,
            "section_governance_exception_timeout_policy": section_governance_exception_timeout_policy,
            "section_authority_delegation_ledger_policy": section_authority_delegation_ledger_policy,
            "section_budget_burnrate_attestation_policy": section_budget_burnrate_attestation_policy,
            "section_evidence_snapshot_expiry_policy": section_evidence_snapshot_expiry_policy,
            "section_release_override_reconciliation_policy": section_release_override_reconciliation_policy,
            "section_governance_ledger_integrity_policy": section_governance_ledger_integrity_policy,
            "section_authority_chain_digest_policy": section_authority_chain_digest_policy,
            "section_budget_reconciliation_digest_policy": section_budget_reconciliation_digest_policy,
            "section_evidence_checkpoint_digest_policy": section_evidence_checkpoint_digest_policy,
            "section_release_chain_digest_policy": section_release_chain_digest_policy,
            "section_governance_policy_replay_lock_policy": section_governance_policy_replay_lock_policy,
            "section_authority_chain_nonce_policy": section_authority_chain_nonce_policy,
            "section_budget_override_attestation_policy": section_budget_override_attestation_policy,
            "section_evidence_packet_nonce_policy": section_evidence_packet_nonce_policy,
            "section_release_gate_override_policy": section_release_gate_override_policy,
            "section_governance_dependency_sequencing_policy": section_governance_dependency_sequencing_policy,
            "section_authority_scope_replay_attestation_policy": section_authority_scope_replay_attestation_policy,
            "section_budget_allocation_trace_policy": section_budget_allocation_trace_policy,
            "section_evidence_manifest_freshness_policy": section_evidence_manifest_freshness_policy,
            "section_release_override_chain_policy": section_release_override_chain_policy,
            "section_governance_verification_digest_policy": section_governance_verification_digest_policy,
            "section_authority_scope_nonce_rotation_policy": section_authority_scope_nonce_rotation_policy,
            "section_budget_forecast_lock_policy": section_budget_forecast_lock_policy,
            "section_evidence_bundle_canonicalization_policy": section_evidence_bundle_canonicalization_policy,
            "section_release_attestation_digest_policy": section_release_attestation_digest_policy,
            "section_governance_dependency_nonce_lock_policy": section_governance_dependency_nonce_lock_policy,
            "section_authority_override_recertification_policy": section_authority_override_recertification_policy,
            "section_budget_exception_rebind_policy": section_budget_exception_rebind_policy,
            "section_evidence_packet_reseal_policy": section_evidence_packet_reseal_policy,
            "section_release_gate_drift_policy": section_release_gate_drift_policy,
            "hitl_escalation_comfort_policy": hitl_escalation_comfort_policy,
            "safety_level": safety_level,
            "escalation_policy": escalation_policy,
            "budget_constraints": source.get("budget_constraints", source.get("budget_ceiling", "standard")),
            "tool_permissions": source.get("tool_permissions", "governed_default"),
            "audit_requirements": audit_requirements,
            "autonomy_level": autonomy_level
        }

    def _build_summary_surface_consistency(
        self,
        summary_bundle: Optional[Dict[str, Any]] = None,
        module_registry_status: Optional[Dict[str, Any]] = None,
        completion_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        bundle = summary_bundle or self._build_summary_surface_bundle()
        module_status = module_registry_status or self.module_manager.get_module_status()
        completion_data = completion_snapshot or self._build_completion_snapshot()
        module_summary = bundle.get("module_registry_summary", {})
        module_total = module_status.get("total_available")
        if module_total is None:
            module_total = len(module_status.get("modules", {}))
        checks = {
            "integration_summary_present": bool(bundle.get("integration_capabilities_summary")),
            "alignment_summary_present": bool(bundle.get("competitive_feature_alignment_summary")),
            "completion_snapshot_present": bool(completion_data.get("areas")),
            "registry_total_matches_status": module_summary.get("total_available") == module_total,
            "registry_core_complete": (
                module_summary.get("core_registered") == module_summary.get("core_expected")
            ) and (
                module_summary.get("core_missing") == []
            )
        }
        status = "consistent" if all(checks.values()) else "drift_detected"
        return {"status": status, "checks": checks}

    def _get_adapter_availability(self) -> Dict[str, bool]:
        if self._adapter_availability is None:
            self._adapter_availability = {}
            for adapter in self.CORE_ADAPTER_CANDIDATES:
                module_name = adapter["module"]
                try:
                    self._adapter_availability[module_name] = importlib.util.find_spec(module_name) is not None
                except (AttributeError, ImportError, ModuleNotFoundError, TypeError, ValueError) as exc:
                    logger.warning("Adapter availability check failed for %s: %s", module_name, exc)
                    self._adapter_availability[module_name] = False
        return self._adapter_availability

    def _suggest_gap_action(self, subsystem_id: str, entry: Optional[Dict[str, Any]]) -> str:
        if not entry or not entry.get("available"):
            return "Install or restore module files to enable this subsystem."
        if not entry.get("wired"):
            return "Wire this subsystem into execute_task or form processing."
        if not entry.get("initialized"):
            return "Initialize subsystem during runtime startup."
        return "No gap detected."

    def _build_capability_alignment(self, planned_subsystems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        audit = self.get_activation_audit()
        module_lookup = {module["id"]: module for module in audit.get("modules", [])}
        alignment = []
        for subsystem in planned_subsystems:
            entry = module_lookup.get(subsystem["id"])
            available = bool(entry and entry.get("available"))
            wired = bool(entry and entry.get("wired"))
            initialized = bool(entry and entry.get("initialized"))
            activated = bool(entry and entry.get("activated"))
            capability_reflects = available and wired
            gap_reason = "ready" if capability_reflects else "gap"
            if not available:
                gap_reason = "missing"
            elif not wired:
                gap_reason = "not_wired"
            elif not initialized:
                gap_reason = "not_initialized"
            alignment.append({
                "id": subsystem["id"],
                "available": available,
                "wired": wired,
                "initialized": initialized,
                "activated": activated,
                "capability_reflects": capability_reflects,
                "gap_reason": gap_reason,
                "gap_action": self._suggest_gap_action(subsystem["id"], entry)
            })
        return alignment

    def _build_autonomy_extension_status(self) -> List[Dict[str, Any]]:
        integration_ready = bool(getattr(self, "integration_engine", None))
        scheduler_ready = bool(getattr(self, "governance_scheduler", None))
        business_ready = bool(getattr(self, "inoni_automation", None))
        flow_ready = bool(getattr(self, "flow_steps", None))

        extensions = [
            {
                "id": "remote_access_invite",
                "name": "Remote access onboarding",
                "status": "needs_integration",
                "evidence": "No remote access adapter is wired in runtime 1.0.",
                "gap_action": "Integrate secure access provisioning (SSO/VPN) and approval gates."
            },
            {
                "id": "delphi_ticketing",
                "name": "Delphi AI ticket management",
                "status": "partial" if integration_ready else "needs_integration",
                "evidence": "Integration engine available; no ticketing adapter configured." if integration_ready else "Integration engine unavailable.",
                "gap_action": "Add a ticketing adapter and bind to librarian/HITL workflows."
            },
            {
                "id": "auto_patching",
                "name": "Update/rollback automation",
                "status": "partial" if scheduler_ready else "needs_integration",
                "evidence": "Scheduler can register triggers; patch orchestration not wired." if scheduler_ready else "Scheduler unavailable for patch triggers.",
                "gap_action": "Wire patch orchestration + rollback playbooks into governance scheduler."
            },
            {
                "id": "business_metrics_scaling",
                "name": "Business metrics & scaling",
                "status": "available" if business_ready else "needs_integration",
                "evidence": "Inoni automation engine provides metrics summary." if business_ready else "Business automation engine not initialized.",
                "gap_action": "Initialize automation engine and bind metrics to executive gates."
            },
            {
                "id": "self_service_onboarding",
                "name": "Self-service onboarding",
                "status": "available" if flow_ready else "needs_configuration",
                "evidence": "Onboarding flow stages are defined in runtime." if flow_ready else "Onboarding flow steps are missing.",
                "gap_action": "Define onboarding questions and map them to gate policies."
            }
        ]
        return extensions

    def _check_llm_readiness(self) -> Dict[str, Any]:
        candidates = self.LLM_MODULE_CANDIDATES
        available = []
        for name in candidates:
            try:
                if importlib.util.find_spec(name) is not None:
                    available.append(name)
            except (ModuleNotFoundError, ValueError, ImportError):
                continue
        status = "available" if available else "not_configured"
        return {"status": status, "modules": available}

    def _calculate_success_rate(self, success: int, total: int) -> float:
        if not total:
            return 0.0
        if success > total:
            logger.warning("Success count exceeds total: %s > %s", success, total)
            success = total
        return (success / total) * 100

    @staticmethod
    def _format_average_execution_time(total: int, total_time: float) -> str:
        return f"{(total_time / total):.3f}s" if total else "0.000s"

    def _build_automation_execution_evaluation(
        self,
        metrics: Dict[str, Any],
        business_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        total = metrics.get("total", 0)
        success = metrics.get("success", 0)
        success_rate = self._calculate_success_rate(success, total)
        average_time = self._format_average_execution_time(total, metrics.get("total_time", 0.0))
        automation_loops_ready = bool(getattr(self, "inoni_automation", None))
        business_signals = business_summary is not None and len(business_summary) > 0
        if total == 0:
            status = "not_executed"
            gap_action = "Run /api/forms/task-execution or /api/automation to log execution metrics."
        elif success_rate < self.AUTOMATION_EXECUTION_SUCCESS_THRESHOLD:
            status = "needs_attention"
            gap_action = "Review failed executions and adjust gates or workflows."
        else:
            status = "validated"
            gap_action = "Execution success rate meets threshold."
        return {
            "status": status,
            "total_executions": total,
            "success_rate": f"{success_rate:.1f}%",
            "average_execution_time": average_time,
            "automation_loops_ready": automation_loops_ready,
            "business_summary_available": business_signals,
            "gap_action": gap_action
        }

    @staticmethod
    def _build_competitive_comparison(automation_execution: Dict[str, Any]) -> Dict[str, Any]:
        execution_status = automation_execution.get("status") or "not_executed"
        status = "baseline_ready" if execution_status == "validated" else "advisory"
        note = (
            "Competitive comparisons are advisory until automation execution is validated."
            if status != "baseline_ready"
            else "Execution metrics are validated; comparisons can be benchmarked."
        )
        return {
            "status": status,
            "targets": [
                {"platform": "Zapier", "focus": "integration automation"},
                {"platform": "Make", "focus": "visual workflow builders"},
                {"platform": "n8n", "focus": "self-hosted automation"}
            ],
            "note": note,
            "next_action": "Collect external benchmarks and compare execution metrics."
        }

    def _build_capability_review(
        self,
        capability_tests: List[Dict[str, Any]],
        capability_alignment: List[Dict[str, Any]],
        org_chart_plan: Dict[str, Any],
        sensor_plan: Dict[str, Any],
        business_summary: Dict[str, Any],
        learning_loop: Optional[Dict[str, Any]] = None,
        delivery_readiness: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        status_counts = {
            "ok": 0,
            "error": 0,
            "needs_info": 0,
            "not_initialized": 0,
            "not_configured": 0,
            "other": 0
        }
        gap_entries = []
        for test in capability_tests:
            status = test.get("status", "other")
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts["other"] += 1
            if status != "ok":
                gap_entries.append({
                    "id": test.get("id", "unknown"),
                    "status": status,
                    "issue": test.get("error") or test.get("message") or "Requires follow-up."
                })

        alignment_gaps = [
            {
                "id": entry["id"],
                "gap_reason": entry.get("gap_reason"),
                "gap_action": entry.get("gap_action")
            }
            for entry in capability_alignment
            if not entry.get("capability_reflects")
        ]
        gap_entries.extend(alignment_gaps)

        metrics = getattr(self, "execution_metrics", {"total": 0, "success": 0, "total_time": 0.0})
        total = metrics.get("total", 0)
        success_rate = self._calculate_success_rate(metrics.get("success", 0), total)
        automation_execution = self._build_automation_execution_evaluation(metrics, business_summary)
        competitive_comparison = self._build_competitive_comparison(automation_execution)

        deterministic_ready_count = len([test for test in capability_tests if test.get("status") == "ok"])
        llm_readiness = self._check_llm_readiness()
        llm_status = llm_readiness["status"]
        llm_gap_action = (
            "Bind LLM adapters into execution + ticketing flows."
            if llm_status != "available"
            else "LLM adapters configured and ready."
        )
        llm_ready_count = len(llm_readiness["modules"])
        workload_balance = {
            "deterministic_ready_count": deterministic_ready_count,
            "llm_ready_count": llm_ready_count,
            "llm_status": llm_status,
            "llm_modules": llm_readiness["modules"],
            "gap_action": llm_gap_action
        }
        learning_loop = learning_loop or {}
        delivery_readiness = delivery_readiness or {}

        return {
            "summary": {
                "total": len(capability_tests),
                **status_counts
            },
            "execution_metrics": {
                "total_executions": total,
                "success_rate": f"{success_rate:.1f}%",
                "average_execution_time": self._format_average_execution_time(
                    total,
                    metrics.get("total_time", 0.0)
                )
            },
            "automation_execution": automation_execution,
            "org_chart_coverage": org_chart_plan.get("coverage_summary", {}),
            "regulatory_scope": {
                "region": sensor_plan.get("region"),
                "primary_source": sensor_plan.get("primary_regulatory_source", {}).get("id"),
                "sources": [source.get("id") for source in sensor_plan.get("regulatory_sources", [])]
            },
            "workload_balance": workload_balance,
            "learning_loop": learning_loop,
            "delivery_readiness": delivery_readiness,
            "automation_extensions": self._build_autonomy_extension_status(),
            "competitive_comparison": competitive_comparison,
            "gaps": gap_entries
        }

    def _run_gap_solution_attempts(
        self,
        task_description: str,
        doc: LivingDocument,
        onboarding_context: Optional[Dict[str, Any]],
        sensor_plan: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if doc.capability_tests:
            return doc.capability_tests
        context = onboarding_context or {}
        results: List[Dict[str, Any]] = []
        results.append(self._attempt_gate_synthesis(task_description, doc, onboarding_context, sensor_plan))
        results.append(self._attempt_domain_swarm(task_description, context))
        results.append(self._attempt_true_swarm(task_description, context))
        results.append(self._attempt_infinity_expansion(task_description))
        results.append(self._attempt_knowledge_gap(task_description, context))
        results.append(self._attempt_org_chart(task_description, doc))
        results.append(self._attempt_compute_plane())
        results.append(self._attempt_recursive_stability())
        results.append(self._attempt_business_automation())
        doc.capability_tests = results
        return results

    def _attempt_gate_synthesis(
        self,
        task_description: str,
        doc: LivingDocument,
        onboarding_context: Optional[Dict[str, Any]],
        sensor_plan: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            from src.gate_synthesis import FailureMode, RiskVector, GateGenerator
            from src.gate_synthesis.models import FailureModeType
            from src.confidence_engine.models import Phase as ConfidenceEnginePhase, AuthorityBand

            risk_vector = RiskVector(
                H=max(0.0, 1.0 - doc.confidence),
                one_minus_D=0.4,
                exposure=0.3,
                authority_risk=0.2
            )
            truncated_description = self._truncate_description(task_description)
            failure_mode = FailureMode(
                id=uuid4().hex,
                type=FailureModeType.CONSTRAINT_VIOLATION,
                probability=0.6,
                impact=0.6,
                risk_vector=risk_vector,
                description=f"Autogenerated for: {truncated_description}"
            )
            generator = GateGenerator()
            gates = generator.generate_gates(
                [failure_mode],
                ConfidenceEnginePhase.EXPAND,
                AuthorityBand.PROPOSE,
                {failure_mode.id: failure_mode.probability}
            )
            control_data = self._build_gate_control_data(task_description, doc, onboarding_context, sensor_plan)
            gate_summaries = []
            for gate in gates:
                summary = self._summarize_gate(gate)
                summary.update(control_data)
                gate_summaries.append(summary)
            return {"id": "gate_synthesis", "status": "ok", "gates": gate_summaries}
        except Exception as exc:
            return {"id": "gate_synthesis", "status": "error", "error": str(exc)}

    def _attempt_domain_swarm(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.domain_swarms import DomainDetector
            from src.mfgc_core import Phase as MfgcCorePhase

            detector = DomainDetector()
            domain = detector.detect_domain(task_description, context)
            if not domain and any(keyword in task_description.lower() for keyword in [
                "business", "marketing", "executive", "operations", "qa", "contract", "hitl"
            ]):
                domain = "business_strategy"
            if not domain:
                return {
                    "id": "domain_swarms",
                    "status": "needs_info",
                    "message": "No domain match; add domain-specific onboarding details."
                }
            swarm = detector.get_swarm(domain)
            candidates = swarm.generate_candidates(task_description, MfgcCorePhase.EXPAND, context)
            gates = swarm.generate_gates(candidates, context)
            if not gates:
                return {
                    "id": "domain_swarms",
                    "status": "needs_info",
                    "domain": domain,
                    "message": "Domain gates not generated; refine onboarding details."
                }
            serialized_gates = [asdict(gate) if is_dataclass(gate) else gate for gate in gates]
            return {
                "id": "domain_swarms",
                "status": "ok",
                "domain": domain,
                "candidate_count": len(candidates),
                # Limit sample gates to avoid response bloat.
                "sample_gates": serialized_gates[:self.MAX_SAMPLE_GATES]
            }
        except Exception as exc:
            return {"id": "domain_swarms", "status": "error", "error": str(exc)}

    def _attempt_true_swarm(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.swarm_system:
                return {"id": "true_swarm_system", "status": "not_initialized"}
            if not hasattr(self.swarm_system, "execute_full_cycle"):
                return {
                    "id": "true_swarm_system",
                    "status": "error",
                    "error": "TrueSwarmSystem missing execute_full_cycle"
                }
            result = self.swarm_system.execute_full_cycle(task_description, context)
            return {
                "id": "true_swarm_system",
                "status": "ok",
                "phases": result.get("phases", []),
                "total_artifacts": result.get("total_artifacts"),
                "total_gates": result.get("total_gates"),
                "final_confidence": result.get("final_confidence"),
                "murphy_risk": result.get("avg_murphy_risk")
            }
        except Exception as exc:
            return {"id": "true_swarm_system", "status": "error", "error": str(exc)}

    def _attempt_infinity_expansion(self, task_description: str) -> Dict[str, Any]:
        try:
            from src.infinity_expansion_system import InfinityExpansionEngine

            engine = InfinityExpansionEngine()
            result = engine.expand_task(task_description, max_iterations=1)
            return {"id": "infinity_expansion_system", "status": "ok", "result": asdict(result)}
        except Exception as exc:
            return {"id": "infinity_expansion_system", "status": "error", "error": str(exc)}

    def _attempt_knowledge_gap(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.knowledge_gap_system import KnowledgeGapDetector

            detector = KnowledgeGapDetector()
            analysis = detector.analyze_query(task_description, context)
            return {"id": "knowledge_gap_system", "status": "ok", "analysis": analysis}
        except Exception as exc:
            return {"id": "knowledge_gap_system", "status": "error", "error": str(exc)}

    def _attempt_compute_plane(self) -> Dict[str, Any]:
        try:
            from src.compute_plane.service import ComputeService

            service = ComputeService(enable_caching=False)
            validation = service.validate_expression("1+1", "sympy")
            return {"id": "compute_plane", "status": "ok", "validation": validation}
        except Exception as exc:
            return {"id": "compute_plane", "status": "error", "error": str(exc)}

    def _attempt_recursive_stability(self) -> Dict[str, Any]:
        try:
            from src.recursive_stability_controller.rsc_service import RecursiveStabilityController

            controller = RecursiveStabilityController()
            result = controller.run_control_cycle()
            return {"id": "recursive_stability_controller", "status": "ok", "cycle": result}
        except Exception as exc:
            return {"id": "recursive_stability_controller", "status": "error", "error": str(exc)}

    def _attempt_org_chart(self, task_description: str, doc: LivingDocument) -> Dict[str, Any]:
        if not self.org_chart_system:
            return {"id": "org_chart_system", "status": "not_initialized"}
        try:
            deliverables = self._extract_deliverables(doc)
            plan = self._build_org_chart_plan(task_description, deliverables)
            return {
                "id": "org_chart_system",
                "status": plan.get("status", "unknown"),
                "positions_required": len(plan.get("required_positions", [])),
                "coverage_summary": plan.get("coverage_summary", {})
            }
        except Exception as exc:
            return {"id": "org_chart_system", "status": "error", "error": str(exc)}

    def _attempt_business_automation(self) -> Dict[str, Any]:
        if not self.inoni_automation:
            return {"id": "inoni_business_automation", "status": "not_initialized"}
        try:
            summary = self.inoni_automation.run_daily_automation()
            return {"id": "inoni_business_automation", "status": "ok", "summary": summary}
        except Exception as exc:
            return {"id": "inoni_business_automation", "status": "error", "error": str(exc)}

    def _build_activation_preview(
        self,
        doc: LivingDocument,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        text = task_description.lower()  # Normalize for keyword matching.
        candidates = [
            {
                "id": "gate_synthesis",
                "reason": "Translate onboarding intent into gate checks.",
                "keywords": ["gate", "risk", "compliance", "safety"]
            },
            {
                "id": "inoni_business_automation",
                "reason": "Run self-automation loops for business operations.",
                "keywords": ["business", "inoni", "self", "automation", "sales", "marketing", "production", "billing"]
            },
            {
                "id": "true_swarm_system",
                "reason": "Expand tasks into swarm execution stages.",
                "keywords": ["swarm", "automation", "workflow", "pipeline"]
            },
            {
                "id": "domain_swarms",
                "reason": "Select domain-specific swarm strategies.",
                "keywords": ["domain", "industry", "software", "marketing", "sales", "finance"]
            },
            {
                "id": "org_chart_system",
                "reason": "Map deliverables to positions and contract coverage.",
                "keywords": ["org", "organization", "role", "position", "contract", "staff", "team", "executive"]
            },
            {
                "id": "infinity_expansion_system",
                "reason": "Expand initial request into deeper requirements.",
                "keywords": ["expand", "discover", "requirements", "scope"]
            },
            {
                "id": "compute_plane",
                "reason": "Deterministic compute plane for symbolic/numeric processing.",
                "keywords": ["calculate", "optimize", "compute", "formula"]
            },
            {
                "id": "knowledge_gap_system",
                "reason": "Detect gaps and generate clarifying questions.",
                "keywords": ["gap", "clarify", "unknown", "assumption"]
            },
            {
                "id": "recursive_stability_controller",
                "reason": "Stability controls for complex automation feedback loops.",
                "keywords": ["stability", "feedback", "drift", "control"]
            }
        ]
        planned_subsystems = [
            {"id": item["id"], "reason": item["reason"]}
            for item in candidates
            if any(keyword in text for keyword in item["keywords"])
        ]
        if not planned_subsystems:
            if doc.confidence < self.ACTIVATION_CONFIDENCE_THRESHOLD:
                planned_subsystems.append({
                    "id": "gate_synthesis",
                    "reason": "Low confidence triggers gate checks."
                })
            if self._should_activate_swarm_system(text, doc):
                planned_subsystems.append({
                    "id": "true_swarm_system",
                    "reason": "Automation requests expand into swarm execution stages."
                })
        if not planned_subsystems:
            planned_subsystems.append({
                "id": "gate_synthesis",
                "reason": "Default gate checks ensure baseline safety."
            })
        if self.org_chart_system and not any(item["id"] == "org_chart_system" for item in planned_subsystems):
            planned_subsystems.append({
                "id": "org_chart_system",
                "reason": "Org chart mapping ensures roles cover deliverables."
            })
        sensor_profile = self._select_control_profile(task_description)
        sensor_plan = self._build_external_sensor_plan(
            sensor_profile["id"],
            task_description,
            onboarding_context
        )
        self._apply_wired_capabilities(task_description, doc, onboarding_context, sensor_plan)
        capability_tests = self._run_gap_solution_attempts(task_description, doc, onboarding_context, sensor_plan)

        tasks_source = doc.generated_tasks or self._generate_swarm_tasks()
        planned_swarm_tasks = [
            {**task, "status": task.get("status", "pending")}
            for task in tasks_source
        ]
        deliverables = self._extract_deliverables(doc, tasks_source)
        org_chart_plan = self._build_org_chart_plan(task_description, deliverables)
        doc.org_chart_plan = org_chart_plan

        onboarding_questions = [
            {"stage": step["stage"], "prompt": step["prompt"]}
            for step in self.flow_steps
        ]

        business_summary = self._summarize_business_automation(doc.automation_summary)
        executive_plan = self._build_executive_branch_plan(doc)
        operations_plan = self._build_operations_plan(doc)
        hitl_contracts = self._build_hitl_contract_plan(doc)
        trigger_plan = self._build_timer_trigger_plan(task_description)
        if trigger_plan.get("status") == "scheduled":
            planned_subsystems.append({
                "id": "governance_scheduler",
                "reason": "Timer/trigger plan scheduled through governance scheduler."
            })
        if self.hitl_monitor:
            planned_subsystems.append({
                "id": "hitl_monitor",
                "reason": "HITL approvals required for contracting and execution."
            })
        if self.librarian:
            planned_subsystems.append({
                "id": "system_librarian",
                "reason": "Librarian generates context and proposed conditions."
            })
        capability_alignment = self._build_capability_alignment(planned_subsystems)
        # Record after adding scheduler/HITL subsystems so metrics reflect full preview.
        self._record_activation_usage([item["id"] for item in planned_subsystems])
        librarian_context = self._build_librarian_context(doc, task_description, planned_subsystems)
        self_operation = self.get_system_status().get("self_operation")
        learning_loop = self._build_learning_loop_plan(task_description, onboarding_context, librarian_context)
        delivery_readiness = self._build_delivery_readiness(
            doc,
            org_chart_plan,
            learning_loop,
            sensor_plan,
            hitl_contracts
        )
        compliance_validation = self._build_compliance_validation_snapshot(
            delivery_readiness,
            sensor_plan
        )
        handoff_queue = self._build_handoff_queue_snapshot(hitl_contracts)
        workload_distribution = self._build_workload_distribution(operations_plan)
        executive_directive = self._build_executive_directive(task_description, operations_plan, delivery_readiness)
        governance_dashboard = self._build_governance_dashboard_snapshot(
            executive_directive,
            operations_plan,
            delivery_readiness,
            handoff_queue
        )
        capability_review = self._build_capability_review(
            capability_tests,
            capability_alignment,
            org_chart_plan,
            sensor_plan,
            business_summary,
            learning_loop,
            delivery_readiness=delivery_readiness
        )
        dynamic_implementation = self._build_dynamic_implementation_plan(
            doc,
            task_description,
            planned_subsystems,
            learning_loop,
            operations_plan,
            delivery_readiness,
            hitl_contracts,
            sensor_plan,
            org_chart_plan,
            trigger_plan
        )
        learning_backlog = self._build_learning_backlog_snapshot(
            learning_loop,
            dynamic_implementation.get("chain_plan", {}).get("training_patterns")
        )
        self_improvement_snapshot = self._build_self_improvement_snapshot(
            dynamic_implementation,
            capability_review
        )

        summary_bundle = self._build_summary_surface_bundle()
        module_registry_status = self.module_manager.get_module_status()
        completion_snapshot = self._build_completion_snapshot()
        runtime_execution_profile = self._build_runtime_execution_profile(
            task_description,
            onboarding_context
        )
        summary_surface_consistency = self._build_summary_surface_consistency(
            summary_bundle,
            module_registry_status,
            completion_snapshot
        )
        self_improvement_snapshot = self._apply_summary_consistency_remediation(
            self_improvement_snapshot,
            summary_surface_consistency
        )
        self_improvement_snapshot = self._apply_completion_snapshot_remediation(
            self_improvement_snapshot,
            completion_snapshot
        )
        adapter_execution = self._build_adapter_execution_snapshot()
        execution_wiring = self._build_execution_wiring_snapshot(doc)
        orchestrator_readiness = self._build_orchestrator_readiness_snapshot()
        persistence_status = self._build_persistence_status()
        observability_snapshot = self._build_observability_snapshot()
        preview = {
            "document_id": doc.doc_id,
            "request_summary": task_description,
            "confidence": doc.confidence,
            "planned_subsystems": planned_subsystems,
            "planned_gates": doc.gates,
            "planned_swarm_tasks": planned_swarm_tasks,
            "onboarding_questions": onboarding_questions,
            "constraints": doc.constraints,
            "region": sensor_plan["region"],
            "module_registry": module_registry_status,
            "module_registry_summary": summary_bundle["module_registry_summary"],
            "summary_surface_consistency": summary_surface_consistency,
            "completion_snapshot": completion_snapshot,
            "runtime_execution_profile": runtime_execution_profile,
            "registry_health": self._build_registry_health_snapshot(),
            "schema_drift": self._build_schema_drift_snapshot(),
            "capability_alignment": capability_alignment,
            "capability_tests": capability_tests,
            "business_automation_summary": business_summary,
            "executive_branch_plan": executive_plan,
            "executive_directive": executive_directive,
            "governance_dashboard": governance_dashboard,
            "operations_plan": operations_plan,
            "workload_distribution": workload_distribution,
            "hitl_contracts": hitl_contracts,
            "timer_triggers": trigger_plan,
            "external_api_sensors": sensor_plan,
            "regulatory_scope": {
                "region": sensor_plan["region"],
                "sources": sensor_plan["regulatory_sources"],
                "notes": "Region-specific regulatory sources inform legal/compliance gate checks."
            },
            "librarian_context": librarian_context,
            "org_chart_plan": org_chart_plan,
            "self_operation": self_operation,
            "learning_loop": learning_loop,
            "learning_backlog": learning_backlog,
            "delivery_readiness": delivery_readiness,
            "compliance_validation": compliance_validation,
            "handoff_queue": handoff_queue,
            "self_improvement": self_improvement_snapshot,
            "capability_review": capability_review,
            "dynamic_implementation": dynamic_implementation,
            "execution_wiring": execution_wiring,
            "orchestrator_readiness": orchestrator_readiness,
            "persistence": persistence_status,
            "observability": observability_snapshot,
            "integration_capabilities": summary_bundle["integration_capabilities"],
            "integration_capabilities_summary": summary_bundle["integration_capabilities_summary"],
            "adapter_execution": adapter_execution,
            "competitive_feature_alignment": summary_bundle["competitive_feature_alignment"],
            "competitive_feature_alignment_summary": summary_bundle["competitive_feature_alignment_summary"]
        }
        if onboarding_context:
            preview["onboarding_context"] = onboarding_context
        if self.librarian:
            self.librarian.log_transcript(
                module="activation_preview",
                action="generate_preview",
                details={
                    "doc_id": doc.doc_id,
                    "request": task_description,
                    "planned_subsystems": planned_subsystems,
                    "conditions": librarian_context.get("recommended_conditions", [])
                },
                actor="user",
                success=True
            )
        return preview

    def _record_execution(self, success: bool, duration: float) -> None:
        self.execution_metrics["total"] += 1
        if success:
            self.execution_metrics["success"] += 1
        self.execution_metrics["total_time"] += duration
        total = self.execution_metrics["total"]
        success_rate = self._calculate_success_rate(self.execution_metrics["success"], total)
        avg_time = self.execution_metrics["total_time"] / total if total else 0.0
        self.mfgc_statistics["total_executions"] = total
        self.mfgc_statistics["success_rate"] = f"{success_rate:.1f}%"
        self.mfgc_statistics["average_execution_time"] = f"{avg_time:.3f}s"

    def _build_confidence_report(self, task_description: str) -> Dict[str, Any]:
        base = min(0.92, 0.45 + (len(task_description) / 200))
        uncertainty = max(0.05, 1.0 - base)
        uncertainty_scores = {
            "UD": min(1.0, uncertainty + 0.05),
            "UA": min(1.0, uncertainty + 0.02),
            "UI": min(1.0, uncertainty + 0.01),
            "UR": min(1.0, uncertainty + 0.04),
            "UG": min(1.0, uncertainty + 0.03)
        }
        approved = base >= 0.6
        gate_result = {
            "approved": approved,
            "reason": "Confidence meets threshold" if approved else "Confidence below threshold"
        }
        return {
            "combined_confidence": base,
            "confidence": base,
            "uncertainty_scores": uncertainty_scores,
            "gate_result": gate_result
        }

    def _create_submission(self, submission_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        submission_id = uuid4().hex
        record = {
            "id": submission_id,
            "type": submission_type,
            "payload": payload,
            "status": "submitted",
            "timestamp": datetime.utcnow().isoformat()
        }
        self.form_submissions[submission_id] = record
        return record

    def _generate_plan(self, goal: str) -> Dict[str, Any]:
        steps = [
            f"Define goal: {goal}",
            "Identify required data sources and integrations",
            "Draft automation workflow and approval checkpoints",
            "Validate with a dry-run and update parameters",
            "Deploy with monitoring and alerting enabled"
        ]
        return {"plan_steps": steps}

    def create_session(self, name: Optional[str] = None) -> Dict[str, Any]:
        session_id = uuid4().hex
        session = {
            "session_id": session_id,
            "name": name or "session",
            "created_at": datetime.utcnow().isoformat()
        }
        self.sessions[session_id] = session
        return {"success": True, **session}

    def _advance_flow(self, session: Dict[str, Any], message: str) -> Dict[str, Any]:
        if "reset" in message.lower() or "start over" in message.lower():
            session["stage_index"] = 0
            session["history"] = []
            session["answers"] = {}
        stage_index = session.get("stage_index", 0)
        current_stage = self.flow_steps[stage_index]
        answers = session.setdefault("answers", {})
        session.setdefault("history", []).append({
            "stage": current_stage["stage"],
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        answers[current_stage["stage"]] = message
        next_index = min(stage_index + 1, len(self.flow_steps) - 1)
        session["stage_index"] = next_index
        next_stage = self.flow_steps[next_index]
        region_input = answers.get("region")
        region_info = self._extract_region_from_context(message, {"answers": answers, "region": region_input})
        region = region_info["region"]
        return {
            "current_stage": current_stage["stage"],
            "next_stage": next_stage["stage"],
            "prompt": next_stage["prompt"],
            "answers": dict(answers),
            "region": region,
            "region_input": region_input
        }

    def _build_mfgc_payload(self, stage: str, duration: float) -> Dict[str, Any]:
        phase_map = {
            "signup": "expand",
            "region": "scope",
            "setup": "type",
            "automation_design": "enumerate",
            "automation_production": "bind",
            "billing": "execute"
        }
        phase = phase_map.get(stage, "execute")
        confidence = min(0.95, 0.65 + (list(phase_map.keys()).index(stage) * 0.05 if stage in phase_map else 0.2))
        authority = 0.72
        murphy_index = min(0.95, self.mfgc_config["murphy_threshold"] + 0.25)
        gates_generated = ["Murphy Gate", "Safety Gate", "Authority Gate"]
        return {
            "final_phase": phase,
            "final_confidence": confidence,
            "total_gates": len(gates_generated),
            "execution_time": duration,
            "murphy_index": murphy_index,
            "gates_generated": gates_generated,
            "system_state": {
                "phase": phase,
                "confidence": confidence,
                "authority": authority
            }
        }

    def handle_chat(self, message: str, session_id: Optional[str], use_mfgc: bool) -> Dict[str, Any]:
        session_id = session_id or "default"
        session = self.chat_sessions.setdefault(session_id, {"stage_index": 0, "history": []})
        start = time.perf_counter()
        flow = self._advance_flow(session, message)
        default_values = {
            "current_stage": "unknown",
            "next_stage": "next",
            "prompt": "Continue with the next step."
        }
        current_stage = flow.get("current_stage", default_values["current_stage"])
        next_stage = flow.get("next_stage", default_values["next_stage"])
        prompt = flow.get("prompt", default_values["prompt"])
        applied_defaults = {
            key: default_values[key]
            for key in default_values
            if key not in flow
        }
        if applied_defaults:
            logger.warning(
                "Flow response missing keys: %s; applying defaults %s.",
                sorted(applied_defaults.keys()),
                applied_defaults
            )
        response = (
            f"Captured {current_stage} details. "
            f"Next step ({next_stage}): {prompt}"
        )
        duration = time.perf_counter() - start
        self._record_execution(success=True, duration=duration)
        doc = self._ensure_document(message, "conversation", session_id)
        self._update_document_tree(doc)
        activation_preview = self._build_activation_preview(
            doc,
            task_description=message,
            onboarding_context=flow
        )
        self.latest_activation_preview = activation_preview
        result = {
            "success": True,
            "session_id": session_id,
            "message": response,
            "flow_stage": next_stage,
            "doc_id": doc.doc_id,
            "block_tree": doc.block_tree,
            "gates": doc.gates,
            "constraints": doc.constraints,
            "activation_preview": activation_preview
        }
        if use_mfgc:
            self.mfgc_config["enabled"] = True
            result["mfgc_control"] = True
            result["data"] = self._build_mfgc_payload(flow["next_stage"], duration)
        return result

    async def handle_form_task_execution(self, data: Dict[str, Any]) -> Dict[str, Any]:
        task_description = data.get("description") or data.get("task_description", "")
        task_type = data.get("task_type", "general")
        parameters = data.get("parameters") or {}
        submission = self._create_submission("task-execution", data)
        session_id = data.get("session_id")
        doc = self._ensure_document(task_description, task_type, session_id)
        confidence_report = self._build_confidence_report(task_description)
        result = await self.execute_task(task_description, task_type, parameters, session_id=session_id)
        submission["status"] = "completed" if result.get("success") else "failed"
        submission["result"] = result
        self._update_document_tree(doc)
        activation_preview = self._build_activation_preview(doc, task_description=task_description)
        self.latest_activation_preview = activation_preview
        return {
            "success": result.get("success", False),
            "submission_id": submission["id"],
            "task_id": submission["id"],
            "status": submission["status"],
            "doc_id": doc.doc_id,
            "confidence_report": confidence_report,
            "output": result.get("result"),
            "block_tree": doc.block_tree,
            "gates": doc.gates,
            "constraints": doc.constraints,
            "activation_preview": activation_preview,
            "error": result.get("error")
        }

    def handle_form_validation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        task_data = data.get("task_data") or data
        description = task_data.get("description", "")
        confidence_report = self._build_confidence_report(description)
        approved = confidence_report["gate_result"]["approved"]
        if not approved:
            intervention_id = uuid4().hex
            self.hitl_interventions[intervention_id] = {
                "request_id": intervention_id,
                "task_id": task_data.get("task_id", "unknown"),
                "intervention_type": "validation_review",
                "urgency": "high" if confidence_report["combined_confidence"] < 0.5 else "medium",
                "reason": confidence_report["gate_result"]["reason"],
                "status": "pending",
                "timestamp": datetime.utcnow().isoformat()
            }
        return {
            "success": True,
            "approved": approved,
            "valid": approved,
            "confidence": confidence_report["combined_confidence"],
            "uncertainty_scores": confidence_report["uncertainty_scores"],
            "gate_result": confidence_report["gate_result"],
            "errors": [] if approved else [confidence_report["gate_result"]["reason"]]
        }

    def handle_form_correction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        correction_id = uuid4().hex
        correction = {
            "id": correction_id,
            "task_id": data.get("task_id"),
            "correction_type": data.get("correction_type"),
            "original_output": data.get("original_output"),
            "corrected_output": data.get("corrected_output"),
            "explanation": data.get("explanation"),
            "timestamp": datetime.utcnow().isoformat()
        }
        self.corrections.append(correction)
        patterns_extracted = 1 if correction.get("explanation") else 0
        return {
            "success": True,
            "correction_id": correction_id,
            "task_id": correction.get("task_id"),
            "patterns_extracted": patterns_extracted
        }

    def handle_form_submission(self, form_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if form_type == "plan-upload":
            submission = self._create_submission(form_type, data)
            return {"success": True, "submission_id": submission["id"], "status": "uploaded"}
        if form_type == "plan-generation":
            submission = self._create_submission(form_type, data)
            plan = self._generate_plan(data.get("goal", data.get("description", "Automation plan")))
            submission["result"] = plan
            submission["status"] = "generated"
            return {"success": True, "submission_id": submission["id"], "plan": plan}
        submission = self._create_submission(form_type, data)
        return {"success": True, "submission_id": submission["id"]}

    def get_correction_patterns(self) -> Dict[str, Any]:
        pattern_counts: Dict[str, int] = {}
        for correction in self.corrections:
            ctype = correction.get("correction_type") or "unknown"
            pattern_counts[ctype] = pattern_counts.get(ctype, 0) + 1
        patterns = [
            {
                "pattern_type": ctype,
                "frequency": count,
                "description": f"Corrections of type {ctype}"
            }
            for ctype, count in pattern_counts.items()
        ]
        return {"success": True, "count": len(patterns), "patterns": patterns}

    def get_correction_statistics(self) -> Dict[str, Any]:
        unique_tasks = {c.get("task_id") for c in self.corrections if c.get("task_id")}
        corrections_by_type: Dict[str, int] = {}
        for correction in self.corrections:
            ctype = correction.get("correction_type") or "unknown"
            corrections_by_type[ctype] = corrections_by_type.get(ctype, 0) + 1
        return {
            "success": True,
            "statistics": {
                "total_corrections": len(self.corrections),
                "total_patterns": sum(corrections_by_type.values()),
                "unique_tasks": len(unique_tasks),
                "corrections_by_type": corrections_by_type,
                "corrections_by_severity": {"normal": len(self.corrections)}
            }
        }

    def get_hitl_state(self) -> Dict[str, Any]:
        pending = [item for item in self.hitl_interventions.values() if item["status"] == "pending"]
        return {
            "pending": pending,
            "statistics": {
                "pending_count": len(pending),
                "total_interventions": len(self.hitl_interventions)
            }
        }

    def get_mfgc_state(self) -> Dict[str, Any]:
        return {
            "mfgc_config": self.mfgc_config,
            "mfgc_statistics": self.mfgc_statistics
        }
    
    # ==================== INTEGRATION ====================
    
    def add_integration(
        self,
        source: str,
        integration_type: str = 'repository',
        category: str = 'general',
        generate_agent: bool = False,
        auto_approve: bool = False
    ) -> Dict:
        """
        Add an integration using Integration Engine.
        
        Args:
            source: GitHub URL, API endpoint, or hardware device
            integration_type: Type of integration
            category: Category for the integration
            generate_agent: Whether to generate an agent
            auto_approve: Skip HITL approval (testing only)
        
        Returns:
            Integration result
        """
        
        if not self.integration_engine:
            return {
                "success": False,
                "error": "Integration engine not available",
                "source": source
            }
        return self.integration_engine.add_integration(
            source=source,
            integration_type=integration_type,
            category=category,
            generate_agent=generate_agent,
            auto_approve=auto_approve
        ).to_dict()
    
    def approve_integration(self, request_id: str, approved_by: str = "user") -> Dict:
        """Approve a pending integration"""
        if not self.integration_engine:
            return {"success": False, "error": "Integration engine not available"}
        return self.integration_engine.approve_integration(
            request_id=request_id,
            approved_by=approved_by
        ).to_dict()
    
    def reject_integration(self, request_id: str, reason: str = "User rejected") -> Dict:
        """Reject a pending integration"""
        if not self.integration_engine:
            return {"success": False, "error": "Integration engine not available"}
        return self.integration_engine.reject_integration(
            request_id=request_id,
            reason=reason
        ).to_dict()
    
    # ==================== BUSINESS AUTOMATION ====================
    
    def run_inoni_automation(
        self,
        engine_name: str,
        action: str,
        parameters: Optional[Dict] = None
    ) -> Dict:
        """
        Run Inoni business automation.
        
        Args:
            engine_name: Name of engine (sales, marketing, rd, business, production)
            action: Action to perform
            parameters: Action parameters
        
        Returns:
            Automation result
        """
        
        if not self.inoni_automation:
            return {
                "success": False,
                "error": "Inoni automation engine not available",
                "engine": engine_name,
                "action": action
            }
        return self.inoni_automation.execute_automation(
            engine_name=engine_name,
            action=action,
            parameters=parameters or {}
        )
    
    # ==================== SYSTEM MANAGEMENT ====================
    
    def get_system_status(self) -> Dict:
        """Get complete system status"""
        
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        self_operation_enabled = self.inoni_automation is not None
        correction_system_available = self.correction_system is not None
        pending_integrations = 0
        committed_integrations = 0
        if self.integration_engine:
            pending_integrations = len(self.integration_engine.list_pending_integrations())
            committed_integrations = len(self.integration_engine.list_committed_integrations())
        # latest_activation_preview may be unset in lightweight/test instances.
        latest_preview = getattr(self, "latest_activation_preview", {}) or {}
        learning_backlog = self._build_learning_backlog_snapshot(
            latest_preview.get("learning_loop"),
            (latest_preview.get("dynamic_implementation") or {})
            .get("chain_plan", {})
            .get("training_patterns")
        )
        self_improvement_snapshot = self._build_self_improvement_snapshot(
            latest_preview.get("dynamic_implementation"),
            latest_preview.get("capability_review")
        )
        governance_dashboard = self._build_governance_dashboard_snapshot(
            latest_preview.get("executive_directive"),
            latest_preview.get("operations_plan"),
            latest_preview.get("delivery_readiness"),
            latest_preview.get("handoff_queue")
        )
        compliance_validation = self._build_compliance_validation_snapshot(
            latest_preview.get("delivery_readiness"),
            latest_preview.get("external_api_sensors")
        )
        summary_bundle = self._build_summary_surface_bundle()
        module_registry_status = self.module_manager.get_module_status()
        completion_snapshot = self._build_completion_snapshot()
        runtime_execution_profile = self._build_runtime_execution_profile(
            latest_preview.get("request_summary", ""),
            latest_preview.get("onboarding_context")
        )
        summary_surface_consistency = self._build_summary_surface_consistency(
            summary_bundle,
            module_registry_status,
            completion_snapshot
        )
        self_improvement_snapshot = self._apply_summary_consistency_remediation(
            self_improvement_snapshot,
            summary_surface_consistency
        )
        self_improvement_snapshot = self._apply_completion_snapshot_remediation(
            self_improvement_snapshot,
            completion_snapshot
        )
        return {
            'version': self.version,
            'status': 'running',
            'uptime_seconds': uptime,
            'start_time': self.start_time.isoformat(),
            'components': {
                'control_plane': self._component_status(self.control_plane),
                'inoni_automation': self._component_status(self.inoni_automation),
                'integration_engine': self._component_status(self.integration_engine),
                'orchestrator': self._component_status(self.orchestrator),
                'form_handler': self._component_status(self.form_handler),
                'confidence_engine': self._component_status(self.confidence_engine),
                'correction_system': self._component_status(self.correction_system),
                'hitl_monitor': self._component_status(self.hitl_monitor)
            },
            'statistics': {
                'sessions': len(self.sessions),
                'repositories': len(self.repositories),
                'active_automations': len(self.active_automations),
                'pending_integrations': pending_integrations,
                'committed_integrations': committed_integrations,
                'executions': self.execution_metrics["total"],
                'execution_success_rate': (
                    self.execution_metrics["success"] / self.execution_metrics["total"]
                    if self.execution_metrics["total"]
                    else 0.0
                )
            },
            'module_registry': module_registry_status,
            'module_registry_summary': summary_bundle["module_registry_summary"],
            'summary_surface_consistency': summary_surface_consistency,
            'completion_snapshot': completion_snapshot,
            'runtime_execution_profile': runtime_execution_profile,
            'registry_health': self._build_registry_health_snapshot(),
            'schema_drift': self._build_schema_drift_snapshot(),
            'adapter_execution': self._build_adapter_execution_snapshot(),
            'integration_capabilities': summary_bundle["integration_capabilities"],
            'integration_capabilities_summary': summary_bundle["integration_capabilities_summary"],
            'competitive_feature_alignment': summary_bundle["competitive_feature_alignment"],
            'competitive_feature_alignment_summary': summary_bundle["competitive_feature_alignment_summary"],
            'connector_orchestration': self._build_connector_orchestration_snapshot(),
            'orchestrator_readiness': self._build_orchestrator_readiness_snapshot(),
            'observability': self._build_observability_snapshot(),
            'compliance_validation': compliance_validation,
            'handoff_queue': self._build_handoff_queue_snapshot(),
            'governance_dashboard': governance_dashboard,
            'learning_backlog': learning_backlog,
            'self_improvement': self_improvement_snapshot,
            'self_operation': {
                'enabled': self_operation_enabled,
                'can_work_on_self': self_operation_enabled and correction_system_available,
                'activation_required': True,
                'state': 'active' if self_operation_enabled else 'unavailable'
            }
        }
    
    def get_system_info(self) -> Dict:
        """Get system information"""
        summary_bundle = self._build_summary_surface_bundle()
        module_registry_status = self.module_manager.get_module_status()
        completion_snapshot = self._build_completion_snapshot()
        # System info has no request/onboarding context, so use neutral defaults.
        runtime_execution_profile = self._build_runtime_execution_profile("", None)
        return {
            'name': 'Murphy System',
            'version': self.version,
            'description': 'Universal AI Automation System',
            'owner': 'Inoni Limited Liability Company',
            'creator': 'Corey Post',
            'license': 'Apache License 2.0',
            'capabilities': [
                'Universal Automation (factory, content, data, system, agent, business)',
                'Self-Integration (GitHub, APIs, hardware)',
                'Self-Improvement (correction learning, shadow agent)',
                'Self-Operation (runs maintenance & R&D tasks once activated)',
                'Safety & Governance (HITL, Murphy validation)',
                'Scalability (Kubernetes-ready)',
                'Monitoring (Prometheus + Grafana)'
            ],
            'components': {
                'original_runtime': '319 Python files, 67 directories',
                'phase_implementations': 'Phase 1-5 (forms, validation, correction, learning)',
                'control_plane': '7 modular engines, 6 control types',
                'business_automation': '5 engines (sales, marketing, R&D, business, production)',
                'integration_engine': '6 components (HITL, safety testing, capability extraction)',
                'orchestrator': '2-phase execution (setup → execute)'
            },
            'integration_capabilities_summary': summary_bundle["integration_capabilities_summary"],
            'competitive_feature_alignment_summary': summary_bundle["competitive_feature_alignment_summary"],
            'module_registry_summary': summary_bundle["module_registry_summary"],
            'summary_surface_consistency': self._build_summary_surface_consistency(
                summary_bundle,
                module_registry_status,
                completion_snapshot
            ),
            'completion_snapshot': completion_snapshot,
            'runtime_execution_profile': runtime_execution_profile
        }

    def get_activation_audit(self) -> Dict[str, Any]:
        """
        Return activation audit data for implemented but unwired subsystems.

        Returns a dict with:
        - summary: total/available/missing counts
        - modules: list of subsystem entries with fields: id, name, path, wired,
          initialized, notes, available, activation_count, activated. The path
          field is returned as a string. The available field is computed at
          runtime based on path existence. The initialized flag reflects runtime
          instantiation when available (currently only TrueSwarmSystem).
        """
        base_dir = Path(__file__).parent / "src"
        swarm_instance = getattr(self, "swarm_system", None)
        swarm_initialized = False
        if swarm_instance is not None:
            try:
                swarm_initialized = isinstance(swarm_instance, TrueSwarmSystem)
            except TypeError:
                swarm_initialized = True
        candidates = [
            {
                "id": "inoni_business_automation",
                "name": "Inoni Business Automation",
                "path": Path(__file__).parent / "inoni_business_automation.py",
                "wired": True,
                "initialized": bool(self.inoni_automation),
                "notes": "Self-operation automation loop for business engines."
            },
            {
                "id": "governance_scheduler",
                "name": "Governance Scheduler",
                "path": base_dir / "governance_framework" / "scheduler.py",
                "wired": True,
                "initialized": bool(self.governance_scheduler),
                "notes": "Schedules timer/trigger execution plans."
            },
            {
                "id": "hitl_monitor",
                "name": "HITL Monitor",
                "path": base_dir / "supervisor_system" / "integrated_hitl_monitor.py",
                "wired": bool(self.hitl_monitor),
                "initialized": bool(self.hitl_monitor),
                "notes": "Tracks human-in-the-loop approvals and contracting."
            },
            {
                "id": "recursive_stability_controller",
                "name": "Recursive Stability Controller",
                "path": base_dir / "recursive_stability_controller",
                "wired": True,
                "initialized": True,
                "notes": "Telemetry and stability services are invoked during activation previews."
            },
            {
                "id": "gate_synthesis",
                "name": "Gate Synthesis Engine",
                "path": base_dir / "gate_synthesis",
                "wired": True,
                "initialized": True,
                "notes": "Gate synthesis is invoked during activation previews."
            },
            {
                "id": "system_librarian",
                "name": "System Librarian",
                "path": base_dir / "system_librarian.py",
                "wired": True,
                "initialized": bool(self.librarian),
                "notes": "Librarian generates context and proposed conditions per request."
            },
            {
                "id": "org_chart_system",
                "name": "Organization Chart System",
                "path": base_dir / "organization_chart_system.py",
                "wired": True,
                "initialized": bool(getattr(self, "org_chart_system", None)),
                "notes": "Maps deliverables to positions and contract coverage."
            },
            {
                "id": "compute_plane",
                "name": "Compute Plane",
                "path": base_dir / "compute_plane",
                "wired": True,
                "initialized": True,
                "notes": "Compute plane validation runs during activation previews."
            },
            {
                "id": "infinity_expansion_system",
                "name": "Infinity Expansion System",
                "path": base_dir / "infinity_expansion_system.py",
                "wired": True,
                "initialized": True,
                "notes": "Problem expansion logic is invoked during activation previews."
            },
            {
                "id": "advanced_swarm_system",
                "name": "Advanced Swarm System",
                "path": base_dir / "advanced_swarm_system.py",
                "wired": False,
                "initialized": False,
                "notes": "Swarm candidate synthesis exists but is not wired into task execution."
            },
            {
                "id": "domain_swarms",
                "name": "Domain Swarms",
                "path": base_dir / "domain_swarms.py",
                "wired": True,
                "initialized": True,
                "notes": "Domain swarm generators are invoked during activation previews."
            },
            {
                "id": "true_swarm_system",
                "name": "True Swarm System",
                "path": base_dir / "true_swarm_system.py",
                "wired": True,
                "initialized": swarm_initialized,
                "notes": "Swarm system executes full cycles during activation previews."
            },
            {
                "id": "knowledge_gap_system",
                "name": "Knowledge Gap System",
                "path": base_dir / "knowledge_gap_system.py",
                "wired": True,
                "initialized": True,
                "notes": "Gap detection is invoked during activation previews."
            },
            {
                "id": "neuro_symbolic_models",
                "name": "Neuro-Symbolic Models",
                "path": base_dir / "neuro_symbolic_models",
                "wired": False,
                "initialized": False,
                "notes": "Model wrappers are implemented without runtime integration."
            }
        ]
        processed = []
        for item in candidates:
            available = item["path"].exists()
            activation_count = self.activation_usage.get(item["id"], 0)
            processed.append({
                **item,
                "available": available,
                "path": str(item["path"]),
                "activation_count": activation_count,
                "activated": activation_count > 0
            })
        available = sum(1 for item in processed if item["available"])
        return {
            "summary": {
                "total": len(candidates),
                "available": available,
                "missing": len(candidates) - available
            },
            "modules": processed
        }
    
    def list_modules(self) -> List[Dict]:
        """List all loaded modules"""
        status = self.module_manager.get_module_status()
        return [
            {
                'name': name,
                'status': info['status'],
                'description': info['description'],
                'capabilities': info['capabilities']
            }
            for name, info in status['modules'].items()
        ]
    
    def list_integrations(self, status: str = 'all') -> List[Dict]:
        """List integrations by status (pending, committed, all)"""
        if not self.integration_engine:
            return []
        if status == 'pending':
            return self.integration_engine.list_pending_integrations()
        elif status == 'committed':
            return self.integration_engine.list_committed_integrations()
        else:
            return {
                'pending': self.integration_engine.list_pending_integrations(),
                'committed': self.integration_engine.list_committed_integrations()
            }


# ==================== FASTAPI APPLICATION ====================

def create_app() -> FastAPI:
    """Create FastAPI application"""
    
    if FastAPI is None:
        raise ImportError("FastAPI not installed. Install with: pip install fastapi uvicorn")
    
    app = FastAPI(
        title="Murphy System 1.0",
        description="Universal AI Automation System",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize Murphy System
    murphy = MurphySystem()
    
    # ==================== CORE ENDPOINTS ====================
    
    @app.post("/api/execute")
    async def execute_task(request: Request):
        """Execute a task"""
        data = await request.json()
        result = await murphy.execute_task(
            task_description=data.get('task_description', ''),
            task_type=data.get('task_type', 'general'),
            parameters=data.get('parameters'),
            session_id=data.get('session_id')
        )
        return JSONResponse(result)

    @app.post("/api/chat")
    async def chat(request: Request):
        """Chat endpoint for terminal UIs"""
        data = await request.json()
        result = murphy.handle_chat(
            message=data.get("message", ""),
            session_id=data.get("session_id"),
            use_mfgc=data.get("use_mfgc", False)
        )
        return JSONResponse(result)
    
    @app.get("/api/status")
    async def get_status():
        """Get system status"""
        return JSONResponse(murphy.get_system_status())
    
    @app.get("/api/info")
    async def get_info():
        """Get system information"""
        return JSONResponse(murphy.get_system_info())

    @app.get("/api/system/info")
    async def get_system_info():
        """Alias for system information (legacy UI compatibility)"""
        info = murphy.get_system_info()
        # Preserve legacy flat response shape for older clients.
        response = {**info, "success": True, "system": info}
        return JSONResponse(response)
    
    @app.get("/api/health")
    async def health_check():
        """Health check"""
        return JSONResponse({'status': 'healthy', 'version': murphy.version})

    # ==================== SESSION ENDPOINTS ====================

    @app.post("/api/sessions/create")
    async def create_session(request: Request):
        """Create a session for UI chat flows"""
        try:
            data = await request.json()
        except Exception:
            data = {}
        result = murphy.create_session(name=data.get("name"))
        return JSONResponse(result)

    # ==================== DOCUMENT ENDPOINTS ====================

    @app.post("/api/documents")
    async def create_document(request: Request):
        """Create a living document for block commands"""
        data = await request.json()
        title = data.get("title") or "Untitled"
        content = data.get("content") or ""
        doc_type = data.get("type") or data.get("doc_type") or "general"
        doc = murphy._create_document(title=title, content=content, doc_type=doc_type, session_id=data.get("session_id"))
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.get("/api/documents/{doc_id}")
    async def get_document(doc_id: str):
        """Fetch a living document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/magnify")
    async def magnify_document(doc_id: str, request: Request):
        """Magnify a document"""
        data = await request.json()
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.magnify(data.get("domain", "general"))
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/simplify")
    async def simplify_document(doc_id: str):
        """Simplify a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.simplify()
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/solidify")
    async def solidify_document(doc_id: str):
        """Solidify a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.solidify()
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/gates")
    async def update_document_gates(doc_id: str, request: Request):
        """Update gate policy for a document"""
        data = await request.json()
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        updates = data.get("gates", [])
        murphy.update_gate_policy(doc, updates, confidence=data.get("confidence"))
        murphy._apply_wired_capabilities(doc.content, doc, data.get("onboarding_context"))
        preview = murphy._build_activation_preview(doc, doc.content, data.get("onboarding_context"))
        return JSONResponse({
            "success": True,
            "doc_id": doc.doc_id,
            "gates": doc.gates,
            "block_tree": doc.block_tree,
            "activation_preview": preview,
            **doc.to_dict()
        })

    @app.get("/api/documents/{doc_id}/blocks")
    async def document_blocks(doc_id: str):
        """Fetch the block command tree for a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        return JSONResponse({"success": True, "block_tree": doc.block_tree})

    # ==================== FORM ENDPOINTS ====================

    @app.post("/api/forms/task-execution")
    async def form_task_execution(request: Request):
        """Execute task via form endpoint"""
        data = await request.json()
        result = await murphy.handle_form_task_execution(data)
        return JSONResponse(result)

    @app.post("/api/forms/validation")
    async def form_validation(request: Request):
        """Validate task via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_validation(data)
        return JSONResponse(result)

    @app.post("/api/forms/correction")
    async def form_correction(request: Request):
        """Submit correction via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_correction(data)
        return JSONResponse(result)

    @app.post("/api/forms/plan-upload")
    async def form_plan_upload(request: Request):
        """Upload a plan via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_submission("plan-upload", data)
        return JSONResponse(result)

    @app.post("/api/forms/plan-generation")
    async def form_plan_generation(request: Request):
        """Generate plan via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_submission("plan-generation", data)
        return JSONResponse(result)

    @app.get("/api/forms/submission/{submission_id}")
    async def form_submission_status(submission_id: str):
        """Get form submission status"""
        submission = murphy.form_submissions.get(submission_id)
        return JSONResponse({"success": bool(submission), "submission": submission})

    @app.post("/api/forms/{form_type}")
    async def form_generic(form_type: str, request: Request):
        """Generic form submission endpoint"""
        data = await request.json()
        if form_type == "task-execution":
            result = await murphy.handle_form_task_execution(data)
            return JSONResponse(result)
        if form_type == "validation":
            result = murphy.handle_form_validation(data)
            return JSONResponse(result)
        if form_type == "correction":
            result = murphy.handle_form_correction(data)
            return JSONResponse(result)
        result = murphy.handle_form_submission(form_type, data)
        return JSONResponse(result)

    # ==================== CORRECTION ENDPOINTS ====================

    @app.get("/api/corrections/patterns")
    async def correction_patterns():
        """Get correction patterns"""
        return JSONResponse(murphy.get_correction_patterns())

    @app.get("/api/corrections/statistics")
    async def correction_statistics():
        """Get correction statistics"""
        return JSONResponse(murphy.get_correction_statistics())

    @app.get("/api/corrections/training-data")
    async def correction_training_data():
        """Get correction training data"""
        return JSONResponse({"success": True, "data": murphy.corrections})

    # ==================== HITL ENDPOINTS ====================

    @app.get("/api/hitl/interventions/pending")
    async def hitl_pending():
        """Get pending HITL interventions"""
        state = murphy.get_hitl_state()
        return JSONResponse({
            "success": True,
            "count": len(state["pending"]),
            "interventions": state["pending"]
        })

    @app.post("/api/hitl/interventions/{intervention_id}/respond")
    async def hitl_respond(intervention_id: str, request: Request):
        """Respond to HITL intervention"""
        data = await request.json()
        intervention = murphy.hitl_interventions.get(intervention_id)
        if intervention:
            intervention["status"] = data.get("status", "resolved")
            intervention["response"] = data.get("response")
        return JSONResponse({"success": bool(intervention), "intervention": intervention})

    @app.get("/api/hitl/statistics")
    async def hitl_statistics():
        """Get HITL statistics"""
        stats = murphy.get_hitl_state().get("statistics", {})
        return JSONResponse({"success": True, "statistics": stats})

    # ==================== MFGC ENDPOINTS ====================

    @app.get("/api/mfgc/state")
    async def mfgc_state():
        """Get MFGC state"""
        return JSONResponse({"success": True, "state": murphy.get_mfgc_state()})

    @app.get("/api/mfgc/config")
    async def mfgc_config():
        """Get MFGC config"""
        return JSONResponse({"success": True, "config": murphy.mfgc_config})

    @app.post("/api/mfgc/config")
    async def mfgc_config_update(request: Request):
        """Update MFGC config"""
        data = await request.json()
        murphy.mfgc_config.update(data)
        return JSONResponse({"success": True, "config": murphy.mfgc_config})

    @app.post("/api/mfgc/setup/{profile}")
    async def mfgc_setup(profile: str):
        """Configure MFGC profile"""
        profiles = {
            "production": {"enabled": True, "murphy_threshold": 0.7},
            "certification": {"enabled": True, "murphy_threshold": 0.6},
            "development": {"enabled": False, "murphy_threshold": 0.3}
        }
        if profile in profiles:
            murphy.mfgc_config.update(profiles[profile])
            return JSONResponse({"success": True, "profile": profile, "config": murphy.mfgc_config})
        return JSONResponse({"success": False, "error": "Unknown profile"})
    
    # ==================== INTEGRATION ENDPOINTS ====================
    
    @app.post("/api/integrations/add")
    async def add_integration(request: Request):
        """Add an integration"""
        data = await request.json()
        result = murphy.add_integration(
            source=data.get('source', ''),
            integration_type=data.get('integration_type', 'repository'),
            category=data.get('category', 'general'),
            generate_agent=data.get('generate_agent', False),
            auto_approve=data.get('auto_approve', False)
        )
        return JSONResponse(result)
    
    @app.post("/api/integrations/{request_id}/approve")
    async def approve_integration(request_id: str, request: Request):
        """Approve an integration"""
        data = await request.json()
        result = murphy.approve_integration(
            request_id=request_id,
            approved_by=data.get('approved_by', 'user')
        )
        return JSONResponse(result)
    
    @app.post("/api/integrations/{request_id}/reject")
    async def reject_integration(request_id: str, request: Request):
        """Reject an integration"""
        data = await request.json()
        result = murphy.reject_integration(
            request_id=request_id,
            reason=data.get('reason', 'User rejected')
        )
        return JSONResponse(result)
    
    @app.get("/api/integrations/{status}")
    async def list_integrations(status: str = 'all'):
        """List integrations"""
        result = murphy.list_integrations(status=status)
        return JSONResponse(result)
    
    # ==================== BUSINESS AUTOMATION ENDPOINTS ====================
    
    @app.post("/api/automation/{engine_name}/{action}")
    async def run_automation(engine_name: str, action: str, request: Request):
        """Run business automation"""
        data = await request.json()
        result = murphy.run_inoni_automation(
            engine_name=engine_name,
            action=action,
            parameters=data.get('parameters')
        )
        return JSONResponse(result)
    
    # ==================== SYSTEM ENDPOINTS ====================
    
    @app.get("/api/modules")
    async def list_modules():
        """List all modules"""
        return JSONResponse(murphy.list_modules())

    @app.get("/api/diagnostics/activation")
    async def activation_audit():
        """List inactive subsystems and activation hints"""
        return JSONResponse(murphy.get_activation_audit())

    @app.get("/api/diagnostics/activation/last")
    async def get_last_activation_preview():
        """Get latest activation preview from request processing"""
        preview = murphy.latest_activation_preview
        return JSONResponse({"success": bool(preview), "preview": preview})

    return app


# ==================== MAIN ====================

def main():
    """Main entry point"""
    
    print("\n" + "="*80)
    print("MURPHY SYSTEM 1.0")
    print("Universal AI Automation System")
    print("="*80 + "\n")
    
    # Create FastAPI app
    app = create_app()
    
    # Run server
    port = int(os.getenv('MURPHY_PORT', 6666))
    
    print(f"\n🚀 Starting Murphy System 1.0 on port {port}...")
    print(f"📊 API Documentation: http://localhost:{port}/docs")
    print(f"🔍 Health Check: http://localhost:{port}/api/health")
    print(f"📈 System Status: http://localhost:{port}/api/status")
    print(f"ℹ️  System Info: http://localhost:{port}/api/info\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
