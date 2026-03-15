"""
Module Compiler Adapter for Murphy System Runtime

Integrates the Module Compiler System for analyzing, compiling, and managing modules.

Capabilities:
- Static code analysis (no execution)
- Capability extraction with I/O schemas
- Determinism classification
- Failure mode detection
- Sandbox profile generation
- Module registry management
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import from module_compiler
try:
    from module_compiler.compiler import ModuleCompiler
    from module_compiler.models.module_spec import (
        Capability,
        DeterminismLevel,
        FailureMode,
        FailureSeverity,
        ModuleSpec,
        ResourceProfile,
        SandboxProfile,
    )
    from module_compiler.registry.module_registry import ModuleRegistry
    MODULE_COMPILER_AVAILABLE = True
except ImportError:
    MODULE_COMPILER_AVAILABLE = False

    # Fallback classes
    class DeterminismLevel:
        """Determinism level."""
        DETERMINISTIC = "deterministic"
        PROBABILISTIC = "probabilistic"
        EXTERNAL_STATE = "external_state"

    class FailureSeverity:
        """Failure severity."""
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"


class ModuleCompilerAdapter:
    """
    Adapter for Module Compiler integration with SystemIntegrator.

    Provides:
    - Static code analysis without execution
    - Capability extraction with I/O schemas
    - Determinism classification
    - Failure mode detection
    - Sandbox profile generation
    - Module registry management
    """

    def __init__(self):
        """Initialize module compiler adapter"""
        self.enabled = MODULE_COMPILER_AVAILABLE
        self.compiler = ModuleCompiler() if self.enabled else None
        self.registry = ModuleRegistry() if self.enabled else None
        self.compiled_modules: Dict[str, Dict[str, Any]] = {}
        self.analysis_history: List[Dict[str, Any]] = []

        # Metrics
        self.modules_analyzed = 0
        self.capabilities_extracted = 0
        self.failure_modes_detected = 0

    def compile_module(self,
                      source_path: str,
                      requested_capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Compile a Python module into a module specification.

        Args:
            source_path: Path to Python module file or directory
            requested_capabilities: Specific capabilities to focus on

        Returns:
            Dictionary with module specification
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "Module compiler not available",
                "source_path": source_path
            }

        try:
            # Compile the module
            if requested_capabilities:
                spec = self.compiler.compile_module(source_path, requested_capabilities)
            else:
                spec = self.compiler.compile_module(source_path)

            # Convert to dict
            result = self._spec_to_dict(spec)
            result["success"] = True
            result["source_path"] = source_path

            # Update metrics
            self.modules_analyzed += 1
            self.capabilities_extracted += len(spec.capabilities)
            self.failure_modes_detected += sum(
                len(cap.failure_modes) for cap in spec.capabilities
            )

            # Store in registry (if method exists)
            if self.registry and hasattr(self.registry, 'register_module'):
                try:
                    self.registry.register_module(spec)
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    pass  # Registry registration is optional

            # Store compiled module
            self.compiled_modules[spec.module_id] = result

            # Log analysis
            self._log_analysis(source_path, spec)

            return result

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "source_path": source_path
            }

    def compile_directory(self,
                         directory_path: str,
                         recursive: bool = True) -> Dict[str, Any]:
        """
        Compile all modules in a directory.

        Args:
            directory_path: Path to directory
            recursive: Whether to search subdirectories

        Returns:
            Dictionary with compilation results
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "Module compiler not available",
                "directory_path": directory_path
            }

        try:
            import glob

            # Find Python files (recursive if requested)
            if recursive:
                pattern = os.path.join(directory_path, "**", "*.py")
                python_files = glob.glob(pattern, recursive=True)
            else:
                pattern = os.path.join(directory_path, "*.py")
                python_files = glob.glob(pattern)

            # Compile each file
            specs = []
            for file_path in python_files:
                # Skip __init__.py and test files
                if file_path.endswith('__init__.py') or 'test' in file_path.lower():
                    continue

                try:
                    spec = self.compiler.compile_module(file_path)
                    specs.append(spec)
                except Exception as exc:
                    # Continue with other files even if one fails
                    logger.debug("Suppressed exception: %s", exc)
                    continue

            # Convert all specs to dicts
            results = []
            for spec in specs:
                result = self._spec_to_dict(spec)
                result["success"] = True
                result["source_path"] = spec.source_path
                results.append(result)

                # Update metrics
                self.modules_analyzed += 1
                self.capabilities_extracted += len(spec.capabilities)
                self.failure_modes_detected += sum(
                    len(cap.failure_modes) for cap in spec.capabilities
                )

                # Store in registry (if method exists)
                if self.registry and hasattr(self.registry, 'register_module'):
                    try:
                        self.registry.register_module(spec)
                    except Exception as exc:
                        logger.debug("Suppressed exception: %s", exc)
                        pass  # Registry registration is optional

                self.compiled_modules[spec.module_id] = result

            return {
                "success": True,
                "directory_path": directory_path,
                "modules_compiled": len(results),
                "results": results
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "directory_path": directory_path
            }

    def get_compiled_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a compiled module by ID.

        Args:
            module_id: Module identifier

        Returns:
            Module specification or None
        """
        return self.compiled_modules.get(module_id)

    def get_all_compiled_modules(self) -> List[Dict[str, Any]]:
        """
        Get all compiled modules.

        Returns:
            List of module specifications
        """
        return list(self.compiled_modules.values())

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
        if not self.enabled:
            return []

        results = []

        for module in self.compiled_modules.values():
            match = True

            # Filter by capability name
            if capability_name:
                capabilities = module.get("capabilities", [])
                if not any(
                    cap.get("name") == capability_name or capability_name.lower() in cap.get("name", "").lower()
                    for cap in capabilities
                ):
                    match = False

            # Filter by exact determinism
            if determinism and match:
                capabilities = module.get("capabilities", [])
                if not any(
                    cap.get("determinism") == determinism
                    for cap in capabilities
                ):
                    match = False

            # Filter by minimum determinism level
            if min_determinism and match:
                determinism_order = [
                    "deterministic",
                    "probabilistic",
                    "external_state"
                ]
                min_level = determinism_order.index(min_determinism)
                capabilities = module.get("capabilities", [])

                has_min = False
                for cap in capabilities:
                    cap_level = cap.get("determinism", "external_state")
                    if cap_level in determinism_order:
                        if determinism_order.index(cap_level) <= min_level:
                            has_min = True
                            break

                if not has_min:
                    match = False

            if match:
                results.append(module)

        return results

    def get_module_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about compiled modules.

        Returns:
            Dictionary with statistics
        """
        if not self.enabled:
            return {
                "enabled": False,
                "message": "Module compiler not available"
            }

        # Count capabilities by determinism level
        determinism_counts = {
            "deterministic": 0,
            "probabilistic": 0,
            "external_state": 0
        }

        # Count failure modes by severity
        severity_counts = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0
        }

        for module in self.compiled_modules.values():
            for cap in module.get("capabilities", []):
                # Count determinism
                det = cap.get("determinism", "external_state")
                determinism_counts[det] = determinism_counts.get(det, 0) + 1

                # Count failure modes
                for fm in cap.get("failure_modes", []):
                    sev = fm.get("severity", "low")
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "enabled": True,
            "modules_analyzed": self.modules_analyzed,
            "capabilities_extracted": self.capabilities_extracted,
            "failure_modes_detected": self.failure_modes_detected,
            "capabilities_by_determinism": determinism_counts,
            "failure_modes_by_severity": severity_counts,
            "analysis_history_count": len(self.analysis_history)
        }

    def _spec_to_dict(self, spec: Any) -> Dict[str, Any]:
        """Convert ModuleSpec to dictionary"""
        return {
            "module_id": spec.module_id,
            "source_path": spec.source_path,
            "version_hash": spec.version_hash,
            "module_name": os.path.basename(spec.source_path).replace('.py', ''),
            "capabilities": [
                self._capability_to_dict(cap) for cap in spec.capabilities
            ],
            "dependencies": spec.dependencies,
            "build_steps": spec.build_steps,
            "sandbox_profile": self._sandbox_profile_to_dict(spec.sandbox_profile) if spec.sandbox_profile else None,
            "verification_checks": spec.verification_checks,
            "verification_status": spec.verification_status,
            "uncertainty_flags": spec.uncertainty_flags,
            "requires_manual_review": spec.requires_manual_review,
            "is_partial": spec.is_partial,
            "compiled_at": spec.compiled_at,
            "compiler_version": spec.compiler_version
        }

    def _capability_to_dict(self, cap: Any) -> Dict[str, Any]:
        """Convert Capability to dictionary"""
        return {
            "name": cap.name,
            "description": cap.description,
            "input_schema": cap.input_schema,
            "output_schema": cap.output_schema,
            "determinism": cap.determinism.value if hasattr(cap.determinism, 'value') else str(cap.determinism),
            "resource_profile": self._resource_profile_to_dict(cap.resource_profile) if cap.resource_profile else None,
            "failure_modes": [
                self._failure_mode_to_dict(fm) for fm in cap.failure_modes
            ],
            "tags": cap.tags if hasattr(cap, 'tags') else []
        }

    def _failure_mode_to_dict(self, fm: Any) -> Dict[str, Any]:
        """Convert FailureMode to dictionary"""
        return {
            "type": fm.type,
            "severity": fm.severity.value if hasattr(fm.severity, 'value') else str(fm.severity),
            "description": fm.description,
            "mitigation": fm.mitigation,
            "probability": fm.probability
        }

    def _resource_profile_to_dict(self, rp: Any) -> Dict[str, Any]:
        """Convert ResourceProfile to dictionary"""
        return {
            "cpu_limit": rp.cpu_limit,
            "memory_limit": rp.memory_limit,
            "disk_limit": rp.disk_limit,
            "timeout_seconds": rp.timeout_seconds,
            "network_required": rp.network_required,
            "gpu_required": rp.gpu_required
        }

    def _sandbox_profile_to_dict(self, sp: Any) -> Dict[str, Any]:
        """Convert SandboxProfile to dictionary"""
        return {
            "base_image": sp.base_image,
            "read_only_root": sp.read_only_root,
            "network_enabled": sp.network_enabled,
            "gpu_enabled": sp.gpu_enabled,
            "privileged": sp.privileged,
            "cpu_limit": sp.cpu_limit,
            "memory_limit": sp.memory_limit,
            "disk_limit": sp.disk_limit,
            "mounts": sp.mounts,
            "allowed_env_vars": sp.allowed_env_vars,
            "capabilities": sp.capabilities
        }

    def _log_analysis(self, source_path: str, spec: Any):
        """Log analysis for tracking"""
        self.analysis_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_path": source_path,
            "module_id": spec.module_id,
            "module_name": os.path.basename(spec.source_path).replace('.py', ''),
            "capabilities_count": len(spec.capabilities),
            "requires_manual_review": spec.requires_manual_review
        })

    def get_analysis_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get analysis history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of analysis entries
        """
        return self.analysis_history[-limit:]


# Factory function
def create_module_compiler_adapter() -> ModuleCompilerAdapter:
    """Create and configure module compiler adapter"""
    return ModuleCompilerAdapter()
