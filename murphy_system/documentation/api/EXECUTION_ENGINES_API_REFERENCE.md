# Execution Engines API Reference

Complete API reference for all execution engines in the Murphy System Runtime.

## Table of Contents
1. [Task Executor](#task-executor)
2. [Workflow Orchestrator](#workflow-orchestrator)
3. [Decision Engine](#decision-engine)
4. [State Manager](#state-manager)
5. [Integration Framework](#integration-framework)
6. [Database Connectors](#database-connectors)
7. [Document Generation Engine](#document-generation-engine)

---

## Task Executor

### Overview
The Task Executor is responsible for executing individual tasks with retry logic, timeout handling, and error recovery.

### Classes

#### `Task`

Represents a single task to be executed.

**Constructor Parameters:**
```python
Task(
    task_id: Optional[str] = None,          # Unique task identifier (auto-generated if not provided)
    task_type: str = "generic",             # Type of task
    action: Optional[Callable] = None,      # Callable function to execute
    parameters: Optional[Dict] = None,      # Parameters to pass to action
    dependencies: Optional[List[str]] = None,  # List of task IDs this task depends on
    timeout: float = 300.0,                 # Timeout in seconds
    max_retries: int = 3,                   # Maximum number of retry attempts
    retry_delay: float = 1.0,               # Delay between retries in seconds
    metadata: Optional[Dict] = None         # Additional metadata
)
```

**Example:**
```python
task = Task(
    task_id="TASK-001",
    task_type="research",
    action=research_function,
    parameters={"topic": "authentication"},
    timeout=600.0,
    max_retries=5
)
```

#### `TaskExecutor`

Main executor for running tasks.

**Constructor Parameters:**
```python
TaskExecutor(
    max_workers: int = 4,                   # Maximum number of concurrent workers
    enable_retry: bool = True,              # Enable automatic retry logic
    enable_timeout: bool = True,            # Enable timeout handling
    circuit_breaker_threshold: int = 5     # Circuit breaker threshold
)
```

**Methods:**

##### `execute_task(task: Task) -> Dict`
Execute a single task and return result.

**Parameters:**
- `task` (Task): Task to execute

**Returns:**
```python
{
    "success": bool,           # Whether execution was successful
    "result": Any,             # Task execution result
    "error": Optional[str],    # Error message if failed
    "execution_time": float,   # Execution time in seconds
    "retries": int             # Number of retries attempted
}
```

**Example:**
```python
executor = TaskExecutor(max_workers=4)
result = executor.execute_task(task)
if result['success']:
    print(f"Task completed: {result['result']}")
else:
    print(f"Task failed: {result['error']}")
```

##### `execute_tasks(tasks: List[Task]) -> List[Dict]`
Execute multiple tasks concurrently.

**Parameters:**
- `tasks` (List[Task]): List of tasks to execute

**Returns:**
- `List[Dict]`: List of execution results (one per task)

**Example:**
```python
tasks = [task1, task2, task3]
results = executor.execute_tasks(tasks)
for result in results:
    print(f"Task {result['task_id']}: {result['success']}")
```

---

## Workflow Orchestrator

### Overview
The Workflow Orchestrator manages complex workflows with multiple steps, dependencies, parallel execution, and conditional branching.

### Classes

#### `Workflow`

Represents a complete workflow with multiple steps.

**Constructor Parameters:**
```python
Workflow(
    workflow_id: Optional[str] = None,      # Unique workflow identifier (auto-generated)
    name: str = "Unnamed Workflow",         # Workflow name
    description: str = "",                   # Workflow description
    steps: Optional[List[WorkflowStep]] = None,  # List of workflow steps
    variables: Optional[Dict] = None,       # Workflow variables
    timeout: float = 3600.0                 # Overall timeout in seconds
)
```

**Example:**
```python
workflow = Workflow(
    workflow_id="WF-001",
    name="Authentication System Development",
    description="Develop and deploy user authentication system",
    steps=[step1, step2, step3],
    variables={"environment": "staging"}
)
```

**Methods:**

##### `add_step(step: WorkflowStep) -> None`
Add a step to the workflow.

**Parameters:**
- `step` (WorkflowStep): Step to add

**Example:**
```python
workflow.add_step(step1)
workflow.add_step(step2)
```

#### `WorkflowStep`

Represents a single step in a workflow.

**Constructor Parameters:**
```python
WorkflowStep(
    step_id: Optional[str] = None,              # Unique step identifier (auto-generated)
    step_type: WorkflowStepType = WorkflowStepType.TASK,  # Step type
    action: Optional[Callable] = None,          # Callable function to execute
    parameters: Optional[Dict] = None,          # Parameters for action
    conditions: Optional[List[Dict]] = None,    # Conditions for execution
    dependencies: Optional[List[str]] = None,   # Dependencies on other steps
    parallel_steps: Optional[List[WorkflowStep]] = None,  # Parallel steps
    loop_config: Optional[Dict] = None          # Loop configuration
)
```

**Example:**
```python
step = WorkflowStep(
    step_id="STEP-001",
    step_type=WorkflowStepType.TASK,
    action=implement_auth,
    parameters={"framework": "FastAPI"},
    conditions=[{"field": "environment", "operator": "==", "value": "staging"}]
)
```

#### `WorkflowOrchestrator`

Main orchestrator for executing workflows.

**Constructor Parameters:**
```python
WorkflowOrchestrator(
    task_executor: TaskExecutor,        # Task executor instance
    max_parallel_steps: int = 3,       # Maximum parallel steps
    enable_circuit_breaker: bool = True # Enable circuit breaker
)
```

**Methods:**

##### `execute_workflow(workflow: Workflow) -> Dict`
Execute a complete workflow.

**Parameters:**
- `workflow` (Workflow): Workflow to execute

**Returns:**
```python
{
    "success": bool,                    # Whether workflow was successful
    "workflow_id": str,                 # Workflow identifier
    "status": str,                      # Final status
    "results": Dict[str, Any],          # Results from each step
    "errors": List[Dict],               # Errors encountered
    "execution_time": float,            # Total execution time
    "summary": {
        "total_steps": int,             # Total number of steps
        "successful": int,              # Successful steps
        "failed": int,                  # Failed steps
        "skipped": int                  # Skipped steps
    }
}
```

**Example:**
```python
orchestrator = WorkflowOrchestrator(task_executor)
result = orchestrator.execute_workflow(workflow)
print(f"Workflow status: {result['status']}")
print(f"Successful steps: {result['summary']['successful']}")
```

---

## Decision Engine

### Overview
The Decision Engine makes autonomous decisions based on rules, conditions, and confidence scoring.

### Classes

#### `Rule`

Represents a decision rule.

**Constructor Parameters:**
```python
Rule(
    rule_id: Optional[str] = None,          # Unique rule identifier (auto-generated)
    name: str = "",                         # Rule name
    description: str = "",                   # Rule description
    conditions: Optional[List[Dict]] = None, # List of conditions
    actions: Optional[List[Dict]] = None,   # List of actions
    priority: int = 0,                      # Rule priority (higher = more important)
    confidence: float = 1.0                 # Rule confidence (0.0 to 1.0)
)
```

**Example:**
```python
rule = Rule(
    rule_id="RULE-001",
    name="High Priority Rule",
    description="Assign critical priority to complex tasks",
    conditions=[
        {"field": "complexity", "operator": ">", "value": 8}
    ],
    actions=[
        {"type": "set_priority", "value": "CRITICAL"}
    ],
    priority=1,
    confidence=0.95
)
```

#### `Decision`

Represents a decision result.

**Attributes:**
```python
decision.decision_id      # Unique decision identifier
decision.rule_id          # Rule that made the decision
decision.action           # Action taken
decision.confidence       # Confidence score (0.0 to 1.0)
decision.context          # Context used for decision
decision.timestamp        # Decision timestamp
```

#### `DecisionEngine`

Main decision engine.

**Constructor Parameters:**
```python
DecisionEngine(
    enable_learning: bool = True,     # Enable learning from decisions
    default_confidence: float = 0.5   # Default confidence for decisions
)
```

**Methods:**

##### `add_rule(rule: Rule) -> None`
Add a rule to the decision engine.

**Parameters:**
- `rule` (Rule): Rule to add

**Example:**
```python
decision_engine = DecisionEngine()
decision_engine.add_rule(rule)
```

##### `make_decision(context: Dict) -> Decision`
Make a decision based on context.

**Parameters:**
- `context` (Dict): Context for decision making

**Returns:**
- `Decision`: Decision object with action and confidence

**Example:**
```python
decision = decision_engine.make_decision({
    "complexity": 9,
    "type": "development"
})
print(f"Action: {decision.action}")
print(f"Confidence: {decision.confidence}")
```

##### `get_decision_history(limit: int = 100) -> List[Decision]`
Get history of decisions made.

**Parameters:**
- `limit` (int): Maximum number of decisions to return

**Returns:**
- `List[Decision]`: List of past decisions

**Example:**
```python
history = decision_engine.get_decision_history(limit=10)
for decision in history:
    print(f"{decision.action} (confidence: {decision.confidence})")
```

---

## State Manager

### Overview
The State Manager manages system state, transitions, and persistence.

### Classes

#### `SystemState`

Represents a system state.

**Constructor Parameters:**
```python
SystemState(
    state_id: Optional[str] = None,              # Unique state identifier (auto-generated)
    state_type: StateType = StateType.SYSTEM,   # State type
    state_name: str = "default",                # State name
    variables: Optional[Dict] = None,           # State variables
    version: int = 1                            # State version
)
```

**Example:**
```python
state = SystemState(
    state_id="STATE-001",
    state_type=StateType.SYSTEM,
    state_name="Executing",
    variables={
        "status": "running",
        "tasks_completed": 5,
        "tasks_remaining": 3
    }
)
```

**Methods:**

##### `get_variable(name: str, default: Any = None) -> Any`
Get a variable value from the state.

**Parameters:**
- `name` (str): Variable name
- `default` (Any): Default value if not found

**Returns:**
- `Any`: Variable value

**Example:**
```python
status = state.get_variable("status", "unknown")
```

##### `set_variable(name: str, value: Any) -> None`
Set a variable value in the state.

**Parameters:**
- `name` (str): Variable name
- `value` (Any): Variable value

**Example:**
```python
state.set_variable("status", "completed")
```

#### `StateManager`

Main state manager.

**Constructor Parameters:**
```python
StateManager(
    enable_persistence: bool = True,   # Enable state persistence
    max_history: int = 1000            # Maximum history size
)
```

**Methods:**

##### `create_state(state: SystemState) -> str`
Create a new state.

**Parameters:**
- `state` (SystemState): State to create

**Returns:**
- `str`: State ID

**Example:**
```python
state_manager = StateManager()
state_id = state_manager.create_state(state)
```

##### `get_state(state_id: str) -> Optional[SystemState]`
Get a state by ID.

**Parameters:**
- `state_id` (str): State identifier

**Returns:**
- `Optional[SystemState]`: State object or None

**Example:**
```python
state = state_manager.get_state("STATE-001")
if state:
    print(f"State: {state.state_name}")
```

##### `update_state(state_id: str, variables: Dict) -> bool`
Update state variables.

**Parameters:**
- `state_id` (str): State identifier
- `variables` (Dict): Variables to update

**Returns:**
- `bool`: True if successful

**Example:**
```python
state_manager.update_state("STATE-001", {
    "status": "completed",
    "tasks_completed": 8
})
```

##### `transition_state(state_id: str, to_state_name: str, metadata: Dict = None) -> bool`
Transition to a new state.

**Parameters:**
- `state_id` (str): Current state identifier
- `to_state_name` (str): New state name
- `metadata` (Dict, optional): Transition metadata

**Returns:**
- `bool`: True if successful

**Example:**
```python
state_manager.transition_state(
    "STATE-001",
    "Completed",
    metadata={"reason": "All tasks finished"}
)
```

---

## Integration Framework

### Overview
The Integration Framework manages external system integrations with connection pooling, circuit breakers, and rate limiting.

### Classes

#### `Integration`

Represents an external system integration.

**Constructor Parameters:**
```python
Integration(
    integration_id: Optional[str] = None,          # Unique integration identifier (auto-generated)
    name: str = "",                                # Integration name
    system_type: IntegrationType = IntegrationType.CUSTOM,  # System type
    connection_params: Optional[Dict] = None,      # Connection parameters
    authentication: Optional[Dict] = None,         # Authentication configuration
    rate_limits: Optional[Dict] = None,            # Rate limits
    endpoints: Optional[Dict] = None,              # API endpoints
    metadata: Optional[Dict] = None                # Additional metadata
)
```

**Example:**
```python
integration = Integration(
    integration_id="INT-001",
    name="CRM Integration",
    system_type=IntegrationType.API,
    connection_params={
        "host": "api.crm.com",
        "port": 443,
        "secure": True
    },
    authentication={
        "type": "oauth2",
        "token": "your-token"
    },
    rate_limits={
        "max_requests": 100,
        "window": 60
    },
    endpoints={
        "contacts": "/api/v1/contacts",
        "deals": "/api/v1/deals"
    }
)
```

#### `IntegrationFramework`

Main integration framework.

**Constructor Parameters:**
```python
IntegrationFramework(
    enable_circuit_breaker: bool = True,   # Enable circuit breaker
    enable_rate_limiting: bool = True,     # Enable rate limiting
    default_timeout: float = 30.0          # Default timeout in seconds
)
```

**Methods:**

##### `register_integration(integration: Integration) -> bool`
Register an integration.

**Parameters:**
- `integration` (Integration): Integration to register

**Returns:**
- `bool`: True if successful

**Example:**
```python
framework = IntegrationFramework()
framework.register_integration(integration)
```

##### `get_integration(integration_id: str) -> Optional[Integration]`
Get an integration by ID.

**Parameters:**
- `integration_id` (str): Integration identifier

**Returns:**
- `Optional[Integration]`: Integration object or None

**Example:**
```python
integration = framework.get_integration("INT-001")
```

##### `get_all_integrations() -> List[Integration]`
Get all registered integrations.

**Returns:**
- `List[Integration]`: List of all integrations

**Example:**
```python
integrations = framework.get_all_integrations()
for integration in integrations:
    print(f"{integration.name}: {integration.system_type}")
```

---

## Database Connectors

### Overview
Database connectors for SQL and NoSQL databases.

The SQL connector supports a **live/stub mode** toggle via the `MURPHY_DB_MODE`
environment variable:

| Value | Behaviour |
|-------|-----------|
| `stub` (default) | Returns deterministic in-memory fixture data. No database required. Suitable for development and testing. |
| `live` | Executes queries against a real database via SQLAlchemy. Requires a reachable database and `DATABASE_URL`-compatible connection string. |

**Example:**
```bash
# Run with a real PostgreSQL database (connection_string passed to constructor)
MURPHY_DB_MODE=live python app.py

# In Python, pass the connection string directly to the constructor:
connector = SQLDatabaseConnector(
    connection_string="postgresql://user:pass@localhost/mydb",
    database_type=DatabaseType.POSTGRESQL
)
connector.connect()  # establishes live SQLAlchemy engine

# Run without any database (default, suitable for development)
MURPHY_DB_MODE=stub python app.py
```

### Classes

#### `SQLDatabaseConnector`

SQL database connector.

**Constructor Parameters:**
```python
SQLDatabaseConnector(
    connection_string: str,                         # Database connection string
    database_type: DatabaseType = DatabaseType.MYSQL,  # Database type enum (default: MYSQL)
    **kwargs                                        # Additional connection parameters
)
```

**Example:**
```python
connector = SQLDatabaseConnector(
    connection_string="postgresql://user:password@localhost:5432/mydb",
    database_type=DatabaseType.POSTGRESQL
)
```

**Methods:**

##### `execute_query(query: str, parameters: Optional[Dict] = None) -> IntegrationResult`
Execute a SQL query.

**Parameters:**
- `query` (str): SQL query
- `parameters` (Dict, optional): Query parameters

**Returns:**
- `IntegrationResult`: Result object with `.success` (bool), `.data` (List[Dict] of rows on success), and `.error` (str on failure)

**Example:**
```python
result = connector.execute_query(
    "SELECT * FROM users WHERE status = :status",
    parameters={"status": "active"}
)
if result.success:
    rows = result.data
else:
    print(result.error)
```

##### `execute_transaction(operations: List[Dict]) -> IntegrationResult`
Execute a series of operations as a single transaction.

**Parameters:**
- `operations` (List[Dict]): List of operation dicts, each containing `query` (str) and optional `parameters` (Dict)

**Returns:**
- `IntegrationResult`: Result object with `.success` (bool), `.data` (List of per-operation results on success), and `.error` (str on failure)

**Example:**
```python
result = connector.execute_transaction([
    {"query": "INSERT INTO orders (user_id, total) VALUES (:user_id, :total)",
     "parameters": {"user_id": 42, "total": 99.99}},
    {"query": "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = :item_id",
     "parameters": {"item_id": 7}},
])
if result.success:
    print("Transaction committed")
else:
    print(result.error)
```

##### `execute_stored_procedure(name: str, parameters: Optional[Dict] = None) -> IntegrationResult`
Execute a stored procedure.

**Parameters:**
- `name` (str): Name of the stored procedure
- `parameters` (Dict, optional): Parameters to pass to the stored procedure

**Returns:**
- `IntegrationResult`: Result object with `.success` (bool), `.data` (Dict containing procedure result on success), and `.error` (str on failure)

**Example:**
```python
result = connector.execute_stored_procedure(
    "sp_get_user_report",
    parameters={"user_id": 42, "start_date": "2024-01-01"}
)
if result.success:
    report = result.data
else:
    print(result.error)
```

---

## Document Generation Engine

### Overview
The Document Generation Engine generates documents from templates (PDF, Word, HTML).

### Classes

#### `DocumentTemplate`

Represents a document template.

**Constructor Parameters:**
```python
DocumentTemplate(
    template_id: Optional[str] = None,  # Unique template identifier (auto-generated)
    template_type: str = "",            # Template type (report, letter, etc.)
    content: str = "",                  # Template content (with placeholders)
    metadata: Optional[Dict] = None     # Additional metadata
)
```

**Example:**
```python
template = DocumentTemplate(
    template_id="TPL-001",
    template_type="project_report",
    content="""
# Project Report

## Summary
{{summary}}

## Details
{{details}}
"""
)
```

#### `Document`

Represents a generated document.

**Attributes:**
```python
document.document_id      # Unique document identifier
document.template_id      # Template ID used
document.content          # Generated content
document.document_type    # Document type (PDF, Word, HTML, etc.)
document.metadata         # Document metadata
document.timestamp        # Generation timestamp
```

#### `DocumentGenerationEngine`

Main document generation engine.

**Constructor Parameters:**
```python
DocumentGenerationEngine(
    output_format: str = "markdown",  # Default output format
    enable_caching: bool = True       # Enable template caching
)
```

**Methods:**

##### `generate_document(template_type: str, data: Dict, template: DocumentTemplate = None) -> Document`
Generate a document from template and data.

**Parameters:**
- `template_type` (str): Type of document to generate
- `data` (Dict): Data to populate template
- `template` (DocumentTemplate, optional): Custom template

**Returns:**
- `Document`: Generated document

**Example:**
```python
engine = DocumentGenerationEngine()
document = engine.generate_document(
    "project_report",
    data={
        "summary": "Project completed successfully",
        "details": "All tasks finished on time"
    }
)
print(document.content)
```

---

## Usage Examples

### Complete Workflow Example

```python
from src.execution_engine.task_executor import TaskExecutor, Task
from src.execution_engine.workflow_orchestrator import WorkflowOrchestrator, Workflow, WorkflowStep

# Create task executor
task_executor = TaskExecutor(max_workers=4)

# Create workflow
workflow = Workflow(
    workflow_id="WF-001",
    name="Authentication System",
    description="Develop user authentication system"
)

# Add steps
step1 = WorkflowStep(
    step_id="STEP-001",
    action=research_function,
    parameters={"topic": "authentication"}
)
workflow.add_step(step1)

# Execute workflow
orchestrator = WorkflowOrchestrator(task_executor)
result = orchestrator.execute_workflow(workflow)
```

### Decision Making Example

```python
from src.execution_engine.decision_engine import DecisionEngine, Rule

# Create decision engine
decision_engine = DecisionEngine()

# Add rules
rule = Rule(
    name="High Priority Rule",
    conditions=[{"field": "complexity", "operator": ">", "value": 8}],
    actions=[{"type": "set_priority", "value": "CRITICAL"}],
    confidence=0.95
)
decision_engine.add_rule(rule)

# Make decision
decision = decision_engine.make_decision({"complexity": 9})
print(f"Action: {decision.action}, Confidence: {decision.confidence}")
```

### State Management Example

```python
from src.execution_engine.state_manager import StateManager, SystemState, StateType

# Create state manager
state_manager = StateManager()

# Create state
state = SystemState(
    state_type=StateType.SYSTEM,
    state_name="Executing",
    variables={"status": "running", "tasks": 5}
)

# Add state
state_id = state_manager.create_state(state)

# Update state
state_manager.update_state(state_id, {"tasks": 8})

# Transition state
state_manager.transition_state(state_id, "Completed")
```

---

## Error Handling

All execution engines provide comprehensive error handling:

### Task Executor
```python
result = task_executor.execute_task(task)
if not result['success']:
    print(f"Error: {result['error']}")
    print(f"Retries attempted: {result['retries']}")
```

### Workflow Orchestrator
```python
result = orchestrator.execute_workflow(workflow)
if not result['success']:
    for error in result['errors']:
        print(f"Step {error['step_id']}: {error['message']}")
```

### Decision Engine
```python
decision = decision_engine.make_decision(context)
if decision.confidence < 0.5:
    print("Low confidence decision - review recommended")
```

---

## Performance Considerations

### Task Executor
- Use appropriate `max_workers` based on available CPU cores
- Set realistic `timeout` values for long-running tasks
- Configure `max_retries` based on task criticality

### Workflow Orchestrator
- Limit `max_parallel_steps` for resource-intensive workflows
- Use `timeout` to prevent runaway workflows
- Monitor circuit breaker thresholds

### State Manager
- Use `enable_persistence=False` for transient states
- Set appropriate `max_history` to limit memory usage
- Use efficient variable names and types

---

## License

BSL 1.1 (converts to Apache 2.0 after four years)

Copyright © 2026 Corey Post InonI LLC

Contact: corey.gfc@gmail.com