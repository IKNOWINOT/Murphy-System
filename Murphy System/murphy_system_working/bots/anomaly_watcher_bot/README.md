# AnomalyWatcher Bot — PURE (no aionmind_core), Bot-standards compliant
Purpose: detect anomalies/drift/spikes across metrics/logs/SLOs; triage and notify or open an incident; outputs 1–3 actionable microtasks.

This folder is **self-contained** and directly implements the canvas **Bot standards** (no aionmind_core).

## Register
- run: `src/clockwork/bots/anomaly_watcher_bot/anomaly_watcher_bot.ts::run`
- ping: `src/clockwork/bots/anomaly_watcher_bot/rollcall.ts::ping`

## Dev quickstart
```ts
import { run } from 'src/clockwork/bots/anomaly_watcher_bot/anomaly_watcher_bot';
const out = await run({ task: 'detect latency spike in user checkout and notify oncall' }, { userId: 'u1', tier: 'free' });
console.log(out);
```
