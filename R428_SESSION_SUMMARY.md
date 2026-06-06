# R428 — Agent Employment Bridge — Session Lock 2026-06-01

## What shipped tonight

1. **`src/agent_employment_bridge.py`** (240 lines) — chains existing engines:
   - `DynamicRosettaPlanner.plan(task)` → DispatchPacket
   - `SoulForge.forge_soul()` → ForgedSoul (LLM-written L2 when LLM provided)
   - `POST edge:8011/api/identity/spawn-agent` → real profile_id + api_key
   - `agent_souls` table → persist soul keyed to profile_id
   - Returns `{team_id, agents:[...]}` with `soul_envelope` ready to inject

2. **`patch410_unified_identity.py`** generalized — accepts any role class
   (was hardcoded to SDR/AE/Enterprise_AE). Wallet seeds default to $5
   for novel roles, $3 for INTERVIEWER, etc.

3. **`soul_forge.py` bugfix** — `inject_soul_into_prompt` was reading
   `soul.l0` but ForgedSoul stores it at `soul.soul.l0`. Fixed.

4. **New table** `agent_souls` in `/var/lib/murphy-production/murphy_identity.db`
   — 16 rows persisted across smoke runs tonight.

## What proved out

- Mechanical bridge works in 4.1s end-to-end (no-LLM mode)
- edge:8011 spawns persist correctly
- DB ↔ edge linkage solid
- Backups in place: `.pre-r428`, `.pre-r428-bugfix`, `.pre-llm-wrap`

## What's NOT in yet (open for next session)

- **LLM-driven `analyze_task`** in DynamicRosettaPlanner.
  Current keyword analyzer maps "PR interview the founder" to
  `domain=exec_admin, complexity=trivial, team=Coordinator+HITL Gate`.
  Wrong shape. LLM analyzer would produce
  `Interviewer + Brand Strategist + Founder Listener` instead.

- **Bounded LLM that actually kills the upstream socket.**
  `concurrent.futures` timeout cancels the future but socket hangs.
  Need either signal-based timeout or urllib socket-level timeout.

- **`/api/agents/employ` HTTP route** — currently only callable from Python.

- **rosetta_ml_study live integration** — still batch-mode against
  canned prompts. Wire it to score live agent runs.

## Substrate state at session end

- murphy-production: active, 200
- murphy-edge: active, 200
- Outreach schedulers: paused (lead-prospector, followup-cadence)
- 6 HITL real-domain items: still pending founder approve/reject
- NOWPayments KYB reply check: auto-scheduled 2026-06-04 09:00 PT
