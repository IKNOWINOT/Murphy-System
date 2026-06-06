# MURPHY ENDPOINT MAP — AUTHORITATIVE
**Audited 2026-05-25 by walking the source code, not memory.**

Total: 1,727 unique routes across 270 prefixes, in 64 source files.
Full machine-readable inventory: `/app/murphy_routes_full.json` (12,633 lines)
On-server inventory: `/tmp/murphy_routes.json`

## Discovery method (re-run anytime to refresh)
```python
# /opt/Murphy-System/scripts/dump_routes.py
import re, json, os
routes = []
# Inline @app routes in src/runtime/app.py
pattern_app = re.compile(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']')
# @router routes — find APIRouter(prefix=...) + @router decorators
pattern_prefix = re.compile(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']')
pattern_router = re.compile(r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']')
```

Skip `.bak`, `.pre-*`, hidden files. The mount point is `app.include_router(...)`.

## What the founder needs to know

### Three lanes the founder uses (most important)

**LANE 1 — Prompt to output (chat with Murphy):**
- `POST /api/chat` — passive responder, canned greeting (NOT the real lane 1)
- `POST /api/rosetta/dispatch` — REAL: spawns 4-agent swarm, returns DAG ID, fires LLM. ✅ Verified DeepInfra call succeeds.
- `GET /api/swarm/bus/feed` — SSE stream of agent notifications during dispatch
- ⚠️ **MISSING:** `GET /api/dag/{id}` for result retrieval. Output vanishes today. Build in PATCH-453a.

