# Murphy Business Glossary — LOCKED 2026-06-08

Canonical definitions for every domain term used in Murphy. Source of
truth for `glossary_lookup.py` and CI pre-commit term-check.

**Rule:** If you're about to introduce a new ALL-CAPS abbreviation or
hyphenated technical term, add it here FIRST. CI will refuse commits
that use undefined terms.

Format per entry:
- **TERM** (first-introduced YYYY-MM-DD, related: TERM2, TERM3)
  One-paragraph definition (≤ 50 words).

---

## Core platform terms

- **Murphy** (2025-12-01, related: Inoni)
  The autonomous AI business platform. A single living service that
  reasons, patches its own code, talks to customers, runs invoices, and
  ships work. NOT a chatbot, NOT a workflow tool — a self-modifying
  operator.

- **Inoni** (2026-01-15, related: Murphy, tenant_identity)
  Inoni LLC is the legal entity that owns and operates Murphy. Founder:
  Corey Post. The `inoni` tenant_id refers to internal Murphy work.

- **Superagent** (2026-05-20, related: Murphy)
  Base44's product name for personal AI agents — what Murphy IS to the
  founder. Distinct from Base44's app builder.

## Engineering process

- **R-number** / **R-cycle** (2025-12-10)
  Murphy's session-numbered work cycles. R83 means the 83rd cycle of
  feature work. Each R-number can have sub-patches (R83.P1, R83.P2).
  Used in commit messages and memory.

- **PATCH-NNN** (2026-02-04, related: PCR)
  A numbered architectural patch. Three-digit, incrementing. Used when
  the change is too structural for a single R-cycle. PATCH-408 added
  vault classes; PATCH-409 added job-tagged ledger.

- **PCR-NNN** (2026-06-08, related: PATCH, context_readiness_canon)
  Patch: Context Readiness. The 15 patches that move Murphy from 5.5/10
  to 10/10 across the DataHub-guide context standards. PCR-001 to
  PCR-015. Tagged in commit messages as `STD-N M→K: ...`.

- **PSM** (2025-12-20, related: snapshot, before_after_canon)
  Patch State Management. The discipline of snapshot-before-change,
  verifier-after-change for every production touch. Embodied in the
  `before_after_canon.md` rule.

- **Shape of complete** (2026-01-08, related: verifier, PSM)
  A patch is "complete" only when there's a humanly-readable test that
  an outside party can run and see the result. No "trust me, it works".
  Every PCR has a verifier command that proves its score.

- **Verifier** (2026-06-08, related: shape of complete, PCR)
  A one-liner shell or Python command that recomputes a capability's
  state from production. The verifier IS the shape of complete. Lives
  in `docs/architecture/<canon>.md` next to the standard it proves.

- **Tripwire** (2026-04-12)
  Source-integrity guard. Pre-commit + nightly check that catches
  unauthorized edits to tracked `src/` files. Refuses commits that
  break canonical structure.

## Architecture concepts

- **Rosetta** (2026-03-22, related: org chart, dispatcher)
  Murphy's role-injection mechanism. An agent becomes itself by being
  equipped at dispatch time with skills + knowledge + perspective based
  on its title in the org chart. Spec at `.agents/rules/rosetta_architecture.md`.

- **Conductor** (2026-05-15, related: state machine, dispatcher)
  The Netflix-style workflow state machine at `src/conductor/`. Schedules
  tasks across the agent swarm with deterministic state transitions.
  Exposed at `/api/conductor/*`.

- **Dispatcher** / **Executor** (2026-03-22, related: Rosetta, Conductor)
  Reads a plan, resolves each task to a role (via org chart), spawns a
  fresh agent equipped with that role's bundle, executes typed
  commands. Communication = LLM. Action = skills. Never inverted.

- **Org chart** (2026-03-22, related: Rosetta, role template)
  The canonical list of roles in Murphy's organization. Each row has a
  title that maps to a Rosetta injection bundle. Title is canonical;
  no two rows share a title.

- **Skill / typed dispatch** (2026-03-22, related: Rosetta)
  A typed callable that an agent can invoke. Skills declare their input
  types. Untyped free-text prompts are NOT skills. `dispatch("send_quote",
  customer_id=X, line_items=Y)` is canonical form.

- **Soul** (2026-02-18, related: identity, conscience)
  The agent's value system and decision frame. `rosetta_core.py:RosettaSoul`
  is the conscience gate that returns `proceed | block | defer_hitl`
  on every consequential action. Murphy's soul lives in `SOUL.md`.

## Operations

- **HITL** (2025-12-15)
  Human-In-The-Loop. A pause point where Murphy refuses to act without
  the founder's confirmation. Triggered for: dollar amounts above
  threshold, external messaging to non-allowlisted addresses, soul
  conflicts. Queue at `/os/hitl`.

- **STATUS block** (2026-04-30, related: shape of complete)
  Weekly health snapshot Murphy posts to itself. Format: `N 🟢 / M 🟡 /
  K 🔴 (HEAD <hash>)`. Each color is a canonical surface or a tracked
  concern. The block is the single source of truth for "where are we".

- **Canonical surface** (2026-04-30, related: STATUS, SLA)
  An endpoint or capability we promise will be working. Currently 6:
  `/`, `/os`, `/api/public/stats`, `/api/health`, `/api/conductor/healthz`,
  `/api/self/audit`. Each will get a formal SLA in PCR-006.

- **Sandbox enforcement** (2026-04-22, related: tripwire)
  Production code is read-only outside of approved patch paths. New
  code goes through `state_snapshots/` and tripwire verification before
  it touches tracked files.

- **Allowlist** (2026-05-25, related: HITL, autoresponder)
  Phone numbers and email addresses Murphy is authorized to message
  without HITL. Currently: cpost@murphy.systems, hpost@murphy.systems
  (Hawthorne), callmehandy@gmail.com (Hawthorne), founder mobile.

