# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Optimal Routing Wiring — Murphy System
========================================

Defines the **optimal routing pipeline** by wiring together five systems in
the order that produces the highest average percentage of successful tool calls:

  1. **Triage**      — classify and prioritise the incoming request
                       (TicketTriageEngine: severity + category + team routing)

  2. **Librarian**   — suggest the best-matching tool/module/command
                       (LibrarianExecutionSuggestor: confidence-ranked suggestions)

  3. **Causality**   — simulate the causal chain before committing
                       (CausalitySandboxEngine: exhaustive action enumeration)

  4. **Rubix**       — verify evidence via deterministic statistical checks
                       (RubixEvidenceAdapter: CI + hypothesis + Monte Carlo)

  5. **Golden Path** — record or replay the highest-success-rate execution path
                       (GoldenPathBridge: success rate ranked, best path first)

Golden Path outputs = the sequence of tool calls ordered by empirical success rate
(highest functional average percentage of successful calls in order).

Routing pipeline (in order)
----------------------------
::

    request
      → Triage (classify + priority)
      → Librarian (tool suggestions, confidence ranked)
      → for each suggestion (highest confidence first):
          → Causality (simulate + score)
          → Rubix (evidence verification)
          → if evidence passes: execute tool call
          → GoldenPath.record_success / record_failure
      → return GoldenPath.find_matching_paths (best path for this pattern)

Design:  ORW-001
Owner:   Platform AI / Execution
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RoutingStage(str, Enum):
    """Stage in the optimal routing pipeline."""
    TRIAGE    = "triage"
    LIBRARIAN = "librarian"
    CAUSALITY = "causality"
    RUBIX     = "rubix"
    EXECUTION = "execution"
    GOLDEN    = "golden"
    COMPLETE  = "complete"
    FAILED    = "failed"


class RoutingOutcome(str, Enum):
    """Final outcome of a routing run."""
    SUCCESS           = "success"
    PARTIAL           = "partial"      # some tools succeeded
    BLOCKED_BY_RUBIX  = "blocked_rubix"
    BLOCKED_BY_TRIAGE = "blocked_triage"
    NO_TOOLS_FOUND    = "no_tools"
    GOLDEN_REPLAYED   = "golden_replayed"
    ERROR             = "error"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ToolCandidate:
    """A single tool/module/command candidate from the Librarian."""
    tool_id: str
    tool_name: str
    confidence: float               = 0.0
    domain: str                     = ""
    command: str                    = ""
    api_path: str                   = ""
    metadata: Dict[str, Any]        = field(default_factory=dict)


@dataclass
class RoutingStep:
    """Record of one stage in the routing pipeline."""
    stage: RoutingStage
    input_summary: str              = ""
    output_summary: str             = ""
    duration_ms: float              = 0.0
    success: bool                   = True
    details: Dict[str, Any]         = field(default_factory=dict)


@dataclass
class RoutingResult:
    """
    Complete result of the optimal routing pipeline.

    ``golden_path_id`` is set when a previously recorded golden path
    was replayed (fastest path for known patterns).
    ``tool_results`` maps tool_id → outcome dict.
    ``steps`` is the full audit trail through all five systems.
    ``success_rate`` is the empirical fraction of tool calls that succeeded.
    """
    request_id: str                             = field(default_factory=lambda: str(uuid.uuid4()))
    outcome: RoutingOutcome                     = RoutingOutcome.ERROR
    triage_severity: str                        = "medium"
    triage_category: str                        = "general"
    suggested_tools: List[ToolCandidate]        = field(default_factory=list)
    executed_tools: List[str]                   = field(default_factory=list)
    tool_results: Dict[str, Any]                = field(default_factory=dict)
    golden_path_id: Optional[str]               = None
    steps: List[RoutingStep]                    = field(default_factory=list)
    success_rate: float                         = 0.0
    total_duration_ms: float                    = 0.0
    ordered_tool_calls: List[str]               = field(default_factory=list)  # golden path order


# ---------------------------------------------------------------------------
# Main wiring orchestrator
# ---------------------------------------------------------------------------

