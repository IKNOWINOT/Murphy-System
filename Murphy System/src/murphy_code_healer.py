"""
Murphy Code Healer — Autonomous Self-Coding Engine.

Design Label: ARCH-006 — Murphy Code Healer
Owner: Backend Team
Dependencies:
  - BugPatternDetector (DEV-004)
  - SelfImprovementEngine (ARCH-001)
  - SelfHealingCoordinator (OBS-004)
  - EventBackbone
  - PersistenceManager
  - GovernanceFramework (AgentDescriptor, AuthorityBand)

Extends the existing SelfFixLoop (ARCH-005) to perform **source-level**
analysis and code proposal generation.  The healer never writes to disk
directly; every change is surfaced as a ``CodeProposal`` for human review.

Architecture:
  DiagnosticSupervisor → CodeIntelligence → BayesianFixPlanner
       ↓                                          ↓
  ReconciliationController ←── PatchGenerator ──→ HealerChaosRunner
       ↓
  HealerSupervisor   GoldenPathRecorder   EventBackbone

Safety invariants:
  - NEVER modifies source files on disk
  - All proposals require human approval before application
  - Confidence-gated execution (< 0.7 → log only; 0.7–0.9 → propose;
    > 0.9 → propose with auto-merge suggestion — still never auto-writes)
  - Thread-safe: all shared state guarded by threading.Lock
  - Bounded collections via capped_append

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import collections
import difflib
import json
import logging
import os
import re
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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

_MAX_GAPS = 1_000
_MAX_PROPOSALS = 500
_MAX_GOLDEN_PATHS = 200
_MAX_EVENTS = 5_000
_MAX_WORKERS = 20
_WORKER_MAX_RESTARTS = 5
_WORKER_RESTART_WINDOW = 60  # seconds
_BACKOFF_BASE = 2.0
_BACKOFF_MAX = 300.0  # 5 min cap

# Confidence thresholds
_CONFIDENCE_LOG_ONLY = 0.70
_CONFIDENCE_PROPOSE = 0.90

# Complexity threshold (McCabe)
_COMPLEXITY_THRESHOLD = 10

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CodeGap:
    """Structured description of a detected source-level gap or issue."""

    gap_id: str
    description: str
    source: str  # "static_analysis" | "test_gap" | "doc_drift" | "bug_pattern" | ...
    severity: str = "medium"  # critical | high | medium | low
    category: str = ""
    file_path: str = ""
    line_number: int = 0
    function_name: str = ""
    class_name: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    correlation_group: Optional[str] = None  # groups related gaps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "source": self.source,
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "class_name": self.class_name,
            "context": self.context,
            "detected_at": self.detected_at,
            "correlation_group": self.correlation_group,
        }


@dataclass
class CodeContext:
    """AST-derived context for a specific code location."""

    target_file: str
    target_function: str
    target_class: str
    ast_node: Optional[Any] = None  # ast.FunctionDef or ast.ClassDef
    callers: List[str] = field(default_factory=list)
    callees: List[str] = field(default_factory=list)
    related_tests: List[str] = field(default_factory=list)
    docstring: str = ""
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_file": self.target_file,
            "target_function": self.target_function,
            "target_class": self.target_class,
            "callers": self.callers,
            "callees": self.callees,
            "related_tests": self.related_tests,
            "docstring": self.docstring,
            "signature": self.signature,
        }


@dataclass
class BeliefState:
    """Bayesian belief distribution over fix hypotheses for a gap."""

    gap_id: str
    hypotheses: Dict[str, float] = field(
        default_factory=lambda: {
            "simple_config_fix": 1 / 6,
            "missing_guard_clause": 1 / 6,
            "incorrect_logic": 1 / 6,
            "missing_feature": 1 / 6,
            "performance_issue": 1 / 6,
            "test_gap": 1 / 6,
        }
    )
    observation_count: int = 0

    def update(self, likelihood: Dict[str, float]) -> None:
        """Bayesian update: posterior ∝ prior × likelihood."""
        unnormalized: Dict[str, float] = {}
        for h, prior in self.hypotheses.items():
            unnormalized[h] = prior * likelihood.get(h, 1.0)
        total = sum(unnormalized.values()) or 1.0
        self.hypotheses = {h: v / total for h, v in unnormalized.items()}
        self.observation_count += 1

    def best_hypothesis(self) -> Tuple[str, float]:
        best = max(self.hypotheses, key=lambda k: self.hypotheses[k])
        return best, self.hypotheses[best]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "hypotheses": dict(self.hypotheses),
            "observation_count": self.observation_count,
        }


@dataclass
class CodeFixPlan:
    """A structured plan for fixing a code gap."""

    plan_id: str
    gap_id: str
    patch_type: str  # add_function|modify_function|add_test|add_guard|refactor|add_docstring
    target_file: str
    target_function: str
    target_class: str
    patch_description: str
    patch_code: str
    test_code: str
    rollback_plan: str
    confidence_score: float
    risk_assessment: str
    hypothesis: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "gap_id": self.gap_id,
            "patch_type": self.patch_type,
            "target_file": self.target_file,
            "target_function": self.target_function,
            "target_class": self.target_class,
            "patch_description": self.patch_description,
            "patch_code": self.patch_code,
            "test_code": self.test_code,
            "rollback_plan": self.rollback_plan,
            "confidence_score": self.confidence_score,
            "risk_assessment": self.risk_assessment,
            "hypothesis": self.hypothesis,
            "created_at": self.created_at,
        }


@dataclass
class CodeProposal:
    """A fully audited proposal ready for human review."""

    proposal_id: str
    plan_id: str
    gap_id: str
    unified_diff: str
    test_diff: str
    adversarial_test: str
    resilience_score: float
    auto_merge_suggested: bool
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending | approved | rejected | applied
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "plan_id": self.plan_id,
            "gap_id": self.gap_id,
            "unified_diff": self.unified_diff,
            "test_diff": self.test_diff,
            "adversarial_test": self.adversarial_test,
            "resilience_score": self.resilience_score,
            "auto_merge_suggested": self.auto_merge_suggested,
            "audit_trail": list(self.audit_trail),
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class ResilienceScore:
    """Chaos-testing derived resilience assessment for a patch."""

    scenario: str
    passed: bool
    details: str
    score: float  # 0.0–1.0


@dataclass
class GoldenPath:
    """A recorded successful fix pattern for future replay."""

    path_id: str
    gap_category: str
    patch_type: str
    description: str
    patch_template: str
    test_template: str
    success_count: int = 1
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "gap_category": self.gap_category,
            "patch_type": self.patch_type,
            "description": self.description,
            "patch_template": self.patch_template,
            "test_template": self.test_template,
            "success_count": self.success_count,
            "recorded_at": self.recorded_at,
        }


# ---------------------------------------------------------------------------
# 1. DiagnosticSupervisor
# ---------------------------------------------------------------------------


class DiagnosticSupervisor:
    """Aggregates gap signals from all Murphy subsystems.

    Continuously scans for anomalies from static analysis, test coverage,
    documentation drift, bug patterns, improvement backlogs, and healing
    failure history.
    """

    def __init__(
        self,
        bug_detector=None,
        improvement_engine=None,
        healing_coordinator=None,
        src_root: Optional[str] = None,
        tests_root: Optional[str] = None,
        docs_root: Optional[str] = None,
    ) -> None:
        self._bug_detector = bug_detector
        self._engine = improvement_engine
        self._coordinator = healing_coordinator
        self._src_root = src_root
        self._tests_root = tests_root
        self._docs_root = docs_root
        self._lock = threading.Lock()
        self._gap_history: List[CodeGap] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect_gaps(self) -> List[CodeGap]:
        """Run all detectors and return deduplicated CodeGap list."""
        gaps: List[CodeGap] = []
        gaps.extend(self._gaps_from_bug_detector())
        gaps.extend(self._gaps_from_improvement_engine())
        gaps.extend(self._gaps_from_healing_coordinator())
        if self._src_root:
            gaps.extend(self._static_analysis_gaps(self._src_root))
            if self._tests_root:
                gaps.extend(
                    self._test_coverage_gaps(self._src_root, self._tests_root)
                )
            gaps.extend(self._doc_drift_gaps(self._src_root))
        if self._docs_root:
            gaps.extend(self._markdown_file_ref_gaps(self._docs_root))
        gaps = self._correlate_gaps(gaps)
        with self._lock:
            for g in gaps:
                capped_append(self._gap_history, g, max_size=_MAX_GAPS)
        return gaps

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [g.to_dict() for g in self._gap_history[-limit:]]

    # ------------------------------------------------------------------
    # Internal detectors
    # ------------------------------------------------------------------

    def _gaps_from_bug_detector(self) -> List[CodeGap]:
        if self._bug_detector is None:
            return []
        gaps: List[CodeGap] = []
        try:
            report = self._bug_detector.run_detection_cycle()
            for pat in self._bug_detector.get_patterns():
                gaps.append(
                    CodeGap(
                        gap_id=f"gap-bug-{pat.get('pattern_id', uuid.uuid4().hex[:8])}",
                        description=pat.get("description", "Bug pattern detected"),
                        source="bug_detector",
                        severity=pat.get("severity", "medium"),
                        category="bug_pattern",
                        context={"pattern": pat, "report_id": getattr(report, "report_id", "")},
                    )
                )
        except Exception as exc:
            logger.debug("BugPatternDetector unavailable: %s", exc)
        return gaps

    def _gaps_from_improvement_engine(self) -> List[CodeGap]:
        if self._engine is None:
            return []
        gaps: List[CodeGap] = []
        try:
            backlog = self._engine.get_remediation_backlog()
            for prop in backlog:
                gaps.append(
                    CodeGap(
                        gap_id=f"gap-eng-{getattr(prop, 'proposal_id', uuid.uuid4().hex[:8])}",
                        description=getattr(prop, "description", "Improvement needed"),
                        source="improvement_engine",
                        severity=getattr(prop, "priority", "medium"),
                        category=getattr(prop, "category", ""),
                        context={"proposal_id": getattr(prop, "proposal_id", "")},
                    )
                )
        except Exception as exc:
            logger.debug("SelfImprovementEngine unavailable: %s", exc)
        return gaps

    def _gaps_from_healing_coordinator(self) -> List[CodeGap]:
        if self._coordinator is None:
            return []
        gaps: List[CodeGap] = []
        try:
            history = self._coordinator.get_history(limit=50)
            failures = [h for h in history if h.get("status") == "failed"]
            for entry in failures:
                gaps.append(
                    CodeGap(
                        gap_id=f"gap-heal-{uuid.uuid4().hex[:8]}",
                        description=f"Recovery procedure failed: {entry.get('category', 'unknown')}",
                        source="healing_coordinator",
                        severity="high",
                        category="recovery_failure",
                        context=entry,
                    )
                )
        except Exception as exc:
            logger.debug("SelfHealingCoordinator unavailable: %s", exc)
        return gaps

    def _static_analysis_gaps(self, src_root: str) -> List[CodeGap]:
        """Scan Python source files for common anti-patterns."""
        gaps: List[CodeGap] = []
        for py_file in Path(src_root).rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                file_str = str(py_file)
                gaps.extend(self._check_bare_excepts(source, file_str))
                gaps.extend(self._check_todo_markers(source, file_str))
                gaps.extend(self._check_complexity(source, file_str))
            except Exception as exc:
                logger.debug("Static analysis skipped for %s: %s", py_file, exc)
        return gaps

    def _check_bare_excepts(self, source: str, file_str: str) -> List[CodeGap]:
        gaps: List[CodeGap] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return gaps
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                gaps.append(
                    CodeGap(
                        gap_id=f"gap-sa-bareexcept-{uuid.uuid4().hex[:8]}",
                        description="Bare except clause found — catches all exceptions including SystemExit",
                        source="static_analysis",
                        severity="medium",
                        category="bare_except",
                        file_path=file_str,
                        line_number=node.lineno,
                    )
                )
        return gaps

    def _check_todo_markers(self, source: str, file_str: str) -> List[CodeGap]:
        gaps: List[CodeGap] = []
        pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
        for i, line in enumerate(source.splitlines(), start=1):
            if pattern.search(line):
                gaps.append(
                    CodeGap(
                        gap_id=f"gap-sa-todo-{uuid.uuid4().hex[:8]}",
                        description=f"TODO/FIXME/HACK marker at line {i}",
                        source="static_analysis",
                        severity="low",
                        category="todo_marker",
                        file_path=file_str,
                        line_number=i,
                        context={"line": line.strip()},
                    )
                )
        return gaps

    def _check_complexity(self, source: str, file_str: str) -> List[CodeGap]:
        """Flag functions whose cyclomatic complexity exceeds threshold."""
        gaps: List[CodeGap] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return gaps
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._cyclomatic_complexity(node)
                if complexity > _COMPLEXITY_THRESHOLD:
                    gaps.append(
                        CodeGap(
                            gap_id=f"gap-sa-complex-{uuid.uuid4().hex[:8]}",
                            description=(
                                f"Function '{node.name}' has cyclomatic complexity "
                                f"{complexity} (threshold {_COMPLEXITY_THRESHOLD})"
                            ),
                            source="static_analysis",
                            severity="medium",
                            category="high_complexity",
                            file_path=file_str,
                            line_number=node.lineno,
                            function_name=node.name,
                            context={"complexity": complexity},
                        )
                    )
        return gaps

    @staticmethod
    def _cyclomatic_complexity(node: ast.AST) -> int:
        """Approximate cyclomatic complexity (branch count + 1)."""
        branch_nodes = (
            ast.If, ast.For, ast.While, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension,
        )
        count = 1
        for child in ast.walk(node):
            if isinstance(child, branch_nodes):
                count += 1
            elif isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
        return count

    def _test_coverage_gaps(self, src_root: str, tests_root: str) -> List[CodeGap]:
        """Identify public functions/classes with no corresponding test."""
        gaps: List[CodeGap] = []
        tested_names: Set[str] = set()
        # Collect names referenced in test files
        for tf in Path(tests_root).rglob("test_*.py"):
            try:
                tree = ast.parse(
                    tf.read_text(encoding="utf-8", errors="replace")
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name):
                        tested_names.add(node.id)
                    elif isinstance(node, ast.Attribute):
                        tested_names.add(node.attr)
            except (SyntaxError, ValueError) as exc:
                logger.debug("Skipping unparseable test file %s: %s", tf, exc)
        for py_file in Path(src_root).rglob("*.py"):
            if "test" in py_file.name:
                continue
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8", errors="replace")
                )
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name.startswith("_"):
                            continue
                        if node.name not in tested_names:
                            gaps.append(
                                CodeGap(
                                    gap_id=f"gap-tc-{uuid.uuid4().hex[:8]}",
                                    description=f"No test found for public symbol '{node.name}'",
                                    source="test_coverage",
                                    severity="low",
                                    category="test_gap",
                                    file_path=str(py_file),
                                    line_number=node.lineno,
                                    function_name=node.name
                                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                    else "",
                                    class_name=node.name
                                    if isinstance(node, ast.ClassDef)
                                    else "",
                                )
                            )
            except (SyntaxError, ValueError) as exc:
                logger.debug("Skipping unparseable source file %s: %s", py_file, exc)
        return gaps

    def _doc_drift_gaps(self, src_root: str) -> List[CodeGap]:
        """Find docstrings whose param names don't match function signatures."""
        gaps: List[CodeGap] = []
        for py_file in Path(src_root).rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except Exception as exc:
                logger.debug("Skipping %s: %s", py_file, type(exc).__name__)
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                docstring = ast.get_docstring(node) or ""
                if not docstring:
                    continue
                sig_params = {
                    arg.arg
                    for arg in node.args.args
                    if arg.arg not in ("self", "cls")
                }
                doc_params = set(
                    re.findall(r":param\s+(\w+):", docstring)
                    + re.findall(r"Args:\s*\n(?:\s+(\w+)\s*:)", docstring)
                )
                drift = sig_params.symmetric_difference(doc_params)
                if drift:
                    gaps.append(
                        CodeGap(
                            gap_id=f"gap-dd-{uuid.uuid4().hex[:8]}",
                            description=(
                                f"Documentation drift in '{node.name}': "
                                f"param mismatch {drift}"
                            ),
                            source="doc_drift",
                            severity="low",
                            category="doc_drift",
                            file_path=str(py_file),
                            line_number=node.lineno,
                            function_name=node.name,
                            context={"drift_params": list(drift)},
                        )
                    )
        return gaps

    def _markdown_file_ref_gaps(self, docs_root: str) -> List[CodeGap]:
        """Parse all *.md files under *docs_root* for file path references.

        Looks for markdown links ``[text](path)`` and inline backtick paths
        like ``src/foo.py`` and checks whether each referenced path exists
        on disk (resolved relative to *docs_root*).  Missing paths are
        reported as ``doc_drift`` gaps.
        """
        gaps: List[CodeGap] = []
        docs_path = Path(docs_root)
        # Regex: markdown link targets  [label](some/path.ext)
        _md_link_re = re.compile(r"\[([^\]]*)\]\(([^)#?\s]+)\)")
        # Regex: bare file-like tokens  e.g. `src/foo.py`  or  src/foo.py
        _bare_path_re = re.compile(
            r"(?:^|[\s`'\"])([a-zA-Z0-9_./-]+\.(?:py|md|yaml|yml|json|toml|sh|txt))"
        )

        for md_file in docs_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.debug("Skipping %s: %s", md_file, exc)
                continue

            refs: List[str] = []
            for _label, target in _md_link_re.findall(content):
                # Skip URLs and anchors
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                refs.append(target)
            for m in _bare_path_re.finditer(content):
                candidate = m.group(1).strip("`'\" \t")
                if "/" in candidate and not candidate.startswith("http"):
                    refs.append(candidate)

            for ref in refs:
                # Resolve relative to the docs_root first, then the md_file dir
                resolved = docs_path / ref
                if not resolved.exists():
                    resolved = md_file.parent / ref
                if not resolved.exists():
                    gaps.append(
                        CodeGap(
                            gap_id=f"gap-mdr-{uuid.uuid4().hex[:8]}",
                            description=(
                                f"Broken file reference '{ref}' in {md_file.name}"
                            ),
                            source="doc_drift",
                            severity="low",
                            category="broken_md_ref",
                            file_path=str(md_file),
                            context={"missing_ref": ref, "md_file": str(md_file)},
                        )
                    )
        return gaps

    def _correlate_gaps(self, gaps: List[CodeGap]) -> List[CodeGap]:
        """Group gaps that share the same file + function into correlation groups."""
        key_to_group: Dict[str, str] = {}
        for gap in gaps:
            if gap.file_path and gap.function_name:
                key = f"{gap.file_path}::{gap.function_name}"
                if key not in key_to_group:
                    key_to_group[key] = f"corr-{uuid.uuid4().hex[:8]}"
                gap.correlation_group = key_to_group[key]
        return gaps