- **Tracer** (2026-03-08, related: HITL, allowlist)
  Inbound-message router. Decides: respond automatically (allowlisted),
  queue for HITL (unknown sender, financial content), or drop (spam).

## Data + accounting

- **Vault** / **murphy_vault.db** (2026-02-01, related: PATCH-408)
  The encrypted secrets store. AES-256-GCM. Canonical path:
  `/var/lib/murphy-production/murphy_vault.db`. Two classes (see below).

- **class = platform** (2026-06-08, related: vault, PATCH-408)
  Vault rows owned by Murphy's engine. Examples: TOGETHER_API_KEY,
  NOWPAYMENTS_API_KEY, TWILIO_*. Used for Murphy's own external calls
  and as default for tenant ops.

- **class = tenant_identity** (2026-06-08, related: vault, PATCH-408)
  Vault rows owned by a tenant — their bring-your-own credentials.
  Examples: a tenant's own Twilio or NOWPayments key. When present,
  override the platform default for that tenant's ops. Murphy never
  reads the raw value; admins see only name + metadata + audit.

- **CrossTenantReadRefused** (2026-06-08, related: tenant_identity)
  Exception raised by `_vault_or_env()` when one tenant's code attempts
  to read another tenant's identity secret. The privacy floor is in
  code, not policy.

- **BYO transaction model** (2026-06-08, related: tenant_identity)
  When a tenant uses their own credential, Murphy takes ZERO from that
  transaction. Money flows direct to the tenant. Captured in
  `vault_and_accounting_canon.md`.

- **Work-for-tenant model** (2026-06-08, related: job_id, PATCH-409)
  When Murphy does work FOR a tenant (LLM calls, voice min, SMS, etc.),
  every action is tagged `(tenant_id, job_id)` for customer-facing
  invoice attribution.

- **job_id / JOB-NNN** (2026-06-08, related: PATCH-409, work-for-tenant)
  Canonical work-unit identifier for tenant-attributable cost. Format:
  `JOB-YYYY-NNNNNN`. Lives on every row in the LLM cost ledger.

- **Cost ledger** / **llm_cost_ledger.db** (2026-02-15, related: PATCH-089c, PATCH-409)
  The per-LLM-call accounting store. Every record() call writes:
  ts, model, provider, tokens, cost_usd, latency, caller, success,
  tenant_id, job_id. Source of truth for billing rollups.

## Pricing canon (Option A, locked 2026-06-08)

- **Solo tier** ($99/mo, $950/yr, 1 seat)
  Single-operator plan. No extra-seat option; upgrade to Team.

- **Team tier** ($399/mo, $3,830/yr, 5 seats, +$79/extra seat)
  Small team. First plan with extra-seat add-on.

- **Business tier** ($799/mo, $7,670/yr, 15 seats, +$79/extra seat)
  Mid-market. Same per-seat add-on as Team.

- **Enterprise tier** (Custom pricing, unlimited seats, +$79/extra seat)
  Sales-quoted. DB sentinel: amount_usd = 0.0. Same per-seat add-on.

- **Operator tiers** (Starter $1,499 / Pro $2,999 / Senior $5,999 — separate rail)
  Role-hire pricing. A tenant hires a Murphy operator (SDR, dispatcher,
  bookkeeper). NOT a subscriber tier. Per-hire, not per-seat.

## Vendor terms

- **NOWPayments** (2026-02-01, related: vault, crypto)
  Crypto payment processor. Murphy's canonical billing rail for
  subscriber tiers. Platform key: NOWPAYMENTS_API_KEY in vault.

- **TOGETHER** (2026-01-12, related: LLM, cost ledger)
  TogetherAI. Murphy's primary LLM provider (Llama 3.3 70B). Platform
  key: TOGETHER_API_KEY in vault.

- **Twilio** (2026-01-12, related: SMS, voice)
  Telecom provider for Murphy's voice + SMS rails. Platform keys:
  TWILIO_* (4 entries: account SID, auth token, voice number, SMS number).

## Standing decisions

- **Standing Decision NN** (2026-04-12)
  Persistent founder rulings. Numbered. Saved in `USER.md`. Examples:
  SD-55 (re-audit long-standing findings), SD-56 (no unilateral
  architectural choices). Override individual session decisions.

- **BL-RNN / Blockers** (2026-04-30, related: do-not-touch)
  Persistent blockers. BL-R11 = GitHub PAT rotation (LOCKED forever per
  founder). Never propose, never mention, never include in plans.

## DataHub guide terms (added 2026-06-08)

- **Context (3-layer model)** (2026-06-08, related: PCR, DataHub guide)
  Technical (lineage, schema, version) + Operational (runtime, audit,
  SLA, attribution) + Business/social (glossary, docs, compliance, ownership).
  Plus the AI-agent-readable layer (MCP, anomaly, auto-doc, model lineage).

- **AI-ready** (2026-06-08, related: context readiness)
  Score ≥ 7 on a context-readiness standard. Below this, the system is
  dangerous to operate at scale (per the DataHub guide).

- **Best-in-class** (2026-06-08, related: AI-ready)
  Score = 10. The capability is clean enough that an outside engineer
  could understand and trust it within 5 minutes.

- **Investment ledger** (2026-06-08, related: cost ledger, PCR)
  Cost-ledger entries with `caller='context_readiness'` are tracked
  separately as the investment in context capability. Target: > 20%
  engineering time until all standards ≥ 7, > 10% steady-state.

---

## Append-only zone

When adding a new term, append at the bottom of the relevant section
with first-introduced date. Never silently rename or delete entries —
add a deprecation note instead.
