# Self-Selling Engine

The `self_selling_engine` package enables Murphy to autonomously market
and sell its own services, subject to strict compliance and outreach-consent
constraints.

## Key Modules

| Module | Purpose |
|--------|---------|
| `_engine.py` | `SelfSellingEngine` — orchestrates the marketing pipeline |
| `marketing_plan.py` | Generates and executes personalised marketing plans |
| `_outreach_compliance.py` | Enforces outreach consent and CAN-SPAM rules |
| `_compliance.py` | General compliance checks for sales activities |
| `_constraints.py` | Hard limits (budget, frequency, channel) for outreach |
