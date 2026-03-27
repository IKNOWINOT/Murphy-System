# Librarian Routing Specification

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1
-->

This document describes the Murphy Librarian's command routing system — how
commands are registered, catalogued, and dispatched across the subsystem layer.

---

## Overview

The Murphy Librarian exposes a `/api/librarian/commands` endpoint that returns
the full command catalog.  Every command declared in `module_manifest.py` must
appear in that catalog so that the Librarian can route it correctly.

Three systems must be kept in sync:

| System | File | Purpose |
|--------|------|---------|
| Module Manifest | `src/matrix_bridge/module_manifest.py` | Source of truth — `ModuleEntry` objects with commands |
| Librarian Catalog | `src/runtime/app.py` (`/api/librarian/commands`) | Catalogue served to clients |
| Subsystem Registry | `src/matrix_bridge/_registry_data_b.py` | Runtime command tokens per subsystem |

---

## Command Registration Invariants

The following invariants **must** hold at all times.  They are enforced by
`tests/test_librarian_command_coverage.py`.

### 1 — Every ModuleEntry must have at least one command

```python
# ✅ correct
ModuleEntry(
    module="my_module",
    room="murphy-my-room",
    commands=["my command"],
    ...
)

# ❌ wrong — empty commands list
ModuleEntry(
    module="my_module",
    room="murphy-my-room",
    commands=[],
    ...
)
```

### 2 — Every manifest command must appear in the librarian catalog

The catalog lives in `src/runtime/app.py` inside the
`/api/librarian/commands` route handler.  Every string in any
`ModuleEntry.commands` list must have a corresponding catalog entry.

### 3 — Catalog entry format

Each entry is a plain Python dict with exactly these keys:

```python
{
    "command":     "<command string>",   # e.g. "swarm propose"
    "category":    "<category>",         # e.g. "swarm"
    "description": "<short description>",
    "api":         "/api/<module/path>",
    "ui":          "/ui/<terminal-page>#<category>",
}
```

### 4 — How to add new commands

1. Add the command string to the `commands=[...]` list of the relevant
   `ModuleEntry` in `src/matrix_bridge/module_manifest.py`.

2. Add a matching entry to the catalog in `src/runtime/app.py`, choosing
   the appropriate `category` from the table below.

3. If the command's top-level token (first word) does not already have a
   dispatcher handler, add a stub handler in
   `src/matrix_bridge/command_dispatcher.py` following this pattern:

   ```python
   def _handle_mytoken(
       dispatcher: CommandDispatcher, cmd: ParsedCommand
   ) -> CommandResponse:
       """Route MYTOKEN subsystem commands."""
       sub = cmd.subcommand or ""
       args_str = " ".join(cmd.args)
       return CommandResponse(
           success=True,
           message=f"[MYTOKEN] {sub} {args_str} — route to subsystem handler".strip(),
           format="text",
       )
   ```

   Then register it inside `_register_builtins()`:

   ```python
   self.register_handler("mytoken", _handle_mytoken, "My subsystem commands")
   ```

4. Run `pytest tests/test_librarian_command_coverage.py` to verify.

---

## Category Reference

| Category | Modules / Room Prefixes |
|----------|------------------------|
| `security` | confidence, security, rbac, oauth, credentials, fastapi_security |
| `execution` | exec, execution, orchestrat |
| `automation` | automation, full_automation, self_automation, nocode, rpa, playwright |
| `llm` | llm, local_llm, local_model, deepinfra, openai, enhanced_local, safe_llm |
| `compliance` | compliance, outreach_compliance, contact_compliance |
| `governance` | governance, authority, bypass, base_governance |
| `hitl` | hitl, freelancer_validator, resolution_scoring, trading_hitl |
| `safety` | safety, emergency_stop |
| `self-healing` | self_fix, chaos_resil, blackstart, self_improv, self_optim, autonomous_repair, code_repair, predictive_fail |
| `learning` | learn, shadow_train, telemetry_learn |
| `swarm` | swarm, true_swarm, advanced_swarm, durable_swarm, domain_swarms, visual_swarm, llm_swarm |
| `agents` | agent, murphy_crew, shadow_agent |
| `workflows` | workflow, ai_workflow |
| `integrations` | integration, enterprise_integrat, platform_connector, integration_bus, api_collection, bridge_layer |
| `forms` | form |
| `librarian` | librarian, org_compiler, module_compiler, bot_inventory, capability_map, concept_graph, knowledge_graph |
| `knowledge` | knowledge, research, rag, advanced_research, generative_knowledge |
| `control` | control_plane, compute_plane, deterministic, control_theory |
| `mfgc` | gate, mfgc, cost_explosion, inference_gate, niche_viability, domain_gate |
| `onboarding` | onboard, setup_wizard, environment_setup, hardware_visual |
| `monitoring` | monitor, log_analysis, observability, prometheus, murphy_trace, slo_tracker, alert, heartbeat, telemetry |
| `audit` | audit, blockchain_audit |
| `finance` | finance, crypto, trading, invoice, budget, coinbase, financial_report |
| `marketing` | marketing, campaign, seo, content_pipeline, social, outreach, self_marketing |
| `crm` | crm, customer |
| `orgchart` | org, organization_chart, ceo_branch |
| `business` | biz, business, competitive, kfactor, niche_business, innovation |
| `data` | data, ml, persistence, data_archive, data_pipeline |
| `infrastructure` | kubernetes, docker, cloudflare, hetzner, backup, capacity, fleet, ci_cd |
| `iot` | building_automation, sensor, digital_twin, computer_vision, additive, energy_management, robotics, manufacturing |
| `content` | image, video, murphy_drawing |
| `communications` | comms, email, notification, communication, delivery, announcer |
| `development` | code_gen, auto_doc, architecture_evol, dev_module, murphy_engineering, domain_expert |
| `management` | board, timeline, workspace, recipe, dashboard, collaboration |
| `terminal` | protocols, legacy, thread_safe, shim, cli_art, murphy_template, murphy_repl, golden_path |
| `platform` | avatar, account, rosetta, aionmind, osmosis, knostalgia |
| `intelligence` | neuro, sim, wingman, murphy_wingman, domain_engine, dynamic_assist |

---

## Audit History

| Date | Action | Result |
|------|--------|--------|
| 2026-03-16 | Full command registration audit | 283 ModuleEntry objects audited; 405 commands added to catalog (total 584); 61 registry entries updated; 21 dispatcher stubs added |
