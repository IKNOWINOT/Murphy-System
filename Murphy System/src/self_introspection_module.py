# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Self-Introspection Module for Murphy System.

Design Label: INTRO-001 — Self-Introspection Engine
Owner: Platform Engineering / Architecture

Provides Murphy System with full self-visibility into its own codebase:
  - AST-based scanning of every .py file under Murphy System/src/
  - Module dependency graph construction from import analysis
  - Complexity reporting (LOC, class/function counts, cyclomatic estimate)
  - Capability search across docstrings and function names
  - Health snapshot: missing imports, parse errors, circular dependencies

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Errors sanitised before logging (CWE-209).
  - File traversal restricted to the declared root_path (CWE-22).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input-validation constants                                         [CWE-20]
# ---------------------------------------------------------------------------

_PATH_COMPONENT_RE = re.compile(r"^[a-zA-Z0-9_.\- /\\:]{1,4096}$")
_MAX_CAPABILITY_QUERY_LEN: int = 500
_MAX_NODES: int = 10_000
_MAX_EDGES: int = 50_000
_MAX_SCAN_ERRORS: int = 5_000
_MAX_FILE_BYTES: int = 5 * 1024 * 1024  # 5 MB per file (CWE-400)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ModuleNode:
    """Represents a single Python module in the dependency graph."""

    module_name: str
    file_path: str
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    size_bytes: int = 0
    last_modified: str = ""
    docstring: str = ""
    parse_error: str = ""
    loc: int = 0  # lines of code (non-blank, non-comment)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "file_path": self.file_path,
            "classes": list(self.classes),
            "functions": list(self.functions),
            "imports": list(self.imports),
            "dependencies": list(self.dependencies),
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified,
            "docstring": self.docstring[:500] if self.docstring else "",
            "parse_error": self.parse_error,
            "loc": self.loc,
        }


@dataclass
class SystemGraph:
    """Full dependency graph of the Murphy System codebase."""

    nodes: Dict[str, ModuleNode] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    total_modules: int = 0
    total_classes: int = 0
    total_functions: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scan_errors: List[str] = field(default_factory=list)
    root_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [list(exc) for e in self.edges],
            "total_modules": self.total_modules,
            "total_classes": self.total_classes,
            "total_functions": self.total_functions,
            "generated_at": self.generated_at,
            "scan_errors": list(self.scan_errors),
            "root_path": self.root_path,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_module_name(file_path: str, root_path: str) -> str:
    """Convert a file path to a dotted module name relative to root_path."""
    rel = os.path.relpath(file_path, root_path)
    without_ext = os.path.splitext(rel)[0]
    return without_ext.replace(os.sep, ".").replace("/", ".")


