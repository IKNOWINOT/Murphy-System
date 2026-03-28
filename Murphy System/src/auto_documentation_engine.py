"""
Auto-Documentation Engine for Murphy System.

Design Label: DEV-003 — Automated Documentation Generation from Code Analysis
Owner: Documentation Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable documentation artifacts)
  - EventBackbone (publishes LEARNING_FEEDBACK on doc generation)
  - RAGVectorIntegration (optional, for semantic indexing of docs)

Implements Phase 2 — Development Automation:
  Analyses Python source files to extract module docstrings, class
  docstrings, function signatures, and design labels. Generates
  structured documentation artifacts (module summaries, API references,
  design-label inventories) that can be persisted and published.

Flow:
  1. Scan source file for module docstring, classes, functions
  2. Extract signatures, docstrings, design labels, and dependencies
  3. Generate structured documentation artifact (ModuleDoc)
  4. Optionally persist artifact via PersistenceManager
  5. Publish LEARNING_FEEDBACK event with doc generation outcome

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies source files
  - Bounded: configurable max artifacts to prevent memory issues
  - Pure stdlib: uses ast module, no external dependencies
  - Audit trail: every generation is logged

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
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ARTIFACTS = 10_000
_DESIGN_LABEL_PATTERN = re.compile(r"Design Label:\s*(\S+)")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FunctionDoc:
    """Documentation for a single function or method."""
    name: str
    signature: str
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "signature": self.signature,
            "docstring": self.docstring,
            "decorators": list(self.decorators),
            "line_number": self.line_number,
        }


@dataclass
class ClassDoc:
    """Documentation for a single class."""
    name: str
    docstring: str = ""
    bases: List[str] = field(default_factory=list)
    methods: List[FunctionDoc] = field(default_factory=list)
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "docstring": self.docstring,
            "bases": list(self.bases),
            "methods": [m.to_dict() for m in self.methods],
            "line_number": self.line_number,
        }


@dataclass
class ModuleDoc:
    """Structured documentation for a Python module."""
    doc_id: str
    file_path: str
    module_name: str
    module_docstring: str = ""
    design_label: str = ""
    owner: str = ""
    classes: List[ClassDoc] = field(default_factory=list)
    functions: List[FunctionDoc] = field(default_factory=list)
    total_lines: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "file_path": self.file_path,
            "module_name": self.module_name,
            "module_docstring": self.module_docstring,
            "design_label": self.design_label,
            "owner": self.owner,
            "classes": [c.to_dict() for c in self.classes],
            "functions": [f.to_dict() for f in self.functions],
            "total_lines": self.total_lines,
            "generated_at": self.generated_at,
        }


@dataclass
class DesignLabelEntry:
    """A design label discovered across the codebase."""
    label: str
    module_name: str
    file_path: str
    owner: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "module_name": self.module_name,
            "file_path": self.file_path,
            "owner": self.owner,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# AutoDocumentationEngine
# ---------------------------------------------------------------------------

class AutoDocumentationEngine:
    """Automated documentation generation from Python source analysis.

    Design Label: DEV-003
    Owner: Documentation Team / Platform Engineering

    Usage::

        engine = AutoDocumentationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        doc = engine.analyse_file("src/health_monitor.py")
        labels = engine.scan_directory("src/")
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_artifacts: int = _MAX_ARTIFACTS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._artifacts: List[ModuleDoc] = []
        self._label_inventory: List[DesignLabelEntry] = []
        self._max_artifacts = max_artifacts

    # ------------------------------------------------------------------
    # Single-file analysis
    # ------------------------------------------------------------------

    def analyse_file(self, file_path: str) -> Optional[ModuleDoc]:
        """Analyse a Python source file and generate documentation."""
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                source = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return None

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.warning("Syntax error in %s: %s", file_path, exc)
            return None

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        module_docstring = ast.get_docstring(tree) or ""

        # Extract design label and owner from module docstring
        design_label = ""
        owner = ""
        label_match = _DESIGN_LABEL_PATTERN.search(module_docstring)
        if label_match:
            design_label = label_match.group(1).rstrip("—–-")
        owner_match = re.search(r"Owner:\s*(.+)", module_docstring)
        if owner_match:
            owner = owner_match.group(1).strip()

        # Extract classes and functions
        classes = self._extract_classes(tree)
        functions = self._extract_functions(tree)
        total_lines = len(source.splitlines())

        doc = ModuleDoc(
            doc_id=f"doc-{uuid.uuid4().hex[:8]}",
            file_path=file_path,
            module_name=module_name,
            module_docstring=module_docstring[:2000],
            design_label=design_label,
            owner=owner,
            classes=classes,
            functions=functions,
            total_lines=total_lines,
        )

        with self._lock:
            if len(self._artifacts) >= self._max_artifacts:
                evict = max(1, self._max_artifacts // 10)
                self._artifacts = self._artifacts[evict:]
            self._artifacts.append(doc)

            if design_label:
                capped_append(self._label_inventory, DesignLabelEntry(
                    label=design_label,
                    module_name=module_name,
                    file_path=file_path,
                    owner=owner,
                    description=module_docstring[:200],
                ))

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=doc.doc_id, document=doc.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(doc)

        logger.info("Generated docs for %s (label=%s)", module_name, design_label)
        return doc

    # ------------------------------------------------------------------
    # Directory scanning
    # ------------------------------------------------------------------

    def scan_directory(self, directory: str) -> List[ModuleDoc]:
        """Scan a directory for Python files and generate docs for each."""
        docs: List[ModuleDoc] = []
        if not os.path.isdir(directory):
            logger.warning("Not a directory: %s", directory)
            return docs

        for entry in sorted(os.listdir(directory)):
            if entry.endswith(".py") and not entry.startswith("__"):
                full = os.path.join(directory, entry)
                doc = self.analyse_file(full)
                if doc is not None:
                    docs.append(doc)
        return docs

    # ------------------------------------------------------------------
    # Design label inventory
    # ------------------------------------------------------------------

    def get_label_inventory(self) -> List[Dict[str, Any]]:
        """Return all discovered design labels."""
        with self._lock:
            return [e.to_dict() for e in self._label_inventory]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_artifacts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent documentation artifacts."""
        with self._lock:
            artifacts = list(self._artifacts)
        return [a.to_dict() for a in artifacts[-limit:]]

    def get_artifact(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific artifact by doc_id."""
        with self._lock:
            for a in self._artifacts:
                if a.doc_id == doc_id:
                    return a.to_dict()
        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            return {
                "total_artifacts": len(self._artifacts),
                "total_labels": len(self._label_inventory),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_classes(self, tree: ast.Module) -> List[ClassDoc]:
        """Extract class documentation from AST."""
        classes: List[ClassDoc] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(self._function_doc(item))
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.dump(base))
                classes.append(ClassDoc(
                    name=node.name,
                    docstring=(ast.get_docstring(node) or "")[:1000],
                    bases=bases,
                    methods=methods,
                    line_number=node.lineno,
                ))
        return classes

    def _extract_functions(self, tree: ast.Module) -> List[FunctionDoc]:
        """Extract top-level function documentation from AST."""
        fns: List[FunctionDoc] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fns.append(self._function_doc(node))
        return fns

    def _function_doc(self, node) -> FunctionDoc:
        """Build FunctionDoc from an AST function node."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        sig = f"({', '.join(args)})"
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(ast.dump(dec))
        return FunctionDoc(
            name=node.name,
            signature=sig,
            docstring=(ast.get_docstring(node) or "")[:500],
            decorators=decorators,
            line_number=node.lineno,
        )

    def _publish_event(self, doc: ModuleDoc) -> None:
        """Publish a LEARNING_FEEDBACK event for doc generation."""
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "auto_documentation_engine",
                    "action": "doc_generated",
                    "doc_id": doc.doc_id,
                    "module_name": doc.module_name,
                    "design_label": doc.design_label,
                    "classes": len(doc.classes),
                    "functions": len(doc.functions),
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="auto_documentation_engine",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
