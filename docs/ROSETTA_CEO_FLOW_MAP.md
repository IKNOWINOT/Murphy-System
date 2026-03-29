# Rosetta ↔ CEO Branch System Flow Map

> **Design Label:** FLOW-001 — Rosetta↔CEO Integration Flow Map
> **Owner:** Platform Engineering / State Management
> **Status:** Production-ready — all 5 gaps closed
> **Copyright © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1**

---

## System Entry Point Decision

The Murphy System entry point is **`murphy_production_server.py`** (the FastAPI
production server), which creates the `ActivatedHeartbeatRunner`. The runner
embeds `CEOBranch` as an optional extension. On each heartbeat tick, the runner
calls `CEOBranch.run_tick()`, which cascades through the entire org chart.

**Architecture:** The entry point is the **agentic side** — the CEO Branch is
the autonomous decision-maker. The Rosetta system is the **state layer** that
agents read before acting and write to after acting. Sidebots and external
commands flow through the production server's API routes, not through Rosetta
directly.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  murphy_production_server.py                        │
│                  (FastAPI — production entry point)                  │
│                                                                     │
│  Creates:                                                           │
│    ActivatedHeartbeatRunner                                         │
│      └── CEOBranch (embedded, optional)                             │
│            ├── OrgChartAutomation (10 VP roles)                     │
│            ├── SystemWorkflow (continuous tick loop)                 │
│            ├── RosettaManager (state persistence)         ← P0/P1  │
│            ├── RosettaPlatformManager (platform state)    ← P3     │
│            └── RosettaStoneHeartbeat (org pulse)          ← P4     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complete Flow Diagram

### Startup Sequence (CEO Branch Activation)

```
murphy_production_server.py
  │
  ├─ ActivatedHeartbeatRunner.__init__()
  │    └─ CEOBranch.__init__(
  │         rosetta_manager=RosettaManager,
  │         platform_manager=RosettaPlatformManager,
  │         heartbeat=RosettaStoneHeartbeat
  │       )
  │         │
  │         ├─ OrgChartAutomation.__init__(rosetta_manager=mgr)  ← P1
  │         │    └─ For each role in _ORG_CHART_DEFINITION:
  │         │         VPRole(role_label, subsystems, responsibilities,
  │         │                rosetta_manager=mgr)
  │         │
  │         └─ SystemWorkflow.__init__(org_chart, rosetta_manager=mgr)  ← P2
  │
  └─ CEOBranch.activate()
       │
       ├─ [P0] _seed_rosetta_personas()
       │    └─ For each VP role:
       │         RosettaManager.save_state(RosettaAgentState(
       │           identity=Identity(agent_id, name, role, org),
       │           system_state=SystemState(status="idle"),
       │           agent_state=AgentState(current_phase="onboarding")
       │         ))
       │
       ├─ [P4] _register_heartbeat_translator()
       │    └─ RosettaStoneHeartbeat.register_translator(
       │         OrganizationTier.MANAGEMENT,
       │         _management_translator  ← cascades directives to VPs
       │       )
       │
       └─ SystemWorkflow.start()
            └─ Begins periodic tick timer (default 20 min)
```

### Operational Loop (Per Tick)

```
ActivatedHeartbeatRunner._run_tick()
  │
  └─ CEOBranch.run_tick()
       │
       └─ SystemWorkflow.tick()
            │
            ├─ Step 1: _update_operational_plan()
            │    └─ Generates plan with 7 domains:
            │         revenue_generation, customer_onboarding,
            │         production_delivery, compliance_monitoring,
            │         system_health, community_outreach,
            │         resource_allocation
            │
            ├─ Step 2: OrgChartAutomation.collect_reports()
            │    └─ For each VP role:
            │         ├─ [P1] VPRole.rosetta_state → reads own Rosetta doc
            │         │    └─ RosettaManager.load_state(agent_id)
            │         │         → Returns goals, tasks, automation progress
            │         │
            │         └─ VPRole.generate_report() → RoleReport
            │              ├─ status_check() → HEALTHY/DEGRADED/OFFLINE
            │              ├─ Metrics from status_probe()
            │              └─ [P1] Enriched with rosetta_goals, rosetta_tasks
            │
            ├─ Step 3: Compute confidence score
            │    └─ confidence = healthy_count / total_roles
            │
            ├─ Step 4: Adaptive plan adjustment
            │    └─ If confidence < threshold (0.70):
            │         → Phase = DEGRADED, narrow scope to healthy roles
            │
            ├─ Step 5: Alert emission
            │    └─ Collect alerts from all reports
            │         → Call alert_hook if configured
            │
            └─ [P2] _persist_reports_to_rosetta()
                 └─ For each RoleReport:
                      RosettaManager.load_state(agent_id)
                      ├─ Update system_state.status
                      ├─ Update system_state.active_tasks
                      ├─ Append AutomationProgress entry
                      ├─ Set metadata.extras.last_tick
                      ├─ Set metadata.extras.last_confidence
                      ├─ Set metadata.extras.last_report
                      └─ RosettaManager.save_state(state)
```

### Directive Flow (CEO → VP Roles)

```
External Command (API / HITL / Heartbeat pulse)
  │
  └─ CEOBranch.issue_directive("Focus on revenue growth")
       │
       ├─ OrgChartAutomation.broadcast_directive(directive, roles=[...])
       │    └─ For each target VP role:
       │         VPRole.execute_directive(directive)
       │           ├─ Validate and sanitize (max 2000 chars)
       │           ├─ Log to _directive_log (bounded, CWE-770)
       │           └─ Return DirectiveResult(accepted=True)
       │
       ├─ [P3] RosettaPlatformManager.update_platform(
       │         status="active",
       │         metadata={"last_directive": directive}
       │       )
       │
       └─ [P3] For each target role:
            RosettaPlatformManager.sync_down(role.agent_id)
              └─ Push platform calibrations to agent's
                 metadata.extras["platform_calibrations"]
```

