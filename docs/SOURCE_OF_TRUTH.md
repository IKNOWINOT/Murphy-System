# Source of Truth — Murphy System Architecture

## TL;DR

`Murphy System/` is the **canonical source of truth** for all Python source
code, tests, and configuration.  Root-level copies of the same files are
either entrypoints, mirrors that must stay in sync, or root-only files.

---

## Why `Murphy System/` Exists

The `Murphy System/` subdirectory was created as a **swarm staging area** for
deliverable-to-deliverable handoffs.  In the Murphy swarm pipeline, each
autonomous agent operates within a well-defined deliverable boundary, and
`Murphy System/` represents that boundary.

Evidence that it is the canonical source:

- All CI workflows use `working-directory: "Murphy System"`.
- PYTHONPATH is set to `Murphy System/` and `Murphy System/src` in CI.
- `murphy_production_server.py` sets
  `ROOT = Path(__file__).resolve().parent / "Murphy System"` and inserts
  that path into `sys.path`.
- The Hetzner deploy script runs tests from `Murphy System/tests/`.

---

## File Categories

### Entrypoints (live at root, import from `Murphy System/`)

| File | Role |
|------|------|
| `murphy_production_server.py` | Main production API server; uses `sys.path` to import from `Murphy System/src` |

### Mirrors (must be byte-identical between root and `Murphy System/`)

These files are maintained inside `Murphy System/` and **mirrored** to root.
The CI `source-drift-guard` job will block merges if they drift.

| File | Notes |
|------|-------|
| `.env.example` | Environment variable template |
| `.coveragerc` | Coverage configuration |
| `.dockerignore` | Docker build ignore rules |
| `.gitattributes` | Git attribute rules |
| `Dockerfile` | Container build instructions |
| `docker-compose.yml` | Service composition |
| `requirements.txt` | Python runtime dependencies |
| `ARCHITECTURE_MAP.md` | System architecture documentation |
| `inoni_business_automation.py` | Business automation module |
| `Makefile` | Developer task shortcuts |
| `LICENSE` | License file |
| `setup.py` | Package setup |
| `pyproject.toml` | Project metadata and tool config |

### Root-only (no `Murphy System/` equivalent)

| File/Directory | Notes |
|----------------|-------|
| `.github/` | CI workflows — only root `.github/workflows/` is executed by GitHub Actions |
| `README.md` | Top-level project readme |
| `scripts/` | Utility and maintenance scripts |
| `docs/` (root) | Top-level architecture docs |
| `alembic/`, `alembic.ini` | Database migration files |

---

## Sync Direction

```
Murphy System/  →  root   (canonical → mirror)
```

- **Never** edit root mirrors independently without also updating the
  `Murphy System/` copy.
- When in doubt, treat `Murphy System/` as authoritative and overwrite root.

---

## Drift Prevention

### CI enforcement

Three CI jobs block merges that introduce drift:

1. **`tree-divergence-check`** (`ci.yml`) — fails if any tracked file (`.py`,
   `.html`, `.yaml`, `.yml`, `.md`, `.js`, `.ts`, `.sh`, `.bat`, `.css`)
   exists in `Murphy System/` but not at the repo root.  Covers **all
   directories**, not just `src/`.
2. **`source-drift-guard`** (`source-drift-guard.yml`) — fails if any
   auto-discovered paired file differs in content between root and
   `Murphy System/`.  On PRs, also runs a session-scoped check that verifies
   changed files have their mirror counterpart updated in the same PR.

### Running locally

```bash
# Full scan — auto-discovers all pairs and checks byte-identity:
python scripts/enforce_canonical_source.py

# Example output when clean:
# OK: All N auto-discovered paired files are byte-identical between root and Murphy System/.

# Example output when drifted:
# DRIFT DETECTED: 1 file(s) differ between root and Murphy System/:
#   requirements.txt  (root=2,900B  mirror=2,500B)

# Session-scoped scan — checks only files changed in the current branch:
python scripts/enforce_canonical_source.py --changed-only
```

---

## Dead Workflow Files Removed

`Murphy System/.github/workflows/` previously contained workflow files
(`doc-drift.yml`, `gap-detector.yml`, `TASK_INSTRUCTIONS.txt`) that **never
executed** because GitHub Actions only reads root `.github/workflows/`.
Those files were removed to prevent AI agents from treating `Murphy System/`
as a standalone repo root.

---

## Historical Background

Prior to this architecture being formalized, `murphy_production_server.py`
lived at root and imported from `Murphy System/src` via `sys.path.insert`.
This created a confusing two-tree structure where root and subdirectory
copies evolved independently.  The resolution:

1. Declare `Murphy System/` canonical.
2. Make CI drift checks **blocking** (not just warnings).
3. Document the pattern so contributors and AI agents follow it.
