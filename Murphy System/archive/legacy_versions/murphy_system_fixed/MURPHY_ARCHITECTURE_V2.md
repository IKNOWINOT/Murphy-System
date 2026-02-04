# Murphy System - Architecture & Implementation Guide v2.0

## Executive Summary

The Murphy System is a transparent, agentic business operating system that provides real-time visibility into autonomous agent operations through a terminal-driven interface with interactive visualizations. This document serves as the single source of truth for system architecture, component definitions, and implementation patterns.

### Core Philosophy
- **Transparency First**: Every operation is visible and understandable
- **Interactive Control**: Users can observe, interact with, and control system behavior
- **Evolutionary Architecture**: Components evolve through state transitions
- **Swarm Intelligence**: Multiple agents work in parallel using different approaches
- **Living Documents**: Knowledge evolves from fuzzy to solid through magnification and simplification

---

## 1. System Architecture Overview

### 1.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         MURPHY SYSTEM                            │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────┐  │
│  │   Frontend UI    │────│   Backend API    │────│    LLMs    │  │
│  │   (Port 9090)    │    │   (Port 6666)    │    │            │  │
│  │                  │    │                  │    │ • Groq     │  │
│  │ • Terminal       │    │ • Flask Server   │    │ • Aristotle│  │
│  │ • Visualization  │────│ • WebSocket      │    │ • Onboard  │  │
│  │ • Interactive    │    │ • State Mgmt     │    │            │  │
│  │ • State Tree     │    │ • Swarm Engine   │    └───────────┘  │
│  └──────────────────┘    └──────────────────┘                    │
│                                  │                               │
│                          ┌───────▼────────┐                      │
│                          │ Murphy Runtime  │                      │
│                          │                │                      │
│                          │ • MFGC Core    │                      │
│                          │ • Domain Engine│                      │
│                          │ • Gate Builder │                      │
│                          │ • Org Chart    │                      │
│                          └────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Definitions (Complete)

### 2.1 Agents
**Definition**: Autonomous entities that execute specific tasks within assigned domains.

**Properties**:
- `id`: Unique identifier
- `name`: Display name
- `type`: Agent type (Sales, Engineering, Financial, etc.)
- `status`: Current state (active, idle, error, paused)
- `domain`: Assigned domain
- `task`: Current task being executed
- `progress`: Task completion percentage (0-100)
- `confidence`: Confidence level (0.00-1.00)

**Visual**: Animated nodes with status indicators and progress bars
**Interaction**: Click to view details, override, pause/resume

### 2.2 Components
**Definition**: Modular building blocks (LLM Router, Domain Engine, Gate Builder, Swarm Generator).

**Properties**:
- `id`: Unique identifier
- `name`: Component name
- `type`: Component type (router, engine, builder, generator)
- `status`: Operational status (active, inactive, error)
- `health`: Health score (0-100)
- `recent_ops`: List of recent operations

**Visual**: Static panels with active indicators and health meters
**Interaction**: Click to view parameters, health status, recent logs

### 2.3 Gates
**Definition**: Validation checkpoints ensuring outputs meet standards.

**Properties**:
- `id`: Unique identifier
- `name`: Gate name
- `type`: Gate type (regulatory, security, business, quality)
- `criteria`: Validation criteria
- `status`: Current status (pass, fail, pending)
- `results`: Validation results

**Visual**: Gateway symbols (🚧) that light up green/red
**Interaction**: Click to view criteria, results, override permissions

### 2.4 Systems
**Definition**: Complete operational workflows (Contract Generation, Product Development).

**Properties**:
- `id`: Unique identifier
- `name`: System name
- `description`: System purpose and scope
- `status`: Current state (running, paused, completed, error)
- `stages`: List of process stages
- `current_stage`: Currently active stage
- `metrics`: Performance metrics

**Visual**: Flowchart diagrams showing process stages
**Interaction**: Pause/resume, modify parameters, inject manual steps

### 2.5 States
**Definition**: Snapshot conditions of system components at a point in time.

