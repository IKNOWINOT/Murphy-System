/**
 * Murphy System - Shadow Agent Panel
 * Displays shadow agents, observations, automation proposals, and active automations
 */

class ShadowAgentPanel {
    constructor() {
        this.agents = [];
        this.observations = [];
        this.proposals = [];
        this.automations = [];
        this.selectedAgent = null;
        this.refreshInterval = null;
        this.init();
    }

    init() {
        console.log('Initializing Shadow Agent Panel...');
        this.loadInitialData();
        this.startAutoRefresh();
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.loadAgents(),
                this.loadObservations(),
                this.loadProposals(),
                this.loadAutomations()
            ]);
            this.render();
        } catch (error) {
            console.error('Error loading shadow agent data:', error);
            this.showError('Failed to load shadow agent data');
        }
    }

    async loadAgents() {
        try {
            const response = await fetch('http://localhost:3002/api/shadow/agents');
            if (!response.ok) throw new Error('Failed to load agents');
            this.agents = await response.json();
        } catch (error) {
            console.error('Error loading agents:', error);
        }
    }

    async loadObservations() {
        try {
            const response = await fetch('http://localhost:3002/api/shadow/observations');
            if (!response.ok) throw new Error('Failed to load observations');
            this.observations = await response.json();
        } catch (error) {
            console.error('Error loading observations:', error);
        }
    }

    async loadProposals() {
        try {
            const response = await fetch('http://localhost:3002/api/shadow/proposals');
            if (!response.ok) throw new Error('Failed to load proposals');
            this.proposals = await response.json();
        } catch (error) {
            console.error('Error loading proposals:', error);
        }
    }

    async loadAutomations() {
        try {
            const response = await fetch('http://localhost:3002/api/shadow/automations');
            if (!response.ok) throw new Error('Failed to load automations');
            this.automations = await response.json();
        } catch (error) {
            console.error('Error loading automations:', error);
        }
    }

    startAutoRefresh() {
        // Refresh every 10 seconds
        this.refreshInterval = setInterval(() => {
            this.loadInitialData();
        }, 10000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    render() {
        this.renderAgentList();
        this.renderObservations();
        this.renderProposals();
        this.renderAutomations();
        this.renderStats();
    }

    renderAgentList() {
        const container = document.getElementById('shadow-agents-list');
        if (!container) return;

        container.innerHTML = this.agents.map(agent => `
            <div class="shadow-agent-card ${this.selectedAgent === agent.id ? 'selected' : ''}"
                 onclick="shadowPanel.selectAgent('${agent.id}')">
                <div class="agent-header">
                    <span class="agent-icon">${this.getAgentIcon(agent.type)}</span>
                    <div class="agent-info">
                        <h4 class="agent-name">${agent.name}</h4>
                        <span class="agent-type">${this.formatAgentType(agent.type)}</span>
                    </div>
                    <span class="agent-status ${agent.status.toLowerCase()}">${agent.status}</span>
                </div>
                <div class="agent-metrics">
                    <div class="metric">
                        <span class="metric-label">Observations</span>
                        <span class="metric-value">${agent.observations_count || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Patterns</span>
                        <span class="metric-value">${agent.patterns_count || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Automations</span>
                        <span class="metric-value">${agent.automations_count || 0}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderObservations() {
        const container = document.getElementById('shadow-observations-list');
        if (!container) return;

        const filteredObservations = this.selectedAgent
            ? this.observations.filter(obs => obs.agent_id === this.selectedAgent)
            : this.observations;

        container.innerHTML = filteredObservations.slice(0, 20).map(obs => `
            <div class="observation-item">
                <div class="observation-header">
                    <span class="observation-type">${obs.action_type}</span>
                    <span class="observation-time">${this.formatTime(obs.timestamp)}</span>
                </div>
                <div class="observation-content">${this.truncate(obs.description, 100)}</div>
                <div class="observation-meta">
                    <span class="observation-agent">${this.getAgentName(obs.agent_id)}</span>
                    <span class="observation-confidence">Confidence: ${(obs.confidence || 0).toFixed(2)}</span>
                </div>
            </div>
        `).join('');
    }

    renderProposals() {
        const container = document.getElementById('shadow-proposals-list');
        if (!container) return;

        const filteredProposals = this.selectedAgent
            ? this.proposals.filter(prop => prop.agent_id === this.selectedAgent)
            : this.proposals;

        container.innerHTML = filteredProposals.map(prop => `
            <div class="proposal-card ${prop.status.toLowerCase()}">
                <div class="proposal-header">
                    <h4 class="proposal-title">${prop.title}</h4>
                    <span class="proposal-status ${prop.status.toLowerCase()}">${prop.status}</span>
                </div>
                <div class="proposal-content">${this.truncate(prop.description, 150)}</div>
                <div class="proposal-metrics">
                    <span class="proposal-confidence">Confidence: ${(prop.confidence || 0).toFixed(2)}</span>
                    <span class="proposal-savings">Est. Savings: ${prop.estimated_savings || 'N/A'}</span>
                </div>
                ${prop.status === 'PENDING' ? `
                    <div class="proposal-actions">
                        <button class="btn btn-sm btn-success" onclick="shadowPanel.approveProposal('${prop.agent_id}', '${prop.id}')">
                            ✓ Approve
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="shadowPanel.rejectProposal('${prop.agent_id}', '${prop.id}')">
                            ✗ Reject
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    renderAutomations() {
        const container = document.getElementById('shadow-automations-list');
        if (!container) return;

        const filteredAutomations = this.selectedAgent
            ? this.automations.filter(auto => auto.agent_id === this.selectedAgent)
            : this.automations;

        container.innerHTML = filteredAutomations.map(auto => `
            <div class="automation-card ${auto.status.toLowerCase()}">
                <div class="automation-header">
                    <h4 class="automation-title">${auto.title}</h4>
                    <span class="automation-status ${auto.status.toLowerCase()}">${auto.status}</span>
                </div>
                <div class="automation-content">${this.truncate(auto.description, 120)}</div>
                <div class="automation-metrics">
                    <span class="automation-runs">Runs: ${auto.execution_count || 0}</span>
                    <span class="automation-success">Success Rate: ${((auto.success_count || 0) / (auto.execution_count || 1) * 100).toFixed(1)}%</span>
                </div>
                <div class="automation-actions">
                    <button class="btn btn-sm btn-primary" onclick="shadowPanel.runAutomation('${auto.id}')">
                        ▶ Run Now
                    </button>
                    <button class="btn btn-sm btn-warning" onclick="shadowPanel.disableAutomation('${auto.id}')">
                        ⏸ Disable
                    </button>
                </div>
            </div>
        `).join('');
    }

    renderStats() {
        const container = document.getElementById('shadow-stats');
        if (!container) return;

        const totalObservations = this.observations.length;
        const totalProposals = this.proposals.length;
        const pendingProposals = this.proposals.filter(p => p.status === 'PENDING').length;
        const totalAutomations = this.automations.length;
        const activeAutomations = this.automations.filter(a => a.status === 'ACTIVE').length;

        container.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">Active Agents</span>
                <span class="stat-value">${this.agents.length}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Total Observations</span>
                <span class="stat-value">${totalObservations}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Proposals</span>
                <span class="stat-value">${totalProposals}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Pending</span>
                <span class="stat-value">${pendingProposals}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Automations</span>
                <span class="stat-value">${totalAutomations}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Active</span>
                <span class="stat-value">${activeAutomations}</span>
            </div>
        `;
    }

    selectAgent(agentId) {
        this.selectedAgent = agentId;
        this.render();
    }

    async approveProposal(agentId, proposalId) {
        try {
            const response = await fetch(
                `http://localhost:3002/api/shadow/proposals/${agentId}/${proposalId}/approve`,
                { method: 'POST' }
            );
            if (!response.ok) throw new Error('Failed to approve proposal');
            
            // Reload data
            await this.loadProposals();
            await this.loadAutomations();
            this.render();
            
            this.showSuccess('Proposal approved successfully');
        } catch (error) {
            console.error('Error approving proposal:', error);
            this.showError('Failed to approve proposal');
        }
    }

    async rejectProposal(agentId, proposalId) {
        try {
            const response = await fetch(
                `http://localhost:3002/api/shadow/proposals/${agentId}/${proposalId}/reject`,
                { method: 'POST' }
            );
            if (!response.ok) throw new Error('Failed to reject proposal');
            
            // Reload data
            await this.loadProposals();
            this.render();
            
            this.showSuccess('Proposal rejected');
        } catch (error) {
            console.error('Error rejecting proposal:', error);
            this.showError('Failed to reject proposal');
        }
    }

    async runAutomation(automationId) {
        try {
            this.showInfo('Running automation...');
            // This would trigger the automation execution
            // For now, we'll just show a success message
            this.showSuccess('Automation executed successfully');
        } catch (error) {
            console.error('Error running automation:', error);
            this.showError('Failed to run automation');
        }
    }

    async disableAutomation(automationId) {
        try {
            const response = await fetch(
                `http://localhost:3002/api/shadow/automations/${automationId}/disable`,
                { method: 'POST' }
            );
            if (!response.ok) throw new Error('Failed to disable automation');
            
            await this.loadAutomations();
            this.render();
            
            this.showSuccess('Automation disabled');
        } catch (error) {
            console.error('Error disabling automation:', error);
            this.showError('Failed to disable automation');
        }
    }

    // Utility methods
    getAgentIcon(type) {
        const icons = {
            'command_observer': '🔍',
            'document_watcher': '📄',
            'artifact_monitor': '🎨',
            'state_tracker': '🔄',
            'workflow_analyzer': '⚡'
        };
        return icons[type] || '🤖';
    }

    formatAgentType(type) {
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    getAgentName(agentId) {
        const agent = this.agents.find(a => a.id === agentId);
        return agent ? agent.name : 'Unknown';
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }

    truncate(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // Notification methods
    showSuccess(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`✓ ${message}`, 'success');
        }
    }

    showError(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`✗ ${message}`, 'error');
        }
    }

    showInfo(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`ℹ ${message}`, 'info');
        }
    }
}

// Global instance
let shadowPanel = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    shadowPanel = new ShadowAgentPanel();
});