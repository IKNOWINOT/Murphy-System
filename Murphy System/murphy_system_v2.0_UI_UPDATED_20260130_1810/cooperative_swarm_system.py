"""
Cooperative Swarm Execution System
Implements agent-to-agent handoffs, task delegation, and sequential workflows
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid
from datetime import datetime


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_HANDOFF = "waiting_for_handoff"


class HandoffType(Enum):
    DELEGATE = "delegate"  # Parent delegates task to child
    ESCALATE = "escalate"  # Child escalates to parent
    COLLABORATE = "collaborate"  # Peer-to-peer collaboration
    RELAY = "relay"  # Pass to next agent in sequence


@dataclass
class Task:
    """A task that can be executed by an agent"""
    id: str
    description: str
    task_type: str
    required_capabilities: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    parent_task_id: Optional[str] = None
    child_task_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class AgentHandoff:
    """Represents a handoff between agents"""
    id: str
    from_agent: str
    to_agent: str
    task_id: str
    handoff_type: HandoffType
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    result: Optional[Dict[str, Any]] = None


@dataclass
class AgentMessage:
    """Message between agents"""
    id: str
    from_agent: str
    to_agent: str
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    read: bool = False


class CooperativeSwarmSystem:
    """Main system for cooperative swarm execution"""
    
    def __init__(self, llm_integration=None):
        self.tasks: Dict[str, Task] = {}
        self.handoffs: List[AgentHandoff] = []
        self.messages: List[AgentMessage] = []
        self.active_workflows: Dict[str, Dict] = {}
        self.llm_integration = llm_integration
        
    def create_task(self, description: str, task_type: str, 
                    required_capabilities: List[str],
                    input_data: Dict[str, Any] = None,
                    parent_task_id: str = None) -> Task:
        """Create a new task"""
        task = Task(
            id=str(uuid.uuid4()),
            description=description,
            task_type=task_type,
            required_capabilities=required_capabilities,
            input_data=input_data or {},
            parent_task_id=parent_task_id
        )
        self.tasks[task.id] = task
        
        if parent_task_id and parent_task_id in self.tasks:
            self.tasks[parent_task_id].child_task_ids.append(task.id)
            
        return task
    
    def delegate_task(self, task_id: str, from_agent: str, to_agent: str,
                     context: Dict[str, Any] = None) -> AgentHandoff:
        """Delegate a task from one agent to another"""
        handoff = AgentHandoff(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            handoff_type=HandoffType.DELEGATE,
            context=context or {}
        )
        
        self.handoffs.append(handoff)
        
        if task_id in self.tasks:
            self.tasks[task_id].assigned_agent = to_agent
            self.tasks[task_id].status = TaskStatus.ASSIGNED
            
        return handoff
    
    def escalate_task(self, task_id: str, from_agent: str, to_agent: str,
                     context: Dict[str, Any] = None) -> AgentHandoff:
        """Escalate a task to a higher-level agent"""
        handoff = AgentHandoff(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            handoff_type=HandoffType.ESCALATE,
            context=context or {}
        )
        
        self.handoffs.append(handoff)
        
        if task_id in self.tasks:
            self.tasks[task_id].assigned_agent = to_agent
            self.tasks[task_id].status = TaskStatus.WAITING_FOR_HANDOFF
            
        return handoff
    
    def send_message(self, from_agent: str, to_agent: str, 
                    message_type: str, content: Dict[str, Any]) -> AgentMessage:
        """Send a message from one agent to another"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
        
        self.messages.append(message)
        return message
    
    def get_agent_messages(self, agent_id: str, unread_only: bool = False) -> List[AgentMessage]:
        """Get messages for an agent"""
        messages = [m for m in self.messages if m.to_agent == agent_id]
        if unread_only:
            messages = [m for m in messages if not m.read]
        return messages
    
    def mark_messages_read(self, agent_id: str):
        """Mark all messages for an agent as read"""
        for message in self.messages:
            if message.to_agent == agent_id:
                message.read = True
    
    async def execute_cooperative_workflow(self, workflow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a cooperative workflow with multiple agents
        
        Workflow definition:
        {
            "workflow_id": "unique_id",
            "description": "Workflow description",
            "steps": [
                {
                    "step_id": "step_1",
                    "agent": "agent_name",
                    "action": "action_type",
                    "input": {...},
                    "handoff_to": "agent_name",
                    "condition": "condition_expression"
                }
            ]
        }
        """
        workflow_id = workflow_definition.get("workflow_id", str(uuid.uuid4()))
        self.active_workflows[workflow_id] = {
            "definition": workflow_definition,
            "status": "in_progress",
            "current_step": 0,
            "results": {},
            "started_at": datetime.now()
        }
        
        try:
            steps = workflow_definition.get("steps", [])
            results = {}
            
            for i, step in enumerate(steps):
                step_id = step.get("step_id", f"step_{i}")
                agent = step.get("agent")
                action = step.get("action")
                input_data = step.get("input", {})
                
                # Execute step
                step_result = await self._execute_agent_step(agent, action, input_data, results)
                results[step_id] = step_result
                
                # Check if handoff is needed
                handoff_to = step.get("handoff_to")
                if handoff_to and i < len(steps) - 1:
                    # Perform handoff
                    handoff_context = {
                        "previous_result": step_result,
                        "workflow_id": workflow_id
                    }
                    self.delegate_task(step_id, agent, handoff_to, handoff_context)
                
                # Check condition
                condition = step.get("condition")
                if condition and not self._evaluate_condition(condition, step_result):
                    # Skip remaining steps
                    break
            
            self.active_workflows[workflow_id]["status"] = "completed"
            self.active_workflows[workflow_id]["results"] = results
            self.active_workflows[workflow_id]["completed_at"] = datetime.now()
            
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "results": results
            }
            
        except Exception as e:
            self.active_workflows[workflow_id]["status"] = "failed"
            self.active_workflows[workflow_id]["error"] = str(e)
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_agent_step(self, agent: str, action: str, 
                                  input_data: Dict, previous_results: Dict) -> Dict[str, Any]:
        """Execute a single agent step"""
        # This would call the actual agent implementation
        # For now, simulate execution
        return {
            "agent": agent,
            "action": action,
            "input": input_data,
            "output": f"Executed {action} by {agent}",
            "timestamp": datetime.now().isoformat()
        }
    
    def _evaluate_condition(self, condition: str, result: Dict) -> bool:
        """Evaluate a condition based on result"""
        # Simple evaluation - would be more sophisticated
        if condition == "success":
            return "error" not in result
        elif condition == "has_output":
            return "output" in result and result["output"]
        return True
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of a workflow"""
        return self.active_workflows.get(workflow_id, {})
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        return self.tasks.get(task_id)
    
    def get_tasks_for_agent(self, agent_id: str) -> List[Task]:
        """Get all tasks assigned to an agent"""
        return [task for task in self.tasks.values() 
                if task.assigned_agent == agent_id]
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          output_data: Dict = None, error_message: str = None):
        """Update task status"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if output_data:
                self.tasks[task_id].output_data = output_data
            if error_message:
                self.tasks[task_id].error_message = error_message
            if status == TaskStatus.COMPLETED:
                self.tasks[task_id].completed_at = datetime.now()