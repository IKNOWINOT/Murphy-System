# CAD Bot (ported from Python) — PURE TypeScript, Bot-standards compliant

**Based on:** `third_party/original/SYN_CORE/agents/modern_arcana/cad_bot.py` (entities + units JSON spec).  
This port mirrors the Python behavior (produce `{entities, units}`) and **upgrades** with: quotas, budget guard/charges, Golden Path reuse/record, stability S(t) breaker, and observability emits.

## Register
- run: `src/clockwork/bots/cad_bot/cad_bot.ts::run`
- ping: `src/clockwork/bots/cad_bot/rollcall.ts::ping`

## Output
`result.cad_spec` matches the Python schema: `{ entities:[{type,params}], units }`.

## Quickstart
```ts
import { run } from 'src/clockwork/bots/cad_bot/cad_bot';
const out = await run({ task: 'make a 100x5x100 plate (mm) and export step' }, { userId: 'u1', tier: 'free' });
console.log(out.result.cad_spec);
```

