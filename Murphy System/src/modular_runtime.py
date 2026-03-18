"""
Modular Runtime System
Dynamic module coupling/decoupling at runtime
"""
import importlib
import inspect
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("modular_runtime")

# Import gate builder
from src.gate_builder import GateBuilder
from src.system_builder import SystemBuilder


class ModuleStatus(Enum):
    """Module lifecycle status"""
    LOADED = "loaded"
    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"

@dataclass
class Module:
    """Represents a runtime module"""
    name: str
    module_path: str
    description: str
    version: str = "1.0.0"
    status: ModuleStatus = ModuleStatus.LOADED
    dependencies: List[str] = field(default_factory=list)
    commands: Dict[str, Callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Load the module and extract commands"""
        self._load_module()

    def _load_module(self):
        """Dynamically load the module and extract commands"""
        try:
            # Import the module
            self.module = importlib.import_module(self.module_path)

            # Extract all functions
            for name, obj in inspect.getmembers(self.module, inspect.isfunction):
                if not name.startswith('_'):  # Skip private functions
                    self.commands[name] = obj

            self.status = ModuleStatus.ACTIVE

        except Exception as exc:
            logger.info(f"Error loading module {self.name}: {exc}")
            self.status = ModuleStatus.LOADED

    def get_command_signature(self, command_name: str) -> str:
        """Get the signature of a command"""
        if command_name in self.commands:
            sig = inspect.signature(self.commands[command_name])
            return str(sig)
        return "No signature available"

    def get_help_text(self) -> str:
        """Generate help text for this module"""
        help_text = f"\n## {self.name} ({self.version})\n"
        help_text += f"{self.description}\n\n"

        if self.commands:
            help_text += "**Commands:**\n"
            for cmd_name, cmd_func in self.commands.items():
                sig = self.get_command_signature(cmd_name)
                help_text += f"  - `{cmd_name}{sig}`\n"

        if self.dependencies:
            help_text += f"\n**Dependencies:** {', '.join(self.dependencies)}\n"

        return help_text

class ModularRuntime:
    """
    Runtime system that can dynamically couple/decouple modules
    """

    def __init__(self):
        self.modules: Dict[str, Module] = {}
        self.active_modules: Dict[str, Module] = {}
        self.help_cache: Optional[str] = None
        self.gate_builder = GateBuilder()
        self.system_builder = SystemBuilder()

        # Initialize with core modules
        self._initialize_core_modules()

        # Register module manager in module system
        self._setup_module_manager()

    def _initialize_core_modules(self):
        """Initialize core system modules"""
        # Define core modules
        core_modules = [
            {
                "name": "SystemBuilder",
                "module_path": "src.system_builder",
                "description": "Builds system architecture from natural language",
                "version": "1.0.0"
            },
            {
                "name": "GateBuilder",
                "module_path": "src.gate_builder",
                "description": "Creates safety gates for any system",
                "version": "1.0.0"
            },
            {
                "name": "ModuleManager",
                "module_path": "src.module_manager",
                "description": "Manages dynamic module coupling/decoupling",
                "version": "1.0.0"
            },
            {
                "name": "TaskExecutor",
                "module_path": "src.task_executor",
                "description": "Executes tasks using available tools",
                "version": "1.0.0"
            }
        ]

        # Load core modules
        for mod_config in core_modules:
            self.load_module(**mod_config)

    def _setup_module_manager(self):
        """Setup module manager with core capabilities"""
        # Register core modules in module manager
        from src.module_manager import module_manager

        core_module_caps = [
            ("SystemBuilder", "src.system_builder",
             "Builds system architecture from natural language",
             ["architecture_design", "component_selection", "system_planning"]),
            ("GateBuilder", "src.gate_builder",
             "Creates safety gates for any system",
             ["safety_gates", "risk_mitigation", "security_checks"]),
            ("ModuleManager", "src.module_manager",
             "Manages dynamic module coupling/decoupling",
             ["module_management", "dynamic_loading", "system_integration"]),
            ("TaskExecutor", "src.task_executor",
             "Executes tasks using available tools",
             ["task_execution", "tool_selection", "automation"])
        ]

        for name, path, desc, caps in core_module_caps:
            module_manager.register_module(name, path, desc, caps)

    def load_module(self, name: str, module_path: str, description: str,
                    version: str = "1.0.0", dependencies: List[str] = None):
        """Load a new module into the runtime"""
        if name in self.modules:
            logger.info(f"Module {name} already loaded")
            return

        module = Module(
            name=name,
            module_path=module_path,
            description=description,
            version=version,
            dependencies=dependencies or []
        )

        self.modules[name] = module
        self.active_modules[name] = module
        self.help_cache = None  # Invalidate cache
        logger.info(f"✓ Loaded module: {name} v{version}")

    def unload_module(self, name: str):
        """Unload a module from the runtime"""
        if name in self.modules:
            self.modules[name].status = ModuleStatus.REMOVED
            del self.active_modules[name]
            self.help_cache = None  # Invalidate cache
            logger.info(f"✗ Unloaded module: {name}")

    def pause_module(self, name: str):
        """Pause a module (keep loaded but not active)"""
        if name in self.active_modules:
            self.modules[name].status = ModuleStatus.PAUSED
            del self.active_modules[name]
            self.help_cache = None
            logger.info(f"⏸ Paused module: {name}")

    def resume_module(self, name: str):
        """Resume a paused module"""
        if name in self.modules and self.modules[name].status == ModuleStatus.PAUSED:
            self.modules[name].status = ModuleStatus.ACTIVE
            self.active_modules[name] = self.modules[name]
            self.help_cache = None
            logger.info(f"▶ Resumed module: {name}")

    def get_active_commands(self) -> Dict[str, Dict]:
        """Get all active commands from all active modules"""
        commands = {}
        for module_name, module in self.active_modules.items():
            for cmd_name, cmd_func in module.commands.items():
                full_command = f"{module_name.lower()}.{cmd_name}"
                commands[full_command] = {
                    "module": module_name,
                    "function": cmd_name,
                    "signature": module.get_command_signature(cmd_name),
                    "description": cmd_func.__doc__ or "No description"
                }
        return commands

    def generate_help(self) -> str:
        """Generate dynamic help text based on active modules"""
        if self.help_cache:
            return self.help_cache

        help_text = "# Available Commands\n\n"
        help_text += "The following commands are currently available:\n\n"

        # Group by module
        for module_name, module in self.active_modules.items():
            help_text += module.get_help_text()

        # Add system-level commands
        help_text += "\n## System Commands\n"
        help_text += "  - `/modules list` - List all modules\n"
        help_text += "  - `/modules load <name>` - Load a module\n"
        help_text += "  - `/modules unload <name>` - Unload a module\n"
        help_text += "  - `/modules pause <name>` - Pause a module\n"
        help_text += "  - `/modules resume <name>` - Resume a module\n"
        help_text += "  - `/help` - Show this help text\n"

        self.help_cache = help_text
        return help_text

    def auto_select_tools(self, task_description: str, confidence: float) -> List[str]:
        """
        Automatically select tools/modules based on task and confidence

        Args:
            task_description: Natural language description of the task
            confidence: Confidence level (0.0 to 1.0)

        Returns:
            List of module names to activate
        """
        selected_modules = []

        # Analyze task description for keywords
        task_lower = task_description.lower()

        # High confidence (> 0.8) - Use precise tools
        if confidence > 0.8:
            if "build" in task_lower or "create" in task_lower or "make" in task_lower:
                selected_modules.append("SystemBuilder")
            if "gate" in task_lower or "safety" in task_lower or "protect" in task_lower:
                selected_modules.append("GateBuilder")
            if "execute" in task_lower or "run" in task_lower or "do" in task_lower:
                selected_modules.append("TaskExecutor")

        # Medium confidence (0.5 to 0.8) - Use broader tools
        elif confidence > 0.5:
            selected_modules.extend(["SystemBuilder", "GateBuilder"])

        # Low confidence (< 0.5) - Use exploratory tools
        else:
            selected_modules.extend(["SystemBuilder", "GateBuilder", "TaskExecutor"])

        # Always include ModuleManager for runtime flexibility
        if "ModuleManager" not in selected_modules:
            selected_modules.append("ModuleManager")

        return selected_modules

    def build_system_from_request(self, user_request: str) -> Dict[str, Any]:
        """
        Build a complete system from a non-technical user request

        Args:
            user_request: Natural language request (high school reading level)

        Returns:
            System architecture and plan
        """
        logger.info(f"\n{'='*60}")
        logger.info("Building system from request:")
        logger.info(f"'{user_request}'")
        logger.info(f"{'='*60}\n")

        # Step 1: Analyze the request (non-technical → technical)
        analysis = self._analyze_request(user_request)
        logger.info("📋 Request Analysis:")
        logger.info(f"  Intent: {analysis['intent']}")
        logger.info(f"  Domain: {analysis['domain']}")
        logger.info(f"  Complexity: {analysis['complexity']}")

        # Step 2: Select appropriate modules
        confidence = 0.7  # Start with medium confidence
        selected_modules = self.auto_select_tools(user_request, confidence)
        logger.info("🔧 Selected Modules:")
        for mod in selected_modules:
            logger.info(f"  ✓ {mod}")

        # Step 3: Build system architecture
        architecture = self.system_builder.build_architecture(
            analysis,
            selected_modules
        )
        logger.info("🏗️  System Architecture:")
        logger.info(f"  Components: {len(architecture['components'])}")
        logger.info(f"  Layers: {len(architecture['layers'])}")

        # Step 4: Generate gates
        gates = self.gate_builder.build_gates(
            analysis,
            architecture
        )
        logger.info("🚧 Safety Gates:")
        for gate in gates:
            logger.info(f"  ⚠️  {gate['name']}: {gate['description']}")

        # Step 5: Generate implementation plan
        plan = self._generate_implementation_plan(
            architecture,
            gates,
            selected_modules
        )
        logger.info("📝 Implementation Plan:")
        for step in plan['steps']:
            logger.info(f"  {step['order']}. {step['title']}")
            logger.info(f"     {step['description']}")

        return {
            "request": user_request,
            "analysis": analysis,
            "architecture": architecture,
            "gates": gates,
            "implementation_plan": plan,
            "selected_modules": selected_modules
        }

    def _analyze_request(self, user_request: str) -> Dict[str, Any]:
        """Analyze a non-technical request"""
        # Simple keyword-based analysis (in real system, use LLM)
        request_lower = user_request.lower()

        # Determine intent
        if any(word in request_lower for word in ["build", "create", "make", "develop"]):
            intent = "build_system"
        elif any(word in request_lower for word in ["help", "explain", "show"]):
            intent = "get_help"
        elif any(word in request_lower for word in ["fix", "repair", "debug"]):
            intent = "fix_problem"
        else:
            intent = "general_inquiry"

        # Determine domain
        domains = {
            "web": ["website", "web", "api", "server"],
            "data": ["data", "database", "storage", "information"],
            "ai": ["ai", "intelligence", "learning", "smart"],
            "system": ["system", "application", "program", "software"]
        }

        domain = "general"
        for d, keywords in domains.items():
            if any(kw in request_lower for kw in keywords):
                domain = d
                break

        # Determine complexity
        complexity_words = {
            "simple": ["simple", "basic", "easy", "quick", "small"],
            "medium": ["medium", "moderate", "standard"],
            "complex": ["complex", "advanced", "sophisticated", "large", "scalable"]
        }

        complexity = "medium"
        for comp, keywords in complexity_words.items():
            if any(kw in request_lower for kw in keywords):
                complexity = comp
                break

        return {
            "intent": intent,
            "domain": domain,
            "complexity": complexity,
            "original_request": user_request
        }

    def _generate_implementation_plan(self, architecture: Dict,
                                     gates: List[Dict],
                                     modules: List[str]) -> Dict[str, Any]:
        """Generate implementation plan"""
        steps = []

        # Step 1: Setup
        steps.append({
            "order": 1,
            "title": "Initialize Project",
            "description": "Set up project structure and dependencies"
        })

        # Step 2: Core components
        steps.append({
            "order": 2,
            "title": "Build Core Components",
            "description": f"Implement {len(architecture['components'])} core components"
        })

        # Step 3: Safety gates
        steps.append({
            "order": 3,
            "title": "Implement Safety Gates",
            "description": f"Add {len(gates)} safety gates for risk mitigation"
        })

        # Step 4: Integration
        steps.append({
            "order": 4,
            "title": "Integrate Modules",
            "description": f"Connect {len(modules)} modules together"
        })

        # Step 5: Testing
        steps.append({
            "order": 5,
            "title": "Test and Validate",
            "description": "Run tests and validate system behavior"
        })

        return {
            "total_steps": len(steps),
            "estimated_time": self._estimate_time(steps),
            "steps": steps
        }

    def _estimate_time(self, steps: List[Dict]) -> str:
        """Estimate implementation time"""
        # Simple heuristic: 1 hour per step
        hours = len(steps)
        if hours == 1:
            return "1 hour"
        elif hours < 8:
            return f"{hours} hours"
        else:
            days = hours / 8
            return f"{int(days)} days"

# Lazy proxy — only instantiates ModularRuntime on first attribute access.
# This prevents ALL modules from being imported when any file imports
# modular_runtime (eager init was the original behaviour).
class _LazyRuntime:
    """Lazy proxy for ModularRuntime. Only instantiates on first use."""
    _instance = None

    def __getattr__(self, name: str):
        if _LazyRuntime._instance is None:
            _LazyRuntime._instance = ModularRuntime()
        return getattr(_LazyRuntime._instance, name)


runtime = _LazyRuntime()

if __name__ == "__main__":
    logger.info("Modular Runtime System v1.0")
    logger.info("=" * 60)
    logger.info("\nLoaded Modules:")
    for name, module in runtime.modules.items():
        logger.info(f"  ✓ {name} - {module.description}")
