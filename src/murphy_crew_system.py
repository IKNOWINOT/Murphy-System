"""
Murphy System - Murphy Crew System
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Role-based multi-agent team orchestration system for Murphy's 104 bots.
Maps Murphy's 6 automation types (factory, content, data, system, agent, business) to pre-built crew templates.
Integrates with: triage_rollcall_adapter.py, bot_resource_quotas.py, wingman_protocol.py
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AutomationType(str, Enum):
    """Six primary automation categories supported by the Murphy System."""
    FACTORY = "factory"
    CONTENT = "content"
    DATA = "data"
    SYSTEM = "system"
    AGENT = "agent"
    BUSINESS = "business"


class CrewProcess(str, Enum):
    """Execution strategy for a crew mission."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CrewRole(BaseModel):
    """Describes a single agent role within a crew."""
    role_id: str
    name: str
    description: str
    capabilities: List[str]
    authority_level: int = Field(default=5, ge=1, le=10)
    automation_types: List[AutomationType]
    max_concurrent_tasks: int = 3


class CrewTask(BaseModel):
    """Unit of work assigned to a role inside a crew mission."""
    task_id: str
    description: str
    expected_output: str
    assigned_role_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    priority: int = 5


class TaskResult(BaseModel):
    """Outcome of executing a single CrewTask."""
    task_id: str
    role_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    confidence: float = 1.0


class CrewMission(BaseModel):
    """Collection of tasks forming a coherent mission for a crew."""
    mission_id: str
    description: str
    tasks: List[CrewTask]
    automation_type: AutomationType
    process: CrewProcess = CrewProcess.SEQUENTIAL
    budget_usd: float = 10.0
    timeout_s: float = 300.0


# ---------------------------------------------------------------------------
# Dataclass for execution results
# ---------------------------------------------------------------------------

@dataclass
class CrewExecution:
    """Aggregated result of a completed crew mission execution."""
    execution_id: str
    mission_id: str
    results: List[TaskResult]
    total_cost_usd: float
    total_duration_ms: float
    success_rate: float
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# CrewManager - hierarchical delegation layer
# ---------------------------------------------------------------------------

class CrewManager:
    """Hierarchical manager that delegates, reviews, and escalates tasks."""

    def __init__(self, name: str = "Murphy Manager") -> None:
        self.name = name
        logger.debug("CrewManager '%s' initialised.", self.name)

    def delegate(self, task: CrewTask, role: CrewRole) -> TaskResult:
        """Simulate delegation of *task* to *role* and return a TaskResult."""
        start = time.perf_counter()
        logger.debug(
            "Manager '%s' delegating task '%s' to role '%s'.",
            self.name, task.task_id, role.role_id,
        )
        duration_ms = (time.perf_counter() - start) * 1000
        return TaskResult(
            task_id=task.task_id,
            role_id=role.role_id,
            success=True,
            output=f"Delegated by {self.name}: {task.expected_output}",
            cost_usd=0.01 * role.authority_level,
            duration_ms=duration_ms,
            confidence=0.85,
        )

    def review(self, result: TaskResult) -> bool:
        """Return True when *result* meets the minimum confidence threshold."""
        return result.confidence >= 0.6

    def escalate(self, task: CrewTask) -> str:
        """Return an escalation message for *task*."""
        msg = (
            f"[{self.name}] Escalating task '{task.task_id}': "
            f"'{task.description}' — manual intervention required."
        )
        logger.warning(msg)
        return msg


# ---------------------------------------------------------------------------
# Crew - main orchestration class
# ---------------------------------------------------------------------------

