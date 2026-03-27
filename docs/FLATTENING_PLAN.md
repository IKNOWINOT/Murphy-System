# Murphy System — Phased Flattening & Improvement Plan

> **Version:** 1.0  
> **License:** BSL 1.1  
> **Last updated:** 2026-03-09

This document is the authoritative, phased execution plan for three interconnected structural improvements to the Murphy System repository. All eighteen phases are scoped so that each can be executed, verified, and rolled back independently.

---

## Overview

| Phase group | Phases | Goal |
|---|---|---|
| Repo flattening | 1–4 | Move `murphy_system/*` to root, fix imports and scripts |
| Documentation consolidation | 5–8 | Merge duplicate docs, rewrite to reflect real system |
| Librarian-driven routing | 9–12 | Wire `task_router.py`, `SystemLibrarian`, `SolutionPathRegistry` |
| UI consolidation | 13–15 | Dark-only theme, consolidate CSS, simplify terminal HTML |
| Final validation | 16–18 | Tests, imports, scripts, smoke test |

---

## Phase 1 — Audit and Snapshot

**Goal:** Document the exact current state before any file moves, to enable reliable rollback.

**Scope:** Read-only. No files modified.

**Prerequisites:** None.

**Steps:**
1. Run `git status` and confirm the working tree is clean.
2. Capture directory tree: `find . -type f | sort > /tmp/pre-flatten-manifest.txt`
3. Record all Python `import` statements that reference `murphy_system/` subdirectory paths.
4. Record all shell script invocations that `cd "murphy_system"` or reference it explicitly.
5. Record all HTML files that `<link>` or `<script src="...">` with paths containing `murphy_system/`.
6. Commit the manifest as `docs/archive/pre-flatten-manifest.txt`.

**Verification:**
- Manifest file exists and is non-empty.
- `git diff HEAD` shows only the new manifest file.

**Rollback:**
- Delete the manifest file. Nothing else was changed.

---

## Phase 2 — Move Source Tree to Repository Root

**Goal:** Copy everything from `murphy_system/` to the repository root, preserving directory structure.

**Prerequisites:** Phase 1 complete.

**Files touched:**
- All files under `murphy_system/` (moved, not deleted — deletion is Phase 4).
- Root-level `.gitignore` (add `murphy_system/` exclusion entry).

**Steps:**
1. From the repository root, copy the subtree:
   ```bash
   cp -r "murphy_system/." .
   ```
2. Resolve conflicts where a root-level file already exists (e.g., `README.md`, `GETTING_STARTED.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`):
   - Keep the `murphy_system/` version as the canonical version (it is more detailed and current).
   - Archive the root-level stale copy to `docs/archive/root-level-pre-flatten/`.
3. Stage the new files: `git add .`
4. Do **not** commit yet — verify imports first (Phase 3).

**Verification:**
- `src/`, `static/`, `tests/`, `docs/`, `bots/`, `config/`, `k8s/`, `monitoring/` all exist at the repository root.
- `murphy_system_1.0_runtime.py` exists at the repository root.
- `murphy_terminal.py` exists at the repository root.
- All 14 HTML terminal files exist at the repository root.

**Rollback:**
```bash
git checkout -- .
git clean -fd
```

---

## Phase 3 — Update All Import Paths and Script References

**Goal:** Every Python import, shell script, HTML asset path, and documentation link that pointed inside `murphy_system/` now points to the equivalent path at the repository root.

**Prerequisites:** Phase 2 complete (files exist at both locations, not yet committed).

**Files touched:**
- `setup_and_start.sh`
- `setup_and_start.bat`
- `scripts/*.sh` (any script that `cd "murphy_system"`)
- `start_murphy_1.0.sh` (if present)
- `murphy` CLI script (if present)
- `murphy_system_1.0_runtime.py` — any internal `sys.path` manipulation that prepends `murphy_system/`
- `src/**/*.py` — any module that uses `from Murphy System.src...` style imports
- All 14 HTML terminal files — `<link href="murphy_system/static/...">` → `<link href="static/...">`
- `Makefile` — any target that `cd "murphy_system"`
- `docker-compose.yml`, `Dockerfile` — working directory or volume mounts

**Steps:**
1. Find all `cd "murphy_system"` occurrences:
   ```bash
   grep -r 'Murphy System' . --include="*.sh" --include="*.bat" --include="*.py" \
        --include="*.html" --include="*.yml" --include="*.yaml" --include="Makefile" -l
   ```
