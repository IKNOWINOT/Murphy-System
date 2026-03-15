"""
Module Manager - Manages dynamic module coupling/decoupling
Reading level: High school student
"""
import importlib
import inspect
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("module_manager")

class ModuleManager:
    """
    Manages which modules are active in the system
    Can add or remove modules while the system is running
    """

    def __init__(self):
        # All available modules (loaded or not)
        self.available_modules: Dict[str, Dict] = {}

        # Currently active modules
        self.active_modules: Dict[str, Any] = {}

        # Module capabilities (what each module can do)
        self.module_capabilities: Dict[str, List[str]] = {}

    def register_module(self, name: str, module_path: str,
                       description: str, capabilities: List[str]):
        """
        Register a new module that can be loaded

        Args:
            name: Name of the module
            module_path: Python import path
            description: What the module does
            capabilities: List of things the module can do
        """
        self.available_modules[name] = {
            "path": module_path,
            "description": description,
            "capabilities": capabilities,
            "status": "available"
        }

        # Map capabilities to modules
        for capability in capabilities:
            if capability not in self.module_capabilities:
                self.module_capabilities[capability] = []
            self.module_capabilities[capability].append(name)

    def load_module(self, name: str) -> bool:
        """
        Load and activate a module

        Args:
            name: Name of module to load

        Returns:
            True if successful, False otherwise
        """
        if name not in self.available_modules:
            logger.info(f"Module {name} not found")
            return False

        if name in self.active_modules:
            logger.info(f"Module {name} is already active")
            return True

        try:
            # Import the module
            module_path = self.available_modules[name]["path"]
            module = importlib.import_module(module_path)

            # Add to active modules
            self.active_modules[name] = module
            self.available_modules[name]["status"] = "active"

            logger.info(f"✓ Loaded module: {name}")
            return True

        except Exception as exc:
            logger.info(f"✗ Failed to load module {name}: {exc}")
            return False

    def unload_module(self, name: str) -> bool:
        """
        Unload and deactivate a module

        Args:
            name: Name of module to unload

        Returns:
            True if successful, False otherwise
        """
        if name not in self.active_modules:
            logger.info(f"Module {name} is not active")
            return False

        try:
            # Remove from active modules
            del self.active_modules[name]
            self.available_modules[name]["status"] = "available"

            logger.info(f"✗ Unloaded module: {name}")
            return True

        except Exception as exc:
            logger.info(f"✗ Failed to unload module {name}: {exc}")
            return False

    def find_modules_for_capability(self, capability: str) -> List[str]:
        """
        Find modules that can do a specific thing

        Args:
            capability: What we want to do

        Returns:
            List of module names that have this capability
        """
        return self.module_capabilities.get(capability, [])

    def auto_select_modules(self, required_capabilities: List[str]) -> List[str]:
        """
        Automatically select modules based on what needs to be done

        Args:
            required_capabilities: List of things we need to do

        Returns:
            List of module names to activate
        """
        selected_modules = set()

        for capability in required_capabilities:
            modules = self.find_modules_for_capability(capability)
            selected_modules.update(modules)

        return list(selected_modules)

    def get_active_commands(self) -> Dict[str, Any]:
        """
        Get all commands from active modules

        Returns:
            Dictionary of commands and their sources
        """
        commands = {}

        for module_name, module in self.active_modules.items():
            # Get all functions from the module
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if not name.startswith('_'):
                    commands[f"{module_name}.{name}"] = {
                        "module": module_name,
                        "function": name,
                        "description": obj.__doc__ or "No description"
                    }

        return commands

    def generate_help(self) -> str:
        """
        Generate help text showing all available commands
        Reading level: High school student
        """
        help_text = "# Available Commands\n\n"
        help_text += "These are the commands you can use right now:\n\n"

        # Get active commands
        commands = self.get_active_commands()

        # Group by module
        module_commands = {}
        for full_command, info in commands.items():
            module = info["module"]
            if module not in module_commands:
                module_commands[module] = []
            module_commands[module].append(info)

        # Generate help for each module
        for module, cmd_list in module_commands.items():
            help_text += f"## {module}\n"
            help_text += f"{self.available_modules[module]['description']}\n\n"
            help_text += "**Commands:**\n"
            for cmd in cmd_list:
                help_text += f"  - `{cmd['function']}` - {cmd['description']}\n"
            help_text += "\n"

        # Add system commands
        help_text += "## System Commands\n"
        help_text += "**Module Management:**\n"
        help_text += "  - `/modules list` - Show all modules\n"
        help_text += "  - `/modules load <name>` - Load a module\n"
        help_text += "  - `/modules unload <name>` - Unload a module\n"
        help_text += "  - `/modules capabilities <name>` - See what a module can do\n"
        help_text += "  - `/modules find <capability>` - Find modules for a task\n"
        help_text += "\n"

        help_text += "**General:**\n"
        help_text += "  - `/help` - Show this help\n"
        help_text += "  - `/status` - Show system status\n"

        return help_text

    def get_module_status(self) -> Dict[str, Any]:
        """
        Get status of all modules

        Returns:
            Status information for all modules
        """
        status = {
            "total_available": len(self.available_modules),
            "total_active": len(self.active_modules),
            "modules": {}
        }

        for name, info in self.available_modules.items():
            status["modules"][name] = {
                "description": info["description"],
                "status": info["status"],
                "capabilities": info["capabilities"]
            }

        return status

# Initialize for easy import
module_manager = ModuleManager()

if __name__ == "__main__":
    logger.info("Module Manager")
    logger.info("Manages dynamic module coupling/decoupling")
