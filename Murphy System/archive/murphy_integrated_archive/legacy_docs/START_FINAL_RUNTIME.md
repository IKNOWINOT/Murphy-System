# Murphy Final Runtime - Quick Start Guide

## What Is This?

**murphy_final_runtime.py** is the unified orchestrator that wires together ALL Murphy systems:

- ✅ Agent Swarms (TrueSwarmSystem, DomainSwarms)
- ✅ MFGC Controller (orchestration)
- ✅ Confidence Engine (validation)
- ✅ Execution Engine (task execution)
- ✅ Learning Engine (improvement)
- ✅ Conversation Manager (dialogue)
- ✅ Telemetry Learning (data capture)
- ✅ Form Intake (structured input)
- ✅ Session Management (user sessions)
- ✅ Repository Management (automation projects)

## Quick Start

### 1. Install Dependencies
```bash
cd murphy_integrated
pip install flask flask-cors flask-socketio numpy
```

### 2. Start the Runtime
```bash
python murphy_final_runtime.py
```

Server starts on: `http://localhost:5000`

### 3. Check Status
```bash
curl http://localhost:5000/api/status
```

## API Endpoints

### System Status
- `GET /api/status` - Get system status and available modules

### Session Management
- `POST /api/session/create` - Create new session
  ```json
  {"user_id": "user123", "repository_id": "repo456"}
  ```
- `GET /api/session/<session_id>` - Get session details
- `POST /api/session/<session_id>/end` - End session

### Repository Management
- `POST /api/repository/create` - Create automation repository
  ```json
  {"user_id": "user123", "name": "Blog Automation", "type": "publishing"}
  ```
- `GET /api/repository/list?user_id=user123` - List user repositories

### Conversation & Input Processing
- `POST /api/conversation/message` - Process user message (MAIN ENTRY POINT)
  ```json
  {
    "message": "Automate my blog publishing",
    "session_id": "session_123"
  }
  ```
- `GET /api/conversation/thread/<session_id>` - Get conversation history

### Swarm System
- `POST /api/swarm/spawn` - Spawn agent swarm
  ```json
  {"mode": "collaborative", "domain": "software_engineering"}
  ```
- `GET /api/swarm/agents?session_id=session_123` - List active agents

### Form Intake
- `POST /api/forms/submit` - Submit structured form
  ```json
  {
    "form_type": "plan_generation",
    "form_data": {"description": "...", "domain": "..."}
  }
  ```

### Confidence Engine
- `POST /api/confidence/calculate` - Calculate confidence score
- `POST /api/confidence/murphy-gate` - Check Murphy gate

### Telemetry & Learning
- `GET /api/telemetry/metrics` - Get telemetry metrics
- `GET /api/learning/patterns` - Get learned patterns

## Complete User Flow Example

### 1. Create Repository
```bash
curl -X POST http://localhost:5000/api/repository/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "name": "Blog Automation", "type": "publishing"}'
```

Response: `{"success": true, "repository_id": "repo_1234567890"}`

### 2. Create Session
```bash
curl -X POST http://localhost:5000/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "repository_id": "repo_1234567890"}'
```

Response: `{"success": true, "session_id": "session_1234567890"}`

### 3. Send Message (Main Flow)
```bash
curl -X POST http://localhost:5000/api/conversation/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Automate my blog publishing to WordPress and Medium",
    "session_id": "session_1234567890"
  }'
```

Response:
```json
{
  "success": true,
  "intent": "automation_request",
  "confidence": {"G": 0.85, "D": 0.90, "H": 0.95},
  "gate_result": {"action": "PROCEED", "confidence": 0.90},
  "execution": {"status": "completed", "tasks": [...]},
  "agents": ["agent_1", "agent_2", "agent_3"]
}
```

### 4. Check Conversation History
```bash
curl http://localhost:5000/api/conversation/thread/session_1234567890
```

### 5. View Active Agents
```bash
curl http://localhost:5000/api/swarm/agents?session_id=session_1234567890
```

### 6. Get Learning Patterns
```bash
curl http://localhost:5000/api/learning/patterns
```

## What Happens Behind the Scenes

When you send a message via `/api/conversation/message`:

1. **Message Pipeline** - Processes and classifies intent
2. **Domain Detection** - Determines domain (software, business, etc.)
3. **Swarm Spawning** - Creates appropriate agent swarm
4. **MFGC Orchestration** - Coordinates agent actions
5. **Agent Collaboration** - Agents work together in workspace
6. **Confidence Validation** - Calculates confidence scores
7. **Murphy Gate** - Validates against thresholds
8. **Execution** - Runs approved actions
9. **Telemetry Capture** - Records execution data
10. **Learning** - Improves from execution

## System Architecture

```
User Input
  ↓
murphy_final_runtime.py (RuntimeOrchestrator)
  ↓
┌─────────────────────────────────────────┐
│  Message Pipeline → Intent Classifier   │
│  Domain Detector → Swarm Spawner        │
│  MFGC Controller → Agent Coordination   │
│  Confidence Engine → Murphy Gate        │
│  Execution Engine → Task Execution      │
│  Telemetry → Learning → Improvement     │
└─────────────────────────────────────────┘
  ↓
Response to User
```

## Integration with murphy_ui_final.html

Update the UI to use this runtime:

```javascript
const API_BASE = 'http://localhost:5000';

// Create session on load
fetch(`${API_BASE}/api/session/create`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({user_id: 'user123', repository_id: 'repo123'})
})
.then(r => r.json())
.then(data => {
  sessionId = data.session_id;
});

// Send messages
function sendMessage(message) {
  fetch(`${API_BASE}/api/conversation/message`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: message, session_id: sessionId})
  })
  .then(r => r.json())
  .then(data => {
    console.log('Response:', data);
    // Display agents, confidence, execution results
  });
}
```

## Next Steps

1. ✅ Runtime created and tested
2. ⏳ Update murphy_ui_final.html to use this runtime
3. ⏳ Add remaining endpoints (agent communication, etc.)
4. ⏳ Build universal question framework for onboarding
5. ⏳ Test complete end-to-end flows

## Troubleshooting

### Import Errors
If you see import errors, install missing dependencies:
```bash
pip install numpy flask flask-cors flask-socketio pydantic
```

### Port Already in Use
Change the port in murphy_final_runtime.py:
```python
port = int(os.environ.get('PORT', 5001))  # Change 5000 to 5001
```

### System Not Available
Check `/api/status` to see which systems initialized successfully.