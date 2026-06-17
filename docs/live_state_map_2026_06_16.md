# Murphy Live-State Map — 2026-06-16

This document is **grep-able** when things break. It maps every running
worker, scheduled timer, and database to what it does, when it fires,
what it reads, and what it writes. Update it when the architecture
changes; trust it when you're debugging at 3am.

## How to read this doc
- Each row tells you: **NAME — WHAT — WHEN — READS — WRITES — IF BROKEN**
- Search for the symptom you see. Find the row. Look at WHAT and READS/WRITES.
- "IF BROKEN" gives the most-likely cause + 1-line fix.

## Long-running services (systemd, type=simple)

### murphy-production.service
- WHAT: main FastAPI app, 1,727 routes, port 8080
- READS: most DBs in /var/lib/murphy-production/
- WRITES: most DBs (gated by RLS + posture)
- IF BROKEN: check journalctl -u murphy-production. As of Ship 31cs.P2,
  cosmetic Starlette TaskGroup spam is silenced. Real errors will surface.

### murphy-conductor.service
- WHAT: meta-orchestrator that decides what runs when
- READS: conductor_state.db, posture, autonomy_policy
- WRITES: conductor_decisions.db
- IF BROKEN: timers will still fire but coordination will drift

### murphy-edge.service
- WHAT: tenant-edge router (R382) for multi-tenant requests
- READS: tenant_isolation.db, accounts.db
- WRITES: tenant_request_log.db
- IF BROKEN: multi-tenant requests 502; founder routes still work

### murphy-ops.service
- WHAT: ops/admin endpoints, internal-only
- READS: most internal DBs
- WRITES: ops_action_log.db
- IF BROKEN: founder ops UI stops, runtime unaffected

### murphy-r382-tenant-chat.service
- WHAT: per-tenant chat surface
- READS: tenant + chat DBs
- WRITES: tenant_chat_history.db
- IF BROKEN: tenant /chat 502; main chat unaffected

### murphy-r384-hitl.service
- WHAT: human-in-the-loop queue on :8083
- READS: hitl_v2.db, hitl_provenance.db
- WRITES: hitl_v2.db (verdicts)
- IF BROKEN: pending approvals stall; nothing auto-applies

### murphy-r387-chat-v2.service
- WHAT: LLM router (DeepInfra → Together → Anthropic → OpenAI)
- READS: vault secrets, model registry
- WRITES: llm_call_log.db, cost_ledger.db
- IF BROKEN: drafts fall back to single-provider or fail; check 402s

### murphy-r389-sms.service
- WHAT: outbound SMS via Twilio
- READS: sms_queue.db, vault secrets
- WRITES: sms_send_log.db
- IF BROKEN: SMS queue piles up; check Twilio account status

### murphy-r391-mesh.service
- WHAT: mesh-state coordinator across instances (multi-node ready)
- READS: mesh_state.db
- WRITES: mesh_state.db
- IF BROKEN: single-node operation continues; multi-node coordination drifts

### murphy-r394-pulse.service
- WHAT: cadence pulse (rhythm signals for other workers)
- READS: cadence_pulse.db
- WRITES: cadence_pulse.db
- IF BROKEN: workers may lose rhythm; restart this first

### murphy-r395-cascade.service
- WHAT: cascade trigger chain (one event → many follow-ups)
- READS: cascade_rules.db
- WRITES: cascade_runs.db
- IF BROKEN: chained side-effects don't fire; single events still work

### murphy-r604-agents.service
- WHAT: multi-agent runtime (16 named souls)
- READS: agent_souls.db, agent_contracts.db
- WRITES: agent_runs.db, agent_outputs.db
- IF BROKEN: multi-agent dispatch falls back to single-LLM

### murphy-r615-spawn.service
- WHAT: emergent spawn + org graph generator
- READS: agent_substrate.db, spawn_policy.db
- WRITES: r615_spawns.db, org_graph_*.db
- IF BROKEN: dynamic spawns disabled; static agents still run

### murphy-robotics.service
- WHAT: household + picar + voice (low-latency)
- READS: voice_config, robotics_state.db
- WRITES: robotics_action_log.db
- IF BROKEN: voice/robotics surface stops; everything else fine