2. For each file found, replace `murphy_system/` path prefixes with the root-relative equivalent.
3. For shell scripts: replace `cd "murphy_system"` with `cd "$(dirname "$0")"` or remove the `cd` entirely if the script is already expected to run from the root.
4. For HTML files: replace `src="murphy_system/static/` with `src="static/` and `href="murphy_system/static/` with `href="static/`.
5. Run `python -c "import murphy_system_1.0_runtime"` equivalent import check (substitute actual module name).

**Verification:**
- `grep -r "murphy_system" . --include="*.py" --include="*.sh" --include="*.html"` returns no results (excluding `docs/archive/`).
- `bash setup_and_start.sh --check` (dry-run mode) exits 0.
- `python3 -c "import sys; sys.path.insert(0, '.'); import src.governance_kernel.governance_kernel"` exits 0.

**Rollback:**
```bash
git checkout -- .
git clean -fd
```

---

## Phase 4 — Remove the `murphy_system/` Subdirectory

**Goal:** Delete the now-redundant nested subdirectory.

**Prerequisites:** Phase 3 complete and verified — imports work from root.

**Files touched:**
- `murphy_system/` directory (deleted entirely).

**Steps:**
1. Confirm Phase 3 verification passes.
2. Remove the directory:
   ```bash
   git rm -r "murphy_system/"
   ```
3. Commit:
   ```bash
   git commit -m "chore: flatten repo — remove murphy_system/ subdirectory"
   ```

**Verification:**
- `ls "murphy_system/"` returns "No such file or directory".
- `python3 murphy_system_1.0_runtime.py --dry-run` exits 0.
- `bash setup_and_start.sh` completes successfully.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 5 — Consolidate `GETTING_STARTED.md`

**Goal:** Produce a single authoritative `GETTING_STARTED.md` at the repository root that accurately describes what Murphy System is and how to use it.

**Prerequisites:** Phase 4 complete (single root exists).

**Files touched:**
- `GETTING_STARTED.md` (root) — full rewrite.
- `docs/archive/GETTING_STARTED_pre_flatten_root.md` (archive of old root version).
- `docs/archive/GETTING_STARTED_pre_flatten_murphy_system.md` (archive of old nested version).

**Steps:**
1. Archive both old versions to `docs/archive/`.
2. Write the new `GETTING_STARTED.md` per the specification in Problem 2 of the problem statement:
   - Open with what Murphy System IS.
   - Two-phase architecture (Generative Setup → Production Execute).
   - Governance model (confidence scoring, gates, HITL).
   - Real module surface area summary.
   - Working installation steps (`setup_and_start.sh`).
   - Real API examples (chat, execute, librarian queries, gate status).
   - First-class concepts: Librarian, Confidence Engine, Gate system, Wingman Protocol.
   - No hype, no emoji spam, no internal operational details.
3. Commit.

**Verification:**
- `GETTING_STARTED.md` contains the word "Librarian" at least once.
- `GETTING_STARTED.md` contains the word "governance" at least once.
- `GETTING_STARTED.md` does not contain "MercyAnnouncer" or "YouTube publishing".
- `GETTING_STARTED.md` does not contain broken relative links (run `markdown-link-check` or equivalent).

**Rollback:**
```bash
git revert HEAD
cp docs/archive/GETTING_STARTED_pre_flatten_root.md GETTING_STARTED.md
git commit -m "revert: restore old GETTING_STARTED.md"
```

---

## Phase 6 — Consolidate `README.md`

**Goal:** Produce a single authoritative `README.md` at the repository root.

**Prerequisites:** Phase 4 complete.

**Files touched:**
- `README.md` (root) — review and update to reflect flattened structure.
- `docs/archive/README_pre_flatten_root.md` (archive).

**Steps:**
1. Archive the old root-level README to `docs/archive/`.
2. Merge the best content from the `murphy_system/README.md` into the root `README.md`.
3. Update all internal links to reflect the flat path structure.
4. Ensure the README points to `GETTING_STARTED.md` as the entry point for new users.

**Verification:**
- All relative links in `README.md` resolve to existing files.
- `README.md` contains a link to `GETTING_STARTED.md`.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 7 — Consolidate Remaining Duplicate Docs

**Goal:** Merge all other duplicate root-level vs. `murphy_system/`-level documentation files.

**Prerequisites:** Phase 5 and Phase 6 complete.

