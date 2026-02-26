# Rosetta Agent State Document — Schema & Template

**Document Version:** 1.0.0  
**Runtime Scope:** `Murphy System/Murphy System/` only  
**Storage Path:** `.murphy_persistence/rosetta/<agent_id>.json`  
**Owner:** Inoni LLC / Corey Post  

---

## Overview

A Rosetta document is the **single source of truth** for an agent's current state, goals, task progress, and improvement history. It is:

- **Written** by the agent after every task phase transition (7-step workflow pattern)
- **Read** by peer agents, the supervisor loop, the recalibration scheduler, and the RAG system
- **Persisted** via `PersistenceManager` to `.murphy_persistence/rosetta/<agent_id>.json`
- **Indexed** into `RAGVectorIntegration` after every save for semantic querying
- **Recalibrated** weekly by `RecalibrationScheduler` to classify archive vs. current items

---

## Full JSON Schema with Annotations

```json
{
  // ═══════════════════════════════════════════════════════════════
  // SECTION 1: IDENTITY
  // Who this document belongs to. Never changes after creation.
  // ═══════════════════════════════════════════════════════════════
  "identity": {
    "agent_id": "string — unique agent identifier (UUID or named slug, e.g. 'engineering_bot')",
    "agent_role": "string — human-readable role name (e.g. 'Engineering Bot', 'Triage Bot')",
    "agent_class": "string — class name from bots/ or src/ (e.g. 'EngineeringBot')",
    "authority_band": "string — NONE | LOW | MEDIUM | HIGH | CRITICAL (from AgentDescriptor)",
    "owner": "string — 'Inoni LLC / Corey Post'",
    "schema_version": "string — '1.0.0'",
    "created_at": "ISO-8601 datetime — when this document was first created",
    "last_updated": "ISO-8601 datetime — when this document was last written"
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 2: SYSTEM STATE
  // Global view of the Murphy system as seen by this agent.
  // Updated during recalibration and on SYSTEM_HEALTH events.
  // ═══════════════════════════════════════════════════════════════
  "system_state": {
    "global_phase": "string — STARTUP | OPERATIONAL | DEGRADED | RECALIBRATING | SHUTDOWN",
    "health_status": "string — HEALTHY | WARNING | CRITICAL",
    "health_score": "float 0.0–1.0 — aggregated from StabilityMetrics",
    "active_agent_count": "integer — number of agents currently running",
    "active_agent_ids": ["array of agent_id strings currently active"],
    "system_flags": {
      "recalibration_in_progress": "boolean",
      "hitl_required": "boolean — true if any agent needs human review",
      "security_alert": "boolean",
      "maintenance_mode": "boolean"
    },
    "last_system_snapshot_at": "ISO-8601 datetime — last PersistenceReplayCompleteness snapshot",
    "observed_at": "ISO-8601 datetime — when this agent last refreshed system state"
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 3: AGENT STATE
  // This agent's current operational state.
  // Updated on every workflow phase transition.
  // ═══════════════════════════════════════════════════════════════
  "agent_state": {
    "current_status": "string — IDLE | ANALYZING | PLANNING | EXECUTING | TESTING | FIXING | TRANSITIONING | DOCUMENTING | BLOCKED | SUSPENDED | TERMINATED",
    "current_workflow_phase": "string — ANALYZE | PLAN | EXECUTE | TEST | FIX_RETEST | TRANSITION | DOCUMENT (7-step pattern)",
    "current_task_id": "string | null — ID of the task currently being worked",
    "current_goal_id": "string | null — ID of the goal this task belongs to",
    "stability_score": "float 0.0–1.0 — from StabilityMetrics.calculate_stability_score()",
    "confidence_score": "float 0.0–1.0 — from ConfidenceEngine",
    "authority_band": "string — mirrors identity.authority_band (for quick reads)",
    "resource_usage": {
      "cpu_cores_used": "integer",
      "memory_mb_used": "integer",
      "api_calls_this_window": "integer",
      "execution_time_sec": "float"
    },
    "session_id": "string | null — current active session ID",
    "state_version": "integer — increments on every state change (from StateManager.version)",
    "state_hash": "string — SHA-256 of current state for integrity checking",
    "last_gate_decision": "string | null — PROCEED | HALT | CLARIFY | VERIFY | ERROR",
    "blocked_reason": "string | null — populated when current_status = BLOCKED",
    "variables": {
      "key": "value — arbitrary agent-specific runtime variables from StateManager"
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 4: GOALS
  // What this agent is trying to achieve.
  // Goals contain tasks. Goals are classified archive/current weekly.
  // ═══════════════════════════════════════════════════════════════
  "goals": {
    "active_goals": [
      {
        "goal_id": "string — UUID",
        "title": "string — short human-readable goal title",
        "description": "string — full goal description",
        "category": "string — COVERAGE_GAP | INTEGRATION_GAP | QUALITY_GAP | FEATURE_REQUEST | BUG_FIX | SELF_IMPROVEMENT",
        "priority": "integer 1–5 (1=highest)",
        "created_at": "ISO-8601 datetime",
        "target_completion_at": "ISO-8601 datetime | null",
        "task_ids": ["array of task_id strings belonging to this goal"],
        "completion_pct": "float 0.0–100.0 — derived from child task stages",
        "source": "string — who/what created this goal (e.g. 'recalibration', 'supervisor', 'self_improvement_engine')",
        "tags": ["array of string tags"]
      }
    ],
    "completed_goals": [
      {
        "goal_id": "string",
        "title": "string",
        "completed_at": "ISO-8601 datetime",
        "outcome_summary": "string — brief description of what was achieved",
        "task_ids": ["array"],
        "archive_eligible_at": "ISO-8601 datetime — completed_at + 30 days"
      }
    ],
    "blocked_goals": [
      {
        "goal_id": "string",
        "title": "string",
        "blocked_since": "ISO-8601 datetime",
        "blocked_reason": "string",
        "unblock_conditions": ["array of string conditions that would unblock this goal"],
        "escalated_to_hitl": "boolean"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 5: TASKS
  // Individual units of work. Maps to TaskRecord and TaskLifecycle.
  // Tasks are the primary unit of archive/current classification.
  // ═══════════════════════════════════════════════════════════════
  "tasks": {
    "active_tasks": [
      {
        "task_id": "string — UUID (matches TaskRecord.id)",
        "title": "string",
        "description": "string",
        "goal_id": "string | null — parent goal",
        "workflow_id": "string | null — parent workflow",
        "bot": "string — bot responsible for execution (matches TaskRecord.bot)",
        "priority": "integer 1–10 (matches TaskRecord.priority)",
        "stage": "integer — 0 | 30 | 60 | 90 | 100 (matches TaskRecord.stage)",
        "current_phase": "string — current step in 7-step workflow pattern",
        "created_at": "ISO-8601 datetime",
        "started_at": "ISO-8601 datetime | null",
        "estimated_completion_at": "ISO-8601 datetime | null",
        "retry_count": "integer",
        "max_retries": "integer",
        "job_number": "string | null — external job/ticket number for archive classification",
        "closed": "boolean — true when external job is closed",
        "plan_steps": [
          {
            "step_number": "integer",
            "description": "string",
            "status": "string — PENDING | COMPLETE | SKIPPED",
            "completed_at": "ISO-8601 datetime | null"
          }
        ],
        "test_results": [
          {
            "attempt": "integer",
            "passed": "boolean",
            "tested_at": "ISO-8601 datetime",
            "notes": "string"
          }
        ],
        "analysis_notes": "string — notes from ANALYZE phase",
        "tags": ["array of string tags"],
        "entropy": "float | null — from TaskRecord.entropy"
      }
    ],
    "completed_tasks": [
      {
        "task_id": "string",
        "title": "string",
        "goal_id": "string | null",
        "completed_at": "ISO-8601 datetime",
        "outcome": "string — SUCCESS | PARTIAL | FAILURE",
        "stage": "integer — should be 100",
        "job_number": "string | null",
        "closed": "boolean",
        "feedback_score": "float | null — from TaskRecord.feedback_score",
        "feedback_comments": ["array of strings"],
        "archive_eligible_at": "ISO-8601 datetime — completed_at + 30 days",
        "archive_status": "string — CURRENT | ARCHIVED"
      }
    ],
    "failed_tasks": [
      {
        "task_id": "string",
        "title": "string",
        "goal_id": "string | null",
        "failed_at": "ISO-8601 datetime",
        "failure_reason": "string",
        "retry_count": "integer",
        "max_retries": "integer",
        "outcome_type": "string — FAILURE | TIMEOUT | BLOCKED (from OutcomeType enum)",
        "improvement_proposal_id": "string | null — linked proposal from SelfImprovementEngine",
        "archive_status": "string — CURRENT | ARCHIVED"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 6: AUTOMATION PROGRESS
  // Tracks multi-step automation workflows (WorkflowDAGEngine).
  // Shows overall system progress toward automation goals.
  // ═══════════════════════════════════════════════════════════════
  "automation_progress": {
    "overall_completion_pct": "float 0.0–100.0 — weighted average across all active workflows",
    "current_workflow_id": "string | null — ID of the workflow currently executing",
    "workflows": [
      {
        "workflow_id": "string — UUID",
        "name": "string — human-readable workflow name",
        "status": "string — DRAFT | READY | RUNNING | COMPLETED | FAILED | PAUSED | CANCELLED",
        "created_at": "ISO-8601 datetime",
        "started_at": "ISO-8601 datetime | null",
        "completed_at": "ISO-8601 datetime | null",
        "completion_pct": "float 0.0–100.0",
        "total_steps": "integer",
        "completed_steps": "integer",
        "failed_steps": "integer",
        "steps": [
          {
            "step_id": "string",
            "name": "string",
            "status": "string — PENDING | READY | RUNNING | COMPLETED | FAILED | SKIPPED | BLOCKED | TIMED_OUT",
            "depends_on": ["array of step_id strings"],
            "started_at": "ISO-8601 datetime | null",
            "completed_at": "ISO-8601 datetime | null",
            "result_summary": "string | null"
          }
        ],
        "archive_status": "string — CURRENT | ARCHIVED",
        "source": "string — 'self_automation_orchestrator' | 'manual' | 'recalibration'"
      }
    ],
    "cycle_records": [
      {
        "cycle_id": "string — from SelfAutomationOrchestrator.CycleRecord",
        "started_at": "ISO-8601 datetime",
        "completed_at": "ISO-8601 datetime | null",
        "tasks_attempted": "integer",
        "tasks_completed": "integer",
        "tasks_failed": "integer",
        "improvement_proposals_generated": "integer"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 7: RECALIBRATION
  // Tracks the weekly recalibration cycle for this agent.
  // RecalibrationScheduler reads next_recal_at to trigger the cycle.
  // ═══════════════════════════════════════════════════════════════
  "recalibration": {
    "last_recal_at": "ISO-8601 datetime | null — when the last recalibration completed",
    "next_recal_at": "ISO-8601 datetime — when the next recalibration should trigger",
    "recal_window_days": "integer — default 7 (weekly)",
    "recal_status": "string — IDLE | IN_PROGRESS | COMPLETE | FAILED",
    "recal_history": [
      {
        "recal_id": "string — UUID",
        "started_at": "ISO-8601 datetime",
        "completed_at": "ISO-8601 datetime",
        "phase_durations_sec": {
          "snapshot": "float",
          "classify": "float",
          "improvement_extraction": "float",
          "recalibrate_goals": "float",
          "rag_refresh": "float",
          "finalize": "float"
        },
        "items_archived": "integer — tasks + goals + workflows archived this cycle",
        "items_kept_current": "integer",
        "proposals_generated": "integer",
        "goals_reprioritized": "integer",
        "stability_score_before": "float",
        "stability_score_after": "float",
        "notes": "string | null — any notable events during this recalibration"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 8: ARCHIVE LOG
  // Record of everything that has been classified as archived.
  // Items are moved here from tasks, goals, and workflows.
  // This is the permanent record — items are never deleted.
  // ═══════════════════════════════════════════════════════════════
  "archive_log": {
    "last_archive_at": "ISO-8601 datetime | null",
    "total_archived_items": "integer",
    "archive_criteria_version": "string — '1.0.0' (version of classification rules applied)",
    "archived_items": [
      {
        "item_id": "string — original task_id, goal_id, or workflow_id",
        "item_type": "string — TASK | GOAL | WORKFLOW | IMPROVEMENT_PROPOSAL",
        "item_title": "string",
        "archived_at": "ISO-8601 datetime",
        "archive_reason": "string — completed_job | age_threshold | max_retries_exceeded | stale_blocked | orphaned_goal | stale_proposal",
        "job_number": "string | null — external job number if applicable",
        "original_section": "string — which section it came from (e.g. 'tasks.completed_tasks')",
        "summary": "string — brief summary of what this item was and what it accomplished"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 9: IMPROVEMENT PROPOSALS
  // Generated by SelfImprovementEngine from execution outcome patterns.
  // Drives the self-improvement loop.
  // ═══════════════════════════════════════════════════════════════
  "improvement_proposals": {
    "pending": [
      {
        "proposal_id": "string — UUID (matches ImprovementProposal.proposal_id)",
        "category": "string — routing | gating | delivery | confidence | coverage | integration | quality",
        "title": "string",
        "description": "string — full description of the proposed improvement",
        "priority": "string — critical | high | medium | low",
        "source_pattern": "string — description of the failure/success pattern that generated this",
        "suggested_action": "string — concrete action to take",
        "created_at": "ISO-8601 datetime",
        "linked_task_ids": ["array of task_ids that contributed to this pattern"],
        "linked_failure_count": "integer — how many failures triggered this proposal",
        "estimated_effort": "string — e.g. '2 hours', '1 day'",
        "hitl_required": "boolean — does this need human review before implementation?"
      }
    ],
    "applied": [
      {
        "proposal_id": "string",
        "title": "string",
        "applied_at": "ISO-8601 datetime",
        "applied_by": "string — agent_id or 'human'",
        "outcome": "string — description of what changed",
        "verified": "boolean"
      }
    ],
    "rejected": [
      {
        "proposal_id": "string",
        "title": "string",
        "rejected_at": "ISO-8601 datetime",
        "rejected_by": "string — agent_id or 'human'",
        "rejection_reason": "string"
      }
    ]
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 10: WORKFLOW PATTERN
  // Tracks the agent's position in the 7-step workflow pattern.
  // Updated on every phase transition.
  // ═══════════════════════════════════════════════════════════════
  "workflow_pattern": {
    "current_phase": "string — ANALYZE | PLAN | EXECUTE | TEST | FIX_RETEST | TRANSITION | DOCUMENT",
    "current_task_id": "string | null — task being processed in current phase",
    "phase_entered_at": "ISO-8601 datetime — when current phase started",
    "phase_history": [
      {
        "task_id": "string",
        "phase": "string",
        "entered_at": "ISO-8601 datetime",
        "exited_at": "ISO-8601 datetime | null",
        "duration_sec": "float | null",
        "outcome": "string | null — PASS | FAIL | SKIP"
      }
    ],
    "fix_retest_loop_count": "integer — how many FIX_RETEST iterations on current task",
    "total_tasks_processed": "integer — lifetime count",
    "total_phases_completed": "integer — lifetime count"
  },

  // ═══════════════════════════════════════════════════════════════
  // SECTION 11: METADATA
  // Document integrity and indexing metadata.
  // ═══════════════════════════════════════════════════════════════
  "metadata": {
    "schema_version": "string — '1.0.0'",
    "document_type": "string — 'rosetta_agent_state'",
    "rag_ingested_at": "ISO-8601 datetime | null — last time this doc was ingested into RAGVectorIntegration",
    "rag_doc_id": "string | null — doc_id assigned by RAGVectorIntegration",
    "integrity_hash": "string — SHA-256 of document content (excluding this field)",
    "event_count": "integer — total events in PersistenceManager audit trail for this agent",
    "persistence_dir": "string — path to .murphy_persistence/rosetta/<agent_id>.json",
    "last_written_by": "string — agent_id or process that last wrote this document",
    "write_count": "integer — total number of times this document has been saved"
  }
}
```

