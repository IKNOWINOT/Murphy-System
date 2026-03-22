# Murphy System — Communication Hub

**Module:** `src/communication_hub.py`  
**Router:** `src/comms_hub_routes.py`  
**UI:** `communication_hub.html` at `/ui/comms-hub`  
**Tests:** `tests/test_communication_hub.py` (83 tests)  
**ORM Models:** `src/db.py` (`IMThread`, `IMMessage`, `CallSession`, `EmailRecord`,
`CommsAutomationRule`, `CommsModAuditLog`, `CommsBroadcast`, `CommsUserProfile`)

---

## Overview

The Communication Hub is Murphy System's unified onboard communication layer.  It
provides:

| Channel | Capability |
|---------|------------|
| **Instant Messaging (IM)** | Multi-account thread-based chat; direct and group threads; emoji reactions; per-message automod |
| **Voice Calls** | WebRTC-ready signalling: SDP offer/answer + ICE candidate forwarding, call lifecycle management, voicemail URL storage |
| **Video Calls** | Same signalling model as voice; separate session namespace |
| **Email** | Compose and send with to/cc/bcc, per-user inbox + outbox, mark-read, per-email automod |
| **Automation Rules** | Event-driven rules: `on_message`, `on_email`, `on_missed_call`, `on_voicemail`, `scheduled`; keyword and automod-flag conditions |
| **Moderator Console** | Discord-style controls: warn / mute / kick / ban; custom blocked-word lists; multi-platform broadcast; full persisted audit log |

All data is stored in SQLite via SQLAlchemy ORM.  Messages, call sessions, and emails
survive server restarts and are immediately visible across all active accounts sharing
the same deployment.

---

## Quick Start

### 1. Open the UI

Navigate to `/ui/comms-hub` after logging in.  The panel auto-detects your account
from `/api/profiles/me`.

### 2. Start a conversation

1. Click **+ New Thread** in the IM panel.
2. Enter the account usernames / emails of the other participants.
3. Select *Direct* (two participants) or *Group* (three or more).
4. Click **Create** — the thread appears immediately in the left sidebar.

Messages sent in the thread are visible to **all participants** from their own accounts.
The thread and every message are persisted to `murphy_logs.db` and survive a server
restart.

### 3. Make a voice or video call

1. Switch to the **Voice Calls** or **Video Calls** tab.
2. Click **+ New Call** and enter the participant usernames.
3. The session enters `ringing` state — the callee sees it in their own session list and
   clicks **Answer**.
4. SDP offers, SDP answers, and ICE candidates can be submitted via the API for full
   WebRTC peer-to-peer establishment (the hub stores and relays signalling data only;
   media flows directly between peers).

### 4. Send an email

1. Switch to the **Email** tab.
2. Click **✏️ Compose** and fill in *To*, *Subject*, and *Body*.
3. Click **📤 Send**.  The email appears in the recipient's **Inbox** and in your
   **Outbox** immediately.

### 5. Broadcast as a moderator

1. Switch to the **Moderator Console** tab.
2. In the **Broadcast** panel, toggle the target platforms (IM, Email, Slack, …).
3. Type your message, choose a priority, and click **📢 Broadcast**.
4. The hub delivers the message to every registered channel on each selected platform
   and records the result in the **Broadcast History**.

---

## Persistence

All communication data is stored in SQLite (default: `murphy_logs.db`).  A PostgreSQL
database is used automatically when the `DATABASE_URL` environment variable is set.

| Table | Description |
|-------|-------------|
| `comms_im_threads` | Thread metadata (id, name, type, participants) |
| `comms_im_messages` | Messages (id, thread_id, sender, content, reactions, automod) |
| `comms_call_sessions` | Call sessions (type, caller, participants, state, SDP, ICE, duration) |
| `comms_emails` | Emails (sender, recipients, cc, bcc, subject, body, read_by, automod) |
| `comms_automation_rules` | Automation rules (trigger, channel, conditions, enabled, fire_count) |
| `comms_user_profiles` | Moderated user profiles (role, muted, banned, warnings) |
| `comms_mod_audit` | Moderator audit log (actor, action, target, reason, timestamp) |
| `comms_broadcasts` | Broadcast history (sender, platforms, results, created) |

Tables are created automatically by `create_tables()` on server startup (or when
`communication_hub.py` is first imported).

---

## API Reference

### Instant Messaging

```
POST /api/comms/im/threads
  Body: { participants: [str], name?: str, type?: "direct"|"group" }
  → { ok: true, thread: { id, name, type, participants, created } }

GET  /api/comms/im/threads?user=<username>
  → { threads: [...] }

GET  /api/comms/im/threads/{tid}
  → { thread: {...} }

POST /api/comms/im/threads/{tid}/messages
  Body: { sender: str, content: str, attachments?: [str] }
  → { ok: true, message: { id, sender, content, automod, ... } }

GET  /api/comms/im/threads/{tid}/messages?limit=50
  → { messages: [...] }

POST /api/comms/im/threads/{tid}/messages/{mid}/reactions
  Body: { emoji: str, user: str }
  → { ok: true, reactions: { "👍": ["alice", ...] } }
```

### Voice / Video Calls

The voice and video endpoints share the same shape; substitute `voice` ↔ `video`.

