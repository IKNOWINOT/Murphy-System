# Surface-area audit — actionable deletion candidates

**Class S Roadmap, Item 20** · *Updated by re-running the script and
re-categorizing.*

This document is the queue of "delete or move to `experimental/`"
decisions surfaced by `scripts/find_unused_modules.py`. It is the
remaining sub-item of Item 20 — the script and allowlist have already
landed; what's left is the per-module audit-owner call.

## How the list is generated

```bash
python scripts/find_unused_modules.py \
    --allowlist scripts/find_unused_modules.allowlist.txt
```

Static counts (April 2026):

| Stage                                                  | Modules |
|--------------------------------------------------------|--------:|
| Total Python modules under `src/` (excluding `__init__.py` and tests) | 1 302 |
| Reported as unused by the absolute-only scanner (the original bug)    |   200 |
| Reported as unused after the relative-import fix landed in this PR    |    79 |
| Allowlisted (string-name registries: matrix bridge, terminal command registry, `python -m` entry points) | 74 |
| **Actionable deletion candidates remaining**           |   **5** |

The 200 → 5 reduction (97.5 %) is what makes this list reviewable. Before
the fix, the audit owner would have had to triage 200 candidates by
hand; ~195 of those were re-exports caught by the new relative-import
pass and runtime-loaded modules caught by the seed allowlist.

## The 5 actionable candidates

Each row is a single audit-owner decision: **delete**, **move to
`experimental/`**, or **wire the lone consumer**.

| Module | LOC | Status | Recommended action | Notes |
|---|---:|---|---|---|
| `src/presets/healthcare.py` | 143 | Obsolete | **Delete** | Superseded by the live `src/org_build_plan/presets/` package (which has `saas_agency.py`, `nonprofit_advocacy.py`, etc., consumed by `src/org_build_plan/build_orchestrator.py` via `from .presets import get_preset, list_presets`). The `src/presets/` siblings (`base.py`, `financial_services.py`, `manufacturing.py`) are referenced — **only the four vertical presets here are orphaned**. |
| `src/presets/professional_services.py` | 1 786 | Obsolete | **Delete** | Same parallel-package situation. |
| `src/presets/retail_commerce.py` | 213 | Obsolete | **Delete** | Same. |
| `src/presets/technology.py` | 1 318 | Obsolete | **Delete** | Same. |
| `src/runtime/module_loader.py` | 244 | Built-but-not-wired | **Wire or delete** | Module docstring: *"Provides ModuleLoadReport and ModuleLoader to replace the ad-hoc try/except pattern in app.py."* Never wired into `app.py`. Two paths forward: (a) wire it into `src/runtime/app.py` to replace the `_deps` try/except blocks (the original intent); (b) delete it as a never-finished refactor. **Recommend (a)**, tracked as the next-PR title *"Wire `ModuleLoader` into `app.py`; remove `src/runtime/_deps.py` try/except blocks."* If (a) does not happen within one quarter, fall back to (b). |

**Total reclaimable surface if all 5 are deleted: ~3 700 LOC** (the four
preset files alone are 3 460 LOC; the loader adds 244 if option (b) is
chosen).

## Categories the allowlist suppresses (74 entries)

Recorded here so the audit owner can re-verify that the suppression is
still warranted next quarter:

| Category | Count | Loaded by |
|---|---:|---|
| Matrix-bridge module manifest | 60 | `src/matrix_bridge/module_manifest.py` (string `module='integrations_airtable_connector'`-style lookup) |
| Murphy terminal command registry | 13 | `src/murphy_terminal/command_registry.py` (`CommandDefinition("name", ...)`) |
| `python -m` CLI entry points | 1 | `src.murphy_cli.__main__` |

If any of these registries is removed or rewritten to use real `import`
statements, the corresponding allowlist block becomes stale and should
be removed in the same PR.

## Re-running the audit

* **Locally before opening a PR that touches `src/`**:

  ```bash
  python scripts/find_unused_modules.py \
      --allowlist scripts/find_unused_modules.allowlist.txt
  ```

* **CI**: not currently wired. The audit is intentionally reviewer-driven
  rather than gate-driven: a CI gate would force every PR that adds a
  new module to also add an importer or allowlist entry, which has
  higher false-positive cost than value at this stage of the codebase.

## History

| Date | Change | LOC delta |
|---|---|---|
| 2026-04-22 | Relative-import detection added; allowlist seeded; 200 → 5 | n/a (read-only audit) |