---

## Minimal Starter Document (New Agent)

Use this as the initial document when registering a new agent:

```json
{
  "identity": {
    "agent_id": "REPLACE_WITH_AGENT_ID",
    "agent_role": "REPLACE_WITH_ROLE_NAME",
    "agent_class": "REPLACE_WITH_CLASS_NAME",
    "authority_band": "MEDIUM",
    "owner": "Inoni LLC / Corey Post",
    "schema_version": "1.0.0",
    "created_at": "REPLACE_WITH_ISO_DATETIME",
    "last_updated": "REPLACE_WITH_ISO_DATETIME"
  },
  "system_state": {
    "global_phase": "OPERATIONAL",
    "health_status": "HEALTHY",
    "health_score": 1.0,
    "active_agent_count": 0,
    "active_agent_ids": [],
    "system_flags": {
      "recalibration_in_progress": false,
      "hitl_required": false,
      "security_alert": false,
      "maintenance_mode": false
    },
    "last_system_snapshot_at": null,
    "observed_at": "REPLACE_WITH_ISO_DATETIME"
  },
  "agent_state": {
    "current_status": "IDLE",
    "current_workflow_phase": "ANALYZE",
    "current_task_id": null,
    "current_goal_id": null,
    "stability_score": 1.0,
    "confidence_score": 1.0,
    "authority_band": "MEDIUM",
    "resource_usage": {
      "cpu_cores_used": 0,
      "memory_mb_used": 0,
      "api_calls_this_window": 0,
      "execution_time_sec": 0.0
    },
    "session_id": null,
    "state_version": 1,
    "state_hash": null,
    "last_gate_decision": null,
    "blocked_reason": null,
    "variables": {}
  },
  "goals": {
    "active_goals": [],
    "completed_goals": [],
    "blocked_goals": []
  },
  "tasks": {
    "active_tasks": [],
    "completed_tasks": [],
    "failed_tasks": []
  },
  "automation_progress": {
    "overall_completion_pct": 0.0,
    "current_workflow_id": null,
    "workflows": [],
    "cycle_records": []
  },
  "recalibration": {
    "last_recal_at": null,
    "next_recal_at": "REPLACE_WITH_FIRST_RECAL_DATETIME",
    "recal_window_days": 7,
    "recal_status": "IDLE",
    "recal_history": []
  },
  "archive_log": {
    "last_archive_at": null,
    "total_archived_items": 0,
    "archive_criteria_version": "1.0.0",
    "archived_items": []
  },
  "improvement_proposals": {
    "pending": [],
    "applied": [],
    "rejected": []
  },
  "workflow_pattern": {
    "current_phase": "ANALYZE",
    "current_task_id": null,
    "phase_entered_at": "REPLACE_WITH_ISO_DATETIME",
    "phase_history": [],
    "fix_retest_loop_count": 0,
    "total_tasks_processed": 0,
    "total_phases_completed": 0
  },
  "metadata": {
    "schema_version": "1.0.0",
    "document_type": "rosetta_agent_state",
    "rag_ingested_at": null,
    "rag_doc_id": null,
    "integrity_hash": null,
    "event_count": 0,
    "persistence_dir": ".murphy_persistence/rosetta/REPLACE_WITH_AGENT_ID.json",
    "last_written_by": "system",
    "write_count": 0
  }
}
```

