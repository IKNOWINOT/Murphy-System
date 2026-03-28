# triage_bot — Clockwork1 (TypeScript) — bots-only drop-in

Router that takes a free-form task, checks Golden Paths, runs a capability-aware roll-call,
ranks candidates with stability S(t) + KaiaMix + cost/latency predictions, and stages HIL
if confidence or risk suggests it.

This folder is designed to live **only** at:
`clockwork1/src/clockwork/bots/triage_bot/*`
and references sibling modules under `src/clockwork/...` (wired by Codex).

## Key features
- Bot Standards / Bot Base compliant (no raw OpenAI, uses `model_proxy`).
- Quotas/Budgets guardrails (via `withBotBase` in ../_base/bot_base.ts).
- GP-first: reuse if available within token budget; record GP candidate on success.
- Capability-aware roll-call: candidates from `bot_capabilities`, not a hardcoded list.
- Ranking: S(t)-style score blended with KaiaMix (Veritas/Vallon/Kiren) and historical stats.
- Bandit hook for learning (optional, persisted in `stats_json`).
- Emits `run.complete` / `hil.required` via `audit_events`.
- Tests with Vitest (mocks for DB/KV/model_proxy).

## External modules referenced (wired by Codex)
- ../../orchestration/model_proxy
- ../../orchestration/experience/golden_paths
- ../../orchestration/stability
- ../../orchestration/quota_mw
- ../../orchestration/budget_governor
- ../../observability/emit
- ../../memory/ltm_adapter (optional)

## SLOs
- p95 triage decision ≤ 2.5s (mini profile)
- avg cost ≤ $0.01/run
