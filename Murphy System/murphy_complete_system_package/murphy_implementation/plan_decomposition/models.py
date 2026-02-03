"""
Data Models for Plan Decomposition

Defines the structure of plans, tasks, dependencies, and validation criteria.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyType(str, Enum):
    """Types of task dependencies"""
    FINISH_TO_START = "finish_to_start"  # Task B starts after Task A finishes
    START_TO_START = "start_to_start"    # Task B starts when Task A starts
    FINISH_TO_FINISH = "finish_to_finish"  # Task B finishes when Task A finishes
    START_TO_FINISH = "start_to_finish"  # Task B finishes when Task A starts


class Dependency(BaseModel):
    """Task dependency"""
    
    dependency_id: str = Field(..., description="Unique dependency ID")
    from_task_id: str = Field(..., description="Task that must be completed first")
    to_task_id: str = Field(..., description="Task that depends on the first task")
    dependency_type: DependencyType = Field(
        default=DependencyType.FINISH_TO_START,
        description="Type of dependency relationship"
    )
    lag_days: int = Field(
        default=0,
        description="Number of days to wait after dependency is satisfied"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "dependency_id": "dep_001",
                "from_task_id": "task_design_ui",
                "to_task_id": "task_implement_ui",
                "dependency_type": "finish_to_start",
                "lag_days": 0
            }
        }


class ValidationCriterion(BaseModel):
    """Validation criterion for task completion"""
    
    criterion_id: str = Field(..., description="Unique criterion ID")
    description: str = Field(..., description="What needs to be validated")
    validation_method: str = Field(
        ...,
        description="How to validate (automated test, human review, metric check, etc.)"
    )
    acceptance_threshold: Optional[float] = Field(
        None,
        description="Numeric threshold for acceptance (if applicable)"
    )
    is_mandatory: bool = Field(
        default=True,
        description="Whether this criterion must be met"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "criterion_id": "crit_001",
                "description": "All unit tests pass",
                "validation_method": "automated_test",
                "acceptance_threshold": 1.0,
                "is_mandatory": True
            }
        }


class HumanCheckpoint(BaseModel):
    """Human review checkpoint"""
    
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    checkpoint_type: str = Field(
        ...,
        description="Type of checkpoint (approval, review, validation, etc.)"
    )
    description: str = Field(..., description="What needs to be reviewed")
    required_role: Optional[str] = Field(
        None,
        description="Role required to approve (e.g., 'manager', 'technical_lead')"
    )
    blocking: bool = Field(
        default=True,
        description="Whether execution blocks until checkpoint is cleared"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "checkpoint_id": "chk_001",
                "checkpoint_type": "approval",
                "description": "Review and approve UI design mockups",
                "required_role": "product_manager",
                "blocking": True
            }
        }


class Task(BaseModel):
    """Individual task in a plan"""
    
    task_id: str = Field(..., description="Unique task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Task priority"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current task status"
    )
    estimated_hours: Optional[float] = Field(
        None,
        description="Estimated hours to complete"
    )
    estimated_cost: Optional[float] = Field(
        None,
        description="Estimated cost in USD"
    )
    assigned_to: Optional[str] = Field(
        None,
        description="Person or role assigned to this task"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of task IDs this task depends on"
    )
    validation_criteria: List[ValidationCriterion] = Field(
        default_factory=list,
        description="Criteria for validating task completion"
    )
    human_checkpoints: List[HumanCheckpoint] = Field(
        default_factory=list,
        description="Human review checkpoints for this task"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made for this task"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Identified risks for this task"
    )
    deliverables: List[str] = Field(
        default_factory=list,
        description="Expected deliverables from this task"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional task metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Task creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Task last update timestamp"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_001",
                "title": "Design user interface mockups",
                "description": "Create high-fidelity mockups for the main application screens including dashboard, settings, and user profile pages.",
                "priority": "high",
                "status": "pending",
                "estimated_hours": 16.0,
                "estimated_cost": 2400.0,
                "assigned_to": "ui_designer",
                "dependencies": [],
                "validation_criteria": [
                    {
                        "criterion_id": "crit_001",
                        "description": "All screens designed",
                        "validation_method": "human_review",
                        "is_mandatory": True
                    }
                ],
                "human_checkpoints": [
                    {
                        "checkpoint_id": "chk_001",
                        "checkpoint_type": "approval",
                        "description": "Product manager approval",
                        "required_role": "product_manager",
                        "blocking": True
                    }
                ],
                "assumptions": [
                    "Design system already exists",
                    "Brand guidelines are available"
                ],
                "risks": [
                    "Design revisions may extend timeline",
                    "Stakeholder feedback may require major changes"
                ],
                "deliverables": [
                    "Figma mockups for all screens",
                    "Design specifications document"
                ]
            }
        }


class Plan(BaseModel):
    """Complete execution plan"""
    
    plan_id: str = Field(..., description="Unique plan ID")
    title: str = Field(..., description="Plan title")
    description: str = Field(..., description="Plan description")
    goal: str = Field(..., description="Overall goal of the plan")
    domain: str = Field(..., description="Domain category")
    timeline: str = Field(..., description="Expected timeline")
    budget: Optional[float] = Field(None, description="Total budget in USD")
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    dependencies: List[Dependency] = Field(
        default_factory=list,
        description="Task dependencies"
    )
    success_criteria: List[str] = Field(
        default_factory=list,
        description="Overall success criteria for the plan"
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Plan constraints"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Plan-level assumptions"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Plan-level risks"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional plan metadata"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Plan creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Plan last update timestamp"
    )
    created_by: Optional[str] = Field(
        None,
        description="User who created the plan"
    )
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_task_dependencies(self, task_id: str) -> List[Dependency]:
        """Get all dependencies for a task"""
        return [dep for dep in self.dependencies if dep.to_task_id == task_id]
    
    def get_dependent_tasks(self, task_id: str) -> List[str]:
        """Get all tasks that depend on this task"""
        return [dep.to_task_id for dep in self.dependencies if dep.from_task_id == task_id]
    
    def get_ready_tasks(self) -> List[Task]:
        """Get all tasks that are ready to execute (dependencies satisfied)"""
        ready_tasks = []
        
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check if all dependencies are satisfied
            dependencies = self.get_task_dependencies(task.task_id)
            all_satisfied = True
            
            for dep in dependencies:
                dep_task = self.get_task(dep.from_task_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_satisfied = False
                    break
            
            if all_satisfied:
                ready_tasks.append(task)
        
        return ready_tasks
    
    def get_critical_path(self) -> List[str]:
        """Get critical path (longest path through dependencies)"""
        # TODO: Implement critical path calculation
        # This is a simplified version - full implementation would use
        # proper critical path method (CPM) algorithm
        return []
    
    def get_completion_percentage(self) -> float:
        """Get plan completion percentage"""
        if not self.tasks:
            return 0.0
        
        completed = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
        return (completed / len(self.tasks)) * 100.0
    
    class Config:
        schema_extra = {
            "example": {
                "plan_id": "plan_001",
                "title": "Q1 2025 Product Launch",
                "description": "Complete plan for launching new SaaS product in Q1 2025",
                "goal": "Launch beta product with 100 users",
                "domain": "software_development",
                "timeline": "6 months",
                "budget": 150000.0,
                "tasks": [],
                "dependencies": [],
                "success_criteria": [
                    "Beta product launched",
                    "100 active users acquired",
                    "User satisfaction > 4.0/5.0"
                ],
                "constraints": [
                    "Budget: $150,000",
                    "Timeline: 6 months",
                    "Team size: 8 people"
                ],
                "assumptions": [
                    "Market demand exists",
                    "Team has necessary skills",
                    "Infrastructure is available"
                ],
                "risks": [
                    "Market competition may increase",
                    "Technical challenges may delay launch",
                    "User acquisition may be slower than expected"
                ]
            }
        }