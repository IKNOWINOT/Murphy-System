"""
Workflow Orchestrator
Manages complex multi-agent workflows with conditional logic and parallel execution
"""

from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid
from datetime import datetime
import json
from cooperative_swarm_system import Task, TaskStatus, CooperativeSwarmSystem
from agent_handoff_manager import AgentHandoffManager, HandoffContext


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"  # Execute steps one after another
    PARALLEL = "parallel"  # Execute all steps in parallel
    CONDITIONAL = "conditional"  # Execute based on conditions
    HYBRID = "hybrid"  # Mix of sequential and parallel


@dataclass
class WorkflowStep:
    """A single step in a workflow"""
    step_id: str
    agent: str
    action: str
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    condition: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    parallel_with: List[str] = field(default_factory=list)
    timeout: float = 60.0
    retry_on_failure: bool = False
    max_retries: int = 3


@dataclass
class WorkflowDefinition:
    """Definition of a complete workflow"""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    global_timeout: float = 300.0
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Execution instance of a workflow"""
    execution_id: str
    workflow_definition: WorkflowDefinition
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_index: int = 0
    step_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: HandoffContext = field(default_factory=HandoffContext)


class WorkflowOrchestrator:
    """Orchestrates complex multi-agent workflows"""
    
    def __init__(self, cooperative_swarm: CooperativeSwarmSystem,
                 handoff_manager: AgentHandoffManager):
        self.cooperative_swarm = cooperative_swarm
        self.handoff_manager = handoff_manager
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        self.step_handlers: Dict[str, Callable] = {}
        self.condition_evaluators: Dict[str, Callable] = {}
        
    def register_step_handler(self, step_type: str, handler: Callable):
        """Register a handler for a specific step type"""
        self.step_handlers[step_type] = handler
    
    def register_condition_evaluator(self, condition_type: str, evaluator: Callable):
        """Register an evaluator for a condition type"""
        self.condition_evaluators[condition_type] = evaluator
    
    def define_workflow(self, name: str, description: str,
                       steps: List[Dict], execution_mode: str = "sequential",
                       **kwargs) -> WorkflowDefinition:
        """
        Define a workflow from a specification
        
        Example steps spec:
        [
            {
                "step_id": "step_1",
                "agent": "planning_agent",
                "action": "create_plan",
                "input_mapping": {"user_request": "input.user_request"},
                "condition": "input.complexity > 5"
            },
            {
                "step_id": "step_2",
                "agent": "execution_agent",
                "action": "execute_task",
                "depends_on": ["step_1"]
            }
        ]
        """
        workflow_steps = []
        
        for step_spec in steps:
            step = WorkflowStep(
                step_id=step_spec.get("step_id", str(uuid.uuid4())),
                agent=step_spec["agent"],
                action=step_spec["action"],
                input_mapping=step_spec.get("input_mapping", {}),
                output_mapping=step_spec.get("output_mapping", {}),
                condition=step_spec.get("condition"),
                depends_on=step_spec.get("depends_on", []),
                parallel_with=step_spec.get("parallel_with", []),
                timeout=step_spec.get("timeout", 60.0),
                retry_on_failure=step_spec.get("retry_on_failure", False),
                max_retries=step_spec.get("max_retries", 3)
            )
            workflow_steps.append(step)
        
        workflow = WorkflowDefinition(
            workflow_id=kwargs.get("workflow_id", str(uuid.uuid4())),
            name=name,
            description=description,
            steps=workflow_steps,
            execution_mode=ExecutionMode(execution_mode),
            global_timeout=kwargs.get("global_timeout", 300.0),
            variables=kwargs.get("variables", {}),
            metadata=kwargs.get("metadata", {})
        )
        
        return workflow
    
    async def execute_workflow(self, workflow: WorkflowDefinition,
                            initial_input: Dict[str, Any] = None) -> WorkflowExecution:
        """Execute a workflow"""
        execution = WorkflowExecution(
            execution_id=str(uuid.uuid4()),
            workflow_definition=workflow,
            started_at=datetime.now(),
            status=WorkflowStatus.RUNNING
        )
        
        # Initialize context
        if initial_input:
            execution.context.shared_variables.update(initial_input)
        
        self.active_executions[execution.execution_id] = execution
        
        try:
            # Execute based on mode
            if workflow.execution_mode == ExecutionMode.SEQUENTIAL:
                await self._execute_sequential(execution)
            elif workflow.execution_mode == ExecutionMode.PARALLEL:
                await self._execute_parallel(execution)
            elif workflow.execution_mode == ExecutionMode.CONDITIONAL:
                await self._execute_conditional(execution)
            elif workflow.execution_mode == ExecutionMode.HYBRID:
                await self._execute_hybrid(execution)
            
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now()
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.errors.append({
                "step": execution.current_step_index,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            execution.completed_at = datetime.now()
        
        self.execution_history.append(execution)
        
        return execution
    
    async def _execute_sequential(self, execution: WorkflowExecution):
        """Execute workflow steps sequentially"""
        workflow = execution.workflow_definition
        
        for i, step in enumerate(workflow.steps):
            execution.current_step_index = i
            
            # Check if condition is met
            if step.condition and not self._evaluate_condition(step.condition, execution):
                continue
            
            # Check dependencies
            if not self._check_dependencies(step, execution):
                raise Exception(f"Dependencies not met for step {step.step_id}")
            
            # Execute step
            result = await self._execute_step(step, execution)
            execution.step_results[step.step_id] = result
            
            # Map outputs to context
            self._map_outputs(step.output_mapping, result, execution.context)
    
    async def _execute_parallel(self, execution: WorkflowExecution):
        """Execute workflow steps in parallel where possible"""
        workflow = execution.workflow_definition
        execution_groups = self._group_parallel_steps(workflow.steps)
        
        for group in execution_groups:
            # Execute group in parallel
            tasks = [self._execute_step(step, execution) for step in group]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results
            for step, result in zip(group, results):
                if isinstance(result, Exception):
                    execution.errors.append({
                        "step": step.step_id,
                        "error": str(result)
                    })
                else:
                    execution.step_results[step.step_id] = result
                    self._map_outputs(step.output_mapping, result, execution.context)
    
    async def _execute_conditional(self, execution: WorkflowExecution):
        """Execute workflow with conditional logic"""
        workflow = execution.workflow_definition
        
        for i, step in enumerate(workflow.steps):
            execution.current_step_index = i
            
            # Check condition
            if step.condition:
                should_execute = self._evaluate_condition(step.condition, execution)
                if not should_execute:
                    continue
            
            # Execute step
            result = await self._execute_step(step, execution)
            execution.step_results[step.step_id] = result
            self._map_outputs(step.output_mapping, result, execution.context)
    
    async def _execute_hybrid(self, execution: WorkflowExecution):
        """Execute workflow with mix of sequential and parallel"""
        workflow = execution.workflow_definition
        executed_steps = set()
        
        for i, step in enumerate(workflow.steps):
            if step.step_id in executed_steps:
                continue
            
            execution.current_step_index = i
            
            # Check condition and dependencies
            if step.condition and not self._evaluate_condition(step.condition, execution):
                continue
            
            if not self._check_dependencies(step, execution):
                continue
            
            # Execute this step and any parallel steps
            parallel_steps = [step]
            for parallel_id in step.parallel_with:
                parallel_step = next((s for s in workflow.steps if s.step_id == parallel_id), None)
                if parallel_step:
                    parallel_steps.append(parallel_step)
            
            # Execute group
            tasks = [self._execute_step(s, execution) for s in parallel_steps]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results
            for s, result in zip(parallel_steps, results):
                executed_steps.add(s.step_id)
                if isinstance(result, Exception):
                    execution.errors.append({"step": s.step_id, "error": str(result)})
                else:
                    execution.step_results[s.step_id] = result
                    self._map_outputs(s.output_mapping, result, execution.context)
    
    async def _execute_step(self, step: WorkflowStep, 
                            execution: WorkflowExecution) -> Dict[str, Any]:
        """Execute a single workflow step"""
        # Get handler for this action type
        handler = self.step_handlers.get(step.action)
        
        # Prepare input
        input_data = self._prepare_input(step.input_mapping, execution.context)
        
        # Create task
        task = self.cooperative_swarm.create_task(
            description=f"Execute {step.action}",
            task_type=step.action,
            required_capabilities=[step.action],
            input_data=input_data
        )
        
        # Execute with retry logic
        retries = 0
        while retries <= step.max_retries:
            try:
                if handler:
                    result = await handler(step.agent, task, input_data, execution.context)
                else:
                    result = await self._default_step_handler(step.agent, task, input_data)
                
                task.status = TaskStatus.COMPLETED
                task.output_data = result
                
                return result
                
            except Exception as e:
                retries += 1
                if retries <= step.max_retries and step.retry_on_failure:
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    raise
    
    async def _default_step_handler(self, agent: str, task: Task, 
                                   input_data: Dict) -> Dict[str, Any]:
        """Default handler for steps without registered handler"""
        return {
            "agent": agent,
            "task_id": task.id,
            "input": input_data,
            "output": f"Executed {task.task_type} by {agent}",
            "timestamp": datetime.now().isoformat()
        }
    
    def _evaluate_condition(self, condition: str, execution: WorkflowExecution) -> bool:
        """Evaluate a condition expression"""
        # Simple evaluation - in production would use a proper expression parser
        context_vars = execution.context.shared_variables
        
        try:
            # Replace variable references
            evaluated = condition
            for var_name, var_value in context_vars.items():
                evaluated = evaluated.replace(f"input.{var_name}", str(var_value))
                evaluated = evaluated.replace(f"var.{var_name}", str(var_value))
            
            # Evaluate the expression
            return bool(eval(evaluated))
        except:
            return False
    
    def _check_dependencies(self, step: WorkflowStep, execution: WorkflowExecution) -> bool:
        """Check if step dependencies are satisfied"""
        for dep_id in step.depends_on:
            if dep_id not in execution.step_results:
                return False
        return True
    
    def _prepare_input(self, input_mapping: Dict[str, str], 
                      context: HandoffContext) -> Dict[str, Any]:
        """Prepare input data for a step"""
        prepared = {}
        
        for target_key, source_ref in input_mapping.items():
            # Parse source reference (e.g., "input.user_request", "step_1.output")
            if source_ref.startswith("input."):
                var_name = source_ref[6:]
                prepared[target_key] = context.shared_variables.get(var_name)
            elif source_ref.startswith("step_"):
                parts = source_ref.split(".")
                if len(parts) == 2:
                    step_id, output_key = parts
                    # In real implementation, would fetch from step results
                    prepared[target_key] = f"Result from {step_id}"
            else:
                prepared[target_key] = source_ref
        
        return prepared
    
    def _map_outputs(self, output_mapping: Dict[str, str], 
                     result: Dict, context: HandoffContext):
        """Map step outputs to context variables"""
        for target_var, source_ref in output_mapping.items():
            if source_ref.startswith("output."):
                key = source_ref[7:]
                context.shared_variables[target_var] = result.get(key)
            else:
                context.shared_variables[target_var] = source_ref
    
    def _group_parallel_steps(self, steps: List[WorkflowStep]) -> List[List[WorkflowStep]]:
        """Group steps that can be executed in parallel"""
        groups = []
        processed = set()
        
        for step in steps:
            if step.step_id in processed:
                continue
            
            # Find all parallel steps
            group = [step]
            processed.add(step.step_id)
            
            for parallel_id in step.parallel_with:
                parallel_step = next((s for s in steps if s.step_id == parallel_id), None)
                if parallel_step and parallel_step.step_id not in processed:
                    group.append(parallel_step)
                    processed.add(parallel_step.step_id)
            
            groups.append(group)
        
        return groups
    
    def get_execution_status(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get status of a workflow execution"""
        return self.active_executions.get(execution_id)
    
    def pause_execution(self, execution_id: str) -> bool:
        """Pause a running workflow execution"""
        execution = self.active_executions.get(execution_id)
        if execution:
            execution.status = WorkflowStatus.PAUSED
            return True
        return False
    
    def resume_execution(self, execution_id: str) -> bool:
        """Resume a paused workflow execution"""
        execution = self.active_executions.get(execution_id)
        if execution and execution.status == WorkflowStatus.PAUSED:
            execution.status = WorkflowStatus.RUNNING
            # Would need to resume execution here
            return True
        return False
    
    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a workflow execution"""
        execution = self.active_executions.get(execution_id)
        if execution:
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now()
            return True
        return False