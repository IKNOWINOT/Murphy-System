# Copilot Instructions — Murphy System

## Source of Truth

**`Murphy System/` is the canonical source** for all Python source code,
tests, configs, and documentation.  All CI workflows, the PYTHONPATH, and
the production server (`murphy_production_server.py`) import from
`Murphy System/src`.

## Rules for AI Agents

### 1. Always edit inside `Murphy System/`, never root copies independently

| What you want to change | Where to edit |
|------------------------|---------------|
| Python source modules | `Murphy System/src/` |
| Tests | `Murphy System/tests/` |
| Config files (`.env.example`, `Dockerfile`, etc.) | `Murphy System/` — then sync root copy |
| Documentation | `Murphy System/docs/` or repo root docs |
| CI workflows | Root `.github/workflows/` **only** |

### 2. Root-level files are in one of three categories

| Category | Examples | Rule |
|----------|----------|------|
| **Entrypoints** | `murphy_production_server.py` | Lives at root, imports from `Murphy System/src` via `sys.path` |
| **Mirrors** | `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`, `ARCHITECTURE_MAP.md` | Must be kept byte-identical to `Murphy System/` copy |
| **Root-only** | `.github/`, `pyproject.toml`, root `README.md` | No `Murphy System/` equivalent |

### 3. Only root `.github/workflows/` files are executed

GitHub Actions **only** runs workflows in the root `.github/workflows/`
directory.  The `Murphy System/.github/` directory no longer contains
workflow files — do **not** create new workflow files there.

### 4. CI will block merges if drift is introduced

Two CI jobs enforce parity:

- **`tree-divergence-check`** (in `ci.yml`) — blocks if `.py` files exist
  in `Murphy System/src/` but not in root `src/`.
- **`source-drift-guard`** (in `source-drift-guard.yml`) — blocks if
  paired config files differ between root and `Murphy System/`.

If CI fails with a drift error, copy the canonical `Murphy System/` version
to root (never the reverse) and commit both files.

### 5. Sync direction

```
Murphy System/  →  root  (Murphy System is authoritative)
```

Never edit root copies without also updating the `Murphy System/` copy, and
vice-versa.

## Quick Reference

```bash
# Check for drift locally before opening a PR
python scripts/enforce_canonical_source.py
```

See `docs/SOURCE_OF_TRUTH.md` for the full architecture rationale.
