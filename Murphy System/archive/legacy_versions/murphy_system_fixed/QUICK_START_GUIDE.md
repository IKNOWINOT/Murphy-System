# Murphy System - Quick Start Guide

## 🚀 Get Started in 3 Minutes

### Access the System
```
https://8080-0e281fd4-a558-4e54-b1ea-6dc0c0ecb8fe.sandbox-service.public.prod.myninja.ai/murphy_complete_v2.html
```

---

## Step 1: Initialize the System (30 seconds)

Type this in the terminal and press Enter:
```
/initialize
```

**Expected Output:**
```
✓ System initialized successfully
  Loaded 5 agents
  Loaded 1 states
```

---

## Step 2: Check System Status (10 seconds)

```
/status
```

**Expected Output:**
```
=== System Status ===
Version: 3.0.0
Components: 8/9 active
  ✓ Monitoring
  ✓ Artifacts
  ✓ Shadow Agents
  ✓ Cooperative Swarm
  ✓ Authentication
  ✓ Database
  ✓ Command System
  ✓ Modules
  ✗ LLM (needs API keys)
```

---

## Step 3: Explore the System

### View Available Commands
```
/help
```

### List Agents
```
/agent list
```

### List States
```
/state list
```

---

## Step 4: Try Out the Panels

### Artifact Panel
Click the "Artifact Panel" button in the sidebar to:
- View generated artifacts
- Search for artifacts
- Generate new artifacts

### Shadow Agent Panel
Click the "Shadow Agent Panel" button to:
- Monitor 5 learning agents
- View observations
- Approve/reject automation proposals

### Monitoring Panel
Click the "Monitoring Panel" button to:
- View system health (100% score)
- Check performance metrics
- See optimization recommendations

---

## Common Terminal Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | System status |
| `/clear` | Clear terminal |
| `/initialize` | Initialize system |
| `/agent list` | List all agents |
| `/state list` | List all states |
| `/state evolve <id>` | Evolve a state |
| `/shadow list` | List shadow agents |
| `/artifact list` | List artifacts |
| `/monitoring health` | Show system health |

---

## Troubleshooting

### Terminal Not Responding?
- **Problem:** Enter key doesn't work
- **Solution:** Click anywhere in the terminal area to focus it

### Connection Errors?
- **Problem:** "Failed to fetch" errors
- **Solution:** Wait 5 seconds, the backend is starting up

### Panel Not Loading?
- **Problem:** Panel shows error messages
- **Solution:** Initialize the system first with `/initialize`

---

## System Features

### 6 Interactive Panels
1. **Librarian Panel** - Intent mapping and search
2. **Plan Review Panel** - Review and approve plans
3. **Document Editor Panel** - Manage living documents
4. **Artifact Panel** - Generate and manage artifacts
5. **Shadow Agent Panel** - Monitor learning agents
6. **Monitoring Panel** - System health and metrics

### Visualizations
- **Agent Graph** - Shows agent relationships (Cytoscape.js)
- **State Tree** - Hierarchical state evolution
- **Process Flow** - Workflow visualization (D3.js)

### Real-Time Updates
- WebSocket connection for live updates
- Automatic UI refresh on data changes
- Live terminal output

---

## Next Steps

1. **Initialize the system** - Type `/initialize`
2. **Explore commands** - Type `/help`
3. **Check status** - Type `/status`
4. **Open panels** - Click panel buttons in sidebar
5. **Try workflows** - Evolve states, create artifacts

---

## System Architecture

```
Frontend (Port 8080)
    ↓ HTTP/WebSocket
Backend (Port 3002)
    ↓
Components:
  • Monitoring System
  • Artifact Generation
  • Shadow Agent Learning
  • Cooperative Swarm
  • Command System
  • Authentication (JWT)
  • Database (SQLite)
  • Module System
```

---

**Ready to go! Open the URL and start exploring.**