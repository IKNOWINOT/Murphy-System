# Murphy System — Engineering Rules (LOCKED)
# Approved by: Corey Post | Date: 2026-05-07
# Updated: 2026-05-12 — Game commissioning requirements added

---

## RULE 0 — Read Before Touch
Before ANY session work:
1. Run live endpoint scan — show what's working vs broken with real HTTP status
2. Read the actual source of any module being changed via SFTP — never assume
3. State HEAD commit at start of every session
4. No work begins until this map is shown to the user

---

## RULE 1 — No New Files. Ever. (Unless Approved)
- Every new feature goes INTO an existing module
- New UI wires to an EXISTING endpoint — never creates new backend
- If I think a new file is needed, I must:
  a) Name the existing file it COULD go into
  b) Explain specifically why it can't hold it
  c) Wait for explicit user approval before creating anything new
- The 469 orphaned modules are proof this rule was violated. It stops now.

---

## RULE 2 — The Dynamic Assembly Pattern (Soul → Rosetta → MFGC → MSS → Swarm)
Every task MUST follow this order. This is not optional, not skippable.

**Step 0 — Soul Load**
Before any agent acts, RosettaSoulRenderer renders that agent's soul from
its RosettaDocument. This is the SOUL.md equivalent — who this agent IS,
what it VALUES, what its BOUNDARIES and AUTHORITY are.
- Soul is layered: L0 (identity ~50 tokens), L1 (critical facts ~120 tokens),
  L2 (full role), L3 (deep history)
- Wake-up context = L0 + L1 only (compact, injected into every task prompt)
- Soul is NOT static — it is rendered fresh from RosettaManager state each time
- build_org_chart(manager) assembles the live org from RosettaManager state
- platform_org_seed fills canonical roles (CEO/CTO/Compliance/SRE) if missing
- The org chart IS the soul manifest — every node in it has a rendered soul

**Step 1 — Rosetta Dispatch**
POST /api/rosetta/dispatch with the task prompt
→ SwarmCoordinator reads the live org chart
→ Assigns roles dynamically based on task context + soul fit
→ Returns dag_id + assigned agents with their rendered souls injected

**Step 2 — MFGC Business Logic Gates**
GET /api/mfgc/state → current 7-phase control state
→ MFGC maps the task to its business execution phase
→ Gates define what must be true before each phase runs
→ Each gate-passing agent already has its soul loaded from Step 0

**Step 3 — MSS Resolution Sequence**
POST /api/mss/score → score the task input (payload: {"text": "..."})
POST /api/mss/magnify or /api/mss/simplify → adjust resolution as needed
→ MSS expands or compresses the task scope based on soul-defined authority
→ Each transformation emits a notification

**Step 4 — Swarm Execute with Soul-Aware Agents**
POST /api/swarm/propose → agents receive tasks scoped to their soul
POST /api/swarm/execute → DAG runs, each agent acts within its soul boundaries
GET /api/swarm/agents/status → live status + soul context per agent
→ Notifications emitted at each step via /api/swarm/bus/feed

---

## RULE 3 — Notifications Are Mandatory
Every step emits a visible notification to the UI:
- "Loading soul for [role]: L0+L1 context injected..."
- "Rosetta assembling org chart for: [task]..."
- "MFGC phase [N] gate [open/closed] — [reason]..."
- "MSS scoring at RM[N] — [magnifying/simplifying] to RM[N+1]..."
- "Swarm agent [Collector] dispatched — soul: [role summary]..."
- "Task complete: [result summary]"

Notifications go to UI via SSE stream at /api/swarm/bus/feed.
A feature with no visible notification trail is NOT done.

---

## RULE 4 — Existing Routes Are Canonical
Before writing ANY endpoint call in UI:
1. grep app.py for the actual route
2. Test it live with curl before wiring the UI to it
3. If the route returns 404, find the REAL route — don't invent a new one

Verified live routes (PATCH-228b):
- Soul: rendered via RosettaSoulRenderer from rosetta_soul_renderer.py
- Org: build_org_chart(manager) in rosetta/org_chart.py
- Rosetta: /api/rosetta/soul, /api/rosetta/status, /api/rosetta/dispatch
- MFGC: /api/mfgc/state, /api/mfgc/config, /api/mfgc/setup/{profile}, /api/mfgc/gates
- MSS: /api/mss/magnify, /api/mss/simplify, /api/mss/solidify, /api/mss/score
- Swarm: /api/swarm/propose, /api/swarm/execute, /api/swarm/agents/status
- Swarm Mind: /api/swarm/mind/status, /api/swarm/mind/self-model
- Bus: /api/swarm/bus/feed (SSE), /api/swarm/bus/publish
- CRM: /api/crm/deals, /api/crm/contacts
- Capital: /api/capital/proposals
- Security: /api/shield/status, /api/security/events

---

## RULE 5 — A Feature Is Done When It Shows Real Data
Not when the page renders. Not when the API returns 200.
Done = live data flowing from the actual backend, visible in the UI.
Screenshot proof required before calling it complete.

---

## RULE 6 — One Patch, One Thing
Each patch label (PATCH-NNN) does exactly one thing.
No "while I'm in here" additions.
If something else is broken, note it and address it in the NEXT patch.

---

