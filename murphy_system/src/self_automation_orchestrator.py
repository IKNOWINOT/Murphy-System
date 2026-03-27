"""
Self-Automation Orchestrator for Murphy System.

Enables the Murphy System to define, queue, and execute its own improvement tasks
using structured prompt chain templates. Provides task discovery, prioritization,
execution tracking, and continuous improvement loop management.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class TaskCategory(str, Enum):
    """Task category (str subclass)."""
    COVERAGE_GAP = "coverage_gap"
    INTEGRATION_GAP = "integration_gap"
    COMPETITIVE_GAP = "competitive_gap"
    QUALITY_GAP = "quality_gap"
    DOCUMENTATION_GAP = "documentation_gap"
    SELF_IMPROVEMENT = "self_improvement"
    FEATURE_REQUEST = "feature_request"
    BUG_FIX = "bug_fix"


class TaskStatus(str, Enum):
    """Task status (str subclass)."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class PromptStep(str, Enum):
    """Prompt step (str subclass)."""
    ANALYSIS = "analysis"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    DOCUMENTATION = "documentation"
    ITERATION = "iteration"
    TRANSITION = "transition"


@dataclass
class ImprovementTask:
    """A single self-improvement task."""
    task_id: str
    title: str
    category: TaskCategory
    priority: int  # 1 = highest, 5 = lowest
    description: str
    prompt_template: str = ""
    estimated_tests: int = 0
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    current_step: PromptStep = PromptStep.ANALYSIS
    module_name: Optional[str] = None
    test_file: Optional[str] = None


@dataclass
class CycleRecord:
    """Record of one complete improvement cycle."""
    cycle_id: str
    started_at: str
    completed_at: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tests_added: int = 0
    modules_added: List[str] = field(default_factory=list)
    gap_analysis: Optional[Dict[str, Any]] = None


