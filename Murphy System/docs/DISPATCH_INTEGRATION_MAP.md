# Dispatch Integration Map

**Murphy System — Unified Tool-Calling Engine**  
*Version 1.0 | © 2020 Inoni Limited Liability Company*

---

## Overview

**Dispatch** is Murphy System's unified tool-calling layer—a central nervous system that routes actions from agents, LLMs, humans, shadow agents, avatars, and ambient context modules to concrete system operations. Think of it as a universal RPC (Remote Procedure Call) mechanism with built-in safety rails, approval workflows, and natural language activation.

Every tool call flows through Dispatch, ensuring:
- **Auditability** — every call logged to DB with caller, args, result, duration
- **Safety** — HITL approval tiers prevent unsafe autonomous actions
- **Discoverability** — tools self-describe via JSON schema for LLM consumption
- **Modularity** — handlers soft-import their dependencies; failures are graceful
- **Observability** — live log panel + MultiCursor workspace snapshots

Dispatch currently powers 14 built-in tools across 6 categories (comms, meetings, system, analysis, memory, llm, org), with clear pathways to integrate 30+ more modules and bots.

---

## Approval Tiers

Every tool declares an `approval_tier` controlling when human-in-the-loop (HITL) approval is required:

### 1. **none** — Fully autonomous
No approval needed. Safe read-only operations.

**Examples:**
- `system.health` — read DB status, tool count, pending approvals

### 2. **platform** — MSS-gated autonomous
Dispatch automatically checks content quality via Murphy Sentiment Score (MSS). If score < 0.3 (poor quality/potentially harmful), the call is queued for approval. Otherwise, it executes autonomously.

**Examples:**
- `comms.send_im` — IM messages auto-checked for toxicity/spam
- `comms.start_voice_call` — voice calls auto-checked for appropriateness
- `analysis.run` — cognitive analysis tasks
- `memory.store` — storing agent memories
- `llm.query` — LLM inference calls
- `shadow.observe` — shadow agent observation mode

**Rationale:** Platform-tier tools are low-risk when content is appropriate, but could cause harm if abused. MSS acts as a soft gate—most calls pass through, but malicious/low-quality ones get caught.

### 3. **user** — Requires user approval
Murphy user (operator/admin) must explicitly approve before execution.

**Examples:**
- `comms.send_email` — email has broader reach than IM
- `comms.broadcast` — system-wide announcements
- `meeting.start` — starting meetings consumes calendar slots
- `meeting.end` — ending meetings affects participants
- `shadow.propose` — shadow agent proposals need review
- `org.escalate` — escalating org chart issues

**Rationale:** User-tier tools have business impact or affect multiple people. The Murphy operator should review and approve.

### 4. **customer** — Requires external customer approval
For enterprise/SaaS deployments: Murphy proposes an action, customer approves via external portal. Not yet implemented (reserved for future multi-tenant features).

**Examples (future):**
- `invoice.send` — sending invoices to external customers
- `campaign.launch` — launching marketing campaigns
- `contract.sign` — digital contract signing

---

## Voice / Natural Language Activation

Dispatch now supports natural language input—speak to Murphy in plain English, and Dispatch will:
1. Parse your intent using keyword/pattern matching (falls back from NLQueryEngine if available)
2. Identify the target tool
3. Extract arguments from context
4. Queue the tool call for execution (subject to approval tier)

### Supported Phrases

| You say | Dispatch calls |
|---------|---------------|
| "Send an IM to alice: report is ready" | `comms.send_im` |
| "Email the team: deadline is Friday" | `comms.send_email` |
| "Call alice" | `comms.start_voice_call` |
| "Video call with alice, bob, carol" | `comms.start_video_call` |
| "Broadcast: system maintenance tonight" | `comms.broadcast` |
| "Start a meeting with alice and bob about Q3" | `meeting.start` |
| "Check system health" | `system.health` |
| "Take a snapshot" | *(returns None — use MultiCursor directly)* |