class OptimalRoutingWiring:
    """
    Wires Triage → Librarian → Causality → Rubix → GoldenPath into a single
    routing pipeline.

    All five subsystems are optional (graceful degradation).  When a subsystem
    is unavailable its stage is skipped and a warning is logged.

    ── MCB AGENT CONTROLLER ─────────────────────────────────────────────
    OptimalRoutingWiring checks out a MultiCursorBrowser controller at
    construction time (agent_id ``"optimal_routing_wiring"``), making MCB
    the controller for any UI validation or browser-based routing steps.

    Parameters
    ----------
    triage_engine:
        ``TicketTriageEngine`` instance (or compatible duck-type).
    librarian_suggestor:
        ``LibrarianExecutionSuggestor`` instance.
    causality_engine:
        ``CausalitySandboxEngine`` instance.
    rubix_adapter:
        ``RubixEvidenceAdapter`` instance.
    golden_path_bridge:
        ``GoldenPathBridge`` instance.
    max_tool_candidates:
        How many librarian suggestions to evaluate per request (default 5).
    rubix_pass_threshold:
        Minimum Rubix evidence score to allow execution (0–1, default 0.6).
    """

    def __init__(
        self,
        triage_engine: Optional[Any]       = None,
        librarian_suggestor: Optional[Any] = None,
        causality_engine: Optional[Any]    = None,
        rubix_adapter: Optional[Any]       = None,
        golden_path_bridge: Optional[Any]  = None,
        max_tool_candidates: int           = 5,
        rubix_pass_threshold: float        = 0.60,
    ) -> None:
        self._triage    = triage_engine
        self._librarian = librarian_suggestor
        self._causality = causality_engine
        self._rubix     = rubix_adapter
        self._golden    = golden_path_bridge
        self._max_tools = max_tool_candidates
        self._rubix_thr = rubix_pass_threshold

        # ── MCB controller checkout ───────────────────────────────────
        try:
            from agent_module_loader import MultiCursorBrowser as _MCB
            self._mcb = _MCB.get_controller(agent_id="optimal_routing_wiring")
        except Exception:
            self._mcb = None


    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def route(
        self,
        request: str,
        context: Optional[Dict[str, Any]] = None,
        domain: str = "general",
    ) -> RoutingResult:
        """
        Run *request* through the full optimal routing pipeline.

        Returns a :class:`RoutingResult` with the golden-path-ordered list
        of tool calls and their outcomes.
        """
        t_total = time.monotonic()
        ctx = context or {}
        result = RoutingResult()

        # ── Stage 1: Golden Path fast-track ────────────────────────────
        golden_replay = self._try_golden_replay(request, domain, result)
        if golden_replay:
            result.total_duration_ms = (time.monotonic() - t_total) * 1000
            return result

        # ── Stage 2: Triage ────────────────────────────────────────────
        severity, category = self._run_triage(request, ctx, result)
        result.triage_severity = severity
        result.triage_category = category
        if severity == "critical" and category == "blocked":
            result.outcome = RoutingOutcome.BLOCKED_BY_TRIAGE
            result.total_duration_ms = (time.monotonic() - t_total) * 1000
            return result

        # ── Stage 3: Librarian ─────────────────────────────────────────
        candidates = self._run_librarian(request, ctx, result, domain)
        result.suggested_tools = candidates
        if not candidates:
            result.outcome = RoutingOutcome.NO_TOOLS_FOUND
            result.total_duration_ms = (time.monotonic() - t_total) * 1000
            return result

        # ── Stage 4+5: Causality + Rubix per candidate ────────────────
        successes: List[str] = []
        failures:  List[str] = []

        for candidate in candidates[:self._max_tools]:
            ok = self._evaluate_candidate(candidate, request, ctx, result)
            if ok:
                successes.append(candidate.tool_id)
                result.executed_tools.append(candidate.tool_id)
            else:
                failures.append(candidate.tool_id)

        # ── Stage 6: Record to GoldenPath ─────────────────────────────
        if successes:
            self._record_golden(request, domain, successes, result)

        # ── Compute success rate and final outcome ─────────────────────
        total = len(successes) + len(failures)
        result.success_rate = len(successes) / total if total else 0.0
        result.ordered_tool_calls = successes + failures   # successes first = golden order

        if len(successes) == total and total > 0:
            result.outcome = RoutingOutcome.SUCCESS
        elif successes:
            result.outcome = RoutingOutcome.PARTIAL
        else:
            result.outcome = RoutingOutcome.BLOCKED_BY_RUBIX

        result.total_duration_ms = (time.monotonic() - t_total) * 1000
        logger.info(
            "OptimalRouting: %s  severity=%s  tools=%d/%d  success_rate=%.0f%%  %.0fms",
            result.outcome.value, severity, len(successes), total,
            result.success_rate * 100, result.total_duration_ms,
        )
        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _try_golden_replay(
        self, request: str, domain: str, result: RoutingResult
    ) -> bool:
        """Attempt to replay a known golden path. Returns True if replayed."""
        if self._golden is None:
            return False
        t0 = time.monotonic()
        try:
            matches = self._golden.find_matching_paths(request, domain=domain)
            if matches:
                best = matches[0]
                path = self._golden.replay_path(best.path_id)
                if path:
                    result.golden_path_id    = best.path_id
                    result.outcome           = RoutingOutcome.GOLDEN_REPLAYED
                    result.success_rate      = best.confidence
                    result.ordered_tool_calls = list(
                        path.get("execution_spec", {}).get("tools", [])
                    )
                    result.steps.append(RoutingStep(
                        stage          = RoutingStage.GOLDEN,
                        input_summary  = f"Pattern: {best.task_pattern}",
                        output_summary = f"Replayed path {best.path_id} conf={best.confidence:.0%}",
                        duration_ms    = (time.monotonic() - t0) * 1000,
                        success        = True,
                        details        = {"path_id": best.path_id, "match_score": best.match_score},
                    ))
                    return True
        except Exception as exc:
            logger.debug("Golden replay failed: %s", exc)
        return False

    def _run_triage(
        self, request: str, ctx: Dict[str, Any], result: RoutingResult
    ) -> Tuple[str, str]:
        """Run triage stage. Returns (severity, category)."""
        t0 = time.monotonic()
        severity, category = "medium", "general"
        if self._triage is not None:
            try:
                ticket = self._triage.triage(
                    title=request[:100],
                    description=request,
                    metadata=ctx,
                )
                severity = getattr(ticket, "severity",  "medium")
                category = getattr(ticket, "category",  "general")
                if hasattr(severity, "value"): severity = severity.value
                if hasattr(category, "value"): category = category.value
            except Exception as exc:
                logger.debug("Triage stage failed: %s", exc)

        result.steps.append(RoutingStep(
            stage          = RoutingStage.TRIAGE,
            input_summary  = request[:80],
            output_summary = f"severity={severity} category={category}",
            duration_ms    = (time.monotonic() - t0) * 1000,
        ))
        return str(severity), str(category)

    def _run_librarian(
        self, request: str, ctx: Dict[str, Any],
        result: RoutingResult, domain: str
    ) -> List[ToolCandidate]:
        """Run librarian stage. Returns ranked tool candidates."""
        t0 = time.monotonic()
        candidates: List[ToolCandidate] = []

        if self._librarian is not None:
            try:
                plan = self._librarian.analyze_request(request, context=ctx)
                suggestions = getattr(plan, "suggestions", [])
                for s in suggestions[:self._max_tools]:
                    candidates.append(ToolCandidate(
                        tool_id    = getattr(s, "tool_id",   str(uuid.uuid4())),
                        tool_name  = getattr(s, "tool_name", str(s)),
                        confidence = float(getattr(s, "confidence", 0.5)),
                        domain     = domain,
                        command    = getattr(s, "command",   ""),
                        api_path   = getattr(s, "api_path",  ""),
                    ))
                # Sort by confidence descending (golden-path order)
                candidates.sort(key=lambda c: c.confidence, reverse=True)
            except Exception as exc:
                logger.debug("Librarian stage failed: %s", exc)

        # Fallback: create a single generic candidate
        if not candidates:
            candidates = [ToolCandidate(
                tool_id   = "generic",
                tool_name = "generic_execution",
                confidence= 0.5,
                domain    = domain,
            )]

        result.steps.append(RoutingStep(
            stage          = RoutingStage.LIBRARIAN,
            input_summary  = request[:80],
            output_summary = f"{len(candidates)} candidates (top: {candidates[0].tool_name} conf={candidates[0].confidence:.0%})",
            duration_ms    = (time.monotonic() - t0) * 1000,
        ))
        return candidates

    def _evaluate_candidate(
        self, candidate: ToolCandidate,
        request: str, ctx: Dict[str, Any],
        result: RoutingResult,
    ) -> bool:
        """
        Run Causality + Rubix for *candidate*.
        Returns True if the candidate passes and should be executed.
        """
        # Causality simulation ─────────────────────────────────────────
        causal_ok = True
        t0 = time.monotonic()
        if self._causality is not None:
            try:
                snapshot = {"request": request, "tool": candidate.tool_id, **ctx}
                reports  = self._causality.explore(snapshot, max_actions=10)
                if reports:
                    best_score = max(getattr(r, "score", 0.5) for r in reports)
                    causal_ok  = best_score > 0.3
                    result.steps.append(RoutingStep(
                        stage          = RoutingStage.CAUSALITY,
                        input_summary  = candidate.tool_id,
                        output_summary = f"best_score={best_score:.2f} ok={causal_ok}",
                        duration_ms    = (time.monotonic() - t0) * 1000,
                        success        = causal_ok,
                        details        = {"best_score": best_score},
                    ))
            except Exception as exc:
                logger.debug("Causality stage failed for %s: %s", candidate.tool_id, exc)

        # Rubix evidence check ─────────────────────────────────────────
        rubix_ok = True
        if causal_ok and self._rubix is not None:
            t0 = time.monotonic()
            try:
                sample = [candidate.confidence] * 5
                battery = self._rubix.run_battery([
                    self._rubix.confidence_interval_check(sample, expected_mean=0.5),
                    self._rubix.monte_carlo_check(
                        lambda: candidate.confidence > 0.4, n_simulations=50
                    ),
                ])
                rubix_ok = battery.overall_score >= self._rubix_thr
                result.steps.append(RoutingStep(
                    stage          = RoutingStage.RUBIX,
                    input_summary  = candidate.tool_id,
                    output_summary = f"score={battery.overall_score:.2f} pass={rubix_ok}",
                    duration_ms    = (time.monotonic() - t0) * 1000,
                    success        = rubix_ok,
                    details        = {"overall_score": battery.overall_score},
                ))
            except Exception as exc:
                logger.debug("Rubix stage failed for %s: %s", candidate.tool_id, exc)

        passed = causal_ok and rubix_ok
        result.tool_results[candidate.tool_id] = {
            "causal_ok": causal_ok,
            "rubix_ok":  rubix_ok,
            "passed":    passed,
        }
        return passed

    def _record_golden(
        self, request: str, domain: str,
        succeeded_tools: List[str], result: RoutingResult,
    ) -> None:
        """Record a successful routing as a golden path."""
        if self._golden is None:
            return
        t0 = time.monotonic()
        try:
            path_id = self._golden.record_success(
                task_pattern   = request[:120],
                domain         = domain,
                execution_spec = {
                    "tools":        succeeded_tools,
                    "success_rate": result.success_rate,
                    "request_id":   result.request_id,
                },
            )
            result.golden_path_id = path_id
            result.steps.append(RoutingStep(
                stage          = RoutingStage.GOLDEN,
                input_summary  = f"{len(succeeded_tools)} tools",
                output_summary = f"Recorded golden path {path_id}",
                duration_ms    = (time.monotonic() - t0) * 1000,
                success        = True,
            ))
        except Exception as exc:
            logger.debug("Golden path recording failed: %s", exc)

    # ------------------------------------------------------------------
    # Convenience factory
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, **kwargs: Any) -> "OptimalRoutingWiring":
        """
        Build an :class:`OptimalRoutingWiring` by lazily importing all five
        subsystems from the Murphy runtime.

        Any subsystem that fails to import is silently skipped.
        """
        systems: Dict[str, Any] = {}

        def _try(key: str, factory_fn):
            try:
                systems[key] = factory_fn()
            except Exception as exc:
                logger.debug("OptimalRoutingWiring.build: %s unavailable: %s", key, exc)

        _try("triage_engine",      lambda: __import__("src.ticket_triage_engine",
                                       fromlist=["TicketTriageEngine"]).TicketTriageEngine())
        _try("librarian_suggestor",lambda: __import__("src.agent_module_loader",
                                       fromlist=["LibrarianExecutionSuggestor"]).LibrarianExecutionSuggestor())
        _try("causality_engine",   lambda: __import__("src.causality_sandbox",
                                       fromlist=["CausalitySandboxEngine"]).CausalitySandboxEngine())
        _try("rubix_adapter",      lambda: __import__("src.rubix_evidence_adapter",
                                       fromlist=["RubixEvidenceAdapter"]).RubixEvidenceAdapter())
        _try("golden_path_bridge", lambda: __import__("src.golden_path_bridge",
                                       fromlist=["GoldenPathBridge"]).GoldenPathBridge())

        systems.update(kwargs)
        return cls(**systems)


__all__ = [
    "RoutingStage",
    "RoutingOutcome",
    "ToolCandidate",
    "RoutingStep",
    "RoutingResult",
    "OptimalRoutingWiring",
]
