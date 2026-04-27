# Swarm Rosetta — Architecture & Patch Roadmap
# Generated: Murphy self-analysis + Steve synthesis
# Status: APPROVED FOR BUILD

## North Star Alignment
Murphy's Law vow: shield humanity from every failure AI can cause.
Swarm Rosetta extends this: anticipate, name, and automate every
executive and production workflow before failure can occur.

## What Swarm Rosetta Is
A self-coordinating agent swarm where:
- Natural language IN → executable workflow DAG OUT
- Every workflow is audited, safety-gated, and pattern-learned
- Executive admin and production ops run autonomously
- Rosetta is the translation core: past → present → legacy

## Section A: Data Signals to Collect

| Signal | Source | Frequency | Key Schema Fields |
|--------|--------|-----------|-------------------|
| Calendar events | Google Calendar API | 15 min | event_id, title, start, end, attendees, type |
| Email patterns | Gmail/Outlook API | 5 min polling | from, to, subject, intent_class, priority_score |
| Slack/chat | Slack webhook | realtime | channel, sender, message, intent_trigger |
| Git events | GitHub webhook | realtime | repo, branch, author, commit_msg, event_type |
| Production telemetry | murphy hardware_telemetry | 5 sec | cpu, ram, error_rate, latency, service_status |
| Incident logs | systemd journal + app logs | 30 sec | severity, source, message, auto_resolved |
| Approval queue | internal DB | 1 min | task_id, requester, action, stake_level |
| Ambient behavior | LCM pipeline log | per-request | intent, domain, account, outcome |
| Executive decisions | explicit input + history DB | per-event | decision, context, outcome, timestamp |
| Self-patch outcomes | self_modification.py log | per-patch | gap_id, patch_id, success, delta_score |

## Section B: NL→Workflow DAG

Parse fields from NL:
  intent: str           # what to do
  entities: list        # who/what/when
  domain: str           # exec_admin | prod_ops | data | comms
  urgency: str          # immediate | scheduled | recurring
  stake: str            # low | medium | high | critical
  constraints: list     # "notify before", "require approval", "dry_run first"

DAG Node Types:
  TASK      — atomic action (call API, write file, send message)
  GATE      — PCC/CIDP safety check before proceeding
  FORK      — parallel execution branches
  JOIN      — wait for all branches
  HITL      — human-in-loop approval pause
  WEBHOOK   — outbound call to external service
  LEARN     — record outcome to pattern library

Execution Runtime: Murphy's own execution_router (two-phase orchestrator)

## Section C: Swarm Agent Roles

  📡 Collector    — ingests all signals, normalizes to SignalRecord
  🧠 Translator   — NL→DAG via LCM extension + pattern library lookup
  🗓️  Scheduler    — APScheduler backbone, manages cron + event triggers
  ⚡ Executor     — runs DAG nodes via execution_router
  📋 Auditor      — logs every step, feeds pattern library
  👔 ExecAdmin    — executive assistant agent (calendar, email, approvals)
  🔧 ProdOps      — production ops agent (deploy, health, incident, patch)
  🔴 HITL Gate    — human approval for stake=high/critical
  🌐 Rosetta      — coordinator: routes signals→agents, translates layers

## Section D: Executive Admin Tasks

  schedule_meeting     | "Schedule a meeting with X" | Calendar + invite
  triage_email         | New email arrives            | Classify + draft reply
  generate_report      | "Send weekly summary"        | Aggregate + email PDF
  approve_request      | Approval queue item          | Review + route or escalate
  brief_executive      | Morning trigger (8am)        | Collect signals + summarize
  draft_communication  | "Draft email to team re X"   | LLM compose + human review

## Section E: Production Tasks

  deploy_patch         | Git push to main             | Build + test + deploy
  health_watchdog      | Every 5 min                  | Check all services + auto-heal
  incident_response    | Error spike detected         | Classify + runbook + alert
  self_patch_cycle     | Daily 3am                    | run_autonomous_cycle(dry_run=False)
  log_rotation         | Weekly                       | Archive + compress old logs
  capacity_alert       | RAM/CPU >85%                 | Scale warning + auto-throttle

## Section F: Patch Roadmap (Build Order)

PATCH-112 | SignalCollector
  src/signal_collector.py
  Collects all signals → normalizes → SQLite signal_records table
  API: GET /api/signals/latest, POST /api/signals/ingest

PATCH-113 | WorkflowDAGEngine  
  src/workflow_dag.py
  Defines DAGNode, DAGGraph, DAGExecutor
  Runs DAG via execution_router, logs to workflow_runs table
  API: POST /api/workflow/build, POST /api/workflow/run/{dag_id}

PATCH-114 | NLWorkflowParser (LCM extension)
  src/nl_workflow_parser.py
  Extends LCM: NL → structured WorkflowSpec → DAGGraph
  Uses pattern library for known intents
  API: POST /api/nlwf/parse, POST /api/nlwf/build

PATCH-115 | RosettraCore (Swarm Coordinator)
  src/rosetta_core.py
  Routes signals→agents, maintains swarm state
  Applies translation layers: past_patterns → present_context → legacy_update
  API: GET /api/rosetta/status, POST /api/rosetta/route

PATCH-116 | ExecAdminAgent
  src/exec_admin_agent.py
  Handles: calendar, email triage, reports, morning brief
  Triggered by schedule + NL + incoming signals
  API: POST /api/exec/brief, POST /api/exec/schedule, POST /api/exec/triage

PATCH-117 | ProdOpsAgent
  src/prod_ops_agent.py
  Handles: deploy, health watchdog, incident response, self-patch
  Triggered by git webhooks + hardware telemetry + cron
  API: POST /api/prodops/deploy, GET /api/prodops/status

PATCH-118 | SwarmScheduler
  src/swarm_scheduler.py
  APScheduler-backed: cron + event + NL-specified schedules
  Manages all agent trigger schedules in one place
  API: GET /api/scheduler/jobs, POST /api/scheduler/add, DELETE /api/scheduler/job/{id}

PATCH-119 | PatternLibrary
  src/pattern_library.py
  Learns from workflow outcomes → indexes by intent class
  Provides ranked DAG templates for known patterns
  API: GET /api/patterns/lookup?intent=X, POST /api/patterns/record

PATCH-120 | HITLGate (Human-in-Loop)
  src/hitl_gate.py  (extend existing HITLExecutionGate)
  Stakes high/critical → pause DAG → notify human → await approval
  Approval via API or Telegram/email channel
  API: GET /api/hitl/pending, POST /api/hitl/approve/{task_id}

PATCH-121 | SwarmDashboard
  murphy_swarm_dashboard.html
  Live view: all agent statuses, active workflows, signal feed,
  pattern library size, HITL queue, scheduler jobs
  WS: /ws/swarm — real-time push

## Build Sequence Logic
112 first — nothing works without signals.
113 second — DAG engine is the execution backbone.
114 third — NL parsing needs the DAG engine to emit into.
115 fourth — Rosetta needs agents (112-114) to coordinate.
116/117 fifth — domain agents need Rosetta to route them.
118 sixth — Scheduler needs agents to schedule.
119 seventh — Pattern library needs workflow runs to learn from.
120 eighth — HITL extends existing gate with DAG integration.
121 last — Dashboard needs all other systems live to display.
