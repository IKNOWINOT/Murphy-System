
# FeedbackBot — Production Feedback Orchestrator (Bot Standards compliant)

Purpose: Ingest and analyze feedback signals (explicit & implicit) from all bots and desktop agents, compute reinforcement-aware decayed scores with robust aggregation, detect recurring clusters, and (optionally) propose remediation actions. Integrates with Golden Paths and S(t).

## Register
- run: `src/clockwork/bots/feedback_bot/feedback_bot.ts::run`
- ping: `src/clockwork/bots/feedback_bot/rollcall.ts::ping`

## Example
```ts
// Ingest
await run({ task:'ingest', params:{ events:[{ ts:new Date().toISOString(), bot:'ghost_controller_bot', value:1, meta:{category:'microtask.pass'} }] } }, ctx);

// Analyze
await run({ task:'analyze', params:{ strategy:'decay', half_life_days:3 } }, ctx);

// Propose actions (gated)
await run({ task:'propose_actions', params:{ propose:{enabled:true} } }, ctx);
```
