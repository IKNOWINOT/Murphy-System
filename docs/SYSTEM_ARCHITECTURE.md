# Murphy System — Architecture Overview

> Updated: automatically maintained · License: BSL 1.1 · © 2020 Inoni LLC

## Pilot Account

All platform-level automations route through the canonical pilot account:

| Field | Value |
|-------|-------|
| Email | `cpost@murphy.systems` |
| Name | Corey Post |
| Role | `founder_admin` |
| Org | Inoni LLC |
| HITL Level | `graduated` (auto-executes when confidence criteria met) |

Config source: `src/pilot_config.py`

---

## Information Flow: NL → Automation

```
User / System Input
        │
        ▼
┌───────────────────────────────────────────────────────┐
│              Large Control Model (LCM)                │
│  src/large_control_model.py                           │
│                                                       │
│  1. NLQueryEngine   — parse intent                    │
│  2. MSSController   — determine resolution level      │
│  3. RosetteLens     — agent positions shape data lens │
│  4. CausalitySandbox— simulate before committing      │
│  5. Dispatch        — execute (if confidence ≥ 85%)   │
│  6. HITL            — return to human if below gate   │
└───────────────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
  Auto-Dispatch              Human Review Queue
  (≥85% confidence)          (HITL graduation)
```

---

## MSS System — Magnify / Simplify / Solidify

| Operation | Effect | Resolution |
|-----------|--------|-----------|
| Magnify | Expand query to full requirements + components | +2 RM levels |
| Simplify | Reduce noise, distil to core signals | -2 RM levels |
| Solidify | Lock to implementation plan (MFGC ≥85%) | RM5 (locked) |

**Rosette Lens** shapes which data MSS operates on:
- Agent positions (RosettaAgentState) → guise selection
- Guise → filter criteria passed to MSS
- Source: `src/rosette_lens.py`

---

## Navigation Registry

All 50+ modules are mapped to categories in `src/nav_registry.py`:

| Category | Key Modules |
|----------|-------------|
| Operations | Dashboard, Workspace, Management, Calendar |
| Intelligence | Terminal, Ambient Intelligence, System Visualizer |
| **Finance** | **Grant Wizard, Grant Dashboard, Financing Options, Wallet** |
| Control | Dispatch, Automation Scheduler, Terminal Architect |
| Automation | AI Workflows, Communication Hub, Agent Monitor |
| Communication | Blog, Community Forum, Docs |
| Compliance | Compliance Dashboard, Legal, Privacy |
| Onboarding | Onboarding Wizard, Demo |
| Settings | Account Settings, Change Password |

Shared nav component: `static/murphy-nav.js` (auto-injects on import)

---

## Demo System — Commissioned Pipeline

The demo at `/ui/demo` routes through the **real Murphy System pipeline**:

```
User types query
      │
      ▼
POST /api/demo/run
      │
      ├── DemoRunner.run_scenario(query)   [src/demo_runner.py]
      │         │
      │         ├── MFGC gate (confidence scoring)
      │         ├── MSS Magnify (functional requirements)
      │         ├── MSS Solidify (implementation plan, RM5)
      │         ├── AI Workflow Generator (executable DAG)
      │         └── Automation Spec (ROI, integrations, spec_id)
      │
      ▼
Animated terminal output (real pipeline steps)
      │
      ▼
POST /api/demo/generate-deliverable
      │
      └── Downloadable .txt automation schematic
          (usable blueprint for activating automations on Murphy System)
```

Fallback: if `/api/demo/run` is unavailable, UI falls back to local animated scenarios.

---

## Automation Routing (Pilot Account)

Source: `src/pilot_config.py`

| Category | Shadow Agents / Modules |
|----------|------------------------|
| sales | chief_revenue_officer, vp_sales, partnership_manager |
| marketing | vp_marketing |
| engineering | technical_operations |
| research | chief_research_officer |
| communications | ai_communications |
| finance | grant_wizard, grant_dashboard, financing_options |
| compliance | compliance_dashboard |
| onboarding | onboarding_wizard, task_catalog |

---

## MFGC — Multi-Factor Gate Controller

The MFGC gates every automation request through 7 phases before dispatch.
`ALWAYS follow task when the MFGC system operates.`

Confidence ≥ 85% → auto-execute via Dispatch
Confidence < 85% → HITL queue (graduated graduation policy)

---

## Causality Sandbox

Source: `src/causality_sandbox.py`

Simulates every proposed action in an isolated sandbox before committing.
Wired into the LCM pipeline for "what-if" queries.
Biological immune memory for sub-linear resolution of recurring patterns.

---

## Rosetta System — Agent Position Constellation

The "rosette" is the constellation of agent positions whose configuration
shapes the data lens that MSS operates on.

Available guises (configurations):
- `default` — balanced lens at RM2
- `sales_focus` — magnify pipeline + revenue, simplify ops noise
- `compliance_focus` — high-res compliance view at RM4
- `research_focus` — maximum breadth at RM5
- `finance_focus` — grant + funding data lens at RM3

Source: `src/rosette_lens.py`

---

## Key Source Files

| File | Purpose |
|------|---------|
| `src/pilot_config.py` | Pilot account constants + routing |
| `src/large_control_model.py` | LCM meta-controller |
| `src/rosette_lens.py` | Rosetta→MSS data lens bridge |
| `src/nav_registry.py` | Module→category navigation map |
| `src/demo_runner.py` | Real demo pipeline commissioning |
| `src/demo_deliverable_generator.py` | Automation schematic generator |
| `src/causality_sandbox.py` | Pre-commit simulation engine |
| `src/mss_controls.py` | Magnify/Simplify/Solidify |
| `src/dispatch_routes.py` | NL→tool dispatch |
| `static/murphy-nav.js` | Shared navigation component |
