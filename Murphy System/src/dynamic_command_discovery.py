"""
Dynamic Command Discovery System for Murphy System Runtime

This module provides automatic command discovery based on module coupling:
- Automatically discover available commands from coupled modules
- Dynamic command registration and availability checking
- Context-aware command suggestions
- Automatic command help generation
"""

import importlib
import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("dynamic_command_discovery")


class CommandCategory(Enum):
    """Command categories"""
    SYSTEM = "system"
    MODULE = "module"
    WORKFLOW = "workflow"
    GOVERNANCE = "governance"
    AGENTIC = "agentic"
    LLM = "llm"
    ANALYSIS = "analysis"
    INTEGRATION = "integration"
    LEARNING = "learning"
    AUTONOMOUS = "autonomous"


@dataclass
class Command:
    """Represents a dynamic command"""
    command_name: str
    command_type: str  # function, method, endpoint
    category: CommandCategory
    description: str
    module_name: str
    function_name: str
    callable_obj: Optional[Callable] = None
    parameters: Dict[str, Any] = None
    examples: List[str] = None
    requires_auth: bool = False
    required_permissions: List[str] = None
    risk_level: str = "low"  # low, medium, high, critical

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.examples is None:
            self.examples = []
        if self.required_permissions is None:
            self.required_permissions = []


@dataclass
class ModuleInfo:
    """Information about a module"""
    module_name: str
    module_path: str
    is_coupled: bool
    is_active: bool
    commands: List[str] = None
    dependencies: List[str] = None

    def __post_init__(self):
        if self.commands is None:
            self.commands = []
        if self.dependencies is None:
            self.dependencies = []