---

## Global System State Document

Stored at `.murphy_persistence/rosetta/global_system_state.json`. Written by `GlobalStateAggregator` during recalibration and on demand.

```json
{
  "document_type": "global_system_state",
  "generated_at": "ISO-8601 datetime",
  "generated_by": "GlobalStateAggregator",
  "schema_version": "1.0.0",

  "system_summary": {
    "total_agents": "integer",
    "active_agents": "integer",
    "idle_agents": "integer",
    "blocked_agents": "integer",
    "overall_health_score": "float 0.0–1.0",
    "overall_stability_score": "float 0.0–1.0",
    "total_active_tasks": "integer",
    "total_active_goals": "integer",
    "total_pending_proposals": "integer",
    "hitl_required_count": "integer"
  },

  "agent_summaries": [
    {
      "agent_id": "string",
      "agent_role": "string",
      "current_status": "string",
      "current_phase": "string",
      "stability_score": "float",
      "active_task_count": "integer",
      "active_goal_count": "integer",
      "last_updated": "ISO-8601 datetime"
    }
  ],

  "system_flags": {
    "recalibration_in_progress": "boolean",
    "any_agent_blocked": "boolean",
    "any_hitl_required": "boolean",
    "security_alert": "boolean"
  },

  "last_recalibration": {
    "completed_at": "ISO-8601 datetime | null",
    "next_scheduled_at": "ISO-8601 datetime",
    "items_archived_total": "integer",
    "proposals_generated_total": "integer"
  },

  "integrity_hash": "string — SHA-256 of document content"
}
```

