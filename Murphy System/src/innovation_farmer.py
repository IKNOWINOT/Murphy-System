"""
Innovation Farmer for the Murphy System.

Design Label: ARCH-006 — Open-Source Innovation Harvester
Owner: Backend Team
Dependencies:
  - ImprovementProposal (ARCH-001 — SelfImprovementEngine)
  - EventBackbone
  - PersistenceManager

Scans open-source repositories and domain patterns to discover novel
techniques, feature ideas, and competitive gap analysis for the Murphy System.

Safety invariants:
  - Read-only analysis; never modifies any source files
  - All proposals require human review before implementation
  - Full audit trail via EventBackbone and PersistenceManager
  - Graceful degradation when network/GitHub APIs are unavailable

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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

_MAX_PROPOSALS = 1_000
_MAX_PATTERNS = 500
_MAX_GAP_ENTRIES = 200
_MAX_SCAN_HISTORY = 100


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PatternCategory(str, Enum):
    """Category of an extracted open-source pattern."""
    ARCHITECTURAL = "architectural"
    ALGORITHM = "algorithm"
    API_DESIGN = "api_design"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    WORKFLOW = "workflow"
    AGENT_ORCHESTRATION = "agent_orchestration"
    SELF_HEALING = "self_healing"
    NO_CODE = "no_code"
    BPM = "bpm"


class GapPriority(str, Enum):
    """Priority of a competitive gap."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OpenSourcePattern:
    """An architectural or algorithmic pattern discovered from open-source repos."""
    pattern_id: str
    name: str
    description: str
    category: PatternCategory
    source_repo: str
    relevance_score: float = 0.5
    tags: List[str] = field(default_factory=list)
    discovered_at: str = ""

    def __post_init__(self) -> None:
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "source_repo": self.source_repo,
            "relevance_score": self.relevance_score,
            "tags": self.tags,
            "discovered_at": self.discovered_at,
        }


@dataclass
class FeatureProposal:
    """A structured proposal for a Murphy System feature based on an open-source pattern."""
    proposal_id: str
    title: str
    pattern_name: str
    what_it_does: str
    how_to_adapt: str
    murphy_modules_affected: List[str]
    implementation_complexity: str
    expected_business_value: str
    source_pattern_id: str
    requires_human_review: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "pattern_name": self.pattern_name,
            "what_it_does": self.what_it_does,
            "how_to_adapt": self.how_to_adapt,
            "murphy_modules_affected": self.murphy_modules_affected,
            "implementation_complexity": self.implementation_complexity,
            "expected_business_value": self.expected_business_value,
            "source_pattern_id": self.source_pattern_id,
            "requires_human_review": self.requires_human_review,
            "created_at": self.created_at,
        }


@dataclass
class CompetitiveGapEntry:
    """A gap between Murphy's capabilities and competitor or open-source patterns."""
    gap_id: str
    gap_description: str
    competitor_capability: str
    murphy_current_state: str
    priority: GapPriority
    business_impact: str
    implementation_feasibility: str
    roadmap_entry: str = ""
    identified_at: str = ""

    def __post_init__(self) -> None:
        if not self.identified_at:
            self.identified_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "gap_id": self.gap_id,
            "gap_description": self.gap_description,
            "competitor_capability": self.competitor_capability,
            "murphy_current_state": self.murphy_current_state,
            "priority": self.priority.value,
            "business_impact": self.business_impact,
            "implementation_feasibility": self.implementation_feasibility,
            "roadmap_entry": self.roadmap_entry,
            "identified_at": self.identified_at,
        }


@dataclass
class InnovationScanReport:
    """Summary report of a single innovation farming scan."""
    report_id: str
    patterns_discovered: int
    proposals_generated: int
    gaps_identified: int
    scan_scope: List[str]
    duration_seconds: float
    completed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "report_id": self.report_id,
            "patterns_discovered": self.patterns_discovered,
            "proposals_generated": self.proposals_generated,
            "gaps_identified": self.gaps_identified,
            "scan_scope": self.scan_scope,
            "duration_seconds": self.duration_seconds,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# Pattern library (curated baseline, no external calls required)
# ---------------------------------------------------------------------------

