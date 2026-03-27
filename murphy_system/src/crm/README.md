# `src/crm` — CRM Module

Contact, deal, pipeline, and activity management — Monday.com CRM feature parity for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The CRM package delivers a complete customer relationship management layer built on Murphy's board primitives. Contacts are typed (lead, customer, partner) and linked to deals that progress through configurable pipeline stages. CRM activities — calls, emails, meetings, and notes — are attached to both contacts and deals, creating a full interaction timeline. The `CRMManager` provides all business logic and the FastAPI router exposes a REST API at `/api/crm`.

## Key Components

| Module | Purpose |
|--------|---------|
| `crm_manager.py` | `CRMManager` — contact, deal, pipeline, and activity CRUD |
| `models.py` | `Contact`, `Deal`, `Pipeline`, `Stage`, `CRMActivity`, `DealStage`, `ActivityType` |
| `api.py` | FastAPI router (`create_crm_router`) for CRM REST endpoints |

## Usage

```python
from crm import CRMManager, ContactType, DealStage

mgr = CRMManager()
contact = mgr.create_contact("Acme Corp", email="sales@acme.com", type=ContactType.LEAD)
pipeline = mgr.create_pipeline("Enterprise Sales")
deal = mgr.create_deal("Acme Enterprise", contact_id=contact.id, pipeline_id=pipeline.id)
mgr.advance_deal(deal.id, stage=DealStage.PROPOSAL)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
