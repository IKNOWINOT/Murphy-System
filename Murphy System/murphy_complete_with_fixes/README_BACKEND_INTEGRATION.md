# Murphy System - Backend Integrated Runtime

## 🎯 What This Is

This is a **fully integrated Murphy System** where the frontend interface is wired directly to the actual Murphy System backend runtime. Every click, every interaction, every state change affects real backend logic using the actual Murphy System components.

## 🚀 Quick Start

### Option 1: Standalone Frontend (No Backend)
Simply open `murphy_backend_integrated.html` in your browser. This runs with simulated backend logic in JavaScript.

### Option 2: Full Backend Integration (Recommended)

1. **Install Dependencies:**
   ```bash
   ./start_murphy_system.sh
   ```
   Or manually:
   ```bash
   pip3 install flask flask-cors flask-socketio python-socketio
   ```

2. **Start Backend Server:**
   ```bash
   python3 murphy_backend_server.py
   ```
   Server will start on `http://localhost:5000`

3. **Open Frontend:**
   Open `murphy_backend_integrated.html` in your browser

4. **Initialize System:**
   Click the "INITIALIZE" button to start the Murphy System

## 📁 Files Overview

### Frontend
- **`murphy_backend_integrated.html`** - Main interface with terminal, state tree, LLM controls, metrics
  - Terminal-style interface showing all operations
  - Clickable state evolution tree
  - LLM controls (Groq, Aristotle, Onboard)
  - Real-time metrics and visualizations
  - Modal dialogs for state details
  - Command input for direct control

### Backend
- **`murphy_backend_server.py`** - Python Flask server integrating Murphy System runtime
  - REST API endpoints for all operations
  - WebSocket support for real-time updates
  - Murphy System component integration
  - State management and persistence
  - Swarm execution and artifact generation

### Documentation
- **`MURPHY_INTEGRATION_GUIDE.md`** - Comprehensive integration guide
  - Architecture overview
  - Integration points explained
  - API documentation
  - WebSocket events
  - Usage examples

### Murphy System Runtime
- **`murphy_system/`** - Complete Murphy System source code (424+ modules)
  - `src/mfgc_core.py` - 7-phase MFGC system
  - `src/advanced_swarm_system.py` - Swarm generation
  - `src/constraint_system.py` - Constraint management
  - `src/gate_builder.py` - Safety gates
  - `src/organization_chart_system.py` - Org structure
  - `src/llm_integration.py` - LLM providers

## 🎮 How to Use

### 1. Initialize the System
Click **INITIALIZE** button or type `help` for commands.

The system will:
- Activate LLMs (Groq, Aristotle, Onboard)
- Create root state
- Generate initial constraints (Budget, Timeline, Security)
- Activate safety gates
- Launch swarms for analysis
- Create 5 child states

### 2. Explore States
Click any state in the **State Evolution Tree** (left sidebar) to:
- View state details
- See associated artifacts
- Check active gates
- View child states
- **EVOLVE** - Create child state with enhanced capabilities
- **REGENERATE** - Regenerate with new confidence
- **ROLLBACK** - Return to parent state

### 3. Watch Swarms Work
In the **Active Swarms** section (right sidebar):
- See swarm type (CREATIVE, ANALYTICAL, HYBRID)
- Watch progress bars
- See artifacts generated when complete

### 4. Monitor System
The **System Metrics** section shows:
- States Generated
- Artifacts Created
- Gates Active
- Confidence Level
- Murphy Index

### 5. Use Commands
Type commands in the input area:
- `help` - Show available commands
- `status` - Show system status
- `advance` - Advance to next MFGC phase
- `evolve STATE-0` - Evolve a specific state
- `regenerate STATE-0` - Regenerate a state
- `create-constraint budget "New Budget" "$200,000"` - Create constraint

