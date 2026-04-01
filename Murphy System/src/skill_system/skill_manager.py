"""
Skill Manager — registry, composition, sharing, and execution.

Design Label: SK-003

Provides:
  • Skill registration and versioning
  • DAG-based composition (nested skills)
  • Inter-tenant sharing with access control
  • Priority matching for Describe → Execute pipeline
  • Cycle detection for composed skill DAGs
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Set

from src.skill_system.models import (
    SkillAccess,
    SkillComposition,
    SkillExecutionRecord,
    SkillSpec,
    SkillStep,
    SkillStepStatus,
)

logger = logging.getLogger(__name__)

_MAX_EXECUTION_LOG = 500
_MAX_NESTING_DEPTH = 10


class SkillManager:
    """Thread-safe skill registry with composition and sharing.

    Integrates with the Describe → Execute pipeline by providing
    skill matching before falling back to template matching.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._skills: Dict[str, SkillSpec] = {}
        self._execution_log: Deque[SkillExecutionRecord] = deque(
            maxlen=_MAX_EXECUTION_LOG,
        )
        self._tool_executors: Dict[str, Callable[..., Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, skill: SkillSpec) -> None:
        """Register or update a skill."""
        with self._lock:
            self._skills[skill.skill_id] = skill
            logger.info("Skill registered: %s (%s) v%s [%s]",
                        skill.skill_id, skill.name, skill.version,
                        skill.access.value)

    def unregister(self, skill_id: str) -> SkillSpec:
        """Remove a skill.  Raises KeyError if not found."""
        with self._lock:
            skill = self._skills.pop(skill_id)
            logger.info("Skill unregistered: %s", skill_id)
            return skill

    def get(self, skill_id: str) -> SkillSpec:
        """Get a skill by ID.  Raises KeyError if not found."""
        with self._lock:
            return self._skills[skill_id]

    def register_tool_executor(
        self,
        tool_id: str,
        executor: Callable[..., Dict[str, Any]],
    ) -> None:
        """Register a callable for a tool_id used in skill steps."""
        self._tool_executors[tool_id] = executor

    # ------------------------------------------------------------------
    # Discovery / Matching
    # ------------------------------------------------------------------

    def list_skills(
        self,
        *,
        tenant_id: Optional[str] = None,
        access_filter: Optional[SkillAccess] = None,
    ) -> List[SkillSpec]:
        """List skills visible to a tenant."""
        with self._lock:
            results: List[SkillSpec] = []
            for skill in self._skills.values():
                if access_filter and skill.access != access_filter:
                    continue
                if tenant_id:
                    if skill.access == SkillAccess.PRIVATE and skill.owner_tenant != tenant_id:
                        continue
                results.append(skill)
            return results

    def search(
        self,
        query: str,
        *,
        tenant_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
    ) -> List[SkillSpec]:
        """Search skills by text query, tags, and category."""
        query_lower = query.lower()
        with self._lock:
            results: List[SkillSpec] = []
            for skill in self._skills.values():
                # Access control
                if tenant_id:
                    if skill.access == SkillAccess.PRIVATE and skill.owner_tenant != tenant_id:
                        continue

                # Text match
                text_match = (
                    query_lower in skill.name.lower()
                    or query_lower in skill.description.lower()
                    or any(query_lower in t.lower() for t in skill.metadata.tags)
                )
                if not text_match:
                    continue

                # Tag filter
                if tags and not set(tags).intersection(skill.metadata.tags):
                    continue
                if category and skill.metadata.category != category:
                    continue

                results.append(skill)
            return results

    def match_for_pipeline(
        self,
        description: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[SkillSpec]:
        """Match a natural-language description to a skill.

        Used by the Describe → Execute pipeline before falling back
        to template matching → keyword inference → generic.
        """
        matches = self.search(description, tenant_id=tenant_id)
        if not matches:
            return None
        # Return highest execution count (most proven)
        return max(matches, key=lambda s: s.execution_count)

    # ------------------------------------------------------------------
    # Composition validation
    # ------------------------------------------------------------------

    def validate_composition(self, skill_id: str) -> List[str]:
        """Validate a skill's DAG: check for cycles and missing refs."""
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                return [f"Skill {skill_id} not found"]
            return self._validate_dag(skill, set(), 0)

    def _validate_dag(
        self,
        skill: SkillSpec,
        visited: Set[str],
        depth: int,
    ) -> List[str]:
        """Recursive DAG validation with cycle detection."""
        errors: List[str] = []
        if depth > _MAX_NESTING_DEPTH:
            errors.append(f"Max nesting depth ({_MAX_NESTING_DEPTH}) exceeded")
            return errors

        if skill.skill_id in visited:
            errors.append(f"Circular dependency detected: {skill.skill_id}")
            return errors

        visited.add(skill.skill_id)

        step_ids = {s.step_id for s in skill.composition.steps}
        for step in skill.composition.steps:
            # Check dependency references
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"Step {step.step_id} depends on unknown step {dep}"
                    )

            # Check sub-skill references
            if step.sub_skill_id:
                sub = self._skills.get(step.sub_skill_id)
                if not sub:
                    errors.append(
                        f"Step {step.step_id} references unknown skill {step.sub_skill_id}"
                    )
                else:
                    errors.extend(self._validate_dag(sub, visited.copy(), depth + 1))

        return errors

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        *,
        tenant_id: str = "",
    ) -> SkillExecutionRecord:
        """Execute a skill by running its composition DAG."""
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                return SkillExecutionRecord(
                    skill_id=skill_id,
                    tenant_id=tenant_id,
                    status=SkillStepStatus.FAILED,
                    error=f"Skill {skill_id} not found",
                )

        t0 = time.monotonic()
        context = dict(input_data)
        step_results: Dict[str, Any] = {}
        error: Optional[str] = None
        status = SkillStepStatus.COMPLETED

        try:
            completed_steps: set[str] = set()
            pending = list(skill.composition.steps)

            while pending:
                ready = [
                    s for s in pending
                    if all(d in completed_steps for d in s.depends_on)
                ]
                if not ready:
                    error = "Deadlock in skill DAG"
                    status = SkillStepStatus.FAILED
                    break

                for step in ready:
                    step_result = self._execute_step(step, context)
                    step_results[step.step_id] = step_result

                    if step_result.get("status") == "failed":
                        error = step_result.get("error", "Step failed")
                        status = SkillStepStatus.FAILED
                        break

                    # Apply output mapping to context
                    for src_key, dst_key in step.output_mapping.items():
                        if src_key in step_result:
                            context[dst_key] = step_result[src_key]

                    completed_steps.add(step.step_id)
                    pending.remove(step)

                if status == SkillStepStatus.FAILED:
                    break

        except Exception as exc:
            logger.exception("Skill %s execution failed: %s", skill_id, exc)
            error = str(exc)
            status = SkillStepStatus.FAILED

        elapsed_ms = (time.monotonic() - t0) * 1000

        # Update skill stats
        with self._lock:
            if skill_id in self._skills:
                self._skills[skill_id].execution_count += 1
                if status == SkillStepStatus.COMPLETED:
                    self._skills[skill_id].success_count += 1

        record = SkillExecutionRecord(
            skill_id=skill_id,
            tenant_id=tenant_id,
            status=status,
            input_data=input_data,
            output_data=context,
            step_results=step_results,
            execution_time_ms=elapsed_ms,
            error=error,
        )
        self._execution_log.append(record)
        return record

    def _execute_step(
        self,
        step: SkillStep,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single skill step."""
        # Build step input from context via input_mapping
        step_input: Dict[str, Any] = {}
        for ctx_key, step_key in step.input_mapping.items():
            if ctx_key in context:
                step_input[step_key] = context[ctx_key]

        if step.sub_skill_id:
            # Nested skill execution
            record = self.execute(step.sub_skill_id, step_input)
            if record.status == SkillStepStatus.COMPLETED:
                return {**record.output_data, "status": "completed"}
            return {"status": "failed", "error": record.error}

        if step.tool_id:
            executor = self._tool_executors.get(step.tool_id)
            if executor is None:
                return {
                    "status": "failed",
                    "error": f"No executor for tool {step.tool_id}",
                }
            try:
                result = executor(step_input)
                return {**result, "status": "completed"}
            except Exception as exc:
                logger.exception("Step %s (%s) failed: %s",
                                 step.step_id, step.tool_id, exc)
                return {"status": "failed", "error": str(exc)}

        # No tool or sub-skill: pass-through
        return {"status": "completed", **step_input}

    # ------------------------------------------------------------------
    # Saving workflows as skills
    # ------------------------------------------------------------------

    def save_workflow_as_skill(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        *,
        tenant_id: str = "system",
        access: SkillAccess = SkillAccess.PRIVATE,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> SkillSpec:
        """Save an executed workflow as a named, reusable skill."""
        composition = SkillComposition(
            steps=[SkillStep(**s) for s in steps],
        )
        # Auto-detect entry points
        all_ids = {s.step_id for s in composition.steps}
        deps = set()
        for s in composition.steps:
            deps.update(s.depends_on)
        composition.entry_points = [
            sid for sid in all_ids if sid not in deps
        ]

        skill = SkillSpec(
            name=name,
            description=description,
            owner_tenant=tenant_id,
            access=access,
            composition=composition,
            metadata=SkillSpec.model_fields["metadata"].default_factory()
            if callable(SkillSpec.model_fields["metadata"].default_factory)
            else SkillSpec.model_fields["metadata"].default,
        )
        skill.metadata.tags = tags or []
        self.register(skill)
        return skill

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------

    def share_skill(
        self,
        skill_id: str,
        access: SkillAccess,
    ) -> None:
        """Change the access level of a skill."""
        with self._lock:
            skill = self._skills.get(skill_id)
            if not skill:
                raise KeyError(f"Skill {skill_id} not found")
            skill.access = access
            logger.info("Skill %s access changed to %s", skill_id, access.value)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Number of registered skills."""
        with self._lock:
            return len(self._skills)

    def get_execution_log(self) -> List[SkillExecutionRecord]:
        """Return recent execution records."""
        return list(self._execution_log)
