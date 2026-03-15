# Murphy System — Rosetta State Management System
## Design Specification, Gap Analysis & Implementation Plan

**Document Version:** 1.0.0  
**Branch:** `feature/rosetta-state-management`  
**Owner:** Inoni LLC / Corey Post  
**Repository:** https://github.com/IKNOWINOT/Murphy-System  
**Runtime Scope:** repository root only  

---

## Table of Contents

1. [Executive Summary & Verdict](#1-executive-summary--verdict)
2. [Current System Analysis](#2-current-system-analysis)
3. [Gap Analysis — What Is Missing](#3-gap-analysis--what-is-missing)
4. [Architecture Decision — Existing vs. Proposed](#4-architecture-decision--existing-vs-proposed)
5. [Rosetta State Management Architecture](#5-rosetta-state-management-architecture)
6. [Rosetta Document Schema](#6-rosetta-document-schema)
7. [Process Flow — State Updates & Recalibration](#7-process-flow--state-updates--recalibration)
8. [Weekly Recalibration Process](#8-weekly-recalibration-process)
9. [Archive vs. Current Classification Rules](#9-archive-vs-current-classification-rules)
10. [Agent Workflow Pattern Integration](#10-agent-workflow-pattern-integration)
11. [Integration Map — Existing Murphy Modules](#11-integration-map--existing-murphy-modules)
12. [Implementation Checklist](#12-implementation-checklist)
13. [File & Directory Specification](#13-file--directory-specification)

---

## 1. Executive Summary & Verdict

### The Question
You asked: *"Is my current agent persistence system aligned with my original architectural plan, and which approach is superior?"*

### The Verdict: **Hybrid — Extend the Existing System, Do Not Replace It**

After reading every relevant file in the repository root, the conclusion is clear:

**Your existing infrastructure is architecturally sound and more capable than you may realize.** The `PersistenceManager`, `StateManager`, `SelfImprovementEngine`, `SelfAutomationOrchestrator`, `RAGVectorIntegration`, `WorkflowDAGEngine`, `EventBackbone`, and `GovernanceScheduler` collectively form a strong foundation. The problem is not that the wrong system was built — it is that **these components are not wired together into a unified, agent-readable state surface**.

What is missing is a **Rosetta Layer**: a standardized, structured document format that each agent can read and write, that aggregates state from all existing subsystems into a single coherent view, and that drives the weekly recalibration cycle you described.

**The superior plan is:** Keep everything that exists. Add the Rosetta document layer on top. Wire the existing modules as data sources into it.

---

## 2. Current System Analysis

### 2.1 What Exists and How It Works

The `Murphy System` runtime contains six distinct state-related subsystems that currently operate in isolation from one another:

#### Layer 1 — Raw Persistence (`src/persistence_manager.py`)
The `PersistenceManager` provides file-based JSON storage with four namespaces: `documents/`, `gate_history/`, `librarian_context/`, and `audit/`. It is thread-safe via per-directory locks and supports atomic writes via `.tmp` rename. It has full replay support via `get_replay_events()` which merges gate history and audit trail chronologically. This is the **durable storage backbone** — it works correctly and should be kept as-is.

**What it lacks:** It stores raw events and documents but has no concept of an agent's current goal, task progress, or recalibration state. It is a log, not a living state surface.

#### Layer 2 — In-Memory State (`src/execution_engine/state_manager.py`)
The `StateManager` manages `SystemState` objects in memory with typed state categories (`SYSTEM`, `WORKFLOW`, `TASK`, `USER`, `SESSION`, `CONFIGURATION`), transition history, SHA-256 integrity hashing, and file-based persist/restore. It is thread-safe and supports state versioning.

**What it lacks:** It is purely in-memory with manual file persistence. There is no automatic sync to `PersistenceManager`. States are identified by UUID, not by agent name or role. There is no concept of goals, automation progress, or recalibration windows. The `cleanup_old_states()` method deletes states older than N days — this is the wrong behavior for agent state; old states should be archived, not deleted.

#### Layer 3 — Task Lifecycle (`bots/task_lifecycle.py`, `bots/task_record.py`)
`TaskLifecycle` (Pydantic) tracks `CREATED → RUNNING → FAILED/COMPLETED` with timestamps. `TaskRecord` adds priority (1–10), feedback scoring, recursion depth, entropy tracking, stage percentages (30/60/90/100%), and bot assignment. These are the most granular task-level models in the system.

**What it lacks:** No link back to a parent agent state document. No concept of which automation workflow a task belongs to. No archive/current classification flag.

#### Layer 4 — Self-Improvement Loop (`src/self_improvement_engine.py`, `src/self_automation_orchestrator.py`)
`SelfImprovementEngine` records `ExecutionOutcome` objects, extracts recurring failure/success patterns, generates `ImprovementProposal` objects with priority and status, and calibrates confidence. `SelfAutomationOrchestrator` manages `ImprovementTask` objects with a full `PromptStep` lifecycle (`ANALYSIS → PLANNING → IMPLEMENTATION → TESTING → REVIEW → DOCUMENTATION → ITERATION`) and `CycleRecord` tracking.

**What it lacks:** The improvement proposals and cycle records are stored only in memory. They are not persisted to `PersistenceManager`. They are not surfaced in any agent-readable document. The weekly recalibration trigger does not exist.

#### Layer 5 — Governance & Scheduling (`src/governance_framework/agent_descriptor.py`, `src/governance_framework/scheduler.py`)
`AgentDescriptor` is a rich formal specification: authority band, resource caps, access matrix, action permissions, convergence constraints, retry policy, scheduling spec, termination criteria, and escalation policy. `GovernanceScheduler` enforces authority precedence, resource limits, and dependency ordering.

**What it lacks:** The `AgentDescriptor` is a static governance contract, not a living state document. It describes what an agent *is allowed to do*, not what it *is currently doing* or *has done*. There is no runtime state attached to the descriptor.

#### Layer 6 — Memory & RAG (`bots/memory_cortex_bot.py`, `src/rag_vector_integration.py`)
`MemoryCortexBot` unifies short-term/long-term memory, deduplication, document indexing, and external loading. `RAGVectorIntegration` provides TF-IDF semantic search, knowledge graph entity extraction, and context assembly for LLM prompts.

**What it lacks:** Agent state documents are not ingested into the RAG system, meaning agents cannot semantically query their own history or the history of peer agents. This is the biggest missed opportunity for self-improvement inference.

### 2.2 Alignment Assessment

| Your Requirement | Existing Coverage | Gap |
|---|---|---|
| Agent state files per agent | Partial — `StateManager` has typed states but not per-agent named documents | No named, persistent, agent-scoped document |
| Global system state | Partial — `PersistenceManager` audit trail covers events | No aggregated global state view |
| Current goals and tasks | Partial — `ImprovementTask` + `TaskRecord` exist | Not linked to agent identity or persisted |
| Progress on automations | Partial — `TaskRecord.stage` (30/60/90/100%) exists | Not surfaced in a readable document |
| Chronological rollout | Partial — `PersistenceManager.get_replay_events()` exists | No time-window based progression logic |
| Weekly recalibration | **Missing** — no scheduler trigger exists | Needs `GovernanceScheduler` + cron wiring |
| Archive vs. current classification | **Missing** — `StateManager.cleanup_old_states()` deletes, not archives | Needs classification rules + archive namespace |
| Rolling Rosetta document updates | **Missing** — no document format defined | Core gap this design addresses |
| Better inference than simple logs | Partial — `RAGVectorIntegration` exists but not wired to state | Needs ingestion pipeline from state docs |
| Agent workflow pattern (7 steps) | Partial — `PromptStep` enum covers 6 of 7 steps | Missing explicit "move to next task" transition |

---

## 3. Gap Analysis — What Is Missing

### GAP-001: No Named, Persistent, Agent-Scoped State Document
**Severity: Critical**  
There is no file or database record that answers the question: *"What is agent X currently doing, what has it completed, and what are its active goals?"* The `StateManager` uses UUIDs, not agent names. The `PersistenceManager` stores events, not agent summaries.

### GAP-002: No Global System State Aggregator
**Severity: Critical**  
There is no single document that shows the state of all agents simultaneously. The `ARCHITECTURE_MAP.md` describes the system structure but is static documentation, not a live state surface.

### GAP-003: Self-Improvement Data Is Not Persisted
**Severity: High**  
`SelfImprovementEngine` and `SelfAutomationOrchestrator` hold all improvement proposals, cycle records, and outcome patterns in memory only. A process restart loses all learning history.

### GAP-004: No Weekly Recalibration Trigger
**Severity: High**  
The `GovernanceScheduler` has the infrastructure to schedule agents but there is no recurring weekly job that triggers the recalibration cycle described in your requirements.

### GAP-005: Archive Classification Is Destructive
**Severity: High**  
`StateManager.cleanup_old_states()` deletes states older than N days. This is wrong for an agent system — old states should be classified as archived and moved to a separate namespace, not deleted. The `ARCHIVE_STRATEGY.md` defines the right philosophy for the repo but it has not been applied to runtime state.

### GAP-006: RAG System Not Wired to Agent State
**Severity: Medium**  
`RAGVectorIntegration` is fully functional but agent state documents, improvement proposals, and task records are not ingested into it. This means agents cannot use semantic search to reason about their own history.

### GAP-007: No Standardized Update Protocol After Each Task
**Severity: Medium**  
There is no defined procedure for what an agent must write after completing a task. The `PromptStep.DOCUMENTATION` step exists in `SelfAutomationOrchestrator` but has no concrete output format or target file.

### GAP-008: No Cross-Agent State Visibility
**Severity: Medium**  
Agents cannot read each other's state. The `EventBackbone` publishes events but there is no mechanism for an agent to query the current state of a peer agent.

---

## 4. Architecture Decision — Existing vs. Proposed

### Option A: Replace with New System
Build a new state management system from scratch using Rosetta documents as the primary store, replacing `StateManager` and `PersistenceManager`.

**Verdict: Rejected.** The existing `PersistenceManager` is well-engineered with atomic writes, thread safety, and replay support. The `StateManager` has integrity hashing and typed transitions. Replacing them would discard working, tested code and introduce regression risk.

### Option B: Extend with Rosetta Layer (Selected)
Keep all existing subsystems. Add a `RosettaStateLayer` that:
1. Defines a standardized Rosetta document schema for each agent
2. Reads from all existing subsystems to populate the document
3. Writes the document to `PersistenceManager` under a new `rosetta/` namespace
4. Ingests documents into `RAGVectorIntegration` for semantic querying
5. Drives the weekly recalibration cycle via `GovernanceScheduler`

**Verdict: Selected.** Zero breaking changes. Additive only. Leverages all existing infrastructure.

### Why Option B Is Superior
The existing system already has: durable storage, event replay, in-memory state with integrity hashing, task lifecycle models, self-improvement pattern extraction, semantic memory, governance scheduling, and a full agent descriptor schema. The only thing missing is a **unified surface** that aggregates these into a format agents can read and write. That is exactly what a Rosetta document provides.

---

## 5. Rosetta State Management Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ROSETTA STATE LAYER                              │
│              src/rosetta/                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐   │
│  │  RosettaStateManager│    │  RecalibrationScheduler          │   │
│  │  (rosetta_manager.py│    │  (recalibration_scheduler.py)    │   │
│  │                     │    │                                  │   │
│  │  • load_agent_doc() │    │  • trigger_weekly_recal()        │   │
│  │  • save_agent_doc() │    │  • classify_archive_current()    │   │
│  │  • update_after_    │    │  • run_recalibration_cycle()     │   │
│  │    task()           │    │  • emit RECALIBRATION_COMPLETE   │   │
│  │  • get_global_view()│    │                                  │   │
│  │  • ingest_to_rag()  │    └──────────────────────────────────┘   │
│  └──────────┬──────────┘                                           │
│             │                                                       │
│  ┌──────────▼──────────────────────────────────────────────────┐   │
│  │              RosettaDocument (per agent)                    │   │
│  │  rosetta/<agent_id>.json                                    │   │
│  │                                                             │   │
│  │  identity | system_state | agent_state | goals | tasks |   │   │
│  │  automation_progress | recalibration | archive_log |       │   │
│  │  improvement_proposals | workflow_pattern | metadata       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ reads from / writes to
        ┌──────────────────────┼──────────────────────────┐
        ▼                      ▼                          ▼
┌───────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ Persistence   │   │  StateManager    │   │ SelfImprovement     │
│ Manager       │   │  (in-memory)     │   │ Engine +            │
│               │   │                  │   │ SelfAutomation      │
│ documents/    │   │ SystemState      │   │ Orchestrator        │
│ gate_history/ │   │ StateTransition  │   │                     │
│ librarian/    │   │ StateType        │   │ ExecutionOutcome     │
│ audit/        │   │                  │   │ ImprovementProposal  │
│ rosetta/  ◄───┼───┼──────────────────┼───┼─────────────────────│
│ snapshots/    │   │                  │   │ ImprovementTask     │
└───────────────┘   └──────────────────┘   └─────────────────────┘
        │                      │                          │
        ▼                      ▼                          ▼
┌───────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ RAG Vector    │   │ GovernanceFrame  │   │ EventBackbone       │
│ Integration   │   │ work             │   │                     │
│               │   │                  │   │ TASK_SUBMITTED      │
│ ingest_doc()  │   │ AgentDescriptor  │   │ TASK_COMPLETED      │
│ semantic_     │   │ GovernanceSchedul│   │ TASK_FAILED         │
│ search()      │   │ er               │   │ PERSISTENCE_SNAPSHOT│
│               │   │                  │   │ RECALIBRATION_START │
└───────────────┘   └──────────────────┘   └─────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| `RosettaStateManager` | `src/rosetta/rosetta_manager.py` | Load/save/update Rosetta documents; aggregate from subsystems; ingest to RAG |
| `RecalibrationScheduler` | `src/rosetta/recalibration_scheduler.py` | Weekly trigger; archive/current classification; cycle orchestration |
| `RosettaDocument` | `src/rosetta/rosetta_models.py` | Pydantic model for the full document schema |
| `RosettaArchiveClassifier` | `src/rosetta/archive_classifier.py` | Rules engine for archive vs. current decisions |
| `GlobalStateAggregator` | `src/rosetta/global_aggregator.py` | Reads all agent Rosetta docs; produces system-wide view |
| Rosetta namespace | `.murphy_persistence/rosetta/` | Storage location — one JSON file per agent |

---

## 6. Rosetta Document Schema

See companion file: `ROSETTA_AGENT_STATE_TEMPLATE.md` for the full annotated template.

The schema has 11 top-level sections:

```
RosettaDocument
├── identity              — agent_id, role, version, created_at, last_updated
├── system_state          — global_phase, health_status, active_agents, system_flags
├── agent_state           — current_status, current_step, authority_band, stability_score
├── goals                 — active_goals[], completed_goals[], blocked_goals[]
├── tasks                 — active_tasks[], completed_tasks[], failed_tasks[]
├── automation_progress   — workflows[], current_workflow_id, overall_completion_pct
├── recalibration         — last_recal_at, next_recal_at, recal_window, recal_history[]
├── archive_log           — archived_items[], archive_criteria, last_archive_at
├── improvement_proposals — pending[], applied[], rejected[]
├── workflow_pattern      — current_phase (of 7-step pattern), phase_history[]
└── metadata              — schema_version, rag_ingested_at, integrity_hash
```

---

## 7. Process Flow — State Updates & Recalibration

### 7.1 Per-Task State Update Flow

```
Agent receives task
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  STEP 1: ANALYZE                                          │
│  • Load RosettaDocument for this agent                    │
│  • Set workflow_pattern.current_phase = "ANALYZE"         │
│  • Add task to tasks.active_tasks[]                       │
│  • Save document                                          │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  STEP 2: PLAN                                             │
│  • Update workflow_pattern.current_phase = "PLAN"         │
│  • Populate task.plan_steps[]                             │
│  • Set task.stage = 30                                    │
│  • Save document                                          │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  STEP 3: EXECUTE                                          │
│  • Update workflow_pattern.current_phase = "EXECUTE"      │
│  • Set task.stage = 60                                    │
│  • Emit EventType.TASK_SUBMITTED to EventBackbone         │
│  • Save document                                          │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│  STEP 4: TEST                                             │
│  • Update workflow_pattern.current_phase = "TEST"         │
│  • Record test results in task.test_results[]             │
│  • Save document                                          │
└───────────────────────┬───────────────────────────────────┘
                        │
                ┌───────┴────────┐
                │                │
           PASS │           FAIL │
                ▼                ▼
┌───────────────────┐  ┌─────────────────────────────────────┐
│  STEP 6:          │  │  STEP 5: FIX & RETEST               │
│  NEXT TASK        │  │  • workflow_pattern = "FIX_RETEST"  │
│                   │  │  • Increment task.retry_count       │
│  • Move task from │  │  • Record failure in               │
│    active to      │  │    SelfImprovementEngine            │
│    completed      │  │  • Loop back to STEP 4              │
│  • Set stage=100  │  │  • If retry_count > max_retries:    │
│  • Emit           │  │    move to tasks.failed_tasks[]     │
│    TASK_COMPLETED │  └─────────────────────────────────────┘
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  STEP 7: DOCUMENT                                         │
│  • workflow_pattern.current_phase = "DOCUMENT"            │
│  • Update goals: mark completed if all tasks done         │
│  • Update automation_progress.overall_completion_pct      │
│  • Ingest updated document into RAGVectorIntegration      │
│  • Emit EventType.PERSISTENCE_SNAPSHOT                    │
│  • Save final document                                    │
└───────────────────────────────────────────────────────────┘
```

### 7.2 Chronological Rollout Flow

The system progresses state based on real wall-clock time using the following rules:

```
Time Window          Action
─────────────────────────────────────────────────────────────
T+0 (task created)   task.created_at set; stage = 0
T+task_start         stage = 30; workflow_phase = EXECUTE
T+test_pass          stage = 60; workflow_phase = TEST
T+review_pass        stage = 90; workflow_phase = REVIEW
T+doc_complete       stage = 100; task moved to completed
Weekly boundary      RecalibrationScheduler triggers
```

The `RecalibrationScheduler` uses `GovernanceScheduler` to register a weekly recurring job. It reads the `recalibration.next_recal_at` field from each agent's Rosetta document and triggers when wall-clock time exceeds that value.

---

## 8. Weekly Recalibration Process

### 8.1 Trigger Conditions
The recalibration cycle fires when **any** of these conditions are true:
- Wall-clock time has passed `recalibration.next_recal_at`
- `EventBackbone` receives a manual `RECALIBRATION_START` event
- System health drops below threshold (from `system_state.health_status`)

### 8.2 Recalibration Cycle Steps

```
WEEKLY RECALIBRATION CYCLE
═══════════════════════════════════════════════════════════════

Phase 1: SNAPSHOT (T=0)
  ├── PersistenceReplayCompleteness.create_snapshot() for all agents
  ├── GlobalStateAggregator.build_global_view()
  └── Write snapshot to .murphy_persistence/snapshots/weekly_<date>.json

Phase 2: CLASSIFY (T+5min)
  ├── For each task in tasks.completed_tasks[]:
  │     ├── IF task.job_number is set AND task.closed = True
  │     │     → Move to archive_log.archived_items[]
  │     │     → Set archive_reason = "completed_job"
  │     └── ELSE IF task.completed_at < (now - 30 days)
  │           → Move to archive_log.archived_items[]
  │           → Set archive_reason = "age_threshold"
  │
  ├── For each goal in goals.completed_goals[]:
  │     ├── IF all child tasks archived → archive goal
  │     └── ELSE → keep in completed_goals (still current)
  │
  └── For each workflow in automation_progress.workflows[]:
        ├── IF workflow.status = COMPLETED AND all tasks archived
        │     → Mark workflow as archived
        └── ELSE → Keep as current

Phase 3: IMPROVEMENT EXTRACTION (T+10min)
  ├── SelfImprovementEngine.extract_patterns()
  ├── Generate ImprovementProposals for recurring failures
  ├── Write proposals to improvement_proposals.pending[]
  └── Persist to PersistenceManager

Phase 4: RECALIBRATE GOALS (T+15min)
  ├── Review goals.blocked_goals[] — can any be unblocked?
  ├── Reprioritize goals.active_goals[] by urgency score
  ├── Generate new goals from improvement_proposals if needed
  └── Update agent_state.stability_score

Phase 5: RAG REFRESH (T+20min)
  ├── For each agent: RAGVectorIntegration.ingest_document(rosetta_doc)
  ├── Update metadata.rag_ingested_at
  └── Rebuild knowledge graph entity links

Phase 6: FINALIZE (T+25min)
  ├── Set recalibration.last_recal_at = now
  ├── Set recalibration.next_recal_at = now + 7 days
  ├── Append entry to recalibration.recal_history[]
  ├── Emit EventType.HITL_REQUIRED if any proposals need review
  └── Save all Rosetta documents
```

### 8.3 Recalibration Output
After each weekly recalibration, every agent's Rosetta document will have:
- A clean `tasks.active_tasks[]` containing only genuinely in-progress work
- A populated `archive_log` with reasons for each archived item
- Updated `improvement_proposals.pending[]` with actionable fixes
- A refreshed `recalibration.recal_history[]` entry with metrics
- An updated `metadata.integrity_hash`

---

## 9. Archive vs. Current Classification Rules

### 9.1 Task Classification

| Condition | Classification | Action |
|---|---|---|
| `task.status = COMPLETED` AND `task.job_number` set AND `task.closed = True` | **ARCHIVE** | Move to `archive_log`; reason = `completed_job` |
| `task.status = COMPLETED` AND `task.completed_at < now - 30d` | **ARCHIVE** | Move to `archive_log`; reason = `age_threshold` |
| `task.status = COMPLETED` AND `task.completed_at >= now - 30d` | **CURRENT** | Keep in `tasks.completed_tasks[]` |
| `task.status = FAILED` AND `task.retry_count >= task.max_retries` | **ARCHIVE** | Move to `archive_log`; reason = `max_retries_exceeded` |
| `task.status = ACTIVE` | **CURRENT** | Always keep in `tasks.active_tasks[]` |
| `task.status = BLOCKED` AND blocked for > 14 days | **ARCHIVE** | Move to `archive_log`; reason = `stale_blocked` |

### 9.2 Goal Classification

| Condition | Classification |
|---|---|
| All child tasks archived AND goal marked complete | **ARCHIVE** |
| Goal has at least one active or recent completed task | **CURRENT** |
| Goal has no tasks and was created > 60 days ago | **ARCHIVE** (reason: `orphaned_goal`) |

### 9.3 Workflow Classification

| Condition | Classification |
|---|---|
| `workflow.status = COMPLETED` AND completion > 30 days ago | **ARCHIVE** |
| `workflow.status = COMPLETED` AND completion < 30 days ago | **CURRENT** |
| `workflow.status = RUNNING` or `PAUSED` | **CURRENT** |
| `workflow.status = FAILED` AND no retry planned | **ARCHIVE** |

### 9.4 Improvement Proposal Classification

| Condition | Classification |
|---|---|
| `proposal.status = applied` | Move to `improvement_proposals.applied[]` |
| `proposal.status = rejected` | Move to `improvement_proposals.rejected[]` |
| `proposal.status = pending` AND created > 90 days ago | **ARCHIVE** (reason: `stale_proposal`) |
| `proposal.status = pending` AND created < 90 days ago | **CURRENT** |

---

## 10. Agent Workflow Pattern Integration

Your 7-step workflow pattern maps directly to the `PromptStep` enum in `SelfAutomationOrchestrator` with one addition:

| Your Step | PromptStep Enum | Rosetta Field Updated |
|---|---|---|
| 1. Analyze what needs to be done | `ANALYSIS` | `workflow_pattern.current_phase`, `tasks.active_tasks[].analysis_notes` |
| 2. Create a plan for tasks | `PLANNING` | `tasks.active_tasks[].plan_steps[]`, `task.stage = 30` |
| 3. Execute and test tasks | `IMPLEMENTATION` | `task.stage = 60`, EventBackbone `TASK_SUBMITTED` |
| 4. Review test results | `TESTING` | `tasks.active_tasks[].test_results[]` |
| 5. Fix and retest loop | `ITERATION` | `task.retry_count++`, `SelfImprovementEngine.record_outcome()` |
| 6. Move to next task | *(new: `TRANSITION`)* | Move task to `completed_tasks[]`, load next from queue |
| 7. Update documentation | `DOCUMENTATION` | Full Rosetta doc save + RAG ingest |

The `TRANSITION` step (step 6) is the only gap in the existing `PromptStep` enum. It should be added as `TRANSITION = "transition"` to make the enum complete.

### Workflow Pattern State Machine

```
ANALYZE → PLAN → EXECUTE → TEST ──PASS──→ TRANSITION → DOCUMENT
                              │                              │
                              └──FAIL──→ ITERATE ──────────►┘
                                         (loop until
                                          pass or max_retries)
```

Each phase transition writes to the Rosetta document immediately, ensuring that if the agent is interrupted at any point, the document reflects the last known good state.

---

## 11. Integration Map — Existing Murphy Modules

### 11.1 Modules That Feed INTO Rosetta Documents (Data Sources)

| Existing Module | Data Provided | Rosetta Section |
|---|---|---|
| `PersistenceManager.get_audit_trail()` | All historical events | `metadata.event_count`, `recalibration.recal_history` |
| `PersistenceManager.get_gate_history()` | Gate decisions per session | `agent_state.gate_decisions[]` |
| `StateManager.get_state_by_name()` | Current in-memory state | `agent_state.current_status`, `agent_state.variables` |
| `SelfImprovementEngine.extract_patterns()` | Failure/success patterns | `improvement_proposals.pending[]` |
| `SelfAutomationOrchestrator` cycle records | Improvement task history | `automation_progress.workflows[]` |
| `TaskRecord` objects | Task priority, stage, feedback | `tasks.active_tasks[]`, `tasks.completed_tasks[]` |
| `AgentDescriptor` | Authority, resource limits | `agent_state.authority_band`, `agent_state.resource_limits` |
| `StabilityMetrics.calculate_stability_score()` | Stability score 0.0–1.0 | `agent_state.stability_score` |
| `WorkflowDAGEngine` execution history | Step completion status | `automation_progress.workflows[].steps[]` |
| `EventBackbone` event stream | Real-time events | Triggers Rosetta updates via subscription |

### 11.2 Modules That Read FROM Rosetta Documents (Consumers)

| Existing Module | What It Reads | Why |
|---|---|---|
| `RAGVectorIntegration` | Full Rosetta document text | Semantic search over agent history |
| `GovernanceScheduler` | `recalibration.next_recal_at` | Schedule weekly recalibration job |
| `MemoryCortexBot` | `goals.active_goals[]` | Context for LLM prompt assembly |
| `SupervisorLoop` | `agent_state.stability_score` | HITL escalation trigger |
| `SelfImprovementEngine` | `improvement_proposals.pending[]` | Avoid duplicate proposals |
| `GlobalStateAggregator` | All agent Rosetta docs | System-wide health view |

### 11.3 New EventBackbone Event Types Required

Add to `EventType` enum in `src/event_backbone.py`:

```python
RECALIBRATION_START    = "recalibration_start"
RECALIBRATION_COMPLETE = "recalibration_complete"
ROSETTA_UPDATED        = "rosetta_updated"
TASK_ARCHIVED          = "task_archived"
GOAL_ARCHIVED          = "goal_archived"
WORKFLOW_PHASE_CHANGED = "workflow_phase_changed"
```

---

## 12. Implementation Checklist

### Priority 1 — Foundation (Week 1)

- [ ] **P1-001** Create `src/rosetta/` directory with `__init__.py`
- [ ] **P1-002** Implement `src/rosetta/rosetta_models.py` — full Pydantic schema (see `ROSETTA_AGENT_STATE_TEMPLATE.md`)
- [ ] **P1-003** Implement `src/rosetta/rosetta_manager.py` — `RosettaStateManager` class with `load_agent_doc()`, `save_agent_doc()`, `update_after_task()`, `get_global_view()`
- [ ] **P1-004** Add `rosetta/` namespace to `PersistenceManager._locks` and `_init_directories()`
- [ ] **P1-005** Add `TRANSITION = "transition"` to `PromptStep` enum in `src/self_automation_orchestrator.py`
- [ ] **P1-006** Add 6 new `EventType` values to `src/event_backbone.py`
- [ ] **P1-007** Write `tests/test_rosetta_manager.py` — load/save/update cycle

### Priority 2 — Recalibration Engine (Week 2)

- [ ] **P2-001** Implement `src/rosetta/archive_classifier.py` — `RosettaArchiveClassifier` with all 4 classification rule sets
- [ ] **P2-002** Implement `src/rosetta/recalibration_scheduler.py` — `RecalibrationScheduler` with weekly trigger, 6-phase cycle
- [ ] **P2-003** Wire `RecalibrationScheduler` into `GovernanceScheduler` as a recurring job
- [ ] **P2-004** Implement `src/rosetta/global_aggregator.py` — `GlobalStateAggregator.build_global_view()`
- [ ] **P2-005** Write `tests/test_recalibration_scheduler.py`
- [ ] **P2-006** Write `tests/test_archive_classifier.py`

### Priority 3 — Subsystem Wiring (Week 3)

- [ ] **P3-001** Wire `SelfImprovementEngine.extract_patterns()` output into `RosettaStateManager.update_after_task()`
- [ ] **P3-002** Wire `SelfAutomationOrchestrator` cycle records into `automation_progress.workflows[]`
- [ ] **P3-003** Wire `RAGVectorIntegration.ingest_document()` call into `RosettaStateManager.save_agent_doc()`
- [ ] **P3-004** Wire `EventBackbone` subscription in `RosettaStateManager` — subscribe to `TASK_COMPLETED`, `TASK_FAILED`, `GATE_EVALUATED`
- [ ] **P3-005** Wire `StateManager` sync — on `SystemState` update, push delta to Rosetta document
- [ ] **P3-006** Write `tests/test_rosetta_subsystem_wiring.py`

### Priority 4 — Self-Improvement Persistence (Week 4)

- [ ] **P4-001** Persist `SelfImprovementEngine._outcomes` to `PersistenceManager` on every `record_outcome()` call
- [ ] **P4-002** Persist `SelfImprovementEngine._proposals` to `PersistenceManager` on every `generate_proposals()` call
- [ ] **P4-003** Restore `SelfImprovementEngine` state from `PersistenceManager` on startup
- [ ] **P4-004** Persist `SelfAutomationOrchestrator` cycle records to `PersistenceManager`
- [ ] **P4-005** Write `tests/test_self_improvement_persistence.py`

### Priority 5 — Documentation & README (Week 4)

- [ ] **P5-001** Update `ARCHITECTURE_MAP.md` to include Rosetta layer
- [ ] **P5-002** Update `API_DOCUMENTATION.md` with Rosetta endpoints
- [ ] **P5-003** Add Rosetta state management section to main `README.md`

---

## 13. File & Directory Specification

### New Files to Create

```
./
└── src/
    └── rosetta/
        ├── __init__.py
        ├── rosetta_models.py          # Pydantic schema — RosettaDocument and all sub-models
        ├── rosetta_manager.py         # RosettaStateManager — load/save/update/aggregate
        ├── archive_classifier.py      # RosettaArchiveClassifier — classification rules engine
        ├── recalibration_scheduler.py # RecalibrationScheduler — weekly cycle orchestrator
        └── global_aggregator.py       # GlobalStateAggregator — system-wide view builder

./
└── tests/
    ├── test_rosetta_manager.py
    ├── test_recalibration_scheduler.py
    ├── test_archive_classifier.py
    ├── test_rosetta_subsystem_wiring.py
    └── test_self_improvement_persistence.py

./
└── docs/
    └── state_management/
        ├── ROSETTA_STATE_MANAGEMENT_SYSTEM.md   # This document
        └── ROSETTA_AGENT_STATE_TEMPLATE.md      # Schema template
```

### Modified Files (Zero Breaking Changes)

```
src/persistence_manager.py
  + Add "rosetta" to SUBDIRECTORY constants
  + Add "rosetta" lock to _locks dict
  + Add save_rosetta_doc() / load_rosetta_doc() / list_rosetta_docs() methods

src/event_backbone.py
  + Add 6 new EventType values

src/self_automation_orchestrator.py
  + Add TRANSITION = "transition" to PromptStep enum

.murphy_persistence/
  + rosetta/          ← new namespace (auto-created by PersistenceManager)
  + snapshots/        ← already exists via persistence_replay_completeness.py
```

### Storage Layout

```
.murphy_persistence/
├── documents/          # LivingDocuments (existing)
├── gate_history/       # Gate decisions per session (existing)
├── librarian_context/  # Librarian curated context (existing)
├── audit/              # Audit trail (existing)
├── wal/                # Write-ahead log (existing)
├── snapshots/          # Point-in-time snapshots (existing)
└── rosetta/            # NEW — one file per agent
    ├── global_system_state.json      # GlobalStateAggregator output
    ├── <agent_id_1>.json             # Per-agent Rosetta document
    ├── <agent_id_2>.json
    └── recalibration_history.json    # Cross-agent recalibration log
```