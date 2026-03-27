# Tiered Runtime — Murphy System

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

---

## Why the Tiered Runtime Exists

Murphy System originally loaded every module at startup regardless of which
capabilities a team actually needed.  A company that uses Murphy purely for
HVAC control still paid the startup cost and memory footprint of the CRM,
Matrix bridge, ML pipeline, content generator, and payment processor.

The tiered runtime solves this with a simple principle:

> **If the onboarding flow didn't ask for HVAC, HVAC doesn't load.**

At the same time the monolith (`src/runtime/murphy_system_core.py`) must
remain the safe fallback so that a bug in the tiered system never leaves a
customer dark.

---

## Architecture: Four Tiers

```
┌────────────────────────────────────────────────────────────────────┐
│  Tier 0 — KERNEL  (always loaded — system dies without these)      │
│  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────────────┐│
│  │ kernel_security  │ │ kernel_events│ │ kernel_governance        ││
│  │ kernel_health    │ └──────────────┘ └──────────────────────────┘│
│  └──────────────────┘                                               │
├────────────────────────────────────────────────────────────────────┤
│  Tier 1 — PLATFORM  (loaded at startup, needed for basic ops)      │
│  ┌──────────────┐ ┌────────────┐ ┌─────────────────────────────┐  │
│  │ platform_api │ │platform_llm│ │ platform_persistence        │  │
│  │              │ └────────────┘ │ platform_confidence         │  │
│  └──────────────┘                └─────────────────────────────┘  │
├────────────────────────────────────────────────────────────────────┤
│  Tier 2 — DOMAIN  (loaded on-demand based on team profile)         │
│  ┌───────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │domain_crm │ │domain_matrix│ │domain_hvac  │ │domain_ml     │  │
│  └───────────┘ └─────────────┘ └─────────────┘ └──────────────┘  │
│  ┌──────────────────┐ ┌────────────────┐ ┌──────────────────────┐ │
│  │domain_payments   │ │domain_content  │ │domain_observability  │ │
│  └──────────────────┘ └────────────────┘ └──────────────────────┘ │
│  ┌─────────────────┐                                               │
│  │domain_onboarding│                                               │
│  └─────────────────┘                                               │
├────────────────────────────────────────────────────────────────────┤
│  Tier 3 — EPHEMERAL  (spun up per-task, torn down when done)       │
│  Never pre-loaded.  Lifecycle managed entirely by the calling task.│
└────────────────────────────────────────────────────────────────────┘
```

---

## Switching Between Modes

Set the `MURPHY_RUNTIME_MODE` environment variable in your `.env` file:

```dotenv
# Default — identical to current behaviour, nothing changes
MURPHY_RUNTIME_MODE=monolith

# Opt-in to tiered loading (after validation)
MURPHY_RUNTIME_MODE=tiered
```

**`monolith` is the default.**  You must explicitly opt in to `tiered`.
Existing deployments are unaffected until you change this variable.

### Fallback behaviour

When a KERNEL or PLATFORM pack fails to load in tiered mode, the system
falls back according to `MURPHY_PACK_FALLBACK`:

| Value | Behaviour |
|-------|-----------|
| `monolith` | Boot the original `MurphySystem` as a safety net **(default)** |
| `degraded` | Log the error and continue without the failed pack |
| `strict` | Abort startup immediately |

```dotenv
MURPHY_PACK_FALLBACK=monolith
```

---

## How Packs Are Defined

A pack is a `RuntimePack` dataclass defined in
`src/runtime/runtime_packs/registry.py`:

```python
RuntimePack(
    name="domain_crm",
    tier=RuntimeTier.DOMAIN,
    modules=[
        "src.crm_automation",
        "src.outreach_campaign_planner",
    ],
    dependencies=["platform_persistence", "platform_llm"],
    capabilities=["crm_automation"],
    api_routers=[],
    idle_timeout_minutes=30,
    max_memory_mb=256,
)
```

| Field | Purpose |
|-------|---------|
| `name` | Unique pack identifier |
| `tier` | KERNEL / PLATFORM / DOMAIN / EPHEMERAL |
| `modules` | Python import paths loaded via `importlib.import_module()` |
| `dependencies` | Other pack names that must be active first |
| `capabilities` | Tags that onboarding uses to select this pack |
| `api_routers` | FastAPI router dotted paths to mount when active |
| `idle_timeout_minutes` | Auto-unload after this many idle minutes (0 = never) |

---

## How Onboarding Maps to Packs

When a team completes onboarding, `onboarding_flow._infer_capabilities()`
returns a list of capability tags.  The tiered orchestrator reads
`CAPABILITY_TO_PACK` (from `registry.py`) to find which domain pack covers
each tag, then loads only those packs.

```python
CAPABILITY_TO_PACK = {
    "crm_automation":           "domain_crm",
    "communication_automation": "domain_matrix",
    "reporting_automation":     "domain_observability",
    "notification_automation":  "domain_matrix",
    "code_management":          "domain_onboarding",
    "project_tracking":         "domain_onboarding",
    "data_processing":          "domain_ml",
    "scheduling_automation":    "domain_onboarding",
    # … see registry.py for full list
}
```

Example — an HVAC company's boot:

```
Onboarding capabilities: ["hvac_control", "scheduling_automation"]
→ Loads: kernel_*, platform_*, domain_hvac, domain_onboarding
→ Does NOT load: domain_crm, domain_matrix, domain_ml, domain_payments, …
```