## RULE 7 — LLM Chain Is Fixed — Don't Touch It
Chain: DeepInfra (8s fast-fail) → Together.ai (120s) → Ollama phi3 (60s) → stub
- complete() accepts both system= and system_prompt= (alias in place)
- Primary model: meta-llama/Meta-Llama-3.1-70B-Instruct
- DeepInfra fast-fails at 8s so Together.ai picks up immediately
- Together.ai full window: 120s — enough for multi-agent swarm tasks
- Ollama phi3 is the onboard fallback (localhost:11434, 60s window)
- DO NOT add new LLM provider files — wire into llm_provider.py only

---

## RULE 8 — Swarm Mind Informs Soul Loading
/api/swarm/mind/status → cycle 1206+, confidence 0.901, RUNNING
The mind's current self-model feeds into soul rendering — it knows which
agents are performing well, which roles need strengthening.
Check mind status at start of every task dispatch. Use self-model to
inform which soul layers get promoted to L0/L1 for the current context.

---

## RULE 9 — Game Commissioning Requirements (LOCKED — 2026-05-12)

A game is NOT commissioned until it passes ALL of the following. These are
non-negotiable. The static GameCritic score is meaningless without them.

### 9A — Ghost Commissioning (Live Browser Test) is MANDATORY
Every generated game MUST be verified via headless Playwright before it is
called done. The ghost_commission() function in game_forge.py does this:
  1. Navigate to the live /play/{slug} URL
  2. Screenshot → verify title screen is visible (not black)
  3. Fire pointerdown on document → wait 2s → screenshot again
  4. Verify the screen changed (pixel diff > 3%) — confirms TAP TO START worked
  5. Verify game screen is not black
If ghost_commission() fails → auto-repair → re-check. NEVER ship without this.

### 9B — TAP TO START Handler (MANDATORY in every game)
ALWAYS attach the state-machine tap handler to `document`, not canvas, not a div:
  document.addEventListener('pointerdown', function(e) {
    if (state === 'title') { state = 'game'; initGame(); return; }
    if (state === 'dead')  { state = 'game'; initGame(); return; }
  });
This is the #1 runtime failure mode. It is NOT a "nice to have" — it is the
only reliable way to handle both mouse and touch on all browsers.
NEVER use canvas.addEventListener or div.addEventListener for tap-to-start.

### 9C — Bootstrap RAF (MANDATORY)
The LAST line inside the window.addEventListener('load', ...) wrapper MUST be:
  requestAnimationFrame(loop);
Without this line: complete black screen, no errors, game never starts.
This must appear AFTER all function definitions, AFTER all event listeners.

### 9D — Player Must Be Visible Immediately
initGame() MUST set player.x = W/2, player.y = H/2 (or equivalent center).
Player MUST be drawn as a colored shape ≥ 20px. Never transparent, never size 0.
If the player is invisible the user thinks the game is broken. It IS broken.

### 9E — initGame() Must Exist and Be Called
There MUST be a standalone initGame() function that fully resets all game state.
It must be called on title→game AND dead→game transitions.
Resetting inside the loop or inline is not acceptable.

### 9F — MURPHY_API_KEY (singular) Must Be Set in murphy.service
The env var MURPHY_API_KEYS (plural, comma-separated) does NOT work for
hmac.compare_digest authentication — it compares the entire comma-separated
string as the expected key, causing AUTH_REQUIRED for every API call.
MURPHY_API_KEY (singular) = the founder key alone must ALWAYS be present in
/etc/systemd/system/murphy.service. Verify this before any API test.

---

## TIMEOUT POLICY (PATCH-228a — LOCKED)
Swarms are not web requests. They are multi-agent computations.
- DeepInfra: 8s (fast-fail to Together)
- Together.ai: 120s
- LLM_TIMEOUT: 120s
- Ollama: 60s
- Startup join: 120s
- Task default: 120s
- Circuit breaker recovery: 10s
NEVER reduce these back to 30s without explicit approval.

---

## FOUNDER AUTH (PATCH-228b — LOCKED)
cpost@murphy.systems always gets role=owner, tier=enterprise.
_apply_founder_override() is called in:
  - _get_account_from_session() — all session/cookie/bearer paths
  - account_profile() — what the admin panel reads
  - auth_login() — login response includes role field
DO NOT remove these override calls.

---

## WHAT CURRENTLY WORKS (verified live, 2026-05-07 PATCH-228b)
✅ /api/rosetta/soul
✅ /api/rosetta/status
✅ /api/rosetta/dispatch
✅ /api/mfgc/state
✅ /api/mfgc/gates
✅ /api/mss/score (payload: {"text": "..."})
✅ /api/mss/magnify
✅ /api/swarm/agents/status
✅ /api/swarm/mind/status — cycle 1206, confidence 0.901
✅ /api/swarm/bus/feed — SSE stream
✅ /api/capital/proposals
✅ /api/crm/deals
✅ /api/shield/status — 19/20 layers active
✅ /api/security/events
✅ /api/admin/users — founder (cpost@murphy.systems) has full access
✅ /api/account/profile — returns role=owner for founder

## STILL BROKEN (next patches, in order)
❌ Soul not injected into task dispatch — RosettaSoulRenderer never called from dispatch handler (PATCH-229)
❌ build_org_chart() not called — org is static, not dynamic (PATCH-229)
❌ /api/swarm/rosetta — times out (PATCH-230)
❌ /api/rosetta/translate — times out (PATCH-230)
❌ /api/roi-calendar/summary — 500 error (PATCH-231)
❌ MURPHY_API_KEY (singular) missing from murphy.service — API auth broken after restart
❌ ghost_commission() not yet wired to block on failure — needs PATCH-254