### API Endpoints

- **POST /api/dispatch/nl** — body: `{text: str, caller_id?: str}`
- **POST /api/dispatch/voice** — body: `{transcript: str, caller_id?: str}` (same as /nl)

### UI Integration

The `dispatch.html` UI now includes a **Voice / Natural Language Activation** panel where you can type or paste voice transcripts. Perfect for prototyping agent workflows or testing Murphy's comprehension.

---

## MultiCursor — Workspace Snapshot

Before executing complex agentic tasks, call **MultiCursor** to take a simultaneous snapshot of system state across all relevant domains. This is analogous to `playwright-browser_snapshot`—giving the agent full situational awareness before acting.

### Domains

MultiCursor snapshots 10 domains:
1. **im** — IM thread count (filtered by user if specified)
2. **meetings** — active/scheduled meetings
3. **calls** — active voice/video calls (ringing, active, on_hold)
4. **email** — inbox count (per user)
5. **ambient** — recent ambient context entries + stats
6. **shadow** — shadow agent status
7. **automation** — comms automation rule count
8. **moderator** — user count + recent broadcast history
9. **system** — DB status, tool count, pending approval count
10. **approvals** — list of pending HITL approvals

### Usage

```python
from src.dispatch import cursor_context

# Take snapshot of all domains
snap = cursor_context.snapshot()
print(snap["cursor_id"])  # unique ID for this snapshot
print(snap["domains"]["system"])  # system state

# Take snapshot of specific domains for a user
snap = cursor_context.snapshot(domains=["im", "meetings", "email"], user="alice")

# Format for agent consumption (compact text summary)
text = cursor_context.format_for_agent(snap)
# Pass `text` as context to LLM or agent
```

### API Endpoint

- **POST /api/dispatch/cursor** — body: `{domains?: list, user?: str}`
  - Returns: `{cursor_id: str, timestamp: str, domains: {...}}`

### UI Integration

The `dispatch.html` UI includes a **MultiCursor** panel where you can:
- Select domains (checkboxes for each of the 10 domains)
- Filter by user (optional)
- Take snapshot (rendered as JSON tree)
- Copy formatted snapshot to clipboard for pasting into agent prompts

---

## Already Integrated Modules

The following Murphy System modules are **already wired** into Dispatch:

### Comms Hub
| Tool | Tier | Description |
|------|------|-------------|
| `comms.send_im` | platform | Send instant message |
| `comms.send_email` | user | Send email |
| `comms.start_voice_call` | platform | Initiate voice call |
| `comms.start_video_call` | platform | Initiate video call |
| `comms.broadcast` | user | System-wide announcement |

**Source:** `src/communication_hub.py` (IMStore, EmailStore, CallStore, ModConsole)

### Meetings Bridge
| Tool | Tier | Description |
|------|------|-------------|
| `meeting.start` | user | Start meeting with participants |
| `meeting.end` | user | End meeting by ID |

**Source:** `src/meetings_bridge.py` (MeetingsBridge)

### System Health
| Tool | Tier | Description |
|------|------|-------------|
| `system.health` | none | Check DB status + tool count |

**Source:** `src/db.py` (check_database)

### Analysis
| Tool | Tier | Description |
|------|------|-------------|
| `analysis.run` | platform | Cognitive analysis task |

**Source:** `bots/analysisbot/` (AnalysisBot, soft-imported)

### Memory
| Tool | Tier | Description |
|------|------|-------------|
| `memory.store` | platform | Store key-value memory with tags |
| `memory.recall` | platform | Recall memory by query |

**Source:** `bots/memory_cortex_bot.py` (MemoryCortexBot, soft-imported)

### LLM
| Tool | Tier | Description |
|------|------|-------------|
| `llm.query` | platform | LLM inference call |

**Source:** `src/llm_controller.py` (LLMController, soft-imported)