**Properties**:
- `id`: Unique identifier
- `parent_id`: Parent state ID (for hierarchy)
- `type`: State type (document, gate, artifact, swarm, system)
- `label`: Display label
- `description`: State description
- `confidence`: Confidence level (0.00-1.00)
- `timestamp`: Creation timestamp
- `children`: List of child state IDs
- `metadata`: Additional state information

**Visual**: State tree with parent-child relationships and icons
**Interaction**: Evolve, regenerate, rollback, view details

### 2.6 Deterministic Systems
**Definition**: Processes with predictable, repeatable outcomes (Aristotle API, temp 0.1).

**Properties**: Inherits from System, plus deterministic rules and validation logs
**Visual**: Blue-colored components with lock icons
**Interaction**: View rules, input/output mappings, validation logs

### 2.7 Verified Systems
**Definition**: Systems that have passed all validation gates and are approved for production.

**Properties**: Inherits from System, plus certification history and approval chain
**Visual**: Gold badges or checkmarks indicating certified status
**Interaction**: View certification history, gate results, approval chain

### 2.8 Generated Systems
**Definition**: Systems created dynamically by the Murphy runtime based on requirements.

**Properties**: Inherits from System, plus generation metadata and parent requirements
**Visual**: Dashed outlines showing AI-generated nature
**Interaction**: Review generation process, modify logic, regenerate

---

## 3. Backend Architecture Enhancement Plan

### 3.1 WebSocket Integration
**Purpose**: Real-time data streaming to frontend

**Implementation**:
```python
# Add Flask-SocketIO to backend
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'connected': True})

def broadcast_agent_update(agents, connections):
    socketio.emit('agent_update', {
        'agents': agents,
        'connections': connections,
        'timestamp': datetime.now().isoformat()
    })
```

### 3.2 Agent Tracking System
**Purpose**: Track and manage autonomous agents

**Data Structure**:
```python
agents = {}  # Dictionary of Agent objects

class Agent:
    def __init__(self, id, name, type, domain):
        self.id = id
        self.name = name
        self.type = type
        self.domain = domain
        self.status = "idle"
        self.current_task = None
        self.progress = 0
        self.confidence = 0.0
        self.recent_ops = []
        self.config = {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'domain': self.domain,
            'status': self.status,
            'current_task': self.current_task,
            'progress': self.progress,
            'confidence': self.confidence,
            'recent_ops': self.recent_ops,
            'config': self.config
        }
```

### 3.3 State Management API
**Purpose**: Manage state evolution and hierarchy

**Endpoints**:
- GET /api/states - Get all states
- GET /api/states/{state_id} - Get specific state
- POST /api/states/{state_id}/evolve - Evolve state into children
- POST /api/states/{state_id}/regenerate - Regenerate state
- POST /api/states/{state_id}/rollback - Rollback to parent

### 3.4 Real-time Broadcast Functions
**Purpose**: Send updates to connected clients

**Functions**:
- broadcast_agent_update(agents, connections)
- broadcast_state_update(states)
- broadcast_process_update(process)
- broadcast_gate_result(gate, result)

---

## 4. Frontend Architecture Enhancement Plan

### 4.1 Visualization Infrastructure

**Libraries to Add**:
- D3.js v7 - For process flow visualization
- Cytoscape.js v3.26 - For agent graph visualization

**HTML Structure**:
```html
<div id="visualization-container" class="visualization-container">
    <div id="agent-graph" class="graph-container"></div>
    <div id="process-flow" class="flow-container"></div>
</div>
```

**CSS Styling**:
```css
.visualization-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    height: 400px;
    margin-top: 20px;
}

.graph-container, .flow-container {
    background: rgba(0, 20, 40, 0.8);
    border: 1px solid #00ff41;
    border-radius: 5px;
    position: relative;
    overflow: hidden;
}
```

### 4.2 Agent Graph (Cytoscape.js)

**Initialization**:
```javascript
let agentGraph = cytoscape({
    container: document.getElementById('agent-graph'),
    style: [
        {
            selector: 'node',
            style: {
                'background-color': '#00ff41',
                'label': 'data(label)',
                'color': '#000',
                'text-valign': 'center',
                'text-halign': 'center',
                'font-size': '12px',
                'width': '60px',
                'height': '60px'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': '#00ff41',
                'target-arrow-color': '#00ff41',
                'target-arrow-shape': 'triangle'
            }
        }
    ]
});
```

