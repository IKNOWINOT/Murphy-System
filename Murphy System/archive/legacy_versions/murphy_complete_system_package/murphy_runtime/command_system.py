# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Command System with Librarian Integration
Manages all system commands, integrates with Librarian for context and history
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Command categories for organization"""
    SYSTEM = "system"
    LIBRARIAN = "librarian"
    MODULE = "module"
    STATE = "state"
    AGENT = "agent"
    ARTIFACT = "artifact"
    SHADOW = "shadow"
    MONITORING = "monitoring"
    ATTENTION = "attention"
    COOPERATIVE = "cooperative"


@dataclass
class Command:
    """Represents a single command in the system"""
    name: str
    description: str
    category: CommandCategory
    module: Optional[str] = None  # Module that provides this command (None for core system)
    handler: Optional[Callable] = None  # Handler function
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    requires_auth: bool = False
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    implemented: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert command to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "module": self.module,
            "parameters": self.parameters,
            "examples": self.examples,
            "requires_auth": self.requires_auth,
            "risk_level": self.risk_level,
            "implemented": self.implemented
        }


class CommandRegistry:
    """Central registry for all system commands"""
    
    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self.module_commands: Dict[str, List[str]] = {}  # module_id -> list of command names
        self.librarian_adapter = None
        
    def register_command(self, command: Command):
        """Register a new command"""
        self.commands[command.name] = command
        
        # Track by module
        if command.module:
            if command.module not in self.module_commands:
                self.module_commands[command.module] = []
            self.module_commands[command.module].append(command.name)
            
        logger.info(f"✓ Registered command: /{command.name} (module: {command.module})")
        
        # Log to Librarian if available
        if self.librarian_adapter:
            self.librarian_adapter.log_command_registration(command)
    
    def unregister_command(self, command_name: str):
        """Unregister a command"""
        if command_name in self.commands:
            command = self.commands[command_name]
            
            # Remove from module tracking
            if command.module and command.module in self.module_commands:
                self.module_commands[command.module].remove(command_name)
                if not self.module_commands[command.module]:
                    del self.module_commands[command.module]
            
            del self.commands[command_name]
            logger.info(f"✓ Unregistered command: /{command_name}")
            
            # Log to Librarian if available
            if self.librarian_adapter:
                self.librarian_adapter.log_command_unregistration(command_name)
    
    def get_command(self, command_name: str) -> Optional[Command]:
        """Get a command by name"""
        return self.commands.get(command_name)
    
    def get_all_commands(self) -> List[Command]:
        """Get all registered commands"""
        return list(self.commands.values())
    
    def get_commands_by_module(self, module_id: str) -> List[Command]:
        """Get all commands from a specific module"""
        if module_id not in self.module_commands:
            return []
        command_names = self.module_commands[module_id]
        return [self.commands[name] for name in command_names if name in self.commands]
    
    def get_commands_by_category(self, category: CommandCategory) -> List[Command]:
        """Get all commands in a specific category"""
        return [cmd for cmd in self.commands.values() if cmd.category == category]
    
    def get_implemented_commands(self) -> List[Command]:
        """Get only implemented commands"""
        return [cmd for cmd in self.commands.values() if cmd.implemented]
    
    def get_help_text(self, module_id: Optional[str] = None) -> str:
        """Generate help text for commands
        
        Args:
            module_id: If provided, only show commands from this module
        """
        if module_id:
            commands = self.get_commands_by_module(module_id)
            if not commands:
                return f"No commands available for module: {module_id}"
            
            help_text = f"\n{'='*60}\n"
            help_text += f"Commands for module: {module_id}\n"
            help_text += f"{'='*60}\n\n"
        else:
            commands = self.get_implemented_commands()
            help_text = f"\n{'='*60}\n"
            help_text += "Available Commands\n"
            help_text += f"{'='*60}\n\n"
        
        # Group by category
        by_category = {}
        for cmd in commands:
            if cmd.category not in by_category:
                by_category[cmd.category] = []
            by_category[cmd.category].append(cmd)
        
        # Generate help for each category
        for category in sorted(by_category.keys(), key=lambda x: x.value):
            help_text += f"\n{category.value.upper()} COMMANDS:\n"
            help_text += f"{'-'*40}\n"
            
            for cmd in by_category[category]:
                module_info = f" [{cmd.module}]" if cmd.module else ""
                risk_info = f" [{cmd.risk_level}]" if cmd.risk_level != "LOW" else ""
                help_text += f"  /{cmd.name}{module_info}{risk_info}\n"
                help_text += f"    {cmd.description}\n"
                
                if cmd.examples:
                    help_text += f"    Examples:\n"
                    for ex in cmd.examples:
                        help_text += f"      {ex}\n"
                help_text += "\n"
        
        help_text += f"\n{'='*60}\n"
        return help_text
    
    def register_module_commands(self, module_spec: Dict[str, Any]):
        """Register all commands from a module specification"""
        module_id = module_spec.get('module_id')
        module_name = module_spec.get('module_name')
        
        if not module_id or not module_spec.get('commands'):
            return
        
        # Unregister existing commands from this module
        if module_id in self.module_commands:
            for cmd_name in self.module_commands[module_id][:]:
                self.unregister_command(cmd_name)
        
        # Register new commands
        for cmd_data in module_spec.get('commands', []):
            command = Command(
                name=cmd_data.get('name'),
                description=cmd_data.get('description', ''),
                category=CommandCategory(cmd_data.get('category', 'MODULE')),
                module=module_id,
                parameters=cmd_data.get('parameters', []),
                examples=cmd_data.get('examples', []),
                requires_auth=cmd_data.get('requires_auth', False),
                risk_level=cmd_data.get('risk_level', 'LOW'),
                implemented=cmd_data.get('implemented', True)
            )
            self.register_command(command)
        
        logger.info(f"✓ Registered {len(module_spec.get('commands', []))} commands from module: {module_name}")


# Global command registry instance
command_registry = CommandRegistry()


def get_command_registry() -> CommandRegistry:
    """Get the global command registry"""
    return command_registry


def initialize_core_commands():
    """Initialize core system commands (not from modules)"""
    
    core_commands = [
        Command(
            name="help",
            description="Show all available commands by module",
            category=CommandCategory.SYSTEM,
            parameters=[
                {"name": "module", "description": "Optional: Show commands for specific module", "required": False}
            ],
            examples=[
                "/help",
                "/help system",
                "/help <module_id>"
            ]
        ),
        Command(
            name="status",
            description="Show system status and component health",
            category=CommandCategory.SYSTEM,
            examples=["/status"]
        ),
        Command(
            name="initialize",
            description="Initialize the Murphy System with default components",
            category=CommandCategory.SYSTEM,
            risk_level="MEDIUM",
            examples=["/initialize"]
        ),
        Command(
            name="clear",
            description="Clear the terminal",
            category=CommandCategory.SYSTEM,
            examples=["/clear"]
        ),
        Command(
            name="state",
            description="Manage system states",
            category=CommandCategory.STATE,
            parameters=[
                {"name": "action", "description": "Action: list, evolve, regenerate, rollback", "required": True},
                {"name": "id", "description": "State ID (for evolve/regenerate/rollback)", "required": False}
            ],
            examples=[
                "/state list",
                "/state evolve <id>",
                "/state regenerate <id>",
                "/state rollback <id>"
            ]
        ),
        Command(
            name="agent",
            description="Manage AI agents",
            category=CommandCategory.AGENT,
            parameters=[
                {"name": "action", "description": "Action: list, override", "required": True},
                {"name": "id", "description": "Agent ID", "required": False}
            ],
            examples=[
                "/agent list",
                "/agent override <id>"
            ]
        ),
        Command(
            name="artifact",
            description="Manage generated artifacts",
            category=CommandCategory.ARTIFACT,
            parameters=[
                {"name": "action", "description": "Action: list, view, generate, search, convert, download, stats", "required": True}
            ],
            examples=[
                "/artifact list",
                "/artifact view <id>",
                "/artifact generate",
                "/artifact stats"
            ]
        ),
        Command(
            name="shadow",
            description="Manage shadow agent learning",
            category=CommandCategory.SHADOW,
            parameters=[
                {"name": "action", "description": "Action: list, observations, proposals, automations, approve, reject, learn, stats", "required": True}
            ],
            examples=[
                "/shadow list",
                "/shadow learn",
                "/shadow stats"
            ]
        ),
        Command(
            name="monitoring",
            description="Access monitoring system",
            category=CommandCategory.MONITORING,
            parameters=[
                {"name": "action", "description": "Action: health, metrics, anomalies, recommendations, alerts, analyze, dismiss, panel", "required": True}
            ],
            examples=[
                "/monitoring health",
                "/monitoring metrics",
                "/monitoring panel"
            ]
        ),
        Command(
            name="module",
            description="Manage system modules",
            category=CommandCategory.MODULE,
            parameters=[
                {"name": "action", "description": "Action: compile, list, search, load, unload, spec, loaded", "required": True},
                {"name": "source", "description": "GitHub URL or file path", "required": False}
            ],
            examples=[
                "/module list",
                "/module compile github <url>",
                "/module load <id>",
                "/module loaded"
            ]
        )
    ]
    
    for cmd in core_commands:
        command_registry.register_command(cmd)
    
    logger.info(f"✓ Initialized {len(core_commands)} core system commands")


def execute_command(command_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a command
    
    Args:
        command_name: Name of the command to execute
        args: Command arguments
        
    Returns:
        Execution result with success status and data/error
    """
    command = command_registry.get_command(command_name)
    
    if not command:
        return {
            "success": False,
            "error": f"Unknown command: /{command_name}",
            "suggestion": f"Use /help to see available commands"
        }
    
    if not command.implemented:
        return {
            "success": False,
            "error": f"Command /{command_name} is not yet implemented"
        }
    
    # Log command execution to Librarian if available
    if command_registry.librarian_adapter:
        command_registry.librarian_adapter.log_command_execution(command, args)
    
    # Execute command handler if available
    if command.handler:
        try:
            result = command.handler(**args)
            return {
                "success": True,
                "data": result
            }
        except Exception as e:
            logger.error(f"Error executing command /{command_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # No handler registered - command exists but needs implementation
    return {
        "success": False,
        "error": f"Command /{command_name} registered but no handler implemented"
    }


# Initialize core commands on import
initialize_core_commands()