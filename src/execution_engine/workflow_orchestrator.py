"""
Workflow Orchestrator - Define and execute complex workflows
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .task_executor import Task, TaskExecutor, TaskState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowState(Enum):
    """Workflow execution states"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepType(Enum):
    """Types of workflow steps"""
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    LOOP = "loop"
    SUBWORKFLOW = "subworkflow"


class WorkflowStep:
    """Single workflow step"""

    def __init__(
        self,
        step_id: Optional[str] = None,
        step_type: WorkflowStepType = WorkflowStepType.TASK,
        action: Optional[Callable] = None,
        parameters: Optional[Dict] = None,
        conditions: Optional[List[Dict]] = None,
        dependencies: Optional[List[str]] = None,
        parallel_steps: Optional[List['WorkflowStep']] = None,
        loop_config: Optional[Dict] = None
    ):
        self.step_id = step_id or str(uuid.uuid4())
        self.step_type = step_type
        self.action = action
        self.parameters = parameters or {}
        self.conditions = conditions or []
        self.dependencies = dependencies or []
        self.parallel_steps = parallel_steps or []
        self.loop_config = loop_config or {}

        # Execution state
        self.state = WorkflowState.PENDING
        self.result = None
        self.error = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.execution_time: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert step to dictionary"""
        return {
            'step_id': self.step_id,
            'step_type': self.step_type.value,
            'parameters': self.parameters,
            'conditions': self.conditions,
            'dependencies': self.dependencies,
            'state': self.state.value,
            'result': self.result,
            'error': str(self.error) if self.error else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time
        }


class Workflow:
    """Workflow definition"""

    def __init__(
        self,
        workflow_id: Optional[str] = None,
        name: str = "Unnamed Workflow",
        description: str = "",
        steps: Optional[List[WorkflowStep]] = None,
        variables: Optional[Dict] = None,
        timeout: float = 3600.0
    ):
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.steps = steps or []
        self.variables = variables or {}
        self.timeout = timeout

        # Execution state
        self.state = WorkflowState.PENDING
        self.current_step_index = 0
        self.results: Dict[str, Any] = {}
        self.errors: List[Dict] = []
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.execution_time: Optional[float] = None

    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow"""
        self.steps.append(step)

    def add_variable(self, name: str, value: Any) -> None:
        """Add a variable to the workflow"""
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a workflow variable"""
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a workflow variable"""
        self.variables[name] = value

    def to_dict(self) -> Dict:
        """Convert workflow to dictionary"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'steps': [step.to_dict() for step in self.steps],
            'variables': self.variables,
            'state': self.state.value,
            'current_step_index': self.current_step_index,
            'results': self.results,
            'errors': self.errors,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time
        }


class WorkflowOrchestrator:
    """Orchestrate workflow execution"""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.workflows: Dict[str, Workflow] = {}
        self.task_executor = TaskExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def create_workflow(
        self,
        name: str,
        description: str = "",
        steps: Optional[List[WorkflowStep]] = None,
        **kwargs
    ) -> Workflow:
        """Create a new workflow"""
        workflow = Workflow(
            name=name,
            description=description,
            steps=steps,
            **kwargs
        )

        with self._lock:
            self.workflows[workflow.workflow_id] = workflow

        logger.info(f"Workflow created: {workflow.workflow_id} - {name}")
        return workflow

    def execute_workflow(self, workflow_id: str) -> str:
        """Execute a workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Start task executor
        self.task_executor.start()

        # Update workflow state
        workflow.state = WorkflowState.RUNNING
        workflow.started_at = datetime.now(timezone.utc)

        logger.info(f"Workflow started: {workflow.workflow_id}")

        # Execute workflow steps
        try:
            self._execute_workflow_steps(workflow)
            workflow.state = WorkflowState.COMPLETED
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.execution_time = (workflow.completed_at - workflow.started_at).total_seconds()

            logger.info(f"Workflow completed: {workflow.workflow_id} in {workflow.execution_time:.2f}s")

        except Exception as exc:
            workflow.state = WorkflowState.FAILED
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.execution_time = (workflow.completed_at - workflow.started_at).total_seconds()
            workflow.errors.append({
                'error': str(exc),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

            logger.error(f"Workflow failed: {workflow.workflow_id} - {exc}")

        return workflow_id

    def _execute_workflow_steps(self, workflow: Workflow) -> None:
        """Execute workflow steps"""
        while workflow.current_step_index < len(workflow.steps):
            step = workflow.steps[workflow.current_step_index]

            # Check if step should execute
            if not self._should_execute_step(workflow, step):
                workflow.current_step_index += 1
                continue

            # Execute the step
            step.state = WorkflowState.RUNNING
            step.started_at = datetime.now(timezone.utc)

            try:
                result = self._execute_step(workflow, step)
                step.result = result
                step.state = WorkflowState.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
                step.execution_time = (step.completed_at - step.started_at).total_seconds()

                # Store result in workflow variables
                workflow.results[step.step_id] = result

            except Exception as exc:
                step.error = exc
                step.state = WorkflowState.FAILED
                step.completed_at = datetime.now(timezone.utc)
                step.execution_time = (step.completed_at - step.started_at).total_seconds()

                workflow.errors.append({
                    'step_id': step.step_id,
                    'error': str(exc),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                logger.error(f"Step failed: {step.step_id} - {exc}")
                raise

            # Move to next step
            workflow.current_step_index += 1

    def _should_execute_step(self, workflow: Workflow, step: WorkflowStep) -> bool:
        """Check if step should execute based on conditions"""
        # Check dependencies
        for dep_id in step.dependencies:
            dep_step = self._get_step_by_id(workflow, dep_id)
            if not dep_step or dep_step.state != WorkflowState.COMPLETED:
                return False

        # Check conditions
        for condition in step.conditions:
            if not self._evaluate_condition(workflow, condition):
                return False

        return True

    def _evaluate_condition(self, workflow: Workflow, condition: Dict) -> bool:
        """Evaluate a condition"""
        condition_type = condition.get('type')

        if condition_type == 'variable_equals':
            variable_name = condition.get('variable')
            expected_value = condition.get('value')
            actual_value = workflow.get_variable(variable_name)
            return actual_value == expected_value

        elif condition_type == 'result_contains':
            step_id = condition.get('step_id')
            expected_value = condition.get('value')
            result = workflow.results.get(step_id)
            return expected_value in str(result)

        elif condition_type == 'custom':
            custom_function = condition.get('function')
            if custom_function and callable(custom_function):
                return custom_function(workflow)

        return True

    def _execute_step(self, workflow: Workflow, step: WorkflowStep) -> Any:
        """Execute a workflow step"""
        if step.step_type == WorkflowStepType.TASK:
            return self._execute_task_step(workflow, step)

        elif step.step_type == WorkflowStepType.PARALLEL:
            return self._execute_parallel_steps(workflow, step)

        elif step.step_type == WorkflowStepType.LOOP:
            return self._execute_loop_step(workflow, step)

        elif step.step_type == WorkflowStepType.CONDITION:
            return self._execute_condition_step(workflow, step)

        else:
            raise ValueError(f"Unknown step type: {step.step_type}")

    def _execute_task_step(self, workflow: Workflow, step: WorkflowStep) -> Any:
        """Execute a task step"""
        # Create a task from the step
        task = Task(
            task_type=step.step_id,
            action=step.action,
            parameters=step.parameters
        )

        # Execute the task
        task_id = self.task_executor.schedule_task(task)

        # Wait for task completion with timeout
        deadline = time.monotonic() + 30
        while True:
            task_status = self.task_executor.get_task_status(task_id)
            if not task_status:
                raise Exception(f"Task not found: {task_id}")

            if task_status['state'] in ['completed', 'failed', 'cancelled', 'timeout']:
                break

            if time.monotonic() > deadline:
                raise Exception(f"Task timed out: {task_id}")

            time.sleep(0.1)

        # Return result or raise error
        if task_status['state'] == 'completed':
            return task_status['result']
        else:
            raise Exception(f"Task failed: {task_status.get('error')}")

    def _execute_parallel_steps(self, workflow: Workflow, step: WorkflowStep) -> List[Any]:
        """Execute parallel steps"""
        if not step.parallel_steps:
            return []

        # Execute all parallel steps
        results = []
        for parallel_step in step.parallel_steps:
            result = self._execute_step(workflow, parallel_step)
            results.append(result)

        return results

    def _execute_loop_step(self, workflow: Workflow, step: WorkflowStep) -> List[Any]:
        """Execute a loop step"""
        loop_count = step.loop_config.get('count', 1)
        loop_variable = step.loop_config.get('variable', 'item')

        results = []
        for i in range(loop_count):
            # Set loop variable
            workflow.set_variable(loop_variable, i)

            # Execute step
            result = self._execute_task_step(workflow, step)
            results.append(result)

        return results

    def _execute_condition_step(self, workflow: Workflow, step: WorkflowStep) -> bool:
        """Execute a condition step"""
        return self._evaluate_condition(workflow, step.parameters)

    def _get_step_by_id(self, workflow: Workflow, step_id: str) -> Optional[WorkflowStep]:
        """Get step by ID"""
        for step in workflow.steps:
            if step.step_id == step_id:
                return step
        return None

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a workflow"""
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.state == WorkflowState.RUNNING:
            workflow.state = WorkflowState.PAUSED
            logger.info(f"Workflow paused: {workflow_id}")
            return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow"""
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.state == WorkflowState.PAUSED:
            workflow.state = WorkflowState.RUNNING
            logger.info(f"Workflow resumed: {workflow_id}")
            return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow"""
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.state in [WorkflowState.RUNNING, WorkflowState.PAUSED]:
            workflow.state = WorkflowState.CANCELLED
            workflow.completed_at = datetime.now(timezone.utc)
            if workflow.started_at:
                workflow.execution_time = (workflow.completed_at - workflow.started_at).total_seconds()
            logger.info(f"Workflow cancelled: {workflow_id}")
            return True
        return False

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow status"""
        workflow = self.workflows.get(workflow_id)
        if workflow:
            return workflow.to_dict()
        return None

    def get_all_workflows(self) -> List[Dict]:
        """Get all workflows"""
        return [workflow.to_dict() for workflow in self.workflows.values()]

    def start(self) -> None:
        """Start the orchestrator"""
        self.task_executor.start()
        logger.info("Workflow orchestrator started")

    def stop(self) -> None:
        """Stop the orchestrator"""
        self.task_executor.stop()
        logger.info("Workflow orchestrator stopped")


# Convenience functions

def create_workflow_step(
    step_type: WorkflowStepType = WorkflowStepType.TASK,
    action: Optional[Callable] = None,
    parameters: Optional[Dict] = None,
    **kwargs
) -> WorkflowStep:
    """Create a workflow step"""
    return WorkflowStep(
        step_type=step_type,
        action=action,
        parameters=parameters,
        **kwargs
    )


def execute_workflow(
    name: str,
    steps: List[WorkflowStep],
    **kwargs
) -> Dict:
    """Execute a workflow immediately"""
    orchestrator = WorkflowOrchestrator()

    workflow = orchestrator.create_workflow(
        name=name,
        steps=steps,
        **kwargs
    )

    orchestrator.start()
    orchestrator.execute_workflow(workflow.workflow_id)
    orchestrator.stop()

    return workflow.to_dict()