---

## The Monolith Fallback Mechanism

The monolith files are the **last line of defence**.  Rules:

1. `src/runtime/murphy_system_core.py` and `src/runtime/app.py` are
   **never imported** unless the fallback path is explicitly triggered.
2. When triggered, the orchestrator logs a prominent `CRITICAL` banner:

   ```
   ═══════════════════════════════════════════════════════
     TIERED ORCHESTRATOR ENTERING MONOLITH FALLBACK MODE
     All KERNEL/PLATFORM failures triggered this path.
     System is running on the legacy MurphySystem runtime.
   ═══════════════════════════════════════════════════════
   ```

3. `MurphySystem.startup()` is called exactly as before.
4. The `in_fallback` flag in `get_status()` is set to `True`.

### ⚠️ DO NOT delete the monolith runtime files

`murphy_system_core.py` and `app.py` **must not be deleted** until the
tiered system has been fully validated in production at scale.  They are
the fallback and represent years of battle-tested runtime logic.  Treat
them as read-only artefacts.

---

## Boot Sequence (Tiered Mode)

```
TieredOrchestrator.boot(team_profile)
  │
  ├─ 1. Load KERNEL packs (in registration order)
  │      kernel_security → kernel_events → kernel_governance → kernel_health
  │      Any failure → fallback_to_monolith() [if mode == "monolith"]
  │
  ├─ 2. Load PLATFORM packs
  │      platform_api → platform_llm → platform_persistence → platform_confidence
  │      Any failure → fallback_to_monolith() [if mode == "monolith"]
  │
  ├─ 3. Load DOMAIN packs matching team_profile["capabilities"]
  │      e.g. crm_automation → load domain_crm
  │      Failure here does NOT abort boot (graceful degradation)
  │
  └─ 4. EPHEMERAL packs — never pre-loaded
```

---

## Adding a New Domain Pack

1. **Define the pack** in `src/runtime/runtime_packs/registry.py`:

   ```python
   RuntimePack(
       name="domain_robotics",
       tier=RuntimeTier.DOMAIN,
       modules=["src.robotics_controller", "src.motion_planner"],
       dependencies=["kernel_events", "platform_persistence"],
       capabilities=["robotics_control"],
       api_routers=[],
       idle_timeout_minutes=60,
       max_memory_mb=512,
   )
   ```

2. **Add the capability mapping** to `CAPABILITY_TO_PACK`:

   ```python
   "robotics_control": "domain_robotics",
   ```

3. **Add the pack to `_DOMAIN_PACKS`** in `registry.py` so
   `get_default_packs()` returns it.

4. **Register the pack** when building your orchestrator:

   ```python
   orchestrator = TieredOrchestrator()
   for pack in get_default_packs():
       orchestrator.register_pack(pack)
   ```

5. **Write tests** in
   `src/runtime/runtime_packs/tests/test_tiered_orchestrator.py`.

6. **Update `murphy_system/docs/MODULE_REGISTRY.md`** (Runtime Packs
   section) so developers can find it.

---

## Idle Sweep (Automatic Memory Recovery)

Domain packs with no activity for `idle_timeout_minutes` minutes are
automatically unloaded by `idle_sweep()`.  Wire this to your scheduler:

```python
# Example: run every 5 minutes via APScheduler
scheduler.add_job(orchestrator.idle_sweep, "interval", minutes=5)
```

Set `idle_timeout_minutes=0` on a pack to disable auto-unload for it.

Override the default per-team via `MURPHY_PACK_IDLE_TIMEOUT` in `.env`.

---

## Troubleshooting

### "I switched to tiered and X stopped working"

1. Check `GET /api/health` — look at `packs[<name>].status`.  If a pack is
   `"failed"`, the error message is in `packs[<name>].error`.
2. Check that the team's onboarding profile contains the capability tag
   that maps to the missing pack.  Add it to `CAPABILITY_TO_PACK` if absent.
3. Set `MURPHY_PACK_FALLBACK=monolith` temporarily.  The system falls back
   to full loading while you debug.
4. Set `MURPHY_RUNTIME_MODE=monolith` to revert to the original behaviour
   entirely — zero risk to existing functionality.

### "The fallback monolith itself failed"

This means both the tiered system AND `MurphySystem` could not start.
Check `CRITICAL`-level log lines for the root cause.  This is usually a
missing environment variable (`DATABASE_URL`, `MURPHY_CREDENTIAL_MASTER_KEY`)
or an uninstalled dependency.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_RUNTIME_MODE` | `monolith` | `monolith` or `tiered` |
| `MURPHY_PACK_IDLE_TIMEOUT` | `30` | Minutes before idle domain packs are unloaded |
| `MURPHY_PACK_FALLBACK` | `monolith` | `monolith` \| `degraded` \| `strict` |

---

## Key Files

| File | Purpose |
|------|---------|
| `src/runtime/tiered_orchestrator.py` | `TieredOrchestrator` — the brain |
| `src/runtime/runtime_packs/registry.py` | All pack definitions + `CAPABILITY_TO_PACK` |
| `src/runtime/runtime_packs/__init__.py` | Public exports |
| `src/runtime/runtime_packs/tests/test_tiered_orchestrator.py` | Unit tests |
| `src/runtime/murphy_system_core.py` | **Monolith fallback — DO NOT EDIT** |
| `src/runtime/app.py` | **Monolith fallback — DO NOT EDIT** |

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1*