class Crew:
    """Thread-safe crew that manages roles and executes missions."""

    def __init__(
        self,
        crew_id: str,
        name: str,
        process: CrewProcess = CrewProcess.SEQUENTIAL,
    ) -> None:
        self.crew_id = crew_id
        self.name = name
        self.process = process
        self._roles: Dict[str, CrewRole] = {}
        self._lock = threading.Lock()
        logger.debug("Crew '%s' (%s) created with process=%s.", name, crew_id, process.value)

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def add_role(self, role: CrewRole) -> None:
        with self._lock:
            self._roles[role.role_id] = role

    def remove_role(self, role_id: str) -> None:
        with self._lock:
            self._roles.pop(role_id, None)

    def get_role(self, role_id: str) -> Optional[CrewRole]:
        with self._lock:
            return self._roles.get(role_id)

    def list_roles(self) -> List[CrewRole]:
        with self._lock:
            return list(self._roles.values())

    # ------------------------------------------------------------------
    # Task assignment
    # ------------------------------------------------------------------

    def assign_task(self, task: CrewTask) -> Optional[CrewRole]:
        """Return the best-matching role for *task* based on description keywords."""
        with self._lock:
            roles = list(self._roles.values())

        if not roles:
            return None

        task_words = set(task.description.lower().split())
        best_role: Optional[CrewRole] = None
        best_score = -1

        for role in roles:
            caps_words = {cap.lower() for cap in role.capabilities}
            score = len(task_words & caps_words)
            if score > best_score or (score == best_score and best_role is None):
                best_score = score
                best_role = role

        return best_role

    # ------------------------------------------------------------------
    # Mission execution helpers
    # ------------------------------------------------------------------

    def _simulate_task(
        self,
        task: CrewTask,
        role: CrewRole,
    ) -> TaskResult:
        """Simulate successful task execution when no handler is provided."""
        start = time.perf_counter()
        duration_ms = (time.perf_counter() - start) * 1000
        return TaskResult(
            task_id=task.task_id,
            role_id=role.role_id,
            success=True,
            output=task.expected_output,
            cost_usd=0.005,
            duration_ms=duration_ms,
            confidence=0.95,
        )

    def _run_task(
        self,
        task: CrewTask,
        role: CrewRole,
        task_handlers: Optional[Dict[str, Callable]],
    ) -> TaskResult:
        start = time.perf_counter()
        try:
            if task_handlers and task.task_id in task_handlers:
                output = task_handlers[task.task_id](task, role)
                duration_ms = (time.perf_counter() - start) * 1000
                return TaskResult(
                    task_id=task.task_id,
                    role_id=role.role_id,
                    success=True,
                    output=output,
                    cost_usd=0.005,
                    duration_ms=duration_ms,
                    confidence=0.95,
                )
            return self._simulate_task(task, role)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Task '%s' raised an error: %s", task.task_id, exc)
            return TaskResult(
                task_id=task.task_id,
                role_id=role.role_id,
                success=False,
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
                confidence=0.0,
            )

    def _resolve_role_for_task(self, task: CrewTask) -> Optional[CrewRole]:
        if task.assigned_role_id:
            role = self.get_role(task.assigned_role_id)
            if role:
                return role
        return self.assign_task(task)

    # ------------------------------------------------------------------
    # Sequential execution
    # ------------------------------------------------------------------

    def _execute_sequential(
        self,
        mission: CrewMission,
        task_handlers: Optional[Dict[str, Callable]],
    ) -> List[TaskResult]:
        completed: Dict[str, TaskResult] = {}
        results: List[TaskResult] = []

        for task in mission.tasks:
            unmet = [dep for dep in task.dependencies if dep not in completed]
            if unmet:
                logger.warning(
                    "Task '%s' has unmet dependencies %s — skipping.", task.task_id, unmet
                )
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        role_id="",
                        success=False,
                        output=None,
                        error=f"Unmet dependencies: {unmet}",
                    )
                )
                continue

            role = self._resolve_role_for_task(task)
            if role is None:
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        role_id="",
                        success=False,
                        output=None,
                        error="No suitable role found.",
                    )
                )
                continue

            result = self._run_task(task, role, task_handlers)
            completed[task.task_id] = result
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def _execute_parallel(
        self,
        mission: CrewMission,
        task_handlers: Optional[Dict[str, Callable]],
    ) -> List[TaskResult]:
        results: List[TaskResult] = []
        collected: Dict[str, TaskResult] = {}
        lock = threading.Lock()

        def run(task: CrewTask) -> None:
            role = self._resolve_role_for_task(task)
            if role is None:
                result = TaskResult(
                    task_id=task.task_id,
                    role_id="",
                    success=False,
                    output=None,
                    error="No suitable role found.",
                )
            else:
                result = self._run_task(task, role, task_handlers)
            with lock:
                collected[task.task_id] = result

        threads = [threading.Thread(target=run, args=(t,)) for t in mission.tasks]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for task in mission.tasks:
            results.append(collected[task.task_id])
        return results

    # ------------------------------------------------------------------
    # Hierarchical execution
    # ------------------------------------------------------------------

    def _execute_hierarchical(
        self,
        mission: CrewMission,
        task_handlers: Optional[Dict[str, Callable]],
    ) -> List[TaskResult]:
        manager = CrewManager()
        results: List[TaskResult] = []

        for task in mission.tasks:
            role = self._resolve_role_for_task(task)
            if role is None:
                results.append(
                    TaskResult(
                        task_id=task.task_id,
                        role_id="",
                        success=False,
                        output=None,
                        error="No suitable role found.",
                    )
                )
                continue

            if task_handlers and task.task_id in task_handlers:
                result = self._run_task(task, role, task_handlers)
            else:
                result = manager.delegate(task, role)

            if not manager.review(result):
                escalation_msg = manager.escalate(task)
                result = TaskResult(
                    task_id=task.task_id,
                    role_id=role.role_id,
                    success=False,
                    output=None,
                    error=escalation_msg,
                    cost_usd=result.cost_usd,
                    duration_ms=result.duration_ms,
                    confidence=result.confidence,
                )

            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Public mission entry-point
    # ------------------------------------------------------------------

    def execute_mission(
        self,
        mission: CrewMission,
        task_handlers: Optional[Dict[str, Callable]] = None,
    ) -> CrewExecution:
        """Execute *mission* using the crew's configured process strategy."""
        execution_id = str(uuid.uuid4())
        logger.info(
            "Crew '%s' starting mission '%s' [%s].",
            self.name, mission.mission_id, mission.process.value,
        )

        mission_start = time.perf_counter()

        if mission.process == CrewProcess.SEQUENTIAL:
            results = self._execute_sequential(mission, task_handlers)
        elif mission.process == CrewProcess.PARALLEL:
            results = self._execute_parallel(mission, task_handlers)
        else:
            results = self._execute_hierarchical(mission, task_handlers)

        total_duration_ms = (time.perf_counter() - mission_start) * 1000
        total_cost_usd = sum(r.cost_usd for r in results)
        successes = sum(1 for r in results if r.success)
        success_rate = successes / (len(results) or 1)

        if success_rate >= 1.0:
            status = "completed"
        elif success_rate > 0.0:
            status = "partial"
        else:
            status = "failed"

        logger.info(
            "Mission '%s' finished — status=%s success_rate=%.2f cost=$%.4f.",
            mission.mission_id, status, success_rate, total_cost_usd,
        )

        return CrewExecution(
            execution_id=execution_id,
            mission_id=mission.mission_id,
            results=results,
            total_cost_usd=total_cost_usd,
            total_duration_ms=total_duration_ms,
            success_rate=success_rate,
            status=status,
        )


