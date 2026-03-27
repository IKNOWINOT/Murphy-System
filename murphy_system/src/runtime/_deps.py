"""
Murphy System 1.0 - Dependency Resolution

All third-party and internal imports with graceful fallbacks.
Extracted from the monolithic runtime for maintainability (INC-13 / H-04 / L-02).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import asyncio
import importlib.util
import json
import logging
import math
import numbers
import os
import platform
import re
import sys
import time
from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Set, Tuple
from uuid import uuid4

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:
    _load_dotenv = None

# B-001: Actually call load_dotenv() so .env variables are loaded at import time.
# Resolve to project root (murphy_system/) — three levels up from src/runtime/_deps.py.
if _load_dotenv is not None:
    _load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)

from threading import Lock

# Setup logging early so all import warnings use the logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root (murphy_system/) to path so both ``src.*`` and bare
# module names resolve correctly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Core imports
from src.modular_runtime import ModularRuntime
from src.module_manager import module_manager

if TYPE_CHECKING:
    from src.compute_plane.service import ComputeService as ComputeServiceType
else:
    ComputeServiceType = Any

# Universal Control Plane
try:
    from universal_control_plane import UniversalControlPlane
except ImportError as e:
    logger.warning("Could not import UniversalControlPlane: %s", e)
    UniversalControlPlane = None

# Inoni Business Automation
try:
    from inoni_business_automation import InoniBusinessAutomation
except ImportError as e:
    logger.warning("Could not import InoniBusinessAutomation: %s", e)
    InoniBusinessAutomation = None

# Integration Engine
try:
    from src.integration_engine.unified_engine import UnifiedIntegrationEngine
except ImportError as e:
    logger.warning("Could not import UnifiedIntegrationEngine: %s", e)
    logger.warning("This may be due to missing dependencies. Please ensure all requirements are installed.")
    UnifiedIntegrationEngine = None

# Two-Phase Orchestrator
try:
    from two_phase_orchestrator import TwoPhaseOrchestrator
except ImportError as e:
    logger.warning("Could not import TwoPhaseOrchestrator: %s", e)
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
    from src.governance_framework.agent_descriptor_complete import ActionSet, AgentDescriptor
    from src.governance_framework.agent_descriptor_complete import ActionType as GovernanceActionType
    from src.governance_framework.agent_descriptor_complete import AuthorityBand as GovernanceAuthorityBand
    from src.governance_framework.scheduler import GovernanceScheduler, PriorityLevel, ScheduledAgent
    from src.system_librarian import SystemLibrarian
    from src.telemetry_learning.ingestion import TelemetryBus, TelemetryIngester
    from src.true_swarm_system import TrueSwarmSystem
except ImportError as e:
    logger.warning("Some original Murphy components not available: %s", e)
    SystemLibrarian = TrueSwarmSystem = GovernanceScheduler = TelemetryIngester = TelemetryBus = None
    ScheduledAgent = PriorityLevel = AgentDescriptor = GovernanceAuthorityBand = GovernanceActionType = ActionSet = None

# MFGC Adapter
try:
    from src.mfgc_adapter import MFGCAdapter, MFGCConfig
    from src.system_integrator import SystemIntegrator
except ImportError as e:
    logger.warning("MFGC adapter not available: %s", e)
    MFGCAdapter = MFGCConfig = SystemIntegrator = None

# Adapter Framework
try:
    from src.adapter_framework.adapter_runtime import AdapterRuntime
except ImportError as e:
    logger.warning("Adapter runtime not available: %s", e)
    AdapterRuntime = None

# MSS Controls & Intelligence Layer
try:
    from src.concept_translation import ConceptTranslationEngine
    from src.information_density import InformationDensityEngine
    from src.information_quality import InformationQualityEngine
    from src.mss_controls import MSSController
    from src.resolution_scoring import ResolutionDetectionEngine
    from src.simulation_engine import StrategicSimulationEngine
    from src.structural_coherence import StructuralCoherenceEngine
    _mss_available = True
except ImportError as e:
    logger.warning("MSS controls not available: %s", e)
    _mss_available = False

# Org Chart System
try:
    from src.organization_chart_system import OrganizationChart
except ImportError as e:
    logger.warning("Organization chart system not available: %s", e)
    OrganizationChart = None

# New integrated modules
try:
    from src.persistence_manager import PersistenceManager
except ImportError as e:
    logger.warning("Persistence manager not available: %s", e)
    PersistenceManager = None

try:
    from src.event_backbone import EventBackbone
    from src.event_backbone import EventType as BackboneEventType
except ImportError as e:
    logger.warning("Event backbone not available: %s", e)
    EventBackbone = None
    BackboneEventType = None

try:
    from src.delivery_adapters import (
        ChatDeliveryAdapter,
        DeliveryChannel,
        DeliveryOrchestrator,
        DeliveryRequest,
        DeliveryStatus,
        DocumentDeliveryAdapter,
        EmailDeliveryAdapter,
        TranslationDeliveryAdapter,
        VoiceDeliveryAdapter,
    )
except ImportError as e:
    logger.warning("Delivery adapters not available: %s", e)
    DeliveryOrchestrator = DeliveryChannel = DeliveryRequest = DeliveryStatus = None
    DocumentDeliveryAdapter = EmailDeliveryAdapter = ChatDeliveryAdapter = None
    VoiceDeliveryAdapter = TranslationDeliveryAdapter = None

try:
    from src.gate_execution_wiring import GateExecutionWiring, GatePolicy, GateType
except ImportError as e:
    logger.warning("Gate execution wiring not available: %s", e)
    GateExecutionWiring = GateType = GatePolicy = None

try:
    from src.self_improvement_engine import ExecutionOutcome, OutcomeType, SelfImprovementEngine
except ImportError as e:
    logger.warning("Self-improvement engine not available: %s", e)
    SelfImprovementEngine = ExecutionOutcome = OutcomeType = None

try:
    from src.operational_slo_tracker import ExecutionRecord as SLOExecutionRecord
    from src.operational_slo_tracker import OperationalSLOTracker, SLOTarget
except ImportError as e:
    logger.warning("Operational SLO tracker not available: %s", e)
    OperationalSLOTracker = SLOTarget = SLOExecutionRecord = None

try:
    from src.automation_scheduler import AutomationScheduler, ProjectSchedule, SchedulePriority
except ImportError as e:
    logger.warning("Automation scheduler not available: %s", e)
    AutomationScheduler = ProjectSchedule = SchedulePriority = None

try:
    from src.self_fix_loop import SelfFixLoop
except ImportError as e:
    logger.warning("SelfFixLoop not available: %s", e)
    SelfFixLoop = None

try:
    from src.scheduler import MurphyScheduler
except ImportError as e:
    logger.warning("MurphyScheduler not available: %s", e)
    MurphyScheduler = None

try:
    from src.autonomous_repair_system import AutonomousRepairSystem
except ImportError as e:
    logger.warning("AutonomousRepairSystem not available: %s", e)
    AutonomousRepairSystem = None

try:
    from src.capability_map import CapabilityMap
except ImportError as e:
    logger.warning("Capability map not available: %s", e)
    CapabilityMap = None

try:
    from src.compliance_engine import ComplianceEngine, ComplianceFramework
except ImportError as e:
    logger.warning("Compliance engine not available: %s", e)
    ComplianceEngine = ComplianceFramework = None

try:
    from src.rbac_governance import Permission as RBACPermission
    from src.rbac_governance import RBACGovernance, TenantPolicy, UserIdentity
    from src.rbac_governance import Role as RBACRole
except ImportError as e:
    logger.warning("RBAC governance not available: %s", e)
    RBACGovernance = TenantPolicy = UserIdentity = RBACRole = RBACPermission = None

try:
    from src.ticketing_adapter import TicketingAdapter
except ImportError as e:
    logger.warning("Ticketing adapter not available: %s", e)
    TicketingAdapter = None

try:
    from src.wingman_protocol import WingmanProtocol
except ImportError as e:
    logger.warning("Wingman protocol not available: %s", e)
    WingmanProtocol = None

try:
    from src.wingman_system import WingmanSystem
except ImportError as e:
    logger.warning("Wingman system not available: %s", e)
    WingmanSystem = None

try:
    from src.api_capability_builder import WingmanApiGapChecker
except ImportError as e:
    logger.warning("API capability builder not available: %s", e)
    WingmanApiGapChecker = None

try:
    from src.runtime_profile_compiler import RuntimeProfileCompiler
except ImportError as e:
    logger.warning("Runtime profile compiler not available: %s", e)
    RuntimeProfileCompiler = None

try:
    from src.governance_kernel import GovernanceKernel
except ImportError as e:
    logger.warning("Governance kernel not available: %s", e)
    GovernanceKernel = None

try:
    from src.control_plane_separation import ControlPlaneSeparation
except ImportError as e:
    logger.warning("Control plane separation not available: %s", e)
    ControlPlaneSeparation = None

try:
    from src.durable_swarm_orchestrator import DurableSwarmOrchestrator
except ImportError as e:
    logger.warning("Durable swarm orchestrator not available: %s", e)
    DurableSwarmOrchestrator = None

try:
    from src.golden_path_bridge import GoldenPathBridge
except ImportError as e:
    logger.warning("Golden path bridge not available: %s", e)
    GoldenPathBridge = None

try:
    from src.org_chart_enforcement import OrgChartEnforcement
except ImportError as e:
    logger.warning("Org chart enforcement not available: %s", e)
    OrgChartEnforcement = None

try:
    from src.shadow_agent_integration import ShadowAgentIntegration
except ImportError as e:
    logger.warning("Shadow agent integration not available: %s", e)
    ShadowAgentIntegration = None

try:
    from src.triage_rollcall_adapter import TriageRollcallAdapter
except ImportError as e:
    logger.warning("Triage rollcall adapter not available: %s", e)
    TriageRollcallAdapter = None

try:
    from src.rubix_evidence_adapter import RubixEvidenceAdapter
except ImportError as e:
    logger.warning("Rubix evidence adapter not available: %s", e)
    RubixEvidenceAdapter = None

try:
    from src.semantics_boundary_controller import SemanticsBoundaryController
except ImportError as e:
    logger.warning("Semantics boundary controller not available: %s", e)
    SemanticsBoundaryController = None

try:
    from src.bot_governance_policy_mapper import BotGovernancePolicyMapper
except ImportError as e:
    logger.warning("Bot governance policy mapper not available: %s", e)
    BotGovernancePolicyMapper = None

try:
    from src.bot_telemetry_normalizer import BotTelemetryNormalizer
except ImportError as e:
    logger.warning("Bot telemetry normalizer not available: %s", e)
    BotTelemetryNormalizer = None

try:
    from src.legacy_compatibility_matrix import LegacyCompatibilityMatrixAdapter
except ImportError as e:
    logger.warning("Legacy compatibility matrix not available: %s", e)
    LegacyCompatibilityMatrixAdapter = None

try:
    from src.hitl_autonomy_controller import HITLAutonomyController
except ImportError as e:
    logger.warning("HITL autonomy controller not available: %s", e)
    HITLAutonomyController = None

try:
    from src.compliance_region_validator import ComplianceRegionValidator
except ImportError as e:
    logger.warning("Compliance region validator not available: %s", e)
    ComplianceRegionValidator = None

try:
    from src.observability_counters import ObservabilitySummaryCounters
except ImportError as e:
    logger.warning("Observability summary counters not available: %s", e)
    ObservabilitySummaryCounters = None

try:
    from src.deterministic_routing_engine import DeterministicRoutingEngine
except ImportError as e:
    logger.warning("Deterministic routing engine not available: %s", e)
    DeterministicRoutingEngine = None

try:
    from src.platform_connector_framework import PlatformConnectorFramework
except ImportError as e:
    logger.warning("Platform connector framework not available: %s", e)
    PlatformConnectorFramework = None

try:
    from src.workflow_dag_engine import WorkflowDAGEngine
except ImportError as e:
    logger.warning("Workflow DAG engine not available: %s", e)
    WorkflowDAGEngine = None

try:
    from src.automation_type_registry import AutomationTypeRegistry
except ImportError as e:
    logger.warning("Automation type registry not available: %s", e)
    AutomationTypeRegistry = None

try:
    from src.api_gateway_adapter import APIGatewayAdapter
except ImportError as e:
    logger.warning("API gateway adapter not available: %s", e)
    APIGatewayAdapter = None

try:
    from src.webhook_event_processor import WebhookEventProcessor
except ImportError as e:
    logger.warning("Webhook event processor not available: %s", e)
    WebhookEventProcessor = None

try:
    from src.self_automation_orchestrator import SelfAutomationOrchestrator
except ImportError as e:
    logger.warning("Self-automation orchestrator not available: %s", e)
    SelfAutomationOrchestrator = None

try:
    from src.plugin_extension_sdk import PluginExtensionSDK
except ImportError as e:
    logger.warning("Plugin extension SDK not available: %s", e)
    PluginExtensionSDK = None

try:
    from src.ai_workflow_generator import AIWorkflowGenerator
except ImportError as e:
    logger.warning("AI workflow generator not available: %s", e)
    AIWorkflowGenerator = None

try:
    from src.workflow_template_marketplace import WorkflowTemplateMarketplace
except ImportError as e:
    logger.warning("Workflow template marketplace not available: %s", e)
    WorkflowTemplateMarketplace = None

try:
    from src.cross_platform_data_sync import CrossPlatformDataSync
except ImportError as e:
    logger.warning("Cross-platform data sync not available: %s", e)
    CrossPlatformDataSync = None

# Building Automation Connectors
try:
    from src.building_automation_connectors import BuildingAutomationRegistry
except ImportError as e:
    logger.warning("Building automation connectors not available: %s", e)
    BuildingAutomationRegistry = None

# Manufacturing Automation Standards
try:
    from src.manufacturing_automation_standards import ManufacturingAutomationRegistry
except ImportError as e:
    logger.warning("Manufacturing automation standards not available: %s", e)
    ManufacturingAutomationRegistry = None

# Energy Management Connectors
try:
    from src.energy_management_connectors import EnergyManagementRegistry
except ImportError as e:
    logger.warning("Energy management connectors not available: %s", e)
    EnergyManagementRegistry = None

# Analytics Dashboard
try:
    from src.analytics_dashboard import AnalyticsDashboard
except ImportError as e:
    logger.warning("Analytics dashboard not available: %s", e)
    AnalyticsDashboard = None

# Executive Planning Engine
try:
    from src.executive_planning_engine import ExecutivePlanningEngine
except ImportError as e:
    logger.warning("Executive planning engine not available: %s", e)
    ExecutivePlanningEngine = None

# Enterprise Integrations
try:
    from src.enterprise_integrations import EnterpriseIntegrationRegistry
except ImportError as e:
    logger.warning("Enterprise integrations not available: %s", e)
    EnterpriseIntegrationRegistry = None

# Digital Asset Generator
try:
    from src.digital_asset_generator import DigitalAssetGenerator
except ImportError as e:
    logger.warning("Digital asset generator not available: %s", e)
    DigitalAssetGenerator = None

# Rosetta Stone Heartbeat
try:
    from src.rosetta_stone_heartbeat import RosettaStoneHeartbeat
except ImportError as e:
    logger.warning("Rosetta stone heartbeat not available: %s", e)
    RosettaStoneHeartbeat = None

# Content Creator Platform Modulator
try:
    from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
except ImportError as e:
    logger.warning("Content creator platform modulator not available: %s", e)
    ContentCreatorPlatformRegistry = None

# ML Strategy Engine
try:
    from src.ml_strategy_engine import MLStrategyEngine
except ImportError as e:
    logger.warning("ML strategy engine not available: %s", e)
    MLStrategyEngine = None

# Agentic API Provisioner
try:
    from src.agentic_api_provisioner import AgenticAPIProvisioner
except ImportError as e:
    logger.warning("Agentic API provisioner not available: %s", e)
    AgenticAPIProvisioner = None

# Video Streaming Connector
try:
    from src.video_streaming_connector import VideoStreamingRegistry
except ImportError as e:
    logger.warning("Video streaming connector not available: %s", e)
    VideoStreamingRegistry = None

# Remote Access Connector
try:
    from src.remote_access_connector import RemoteAccessRegistry
except ImportError as e:
    logger.warning("Remote access connector not available: %s", e)
    RemoteAccessRegistry = None

# UI Testing Framework
try:
    from src.ui_testing_framework import UITestingFramework
except ImportError as e:
    logger.warning("UI testing framework not available: %s", e)
    UITestingFramework = None

# Security Hardening Config
try:
    from src.security_hardening_config import SecurityHardeningConfig
except ImportError as e:
    logger.warning("Security hardening config not available: %s", e)
    SecurityHardeningConfig = None

# Image Generation Engine (open-source, no API key required)
try:
    from src.image_generation_engine import ImageGenerationEngine, ImageRequest, ImageStyle
except ImportError as e:
    logger.warning("Image generation engine not available: %s", e)
    ImageGenerationEngine = None

# Universal Integration Adapter (plug-and-play for any service)
try:
    from src.universal_integration_adapter import IntegrationSpec, UniversalIntegrationAdapter
except ImportError as e:
    logger.warning("Universal integration adapter not available: %s", e)
    UniversalIntegrationAdapter = None

# FastAPI for REST API
try:
    import uvicorn
    from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError:
    logger.warning("FastAPI not installed. Install with: pip install fastapi uvicorn")
    FastAPI = None
    uvicorn = None
    CORSMiddleware = None
    HTTPException = None
    JSONResponse = None
    Depends = None
    Request = None
    BackgroundTasks = None

# Dynamic Assist Engine (PR #195)
try:
    from src.dynamic_assist_engine import DynamicAssistEngine, DynamicAssistInput, DynamicAssistOutput
except ImportError as e:
    logger.warning("DynamicAssistEngine not available: %s", e)
    DynamicAssistEngine = None
    DynamicAssistInput = None
    DynamicAssistOutput = None

# KFactor Calculator (PR #195)
try:
    from src.kfactor_calculator import KFactorCalculator
except ImportError as e:
    logger.warning("KFactorCalculator not available: %s", e)
    KFactorCalculator = None

# Shadow-Knostalgia Bridge (PR #195)
try:
    from src.shadow_knostalgia_bridge import ShadowKnostalgiaBridge
except ImportError as e:
    logger.warning("ShadowKnostalgiaBridge not available: %s", e)
    ShadowKnostalgiaBridge = None

# Onboarding Team Pipeline (PR #195)
try:
    from src.onboarding_team_pipeline import OnboardingTeamPipeline
except ImportError as e:
    logger.warning("OnboardingTeamPipeline not available: %s", e)
    OnboardingTeamPipeline = None

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
    "Depends", "Request", "BackgroundTasks",
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
    # Persistence / scheduling / self-automation
    "PersistenceManager", "AutomationScheduler",
    "SelfFixLoop", "MurphyScheduler", "AutonomousRepairSystem",
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
    "WingmanProtocol", "WingmanSystem", "WingmanApiGapChecker", "GateExecutionWiring",
    "RubixEvidenceAdapter", "MFGCAdapter",
    "ImageGenerationEngine", "DigitalAssetGenerator",
    "OrgChartEnforcement", "OrganizationChart",
    "StrategicSimulationEngine", "StructuralCoherenceEngine",
    "ResolutionDetectionEngine", "ConceptTranslationEngine",
    "InformationDensityEngine", "InformationQualityEngine",
    "SystemIntegrator",
    # New modules — PR #195
    "DynamicAssistEngine", "DynamicAssistInput", "DynamicAssistOutput",
    "KFactorCalculator",
    "ShadowKnostalgiaBridge",
    "OnboardingTeamPipeline",
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
    # dotenv
    "_load_dotenv",
]
