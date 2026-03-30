# Murphy System — Flattening Plan

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Overview

This document outlines the phased plan for flattening and consolidating the
Murphy System directory structure.  The goal is to reduce nesting depth,
eliminate circular imports, and standardise package boundaries so that all
650+ modules can be imported cleanly from a single `src/` root.

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Consolidate duplicate utility modules | ✅ Complete |
| 2 | Flatten deeply nested sub-packages (≤ 2 levels) | ✅ Complete |
| 3 | Unify import paths (remove `src.` prefix duplication) | ✅ Complete |
| 4 | Standardise `__init__.py` exports across all packages | ✅ Complete |
| 5 | Validate zero import failures via automated sweep | ✅ Complete |

## Current State

All five phases are complete.  The import sweep (`python -m pytest tests/ -x`)
confirms zero failures across 319+ source files and 56+ packages.

---

*Murphy System v1.0 — BSL 1.1 — Murphy Collective*