def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    """Return an opaque error token; never leak raw exception details."""
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_loc(source: str) -> int:
    """Count non-blank, non-comment lines."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _estimate_cyclomatic(tree: ast.AST) -> int:
    """Rough cyclomatic complexity estimate: 1 + branching nodes."""
    branch_types = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.Assert, ast.comprehension,
    )
    return 1 + sum(1 for _ in ast.walk(tree) if isinstance(_, branch_types))


# ---------------------------------------------------------------------------
# Core Engine                                                      INTRO-001
# ---------------------------------------------------------------------------

class SelfIntrospectionEngine:
    """
    Runtime engine that gives Murphy System full self-visibility.

    Call ``scan_codebase(root_path)`` once to build a SystemGraph, then use
    the query helpers to navigate that graph.  All public methods are
    thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._graph: Optional[SystemGraph] = None
        self._scan_count: int = 0

    # ------------------------------------------------------------------
    # Primary scan
    # ------------------------------------------------------------------

    def scan_codebase(self, root_path: str) -> SystemGraph:
        """Walk root_path, parse every .py file, and build a SystemGraph.

        The resulting graph is cached in ``self._graph``.
        """
        # Path validation                                             [CWE-22]
        if not isinstance(root_path, str) or not root_path:
            raise ValueError("root_path must be a non-empty string")
        if not _PATH_COMPONENT_RE.match(root_path):
            raise ValueError("root_path contains invalid characters")
        abs_root = os.path.realpath(root_path)
        if not os.path.isdir(abs_root):
            raise ValueError(f"root_path is not a directory: {abs_root!r}")

        graph = SystemGraph(root_path=abs_root)

        for dirpath, _, filenames in os.walk(abs_root):
            # Restrict traversal to within abs_root              [CWE-22]
            if not os.path.realpath(dirpath).startswith(abs_root):
                continue
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                if len(graph.nodes) >= _MAX_NODES:
                    capped_append(
                        graph.scan_errors,
                        "MAX_NODES reached; scan truncated",
                        max_size=_MAX_SCAN_ERRORS,
                    )
                    break
                node = self._parse_file(fpath, abs_root)
                graph.nodes[node.module_name] = node

        # Build edges from import relationships
        self._build_edges(graph)

        # Aggregate counts
        graph.total_modules = len(graph.nodes)
        graph.total_classes = sum(len(n.classes) for n in graph.nodes.values())
        graph.total_functions = sum(len(n.functions) for n in graph.nodes.values())
        graph.generated_at = _ts()

        with self._lock:
            self._graph = graph
            self._scan_count += 1

        logger.info(
            "INTRO-001 scan complete: %d modules, %d classes, %d functions, %d edges",
            graph.total_modules,
            graph.total_classes,
            graph.total_functions,
            len(graph.edges),
        )
        return graph

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_module_dependency_graph(self) -> Dict[str, List[str]]:
        """Return adjacency list of import dependencies.

        ``{module_name: [imported_module, ...]}``
        """
        with self._lock:
            graph = self._graph
        if graph is None:
            return {}
        return {name: list(node.dependencies) for name, node in graph.nodes.items()}

    def get_complexity_report(self) -> Dict[str, Any]:
        """Return LOC, cyclomatic complexity estimates, and counts."""
        with self._lock:
            graph = self._graph
        if graph is None:
            return {"error": "codebase_not_scanned"}

        total_loc = sum(n.loc for n in graph.nodes.values())
        # Cyclomatic complexity is pre-estimated per module; sum and average
        cyc_values = [n.loc // 10 + 1 for n in graph.nodes.values()]  # rough heuristic
        avg_cyc = round(sum(cyc_values) / len(cyc_values), 2) if cyc_values else 0.0

        most_complex = sorted(
            graph.nodes.values(), key=lambda n: n.loc, reverse=True
        )[:10]

        return {
            "total_modules": graph.total_modules,
            "total_classes": graph.total_classes,
            "total_functions": graph.total_functions,
            "total_loc": total_loc,
            "avg_cyclomatic_estimate": avg_cyc,
            "largest_modules": [
                {"module": n.module_name, "loc": n.loc, "size_bytes": n.size_bytes}
                for n in most_complex
            ],
            "scan_errors": len(graph.scan_errors),
            "generated_at": graph.generated_at,
        }

    def find_module_for_capability(self, capability_description: str) -> List[ModuleNode]:
        """Keyword search across module docstrings, class names, and function names."""
        if not isinstance(capability_description, str):
            raise ValueError("capability_description must be a string")
        query = capability_description[:_MAX_CAPABILITY_QUERY_LEN].lower()
        keywords = [w for w in re.split(r"\W+", query) if len(w) >= 3]

        with self._lock:
            graph = self._graph
        if graph is None:
            return []

        results: List[ModuleNode] = []
        for node in graph.nodes.values():
            searchable = " ".join(
                [node.module_name, node.docstring]
                + node.classes
                + node.functions
            ).lower()
            if any(kw in searchable for kw in keywords):
                results.append(node)

        return results

    def get_health_snapshot(self) -> Dict[str, Any]:
        """Return modules with parse errors, missing imports, and circular deps."""
        with self._lock:
            graph = self._graph
        if graph is None:
            return {"error": "codebase_not_scanned"}

        errored = [
            {"module": n.module_name, "error": n.parse_error}
            for n in graph.nodes.values()
            if n.parse_error
        ]

        # Detect circular dependencies (DFS)
        circular = self._find_circular_deps(graph)

        # Modules that import something not in the graph (external or missing)
        internal_names = set(graph.nodes.keys())
        missing_imports: List[Dict[str, Any]] = []
        for node in graph.nodes.values():
            ext = [d for d in node.dependencies if d not in internal_names]
            if ext:
                missing_imports.append(
                    {"module": node.module_name, "external_imports": ext[:20]}
                )

        return {
            "parse_errors": errored,
            "circular_dependencies": circular,
            "modules_with_external_imports": missing_imports[:100],
            "total_modules": len(graph.nodes),
            "health_score": round(
                1.0 - (len(errored) / max(len(graph.nodes), 1)), 4
            ),
            "generated_at": _ts(),
        }

    def get_graph(self) -> Optional[SystemGraph]:
        """Return the last cached SystemGraph, or None if not yet scanned."""
        with self._lock:
            return self._graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_file(self, file_path: str, root_path: str) -> ModuleNode:
        """Parse a single .py file and return a ModuleNode."""
        module_name = _safe_module_name(file_path, root_path)
        node = ModuleNode(module_name=module_name, file_path=file_path)

        try:
            stat = os.stat(file_path)
            node.size_bytes = stat.st_size
            node.last_modified = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            if node.size_bytes > _MAX_FILE_BYTES:
                node.parse_error = "file_too_large"
                return node

            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()

            node.loc = _count_loc(source)
            tree = ast.parse(source, filename=file_path)

            # Module docstring
            node.docstring = ast.get_docstring(tree) or ""

            # Collect classes, functions, imports
            for child in ast.walk(tree):
                if isinstance(child, ast.ClassDef):
                    node.classes.append(child.name)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    node.functions.append(child.name)
                elif isinstance(child, ast.Import):
                    for alias in child.names:
                        dep = alias.name.split(".")[0]
                        capped_append(node.imports, alias.name, max_size=500)
                        capped_append(node.dependencies, dep, max_size=500)
                elif isinstance(child, ast.ImportFrom):
                    if child.module:
                        dep = child.module.split(".")[0]
                        capped_append(node.imports, child.module, max_size=500)
                        capped_append(node.dependencies, dep, max_size=500)

            # Deduplicate
            node.imports = list(dict.fromkeys(node.imports))
            node.dependencies = list(dict.fromkeys(node.dependencies))

        except SyntaxError as exc:
            node.parse_error = f"SyntaxError:line{exc.lineno}"
            logger.debug("Parse error in %s: %s", file_path, _sanitize_error(exc))
        except OSError as exc:
            node.parse_error = _sanitize_error(exc)
            logger.debug("OSError reading %s", file_path)

        return node

    def _build_edges(self, graph: SystemGraph) -> None:
        """Populate graph.edges from cross-module import relationships."""
        internal = set(graph.nodes.keys())
        for name, node in graph.nodes.items():
            for dep in node.dependencies:
                if dep in internal and dep != name:
                    edge = (name, dep)
                    if len(graph.edges) < _MAX_EDGES:
                        graph.edges.append(edge)

    def _find_circular_deps(self, graph: SystemGraph) -> List[List[str]]:
        """Detect cycles via iterative DFS; returns list of cycle paths."""
        adj: Dict[str, List[str]] = {
            n: [d for d in node.dependencies if d in graph.nodes]
            for n, node in graph.nodes.items()
        }
        visited: set = set()
        in_stack: set = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]) -> None:
            if len(cycles) >= 20:  # cap detection
                return
            visited.add(node)
            in_stack.add(node)
            path.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in in_stack:
                    # Found a cycle — record it
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
            path.pop()
            in_stack.discard(node)

        for n in list(graph.nodes.keys()):
            if n not in visited:
                dfs(n, [])

        return cycles
