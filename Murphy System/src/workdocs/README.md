# `src/workdocs` — Collaborative Documents

Block-based collaborative document authoring with versioning and sharing for Murphy workspaces.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The workdocs package provides a Monday.com-style collaborative document layer where rich documents are owned by users, linked to boards, and composed of typed `Block` objects. Eleven block types are supported — text, heading, bullet/numbered lists, checklists, code, quote, divider, image, table, and board embed — enabling everything from sprint notes to technical runbooks. Snapshot-based versioning captures the full document state at each save, and a collaborator model with permission checks ensures only authorised users can edit. A FastAPI router exposes all operations at `/api/workdocs`.

## Key Components

| Module | Purpose |
|--------|---------|
| `doc_manager.py` | `DocManager` — document and block CRUD, versioning, and collaborator management |
| `models.py` | `Document`, `Block`, `BlockType`, `DocVersion`, `DocPermission`, `DocStatus` |
| `api.py` | FastAPI router (`create_workdocs_router`) at `/api/workdocs` |

## Usage

```python
from workdocs import DocManager, BlockType

mgr = DocManager()
doc = mgr.create_document("Sprint Notes", owner_id="u1")
mgr.add_block(doc.id, BlockType.HEADING, "Sprint Goal")
mgr.add_block(doc.id, BlockType.TEXT, "Ship auth service by Friday.")
mgr.create_version(doc.id, editor_id="u1", summary="Initial draft")
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
