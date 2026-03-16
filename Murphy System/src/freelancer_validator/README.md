# Freelancer Validator

The `freelancer_validator` package vets freelancer profiles against
configurable criteria, manages budgets, and routes approvals through
a human-in-the-loop (HITL) gate.

## Key Modules

| Module | Purpose |
|--------|---------|
| `criteria_engine.py` | Evaluates freelancer profiles against scoring criteria |
| `credential_verifier.py` | Verifies credentials and portfolio evidence |
| `budget_manager.py` | Tracks available budget and enforces spending limits |
| `hitl_bridge.py` | Pauses validation for human approval when criteria are unclear |
| `models.py` | `FreelancerProfile`, `ValidationResult`, `Budget` models |