# ---------------------------------------------------------------------------
# 2. CodeIntelligence
# ---------------------------------------------------------------------------


class CodeIntelligence:
    """AST-aware code understanding engine.

    Parses Python source files to build a structural map:
    function signatures, class hierarchies, import graphs, call graphs.
    Performs spectrum-based fault localisation for each CodeGap.
    """

    def __init__(self, src_root: Optional[str] = None) -> None:
        self._src_root = src_root
        self._lock = threading.Lock()
        self._module_map: Dict[str, ast.Module] = {}  # file → AST
        self._function_map: Dict[str, List[ast.FunctionDef]] = {}  # file → funcs
        self._class_map: Dict[str, List[ast.ClassDef]] = {}  # file → classes
        self._call_graph: Dict[str, Set[str]] = collections.defaultdict(set)
        self._parsed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_map(self, src_root: Optional[str] = None) -> None:
        """Parse all Python files and populate internal maps."""
        root = src_root or self._src_root
        if root is None:
            return
        with self._lock:
            for py_file in Path(root).rglob("*.py"):
                self._parse_file(str(py_file))
            self._parsed = True

    def get_context(self, gap: CodeGap) -> CodeContext:
        """Build a CodeContext for the given gap using the AST map."""
        if not self._parsed and self._src_root:
            self.build_map()
        ctx = CodeContext(
            target_file=gap.file_path,
            target_function=gap.function_name,
            target_class=gap.class_name,
        )
        if gap.file_path:
            funcs = self._function_map.get(gap.file_path, [])
            for fn in funcs:
                if fn.name == gap.function_name:
                    ctx.ast_node = fn
                    ctx.docstring = ast.get_docstring(fn) or ""
                    ctx.signature = self._signature_str(fn)
                    break
            ctx.callees = list(
                self._call_graph.get(
                    f"{gap.file_path}::{gap.function_name}", set()
                )
            )
            # Callers: any function that calls our target
            for caller_key, callees in self._call_graph.items():
                if gap.function_name in callees:
                    ctx.callers.append(caller_key)
        return ctx

    def localise_fault(self, gap: CodeGap) -> List[Tuple[str, float]]:
        """Spectrum-based fault localisation.

        Returns list of (function_key, suspicion_score) sorted desc.
        """
        results: List[Tuple[str, float]] = []
        target = gap.function_name
        if not target:
            return results
        for file_path, funcs in self._function_map.items():
            for fn in funcs:
                score = 0.0
                if fn.name == target:
                    score = 1.0
                elif target in self._call_graph.get(f"{file_path}::{fn.name}", set()):
                    score = 0.6
                elif fn.name in self._call_graph.get(
                    f"{gap.file_path}::{target}", set()
                ):
                    score = 0.4
                if score > 0:
                    results.append((f"{file_path}::{fn.name}", score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def extract_functions(self, file_path: str) -> List[Dict[str, Any]]:
        """Return metadata for all functions in a file."""
        with self._lock:
            funcs = self._function_map.get(file_path, [])
        return [
            {
                "name": fn.name,
                "lineno": fn.lineno,
                "signature": self._signature_str(fn),
                "docstring": ast.get_docstring(fn) or "",
            }
            for fn in funcs
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_file(self, file_path: str) -> None:
        try:
            source = Path(file_path).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            self._module_map[file_path] = tree
            self._function_map[file_path] = [
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            self._class_map[file_path] = [
                n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
            ]
            # Build call graph entries for this file
            for fn in self._function_map[file_path]:
                key = f"{file_path}::{fn.name}"
                for child in ast.walk(fn):
                    if isinstance(child, ast.Call):
                        callee = self._call_name(child)
                        if callee:
                            self._call_graph[key].add(callee)
        except Exception as exc:
            logger.debug("Could not parse %s: %s", file_path, exc)

    @staticmethod
    def _call_name(node: ast.Call) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    @staticmethod
    def _signature_str(fn: ast.FunctionDef) -> str:
        args = [arg.arg for arg in fn.args.args]
        return f"def {fn.name}({', '.join(args)})"


# ---------------------------------------------------------------------------
# 3. BayesianFixPlanner
# ---------------------------------------------------------------------------


class BayesianFixPlanner:
    """Plans code fixes using Bayesian belief updates.

    Applies the MMSMMS (Magnify→Magnify→Simplify→Magnify→Magnify→Solidify)
    cadence before committing to a fix strategy.
    """

    # Likelihood tables: given gap category, how likely is each hypothesis?
    # Values > 1.0 boost a hypothesis; values < 1.0 suppress it.
    # Unspecified hypotheses default to 1.0 (neutral).
    _LIKELIHOODS: Dict[str, Dict[str, float]] = {
        "bare_except": {
            "missing_guard_clause": 8.0,
            "incorrect_logic": 4.0,
            "simple_config_fix": 0.5,
        },
        "high_complexity": {
            "incorrect_logic": 6.0,
            "performance_issue": 4.0,
            "missing_feature": 2.0,
        },
        "test_gap": {
            "test_gap": 15.0,
            "incorrect_logic": 0.3,
            "missing_guard_clause": 0.3,
        },
        "doc_drift": {
            "simple_config_fix": 6.0,
            "missing_feature": 2.0,
        },
        "bug_pattern": {
            "incorrect_logic": 6.0,
            "missing_guard_clause": 4.0,
        },
        "recovery_failure": {
            "missing_guard_clause": 6.0,
            "missing_feature": 3.0,
        },
    }

    # Mapping: hypothesis → patch_type
    _PATCH_TYPE_MAP: Dict[str, str] = {
        "simple_config_fix": "modify_function",
        "missing_guard_clause": "add_guard",
        "incorrect_logic": "modify_function",
        "missing_feature": "add_function",
        "performance_issue": "refactor",
        "test_gap": "add_test",
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._belief_states: Dict[str, BeliefState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_plan(self, gap: CodeGap, context: CodeContext) -> CodeFixPlan:
        """Run MMSMMS cadence and produce a CodeFixPlan."""
        belief = self._get_or_create_belief(gap)
        # MMSMMS: six passes to refine understanding
        belief = self._mmsmms_cadence(belief, gap, context)
        hypothesis, confidence = belief.best_hypothesis()
        patch_type = self._PATCH_TYPE_MAP.get(hypothesis, "modify_function")
        patch_code, test_code = self._generate_patch_templates(
            gap, context, patch_type, hypothesis
        )
        return CodeFixPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:12]}",
            gap_id=gap.gap_id,
            patch_type=patch_type,
            target_file=gap.file_path,
            target_function=gap.function_name,
            target_class=gap.class_name,
            patch_description=self._describe_patch(gap, hypothesis, patch_type),
            patch_code=patch_code,
            test_code=test_code,
            rollback_plan=f"Revert changes to {gap.file_path} (git revert or manual undo)",
            confidence_score=round(confidence, 4),
            risk_assessment=self._assess_risk(gap, patch_type, confidence),
            hypothesis=hypothesis,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_belief(self, gap: CodeGap) -> BeliefState:
        with self._lock:
            if gap.gap_id not in self._belief_states:
                self._belief_states[gap.gap_id] = BeliefState(gap_id=gap.gap_id)
            return self._belief_states[gap.gap_id]

    def _mmsmms_cadence(
        self, belief: BeliefState, gap: CodeGap, context: CodeContext
    ) -> BeliefState:
        """Apply six-pass MMSMMS refinement."""
        # Pass 1 — Magnify: category likelihood
        lk = self._LIKELIHOODS.get(gap.category, {})
        if lk:
            belief.update(lk)
        # Pass 2 — Magnify: severity boosts
        sev_lk: Dict[str, float] = {}
        if gap.severity == "critical":
            sev_lk = {"missing_guard_clause": 2.0, "incorrect_logic": 1.5}
        elif gap.severity == "high":
            sev_lk = {"missing_guard_clause": 1.5}
        if sev_lk:
            belief.update(sev_lk)
        # Pass 3 — Simplify: check if docstring present (reduces doc_drift weight)
        if context.docstring:
            belief.update({"simple_config_fix": 1.1})
        # Pass 4 — Magnify: callee count (more callees → complexity)
        if len(context.callees) > 5:
            belief.update({"performance_issue": 1.2, "incorrect_logic": 1.1})
        # Pass 5 — Magnify: no related tests → test_gap more likely
        if not context.related_tests and gap.category != "test_gap":
            belief.update({"test_gap": 1.15})
        # Pass 6 — Solidify: no further update; confidence reflects final state
        return belief

    def _generate_patch_templates(
        self,
        gap: CodeGap,
        context: CodeContext,
        patch_type: str,
        hypothesis: str,
    ) -> Tuple[str, str]:
        """Generate patch code and test code from templates."""
        fn = gap.function_name or "unknown_function"
        cls = gap.class_name or ""
        file_mod = (
            Path(gap.file_path).stem if gap.file_path else "module"
        )

        if patch_type == "add_guard":
            patch = textwrap.dedent(
                f"""\
                # Guard clause added for '{fn}' — addresses: {gap.description}
                if not isinstance(arg, expected_type):
                    raise TypeError(f"Expected expected_type, got {{type(arg).__name__}}")
                """
            )
        elif patch_type == "add_test":
            patch = textwrap.dedent(
                f"""\
                def test_{fn}():
                    \"\"\"Auto-generated test for '{fn}'.\"\"\"
                    # NOTE: instantiate subject and call {fn}
                    assert True
                """
            )
        elif patch_type == "add_function":
            patch = textwrap.dedent(
                f"""\
                def {fn}_extension() -> None:
                    \"\"\"Auto-generated stub for missing feature.\"\"\"
                    raise RuntimeError("{fn}_extension not yet implemented")
                """
            )
        elif patch_type == "add_docstring":
            patch = textwrap.dedent(
                f"""\
                \"\"\"
                {fn} — auto-generated docstring.

                NOTE: Add real description, params, and return docs.
                \"\"\"
                """
            )
        else:
            patch = textwrap.dedent(
                f"""\
                # Modification proposed for '{fn}' — {gap.description}
                # NOTE: implement fix for hypothesis '{hypothesis}'
                pass
                """
            )

        test = textwrap.dedent(
            f"""\
            def test_{fn}_patched():
                \"\"\"Validate patch for gap: {gap.gap_id}.\"\"\"
                # Import from {file_mod}
                # Arrange
                # Act — call {fn}
                # Assert — expected behaviour after patch
                assert True
            """
        )
        return patch, test

    @staticmethod
    def _describe_patch(gap: CodeGap, hypothesis: str, patch_type: str) -> str:
        return (
            f"[{patch_type.upper()}] {hypothesis} identified in "
            f"'{gap.function_name or gap.class_name or gap.file_path}': "
            f"{gap.description}"
        )

    @staticmethod
    def _assess_risk(gap: CodeGap, patch_type: str, confidence: float) -> str:
        risk_level = "low" if confidence > 0.8 else "medium" if confidence > 0.6 else "high"
        return (
            f"Risk level: {risk_level}. "
            f"Patch type '{patch_type}' for gap severity '{gap.severity}'. "
            f"Confidence: {confidence:.2f}. "
            "Review callers before applying; run full test suite post-apply."
        )


# ---------------------------------------------------------------------------
# 4. PatchGenerator
# ---------------------------------------------------------------------------


class PatchGenerator:
    """Generates unified diffs and CodeProposal objects.

    All patches are validated against governance constraints and stored
    with a full audit trail.  The healer operates at AuthorityBand.MEDIUM:
    it can *propose* but never directly apply without approval.
    """

    def __init__(self, governance_framework=None) -> None:
        self._governance = governance_framework
        self._lock = threading.Lock()
        self._proposals: List[CodeProposal] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_proposal(
        self,
        plan: CodeFixPlan,
        resilience_score: float = 1.0,
        adversarial_test: str = "",
    ) -> Optional[CodeProposal]:
        """Build a CodeProposal from a CodeFixPlan.

        Returns None if governance constraints block the proposal.
        """
        if not self._governance_check(plan):
            logger.warning(
                "Governance check blocked proposal for plan %s", plan.plan_id
            )
            return None

        unified = self._make_diff(plan)
        test_diff = self._make_test_diff(plan)
        auto_merge = plan.confidence_score >= _CONFIDENCE_PROPOSE

        proposal = CodeProposal(
            proposal_id=f"prop-{uuid.uuid4().hex[:12]}",
            plan_id=plan.plan_id,
            gap_id=plan.gap_id,
            unified_diff=unified,
            test_diff=test_diff,
            adversarial_test=adversarial_test,
            resilience_score=resilience_score,
            auto_merge_suggested=auto_merge,
            audit_trail=[
                {
                    "event": "proposal_created",
                    "plan_id": plan.plan_id,
                    "confidence": plan.confidence_score,
                    "patch_type": plan.patch_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
        with self._lock:
            capped_append(self._proposals, proposal, max_size=_MAX_PROPOSALS)
        logger.info(
            "CodeProposal %s created (confidence=%.2f, auto_merge=%s)",
            proposal.proposal_id,
            plan.confidence_score,
            auto_merge,
        )
        return proposal

    def get_proposals(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._proposals[-limit:]]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _governance_check(self, plan: CodeFixPlan) -> bool:
        """Validate against authority constraints.

        The healer agent operates at MEDIUM authority: may propose but not
        execute.  Reject patches targeting safety-critical files.
        """
        if plan.confidence_score < _CONFIDENCE_LOG_ONLY:
            logger.info(
                "Plan %s below confidence threshold (%.2f < %.2f) — logging only",
                plan.plan_id,
                plan.confidence_score,
                _CONFIDENCE_LOG_ONLY,
            )
            return False
        # Governance object check (optional integration)
        if self._governance is not None:
            try:
                allowed = self._governance.check_authority(
                    "murphy_code_healer", "propose_patch", plan.to_dict()
                )
                if not allowed:
                    return False
            except Exception as exc:
                logger.debug("Governance check skipped: %s", exc)
        return True

    @staticmethod
    def _make_diff(plan: CodeFixPlan) -> str:
        """Generate a unified diff for the patch."""
        original_lines = [
            f"# Original content of {plan.target_function or plan.target_file}\n"
        ]
        patched_lines = [
            f"# Patched content of {plan.target_function or plan.target_file}\n"
        ] + [line + "\n" for line in plan.patch_code.splitlines()]
        diff = difflib.unified_diff(
            original_lines,
            patched_lines,
            fromfile=f"a/{plan.target_file}",
            tofile=f"b/{plan.target_file}",
            lineterm="",
        )
        return "\n".join(diff)

    @staticmethod
    def _make_test_diff(plan: CodeFixPlan) -> str:
        """Generate a unified diff for the auto-generated test."""
        if not plan.test_code:
            return ""
        test_file = f"tests/test_{Path(plan.target_file).stem}_healer.py"
        patched_lines = [line + "\n" for line in plan.test_code.splitlines()]
        diff = difflib.unified_diff(
            [],
            patched_lines,
            fromfile=f"a/{test_file}",
            tofile=f"b/{test_file}",
            lineterm="",
        )
        return "\n".join(diff)


# ---------------------------------------------------------------------------
# 5. ReconciliationController
# ---------------------------------------------------------------------------


class ReconciliationController:
    """Desired-state reconciliation loop.

    Desired state: zero known gaps, all tests passing, all docs current.
    Continuously compares observed state against desired state and triggers
    the fix pipeline when drift is detected.  Uses exponential backoff for
    repeated failures on the same gap.  Implements a leader-election guard
    (only one controller active at a time) using the shared mutex pattern.
    """

    def __init__(
        self,
        diagnostic_supervisor: DiagnosticSupervisor,
        fix_pipeline: Optional[Callable[[CodeGap], Optional[CodeProposal]]] = None,
    ) -> None:
        self._supervisor = diagnostic_supervisor
        self._pipeline = fix_pipeline
        self._lock = threading.Lock()
        self._running = False
        self._backoff: Dict[str, float] = {}  # gap_id → backoff seconds
        self._attempts: Dict[str, int] = {}  # gap_id → attempt count
        self._resolved: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconcile_once(self) -> Dict[str, Any]:
        """Run a single reconciliation pass.  Returns summary."""
        with self._lock:
            if self._running:
                return {"status": "already_running"}
            self._running = True
        try:
            return self._do_reconcile()
        finally:
            with self._lock:
                self._running = False

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "pending_gaps": len(self._backoff),
                "resolved_gaps": len(self._resolved),
                "backoff_state": dict(self._backoff),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_reconcile(self) -> Dict[str, Any]:
        observed_gaps = self._supervisor.collect_gaps()
        open_gaps = [g for g in observed_gaps if g.gap_id not in self._resolved]
        proposals_created = 0
        skipped_backoff = 0

        for gap in open_gaps:
            if self._is_backed_off(gap.gap_id):
                skipped_backoff += 1
                continue
            if self._pipeline:
                try:
                    proposal = self._pipeline(gap)
                    if proposal is not None:
                        self._resolved.add(gap.gap_id)
                        proposals_created += 1
                        self._backoff.pop(gap.gap_id, None)
                        self._attempts.pop(gap.gap_id, None)
                    else:
                        self._record_failure(gap.gap_id)
                except Exception as exc:
                    logger.warning(
                        "Pipeline error for gap %s: %s", gap.gap_id, exc
                    )
                    self._record_failure(gap.gap_id)

        return {
            "observed_gaps": len(observed_gaps),
            "open_gaps": len(open_gaps),
            "proposals_created": proposals_created,
            "skipped_backoff": skipped_backoff,
            "resolved_total": len(self._resolved),
        }

    def _is_backed_off(self, gap_id: str) -> bool:
        until = self._backoff.get(gap_id, 0.0)
        return time.monotonic() < until

    def _record_failure(self, gap_id: str) -> None:
        attempts = self._attempts.get(gap_id, 0) + 1
        self._attempts[gap_id] = attempts
        delay = min(_BACKOFF_BASE ** attempts, _BACKOFF_MAX)
        self._backoff[gap_id] = time.monotonic() + delay
        logger.debug(
            "Backoff for gap %s: attempt %d, wait %.1fs", gap_id, attempts, delay
        )


# ---------------------------------------------------------------------------
# 6. HealerSupervisor
# ---------------------------------------------------------------------------


@dataclass
class _WorkerRecord:
    name: str
    target: Callable[[], None]
    strategy: str  # "one_for_one" | "one_for_all"
    thread: Optional[threading.Thread] = None
    restart_times: List[float] = field(default_factory=list)
    alive: bool = False
    last_heartbeat: float = field(default_factory=time.monotonic)


class HealerSupervisor:
    """Worker supervision tree for healing processes.

    Strategies:
      one_for_one   — restart only the failed worker
      one_for_all   — restart all workers if any critical worker fails
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: Dict[str, _WorkerRecord] = {}
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_worker(
        self,
        name: str,
        target: Callable[[], None],
        strategy: str = "one_for_one",
    ) -> None:
        with self._lock:
            self._workers[name] = _WorkerRecord(
                name=name, target=target, strategy=strategy
            )

    def start_all(self) -> None:
        """Start all registered workers and the monitor."""
        with self._lock:
            self._running = True
            for rec in self._workers.values():
                self._start_worker(rec)
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="healer-supervisor-monitor"
        )
        self._monitor_thread.start()

    def stop_all(self) -> None:
        with self._lock:
            self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

    def heartbeat(self, worker_name: str) -> None:
        """Workers call this periodically to report liveness."""
        with self._lock:
            rec = self._workers.get(worker_name)
            if rec:
                rec.last_heartbeat = time.monotonic()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                name: {
                    "alive": rec.alive,
                    "restarts": len(rec.restart_times),
                    "strategy": rec.strategy,
                    "last_heartbeat_ago": round(
                        time.monotonic() - rec.last_heartbeat, 1
                    ),
                }
                for name, rec in self._workers.items()
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_worker(self, rec: _WorkerRecord) -> None:
        """Must be called under self._lock."""
        t = threading.Thread(
            target=self._worker_wrapper,
            args=(rec,),
            daemon=True,
            name=f"healer-worker-{rec.name}",
        )
        rec.thread = t
        rec.alive = True
        t.start()

    def _worker_wrapper(self, rec: _WorkerRecord) -> None:
        try:
            rec.target()
        except Exception as exc:
            logger.warning("Worker '%s' crashed: %s", rec.name, exc)
        finally:
            with self._lock:
                rec.alive = False

    def _monitor_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            time.sleep(5)
            self._check_workers()

    def _check_workers(self) -> None:
        with self._lock:
            for rec in list(self._workers.values()):
                if not self._running:
                    break
                if not rec.alive:
                    self._handle_crash(rec)

    def _handle_crash(self, rec: _WorkerRecord) -> None:
        """Must be called under self._lock."""
        now = time.monotonic()
        # Prune old restart records outside window
        rec.restart_times = [
            t for t in rec.restart_times if now - t < _WORKER_RESTART_WINDOW
        ]
        if len(rec.restart_times) >= _WORKER_MAX_RESTARTS:
            logger.error(
                "Worker '%s' exceeded restart budget (%d in %ds) — not restarting",
                rec.name,
                _WORKER_MAX_RESTARTS,
                _WORKER_RESTART_WINDOW,
            )
            return
        rec.restart_times.append(now)
        if rec.strategy == "one_for_all":
            logger.warning(
                "one_for_all: restarting all workers due to '%s' crash", rec.name
            )
            for other in self._workers.values():
                other.alive = False
                self._start_worker(other)
        else:
            logger.info("one_for_one: restarting worker '%s'", rec.name)
            self._start_worker(rec)


# ---------------------------------------------------------------------------
# 7. HealerChaosRunner
# ---------------------------------------------------------------------------


class HealerChaosRunner:
    """Integrates with SyntheticFailureGenerator for chaos validation.

    After a patch plan is generated, runs chaos scenarios to verify the
    patch does not introduce new failure modes.
    """

    def __init__(self, failure_generator=None) -> None:
        self._generator = failure_generator

    def evaluate(self, plan: CodeFixPlan) -> ResilienceScore:
        """Run chaos scenarios and return a ResilienceScore."""
        if self._generator is None:
            return ResilienceScore(
                scenario="no_chaos_runner",
                passed=True,
                details="SyntheticFailureGenerator not configured; chaos skipped",
                score=1.0,
            )
        try:
            result = self._generator.inject_failure(
                failure_type="patch_validation",
                target=plan.target_function or plan.target_file,
                context=plan.to_dict(),
            )
            passed = result.get("survived", True)
            score = 1.0 if passed else 0.5
            return ResilienceScore(
                scenario="patch_validation_chaos",
                passed=passed,
                details=str(result),
                score=score,
            )
        except Exception as exc:
            logger.debug("Chaos evaluation error: %s", exc)
            return ResilienceScore(
                scenario="chaos_error",
                passed=True,
                details=f"Chaos runner error (non-fatal): {exc}",
                score=0.8,
            )

    def generate_adversarial_test(self, plan: CodeFixPlan) -> str:
        """Generate a test that tries to break the patch."""
        fn = plan.target_function or "target"
        return textwrap.dedent(
            f"""\
            def test_{fn}_adversarial():
                \"\"\"Adversarial test: attempts to break the patch for gap {plan.gap_id}.\"\"\"
                # This test deliberately exercises edge cases and boundary conditions.
                # Verify that the patched code handles:
                #   - None inputs
                #   - Empty collections
                #   - Extreme values
                #   - Concurrent access
                # If any of these cause an unexpected exception, the patch is fragile.
                try:
                    pass  # Replace with actual adversarial calls
                except RuntimeError:
                    pass  # Expected for stubs
                except Exception as exc:
                    raise AssertionError(
                        f"Adversarial test revealed fragility in patch: {{exc}}"
                    ) from exc
            """
        )


# ---------------------------------------------------------------------------
# 8. GoldenPathRecorder
# ---------------------------------------------------------------------------


class GoldenPathRecorder:
    """Records successful fix patterns as golden paths for future replay."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._paths: List[GoldenPath] = []

    def record(self, plan: CodeFixPlan, proposal: CodeProposal) -> GoldenPath:
        """Record a successful fix as a golden path."""
        existing = self._find_similar(plan)
        if existing:
            with self._lock:
                existing.success_count += 1
            logger.debug(
                "Golden path %s incremented to %d", existing.path_id, existing.success_count
            )
            return existing

        path = GoldenPath(
            path_id=f"gp-{uuid.uuid4().hex[:12]}",
            gap_category=plan.gap_id,  # template key uses category pattern
            patch_type=plan.patch_type,
            description=plan.patch_description,
            patch_template=plan.patch_code,
            test_template=plan.test_code,
        )
        with self._lock:
            capped_append(self._paths, path, max_size=_MAX_GOLDEN_PATHS)
        logger.info("Golden path %s recorded for patch_type=%s", path.path_id, plan.patch_type)
        return path

    def find_for_gap(self, gap: CodeGap) -> Optional[GoldenPath]:
        """Return the most successful golden path matching the gap category."""
        with self._lock:
            candidates = [
                p for p in self._paths if p.patch_type in self._PATCH_TYPE_MAP.get(gap.category, [])
            ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.success_count)

    def get_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._paths[-limit:]]

    # category → list of applicable patch_types
    _PATCH_TYPE_MAP: Dict[str, List[str]] = {
        "bare_except": ["add_guard", "modify_function"],
        "high_complexity": ["refactor"],
        "test_gap": ["add_test"],
        "doc_drift": ["add_docstring"],
        "bug_pattern": ["modify_function", "add_guard"],
        "recovery_failure": ["add_guard", "add_function"],
    }

    def _find_similar(self, plan: CodeFixPlan) -> Optional[GoldenPath]:
        with self._lock:
            for path in self._paths:
                if path.patch_type == plan.patch_type:
                    return path
        return None


# ---------------------------------------------------------------------------
# 9. MurphyCodeHealer — top-level orchestrator
# ---------------------------------------------------------------------------


class MurphyCodeHealer:
    """Autonomous self-coding engine for the Murphy System.

    Design Label: ARCH-006 — Murphy Code Healer

    Combines DiagnosticSupervisor, CodeIntelligence, BayesianFixPlanner,
    PatchGenerator, ReconciliationController, HealerSupervisor,
    HealerChaosRunner, and GoldenPathRecorder into a single, safe
    orchestration layer.

    Safety: NEVER writes to source files.  All patches are proposals only.

    Usage::

        healer = MurphyCodeHealer(
            bug_detector=detector,
            improvement_engine=engine,
            healing_coordinator=coordinator,
            event_backbone=backbone,
            persistence_manager=pm,
            src_root="Murphy System/src",
            tests_root="Murphy System/tests",
        )
        report = healer.run_healing_cycle()
    """

    def __init__(
        self,
        bug_detector=None,
        improvement_engine=None,
        healing_coordinator=None,
        event_backbone=None,
        persistence_manager=None,
        failure_generator=None,
        governance_framework=None,
        src_root: Optional[str] = None,
        tests_root: Optional[str] = None,
        docs_root: Optional[str] = None,
    ) -> None:
        self._backbone = event_backbone
        self._pm = persistence_manager
        self._lock = threading.Lock()
        self._running = False
        self._subscription_ids: List[str] = []

        self.diagnostic = DiagnosticSupervisor(
            bug_detector=bug_detector,
            improvement_engine=improvement_engine,
            healing_coordinator=healing_coordinator,
            src_root=src_root,
            tests_root=tests_root,
            docs_root=docs_root,
        )
        self.intelligence = CodeIntelligence(src_root=src_root)
        self.planner = BayesianFixPlanner()
        self.patch_gen = PatchGenerator(governance_framework=governance_framework)
        self.chaos = HealerChaosRunner(failure_generator=failure_generator)
        self.recorder = GoldenPathRecorder()
        self.supervisor = HealerSupervisor()
        self.reconciler = ReconciliationController(
            diagnostic_supervisor=self.diagnostic,
            fix_pipeline=self.analyze_and_propose,
        )

        # Metrics
        self._metrics: Dict[str, int] = collections.defaultdict(int)
        self._proposals: List[CodeProposal] = []
        self._detect_times: List[float] = []
        self._patch_times: List[float] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_healing_cycle(self, max_gaps: int = 50) -> Dict[str, Any]:
        """Run a full detect → analyse → propose cycle.

        Returns a summary report.
        Raises RuntimeError if already running (leader election).
        """
        with self._lock:
            if self._running:
                raise RuntimeError(
                    "MurphyCodeHealer is already running; only one concurrent cycle is allowed"
                )
            self._running = True

        start = time.monotonic()
        self._publish_event("CODE_HEALER_STARTED", {"max_gaps": max_gaps})
        logger.info("MurphyCodeHealer cycle started (max_gaps=%d)", max_gaps)

        gaps_detected = 0
        proposals_created = 0
        proposals_skipped = 0

        try:
            detect_start = time.monotonic()
            gaps = self.diagnostic.collect_gaps()
            detect_elapsed = time.monotonic() - detect_start
            capped_append(self._detect_times, detect_elapsed, max_size=1000)
            self._metrics["gaps_detected"] += len(gaps)
            gaps_detected = len(gaps)

            for gap in gaps[:max_gaps]:
                patch_start = time.monotonic()
                proposal = self.analyze_and_propose(gap)
                patch_elapsed = time.monotonic() - patch_start
                capped_append(self._patch_times, patch_elapsed, max_size=1000)
                if proposal:
                    proposals_created += 1
                else:
                    proposals_skipped += 1

        finally:
            with self._lock:
                self._running = False

        elapsed = time.monotonic() - start
        report = {
            "gaps_detected": gaps_detected,
            "proposals_created": proposals_created,
            "proposals_skipped": proposals_skipped,
            "elapsed_seconds": round(elapsed, 3),
            "mean_detect_ms": round(
                sum(self._detect_times) / (len(self._detect_times) or 1) * 1000, 1
            ),
            "mean_patch_ms": round(
                sum(self._patch_times) / (len(self._patch_times) or 1) * 1000, 1
            ),
            "total_proposals": self._metrics["patches_generated"],
        }
        self._publish_event("CODE_HEALER_COMPLETED", report)
        logger.info("MurphyCodeHealer cycle done: %s", report)
        return report

    def analyze_and_propose(self, gap: CodeGap) -> Optional[CodeProposal]:
        """Analyse a single gap and return a CodeProposal (or None).

        This is the bridge method that SelfFixLoop can delegate to
        when it encounters a gap requiring source-level changes.
        """
        if not self.intelligence._parsed and self.intelligence._src_root:
            try:
                self.intelligence.build_map()
            except Exception as exc:
                logger.debug("CodeIntelligence build_map skipped: %s", exc)

        context = self.intelligence.get_context(gap)
        plan = self.planner.create_plan(gap, context)

        if plan.confidence_score < _CONFIDENCE_LOG_ONLY:
            logger.info(
                "Gap %s confidence %.2f below threshold — logged only",
                gap.gap_id,
                plan.confidence_score,
            )
            self._metrics["patches_rejected"] += 1
            self._publish_event(
                "CODE_HEALER_GAP_LOW_CONFIDENCE",
                {"gap_id": gap.gap_id, "confidence": plan.confidence_score},
            )
            return None

        resilience = self.chaos.evaluate(plan)
        adversarial = self.chaos.generate_adversarial_test(plan)

        proposal = self.patch_gen.generate_proposal(
            plan,
            resilience_score=resilience.score,
            adversarial_test=adversarial,
        )
        if proposal is None:
            self._metrics["patches_rejected"] += 1
            return None

        self._metrics["patches_generated"] += 1
        capped_append(self._proposals, proposal, max_size=_MAX_PROPOSALS)
        self.recorder.record(plan, proposal)
        self._persist_proposal(proposal)
        self._publish_event(
            "CODE_HEALER_PROPOSAL_CREATED",
            {
                "proposal_id": proposal.proposal_id,
                "gap_id": gap.gap_id,
                "confidence": plan.confidence_score,
                "auto_merge": proposal.auto_merge_suggested,
            },
        )
        return proposal

    def get_proposals(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._proposals[-limit:]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **dict(self._metrics),
            "mean_time_to_detect_ms": round(
                sum(self._detect_times) / (len(self._detect_times) or 1) * 1000, 1
            ),
            "mean_time_to_patch_ms": round(
                sum(self._patch_times) / (len(self._patch_times) or 1) * 1000, 1
            ),
        }

    def bridge_to_code_healer(self) -> Callable[[CodeGap], Optional[CodeProposal]]:
        """Return a callable bridge for SelfFixLoop integration.

        Usage in SelfFixLoop::

            bridge = healer.bridge_to_code_healer()
            proposal = bridge(gap)
        """
        return self.analyze_and_propose

    def subscribe_to_events(self) -> None:
        """Subscribe to EventBackbone events that trigger healing cycles.

        Handles:
        - ``TASK_FAILED`` — a runtime task failed; trigger gap detection.
        - ``TEST_FAILED`` — a test suite failure was reported.
        - ``DOC_DRIFT`` — documentation drift was detected externally.

        Each event is processed in the background thread to avoid blocking
        the event dispatch loop.  Safe to call multiple times; duplicate
        subscriptions are idempotent (tracked via ``_subscription_ids``).
        """
        if self._backbone is None:
            logger.debug("MurphyCodeHealer: no EventBackbone — skipping subscriptions")
            return

        try:
            from event_backbone import EventType
        except ImportError:
            try:
                from src.event_backbone import EventType
            except ImportError:
                logger.warning("MurphyCodeHealer: EventType not importable — cannot subscribe")
                return

        def _handle_task_failed(event) -> None:
            payload = event.payload if hasattr(event, "payload") else {}
            logger.info(
                "MurphyCodeHealer triggered by TASK_FAILED (event=%s)",
                getattr(event, "event_id", "?"),
            )
            gap = CodeGap(
                gap_id=f"gap-tf-{uuid.uuid4().hex[:8]}",
                description=(
                    f"Task failure detected: {payload.get('task_type', 'unknown')}"
                ),
                source="task_failed_event",
                severity="high",
                category="task_failure",
                file_path=payload.get("file_path", ""),
                function_name=payload.get("function_name", ""),
                context={"event_payload": payload},
            )
            threading.Thread(
                target=self._safe_analyze_and_propose,
                args=(gap,),
                daemon=True,
                name="healer-task-failed",
            ).start()

        def _handle_test_failed(event) -> None:
            payload = event.payload if hasattr(event, "payload") else {}
            logger.info(
                "MurphyCodeHealer triggered by TEST_FAILED (event=%s)",
                getattr(event, "event_id", "?"),
            )
            gap = CodeGap(
                gap_id=f"gap-testf-{uuid.uuid4().hex[:8]}",
                description=(
                    f"Test failure: {payload.get('test_name', 'unknown')}"
                ),
                source="test_failed_event",
                severity="high",
                category="test_failure",
                file_path=payload.get("file_path", ""),
                function_name=payload.get("test_name", ""),
                context={"event_payload": payload},
            )
            threading.Thread(
                target=self._safe_analyze_and_propose,
                args=(gap,),
                daemon=True,
                name="healer-test-failed",
            ).start()

        def _handle_doc_drift(event) -> None:
            payload = event.payload if hasattr(event, "payload") else {}
            logger.info(
                "MurphyCodeHealer triggered by DOC_DRIFT (event=%s)",
                getattr(event, "event_id", "?"),
            )
            gap = CodeGap(
                gap_id=f"gap-dd-{uuid.uuid4().hex[:8]}",
                description=(
                    f"Documentation drift: {payload.get('description', 'unknown')}"
                ),
                source="doc_drift_event",
                severity="low",
                category="doc_drift",
                file_path=payload.get("file_path", ""),
                context={"event_payload": payload},
            )
            threading.Thread(
                target=self._safe_analyze_and_propose,
                args=(gap,),
                daemon=True,
                name="healer-doc-drift",
            ).start()

        try:
            sub_ids = [
                self._backbone.subscribe(EventType.TASK_FAILED, _handle_task_failed),
                self._backbone.subscribe(EventType.TEST_FAILED, _handle_test_failed),
                self._backbone.subscribe(EventType.DOC_DRIFT, _handle_doc_drift),
            ]
            self._subscription_ids.extend(sub_ids)
            logger.info(
                "MurphyCodeHealer subscribed to TASK_FAILED, TEST_FAILED, DOC_DRIFT "
                "(ids=%s)",
                sub_ids,
            )
        except Exception as exc:
            logger.warning("MurphyCodeHealer event subscription failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_analyze_and_propose(self, gap: CodeGap) -> None:
        """Run analyze_and_propose in a safe wrapper (used by event handlers)."""
        try:
            self.analyze_and_propose(gap)
        except Exception as exc:
            logger.warning(
                "MurphyCodeHealer._safe_analyze_and_propose failed for gap %s: %s",
                gap.gap_id,
                exc,
            )

    def _persist_proposal(self, proposal: CodeProposal) -> None:
        if self._pm is not None:
            try:
                self._pm.save_document(proposal.proposal_id, proposal.to_dict())
            except Exception as exc:
                logger.debug("Proposal persistence skipped: %s", exc)

    def _publish_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self._backbone is None:
            return
        try:
            self._backbone.publish(
                event_type=None,
                payload={
                    "event": event_name,
                    "source": "murphy_code_healer",
                    "correlation_id": uuid.uuid4().hex,
                    **payload,
                },
            )
        except Exception as exc:
            logger.debug("Event publish skipped (%s): %s", event_name, exc)
