# Meeting Intelligence & Ambient Intelligence

**Murphy System — Shadow AI Collaborative Intelligence**
*© 2020 Inoni Limited Liability Company by Corey Post | License: BSL 1.1*

---

## Table of Contents

1. [Overview](#overview)
2. [Meeting Intelligence](#meeting-intelligence)
   - [Shadow AI Swarm Agents](#shadow-ai-swarm-agents)
   - [Session Flow](#session-flow)
   - [Draft Generation & Voting](#draft-generation--voting)
   - [Royalty & Licensing System](#royalty--licensing-system)
   - [Org Intelligence Accumulation](#org-intelligence-accumulation)
3. [Ambient Intelligence](#ambient-intelligence)
   - [6th Sense Architecture](#6th-sense-architecture)
   - [Context Collection](#context-collection)
   - [Synthesis Engine](#synthesis-engine)
   - [Delivery Pipeline](#delivery-pipeline)
4. [API Reference](#api-reference)
5. [UI Pages](#ui-pages)
6. [Ethical Safeguards](#ethical-safeguards)
7. [Integration Points](#integration-points)

---

## Overview

Murphy's collaborative intelligence layer transforms meetings and passive work context into proactive, organisation-owned intelligence. It operates on two levels:

| Layer | Trigger | Output | Delivery |
|---|---|---|---|
| **Meeting Intelligence** | Active sessions (30–60 min) | Drafts, decisions, risks, action plans | Meeting Intelligence page |
| **Ambient Intelligence** | Passive context (calendar, tasks, workspace) | Briefs, alerts, summaries | Email, UI stream |

Both layers accumulate into **Organisational Intelligence** — a reusable problem-solving capability that belongs to the organisation, not any individual.

---

## Meeting Intelligence

### Shadow AI Swarm Agents

During a meeting session in the Workspace or Community Forum, a swarm of shadow agents activates. Each agent operates independently but is orchestrated collectively:

| Agent Role | What It Watches | What It Produces |
|---|---|---|
| **Pattern Agent** | Recurring themes, words, priorities | Insight cards highlighting consensus |
| **Risk Agent** | Blockers, dependencies, concerns | Risk flags with severity |
| **Action Agent** | Commitments, assignments, deadlines | Action items with owners |
| **Synthesis Agent** | Full conversation arc | Drafts (action plan, decisions, proposals, risks) |
| **Confidence Agent** | Level of agreement in conversation | Live confidence meter (0–100%) |

All agents are subject to **ethical safeguards** — see [Ethical Safeguards](#ethical-safeguards).

### Session Flow

```
1. User starts Shadow AI session in Workspace (/ui/workspace)
   └─ Shadow AI panel opens, agents activate

2. Live transcription feeds all agents simultaneously
   └─ Insight cards surface in real-time

3. Group confidence meter fluctuates as discussion evolves
   └─ High variance = low confidence; convergence = rising confidence

4. At end of session, user clicks "Generate Drafts"
   └─ Synthesis Agent produces 4 document types

5. Session data saved to localStorage + API
   └─ Navigates to Meeting Intelligence (/ui/meeting-intelligence?session=<id>)

6. Participants vote on drafts
   └─ Accepted drafts trigger royalty credits
   └─ Org intelligence counter increments
```

### Draft Generation & Voting

The Shadow AI session automatically produces up to 4 draft types:

| Draft Type | Contents | Typical Length |
|---|---|---|
| **Action Plan** | Prioritised next steps, owners, timelines | 200–400 words |
| **Decision Record** | What was decided, context, consequences | 150–300 words |
| **Proposal** | Ideas for implementation with rationale | 200–500 words |
| **Risk Register** | Identified risks, severity, mitigations | 100–300 words |

**Voting:** Each draft can be voted `Accept`, `Revise`, or `Reject` by any participant. A consensus bar shows the team's aggregate vote. Only accepted drafts trigger royalty credits.

> **Important:** All drafts are **suggestions only**. No draft is implemented without explicit human acceptance.

### Royalty & Licensing System

Under BSL 1.1, the royalty system ensures that shadow agents (and their users) are compensated when their insights are reused:

```
Shadow Agent contributes insight
  └─ Insight accepted by team → earns Ω credits

Organisation reuses a capability derived from that session
  └─ Micro-licensing fee triggered
  └─ Fee distributed proportionally:
       ├─ Contributing shadow agents (tracked by agent ID)
       └─ Their users (by percentage of contribution)

Royalty ledger maintained in:
  ├─ localStorage (client-side, per device)
  └─ /api/ambient/royalty (server-side, persistent)
```

**Credit Unit:** `Ω` (Murphy Omega credit). Conversion to real-world value is at the organisation's discretion and subject to the BSL 1.1 license terms.

**Higher ethical implications:** Because these agents operate on behalf of people, they are held to stricter ethical standards than standard automation. See [Ethical Safeguards](#ethical-safeguards).

### Org Intelligence Accumulation

Every completed session adds to the organisation's problem-solving capability:

```
Session completed
  └─ +1 org session counter
  └─ Accepted insights → org insight library
  └─ Accepted drafts → org draft library
  └─ Capability patterns extracted → org capability map

Organisation capability map grows over time:
  └─ Pattern: "Onboarding friction" appeared in 3 sessions
     → Org capability: Onboarding Analysis (3 sessions deep)
  └─ Pattern: "Phased rollout" appeared in 2 sessions
     → Org capability: Launch Planning (2 sessions deep)
```

The capability map is visible at `/ui/meeting-intelligence` under the **Org Intelligence** tab.

---

## Ambient Intelligence

### 6th Sense Architecture

Ambient Intelligence is a **passive, silent layer** that observes context across all connected systems without requiring any request or prompt. It works around a moving target — your day — and forms what you need before you know you need it.

```
Context Sources          Synthesis Engine          Delivery Pipeline
─────────────────        ─────────────────        ──────────────────
📅 Calendar     ──────►  Pattern matching  ──────► UI Stream
✅ Tasks        ──────►  Signal fusion     ──────► Email (proactive)
💬 Workspace    ──────►  Confidence score  ──────► Notification
🧠 Meetings     ──────►  Package builder   ──────► Royalty log
```

The engine runs entirely in the browser background via `static/murphy_ambient.js`, with server-side persistence via the `/api/ambient/*` endpoints.

### Context Collection

The `ContextCollector` polls four sources every 60 seconds:

| Source | Signal Types | Example |
|---|---|---|
| **Calendar** | `upcoming_meeting`, `post_meeting` | Meeting in 47 min → prepare brief |
| **Meeting Intelligence** | `pending_votes`, `org_milestone` | 2 drafts pending vote |
| **Tasks** | `overdue`, `unassigned` | 3 overdue tasks → alert |
| **Workspace** | `high_unread` | 25 unread messages → digest |

All signals are pushed to `/api/ambient/context` for server-side enrichment and persistence.

### Synthesis Engine

The `SynthesisEngine` runs every 90 seconds, cross-referencing collected signals:

| Combination | Output | Confidence |
|---|---|---|
| upcoming_meeting + pending_votes + overdue | Pre-meeting brief | High (85–92%) |
| unassigned + overdue | Risk alert + responsibility matrix | High (88–94%) |
| org_milestone | Org capability report | Very high (95%+) |
| post_meeting | Post-meeting summary + action items | Medium (70–80%) |

Only insights above the configured **confidence threshold** (default: 65%) are delivered.

### Delivery Pipeline

The `DeliveryPipeline` routes synthesised insights to channels:

| Channel | When Used | Respects Shadow Mode |
|---|---|---|
| **UI Stream** | Always (ambient page) | No |
| **Email** | When `emailEnabled = true` | Yes (email only in shadow mode) |
| **Notification** | Future: browser push / in-app | N/A |

**Shadow Mode:** When enabled, all UI notifications are suppressed. Only email delivery is used. True 6th sense — you receive the output without seeing the process.

**Frequency settings:**
- `realtime` — Deliver immediately as synthesised
- `hourly` — Bundle into hourly digest
- `daily` — Morning brief (default)
- `weekly` — Weekly summary

---

## API Reference

### Meeting Intelligence

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/meeting-intelligence/drafts` | Save a draft from a Shadow AI session |
| `POST` | `/api/meeting-intelligence/vote` | Record a vote on a draft |
| `POST` | `/api/meeting-intelligence/email-report` | Queue a session report for email delivery |
| `GET` | `/api/meeting-intelligence/sessions` | List all sessions |

### Ambient Intelligence

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ambient/context` | Push context signals from the engine |
| `POST` | `/api/ambient/insights` | Push synthesised insights |
| `POST` | `/api/ambient/deliver` | Trigger delivery via a channel |
| `POST` | `/api/ambient/royalty` | Log a royalty record |
| `GET` | `/api/ambient/settings` | Get engine settings |
| `POST` | `/api/ambient/settings` | Save engine settings |

---

## UI Pages

| Route | File | Description |
|---|---|---|
| `/ui/workspace` | `workspace.html` | Shadow AI session panel (live transcription, swarm agents, drafts) |
| `/ui/community` | `community_forum.html` | Shadow AI session panel for community meetings |
| `/ui/meeting-intelligence` | `meeting_intelligence.html` | Post-meeting review: drafts, voting, royalties, org intelligence |
| `/ui/ambient` | `ambient_intelligence.html` | 6th sense dashboard: context stream, proactive feed, email log, settings |
| `/ui/calendar` | `calendar.html` | Scheduling, meeting inviter (context source for ambient engine) |
| `/ui/management` | `management.html` | Task boards (context source for ambient engine) |

---

## Ethical Safeguards

Shadow agents and ambient intelligence operate under strict ethical constraints:

### 1. Suggestion-Only Principle
All shadow AI outputs are **suggestions only**. No draft, action, or decision is implemented without explicit human acceptance. The system cannot autonomously execute anything.

### 2. Higher Safety Standards
Because these agents work on behalf of people in collaborative contexts, they are subject to stricter ethical and safety standards than standard automation:
- No suggestion may demean, exclude, or discriminate against any participant
- Risk flags must be proportionate and evidence-based
- Confidence scores must be honest (not inflated)

### 3. Legal Compliance
- All session data belongs to the **organisation** that scheduled the meeting
- Shadow agents do not retain personal data beyond the session
- Royalty ledgers are subject to BSL 1.1 license terms
- GDPR/CCPA: participants can request deletion of their transcript contributions

### 4. Transparency
- The Shadow AI panel is always visible — nothing happens in a hidden background
- Ambient Intelligence settings are user-controlled and can be paused/stopped at any time
- The Delivery Log shows every email sent by the ambient engine

### 5. Consent
- Shadow AI session must be explicitly started by a user — it cannot auto-start
- Ambient Intelligence can be fully disabled per-user in settings
- Shadow mode is opt-in only

---

## Integration Points

| System | Integration | Status |
|---|---|---|
| **Calendar** (`/ui/calendar`) | Event proximity triggers ambient briefs | ✅ Implemented |
| **Management** (`/ui/management`) | Overdue/unassigned tasks trigger alerts | ✅ Implemented |
| **Meeting Intelligence** (`/ui/meeting-intelligence`) | Session data feeds ambient context | ✅ Implemented |
| **Workspace** (`/ui/workspace`) | Shadow AI swarm panel | ✅ Implemented |
| **Community Forum** (`/ui/community`) | Shadow AI swarm panel | ✅ Implemented |
| **Email** (`/api/email/send`) | Ambient delivery pipeline | ✅ Stub ready |
| **Prezi** | Presentation integration in call overlay | ✅ Iframe embed |
| **Murphy Librarian** | Generate suggestions via `/api/librarian/query` | ✅ Live |
| **Royalty / Wallet** (`/ui/wallet`) | Omega credit balance from royalty ledger | 🔜 Planned |

---

*This document is part of the Murphy System user guide. For API details, see [API Reference](../user_guides/API_REFERENCE.md). For system architecture, see [Architecture Overview](../architecture/).*
