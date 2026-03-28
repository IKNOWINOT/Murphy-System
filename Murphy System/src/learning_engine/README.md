# `src/learning_engine` — Learning Engine

Comprehensive learning and adaptation subsystem for Murphy. Tracks performance,
recognizes patterns, collects feedback, and drives adaptive decision-making —
without autonomously executing actions.

## Public API

```python
from learning_engine import (
    LearningEngine, PatternRecognizer, PerformanceTracker, FeedbackCollector,
    LearnedPattern, LearningInsight,
    HumanFeedbackSystem, OperationalFeedbackSystem,
    Feedback, FeedbackEntry, FeedbackAnalysis,
)
```

## Core Usage

```python
from learning_engine import LearningEngine

engine = LearningEngine()

# Record an outcome
engine.feedback_collector.record(
    task_id="task-123",
    outcome="success",
    duration_ms=412,
    confidence=0.87,
)

# Extract patterns
patterns: List[LearnedPattern] = engine.pattern_recognizer.extract()

# Get insights (recommendations only — never auto-executed)
insights: List[LearningInsight] = engine.get_insights()
```

## Key Classes

| Class | Module | Description |
|-------|--------|-------------|
| `LearningEngine` | `learning_engine.py` | Top-level coordinator |
| `PatternRecognizer` | `learning_engine.py` | Statistical pattern detection |
| `PerformanceTracker` | `learning_engine.py` | Rolling performance metrics |
| `FeedbackCollector` | `learning_engine.py` | Collects task outcomes |
| `HumanFeedbackSystem` | `feedback_system.py` | Human-provided feedback UI |
| `OperationalFeedbackSystem` | `feedback_system.py` | Automated ops feedback |
| `AdaptiveDecisionEngine` | `adaptive_decision_engine.py` | Decision recommendations |
| `ShadowAgent` | `shadow_agent.py` | Runs shadow experiments offline |

## Connector (Closed-Loop Wiring)

`src/learning_engine_connector.py` subscribes to EventBackbone events
(`TASK_COMPLETED`, `TASK_FAILED`, `GATE_EVALUATED`, `AUTOMATION_EXECUTED`) and
chains `FeedbackIntegrator → PatternRecognizer → PerformancePredictor → gate threshold evolution`.

## Tests

`tests/test_learning_engine*.py`, `tests/test_learning_engine_connector.py` (43 tests).