### murphy-console-api.service
- WHAT: console/admin API on internal port
- READS: console_state.db
- WRITES: console_action_log.db
- IF BROKEN: console UI fails; agent unaffected

## Scheduled timers (most-common)

### murphy-inbox-poller.timer (every 1 min)
- WHAT: pulls maildir → inbound_replies.db
- WRITES: inbound_replies.db
- IF BROKEN: new mail invisible to system; check dovecot too

### murphy-reply-correlator.timer (every 1 min)
- WHAT: matches inbound replies to outbound deals
- READS: inbound_replies.db, outbound.db
- WRITES: crm.db correlation field
- IF BROKEN: replies don't update CRM; sales pipeline drifts

### murphy-r388-email-in.timer (every 5 min)
- WHAT: deeper email-in processing + intent classification
- READS: inbound_replies.db
- WRITES: inbound_intent.db
- IF BROKEN: intent gating fails open; downstream may over-respond

### murphy-inbound-autoresponse.timer (CURRENTLY DISABLED)
- WHAT: generates + sends stranger replies
- DISABLED since: 2026-06-15 mcconnaire loop incident
- IF RE-ENABLING: verify Ship 31cu pre-drill shape is wired + critic loop active

### murphy-shape-verifier.timer (every 30 min)
- WHAT: runs 49 checks against deployed system
- WRITES: shape_verifier_log.db
- IF BROKEN: we lose green/red signal; system can drift unnoticed

### murphy-r477-vision-loop.timer (every 22 min)
- WHAT: Murphy scans 10 pages, proposes self-improvements
- READS: live pages, vision_loop.db
- WRITES: vision_loop.db proposals table
- IF BROKEN: self-improvement loop stops; manual patching still works
- POST Ship 31ct: dedup gate in _save_proposal; tiered critic for static assets

### murphy-vision-stale-sweep.timer (daily)
- WHAT: archive >7d pending vision proposals (Ship 31ct.b)
- WRITES: vision_loop.db status field
- IF BROKEN: queue may grow stale; not urgent

### murphy-r609-drafter.timer (every 30 min)
- WHAT: drafts patch proposals from r609 gaps
- READS: r609_gaps.db
- WRITES: self_plan.db proposals
- IF BROKEN: auto-draft stops; manual planning still works

### murphy-watchdog.timer (every 2 min)
- WHAT: liveness check on critical services
- WRITES: watchdog_log.db
- IF BROKEN: service deaths go undetected; restart manually

### murphy-hang-watchdog.timer (every 3 min)
- WHAT: detects hung HTTP requests
- WRITES: hang_log.db
- IF BROKEN: hung requests pile up; restart murphy-production

### murphy-backlog-drain.timer (every hour)
- WHAT: drains classifier backlog (Ship 31bc)
- READS: classifier_backlog.db
- WRITES: classifier_results.db
- IF BROKEN: classification falls behind; sends may queue

### murphy-r603-cto.timer (daily 15:00 UTC)
- WHAT: fires the 5-agent CTO dispatch
- WRITES: rosetta_cto_runs.db
- IF BROKEN: daily strategy review missed; not urgent

## Loom-Lite live state (NEW per Shape of Complete v3, not yet built)

### loom_lite.ghost_layer
- WHAT: per-turn working-set snapshots
- WHEN: turn boundaries (4 frames per email)
- STORAGE: ghost_snapshots.db (7-day retention)
- IF BROKEN: turn audit loses fidelity but pipeline continues

### loom_lite.psi_history
- WHAT: operation log w/ cost+latency+outcome typing
- WHEN: every meaningful op (drill iter, team pick, critic verdict, send)
- STORAGE: psi_log.db (30-day retention)
- IF BROKEN: cost tracking drifts; pipeline continues

### loom_lite.recursion_gate
- WHAT: spawn-depth tracker
- WHEN: every sub-agent enter/exit
- STORAGE: in-process + r615_spawns.db
- IF BROKEN: depth limits not enforced; risk of runaway loops

### loom_lite.precipitator
- WHAT: turn-end crystallization
- WHEN: end of each turn
- STORAGE: dlf_packages/ + dlf_packages.db
- IF BROKEN: no durable memory of the turn; runtime continues