**Files touched (examples — exact list from Phase 1 manifest):**
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`

**Steps:**
1. For each duplicate pair, compare root-level vs. `murphy_system/` version.
2. Keep the more complete/recent version; archive the other to `docs/archive/`.
3. Ensure all internal cross-references use root-relative paths.

**Verification:**
- No two files in the repository have identical base names at different directory depths (excluding `docs/archive/`).

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 8 — Update All Internal Documentation Links

**Goal:** Every `docs/`, `documentation/`, and in-code reference that points to a path inside the old `murphy_system/` structure is updated to the flat path.

**Prerequisites:** Phase 7 complete.

**Files touched:**
- All `.md` files under `docs/`.
- All `.md` files under `documentation/`.
- Any `.py` or `.sh` file with string references to docs paths.

**Steps:**
1. Find all occurrences of `murphy_system/` in markdown files:
   ```bash
   grep -r "murphy_system/" docs/ documentation/ --include="*.md" -l
   ```
2. For each occurrence, replace with the root-relative equivalent path.
3. Run a link checker to confirm no broken links remain.

**Verification:**
- `grep -r "murphy_system/" docs/ documentation/ --include="*.md"` returns no results.
- Link checker reports zero broken internal links.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 9 — Implement `task_router.py`

**Goal:** Create the Librarian-first task router that replaces hardcoded `IntegrationBus` chains.

**Prerequisites:** Phase 4 complete (flat source tree).

**Files touched:**
- `src/task_router/task_router.py` (new).
- `src/task_router/__init__.py` (new).
- `tests/test_task_router.py` (new).

**Steps:**
1. Implement `TaskRouter` per the interface in `docs/LIBRARIAN_ROUTING_SPEC.md`.
2. The router must:
   a. Accept any incoming task dict.
   b. Call `SystemLibrarian.find_capabilities(task)` to get ranked `CapabilityMatch` list.
   c. Build `SolutionPath` objects from the matches.
   d. Pass paths through `GovernanceKernel` gate validation.
   e. Return the best valid `SolutionPath` or raise `NoViablePathError`.
3. Write unit tests covering: happy path, no capabilities found, all paths gate-blocked, HITL intercept.

**Verification:**
- `python -m pytest tests/test_task_router.py -v` passes.
- `TaskRouter` is importable from `src.task_router`.

**Rollback:**
```bash
git rm src/task_router/task_router.py src/task_router/__init__.py tests/test_task_router.py
git commit -m "revert: remove task_router.py"
```

---

## Phase 10 — Wire `SystemLibrarian` to `ModuleRegistry`

**Goal:** `SystemLibrarian` consumes `ModuleRegistry.get_capabilities()` instead of maintaining its own hardcoded capability dictionary.

**Prerequisites:** Phase 9 complete.

**Files touched:**
- `src/system_librarian/system_librarian.py` (or wherever `SystemLibrarian` is defined).
- `src/module_registry/module_registry.py` (ensure `get_capabilities()` exists and is public).

**Steps:**
1. Locate `SystemLibrarian.__init__` or `load_capabilities()` method.
2. Replace hardcoded dict with a call to `ModuleRegistry.get_capabilities()`.
3. Ensure `CapabilityMap.scan()` output is fed into the Librarian's knowledge base on startup.
4. Wire the `librarian_bot` TypeScript service via the existing `LibrarianAdapter` bridge.

**Verification:**
- `python -m pytest tests/test_system_librarian.py -v` passes.
- `SystemLibrarian().find_capabilities("generate invoice")` returns a non-empty list of `CapabilityMatch` objects sourced from the module registry.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 11 — Implement `SolutionPathRegistry`

**Goal:** Persist solution path alternatives so the system can present options to the user, learn which paths perform better, and fall back when the primary path fails.

**Prerequisites:** Phase 10 complete.

**Files touched:**
- `src/solution_path_registry/solution_path_registry.py` (new).
- `src/solution_path_registry/__init__.py` (new).
- `tests/test_solution_path_registry.py` (new).

**Steps:**
1. Implement `SolutionPathRegistry` per the interface in `docs/LIBRARIAN_ROUTING_SPEC.md`.
2. Persist paths to the existing `data/` directory as JSON.
3. Expose:
   - `register(task_id, paths: List[SolutionPath])` — store alternatives.
   - `get_alternatives(task_id) -> List[SolutionPath]` — retrieve for HITL presentation.
   - `record_outcome(task_id, path_id, success: bool)` — feed into `FeedbackIntegrator`.
4. Write unit tests.

**Verification:**
- `python -m pytest tests/test_solution_path_registry.py -v` passes.
- Registry survives a process restart (data persists to disk).

**Rollback:**
```bash
git rm -r src/solution_path_registry/ tests/test_solution_path_registry.py
git commit -m "revert: remove SolutionPathRegistry"
```

---

## Phase 12 — Connect `FeedbackIntegrator` to `SolutionPathRegistry`

**Goal:** Execution outcomes recorded by the `SolutionPathRegistry` flow into the `FeedbackIntegrator`, so the router learns to prefer paths that succeed historically.

**Prerequisites:** Phase 11 complete.

**Files touched:**
- `src/feedback_integrator/feedback_integrator.py` (update).
- `src/task_router/task_router.py` (update scoring to use feedback weights).

**Steps:**
1. Add `FeedbackIntegrator.get_path_score(capability_id) -> float` if not present.
2. In `TaskRouter._rank_paths()`, multiply the Librarian match score by the `FeedbackIntegrator` historical success rate.
3. Write regression tests confirming that a path that has previously failed 3 times is ranked lower than a fresh alternative.

**Verification:**
- `python -m pytest tests/test_task_router.py tests/test_feedback_integrator.py -v` passes.
- A path with 100% historical failure is never selected as primary when an alternative exists.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 13 — Remove Light Theme from CSS

**Goal:** `murphy-design-system.css` no longer contains the `body.murphy-light` block or any `prefers-color-scheme: light` media queries.

**Prerequisites:** Phase 4 complete (files at root).

**Files touched:**
- `static/murphy-design-system.css`.

**Steps:**
1. Delete the `/* 2. LIGHT THEME */` section (`body.murphy-light { ... }`) entirely.
2. Delete any `@media (prefers-color-scheme: light)` blocks.
3. Delete any `body.murphy-light` overrides scattered through the file (e.g., `.murphy-topbar` variant at line 840).
4. Run a visual regression check: load each of the 14 terminal HTML files in a browser, confirm no white-background flash.

**Verification:**
- `grep -n "murphy-light" static/murphy-design-system.css` returns no results.
- All 14 HTML interfaces render with dark background in all major browsers.

**Rollback:**
```bash
git checkout -- static/murphy-design-system.css
```

---

## Phase 14 — Remove Light Theme from `murphy-components.js`

**Goal:** `MurphyTheme` class is dark-only. The `toggle()` method, `_readStorage()` / `_persist()` light-related logic, and `murphy-light` class manipulation are removed.

**Prerequisites:** Phase 13 complete.

**Files touched:**
- `static/murphy-components.js`.

**Steps:**
1. In `MurphyTheme`:
   - Remove the `toggle()` method.
   - Remove `_persist()` and `_readStorage()` (no longer needed).
   - Simplify `init()` to always set `this._theme = 'dark'` and call `this._apply()`.
   - Simplify `_apply()` to only call `document.body.classList.remove('murphy-light')`.
   - Remove the `onChange()` callback system if it was only used for theme switching.
2. Remove all `localStorage` reads/writes related to theme.
3. Search HTML files for any theme-toggle button (`id="theme-toggle"` or similar) and remove those buttons.

**Verification:**
- `grep -n "murphy-light\|toggle.*theme\|theme.*toggle" static/murphy-components.js` returns no results.
- `MurphyTheme.get()` always returns `'dark'`.

**Rollback:**
```bash
git checkout -- static/murphy-components.js
```

---

## Phase 15 — Consolidate `murphy-theme.css` into `murphy-design-system.css`

**Goal:** The older `murphy-theme.css` (`#0a0a0a` black, `#00ff41` green) is evaluated and either merged or archived. A single canonical dark stylesheet remains.

