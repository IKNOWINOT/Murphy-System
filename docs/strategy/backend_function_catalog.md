# Backend Function Catalog — PCR-018 / Phase 2 of Final Shape of Complete

**Generated:** 2026-06-08T19:56:54+00:00
**Generator:** `scripts/backend_catalog_check.py`
**Plan:** `docs/strategy/final_shape_of_complete_plan.md` (Phase 2)
**Pairs with:** `docs/strategy/ui_surface_audit.md` (Phase 1)

> This file is AUTO-GENERATED. Do not edit by hand — re-run the
> generator. Hand-edits are wiped on next run.

## Purpose

Inverse of Phase 1's UI audit. Every backend HTTP route discovered
in `src/` enumerated and classified:

| Class | Meaning |
|---|---|
| 🟢 UI-LINKED | At least one `static/*.html` fetches this route |
| 🔧 INTERNAL | No UI consumer; probe returns 401/403 (auth-gated, expected) or non-GET (can't probe) |
| 👻 GHOST | No UI consumer; probe returns 200 (real backend, no UI handle — Phase 3 closure target) |
| 💀 DEAD | Registered but probe returns 404/500 (broken endpoint) |
| ❓ UNKNOWN | Couldn't probe (network error, parametric path with no UI match) |

## Headline numbers

- **Total backend routes:** 2164
- **Unique UI fetch targets:** 38

### Classification breakdown

| Class | Count | % |
|---|---|---|
| 🟢 UI-LINKED | 41 | 1.9% |
| 🔧 INTERNAL | 1848 | 85.4% |
| 👻 GHOST | 130 | 6.0% |
| 💀 DEAD | 145 | 6.7% |
| ❓ UNKNOWN | 0 | 0.0% |

## UI-LINKED routes (the connected surface)

These backend routes are reachable from the UI. Healthy.

| Method | Path | File |
|---|---|---|
| GET | `/` | `src/murphy_ops.py` |
| GET | `/` | `src/auto_wire_router.py` |
| GET | `/` | `src/murphy_edge.py` |
| GET | `/` | `src/murphy_robotics.py` |
| GET | `/` | `src/runtime/app.py` |
| GET | `/api/account/billing-history` | `src/runtime/app.py` |
| GET | `/api/account/subscription` | `src/runtime/app.py` |
| GET | `/api/account/tenant` | `src/runtime/app.py` |
| POST | `/api/auth/login` | `src/fastapi_security.py` |
| GET | `/api/auth/login` | `src/runtime/app.py` |
| POST | `/api/auth/login` | `src/runtime/app.py` |
| POST | `/api/auth/logout` | `src/runtime/app.py` |
| GET | `/api/auth/me` | `src/runtime/app.py` |
| POST | `/api/chat` | `src/runtime/app.py` |
| GET | `/api/chat/history` | `src/runtime/app.py` |
| POST | `/api/contact/submit` | `src/runtime/app.py` |
| GET | `/api/dlfr/list` | `src/runtime/app.py` |
| GET | `/api/dlfr/load/{package_id}` | `src/runtime/app.py` |
| GET | `/api/dlfr/stats` | `src/runtime/app.py` |
| GET | `/api/health` | `src/demo_deliverable_generator.py` |
| GET | `/api/health` | `src/runtime/app.py` |
| GET | `/api/health` | `src/runtime/tiered_app_factory.py` |
| GET | `/api/health/capacity` | `src/production_router.py` |
| GET | `/api/hitl/items` | `src/runtime/app.py` |
| POST | `/api/hitl/items/bulk-approve` | `src/runtime/app.py` |
| POST | `/api/hitl/items/bulk-reject` | `src/runtime/app.py` |
| GET | `/api/hitl/queue` | `src/runtime/app.py` |
| GET | `/api/incidents` | `src/patch_incident_router.py` |
| GET | `/api/llm/spend` | `src/runtime/app.py` |
| GET | `/api/mail/outbound/queue` | `src/patch417_outbound_queue.py` |
| GET | `/api/mail/outbound/queue` | `src/runtime/app.py` |
| GET | `/api/mail/outbound/{queue_id}` | `src/patch417_outbound_queue.py` |
| GET | `/api/mail/outbound/{queue_id}` | `src/runtime/app.py` |
| POST | `/api/payments/nowpayments/checkout` | `src/runtime/app.py` |
| POST | `/api/rosetta/dispatch` | `src/runtime/app.py` |
| GET | `/api/self/audit` | `src/runtime/app.py` |
| POST | `/api/support/ticket` | `src/patch_support_system.py` |
| GET | `/api/work/list` | `src/runtime/app.py` |
| GET | `/api/work/{dag_id}` | `src/runtime/app.py` |
| PATCH | `/api/work/{dag_id}/complete` | `src/runtime/app.py` |
| POST | `/{slug}/chat` | `src/tenant_chat_endpoint.py` |

## GHOST routes (the directive's main target)

These routes return 200 OK but have no UI handle. They represent
**backend power without a user surface** — exactly the gap the
directive calls out.

Each one falls into one of three categories (Phase 3 will decide):
- **Promote to UI** — has obvious user value, deserves a CTA
- **Document as internal** — legitimate machine-only endpoint
- **Deprecate** — orphan code, no longer needed

| Method | Path | File |
|---|---|---|
| GET | `/agents` | `src/r604_agents_surface.py` |
| GET | `/agents` | `src/aionmind/chat_router.py` |
| GET | `/api/account/flow` | `src/runtime/app.py` |
| GET | `/api/agents` | `src/r604_agents_surface.py` |
| GET | `/api/agents` | `src/runtime/app.py` |
| GET | `/api/agents/artifacts` | `src/r604_agents_surface.py` |
| GET | `/api/audit/health` | `src/patch407_security_audit.py` |
| GET | `/api/auth/providers` | `src/runtime/app.py` |
| GET | `/api/auth/role` | `src/runtime/app.py` |
| GET | `/api/auth/whoami` | `src/runtime/app.py` |
| GET | `/api/automation/loop/status` | `src/runtime/app.py` |
| GET | `/api/billing/products` | `src/runtime/app.py` |
| GET | `/api/brain/status` | `src/brain_api.py` |
| GET | `/api/bus/status` | `src/event_bus.py` |
| GET | `/api/cidp/stats` | `src/runtime/app.py` |
| GET | `/api/client-solutions/health` | `src/patch403_client_solutions.py` |
| GET | `/api/comms/email/inbox` | `src/comms_hub_routes.py` |
| GET | `/api/comms/email/outbox` | `src/comms_hub_routes.py` |
| GET | `/api/comms/video/sessions` | `src/comms_hub_routes.py` |
| GET | `/api/compliance/recommended` | `src/runtime/app.py` |
| GET | `/api/compliance/toggles` | `src/runtime/app.py` |
| GET | `/api/conductor/healthz` | `src/conductor/routes.py` |
| GET | `/api/connectors/known` | `src/murphy_connector_agent.py` |
| GET | `/api/connectors/stats` | `src/murphy_connector_agent.py` |
| GET | `/api/corpus/stats` | `src/runtime/app.py` |
| GET | `/api/crypto/status` | `src/runtime/app.py` |
| GET | `/api/demo/deliverable/formats` | `src/runtime/app.py` |
| GET | `/api/demo/export` | `src/runtime/app.py` |
| GET | `/api/demo/forge-stream` | `src/runtime/app.py` |
| GET | `/api/gate-synthesis/health` | `src/runtime/app.py` |
| GET | `/api/identity/health` | `src/patch410_unified_identity.py` |
| GET | `/api/info` | `src/runtime/app.py` |
| GET | `/api/internal/health` | `src/internal_auth.py` |
| GET | `/api/ledger/status` | `src/runtime/app.py` |
| GET | `/api/manifest` | `src/runtime/app.py` |
| GET | `/api/marketplace/agents` | `src/runtime/app.py` |
| GET | `/api/marketplace/categories` | `src/runtime/app.py` |
| GET | `/api/matrix/chat/rooms` | `src/runtime/app.py` |
| GET | `/api/murphy/ask-steve/authorities` | `src/production_router.py` |
| GET | `/api/pcc/status` | `src/runtime/app.py` |
| GET | `/api/phone/health` | `src/patch406a_voice_telephony.py` |
| GET | `/api/picarx/spec` | `src/patch408_household_picarx.py` |
| GET | `/api/policy/autonomy/history` | `src/patch434_routes.py` |
| GET | `/api/readiness` | `src/runtime/app.py` |
| GET | `/api/repair/proposals` | `src/runtime/app.py` |
| GET | `/api/roi-calendar/events` | `src/runtime/app.py` |
| GET | `/api/rosetta/status` | `src/runtime/app.py` |
| GET | `/api/rrom/history` | `src/runtime/app.py` |
| GET | `/api/rrom/snapshot` | `src/runtime/app.py` |
| GET | `/api/self-fix/status` | `src/runtime/app.py` |
| GET | `/api/support/tickets` | `src/patch_support_system.py` |
| GET | `/api/swarm/critic/modes` | `src/runtime/app.py` |
| GET | `/api/swarm/mind/status` | `src/runtime/app.py` |
| GET | `/api/system/health` | `src/module_registry.py` |
| GET | `/api/system/modules` | `src/module_registry.py` |
| GET | `/api/tenant/check-slug` | `src/runtime/app.py` |
| GET | `/api/trading/emergency/status` | `src/trading_routes.py` |
| GET | `/api/trading/graduation/status` | `src/trading_routes.py` |
| GET | `/api/trading/paper/status` | `src/runtime/app.py` |
| GET | `/api/trading/risk/assessment` | `src/trading_routes.py` |
| GET | `/api/ui/links` | `src/runtime/app.py` |
| GET | `/api/v1/docs` | `src/murphy_api_server.py` |
| GET | `/api/v1/openapi.json` | `src/murphy_api_server.py` |
| GET | `/api/v1/ping` | `src/murphy_api_server.py` |
| GET | `/api/vault/health` | `src/patch405_secrets_vault.py` |
| GET | `/api/visual/snapshots` | `src/runtime/app.py` |
| GET | `/api/wallet/balances` | `src/runtime/app.py` |
| GET | `/api/world/business-domains` | `src/runtime/app.py` |
| GET | `/audit` | `src/patch407_security_audit.py` |
| GET | `/audit` | `src/aionmind/api.py` |
| GET | `/customers` | `src/runtime/app.py` |
| GET | `/customers` | `src/billing/api.py` |
| GET | `/deck` | `src/runtime/app.py` |
| GET | `/desktop` | `src/runtime/app.py` |
| GET | `/desktop/install_murphy_desktop.bat` | `src/runtime/app.py` |
| GET | `/devices` | `src/patch410_unified_identity.py` |
| GET | `/dlfr` | `src/runtime/app.py` |
| GET | `/favicon.ico` | `src/runtime/app.py` |
| GET | `/founder` | `src/production_router.py` |
| GET | `/health` | `src/patch412_capability_cube.py` |
| GET | `/health` | `src/management_ai_router.py` |
| GET | `/health` | `src/self_manifest_router.py` |
| GET | `/health` | `src/demo_deliverable_generator.py` |
| GET | `/health` | `src/demo_deliverable_generator.py` |
| GET | `/health` | `src/r604_agents_surface.py` |
| GET | `/health` | `src/founder_update_api.py` |
| GET | `/health` | `src/auar_api.py` |
| GET | `/health` | `src/form_intake/api.py` |
| GET | `/health` | `src/telemetry_learning/api.py` |
| GET | `/household` | `src/patch408_household_picarx.py` |
| GET | `/marketplace` | `src/runtime/app.py` |
| GET | `/module-instances/` | `src/module_instance_api.py` |
| GET | `/module-instances/audit/export` | `src/module_instance_api.py` |
| GET | `/module-instances/audit/trail` | `src/module_instance_api.py` |
| GET | `/module-instances/status/manager` | `src/module_instance_api.py` |
| GET | `/module-instances/status/resources` | `src/module_instance_api.py` |
| GET | `/module-instances/types` | `src/module_instance_api.py` |
| GET | `/phone` | `src/patch406a_voice_telephony.py` |
| GET | `/picarx` | `src/patch408_household_picarx.py` |
| GET | `/start` | `src/production_router.py` |
| … | _(30 more — see source)_ | … |

## INTERNAL routes (auth-gated or non-GET, no UI consumer)

These routes are real but expected to be internal. No action.
Total: **1848**

Top 30 by path:

| Method | Path | Status |
|---|---|---|
| GET | `/.well-known/jwks.json` | 429 |
| GET | `/.well-known/openid-configuration` | 429 |
| POST | `/ab-test` | — |
| GET | `/actions/{item_id}` | — |
| PUT | `/active-model` | — |
| POST | `/activities` | — |
| GET | `/activities` | 429 |
| POST | `/addons/grant` | — |
| POST | `/addons/revoke` | — |
| GET | `/address/{name}` | — |
| GET | `/admin` | 429 |
| GET | `/api-console` | 429 |
| GET | `/api/_r65b_debug/llm_timeout` | 401 |
| POST | `/api/account/onboarding-completed` | — |
| GET | `/api/account/profile` | 429 |
| PUT | `/api/account/profile` | — |
| GET | `/api/account/statements` | 429 |
| POST | `/api/account/subscription/cancel` | — |
| GET | `/api/admin/appointments` | 429 |
| GET | `/api/admin/audit-log` | 429 |
| GET | `/api/admin/organizations` | 429 |
| POST | `/api/admin/organizations` | — |
| GET | `/api/admin/organizations/{org_id}` | — |
| PATCH | `/api/admin/organizations/{org_id}` | — |
| DELETE | `/api/admin/organizations/{org_id}` | — |
| GET | `/api/admin/organizations/{org_id}/members` | — |
| POST | `/api/admin/organizations/{org_id}/members` | — |
| DELETE | `/api/admin/organizations/{org_id}/members/{user_id}` | — |
| GET | `/api/admin/orgs` | 429 |
| GET | `/api/admin/roster` | 403 |

## DEAD routes (registered but broken)

**Immediate cleanup target.** These routes exist in source but
the live probe returns 404/500. Either the handler is broken or
the route prefix is misconfigured.

| Method | Path | Status | File |
|---|---|---|---|
| GET | `/actions` | 404 | `src/registry_router.py` |
| GET | `/addons/pricing` | 404 | `src/billing/api.py` |
| GET | `/api/auth/verify-email` | 500 | `src/runtime/app.py` |
| GET | `/api/files/list` | 404 | `src/runtime/app.py` |
| GET | `/api/public/assist/list` | 404 | `src/runtime/app.py` |
| GET | `/api/public/treasury` | 404 | `src/runtime/app.py` |
| GET | `/api/tenant/isolation-check` | 404 | `src/runtime/app.py` |
| GET | `/api/v1/data` | 404 | `src/demo_deliverable_generator.py` |
| GET | `/approvals` | 404 | `src/dispatch_routes.py` |
| GET | `/auto-update/recommendations` | 404 | `src/system_update_api.py` |
| GET | `/bars` | 404 | `src/portfolio/api.py` |
| GET | `/boards` | 404 | `src/management_ai_router.py` |
| GET | `/bug-responses/recommendations` | 404 | `src/system_update_api.py` |
| GET | `/bugs` | 404 | `src/dev_module/api.py` |
| GET | `/business-lines/classify` | 404 | `src/billing/api.py` |
| GET | `/business-lines/clients` | 404 | `src/billing/api.py` |
| GET | `/business-lines/pnl` | 404 | `src/billing/api.py` |
| GET | `/cadence` | 404 | `src/registry_router.py` |
| GET | `/calibration/costs` | 404 | `src/paper_trading_routes.py` |
| GET | `/calibration/errors` | 404 | `src/paper_trading_routes.py` |
| GET | `/chaos/suite` | 404 | `src/shield_wall.py` |
| GET | `/checkpoint` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/commission/history` | 404 | `src/shield_wall.py` |
| GET | `/commission/status` | 404 | `src/shield_wall.py` |
| GET | `/conduct/status` | 404 | `src/shield_wall.py` |
| GET | `/contacts` | 404 | `src/illuminate_router.py` |
| GET | `/contacts` | 404 | `src/crm/api.py` |
| GET | `/contract` | 404 | `src/shield_wall.py` |
| GET | `/convergence/graph/stats` | 404 | `src/shield_wall.py` |
| GET | `/convergence/patterns` | 404 | `src/shield_wall.py` |
| GET | `/critical-path` | 404 | `src/portfolio/api.py` |
| GET | `/critical-path` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/currencies` | 404 | `src/billing/api.py` |
| GET | `/customers/stats` | 404 | `src/billing/api.py` |
| GET | `/dashboards/templates` | 404 | `src/management_ai_router.py` |
| GET | `/deadlines` | 404 | `src/billing/grants/api.py` |
| GET | `/deadlines/alerts` | 404 | `src/billing/grants/api.py` |
| GET | `/documents` | 404 | `src/engineering_router.py` |
| GET | `/domain-search` | 404 | `src/illuminate_router.py` |
| GET | `/eligibility` | 404 | `src/billing/grants/api.py` |
| GET | `/email-finder` | 404 | `src/illuminate_router.py` |
| GET | `/example` | 404 | `src/db.py` |
| GET | `/export/excel` | 404 | `src/workflow_ops_router.py` |
| GET | `/export/formats` | 404 | `src/document_export/api.py` |
| GET | `/exposure` | 404 | `src/dynamic_manifold_router.py` |
| GET | `/feed/global` | 404 | `src/collaboration/api.py` |
| GET | `/feed/status` | 404 | `src/hack_stream_graph.py` |
| GET | `/find` | 404 | `src/patch412_capability_cube.py` |
| GET | `/footprint` | 404 | `src/shield_wall.py` |
| GET | `/footprint/status` | 404 | `src/shield_wall.py` |
| GET | `/forms` | 404 | `src/guest_collab/api.py` |
| GET | `/forms` | 404 | `src/billing/grants/api.py` |
| GET | `/frontline` | 404 | `src/shield_wall.py` |
| GET | `/gate-evolution/log` | 404 | `src/telemetry_learning/api.py` |
| GET | `/gate-evolution/rollbacks` | 404 | `src/telemetry_learning/api.py` |
| GET | `/gates` | 404 | `src/registry_router.py` |
| GET | `/git` | 404 | `src/dev_module/api.py` |
| GET | `/graph` | 404 | `src/hack_stream_graph.py` |
| GET | `/graph/stats` | 404 | `src/convergence_router.py` |
| GET | `/graph/stream` | 404 | `src/hack_stream_graph.py` |
| GET | `/healthz` | 404 | `src/murphy_ops.py` |
| GET | `/healthz` | 404 | `src/murphy_edge.py` |
| GET | `/healthz` | 404 | `src/murphy_robotics.py` |
| GET | `/healthz/live` | 404 | `src/health_monitor.py` |
| GET | `/healthz/ready` | 404 | `src/health_monitor.py` |
| GET | `/history` | 404 | `src/lcm_router.py` |
| GET | `/history` | 404 | `src/founder_update_api.py` |
| GET | `/history` | 404 | `src/rsc_router.py` |
| GET | `/history` | 404 | `src/ghost_runner.py` |
| GET | `/investment/applications` | 404 | `src/billing/api.py` |
| GET | `/investment/data-room` | 404 | `src/billing/api.py` |
| GET | `/investment/investors` | 404 | `src/billing/api.py` |
| GET | `/investment/valuation` | 404 | `src/billing/api.py` |
| GET | `/ledger/debts` | 404 | `src/shield_wall.py` |
| GET | `/ledger/frontline` | 404 | `src/shield_wall.py` |
| GET | `/ledger/full` | 404 | `src/shield_wall.py` |
| GET | `/ledger/status` | 404 | `src/shield_wall.py` |
| GET | `/maintenance/recommendations` | 404 | `src/system_update_api.py` |
| GET | `/memory/stats` | 404 | `src/aionmind/api.py` |
| GET | `/milestones` | 404 | `src/portfolio/api.py` |
| GET | `/next` | 404 | `src/walker_routes.py` |
| GET | `/next` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/north-star` | 404 | `src/shield_wall.py` |
| GET | `/operations/recommendations` | 404 | `src/system_update_api.py` |
| GET | `/pages` | 404 | `src/registry_router.py` |
| GET | `/paper/performance` | 404 | `src/paper_trading_routes.py` |
| GET | `/paper/strategies` | 404 | `src/paper_trading_routes.py` |
| GET | `/paper/trades` | 404 | `src/paper_trading_routes.py` |
| GET | `/parallel-groups` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/patterns` | 404 | `src/convergence_router.py` |
| GET | `/payloads` | 404 | `src/ethical_hacking_engine.py` |
| GET | `/pilot/status` | 404 | `src/chaos/api.py` |
| GET | `/plans` | 404 | `src/billing/api.py` |
| GET | `/prerequisites` | 404 | `src/billing/grants/api.py` |
| GET | `/prerequisites` | 404 | `src/billing/grants/api.py` |
| GET | `/products` | 404 | `src/records_router.py` |
| GET | `/profiles` | 404 | `src/billing/grants/api.py` |
| GET | `/programs` | 404 | `src/billing/grants/api.py` |
| GET | `/programs` | 404 | `src/billing/grants/api.py` |
| GET | `/progress` | 404 | `src/walker_routes.py` |
| GET | `/proposals` | 404 | `src/self_manifest_router.py` |
| GET | `/proposals` | 404 | `src/aionmind/api.py` |
| GET | `/providers` | 404 | `src/ghost_runner.py` |
| GET | `/recipes` | 404 | `src/management_ai_router.py` |
| GET | `/releases` | 404 | `src/dev_module/api.py` |
| GET | `/report` | 404 | `src/founder_update_api.py` |
| GET | `/risk/assessment` | 404 | `src/risk_routes.py` |
| GET | `/roadmap` | 404 | `src/dev_module/api.py` |
| GET | `/routes` | 404 | `src/registry_router.py` |
| GET | `/safety/blocked-actions` | 404 | `src/telemetry_learning/api.py` |
| GET | `/safety/violations` | 404 | `src/telemetry_learning/api.py` |
| GET | `/scans` | 404 | `src/ethical_hacking_engine.py` |
| GET | `/sdk/recommendations` | 404 | `src/system_update_api.py` |
| GET | `/search` | 404 | `src/registry_router.py` |
| GET | `/sessions` | 404 | `src/billing/grants/api.py` |
| GET | `/shadow-mode/log` | 404 | `src/telemetry_learning/api.py` |
| GET | `/shadow-mode/status` | 404 | `src/telemetry_learning/api.py` |
| GET | `/sprints` | 404 | `src/dev_module/api.py` |
| GET | `/stats` | 404 | `src/patch412_capability_cube.py` |
| GET | `/stats` | 404 | `src/illuminate_router.py` |
| GET | `/stats` | 404 | `src/resume_router.py` |
| GET | `/stats` | 404 | `src/ambient_api_router.py` |
| GET | `/stats` | 404 | `src/ambient_full_router.py` |
| GET | `/stats` | 404 | `src/auar_api.py` |
| GET | `/stats` | 404 | `src/telemetry_learning/api.py` |
| GET | `/stats` | 404 | `src/billing/grants/api.py` |
| GET | `/status/columns` | 404 | `src/management_ai_router.py` |
| GET | `/summary` | 404 | `src/registry_router.py` |
| GET | `/summary` | 404 | `src/founder_maintenance_api.py` |
| GET | `/summary` | 404 | `src/roi_ledger_router.py` |
| GET | `/summary` | 404 | `src/dynamic_manifold_router.py` |
| GET | `/targets` | 404 | `src/roi_ledger_router.py` |
| GET | `/tasks` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/team/roe` | 404 | `src/shield_wall.py` |
| GET | `/tenant/intake-questions` | 404 | `src/billing/api.py` |
| GET | `/tenant/knowledge-context` | 404 | `src/billing/api.py` |
| GET | `/tenant/profile` | 404 | `src/billing/api.py` |
| GET | `/tenant/scope` | 404 | `src/billing/api.py` |
| GET | `/tenant/strategy` | 404 | `src/billing/api.py` |
| GET | `/timeline` | 404 | `src/management_ai_router.py` |
| GET | `/timeline` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/treasury/status` | 404 | `src/billing/api.py` |
| GET | `/value-report` | 404 | `src/platform_onboarding/onboarding_api.py` |
| GET | `/verify` | 404 | `src/illuminate_router.py` |
| GET | `/workspaces` | 404 | `src/management_ai_router.py` |

## Non-HTTP surfaces

### Skills (.agents/skills/)

_(none registered)_

### Module count

- Total `src/*.py` modules indexed by PCR-014: **1,749**
- Files containing route decorators: **103**
- Remaining modules are libraries / helpers / internal classes

## Methodology

1. Walk `src/` for any `@app.<method>("/path")` or `@router.<method>("/path")` decorator.
2. Walk `static/*.html` for any `fetch("/api/...")` call.
3. For each route, check if any UI fetch target matches (including parametric `/foo/{id}`).
4. For non-parametric GET routes, probe live with real UA + retry-once.
5. Classify per the 5-class taxonomy above.

## What this catalog enables

- **Phase 3 (Gap Map):** the GHOST list IS the gap. Each one gets a closure decision.
- **Phase 4 (Drill-Down):** UI-LINKED routes are the drill-down targets.
- **Phase 6 (Bottleneck monitor):** the route list IS the watch list.

