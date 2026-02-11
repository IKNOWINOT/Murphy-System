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
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio
import time
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Core imports
from src.module_manager import module_manager
from src.modular_runtime import ModularRuntime

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
    from src.governance_framework.scheduler import GovernanceScheduler
    from src.telemetry_learning.ingestion import TelemetryIngester, TelemetryBus
except ImportError as e:
    print(f"Warning: Some original Murphy components not available: {e}")
    SystemLibrarian = TrueSwarmSystem = GovernanceScheduler = TelemetryIngester = TelemetryBus = None

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


class LivingDocument:
    """
    Living document model used for block-command workflows.

    - magnify: expands domain depth to increase context coverage
    - simplify: reduces complexity to improve clarity
    - solidify: locks the document and triggers swarm task generation
    - block_tree: hierarchical representation of pending/complete actions
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
            "generated_tasks": self.generated_tasks
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
    
    def __init__(self):
        self.version = "1.0.0"
        self.start_time = datetime.utcnow()
        
        logger.info("="*80)
        logger.info(f"MURPHY SYSTEM {self.version} - INITIALIZING")
        logger.info("="*80)
        
        # Initialize core components
        logger.info("Initializing core components...")
        self.module_manager = module_manager
        self.modular_runtime = ModularRuntime()
        
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
            if TelemetryBus and TelemetryIngester:
                self.telemetry_bus = TelemetryBus()
                self.telemetry_ingester = TelemetryIngester(self.telemetry_bus)
            else:
                self.telemetry_bus = None
                self.telemetry_ingester = None
        except Exception as e:
            logger.warning(f"Some original components not available: {e}")
        
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
        self.latest_activation_preview: Dict[str, Any] = {}
        self.execution_metrics = {"total": 0, "success": 0, "total_time": 0.0}
        self.chat_sessions: Dict[str, Dict] = {}
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
        self.flow_steps = [
            {
                "stage": "signup",
                "prompt": "Collect signup details (company name, contact email, primary goal)."
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
        
        logger.info("="*80)
        logger.info(f"MURPHY SYSTEM {self.version} - READY")
        logger.info("="*80)
    
    # ==================== CORE EXECUTION ====================
    
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
        
        if not self._is_orchestrator_available():
            logger.warning("Two-Phase Orchestrator unavailable; using simulation mode.")
            return self._simulate_execution(task_description, task_type, parameters, session_id)

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
            
            # Return complete result
            return {
                'success': True,
                'session_id': session_id,
                'execution_packet': execution_packet,
                'result': execution_result.get('result'),
                'deliverables': execution_result.get('deliverables', []),
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
        return {
            "success": True,
            "session_id": session_id or self.create_session().get("session_id"),
            "result": summary,
            "deliverables": [],
            "metadata": {
                "task_description": task_description,
                "task_type": task_type,
                "timestamp": datetime.utcnow().isoformat(),
                "mode": "simulation"
            }
        }

    def _is_orchestrator_available(self) -> bool:
        return (
            self.orchestrator is not None
            and hasattr(self.orchestrator, "phase1_generative_setup")
            and hasattr(self.orchestrator, "phase2_production_execution")
        )

    @staticmethod
    def _component_status(component_instance: Optional[Any]) -> str:
        return "active" if component_instance else "inactive"

    def _create_document(self, title: str, content: str, doc_type: str, session_id: Optional[str] = None) -> LivingDocument:
        doc = LivingDocument(uuid4().hex, title, content, doc_type)
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
        """Generate default swarm tasks from onboarding flow steps."""
        tasks = []
        for step in self.flow_steps:
            tasks.append({
                "task_id": uuid4().hex,
                "stage": step["stage"],
                "description": step["prompt"]
            })
        return tasks

    def _build_gate_chain(self, doc: LivingDocument) -> List[Dict[str, Any]]:
        gate_templates = [
            ("Magnify Gate", 0.5),
            ("Simplify Gate", 0.6),
            ("Solidify Gate", 0.7)
        ]
        gates = []
        for name, threshold in gate_templates:
            status = "open" if doc.confidence >= threshold else "blocked"
            gates.append({
                "name": name,
                "threshold": threshold,
                "status": status
            })
        return gates

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

    def _record_activation_usage(self, subsystems: List[str]) -> None:
        for subsystem in subsystems:
            self.activation_usage[subsystem] = self.activation_usage.get(subsystem, 0) + 1

    def _build_activation_preview(
        self,
        doc: LivingDocument,
        task_description: str,
        onboarding_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        text = task_description.lower()
        candidates = [
            {
                "id": "gate_synthesis",
                "reason": "Translate onboarding intent into gate checks.",
                "keywords": ["gate", "risk", "compliance", "safety"]
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
            if doc.confidence < 0.7:
                planned_subsystems.append({
                    "id": "gate_synthesis",
                    "reason": "Low confidence triggers gate checks."
                })
            if "automation" in text or doc.state == "SOLIDIFIED":
                planned_subsystems.append({
                    "id": "true_swarm_system",
                    "reason": "Automation requests expand into swarm execution stages."
                })
        if not planned_subsystems:
            planned_subsystems.append({
                "id": "gate_synthesis",
                "reason": "Default gate checks ensure baseline safety."
            })
        self._record_activation_usage([item["id"] for item in planned_subsystems])

        tasks_source = doc.generated_tasks or self._generate_swarm_tasks()
        planned_swarm_tasks = [
            {**task, "status": task.get("status", "pending")}
            for task in tasks_source
        ]

        onboarding_questions = [
            {"stage": step["stage"], "prompt": step["prompt"]}
            for step in self.flow_steps
        ]

        preview = {
            "request_summary": task_description,
            "confidence": doc.confidence,
            "planned_subsystems": planned_subsystems,
            "planned_gates": doc.gates,
            "planned_swarm_tasks": planned_swarm_tasks,
            "onboarding_questions": onboarding_questions,
            "constraints": doc.constraints
        }
        if onboarding_context:
            preview["onboarding_context"] = onboarding_context
        return preview

    def _record_execution(self, success: bool, duration: float) -> None:
        self.execution_metrics["total"] += 1
        if success:
            self.execution_metrics["success"] += 1
        self.execution_metrics["total_time"] += duration
        total = self.execution_metrics["total"]
        success_rate = (self.execution_metrics["success"] / total) * 100 if total else 0.0
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
        stage_index = session.get("stage_index", 0)
        current_stage = self.flow_steps[stage_index]
        session.setdefault("history", []).append({
            "stage": current_stage["stage"],
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        next_index = min(stage_index + 1, len(self.flow_steps) - 1)
        session["stage_index"] = next_index
        next_stage = self.flow_steps[next_index]
        return {
            "current_stage": current_stage["stage"],
            "next_stage": next_stage["stage"],
            "prompt": next_stage["prompt"]
        }

    def _build_mfgc_payload(self, stage: str, duration: float) -> Dict[str, Any]:
        phase_map = {
            "signup": "expand",
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
        doc = self._ensure_document(task_description, task_type, data.get("session_id"))
        confidence_report = self._build_confidence_report(task_description)
        result = await self.execute_task(task_description, task_type, parameters)
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
            'self_operation': {
                'enabled': self_operation_enabled,
                'can_work_on_self': self_operation_enabled and correction_system_available,
                'activation_required': True,
                'state': 'active' if self_operation_enabled else 'unavailable'
            }
        }
    
    def get_system_info(self) -> Dict:
        """Get system information"""
        
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
            }
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
                "id": "recursive_stability_controller",
                "name": "Recursive Stability Controller",
                "path": base_dir / "recursive_stability_controller",
                "wired": False,
                "initialized": False,
                "notes": "Telemetry and stability services exist but are not started by runtime."
            },
            {
                "id": "gate_synthesis",
                "name": "Gate Synthesis Engine",
                "path": base_dir / "gate_synthesis",
                "wired": False,
                "initialized": False,
                "notes": "Gate synthesis APIs are implemented but not invoked from runtime flows."
            },
            {
                "id": "compute_plane",
                "name": "Compute Plane",
                "path": base_dir / "compute_plane",
                "wired": False,
                "initialized": False,
                "notes": "Symbolic/numeric solver service is available but not exposed in runtime."
            },
            {
                "id": "infinity_expansion_system",
                "name": "Infinity Expansion System",
                "path": base_dir / "infinity_expansion_system.py",
                "wired": False,
                "initialized": False,
                "notes": "Problem expansion logic is present but not hooked into execution."
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
                "wired": False,
                "initialized": False,
                "notes": "Domain swarm generators are defined but unused in runtime."
            },
            {
                "id": "true_swarm_system",
                "name": "True Swarm System",
                "path": base_dir / "true_swarm_system.py",
                "wired": False,
                "initialized": swarm_initialized,
                "notes": "Swarm system initializes but is not invoked by execute_task."
            },
            {
                "id": "knowledge_gap_system",
                "name": "Knowledge Gap System",
                "path": base_dir / "knowledge_gap_system.py",
                "wired": False,
                "initialized": False,
                "notes": "Gap detection logic exists but is not referenced."
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
