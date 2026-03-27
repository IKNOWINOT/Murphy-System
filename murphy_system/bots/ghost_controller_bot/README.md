
# GhostControllerBot — Complete App (Bot-standards compliant)

Drop this folder into `clockwork1/src/clockwork/bots/ghost_controller_bot`.

## What’s included
- **TypeScript (cloud bot)**: schema, run(), rollcall, privacy redaction, microtask pipeline, Kaia clarifier, GP submit + optional POST.
- **Internal shims**: quotas, budgets, golden paths, stability, metrics.
- **Desktop tools**: local relay server, validate server, playback runner (image+OCR+validate post), locator tool, metrics dashboard, context-menu stub.

## Register (per Bot standards)
- run: `src/clockwork/bots/ghost_controller_bot/ghost_controller_bot.ts::run`
- ping: `src/clockwork/bots/ghost_controller_bot/rollcall.ts::ping`

## Desktop quick start
```bash
export GHOST_RELAY_TOKEN=dev-token
python3 desktop/local_relay_server.py           # receive events -> queue.ndjson
python3 desktop/validate_server.py              # receive validation runs -> runs.ndjson
python3 desktop/playback_runner.py automation.json --dry-run
python3 desktop/metrics_dashboard.py -e queue.ndjson -r runs.ndjson -o dashboard.html
```

## Notes
- Privacy redaction is on by default (`params.privacy.redact=true`).
- App allowlist can block unintended captures (`params.allow_apps`).
- GoldenPath POST is optional (`params.gp_post_endpoint`).

