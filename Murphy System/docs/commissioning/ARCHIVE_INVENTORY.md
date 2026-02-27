# Archive Inventory

**Document ID:** MURPHY-ARC-2026-001  
**Version:** 1.0.0  
**Date:** February 27, 2026  
**Owner:** @doc-lead  
**Phase:** 1 — Environment Cleanup & Assessment  
**Completion:** 100%

---

## Overview

This document catalogs all archived content in the Murphy System repository. Archived files are preserved for historical reference but are not part of the active system. **No files have been deleted** — all pushes have preserved the complete history.

---

## Archive Structure

```
Murphy System/archive/
├── ARCHIVE_MANIFEST.md          — Self-documenting manifest of archive contents
├── artifacts/                   — Build artifacts, generated outputs, snapshots
├── legacy_versions/             — Previous major version implementations
├── legacy_workspace/            — Development workspace backups
└── murphy_integrated_archive/   — Consolidated archive from integration phases
```

---

## Archive Categories

### 1. Legacy Versions (`archive/legacy_versions/`)

| Content | Description | Original Version | Archived Date |
|---------|-------------|-----------------|---------------|
| Pre-1.0 runtime files | Earlier runtime implementations before unified 1.0 | v0.x | Pre-2025 |
| Phase prototypes | Phase 1-5 prototype implementations | Prototype | Pre-2025 |
| Standalone engines | Individual engine implementations before UCP | Standalone | Pre-2025 |

**Status:** Historical reference only. Superseded by `murphy_system_1.0_runtime.py` and `universal_control_plane.py`.

### 2. Artifacts (`archive/artifacts/`)

| Content | Description | Purpose |
|---------|-------------|---------|
| Generated outputs | Auto-generated reports, diagrams | Historical snapshots |
| Build artifacts | Previous build outputs | Rollback reference |
| Test snapshots | Historical test results | Regression comparison |

**Status:** Snapshot reference. Active artifacts are generated fresh by CI/CD.

### 3. Legacy Workspace (`archive/legacy_workspace/`)

| Content | Description | Purpose |
|---------|-------------|---------|
| Development notebooks | Jupyter/exploration notebooks | Research reference |
| Configuration backups | Previous config versions | Migration reference |
| Workspace state | Saved development state | Recovery reference |

**Status:** Development history. Not required for production operation.

### 4. Integrated Archive (`archive/murphy_integrated_archive/`)

| Content | Description | Purpose |
|---------|-------------|---------|
| Pre-integration modules | Modules before unified integration | Merge history |
| Conflict resolutions | Records of merge decisions | Decision reference |
| Migration artifacts | Data migration scripts | One-time use |

**Status:** Integration history. All content has been successfully merged into active codebase.

---

## Archive Size Summary

| Category | Est. File Count | Purpose | Retention Policy |
|----------|----------------|---------|-----------------|
| Legacy Versions | ~50+ | Historical reference | Permanent |
| Artifacts | ~30+ | Snapshots | Permanent |
| Legacy Workspace | ~20+ | Development history | Permanent |
| Integrated Archive | ~40+ | Merge history | Permanent |
| **Total** | **~140+** | **Complete history** | **Permanent** |

---

## Relationship to Active System

| Archive Content | Active Replacement | Migration Complete |
|----------------|-------------------|-------------------|
| Pre-1.0 runtimes | `murphy_system_1.0_runtime.py` | ✅ Yes |
| Standalone engines | `universal_control_plane.py` | ✅ Yes |
| Phase prototypes | `src/` (150+ modules) | ✅ Yes |
| Old configurations | `.env.example`, `config/` | ✅ Yes |
| Old tests | `tests/` (297 files) | ✅ Yes |

---

## Recommendations

1. **Do NOT delete archive contents** — Git history preservation is a project policy
2. **Do NOT reference archive in new code** — Use active `src/` modules only
3. **Do NOT run archived test files** — They may reference deprecated APIs
4. **Consider:** Adding archive path exclusions to CI/CD test discovery
5. **Consider:** `ARCHIVE_MANIFEST.md` within archive should be kept up-to-date

---

**© 2026 Inoni Limited Liability Company. All rights reserved.**
