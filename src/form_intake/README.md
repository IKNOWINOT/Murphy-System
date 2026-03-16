# `src/form_intake` — Form Intake Module

Structured form capture for Murphy plans, task execution requests, and validation workflows.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

All user interactions with Murphy start with a form that captures requirements, context, and validation criteria before any agent work begins. The form intake package defines the schema for every form type in the system, validates submissions, and converts them into typed plan or task objects for downstream processing. The `PlanDecomposer` breaks `PlanGenerationForm` submissions into structured sub-tasks. A FastAPI router and handler layer manage form submission, validation, and error responses.

## Key Components

| Module | Purpose |
|--------|---------|
| `schemas.py` | All form schemas: `PlanUploadForm`, `PlanGenerationForm`, `TaskExecutionForm`, `ValidationForm`, `CorrectionForm` |
| `plan_models.py` | Plan decomposition output models |
| `plan_decomposer.py` | `PlanDecomposer` — breaks plan forms into ordered sub-tasks |
| `handlers.py` | Request handlers for each form type |
| `api.py` | FastAPI router for form submission and retrieval |

## Usage

```python
from form_intake import PlanGenerationForm, FormType, RiskTolerance, validate_form

form = PlanGenerationForm(
    form_type=FormType.PLAN_GENERATION,
    goal="Deploy new auth service",
    risk_tolerance=RiskTolerance.LOW,
)
result = validate_form(form)
print(result.valid, result.errors)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
