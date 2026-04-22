# ADR-0005: Canonical source layout — `Murphy System/` mirrored to root

* **Status:** Accepted
* **Date:** 2026-04-22 (retroactive)
* **Supporting docs:** [docs/SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md),
  `scripts/enforce_canonical_source.py`, `.github/workflows/source-drift-guard.yml`

## Context

The repository contains two parallel copies of the Python source, configs,
Dockerfiles, and most documentation: one rooted at the repository root, and
one rooted at `Murphy System/`. Historically this was the result of a
flattening migration (the codebase used to live entirely under
`Murphy System/`, then the root-level layout was added so that
`pip install -e .`, GitHub Actions paths, and Docker `COPY` lines work
without quoting a path with a space in it).

Three options were on the table:

1. **Delete `Murphy System/`** and treat the root as the only source.
2. **Delete the root** and treat `Murphy System/` as the only source.
3. **Keep both**, declare one canonical, and enforce parity in CI.

Option 1 broke external automation, deployment scripts, and downstream
tooling that referenced `Murphy System/`. Option 2 broke `pip install -e .`,
GitHub Actions YAML paths, and any tooling that does not survive a
space-in-path. Both option 1 and option 2 also break already-cloned
repositories on contributor machines.

## Decision

Option 3. Specifically:

* `Murphy System/` is the **canonical** location for source code, tests,
  configs, and documentation. AI agents and contributors edit there first.
* The root is a **mirror** for the subset of files that tooling requires at
  the root (entrypoints, Docker context, GitHub Actions paths,
  `pip install -e .`).
* The mirror direction is **always** `Murphy System/` → root. Never the
  reverse.
* `scripts/enforce_canonical_source.py` discovers paired files automatically
  and verifies byte equality. The `source-drift-guard` workflow runs it on
  every PR and blocks merges on drift.
* `.github/workflows/` is the **only** location for CI workflow files —
  `Murphy System/.github/workflows/` is reserved for non-runnable
  documentation (`README.md`, `agent.yml` reference templates) and never
  contains files that GitHub Actions executes.

## Consequences

* **Positive:** every tool — `pip`, GitHub Actions, Docker, contributor
  IDEs — works without special-casing. No path-with-spaces gymnastics.
* **Positive:** the canonical location is unambiguous, so AI agents and
  human contributors cannot accidentally edit the "wrong" copy
  asymmetrically.
* **Positive:** drift is mechanically detected, not policed by reviewers.
* **Negative:** every change to a paired file requires updating two paths.
  The cost is small (one `cp` command) compared to either of the
  alternatives, but it is non-zero.
* **Negative:** the layout is unusual and surprises new contributors. The
  copilot-instructions document and `docs/SOURCE_OF_TRUTH.md` mitigate by
  making the rules explicit and short.