**Update Function**:
```javascript
function updateAgentGraph(data) {
    agentGraph.json({
        nodes: data.agents.map(agent => ({
            data: { 
                id: agent.id, 
                label: agent.name,
                status: agent.status
            }
        })),
        edges: data.connections
    });
}
```

### 4.3 Process Flow (D3.js)

**Initialization**:
```javascript
const processFlowSvg = d3.select("#process-flow")
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%");
```

**Render Function**:
```javascript
function renderProcessFlow(data) {
    // Clear existing content
    processFlowSvg.selectAll("*").remove();
    
    // Render stages
    const stages = processFlowSvg.selectAll(".stage")
        .data(data.stages)
        .enter()
        .append("g")
        .attr("class", "stage")
        .attr("transform", (d, i) => `translate(${50 + i * 150}, 50)`);
    
    // Add stage boxes
    stages.append("rect")
        .attr("width", 120)
        .attr("height", 60)
        .attr("rx", 5)
        .attr("fill", d => d.status === 'completed' ? '#00ff41' : 
                       d.status === 'active' ? '#ffaa00' : '#333');
    
    // Add stage labels
    stages.append("text")
        .attr("x", 60)
        .attr("y", 35)
        .attr("text-anchor", "middle")
        .attr("fill", "#fff")
        .text(d => d.name);
}
```

### 4.4 State Tree Implementation

**HTML Structure**:
```html
<div id="state-tree" class="state-tree-container">
    <div class="tree-title">🌳 STATE EVOLUTION</div>
    <div id="tree-content" class="tree-content"></div>
</div>
```

**Render Function**:
```javascript
function renderStateTree(states) {
    const treeContent = document.getElementById('tree-content');
    treeContent.innerHTML = renderTreeNodes(states, null);
    
    // Add click handlers
    document.querySelectorAll('.state-node').forEach(node => {
        node.addEventListener('click', function() {
            const stateId = this.dataset.stateId;
            showStateDetails(stateId);
        });
    });
}

function renderTreeNodes(states, parentId) {
    const childStates = states.filter(s => s.parent_id === parentId);
    
    if (childStates.length === 0) return '';
    
    let html = '<ul>';
    childStates.forEach(state => {
        html += `
            <li>
                <div class="state-node" data-state-id="${state.id}" data-state-type="${state.type}">
                    <span class="state-icon">${getStateIcon(state.type)}</span>
                    <span class="state-label">${state.label}</span>
                    <span class="state-confidence">${state.confidence.toFixed(2)}</span>
                </div>
                ${renderTreeNodes(states, state.id)}
            </li>
        `;
    });
    html += '</ul>';
    return html;
}

function getStateIcon(type) {
    const icons = {
        'document': '📄',
        'gate': '🚧',
        'artifact': '📦',
        'swarm': '🐝',
        'system': '⚙️'
    };
    return icons[type] || '📍';
}
```

### 4.5 Detail Panel Modal

**HTML Structure**:
```html
<div id="detail-panel" class="detail-panel hidden">
    <div class="detail-header">
        <h2 id="detail-title">Component Details</h2>
        <button onclick="closeDetailPanel()" class="close-btn">×</button>
    </div>
    <div class="detail-content" id="detail-content"></div>
</div>
```

**CSS Styling**:
```css
.detail-panel {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 600px;
    max-height: 80vh;
    background: rgba(10, 14, 39, 0.98);
    border: 2px solid #00ff41;
    border-radius: 10px;
    z-index: 2000;
    overflow-y: auto;
}

.detail-panel.hidden {
    display: none;
}

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #00ff41;
}

.detail-content {
    padding: 20px;
}
```