**LANE 2 — Patch the system (founder self-modification):**
- `POST /api/platform/self-modification/launch` — submit a proposal (requires `X-Murphy-Platform-Operator` header, token in memory key #51)
- `GET /api/platform/self-modification/ledger` — view hash-chained history (currently **20 verified entries**)
- `GET /api/platform/self-modification/console` — minimal HTML UI (auth-walled)
- ❌ Memory's `/status` doesn't exist. There are only three endpoints under this prefix.

**LANE 3 — See autonomous work:**
- `GET /api/swarm/agents/status` — 9 swarm agents, run counts
- `GET /api/swarm/mind/status` — cycle count + confidence
- `GET /api/swarm/mind/history` — recent cycle telemetry
- `GET /api/mail/outbound/queue` — outbound mail draft queue (monolith)
- `GET /api/mail/outbound/stats` — counts by status
- `GET /api/swarm/hitl/pending` — HITL approval queue (28 jobs)
- ⚠️ HITL engineering jobs live separately in `hitl_jobs.db` — no clean API
- `GET /api/public/stats` — landing-page aggregator (swarm, mind, MFGC, crm_deals)

### Self-modification gateway (PSM) — corrected

**Real endpoints under `/api/platform/self-modification/`:**
| Method | Path | Purpose |
|---|---|---|
| POST | `/launch` | Submit + execute a proposal (operator-token required) |
| GET | `/ledger` | Hash-chained proposal history |
| GET | `/console` | Built-in HTML console (cookie auth) |

**Schema for POST /launch body:** Pydantic `LaunchRequest` with `proposal_id`, `operator_id`, `justification`. Required header: `X-Murphy-Platform-Operator: <token>`.

Module: `src/platform_self_modification/endpoint.py`
Ledger DB: `/var/lib/murphy-production/psm_ledger.db` (DIFFERENT from the root-owned 0-byte one I confused earlier — the real one is wherever `SelfEditLedger._resolve_ledger_path()` points)

### Top 20 prefixes by route count

| Prefix | Routes | Source |
|---|---|---|
| `/api/trading` | 55 | app.py, paper_trading_routes.py, risk_routes.py |
| `/api/billing` | 53 | billing/api.py, app.py |
| `/api/grants` | 51 | billing/grants/api.py |
| `/api/self` | 39 | app.py, self_manifest_router.py |
| `/api/onboarding` | 33 | platform_onboarding/onboarding_api.py |
| `/api/comms` | 31 | comms_hub_routes.py |
| `/api/mgmt` | 29 | management_ai_router.py |
| `/api/manifold` | 25 | dynamic_manifold_router.py, manifold_router.py |
| `/api/shadow` | 25 | app.py |
| `/api/shield` | 25 | shield_wall.py |
| `/api/dev` | 24 | dev_module/api.py |
| `/api/boards` | 21 | board_system/api.py |
| `/api/aionmind` | 20 | aionmind/api.py, chat_router.py |
| `/api/automation` | 20 | app.py |
| `/api/admin` | 20 | app.py |
| `/api/gate-synthesis` | 19 | app.py |
| `/api/guest` | 19 | guest_collab/api.py |
| `/api/moderator` | 19 | comms_hub_routes.py |
| `/api/auth` | 18 | app.py |
| `/api/crm` | 18 | crm/api.py, app.py |

### Memory errors corrected (this audit)

| Old memory claim | Reality |
|---|---|
| `/api/capital/proposals` | ❌ 404. Real: `/state`, `/rounds`, `/rounds/open`, `/investors`, `/investors/import`, `/commitments`, `/dataroom`, `/dataroom/upload`, `/agent/init` |
| `/api/mail/outbound/review` (monolith) | ❌ 404 on monolith. Exists on edge node `:8011`. On monolith, use `/api/mail/outbound/queue` |
| `/api/mail/outbound/approve` | ⚠️ Wrong shape. Real: `POST /api/mail/outbound/{queue_id}/approve` |
| `/api/phone/dial` "unmounted on monolith" | ❌ WRONG — it's mounted (via `patch406a_voice_telephony.py` line 453). Returns proper 503-ish error: `credentials_not_in_vault`. Just needs Twilio creds via `POST /api/phone/request-credentials` |
| `/api/platform/self-modification/status` | ❌ Doesn't exist. Real endpoints: `/launch`, `/ledger`, `/console` only |

### Known-good golden examples (test these to verify health)
```bash
KEY="<founder_key>"

# Lane 1
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"task":"Write a paragraph about MEP contractors"}' \
  https://murphy.systems/api/rosetta/dispatch

# Lane 2
curl -H "X-API-Key: $KEY" https://murphy.systems/api/platform/self-modification/ledger

# Lane 3
curl -H "X-API-Key: $KEY" https://murphy.systems/api/swarm/agents/status
curl -H "X-API-Key: $KEY" https://murphy.systems/api/swarm/mind/status
curl -H "X-API-Key: $KEY" https://murphy.systems/api/mail/outbound/queue
```

### Routers that mount their own /api/* prefix (66 total)
Major ones:
- `aionmind/api.py` → `/api/aionmind` (14 routes) — alt chat/cognitive surface
- `billing/api.py` → `/api/billing` (43 routes) — Stripe + NOWPayments + subscriptions
- `billing/grants/api.py` → `/api/grants` (55 routes) — grants tracking
- `board_system/api.py` → `/api/boards` (19 routes)
- `crm/api.py` → `/api/crm` (17 routes)
- `dev_module/api.py` → `/api/dev` (24 routes)
- `dispatch_routes.py` → `/api/dispatch` (11 routes)
- `engineering_router.py` → `/api/eng` (6 routes) — document ingest + paper fetch + RAG
- `forge_router.py` → `/api/forge` (8 routes) — app builder
- `ghost_runner.py` → `/api/ghost-runner` (5 routes)
- `manifold_router.py` + `dynamic_manifold_router.py` → `/api/manifold/*`
- `marketing_router.py` → `/api/marketing` (8 routes)
- `ml/api.py` → `/api/ml` (12 routes)
- `paper_trading_routes.py` → `/api/trading` (11 routes)
- `patch412_capability_cube.py` → `/api/cube` (6 routes) — capability discovery + dispatch
- `platform_self_modification/endpoint.py` → `/api/platform/self-modification` (3 routes)
- `risk_routes.py` → `/api/trading` (15 routes)
- `rsc_router.py` → `/api/rsc` (5 routes) — Recursive Stability Controller
- `shield_wall.py` → `/api/shield` (25 routes)
- `web_tool_router.py` → `/api/web` (4 routes)
- `workflow_ops_router.py` → `/api/ops` (9 routes)

### Refresh procedure
When endpoints feel uncertain:
1. SSH to `5.78.41.114`
2. Run the discovery snippet at top of this file
3. Save to `/tmp/murphy_routes.json`
4. Run live HTTP audit with `X-API-Key` header
5. Update this file with any new errors
6. Memory key #54 references this file as authoritative

### Cleanup needed (not blocking)
- 7 stale `app.py.pre-*` files in `/opt/Murphy-System/src/runtime/` — pollute grep results
- 3 stale `patch412_capability_cube.py.pre-*` files
- 4 stale `billing/api.py.bak*` files

---

## BLOCK-A.2.8 — Registry endpoints (deployed 2026-05-25)

| Endpoint | Purpose |
|---|---|
| `GET /api/registry/summary` | counts per registry + audit_events |
| `GET /api/registry/gates?min_gates=N` | items with <N of 5 gates set |
| `GET /api/registry/search?q=foo` | text search across all 5 registries |
| `GET /api/registry/pages` | list pages (filters: page_type, tenant_scope, capability) |
| `GET /api/registry/pages/{id}` | single page |
| `GET /api/registry/routes` | list routes (filters: method, capability, tenant_scope) |
| `GET /api/registry/routes/{id}` | single route |
| `GET /api/registry/capabilities` | list capabilities (filters: source, domain, risk_class) |
| `GET /api/registry/capabilities/{id}` | single capability |
| `GET /api/registry/actions` | list actions (filters: risk_class, hitl_lane, reversibility) |
| `GET /api/registry/actions/{id}` | single action |
| `GET /api/registry/cadence` | list cadence (filters: source_type, tier, health_status) |
| `GET /api/registry/cadence/{id}` | single cadence source |

Module: `src/registry_router.py` mounted in `app.py:2046`
DB: `murphy_registry.db` (5 tables) + `murphy_audit.db` (events ext)

---

## BLOCK-A.3.1 — Job pipeline endpoints (deployed 2026-05-25)

| Endpoint | Purpose |
|---|---|
| `GET /api/jobs` | list jobs (filter: status; pagination) |
| `GET /api/jobs/{job_number}` | resolve JOB- → chain detail + step/file counts |
| `GET /api/jobs/{job_number}/files` | list artifacts for a job |

Note: Cloudflare lowercases path segments. SQL uses `UPPER()` comparison
so both `JOB-2026-00001` and `job-2026-00001` resolve.

DB extension: `chain_engine.chain_requests.job_number` (UNIQUE), `job_files`

---

## BLOCK-A.4.1 — Pulse infrastructure (deployed 2026-05-25)

**New DB:** `cadence_pulse.db` (NOT `murphy_pulse.db` — avoids collision
with `economic_pulse.db.pulse_log` financial domain)
**Table:** `pulse_ticks` (id, source_name, ts, drift_ms, duration_ms,
success, error_text, payload_json) + 4 indexes

**Helper:** `src/cadence_emit.py` — single function `emit_heartbeat()`
that writes pulse_tick + updates cadence_registry rolling state.
CLI: `python3 src/cadence_emit.py <source_name> [--fail] [--error MSG]
[--duration_ms N] [--payload JSON] [--publish-to-bus]`

**Wired to 3 systemd .service files via ExecStartPost=** :
- murphy-watchdog.service
- murphy-hitl-expire.service
- murphy-autonomy-reset.service

**Effect on existing endpoint:**
- `GET /api/registry/cadence` — `health_status` GENERATED column now
  flips from 'never_ticked' to 'healthy/degraded/failing' based on
  rolling state, no new endpoint needed