**Prerequisites:** Phase 13 and Phase 14 complete.

**Files touched:**
- `static/murphy-theme.css`.
- `static/murphy-design-system.css`.
- Any HTML file that links `murphy-theme.css`.

**Steps:**
1. Audit `murphy-theme.css` for any rules not present in `murphy-design-system.css`.
2. If unique rules exist and are needed, merge them into `murphy-design-system.css`.
3. Remove all `<link href="...murphy-theme.css">` references from HTML files.
4. Archive `murphy-theme.css` to `docs/archive/murphy-theme.css.bak`.

**Verification:**
- `grep -r "murphy-theme.css" . --include="*.html"` returns no results.
- All 14 terminal UIs render correctly with only `murphy-design-system.css`.

**Rollback:**
```bash
git revert HEAD
```

---

## Phase 16 — Full Test Suite Validation

**Goal:** All existing tests pass against the flattened, consolidated codebase.

**Prerequisites:** Phases 1–15 complete.

**Steps:**
1. From the repository root (not from `murphy_system/`):
   ```bash
   python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/phase16-test-results.txt
   ```
2. Compare pass/fail counts to the pre-flatten baseline recorded in Phase 1.
3. Any new failures introduced by the flatten are bugs — fix them in this phase.
4. Any pre-existing failures (numpy-dependent tenant isolation tests etc.) are documented and accepted.