class SelfAutomationOrchestrator:
    """
    Orchestrates self-improvement cycles for the Murphy System.

    Design Label: ARCH-002 — Persistence-Aware Self-Automation Orchestrator
    Owner: Backend Team
    Dependency: PersistenceManager (optional, graceful degradation)

    Provides:
    - Task discovery from module/test analysis
    - Priority-based task queue with dependency resolution
    - Prompt chain step tracking per task
    - Cycle management with history
    - Gap analysis and remediation tracking
    - Durable state via PersistenceManager  [ARCH-002]
    """

    # Default prompt chain templates
    PROMPT_TEMPLATES = {
        PromptStep.ANALYSIS: (
            "Analyze the Murphy System module at src/{module_name}.py. "
            "Check test coverage at tests/test_{module_name}.py. "
            "Identify gaps in functionality, test coverage, and integration wiring."
        ),
        PromptStep.PLANNING: (
            "Plan implementation for: {title}. "
            "Define classes, methods, test cases, and runtime wiring for src/{module_name}.py. "
            "Ensure no circular dependencies with existing modules."
        ),
        PromptStep.IMPLEMENTATION: (
            "Implement src/{module_name}.py following Murphy System conventions: "
            "Python stdlib only, type hints, threading.Lock for shared state, "
            "get_status() method, unittest.TestCase tests in tests/test_{module_name}.py."
        ),
        PromptStep.TESTING: (
            "Run tests for the module: "
            "python -m pytest tests/test_{module_name}.py -x -v && "
            "python -m pytest tests/test_integrated_execution_wiring.py -x -q"
        ),
        PromptStep.REVIEW: (
            "Review src/{module_name}.py for: no secrets, stdlib only, "
            "thread safety, error handling, type hints, docstrings, naming conventions."
        ),
        PromptStep.DOCUMENTATION: (
            "Update FULL_SYSTEM_ASSESSMENT.md, README.md, and RECOMMENDATIONS.md "
            "to reflect the addition of {module_name} with {test_count} tests."
        ),
        PromptStep.ITERATION: (
            "Check if more improvement tasks remain. "
            "Re-run gap analysis and update the task queue."
        ),
        PromptStep.TRANSITION: (
            "Transition module {module_name} to the next operational phase. "
            "Validate prerequisites, update state, and notify dependent systems."
        ),
    }

    # Persistence document ID  [ARCH-002]
    _PERSIST_DOC_ID = "self_automation_orchestrator_state"

    def __init__(self, persistence_manager=None) -> None:
        from threading import RLock
        self._lock = RLock()
        self._tasks: Dict[str, ImprovementTask] = {}
        self._queue_order: List[str] = []  # task_ids in priority order
        self._cycles: List[CycleRecord] = []
        self._current_cycle: Optional[CycleRecord] = None
        self._completed_tasks: List[str] = []
        self._gap_registry: Dict[str, Dict[str, Any]] = {}
        self._persistence = persistence_manager

    # ---- Persistence Integration  [ARCH-002] ----

    def save_state(self) -> bool:
        """Persist orchestrator state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._persistence is None:
            return False
        with self._lock:
            state = {
                "tasks": {
                    tid: asdict(t) for tid, t in self._tasks.items()
                },
                "queue_order": list(self._queue_order),
                "cycles": [asdict(c) for c in self._cycles],
                "current_cycle": asdict(self._current_cycle) if self._current_cycle else None,
                "completed_tasks": list(self._completed_tasks),
                "gap_registry": dict(self._gap_registry),
            }
        try:
            self._persistence.save_document(self._PERSIST_DOC_ID, state)
            return True
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore orchestrator state from PersistenceManager.

        Returns True on success, False if persistence is unavailable or
        no prior state exists.
        """
        if self._persistence is None:
            return False
        try:
            state = self._persistence.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return False
        if state is None:
            return False
        with self._lock:
            self._tasks = {}
            for tid, td in state.get("tasks", {}).items():
                self._tasks[tid] = ImprovementTask(
                    task_id=td["task_id"],
                    title=td["title"],
                    category=TaskCategory(td["category"]),
                    priority=td["priority"],
                    description=td.get("description", ""),
                    prompt_template=td.get("prompt_template", ""),
                    estimated_tests=td.get("estimated_tests", 0),
                    dependencies=td.get("dependencies", []),
                    status=TaskStatus(td["status"]),
                    created_at=td.get("created_at", ""),
                    started_at=td.get("started_at"),
                    completed_at=td.get("completed_at"),
                    result=td.get("result"),
                    retry_count=td.get("retry_count", 0),
                    max_retries=td.get("max_retries", 3),
                    current_step=PromptStep(td.get("current_step", "analysis")),
                    module_name=td.get("module_name"),
                    test_file=td.get("test_file"),
                )
            self._queue_order = state.get("queue_order", [])
            self._cycles = [
                CycleRecord(
                    cycle_id=cd["cycle_id"],
                    started_at=cd["started_at"],
                    completed_at=cd.get("completed_at"),
                    tasks_completed=cd.get("tasks_completed", 0),
                    tasks_failed=cd.get("tasks_failed", 0),
                    tests_added=cd.get("tests_added", 0),
                    modules_added=cd.get("modules_added", []),
                    gap_analysis=cd.get("gap_analysis"),
                )
                for cd in state.get("cycles", [])
            ]
            cc = state.get("current_cycle")
            self._current_cycle = CycleRecord(
                cycle_id=cc["cycle_id"],
                started_at=cc["started_at"],
                completed_at=cc.get("completed_at"),
                tasks_completed=cc.get("tasks_completed", 0),
                tasks_failed=cc.get("tasks_failed", 0),
                tests_added=cc.get("tests_added", 0),
                modules_added=cc.get("modules_added", []),
                gap_analysis=cc.get("gap_analysis"),
            ) if cc else None
            self._completed_tasks = state.get("completed_tasks", [])
            self._gap_registry = state.get("gap_registry", {})
        return True

    # ---- Task Management ----

    def create_task(
        self,
        title: str,
        category: TaskCategory,
        priority: int = 3,
        description: str = "",
        module_name: Optional[str] = None,
        test_file: Optional[str] = None,
        estimated_tests: int = 0,
        dependencies: Optional[List[str]] = None,
        prompt_template: str = "",
    ) -> ImprovementTask:
        """Create and queue a new improvement task."""
        task_id = f"task-{hashlib.sha256(f'{title}:{time.time()}'.encode()).hexdigest()[:12]}"
        task = ImprovementTask(
            task_id=task_id,
            title=title,
            category=category,
            priority=max(1, min(5, priority)),
            description=description,
            module_name=module_name,
            test_file=test_file or (f"tests/test_{module_name}.py" if module_name else None),
            estimated_tests=estimated_tests,
            dependencies=dependencies or [],
            prompt_template=prompt_template,
        )
        with self._lock:
            self._tasks[task_id] = task
            capped_append(self._queue_order, task_id)
            self._sort_queue()
        return task

    def get_task(self, task_id: str) -> Optional[ImprovementTask]:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        category: Optional[TaskCategory] = None,
    ) -> List[ImprovementTask]:
        """List tasks with optional filtering."""
        with self._lock:
            tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if category is not None:
            tasks = [t for t in tasks if t.category == category]
        return sorted(tasks, key=lambda t: (t.priority, t.created_at))

    def get_next_task(self) -> Optional[ImprovementTask]:
        """Get the next task from the queue that has all dependencies met."""
        with self._lock:
            completed_ids: Set[str] = {
                tid for tid, t in self._tasks.items()
                if t.status == TaskStatus.COMPLETED
            }
            for task_id in self._queue_order:
                task = self._tasks[task_id]
                if task.status != TaskStatus.QUEUED:
                    continue
                if all(dep in completed_ids for dep in task.dependencies):
                    return task
        return None

    def start_task(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.QUEUED:
                return False
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now(timezone.utc).isoformat()
            task.current_step = PromptStep.IMPLEMENTATION
            return True

    def advance_step(self, task_id: str, step: PromptStep) -> bool:
        """Advance a task to the next prompt chain step."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.TESTING, TaskStatus.REVIEW):
                return False
            task.current_step = step
            if step == PromptStep.TESTING:
                task.status = TaskStatus.TESTING
            elif step == PromptStep.REVIEW:
                task.status = TaskStatus.REVIEW
            return True

    def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a task as completed."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()
            task.result = result or {}
            capped_append(self._completed_tasks, task_id)
            if task_id in self._queue_order:
                self._queue_order.remove(task_id)
            if self._current_cycle:
                self._current_cycle.tasks_completed += 1
                self._current_cycle.tests_added += task.estimated_tests
                if task.module_name:
                    self._current_cycle.modules_added.append(task.module_name)
            return True

    def fail_task(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as failed (may retry)."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.QUEUED
                task.current_step = PromptStep.ANALYSIS
                task.result = {"last_failure": reason, "retries": task.retry_count}
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.result = {"failure_reason": reason, "retries": task.retry_count}
                if self._current_cycle:
                    self._current_cycle.tasks_failed += 1
            return True

    def block_task(self, task_id: str, reason: str = "") -> bool:
        """Mark a task as blocked."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task.status = TaskStatus.BLOCKED
            task.result = {"blocked_reason": reason}
            return True

    # ---- Cycle Management ----

    def start_cycle(self, gap_analysis: Optional[Dict[str, Any]] = None) -> CycleRecord:
        """Start a new improvement cycle."""
        cycle_id = f"cycle-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}"
        cycle = CycleRecord(
            cycle_id=cycle_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            gap_analysis=gap_analysis,
        )
        with self._lock:
            self._current_cycle = cycle
        return cycle

    def complete_cycle(self) -> Optional[CycleRecord]:
        """Complete the current improvement cycle."""
        with self._lock:
            if not self._current_cycle:
                return None
            self._current_cycle.completed_at = datetime.now(timezone.utc).isoformat()
            capped_append(self._cycles, self._current_cycle)
            completed = self._current_cycle
            self._current_cycle = None
            return completed

    def get_cycle_history(self) -> List[CycleRecord]:
        """Get all completed improvement cycles."""
        with self._lock:
            return list(self._cycles)

    # ---- Gap Analysis ----

    def register_gap(
        self,
        gap_id: str,
        category: TaskCategory,
        title: str,
        severity: int = 3,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a discovered gap for tracking."""
        with self._lock:
            self._gap_registry[gap_id] = {
                "gap_id": gap_id,
                "category": category.value,
                "title": title,
                "severity": severity,
                "details": details or {},
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "resolved": False,
            }

    def resolve_gap(self, gap_id: str, resolution: str = "") -> bool:
        """Mark a gap as resolved."""
        with self._lock:
            gap = self._gap_registry.get(gap_id)
            if not gap:
                return False
            gap["resolved"] = True
            gap["resolution"] = resolution
            gap["resolved_at"] = datetime.now(timezone.utc).isoformat()
            return True

    def get_open_gaps(self) -> List[Dict[str, Any]]:
        """Get all unresolved gaps."""
        with self._lock:
            return [g for g in self._gap_registry.values() if not g["resolved"]]

    def analyze_coverage_gaps(
        self,
        module_test_counts: Dict[str, int],
        min_tests: int = 25,
    ) -> List[Dict[str, Any]]:
        """Analyze modules for test coverage gaps.

        Args:
            module_test_counts: mapping of module_name → test count
            min_tests: minimum acceptable test count per module

        Returns:
            list of gap descriptions for under-covered modules
        """
        gaps = []
        for module, count in module_test_counts.items():
            if count < min_tests:
                gap = {
                    "module": module,
                    "current_tests": count,
                    "target_tests": min_tests,
                    "deficit": min_tests - count,
                    "category": TaskCategory.COVERAGE_GAP.value,
                }
                gaps.append(gap)
                self.register_gap(
                    gap_id=f"coverage-{module}",
                    category=TaskCategory.COVERAGE_GAP,
                    title=f"{module} has only {count} tests (min: {min_tests})",
                    severity=2 if count < 15 else 3,
                    details=gap,
                )
        return sorted(gaps, key=lambda g: g["deficit"], reverse=True)

    # ---- Prompt Generation ----

    def generate_prompt(
        self,
        task: ImprovementTask,
        step: Optional[PromptStep] = None,
    ) -> str:
        """Generate the prompt for a specific step of a task."""
        step = step or task.current_step
        template = task.prompt_template or self.PROMPT_TEMPLATES.get(step, "")
        return template.format(
            title=task.title,
            module_name=task.module_name or "unknown",
            test_count=task.estimated_tests,
            description=task.description,
        )

    def generate_full_chain(self, task: ImprovementTask) -> Dict[str, str]:
        """Generate all prompts in the chain for a task."""
        chain = {}
        for step in PromptStep:
            chain[step.value] = self.generate_prompt(task, step)
        return chain

    # ---- Status ----

    def get_status(self) -> Dict[str, Any]:
        """Get the current orchestrator status."""
        with self._lock:
            status_counts = {}
            for task in self._tasks.values():
                key = task.status.value
                status_counts[key] = status_counts.get(key, 0) + 1

            category_counts = {}
            for task in self._tasks.values():
                key = task.category.value
                category_counts[key] = category_counts.get(key, 0) + 1

            return {
                "total_tasks": len(self._tasks),
                "queue_length": len(self._queue_order),
                "completed_count": len(self._completed_tasks),
                "status_breakdown": status_counts,
                "category_breakdown": category_counts,
                "open_gaps": len(self.get_open_gaps()),
                "total_gaps": len(self._gap_registry),
                "current_cycle": asdict(self._current_cycle) if self._current_cycle else None,
                "completed_cycles": len(self._cycles),
                "prompt_steps": [s.value for s in PromptStep],
                "available_categories": [c.value for c in TaskCategory],
            }

    # ---- Internal ----

    def _sort_queue(self) -> None:
        """Sort the queue by priority (lower number = higher priority)."""
        self._queue_order.sort(
            key=lambda tid: self._tasks[tid].priority
        )
