"""
System Integrator
Wires all components together: Dynamic Expert Generation, Domain Gates, Constraints,
Document Processing, Inquisitory Engine, and LLM Integration Layer
Provides backend-to-frontend API layer for user interaction
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("system_integrator")

# Import all system components
from src.bot_inventory_library import BotAgent, BotInventoryLibrary, BotRole
from src.constraint_system import Constraint, ConstraintSystem, ConstraintType
from src.contractual_audit import ContractualAgreement, ContractualAuditSystem, ProductivityGap
from src.document_processor import DesignRequirement, DocumentProcessor
from src.domain_gate_generator import DomainGate, DomainGateGenerator, GateType
from src.dynamic_expert_generator import DynamicExpertGenerator, GeneratedExpert
from src.inquisitory_engine import ChoiceRecommendation, ChoiceType, InquisitoryEngine
from src.llm_integration_layer import DomainType, LLMIntegrationLayer, LLMProvider
from src.system_librarian import SystemLibrarian


@dataclass
class SystemState:
    """Overall system state"""
    system_id: str
    initialized: bool
    experts: List[GeneratedExpert]
    gates: List[DomainGate]
    constraints: Dict[str, Constraint]
    requirements: List[DesignRequirement]
    recommendations: List[ChoiceRecommendation]
    last_updated: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict:
        return {
            "system_id": self.system_id,
            "initialized": self.initialized,
            "expert_count": len(self.experts),
            "gate_count": len(self.gates),
            "constraint_count": len(self.constraints),
            "requirement_count": len(self.requirements),
            "recommendation_count": len(self.recommendations),
            "last_updated": self.last_updated,
            "metrics": self.metrics
        }

    def __contains__(self, item):
        """Support 'in' operator for dict-like field access"""
        return hasattr(self, item) or item in self.to_dict()

    def get(self, key, default=None):
        """Dict-like get for compatibility"""
        if hasattr(self, key):
            return getattr(self, key)
        return self.to_dict().get(key, default)

    def __getitem__(self, key):
        """Dict-like index access"""
        if hasattr(self, key):
            return getattr(self, key)
        return self.to_dict()[key]


@dataclass
class UserRequest:
    """User request from frontend"""
    request_id: str
    user_input: str
    request_type: str  # build_system, generate_expert, create_gates, etc.
    parameters: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "user_input": self.user_input,
            "request_type": self.request_type,
            "parameters": self.parameters,
            "timestamp": self.timestamp
        }


@dataclass
class SystemResponse:
    """Response to frontend"""
    request_id: str
    success: bool
    data: Dict[str, Any]
    message: str
    warnings: List[str]
    triggers: List[Dict[str, Any]]
    timestamp: str

    @property
    def response(self) -> str:
        """Alias for message, for test compatibility"""
        return self.message

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "warnings": self.warnings,
            "triggers": self.triggers,
            "timestamp": self.timestamp,
            "response": self.message,
        }

    def __contains__(self, item):
        """Support 'in' operator for dict-like field access"""
        return hasattr(self, item) or item in self.to_dict()


class SystemIntegrator:
    """
    Master integrator that wires all system components together
    Provides unified API for frontend interaction
    """

    def __init__(self):
        self.system_id = f"murphy_system_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.request_count = 0

        # Initialize all components
        self.expert_generator = DynamicExpertGenerator()
        self.gate_generator = DomainGateGenerator()
        self.constraint_system = ConstraintSystem()
        self.document_processor = DocumentProcessor()
        self.inquisitory_engine = InquisitoryEngine()
        self.llm_layer = LLMIntegrationLayer()
        self.bot_inventory = BotInventoryLibrary()
        self.contractual_audit = ContractualAuditSystem()
        self.librarian = SystemLibrarian()

        # Security components
        try:
            from src.security_plane_adapter import SecurityPlaneAdapter
            self.security_adapter = SecurityPlaneAdapter()
            self.security_enabled = True
        except ImportError:
            self.security_adapter = None
            self.security_enabled = False

        # Module compiler components
        try:
            from src.module_compiler_adapter import ModuleCompilerAdapter
            self.module_compiler = ModuleCompilerAdapter()
            self.module_compiler_enabled = True
        except ImportError:
            self.module_compiler = None
            self.module_compiler_enabled = False

        # Neuro-symbolic adapter
        try:
            from src.neuro_symbolic_adapter import NeuroSymbolicAdapter
            from src.neuro_symbolic_models import NeuroSymbolicConfidenceModel
            neuro_symbolic_models = NeuroSymbolicConfidenceModel()
            self.neuro_symbolic = NeuroSymbolicAdapter(neuro_symbolic_models)
            self.neuro_symbolic_enabled = True
        except ImportError:
            self.neuro_symbolic = None
            self.neuro_symbolic_enabled = False

        # Telemetry adapter
        try:
            from src.telemetry_adapter import TelemetryAdapter
            from src.telemetry_learning import TelemetryLearningEngine
            telemetry_learning = TelemetryLearningEngine()
            self.telemetry = TelemetryAdapter(telemetry_learning)
            self.telemetry_enabled = True
        except ImportError:
            self.telemetry = None
            self.telemetry_enabled = False

        # Librarian adapter
        try:
            from src.librarian import LibrarianModule
            from src.librarian_adapter import LibrarianAdapter
            librarian_module = LibrarianModule()
            self.librarian_adapter = LibrarianAdapter(librarian_module)
            self.librarian_adapter_enabled = True
        except ImportError:
            self.librarian_adapter = None
            self.librarian_adapter_enabled = False

        # Dynamic Assist Engine + KFactor Calculator (PR #195)
        try:
            from src.dynamic_assist_engine import DynamicAssistEngine
            from src.kfactor_calculator import KFactorCalculator
            self.kfactor_calculator = KFactorCalculator()
            self.dynamic_assist_engine = DynamicAssistEngine()
            self.dynamic_assist_enabled = True
        except ImportError:
            self.kfactor_calculator = None
            self.dynamic_assist_engine = None
            self.dynamic_assist_enabled = False

        # Shadow-Knostalgia Bridge (PR #195)
        try:
            from src.shadow_knostalgia_bridge import ShadowKnostalgiaBridge
            self.shadow_knostalgia_bridge = ShadowKnostalgiaBridge(
                kfactor_calculator=self.kfactor_calculator,
                dynamic_assist_engine=self.dynamic_assist_engine,
            )
            self.shadow_knostalgia_bridge_enabled = True
        except ImportError:
            self.shadow_knostalgia_bridge = None
            self.shadow_knostalgia_bridge_enabled = False

        # Onboarding Team Pipeline (PR #195)
        try:
            from src.onboarding_team_pipeline import OnboardingTeamPipeline
            self.onboarding_team_pipeline = OnboardingTeamPipeline()
            self.onboarding_team_pipeline_enabled = True
        except ImportError:
            self.onboarding_team_pipeline = None
            self.onboarding_team_pipeline_enabled = False

        # System state
        self.experts: List[GeneratedExpert] = []
        self.gates: List[DomainGate] = []
        self.requirements: List[DesignRequirement] = []
        self.recommendations: List[ChoiceRecommendation] = []

        # Request history
        self.request_history: List[UserRequest] = []
        self.response_history: List[SystemResponse] = []

    def process_user_request(self, user_input: str, parameters: Optional[Dict] = None) -> SystemResponse:
        """
        Process user request from frontend

        Args:
            user_input: User's natural language input
            parameters: Additional parameters (files, specific settings, etc.)

        Returns:
            SystemResponse object
        """
        self.request_count += 1
        request_id = f"req_{self.request_count}"

        # Security validation
        if self.security_enabled and self.security_adapter:
            # Validate and sanitize input
            is_valid, error_msg = self.security_adapter.validate_input("user_message", user_input)
            if not is_valid:
                # Detect anomaly
                self.security_adapter.detect_anomaly(
                    anomaly_type="injection_attempt",
                    entity_id=f"user_{request_id}",
                    details={"error": error_msg, "input": user_input[:100]}
                )
                return SystemResponse(
                    request_id=request_id,
                    response_type="error",
                    content=f"Security validation failed: {error_msg}",
                    confidence=1.0,
                    metadata={"security_error": True, "error_type": "validation_failed"}
                )

            # Sanitize input
            user_input = self.security_adapter.sanitize_input(user_input, "string")

        # Create request object
        request = UserRequest(
            request_id=request_id,
            user_input=user_input,
            request_type="auto_detect",
            parameters=parameters or {},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.request_history.append(request)

        # Detect request type and route appropriately
        request_type = self._detect_request_type(user_input, parameters or {})

        try:
            # Process based on type
            if request_type == "build_system":
                response = self._handle_build_system(request)
            elif request_type == "generate_experts":
                response = self._handle_generate_experts(request)
            elif request_type == "create_gates":
                response = self._handle_create_gates(request)
            elif request_type == "add_constraints":
                response = self._handle_add_constraints(request)
            elif request_type == "upload_document":
                response = self._handle_upload_document(request)
            elif request_type == "analyze_choice":
                response = self._handle_analyze_choice(request)
            elif request_type == "validate_system":
                response = self._handle_validate_system(request)
            elif request_type == "get_recommendations":
                response = self._handle_get_recommendations(request)
            elif request_type == "chat":
                response = self._handle_chat(request)
            else:
                response = self._handle_general_query(request)

            # Add human-in-the-loop triggers from LLM layer
            triggers = self.llm_layer.get_pending_triggers()
            response.triggers = [t.to_dict() for t in triggers]

            # Add to history
            self.response_history.append(response)

            return response

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return SystemResponse(
                request_id=request_id,
                success=False,
                data={},
                message=f"Error processing request: {str(exc)}",
                warnings=[],
                triggers=[],
                timestamp=datetime.now(timezone.utc).isoformat()
            )

    def _detect_request_type(self, user_input: str, parameters: Dict) -> str:
        """Detect type of user request"""
        input_lower = user_input.lower()

        # Check for explicit type in parameters
        if "request_type" in parameters:
            return parameters["request_type"]

        # Pattern matching
        if any(keyword in input_lower for keyword in
               ["build system", "create system", "design system", "setup system"]):
            return "build_system"
        elif any(keyword in input_lower for keyword in
                 ["expert", "team", "specialist", "hire"]):
            return "generate_experts"
        elif any(keyword in input_lower for keyword in
                 ["gate", "safety", "validation", "compliance"]):
            return "create_gates"
        elif any(keyword in input_lower for keyword in
                 ["constraint", "limit", "budget", "deadline"]):
            return "add_constraints"
        elif any(keyword in input_lower for keyword in
                 ["upload", "document", "file", "requirements doc"]):
            return "upload_document"
        elif any(keyword in input_lower for keyword in
                 ["choose", "select", "recommend", "decision"]):
            return "analyze_choice"
        elif any(keyword in input_lower for keyword in
                 ["validate", "check", "verify", "test"]):
            return "validate_system"
        elif "recommendation" in input_lower:
            return "get_recommendations"
        else:
            return "chat"

    def _handle_build_system(self, request: UserRequest) -> SystemResponse:
        """Handle system building request"""
        # Use LLM to extract requirements from natural language
        llm_response = self.llm_layer.route_request(
            prompt=f"Extract system requirements from: {request.user_input}",
            domain=DomainType.ARCHITECTURAL,
            context=request.parameters
        )

        # Parse requirements (simplified - would use actual parsing)
        requirements = self._parse_system_requirements(request.user_input, request.parameters)

        # Generate experts
        experts, expert_analysis = self.expert_generator.generate_expert_team(requirements)
        self.experts.extend(experts)

        # Generate gates
        gates, gate_analysis = self.gate_generator.generate_gates_for_system(requirements)
        self.gates.extend(gates)

        # Add constraints
        if requirements.get("budget"):
            self.constraint_system.add_constraint_from_template(
                "budget", "total_cost", requirements["budget"],
                justification="System budget constraint"
            )

        # Use inquisitory engine for choice recommendations
        if "tech_stack" not in request.parameters:
            tech_question = "What technology stack should we use?"
            tech_options = self._get_default_tech_options()
            recommendation = self.inquisitory_engine.analyze_choice(
                question=tech_question,
                choice_type=ChoiceType.TECHNICAL,
                options=tech_options,
                context={"budget": requirements.get("budget", float('inf'))}
            )
            self.recommendations.append(recommendation)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "experts": [e.to_dict() for e in experts],
                "gates": [g.to_dict() for g in gates],
                "expert_analysis": expert_analysis,
                "gate_analysis": gate_analysis,
                "requirements": requirements,
                "recommendations": [r.to_dict() for r in self.recommendations]
            },
            message=f"System built successfully with {len(experts)} experts and {len(gates)} gates",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_generate_experts(self, request: UserRequest) -> SystemResponse:
        """Handle expert generation request"""
        # Use LLM to understand requirements
        llm_response = self.llm_layer.route_request(
            prompt=f"Extract expert requirements from: {request.user_input}",
            domain=DomainType.STRATEGIC,
            context=request.parameters
        )

        # Parse requirements
        requirements = request.parameters or {}

        # Generate team or single expert
        if "team" in request.user_input.lower() or "multiple" in request.user_input.lower():
            experts, analysis = self.expert_generator.generate_expert_team(
                requirements,
                budget=requirements.get("budget")
            )
            message = f"Generated expert team with {len(experts)} experts"
        else:
            expert = self.expert_generator.generate_expert(
                title=requirements.get("title", "Software Developer"),
                domain=requirements.get("domain", "software"),
                level=requirements.get("level", "mid"),
                specializations=requirements.get("specializations"),
                budget_constraint=requirements.get("budget")
            )
            experts = [expert]
            analysis = {"total_experts": 1, "total_cost_per_hour": expert.cost_per_hour}
            message = f"Generated expert: {expert.name}"

        self.experts.extend(experts)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "experts": [e.to_dict() for e in experts],
                "analysis": analysis
            },
            message=message,
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_create_gates(self, request: UserRequest) -> SystemResponse:
        """Handle gate creation request"""
        # Use LLM to understand gate requirements
        llm_response = self.llm_layer.route_request(
            prompt=f"Extract gate requirements from: {request.user_input}",
            domain=DomainType.REGULATORY,
            context=request.parameters
        )

        # Parse system requirements
        requirements = request.parameters or {}

        # Generate gates
        gates, analysis = self.gate_generator.generate_gates_for_system(requirements)
        self.gates.extend(gates)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "gates": [g.to_dict() for g in gates],
                "analysis": analysis
            },
            message=f"Generated {len(gates)} domain gates",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_add_constraints(self, request: UserRequest) -> SystemResponse:
        """Handle constraint addition request"""
        # Parse constraint details
        parameters = request.parameters or {}

        # Add constraint based on parameters
        if parameters.get("type") == "budget":
            constraint = self.constraint_system.add_constraint_from_template(
                "budget", "total_cost", parameters.get("value"),
                priority=parameters.get("priority", 8),
                justification=parameters.get("justification", "Budget constraint")
            )
        elif parameters.get("type") == "performance":
            constraint = self.constraint_system.add_constraint_from_template(
                "performance", "response_time", parameters.get("value"),
                priority=parameters.get("priority", 7),
                justification=parameters.get("justification", "Performance requirement")
            )
        else:
            # Generic constraint
            constraint = self.constraint_system.add_constraint(
                name=parameters.get("name", "Custom Constraint"),
                constraint_type=ConstraintType(parameters.get("type", "business")),
                parameter=parameters.get("parameter", "value"),
                operator=parameters.get("operator", "<="),
                threshold_value=parameters.get("value"),
                severity=parameters.get("severity", "medium"),
                description=parameters.get("description", ""),
                priority=parameters.get("priority", 5)
            )

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "constraint": constraint.to_dict()
            },
            message=f"Added constraint: {constraint.name}",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_upload_document(self, request: UserRequest) -> SystemResponse:
        """Handle document upload request"""
        parameters = request.parameters

        # Process document
        metadata = self.document_processor.upload_document(
            name=parameters.get("filename", "document.txt"),
            file_type=parameters.get("file_type", "txt"),
            content=parameters.get("content", ""),
            document_type=parameters.get("document_type")
        )

        # Get summary
        summary = self.document_processor.get_document_summary(metadata.document_id)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "metadata": metadata.to_dict(),
                "summary": summary
            },
            message=f"Document processed: {metadata.name}",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_analyze_choice(self, request: UserRequest) -> SystemResponse:
        """Handle choice analysis request"""
        # Use LLM to understand the choice
        llm_response = self.llm_layer.route_request(
            prompt=f"Analyze this choice request: {request.user_input}",
            domain=DomainType.STRATEGIC,
            context=request.parameters
        )

        # Get options from parameters or generate defaults
        options = request.parameters.get("options", [])
        if not options:
            options = self._get_default_tech_options()

        # Analyze choice
        recommendation = self.inquisitory_engine.analyze_choice(
            question=request.user_input,
            choice_type=ChoiceType(request.parameters.get("type", "technical")),
            options=options,
            context=request.parameters.get("context", {})
        )

        self.recommendations.append(recommendation)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "recommendation": recommendation.to_dict()
            },
            message=f"Choice analysis complete. Recommended: {recommendation.recommended_option}",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_validate_system(self, request: UserRequest) -> SystemResponse:
        """Handle system validation request"""
        # Validate constraints
        system_state = request.parameters.get("system_state", {})
        results, warnings = self.constraint_system.validate_constraints(system_state)

        # Validate gates
        gate_results = []
        for gate in self.gates:
            result = self.gate_generator.execute_gate(gate, system_state)
            gate_results.append(result)

        # Get LLM validation for math/physics
        if request.parameters.get("validate_math_physics"):
            llm_response = self.llm_layer.route_request(
                prompt=f"Validate system calculations: {request.user_input}",
                domain=DomainType.MATHEMATICAL,
                context=request.parameters
            )

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "constraint_validation": results,
                "gate_validation": gate_results,
                "llm_validation": llm_response.to_dict() if 'llm_response' in locals() else None
            },
            message="System validation complete",
            warnings=warnings,
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_get_recommendations(self, request: UserRequest) -> SystemResponse:
        """Handle get recommendations request"""
        # Generate report
        report = self.inquisitory_engine.generate_choice_report(self.recommendations)

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "report": report,
                "recommendations": [r.to_dict() for r in self.recommendations]
            },
            message=f"Retrieved {len(self.recommendations)} recommendations",
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_chat(self, request: UserRequest) -> SystemResponse:
        """Handle general chat request"""
        # Use LLM to generate response
        llm_response = self.llm_layer.route_request(
            prompt=request.user_input,
            domain=DomainType.GENERAL,
            context=request.parameters
        )

        return SystemResponse(
            request_id=request.request_id,
            success=True,
            data={
                "llm_response": llm_response.to_dict()
            },
            message=llm_response.response,
            warnings=[],
            triggers=[],
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _handle_general_query(self, request: UserRequest) -> SystemResponse:
        """Handle general query"""
        return self._handle_chat(request)

    def _parse_system_requirements(self, user_input: str, parameters: Dict) -> Dict:
        """Parse system requirements from user input (simplified)"""
        requirements = parameters.copy()

        input_lower = user_input.lower()

        # Extract complexity
        if "simple" in input_lower:
            requirements["complexity"] = "simple"
        elif "complex" in input_lower:
            requirements["complexity"] = "complex"
        else:
            requirements["complexity"] = "medium"

        # Extract domain
        if "software" in input_lower or "app" in input_lower:
            requirements["domain"] = "software"
        elif "infrastructure" in input_lower or "cloud" in input_lower:
            requirements["domain"] = "infrastructure"
        elif "data" in input_lower:
            requirements["domain"] = "data"
        else:
            requirements["domain"] = "software"

        # Extract security focus
        requirements["security_focus"] = any(keyword in input_lower for keyword in
                                              ["security", "secure", "compliance"])

        return requirements

    def _get_default_tech_options(self) -> List[Dict]:
        """Get default technology stack options"""
        return [
            {
                "name": "React + Node.js",
                "description": "Full JavaScript stack",
                "pros": ["Large ecosystem", "Good performance", "Consistent language"],
                "cons": ["Async complexity"],
                "estimated_cost": 6000,
                "estimated_time": 150,
                "risk_level": "medium",
                "success_probability": 0.88
            },
            {
                "name": "React + Django",
                "description": "React frontend with Django backend",
                "pros": ["Simple setup", "Good documentation"],
                "cons": ["Limited scalability"],
                "estimated_cost": 5000,
                "estimated_time": 160,
                "risk_level": "low",
                "success_probability": 0.85
            }
        ]

    def get_system_state_dict(self) -> Dict[str, Any]:
        """Get current system state as a dictionary"""
        return self.get_system_state().to_dict()

    def generate_system_report(self) -> Dict[str, Any]:
        """Generate comprehensive system report"""
        report = {
            'system_id': self.system_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_state': self.get_system_state().__dict__,
            'metrics': {
                'total_requests': self.request_count,
                'total_experts': len(self.experts),
                'total_gates': len(self.gates),
                'total_constraints': len(self.constraint_system.constraints) if hasattr(self.constraint_system, 'constraints') else 0
            }
        }

        # LLM report
        if self.llm_layer:
            report['llm_report'] = {
                'total_requests': self.llm_layer.request_count if hasattr(self.llm_layer, 'request_count') else 0,
                'provider_status': 'available'
            }

        # Security section
        if self.security_enabled and self.security_adapter:
            security_summary = self.security_adapter.get_security_summary()
            report['security'] = {
                'enabled': True,
                'summary': security_summary,
                'active_gates': self.security_adapter.get_active_security_gates(),
                'recent_anomalies': self.security_adapter.get_recent_anomalies(10)
            }
        else:
            report['security'] = {'enabled': False}

        # Module compiler section
        if self.module_compiler_enabled and self.module_compiler:
            module_stats = self.module_compiler.get_module_statistics()
            report['module_compiler'] = {
                'enabled': True,
                'statistics': module_stats,
                'total_modules': len(self.module_compiler.get_all_compiled_modules())
            }
        else:
            report['module_compiler'] = {'enabled': False}

        return report

    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get security summary from security adapter.

        Returns:
            Dictionary with security metrics and state
        """
        if not self.security_enabled or not self.security_adapter:
            return {
                "enabled": False,
                "message": "Security plane not available"
            }

        return self.security_adapter.get_security_summary()

    def get_security_gates(self) -> List[Dict[str, Any]]:
        """
        Get list of active security gates.

        Returns:
            List of security gate dictionaries
        """
        if not self.security_enabled or not self.security_adapter:
            return []

        return self.security_adapter.get_active_security_gates()

    def compute_trust_score(self, entity_id: str, base_score: float = 0.5, factors: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Compute trust score for an entity.

        Args:
            entity_id: Unique identifier for the entity
            base_score: Base trust score (0.0 to 1.0)
            factors: Dictionary of trust factors with weights

        Returns:
            Dictionary with trust score and level
        """
        if not self.security_enabled or not self.security_adapter:
            return {
                "entity_id": entity_id,
                "trust_score": base_score,
                "message": "Security plane not available"
            }

        return self.security_adapter.compute_trust_score(entity_id, base_score, factors)

    def get_trust_score(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trust score for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Trust score dictionary or None
        """
        if not self.security_enabled or not self.security_adapter:
            return None

        return self.security_adapter.get_trust_score(entity_id)

    def get_security_anomalies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent security anomalies.

        Args:
            limit: Maximum number to return

        Returns:
            List of anomaly dictionaries
        """
        if not self.security_enabled or not self.security_adapter:
            return []

        return self.security_adapter.get_recent_anomalies(limit)

    def check_security_gate(self, gate_id: str, trust_score: float) -> Tuple[bool, str]:
        """
        Check if a security gate allows passage.

        Args:
            gate_id: ID of the gate to check
            trust_score: Trust score of the entity

        Returns:
            Tuple of (allowed, reason)
        """
        if not self.security_enabled or not self.security_adapter:
            return True, "Security plane not enabled"

        return self.security_adapter.check_security_gate(gate_id, trust_score)

    # ========== Module Compiler Methods ==========

    def compile_module(self, source_path: str, requested_capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compile a Python module into a module specification.

        Args:
            source_path: Path to Python module file or directory
            requested_capabilities: Specific capabilities to focus on

        Returns:
            Dictionary with module specification
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return {
                "success": False,
                "error": "Module compiler not enabled",
                "source_path": source_path
            }

        return self.module_compiler.compile_module(source_path, requested_capabilities)

    def compile_directory(self, directory_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Compile all modules in a directory.

        Args:
            directory_path: Path to directory
            recursive: Whether to search subdirectories

        Returns:
            Dictionary with compilation results
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return {
                "success": False,
                "error": "Module compiler not enabled",
                "directory_path": directory_path
            }

        return self.module_compiler.compile_directory(directory_path, recursive)

    def get_compiled_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a compiled module by ID.

        Args:
            module_id: Module identifier

        Returns:
            Module specification or None
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return None

        return self.module_compiler.get_compiled_module(module_id)

    def get_all_compiled_modules(self) -> List[Dict[str, Any]]:
        """
        Get all compiled modules.

        Returns:
            List of module specifications
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return []

        return self.module_compiler.get_all_compiled_modules()

    def search_modules(self,
                      capability_name: Optional[str] = None,
                      determinism: Optional[str] = None,
                      min_determinism: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search compiled modules by criteria.

        Args:
            capability_name: Filter by capability name
            determinism: Filter by exact determinism level
            min_determinism: Filter by minimum determinism level

        Returns:
            List of matching modules
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return []

        return self.module_compiler.search_modules(
            capability_name=capability_name,
            determinism=determinism,
            min_determinism=min_determinism
        )

    def get_module_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about compiled modules.

        Returns:
            Dictionary with statistics
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return {
                "enabled": False,
                "message": "Module compiler not available"
            }

        return self.module_compiler.get_module_statistics()

    def get_module_analysis_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get module analysis history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of analysis entries
        """
        if not self.module_compiler_enabled or not self.module_compiler:
            return []

        return self.module_compiler.get_analysis_history(limit)

    def get_system_state(self) -> SystemState:
        """Get current system state"""
        return SystemState(
            system_id=self.system_id,
            initialized=True,
            experts=self.experts,
            gates=self.gates,
            constraints=self.constraint_system.constraints if hasattr(self.constraint_system, 'constraints') else {},
            requirements=self.requirements,
            recommendations=self.recommendations,
            last_updated=datetime.now(timezone.utc).isoformat(),
            metrics={
                "total_requests": self.request_count,
                "total_experts": len(self.experts),
                "total_gates": len(self.gates),
                "total_constraints": len(self.constraint_system.constraints) if hasattr(self.constraint_system, 'constraints') else 0
            }
        )

    # ========== Neuro-Symbolic Methods ==========

    def perform_inference(self,
                        query: str,
                        reasoning_mode: str = "hybrid",
                        context: Optional[Dict] = None,
                        constraints: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform neural-symbolic inference.

        Args:
            query: Query to reason about
            reasoning_mode: Mode of reasoning (hybrid, neural, symbolic)
            context: Optional context for inference
            constraints: Optional list of constraints to apply

        Returns:
            Dictionary with inference results
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return {
                "success": False,
                "error": "Neuro-symbolic adapter not enabled",
                "query": query
            }

        return self.neuro_symbolic.perform_inference(
            query=query,
            reasoning_mode=reasoning_mode,
            context=context,
            constraints=constraints
        )

    def validate_constraints(self,
                           statement: str,
                           constraints: List[str],
                           context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate constraints against a statement.

        Args:
            statement: Statement to validate
            constraints: List of constraints to validate
            context: Optional context for validation

        Returns:
            Dictionary with validation results
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return {
                "success": False,
                "error": "Neuro-symbolic adapter not enabled",
                "statement": statement
            }

        return self.neuro_symbolic.validate_constraints(
            statement=statement,
            constraints=constraints,
            context=context
        )

    def perform_hybrid_reasoning(self,
                                problem: str,
                                neural_input: str,
                                symbolic_constraints: List[str],
                                context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform hybrid neural-symbolic reasoning.

        Args:
            problem: Problem to solve
            neural_input: Input for neural processing
            symbolic_constraints: Symbolic constraints
            context: Optional context

        Returns:
            Dictionary with reasoning results
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return {
                "success": False,
                "error": "Neuro-symbolic adapter not enabled",
                "problem": problem
            }

        return self.neuro_symbolic.perform_hybrid_reasoning(
            problem=problem,
            neural_input=neural_input,
            symbolic_constraints=symbolic_constraints,
            context=context
        )

    def create_knowledge_graph(self,
                             entities: List[str],
                             relationships: List[Dict[str, Any]],
                             constraints: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a knowledge graph from entities and relationships.

        Args:
            entities: List of entity names
            relationships: List of relationship dictionaries
            constraints: Optional constraints for graph creation

        Returns:
            Dictionary with knowledge graph
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return {
                "success": False,
                "error": "Neuro-symbolic adapter not enabled"
            }

        return self.neuro_symbolic.create_knowledge_graph(
            entities=entities,
            relationships=relationships,
            constraints=constraints
        )

    def get_reasoning_statistics(self) -> Dict[str, Any]:
        """
        Get reasoning statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return {
                "success": False,
                "error": "Neuro-symbolic adapter not enabled"
            }

        return self.neuro_symbolic.get_reasoning_statistics()

    def get_inference_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get inference history.

        Args:
            limit: Maximum number of entries

        Returns:
            List of inference history entries
        """
        if not self.neuro_symbolic_enabled or not self.neuro_symbolic:
            return []

        return self.neuro_symbolic.get_inference_history(limit)

    # ========== Telemetry Methods ==========

    def collect_metric(self,
                      metric_type: str,
                      metric_name: str,
                      value: float,
                      labels: Optional[Dict] = None,
                      timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect a single metric.

        Args:
            metric_type: Type of metric (performance, error, warning, system_event, user_action)
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels/dimensions for the metric
            timestamp: Optional timestamp (ISO format)

        Returns:
            Dictionary with collection result
        """
        if not self.telemetry_enabled or not self.telemetry:
            return {
                "success": False,
                "error": "Telemetry adapter not enabled"
            }

        return self.telemetry.collect_metric(
            metric_type=metric_type,
            metric_name=metric_name,
            value=value,
            labels=labels,
            timestamp=timestamp
        )

    def get_metrics(self,
                   metric_type: Optional[str] = None,
                   metric_name: Optional[str] = None,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None,
                   limit: int = 100) -> Dict[str, Any]:
        """
        Get metrics with optional filtering.

        Args:
            metric_type: Filter by metric type (None for all)
            metric_name: Filter by metric name (None for all)
            start_time: Filter by start time (ISO format)
            end_time: Filter by end time (ISO format)
            limit: Maximum number of metrics to return

        Returns:
            Dictionary with metrics
        """
        if not self.telemetry_enabled or not self.telemetry:
            return {
                "success": False,
                "error": "Telemetry adapter not enabled"
            }

        return self.telemetry.get_metrics(
            metric_type=metric_type,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalies in metrics.

        Returns:
            List of detected anomalies
        """
        if not self.telemetry_enabled or not self.telemetry:
            return []

        return self.telemetry.detect_anomalies()

    def discover_patterns(self) -> List[Dict[str, Any]]:
        """
        Discover patterns in metric data.

        Returns:
            List of discovered patterns
        """
        if not self.telemetry_enabled or not self.telemetry:
            return []

        return self.telemetry.discover_patterns()

    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate actionable recommendations from telemetry data.

        Returns:
            List of recommendations
        """
        if not self.telemetry_enabled or not self.telemetry:
            return []

        return self.telemetry.generate_recommendations()

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """
        Get summary of all telemetry data.

        Returns:
            Dictionary with telemetry summary
        """
        if not self.telemetry_enabled or not self.telemetry:
            return {
                "enabled": False,
                "error": "Telemetry adapter not enabled"
            }

        return self.telemetry.get_telemetry_summary()

    def update_telemetry_config(self, config: Dict) -> Dict[str, Any]:
        """
        Update telemetry configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Dictionary with update result
        """
        if not self.telemetry_enabled or not self.telemetry:
            return {
                "success": False,
                "error": "Telemetry adapter not enabled"
            }

        return self.telemetry.update_config(config)

    def clear_metrics(self, metric_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear metrics from storage.

        Args:
            metric_type: Type to clear (None for all)

        Returns:
            Dictionary with clear result
        """
        if not self.telemetry_enabled or not self.telemetry:
            return {
                "success": False,
                "error": "Telemetry adapter not enabled"
            }

        return self.telemetry.clear_metrics(metric_type)

    # ========== Librarian Methods ==========

    def ask_librarian_question(self, question: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Ask the system librarian a question.

        Args:
            question: The question to ask
            topic: Optional topic for the question

        Returns:
            Dictionary with answer and metadata
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled",
                "question": question
            }

        return self.librarian_adapter.ask_question(question, topic)

    def get_librarian_topics(self) -> Dict[str, Any]:
        """
        Get available topics from librarian.

        Returns:
            Dictionary with topics
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled"
            }

        return self.librarian_adapter.get_topics()

    def get_system_health_status(self) -> Dict[str, Any]:
        """
        Get overall system health status.

        Returns:
            Dictionary with health status of all components
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled"
            }

        return self.librarian_adapter.get_health_status()

    def get_troubleshooting_guide(self, issue: str) -> Dict[str, Any]:
        """
        Get troubleshooting guidance for an issue.

        Args:
            issue: Description of the issue

        Returns:
            Dictionary with troubleshooting steps
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled",
                "issue": issue
            }

        return self.librarian_adapter.get_troubleshooting_guide(issue)

    def get_librarian_documentation(self, topic: str) -> Dict[str, Any]:
        """
        Get documentation on a topic.

        Args:
            topic: Topic to get documentation for

        Returns:
            Dictionary with documentation content
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled",
                "topic": topic
            }

        return self.librarian_adapter.get_documentation(topic)

    def search_librarian_knowledge_base(self, query: str) -> Dict[str, Any]:
        """
        Search the knowledge base.

        Args:
            query: Search query

        Returns:
            Dictionary with search results
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled",
                "query": query
            }

        return self.librarian_adapter.search_knowledge_base(query)

    def get_librarian_statistics(self) -> Dict[str, Any]:
        """
        Get librarian statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.librarian_adapter_enabled or not self.librarian_adapter:
            return {
                "success": False,
                "error": "Librarian adapter not enabled"
            }

        return self.librarian_adapter.get_librarian_statistics()

    def evaluate_dynamic_assist_mode(
        self,
        recall_confidence: float = 0.5,
        impact_weight: float = 0.5,
        k_factor: float = 0.5,
        risk_level: float = 0.3,
        variation_frequency: float = 0.2,
        novelty_rate: float = 0.1,
    ) -> Dict[str, Any]:
        """Evaluate the dynamic assist mode via the ShadowKnostalgiaBridge.

        Calls ``shadow_knostalgia_bridge.compute_assist_mode()`` when available,
        falling back gracefully when the bridge is not loaded.

        Returns a dict with the computed autonomy parameters.
        """
        if not self.shadow_knostalgia_bridge_enabled or not self.shadow_knostalgia_bridge:
            return {"success": False, "error": "ShadowKnostalgiaBridge not enabled"}

        try:
            output = self.shadow_knostalgia_bridge.compute_assist_mode(
                recall_confidence=recall_confidence,
                impact_weight=impact_weight,
                risk_level=risk_level,
                variation_frequency=variation_frequency,
                novelty_rate=novelty_rate,
            )
            if output is None:
                logger.warning(
                    "SystemIntegrator.evaluate_dynamic_assist_mode: "
                    "compute_assist_mode returned None"
                )
                return {"success": False, "error": "compute_assist_mode returned None"}
            result: Dict[str, Any] = {"success": True}
            for attr in (
                "observe_only", "may_suggest", "may_execute", "requires_approval",
                "computed_epsilon", "computed_learning_rate", "computed_confidence_threshold",
            ):
                if hasattr(output, attr):
                    result[attr] = getattr(output, attr)
            return result
        except Exception as exc:
            logger.warning("SystemIntegrator.evaluate_dynamic_assist_mode failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def handle_team_discovery_message(self, message: str, business_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a natural-language message to discover team members and generate Rosettas.

        Flow:
          1. extract_team_members(message)
          2. generate_all_rosettas() for found members
          3. build_hitl_summary() for HITL presentation
          4. Return the summary dict (caller presents to human; on confirmation
             call on_confirmed() with the results stored in the return value).

        Returns a dict with keys:
          - success (bool)
          - members_found (int)
          - hitl_summary (str)
          - results (list) — the RosettaGenerationResult objects (opaque, pass back to on_confirmed)
          - error (str, only on failure)
        """
        if not self.onboarding_team_pipeline_enabled or not self.onboarding_team_pipeline:
            return {"success": False, "error": "OnboardingTeamPipeline not enabled"}

        ctx: Dict[str, Any] = business_context or {}
        try:
            discovery = self.onboarding_team_pipeline.extract_team_members(message)
            if not discovery.members:
                return {
                    "success": True,
                    "members_found": 0,
                    "hitl_summary": "No team members found in the message.",
                    "results": [],
                }
            results = self.onboarding_team_pipeline.generate_all_rosettas(discovery, ctx)
            summary = self.onboarding_team_pipeline.build_hitl_summary(results)
            return {
                "success": True,
                "members_found": len(discovery.members),
                "hitl_summary": summary,
                "results": results,
            }
        except Exception as exc:
            logger.warning("SystemIntegrator.handle_team_discovery_message failed: %s", exc)
            return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    # Test system integrator
    integrator = SystemIntegrator()

    # Test 1: Build system
    logger.info("=== Test 1: Build System ===")
    response = integrator.process_user_request(
        "Build a complex web application with security focus",
        parameters={
            "budget": 15000,
            "regulatory_requirements": ["gdpr"],
            "architectural_requirements": ["microservices"]
        }
    )
    logger.info(f"Success: {response.success}")
    logger.info(f"Message: {response.message}")
    logger.info(f"Experts: {len(response.data.get('experts', []))}")
    logger.info(f"Gates: {len(response.data.get('gates', []))}")

    # Test 2: Generate experts
    logger.info("\n=== Test 2: Generate Experts ===")
    response = integrator.process_user_request(
        "I need a team of experts for my software project",
        parameters={
            "type": "generate_experts",
            "domain": "software",
            "complexity": "complex",
            "budget": 8000
        }
    )
    logger.info(f"Success: {response.success}")
    logger.info(f"Message: {response.message}")

    # Test 3: Create gates
    logger.info("\n=== Test 3: Create Gates ===")
    response = integrator.process_user_request(
        "Create safety gates for my system",
        parameters={
            "type": "create_gates",
            "domain": "software",
            "security_focus": True,
            "regulatory_requirements": ["gdpr", "hipaa"]
        }
    )
    logger.info(f"Success: {response.success}")
    logger.info(f"Message: {response.message}")

    # Test 4: Analyze choice
    logger.info("\n=== Test 4: Analyze Choice ===")
    response = integrator.process_user_request(
        "Which technology stack should I use?",
        parameters={
            "type": "analyze_choice",
            "type_of_choice": "technical",
            "context": {"budget": 10000, "timeline": 180}
        }
    )
    logger.info(f"Success: {response.success}")
    logger.info(f"Message: {response.message}")

    # Test 5: Get system state
    logger.info("\n=== Test 5: System State ===")
    state = integrator.get_system_state()
    logger.info(f"System ID: {state.system_id}")
    logger.info(f"Experts: {len(state.experts)}")
    logger.info(f"Gates: {len(state.gates)}")
    logger.info(f"Constraints: {len(state.constraints)}")
    logger.info(f"Total Requests: {state.metrics['total_requests']}")

    # Test 6: Generate report
    logger.info("\n=== Test 6: System Report ===")
    report = integrator.generate_system_report()
    logger.info(f"System initialized: {report['system_state']['initialized']}")
    logger.info(f"LLM requests: {report['llm_report']['total_requests']}")
