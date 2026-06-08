# Context Readiness — Task Ladder (PCR-001 .. PCR-015)
# Canon: .agents/rules/context_readiness_canon.md
# Created: 2026-06-08

## Current scores (baseline 2026-06-08)

| # | Standard | Now | Target | Delta |
|---|---|---|---|---|
| 1 | Data lineage | 4 | 10 | +6 |
| 2 | Schema registry | 5 | 10 | +5 |
| 3 | Version control | 9 | 10 | +1 |
| 4 | Runtime metrics | 8 | 10 | +2 |
| 5 | Audit log unification | 8 | 10 | +2 |
| 6 | Data SLAs | 2 | 10 | +8 |
| 7 | Ownership / tenancy | 9 | 10 | +1 |
| 8 | Job attribution | 8 | 10 | +2 |
| 9 | Business glossary | 2 | 10 | +8 |
| 10 | Unstructured docs | 5 | 10 | +5 |
| 11 | Compliance modules | 7 | 10 | +3 |
| 12 | MCP server | 7 | 10 | +3 |
| 13 | Anomaly detection | 4 | 10 | +6 |
| 14 | Auto-documentation | 2 | 10 | +8 |
| 15 | E2E model lineage | 3 | 10 | +7 |

**Aggregate:** 5.5/10 → target 10.0/10. Total delta: 75 score points.

## Execution order (highest ROI first)

Order chosen by: (delta × leverage) / (effort hours). The "quick wins"
move the biggest needles per hour.

### 🔥 TIER 1 — quick wins (each ≤ 2h, +5 to +8 delta)

#### PCR-009: Business glossary (2 → 10, ~90 min)
Standard #9. Already have ~30 docs/*.md files using terms like HITL,
Rosetta, Conductor, PSM, R-numbers, PATCH, BL-, tenant_identity.
None are canonically defined.

**Shape of complete:**
- `docs/glossary.md` exists with ≥ 40 terms, each with: term, definition
  (≤ 50 words), first-introduced date, related-terms cross-refs
- `scripts/glossary_lookup.py "HITL"` returns the entry
- CI pre-commit hook (in tripwire) refuses commits that introduce a
  new ALL-CAPS or hyphenated technical term not present in glossary
- Sandbox copy in `.agents/rules/glossary.md`

**Verifier:** `wc -l docs/glossary.md` returns ≥ 200, `glossary_lookup.py
"PSM"` succeeds.

#### PCR-014: Auto-documentation (2 → 10, ~2h)
Standard #14. Murphy already self-modifies code. Auto-doc generator is
80% there: walk `src/`, extract docstrings + commit history + recent
patches touching each file, write `docs/auto/<module>.md`.

**Shape of complete:**
- `scripts/auto_doc_generator.py` produces `docs/auto/<mod>.md` for every
  Python file in `src/` (excluding _archive)
- Each generated doc has: purpose (from module docstring), public API
  (function signatures + docstrings), recent changes (last 5 commits
  touching the file), dependencies (imports), AND a "Last regenerated"
  timestamp
- Nightly automation regenerates them
- `docs/auto/INDEX.md` lists all auto-docs with module summaries

**Verifier:** `ls docs/auto/*.md | wc -l` matches count of src modules;
timestamps within 24h.

#### PCR-006: Data SLAs (2 → 10, ~90 min)
Standard #6. We have an SLA story for production but no formal commitments.

**Shape of complete:**
- `docs/architecture/sla_registry.md` defines per-endpoint SLAs:
  uptime %, p95 latency, freshness window, support response time
- `src/sla_monitor.py` measures actual vs declared every 5 min
- `/api/health/sla` returns last-30d compliance per endpoint
- Watchdog pages on breach (currently disabled — gate on founder go)

**Verifier:** `curl /api/health/sla` returns structured per-endpoint
compliance data with `committed`, `measured_30d`, `breach_count`.

#### PCR-005: Audit log unification (8 → 10, ~90 min)
Standard #5. We have 8 audit DBs; they share no schema. One nightly
roll-up produces `unified_audit` view.

**Shape of complete:**
- `src/audit_unifier.py` reads from all 8 sources, normalizes to common
  schema `(ts, actor, action, target, outcome, source_db, refs_json)`,
  writes to `var/lib/murphy-production/unified_audit.db`
- `/api/self/audit?q=...` queries the unified view
- Nightly automation refreshes
- Source DBs untouched (read-only roll-up)

**Verifier:** `audit_query(actor='cpost@murphy.systems', limit=10)` returns
results spanning ≥ 3 of the 8 source DBs.

### 🟡 TIER 2 — structural (each 2-4h, +5 to +7 delta)

#### PCR-001: Data lineage / provenance (4 → 10, ~3h)
Standard #1. Build `lineage_trace(output_id)` that walks: output → LLM
call (from `llm_cost_ledger`) → prompt → input vault refs → upstream
patches → docs in context.

**Shape of complete:**
- `src/lineage_engine.py` exposes `lineage_trace(output_id) -> DAG`
- DAG includes: timestamps, actors, source refs, transformations
- Query returns in < 500ms for any output in the last 90 days
- Visualized at `/os/lineage/<output_id>`

**Verifier:** Pick a recent LLM call ID; `lineage_trace(call_id)` returns
≥ 4 hops backward.

#### PCR-015: E2E model lineage (3 → 10, ~2h after PCR-001)
Standard #15. Extension of PCR-001 specifically for agent outputs:
trace from any agent reply backward through prompt template version,
model, system context, and the patches that last touched the prompt.

**Shape of complete:**
- `output_lineage(call_id)` returns causal chain: prompt_template_version,
  model, system_msg_hash, vault_secrets_used, upstream_patches_30d
