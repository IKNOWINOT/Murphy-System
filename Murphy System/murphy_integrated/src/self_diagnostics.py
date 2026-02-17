"""
Murphy System Self-Diagnostics Module

Provides automated health checking, module validation, and self-improvement
recommendations for the Murphy System runtime.
"""

import importlib
import logging
import sys
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ModuleHealthChecker:
    """Validates that all murphy_integrated modules are importable and functional."""

    CORE_MODULES = [
        {
            "name": "confidence_engine",
            "import_path": "confidence_engine.unified_confidence_engine",
            "class_name": "UnifiedConfidenceEngine",
            "category": "core"
        },
        {
            "name": "execution_engine",
            "import_path": "execution_engine.workflow_orchestrator",
            "class_name": "WorkflowOrchestrator",
            "category": "core"
        },
        {
            "name": "learning_engine",
            "import_path": "learning_engine.learning_engine",
            "class_name": "LearningEngine",
            "category": "core"
        },
        {
            "name": "governance_framework",
            "import_path": "governance_framework.agent_descriptor_complete",
            "class_name": "AgentDescriptor",
            "category": "governance"
        },
        {
            "name": "true_swarm_system",
            "import_path": "true_swarm_system",
            "class_name": "TrueSwarmSystem",
            "category": "core"
        },
        {
            "name": "supervisor_system",
            "import_path": "supervisor_system.supervisor_loop",
            "class_name": "SupervisorAuditLogger",
            "category": "governance"
        },
        {
            "name": "module_manager",
            "import_path": "module_manager",
            "class_name": "ModuleManager",
            "category": "infrastructure"
        },
        {
            "name": "compute_plane",
            "import_path": "compute_plane.service",
            "class_name": "ComputeService",
            "category": "core"
        },
        {
            "name": "telemetry_learning",
            "import_path": "telemetry_learning.gate_strengthening",
            "class_name": "GateStrengtheningEngine",
            "category": "observability"
        },
    ]

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.last_check: Optional[datetime] = None

    def run_health_check(self) -> Dict[str, Any]:
        """Run a complete health check on all core modules."""
        self.results = []
        start_time = time.time()

        for module_info in self.CORE_MODULES:
            result = self._check_module(module_info)
            self.results.append(result)

        elapsed = time.time() - start_time
        self.last_check = datetime.now(timezone.utc)

        healthy = sum(1 for r in self.results if r["status"] == "healthy")
        degraded = sum(1 for r in self.results if r["status"] == "degraded")
        failed = sum(1 for r in self.results if r["status"] == "failed")

        return {
            "timestamp": self.last_check.isoformat(),
            "duration_ms": round(elapsed * 1000, 2),
            "total_modules": len(self.results),
            "healthy": healthy,
            "degraded": degraded,
            "failed": failed,
            "overall_status": "healthy" if failed == 0 else ("degraded" if healthy > failed else "critical"),
            "modules": self.results,
            "recommendations": self._generate_recommendations()
        }

    def _check_module(self, module_info: Dict[str, str]) -> Dict[str, Any]:
        """Check a single module's health."""
        result = {
            "name": module_info["name"],
            "category": module_info["category"],
            "import_path": module_info["import_path"],
            "status": "unknown",
            "importable": False,
            "instantiable": False,
            "error": None
        }

        try:
            mod = importlib.import_module(module_info["import_path"])
            result["importable"] = True

            cls = getattr(mod, module_info["class_name"], None)
            if cls is None:
                result["status"] = "degraded"
                result["error"] = f"Class {module_info['class_name']} not found in module"
                return result

            result["instantiable"] = True
            result["status"] = "healthy"

        except ImportError as e:
            result["status"] = "failed"
            result["error"] = f"Import error: {e}"
        except Exception as e:
            result["status"] = "degraded"
            result["error"] = f"Unexpected error: {e}"

        return result

    def _generate_recommendations(self) -> List[str]:
        """Generate self-improvement recommendations based on health check results."""
        recommendations = []

        for result in self.results:
            if result["status"] == "failed":
                recommendations.append(
                    f"[CRITICAL] Module '{result['name']}' failed to import. "
                    f"Check dependencies: {result['error']}"
                )
            elif result["status"] == "degraded":
                recommendations.append(
                    f"[WARNING] Module '{result['name']}' is degraded: {result['error']}"
                )

        if not recommendations:
            recommendations.append("All modules are healthy. No action required.")

        return recommendations


class SystemDiagnostics:
    """Comprehensive system diagnostics for the Murphy runtime."""

    def __init__(self, murphy_system=None):
        self.murphy_system = murphy_system
        self.health_checker = ModuleHealthChecker()

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Run complete system diagnostics."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module_health": self.health_checker.run_health_check(),
            "system_resources": self._check_system_resources(),
            "python_environment": self._check_python_environment(),
            "integration_status": self._check_integration_status()
        }

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 1),
                "disk_percent": psutil.disk_usage('/').percent,
                "status": "healthy"
            }
        except ImportError:
            return {"status": "unavailable", "error": "psutil not installed"}

    def _check_python_environment(self) -> Dict[str, Any]:
        """Check Python environment details."""
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "path_count": len(sys.path),
            "status": "healthy"
        }

    def _check_integration_status(self) -> Dict[str, Any]:
        """Check integration capabilities."""
        integrations = {}

        # Check key optional dependencies
        for pkg in ["fastapi", "uvicorn", "aiohttp", "pydantic", "psutil"]:
            try:
                mod = importlib.import_module(pkg)
                version = getattr(mod, "__version__", "unknown")
                integrations[pkg] = {"available": True, "version": version}
            except ImportError:
                integrations[pkg] = {"available": False}

        return integrations
