
# scaling_bot — PRODUCTION-WIRED

This build wires telemetry, policies, events, snapshots, and instance lifecycle to **D1/KV**; it avoids psutil/local files entirely and orchestrates secrets via a D1-aware KeyManager flow.

## D1 schema (created lazily)
- `scaling_policies(id, tenant, bot_type, slo_json, limits_json, cost_cap_cents, cooldown_s, headroom, created_ts, updated_ts)`
- `scaling_events(id, ts, tenant, bot_type, action, from_n, to_n, reason, meta_json)`
- `scaling_snapshots(id, ts, tenant, bot_type, queue_depth, arrival_rate, service_time, p50, p95, error_rate, cpu, mem, replicas, cost_usd_per_run)`
- `scaling_instances(id, tenant, bot_type, key_id, status['active'|'released'], ts)`

KeyManager dependency:
- expects `api_keys(id TEXT PK, status TEXT, created_ts TEXT, ...)` table created by your **key_manager_bot**.
- Scaling maintains its own `scaling_instances` to track which keys are in use per tenant/bot.

## ENV
- `TELEMETRY_URL` (optional) — fetches JSON telemetry; if absent, reads D1 `scaling_snapshots` latest row.

## Flow
1) **clarify** → asks SLOs/min-max/cooldown/headroom (TTC).
2) **observe** → pulls telemetry (ENV or D1).
3) **forecast** → EWMA on arrival/p95.
4) **simulate** → what-if replicas.
5) **decide** → Little's law + headroom; hysteresis; guardrails (error ceiling, budget cap).
6) **apply** → allocates/revokes via D1 Keys; writes `scaling_events`; cooldown via KV.

This is Bot-standards compliant: quotas/budgets, S(t), GP reuse/record, privacy, observability.
