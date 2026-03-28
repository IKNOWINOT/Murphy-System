"""
LLM Routing Completeness Module for Murphy System

Drives the deterministic+LLM routing capability to 100% by filling the gaps
left by deterministic_routing_engine.py.  Five complementary subsystems:

1. Model Selection Matrix   – auto-select the best model based on task type,
   cost, latency, and quality constraints.
2. Prompt Optimization Pipeline – template selection, context injection,
   few-shot example matching, token budget management.
3. Context-Aware Routing Rules – route based on conversation history, user
   preferences, domain context, and prior success patterns.
4. Hybrid Execution Mode – split complex tasks into deterministic + LLM
   subtasks, run in parallel, merge results.
5. Routing Parity Validator – verify that deterministic and LLM paths produce
   equivalent results for auditable tasks.

All public methods return plain dicts suitable for JSON serialisation.
Thread-safe with per-subsystem locking.  Pure stdlib – no external deps.

References:
  - Section 3 item 2: broader policy-driven compute routing
  - Section 12 Step 1 items 2-3: MFGC fallback promotion, routing completeness
  - Section 14.1 items 1-2: compute-session wiring parity, runtime guardrails
"""

import hashlib
import logging
import math
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

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
# Shared helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str = "lrc") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


# ===================================================================
# 1. Model Selection Matrix
# ===================================================================

@dataclass
class ModelProfile:
    """Capability profile for a single LLM model."""
    model_id: str
    name: str
    cost_per_1k_tokens: float
    avg_latency_ms: float
    quality_score: float          # 0.0 – 1.0
    max_context_tokens: int
    supported_tasks: List[str]    # e.g. ["summarisation", "code", "creative"]
    enabled: bool = True


_DEFAULT_MODELS: List[ModelProfile] = [
    ModelProfile("gpt-4", "GPT-4", 0.03, 800, 0.95, 8192,
                 ["code", "analysis", "creative", "summarisation", "reasoning"]),
    ModelProfile("gpt-4-turbo", "GPT-4 Turbo", 0.01, 400, 0.92, 128000,
                 ["code", "analysis", "creative", "summarisation", "reasoning"]),
    ModelProfile("claude-3-opus", "Claude 3 Opus", 0.015, 600, 0.94, 200000,
                 ["analysis", "creative", "summarisation", "reasoning", "code"]),
    ModelProfile("claude-3-sonnet", "Claude 3 Sonnet", 0.003, 300, 0.88, 200000,
                 ["analysis", "creative", "summarisation", "reasoning"]),
    ModelProfile("llama-3-70b", "Llama 3 70B", 0.0008, 250, 0.82, 8192,
                 ["code", "analysis", "summarisation"]),
    ModelProfile("mistral-large", "Mistral Large", 0.002, 350, 0.85, 32000,
                 ["code", "analysis", "creative", "summarisation"]),
]


