# analysisbot — Clockwork1 (TypeScript) — SQL Analyst upgrade (bots-only)

**New capability:** Natural‑language **SQL analysis** with schema awareness, strict read‑only guardrails, optional execution, and result summarization. 
Compliant with Bot Standards & `bot_base` (quota/budget/Stability S(t)/Golden Paths/observability). 
Designed to live only at: `clockwork1/src/clockwork/bots/analysisbot/*`

## What’s new
- NL → SQL (dialect-aware) via `model_proxy` (JSON mode) with rationale and warnings
- **Safety**: read‑only enforcement (SELECT‑only), single statement, mutation keywords blocked; auto‑downgrade to dry‑run when unsafe
- **Schema‑aware**: accepts inline schema OR fetches via `../../io/sql_adapter.getSchema(dbId)`
- **Optional execution**: `execute: true` runs query through `../../io/sql_adapter.execute(dbId, sql, {limit, readonly:true})`
- **Summarization**: compact result profile + natural language takeaways (JSON mode)
- **GP-first** replay; promotion on ≥20 passes @ ≥0.9 pass_rate

## External adapters (wired by Codex)
- ../../orchestration/model_proxy
- ../../orchestration/experience/golden_paths
- ../../orchestration/{stability, quota_mw, budget_governor}
- ../../observability/emit
- ../../io/sql_adapter       (ASSUMED: getSchema(dbId) -> Schema; execute(dbId, sql, {limit, readonly}) -> {rows: any[], columns: string[]})

## SLOs
- p95 ≤ 2.7s (mini profile), ≤ 1.2s on GP
- Avg cost ≤ $0.012 per request