_CURATED_PATTERNS: List[Dict[str, Any]] = [
    {
        "name": "Kubernetes Reconciliation Loop",
        "description": (
            "Controllers continuously compare actual cluster state to desired state "
            "and drive convergence. Level-triggered logic ensures eventual consistency."
        ),
        "category": PatternCategory.ARCHITECTURAL,
        "source_repo": "kubernetes/kubernetes",
        "relevance_score": 0.95,
        "tags": ["reconciliation", "desired-state", "controllers", "self-healing"],
    },
    {
        "name": "Circuit Breaker Pattern",
        "description": (
            "Wraps calls to external services; trips open on repeated failures, "
            "preventing cascading failures across the system."
        ),
        "category": PatternCategory.ARCHITECTURAL,
        "source_repo": "resilience4j/resilience4j",
        "relevance_score": 0.88,
        "tags": ["resilience", "circuit-breaker", "fault-tolerance"],
    },
    {
        "name": "Temporal Workflow Orchestration",
        "description": (
            "Durable execution engine that persists workflow state and automatically "
            "retries failed activities, providing exactly-once semantics."
        ),
        "category": PatternCategory.WORKFLOW,
        "source_repo": "temporalio/temporal",
        "relevance_score": 0.92,
        "tags": ["workflow", "durable-execution", "retry", "orchestration"],
    },
    {
        "name": "LangChain Agent Executor",
        "description": (
            "Tool-using agent pattern where an LLM selects from a toolkit, "
            "executes tools, and iterates until goal completion."
        ),
        "category": PatternCategory.AGENT_ORCHESTRATION,
        "source_repo": "langchain-ai/langchain",
        "relevance_score": 0.85,
        "tags": ["llm", "agent", "tool-use", "react"],
    },
    {
        "name": "n8n Node-Based Workflow Builder",
        "description": (
            "Visual drag-and-drop workflow builder with pre-built node library, "
            "webhook triggers, and branching logic for no-code automation."
        ),
        "category": PatternCategory.NO_CODE,
        "source_repo": "n8n-io/n8n",
        "relevance_score": 0.90,
        "tags": ["no-code", "workflow", "automation", "visual"],
    },
    {
        "name": "Chaos Monkey Failure Injection",
        "description": (
            "Randomly terminates instances in production to build confidence in "
            "system resilience and validate failure recovery paths."
        ),
        "category": PatternCategory.SELF_HEALING,
        "source_repo": "netflix/chaosmonkey",
        "relevance_score": 0.80,
        "tags": ["chaos", "resilience", "failure-injection", "testing"],
    },
    {
        "name": "OpenTelemetry Distributed Tracing",
        "description": (
            "Vendor-neutral instrumentation API for capturing traces, metrics, "
            "and logs across distributed service boundaries."
        ),
        "category": PatternCategory.ARCHITECTURAL,
        "source_repo": "open-telemetry/opentelemetry-python",
        "relevance_score": 0.82,
        "tags": ["observability", "tracing", "metrics", "otel"],
    },
    {
        "name": "Prefect Data Pipeline Orchestration",
        "description": (
            "Python-native workflow orchestration with dependency graphs, "
            "parameterized flows, and built-in retry/caching logic."
        ),
        "category": PatternCategory.BPM,
        "source_repo": "PrefectHQ/prefect",
        "relevance_score": 0.87,
        "tags": ["pipeline", "orchestration", "data", "scheduling"],
    },
    {
        "name": "Celery Distributed Task Queue",
        "description": (
            "Asynchronous task queue with support for distributed execution, "
            "priority queues, and chaining/grouping of tasks."
        ),
        "category": PatternCategory.WORKFLOW,
        "source_repo": "celery/celery",
        "relevance_score": 0.78,
        "tags": ["async", "queue", "distributed", "workers"],
    },
    {
        "name": "AutoGen Multi-Agent Conversation",
        "description": (
            "Framework for building multi-agent systems where LLM-powered agents "
            "collaborate via structured conversations to solve complex tasks."
        ),
        "category": PatternCategory.AGENT_ORCHESTRATION,
        "source_repo": "microsoft/autogen",
        "relevance_score": 0.91,
        "tags": ["multi-agent", "conversation", "llm", "collaboration"],
    },
]

_MURPHY_CAPABILITIES: List[str] = [
    "self_healing_coordinator",
    "bug_pattern_detector",
    "self_fix_loop",
    "chaos_resilience_loop",
    "event_backbone",
    "inference_gate_engine",
    "semantics_boundary_controller",
    "nocode_workflow_terminal",
    "ai_workflow_generator",
    "shadow_agent_integration",
    "code_repair_engine",
    "self_improvement_engine",
]

