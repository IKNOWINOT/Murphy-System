# `src/service_module` — Service Module

IT service management with a service catalog, SLA tracking, intelligent ticket routing, and knowledge base — Monday.com service desk parity.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The service module delivers a complete IT service management (ITSM) layer within the Murphy workspace platform. A typed service catalog allows teams to define request items with associated forms; tickets created from catalog items inherit SLA policies with automatic escalation. `ServiceManager` supports three routing strategies — round-robin, load-based, and skill-based — for auto-assigning tickets to available agents. A built-in knowledge base lets teams publish resolution articles, and CSAT collection closes the feedback loop after ticket resolution.

## Key Components

| Module | Purpose |
|--------|---------|
| `service_manager.py` | `ServiceManager` — catalog, ticket, routing, KB, and CSAT management |
| `models.py` | `ServiceCatalogItem`, `Ticket`, `TicketPriority`, `TicketStatus`, `SLAPolicy`, `KBArticle`, `CSATResponse` |
| `api.py` | FastAPI router (`create_service_router`) at `/api/service` |

## Usage

```python
from service_module import ServiceManager, TicketPriority

mgr = ServiceManager()
item = mgr.create_catalog_item("VPN Access Request", category="IT")
ticket = mgr.create_ticket("Need VPN access", requester_id="u1", priority=TicketPriority.MEDIUM)
mgr.register_agent("agent-01")
mgr.auto_route(ticket.id)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
