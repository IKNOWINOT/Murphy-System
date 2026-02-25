    
        <script>
        document.addEventListener('DOMContentLoaded', function() {
        // ============================================
        // CONFIGURATION
        // ============================================
        // Auto-detect if we're on localhost or production
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const API_BASE = isLocalhost ? 'http://localhost:3002' : 'https://3002-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai';
        let ws = null;
        let agentGraph = null;
        let processFlowSvg = null;
        let currentStates = [];
        let currentAgents = [];
        let currentConnections = [];
        let selectedStateId = null;

        // ============================================
        // INITIALIZATION
        // ============================================
        
        

        function connectWebSocket() {
            // Use Socket.IO for Flask-SocketIO compatibility
            // CRITICAL: Store socket globally for access throughout the application
            // CRITICAL: Connect to backend URL, not frontend URL
            window.socket = io(API_BASE, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 5
            });
            
            // Use global window.socket for all event handlers
            window.socket.on('connect', function() {
                addTerminalLog('✓ Connected to Murphy System via Socket.IO', 'success');
            });
            
            window.socket.on('connected', function(data) {
                addTerminalLog(`✓ ${data.message}`, 'success');
            });
            
            window.socket.on('system_initialized', function(data) {
                addTerminalLog('✓ System initialized via WebSocket', 'success');
                addTerminalLog(`  System ID: ${data.system_id}`, 'info');
                addTerminalLog(`  Agents: ${data.agents.length}`, 'info');
                addTerminalLog(`  Gates: ${data.gates.length}`, 'info');
                
                // Update data
                currentAgents = data.agents;
                currentConnections = generateAgentConnections(currentAgents);
                
                // Refresh UI
                updateAgentGraph(currentAgents, currentConnections);
                updateMetrics();
            });
            
            window.socket.on('state_updated', function(data) {
                addTerminalLog(`✓ State updated: ${data.state_id}`, 'success');
                
                // Refresh states
                fetch(`${API_BASE}/api/states`)
                    .then(response => response.json())
                    .then(data => {
                        currentStates = data.states || [];
                        renderStateTree(currentStates);
                        updateProcessFlow(currentStates);
                        updateMetrics();
                    });
            });
            
            window.socket.on('agent_updated', function(data) {
                addTerminalLog(`✓ Agent updated: ${data.agent_id}`, 'success');
                
                // Refresh agents
                fetch(`${API_BASE}/api/agents`)
                    .then(response => response.json())
                    .then(data => {
                        currentAgents = data.agents || [];
                        currentConnections = generateAgentConnections(currentAgents);
                        updateAgentGraph(currentAgents, currentConnections);
                        updateMetrics();
                    });
            });
            
            window.socket.on('state_evolved', function(data) {
                addTerminalLog(`✓ State evolved via WebSocket: ${data.parent_id}`, 'success');
                
                // Refresh states
                fetch(`${API_BASE}/api/states`)
                    .then(response => response.json())
                    .then(statesData => {
                        currentStates = statesData.states || [];
                        renderStateTree(currentStates);
                        updateProcessFlow(currentStates);
                        updateMetrics();
                    });
            });
            
            window.socket.on('state_regenerated', function(data) {
                addTerminalLog(`✓ State regenerated via WebSocket: ${data.id}`, 'success');
                
                // Refresh states
                fetch(`${API_BASE}/api/states`)
                    .then(response => response.json())
                    .then(statesData => {
                        currentStates = statesData.states || [];
                        renderStateTree(currentStates);
                        updateProcessFlow(currentStates);
                        updateMetrics();
                    });
            });
            
            window.socket.on('state_rolledback', function(data) {
                addTerminalLog(`✓ State rolled back via WebSocket: ${data.state_id}`, 'success');
                
                // Refresh states
                fetch(`${API_BASE}/api/states`)
                    .then(response => response.json())
                    .then(statesData => {
                        currentStates = statesData.states || [];
                        renderStateTree(currentStates);
                        updateProcessFlow(currentStates);
                        updateMetrics();
                    });
            });
            
            window.socket.on('gate_validated', function(data) {
                addTerminalLog(`✓ Gate validated: ${data.gate_id}`, 'success');
                updateMetrics();
            });
            
            window.socket.on('error', function(data) {
                addTerminalLog(`✗ Socket error: ${data.message}`, 'error');
            });
            
            window.socket.on('disconnect', function() {
                addTerminalLog('✗ Disconnected from Socket.IO', 'warning');
            });
            
            window.socket.on('reconnect', function() {
                addTerminalLog('✓ Reconnected to Socket.IO', 'success');
            });
            
            // Also store as murphySocket for backward compatibility
            window.murphySocket = window.socket;
        }

        async function loadSystemData() {
            // Load states
            const statesResponse = await fetch(`${API_BASE}/api/states`);
            const statesData = await statesResponse.json();
            currentStates = statesData.states;
            renderStateTree(currentStates);
            
            // Load agents
            const agentsResponse = await fetch(`${API_BASE}/api/agents`);
            const agentsData = await agentsResponse.json();
            currentAgents = agentsData.agents;
            updateAgentGraph(currentAgents, []);
            
            // Update metrics
            updateMetrics();
            
            // Update LLM status
            updateLLMStatus();
        }

        // ============================================
        // WEBSOCKET MESSAGE HANDLING
        // ============================================
        
        function handleWebSocketMessage(data) {
            switch (data.type) {
                case 'agent_update':
                    currentAgents = data.agents;
                    currentConnections = data.connections || [];
                    updateAgentGraph(currentAgents, currentConnections);
                    addLog('Agent activity updated', 'info');
                    break;
                    
                case 'state_update':
                    currentStates = data.states;
                    renderStateTree(currentStates);
                    addLog('State tree updated', 'info');
                    break;
                    
                case 'process_update':
                    updateProcessFlow(data.data);
                    addLog('Process flow updated', 'info');
                    break;
                    
                case 'gate_result':
                    addLog(`Gate result: ${data.status} (${data.gate_name})`, 
                           data.status === 'pass' ? 'success' : 'warning');
                    break;
                    
                default:
                    // console.log('Unknown message type:', data.type);
            }
            
            updateMetrics();
        }

        // ============================================
        // AGENT GRAPH (Cytoscape.js)
        // ============================================
        
        function initAgentGraph() {
            agentGraph = cytoscape({
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
                            'height': '60px',
                            'text-wrap': 'wrap',
                            'text-max-width': '80px'
                        }
                    },
                    {
                        selector: 'node[status="active"]',
                        style: {
                            'background-color': '#ffff00',
                            'border-width': '3px',
                            'border-color': '#ffaa00'
                        }
                    },
                    {
                        selector: 'edge',
                        style: {
                            'width': 2,
                            'line-color': '#00ff41',
                            'target-arrow-color': '#00ff41',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier'
                        }
                    }
                ],
                layout: {
                    name: 'circle',
                    fit: true,
                    padding: 30
                }
            });
            
            // Add click handler
            agentGraph.on('tap', 'node', function(evt) {
                const node = evt.target;
                const agentId = node.id();
                showAgentDetails(agentId);
            });
        }

        function updateAgentGraph(agents, connections) {
            if (!agentGraph) {
                initAgentGraph();
            }
            
            const nodes = agents.map(agent => ({
                data: { 
                    id: agent.id, 
                    label: agent.name,
                    status: agent.status
                }
            }));
            
            const edges = (connections || []).map(conn => ({
                data: {
                    source: conn.source,
                    target: conn.target
                }
            }));
            
            agentGraph.json({ nodes, edges });
        }

        async function showAgentDetails(agentId) {
            const response = await fetch(`${API_BASE}/api/agents/${agentId}`);
            const agent = await response.json();
            
            showDetailPanel({
                name: agent.name,
                type: agent.type,
                section1: {
                    title: 'Agent Information',
                    content: `
                        <p><strong>Type:</strong> ${agent.type}</p>
                        <p><strong>Domain:</strong> ${agent.domain || 'N/A'}</p>
                        <p><strong>Status:</strong> <span style="color: ${agent.status === 'active' ? '#00ff41' : '#888'}">${agent.status}</span></p>
                        <p><strong>Progress:</strong> ${agent.progress}%</p>
                        <p><strong>Confidence:</strong> ${(agent.confidence * 100).toFixed(1)}%</p>
                    `
                },
                section2: {
                    title: 'Current Task',
                    content: agent.current_task ? `<p>${agent.current_task}</p>` : '<p>No active task</p>'
                },
                section3: {
                    title: 'Recent Operations',
                    content: agent.recent_ops.length > 0 
                        ? `<ul>${agent.recent_ops.map(op => `<li>${op}</li>`).join('')}</ul>`
                        : '<p>No recent operations</p>'
                },
                section4: {
                    title: 'Configuration',
                    content: `<pre>${JSON.stringify(agent.config, null, 2)}</pre>`
                },
                actions: true
            });
        }

        // ============================================
        // PROCESS FLOW (D3.js)
        // ============================================
        
        function initProcessFlow() {
            processFlowSvg = d3.select("#process-flow")
                .append("svg")
                .attr("width", "100%")
                .attr("height", "100%");
        }

        function updateProcessFlow(data) {
            if (!processFlowSvg) {
                initProcessFlow();
            }
            
            // Clear existing content
            processFlowSvg.selectAll("*").remove();
            
            // Get container dimensions
            const container = document.getElementById('process-flow');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            // Demo process stages
            const stages = [
                { id: 1, name: 'Initialize', status: 'completed' },
                { id: 2, name: 'Analyze', status: 'completed' },
                { id: 3, name: 'Generate', status: 'active' },
                { id: 4, name: 'Validate', status: 'pending' },
                { id: 5, name: 'Approve', status: 'pending' }
            ];
            
            const stageWidth = 100;
            const stageHeight = 50;
            const gap = 20;
            const startX = (width - (stages.length * stageWidth + (stages.length - 1) * gap)) / 2;
            const startY = (height - stageHeight) / 2;
            
            // Render stages
            const stageGroup = processFlowSvg.selectAll(".stage")
                .data(stages)
                .enter()
                .append("g")
                .attr("class", "stage")
                .attr("transform", (d, i) => `translate(${startX + i * (stageWidth + gap)}, ${startY})`);
            
            // Stage boxes
            stageGroup.append("rect")
                .attr("width", stageWidth)
                .attr("height", stageHeight)
                .attr("rx", 5)
                .attr("fill", d => {
                    if (d.status === 'completed') return '#00ff41';
                    if (d.status === 'active') return '#ffaa00';
                    return '#333';
                })
                .attr("stroke", '#00ff41')
                .attr("stroke-width", 2);
            
            // Stage labels
            stageGroup.append("text")
                .attr("x", stageWidth / 2)
                .attr("y", stageHeight / 2 + 5)
                .attr("text-anchor", "middle")
                .attr("fill", "#fff")
                .attr("font-size", "12px")
                .text(d => d.name);
            
            // Connection lines
            for (let i = 0; i < stages.length - 1; i++) {
                processFlowSvg.append("line")
                    .attr("x1", startX + (i + 1) * (stageWidth + gap) - gap / 2)
                    .attr("y1", startY + stageHeight / 2)
                    .attr("x2", startX + (i + 1) * (stageWidth + gap) + gap / 2)
                    .attr("y2", startY + stageHeight / 2)
                    .attr("stroke", "#00ff41")
                    .attr("stroke-width", 2)
                    .attr("marker-end", "url(#arrowhead)");
            }
            
            // Arrowhead marker
            processFlowSvg.append("defs")
                .append("marker")
                .attr("id", "arrowhead")
                .attr("markerWidth", "10")
                .attr("markerHeight", "10")
                .attr("refX", "9")
                .attr("refY", "3")
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,0 L0,6 L9,3 z")
                .attr("fill", "#00ff41");
        }

        // ============================================
        // STATE TREE
        // ============================================
        
        function renderStateTree(states) {
            const treeContent = document.getElementById('state-tree');
            
            if (!states || states.length === 0) {
                treeContent.innerHTML = '<div style="color: #666; padding: 20px; text-align: center;">No states yet</div>';
                return;
            }
            
            treeContent.innerHTML = renderTreeNodes(states, null);
            
            // Add click handlers
            document.querySelectorAll('.state-node').forEach(node => {
                node.addEventListener('click', function() {
                    const stateId = this.dataset.stateId;
                    
                    // Remove previous selection
                    document.querySelectorAll('.state-node.selected').forEach(n => n.classList.remove('selected'));
                    
                    // Add selection
                    this.classList.add('selected');
                    selectedStateId = stateId;
                    
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
                        <div class="state-node ${selectedStateId === state.id ? 'selected' : ''}" 
                             data-state-id="${state.id}" 
                             data-state-type="${state.type}">
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

        async function showStateDetails(stateId) {
            const response = await fetch(`${API_BASE}/api/states/${stateId}`);
            const state = await response.json();
            
            showDetailPanel({
                name: state.label,
                type: state.type,
                section1: {
                    title: 'State Information',
                    content: `
                        <p><strong>Type:</strong> ${state.type}</p>
                        <p><strong>Confidence:</strong> ${(state.confidence * 100).toFixed(1)}%</p>
                        <p><strong>Created:</strong> ${new Date(state.timestamp).toLocaleString()}</p>
                        <p><strong>Parent:</strong> ${state.parent_id || 'Root'}</p>
                        <p><strong>Children:</strong> ${state.children.length}</p>
                    `
                },
                section2: {
                    title: 'Description',
                    content: `<p>${state.description || 'No description'}</p>`
                },
                actions: true,
                stateId: state.id
            });
        }

        // ============================================
        // STATE ACTIONS
        // ============================================
        
        async function evolveState(stateId) {
            addLog(`Evolving state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/evolve`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                addLog(`✓ Evolved ${result.children.length} child states`, 'success');
                closeDetailPanel();
            } catch (error) {
                addLog(`✗ Error evolving state: ${error.message}`, 'error');
            }
        }

        async function regenerateState(stateId) {
            addLog(`Regenerating state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/regenerate`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                addLog(`✓ State regenerated (confidence: ${(result.state.confidence * 100).toFixed(1)}%)`, 'success');
                closeDetailPanel();
            } catch (error) {
                addLog(`✗ Error regenerating state: ${error.message}`, 'error');
            }
        }

        async function rollbackState(stateId) {
            addLog(`Rolling back state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/rollback`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                addLog(`✓ Rolled back to parent state`, 'success');
                closeDetailPanel();
            } catch (error) {
                addLog(`✗ Error rolling back: ${error.message}`, 'error');
            }
        }

        // ============================================
        // DETAIL PANEL
        // ============================================
        
        function showDetailPanel(data) {
            const titleEl = document.getElementById('detail-title');
            const contentEl = document.getElementById('detail-content');
            
            titleEl.textContent = data.name;
            
            let html = '';
            
            if (data.section1) {
                html += `<div class="detail-section"><h3>${data.section1.title}</h3>${data.section1.content}</div>`;
            }
            if (data.section2) {
                html += `<div class="detail-section"><h3>${data.section2.title}</h3>${data.section2.content}</div>`;
            }
            if (data.section3) {
                html += `<div class="detail-section"><h3>${data.section3.title}</h3>${data.section3.content}</div>`;
            }
            if (data.section4) {
                html += `<div class="detail-section"><h3>${data.section4.title}</h3>${data.section4.content}</div>`;
            }
            
            if (data.actions) {
                html += '<div style="text-align: center; margin-top: 20px;">';
                
                if (data.stateId) {
                    html += `
                        <button class="action-btn primary" onclick="evolveState('${data.stateId}')">EVOLVE</button>
                        <button class="action-btn" onclick="regenerateState('${data.stateId}')">REGENERATE</button>
                        <button class="action-btn danger" onclick="rollbackState('${data.stateId}')">ROLLBACK</button>
                    `;
                }
                
                html += '</div>';
            }
            
            contentEl.innerHTML = html;
            document.getElementById('detail-panel').classList.add('active');
        }

        function closeDetailPanel() {
            document.getElementById('detail-panel').classList.remove('active');
        }

        // Close modal on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeDetailPanel();
            }
        });

        // ============================================
        // TERMINAL COMMAND SYSTEM
        // ============================================
        
        // Command history variables - MUST be declared before using them
        let commandHistory = [];
        let historyIndex = -1;
        
        // Initialize terminal input - MOVED HERE TO BE INSIDE DOMContentLoaded
        const terminalInput = document.getElementById('terminal-input');
        const terminal = document.getElementById('terminal');
        
        if (terminalInput) {
            terminalInput.addEventListener('keydown', handleTerminalKeyPress);
            terminalInput.focus();
        }
        
        // Focus terminal when clicking anywhere in terminal area
        if (terminal) {
            terminal.addEventListener('click', function() {
                if (terminalInput) {
                    terminalInput.focus();
                }
            });
        }

        function handleTerminalKeyPress(event) {
            if (event.key === 'Enter') {
                const command = terminalInput.value.trim();
                if (command) {
                    executeTerminalCommand(command);
                    commandHistory.push(command);
                    historyIndex = commandHistory.length;
                    terminalInput.value = '';
                }
            } else if (event.key === 'ArrowUp') {
                if (historyIndex > 0) {
                    historyIndex--;
                    terminalInput.value = commandHistory[historyIndex];
                    event.preventDefault();
                }
            } else if (event.key === 'ArrowDown') {
                if (historyIndex < commandHistory.length - 1) {
                    historyIndex++;
                    terminalInput.value = commandHistory[historyIndex];
                } else {
                    historyIndex = commandHistory.length;
                    terminalInput.value = '';
                }
                event.preventDefault();
            }
        }

        // Commands organized by Murphy System modules
        const availableCommands = {
            'command_system.py': [
                { name: 'help', description: 'Show all commands by module', options: ['<module>'], implemented: true },
                { name: 'status', description: 'Show system status', options: [], implemented: true },
                { name: 'initialize', description: 'Initialize Murphy System', options: [], implemented: true },
                { name: 'clear', description: 'Clear terminal output', options: [], implemented: true }
            ],
            'system_librarian.py': [
                { name: 'librarian search', description: 'Search knowledge base', options: ['<query>'], implemented: false },
                { name: 'librarian transcripts', description: 'View system transcripts', options: [], implemented: false },
                { name: 'librarian overview', description: 'Get system overview', options: [], implemented: false },
                { name: 'librarian knowledge', description: 'Get knowledge about topic', options: ['<topic>'], implemented: false }
            ],
            'advanced_swarm_system.py': [
                { name: 'swarm create', description: 'Create swarm', options: ['<type>'], implemented: false },
                { name: 'swarm execute', description: 'Execute swarm task', options: ['<task>'], implemented: false },
                { name: 'swarm status', description: 'Show active swarms', options: [], implemented: false },
                { name: 'swarm results', description: 'Get swarm results', options: [], implemented: false }
            ],
            'gate_builder.py': [
                { name: 'gate list', description: 'List all gates', options: [], implemented: false },
                { name: 'gate validate', description: 'Validate specific gate', options: ['<gate_id>'], implemented: false },
                { name: 'gate create', description: 'Create new gate', options: ['<type>'], implemented: false },
                { name: 'gate status', description: 'Show gate validation status', options: [], implemented: false }
            ],
            'state_machine.py': [
                { name: 'state list', description: 'List all states', options: [], implemented: true },
                { name: 'state evolve', description: 'Evolve state into children', options: ['<state_id>'], implemented: true },
                { name: 'state regenerate', description: 'Regenerate state', options: ['<state_id>'], implemented: true },
                { name: 'state rollback', description: 'Rollback to parent state', options: ['<state_id>'], implemented: true }
            ],
            'organization_chart_system.py': [
                { name: 'org chart', description: 'Show organization chart', options: [], implemented: false },
                { name: 'org agents', description: 'List all agents', options: [], implemented: true },
                { name: 'org roles', description: 'Show role definitions', options: [], implemented: false },
                { name: 'org assign', description: 'Assign agent to role', options: ['<agent>', '<role>'], implemented: false }
            ],
            'constraint_system.py': [
                { name: 'constraint add', description: 'Add constraint', options: ['<type>'], implemented: false },
                { name: 'constraint list', description: 'List all constraints', options: [], implemented: false },
                { name: 'constraint validate', description: 'Validate constraints', options: [], implemented: false },
                { name: 'constraint conflicts', description: 'Check for conflicts', options: [], implemented: false }
            ],
            'domain_engine.py': [
                { name: 'domain list', description: 'List all domains', options: [], implemented: false },
                { name: 'domain create', description: 'Create new domain', options: ['<name>'], implemented: false },
                { name: 'domain analyze', description: 'Analyze domain coverage', options: ['<request>'], implemented: false },
                { name: 'domain impact', description: 'Show cross-domain impact matrix', options: [], implemented: false }
            ],
            'document_processor.py': [
                { name: 'document create', description: 'Create new document', options: [], implemented: false },
                { name: 'document magnify', description: 'Add domain expertise', options: ['<domain>'], implemented: false },
                { name: 'document simplify', description: 'Distill to essentials', options: [], implemented: false },
                { name: 'document solidify', description: 'Lock for generation', options: [], implemented: false }
            ],
            'memory_artifact_system.py': [
                { name: 'artifact list', description: 'List all artifacts', options: [], implemented: false },
                { name: 'artifact view', description: 'View artifact', options: ['<id>'], implemented: false },
                { name: 'artifact create', description: 'Create artifact', options: [], implemented: false },
                { name: 'artifact search', description: 'Search artifacts', options: ['<query>'], implemented: false }
            ],
            'verification_layer.py': [
                { name: 'verify content', description: 'Verify with Aristotle', options: ['<content>'], implemented: false },
                { name: 'verify gate', description: 'Verify gate', options: ['<id>'], implemented: false },
                { name: 'verify state', description: 'Verify state', options: ['<id>'], implemented: false }
            ],
            'llm_integration.py': [
                { name: 'llm status', description: 'Show LLM status', options: [], implemented: true },
                { name: 'llm switch', description: 'Switch LLM provider', options: ['<provider>'], implemented: false },
                { name: 'llm test', description: 'Test LLM connection', options: [], implemented: false }
            ]
        };

        function executeTerminalCommand(command) {
            const terminalContent = document.getElementById('terminal-content');
            
            // Add command to terminal
            const cmdLine = document.createElement('div');
            cmdLine.className = 'terminal-line';
            cmdLine.innerHTML = `<span style="color: #666;">[${new Date().toLocaleTimeString()}]</span> <span class="terminal-prompt">murphy&gt;</span> <span style="color: #fff;">${command}</span>`;
            terminalContent.appendChild(cmdLine);
            
            // Parse command
            const parts = command.trim().split(/\s+/);
            const cmdName = parts[0].toLowerCase().replace(/^\//, '');
            const args = parts.slice(1);
            
            // Process command
            processCommand(cmdName, args);
            
            // Scroll to bottom
            const terminal = document.getElementById('terminal');
            terminalContent.scrollTop = terminalContent.scrollHeight;
        }

        async function processCommand(cmdName, args) {
            // Handle multi-word commands (e.g., "state evolve", "librarian search")
            const fullCommand = args.length > 0 && !args[0].startsWith('-') 
                ? `${cmdName} ${args[0]}` 
                : cmdName;
            const remainingArgs = args.length > 0 && !args[0].startsWith('-') ? args.slice(1) : args;
            
            // Command routing
            switch (cmdName) {
                // Core system commands
                case 'help':
                    showHelp(args[0]);
                    break;
                    
                case 'status':
                    await showSystemStatus();
                    break;
                    
                case 'initialize':
                case 'init':
                    await initializeSystem();
                    break;
                    
                case 'clear':
                case 'cls':
                    clearTerminal();
                    break;
                
                // State commands
                case 'state':
                    await handleStateCommand(args[0], remainingArgs);
                    break;
                    
                case 'states':
                    await listStates();
                    break;
                    
                case 'evolve':
                    if (args.length > 0) {
                        await evolveStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /evolve <state_id>', 'warning');
                    }
                    break;
                    
                case 'regenerate':
                    if (args.length > 0) {
                        await regenerateStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /regenerate <state_id>', 'warning');
                    }
                    break;
                    
                case 'rollback':
                    if (args.length > 0) {
                        await rollbackStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /rollback <state_id>', 'warning');
                    }
                    break;
                
                // Organization commands
                case 'org':
                    await handleOrgCommand(args[0], remainingArgs);
                    break;
                    
                case 'agents':
                    await listAgents();
                    break;
                
                // Librarian commands
                case 'librarian':
                    await handleLibrarianCommand(args[0], remainingArgs);
                    break;
                
                // Swarm commands
                case 'swarm':
                    await handleSwarmCommand(args[0], remainingArgs);
                    break;
                
                // Gate commands
                case 'gate':
                    await handleGateCommand(args[0], remainingArgs);
                    break;
                
                // Plan commands
                case 'plan':
                    await handlePlanCommand(args[0], remainingArgs);
                    break;
                
                // Document commands
                case 'document':
                case 'doc':
                    await handleDocumentCommand(args[0], remainingArgs);
                    break;
                
                // Artifact commands
                case 'artifact':
                    await handleArtifactCommand(args[0], remainingArgs);
                    break;
                
                // Shadow agent commands
                case 'shadow':
                    await handleShadowCommand(args[0], remainingArgs);
                    break;
                
                // Monitoring commands
                case 'monitoring':
                    await handleMonitoringCommand(args[0], remainingArgs);
                    break;
                
                // Domain commands
                case 'domain':
                    await handleDomainCommand(args[0], remainingArgs);
                    break;
                
                // Constraint commands
                case 'constraint':
                    await handleConstraintCommand(args[0], remainingArgs);
                    break;
                
                // Verification commands
                case 'verify':
                    await handleVerifyCommand(args[0], remainingArgs);
                    break;
                
                // LLM commands
                case 'llm':
                    await handleLLMCommand(args[0], remainingArgs);
                    break;
                    
                default:
                    addTerminalLog(`Unknown command: /${cmdName}. Type /help for available commands.`, 'error');
            }
        }

        function showHelp(moduleName) {
            if (moduleName) {
                // Show help for specific module
                const moduleCommands = availableCommands[moduleName];
                if (moduleCommands) {
                    addTerminalLog(`=== ${moduleName} ===`, 'info');
                    addTerminalLog('', 'info');
                    moduleCommands.forEach(cmd => {
                        const status = cmd.implemented ? '✓' : '○';
                        const options = cmd.options.length > 0 ? ' ' + cmd.options.join(' ') : '';
                        addTerminalLog(`  ${status} /${cmd.name}${options}`, 'info');
                        addTerminalLog(`     ${cmd.description}`, 'info');
                    });
                    addTerminalLog('', 'info');
                    addTerminalLog('Legend: ✓ = Implemented, ○ = Planned', 'info');
                } else {
                    addTerminalLog(`Module not found: ${moduleName}`, 'error');
                    addTerminalLog('Use /help to see all modules', 'info');
                }
            } else {
                // Show all commands grouped by module
                addTerminalLog('=== Murphy System Commands by Module ===', 'info');
                addTerminalLog('', 'info');
                
                let totalImplemented = 0;
                let totalPlanned = 0;
                
                Object.keys(availableCommands).sort().forEach(module => {
                    const commands = availableCommands[module];
                    const implemented = commands.filter(c => c.implemented).length;
                    const planned = commands.filter(c => !c.implemented).length;
                    
                    totalImplemented += implemented;
                    totalPlanned += planned;
                    
                    addTerminalLog(`\n[${module}] (${implemented} implemented, ${planned} planned)`, 'info');
                    commands.forEach(cmd => {
                        const status = cmd.implemented ? '✓' : '○';
                        const options = cmd.options.length > 0 ? ' ' + cmd.options.join(' ') : '';
                        addTerminalLog(`  ${status} /${cmd.name}${options.padEnd(20)} - ${cmd.description}`, 'info');
                    });
                });
                
                addTerminalLog('', 'info');
                addTerminalLog(`Total: ${totalImplemented} implemented, ${totalPlanned} planned`, 'info');
                addTerminalLog('', 'info');
                addTerminalLog('Type /help <module.py> to see commands for a specific module', 'info');
                addTerminalLog('Legend: ✓ = Implemented, ○ = Planned', 'info');
            }
        }

        // ============================================
        // MODULE COMMAND HANDLERS
        // ============================================
        
        async function handleStateCommand(action, args) {
            switch (action) {
                case 'list':
                    await listStates();
                    break;
                case 'evolve':
                    if (args.length > 0) {
                        await evolveStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /state evolve <state_id>', 'warning');
                    }
                    break;
                case 'regenerate':
                    if (args.length > 0) {
                        await regenerateStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /state regenerate <state_id>', 'warning');
                    }
                    break;
                case 'rollback':
                    if (args.length > 0) {
                        await rollbackStateCommand(args[0]);
                    } else {
                        addTerminalLog('Usage: /state rollback <state_id>', 'warning');
                    }
                    break;
                default:
                    addTerminalLog('Available state commands: list, evolve, regenerate, rollback', 'info');
            }
        }
        
        async function handleOrgCommand(action, args) {
            switch (action) {
                case 'chart':
                    addTerminalLog('Organization chart visualization coming soon...', 'warning');
                    break;
                case 'agents':
                    await listAgents();
                    break;
                case 'roles':
                    addTerminalLog('Role definitions coming soon...', 'warning');
                    break;
                case 'assign':
                    addTerminalLog('Agent assignment coming soon...', 'warning');
                    break;
                default:
                    addTerminalLog('Available org commands: chart, agents, roles, assign', 'info');
            }
        }
        
        async function handleLibrarianCommand(action, args) {
            switch (action) {
                case 'ask':
                    if (args.length > 0) {
                        const query = args.join(' ');
                        addTerminalLog(`🧙 Opening Librarian with query: "${query}"`, 'info');
                        librarianPanel.open();
                        setTimeout(() => {
                            document.getElementById('librarian-input').value = query;
                        }, 100);
                    } else {
                        addTerminalLog('🧙 Opening Librarian panel...', 'info');
                        librarianPanel.open();
                    }
                    break;
                case 'search':
                    if (args.length > 0) {
                        const query = args.join(' ');
                        addTerminalLog(`🔍 Searching knowledge base for: "${query}"...`, 'info');
                        try {
                            const response = await fetch(`${API_BASE}/api/librarian/search`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ query })
                            });
                            const data = await response.json();
                            if (data.results &amp;&amp; data.results.length > 0) {
                                addTerminalLog(`✓ Found ${data.count} results:`, 'success');
                                data.results.forEach((result, i) => {
                                    addTerminalLog(`  ${i + 1}. [${result.type.toUpperCase()}] ${result.name}`, 'info');
                                    addTerminalLog(`     ${result.description}`, 'info');
                                });
                            } else {
                                addTerminalLog('No results found', 'warning');
                            }
                        } catch (error) {
                            addTerminalLog(`✗ Search failed: ${error.message}`, 'error');
                        }
                    } else {
                        addTerminalLog('Usage: /librarian search <query>', 'warning');
                    }
                    break;
                case 'transcripts':
                    addTerminalLog('📜 Fetching conversation transcripts...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/librarian/transcripts?limit=5`);
                        const data = await response.json();
                        if (data.transcripts &amp;&amp; data.transcripts.length > 0) {
                            addTerminalLog(`✓ Recent conversations (${data.count}):`, 'success');
                            data.transcripts.forEach((t, i) => {
                                addTerminalLog(`  ${i + 1}. "${t.user_input}"`, 'info');
                                addTerminalLog(`     Intent: ${t.intent_category} (${Math.round(t.confidence * 100)}%)`, 'info');
                                addTerminalLog(`     Response: ${t.message.substring(0, 80)}...`, 'info');
                            });
                        } else {
                            addTerminalLog('No conversation history yet', 'warning');
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Failed to fetch transcripts: ${error.message}`, 'error');
                    }
                    break;
                case 'overview':
                    addTerminalLog('📊 Getting system overview...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/librarian/overview`);
                        const data = await response.json();
                        addTerminalLog('✓ Librarian System Overview:', 'success');
                        addTerminalLog(`  Total Interactions: ${data.total_interactions}`, 'info');
                        if (data.intent_distribution &amp;&amp; Object.keys(data.intent_distribution).length > 0) {
                            addTerminalLog('  Intent Distribution:', 'info');
                            Object.entries(data.intent_distribution).forEach(([intent, count]) => {
                                addTerminalLog(`    • ${intent}: ${count}`, 'info');
                            });
                        }
                        addTerminalLog('  Knowledge Base:', 'info');
                        addTerminalLog(`    • Commands: ${data.knowledge_base_size.commands}`, 'info');
                        addTerminalLog(`    • Concepts: ${data.knowledge_base_size.concepts}`, 'info');
                        addTerminalLog(`    • Workflows: ${data.knowledge_base_size.workflows}`, 'info');
                    } catch (error) {
                        addTerminalLog(`✗ Failed to get overview: ${error.message}`, 'error');
                    }
                    break;
                case 'guide':
                    addTerminalLog('🧙 Opening Librarian for guidance...', 'info');
                    librarianPanel.open();
                    setTimeout(() => {
                        document.getElementById('librarian-input').value = 'I need guidance on what to do next';
                    }, 100);
                    break;
                default:
                    if (!action) {
                        addTerminalLog('🧙 Opening Librarian panel...', 'info');
                        librarianPanel.open();
                    } else {
                        addTerminalLog('Available librarian commands:', 'info');
                        addTerminalLog('  /librarian          - Open interactive Librarian panel', 'info');
                        addTerminalLog('  /librarian ask <q>  - Ask a question', 'info');
                        addTerminalLog('  /librarian search   - Search knowledge base', 'info');
                        addTerminalLog('  /librarian transcripts - View conversation history', 'info');
                        addTerminalLog('  /librarian overview - System overview', 'info');
                        addTerminalLog('  /librarian guide    - Get guidance', 'info');
                    }
            }
        }
        
        async function handleSwarmCommand(action, args) {
            switch (action) {
                case 'create':
                    if (args.length > 0) {
                        addTerminalLog(`Creating ${args[0]} swarm...`, 'info');
                        addTerminalLog('Swarm creation not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /swarm create <type>', 'warning');
                        addTerminalLog('Types: CREATIVE, ANALYTICAL, HYBRID, ADVERSARIAL, SYNTHESIS, OPTIMIZATION', 'info');
                    }
                    break;
                case 'execute':
                    if (args.length > 0) {
                        addTerminalLog(`Executing swarm task: ${args.join(' ')}...`, 'info');
                        addTerminalLog('Swarm execution not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /swarm execute <task>', 'warning');
                    }
                    break;
                case 'status':
                    addTerminalLog('Checking swarm status...', 'info');
                    addTerminalLog('Swarm status not yet implemented', 'warning');
                    break;
                case 'results':
                    addTerminalLog('Getting swarm results...', 'info');
                    addTerminalLog('Swarm results not yet implemented', 'warning');
                    break;
                default:
                    addTerminalLog('Available swarm commands: create, execute, status, results', 'info');
            }
        }
        
        async function handleGateCommand(action, args) {
            switch (action) {
                case 'list':
                    addTerminalLog('Listing all gates...', 'info');
                    addTerminalLog('Gate listing not yet implemented', 'warning');
                    break;
                case 'validate':
                    if (args.length > 0) {
                        addTerminalLog(`Validating gate: ${args[0]}...`, 'info');
                        addTerminalLog('Gate validation not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /gate validate <gate_id>', 'warning');
                    }
                    break;
                case 'create':
                    if (args.length > 0) {
                        addTerminalLog(`Creating ${args[0]} gate...`, 'info');
                        addTerminalLog('Gate creation not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /gate create <type>', 'warning');
                    }
                    break;
                case 'status':
                    addTerminalLog('Checking gate status...', 'info');
                    addTerminalLog('Gate status not yet implemented', 'warning');
                    break;
                default:
                    addTerminalLog('Available gate commands: list, validate, create, status', 'info');
            }
        }
        
        async function handlePlanCommand(action, args) {
            switch (action) {
                case 'create':
                    addTerminalLog('📋 Creating new plan...', 'info');
                    // Create a sample plan and open the review panel
                    try {
                        const response = await fetch(`${API_BASE}/api/plans`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                name: args[0] || 'New Plan',
                                plan_type: 'custom',
                                description: 'User-created plan',
                                content: 'Plan content goes here...',
                                steps: [
                                    {command: '/initialize', description: 'Initialize system', estimated_time: 60}
                                ],
                                domains: []
                            })
                        });
                        const data = await response.json();
                        if (data.success) {
                            addTerminalLog(`✓ Plan created: ${data.plan.name}`, 'success');
                            planReviewPanel.open(data.plan.id);
                        }
                    } catch (error) {
                        addTerminalLog('✗ Failed to create plan', 'error');
                    }
                    break;
                case 'list':
                    addTerminalLog('📋 Listing all plans...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/plans`);
                        const data = await response.json();
                        if (data.plans.length === 0) {
                            addTerminalLog('No plans found', 'warning');
                        } else {
                            data.plans.forEach(plan => {
                                addTerminalLog(`  • ${plan.name} (${plan.current_state}) - v${plan.current_version}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog('✗ Failed to list plans', 'error');
                    }
                    break;
                case 'open':
                    if (args.length > 0) {
                        addTerminalLog(`📋 Opening plan: ${args[0]}`, 'info');
                        planReviewPanel.open(args[0]);
                    } else {
                        addTerminalLog('Usage: /plan open <plan_id>', 'warning');
                    }
                    break;
                default:
                    addTerminalLog('Available plan commands:', 'info');
                    addTerminalLog('  /plan create [name] - Create new plan', 'info');
                    addTerminalLog('  /plan list - List all plans', 'info');
                    addTerminalLog('  /plan open <id> - Open plan for review', 'info');
            }
        }
        
        async function handleDocumentCommand(action, args) {
            switch (action) {
                case 'create':
                    addTerminalLog('📄 Creating new document...', 'info');
                    const docType = args[0] || 'custom';
                    const docName = args[1] || 'New Document';
                    documentEditorPanel.createNew(docType, docName);
                    break;
                case 'list':
                    addTerminalLog('📄 Listing all documents...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/documents`);
                        const data = await response.json();
                        if (data.documents.length === 0) {
                            addTerminalLog('No documents found', 'warning');
                        } else {
                            data.documents.forEach(doc => {
                                addTerminalLog(`  • ${doc.name} (${doc.current_state}) - depth ${doc.expertise_depth}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog('✗ Failed to list documents', 'error');
                    }
                    break;
                case 'open':
                    if (args.length > 0) {
                        addTerminalLog(`📄 Opening document: ${args[0]}`, 'info');
                        documentEditorPanel.open(args[0]);
                    } else {
                        addTerminalLog('Usage: /document open <doc_id>', 'warning');
                    }
                    break;
                case 'templates':
                    addTerminalLog('📋 Opening templates...', 'info');
                    documentEditorPanel.showTemplates();
                    break;
                default:
                    addTerminalLog('Available document commands:', 'info');
                    addTerminalLog('  /document create [type] [name] - Create new document', 'info');
                    addTerminalLog('  /document list - List all documents', 'info');
                    addTerminalLog('  /document open <id> - Open document for editing', 'info');
                    addTerminalLog('  /document templates - Browse templates', 'info');
            }
        }
        
        async function handleArtifactCommand(action, args) {
            switch (action) {
                case 'list':
                    await listArtifacts();
                    break;
                case 'view':
                case 'open':
                    if (args.length > 0) {
                        await viewArtifact(args[0]);
                    } else {
                        addTerminalLog('Usage: /artifact view <id>', 'warning');
                    }
                    break;
                case 'generate':
                case 'create':
                    ArtifactPanel.showGenerateDialog();
                    addTerminalLog('🎨 Opening artifact generation dialog...', 'info');
                    break;
                case 'search':
                    if (args.length > 0) {
                        await searchArtifacts(args.join(' '));
                    } else {
                        addTerminalLog('Usage: /artifact search <query>', 'warning');
                    }
                    break;
                case 'convert':
                    if (args.length >= 2) {
                        await convertArtifact(args[0], args[1]);
                    } else {
                        addTerminalLog('Usage: /artifact convert <id> <format>', 'warning');
                    }
                    break;
                case 'download':
                    if (args.length > 0) {
                        await ArtifactPanel.downloadArtifact(args[0]);
                    } else {
                        addTerminalLog('Usage: /artifact download <id>', 'warning');
                    }
                    break;
                case 'stats':
                    await showArtifactStats();
                    break;
                default:
                    addTerminalLog('Available artifact commands:', 'info');
                    addTerminalLog('  /artifact list              - List all artifacts', 'info');
                    addTerminalLog('  /artifact view <id>         - View artifact details', 'info');
                    addTerminalLog('  /artifact generate          - Generate new artifact', 'info');
                    addTerminalLog('  /artifact search <query>    - Search artifacts', 'info');
                    addTerminalLog('  /artifact convert <id> <fmt> - Convert format', 'info');
                    addTerminalLog('  /artifact download <id>     - Download artifact', 'info');
                    addTerminalLog('  /artifact stats             - Show statistics', 'info');
            }
        }
        
        async function listArtifacts() {
            try {
                addTerminalLog('📦 Listing artifacts...', 'info');
                const response = await fetch(`${API_BASE}/api/artifacts/list`);
                const data = await response.json();
                
                if (data.artifacts &amp;&amp; data.artifacts.length > 0) {
                    addTerminalLog(`\n✓ Found ${data.artifacts.length} artifacts:\n`, 'success');
                    data.artifacts.forEach(artifact => {
                        addTerminalLog(`  [${artifact.type.toUpperCase()}] ${artifact.name}`, 'info');
                        addTerminalLog(`    ID: ${artifact.id}`, 'info');
                        addTerminalLog(`    Status: ${artifact.status} | Quality: ${(artifact.quality_score * 100).toFixed(0)}%`, 'info');
                        addTerminalLog(`    Created: ${new Date(artifact.created_at).toLocaleString()}`, 'info');
                        addTerminalLog('', 'info');
                    });
                } else {
                    addTerminalLog('No artifacts found', 'warning');
                }
            } catch (error) {
                addTerminalLog(`✗ Error listing artifacts: ${error.message}`, 'error');
            }
        }
        
        async function viewArtifact(artifactId) {
            try {
                addTerminalLog(`📄 Loading artifact: ${artifactId}...`, 'info');
                await ArtifactPanel.selectArtifact(artifactId);
            } catch (error) {
                addTerminalLog(`✗ Error viewing artifact: ${error.message}`, 'error');
            }
        }
        
        async function searchArtifacts(query) {
            try {
                addTerminalLog(`🔍 Searching for: "${query}"...`, 'info');
                const response = await fetch(`${API_BASE}/api/artifacts/search?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                if (data.results &amp;&amp; data.results.length > 0) {
                    addTerminalLog(`\n✓ Found ${data.results.length} matching artifacts:\n`, 'success');
                    data.results.forEach(artifact => {
                        addTerminalLog(`  [${artifact.type.toUpperCase()}] ${artifact.name}`, 'info');
                        addTerminalLog(`    ID: ${artifact.id}`, 'info');
                        addTerminalLog('', 'info');
                    });
                } else {
                    addTerminalLog('No matching artifacts found', 'warning');
                }
            } catch (error) {
                addTerminalLog(`✗ Error searching artifacts: ${error.message}`, 'error');
            }
        }
        
        async function convertArtifact(artifactId, format) {
            try {
                addTerminalLog(`🔄 Converting artifact to ${format.toUpperCase()}...`, 'info');
                const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}/convert`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ format: format })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    addTerminalLog(`✓ Artifact converted successfully`, 'success');
                    addTerminalLog(`  New artifact ID: ${data.artifact.id}`, 'info');
                } else {
                    addTerminalLog(`✗ Conversion failed: ${data.error}`, 'error');
                }
            } catch (error) {
                addTerminalLog(`✗ Error converting artifact: ${error.message}`, 'error');
            }
        }
        
        async function showArtifactStats() {
            try {
                addTerminalLog('📊 Loading artifact statistics...', 'info');
                const response = await fetch(`${API_BASE}/api/artifacts/stats`);
                const stats = await response.json();
                
                addTerminalLog('\n=== Artifact Statistics ===\n', 'success');
                addTerminalLog(`Total Artifacts: ${stats.total_artifacts}`, 'info');
                addTerminalLog(`Average Quality: ${(stats.average_quality * 100).toFixed(0)}%`, 'info');
                addTerminalLog(`Total Size: ${formatFileSize(stats.total_size)}`, 'info');
                
                if (Object.keys(stats.by_type).length > 0) {
                    addTerminalLog('\nBy Type:', 'info');
                    Object.entries(stats.by_type).forEach(([type, count]) => {
                        addTerminalLog(`  ${type.toUpperCase()}: ${count}`, 'info');
                    });
                }
                
                if (Object.keys(stats.by_status).length > 0) {
                    addTerminalLog('\nBy Status:', 'info');
                    Object.entries(stats.by_status).forEach(([status, count]) => {
                        addTerminalLog(`  ${status}: ${count}`, 'info');
                    });
                }
                
                addTerminalLog('', 'info');
            } catch (error) {
                addTerminalLog(`✗ Error loading stats: ${error.message}`, 'error');
            }
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        // Shadow agent utility functions
        function getAgentIcon(type) {
            const icons = {
                'command_observer': '🔍',
                'document_watcher': '📄',
                'artifact_monitor': '🎨',
                'state_tracker': '🔄',
                'workflow_analyzer': '⚡'
            };
            return icons[type] || '🤖';
        }

        function formatAgentType(type) {
            return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }

        function formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            
            if (diff < 60000) return 'Just now';
            if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
            if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
            return date.toLocaleDateString();
        }

        function formatComponentName(name) {
            return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }

        function formatMetricName(name) {
            return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }

        function openShadowPanel() {
            document.getElementById('shadow-agents-modal').style.display = 'block';
            if (shadowPanel) {
                shadowPanel.loadInitialData();
            }
        }

        function closeShadowPanel() {
            document.getElementById('shadow-agents-modal').style.display = 'none';
        }

        function openMonitoringPanel() {
            document.getElementById('monitoring-panel-modal').style.display = 'block';
            if (monitoringPanel) {
                monitoringPanel.loadInitialData();
            }
        }

        function closeMonitoringPanel() {
            document.getElementById('monitoring-panel-modal').style.display = 'none';
        }
        
        async function handleShadowCommand(action, args) {
            switch (action) {
                case 'list':
                    addTerminalLog('📋 Listing shadow agents...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/agents`);
                        const agents = await response.json();
                        if (agents && agents.length > 0) {
                            addTerminalLog(`\n✓ Found ${agents.length} shadow agents:\n`, 'success');
                            agents.forEach(agent => {
                                addTerminalLog(`  ${getAgentIcon(agent.type)} ${agent.name}`, 'info');
                                addTerminalLog(`    Type: ${formatAgentType(agent.type)}`, 'info');
                                addTerminalLog(`    Status: ${agent.status}`, 'info');
                                addTerminalLog(`    Observations: ${agent.observations_count || 0}`, 'info');
                                addTerminalLog(`    Patterns: ${agent.patterns_count || 0}`, 'info');
                                addTerminalLog(`    Automations: ${agent.automations_count || 0}`, 'info');
                                addTerminalLog('', 'info');
                            });
                        } else {
                            addTerminalLog('No shadow agents found', 'warning');
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error listing agents: ${error.message}`, 'error');
                    }
                    break;
                case 'observations':
                    addTerminalLog('📊 Fetching recent observations...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/observations`);
                        const observations = await response.json();
                        if (observations && observations.length > 0) {
                            addTerminalLog(`\n✓ Found ${observations.length} observations:\n`, 'success');
                            observations.slice(0, 10).forEach(obs => {
                                addTerminalLog(`  [${formatTime(obs.timestamp)}] ${obs.action_type}`, 'info');
                                addTerminalLog(`    ${obs.description.substring(0, 80)}...`, 'info');
                                addTerminalLog(`    Agent: ${getAgentName(obs.agent_id)} | Confidence: ${(obs.confidence || 0).toFixed(2)}`, 'info');
                                addTerminalLog('', 'info');
                            });
                        } else {
                            addTerminalLog('No observations found', 'warning');
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching observations: ${error.message}`, 'error');
                    }
                    break;
                case 'proposals':
                    addTerminalLog('💡 Fetching automation proposals...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/proposals`);
                        const proposals = await response.json();
                        if (proposals && proposals.length > 0) {
                            addTerminalLog(`\n✓ Found ${proposals.length} proposals:\n`, 'success');
                            proposals.forEach(prop => {
                                addTerminalLog(`  🎯 ${prop.title}`, 'info');
                                addTerminalLog(`    Status: ${prop.status} | Confidence: ${(prop.confidence || 0).toFixed(2)}`, 'info');
                                addTerminalLog(`    Savings: ${prop.estimated_savings || 'N/A'}`, 'info');
                                addTerminalLog(`    ${prop.description.substring(0, 80)}...`, 'info');
                                addTerminalLog('', 'info');
                            });
                        } else {
                            addTerminalLog('No proposals found', 'warning');
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching proposals: ${error.message}`, 'error');
                    }
                    break;
                case 'automations':
                    addTerminalLog('🤖 Fetching active automations...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/automations`);
                        const automations = await response.json();
                        if (automations && automations.length > 0) {
                            addTerminalLog(`\n✓ Found ${automations.length} automations:\n`, 'success');
                            automations.forEach(auto => {
                                const successRate = ((auto.success_count || 0) / (auto.execution_count || 1) * 100).toFixed(1);
                                addTerminalLog(`  ⚡ ${auto.title}`, 'info');
                                addTerminalLog(`    Status: ${auto.status} | Success Rate: ${successRate}%`, 'info');
                                addTerminalLog(`    Runs: ${auto.execution_count || 0}`, 'info');
                                addTerminalLog(`    ${auto.description.substring(0, 80)}...`, 'info');
                                addTerminalLog('', 'info');
                            });
                        } else {
                            addTerminalLog('No automations found', 'warning');
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching automations: ${error.message}`, 'error');
                    }
                    break;
                case 'approve':
                    if (args.length === 0) {
                        addTerminalLog('Usage: /shadow approve <proposal_id>', 'warning');
                        return;
                    }
                    addTerminalLog(`✅ Approving proposal ${args[0]}...`, 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/proposals`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ action: 'approve', proposal_id: args[0] })
                        });
                        addTerminalLog('✓ Proposal approved successfully', 'success');
                    } catch (error) {
                        addTerminalLog(`✗ Error approving proposal: ${error.message}`, 'error');
                    }
                    break;
                case 'reject':
                    if (args.length === 0) {
                        addTerminalLog('Usage: /shadow reject <proposal_id>', 'warning');
                        return;
                    }
                    addTerminalLog(`❌ Rejecting proposal ${args[0]}...`, 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/proposals`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ action: 'reject', proposal_id: args[0] })
                        });
                        addTerminalLog('✓ Proposal rejected', 'success');
                    } catch (error) {
                        addTerminalLog(`✗ Error rejecting proposal: ${error.message}`, 'error');
                    }
                    break;
                case 'learn':
                    addTerminalLog('🧠 Running learning cycle...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/learn`, { method: 'POST' });
                        const result = await response.json();
                        addTerminalLog('✓ Learning cycle complete', 'success');
                        addTerminalLog(`  New patterns detected: ${result.new_patterns || 0}`, 'info');
                        addTerminalLog(`  New proposals generated: ${result.new_proposals || 0}`, 'info');
                    } catch (error) {
                        addTerminalLog(`✗ Error running learning cycle: ${error.message}`, 'error');
                    }
                    break;
                case 'stats':
                    addTerminalLog('📈 Fetching shadow agent statistics...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/shadow/stats`);
                        const stats = await response.json();
                        addTerminalLog('\nShadow Agent Statistics:', 'success');
                        addTerminalLog(`  Total Agents: ${stats.total_agents || 0}`, 'info');
                        addTerminalLog(`  Total Observations: ${stats.total_observations || 0}`, 'info');
                        addTerminalLog(`  Total Patterns: ${stats.total_patterns || 0}`, 'info');
                        addTerminalLog(`  Total Proposals: ${stats.total_proposals || 0}`, 'info');
                        addTerminalLog(`  Total Automations: ${stats.total_automations || 0}`, 'info');
                        addTerminalLog(`  Pending Approvals: ${stats.pending_approvals || 0}`, 'info');
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching statistics: ${error.message}`, 'error');
                    }
                    break;
                default:
                    addTerminalLog('Available shadow agent commands:', 'info');
                    addTerminalLog('  /shadow list             - List all shadow agents', 'info');
                    addTerminalLog('  /shadow observations     - View recent observations', 'info');
                    addTerminalLog('  /shadow proposals        - View automation proposals', 'info');
                    addTerminalLog('  /shadow automations      - View active automations', 'info');
                    addTerminalLog('  /shadow approve <id>     - Approve proposal', 'info');
                    addTerminalLog('  /shadow reject <id>      - Reject proposal', 'info');
                    addTerminalLog('  /shadow learn            - Run learning cycle', 'info');
                    addTerminalLog('  /shadow stats             - Show statistics', 'info');
            }
        }
        
        async function handleMonitoringCommand(action, args) {
            switch (action) {
                case 'health':
                    addTerminalLog('🏥 Fetching system health...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/health`);
                        const healthData = await response.json();
                        
                        addTerminalLog('\n📊 System Health Overview:', 'success');
                        addTerminalLog(`  Overall Status: ${healthData.overall.message}`, 'info');
                        addTerminalLog(`  Health Score: ${healthData.overall.score}%`, 'info');
                        addTerminalLog(`\nComponent Breakdown:`, 'info');
                        addTerminalLog(`  Healthy: ${healthData.overall.components.healthy}`, 'success');
                        addTerminalLog(`  Degraded: ${healthData.overall.components.degraded}`, 'warning');
                        addTerminalLog(`  Unhealthy: ${healthData.overall.components.unhealthy}`, 'error');
                        addTerminalLog(`\nComponent Details:`, 'info');
                        
                        Object.entries(healthData.components).forEach(([name, component]) => {
                            const statusIcon = component.status === 'healthy' ? '✓' : 
                                             component.status === 'degraded' ? '⚠' : 
                                             component.status === 'unhealthy' ? '✗' : '?';
                            addTerminalLog(`  ${statusIcon} ${formatComponentName(name)}: ${component.status}`, 'info');
                            addTerminalLog(`    ${component.message}`, 'info');
                        });
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching health: ${error.message}`, 'error');
                    }
                    break;
                case 'metrics':
                    addTerminalLog('📈 Fetching performance metrics...', 'info');
                    try {
                        const metricName = args[0] || null;
                        const limit = parseInt(args[1]) || 20;
                        
                        const response = await fetch(`${API_BASE}/api/monitoring/metrics?limit=${limit}`);
                        const data = await response.json();
                        
                        if (metricName) {
                            // Show stats for specific metric
                            const stats = data.stats;
                            addTerminalLog(`\n📊 ${metricName.toUpperCase()} Statistics:`, 'success');
                            addTerminalLog(`  Count: ${stats.count}`, 'info');
                            addTerminalLog(`  Average: ${stats.avg.toFixed(2)}`, 'info');
                            addTerminalLog(`  Median: ${stats.median.toFixed(2)}`, 'info');
                            addTerminalLog(`  Min: ${stats.min.toFixed(2)}`, 'info');
                            addTerminalLog(`  Max: ${stats.max.toFixed(2)}`, 'info');
                            addTerminalLog(`  StdDev: ${stats.stddev.toFixed(2)}`, 'info');
                            addTerminalLog(`  P95: ${stats.p95.toFixed(2)}`, 'info');
                            addTerminalLog(`  P99: ${stats.p99.toFixed(2)}`, 'info');
                        } else {
                            // List all metrics
                            addTerminalLog(`\n📊 Available Metrics (${data.metrics.length}):`, 'success');
                            const metricNames = [...new Set(data.metrics.map(m => m.name))];
                            metricNames.forEach(name => {
                                const latest = data.metrics.filter(m => m.name === name).pop();
                                addTerminalLog(`  ${formatMetricName(name)}: ${latest.value.toFixed(2)} ${latest.unit}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching metrics: ${error.message}`, 'error');
                    }
                    break;
                case 'anomalies':
                    addTerminalLog('🔍 Fetching detected anomalies...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/anomalies`);
                        const data = await response.json();
                        
                        if (data.anomalies.length === 0) {
                            addTerminalLog('✓ No anomalies detected', 'success');
                        } else {
                            addTerminalLog(`\n⚠️ Found ${data.anomalies.length} anomalies:`, 'warning');
                            data.anomalies.slice(0, 10).forEach(anomaly => {
                                const severityIcon = anomaly.severity === 'critical' ? '🚨' :
                                                  anomaly.severity === 'high' ? '🔴' :
                                                  anomaly.severity === 'medium' ? '⚠️' : '⚡';
                                addTerminalLog(`  ${severityIcon} ${anomaly.metric_name} [${anomaly.severity.toUpperCase()}]`, 'info');
                                addTerminalLog(`    ${anomaly.description}`, 'info');
                                addTerminalLog(`    Value: ${anomaly.value.toFixed(2)} | Threshold: ${anomaly.threshold.toFixed(2)}`, 'info');
                                addTerminalLog(`    Time: ${formatTime(anomaly.timestamp)}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching anomalies: ${error.message}`, 'error');
                    }
                    break;
                case 'recommendations':
                    addTerminalLog('💡 Fetching optimization recommendations...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/recommendations`);
                        const data = await response.json();
                        
                        if (data.recommendations.length === 0) {
                            addTerminalLog('✓ No recommendations available', 'success');
                        } else {
                            addTerminalLog(`\n💡 Found ${data.recommendations.length} recommendations:`, 'success');
                            data.recommendations.slice(0, 10).forEach(rec => {
                                const priorityIcon = rec.priority === 'critical' ? '🚨' :
                                                   rec.priority === 'high' ? '🔴' :
                                                   rec.priority === 'medium' ? '⚠️' : '💡';
                                addTerminalLog(`  ${priorityIcon} ${rec.title} [${rec.priority.toUpperCase()}]`, 'info');
                                addTerminalLog(`    ${rec.description}`, 'info');
                                addTerminalLog(`    Impact: ${rec.expected_impact}`, 'info');
                                addTerminalLog(`    Category: ${rec.category}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching recommendations: ${error.message}`, 'error');
                    }
                    break;
                case 'alerts':
                    addTerminalLog('🚨 Fetching active alerts...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/alerts`);
                        const data = await response.json();
                        
                        if (data.alerts.length === 0) {
                            addTerminalLog('✓ No active alerts', 'success');
                        } else {
                            addTerminalLog(`\n🚨 Found ${data.alerts.length} active alerts:`, 'error');
                            data.alerts.forEach(alert => {
                                const severityIcon = alert.severity === 'critical' ? '🚨' :
                                                   alert.severity === 'high' ? '🔴' : '⚠️';
                                addTerminalLog(`  ${severityIcon} ${alert.metric_name} [${alert.severity.toUpperCase()}]`, 'info');
                                addTerminalLog(`    ${alert.description}`, 'info');
                                addTerminalLog(`    Time: ${formatTime(alert.timestamp)}`, 'info');
                                addTerminalLog(`    ID: ${alert.id}`, 'info');
                            });
                        }
                    } catch (error) {
                        addTerminalLog(`✗ Error fetching alerts: ${error.message}`, 'error');
                    }
                    break;
                case 'analyze':
                    addTerminalLog('🔄 Running monitoring analysis...', 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/analyze`, {
                            method: 'POST'
                        });
                        const result = await response.json();
                        
                        addTerminalLog('✓ Analysis complete', 'success');
                        addTerminalLog(`  Anomalies detected: ${result.anomalies_detected}`, 'info');
                        addTerminalLog(`  Recommendations generated: ${result.recommendations_generated}`, 'info');
                    } catch (error) {
                        addTerminalLog(`✗ Error running analysis: ${error.message}`, 'error');
                    }
                    break;
                case 'dismiss':
                    if (args.length === 0) {
                        addTerminalLog('Usage: /monitoring dismiss <alert_id>', 'warning');
                        return;
                    }
                    addTerminalLog(`🚫 Dismissing alert ${args[0]}...`, 'info');
                    try {
                        const response = await fetch(`${API_BASE}/api/monitoring/alerts/${args[0]}/dismiss`, {
                            method: 'POST'
                        });
                        addTerminalLog('✓ Alert dismissed', 'success');
                    } catch (error) {
                        addTerminalLog(`✗ Error dismissing alert: ${error.message}`, 'error');
                    }
                    break;
                case 'panel':
                case 'dashboard':
                    openMonitoringPanel();
                    addTerminalLog('📊 Opening monitoring dashboard...', 'info');
                    break;
                default:
                    addTerminalLog('Available monitoring commands:', 'info');
                    addTerminalLog('  /monitoring health         - Show system health', 'info');
                    addTerminalLog('  /monitoring metrics        - Show performance metrics', 'info');
                    addTerminalLog('  /monitoring metrics <name> - Show stats for specific metric', 'info');
                    addTerminalLog('  /monitoring anomalies      - Show detected anomalies', 'info');
                    addTerminalLog('  /monitoring recommendations- Show optimization suggestions', 'info');
                    addTerminalLog('  /monitoring alerts         - Show active alerts', 'info');
                    addTerminalLog('  /monitoring analyze        - Run monitoring analysis', 'info');
                    addTerminalLog('  /monitoring dismiss <id>   - Dismiss alert', 'info');
                    addTerminalLog('  /monitoring panel          - Open monitoring dashboard', 'info');
            }
        }
        
        async function handleDomainCommand(action, args) {
            switch (action) {
                case 'list':
                    addTerminalLog('Listing all domains...', 'info');
                    addTerminalLog('Domain listing not yet implemented', 'warning');
                    break;
                case 'create':
                    if (args.length > 0) {
                        addTerminalLog(`Creating domain: ${args[0]}...`, 'info');
                        addTerminalLog('Domain creation not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /domain create <name>', 'warning');
                    }
                    break;
                case 'analyze':
                    if (args.length > 0) {
                        addTerminalLog(`Analyzing domain coverage for: ${args.join(' ')}...`, 'info');
                        addTerminalLog('Domain analysis not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /domain analyze <request>', 'warning');
                    }
                    break;
                case 'impact':
                    addTerminalLog('Showing cross-domain impact matrix...', 'info');
                    addTerminalLog('Domain impact matrix not yet implemented', 'warning');
                    break;
                default:
                    addTerminalLog('Available domain commands: list, create, analyze, impact', 'info');
            }
        }
        
        async function handleConstraintCommand(action, args) {
            switch (action) {
                case 'add':
                    if (args.length > 0) {
                        addTerminalLog(`Adding ${args[0]} constraint...`, 'info');
                        addTerminalLog('Constraint addition not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /constraint add <type>', 'warning');
                        addTerminalLog('Types: BUDGET, REGULATORY, ARCHITECTURAL, PERFORMANCE, SECURITY, TIME, RESOURCE, BUSINESS', 'info');
                    }
                    break;
                case 'list':
                    addTerminalLog('Listing all constraints...', 'info');
                    addTerminalLog('Constraint listing not yet implemented', 'warning');
                    break;
                case 'validate':
                    addTerminalLog('Validating constraints...', 'info');
                    addTerminalLog('Constraint validation not yet implemented', 'warning');
                    break;
                case 'conflicts':
                    addTerminalLog('Checking for constraint conflicts...', 'info');
                    addTerminalLog('Conflict checking not yet implemented', 'warning');
                    break;
                default:
                    addTerminalLog('Available constraint commands: add, list, validate, conflicts', 'info');
            }
        }
        
        async function handleVerifyCommand(action, args) {
            switch (action) {
                case 'content':
                    if (args.length > 0) {
                        addTerminalLog(`Verifying content with Aristotle: ${args.join(' ')}...`, 'info');
                        addTerminalLog('Content verification not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /verify content <content>', 'warning');
                    }
                    break;
                case 'gate':
                    if (args.length > 0) {
                        addTerminalLog(`Verifying gate: ${args[0]}...`, 'info');
                        addTerminalLog('Gate verification not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /verify gate <id>', 'warning');
                    }
                    break;
                case 'state':
                    if (args.length > 0) {
                        addTerminalLog(`Verifying state: ${args[0]}...`, 'info');
                        addTerminalLog('State verification not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /verify state <id>', 'warning');
                    }
                    break;
                default:
                    addTerminalLog('Available verify commands: content, gate, state', 'info');
            }
        }
        
        async function handleLLMCommand(action, args) {
            switch (action) {
                case 'status':
                    await showSystemStatus();
                    break;
                case 'switch':
                    if (args.length > 0) {
                        addTerminalLog(`Switching to ${args[0]} provider...`, 'info');
                        addTerminalLog('LLM switching not yet implemented', 'warning');
                    } else {
                        addTerminalLog('Usage: /llm switch <provider>', 'warning');
                        addTerminalLog('Providers: groq, aristotle, onboard', 'info');
                    }
                    break;
                case 'test':
                    addTerminalLog('Testing LLM connection...', 'info');
                    addTerminalLog('LLM testing not yet implemented', 'warning');
                    break;
                default:
                    addTerminalLog('Available llm commands: status, switch, test', 'info');
            }
        }
        
        // ============================================
        // HELPER FUNCTIONS
        // ============================================
        
        function generateAgentConnections(agents) {
            const connections = [];
            // Generate connections between agents
            for (let i = 0; i < agents.length; i++) {
                for (let j = i + 1; j < agents.length; j++) {
                    // Randomly create connections to simulate network
                    if (Math.random() > 0.6) {
                        connections.push({
                            source: agents[i].id,
                            target: agents[j].id,
                            type: 'collaboration'
                        });
                    }
                }
            }
            return connections;
        }

        // ============================================
        // CORE COMMAND IMPLEMENTATIONS
        // ============================================

        async function showSystemStatus() {
            addTerminalLog('=== System Status ===', 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/status`);
                const data = await response.json();
                
                addTerminalLog(`System Status: ${data.status}`, 'success');
                addTerminalLog(`Backend Version: ${data.version}`, 'info');
                addTerminalLog(`Initialized: ${data.initialized ? 'Yes' : 'No'}`, 'info');
                
                addTerminalLog('', 'info');
                addTerminalLog('=== LLM Status ===', 'info');
                addTerminalLog(`Groq: ${data.llms.groq.status} (${data.llms.groq.model})`, data.llms.groq.status === 'active' ? 'success' : 'warning');
                addTerminalLog(`Aristotle: ${data.llms.aristotle.status} (${data.llms.aristotle.model})`, data.llms.aristotle.status === 'active' ? 'success' : 'warning');
                addTerminalLog(`Onboard: ${data.llms.onboard.status}`, data.llms.onboard.status === 'active' ? 'success' : 'warning');
                
                if (data.metrics) {
                    addTerminalLog('', 'info');
                    addTerminalLog('=== Metrics ===', 'info');
                    addTerminalLog(`States: ${data.metrics.states}`, 'info');
                    addTerminalLog(`Agents: ${data.metrics.agents}`, 'info');
                    addTerminalLog(`Gates: ${data.metrics.gates}`, 'info');
                    addTerminalLog(`Artifacts: ${data.metrics.artifacts || 0}`, 'info');
                }
            } catch (error) {
                addTerminalLog(`Error fetching status: ${error.message}`, 'error');
            }
        }

        async function initializeSystem() {
            addTerminalLog('Initializing Murphy System...', 'info');
            
            try {
                const initResponse = await fetch(`${API_BASE}/api/initialize`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({})
                });
                const initResult = await initResponse.json();
                
                if (initResult.success || initResult.message) {
                    addTerminalLog('\u2713 System initialized successfully', 'success');
                    
                    // Fetch actual data from backend
                    const [agentsResponse, statesResponse] = await Promise.all([
                        fetch(`${API_BASE}/api/agents`),
                        fetch(`${API_BASE}/api/states`)
                    ]);
                    
                    const agentsData = await agentsResponse.json();
                    const statesData = await statesResponse.json();
                    
                    // Update data
                    currentAgents = agentsData.agents || [];
                    currentStates = statesData.states || [];
                    currentGates = [];
                    
                    // Generate connections for agent graph
                    currentConnections = generateAgentConnections(currentAgents);
                    
                    addTerminalLog(`  Loaded ${currentAgents.length} agents`, 'info');
                    addTerminalLog(`  Loaded ${currentStates.length} states`, 'info');
                    
                    // Refresh UI
                    updateMetrics();
                    updateAgentGraph(currentAgents, currentConnections);
                    renderStateTree(currentStates);
                    updateProcessFlow(currentStates);
                    
                    // Connect to Socket.IO for real-time updates
                    connectWebSocket();
                } else {
                    addTerminalLog('\u2717 Initialization failed', 'error');
                }
            } catch (error) {
                console.error('Initialization error:', error);
                addTerminalLog(`\u2717 Error: ${error.message}`, 'error');
            }
        }

                addTerminalLog('No agents available. Initialize system first.', 'warning');
                return;
            }
            
            currentAgents.forEach(agent => {
                addTerminalLog(`  ${agent.id.padEnd(15)} - ${agent.name}`, 'info');
            });
        }

        async function listStates() {
            addTerminalLog('=== States ===', 'info');
            
            if (currentStates.length === 0) {
                addTerminalLog('No states available. Initialize system first.', 'warning');
                return;
            }
            
            currentStates.forEach(state => {
                addTerminalLog(`  ${state.id.padEnd(15)} - ${state.label} (${state.type})`, 'info');
            });
        }

        async function evolveStateCommand(stateId) {
            addTerminalLog(`Evolving state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/evolve`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    addTerminalLog(`✓ Evolved ${result.children.length} child states`, 'success');
                    
                    // Refresh state data
                    const statesResponse = await fetch(`${API_BASE}/api/states`);
                    const statesData = await statesResponse.json();
                    currentStates = statesData.states || [];
                    
                    // Update visualizations
                    renderStateTree(currentStates);
                    updateProcessFlow(currentStates);
                    updateMetrics();
                } else {
                    addTerminalLog('✗ Evolution failed', 'error');
                }
            } catch (error) {
                addTerminalLog(`✗ Error: ${error.message}`, 'error');
            }
        }

        async function regenerateStateCommand(stateId) {
            addTerminalLog(`Regenerating state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/regenerate`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    addTerminalLog(`✓ State regenerated with new confidence: ${result.confidence.toFixed(2)}`, 'success');
                    
                    // Refresh state data
                    const statesResponse = await fetch(`${API_BASE}/api/states`);
                    const statesData = await statesResponse.json();
                    currentStates = statesData.states || [];
                    
                    // Update visualizations
                    renderStateTree(currentStates);
                    updateProcessFlow(currentStates);
                    updateMetrics();
                } else {
                    addTerminalLog('✗ Regeneration failed', 'error');
                }
            } catch (error) {
                addTerminalLog(`✗ Error: ${error.message}`, 'error');
            }
        }

        async function rollbackStateCommand(stateId) {
            addTerminalLog(`Rolling back state: ${stateId}...`, 'info');
            
            try {
                const response = await fetch(`${API_BASE}/api/states/${stateId}/rollback`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    addTerminalLog(`✓ Rolled back to parent: ${result.parent_id}`, 'success');
                    
                    // Refresh state data
                    const statesResponse = await fetch(`${API_BASE}/api/states`);
                    const statesData = await statesResponse.json();
                    currentStates = statesData.states || [];
                    
                    // Update visualizations
                    renderStateTree(currentStates);
                    updateProcessFlow(currentStates);
                    updateMetrics();
                } else {
                    addTerminalLog('✗ Rollback failed', 'error');
                }
            } catch (error) {
                addTerminalLog(`✗ Error: ${error.message}`, 'error');
            }
        }

        function clearTerminal() {
            const terminalContent = document.getElementById('terminal-content');
            terminalContent.innerHTML = '';
            addTerminalLog('Terminal cleared', 'info');
        }

        // Old help functions removed - now using module-based handlers

        function addTerminalLog(message, type = 'info') {
            const terminalContent = document.getElementById('terminal-content');
            const line = document.createElement('div');
            line.className = `terminal-line ${type}`;
            line.textContent = message;
            terminalContent.appendChild(line);
            terminalContent.scrollTop = terminalContent.scrollHeight;
        }

        // ============================================
        // METRICS
        // ============================================
        
        function updateMetrics() {
            document.getElementById('metric-states').textContent = currentStates.length;
            document.getElementById('metric-agents').textContent = currentAgents.length;
            document.getElementById('metric-gates').textContent = 2; // Demo gates
            document.getElementById('metric-connections').textContent = currentConnections.length;
        }

        async function updateLLMStatus() {
            try {
                const response = await fetch(`${API_BASE}/api/status`);
                const data = await response.json();
                
                // Update Groq status
                const groqIndicator = document.getElementById('groq-status');
                if (data.llms.groq.status === 'active') {
                    groqIndicator.classList.add('active');
                }
                
                // Update Aristotle status
                const aristotleIndicator = document.getElementById('aristotle-status');
                if (data.llms.aristotle.status === 'active') {
                    aristotleIndicator.classList.add('active');
                }
                
                // Update Onboard status
                const onboardIndicator = document.getElementById('onboard-status');
                if (data.llms.onboard.status === 'available') {
                    onboardIndicator.classList.add('active');
                }
                
                addLog('✓ LLM status updated', 'success');
            } catch (error) {
                addLog(`✗ Error updating LLM status: ${error.message}`, 'error');
            }
        }

        // ============================================
        // TERMINAL
        // ============================================
        
        function addLog(message, type = 'info') {
            const terminalContent = document.getElementById('terminal-content');
            const timestamp = new Date().toLocaleTimeString();
            
            const line = document.createElement('div');
            line.className = `terminal-line ${type}`;
            line.textContent = message;
            
            terminalContent.appendChild(line);
            terminalContent.scrollTop = terminalContent.scrollHeight;
        }

        }); // End of DOMContentLoaded

        // ============================================
        // INITIALIZATION - Window Load Event
        // ============================================
        
        // Initialize visualizations on load (after all resources are loaded)
        window.addEventListener('load', function() {
            initAgentGraph();
            initProcessFlow();
            
            // Initialize Librarian Panel
            window.librarianPanel = new LibrarianPanel(API_BASE);
            window.librarianPanel.init();
            
            // Initialize Plan Review Panel
            window.planReviewPanel = new PlanReviewPanel(API_BASE);
            window.planReviewPanel.init();
            
            // Initialize Document Editor Panel
            window.documentEditorPanel = new DocumentEditorPanel(API_BASE);
            window.documentEditorPanel.init();
            
            // Initialize Artifact Panel
            if (typeof ArtifactPanel !== 'undefined') {
                ArtifactPanel.init();
                window.ArtifactPanel = ArtifactPanel;
            }
            
            // Initialize Shadow Agent Panel
            window.shadowAgentPanel = new ShadowAgentPanel();
            window.shadowAgentPanel.init();
            
            // Initialize Monitoring Panel
            window.monitoringPanel = new MonitoringPanel();
            window.monitoringPanel.init();
            
            // Make executeTerminalCommand available globally
            window.executeTerminalCommand = executeTerminalCommand;
            
            // Make addTerminalLog available globally for panels
            window.addTerminalLog = addLog;
            
            addLog('Murphy System v2.0 - Ready', 'info');
            addLog('System auto-initializing...', 'info');
            addLog('Type /librarian to open the intelligent guide', 'info');
            addLog('Type /plan or /document to work with plans and documents', 'info');
            
            // Auto-initialize system
            initializeSystem();
        });
        </script></body>
</html>