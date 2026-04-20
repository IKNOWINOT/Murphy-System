"""
Module Registry — discovers and registers all available modules in src/.

Each module gets a :class:`ModuleDescriptor` capturing name, version, status
(loaded/error/disabled), capabilities, and dependencies.  The registry also
auto-discovers modules by scanning ``src/`` for Python files that match known
naming patterns (controllers, engines, adapters, etc.).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class ModuleStatus(str, Enum):
    """Lifecycle status of a registered module."""

    LOADED = "loaded"
    ERROR = "error"
    DISABLED = "disabled"
    AVAILABLE = "available"


# ---------------------------------------------------------------------------
# ModuleDescriptor
# ---------------------------------------------------------------------------


@dataclass
class ModuleDescriptor:
    """Describes a single registered module.

    Attributes:
        name: Unique module identifier (e.g. ``"llm_controller"``).
        version: Semver string; defaults to ``"1.0.0"``.
        status: Current lifecycle status.
        capabilities: Free-form capability tags (e.g. ``"llm_routing"``).
        dependencies: Names of other modules this module requires.
        error: Error message when *status* is :attr:`ModuleStatus.ERROR`.
        instance: Loaded module object, if available.
    """

    name: str
    version: str = "1.0.0"
    status: ModuleStatus = ModuleStatus.AVAILABLE
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    error: Optional[str] = None
    instance: Optional[Any] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# ModuleRegistry
# ---------------------------------------------------------------------------

# Patterns whose presence in a module filename indicate a "known" module type.
_KNOWN_PATTERNS = (
    "controller",
    "engine",
    "adapter",
    "integrat",
    "orchestrat",
    "swarm",
    "validator",
    "integrator",
    "scheduler",
    "manager",
    "gateway",
    "hub",
    "router",
    "pipeline",
    "activation",
    "introspection",
    "builder",
)

_DEFAULT_CAPABILITIES: Dict[str, List[str]] = {
    "llm_controller": ["llm_routing", "model_selection", "deepinfra_api"],
    "llm_integration_layer": ["llm_routing", "deepinfra_key_rotation", "domain_routing"],
    "llm_output_validator": ["output_validation", "schema_compliance", "injection_detection"],
    "domain_engine": ["domain_inference", "domain_gate", "classification"],
    "feedback_integrator": ["feedback_learning", "state_uncertainty", "closed_loop"],
    "true_swarm_system": ["swarm_coordination", "agent_swarm"],
    "advanced_swarm_system": ["swarm_coordination", "advanced_agents"],
    "durable_swarm_orchestrator": ["swarm_orchestration", "durable_execution"],
    "enhanced_local_llm": ["local_llm_fallback", "pattern_matching"],
    "system_integrator": ["central_integration", "subsystem_wiring"],
    "universal_integration_adapter": ["integration_adapter", "module_wiring"],
    "state_schema": ["typed_state", "state_vector"],
    "automation_integration_hub": ["event_routing", "module_phase"],
}


class ModuleRegistry:
    """Discovers and registers all available modules in ``src/``.

    Usage::

        registry = ModuleRegistry()
        registry.discover()
        registry.load("llm_controller")
        logger.info(registry.get_status())
    """

    def __init__(self, src_root: Optional[Path] = None) -> None:
        self._src_root: Path = src_root or (
            Path(__file__).resolve().parent
        )
        self._modules: Dict[str, ModuleDescriptor] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> List[str]:
        """Scan *src_root* for modules matching known patterns and register them.

        Returns a list of newly discovered module names.
        """
        discovered: List[str] = []
        try:
            for path in sorted(self._src_root.rglob("*.py")):
                if path.name.startswith("_"):
                    continue
                stem = path.stem
                if not any(pat in stem.lower() for pat in _KNOWN_PATTERNS):
                    continue
                if stem not in self._modules:
                    caps = list(_DEFAULT_CAPABILITIES.get(stem, []))
                    descriptor = ModuleDescriptor(
                        name=stem,
                        capabilities=caps,
                        status=ModuleStatus.AVAILABLE,
                    )
                    self._modules[stem] = descriptor
                    discovered.append(stem)
        except Exception as exc:
            logger.warning("Module discovery encountered an error: %s", exc)
        logger.info("ModuleRegistry.discover(): found %d new module(s)", len(discovered))
        return discovered

    def load(self, module_name: str) -> bool:
        """Import and cache the module identified by *module_name*.

        Returns ``True`` on success, ``False`` on failure.  The descriptor's
        status is updated accordingly.
        """
        descriptor = self._modules.get(module_name)
        if descriptor is None:
            # Auto-register before attempting load
            descriptor = ModuleDescriptor(name=module_name)
            self._modules[module_name] = descriptor

        if descriptor.status == ModuleStatus.LOADED and descriptor.instance is not None:
            return True

        import_path = f"src.{module_name}"
        try:
            mod = importlib.import_module(import_path)
            descriptor.instance = mod
            descriptor.status = ModuleStatus.LOADED
            descriptor.error = None
            logger.info("ModuleRegistry: loaded '%s'", module_name)
            return True
        except Exception as exc:
            descriptor.status = ModuleStatus.ERROR
            descriptor.error = str(exc)
            logger.warning("ModuleRegistry: failed to load '%s': %s", module_name, exc)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return a summary dict of all registered modules."""
        modules_out: Dict[str, Any] = {}
        for name, desc in self._modules.items():
            modules_out[name] = {
                "version": desc.version,
                "status": desc.status.value,
                "capabilities": desc.capabilities,
                "dependencies": desc.dependencies,
                "error": desc.error,
            }
        loaded_count = sum(
            1 for d in self._modules.values() if d.status == ModuleStatus.LOADED
        )
        return {
            "total_registered": len(self._modules),
            "total_loaded": loaded_count,
            "modules": modules_out,
        }

    def get_module_status(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Return status dict for a single module, or ``None`` if unknown."""
        desc = self._modules.get(module_name)
        if desc is None:
            return None
        return {
            "name": desc.name,
            "version": desc.version,
            "status": desc.status.value,
            "capabilities": desc.capabilities,
            "dependencies": desc.dependencies,
            "error": desc.error,
        }

    def list_available(self) -> List[str]:
        """Return names of all registered modules."""
        return list(self._modules.keys())

    def get_capabilities(self, module_name: Optional[str] = None) -> Dict[str, List[str]]:
        """Return capability → [module_name] mapping.

        If *module_name* is given, return only that module's capabilities.
        """
        if module_name is not None:
            desc = self._modules.get(module_name)
            if desc is None:
                return {}
            return {module_name: desc.capabilities}

        caps: Dict[str, List[str]] = {}
        for name, desc in self._modules.items():
            for cap in desc.capabilities:
                caps.setdefault(cap, []).append(name)
        return caps

    def register(
        self,
        name: str,
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> ModuleDescriptor:
        """Manually register a module descriptor."""
        descriptor = ModuleDescriptor(
            name=name,
            version=version,
            capabilities=capabilities or [],
            dependencies=dependencies or [],
            status=ModuleStatus.AVAILABLE,
        )
        self._modules[name] = descriptor
        return descriptor

    def get_instance(self, module_name: str) -> Optional[Any]:
        """Return the loaded module object for *module_name*, or ``None``."""
        desc = self._modules.get(module_name)
        if desc is None:
            return None
        return desc.instance


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

module_registry = ModuleRegistry()