# ---------------------------------------------------------------------------
# Pre-built crew templates
# ---------------------------------------------------------------------------

class CrewTemplateFactory:
    """Factory for pre-built, ready-to-use crew configurations."""

    @staticmethod
    def factory_crew() -> Crew:
        """Return a crew optimised for FACTORY automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="Factory Crew",
            process=CrewProcess.SEQUENTIAL,
        )
        crew.add_role(CrewRole(
            role_id="factory-planner",
            name="Factory Planner",
            description="Plans manufacturing workflows and production schedules.",
            capabilities=["planning", "scheduling", "manufacturing", "pipeline"],
            authority_level=8,
            automation_types=[AutomationType.FACTORY],
        ))
        crew.add_role(CrewRole(
            role_id="factory-executor",
            name="Factory Executor",
            description="Executes production tasks and manages machine integrations.",
            capabilities=["execution", "manufacturing", "machine", "integration"],
            authority_level=5,
            automation_types=[AutomationType.FACTORY],
        ))
        crew.add_role(CrewRole(
            role_id="factory-inspector",
            name="Quality Inspector",
            description="Validates output quality and enforces production standards.",
            capabilities=["quality", "inspection", "validation", "standards"],
            authority_level=6,
            automation_types=[AutomationType.FACTORY],
        ))
        return crew

    @staticmethod
    def content_crew() -> Crew:
        """Return a crew optimised for CONTENT automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="Content Crew",
            process=CrewProcess.SEQUENTIAL,
        )
        crew.add_role(CrewRole(
            role_id="content-strategist",
            name="Content Strategist",
            description="Defines content goals, audience targeting, and editorial calendar.",
            capabilities=["strategy", "planning", "content", "editorial", "audience"],
            authority_level=8,
            automation_types=[AutomationType.CONTENT],
        ))
        crew.add_role(CrewRole(
            role_id="content-writer",
            name="Content Writer",
            description="Drafts, edits, and publishes content assets.",
            capabilities=["writing", "editing", "publishing", "content", "copy"],
            authority_level=5,
            automation_types=[AutomationType.CONTENT],
        ))
        crew.add_role(CrewRole(
            role_id="content-reviewer",
            name="Content Reviewer",
            description="Reviews content for accuracy, compliance, and brand alignment.",
            capabilities=["review", "compliance", "brand", "accuracy", "content"],
            authority_level=6,
            automation_types=[AutomationType.CONTENT],
        ))
        crew.add_role(CrewRole(
            role_id="content-distributor",
            name="Content Distributor",
            description="Distributes content across channels and tracks engagement metrics.",
            capabilities=["distribution", "channel", "metrics", "publishing", "content"],
            authority_level=4,
            automation_types=[AutomationType.CONTENT],
        ))
        return crew

    @staticmethod
    def data_crew() -> Crew:
        """Return a crew optimised for DATA automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="Data Crew",
            process=CrewProcess.PARALLEL,
        )
        crew.add_role(CrewRole(
            role_id="data-engineer",
            name="Data Engineer",
            description="Builds and maintains data pipelines and transformations.",
            capabilities=["pipeline", "etl", "data", "transformation", "engineering"],
            authority_level=7,
            automation_types=[AutomationType.DATA],
        ))
        crew.add_role(CrewRole(
            role_id="data-analyst",
            name="Data Analyst",
            description="Analyses datasets and produces actionable insights.",
            capabilities=["analysis", "insights", "data", "reporting", "statistics"],
            authority_level=6,
            automation_types=[AutomationType.DATA],
        ))
        crew.add_role(CrewRole(
            role_id="data-governor",
            name="Data Governor",
            description="Enforces data quality, governance policies, and access controls.",
            capabilities=["governance", "quality", "compliance", "access", "data"],
            authority_level=8,
            automation_types=[AutomationType.DATA],
        ))
        return crew

    @staticmethod
    def system_crew() -> Crew:
        """Return a crew optimised for SYSTEM automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="System Crew",
            process=CrewProcess.HIERARCHICAL,
        )
        crew.add_role(CrewRole(
            role_id="system-architect",
            name="System Architect",
            description="Designs system topology and infrastructure blueprints.",
            capabilities=["architecture", "design", "infrastructure", "system", "planning"],
            authority_level=9,
            automation_types=[AutomationType.SYSTEM],
        ))
        crew.add_role(CrewRole(
            role_id="system-operator",
            name="System Operator",
            description="Operates, monitors, and maintains system components.",
            capabilities=["operations", "monitoring", "maintenance", "system", "deployment"],
            authority_level=5,
            automation_types=[AutomationType.SYSTEM],
        ))
        crew.add_role(CrewRole(
            role_id="system-security",
            name="Security Engineer",
            description="Audits, hardens, and responds to security events.",
            capabilities=["security", "audit", "hardening", "incident", "system"],
            authority_level=8,
            automation_types=[AutomationType.SYSTEM],
        ))
        return crew

    @staticmethod
    def agent_crew() -> Crew:
        """Return a crew optimised for AGENT automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="Agent Crew",
            process=CrewProcess.HIERARCHICAL,
        )
        crew.add_role(CrewRole(
            role_id="agent-orchestrator",
            name="Agent Orchestrator",
            description="Coordinates sub-agents and manages task delegation.",
            capabilities=["orchestration", "delegation", "agent", "coordination"],
            authority_level=9,
            automation_types=[AutomationType.AGENT],
        ))
        crew.add_role(CrewRole(
            role_id="agent-researcher",
            name="Research Agent",
            description="Gathers information, conducts research, and synthesises findings.",
            capabilities=["research", "information", "synthesis", "agent", "retrieval"],
            authority_level=5,
            automation_types=[AutomationType.AGENT],
        ))
        crew.add_role(CrewRole(
            role_id="agent-executor",
            name="Execution Agent",
            description="Carries out concrete actions on behalf of the orchestrator.",
            capabilities=["execution", "action", "agent", "task", "automation"],
            authority_level=4,
            automation_types=[AutomationType.AGENT],
        ))
        crew.add_role(CrewRole(
            role_id="agent-evaluator",
            name="Evaluation Agent",
            description="Evaluates agent outputs and provides feedback loops.",
            capabilities=["evaluation", "feedback", "quality", "agent", "review"],
            authority_level=6,
            automation_types=[AutomationType.AGENT],
        ))
        return crew

    @staticmethod
    def business_crew() -> Crew:
        """Return a crew optimised for BUSINESS automation."""
        crew = Crew(
            crew_id=str(uuid.uuid4()),
            name="Business Crew",
            process=CrewProcess.SEQUENTIAL,
        )
        crew.add_role(CrewRole(
            role_id="business-strategist",
            name="Business Strategist",
            description="Develops business strategies, OKRs, and growth plans.",
            capabilities=["strategy", "planning", "okr", "business", "growth"],
            authority_level=9,
            automation_types=[AutomationType.BUSINESS],
        ))
        crew.add_role(CrewRole(
            role_id="business-analyst",
            name="Business Analyst",
            description="Analyses business processes, costs, and performance metrics.",
            capabilities=["analysis", "process", "metrics", "business", "cost"],
            authority_level=6,
            automation_types=[AutomationType.BUSINESS],
        ))
        crew.add_role(CrewRole(
            role_id="business-ops",
            name="Business Operations",
            description="Executes operational tasks, vendor management, and logistics.",
            capabilities=["operations", "vendor", "logistics", "business", "execution"],
            authority_level=5,
            automation_types=[AutomationType.BUSINESS],
        ))
        return crew

    @staticmethod
    def get_crew_for_type(automation_type: AutomationType) -> Crew:
        """Dispatch to the pre-built crew matching *automation_type*."""
        dispatch: Dict[AutomationType, Callable[[], Crew]] = {
            AutomationType.FACTORY: CrewTemplateFactory.factory_crew,
            AutomationType.CONTENT: CrewTemplateFactory.content_crew,
            AutomationType.DATA: CrewTemplateFactory.data_crew,
            AutomationType.SYSTEM: CrewTemplateFactory.system_crew,
            AutomationType.AGENT: CrewTemplateFactory.agent_crew,
            AutomationType.BUSINESS: CrewTemplateFactory.business_crew,
        }
        return dispatch[automation_type]()


# ---------------------------------------------------------------------------
# Module-level utility function
# ---------------------------------------------------------------------------

def load_bot_crew(bot_names: List[str]) -> Crew:
    """Create a Crew with one CrewRole per entry in *bot_names*.

    Each role is given generic capabilities derived from its name.
    The returned crew uses a SEQUENTIAL process by default.
    """
    crew = Crew(
        crew_id=str(uuid.uuid4()),
        name="Bot Crew",
        process=CrewProcess.SEQUENTIAL,
    )

    for bot_name in bot_names:
        safe_name = bot_name.strip()
        if not safe_name:
            continue
        role_id = f"bot-{safe_name.lower().replace(' ', '-')}"
        capabilities = [safe_name.lower(), "automation", "task", "execution"]
        crew.add_role(CrewRole(
            role_id=role_id,
            name=safe_name,
            description=f"Bot agent: {safe_name}.",
            capabilities=capabilities,
            authority_level=3,
            automation_types=list(AutomationType),
        ))

    logger.debug(
        "load_bot_crew: created crew with %d roles from %d bot names.",
        len(crew.list_roles()),
        len(bot_names),
    )
    return crew
