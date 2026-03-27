# Form Intake

The `form_intake` package processes structured form submissions from users
or APIs and decomposes them into executable plans.

## Key Modules

| Module | Purpose |
|--------|---------|
| `handlers.py` | Form-type-specific intake handlers |
| `plan_decomposer.py` | Decomposes a validated form into a multi-step execution plan |
| `plan_models.py` | `FormPlan`, `PlanStep`, `FormContext` models |
| `schemas.py` | JSON schema definitions for supported form types |
| `api.py` | FastAPI router for form submission endpoints |
