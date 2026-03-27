# Murphy System API Documentation

> **Split from:** `API_ROUTES.md` (1,252 lines)  
> **Date:** 2026-03-27  
> **Addresses:** D-005 (API routes modularization)

---

## API Categories

| Category | File | Endpoints | Description |
|----------|------|-----------|-------------|
| Core | [CORE.md](./CORE.md) | /api/health, /api/status | System health and status |
| Auth | [AUTH.md](./AUTH.md) | /api/auth/* | Authentication and sessions |
| LLM | [LLM.md](./LLM.md) | /api/llm/*, /api/chat | AI/LLM integration |
| Workflows | [WORKFLOWS.md](./WORKFLOWS.md) | /api/workflows/* | Workflow automation |
| Agents | [AGENTS.md](./AGENTS.md) | /api/agents/* | Agent management |
| Modules | [MODULES.md](./MODULES.md) | /api/modules/* | Module system |
| Trading | [TRADING.md](./TRADING.md) | /api/trading/* | Trading system |
| Games | [GAMES.md](./GAMES.md) | /api/game/* | Game creation |
| Founder | [FOUNDER.md](./FOUNDER.md) | /api/founder/* | Founder tools |

---

## Quick Reference

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Authentication
```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "..."}'

# Use token
curl http://localhost:8000/api/status \
  -H "Authorization: Bearer <token>"
```

### Chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Murphy"}'
```

---

## OpenAPI Schema

The full OpenAPI schema is available at:
- `/api/openapi.json` - JSON format
- `/api/docs` - Swagger UI
- `/api/redoc` - ReDoc UI

---

## Original File

The original `API_ROUTES.md` is preserved at the repository root for backward compatibility.
