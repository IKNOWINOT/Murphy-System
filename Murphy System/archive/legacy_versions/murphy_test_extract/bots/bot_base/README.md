# bot_base — Template Bot (PURE), Bot-standards compliant

This is a **template** bot. Copy this folder, rename it (folder + import paths), and update:
- `BOT_NAME`, `KAIA_MIX`, and `SYSTEM_PROMPT` in `bot_base.ts`
- `KEYWORDS` and `DEFAULT_ARCHETYPE` in `rollcall.ts`
- optional adapters in `internal/adapters/*`

## Fits the canvas Bot standards
- Quotas/tiers, budget guard/charges
- Golden Path reuse/record
- Stability S(t) breaker
- Observability emits (console or `ctx.emit`)
- Voice hooks are optional (not enabled by default)

## Register (after rename)
- run: `src/clockwork/bots/<your_bot>/<your_bot>.ts::run`
- ping: `src/clockwork/bots/<your_bot>/rollcall.ts::ping`

## Dev quickstart
```ts
import { run } from 'src/clockwork/bots/bot_base/bot_base';
const out = await run({ task: 'plan and create a short draft' }, { userId: 'u1', tier: 'free' });
console.log(out);
```
