# Shape of Complete — v3 (2026-06-16)

## Why v3 exists
v1 (2026-05-26) defined the 7 Pillars of "done."
v2 (2026-06-XX) added the email-arc shape.
v3 (this doc) adds the **architectural memory layer** — Loom-Lite +
DLF-Lite v2 — so the system can see its own lineage when things break.

v3 does NOT replace v2. It ADDS three new pillars (8, 9, 10) that apply
only to capabilities that produce outputs which could later be reused as
substrate. Existing pillars 1-7 still apply universally.

## The architecture in one paragraph
Murphy has a **live runtime** (Loom-Lite — working memory) and a **portable
memory** (DLF-Lite v2 — durable memory). The live runtime captures what's
happening turn-by-turn. The portable memory crystallizes the parts that
matter into a structured, auditable, hygienic format that survives across
restarts, sessions, and even system boundaries.

## The two layers — Loom-Lite (live) and DLF-Lite v2 (durable)

### Loom-Lite — the live runtime
Lives in process memory + ephemeral DBs. Captures per-turn state.

| Component | What it is | Where it lives |
|---|---|---|
| GhostLayer | Per-turn snapshot of working set (active threads/nodes/pending weaves) | `loom_lite.ghost_layer` + `ghost_snapshots.db` |
| PSI history | Operation log w/ cost+latency+outcome typing | `loom_lite.psi_history` + `psi_log.db` |
| Recursion gate | Spawn-depth tracker (am I inside a sub-agent? a critic? a drill?) | `loom_lite.recursion_gate` + in-process |
| Process-controller link | Bridge to conductor.service + 29 timers | `loom_lite.process_controller` |
| Precipitator | Turn-end: crystallize GhostLayer → DLF-Lite v2 package | `loom_lite.precipitator` |

### DLF-Lite v2 — the durable memory
Lives as `.dlf-lite` containers + indexed in `dlf_packages.db`. Spec from the
Shogun white paper (2026-06-16). Carries semantic continuity across systems.

| Layer | What it carries | Why |
|---|---|---|
| Thread | Raw information units (messages, observations, outputs, events) | The atoms |
| Node | Semantic anchors binding threads with role/authority/hygiene/substrate metadata | The molecules |
| Weave | Typed relationships between nodes | The bonds |
| Fabric | Compact package orientation (domains, keywords, counts, audit posture) | Quick read |
| Provenance | Package origin, source system, export chain, checksum | Trust chain |
| Derivation | How a node/output was derived from prior substrate, with authority rules | Lineage |
| Hygiene | Validation + selection fitness flags (REJECT_FUTURE_SELECTION etc.) | Immune system |
| Audit | Decision rules: AVAILABLE vs SELECTED vs PROVENANCE_CONFIRMED | Did we actually use this? |

## Relation families (v2 spec, §4 of agentic guide)

| Family | Relations | Use |
|---|---|---|
| INTENT_TASK | ANSWERS, HAS_INPUT, HAS_OUTPUT | Connect tasks/requests/outputs |
| PROVENANCE_TRANSFORMATION | CREATIVE_SUBSTRATE, DERIVED_FROM, BACKGROUND_SUBDATA | How outputs were shaped |
| EVIDENCE | SOURCE_REFERENCE, CITES | Factual outputs to evidence |
| SEMANTIC_RELATION | SUPPORT, CONTRADICTION, DEPENDENCY, ASSOCIATION | Semantic topology |
| ORDER | SEQUENCE | Temporal/procedural order |

## Authority roles (v2 spec, §6)

- `creative_background_not_factual_authority` — shapes style/content, not truth
- `factual_authority` — supports factual claims (usually w/ SOURCE_REFERENCE)
- `volatile_current_status` — title-holder/current facts, needs freshness check
- `user_supplied_unverified` — user assertion, not externally verified
- `derived_low_authority` — generated material, doesn't override source

## Provenance audit states (v2 spec, §5)

- `DLF_AVAILABLE` — material exists but no use shown
- `DLF_SELECTED_OR_INJECTED` — material entered generation context
- `DLF_SUBSTRATE_PROVENANCE_CONFIRMED` — provenance weave links output to substrate

## Hygiene rules (v2 spec, §7)

- Do NOT select failed generations as future creative substrate
- Preserve them for audit, mark REJECT_FUTURE_SELECTION
- Reject `[LLM error]`, `[empty answer blocked]`, `[creative output contract violation]`,
  traceback/error records, attribution-only records

# The 10 Pillars (v1 still applies; v3 adds 8, 9, 10)

### Pillar 1 — CODE (v1)
File exists, parses, no must-fix TODOs, no hardcoded secrets.

### Pillar 2 — WIRED (v1)
Imported, registered, reachable.

### Pillar 3 — DEPENDENCIES (v1)
DB tables, secrets, OAuth tokens, sister services.

### Pillar 4 — EXECUTES (v1)
End-to-end on real input, side effects happen.

### Pillar 5 — VISIBLE (v1)
Founder can see it from OS or dedicated UI.

### Pillar 6 — DOCUMENTED (v1)
README + example + CHANGELOG.

### Pillar 7 — CONSISTENT (v1)
Voice + naming + facts match across code/landing/docs/audit.