### Org Chart
| Tool | Tier | Description |
|------|------|-------------|
| `org.check_permission` | platform | Check permission for node+action |
| `org.escalate` | user | Escalate issue to higher org level |

**Source:** `src/org_chart_enforcement.py` (OrgChartEnforcement, soft-imported)

---

## Recommended Integrations

The following modules/bots are **strong candidates** for Dispatch integration. Each entry includes recommended tool names, approval tiers, and integration notes.

### High Priority (Core System Integration)

#### 1. **Ambient Intelligence**
**Source:** `src/ambient_synthesis.py` (AmbientSynthesisEngine)

| Tool | Tier | Description |
|------|------|-------------|
| `ambient.synthesize` | platform | LLM-powered insight synthesis from context |
| `ambient.query` | platform | Query ambient context store |

**Why:** Ambient context is already partially wired (MultiCursor reads from it). Full tool integration lets agents trigger synthesis on-demand.

**Integration:** Soft-import `AmbientSynthesisEngine`, call `synthesize(context_window)` and `query(query_text)`.

#### 2. **Shadow Agent**
**Source:** `src/shadow_agent_integration.py` (ShadowAgentIntegration)

| Tool | Tier | Description |
|------|------|-------------|
| `shadow.observe` | platform | Set shadow agent to observe mode |
| `shadow.propose` | user | Shadow proposes an action for approval |
| `shadow.clarify` | platform | Shadow asks clarifying question |

**Why:** Shadow agents need controlled autonomy—they observe, clarify, and propose, but never act without approval.

**Integration:** Already stubbed in original dispatch.py. Implement handlers calling ShadowAgentIntegration methods.

#### 3. **Avatar Comms**
**Source:** `src/avatar_integration.py` (if exists) or similar

| Tool | Tier | Description |
|------|------|-------------|
| `avatar.speak` | platform | Avatar speaks text (TTS) |
| `avatar.gesture` | platform | Avatar performs gesture |

**Why:** Avatars are Murphy's embodied interface. Tool integration lets agents trigger avatar actions.

**Integration:** Soft-import avatar controller, call `speak(text)` and `gesture(gesture_name)`.

#### 4. **Agent Monitor Dashboard**
**Source:** `src/agent_monitor_dashboard.py`

| Tool | Tier | Description |
|------|------|-------------|
| `agent.status` | none | Get live agent status |
| `agent.pause` | user | Pause an agent |
| `agent.resume` | user | Resume a paused agent |

**Why:** Observability + control. Agents can check their own status or request pauses.

**Integration:** Soft-import dashboard, call `get_agent_status(agent_id)`, `pause_agent(agent_id)`, `resume_agent(agent_id)`.

#### 5. **Agent Run Recorder**
**Source:** `src/agent_run_recorder.py`

| Tool | Tier | Description |
|------|------|-------------|
| `agent.record` | platform | Record telemetry event |
| `agent.get_recordings` | none | Get recorded run data |

**Why:** Agents self-report their actions for replay/debugging.

**Integration:** Soft-import recorder, call `record_event(agent_id, event_type, data)`, `get_recordings(agent_id)`.

---

### Medium Priority (Bot Integration)

#### 6. **Meeting Notes Bot**
**Source:** `bots/meeting_notes_bot/`

| Tool | Tier | Description |
|------|------|-------------|
| `meeting.notes` | platform | Generate meeting notes from transcript |
| `meeting.summarize` | platform | Summarize meeting by ID |

**Why:** Automate post-meeting note generation.

**Integration:** Soft-import bot, call `generate_notes(transcript)`.

#### 7. **Clarifier Bot**
**Source:** `bots/clarifier_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `ai.clarify` | platform | Generate clarifying questions |

**Why:** When agents encounter ambiguity, they can invoke the clarifier.

**Integration:** Soft-import bot, call `clarify(context, ambiguity)`.

#### 8. **Triage Bot**
**Source:** `bots/triage_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `issue.triage` | platform | Categorize and prioritize issue |

