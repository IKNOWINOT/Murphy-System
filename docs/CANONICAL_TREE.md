# Canonical Source Tree — Murphy System

> **TL;DR** — `src/` at the repo root is the **one and only canonical source of truth**
> for all Python modules.  The `Murphy System/src/` directory is a **legacy mirror** that
> is deprecated and will be removed once CI has fully migrated.

---

## Background

The repository historically contained two Python source trees:

| Tree | Status | Python files |
|------|--------|-------------|
| `src/` (repo root) | ✅ **Canonical** | 1 275+ |
| `Murphy System/src/` | ⚠️ **Legacy mirror — deprecated** | 1 168 |

The legacy mirror accumulated during an earlier CI setup that used
`working-directory: "Murphy System"` and a fragile
`PYTHONPATH: "${{ github.workspace }}/Murphy System:${{ github.workspace }}/Murphy System/src"`
(path contains a space, which breaks on many shells and tools).

**PR #441-redo** (`stabilize-ci-imports-module-registry`) recalibrated this:

1. All CI jobs now run from **repo root** with no PYTHONPATH env export.
2. `pyproject.toml` `[tool.pytest.ini_options] pythonpath = [".", "src", "strategic"]`
   is the single authoritative path configuration for tests.
3. Twenty-two modules that existed **only** in the legacy mirror (but had no Groq
   references) were **promoted to root `src/`** so nothing is lost.
4. The legacy mirror is left in place (no bulk delete) with guardrails below.

---

## Provider Canonical Reference (PR #440)

PR #440 migrated the LLM provider from Groq → DeepInfra + Together AI.
**Canonical root `src/` carries those changes.**  The legacy mirror still
contains `groq_key_rotator.py` and several matrix-bridge files with Groq
references — these are **not** promoted to root.

Environment variables to use:

```
DEEPINFRA_API_KEY=<your key>   # Primary LLM provider
TOGETHER_API_KEY=<your key>    # Overflow / alternative provider
```

Do **not** use `GROQ_API_KEY` — Groq support was removed in PR #440.

---

## How to import modules

```python
# Always use the src package prefix — works in tests and runtime alike.
from src.runtime.app import create_app
from src.rosetta_subsystem_wiring import RosettaSubsystemWiring
from src.true_swarm_system import TrueSwarmSystem
```

pytest automatically adds the paths in `pyproject.toml` `pythonpath`; no
`sys.path` manipulation is needed in test files.

---

## Module Registry

`module_registry.yaml` at the repo root is a **machine-generated** index of
all modules in canonical `src/`.  Always regenerate it after adding or
removing modules:

```bash
python scripts/generate_module_registry.py
```

CI will warn (non-blocking today, blocking after migration completes) if the
registry is out of date.  The generator is idempotent and its output is
deterministic and sorted, so diffs are minimal.

---

## Divergence Guard (CI job: `tree-divergence-check`)

A CI job scans for `.py` files that exist in `Murphy System/src/` but **not**
in root `src/`.  Today this job is **non-blocking** (warns only) to allow
incremental migration.  Once the mirror is fully reconciled, flip the script's
`sys.exit(0)` to `sys.exit(1)` to make it a hard gate.

Any file added to `Murphy System/src/` that does not exist in root `src/`
will appear in this check.  The correct action is to **promote it to root**
`src/` (and remove the Groq references if any), not to add it only to the
mirror.

---

## Deprecation Timeline for `Murphy System/` (Legacy Mirror)

| Milestone | Action |
|-----------|--------|
| ✅ **Done** | CI migrated to repo root; 22 unique mirror modules promoted to root `src/` |
| 🔲 Next | Replace divergence guard with hard-fail (exit 1) once all mirror-only files are promoted or documented |
| 🔲 Future | Remove `Murphy System/` directory entirely once CI is stable for 30+ days |

---

## Files Promoted From Legacy Mirror (this PR)

The following modules existed only in `Murphy System/src/` and have been
promoted to root `src/` (no Groq references confirmed):

| Module | Description |
|--------|-------------|
| `as_built_generator.py` | Control-point schedules / schematics from equipment specs |
| `bas_equipment_ingestion.py` | Building Automation System equipment data ingestion |
| `climate_resilience_engine.py` | Climate-risk assessment and resilience scoring |
| `collaborative_task_orchestrator.py` | Multi-agent collaborative task coordination |
| `database/__init__.py` | Database package init |
| `energy_efficiency_framework.py` | Energy optimisation and efficiency modelling |
| `event_backbone_client.py` | EventBackbone publish/subscribe client |
| `industry_automation_wizard.py` | Industry-specific automation configuration wizard |
| `learning_engine_connector.py` | Wires learning-engine outputs to downstream modules |
| `org_chart_generator.py` | Organisational chart generation and export |
| `performance_predictor.py` | ML-based performance prediction for tasks/agents |
| `pro_con_decision_engine.py` | Structured pro/con analysis decision support |
| `production_deliverable_wizard.py` | Production artefact definition and tracking |
| `rosetta_subsystem_wiring.py` | Closes P3-001–P3-006 Rosetta wiring tasks (RSW-001) |
| `runtime/module_loader.py` | Dynamic module loader for the runtime |
| `self_healing_handlers.py` | Concrete recovery handlers for SelfHealingCoordinator |
| `self_healing_startup.py` | Bootstrap self-healing and wire EventBackbone |
| `split_screen_coordinator.py` | UI split-screen layout coordination |
| `synthetic_interview_engine.py` | Synthetic interview simulation and scoring |
| `system_configuration_engine.py` | System-wide configuration management |
| `universal_ingestion_framework.py` | Universal data ingestion pipeline |
| `virtual_controller.py` | Virtual device/controller abstraction |
