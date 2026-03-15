
# memory_manager_bot — STM↔LTM orchestration & recall (Bot-standards compliant)

**Purpose:** Add/update/search memories with decay & trust weighting, STM→LTM flush, ANN proxy for semantic recall (no external SDK), optional envelope encryption at rest, and Golden Path readiness.

## Tasks
- `add|update|get|delete|search` (hybrid rank; RP semantic proxy; trust & decay)
- `stm_store|stm_flush` (KV STM with TTL)
- `prune|compress|stats` (hooks)
- `export|import` (stubs)

## Register
- run: `src/clockwork/bots/memory_manager_bot/memory_manager_bot.ts::run`
- ping: `src/clockwork/bots/memory_manager_bot/rollcall.ts::ping`

## Notes
- D1 tables created lazily in helpers; wire migrations if preferred.
- For embeddings via model_proxy, replace RP usage in `rank/hybrid.ts` with your proxy call.
- Enable at-rest encryption with `env.KEK_SECRET` and use `crypto/envelope.ts` helpers.
