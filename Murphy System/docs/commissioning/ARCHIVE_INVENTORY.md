# Archive Inventory

**Document ID:** MURPHY-ARC-2026-001  
**Version:** 2.0.0  
**Date:** March 2026  
**Owner:** @doc-lead  
**Phase:** 1 — Environment Cleanup & Assessment  
**Completion:** 100%

---

## Overview

The Murphy System archive has been transferred to a dedicated repository to reduce download size and keep the main repository focused on production code.

**Archive Repository:** [iknowinot/murphy-system-archive](https://github.com/IKNOWINOT/murphy-system-archive)

The archive contains legacy versions, artifacts, and internal documents preserved for historical reference and future v3.0 feature integration.

---

## Archive Contents (in murphy-system-archive)

| Category | Description | Purpose |
|----------|-------------|---------|
| Legacy Versions | Previous Murphy System iterations (v1.0, v2.0 variants) | Historical reference |
| Artifacts | Generated images, outputs, summaries | Snapshot reference |
| Legacy Workspace | Older workspace configurations | Development history |
| Integrated Archive | Legacy integration packages | Merge history |

---

## Transfer Details

The archive was transferred using `scripts/transfer_archive.sh` from the main
Murphy-System repository. To run the transfer (if re-running is needed):

```bash
bash scripts/transfer_archive.sh
```

---

## Recommendations

1. **Do NOT reference archive in new code** — Use active `src/` modules only
2. **Do NOT run archived test files** — They may reference deprecated APIs
3. **Archive is permanently preserved** in the dedicated repository

---

**© 2026 Inoni Limited Liability Company. All rights reserved.**
