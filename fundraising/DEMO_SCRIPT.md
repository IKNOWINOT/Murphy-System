# Murphy System — 3-Minute AI Demo Script

> **Format:** Loom screen-share or live investor meeting.  
> **Runtime:** ~3 minutes. Every command below hits a **real AI endpoint** — no mocks, no slides.  
> **What the investor sees:** You type plain English → Murphy's AI builds a governed workflow → HITL gates fire → you approve → it executes. All live.

---

## Pre-Flight Checklist

Before recording or going live:

```bash
# 1. Start the server (skip if already running)
cd "Murphy System" && bash setup_and_start.sh

# 2. Confirm it's alive
curl -s http://localhost:8000/health | python3 -m json.tool
```

You should see `"status": "ok"`, active automations, pending HITL items, and live WebSocket/SSE subscriber counts. If you don't — the server isn't up yet.

**Environment keys required for live AI (set before starting):**
- `DEEPINFRA_API_KEY` — primary LLM (Llama 3.1 70B via DeepInfra)
- `TOGETHER_API_KEY` — fallback LLM (Together.ai)
- If neither is set, Murphy falls back to deterministic on-board templates (still works for the demo, just won't show LLM-generated names/descriptions).

**Browser tabs open:**
- `terminal_unified.html` — Murphy terminal UI
- `demo.html` — interactive demo page (backup)

**Kill notifications. Full-screen split: terminal + browser.**

---

## 0:00 – 0:30 — "What You're About to See"

**Say:**

> "This is Murphy System — an AI automation platform I built solo. 218,000 lines of Python, 1,122 modules, 8,843 passing tests. It converts plain English into governed, production-grade workflows using LLMs — and every high-stakes step requires human approval before it fires.
>
> What I'm about to show you is not a prototype or a Figma mock. These are real API calls against a running server with real AI behind them. Let me prove it."

---

## 0:30 – 0:50 — Prove the System Is Live (2 commands, 20 sec)

### Command 1: System health

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Expected output:**
```json
{
  "status": "ok",
  "version": "3.0.0",
  "env": "production",
  "active_automations": 12,
  "total_automations": 15,
  "tenants": 3,
  "campaigns": 5,
  "pending_hitl_items": 2,
  "sse_subscribers": 45,
  "ws_clients": 12,
  "ts": "2026-04-01T..."
}
```

**Say:** *"Live server. 12 active automations, 3 tenants, 2 items waiting for human approval right now, 45 live SSE subscribers. This is a production runtime."*

### Command 2: Rate governor (shows swarm-scale architecture)

```bash
curl -s http://localhost:8000/api/rate-governor/status | python3 -m json.tool
```

**Say:** *"Four traffic classes — human, swarm, sensor, safety — each rate-limited independently. Murphy is designed to handle multi-agent swarms and IoT sensor traffic at scale, not just one user clicking buttons."*

---

## 0:50 – 1:40 — AI Generates a Workflow from Plain English (50 sec)

This is the money shot. One curl command. The AI builds the whole thing.

### Command 3: NL → Automation (LLM-powered)

```bash
curl -s -X POST http://localhost:8000/api/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Set up a weekly revenue report that pulls from Stripe, aggregates by pricing tier, and sends a summary to Slack every Monday at 9am",
    "tenant_id": "tenant-001"
  }' | python3 -m json.tool
```

**While it runs (~2–5 sec, LLM is thinking), say:**

> *"I just described what I want in one sentence. Murphy's AI — Llama 3.1 70B via DeepInfra — is now generating the automation name, description, and a full milestone plan. No drag-and-drop. No connector wiring. Describe → execute."*

**Expected output (abbreviated):**
```json
{
  "id": "auto-a1b2c3",
  "name": "Weekly Revenue Report Pipeline",
  "description": "Automated weekly Stripe revenue aggregation by pricing tier...",
  "category": "notifications",
  "trigger_type": "schedule",
  "recurrence": "weekly",
  "llm_generated": true,
  "milestones": [
    {"id": "ms-001", "title": "Fetch Stripe Revenue Data", "status": "pending"},
    {"id": "ms-002", "title": "Aggregate by Pricing Tier", "status": "pending"},
    {"id": "ms-003", "title": "Format Summary Report", "status": "pending"},
    {"id": "ms-004", "title": "HITL Gate: Review Report", "status": "pending"},
    {"id": "ms-005", "title": "Send to Slack Channel", "status": "pending"}
  ],
  "cost_savings_monthly_usd": 480.0,
  "status": "active"
}
```

**Point at the output:**

> *"See `llm_generated: true`? That name, that description, those five milestones — all AI-generated from my one sentence. And look at milestone 4: 'HITL Gate: Review Report.' Murphy automatically inserted a human approval step before sending financial data externally. No other automation platform does that."*

---

## 1:40 – 2:10 — AI Builds a DAG with Dependencies (30 sec)

### Command 4: NL → Workflow DAG (structured execution graph)

```bash
curl -s -X POST http://localhost:8000/api/workflows/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Onboard a new enterprise client: collect requirements, create CRM record, run security review, configure access, send welcome package",
    "tenant_id": "tenant-001",
    "execute_immediately": false
  }' | python3 -m json.tool
```

**Expected output (abbreviated):**
```json
{
  "id": "wf-d4e5f6",
  "name": "Onboard A New Enterprise Client Workflow",
  "steps": [
    {"id": "step-001", "name": "Collect Client Requirements", "depends_on": [], "is_hitl": false},
    {"id": "step-002", "name": "Create CRM Record", "depends_on": ["step-001"], "is_hitl": false},
    {"id": "step-003", "name": "Run Security Review", "depends_on": ["step-002"], "is_hitl": false},
    {"id": "step-004", "name": "HITL Gate: Approve Access", "depends_on": ["step-003"], "is_hitl": true},
    {"id": "step-005", "name": "Configure System Access", "depends_on": ["step-004"], "is_hitl": false},
    {"id": "step-006", "name": "Send Welcome Package", "depends_on": ["step-005"], "is_hitl": false}
  ],
  "has_hitl_gates": true,
  "estimated_duration_seconds": 23,
  "status": "draft"
}
```

**Say:**

> *"That's a DAG — a directed acyclic graph. Six steps, each with explicit dependencies. Step 4 is a HITL gate: Murphy will not grant system access to a new client until a human reviews the security audit. This is a draft — I can execute it, and it'll run steps 1 through 3 automatically, then block at the gate and wait for me."*

---

## 2:10 – 2:30 — Execute the Workflow + Approve the HITL Gate (20 sec)

### Command 5: Execute the workflow

```bash
# Start execution — runs all non-HITL steps, blocks at gate
curl -s -X POST http://localhost:8000/api/workflows/wf-d4e5f6/execute | python3 -m json.tool
```

*(Use the actual `wf-*` ID from Command 4's response.)*

**Say:** *"Steps 1, 2, 3 are running now — automatically. Watch it block at the HITL gate."*

### Command 6: Approve the HITL step

```bash
# Approve the gate — execution resumes
curl -s -X POST http://localhost:8000/api/workflows/wf-d4e5f6/steps/step-004/approve \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "founder", "reason": "Security review passed"}' | python3 -m json.tool
```

**Say:**

> *"I just approved the gate. Steps 5 and 6 will now execute. This is how Murphy handles high-stakes decisions — it stops, asks, then continues. Every HITL event is logged, auditable, and SOC 2 compliant."*

---

## 2:30 – 2:50 — Show the HITL Queue + Bot Fleet (20 sec)

### Command 7: HITL queue (pending approvals)

```bash
curl -s "http://localhost:8000/api/hitl/queue?status=pending" | python3 -m json.tool
```

**Say:** *"This is the HITL queue — every pending approval across all automations and workflows. An industrial plant running Murphy would see SCADA valve commands waiting here for operator approval."*

### Command 8: Bot fleet status

```bash
curl -s http://localhost:8000/api/bots/status | python3 -m json.tool
```

**Say:** *"18 autonomous bots — scheduler, anomaly watcher, librarian, triage, engineering, security — all running. This is the multi-agent orchestration layer."*

---

## 2:50 – 3:00 — Close

**Say:**

> "Everything you just saw was live AI. Real LLM calls. Real workflow execution. Real human-in-the-loop gates. 218,000 lines of production Python, 1,122 modules, 8,843 tests, 90+ platform connectors — including SCADA, BACnet, and OPC UA — 14 web interfaces. Built by one person.
>
> I'm raising $500,000 on a SAFE at $5M to $7M cap. No discount. 18 months of runway. The first hire multiplies what you just saw.
>
> corey.gfc@gmail.com. The full codebase is open at github.com/IKNOWINOT/Murphy-System. Thank you."

---

## Bonus Commands (If You Have Extra Time or Investor Asks to See More)

### AI-generated proposal from an inbound RFP

```bash
curl -s -X POST http://localhost:8000/api/proposals/generate | python3 -m json.tool
```

> *"Murphy's AI just ingested a customer RFP, extracted requirements, and generated a full proposal — scope, architecture, investment estimate, timeline, ROI. That goes to the HITL queue for review before it's sent."*

### Demo deliverable — AI generates a document from NL

```bash
curl -s -X POST http://localhost:8000/api/demo/generate-deliverable \
  -H "Content-Type: application/json" \
  -d '{"query": "Create a compliance audit report for SOC 2 readiness"}' | python3 -m json.tool
```

> *"That just went through Murphy's 7-phase MFGC pipeline — intake, analysis, scoring, gating, risk index, librarian enrichment, output. The confidence score on that deliverable determines whether it auto-sends or waits for human review."*

### Inspect the AI pipeline trace

```bash
curl -s -X POST http://localhost:8000/api/demo/inspect \
  -H "Content-Type: application/json" \
  -d '{"query": "Run quarterly compliance audit"}' | python3 -m json.tool
```

> *"This shows exactly how Murphy routes a request through the MFGC pipeline — every phase, every score, every gate. Full transparency into how the AI makes decisions."*

### Show active verticals (10 business domains)

```bash
curl -s http://localhost:8000/api/verticals | python3 -m json.tool
```

> *"10 verticals: marketing, proposals, CRM, monitoring, industrial/SCADA, finance, security, content, communications, AI pipeline. Each can be activated independently. That's why we cover factory floor to content creator — it's the same governed engine across every domain."*

### Self-setup pipeline (Murphy bootstraps itself)

```bash
curl -s http://localhost:8000/api/pipeline/self-setup | python3 -m json.tool
```

> *"Murphy runs a 12-step self-setup pipeline to bootstrap its own operations. Six of those steps have HITL gates — it won't go live without human approval. This is the self-operating backbone."*

---

## Backup Lines (If Something Breaks)

**If the LLM call is slow (>5 sec):**
> *"Murphy is routing through Llama 3.1 70B on DeepInfra — that's a large model doing real inference, not a template. With a dedicated GPU endpoint, this is sub-2 seconds. What you're watching is the AI thinking."*

**If the server isn't responding:**
> *"The server needs a restart — let me show you the codebase while it comes back. 1,122 modules, 81 packages, 644 test files. Here's the terminal UI —"* (switch to `terminal_unified.html` which loads statically).

**If an LLM provider is down (no API key / DeepInfra outage):**
> *"The primary LLM provider is down. Murphy's circuit breaker already kicked in and switched to the fallback provider. If both are down, it falls back to deterministic on-board templates — it still generates the workflow, just without the LLM-powered naming. That's the resilience layer."*

**If asked "Is the AI actually running?":**
> *"Yes — check `llm_generated: true` in the response. That field is only set when the LLM actually runs. I can also show you the provider chain: DeepInfra primary, Together.ai fallback, Ollama local."*

**If asked about revenue:**
> *"Pre-revenue — intentionally. 18 months of building, not selling. This raise funds the first hire and 5 design partners. First revenue target: 6 months after close."*

---

## Recording Tips (Loom)

1. **1920×1080**, not 4K — Loom compresses better at standard res
2. Terminal font **≥16pt** — investors watch on laptops and phones
3. **Pause 1 second** after each curl response before speaking — let them read
4. Run each command **slowly** — copy-paste from a script, don't speed-type
5. Pre-run Commands 3 & 4 once before recording to **warm the LLM cache** — responses will be faster on the second call
6. End with **5 seconds face-on-camera** — it builds trust
7. Total file size target: **under 50MB** so it loads fast when investors click the link

---

## Quick Reference: All 8 Core Commands

| # | Command | What It Proves |
|---|---------|---------------|
| 1 | `GET /health` | Server is live, automations running, HITL items pending |
| 2 | `GET /api/rate-governor/status` | Swarm-scale architecture (4 traffic classes) |
| 3 | `POST /api/prompt` | **AI generates automation from plain English** (LLM-powered) |
| 4 | `POST /api/workflows/generate` | **AI builds a DAG with dependencies + HITL gates** |
| 5 | `POST /api/workflows/{id}/execute` | Workflow executes, blocks at HITL gate |
| 6 | `POST /api/workflows/{id}/steps/{id}/approve` | Human approves gate, execution resumes |
| 7 | `GET /api/hitl/queue` | Full HITL approval queue (industrial-grade governance) |
| 8 | `GET /api/bots/status` | 18 autonomous bots running (multi-agent orchestration) |

---

*Back to [Fundraising Plan](FUNDRAISING_PLAN.md) · [Investment Memo](INVESTOR_MEMO.md)*