---

## Update Rules — When to Write

| Trigger | Sections Updated | Writer |
|---|---|---|
| Agent starts a new task | `agent_state`, `tasks.active_tasks`, `workflow_pattern` | Agent itself |
| Workflow phase transition (any of 7 steps) | `agent_state.current_workflow_phase`, `workflow_pattern`, `tasks.active_tasks[].current_phase` | Agent itself |
| Task test passes | `tasks.active_tasks[].test_results`, `workflow_pattern` | Agent itself |
| Task test fails | `tasks.active_tasks[].test_results`, `workflow_pattern.fix_retest_loop_count` | Agent itself |
| Task completes | `tasks.active_tasks` → `tasks.completed_tasks`, `goals[].completion_pct`, `automation_progress` | Agent itself |
| Task fails permanently | `tasks.active_tasks` → `tasks.failed_tasks`, `improvement_proposals.pending` | Agent + SelfImprovementEngine |
| New goal created | `goals.active_goals` | Agent or Recalibration Scheduler |
| Goal completed | `goals.active_goals` → `goals.completed_goals` | Agent itself |
| Weekly recalibration | All sections — archive classification, proposal generation, RAG refresh | RecalibrationScheduler |
| System health event | `system_state` | GlobalStateAggregator |
| HITL resolution | `agent_state.blocked_reason`, `goals.blocked_goals` | SupervisorLoop |

