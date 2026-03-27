"""
Bot Inventory Library Module
Manages bot/agent spawning, despawning, and lifecycle
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot_inventory_library")


class BotStatus(Enum):
    """Bot lifecycle status"""
    SPAWNING = "spawning"
    ACTIVE = "active"
    PAUSED = "paused"
    IDLE = "idle"
    DESPAWNING = "despawning"
    TERMINATED = "terminated"


class BotRole(Enum):
    """Bot role types"""
    EXPERT = "expert"
    ASSISTANT = "assistant"
    VALIDATOR = "validator"
    MONITOR = "monitor"
    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"
    ANALYZER = "analyzer"
    AUDITOR = "auditor"


@dataclass
class BotCapability:
    """Bot capability definition"""
    capability_id: str
    name: str
    description: str
    function_name: str
    parameters: Dict[str, Any]
    enabled: bool = True
    version: str = "1.0"

    def to_dict(self) -> Dict:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "function_name": self.function_name,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "version": self.version
        }


@dataclass
class BotAgent:
    """Bot agent instance"""
    agent_id: str
    name: str
    role: BotRole
    status: BotStatus
    capabilities: List[BotCapability]
    expert_id: Optional[str] = None  # Links to DynamicExpertGenerator
    assigned_tasks: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "expert_id": self.expert_id,
            "assigned_tasks": self.assigned_tasks,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "last_active": self.last_active
        }


class BotInventoryLibrary:
    """
    Complete bot inventory library
    Manages spawning, despawning, and lifecycle of system agents
    """

    def __init__(self, heartbeat_monitor=None):
        self.bots: Dict[str, BotAgent] = {}
        self.bot_templates: Dict[str, Dict] = self._load_bot_templates()
        self.spawn_count = 0
        self.despawn_count = 0
        self._heartbeat_monitor = heartbeat_monitor

        # Register all system capabilities
        self.capability_registry = self._initialize_capability_registry()

    def _load_bot_templates(self) -> Dict[str, Dict]:
        """Load bot templates for common roles"""
        return {
            "expert_bot": {
                "role": BotRole.EXPERT,
                "capabilities": [
                    "analyze_requirements",
                    "generate_solutions",
                    "validate_design",
                    "provide_recommendations"
                ]
            },
            "validator_bot": {
                "role": BotRole.VALIDATOR,
                "capabilities": [
                    "validate_constraints",
                    "check_gates",
                    "verify_compliance",
                    "audit_system"
                ]
            },
            "monitor_bot": {
                "role": BotRole.MONITOR,
                "capabilities": [
                    "monitor_performance",
                    "track_metrics",
                    "alert_anomalies",
                    "generate_reports"
                ]
            },
            "orchestrator_bot": {
                "role": BotRole.ORCHESTRATOR,
                "capabilities": [
                    "coordinate_tasks",
                    "manage_workflow",
                    "optimize_resources",
                    "handle_conflicts"
                ]
            },
            "auditor_bot": {
                "role": BotRole.AUDITOR,
                "capabilities": [
                    "audit_productivity",
                    "detect_gaps",
                    "generate_contracts",
                    "monitor_compliance"
                ]
            }
        }

    def _initialize_capability_registry(self) -> Dict[str, Dict]:
        """Initialize registry of all system capabilities"""
        return {
            # Expert capabilities
            "analyze_requirements": {
                "name": "Analyze Requirements",
                "description": "Analyze system requirements and extract specifications",
                "function": "analyze_requirements",
                "parameters": {
                    "requirements": "str",
                    "context": "dict",
                    "domain": "str"
                },
                "module": "system_integrator"
            },
            "generate_solutions": {
                "name": "Generate Solutions",
                "description": "Generate technical solutions for requirements",
                "function": "generate_solutions",
                "parameters": {
                    "requirements": "dict",
                    "constraints": "list"
                },
                "module": "system_integrator"
            },
            "validate_design": {
                "name": "Validate Design",
                "description": "Validate system design against best practices",
                "function": "validate_design",
                "parameters": {
                    "design": "dict",
                    "standards": "list"
                },
                "module": "gate_generator"
            },
            "provide_recommendations": {
                "name": "Provide Recommendations",
                "description": "Provide architectural and technical recommendations",
                "function": "provide_recommendations",
                "parameters": {
                    "context": "dict",
                    "options": "list"
                },
                "module": "inquisitory_engine"
            },

            # Validator capabilities
            "validate_constraints": {
                "name": "Validate Constraints",
                "description": "Validate system against constraints",
                "function": "validate_constraints",
                "parameters": {
                    "system_state": "dict"
                },
                "module": "constraint_system"
            },
            "check_gates": {
                "name": "Check Gates",
                "description": "Check if system passes safety gates",
                "function": "check_gates",
                "parameters": {
                    "gates": "list",
                    "system_state": "dict"
                },
                "module": "gate_generator"
            },
            "verify_compliance": {
                "name": "Verify Compliance",
                "description": "Verify regulatory compliance",
                "function": "verify_compliance",
                "parameters": {
                    "compliance_type": "str",
                    "system_state": "dict"
                },
                "module": "llm_integration_layer"
            },
            "audit_system": {
                "name": "Audit System",
                "description": "Perform comprehensive system audit",
                "function": "audit_system",
                "parameters": {
                    "audit_type": "str",
                    "scope": "list"
                },
                "module": "contractual_audit"
            },

            # Monitor capabilities
            "monitor_performance": {
                "name": "Monitor Performance",
                "description": "Monitor system performance metrics",
                "function": "monitor_performance",
                "parameters": {
                    "metrics": "list",
                    "thresholds": "dict"
                },
                "module": "system_integrator"
            },
            "track_metrics": {
                "name": "Track Metrics",
                "description": "Track and aggregate system metrics",
                "function": "track_metrics",
                "parameters": {
                    "metric_type": "str",
                    "data": "any"
                },
                "module": "system_integrator"
            },
            "alert_anomalies": {
                "name": "Alert Anomalies",
                "description": "Detect and alert on system anomalies",
                "function": "alert_anomalies",
                "parameters": {
                    "data": "any",
                    "threshold": "float"
                },
                "module": "system_integrator"
            },
            "generate_reports": {
                "name": "Generate Reports",
                "description": "Generate system reports",
                "function": "generate_reports",
                "parameters": {
                    "report_type": "str",
                    "format": "str"
                },
                "module": "system_integrator"
            },

            # Orchestrator capabilities
            "coordinate_tasks": {
                "name": "Coordinate Tasks",
                "description": "Coordinate tasks across multiple bots",
                "function": "coordinate_tasks",
                "parameters": {
                    "tasks": "list",
                    "bots": "list"
                },
                "module": "system_integrator"
            },
            "manage_workflow": {
                "name": "Manage Workflow",
                "description": "Manage workflow and task execution",
                "function": "manage_workflow",
                "parameters": {
                    "workflow": "dict",
                    "context": "dict"
                },
                "module": "system_integrator"
            },
            "optimize_resources": {
                "name": "Optimize Resources",
                "description": "Optimize resource allocation",
                "function": "optimize_resources",
                "parameters": {
                    "resources": "dict",
                    "constraints": "list"
                },
                "module": "system_integrator"
            },
            "handle_conflicts": {
                "name": "Handle Conflicts",
                "description": "Resolve conflicts between bots or tasks",
                "function": "handle_conflicts",
                "parameters": {
                    "conflicts": "list"
                },
                "module": "system_integrator"
            },

            # Auditor capabilities
            "audit_productivity": {
                "name": "Audit Productivity",
                "description": "Audit system productivity and flow",
                "function": "audit_productivity",
                "parameters": {
                    "timeframe": "str",
                    "metrics": "list"
                },
                "module": "contractual_audit"
            },
            "detect_gaps": {
                "name": "Detect Gaps",
                "description": "Detect productivity flow gaps",
                "function": "detect_gaps",
                "parameters": {
                    "system_state": "dict",
                    "requirements": "list"
                },
                "module": "contractual_audit"
            },
            "generate_contracts": {
                "name": "Generate Contracts",
                "description": "Generate contractual agreements between agents",
                "function": "generate_contracts",
                "parameters": {
                    "agents": "list",
                    "agreement_type": "str"
                },
                "module": "contractual_audit"
            },
            "monitor_compliance": {
                "name": "Monitor Compliance",
                "description": "Monitor ongoing compliance status",
                "function": "monitor_compliance",
                "parameters": {
                    "compliance_types": "list"
                },
                "module": "constraint_system"
            }
        }

    def spawn_bot(
        self,
        name: str,
        role: str,
        capabilities: Optional[List[str]] = None,
        expert_id: Optional[str] = None
    ) -> BotAgent:
        """
        Spawn a new bot agent

        Args:
            name: Bot name
            role: Bot role (expert, validator, monitor, etc.)
            capabilities: List of capability names
            expert_id: Link to expert from DynamicExpertGenerator

        Returns:
            BotAgent object
        """
        self.spawn_count += 1
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"

        # Get role enum
        role_enum = BotRole(role.lower())

        # Get capabilities
        bot_capabilities = []
        if capabilities:
            for cap_name in capabilities:
                if cap_name in self.capability_registry:
                    cap_data = self.capability_registry[cap_name]
                    capability = BotCapability(
                        capability_id=f"cap_{uuid.uuid4().hex[:8]}",
                        name=cap_data["name"],
                        description=cap_data["description"],
                        function_name=cap_data["function"],
                        parameters=cap_data["parameters"],
                        enabled=True
                    )
                    bot_capabilities.append(capability)
        else:
            # Use template capabilities
            template = self.bot_templates.get(f"{role}_bot", {})
            template_caps = template.get("capabilities", [])
            for cap_name in template_caps:
                if cap_name in self.capability_registry:
                    cap_data = self.capability_registry[cap_name]
                    capability = BotCapability(
                        capability_id=f"cap_{uuid.uuid4().hex[:8]}",
                        name=cap_data["name"],
                        description=cap_data["description"],
                        function_name=cap_data["function"],
                        parameters=cap_data["parameters"],
                        enabled=True
                    )
                    bot_capabilities.append(capability)

        # Create bot agent
        bot = BotAgent(
            agent_id=agent_id,
            name=name,
            role=role_enum,
            status=BotStatus.SPAWNING,
            capabilities=bot_capabilities,
            expert_id=expert_id
        )

        # Mark as active
        bot.status = BotStatus.ACTIVE

        self.bots[agent_id] = bot

        # Auto-register with heartbeat monitor if wired
        if self._heartbeat_monitor is not None:
            try:
                self._heartbeat_monitor.register_bot(agent_id)
            except Exception as exc:
                logger.warning(
                    "spawn_bot: failed to register bot %s with heartbeat monitor: %s",
                    agent_id,
                    exc,
                )

        return bot

    def despawn_bot(self, agent_id: str) -> bool:
        """
        Despawn a bot agent

        Args:
            agent_id: ID of bot to despawn

        Returns:
            True if despawned, False if not found
        """
        if agent_id not in self.bots:
            return False

        bot = self.bots[agent_id]
        bot.status = BotStatus.DESPAWNING

        # Clean up assigned tasks
        bot.assigned_tasks.clear()

        # Mark as terminated
        bot.status = BotStatus.TERMINATED

        # Remove from active bots
        del self.bots[agent_id]

        # Deregister from heartbeat monitor if wired
        if self._heartbeat_monitor is not None:
            try:
                self._heartbeat_monitor.deregister_bot(agent_id)
            except Exception as exc:
                logger.warning(
                    "despawn_bot: failed to deregister bot %s from heartbeat monitor: %s",
                    agent_id,
                    exc,
                )

        self.despawn_count += 1
        return True

    def get_bot(self, agent_id: str) -> Optional[BotAgent]:
        """Get bot by ID"""
        return self.bots.get(agent_id)

    def get_bots_by_role(self, role: str) -> List[BotAgent]:
        """Get all bots of a specific role"""
        role_enum = BotRole(role.lower())
        return [bot for bot in self.bots.values() if bot.role == role_enum]

    def get_bots_by_status(self, status: str) -> List[BotAgent]:
        """Get all bots with specific status"""
        status_enum = BotStatus(status.lower())
        return [bot for bot in self.bots.values() if bot.status == status_enum]

    def get_active_bots(self) -> List[BotAgent]:
        """Get all active bots"""
        return self.get_bots_by_status("active")

    def assign_task(self, agent_id: str, task_id: str) -> bool:
        """Assign a task to a bot"""
        bot = self.bots.get(agent_id)
        if not bot:
            return False

        bot.assigned_tasks.append(task_id)
        bot.last_active = datetime.now(timezone.utc).isoformat()
        return True

    def complete_task(self, agent_id: str, task_id: str) -> bool:
        """Mark a task as complete for a bot"""
        bot = self.bots.get(agent_id)
        if not bot:
            return False

        if task_id in bot.assigned_tasks:
            bot.assigned_tasks.remove(task_id)
            bot.last_active = datetime.now(timezone.utc).isoformat()
            return True

        return False

    def update_bot_metrics(self, agent_id: str, metrics: Dict[str, Any]):
        """Update bot metrics"""
        bot = self.bots.get(agent_id)
        if bot:
            bot.metrics.update(metrics)
            bot.last_active = datetime.now(timezone.utc).isoformat()

    def get_capability_function(self, capability_name: str) -> Optional[Dict]:
        """Get capability function details"""
        return self.capability_registry.get(capability_name)

    def get_all_capabilities(self) -> List[Dict]:
        """Get all available capabilities"""
        return list(self.capability_registry.values())

    def get_bot_inventory(self) -> Dict[str, Any]:
        """Get complete bot inventory"""
        by_role = {}
        for bot in self.bots.values():
            role = bot.role.value
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(bot.to_dict())

        by_status = {}
        for bot in self.bots.values():
            status = bot.status.value
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(bot.to_dict())

        return {
            "total_bots": len(self.bots),
            "spawned_count": self.spawn_count,
            "despawned_count": self.despawn_count,
            "by_role": by_role,
            "by_status": by_status,
            "all_bots": [bot.to_dict() for bot in self.bots.values()],
            "available_capabilities": self.get_all_capabilities()
        }

    def get_available_bots(self) -> list:
        """Convenience method: get list of available/active bots"""
        return [bot.to_dict() for bot in self.bots.values()]

    def get_bot_capabilities(self, bot_id: str = None) -> list:
        """Convenience method: get capabilities for a bot or all capabilities"""
        if bot_id and bot_id in self.bots:
            return list(self.bots[bot_id].capabilities)
        return self.get_all_capabilities()

    def register_bot(self, bot_name: str, capabilities: list = None, role: str = "assistant") -> Dict[str, Any]:
        """Convenience method: register (spawn) a bot with given capabilities"""
        # Map common role names to valid BotRole values
        role_map = {"worker": "assistant", "helper": "assistant", "agent": "specialist"}
        mapped_role = role_map.get(role.lower(), role.lower())
        try:
            bot = self.spawn_bot(name=bot_name, role=mapped_role, capabilities=capabilities or [])
            return {"success": True, "bot": bot.to_dict() if hasattr(bot, 'to_dict') else {"agent_id": str(bot)}}
        except ValueError:
            # If role is still invalid, use default
            bot = self.spawn_bot(name=bot_name, role="assistant", capabilities=capabilities or [])
            return {"success": True, "bot": bot.to_dict() if hasattr(bot, 'to_dict') else {"agent_id": str(bot)}}

    def search_bots(self, capability: str = None, role: str = None) -> list:
        """Convenience method: search bots by capability or role"""
        results = list(self.bots.values())
        if role:
            results = [b for b in results if b.role.value == role or b.role.name == role]
        if capability:
            results = [b for b in results if capability in b.capabilities]
        return [b.to_dict() for b in results]

    def generate_runtime_spreadsheet(self) -> Dict[str, Any]:
        """
        Generate complete runtime spreadsheet
        Maps every module, function, and capability in the system
        """
        spreadsheet = {
            "system_modules": {},
            "module_functions": {},
            "bot_capabilities": {},
            "expert_mappings": {},
            "gate_mappings": {},
            "constraint_mappings": {},
            "wired_functions": {},
            "librarian_knowledge": {}
        }

        # System modules
        spreadsheet["system_modules"] = {
            "dynamic_expert_generator": {
                "file": "src/dynamic_expert_generator.py",
                "class": "DynamicExpertGenerator",
                "functions": [
                    "generate_expert",
                    "generate_expert_team",
                    "create_expert_from_description"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "domain_gate_generator": {
                "file": "src/domain_gate_generator.py",
                "class": "DomainGateGenerator",
                "functions": [
                    "generate_gate",
                    "generate_gates_for_system",
                    "execute_gate"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "constraint_system": {
                "file": "src/constraint_system.py",
                "class": "ConstraintSystem",
                "functions": [
                    "add_constraint",
                    "validate_constraints",
                    "detect_conflicts",
                    "resolve_conflicts"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "document_processor": {
                "file": "src/document_processor.py",
                "class": "DocumentProcessor",
                "functions": [
                    "upload_document",
                    "get_document_summary",
                    "generate_requirements_report"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "inquisitory_engine": {
                "file": "src/inquisitory_engine.py",
                "class": "InquisitoryEngine",
                "functions": [
                    "analyze_choice",
                    "navigate_decision_tree",
                    "deductive_reasoning"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "llm_integration_layer": {
                "file": "src/llm_integration_layer.py",
                "class": "LLMIntegrationLayer",
                "functions": [
                    "route_request",
                    "validate_response",
                    "get_pending_triggers"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "system_integrator": {
                "file": "src/system_integrator.py",
                "class": "SystemIntegrator",
                "functions": [
                    "process_user_request",
                    "get_system_state",
                    "generate_system_report"
                ],
                "coupled": True,
                "decoupled_commands": []
            },
            "bot_inventory_library": {
                "file": "src/bot_inventory_library.py",
                "class": "BotInventoryLibrary",
                "functions": [
                    "spawn_bot",
                    "despawn_bot",
                    "assign_task",
                    "get_bot_inventory"
                ],
                "coupled": True,
                "decoupled_commands": []
            }
        }

        # Module functions with full details
        for module_name, module_data in spreadsheet["system_modules"].items():
            spreadsheet["module_functions"][module_name] = {
                func_name: {
                    "signature": f"{module_name}.{func_name}(params)",
                    "description": f"Function {func_name} in {module_name}",
                    "parameters": {},  # Would be populated from actual code
                    "returns": "dict",
                    "wired": True,
                    "help_visible": True
                }
                for func_name in module_data["functions"]
            }

        # Bot capabilities
        for cap_name, cap_data in self.capability_registry.items():
            spreadsheet["bot_capabilities"][cap_name] = {
                "name": cap_data["name"],
                "description": cap_data["description"],
                "function": cap_data["function"],
                "module": cap_data["module"],
                "parameters": cap_data["parameters"],
                "available": True,
                "help_visible": True
            }

        return spreadsheet


if __name__ == "__main__":
    # Test bot inventory library
    library = BotInventoryLibrary()

    # Test 1: Spawn expert bot
    logger.info("=== Test 1: Spawn Expert Bot ===")
    expert_bot = library.spawn_bot(
        name="Architecture Expert",
        role="expert",
        expert_id="expert_001"
    )
    logger.info(f"Spawned: {expert_bot.name} ({expert_bot.role.value})")
    logger.info(f"Capabilities: {len(expert_bot.capabilities)}")
    logger.info(f"Status: {expert_bot.status.value}")

    # Test 2: Spawn validator bot
    logger.info("\n=== Test 2: Spawn Validator Bot ===")
    validator_bot = library.spawn_bot(
        name="Security Validator",
        role="validator"
    )
    logger.info(f"Spawned: {validator_bot.name} ({validator_bot.role.value})")
    logger.info(f"Capabilities: {len(validator_bot.capabilities)}")

    # Test 3: Spawn monitor bot
    logger.info("\n=== Test 3: Spawn Monitor Bot ===")
    monitor_bot = library.spawn_bot(
        name="Performance Monitor",
        role="monitor"
    )
    logger.info(f"Spawned: {monitor_bot.name} ({monitor_bot.role.value})")

    # Test 4: Assign tasks
    logger.info("\n=== Test 4: Assign Tasks ===")
    library.assign_task(expert_bot.agent_id, "task_001")
    library.assign_task(validator_bot.agent_id, "task_002")
    logger.info(f"Expert bot tasks: {expert_bot.assigned_tasks}")
    logger.info(f"Validator bot tasks: {validator_bot.assigned_tasks}")

    # Test 5: Get bot inventory
    logger.info("\n=== Test 5: Bot Inventory ===")
    inventory = library.get_bot_inventory()
    logger.info(f"Total bots: {inventory['total_bots']}")
    logger.info(f"Spawned: {inventory['spawned_count']}")
    logger.info(f"By role: {list(inventory['by_role'].keys())}")
    logger.info(f"Available capabilities: {len(inventory['available_capabilities'])}")

    # Test 6: Despawn bot
    logger.info("\n=== Test 6: Despawn Bot ===")
    despawned = library.despawn_bot(monitor_bot.agent_id)
    logger.info(f"Despawned: {despawned}")
    logger.info(f"Active bots: {len(library.get_active_bots())}")

    # Test 7: Generate runtime spreadsheet
    logger.info("\n=== Test 7: Runtime Spreadsheet ===")
    spreadsheet = library.generate_runtime_spreadsheet()
    logger.info(f"System modules: {len(spreadsheet['system_modules'])}")
    logger.info(f"Module functions: {sum(len(funcs) for funcs in spreadsheet['module_functions'].values())}")
    logger.info(f"Bot capabilities: {len(spreadsheet['bot_capabilities'])}")
