# `src/execution_engine` — Execution Engine

Core execution capabilities for the Murphy System runtime. Provides decision logic,
state management, task execution, and workflow orchestration.

## Public API

```python
from execution_engine import (
    DecisionEngine, Decision, DecisionType, Rule, create_rule, make_decision,
    StateManager, StateType, SystemState, StateTransition,
    TaskExecutor, TaskScheduler, Task, TaskState, create_task, execute_task,
    WorkflowOrchestrator, Workflow, WorkflowState,
)
```

## Core Usage

### Task Execution

```python
from execution_engine import TaskExecutor, create_task

executor = TaskExecutor()
task = create_task(
    name="send_report",
    handler=send_report_handler,
    priority=1,
    timeout_seconds=30,
)
result = await executor.execute(task)
```

### State Management

```python
from execution_engine import StateManager, create_system_state

manager = StateManager()
state = create_system_state(component="email_delivery", status="active")
manager.transition(state, new_status="idle")
current = manager.get_current_state("email_delivery")
```

### Decision Engine

```python
from execution_engine import DecisionEngine, create_rule

engine = DecisionEngine()
rule = create_rule(
    condition=lambda ctx: ctx["confidence"] < 0.7,
    action=DecisionType.REQUIRE_HITL,
)
engine.add_rule(rule)
decision = engine.evaluate(context)
```

## Tests

`tests/test_execution_engine*.py`, `tests/test_task_executor*.py`