**Why:** Automate issue intake.

**Integration:** Soft-import bot, call `triage(issue_text)`.

#### 9. **Coding Bot**
**Source:** `bots/coding_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `code.generate` | user | Generate code from spec |
| `code.review` | platform | Review code for issues |

**Why:** Code generation requires approval (high risk); review is safe.

**Integration:** Soft-import bot, call `generate(spec)`, `review(code)`.

#### 10. **Ghost Controller Bot**
**Source:** `bots/ghost_controller_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `ghost.learn` | platform | Learn ADHD-aware behavior pattern |
| `ghost.suggest` | platform | Suggest next action based on context |

**Why:** Accessibility—Murphy adapts to ADHD users.

**Integration:** Soft-import bot, call `learn_pattern(user_id, behavior)`, `suggest_action(user_id, context)`.

#### 11. **Polyglot Bot**
**Source:** `bots/polyglot_bot/`

| Tool | Tier | Description |
|------|------|-------------|
| `translate.text` | platform | Translate text between languages |

**Why:** Multilingual comms.

**Integration:** Soft-import bot, call `translate(text, target_lang, source_lang=None)`.

#### 12. **Visualization Bot**
**Source:** `bots/visualization_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `chart.generate` | platform | Generate chart from data |

**Why:** Data-driven agent outputs.

**Integration:** Soft-import bot, call `generate_chart(data, chart_type)`.

#### 13. **Simulation Bot**
**Source:** `bots/simulation_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `sim.run` | platform | Run simulation with parameters |

**Why:** Agent-driven scenario planning.

**Integration:** Soft-import bot, call `run_simulation(params)`.

#### 14. **Feedback Bot**
**Source:** `bots/feedback_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `feedback.submit` | platform | Submit user feedback |
| `feedback.get` | none | Get feedback history |

**Why:** Close the feedback loop.

**Integration:** Soft-import bot, call `submit(user_id, message)`, `get_feedback(user_id)`.

#### 15. **Engineering Bot**
**Source:** `bots/engineering_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `engineering.calculate` | platform | Perform engineering calculation |

**Why:** Technical calculations on-demand.

**Integration:** Soft-import bot, call `calculate(formula, inputs)`.

#### 16. **Commissioning Bot**
**Source:** `bots/commissioning_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `commission.task` | user | Commission a task (e.g., hardware config) |

**Why:** High-stakes tasks need approval.

**Integration:** Soft-import bot, call `commission(task_spec)`.

#### 17. **Kiren (NLG)**
**Source:** `bots/kiren_speak.py`, `bots/kiren/`

| Tool | Tier | Description |
|------|------|-------------|
| `ai.speak` | platform | Generate natural language via local model |

**Why:** Local LLM-powered NLG for privacy-sensitive contexts.

**Integration:** Soft-import Kiren, call `speak(prompt)`.

#### 18. **Scheduling Bot**
**Source:** `bots/scheduling_bot.py` (if exists)

| Tool | Tier | Description |
|------|------|-------------|
| `schedule.create` | user | Create calendar event |
| `schedule.cancel` | user | Cancel calendar event |

**Why:** Calendar management.

**Integration:** Soft-import bot, call `create_event(title, start, end, participants)`, `cancel_event(event_id)`.

#### 19. **Anomaly Watcher Bot**
**Source:** `bots/anomaly_watcher_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `anomaly.check` | platform | Check for statistical anomalies in data |

**Why:** Proactive monitoring.

**Integration:** Soft-import bot, call `check(data_stream)`.