### Heartbeat Cascade (P4)

```
RosettaStoneHeartbeat.emit_pulse(
    directives={"priority": "revenue", "action": "increase outreach"}
)
  │
  └─ Propagate through TIER_ORDER:
       │
       ├─ EXECUTIVE tier → passive receipt (propagating)
       │
       ├─ MANAGEMENT tier → _management_translator(pulse_dict)
       │    └─ Extract pulse.directives
       │         └─ For each non-CEO VP role:
       │              VPRole.execute_directive("priority: revenue; action: increase outreach")
       │              → Returns {"ack": True, "actions": 9}
       │
       ├─ OPERATIONS tier → passive receipt
       ├─ WORKER tier → passive receipt
       └─ INTEGRATION tier → passive receipt
```

---

## Org Chart Role Map

| Role | Agent ID | Subsystems | Rosetta State |
|------|----------|------------|---------------|
| CEO | `ceo` | ceo_branch_activation | ✅ Seeded at startup |
| CTO | `cto` | architecture_evolution, code_repair_engine | ✅ Seeded at startup |
| VP Sales | `vp_sales` | self_selling_engine | ✅ Seeded at startup |
| VP Operations | `vp_operations` | full_automation_controller, automation_scheduler | ✅ Seeded at startup |
| VP Compliance | `vp_compliance` | compliance_engine, compliance_as_code_engine | ✅ Seeded at startup |
| VP Engineering | `vp_engineering` | ci_cd_pipeline_manager, autonomous_repair_system | ✅ Seeded at startup |
| VP Customer Success | `vp_customer_success` | onboarding_flow, agentic_onboarding_engine | ✅ Seeded at startup |
| VP Finance | `vp_finance` | financial_reporting_engine, cost_optimization_advisor | ✅ Seeded at startup |
| VP Marketing | `vp_marketing` | campaign_orchestrator, adaptive_campaign_engine | ✅ Seeded at startup |
| Chief Security Officer | `chief_security_officer` | fastapi_security, authority_gate | ✅ Seeded at startup |

---

## Three-Layer Rosetta State System

```
┌─────────────────────────────────────────────────────┐
│ Layer 3: CombinedRosettaView (computed)              │
│   Aggregates Layer 1 + all Layer 2 agents            │
│   Used by: founder-update reports, HITL dashboards   │
├─────────────────────────────────────────────────────┤
│ Layer 2: RosettaAgentState (per agent)               │
│   Managed by: RosettaManager (CRUD + persistence)    │
│   Fields: identity, system_state, agent_state,       │
│           automation_progress, recalibration,         │
│           archive_log, improvement_proposals,         │
│           workflow_patterns, metadata(.extras)         │
│   Read by: VPRole.rosetta_state (P1)                 │
│   Written by: SystemWorkflow.tick() (P2)             │
│   Seeded by: CEOBranch.activate() (P0)               │
├─────────────────────────────────────────────────────┤
│ Layer 1: PlatformRosettaState (singleton)            │
│   Managed by: RosettaPlatformManager                 │
│   Fields: platform_id, status, active_agents,        │
│           calibrations, global_goals, routing_stats   │
│   Updated by: CEOBranch.issue_directive() (P3)       │
│   Synced by: sync_up() / sync_down()                │
└─────────────────────────────────────────────────────┘
```

---

## Metadata.extras Flow (Downstream)

The `Metadata.extras` dict was added to solve the problem of Pydantic
model revalidation silently dropping extra keys. The flow is:

```
P2 writes:
  metadata.extras["last_tick"]       = tick_number (int)
  metadata.extras["last_confidence"] = confidence (float)
  metadata.extras["last_report"]     = RoleReport.to_dict()

P3 writes (via sync_down):
  metadata.extras["platform_calibrations"] = [{sensor_id, value, ...}]

P1 reads:
  VPRole.rosetta_state → full state dict including metadata.extras
  → Agent can see its last tick, confidence, report, and calibrations
```

---

## Gap Closure Summary

| Priority | Gap | What It Does | Module | Tests |
|----------|-----|-------------|--------|-------|
| P0 | Load personas at startup | Seeds RosettaAgentState per VP role | `CEOBranch._seed_rosetta_personas()` | 5 tests |
| P1 | VP Rosetta access | Each VP reads its own state doc | `VPRole.rosetta_state` property | 8 tests |
| P2 | Report write-back | Tick results persist to Rosetta | `SystemWorkflow._persist_reports_to_rosetta()` | 4 tests |
| P3 | Directive audit trail | Directives recorded in platform state | `CEOBranch.issue_directive()` | 3 tests |
| P4 | Heartbeat translators | Pulses cascade as VP directives | `CEOBranch._register_heartbeat_translator()` | 5 tests |

**Total integration tests:** 29 (all passing)
**Total existing tests preserved:** 73 CEO + 57 Rosetta = 130

---

## Safety Invariants

1. **Thread safety** — All shared state guarded by `threading.Lock` / `RLock` (CWE-362)
2. **Bounded collections** — `capped_append()` and manual bounds (CWE-770)
3. **Input validation** — Directives max 2000 chars, null-byte stripped (CWE-20)
4. **Graceful degradation** — Every optional integration has a `None` check; system runs without Rosetta, Platform Manager, or Heartbeat
5. **Idempotent activation** — `_seed_rosetta_personas()` skips existing states
6. **Error isolation** — `# noqa: BLE001` exceptions caught and logged, never crash the tick loop
7. **Path traversal prevention** — `RosettaManager._sanitize_id()` blocks `../` in agent IDs