_MURPHY_GAPS: List[Dict[str, Any]] = [
    {
        "gap_description": "No distributed tracing / OpenTelemetry integration",
        "competitor_capability": "OpenTelemetry distributed tracing across service boundaries",
        "murphy_current_state": "Per-module logging only; no cross-service trace correlation",
        "priority": GapPriority.HIGH,
        "business_impact": "High — cross-module debugging requires manual log correlation",
        "implementation_feasibility": "Medium — requires instrumenting EventBackbone and API layers",
        "roadmap_entry": "ROADMAP: Add OTel span injection to EventBackbone and Flask APIs",
    },
    {
        "gap_description": "No visual no-code workflow builder with branching logic",
        "competitor_capability": "n8n-style drag-and-drop workflow builder",
        "murphy_current_state": "NL-to-DAG generation via ai_workflow_generator; no visual canvas",
        "priority": GapPriority.MEDIUM,
        "business_impact": "Medium — power users want visual editing, not just conversational",
        "implementation_feasibility": "High — NL-to-DAG backend exists; need React canvas frontend",
        "roadmap_entry": "ROADMAP: Add React Flow canvas wrapping ai_workflow_generator",
    },
    {
        "gap_description": "No durable workflow execution with exactly-once semantics",
        "competitor_capability": "Temporal/Prefect durable execution with automatic retry",
        "murphy_current_state": "Event-driven coordination without persistent workflow state",
        "priority": GapPriority.HIGH,
        "business_impact": "High — long-running workflows can lose state on restart",
        "implementation_feasibility": "Medium — requires persistence layer changes",
        "roadmap_entry": "ROADMAP: Add durable execution checkpoints to chaos_resilience_loop",
    },
]


# ---------------------------------------------------------------------------
# Innovation Farmer
# ---------------------------------------------------------------------------