- Renders as a single readable string + a JSON DAG

**Verifier:** Pick a chat completion ID from last 24h; output_lineage
returns the prompt that produced it AND any patch that modified that
prompt in the last 30 days.

#### PCR-002: Schema registry (5 → 10, ~3h)
Standard #2. Consolidate scattered `schemas.py` modules into ONE registry.

**Shape of complete:**
- `src/schema_registry.py` holds: every entity schema, every event schema,
  every external API schema Murphy uses
- Versioned: each schema has `v1`, `v2`, ... with breaking-change rules
- Lookup: `Schema.get("VendorQuote", version="latest")`
- CI check: any PR adding/changing a schema is gated by registry update

**Verifier:** `Schema.list()` returns ≥ 20 schemas; each has version
history; tripwire CI rejects schema changes without registry update.

#### PCR-013: Anomaly detection (4 → 10, ~3h)
Standard #13. Real drift detection on output streams.

**Shape of complete:**
- `src/anomaly_engine.py` runs every 15 min
- Watches: LLM cost-per-call (z-score > 3 alerts), output token length
  drift, refusal rate, latency p95 spike, vault read frequency
- Surfaces alerts at `/os/anomalies`
- Triggers HITL ticket on critical anomalies
- Configurable thresholds in `config/anomaly_thresholds.yaml`

**Verifier:** Inject a deliberate cost spike (mocked); anomaly engine
flags it within 15 min.

#### PCR-010: Unstructured docs index (5 → 10, ~2h)
Standard #10. Semantic search over all docs.

**Shape of complete:**
- `scripts/doc_indexer.py` chunks all docs/*.md and rules/*.md, embeds
  via Together (or local model), stores in sqlite-vss
- `docs.search(query, k=5)` returns top-K chunks with file + line refs
- Refreshes on every doc change
- Available as MCP resource (links to PCR-012)

**Verifier:** `docs.search("how does the vault handle tenant overrides")`
returns the relevant section of `vault_and_accounting_canon.md` in top-3.

### 🟢 TIER 3 — stretch (each 1-2h, polish to 10/10)

#### PCR-003: Version control polish (9 → 10, ~1h)
Build a snapshot-diff viewer at `/os/snapshots` so any past state is
inspectable from the UI.

#### PCR-004: Runtime metrics deep-health (8 → 10, ~1h)
Add `/api/health/deep` with per-module status, latency percentiles,
last-error timestamps.

#### PCR-007: Ownership stretch (9 → 10, ~30 min)
Nightly orphan-row auditor: scan every table with a `tenant_id` or
`owner` column; report any rows without owners.

#### PCR-008: Job attribution stretch (8 → 10, ~2h)
Customer-facing invoice PDF generator (already in PATCH-411 queue;
reclassify as PCR-008).

#### PCR-011: Compliance wiring (7 → 10, ~2h)
Make `compliance_as_code_engine.compliance_check()` a required
pre-flight for every external write (email, SMS, invoice, push,
deploy). Refused checks log + return structured error.

#### PCR-012: MCP server polish (7 → 10, ~2h)
Expose lineage (PCR-001), glossary (PCR-009), schema registry (PCR-002),
docs index (PCR-010) as MCP resources. Test with Claude Desktop client.

## Execution sequence (the ladder)

**Phase 1 — Foundations (Tier 1, ~6 hours total work)**
1. PCR-009 Business glossary
2. PCR-014 Auto-documentation
3. PCR-005 Audit log unification
4. PCR-006 Data SLAs

After Phase 1: aggregate score 5.5 → ~7.4. Every standard ≥ 5.

**Phase 2 — Structural (Tier 2, ~13 hours total work)**
5. PCR-001 Data lineage engine
6. PCR-015 E2E model lineage (extends PCR-001)
7. PCR-002 Schema registry
8. PCR-013 Anomaly detection
9. PCR-010 Docs index

After Phase 2: aggregate ~9.0. Every standard ≥ 8.

**Phase 3 — Polish (Tier 3, ~8 hours total work)**
10. PCR-012 MCP server polish (pulls everything together)
11. PCR-011 Compliance wiring
12. PCR-003, PCR-004, PCR-007, PCR-008 stretch items

After Phase 3: **aggregate 10.0/10. Every standard = 10.**

## Total estimated effort

~27 engineering hours across 3 phases. At our pace (~2-3 patches per
session), this is **5-8 sessions**.

## Sequencing decisions

- PCR-009 (glossary) first because it makes every subsequent patch
  legible — every PCR will introduce terms the glossary should hold.
- PCR-014 (auto-doc) second because every subsequent patch produces
  code that auto-doc will index.
- PCR-005 + PCR-006 in Tier 1 because they're already 80% done; just
  need consolidation.
- PCR-001 leads Tier 2 because PCR-015 and PCR-013 depend on lineage
  being queryable.
- PCR-012 (MCP) last because it exposes everything else; building it
  earlier means re-doing the resource bindings.

## Anti-patterns to refuse

- ❌ Building DataHub Cloud features for the sake of feature-parity.
  We only build what the 15-standard rubric demands.
- ❌ Counting partial work toward score advancement. Verifier must pass.
- ❌ Touching production without a snapshot.
- ❌ Sliding a standard down to ship faster. Standards are floors, not
  starting points.
- ❌ Building a "context dashboard" as a vanity surface. Each PCR has a
  functional verifier; the dashboard, if any, comes from the verifiers.

## Tracking

Each PCR-NNN gets a row in `MASTER_CHECKLIST.md` with: standard #, target
score, verifier command, ship commit hash. The aggregate score is
displayed in the weekly STATUS block.
