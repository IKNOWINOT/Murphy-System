"""
Capability Map Inventory for Murphy System Runtime

This module provides a repository-wide capability map that scans, catalogs,
and analyses all modules in the src/ directory, including:
- Module discovery and capability extraction
- Subsystem categorisation (execution, governance, delivery, etc.)
- Dependency edge detection from import statements
- Utilisation status based on runtime wiring
- Gap analysis between available capabilities and execution wiring
- Remediation sequence generation for underutilised modules
- Thread-safe access for concurrent consumers
"""

import ast
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionCriticality(str, Enum):
    """How critical a module is to runtime execution."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class UtilizationStatus(str, Enum):
    """Whether a module is actively wired into the runtime."""
    ACTIVE = "ACTIVE"
    PARTIAL = "PARTIAL"
    UNUSED = "UNUSED"


# ------------------------------------------------------------------
# Subsystem keyword mapping
# ------------------------------------------------------------------

_SUBSYSTEM_KEYWORDS: Dict[str, List[str]] = {
    "execution": ["executor", "execution", "task_executor", "runtime", "modular_runtime"],
    "governance": ["authority", "gate", "governance", "constraint", "verification", "audit"],
    "delivery": ["delivery", "response_composer", "response_formatter", "document_processor"],
    "persistence": ["persistence", "memory", "state_machine", "artifact"],
    "learning": ["learning", "self_improvement", "confidence", "knowledge_gap", "calibration"],
    "security": ["security", "secure_key", "safe_llm", "input_validation"],
    "telemetry": ["telemetry", "logging", "statistics", "slo_tracker", "metrics", "operational_slo"],
    "swarm": ["swarm", "domain_swarm"],
    "compute": ["compute", "probabilistic", "neuro_symbolic", "reasoning"],
    "integration": [
        "integration", "system_integrator", "system_builder", "librarian",
        "module_manager", "module_compiler", "unified_mfgc",
    ],
    "adapter": [
        "adapter", "bridge", "mfgc_adapter", "llm_integration", "llm_controller",
        "local_llm", "local_model", "deepinfra", "mock_compatible",
    ],
}

# Modules considered HIGH criticality when active
_HIGH_CRITICALITY = {
    "module_manager", "modular_runtime", "gate_execution_wiring",
    "persistence_manager", "self_improvement_engine", "system_integrator",
    "event_backbone", "authority_gate",
}


@dataclass
class ModuleCapability:
    """Records the capability profile of a single module."""
    module_path: str
    subsystem: str
    runtime_role: str
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    governance_boundary: str = "standard"
    execution_criticality: str = ExecutionCriticality.MEDIUM.value
    utilization_status: str = UtilizationStatus.UNUSED.value


class CapabilityMap:
    """Repository-wide capability map for the Murphy System.

    Scans the src/ directory, catalogs every module's capabilities,
    dependencies, and utilisation status, then provides gap analysis
    and remediation sequencing.
    """

    # ------------------------------------------------------------------
    # Static compute-plane capability registry
    # ------------------------------------------------------------------

    #: Map of compute language → (status, notes)
    COMPUTE_CAPABILITY_MAP: Dict[str, Dict[str, str]] = {
        "sympy": {
            "status": "available",
            "notes": "Symbolic computation via sympy (installed by default).",
        },
        "lp": {
            "status": "available",
            "notes": (
                "Linear programming via scipy.optimize.linprog. "
                "Requires 'scipy' (pip install scipy). "
                "Pass objective coefficients via request.metadata['c']."
            ),
        },
        "sat": {
            "status": "planned",
            "notes": (
                "SAT solving is on the roadmap. "
                "A future release will wire python-sat or pysat. "
                "Current status: UNSUPPORTED."
            ),
        },
        "wolfram": {
            "status": "planned",
            "notes": (
                "Wolfram Engine integration is on the roadmap. "
                "Current status: UNSUPPORTED."
            ),
        },
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._modules: Dict[str, ModuleCapability] = {}
        self._runtime_imports: set = set()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan(self, base_path: str) -> None:
        """Scan the src/ directory under *base_path* and build the map."""
        src_dir = os.path.join(base_path, "src")
        if not os.path.isdir(src_dir):
            logger.warning("src directory not found at %s", src_dir)
            return

        # Detect runtime imports first
        self._runtime_imports = _detect_runtime_imports(base_path)

        modules: Dict[str, ModuleCapability] = {}
        for dirpath, _dirnames, filenames in os.walk(src_dir):
            for fname in sorted(filenames):
                if not fname.endswith(".py") or fname.startswith("__"):
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, base_path)
                mod = self._analyse_module(full, rel)
                modules[rel] = mod

        with self._lock:
            self._modules = modules

        logger.info("Capability map scanned %d modules", len(modules))

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_module(self, path: str) -> Optional[ModuleCapability]:
        """Return capability info for a single module, or None."""
        with self._lock:
            return self._modules.get(path)

    def get_subsystem(self, subsystem: str) -> List[ModuleCapability]:
        """Return all modules belonging to *subsystem*."""
        with self._lock:
            return [m for m in self._modules.values() if m.subsystem == subsystem]

    def get_underutilized(self) -> List[ModuleCapability]:
        """Return modules with PARTIAL or UNUSED utilisation status."""
        with self._lock:
            return [
                m for m in self._modules.values()
                if m.utilization_status in (UtilizationStatus.PARTIAL.value, UtilizationStatus.UNUSED.value)
            ]

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Return a dict mapping each module path to its dependency edges."""
        with self._lock:
            return {path: list(mod.dependencies) for path, mod in self._modules.items()}

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------

    def get_gap_analysis(self) -> Dict[str, Any]:
        """Analyse gaps between available capabilities and execution wiring."""
        with self._lock:
            modules = list(self._modules.values())

        total = len(modules)
        active = sum(1 for m in modules if m.utilization_status == UtilizationStatus.ACTIVE.value)
        partial = sum(1 for m in modules if m.utilization_status == UtilizationStatus.PARTIAL.value)
        unused = sum(1 for m in modules if m.utilization_status == UtilizationStatus.UNUSED.value)

        subsystem_coverage: Dict[str, Dict[str, int]] = {}
        for m in modules:
            sub = m.subsystem
            if sub not in subsystem_coverage:
                subsystem_coverage[sub] = {"total": 0, "active": 0, "partial": 0, "unused": 0}
            subsystem_coverage[sub]["total"] += 1
            if m.utilization_status == UtilizationStatus.ACTIVE.value:
                subsystem_coverage[sub]["active"] += 1
            elif m.utilization_status == UtilizationStatus.PARTIAL.value:
                subsystem_coverage[sub]["partial"] += 1
            else:
                subsystem_coverage[sub]["unused"] += 1

        high_unused = [
            m.module_path for m in modules
            if m.execution_criticality == ExecutionCriticality.HIGH.value
            and m.utilization_status != UtilizationStatus.ACTIVE.value
        ]

        return {
            "total_modules": total,
            "active": active,
            "partial": partial,
            "unused": unused,
            "wiring_ratio": round(active / total, 4) if total else 0.0,
            "subsystem_coverage": subsystem_coverage,
            "high_criticality_unwired": high_unused,
        }

    # ------------------------------------------------------------------
    # Remediation sequence
    # ------------------------------------------------------------------

    def get_remediation_sequence(self) -> List[Dict[str, Any]]:
        """Return an ordered list of remediation actions for underutilised modules."""
        underutilised = self.get_underutilized()

        priority_order = {
            ExecutionCriticality.HIGH.value: 0,
            ExecutionCriticality.MEDIUM.value: 1,
            ExecutionCriticality.LOW.value: 2,
        }
        status_order = {
            UtilizationStatus.UNUSED.value: 0,
            UtilizationStatus.PARTIAL.value: 1,
        }

        underutilised.sort(
            key=lambda m: (
                priority_order.get(m.execution_criticality, 99),
                status_order.get(m.utilization_status, 99),
            )
        )

        sequence: List[Dict[str, Any]] = []
        for idx, mod in enumerate(underutilised, 1):
            action = "wire_into_runtime" if mod.utilization_status == UtilizationStatus.UNUSED.value else "complete_wiring"
            sequence.append({
                "order": idx,
                "module_path": mod.module_path,
                "subsystem": mod.subsystem,
                "criticality": mod.execution_criticality,
                "current_status": mod.utilization_status,
                "action": action,
                "description": f"{action.replace('_', ' ').title()} for {os.path.basename(mod.module_path)}",
            })

        return sequence

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall capability map status."""
        with self._lock:
            total = len(self._modules)
            subsystems = list({m.subsystem for m in self._modules.values()})
            active = sum(1 for m in self._modules.values() if m.utilization_status == UtilizationStatus.ACTIVE.value)
            partial = sum(1 for m in self._modules.values() if m.utilization_status == UtilizationStatus.PARTIAL.value)
            unused = sum(1 for m in self._modules.values() if m.utilization_status == UtilizationStatus.UNUSED.value)

        return {
            "total_modules": total,
            "subsystems": sorted(subsystems),
            "active_modules": active,
            "partial_modules": partial,
            "unused_modules": unused,
            "runtime_imports_detected": len(self._runtime_imports),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyse_module(self, full_path: str, rel_path: str) -> ModuleCapability:
        """Build a ModuleCapability for the file at *full_path*."""
        stem = os.path.splitext(os.path.basename(full_path))[0]

        # Parse source safely
        capabilities, dependencies = _extract_capabilities_and_deps(full_path)

        subsystem = _classify_subsystem(stem)
        criticality = (
            ExecutionCriticality.HIGH.value if stem in _HIGH_CRITICALITY
            else ExecutionCriticality.MEDIUM.value if subsystem in ("execution", "governance", "persistence")
            else ExecutionCriticality.LOW.value
        )
        utilization = _determine_utilization(stem, self._runtime_imports)
        governance = "elevated" if subsystem in ("governance", "security") else "standard"
        role = _infer_runtime_role(stem, subsystem)

        return ModuleCapability(
            module_path=rel_path,
            subsystem=subsystem,
            runtime_role=role,
            capabilities=capabilities,
            dependencies=dependencies,
            governance_boundary=governance,
            execution_criticality=criticality,
            utilization_status=utilization,
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _detect_runtime_imports(base_path: str) -> set:
    """Read the runtime file and return a set of src module stems it imports."""
    runtime_path = os.path.join(base_path, "murphy_system_1.0_runtime.py")
    stems: set = set()
    if not os.path.isfile(runtime_path):
        return stems
    try:
        with open(runtime_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                match = re.match(r"from\s+src\.(\w+)", line)
                if match:
                    stems.add(match.group(1))
    except OSError:
        logger.warning("Could not read runtime file at %s", runtime_path)
    return stems


def _extract_capabilities_and_deps(filepath: str):
    """Return (capabilities, dependencies) by parsing the source file."""
    capabilities: List[str] = []
    dependencies: List[str] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return capabilities, dependencies

    # AST-based extraction
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return capabilities, dependencies

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            capabilities.append(f"class:{node.name}")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        capabilities.append(f"method:{node.name}.{item.name}")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            # Top-level public functions
            if isinstance(node, ast.FunctionDef) and _is_top_level(node, tree):
                capabilities.append(f"function:{node.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("src."):
                dep = node.module.split(".")[1]
                if dep not in dependencies:
                    dependencies.append(dep)

    return capabilities, dependencies


def _is_top_level(node: ast.AST, tree: ast.Module) -> bool:
    """Return True if *node* is a direct child of the module body."""
    return node in tree.body


def _classify_subsystem(stem: str) -> str:
    """Map a module stem to a subsystem category."""
    for subsystem, keywords in _SUBSYSTEM_KEYWORDS.items():
        for kw in keywords:
            if kw in stem:
                return subsystem
    return "general"


def _determine_utilization(stem: str, runtime_imports: set) -> str:
    """Determine the utilisation status of a module."""
    if stem in runtime_imports:
        return UtilizationStatus.ACTIVE.value
    # Partial if the stem is a sub-word of any runtime import
    for imp in runtime_imports:
        if stem in imp or imp in stem:
            return UtilizationStatus.PARTIAL.value
    return UtilizationStatus.UNUSED.value


def _infer_runtime_role(stem: str, subsystem: str) -> str:
    """Infer a human-readable runtime role from the module name and subsystem."""
    role_map = {
        "execution": "task execution pipeline",
        "governance": "governance and authority gating",
        "delivery": "response delivery and formatting",
        "persistence": "state persistence and memory management",
        "learning": "learning and self-improvement feedback",
        "security": "security enforcement and key management",
        "telemetry": "observability and metrics collection",
        "swarm": "swarm intelligence coordination",
        "compute": "compute and reasoning layer",
        "integration": "system integration and module management",
        "adapter": "external system adaptation layer",
    }
    return role_map.get(subsystem, "general system component")