**Show Function**:
```javascript
function showDetailPanel(component) {
    document.getElementById('detail-title').textContent = component.name;
    document.getElementById('detail-content').innerHTML = `
        <div class="detail-section">
            <h3>Type: ${component.type}</h3>
            <p>Status: ${component.status}</p>
            <p>Domain: ${component.domain || 'N/A'}</p>
        </div>
        <div class="detail-section">
            <h3>Recent Operations</h3>
            <ul>
                ${component.recent_ops.map(op => `<li>${op}</li>`).join('')}
            </ul>
        </div>
        <div class="detail-section">
            <h3>Configuration</h3>
            <pre>${JSON.stringify(component.config, null, 2)}</pre>
        </div>
    `;
    document.getElementById('detail-panel').classList.remove('hidden');
}

function closeDetailPanel() {
    document.getElementById('detail-panel').classList.add('hidden');
}
```

### 4.6 State Actions

**Evolve State**:
```javascript
async function evolveState(stateId) {
    const response = await fetch(`${API_BASE}/api/states/${stateId}/evolve`, {
        method: 'POST'
    });
    const result = await response.json();
    updateVisualization(result);
    addLog(`✓ State evolved: ${stateId}`, 'success');
}
```

**Regenerate State**:
```javascript
async function regenerateState(stateId) {
    const response = await fetch(`${API_BASE}/api/states/${stateId}/regenerate`, {
        method: 'POST'
    });
    const result = await response.json();
    updateVisualization(result);
    addLog(`✓ State regenerated: ${stateId}`, 'success');
}
```

**Rollback State**:
```javascript
async function rollbackState(stateId) {
    const response = await fetch(`${API_BASE}/api/states/${stateId}/rollback`, {
        method: 'POST'
    });
    const result = await response.json();
    updateVisualization(result);
    addLog(`✓ State rolled back: ${stateId}`, 'success');
}
```

### 4.7 WebSocket Client

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:6666/ws');