### Pillar 8 — LINEAGE (v3, NEW)
**Every output capable of being reused as substrate has a provenance record.**
- For each generated reply/draft/proposal: a DLF-Lite v2 node exists
- The node has weaves back to its inputs (CREATIVE_SUBSTRATE, DERIVED_FROM, etc.)
- The provenance state is at minimum DLF_SELECTED_OR_INJECTED
- VERIFY: `dlf_lite_v2.audit.classify(output_node_id)` returns non-NONE state

### Pillar 9 — HYGIENE (v3, NEW)
**Every failed/violating output is marked so it can't poison future generations.**
- Outputs that exceeded their `recommended_reply_chars` envelope → `REJECT_FUTURE_SELECTION`
- Outputs that got "hold" verdict from critic → `REJECT_FUTURE_SELECTION`
- LLM error markers, empty-blocked, traceback records → `REJECT_FUTURE_SELECTION`
- VERIFY: bad outputs have `hygiene_status='REJECT_FUTURE_SELECTION'` in their node

### Pillar 10 — AUDITABLE (v3, NEW)
**Every turn produces a GhostLayer snapshot precipitable into a DLF-Lite v2 package.**
- Before drill: snapshot the input + shape + sender context
- Between drill and rosetta: snapshot the deliverable plan
- After critic: snapshot the verdict + writer-notes
- After send: snapshot the final body + outcome + cost
- At turn-end: precipitator crystallizes into one `.dlf-lite` package
- VERIFY: a `.dlf-lite` blob exists in `/var/lib/murphy-production/dlf_packages/`
  with the turn's correlation_id

## Verdict states (unchanged from v1)
- 🟢 GREEN — all applicable pillars verified
- 🟡 YELLOW — code works but ≥1 pillar missing
- 🔴 RED — not running or contradictory

## Applying v3 — where pillars 8/9/10 are required

| Capability | Need 8/9/10? | Why |
|---|---|---|
| stranger_responder | 🔴 YES | produces outputs that could re-enter as substrate |
| autoresponder timer | 🔴 YES | same, plus high blast radius |
| HITL drafts | 🔴 YES | drafts can be reused |
| vision_loop proposals | 🔴 YES | already has dedup; needs hygiene flag too |
| /api/* read routes | 🟢 NO | no output, just observation |
| systemd timers (pure observation) | 🟢 NO | no generation |
| auth/login | 🟢 NO | not generative |
| compliance pages (static) | 🟢 NO | static content |

## How a turn flows through both layers

```
INBOUND email arrives
  ↓
Ship 31ba intent gate (conversational? skip)
  ↓
Loom-Lite.ghost_layer.snapshot("turn_start", inputs)
  ↓
Ship 31cu pre-drill shape → world_context (DLF_AVAILABLE)
  ↓
Drill plans deliverable
  Loom-Lite.psi_history.log("drill_iter", cost, latency, outcome)
  ↓
Loom-Lite.ghost_layer.snapshot("post_drill", deliverable_plan)
  ↓
Rosetta picks team
  Loom-Lite.recursion_gate.enter("rosetta_team")
  ↓
Team executes → draft
  ↓
Loom-Lite.ghost_layer.snapshot("post_team", draft)
  ↓
Ship 31bq critic loop (PASS/HOLD/REVISE)
  Loom-Lite.psi_history.log("critic_verdict", verdict)
  ↓
[If REVISE]: writer-notes addendum → re-prompt
  ↓
Loom-Lite.ghost_layer.snapshot("post_critic", final_body, verdict)
  ↓
Send (or hold)
  ↓
Loom-Lite.precipitator.crystallize(correlation_id)
  → writes /var/lib/murphy-production/dlf_packages/{correlation_id}.dlf-lite
  → indexes in dlf_packages.db
  → applies hygiene flags based on verdict + envelope compliance
```

## What this prevents

**Tonight's mcconnaire loop becomes structurally impossible:**
- Before each send, precipitator records the body length + envelope target
- If body exceeded envelope → `REJECT_FUTURE_SELECTION` stamped on the output node
- Next cycle's drill cannot select that bad output as substrate
- The recursion gate stops a 4th-time-same-row spawn
- The GhostLayer would show "we already sent to this row 3 min ago"

## Storage layout

```
/var/lib/murphy-production/
  dlf_packages/                          # one .dlf-lite per turn
    {correlation_id}.dlf-lite
  dlf_packages.db                        # index over the packages
    table: packages(id, correlation_id, created_at, audit_state,
                    hygiene_status, blob_path, checksum)
  ghost_snapshots.db                     # short-lived per-turn snapshots
    table: snapshots(id, correlation_id, phase, payload, created_at)
    retention: 7 days
  psi_log.db                             # operation log
    table: psi_events(id, correlation_id, operation, cost_usd,
                      latency_ms, outcome, created_at)
    retention: 30 days
```

## What's EXCLUDED (kept faithful to DLF-Lite v2 spec)

- GhostLayer runtime internals (we keep the snapshot, not the live process)
- PSI recursion telemetry beyond cost/latency/outcome
- Model weights / embeddings / vector indexes
- Hidden chain-of-thought from LLM providers (we don't have it anyway)
- Live FastAPI route logic