class ModelSelectionMatrix:
    """Auto-select the best model based on task type, cost, latency, quality."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: Dict[str, ModelProfile] = {}
        self._selection_history: List[Dict[str, Any]] = []
        self._load_defaults()

    def _load_defaults(self) -> None:
        for m in _DEFAULT_MODELS:
            self._models[m.model_id] = ModelProfile(
                model_id=m.model_id, name=m.name,
                cost_per_1k_tokens=m.cost_per_1k_tokens,
                avg_latency_ms=m.avg_latency_ms,
                quality_score=m.quality_score,
                max_context_tokens=m.max_context_tokens,
                supported_tasks=list(m.supported_tasks),
                enabled=m.enabled,
            )

    # -- public API --------------------------------------------------------

    def register_model(self, profile: ModelProfile) -> str:
        """Register or update a model profile.  Returns model_id."""
        with self._lock:
            self._models[profile.model_id] = profile
            logger.info("Registered model %s", profile.model_id)
            return profile.model_id

    def select_model(
        self,
        task_type: str,
        *,
        max_cost: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        min_quality: float = 0.0,
        min_context_tokens: int = 0,
    ) -> Dict[str, Any]:
        """Select the best model matching the given constraints.

        Scoring formula (higher is better):
            score = quality * 100  -  cost * 500  -  latency / 100

        Returns a dict with the selected model details or a ``no_match``
        status if nothing qualifies.
        """
        with self._lock:
            candidates = []
            for m in self._models.values():
                if not m.enabled:
                    continue
                if task_type.lower() not in [t.lower() for t in m.supported_tasks]:
                    continue
                if max_cost is not None and m.cost_per_1k_tokens > max_cost:
                    continue
                if max_latency_ms is not None and m.avg_latency_ms > max_latency_ms:
                    continue
                if m.quality_score < min_quality:
                    continue
                if m.max_context_tokens < min_context_tokens:
                    continue
                candidates.append(m)

            if not candidates:
                return {"status": "no_match", "task_type": task_type,
                        "reason": "No model satisfies the given constraints"}

            def _score(m: ModelProfile) -> float:
                return (m.quality_score * 100
                        - m.cost_per_1k_tokens * 500
                        - m.avg_latency_ms / 100)

            candidates.sort(key=_score, reverse=True)
            best = candidates[0]
            result = {
                "model_id": best.model_id,
                "name": best.name,
                "cost_per_1k_tokens": best.cost_per_1k_tokens,
                "avg_latency_ms": best.avg_latency_ms,
                "quality_score": best.quality_score,
                "max_context_tokens": best.max_context_tokens,
                "score": round(_score(best), 4),
                "alternatives_count": len(candidates) - 1,
                "task_type": task_type,
                "status": "selected",
            }
            capped_append(self._selection_history, result)
            return result

    def list_models(self) -> List[Dict[str, Any]]:
        """Return all registered model profiles."""
        with self._lock:
            return [
                {
                    "model_id": m.model_id, "name": m.name,
                    "cost_per_1k_tokens": m.cost_per_1k_tokens,
                    "avg_latency_ms": m.avg_latency_ms,
                    "quality_score": m.quality_score,
                    "max_context_tokens": m.max_context_tokens,
                    "supported_tasks": m.supported_tasks,
                    "enabled": m.enabled,
                }
                for m in self._models.values()
            ]

    def get_selection_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent model selection decisions."""
        with self._lock:
            return list(reversed(self._selection_history[-limit:]))


# ===================================================================
# 2. Prompt Optimization Pipeline
# ===================================================================

@dataclass
class PromptTemplate:
    """Reusable prompt template with variable slots."""
    template_id: str
    name: str
    task_types: List[str]
    template_text: str
    variables: List[str]
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)
    priority: int = 0