**Verification:**
- Test count equals or exceeds pre-flatten baseline.
- Zero new test failures relative to baseline.

**Rollback:**
- Fix failing tests in-place. Phase 16 is a validation phase, not reversible as a unit.

---

## Phase 17 — Verify All Scripts and Import Paths

**Goal:** Confirm that every entry point the system advertises actually works from a clean checkout at the repository root.

**Prerequisites:** Phase 16 passing.

**Steps:**
1. Fresh virtualenv:
   ```bash
   python3 -m venv /tmp/murphy-verify-venv
   source /tmp/murphy-verify-venv/bin/activate
   pip install -r requirements.txt
   ```
2. Check each entry point:
   ```bash
   python3 -c "import murphy_system_1.0_runtime"   # or equivalent
   bash setup_and_start.sh --check
   python3 murphy_terminal.py --help
   murphy --version                                  # CLI
   ```
3. Confirm all HTML files load without 404s for CSS/JS assets:
   ```bash
   python3 -m http.server 9999 &
   curl -s http://localhost:9999/terminal_unified.html | grep -c "murphy-design-system.css"
   ```

**Verification:**
- All entry points exit 0 (or print help text without errors).
- No 404s for static assets.

**Rollback:**
- Fix broken paths in-place. This is a verification phase.

---

## Phase 18 — Smoke Test the Full Boot Sequence

**Goal:** Murphy System boots completely, passes its own health check, and correctly routes a representative task through the Librarian.

**Prerequisites:** Phase 17 passing.

**Steps:**
1. Start Murphy:
   ```bash
   bash setup_and_start.sh
   ```
2. Wait for the ready signal:
   ```
   INFO: Uvicorn running on http://0.0.0.0:8000
   ```
3. Health check:
   ```bash
   curl http://localhost:8000/api/health
   # Expected: {"status":"ok","version":"1.0.0",...}
   ```
4. Librarian query:
   ```bash
   curl -X POST http://localhost:8000/api/librarian/query \
        -H "Content-Type: application/json" \
        -d '{"query": "generate an invoice for a consulting project"}'
   # Expected: list of capability matches with scores
   ```
5. Task execution through new `TaskRouter`:
   ```bash
   curl -X POST http://localhost:8000/api/execute \
        -H "Content-Type: application/json" \
        -d '{"task": "generate invoice", "amount": 5000, "client": "Acme Corp"}'
   # Expected: {"success": true, "solution_path": "invoice_processing_pipeline", ...}
   ```
6. Gate status:
   ```bash
   curl http://localhost:8000/api/gates/status
   # Expected: all active gates listed with current state
   ```

**Verification:**
- All four `curl` commands return HTTP 200.
- `"status": "ok"` in health check.
- Librarian returns at least one capability match.
- Execute returns `"success": true`.
- Gates endpoint returns gate list.

**Rollback:**
- This is the final validation. Any failures here are bugs in earlier phases — trace back to the relevant phase and fix there.

---

## Cross-Phase Dependencies

```
Phase 1
  └── Phase 2
        └── Phase 3
              └── Phase 4
                    ├── Phase 5 ── Phase 6 ── Phase 7 ── Phase 8
                    ├── Phase 9 ── Phase 10 ── Phase 11 ── Phase 12
                    └── Phase 13 ── Phase 14 ── Phase 15
                                                          └── Phase 16 ── Phase 17 ── Phase 18
```

Phases 5–8, 9–12, and 13–15 can be executed in parallel after Phase 4 completes. Phases 16–18 require all prior phases to be complete.

---

*End of Flattening Plan — Murphy System v1.0*
