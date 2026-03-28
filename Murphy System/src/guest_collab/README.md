# `src/guest_collab` — Guest Collaboration

External collaboration via guest invitations, shareable links, client portals, and intake forms.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The guest collaboration package allows organisations to invite external stakeholders into scoped views of Murphy workspaces without granting full system access. Guests receive permission-scoped invitations (view or edit) and can be given access to specific boards. Shareable links provide password-optioned read-only or edit access to boards without requiring a login. Client portals deliver branded views for customer-facing delivery tracking. External forms convert public form submissions directly into board items for seamless intake.

## Key Components

| Module | Purpose |
|--------|---------|
| `guest_manager.py` | `GuestManager` — invite guests, manage links, portals, and forms |
| `models.py` | `GuestUser`, `ShareableLink`, `ClientPortal`, `ExternalForm`, `GuestPermission` |
| `api.py` | FastAPI router (`create_guest_router`) for all guest endpoints |

## Usage

```python
from guest_collab import GuestManager, GuestPermission

mgr = GuestManager()
guest = mgr.invite_guest("client@example.com", permission=GuestPermission.VIEW,
                         board_ids=["board-1"])
link = mgr.create_shareable_link("board-1", created_by="u1", password="secret")
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
