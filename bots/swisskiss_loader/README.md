# swisskiss_loader — Clockwork1 (TypeScript) — bots-only drop-in

This folder contains the **SwissKiss Manual Loader Bot v2.0** ported to TypeScript and aligned with
the **Clockwork1 — Bot Upgrade Protocol (Production SOTA)**. It is designed to live **only** under:

`clockwork1/src/clockwork/bots/swisskiss_loader`

It **uses `bot_base`** (provided here under `../_base/bot_base.ts`) and references the canvas for validation.
Other framework pieces (D1 access, Golden Paths, budgets/quotas, model proxy, observability) are **imported
from sibling directories** under `src/clockwork` and will be wired by Codex in your repo.

## Files here
- `schema.ts` — I/O contracts and meta types
- `swisskiss_loader.ts` — main `run()` implementation (bot loader)
- `rollcall.ts` — roll-call gate / capability ping
- `repo_utils.ts` — HTTPS-based repo inspection (README/License/Reqs/Languages/Risk)
- `../_base/bot_base.ts` — base wrapper (stability S(t), quotas/budgets, GP, metrics)
- `test/swisskiss_loader.spec.ts` — Vitest tests (mocks required)

## External dependencies (referenced, not included here)
- `src/clockwork/orchestration/model_proxy.ts`
- `src/clockwork/orchestration/stability.ts`
- `src/clockwork/orchestration/quota_mw.ts`
- `src/clockwork/orchestration/budget_governor.ts`
- `src/clockwork/orchestration/experience/golden_paths.ts`
- `src/clockwork/observability/emit.ts`

## Integration
1) Drop this folder under the path above.
2) Ensure the external modules exist (Codex wiring).
3) Bind Worker env (CLOCKWORK_DB/KV_QUOTA/KV_MAIN) where your orchestrator calls this bot.
4) Run tests with Vitest (mocks for model_proxy and D1/KV provided in spec).
