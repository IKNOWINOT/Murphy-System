"""
Automation Commissioner
=======================

ML-inference commissioning layer for Murphy System automation workflows.

Given a ``WorkflowDefinition``, the commissioner:
  1. Infers *expected* output for every step using the onboard LLM.
  2. Executes the workflow through ``WorkflowDAGEngine``.
  3. Compares actual step outputs against predictions using semantic similarity.
  4. Produces a ``CommissioningReport`` with per-step confidence scores and an
     overall health score.

The commissioning loop continues until the health score meets the configured
threshold or the maximum iteration count is reached.  Each iteration refines
the expected values based on previous execution data — closing the gap between
predicted and actual behaviour ("dialling the traits").

Usage::

    from automation_commissioner import AutomationCommissioner
    from ai_workflow_generator import AIWorkflowGenerator

    gen = AIWorkflowGenerator()
    wf_dict = gen.generate_workflow("automate order fulfillment for shopify")
    wf_def = gen.to_workflow_definition(wf_dict)

    commissioner = AutomationCommissioner()
    report = commissioner.commission(wf_def, context={"store": "my_shopify_store"})

    print(report.health_score)      # e.g. 0.87
    print(report.ready_for_deploy)  # True when health_score >= threshold

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum health score before a workflow is considered commission-ready.
_DEFAULT_HEALTH_THRESHOLD = 0.75
# Maximum commissioning iterations (prevents infinite loop on stubborn gaps).
_MAX_ITERATIONS = 3


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StepCommissionResult:
    """Commissioning result for a single step."""
    step_id: str
    description: str
    action_type: str
    expected: str
    actual: str
    confidence: float          # 0.0–1.0 semantic similarity
    passed: bool
    iteration: int
    notes: str = ""


@dataclass
class CommissioningReport:
    """Full commissioning report for a workflow."""
    workflow_id: str
    workflow_name: str
    execution_id: str
    iteration: int
    health_score: float          # weighted average of step confidences
    ready_for_deploy: bool
    steps: List[StepCommissionResult] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "execution_id": self.execution_id,
            "iteration": self.iteration,
            "health_score": round(self.health_score, 4),
            "ready_for_deploy": self.ready_for_deploy,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "timestamp": self.timestamp,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "action_type": s.action_type,
                    "expected_summary": s.expected[:200],
                    "actual_summary": s.actual[:200],
                    "confidence": round(s.confidence, 4),
                    "passed": s.passed,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# Commissioner
# ---------------------------------------------------------------------------

class AutomationCommissioner:
    """Infer expected outputs, execute workflow, compare, and score.

    Args:
        health_threshold: Minimum health score (0–1) to mark ready_for_deploy.
        max_iterations:   How many commissioning rounds to attempt.
        llm_controller:   Optional LLMController; falls back to LocalLLMFallback.
    """

    def __init__(
        self,
        health_threshold: float = _DEFAULT_HEALTH_THRESHOLD,
        max_iterations: int = _MAX_ITERATIONS,
        llm_controller: Optional[Any] = None,
    ) -> None:
        self.health_threshold = health_threshold
        self.max_iterations = max_iterations
        self._llm_controller = llm_controller
        self._dag_engine: Optional[Any] = None   # WorkflowDAGEngine, lazy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def commission(
        self,
        workflow_def: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> CommissioningReport:
        """Run the full commissioning loop for *workflow_def*.

        Each iteration:
          1. Predict expected step outputs via LLM.
          2. Execute the workflow DAG.
          3. Compare actual vs expected; compute confidence scores.
          4. If health_score < threshold and iterations remain, refine and retry.

        Returns the best ``CommissioningReport`` found across all iterations.
        """
        t0 = time.time()
        ctx = dict(context or {})
        best_report: Optional[CommissioningReport] = None

        for iteration in range(1, self.max_iterations + 1):
            logger.info(
                "Commissioner: iteration %d/%d for workflow '%s'",
                iteration, self.max_iterations, workflow_def.workflow_id,
            )

            # Step 1: infer expected outputs
            expected = self._infer_expected_outputs(workflow_def, ctx)

            # Step 2: execute
            dag = self._get_dag_engine()
            dag.register_workflow(workflow_def)
            exec_id = dag.create_execution(workflow_def.workflow_id, ctx)
            if not exec_id:
                break
            execution_result = dag.execute_workflow(exec_id)

            # Step 3: score
            step_results = self._score_steps(
                workflow_def, expected, execution_result, iteration
            )
            health = self._compute_health(step_results)
            issues, recs = self._derive_issues_and_recs(step_results, health)

            from datetime import datetime, timezone
            report = CommissioningReport(
                workflow_id=workflow_def.workflow_id,
                workflow_name=workflow_def.name,
                execution_id=exec_id,
                iteration=iteration,
                health_score=health,
                ready_for_deploy=health >= self.health_threshold,
                steps=step_results,
                issues=issues,
                recommendations=recs,
                elapsed_seconds=time.time() - t0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            if best_report is None or report.health_score > best_report.health_score:
                best_report = report

            if report.ready_for_deploy:
                logger.info(
                    "Commissioner: workflow '%s' passed commissioning (health=%.2f) on iteration %d",
                    workflow_def.workflow_id, health, iteration,
                )
                break

            # Refine context for next iteration using issues found
            if iteration < self.max_iterations:
                ctx = self._refine_context(ctx, step_results)

        if best_report is None:
            from datetime import datetime, timezone
            best_report = CommissioningReport(
                workflow_id=workflow_def.workflow_id,
                workflow_name=getattr(workflow_def, "name", "unknown"),
                execution_id="",
                iteration=0,
                health_score=0.0,
                ready_for_deploy=False,
                issues=["Commissioning could not start — no valid workflow execution"],
                recommendations=["Verify workflow definition and retry"],
                elapsed_seconds=time.time() - t0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        best_report.elapsed_seconds = time.time() - t0
        return best_report

    def infer_expected_outputs(
        self,
        workflow_def: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Public wrapper — infer expected outputs without running execution."""
        return self._infer_expected_outputs(workflow_def, context or {})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_dag_engine(self) -> Any:
        if self._dag_engine is None:
            from workflow_dag_engine import WorkflowDAGEngine
            self._dag_engine = WorkflowDAGEngine(
                llm_controller=self._llm_controller
            )
        return self._dag_engine

    def _llm(self, prompt: str, max_tokens: int = 400) -> str:
        """Call LLM with fallback."""
        if self._llm_controller is not None:
            try:
                import asyncio

                from llm_controller import LLMRequest
                req = LLMRequest(prompt=prompt, max_tokens=max_tokens)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            resp = pool.submit(asyncio.run, self._llm_controller.query_llm(req)).result(timeout=30)
                    else:
                        resp = loop.run_until_complete(self._llm_controller.query_llm(req))
                    return resp.content
                except Exception as exc:
                    logger.debug("Commissioner LLM failed: %s", exc)
            except Exception:
                pass
        try:
            from local_llm_fallback import LocalLLMFallback
            return LocalLLMFallback().generate(prompt, max_tokens=max_tokens)
        except Exception:
            return "Expected output for automation step."

    def _infer_expected_outputs(
        self,
        workflow_def: Any,
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """Predict what each step *should* produce.

        Strategy (in priority order):
          1. Try LLM for a rich, context-specific prediction.
          2. If LLM returns a generic / empty response, fall back to constructing
             a deterministic expected string from the step metadata.  This ensures
             keyword-overlap scoring always has meaningful expected text to compare
             against — even in full-offline mode.
        """
        expected: Dict[str, str] = {}
        ctx_summary = str(context)[:200] if context else ""

        for step in workflow_def.steps:
            action = getattr(step, "action", "execute")
            meta = getattr(step, "metadata", {}) or {}
            full_desc = meta.get("description") or step.name

            # Attempt LLM enrichment
            prompt = (
                f"For a '{action}' automation step named '{step.step_id}':\n"
                f"Description: {full_desc}\n"
                f"Workflow context: {ctx_summary}\n\n"
                f"In 2-3 sentences, describe the EXPECTED successful output of this step. "
                f"Be specific about data values, status codes, counts, or messages "
                f"that would indicate the step succeeded."
            )
            llm_result = self._llm(prompt, max_tokens=200).strip()

            # Detect generic/unhelpful LLM responses
            _generic_indicators = [
                "i understand you're asking",
                "business automation with murphy",
                "murphy system lets you",
                "automate repetitive tasks",
                "common automation types",
                "i don't have specific",
            ]
            is_generic = any(ind in llm_result.lower() for ind in _generic_indicators)

            if llm_result and not is_generic:
                expected[step.step_id] = llm_result
            else:
                # Deterministic fallback from step metadata — always domain-specific
                action_phrase = {
                    "data_retrieval": f"Retrieved data successfully: {full_desc}. Source connected. Records retrieved and validated.",
                    "data_transformation": f"Data transformed: {full_desc}. Input normalised. Output schema applied. Records processed.",
                    "validation": f"Validation passed: {full_desc}. All checks passed. No issues found. Status: approved.",
                    "approval": f"Approved: {full_desc}. Approval criteria met. Confidence high. Conditions satisfied.",
                    "notification": f"Notification sent: {full_desc}. Recipient notified. Channel active. Confirmed delivered.",
                    "deployment": f"Deployed: {full_desc}. Environment updated. Health check passed. Version confirmed.",
                    "scheduling": f"Scheduled: {full_desc}. Job confirmed. Next run set. Interval active.",
                    "data_output": f"Data written: {full_desc}. Records stored. Destination confirmed. Confirmation received.",
                    "computation": f"Computed: {full_desc}. Formula applied. Result generated. Calculation complete.",
                    "error_handling": f"Error handling complete: {full_desc}. Errors caught. Resolved. No fallback needed.",
                    "execute": f"Executed: {full_desc}. Action completed. Result confirmed. Status success.",
                    "llm_execute": f"Executed: {full_desc}. Action completed. Result confirmed. Status success.",
                    "llm_generate": f"Generated: {full_desc}. Content created. Artifacts produced.",
                    "llm_analyze": f"Analysis complete: {full_desc}. Risks assessed. Recommendations ready.",
                    "llm_review": f"Review complete: {full_desc}. Approved. Confidence high. Feedback positive.",
                }.get(action, f"Step completed: {full_desc}. Status success. Output confirmed.")
                expected[step.step_id] = action_phrase

        return expected

    def _score_steps(
        self,
        workflow_def: Any,
        expected: Dict[str, str],
        execution_result: Dict[str, Any],
        iteration: int,
    ) -> List[StepCommissionResult]:
        """Score each step by comparing actual result to expected."""
        step_results = []
        step_map = {s.step_id: s for s in workflow_def.steps}
        steps_data = execution_result.get("steps", {})

        for step_id, step_def in step_map.items():
            exp_text = expected.get(step_id, "")
            step_data = steps_data.get(step_id, {})

            # Collect the actual output — handle both flat dicts and nested result dicts
            raw_result = step_data.get("result") or step_data.get("output") or {}
            if isinstance(raw_result, dict):
                # Flatten: join all string values from the dict
                parts = []
                for k, v in raw_result.items():
                    if isinstance(v, str):
                        parts.append(v)
                    elif isinstance(v, (bool, int, float)):
                        parts.append(f"{k}={v}")
                actual_text = " ".join(parts)
                # Also check for explicit success signals in the structured dict
                has_passed = raw_result.get("passed") is True
                has_sent = raw_result.get("sent") is True
                has_approved = raw_result.get("approved") is True
                has_status = raw_result.get("status") in ("completed", "sent", "approved", "scheduled", "resolved")
            else:
                actual_text = str(raw_result)[:500]
                has_passed = has_sent = has_approved = has_status = False

            # Add step-level status from the wrapper
            step_status = step_data.get("status", "")
            if step_status in ("completed", "sent", "approved", "scheduled"):
                has_status = True

            actual_text = actual_text[:500]

            # Semantic confidence
            confidence, notes = self._compute_confidence(
                exp_text, actual_text, step_def,
                bonus_signals={
                    "has_passed": has_passed,
                    "has_sent": has_sent,
                    "has_approved": has_approved,
                    "has_status": has_status,
                }
            )

            meta = getattr(step_def, "metadata", {}) or {}
            step_results.append(StepCommissionResult(
                step_id=step_id,
                description=meta.get("description") or step_def.name,
                action_type=getattr(step_def, "action", "execute"),
                expected=exp_text,
                actual=actual_text,
                confidence=confidence,
                passed=confidence >= 0.5,
                iteration=iteration,
                notes=notes,
            ))

        return step_results

    def _compute_confidence(
        self,
        expected: str,
        actual: str,
        step_def: Any,
        bonus_signals: Optional[Dict[str, bool]] = None,
    ) -> tuple:
        """Compute confidence score 0–1 for a step result.

        Combines four signals with the following weights:

        1. **Keyword overlap** (40%) — fraction of expected-text keywords that
           appear in actual output text.  Rewards domain-specific content.
        2. **Success indicator patterns** (30%) — count of regex patterns for
           words like 'completed', 'approved', 'sent', 'validated' found in the
           actual text.  Normalised to [0, 1] over 3 hits.
        3. **Output length** (15%) — longer outputs indicate more content was
           produced.  Normalised to [0, 1] over 150 characters.
        4. **Structured result bonus** (0–15%) — explicit boolean success flags
           in the result dict: ``has_status`` (+0.15), ``has_passed`` (+0.12),
           ``has_approved`` (+0.12), ``has_sent`` (+0.10).

        Final score is clamped to [0.0, 1.0].
        """
        if not actual or actual.strip() in ("", "None", "null"):
            return 0.1, "Step produced no output"

        bonus = bonus_signals or {}

        # Signal 1: keyword overlap
        exp_words = set(re.findall(r'\b[a-z]{3,}\b', expected.lower()))
        act_words = set(re.findall(r'\b[a-z]{3,}\b', actual.lower()))
        if exp_words:
            overlap = len(exp_words & act_words) / len(exp_words)
        else:
            overlap = 0.5  # no expected words → neutral

        # Signal 2: success indicators in actual output
        success_patterns = [
            r'\bsuccess\b', r'\bcompleted?\b', r'\bapproved?\b',
            r'\bsent\b', r'\bvalidated?\b', r'\bprocessed\b',
            r'\brecorded?\b', r'\bdeployed?\b', r'\bscheduled?\b',
            r'\bconfirm', r'\bverif', r'\b(true|yes|ok)\b',
        ]
        success_hits = sum(
            1 for p in success_patterns if re.search(p, actual.lower())
        )
        success_score = min(1.0, success_hits / 3.0)

        # Signal 3: output length
        length_score = min(1.0, len(actual) / 150.0)

        # Signal 4: structured success flags (each adds 0.12 to raw score)
        structured_bonus = sum([
            0.15 if bonus.get("has_status") else 0.0,
            0.12 if bonus.get("has_passed") else 0.0,
            0.12 if bonus.get("has_approved") else 0.0,
            0.10 if bonus.get("has_sent") else 0.0,
        ])

        # Weighted combination
        raw = overlap * 0.40 + success_score * 0.30 + length_score * 0.15 + structured_bonus
        confidence = max(0.0, min(1.0, raw))

        action = getattr(step_def, "action", "execute")
        notes = (
            f"Keyword overlap={overlap:.2f}, "
            f"success_signals={success_hits}/12, "
            f"structured_bonus={structured_bonus:.2f}, "
            f"action={action}"
        )
        return confidence, notes

    def _compute_health(self, step_results: List[StepCommissionResult]) -> float:
        """Compute overall health score as weighted average of step confidences."""
        if not step_results:
            return 0.0

        # Weight by action type priority (critical steps count more)
        weights = {
            "validation": 1.5,
            "approval": 1.5,
            "data_retrieval": 1.2,
            "notification": 1.2,
            "deployment": 1.3,
            "data_output": 1.1,
        }
        total_weight = 0.0
        weighted_sum = 0.0
        for sr in step_results:
            w = weights.get(sr.action_type, 1.0)
            weighted_sum += sr.confidence * w
            total_weight += w

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _derive_issues_and_recs(
        self,
        step_results: List[StepCommissionResult],
        health: float,
    ) -> tuple:
        """Derive human-readable issues and recommendations from step results."""
        issues = []
        recs = []

        failed = [s for s in step_results if not s.passed]
        low_conf = [s for s in step_results if 0.5 <= s.confidence < 0.7]

        for s in failed:
            issues.append(
                f"Step '{s.step_id}' ({s.action_type}) failed: "
                f"confidence={s.confidence:.2f}. {s.notes}"
            )
            recs.append(
                f"Review step '{s.step_id}': ensure {s.action_type} handler "
                f"is connected to the right data source."
            )

        for s in low_conf:
            issues.append(
                f"Step '{s.step_id}' low confidence ({s.confidence:.2f}). "
                f"Output may not match design intent."
            )
            recs.append(
                f"Dial step '{s.step_id}': add more specific context "
                f"(e.g. connector credentials, data schema)."
            )

        if health < self.health_threshold:
            recs.append(
                f"Overall health {health:.2f} is below threshold "
                f"{self.health_threshold:.2f}. "
                "Add execution context (credentials, schema, sample data) "
                "to improve step fidelity."
            )
        else:
            recs.append(
                f"Workflow commissioned at {health:.2f} health. "
                "Register with AutomationEngine to activate live triggers."
            )

        return issues, recs

    def _refine_context(
        self,
        context: Dict[str, Any],
        step_results: List[StepCommissionResult],
    ) -> Dict[str, Any]:
        """Enrich context with failed step info for the next iteration."""
        ctx = dict(context)
        failed_steps = [s.step_id for s in step_results if not s.passed]
        if failed_steps:
            ctx["retry_failed_steps"] = failed_steps
            ctx["commissioning_iteration_hint"] = (
                f"Previous iteration failed on: {', '.join(failed_steps)}. "
                "Provide more detailed output for these steps."
            )
        return ctx