## DLF-Lite v2 portable memory (NEW per Shape of Complete v3, not yet built)

### dlf_lite_v2.codec
- WHAT: read/write .dlf-lite containers
- USAGE: precipitator + adapter
- STORAGE: dlf_packages/ as files

### dlf_lite_v2.adapter
- WHAT: agent event → nodes/weaves mapping
- READS: agent runs
- WRITES: dlf_packages.db

### dlf_lite_v2.audit
- WHAT: 3-state provenance classification
- READS: a node + its weaves
- RETURNS: DLF_AVAILABLE / DLF_SELECTED_OR_INJECTED / DLF_SUBSTRATE_PROVENANCE_CONFIRMED

### dlf_lite_v2.hygiene
- WHAT: REJECT_FUTURE_SELECTION enforcement
- READS: node hygiene_status field
- BLOCKS: substrate selection from bad outputs

## Top 25 most-referenced DBs (out of 188)

| DB | Purpose | Hot path |
|---|---|---|
| inbound_replies.db | every inbound email | hot, every minute |
| vision_loop.db | self-improvement proposals | hot, every 22min |
| accounts.db | tenant + user identities | hot, every request |
| auth_main.db | login/sessions | hot, every request |
| billing.db | tier + subscription | warm, every request |
| stranger_quota.db | per-correspondent quotas | hot per outbound |
| email_outbound.db | sent log (metadata only) | hot per outbound |
| murphy_mail.db | outbound queue | hot per outbound |
| hitl_v2.db | human-in-loop queue | warm, when humans act |
| hitl_provenance.db | HITL audit trail | warm |
| audit_log.db | system audit | warm |
| event_log.db | state transitions | warm |
| agent_substrate.db | departments + capabilities + org graph | warm |
| brain_bundles.db | desktop agents (8 active) | cold |
| api_registry.db | external API catalog | cold |
| antibody_interventions.db | LLM hallucination catches (3 lifetime) | cold |
| cnc.db | CNC agents (1 active) | cold |
| entity_graph.db | agent contracts (42) | cold |
| marketplace.db | marketplace agents (6) | cold |
| rosetta_learning.db | agent success map (22) | cold |
| memory.db | agent memory (17) | cold |
| capital_engine.db | spend proposals (1228) | cold |
| capacity_dedupe.db | capacity warning rate-limiter | cold |
| autonomy_policy.db | OFF/ASSIST/AUTONOMOUS posture | warm, posture check |
| ghost_snapshots.db (NEW) | per-turn snapshots | will be hot |
| psi_log.db (NEW) | operation log | will be warm |
| dlf_packages.db (NEW) | DLF-Lite v2 package index | will be warm |

## Health endpoints (21)

All at `/api/health/*`. Each returns `{ok: bool, ...}` for shape verifier.

api_patcher, approval_ladder, autonomy, canspam, capacity, citl, compliance,
conductor_identity, credentials, email_boundary, founder_gate, hitl,
hitl_loop, inflight, launch, mail_os, quiet_house, referral, retention_sweep,
status, tenant_isolation

## What to grep when things break

- Mail stops arriving: `journalctl -u murphy-inbox-poller --since "1 hour ago"`
- Replies pile up: `sqlite3 inbound_replies.db "SELECT COUNT(*) FROM inbound_replies WHERE auto_response_status='pending'"`
- Vision loop spamming: check Ship 31ct dedup gate is firing in _save_proposal
- Wrong reply length: check Ship 31cu shape was injected (look for "Ship 31cu pre-drill shape" in journalctl -u murphy-inbound-autoresponse)
- Cosmetic error spam: should be silenced by Ship 31cs.P2; if not, check src/runtime/app.py line ~23638
- LLM cost spiking: check llm_call_log.db
- Posture confusion: check autonomy_policy.db; default is OFF

## Locked commits (reference)
- HEAD post-31cs.P2: `ae79845f` — TaskGroup spam silencer
- HEAD post-31ct + 31cu: `3897f88d` — vision-loop dedup + pre-drill DLFR
- HEAD post-reply-protocol: `2381fec9` — reply protocol locked
