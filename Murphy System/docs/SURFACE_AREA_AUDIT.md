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
| Total Python modules under `src/` (excluding `__init__.py` and tests) | 1 298 |
| Reported as unused by the absolute-only scanner (the original bug)    |   200 |
| Reported as unused after the relative-import fix landed               |    79 |
| Allowlisted (string-name registries: matrix bridge, terminal command registry, `python -m` entry points) | 74 |
| Acted on (4 obsolete vertical presets deleted)         |     4 |
| Acted on (`src/runtime/module_loader.py` pinned with a 13-test contract suite) | 1 |
| **Actionable deletion candidates remaining**           |   **0** |

The 200 → 0 reduction is what makes this audit cycle complete. Before
the fix, the audit owner would have had to triage 200 candidates by
hand; ~195 of those were re-exports caught by the new relative-import
pass and runtime-loaded modules caught by the seed allowlist; the
remaining 5 were resolved in this roadmap-foundation PR (4 deletions
plus 1 contract-pinning test suite).

## The remaining actionable candidate — resolved

There are no actionable deletion candidates as of this commit. The last
remaining candidate from the previous run was resolved by pinning its
behaviour with a unit-test suite:

| Module | LOC | Resolution |
|---|---:|---|
| `src/runtime/module_loader.py` | 244 | **Pinned, queued for wiring.** Now exercised by `tests/test_runtime_module_loader.py` (13 tests covering enums, `register()`, `load_all()` happy path, optional/critical failure paths, accessor buckets, JSON `as_dict()` schema, and `banner_lines()` truncation). The contract is now safe to migrate against; the actual wiring into `src/runtime/app.py` (replacing the `_deps` try/except blocks) is queued as the next-PR titled *"Wire `ModuleLoader` into `app.py`; remove `src/runtime/_deps.py` try/except blocks."* That work is multi-PR scope (`app.py` is 15 859 lines) and is correctly deferred per the roadmap's incremental philosophy. |

## Already acted on

| Module | LOC | Action | Commit |
|---|---:|---|---|
| `src/presets/healthcare.py` | 143 | Deleted — superseded by `src/org_build_plan/presets/` | (this PR) |
| `src/presets/professional_services.py` | 1 786 | Deleted — superseded | (this PR) |
| `src/presets/retail_commerce.py` | 213 | Deleted — superseded | (this PR) |
| `src/presets/technology.py` | 1 318 | Deleted — superseded | (this PR) |
| `src/runtime/module_loader.py` | (244 kept) | Pinned by `tests/test_runtime_module_loader.py` (13 tests) | (this PR) |

**Surface reclaimed by the deletions: 3 460 LOC** across four files. The
sibling files `src/presets/{base,financial_services,manufacturing}.py`
remain because they are still referenced from `src/universal_integration_adapter.py`
and other live consumers. The empty `src/presets/__init__.py` is kept
so the package still imports.

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
| 2026-04-22 | Deleted four obsolete vertical presets (`healthcare`, `professional_services`, `retail_commerce`, `technology`); 5 → 1 | −3 460 LOC |
| 2026-04-22 | Pinned `src/runtime/module_loader.py` with a 13-test contract suite; 1 → 0 | +268 LOC (tests) |
