"""
Murphy System 1.0 - Dependency Resolution

All third-party and internal imports with graceful fallbacks.
Extracted from the monolithic runtime for maintainability (INC-13 / H-04 / L-02).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import sys
import os
import json
import importlib.util
from copy import deepcopy
from pathlib import Path
from collections import deque
from collections.abc import Mapping
from typing import Dict, List, Optional, Any, Tuple, Literal, Set, TYPE_CHECKING
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
import logging
import asyncio
import platform
import time
import re
import math
import numbers
from uuid import uuid4
try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:
    _load_dotenv = None

# B-001: Actually call load_dotenv() so .env variables are loaded at import time
if _load_dotenv is not None:
    _load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

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

# MSS Controls & Intelligence Layer
try:
    from src.resolution_scoring import ResolutionDetectionEngine
    from src.information_density import InformationDensityEngine
    from src.structural_coherence import StructuralCoherenceEngine
    from src.information_quality import InformationQualityEngine
    from src.concept_translation import ConceptTranslationEngine
    from src.simulation_engine import StrategicSimulationEngine
    from src.mss_controls import MSSController
    _mss_available = True
except ImportError as e:
    print(f"Warning: MSS controls not available: {e}")
    _mss_available = False

# Org Chart System
try:
    from src.organization_chart_system import OrganizationChart
except ImportError as e:
    print(f"Warning: Organization chart system not available: {e}")
    OrganizationChart = None

# New integrated modules
try:
    from src.persistence_manager import PersistenceManager
except ImportError as e:
    print(f"Warning: Persistence manager not available: {e}")
    PersistenceManager = None

try:
    from src.event_backbone import EventBackbone, EventType as BackboneEventType
except ImportError as e:
    print(f"Warning: Event backbone not available: {e}")
    EventBackbone = None
    BackboneEventType = None

try:
    from src.delivery_adapters import (
        DeliveryOrchestrator, DeliveryChannel, DeliveryRequest, DeliveryStatus,
        DocumentDeliveryAdapter, EmailDeliveryAdapter, ChatDeliveryAdapter,
        VoiceDeliveryAdapter, TranslationDeliveryAdapter
    )
except ImportError as e:
    print(f"Warning: Delivery adapters not available: {e}")
    DeliveryOrchestrator = DeliveryChannel = DeliveryRequest = DeliveryStatus = None
    DocumentDeliveryAdapter = EmailDeliveryAdapter = ChatDeliveryAdapter = None
    VoiceDeliveryAdapter = TranslationDeliveryAdapter = None

try:
    from src.gate_execution_wiring import GateExecutionWiring, GateType, GatePolicy
except ImportError as e:
    print(f"Warning: Gate execution wiring not available: {e}")
    GateExecutionWiring = GateType = GatePolicy = None

try:
    from src.self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType
except ImportError as e:
    print(f"Warning: Self-improvement engine not available: {e}")
    SelfImprovementEngine = ExecutionOutcome = OutcomeType = None

try:
    from src.operational_slo_tracker import OperationalSLOTracker, SLOTarget, ExecutionRecord as SLOExecutionRecord
except ImportError as e:
    print(f"Warning: Operational SLO tracker not available: {e}")
    OperationalSLOTracker = SLOTarget = SLOExecutionRecord = None

try:
    from src.automation_scheduler import AutomationScheduler, ProjectSchedule, SchedulePriority
except ImportError as e:
    print(f"Warning: Automation scheduler not available: {e}")
    AutomationScheduler = ProjectSchedule = SchedulePriority = None

try:
    from src.capability_map import CapabilityMap
except ImportError as e:
    print(f"Warning: Capability map not available: {e}")
    CapabilityMap = None

try:
    from src.compliance_engine import ComplianceEngine, ComplianceFramework
except ImportError as e:
    print(f"Warning: Compliance engine not available: {e}")
    ComplianceEngine = ComplianceFramework = None

try:
    from src.rbac_governance import RBACGovernance, TenantPolicy, UserIdentity, Role as RBACRole, Permission as RBACPermission
except ImportError as e:
    print(f"Warning: RBAC governance not available: {e}")
    RBACGovernance = TenantPolicy = UserIdentity = RBACRole = RBACPermission = None

try:
    from src.ticketing_adapter import TicketingAdapter
except ImportError as e:
    print(f"Warning: Ticketing adapter not available: {e}")
    TicketingAdapter = None

try:
    from src.wingman_protocol import WingmanProtocol
except ImportError as e:
    print(f"Warning: Wingman protocol not available: {e}")
    WingmanProtocol = None

try:
    from src.runtime_profile_compiler import RuntimeProfileCompiler
except ImportError as e:
    print(f"Warning: Runtime profile compiler not available: {e}")
    RuntimeProfileCompiler = None

try:
    from src.governance_kernel import GovernanceKernel
except ImportError as e:
    print(f"Warning: Governance kernel not available: {e}")
    GovernanceKernel = None

try:
    from src.control_plane_separation import ControlPlaneSeparation
except ImportError as e:
    print(f"Warning: Control plane separation not available: {e}")
    ControlPlaneSeparation = None

try:
    from src.durable_swarm_orchestrator import DurableSwarmOrchestrator
except ImportError as e:
    print(f"Warning: Durable swarm orchestrator not available: {e}")
    DurableSwarmOrchestrator = None

try:
    from src.golden_path_bridge import GoldenPathBridge
except ImportError as e:
    print(f"Warning: Golden path bridge not available: {e}")
    GoldenPathBridge = None

try:
    from src.org_chart_enforcement import OrgChartEnforcement
except ImportError as e:
    print(f"Warning: Org chart enforcement not available: {e}")
    OrgChartEnforcement = None

try:
    from src.shadow_agent_integration import ShadowAgentIntegration
except ImportError as e:
    print(f"Warning: Shadow agent integration not available: {e}")
    ShadowAgentIntegration = None

try:
    from src.triage_rollcall_adapter import TriageRollcallAdapter
except ImportError as e:
    print(f"Warning: Triage rollcall adapter not available: {e}")
    TriageRollcallAdapter = None

try:
    from src.rubix_evidence_adapter import RubixEvidenceAdapter
except ImportError as e:
    print(f"Warning: Rubix evidence adapter not available: {e}")
    RubixEvidenceAdapter = None

try:
    from src.semantics_boundary_controller import SemanticsBoundaryController
except ImportError as e:
    print(f"Warning: Semantics boundary controller not available: {e}")
    SemanticsBoundaryController = None

try:
    from src.bot_governance_policy_mapper import BotGovernancePolicyMapper
except ImportError as e:
    print(f"Warning: Bot governance policy mapper not available: {e}")
    BotGovernancePolicyMapper = None

try:
    from src.bot_telemetry_normalizer import BotTelemetryNormalizer
except ImportError as e:
    print(f"Warning: Bot telemetry normalizer not available: {e}")
    BotTelemetryNormalizer = None

try:
    from src.legacy_compatibility_matrix import LegacyCompatibilityMatrixAdapter
except ImportError as e:
    print(f"Warning: Legacy compatibility matrix not available: {e}")
    LegacyCompatibilityMatrixAdapter = None

try:
    from src.hitl_autonomy_controller import HITLAutonomyController
except ImportError as e:
    print(f"Warning: HITL autonomy controller not available: {e}")
    HITLAutonomyController = None

try:
    from src.compliance_region_validator import ComplianceRegionValidator
except ImportError as e:
    print(f"Warning: Compliance region validator not available: {e}")
    ComplianceRegionValidator = None

try:
    from src.observability_counters import ObservabilitySummaryCounters
except ImportError as e:
    print(f"Warning: Observability summary counters not available: {e}")
    ObservabilitySummaryCounters = None

try:
    from src.deterministic_routing_engine import DeterministicRoutingEngine
except ImportError as e:
    print(f"Warning: Deterministic routing engine not available: {e}")
    DeterministicRoutingEngine = None

try:
    from src.platform_connector_framework import PlatformConnectorFramework
except ImportError as e:
    print(f"Warning: Platform connector framework not available: {e}")
    PlatformConnectorFramework = None

try:
    from src.workflow_dag_engine import WorkflowDAGEngine
except ImportError as e:
    print(f"Warning: Workflow DAG engine not available: {e}")
    WorkflowDAGEngine = None

try:
    from src.automation_type_registry import AutomationTypeRegistry
except ImportError as e:
    print(f"Warning: Automation type registry not available: {e}")
    AutomationTypeRegistry = None

try:
    from src.api_gateway_adapter import APIGatewayAdapter
except ImportError as e:
    print(f"Warning: API gateway adapter not available: {e}")
    APIGatewayAdapter = None

try:
    from src.webhook_event_processor import WebhookEventProcessor
except ImportError as e:
    print(f"Warning: Webhook event processor not available: {e}")
    WebhookEventProcessor = None

try:
    from src.self_automation_orchestrator import SelfAutomationOrchestrator
except ImportError as e:
    print(f"Warning: Self-automation orchestrator not available: {e}")
    SelfAutomationOrchestrator = None

try:
    from src.plugin_extension_sdk import PluginExtensionSDK
except ImportError as e:
    print(f"Warning: Plugin extension SDK not available: {e}")
    PluginExtensionSDK = None

try:
    from src.ai_workflow_generator import AIWorkflowGenerator
except ImportError as e:
    print(f"Warning: AI workflow generator not available: {e}")
    AIWorkflowGenerator = None

try:
    from src.workflow_template_marketplace import WorkflowTemplateMarketplace
except ImportError as e:
    print(f"Warning: Workflow template marketplace not available: {e}")
    WorkflowTemplateMarketplace = None

try:
    from src.cross_platform_data_sync import CrossPlatformDataSync
except ImportError as e:
    print(f"Warning: Cross-platform data sync not available: {e}")
    CrossPlatformDataSync = None

# Building Automation Connectors
try:
    from src.building_automation_connectors import BuildingAutomationRegistry
except ImportError as e:
    print(f"Warning: Building automation connectors not available: {e}")
    BuildingAutomationRegistry = None

# Manufacturing Automation Standards
try:
    from src.manufacturing_automation_standards import ManufacturingAutomationRegistry
except ImportError as e:
    print(f"Warning: Manufacturing automation standards not available: {e}")
    ManufacturingAutomationRegistry = None

# Energy Management Connectors
try:
    from src.energy_management_connectors import EnergyManagementRegistry
except ImportError as e:
    print(f"Warning: Energy management connectors not available: {e}")
    EnergyManagementRegistry = None

# Analytics Dashboard
try:
    from src.analytics_dashboard import AnalyticsDashboard
except ImportError as e:
    print(f"Warning: Analytics dashboard not available: {e}")
    AnalyticsDashboard = None

# Executive Planning Engine
try:
    from src.executive_planning_engine import ExecutivePlanningEngine
except ImportError as e:
    print(f"Warning: Executive planning engine not available: {e}")
    ExecutivePlanningEngine = None

# Enterprise Integrations
try:
    from src.enterprise_integrations import EnterpriseIntegrationRegistry
except ImportError as e:
    print(f"Warning: Enterprise integrations not available: {e}")
    EnterpriseIntegrationRegistry = None

# Digital Asset Generator
try:
    from src.digital_asset_generator import DigitalAssetGenerator
except ImportError as e:
    print(f"Warning: Digital asset generator not available: {e}")
    DigitalAssetGenerator = None

# Rosetta Stone Heartbeat
try:
    from src.rosetta_stone_heartbeat import RosettaStoneHeartbeat
except ImportError as e:
    print(f"Warning: Rosetta stone heartbeat not available: {e}")
    RosettaStoneHeartbeat = None

# Content Creator Platform Modulator
try:
    from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
except ImportError as e:
    print(f"Warning: Content creator platform modulator not available: {e}")
    ContentCreatorPlatformRegistry = None

# ML Strategy Engine
try:
    from src.ml_strategy_engine import MLStrategyEngine
except ImportError as e:
    print(f"Warning: ML strategy engine not available: {e}")
    MLStrategyEngine = None

# Agentic API Provisioner
try:
    from src.agentic_api_provisioner import AgenticAPIProvisioner
except ImportError as e:
    print(f"Warning: Agentic API provisioner not available: {e}")
    AgenticAPIProvisioner = None

# Video Streaming Connector
try:
    from src.video_streaming_connector import VideoStreamingRegistry
except ImportError as e:
    print(f"Warning: Video streaming connector not available: {e}")
    VideoStreamingRegistry = None

# Remote Access Connector
try:
    from src.remote_access_connector import RemoteAccessRegistry
except ImportError as e:
    print(f"Warning: Remote access connector not available: {e}")
    RemoteAccessRegistry = None

# UI Testing Framework
try:
    from src.ui_testing_framework import UITestingFramework
except ImportError as e:
    print(f"Warning: UI testing framework not available: {e}")
    UITestingFramework = None

# Security Hardening Config
try:
    from src.security_hardening_config import SecurityHardeningConfig
except ImportError as e:
    print(f"Warning: Security hardening config not available: {e}")
    SecurityHardeningConfig = None

# Image Generation Engine (open-source, no API key required)
try:
    from src.image_generation_engine import ImageGenerationEngine, ImageRequest, ImageStyle
except ImportError as e:
    print(f"Warning: Image generation engine not available: {e}")
    ImageGenerationEngine = None

# Universal Integration Adapter (plug-and-play for any service)
try:
    from src.universal_integration_adapter import UniversalIntegrationAdapter, IntegrationSpec
except ImportError as e:
    print(f"Warning: Universal integration adapter not available: {e}")
    UniversalIntegrationAdapter = None

# FastAPI for REST API
try:
    from fastapi import Depends, FastAPI, HTTPException, Request
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




__all__ = [
    # stdlib re-exports
    "sys", "os", "json", "importlib",
    "deepcopy", "Path", "deque", "Mapping",
    "Dict", "List", "Optional", "Any", "Tuple", "Literal", "Set", "TYPE_CHECKING",
    "asdict", "is_dataclass",
    "datetime", "timedelta", "timezone",
    "logging", "asyncio", "platform", "time", "re", "math", "numbers",
    "uuid4", "Lock",
    # Internal module system
    "module_manager", "ModularRuntime",
    # logger
    "logger",
    # FastAPI / web
    "FastAPI", "uvicorn", "CORSMiddleware", "HTTPException", "JSONResponse",
    "Depends", "Request",
    # Governance
    "GOVERNANCE_AVAILABLE", "GovernanceScheduler", "GovernanceKernel",
    "GovernanceActionType", "ActionSet", "ScheduledAgent", "PriorityLevel",
    "AgentDescriptor", "GovernanceAuthorityBand",
    # Swarm / telemetry
    "TrueSwarmSystem", "TelemetryIngester", "TelemetryBus",
    "SystemLibrarian",
    # Event backbone
    "EventBackbone", "BackboneEventType",
    # Core engines
    "UniversalControlPlane", "InoniBusinessAutomation",
    "UnifiedIntegrationEngine", "TwoPhaseOrchestrator",
    "IntegratedFormExecutor", "IntegratedCorrectionSystem",
    "IntegratedHITLMonitor", "SelfImprovementEngine",
    "SelfAutomationOrchestrator",
    # Control plane / adapters
    "AutomationTypeRegistry", "ControlPlaneSeparation",
    "UniversalIntegrationAdapter", "AdapterRuntime",
    "PlatformConnectorFramework", "EnterpriseIntegrationRegistry",
    "RBACGovernance", "ComplianceEngine", "ComplianceFramework",
    "AnalyticsDashboard", "WorkflowDAGEngine", "AIWorkflowGenerator",
    # Automation registries
    "ManufacturingAutomationRegistry", "BuildingAutomationRegistry",
    "EnergyManagementRegistry", "ContentCreatorPlatformRegistry",
    "VideoStreamingRegistry", "RemoteAccessRegistry",
    # Delivery / document
    "DeliveryOrchestrator", "DocumentDeliveryAdapter", "VoiceDeliveryAdapter",
    # Persistence / scheduling
    "PersistenceManager", "AutomationScheduler",
    # Strategy / simulation / compliance types
    "MLStrategyEngine", "ExecutivePlanningEngine",
    "CapabilityMap", "GoldenPathBridge",
    "SecurityHardeningConfig", "ComplianceRegionValidator",
    "UnifiedConfidenceEngine", "ObservabilitySummaryCounters",
    "OperationalSLOTracker", "RuntimeProfileCompiler",
    "DeterministicRoutingEngine", "SemanticsBoundaryController",
    "LegacyCompatibilityMatrixAdapter", "PluginExtensionSDK",
    "WorkflowTemplateMarketplace", "CrossPlatformDataSync",
    "UITestingFramework", "RosettaStoneHeartbeat",
    "ShadowAgentIntegration", "DurableSwarmOrchestrator",
    "AgenticAPIProvisioner", "TicketingAdapter",
    "TriageRollcallAdapter", "BotGovernancePolicyMapper",
    "BotTelemetryNormalizer", "HITLAutonomyController",
    "APIGatewayAdapter", "WebhookEventProcessor",
    "WingmanProtocol", "GateExecutionWiring",
    "RubixEvidenceAdapter", "MFGCAdapter",
    "ImageGenerationEngine", "DigitalAssetGenerator",
    "OrgChartEnforcement", "OrganizationChart",
    "StrategicSimulationEngine", "StructuralCoherenceEngine",
    "ResolutionDetectionEngine", "ConceptTranslationEngine",
    "InformationDensityEngine", "InformationQualityEngine",
    "SystemIntegrator",
    # RBAC / tenant / identity types
    "RBACPermission", "RBACRole", "TenantPolicy", "UserIdentity",
    # Execution / SLO types
    "ExecutionOutcome", "OutcomeType",
    "SLOTarget", "SLOExecutionRecord",
    # Gate types
    "GatePolicy", "GateType",
    # Image types
    "ImageRequest", "ImageStyle",
    # Integration / scheduling types
    "IntegrationSpec", "MFGCConfig",
    "ProjectSchedule", "SchedulePriority",
    # Compute / MSS
    "ComputeServiceType", "MSSController", "_mss_available",
    # Form handling
    "FormHandler",
]