class DynamicCommandDiscovery:
    """
    Dynamically discovers commands from coupled modules

    This system automatically discovers available commands by:
    1. Scanning coupled modules for callable functions
    2. Extracting command metadata from docstrings
    3. Registering commands dynamically
    4. Managing command availability based on module coupling
    """

    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self.modules: Dict[str, ModuleInfo] = {}
        self.category_index: Dict[CommandCategory, List[str]] = {}
        self.risk_index: Dict[str, List[str]] = {}  # risk_level -> command_names

        # Initialize category index
        for category in CommandCategory:
            self.category_index[category] = []

        # Initialize risk index
        for risk in ["low", "medium", "high", "critical"]:
            self.risk_index[risk] = []

    def register_module(self, module_name: str, module_path: str,
                       is_coupled: bool = True, dependencies: List[str] = None) -> None:
        """Register a module and discover its commands"""
        module_info = ModuleInfo(
            module_name=module_name,
            module_path=module_path,
            is_coupled=is_coupled,
            is_active=is_coupled,  # Active if coupled
            dependencies=dependencies or []
        )

        self.modules[module_name] = module_info

        # If module is coupled, discover its commands
        if is_coupled:
            self._discover_module_commands(module_name, module_path)

    def unregister_module(self, module_name: str) -> None:
        """Unregister a module and its commands"""
        if module_name in self.modules:
            module_info = self.modules[module_name]
            module_info.is_coupled = False
            module_info.is_active = False

            # Remove commands from registry
            for cmd_name in module_info.commands:
                self._remove_command(cmd_name)

    def couple_module(self, module_name: str) -> bool:
        """Couple a module and make its commands available"""
        if module_name in self.modules:
            module_info = self.modules[module_name]
            module_info.is_coupled = True
            module_info.is_active = True

            # Re-discover commands
            self._discover_module_commands(module_name, module_info.module_path)
            return True
        return False

    def decouple_module(self, module_name: str) -> bool:
        """Decouple a module and hide its commands"""
        if module_name in self.modules:
            module_info = self.modules[module_name]
            module_info.is_coupled = False
            module_info.is_active = False

            # Remove commands from active registry
            for cmd_name in module_info.commands:
                self._remove_command(cmd_name)
            return True
        return False

    def get_available_commands(self) -> List[Command]:
        """Get all currently available commands from coupled modules"""
        return [
            cmd for cmd_name, cmd in self.commands.items()
            if self._is_command_available(cmd)
        ]

    def get_commands_by_category(self, category: CommandCategory) -> List[Command]:
        """Get commands in a specific category"""
        command_names = self.category_index.get(category, [])
        return [
            self.commands[name] for name in command_names
            if name in self.commands and self._is_command_available(self.commands[name])
        ]

    def get_commands_by_risk_level(self, risk_level: str) -> List[Command]:
        """Get commands by risk level"""
        command_names = self.risk_index.get(risk_level, [])
        return [
            self.commands[name] for name in command_names
            if name in self.commands and self._is_command_available(self.commands[name])
        ]

    def get_command(self, command_name: str) -> Optional[Command]:
        """Get a specific command by name"""
        cmd = self.commands.get(command_name)
        if cmd and self._is_command_available(cmd):
            return cmd
        return None

    def search_commands(self, query: str) -> List[Command]:
        """Search for commands by name or description"""
        query = query.lower()
        matching_commands = []

        for cmd in self.get_available_commands():
            if (query in cmd.command_name.lower() or
                query in cmd.description.lower()):
                matching_commands.append(cmd)

        return matching_commands

    def get_help_text(self, command_name: str) -> str:
        """Generate help text for a command"""
        cmd = self.get_command(command_name)
        if not cmd:
            return f"Command '{command_name}' not found"

        help_text = f"Command: /{cmd.command_name}\n"
        help_text += f"Category: {cmd.category.value}\n"
        help_text += f"Description: {cmd.description}\n"
        help_text += f"Module: {cmd.module_name}\n"
        help_text += f"Risk Level: {cmd.risk_level}\n"

        if cmd.parameters:
            help_text += "\nParameters:\n"
            for param_name, param_info in cmd.parameters.items():
                help_text += f"  {param_name}: {param_info}\n"

        if cmd.examples:
            help_text += "\nExamples:\n"
            for example in cmd.examples:
                help_text += f"  {example}\n"

        if cmd.required_permissions:
            help_text += f"\nRequired Permissions: {', '.join(cmd.required_permissions)}\n"

        return help_text

    def generate_dynamic_help(self) -> str:
        """Generate dynamic help text showing all available commands"""
        commands = self.get_available_commands()

        if not commands:
            return "No commands available. Couple modules to enable commands."

        help_text = "=== Available Commands ===\n\n"

        # Group by category
        by_category: Dict[CommandCategory, List[Command]] = {}
        for cmd in commands:
            if cmd.category not in by_category:
                by_category[cmd.category] = []
            by_category[cmd.category].append(cmd)

        # Display by category
        for category in sorted(by_category.keys(), key=lambda x: x.value):
            help_text += f"[{category.value.upper()}]\n"
            for cmd in sorted(by_category[category], key=lambda x: x.command_name):
                help_text += f"  /{cmd.command_name} - {cmd.description}\n"
            help_text += "\n"

        help_text += f"\nTotal: {len(commands)} commands available\n"
        help_text += "Use /help <command_name> for detailed information\n"

        return help_text

    def _discover_module_commands(self, module_name: str, module_path: str) -> None:
        """Discover commands in a module"""
        try:
            # Import the module
            module = importlib.import_module(module_path)

            # Scan for callable functions
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                # Skip private functions
                if name.startswith('_'):
                    continue

                # Extract command metadata from docstring
                docstring = inspect.getdoc(obj) or ""
                command = self._create_command_from_function(
                    name, obj, module_name, docstring
                )

                if command:
                    self._register_command(command)

                    # Track command in module info
                    if module_name in self.modules:
                        self.modules[module_name].commands.append(command.command_name)

        except Exception as exc:
            logger.info(f"Error discovering commands for module {module_name}: {exc}")

    def _create_command_from_function(self, func_name: str, func_obj: Callable,
                                      module_name: str, docstring: str) -> Optional[Command]:
        """Create a command from a function"""
        # Extract metadata from docstring
        description = self._extract_description(docstring)
        parameters = self._extract_parameters(func_obj)
        examples = self._extract_examples(docstring)

        # Determine category based on module name
        category = self._determine_category(module_name, func_name)

        # Determine risk level
        risk_level = self._determine_risk_level(module_name, func_name)

        command = Command(
            command_name=func_name,
            command_type="function",
            category=category,
            description=description,
            module_name=module_name,
            function_name=func_name,
            callable_obj=func_obj,
            parameters=parameters,
            examples=examples,
            risk_level=risk_level
        )

        return command

    def _register_command(self, command: Command) -> None:
        """Register a command"""
        self.commands[command.command_name] = command

        # Add to category index
        if command.category not in self.category_index:
            self.category_index[command.category] = []
        if command.command_name not in self.category_index[command.category]:
            self.category_index[command.category].append(command.command_name)

        # Add to risk index
        if command.risk_level not in self.risk_index:
            self.risk_index[command.risk_level] = []
        if command.command_name not in self.risk_index[command.risk_level]:
            self.risk_index[command.risk_level].append(command.command_name)

    def _remove_command(self, command_name: str) -> None:
        """Remove a command from registry"""
        if command_name in self.commands:
            cmd = self.commands[command_name]

            # Remove from category index
            if cmd.category in self.category_index:
                if command_name in self.category_index[cmd.category]:
                    self.category_index[cmd.category].remove(command_name)

            # Remove from risk index
            if cmd.risk_level in self.risk_index:
                if command_name in self.risk_index[cmd.risk_level]:
                    self.risk_index[cmd.risk_level].remove(command_name)

            # Remove from commands
            del self.commands[command_name]

    def _is_command_available(self, command: Command) -> bool:
        """Check if a command is available (module is coupled)"""
        module_info = self.modules.get(command.module_name)
        if module_info:
            return module_info.is_active and module_info.is_coupled
        return False

    def _extract_description(self, docstring: str) -> str:
        """Extract description from docstring"""
        lines = docstring.split('\n')
        description_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith(':'):
                description_lines.append(stripped)
            elif description_lines:
                # Stop at first parameter description
                break

        return ' '.join(description_lines) if description_lines else docstring

    def _extract_parameters(self, func_obj: Callable) -> Dict[str, str]:
        """Extract parameters from function signature"""
        params = {}
        sig = inspect.signature(func_obj)

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            param_type = param.annotation if param.annotation != inspect.Parameter.empty else 'Any'
            default = param.default if param.default != inspect.Parameter.empty else None

            param_desc = f"Type: {param_type}"
            if default is not None:
                param_desc += f", Default: {default}"

            params[param_name] = param_desc

        return params

    def _extract_examples(self, docstring: str) -> List[str]:
        """Extract examples from docstring"""
        examples = []
        lines = docstring.split('\n')

        in_examples = False
        for line in lines:
            if 'Example' in line or 'example' in line:
                in_examples = True
            if in_examples:
                examples.append(line.strip())
                if not line.strip():
                    in_examples = False

        return examples

    def _determine_category(self, module_name: str, func_name: str) -> CommandCategory:
        """Determine command category based on module and function name"""
        module_lower = module_name.lower()
        func_lower = func_name.lower()

        if any(keyword in module_lower for keyword in ['system', 'core']):
            return CommandCategory.SYSTEM
        elif any(keyword in module_lower for keyword in ['module', 'compiler']):
            return CommandCategory.MODULE
        elif any(keyword in module_lower for keyword in ['workflow', 'orchestrator']):
            return CommandCategory.WORKFLOW
        elif any(keyword in module_lower for keyword in ['governance', 'policy', 'gate']):
            return CommandCategory.GOVERNANCE
        elif any(keyword in module_lower for keyword in ['agentic', 'dynamic', 'configurer']):
            return CommandCategory.AGENTIC
        elif any(keyword in module_lower for keyword in ['llm', 'language', 'model']):
            return CommandCategory.LLM
        elif any(keyword in module_lower for keyword in ['analysis', 'telemetry', 'metric']):
            return CommandCategory.ANALYSIS
        elif any(keyword in module_lower for keyword in ['integration', 'connector']):
            return CommandCategory.INTEGRATION
        elif any(keyword in module_lower for keyword in ['learning', 'feedback', 'adaptive', 'decision']):
            return CommandCategory.LEARNING
        elif any(keyword in module_lower for keyword in ['scheduler', 'autonomous', 'risk', 'oversight']):
            return CommandCategory.AUTONOMOUS
        else:
            return CommandCategory.SYSTEM

    def _determine_risk_level(self, module_name: str, func_name: str) -> str:
        """Determine risk level based on module and function name"""
        module_lower = module_name.lower()
        func_lower = func_name.lower()

        # Critical risk commands
        if any(keyword in func_lower for keyword in ['delete', 'remove', 'destroy', 'shutdown']):
            return 'critical'

        # High risk commands
        if any(keyword in func_lower for keyword in ['deploy', 'execute', 'modify', 'change']):
            return 'high'

        # Medium risk commands
        if any(keyword in func_lower for keyword in ['create', 'update', 'restart']):
            return 'medium'

        # Low risk commands (default)
        if any(keyword in func_lower for keyword in ['get', 'list', 'show', 'help', 'status']):
            return 'low'

        # Default to medium for unknown
        return 'medium'
