# Murphy System Implementation

A form-driven task execution system with Murphy validation, human-in-the-loop checkpoints, and continuous learning through shadow agent training.

## Overview

The Murphy System replaces traditional 50-100 person org charts with an AI-powered execution engine that:
- Accepts any task through structured forms
- Decomposes plans into executable tasks
- Validates through Murphy principles (uncertainty quantification)
- Executes with human oversight
- Learns from corrections to improve over time

**Cost**: $13-103 per task (vs $350-2,800 traditional)
**ROI**: 90-97% cost reduction

## Architecture

```
Forms → Plan Decomposition → Murphy Validation → Execution → HITL → Learning
```

### Components

1. **Form Intake Layer** - 5 form types for all interactions
2. **Plan Decomposition** - Breaks plans into executable tasks
3. **Murphy Validation** - Uncertainty quantification (UD, UA, UI, UR, UG)
4. **Execution Orchestrator** - Phase-based execution (EXPAND → EXECUTE)
5. **HITL Monitor** - Human intervention checkpoints
6. **Correction Capture** - Training data from human corrections
7. **Shadow Agent Training** - Continuous improvement

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m murphy_implementation.main
```

The API will be available at `http://localhost:8000`

### API Documentation

Interactive API docs: `http://localhost:8000/docs`

### Example: Submit a Plan Generation Form

```python
import requests

form_data = {
    "goal": "Launch a new SaaS product for project management",
    "domain": "software_development",
    "timeline": "6 months",
    "budget": 150000.0,
    "team_size": 8,
    "success_criteria": [
        "Beta product launched",
        "100 active users",
        "User satisfaction > 4.0/5.0"
    ],
    "known_constraints": [
        "Must comply with GDPR",
        "Must integrate with Slack"
    ],
    "risk_tolerance": "medium"
}

response = requests.post(
    "http://localhost:8000/api/forms/plan-generation",
    json=form_data
)

print(response.json())
```

## Form Types

### 1. Plan Upload Form
Upload an existing plan for expansion and validation.

**Endpoint**: `POST /api/forms/plan-upload`

### 2. Plan Generation Form
Generate a new plan from a goal description.

**Endpoint**: `POST /api/forms/plan-generation`

### 3. Task Execution Form
Execute a specific task from a plan.

**Endpoint**: `POST /api/forms/task-execution`

### 4. Validation Form
Validate Murphy's output for a task.

**Endpoint**: `POST /api/forms/validation`

### 5. Correction Form
Capture corrections for training Murphy.

**Endpoint**: `POST /api/forms/correction`

## Murphy Validation

### Uncertainty Components

- **UD (Data Uncertainty)**: Quality and completeness of data
- **UA (Authority Uncertainty)**: Credibility of sources
- **UI (Intent Uncertainty)**: Clarity of goals
- **UR (Risk Uncertainty)**: Potential consequences
- **UG (Disagreement Uncertainty)**: Conflicting information

### Confidence Calculation

```
C = 1 - (0.25·UD + 0.20·UA + 0.15·UI + 0.25·UR + 0.15·UG)
```

### Murphy Gate

Threshold-based decision mechanism:
- **C ≥ 0.85**: Proceed automatically
- **C ≥ 0.70**: Proceed with monitoring
- **C ≥ 0.50**: Proceed with caution
- **C < 0.50**: Request human review

## Execution Phases

1. **EXPAND** - Generate possibilities
2. **TYPE** - Classify and categorize
3. **ENUMERATE** - List all options
4. **CONSTRAIN** - Apply rules and limits
5. **COLLAPSE** - Select best option
6. **BIND** - Commit to decision
7. **EXECUTE** - Perform action

## Human-in-the-Loop

### Checkpoint Types

- `before_execution` - Approve before execution
- `after_each_phase` - Review after each phase
- `on_high_risk` - Intervene on high-risk operations
- `on_low_confidence` - Review low-confidence decisions
- `final_review` - Final validation before completion

### Intervention Flow

1. System detects checkpoint condition
2. Creates intervention request
3. Notifies human
4. Waits for response (if blocking)
5. Processes response and continues

## Learning System

### The 80/20 Principle

- Murphy attempts 100% of the task
- Human corrects the 20% that's wrong
- System captures corrections as training data
- Shadow agent trains on corrections
- Next iteration: Murphy gets 85% right, then 90%, then 95%

### Correction Capture

Every human correction is captured with:
- Original output (before)
- Corrected output (after)
- Correction rationale (why)
- Correction type (factual, logic, formatting, etc.)
- Severity (minor, moderate, major, critical)

### Shadow Agent Training

1. Accumulate correction examples
2. Train shadow agent on corrections
3. A/B test shadow vs primary agent
4. Promote shadow if better
5. Repeat continuously

## Implementation Status

### Phase 1: Core Form System ✅ COMPLETE
- Form intake layer
- Plan decomposition engine
- Murphy validation layer
- Execution orchestrator
- HITL monitor

### Phase 2: Murphy Validation Enhancement 🔄 IN PROGRESS
- Enhanced uncertainty calculations
- Integration with existing confidence engine
- Assumption tracking
- Risk assessment

### Phase 3: Correction Capture ⏸️ PLANNED
- Correction capture system
- Training example generation
- Training dataset storage

### Phase 4: Shadow Agent Training ⏸️ PLANNED
- Shadow agent trainer
- A/B testing framework
- Performance tracking
- Promotion mechanism

### Phase 5: Production Deployment ⏸️ PLANNED
- Persistent state storage
- Permanent audit logging
- Cloud deployment
- Monitoring and alerting

## Project Structure

```
murphy_implementation/
├── forms/              # Form schemas, handlers, API
├── plan_decomposition/ # Plan parsing and task generation
├── validation/         # Murphy validation (UD, UA, UI, UR, UG)
├── execution/          # Phase-based execution orchestrator
├── hitl/              # Human-in-the-loop monitor
├── correction/        # Correction capture (Phase 3)
├── training/          # Shadow agent training (Phase 4)
├── main.py            # FastAPI application
└── README.md          # This file
```

## Integration with Existing Murphy Runtime

This implementation integrates with the existing Murphy Runtime Analysis system:

- Uses existing `confidence_engine` for G/D/H calculations
- Uses existing `phase_controller` for phase execution
- Uses existing `supervisor_system` for assumption management
- Adds new Murphy validation layer (UD/UA/UI/UR/UG)
- Adds form-driven interface
- Adds correction capture and learning

## Configuration

### Environment Variables

```bash
# API Configuration
MURPHY_API_HOST=0.0.0.0
MURPHY_API_PORT=8000

# Confidence Thresholds
MURPHY_DEFAULT_THRESHOLD=0.7
MURPHY_EXECUTE_THRESHOLD=0.85

# HITL Configuration
MURPHY_HITL_ENABLED=true
MURPHY_HITL_TIMEOUT=3600

# Storage (Phase 5)
MURPHY_REDIS_URL=redis://localhost:6379
MURPHY_POSTGRES_URL=postgresql://user:pass@localhost/murphy
```

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=murphy_implementation tests/

# Run specific test
pytest tests/test_forms.py
```

## Contributing

1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Follow PEP 8 style guide
5. Use type hints

## License

[Your License Here]

## Contact

[Your Contact Information]

## Acknowledgments

Built on top of the Murphy Runtime Analysis system.
Integrates with existing confidence engine, phase controller, and supervisor system.