ws.onopen = function() {
    console.log('Connected to Murphy System');
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    handleRealtimeUpdate(data);
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

ws.onclose = function() {
    console.log('Disconnected from Murphy System');
};
```

**Message Handler**:
```javascript
function handleRealtimeUpdate(data) {
    switch(data.type) {
        case 'agent_update':
            updateAgentGraph(data.data);
            addLog('Agent activity updated', 'info');
            break;
        case 'state_update':
            renderStateTree(data.data.states);
            addLog('State tree updated', 'info');
            break;
        case 'process_update':
            renderProcessFlow(data.data);
            addLog('Process flow updated', 'info');
            break;
        case 'gate_result':
            updateGateDisplay(data.data);
            addLog(`Gate result: ${data.data.status}`, data.data.status === 'pass' ? 'success' : 'error');
            break;
    }
}
```

---

## 5. Implementation Phases

### Phase 1: Backend WebSocket Integration ✅
- [ ] Add Flask-SocketIO to requirements.txt
- [ ] Initialize SocketIO in backend
- [ ] Create connection handler
- [ ] Implement broadcast functions

### Phase 2: Backend State Management ✅
- [ ] Create Agent class
- [ ] Create State class
- [ ] Implement state evolution logic
- [ ] Add API endpoints for state operations

### Phase 3: Frontend Visualization Libraries ✅
- [ ] Add D3.js to HTML
- [ ] Add Cytoscape.js to HTML
- [ ] Create visualization containers
- [ ] Add CSS for visualization

### Phase 4: Frontend Agent Graph ✅
- [ ] Initialize Cytoscape graph
- [ ] Create update function
- [ ] Add click handlers
- [ ] Style nodes and edges

### Phase 5: Frontend Process Flow ✅
- [ ] Initialize D3 SVG
- [ ] Create render function
- [ ] Add stage visualization
- [ ] Style stages and connections

### Phase 6: Frontend State Tree ✅
- [ ] Create tree container
- [ ] Implement render function
- [ ] Add click handlers
- [ ] Style tree nodes

### Phase 7: Frontend Detail Panel ✅
- [ ] Create modal HTML
- [ ] Add CSS styling
- [ ] Implement show/hide functions
- [ ] Add action buttons

### Phase 8: Frontend WebSocket Client ✅
- [ ] Connect to WebSocket
- [ ] Implement message handlers
- [ ] Add real-time updates
- [ ] Handle errors and reconnection

### Phase 9: Integration & Testing ✅
- [ ] Connect frontend to backend
- [ ] Test real-time updates
- [ ] Test interactive elements
- [ ] Verify all component types

### Phase 10: Documentation & Consistency ✅
- [ ] Update API documentation
- [ ] Document data flow
- [ ] Create testing report
- [ ] Finalize architecture

---

## 6. Data Flow Diagrams

### 6.1 User Interaction Flow

```
User Action
    ↓
Frontend Event Handler
    ↓
API Call (fetch/axios)
    ↓
Backend API Endpoint
    ↓
Murphy Runtime Processing
    ↓
LLM API Call (Groq/Aristotle)
    ↓
Result Processing
    ↓
State Update
    ↓
WebSocket Broadcast
    ↓
Frontend WebSocket Handler
    ↓
UI Update
    ↓
Visualization Refresh
```

### 6.2 State Evolution Flow

```
State Selected
    ↓
User clicks "Evolve"
    ↓
API: POST /api/states/{id}/evolve
    ↓
Backend: State.evolve()
    ↓
Create child states
    ↓
Generate with LLM
    ↓
Update parent.children
    ↓
Broadcast state update
    ↓
Frontend: renderStateTree()
    ↓
Tree updated with new children
```

### 6.3 Agent Operation Flow

```
Agent Task Assigned
    ↓
Agent.status = "active"
    ↓
Execute task via Murphy Runtime
    ↓
Update progress periodically
    ↓
Broadcast agent update
    ↓
Frontend: updateAgentGraph()
    ↓
Agent node shows progress
    ↓
Task completed
    ↓
Agent.status = "idle"
    ↓
Broadcast final update
```

---

## 7. Component Interaction Patterns

### 7.1 Agent ↔ Component Interaction

**Pattern**: Agents interact with components to execute operations

**Example**: Sales Agent interacts with LLM Router to generate email
```
Sales Agent → LLM Router → Groq API → Generated Email
                ↓
            Component logs operation
                ↓
            Agent updates progress
```

### 7.2 State ↔ Gate Interaction

**Pattern**: States must pass gates to proceed

**Example**: Document state passes regulatory gate
```
Document State → Regulatory Gate → Aristotle API → Validation Result
                    ↓
                Gate status updated
                    ↓
                State can evolve
```

### 7.3 System ↔ Swarm Interaction

**Pattern**: Systems use swarms to parallelize work

**Example**: Contract Generation System uses swarm
```
System → Swarm Generator → Multiple Agents → Parallel Processing
                                  ↓
                              Results aggregated
                                  ↓
                              System updates progress
```

---

## 8. Testing Strategy

### 8.1 Unit Tests
- Agent class methods
- State class methods
- Gate validation logic
- Component operations

### 8.2 Integration Tests
- API endpoints
- WebSocket connections
- State evolution workflows
- Agent task execution

### 8.3 End-to-End Tests
- Complete living document workflow
- State evolve → regenerate → rollback cycle
- Real-time update streaming
- Interactive element functionality

---

## 9. Performance Considerations

### 9.1 Real-time Updates
- Use WebSocket for efficient real-time communication
- Implement rate limiting for frequent updates
- Use delta updates to minimize data transfer

### 9.2 State Management
- Implement efficient state tree traversal
- Use lazy loading for large state trees
- Cache frequently accessed states

### 9.3 Visualization Performance
- Use efficient graph layouts
- Limit number of visible nodes
- Implement virtual scrolling for large trees

---

## 10. Security Considerations

### 10.1 API Security
- Implement authentication for all endpoints
- Use CORS to restrict access
- Validate all input data

### 10.2 WebSocket Security
- Use WSS for secure connections
- Implement authentication on connection
- Validate all incoming messages

### 10.3 Data Privacy
- Encrypt sensitive data
- Implement proper logging (no sensitive data in logs)
- Follow GDPR and other regulations

---

**Document Version**: 2.0
**Last Updated**: 2024-01-20
**Status**: Active - Implementation Guide