---

## Integrity Hash Computation

The `metadata.integrity_hash` is computed as follows:

```python
import hashlib, json

def compute_integrity_hash(doc: dict) -> str:
    # Exclude the hash field itself from computation
    doc_copy = {k: v for k, v in doc.items() if k != "metadata"}
    doc_copy["metadata"] = {
        k: v for k, v in doc["metadata"].items() 
        if k != "integrity_hash"
    }
    canonical = json.dumps(doc_copy, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

This matches the pattern already used in `AgentDescriptor.generate_hash()` and `SystemState.get_hash()` — consistent with the existing codebase.

---

## RAG Ingestion Text Format

When ingesting a Rosetta document into `RAGVectorIntegration`, convert it to the following plain-text format for chunking:

```
AGENT: {identity.agent_role} ({identity.agent_id})
STATUS: {agent_state.current_status} | PHASE: {agent_state.current_workflow_phase}
STABILITY: {agent_state.stability_score} | CONFIDENCE: {agent_state.confidence_score}
LAST UPDATED: {identity.last_updated}

ACTIVE GOALS:
{for each goal in goals.active_goals}
  - [{goal.priority}] {goal.title}: {goal.description} ({goal.completion_pct}% complete)

ACTIVE TASKS:
{for each task in tasks.active_tasks}
  - [{task.priority}] {task.title} | Stage: {task.stage}% | Phase: {task.current_phase}
    {task.description}

RECENT COMPLETIONS:
{for each task in tasks.completed_tasks[-5:]}
  - {task.title} completed {task.completed_at} | Outcome: {task.outcome}

PENDING IMPROVEMENTS:
{for each proposal in improvement_proposals.pending}
  - [{proposal.priority}] {proposal.title}: {proposal.suggested_action}

LAST RECALIBRATION: {recalibration.last_recal_at}
NEXT RECALIBRATION: {recalibration.next_recal_at}
```

This format ensures that semantic queries like *"which agent is working on security fixes?"* or *"what failed last week?"* return meaningful results from the RAG system.