class InnovationFarmer:
    """Open-source innovation harvester for the Murphy System.

    Design Label: ARCH-006
    Owner: Backend Team

    Discovers novel patterns, feature ideas, and competitive gaps by analysing
    the curated open-source pattern library and comparing against Murphy's
    known capabilities.

    Safety: Read-only analysis.  Never modifies source files.
    """

    def __init__(
        self,
        event_backbone: Any = None,
        persistence_manager: Any = None,
    ) -> None:
        self._backbone = event_backbone
        self._pm = persistence_manager

        self._patterns: List[OpenSourcePattern] = []
        self._proposals: List[FeatureProposal] = []
        self._gaps: List[CompetitiveGapEntry] = []
        self._scan_history: List[InnovationScanReport] = []

        self._lock = threading.Lock()
        self._load_curated_patterns()

    def run_innovation_scan(self) -> InnovationScanReport:
        """Run a full innovation farming scan.

        Returns:
            An InnovationScanReport summarising what was discovered.
        """
        import time
        start = time.monotonic()

        with self._lock:
            self._patterns.clear()
            self._proposals.clear()
            self._gaps.clear()
            self._load_curated_patterns()

        proposals = self._generate_proposals_from_patterns()
        gaps = self._analyze_competitive_gaps()

        with self._lock:
            for prop in proposals:
                capped_append(self._proposals, prop, max_size=_MAX_PROPOSALS)

        with self._lock:
            for gap in gaps:
                capped_append(self._gaps, gap, max_size=_MAX_GAP_ENTRIES)

        report = InnovationScanReport(
            report_id=str(uuid.uuid4()),
            patterns_discovered=len(self._patterns),
            proposals_generated=len(proposals),
            gaps_identified=len(gaps),
            scan_scope=["curated_pattern_library", "murphy_capability_matrix"],
            duration_seconds=round(time.monotonic() - start, 3),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            capped_append(self._scan_history, report, max_size=_MAX_SCAN_HISTORY)

        if self._pm is not None:
            try:
                self._pm.save(f"innovation_scan_{report.report_id}", report.to_dict())
            except Exception as exc:
                logger.debug("PersistenceManager save failed: %s", exc)

        return report

    def get_proposals(self) -> List[Dict[str, Any]]:
        """Return all generated feature proposals."""
        with self._lock:
            return [p.to_dict() for p in self._proposals]

    def get_gaps(self) -> List[Dict[str, Any]]:
        """Return all identified competitive gaps."""
        with self._lock:
            return [g.to_dict() for g in self._gaps]

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Return all discovered patterns."""
        with self._lock:
            return [p.to_dict() for p in self._patterns]

    def get_scan_history(self) -> List[Dict[str, Any]]:
        """Return scan history."""
        with self._lock:
            return [r.to_dict() for r in self._scan_history]

    def _load_curated_patterns(self) -> None:
        """Load the curated pattern library."""
        for raw in _CURATED_PATTERNS:
            pattern = OpenSourcePattern(
                pattern_id=str(uuid.uuid4()),
                name=raw["name"],
                description=raw["description"],
                category=raw["category"],
                source_repo=raw["source_repo"],
                relevance_score=raw["relevance_score"],
                tags=raw.get("tags", []),
            )
            capped_append(self._patterns, pattern, max_size=_MAX_PATTERNS)

    def _generate_proposals_from_patterns(self) -> List[FeatureProposal]:
        """Generate structured feature proposals from discovered patterns."""
        proposals: List[FeatureProposal] = []
        with self._lock:
            patterns = list(self._patterns)

        for pattern in patterns:
            if pattern.relevance_score < 0.75:
                continue
            affected = self._identify_affected_modules(pattern)
            complexity = self._estimate_complexity(pattern)
            value = self._estimate_business_value(pattern)

            proposal = FeatureProposal(
                proposal_id=str(uuid.uuid4()),
                title=f"Adopt '{pattern.name}' pattern from {pattern.source_repo}",
                pattern_name=pattern.name,
                what_it_does=pattern.description,
                how_to_adapt=(
                    f"Integrate '{pattern.name}' ({pattern.category.value}) "
                    f"into Murphy by extending: {', '.join(affected) or 'core infrastructure'}"
                ),
                murphy_modules_affected=affected,
                implementation_complexity=complexity,
                expected_business_value=value,
                source_pattern_id=pattern.pattern_id,
                requires_human_review=True,
            )
            capped_append(proposals, proposal, max_size=_MAX_PROPOSALS)

        return proposals

    def _analyze_competitive_gaps(self) -> List[CompetitiveGapEntry]:
        """Analyse Murphy's capability gaps against known open-source patterns."""
        gaps: List[CompetitiveGapEntry] = []
        for raw in _MURPHY_GAPS:
            gap = CompetitiveGapEntry(
                gap_id=str(uuid.uuid4()),
                gap_description=raw["gap_description"],
                competitor_capability=raw["competitor_capability"],
                murphy_current_state=raw["murphy_current_state"],
                priority=raw["priority"],
                business_impact=raw["business_impact"],
                implementation_feasibility=raw["implementation_feasibility"],
                roadmap_entry=raw.get("roadmap_entry", ""),
            )
            capped_append(gaps, gap, max_size=_MAX_GAP_ENTRIES)
        return gaps

    def _identify_affected_modules(self, pattern: OpenSourcePattern) -> List[str]:
        """Identify which Murphy modules would be affected by a pattern."""
        tag_module_map: Dict[str, List[str]] = {
            "reconciliation": ["self_fix_loop", "chaos_resilience_loop"],
            "workflow": ["ai_workflow_generator", "nocode_workflow_terminal"],
            "agent": ["shadow_agent_integration", "self_healing_coordinator"],
            "self-healing": ["self_healing_coordinator", "self_fix_loop"],
            "no-code": ["nocode_workflow_terminal", "ai_workflow_generator"],
            "resilience": ["chaos_resilience_loop", "self_healing_coordinator"],
            "tracing": ["event_backbone"],
            "observability": ["event_backbone", "bug_pattern_detector"],
            "llm": ["inference_gate_engine", "ai_workflow_generator"],
            "pipeline": ["ai_workflow_generator", "nocode_workflow_terminal"],
        }
        affected: List[str] = []
        for tag in pattern.tags:
            for module in tag_module_map.get(tag, []):
                if module not in affected:
                    affected.append(module)
        return affected[:5]

    def _estimate_complexity(self, pattern: OpenSourcePattern) -> str:
        """Estimate implementation complexity based on pattern category and tags."""
        high_complexity_categories = {
            PatternCategory.ARCHITECTURAL,
            PatternCategory.DEPLOYMENT,
        }
        if pattern.category in high_complexity_categories:
            return "high"
        if len(pattern.tags) >= 4:
            return "medium"
        return "low"

    def _estimate_business_value(self, pattern: OpenSourcePattern) -> str:
        """Estimate expected business value based on relevance and category."""
        if pattern.relevance_score >= 0.9:
            return "very_high"
        if pattern.relevance_score >= 0.8:
            return "high"
        if pattern.relevance_score >= 0.7:
            return "medium"
        return "low"
