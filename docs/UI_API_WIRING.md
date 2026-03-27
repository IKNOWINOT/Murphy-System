# Murphy System UI → API Wiring Documentation

> **Created:** 2026-03-27  
> **Addresses:** B-007 (UI completion), B-012 (hardcoded localhost)

---

## Overview

All 14 primary web interfaces are wired to the Murphy API. The wiring uses
`static/murphy_config.js` for dynamic API URL detection.

---

## UI Interfaces and Their API Endpoints

| UI | File | Primary API Endpoints | Status |
|----|------|----------------------|--------|
| Landing | `murphy_landing_page.html` | `/api/health`, `/api/status` | ✅ Wired |
| Terminal | `terminal_unified.html` | `/api/chat`, `/api/execute` | ✅ Wired |
| Dashboard | `murphy_ui_integrated.html` | `/api/status`, `/api/sessions` | ✅ Wired |
| Workspace | `workspace.html` | `/api/workflows`, `/api/tasks` | ✅ Wired |
| Login | `login.html` | `/api/auth/login` | ✅ Wired |
| Signup | `signup.html` | `/api/auth/register` | ✅ Wired |
| Pricing | `pricing.html` | `/api/tiers`, `/api/subscribe` | ✅ Wired |
| Admin | `admin_panel.html` | `/api/admin/*` | ✅ Wired |
| Compliance | `compliance_dashboard.html` | `/api/compliance/*` | ✅ Wired |
| Trading | `trading_dashboard.html` | `/api/trading/*` | ✅ Wired |
| Game Creation | `game_creation.html` | `/api/game/*` | ✅ Wired |
| Calendar | `calendar.html` | `/api/calendar/*` | ✅ Wired |
| Community | `community_forum.html` | `/api/community/*` | ✅ Wired |
| Grants | `grant_wizard.html` | `/api/grants/*` | ✅ Wired |

---

## API URL Configuration

### Method 1: Murphy Config (Recommended)

Include the config script in your HTML:

```html
<script src="/static/murphy_config.js"></script>
<script>
    // Use the global MURPHY_API_URL
    fetch(MURPHY_API_URL + '/api/health')
        .then(r => r.json())
        .then(console.log);
    
    // Or use the MurphyConfig helper
    MurphyConfig.fetch('/api/status')
        .then(r => r.json())
        .then(console.log);
</script>
```

### Method 2: Meta Tag

Set API URL via meta tag (server-rendered):

```html
<meta name="murphy-api-url" content="https://api.murphy.systems">
```

### Method 3: Server-Side Injection

Inject config in template:

```html
<script>
    window.MURPHY_CONFIG = {
        apiUrl: "{{ api_url }}",
        wsUrl: "{{ ws_url }}"
    };
</script>
<script src="/static/murphy_config.js"></script>
```

---

## Detection Priority

The `murphy_config.js` script detects the API URL in this order:

1. `window.MURPHY_CONFIG.apiUrl` (server-injected)
2. `<meta name="murphy-api-url">` content
3. Same-origin (production: use current host)
4. Fallback: `http://localhost:8000` (development)

---

## WebSocket Endpoints

Real-time features use WebSocket connections:

| Feature | Endpoint | Protocol |
|---------|----------|----------|
| Chat | `/ws/chat` | WebSocket |
| Notifications | `/ws/notifications` | WebSocket |
| Terminal | `/ws/terminal` | WebSocket |
| Trading | `/ws/trading` | WebSocket |

Access via:
```javascript
const ws = new WebSocket(MURPHY_WS_URL + '/chat');
```

---

## Testing Wiring

```bash
# Test API is accessible
curl http://localhost:8000/api/health

# Test from browser console
fetch(MURPHY_API_URL + '/api/health').then(r => r.json()).then(console.log)
```
