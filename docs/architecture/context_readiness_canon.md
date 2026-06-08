# Context Readiness Canon — LOCKED 2026-06-08

## Source

This canon is Murphy's response to the DataHub guide "Context: The Missing
Link Between Your Data Stack and AI Success" (Acryl Data / DataHub, 2024).
Founder directive 2026-06-08: **"Get us up to ten in all standard."**

The guide's thesis: 80% of AI projects fail because the data foundation
lacks **context** — and context has three layers (technical, operational,
business/social) plus an AI-agent-readable layer that lets agents reason
over metadata.

We accept the framework. We do NOT accept that DataHub Cloud is the only
way to achieve it. Murphy will build the same outcomes natively, in
sandbox-first PSM-logged increments, and score them against the same rubric.

## The 15 Standards (one rubric)

Each standard is scored 0–10. Target: **every standard ≥ 7 ("AI-ready"),
with stretch to 10/10 across the board**. This canon defines what 10/10
LOOKS LIKE for each, and the test that proves it.

### Layer 1: Technical Context

| # | Standard | What 10/10 looks like | Test that proves it |
|---|---|---|---|
| 1 | **Data lineage / provenance** | Any output (LLM call, patch, email, invoice) can be traced backward through every input, transform, and source in ≤ 1 query | `lineage_trace(output_id)` returns full DAG in < 500ms |
| 2 | **Schema registry** | Every entity, table, event has a versioned schema in ONE canonical registry; old versions retained; breaking changes blocked | `schema_registry.list()` shows all schemas; CI rejects breaking changes |
| 3 | **Version control** | Every code, schema, config, automation change is git-tracked, snapshotted, and reversible via canonical restore | Already at 9/10. Stretch: snapshot diff viewer in `/os` |

### Layer 2: Operational Context

| # | Standard | What 10/10 looks like | Test that proves it |
|---|---|---|---|
| 4 | **Runtime metrics** | `/api/health` exposes deep health: per-module status, latency p50/p95/p99, last-error timestamp, dependency health | `/api/health/deep` returns structured per-module health |
| 5 | **Audit log unification** | The 8 fragmented audit DBs roll into ONE `unified_audit` view with consistent schema (`ts, actor, action, target, outcome, refs`) | `audit_query(filter)` works across all sources |
| 6 | **Data SLAs** | Every public-surface endpoint has a declared SLA (uptime, freshness, latency). Watchdog enforces. Breaches paged | `sla_registry.list()` returns commitments; `sla_report()` shows last-30d compliance |
| 7 | **Ownership / tenancy** | Every secret, every entity, every job has a clear owner (platform OR tenant_id). No orphan rows. Cross-tenant reads refused at code level | Already at 9/10. Stretch: orphan-row auditor runs nightly |
| 8 | **Job attribution** | Every billable action (LLM call, voice min, SMS, storage GB-day) tagged with (tenant_id, job_id). Customer-facing invoices auto-roll | Already at 8/10. Stretch: invoice PDF generator |

### Layer 3: Business / Social Context

| # | Standard | What 10/10 looks like | Test that proves it |
|---|---|---|---|
| 9 | **Business glossary** | Every domain term used in Murphy (HITL, R-number, PATCH, tenant_identity, Rosetta, Conductor, etc.) has a one-paragraph definition in `docs/glossary.md`, version-controlled, queryable | `glossary.lookup("HITL")` returns definition; CI fails if new term introduced without definition |
| 10 | **Unstructured docs / tribal knowledge** | All `docs/*.md` indexed for semantic search; agent can answer "why does X exist?" from docs alone | `docs.search(query)` returns top-K relevant doc chunks |
| 11 | **Compliance / governance modules** | `compliance_as_code_engine.py` is wired to: every external action (email, SMS, invoice) checks policy first; violations logged + refused | `compliance_check(action)` is in the path of every external write |

### Layer 4: AI-Agent-Readable Context

| # | Standard | What 10/10 looks like | Test that proves it |
|---|---|---|---|
| 12 | **MCP server / agent-readable context** | `src/mcp_plugin/` exposes: entities, audit, lineage, glossary, schemas as MCP resources. Outside agents can reason over Murphy's metadata | MCP client (e.g. Claude Desktop) connects, lists resources, queries lineage |
| 13 | **Anomaly detection / data drift** | Output streams monitored for drift; alerts on: latency spike, LLM cost spike, output-length drift, refusal-rate spike | `anomaly_dashboard()` shows last-24h anomalies; configurable thresholds |
| 14 | **Auto-documentation** | Every module in `src/` has an auto-generated `README.md` derived from code + commits + last-N-patches. Refreshes nightly | `docs/auto/<module>.md` exists for every src module; CI checks freshness |
| 15 | **End-to-end model lineage** | Any agent output can be traced to: which prompt, which model, which inputs, which upstream patches, which docs were in context | `output_lineage(call_id)` returns full causal chain |

## Standing definitions

- **"AI-ready"** = score ≥ 7. Below this, the system is dangerous to operate at scale.
- **"Best-in-class"** = score = 10. The capability is so clean that an outside engineer could understand and trust it within 5 minutes.
- **"Shape of complete"** = a test that an outside party can run and a humanly-readable result. No "trust me, it works."

## Operating rules

1. **Every patch declares which standards it moves.** Commit messages cite
   the standard # (e.g. `STD-9 4→10: Business glossary shipped`).
2. **No regressions.** If a patch lowers any standard's score, it must be
   declared, justified, and approved.
3. **Snapshot before every standards-shift.** Per `before_after_canon.md`.
4. **Every standard has a verifier.** A one-liner shell or Python command
   that recomputes the score from production state. The verifier IS the
   shape of complete.
5. **Quarterly re-audit.** Walk the 15 standards. Update scores. Publish.

## Investment ledger

The guide is right: under-investing in context is the single highest-leverage
mistake an AI company can make. Murphy will track context investment as a
first-class line item:
- Time spent on context-readiness patches (PCR-001 .. PCR-015) is logged
  in the cost ledger as `caller='context_readiness'`
- The aggregate is reported in the weekly STATUS block
- Goal: > 20% of engineering time spent on context until all standards ≥ 7,
  then > 10% steady-state to prevent decay

## Non-goals (what this canon does NOT require)

- We do NOT need DataHub Cloud. We're building the outcomes natively.
- We do NOT need a 100-connector catalog. Murphy IS the data system; we
  don't catalog third-party warehouses, we catalog our own work.
- We do NOT need enterprise SSO/SOC2 to score 10/10 on these standards.
  Those are separate verticals (security canon, not context canon).

## Lessons embedded

- **L23 (new):** Capability scores are a forcing function. Without them,
  "we should improve X" stays a sentence forever. With them, "X is 4/10
  and we agreed it should be 7" creates obligation.
- **L24 (new):** The guide is selling DataHub, but the FRAMEWORK is sound.
  Borrow the framework; reject the procurement pitch. Murphy beats DataHub
  on cost (zero), on integration depth (we ARE the system), and on
  agent-native design (DataHub bolted on MCP; we are MCP-native).
