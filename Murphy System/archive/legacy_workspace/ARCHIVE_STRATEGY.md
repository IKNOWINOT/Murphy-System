# Murphy System Repository Archive Strategy

**Repository:** murphy_integrated (inside Murphy System workspace)  
**Owner:** Inoni LLC  
**Contact:** Corey Post (corey.gfc@gmail.com)

This document provides a structured, actionable archiving strategy and the concrete plan applied to this repository.

---

## 1. Validation of Approach

**Assessment:** Your proposed criteria are sound. Archiving legacy code that is not part of the production runtime is the right move for navigability and safety.

**Strengths:**
- Focused on production stability (v1.0 remains untouched).
- Keeps legacy work accessible for v3.0 feature migration.
- Avoids destructive deletions.

**Gaps to address:**
- Define “production runtime” explicitly (entry points + runtime dependencies).
- Ensure you preserve install scripts, requirements, and documentation tied to v1.0.
- Add a manifest so future you can locate archived assets quickly.

**Alternative considerations:**
- **Git tags** for “v1.0 production” and “pre-archive state.”
- **Archive folder** inside the same repo for traceability.
- **Optional**: split v2/v3 into separate repos once v3 stabilizes.

---

## 2. File Classification Guidelines

**Keep in main repository (active):**
- v1.0 runtime entry points (`murphy_system_1.0_runtime.py`, `murphy_complete_backend_extended.py`).
- `src/` modules referenced by those entry points.
- `start_murphy_1.0.*`, `requirements*.txt`, `setup.py`.
- Core docs for v1.0 runtime and v3 planning.
- `murphy_v3/` (planned active development).

**Safe to archive:**
- Legacy snapshots (`murphy_system_*`, `murphy_complete_*`, `murphy_runtime_analysis`, etc.).
- Extracts, backups, demo packages that are not required by v1.0 runtime.
- Large log/output folders and summarized conversations.

**Special handling:**
- **Configuration**: keep any active configs for v1.0 (`requirements`, env templates). Archive legacy configs with their version.
- **Documentation**: keep v1.0 docs active; archive historical reports and older summaries.
- **Dependencies**: only archive requirements files if tied to legacy versions.

**Version 2.0 guidance:**
- Treat v2.0 as **legacy/inactive** unless actively maintained.
- Archive v2.0 snapshots but keep a short README in the archive explaining why they were archived and how to revive them.

---

## 3. Archive Organization Best Practices

**Recommended structure:**
```
archive/
  legacy_versions/
  artifacts/
  packages/
  ARCHIVE_MANIFEST.md
```

**Organization model:**
- **legacy_versions/**: old code snapshots (v2, abandoned iterations, extracted backups).
- **artifacts/**: outputs, logs, transcripts, demo captures.
- **packages/**: zip or packaged distributions.

**Documentation to maintain:**
- `ARCHIVE_MANIFEST.md` with:
  - what moved,
  - why it moved,
  - original path,
  - date archived,
  - intended use for v3 integration.

**Repo vs separate repo:**
- Keep archives in this repo for now (best traceability).
- Consider moving to a separate repo once v3 stabilizes and legacy usage drops.

---

## 4. Risk Assessment

**Risks:**
- Accidentally moving a runtime dependency.
- Losing context for why a file existed.
- Breaking scripts/docs referencing old paths.

**Precautions:**
- Tag the current state (`v1.0-production` / `pre-archive-cleanup`).
- Use `git mv` to preserve history.
- Keep a manifest and update any README references.
- Run a targeted smoke test (basic imports or startup script) after moves.

**Rollback plan:**
- `git revert` the archive commit(s) or move directories back with `git mv`.
- Keep the tag from pre-archive state for quick reset.

---

## 5. Version Control Considerations

**Best practices:**
- **Tags**: `v1.0-production` and `pre-archive-cleanup`.
- **Branches**: `archive-cleanup` for the work (already in progress here).
- **git mv** to preserve file history.

**Traceability:**
- Manifest mapping old → new paths.
- Keep archived files in-repo for GitHub search + history.

---

## 6. Branding Update Strategy

**When:** Update branding **after** defining the archive boundary, but **before** committing the archive manifest. This keeps the update scoped to active files.

**How:**
- Use `rg` or `git grep` for legacy branding terms (case-insensitive).
- Manually verify replacements in active docs.

**Scope:**
- Update **active files only** (v1.0 runtime + v3 planning).
- Leave archived files unchanged unless they are reused later.

**Version control note:**
- Document branding changes in the archive manifest or a short log entry in this doc.

---

## 7. Implementation Roadmap

**Order of operations:**
1. Tag current state (v1.0 + pre-archive).
2. Create archive structure and manifest.
3. Move legacy directories into archive using `git mv`.
4. Update documentation references to new archive paths.
5. Update branding references in active files.
6. Run targeted validation test.

**Timeline:**
- **Day 1:** structure + move + manifest (1–2 hours)
- **Day 1:** branding cleanup (30–60 minutes)
- **Day 1:** verification test + review (30 minutes)

---

## Repository-Specific Plan Applied

**Archive structure (created):**
- `archive/legacy_versions/`
- `archive/artifacts/`
- `archive/packages/`

**Directories to archive:**
- `murphy_analysis/`
- `murphy_backup_extracted/`
- `murphy_complete_all_files/`
- `murphy_complete_final/`
- `murphy_complete_installation/`
- `murphy_complete_system_package/`
- `murphy_complete_with_fixes/`
- `murphy_implementation/`
- `murphy_runtime_analysis/`
- `murphy_system/`
- `murphy_system_documentation_package/`
- `murphy_system_fixed/`
- `murphy_system_v2.0_BUGFIXED_20260130_2114/`
- `murphy_system_v2.0_UI_UPDATED_20260130_1810/`
- `murphy_system_working/`
- `murphy_test_extract/`
- `murphy_ui_fixes_package/`

**Artifacts to archive:**
- `artifacts/`, `backups/`, `generated_images/`, `outputs/`,
  `summarized_conversations/`, `uploaded_files/`

**Packages to archive:**
- `_workspace_murphy_system_runtime.zip`
- `552b9696-2ad5-4da4-86fc-0d6f262b1258.zip`

**Branding updates (active scope):**
- Scan active docs for legacy branding terms (case-insensitive) and update to Inoni LLC / Corey Post.