#### 20. **Memory Manager Bot**
**Source:** `bots/memory_manager_bot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `memory.manage` | platform | Embedding-based memory search |

**Why:** Semantic memory recall (upgrade from simple key-value).

**Integration:** Soft-import bot, call `search_embedding(query_text)`.

---

### Low Priority (Specialized Integration)

#### 21. **Campaign Orchestrator**
**Source:** `src/campaign_orchestrator.py`

| Tool | Tier | Description |
|------|------|-------------|
| `campaign.start` | user | Start marketing campaign |
| `campaign.stop` | user | Stop campaign |

**Why:** Marketing automation needs oversight.

**Integration:** Soft-import orchestrator, call `start_campaign(config)`, `stop_campaign(id)`.

#### 22. **Durable Swarm Orchestrator**
**Source:** `src/durable_swarm_orchestrator.py`

| Tool | Tier | Description |
|------|------|-------------|
| `swarm.spawn` | user | Spawn agent swarm for task |
| `swarm.status` | none | Get swarm status |

**Why:** Multi-agent coordination.

**Integration:** Soft-import orchestrator, call `spawn_swarm(task_spec)`, `get_swarm_status(swarm_id)`.

#### 23. **Announcer Voice Engine**
**Source:** `src/announcer_voice_engine.py`

| Tool | Tier | Description |
|------|------|-------------|
| `voice.announce` | platform | TTS narration via MercyAnnouncer |

**Why:** Audio announcements for accessibility.

**Integration:** Soft-import engine, call `announce(text)`.

#### 24. **Matrix Bot / Chatbot**
**Source:** `bots/matrix_bot.py`, `bots/matrix_chatbot.py`

| Tool | Tier | Description |
|------|------|-------------|
| `matrix.send` | platform | Send message to Matrix room |
| `matrix.join` | user | Join Matrix room |

**Why:** External protocol integration.

**Integration:** Soft-import Matrix bot, call `send_message(room_id, text)`, `join_room(room_id)`.

#### 25. **Matrix HITL**
**Source:** `bots/matrix_hitl.py`

| Tool | Tier | Description |
|------|------|-------------|
| `hitl.notify` | platform | Notify user via Matrix for approval |

**Why:** External HITL approval channels.

**Integration:** Soft-import HITL bot, call `notify_approval_request(user_id, approval_data)`.

#### 26. **AionMind Core**
**Source:** `bots/aionmind_core.py`

| Tool | Tier | Description |
|------|------|-------------|
| `ai.orchestrate` | platform | Multi-bot query orchestration |

**Why:** Coordinate multiple bots for complex queries.

**Integration:** Soft-import AionMind, call `orchestrate(query, bots)`.

---

## Security Note

All **customer-tier** tools (external customer approval) are reserved for future enterprise/multi-tenant deployments. By default, Murphy operates in single-tenant mode where:
- `platform` tier = auto-approved with MSS gate
- `user` tier = Murphy operator approval
- `customer` tier = not available (would require external portal)

If you deploy Murphy as SaaS for external customers, you must:
1. Implement customer approval portal
2. Set appropriate tools to `customer` tier
3. Enforce customer opt-in for autonomous actions
4. Log all approvals for compliance

---

## Next Steps

1. **Integrate High-Priority Bots** — Start with ambient synthesis, shadow agent, and avatar tools (foundational).
2. **Expand Natural Language Parsing** — Wire in NLQueryEngine (already soft-imported) for richer intent understanding.
3. **Build HITL Notification Channel** — Integrate Matrix HITL bot to send approval requests to mobile/desktop.
4. **Customer Tier Implementation** — Design external approval portal for enterprise customers.
5. **Tool Discovery UI** — Add search/filter to dispatch.html tool catalog for easier navigation.
6. **Agent-Driven MultiCursor** — Train agents to proactively call MultiCursor before complex actions (analogous to browser agents calling `browser_snapshot`).

---

**Dispatch is the foundation for Murphy's agentic future.** Every new capability should wire through Dispatch—ensuring safety, auditability, and discoverability.

---

*Document Version: 1.0*  
*Last Updated: 2024*  
*Maintainer: Murphy System Core Team*
