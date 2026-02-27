"""
Murphy System — Integration Mapper
Owner: @arch-lead
Phase: 4 — Architecture & Integration Tools
Completion: 100%

Resolves GAP-011 (no integration point mapping).
Uses AST-based static analysis to identify integration points
across the Murphy System codebase.
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Set


class IntegrationMapper:
    """Maps integration points across the Murphy System codebase.

    Uses Python AST parsing to find HTTP calls, database operations,
    event emissions, and cross-module dependencies.

    Attributes:
        src_dir: Path to the source directory to analyze.
        integrations: Discovered integration points by component.
        dependencies: Import-based dependency graph.
    """

    def __init__(self, src_dir: str = "src"):
        self.src_dir = Path(src_dir)
        self.integrations: Dict[str, List[Dict]] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.components: Dict[str, Dict] = {}

    def analyze_codebase(self) -> Dict:
        """Analyze the entire codebase for integration points.

        Returns:
            Dictionary with components, integrations, and dependencies.
        """
        if not self.src_dir.exists():
            return {"error": f"Source directory not found: {self.src_dir}"}

        for py_file in self.src_dir.rglob("*.py"):
            self._analyze_file(py_file)

        return {
            "components": len(self.components),
            "integration_points": sum(
                len(ints) for ints in self.integrations.values()
            ),
            "dependencies": len(self.dependencies),
        }

    def _analyze_file(self, file_path: Path):
        """Analyze a single Python file for integration points."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            tree = ast.parse(code)
            component_name = file_path.stem

            # Extract classes
            classes = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
            ]

            # Extract imports
            imports = self._extract_imports(tree)

            self.components[component_name] = {
                "file": str(file_path),
                "classes": classes,
                "imports": imports,
            }
            self.dependencies[component_name] = set(imports)

            # Find integration points
            self._find_integrations(tree, component_name, file_path)

        except (SyntaxError, UnicodeDecodeError):
            pass  # Skip unparseable files

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all import module names from an AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _find_integrations(
        self, tree: ast.AST, component_name: str, file_path: Path
    ):
        """Find integration points in an AST."""
        if component_name not in self.integrations:
            self.integrations[component_name] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self._check_call_integration(node, component_name)

    def _check_call_integration(self, node: ast.Call, component_name: str):
        """Check if a function call is an integration point."""
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr

            # HTTP integration patterns
            if method in ("get", "post", "put", "delete", "patch"):
                self.integrations[component_name].append({
                    "type": "HTTP",
                    "method": method.upper(),
                })

            # Database patterns
            elif method in ("execute", "fetchall", "fetchone", "commit", "rollback"):
                self.integrations[component_name].append({
                    "type": "Database",
                    "method": method,
                })

            # Event patterns
            elif method in ("emit", "publish", "send_event", "dispatch"):
                self.integrations[component_name].append({
                    "type": "Event",
                    "method": method,
                })

            # Queue patterns
            elif method in ("enqueue", "dequeue", "push", "pop"):
                self.integrations[component_name].append({
                    "type": "Queue",
                    "method": method,
                })

    def get_integration_map(self) -> Dict:
        """Generate the complete integration map.

        Returns:
            Dictionary with all components and their integration points.
        """
        return {
            "components": list(self.integrations.keys()),
            "total_components": len(self.components),
            "integrations": {
                k: v for k, v in self.integrations.items() if v
            },
            "integration_types": self._get_type_summary(),
        }

    def _get_type_summary(self) -> Dict[str, int]:
        """Summarize integration points by type."""
        types: Dict[str, int] = {}
        for ints in self.integrations.values():
            for integration in ints:
                itype = integration["type"]
                types[itype] = types.get(itype, 0) + 1
        return types

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the dependency graph as adjacency list.

        Returns:
            Dictionary mapping component names to their dependencies.
        """
        return {k: list(v) for k, v in self.dependencies.items()}

    def find_components_by_integration_type(self, integration_type: str) -> List[str]:
        """Find all components that have a specific integration type.

        Args:
            integration_type: Type to search for (HTTP, Database, Event, Queue).

        Returns:
            List of component names.
        """
        return [
            comp
            for comp, ints in self.integrations.items()
            if any(i["type"] == integration_type for i in ints)
        ]

    def save_integration_map(self, output_file: str = "integration_map.json") -> str:
        """Save the integration map to a JSON file.

        Args:
            output_file: Path for the output file.

        Returns:
            Path to the saved file.
        """
        integration_map = self.get_integration_map()

        with open(output_file, "w") as f:
            json.dump(integration_map, f, indent=2, default=str)

        return output_file