```
POST /api/comms/voice/sessions
  Body: { caller: str, participants: [str], sdp_offer?: str }
  → { ok: true, session: { id, type, caller, state: "ringing", ... } }

GET  /api/comms/voice/sessions?user=<u>&state=<s>
  → { sessions: [...] }

POST /api/comms/voice/sessions/{sid}/answer
  Body: { sdp_answer?: str }
  → { ok: true, session: { state: "active", answered_at, ... } }

POST /api/comms/voice/sessions/{sid}/hold   → { state: "on_hold" }
POST /api/comms/voice/sessions/{sid}/end    → { state: "ended", duration_seconds }
POST /api/comms/voice/sessions/{sid}/reject → { state: "rejected" }
POST /api/comms/voice/sessions/{sid}/ice    Body: { candidate: str }
```

### Email

```
POST /api/comms/email/send
  Body: { sender, recipients, subject, body, cc?, bcc?, priority?, thread_id? }
  → { ok: true, email: { id, ... } }

GET  /api/comms/email/inbox?user=<u>   → { emails: [...] }
GET  /api/comms/email/outbox?user=<u>  → { emails: [...] }
GET  /api/comms/email/{eid}            → { email: {...} }
POST /api/comms/email/{eid}/read       Body: { user: str }
```

### Automation Rules

```
POST   /api/comms/automate/rules
  Body: { name, trigger, channel, action, conditions?, action_params?, created_by? }

GET    /api/comms/automate/rules?channel=<c>
PATCH  /api/comms/automate/rules/{rid}/toggle   Body: { enabled: bool }
DELETE /api/comms/automate/rules/{rid}

POST   /api/comms/automate/evaluate
  Body: { trigger: str, channel: str, payload: {} }
  → { matched_rules: [...] }
```

### Moderator Console

```
GET    /api/moderator/users
POST   /api/moderator/users/{user}/role     Body: { role, by }
POST   /api/moderator/users/{user}/warn     Body: { reason, by }
POST   /api/moderator/users/{user}/mute     Body: { reason, by }
POST   /api/moderator/users/{user}/unmute   Body: { by }
POST   /api/moderator/users/{user}/kick     Body: { reason, by }
POST   /api/moderator/users/{user}/ban      Body: { reason, by }
POST   /api/moderator/users/{user}/unban    Body: { by }
DELETE /api/moderator/messages/{channel}/{mid}  Body: { by, reason? }

GET    /api/moderator/automod/words
POST   /api/moderator/automod/words            Body: { words: [str], by }
DELETE /api/moderator/automod/words/{word}?by=<actor>
POST   /api/moderator/automod/check            Body: { text: str }

GET    /api/moderator/broadcast/targets
POST   /api/moderator/broadcast/targets        Body: { platform, channel_id, by }
DELETE /api/moderator/broadcast/targets/{platform}/{channel_id}?by=<actor>
POST   /api/moderator/broadcast               Body: { message, platforms?, subject?, priority?, sender? }
GET    /api/moderator/broadcast/history?limit=50
GET    /api/moderator/audit?limit=100
```

---

## Auto-Moderation

Every IM message and email body is checked by `_check_automod()` before being stored.

**Default blocked words:** `spam`, `scam`, `phishing`, `malware`, `ransomware`

The automod result is attached to each message/email:

```json
{
  "flagged": true,
  "action": "warn",
  "matches": ["spam"],
  "reason": "blocked_word"
}
```

Custom blocked words are added via `POST /api/moderator/automod/words` and applied
in addition to the defaults.

---

## Automation Rules Reference

### Trigger types

| Trigger | Fired when |
|---------|-----------|
| `on_message` | Any IM message is posted |
| `on_email` | Any email is sent |
| `on_missed_call` | A call session ends without being answered |
| `on_voicemail` | A call session ends with a `voicemail_url` |
| `scheduled` | (External trigger — evaluated by cron/scheduler) |

### Conditions

| Key | Effect |
|-----|--------|
| `keyword` | Rule only fires when `keyword` appears in the payload `content` |
| `automod_flagged` | Rule only fires when `payload.automod_flagged` is truthy |

### Default rules (seeded on startup)

1. **Auto-reply on missed call** — `on_missed_call` → `send_im` with template message
2. **Escalate urgent emails** — `on_email` in channel `email`, keyword `urgent` → `notify_admin`
3. **Auto-moderate flagged IM** — `on_message`, `automod_flagged` condition → `automod_delete`

---

## Broadcast Platforms

Registered targets are stored in-memory per-process (broadcast targets are not yet
persisted to the database — they are re-seeded from defaults on startup).

| Platform | Notes |
|----------|-------|
| `im` | Internal Murphy IM channels |
| `email` | Internal email distribution lists |
| `voice` | Voice broadcast channels |
| `video` | Video conference channels |
| `slack` | Slack workspace channel |
| `discord` | Discord guild channel |
| `matrix` | Matrix room |
| `sms` | SMS gateway |

Default seeded targets: `im#general`, `email#all-staff`, `matrix#murphy-general`

---

## Environment Variables

No environment variables are required beyond the standard Murphy System variables.
The hub uses the same `DATABASE_URL` / `MURPHY_DB_URL` SQLite default as the rest of
the system.

---

## Testing

```bash
MURPHY_ENV=development python -m pytest tests/test_communication_hub.py \
    --override-ini="addopts=" -v
```

83 tests across 7 test classes:
- `TestAutomod` (5) — content filtering
- `TestIMStore` (15) — threads, messages, persistence, reactions
- `TestCallSessionStore` (12) — full call lifecycle
- `TestEmailStore` (10) — inbox/outbox/mark-read/persistence
- `TestAutomationRuleStore` (12) — CRUD, toggle, evaluate
- `TestModeratorConsole` (24) — all moderation actions + broadcast
- `TestMultiAccountScenario` (5) — end-to-end multi-account flows

The `conftest.py` autouse fixture truncates all comms hub tables before each test
in this file, ensuring full DB isolation between tests.
