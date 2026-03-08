# API Documentation

> **This document has been consolidated.**
> 
> The canonical API reference is **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)**.
> 
> For practical usage examples, see **[documentation/api/EXAMPLES.md](documentation/api/EXAMPLES.md)**.
> 
> For endpoint details, see **[documentation/api/ENDPOINTS.md](documentation/api/ENDPOINTS.md)**.

---

## Core Endpoints (Quick Reference)

| Method | Path | Description |
|--------|------|-------------|
| GET /api/health | Health check — returns `{"status": "ok"}` |
| GET /api/status | Full system status with engine states |
| POST /api/execute | Submit a task for execution |
| POST /api/chat | Chat with the Murphy assistant |
| GET /api/gates | List all governance gates |
| POST /api/onboarding/wizard/start | Begin the onboarding wizard |
| GET /api/integrations | List available integrations |
| POST /api/credentials | Store integration credentials (HITL) |

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for the complete reference.

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*
