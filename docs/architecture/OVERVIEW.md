## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MURPHY SYSTEM 1.0                            │
│                   Universal AI Automation System                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────────────┐
        │          REST API (FastAPI - Port 8000)             │
        │     src/runtime/app.py                              │
        └─────────────────────────────────────────────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
┌───────────────────────────┐        ┌─────────────────────────────┐
│   UNIVERSAL CONTROL PLANE │        │  INONI BUSINESS AUTOMATION  │
│  universal_control_plane.py│        │ inoni_business_automation.py│
├───────────────────────────┤        ├─────────────────────────────┤
│ • Sensor Engine           │        │ • Sales Engine              │
│ • Actuator Engine         │        │ • Marketing Engine          │
│ • Database Engine         │        │ • R&D Engine                │
│ • API Engine              │        │ • Business Management       │
│ • Content Engine          │        │ • Production Management     │
│ • Command Engine          │        └─────────────────────────────┘
│ • Agent Engine            │
└───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│             TWO-PHASE ORCHESTRATOR                            │
│              two_phase_orchestrator.py                        │
├───────────────────────────────────────────────────────────────┤
│  PHASE 1 (Generative Setup)    │  PHASE 2 (Production)       │
│  • Analyze request             │  • Load session             │
│  • Determine control type      │  • Execute with engines     │
│  • Select engines              │  • Deliver results          │
│  • Discover constraints        │  • Learn from execution     │
│  • Create ExecutionPacket      │  • Repeat on schedule       │
│  • Create session              │                             │
└───────────────────────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    CORE SYSTEMS LAYER                         │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│ Form   │ │Confid- │ │Execu-  │ │Learning│ │Supervisor  │
│ Intake │ │ence    │ │tion    │ │Engine  │ │System      │
│        │ │Engine  │ │Engine  │ │        │ │(HITL)      │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│                  SPECIALIZED SYSTEMS                          │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│Security│ │Integra-│ │Govern- │ │Module  │ │Swarm       │
│Plane   │ │tion    │ │ance    │ │Compiler│ │System      │
│        │ │Engine  │ │        │ │        │ │            │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────────┐
│              SUPPORT INFRASTRUCTURE                           │
└───────────────────────────────────────────────────────────────┘
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
│LLM     │ │Logging │ │Memory  │ │Domain  │ │70+ Bots    │
│Integr. │ │System  │ │System  │ │Expert  │ │            │
└────────┘ └────────┘ └────────┘ └────────┘ └────────────┘
```

### AionMind 2.0a Cognitive Pipeline (Embedded)

```
┌───────────────────────────────────────────────────────────────────┐
│                 AIONMIND 2.0a COGNITIVE PIPELINE                  │
│                  (Orchestrator-of-Orchestrators)                   │
├───────────────────────────────────────────────────────────────────┤
│  Layer 1: Context Engine     → ContextObject (structured input)   │
│  Layer 2: Capability Registry → 20+ bot capabilities auto-bridged │
│           Reasoning Engine   → Candidate ExecutionGraphObjects     │
│  Layer 3: RSC Integration    → Stability-gated expansion          │
│  Layer 4: Orchestration      → Graph execution with HITL gates    │
│  Layer 5: Memory (STM/LTM)  → Similarity search, archival        │
│  Layer 6: Optimization       → Conservative proposals only        │
├───────────────────────────────────────────────────────────────────┤
│  /api/execute  ──→  cognitive_execute() ──→  legacy fallback      │
│  /api/forms/*  ──→  cognitive_execute() ──→  legacy fallback      │
│  /api/aionmind/* ──→ dedicated 2.0 endpoints                     │
└───────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  Bot Inventory       RSC Controller      WorkflowDAGEngine
  (capability bridge)  (live wiring)       (backward compat)
```

---