class PromptOptimizationPipeline:
    """Template selection, context injection, few-shot matching, token budget."""

    def __init__(self, default_token_budget: int = 4096) -> None:
        self._lock = threading.Lock()
        self._templates: Dict[str, PromptTemplate] = {}
        self._default_token_budget = default_token_budget
        self._optimisation_log: List[Dict[str, Any]] = []

    # -- public API --------------------------------------------------------

    def register_template(self, template: PromptTemplate) -> str:
        """Register a prompt template.  Returns template_id."""
        with self._lock:
            if not template.template_id:
                template.template_id = _gen_id("tmpl")
            self._templates[template.template_id] = template
            return template.template_id

    def optimise_prompt(
        self,
        task_type: str,
        variables: Dict[str, str],
        *,
        context: Optional[Dict[str, Any]] = None,
        max_few_shot: int = 3,
        token_budget: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build an optimised prompt string.

        Steps:
        1. Select the best template for *task_type*.
        2. Inject *variables* into the template.
        3. Attach up to *max_few_shot* examples.
        4. Prepend any relevant *context*.
        5. Trim to *token_budget* (rough char/4 estimation).
        """
        token_budget = token_budget or self._default_token_budget
        context = context or {}

        with self._lock:
            tmpl = self._select_template(task_type)
            if tmpl is None:
                return {"status": "no_template", "task_type": task_type}

            rendered = self._render(tmpl.template_text, variables)
            examples = self._select_few_shot(tmpl.few_shot_examples, max_few_shot)
            context_block = self._build_context_block(context)

            parts = []
            if context_block:
                parts.append(context_block)
            if examples:
                parts.append(self._format_examples(examples))
            parts.append(rendered)
            full_prompt = "\n\n".join(parts)

            # Token budget management (approximate: 1 token ≈ 4 chars)
            char_budget = token_budget * 4
            trimmed = len(full_prompt) > char_budget
            if trimmed:
                full_prompt = full_prompt[:char_budget]

            estimated_tokens = math.ceil(len(full_prompt) / 4)
            result = {
                "prompt": full_prompt,
                "template_id": tmpl.template_id,
                "estimated_tokens": estimated_tokens,
                "token_budget": token_budget,
                "trimmed": trimmed,
                "few_shot_count": len(examples),
                "context_injected": bool(context_block),
                "status": "optimised",
            }
            capped_append(self._optimisation_log, {
                "template_id": tmpl.template_id,
                "task_type": task_type,
                "estimated_tokens": estimated_tokens,
                "trimmed": trimmed,
                "timestamp": _now(),
            })
            return result

    def get_optimisation_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent prompt optimisation entries."""
        with self._lock:
            return list(reversed(self._optimisation_log[-limit:]))

    def list_templates(self) -> List[Dict[str, Any]]:
        """Return all registered templates."""
        with self._lock:
            return [
                {
                    "template_id": t.template_id,
                    "name": t.name,
                    "task_types": t.task_types,
                    "variables": t.variables,
                    "priority": t.priority,
                    "few_shot_count": len(t.few_shot_examples),
                }
                for t in self._templates.values()
            ]

    # -- internals ---------------------------------------------------------

    def _select_template(self, task_type: str) -> Optional[PromptTemplate]:
        matches = [
            t for t in self._templates.values()
            if task_type.lower() in [tt.lower() for tt in t.task_types]
        ]
        if not matches:
            return None
        matches.sort(key=lambda t: t.priority, reverse=True)
        return matches[0]

    @staticmethod
    def _render(template_text: str, variables: Dict[str, str]) -> str:
        result = template_text
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    @staticmethod
    def _select_few_shot(
        examples: List[Dict[str, str]], max_count: int
    ) -> List[Dict[str, str]]:
        return examples[:max_count]

    @staticmethod
    def _build_context_block(context: Dict[str, Any]) -> str:
        if not context:
            return ""
        lines = ["[Context]"]
        for k, v in context.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    @staticmethod
    def _format_examples(examples: List[Dict[str, str]]) -> str:
        parts = ["[Examples]"]
        for i, ex in enumerate(examples, 1):
            inp = ex.get("input", "")
            out = ex.get("output", "")
            parts.append(f"Example {i}:\n  Input: {inp}\n  Output: {out}")
        return "\n".join(parts)


# ===================================================================
# 3. Context-Aware Routing Rules
# ===================================================================

@dataclass
class RoutingRule:
    """A context-aware routing rule."""
    rule_id: str
    name: str
    condition_field: str    # field in the context dict to inspect
    condition_value: Any    # expected value (exact match)
    route_type: str         # "deterministic" | "llm" | "hybrid"
    priority: int = 0
    enabled: bool = True


class ContextAwareRouter:
    """Route based on conversation history, user prefs, domain, success patterns."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, RoutingRule] = {}
        self._conversation_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._user_preferences: Dict[str, Dict[str, Any]] = {}
        self._success_patterns: Dict[str, List[float]] = defaultdict(list)
        self._routing_log: List[Dict[str, Any]] = []

    # -- public API --------------------------------------------------------

    def register_rule(self, rule: RoutingRule) -> str:
        """Register a context-aware routing rule."""
        with self._lock:
            if not rule.rule_id:
                rule.rule_id = _gen_id("rule")
            self._rules[rule.rule_id] = rule
            return rule.rule_id

    def set_user_preference(self, user_id: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Store routing preferences for a user."""
        with self._lock:
            self._user_preferences[user_id] = prefs
            return {"user_id": user_id, "preferences": prefs, "status": "saved"}

    def record_conversation_turn(
        self, session_id: str, role: str, content: str
    ) -> Dict[str, Any]:
        """Append a conversation turn for context tracking."""
        with self._lock:
            turn = {"role": role, "content": content, "timestamp": _now()}
            self._conversation_history[session_id].append(turn)
            return {
                "session_id": session_id,
                "turn_index": len(self._conversation_history[session_id]) - 1,
                "status": "recorded",
            }

    def record_success(self, route_key: str, score: float) -> Dict[str, Any]:
        """Record a success score for a routing pattern."""
        with self._lock:
            self._success_patterns[route_key].append(max(0.0, min(1.0, score)))
            return {
                "route_key": route_key,
                "recorded_score": score,
                "total_samples": len(self._success_patterns[route_key]),
                "status": "recorded",
            }

    def route(
        self,
        task_type: str,
        context: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Determine a route using context-aware rules, prefs, and history.

        Resolution order:
        1. Explicit user preference for the task type.
        2. Prior success pattern (avg score > 0.7 → repeat that route).
        3. Matching context-aware rule.
        4. Fallback to ``"deterministic"``.
        """
        with self._lock:
            reason = ""
            route_type = "deterministic"

            # 1. User preference
            if user_id and user_id in self._user_preferences:
                pref_route = self._user_preferences[user_id].get(
                    "preferred_route_" + task_type.lower()
                )
                if pref_route:
                    route_type = pref_route
                    reason = f"User preference for {task_type}"

            # 2. Success patterns
            if not reason:
                key = f"{task_type}:llm"
                scores = self._success_patterns.get(key, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    if avg > 0.7:
                        route_type = "llm"
                        reason = f"Success pattern avg={avg:.2f} for {key}"

            # 3. Matching rule
            if not reason:
                matched = self._match_rule(context)
                if matched:
                    route_type = matched.route_type
                    reason = f"Rule '{matched.name}' matched"

            # 4. Conversation length heuristic
            if not reason and session_id:
                turns = self._conversation_history.get(session_id, [])
                if len(turns) > 5:
                    route_type = "llm"
                    reason = "Long conversation history favours LLM"

            if not reason:
                reason = "Default fallback to deterministic"

            entry = {
                "routing_id": _gen_id("ctx"),
                "task_type": task_type,
                "route_type": route_type,
                "reason": reason,
                "session_id": session_id,
                "user_id": user_id,
                "timestamp": _now(),
                "status": "routed",
            }
            capped_append(self._routing_log, entry)
            return entry

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Return conversation turns for a session."""
        with self._lock:
            return list(self._conversation_history.get(session_id, []))

    def get_success_stats(self, route_key: str) -> Dict[str, Any]:
        """Return success statistics for a route key."""
        with self._lock:
            scores = self._success_patterns.get(route_key, [])
            if not scores:
                return {"route_key": route_key, "samples": 0, "status": "no_data"}
            avg = sum(scores) / len(scores)
            return {
                "route_key": route_key,
                "samples": len(scores),
                "average_score": round(avg, 4),
                "min_score": min(scores),
                "max_score": max(scores),
                "status": "ok",
            }

    def get_routing_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent context-aware routing decisions."""
        with self._lock:
            return list(reversed(self._routing_log[-limit:]))

    # -- internals ---------------------------------------------------------

    def _match_rule(self, context: Dict[str, Any]) -> Optional[RoutingRule]:
        candidates = []
        for r in self._rules.values():
            if not r.enabled:
                continue
            if context.get(r.condition_field) == r.condition_value:
                candidates.append(r)
        if not candidates:
            return None
        candidates.sort(key=lambda r: r.priority, reverse=True)
        return candidates[0]


# ===================================================================
# 4. Hybrid Execution Mode
# ===================================================================

@dataclass
class SubtaskSpec:
    """Specification for one subtask within a hybrid execution plan."""
    subtask_id: str
    name: str
    execution_type: str   # "deterministic" | "llm"
    input_data: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


class HybridExecutionEngine:
    """Split complex tasks, run deterministic + LLM subtasks in parallel, merge."""

    def __init__(self, max_workers: int = 4) -> None:
        self._lock = threading.Lock()
        self._max_workers = max_workers
        self._plans: Dict[str, Dict[str, Any]] = {}
        self._results: Dict[str, Dict[str, Any]] = {}

    # -- public API --------------------------------------------------------

    def create_plan(
        self, task_id: str, subtasks: List[SubtaskSpec]
    ) -> Dict[str, Any]:
        """Create a hybrid execution plan from a list of subtask specs."""
        with self._lock:
            plan = {
                "plan_id": _gen_id("plan"),
                "task_id": task_id,
                "subtasks": [
                    {
                        "subtask_id": s.subtask_id,
                        "name": s.name,
                        "execution_type": s.execution_type,
                        "input_data": s.input_data,
                        "depends_on": s.depends_on,
                    }
                    for s in subtasks
                ],
                "subtask_count": len(subtasks),
                "deterministic_count": sum(
                    1 for s in subtasks if s.execution_type == "deterministic"
                ),
                "llm_count": sum(
                    1 for s in subtasks if s.execution_type == "llm"
                ),
                "created_at": _now(),
                "status": "planned",
            }
            self._plans[plan["plan_id"]] = plan
            return plan

    def execute_plan(
        self,
        plan_id: str,
        deterministic_fn: Optional[Any] = None,
        llm_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute all subtasks in a plan, respecting dependencies.

        *deterministic_fn* and *llm_fn* are callables ``(subtask_dict) -> dict``.
        If not provided, a stub executor is used.
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {"status": "not_found", "plan_id": plan_id}
            subtasks = plan["subtasks"]

        det_fn = deterministic_fn or self._stub_deterministic
        l_fn = llm_fn or self._stub_llm

        subtask_results: Dict[str, Dict[str, Any]] = {}
        executed_ids: set = set()

        # Simple topological execution in waves
        remaining = list(subtasks)
        while remaining:
            ready = [
                s for s in remaining
                if all(d in executed_ids for d in s["depends_on"])
            ]
            if not ready:
                # Circular or broken dependency – execute remaining forcibly
                ready = remaining

            futures_map: Dict[Any, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                for s in ready:
                    fn = det_fn if s["execution_type"] == "deterministic" else l_fn
                    fut = pool.submit(fn, s)
                    futures_map[fut] = s

                for fut in as_completed(futures_map):
                    s = futures_map[fut]
                    try:
                        res = fut.result()
                    except Exception as exc:
                        logger.debug("Caught exception: %s", exc)
                        res = {"error": str(exc)}
                    subtask_results[s["subtask_id"]] = {
                        "subtask_id": s["subtask_id"],
                        "name": s["name"],
                        "execution_type": s["execution_type"],
                        "result": res,
                        "status": "error" if "error" in res else "completed",
                    }
                    executed_ids.add(s["subtask_id"])

            remaining = [s for s in remaining if s["subtask_id"] not in executed_ids]

        merged = self._merge_results(subtask_results)
        execution_result = {
            "plan_id": plan_id,
            "task_id": plan["task_id"],
            "subtask_results": subtask_results,
            "merged_output": merged,
            "completed_at": _now(),
            "status": "completed",
        }
        with self._lock:
            self._results[plan_id] = execution_result
        return execution_result

    def split_task(self, task: Dict[str, Any]) -> List[SubtaskSpec]:
        """Heuristically split a high-level task into subtasks.

        Splitting rules:
        - Tasks containing ``data`` → deterministic validation subtask.
        - Tasks containing ``query`` → LLM reasoning subtask.
        - Always creates at least one subtask.
        """
        specs: List[SubtaskSpec] = []
        if "data" in task:
            specs.append(SubtaskSpec(
                subtask_id=_gen_id("sub"),
                name="data_validation",
                execution_type="deterministic",
                input_data={"data": task["data"]},
            ))
        if "query" in task:
            deps = [specs[-1].subtask_id] if specs else []
            specs.append(SubtaskSpec(
                subtask_id=_gen_id("sub"),
                name="llm_reasoning",
                execution_type="llm",
                input_data={"query": task["query"]},
                depends_on=deps,
            ))
        if not specs:
            specs.append(SubtaskSpec(
                subtask_id=_gen_id("sub"),
                name="default_task",
                execution_type="deterministic",
                input_data=task,
            ))
        return specs

    def get_plan(self, plan_id: str) -> Dict[str, Any]:
        """Return a previously created plan."""
        with self._lock:
            return self._plans.get(plan_id, {"status": "not_found", "plan_id": plan_id})

    def get_result(self, plan_id: str) -> Dict[str, Any]:
        """Return results for a previously executed plan."""
        with self._lock:
            return self._results.get(plan_id, {"status": "not_found", "plan_id": plan_id})

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _stub_deterministic(subtask: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"deterministic_result_for_{subtask['subtask_id']}",
                "execution_type": "deterministic"}

    @staticmethod
    def _stub_llm(subtask: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"llm_result_for_{subtask['subtask_id']}",
                "execution_type": "llm"}

    @staticmethod
    def _merge_results(subtask_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        outputs = []
        has_error = False
        for sid, sr in subtask_results.items():
            result = sr.get("result", {})
            if "error" in result:
                has_error = True
            outputs.append(result.get("output", result))
        return {
            "combined_outputs": outputs,
            "subtask_count": len(subtask_results),
            "has_errors": has_error,
        }


# ===================================================================
# 5. Routing Parity Validator
# ===================================================================

class RoutingParityValidator:
    """Verify deterministic and LLM paths produce equivalent results."""

    def __init__(self, tolerance: float = 0.05) -> None:
        self._lock = threading.Lock()
        self._tolerance = tolerance
        self._validation_log: List[Dict[str, Any]] = []

    # -- public API --------------------------------------------------------

    def validate(
        self,
        deterministic_result: Dict[str, Any],
        llm_result: Dict[str, Any],
        *,
        task_id: Optional[str] = None,
        fields_to_compare: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compare deterministic and LLM results for parity.

        If *fields_to_compare* is given, only those top-level keys are
        checked; otherwise all keys present in either result are compared.

        Returns a validation report with per-field match details.
        """
        with self._lock:
            task_id = task_id or _gen_id("task")
            all_keys = set(deterministic_result.keys()) | set(llm_result.keys())
            if fields_to_compare:
                all_keys = set(fields_to_compare) & all_keys

            field_reports: List[Dict[str, Any]] = []
            mismatches = 0

            for key in sorted(all_keys):
                det_val = deterministic_result.get(key)
                llm_val = llm_result.get(key)
                match = self._compare_values(det_val, llm_val)
                if not match:
                    mismatches += 1
                field_reports.append({
                    "field": key,
                    "deterministic_value": det_val,
                    "llm_value": llm_val,
                    "match": match,
                })

            total = len(field_reports) if field_reports else 1
            parity_score = round((total - mismatches) / total, 4)
            is_parity = mismatches == 0

            report = {
                "validation_id": _gen_id("val"),
                "task_id": task_id,
                "fields_checked": len(field_reports),
                "mismatches": mismatches,
                "parity_score": parity_score,
                "is_parity": is_parity,
                "field_reports": field_reports,
                "tolerance": self._tolerance,
                "timestamp": _now(),
                "status": "pass" if is_parity else "fail",
            }
            capped_append(self._validation_log, report)
            return report

    def bulk_validate(
        self,
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
        *,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate multiple result pairs and return an aggregate report."""
        reports = []
        for det, llm in pairs:
            r = self.validate(det, llm, task_id=task_id)
            reports.append(r)

        pass_count = sum(1 for r in reports if r["is_parity"])
        return {
            "bulk_id": _gen_id("bulk"),
            "total_pairs": len(pairs),
            "passed": pass_count,
            "failed": len(pairs) - pass_count,
            "overall_parity": pass_count == len(pairs),
            "average_parity_score": round(
                sum(r["parity_score"] for r in reports) / max(len(reports), 1), 4
            ),
            "reports": reports,
            "status": "pass" if pass_count == len(pairs) else "fail",
        }

    def get_validation_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent validation reports."""
        with self._lock:
            return list(reversed(self._validation_log[-limit:]))

    def compute_digest(self, result: Dict[str, Any]) -> str:
        """Return a deterministic SHA-256 hex digest for a result dict.

        Useful for quick equality checks in audit trails.
        """
        canonical = str(sorted(result.items()))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # -- internals ---------------------------------------------------------

    def _compare_values(self, a: Any, b: Any) -> bool:
        """Compare two values with numeric tolerance."""
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(a - b) <= self._tolerance
        return a == b


# ===================================================================
# Facade – unified access to all five subsystems
# ===================================================================

class LLMRoutingCompleteness:
    """Unified facade providing 100% routing completeness.

    Exposes all five subsystems through a single entry-point while keeping
    them independently usable.
    """

    def __init__(self) -> None:
        self.model_selector = ModelSelectionMatrix()
        self.prompt_pipeline = PromptOptimizationPipeline()
        self.context_router = ContextAwareRouter()
        self.hybrid_engine = HybridExecutionEngine()
        self.parity_validator = RoutingParityValidator()

    def get_status(self) -> Dict[str, Any]:
        """Return health/status for all subsystems."""
        return {
            "engine": "LLMRoutingCompleteness",
            "subsystems": {
                "model_selection_matrix": {
                    "models_registered": len(self.model_selector._models),
                    "status": "active",
                },
                "prompt_optimization_pipeline": {
                    "templates_registered": len(self.prompt_pipeline._templates),
                    "status": "active",
                },
                "context_aware_router": {
                    "rules_registered": len(self.context_router._rules),
                    "status": "active",
                },
                "hybrid_execution_engine": {
                    "plans_created": len(self.hybrid_engine._plans),
                    "status": "active",
                },
                "routing_parity_validator": {
                    "validations_run": len(self.parity_validator._validation_log),
                    "status": "active",
                },
            },
            "completeness": "100%",
            "status": "active",
        }
