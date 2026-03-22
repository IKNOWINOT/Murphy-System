# Platform Onboarding Module

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `src/platform_onboarding/` module implements the Murphy Platform Onboarding DAG — a 147-task dependency graph that bootstraps Murphy's complete business infrastructure, including federal identity registration, grant applications, cloud credits, API keys, compliance certifications, marketplace listings, and recurring operations.

## Architecture

```
platform_onboarding/
├── __init__.py             — Public API
├── task_catalog.py         — 147-task OnboardingTask catalog with reverse-dep computation
├── workflow_definition.py  — Encodes catalog as WorkflowDefinition for DAG engine
├── priority_scorer.py      — Multi-factor task priority scoring
├── wait_state_handler.py   — External wait tracking (e.g. SAM.gov 10-day review)
├── progress_tracker.py     — Completion metrics and parallel group computation
├── url_launcher.py         — Navigation context and prefill hints
├── task_handlers.py        — WorkflowDAGEngine action handlers
├── onboarding_session.py   — Session dataclass (state, data, waits)
└── onboarding_api.py       — FastAPI router with 17 endpoints
```

## Dependency Chains

| Chain | Path |
|-------|------|
| 1 | `1.02 (EIN)` → `1.01 (SAM.gov)` → `[1.03, 1.04, 1.05, 1.06, 1.07, 1.08, 1.09, 1.10]` |
| 2 | `[1.01 + 1.03 + 1.05]` → `2.01 (SBIR)`, `2.04 (NSF)`, etc. |
| 3 | Cloud credits `4.01–4.08` — no dependencies, start immediately |
| 4 | API keys `5.01–5.50` — no dependencies, start immediately |
| 5 | `5.10 (Stripe)` → `3.04 (Affirm)`, `3.05 (Klarna)`, `3.06 (Afterpay)`, `3.07 (Splitit)` |
| 6 | `5.21 (AWS IAM)` → `7.01 (AWS Marketplace)` |
| 6 | `5.45 (GCP SA)` → `7.02 (GCP Marketplace)`, `7.09 (G Suite)` |
| 6 | `5.46 (Azure SP)` → `7.03 (Azure Marketplace)` |
| 7 | Compliance self-assessments `6.04`, `6.05`, `6.06`, `6.07`, `6.11`, `6.12` — level 0 |
| 8 | `1.01 (SAM.gov)` → `8.01–8.10` (international grants, all conditional) |

## Task Sections

| Section | Name | Tasks |
|---------|------|-------|
| 1 | Federal Identity | 10 |
| 2 | Grant Applications Track A | 19 |
| 3 | Customer Financing Track B | 10 |
| 4 | Cloud Credits | 8 |
| 5 | API Keys & Developer Accounts | 50 |
| 6 | Security & Compliance | 12 |
| 7 | Marketplace & Partner Listings | 13 |
| 8 | International Grants | 10 |
| 9 | Domain & Infrastructure | 5 |
| 10 | Recurring Operations | 10 |

## Quick Start

```python
from src.platform_onboarding import create_onboarding_workflow, ProgressTracker, OnboardingSession

# Create the DAG
wf = create_onboarding_workflow()

# Start a session
session = OnboardingSession.create_new("my-account")

# Get unblocked tasks
tracker = ProgressTracker()
unblocked = tracker.get_unblocked_tasks(session)

# Get progress
progress = tracker.compute_progress(session)
print(f"{progress.completion_percentage}% complete")
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/onboarding/start` | Start onboarding workflow |
| GET | `/api/onboarding/status` | Progress dashboard |
| GET | `/api/onboarding/next` | Priority-sorted next tasks |
| GET | `/api/onboarding/tasks` | All tasks with statuses |
| GET | `/api/onboarding/tasks/{task_id}` | Task detail + dependencies |
| POST | `/api/onboarding/tasks/{task_id}/start` | Mark in-progress |
| POST | `/api/onboarding/tasks/{task_id}/complete` | Mark completed |
| POST | `/api/onboarding/tasks/{task_id}/skip` | Skip task |
| POST | `/api/onboarding/tasks/{task_id}/wait` | Mark waiting on external |
| GET | `/api/onboarding/checkpoint` | Save checkpoint |
| POST | `/api/onboarding/resume` | Resume from checkpoint |
| GET | `/api/onboarding/parallel-groups` | Parallel execution groups |
| GET | `/api/onboarding/critical-path` | Critical dependency path |
| GET | `/api/onboarding/value-report` | Value captured/pending |
| GET | `/api/onboarding/timeline` | Projected completion timeline |