### 6. Control LLMs
Click LLM indicators in the header to toggle:
- **GROQ** - Fast inference
- **ARISTOTLE** - Reasoning and logic
- **ONBOARD** - Local LLM (Ollama)

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   Frontend (murphy_backend_         │
│   integrated.html)                  │
│   - Terminal UI                     │
│   - State Tree                      │
│   - LLM Controls                    │
│   - Real-time Updates               │
└─────────────────────────────────────┘
              ↕ REST + WebSocket
┌─────────────────────────────────────┐
│   Backend (murphy_backend_          │
│   server.py)                        │
│   - Flask REST API                  │
│   - WebSocket Events                │
│   - Murphy Runtime Wrapper          │
└─────────────────────────────────────┘
              ↕
┌─────────────────────────────────────┐
│   Murphy System Runtime             │
│   (murphy_system/src/)              │
│   - MFGC Core                       │
│   - Swarm System                    │
│   - Constraint System               │
│   - Gate Builder                    │
│   - LLM Integration                 │
└─────────────────────────────────────┘
```

## 🔑 Key Features

### 1. Real Murphy System Integration
- Uses actual MFGC 7-phase system (EXPAND → TYPE → ENUMERATE → CONSTRAIN → COLLAPSE → BIND → EXECUTE)
- Real swarm generation (Creative, Analytical, Hybrid, Adversarial)
- Actual gate building from Murphy's gate library
- Real constraint management system

### 2. Interactive State Evolution
- Click states to see details
- Evolve states to create children
- Regenerate for different approaches
- Rollback to previous states
- Full parent-child relationship tracking

### 3. Real-time Updates
- WebSocket for instant updates
- See swarm progress in real-time
- Watch artifacts being generated
- Monitor system metrics live

### 4. Terminal-Driven Interface
- All operations visible in terminal
- Color-coded tags (SYSTEM, LLM, SWARM, GATE, ARTIFACT, PHASE, CONSTRAINT)
- Command input for direct control
- murphy> prompt for commands

### 5. Clickable Everything
- Every state is clickable
- Every artifact is clickable
- Every swarm shows progress
- Every gate is visible
- Every constraint is tracked

## 📊 MFGC Phases

The system progresses through 7 phases:

1. **EXPAND** (threshold: 0.3) - Broad exploration, divergent thinking
2. **TYPE** (threshold: 0.5) - Categorize and classify
3. **ENUMERATE** (threshold: 0.6) - List all possibilities
4. **CONSTRAIN** (threshold: 0.65) - Apply constraints
5. **COLLAPSE** (threshold: 0.7) - Narrow down options
6. **BIND** (threshold: 0.75) - Commit to decisions
7. **EXECUTE** (threshold: 0.85) - Final execution

Each phase requires sufficient confidence to advance.

## 🤖 Swarm Types

- **CREATIVE** - Divergent thinking, novel solutions
- **ANALYTICAL** - Systematic, logical approaches
- **HYBRID** - Combines creative + analytical
- **ADVERSARIAL** - Red team, find weaknesses
- **SYNTHESIS** - Combine multiple solutions
- **OPTIMIZATION** - Refine and improve

## 🛡️ Safety Gates

10 built-in safety gates:
- Data Loss Prevention
- Security Gate
- Input Validation
- Load Balancing
- Data Integrity
- Authorization
- Performance
- Compliance
- Resource Management
- Dependency Checking

## 📋 Constraints

8 constraint types:
- BUDGET - Financial constraints
- REGULATORY - Legal requirements
- ARCHITECTURAL - System design constraints
- PERFORMANCE - Speed/efficiency requirements
- SECURITY - Security requirements
- TIME - Timeline constraints
- RESOURCE - Resource availability
- BUSINESS - Business rules

## 🔌 API Endpoints

### System
- `POST /api/initialize` - Initialize system
- `GET /api/status` - Get status

### States
- `GET /api/states` - Get all states
- `GET /api/states/{id}` - Get specific state
- `POST /api/states/{id}/evolve` - Evolve state
- `POST /api/states/{id}/regenerate` - Regenerate state

### LLMs
- `POST /api/llm/{name}/toggle` - Toggle LLM

### Phases
- `POST /api/phase/advance` - Advance phase

### Constraints
- `GET /api/constraints` - Get constraints
- `POST /api/constraints` - Create constraint

### Artifacts
- `GET /api/artifacts` - Get artifacts

### Gates
- `GET /api/gates` - Get gates

### Swarms
- `GET /api/swarms` - Get swarms

## 🎨 UI Components

### Header
- Title: "MURPHY SYSTEM - BACKEND INTEGRATED RUNTIME"
- LLM Controls: GROQ, ARISTOTLE, ONBOARD (clickable)

### Left Sidebar - State Evolution Tree
- Hierarchical state tree
- Color-coded by depth
- Shows confidence for each state
- Click to open details modal

### Center - Terminal
- Color-coded output
- murphy> prompt
- Command input
- INITIALIZE and EXECUTE buttons

### Right Sidebar
- **MFGC Phases** - Visual phase indicator
- **System Metrics** - Live metrics
- **Active Swarms** - Progress bars
- **Generated Artifacts** - Clickable list
- **Active Gates** - Safety gates
- **Constraints** - System constraints

### Modal Dialog
- State information
- Associated artifacts
- Active gates
- Child states
- Actions: EVOLVE, REGENERATE, ROLLBACK, CLOSE

## 🎯 Use Cases

### 1. System Design
- Initialize with requirements
- Watch system generate architecture
- Evolve states for different approaches
- See constraints applied
- Review generated artifacts

### 2. Learning Murphy System
- See MFGC phases in action
- Watch swarms generate solutions
- Understand gate system
- Explore constraint management

### 3. Interactive Exploration
- Click states to explore
- Evolve to see possibilities
- Regenerate for alternatives
- Rollback to previous states

### 4. Development
- Use as template for Murphy integration
- Extend with custom swarms
- Add custom gates
- Integrate with your systems

## 🔧 Customization

### Add Custom Swarm Type
In `murphy_backend_server.py`:
```python
SWARM_TYPES = {
    'custom': 'custom',
    # ... existing types
}
```

### Add Custom Gate
In `murphy_backend_server.py`:
```python
gate_templates = {
    'custom_gate': {
        'name': 'Custom Gate',
        'severity': 0.8
    }
}
```

### Add Custom Constraint Type
In `murphy_backend_server.py`:
```python
CONSTRAINT_TYPES = {
    'CUSTOM': 'custom',
    # ... existing types
}
```

## 📚 Further Reading

- **MURPHY_INTEGRATION_GUIDE.md** - Detailed integration guide
- **murphy_system/README.md** - Murphy System documentation
- **murphy_system/src/** - Source code with inline documentation

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Install dependencies
pip3 install flask flask-cors flask-socketio

# Check port availability
lsof -i :5000
```

### Frontend not connecting
- Verify backend is running on port 5000
- Check browser console for errors
- Verify CORS settings

### Swarms not progressing
- Check WebSocket connection
- Verify asyncio is working
- Check browser console

## 🎓 Learning Path

1. **Start Simple** - Open standalone HTML, click INITIALIZE
2. **Explore States** - Click states, see details
3. **Try Commands** - Use terminal commands
4. **Evolve States** - Create child states
5. **Watch Swarms** - See artifacts generated
6. **Start Backend** - Run full integration
7. **Customize** - Add your own logic

## 🚀 Next Steps

1. Add API keys for real LLM inference
2. Connect to database for persistence
3. Implement authentication
4. Add more swarm types
5. Create custom gates
6. Integrate with your systems

## 📝 License

Part of the Murphy System project by NinjaTech AI.

## 🤝 Contributing

This is a demonstration of Murphy System integration. For the full Murphy System, see the murphy_system/ directory.

---

**Ready to explore?** Click INITIALIZE and watch the Murphy System come to life! 🚀