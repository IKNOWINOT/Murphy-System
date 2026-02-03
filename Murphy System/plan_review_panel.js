/**
 * Murphy System - Plan Review Panel Component
 * 
 * Integrated UI for reviewing, modifying, and approving plans
 * Triggers automatically in workflow when plans are generated
 */

class PlanReviewPanel {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.currentPlan = null;
        this.isProcessing = false;
    }

    /**
     * Initialize the Plan Review panel
     */
    init() {
        this.createPanel();
        this.attachEventListeners();
    }

    /**
     * Create the Plan Review panel HTML
     */
    createPanel() {
        const panelHTML = `
            <div id="plan-review-panel" class="system-panel" style="display: none;">
                <div class="panel-header">
                    <h2>📋 Plan Review</h2>
                    <button class="close-btn" onclick="planReviewPanel.close()">×</button>
                </div>
                
                <div class="panel-content">
                    <!-- Plan Info -->
                    <div id="plan-info" class="plan-info">
                        <div class="info-row">
                            <span class="info-label">Plan:</span>
                            <span id="plan-name" class="info-value">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Type:</span>
                            <span id="plan-type" class="info-value">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">State:</span>
                            <span id="plan-state" class="state-badge">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Version:</span>
                            <span id="plan-version" class="info-value">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Domains:</span>
                            <span id="plan-domains" class="info-value">-</span>
                        </div>
                    </div>

                    <!-- Plan Content Viewer -->
                    <div class="plan-viewer">
                        <div class="viewer-header">
                            <h3>Plan Content</h3>
                            <div class="viewer-controls">
                                <button class="control-btn" onclick="planReviewPanel.showVersionHistory()">
                                    📜 History
                                </button>
                                <button class="control-btn" onclick="planReviewPanel.showDiff()">
                                    🔄 Compare
                                </button>
                            </div>
                        </div>
                        <div id="plan-content" class="plan-content">
                            <!-- Plan content will be displayed here -->
                        </div>
                    </div>

                    <!-- Plan Steps -->
                    <div class="plan-steps">
                        <h3>Plan Steps</h3>
                        <div id="plan-steps-list" class="steps-list">
                            <!-- Steps will be listed here -->
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="plan-actions">
                        <button class="action-btn magnify-btn" onclick="planReviewPanel.showMagnifyDialog()">
                            🔍 Magnify
                        </button>
                        <button class="action-btn simplify-btn" onclick="planReviewPanel.simplify()">
                            ⚡ Simplify
                        </button>
                        <button class="action-btn edit-btn" onclick="planReviewPanel.enableEdit()">
                            ✏️ Edit
                        </button>
                        <button class="action-btn solidify-btn" onclick="planReviewPanel.solidify()">
                            🔒 Solidify
                        </button>
                        <button class="action-btn approve-btn" onclick="planReviewPanel.approve()">
                            ✅ Approve
                        </button>
                        <button class="action-btn reject-btn" onclick="planReviewPanel.showRejectDialog()">
                            ❌ Reject
                        </button>
                    </div>
                </div>
            </div>

            <!-- Magnify Dialog -->
            <div id="magnify-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content">
                    <h3>Magnify Plan with Domain</h3>
                    <p>Select a domain to add expertise:</p>
                    <select id="magnify-domain-select" class="domain-select">
                        <option value="business">Business</option>
                        <option value="engineering">Engineering</option>
                        <option value="financial">Financial</option>
                        <option value="legal">Legal</option>
                        <option value="operations">Operations</option>
                        <option value="marketing">Marketing</option>
                        <option value="hr">HR</option>
                        <option value="sales">Sales</option>
                        <option value="product">Product</option>
                    </select>
                    <div class="dialog-actions">
                        <button class="btn-primary" onclick="planReviewPanel.magnify()">Magnify</button>
                        <button class="btn-secondary" onclick="planReviewPanel.closeMagnifyDialog()">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Reject Dialog -->
            <div id="reject-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content">
                    <h3>Reject Plan</h3>
                    <p>Please provide a reason for rejection:</p>
                    <textarea id="reject-reason" class="reject-reason" placeholder="Enter reason..."></textarea>
                    <div class="dialog-actions">
                        <button class="btn-danger" onclick="planReviewPanel.reject()">Reject</button>
                        <button class="btn-secondary" onclick="planReviewPanel.closeRejectDialog()">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Version History Dialog -->
            <div id="version-history-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content large">
                    <h3>Version History</h3>
                    <div id="version-history-list" class="version-list">
                        <!-- Version history will be listed here -->
                    </div>
                    <div class="dialog-actions">
                        <button class="btn-secondary" onclick="planReviewPanel.closeVersionHistory()">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', panelHTML);
        this.addStyles();
    }

    /**
     * Add CSS styles for Plan Review panel
     */
    addStyles() {
        const styles = `
            <style>
                .plan-info {
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 15px;
                    margin-bottom: 15px;
                }
                
                .info-row {
                    display: flex;
                    justify-content: space-between;
                    padding: 5px 0;
                    border-bottom: 1px solid #222;
                }
                
                .info-row:last-child {
                    border-bottom: none;
                }
                
                .info-label {
                    font-weight: 600;
                    color: #00ff88;
                }
                
                .info-value {
                    color: #fff;
                }
                
                .state-badge {
                    padding: 3px 10px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    text-transform: uppercase;
                }
                
                .state-draft { background: #666; }
                .state-magnified { background: #0066cc; }
                .state-simplified { background: #cc6600; }
                .state-edited { background: #6600cc; }
                .state-solidified { background: #00cc66; }
                .state-approved { background: #00ff00; color: #000; }
                .state-rejected { background: #ff0000; }
                
                .plan-viewer {
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    margin-bottom: 15px;
                }
                
                .viewer-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 10px 15px;
                    border-bottom: 1px solid #333;
                }
                
                .viewer-header h3 {
                    margin: 0;
                    font-size: 14px;
                    color: #00ff88;
                }
                
                .viewer-controls {
                    display: flex;
                    gap: 8px;
                }
                
                .control-btn {
                    padding: 5px 10px;
                    background: #2a2a2a;
                    border: 1px solid #444;
                    border-radius: 3px;
                    color: #fff;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .control-btn:hover {
                    background: #3a3a3a;
                    border-color: #00ff88;
                }
                
                .plan-content {
                    padding: 15px;
                    max-height: 300px;
                    overflow-y: auto;
                    color: #fff;
                    line-height: 1.6;
                    white-space: pre-wrap;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                }
                
                .plan-steps {
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 15px;
                    margin-bottom: 15px;
                }
                
                .plan-steps h3 {
                    margin: 0 0 10px 0;
                    font-size: 14px;
                    color: #00ff88;
                }
                
                .steps-list {
                    max-height: 200px;
                    overflow-y: auto;
                }
                
                .step-item {
                    padding: 10px;
                    margin-bottom: 8px;
                    background: #1a1a1a;
                    border-left: 3px solid #00ff88;
                    border-radius: 3px;
                }
                
                .step-order {
                    display: inline-block;
                    width: 25px;
                    height: 25px;
                    line-height: 25px;
                    text-align: center;
                    background: #00ff88;
                    color: #000;
                    border-radius: 50%;
                    font-weight: 600;
                    font-size: 12px;
                    margin-right: 10px;
                }
                
                .step-command {
                    color: #00aaff;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    margin-bottom: 5px;
                }
                
                .step-description {
                    color: #ccc;
                    font-size: 12px;
                }
                
                .plan-actions {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }
                
                .action-btn {
                    flex: 1;
                    min-width: 120px;
                    padding: 12px 20px;
                    border: none;
                    border-radius: 4px;
                    font-weight: 600;
                    font-size: 13px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .magnify-btn {
                    background: #0066cc;
                    color: #fff;
                }
                
                .magnify-btn:hover {
                    background: #0055aa;
                }
                
                .simplify-btn {
                    background: #cc6600;
                    color: #fff;
                }
                
                .simplify-btn:hover {
                    background: #aa5500;
                }
                
                .edit-btn {
                    background: #6600cc;
                    color: #fff;
                }
                
                .edit-btn:hover {
                    background: #5500aa;
                }
                
                .solidify-btn {
                    background: #00cc66;
                    color: #000;
                }
                
                .solidify-btn:hover {
                    background: #00aa55;
                }
                
                .approve-btn {
                    background: #00ff00;
                    color: #000;
                }
                
                .approve-btn:hover {
                    background: #00cc00;
                }
                
                .reject-btn {
                    background: #ff0000;
                    color: #fff;
                }
                
                .reject-btn:hover {
                    background: #cc0000;
                }
                
                .action-btn:disabled {
                    background: #333;
                    color: #666;
                    cursor: not-allowed;
                }
                
                .modal-dialog {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.8);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 2000;
                }
                
                .dialog-content {
                    background: #1a1a1a;
                    border: 2px solid #00ff88;
                    border-radius: 8px;
                    padding: 25px;
                    min-width: 400px;
                    max-width: 600px;
                }
                
                .dialog-content.large {
                    min-width: 600px;
                    max-width: 800px;
                }
                
                .dialog-content h3 {
                    margin: 0 0 15px 0;
                    color: #00ff88;
                }
                
                .dialog-content p {
                    margin: 0 0 15px 0;
                    color: #ccc;
                }
                
                .domain-select {
                    width: 100%;
                    padding: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                    margin-bottom: 15px;
                }
                
                .reject-reason {
                    width: 100%;
                    min-height: 100px;
                    padding: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                    font-family: inherit;
                    resize: vertical;
                    margin-bottom: 15px;
                }
                
                .dialog-actions {
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                }
                
                .btn-primary {
                    padding: 10px 20px;
                    background: #00ff88;
                    border: none;
                    border-radius: 4px;
                    color: #000;
                    font-weight: 600;
                    cursor: pointer;
                }
                
                .btn-primary:hover {
                    background: #00cc6a;
                }
                
                .btn-secondary {
                    padding: 10px 20px;
                    background: #333;
                    border: none;
                    border-radius: 4px;
                    color: #fff;
                    font-weight: 600;
                    cursor: pointer;
                }
                
                .btn-secondary:hover {
                    background: #444;
                }
                
                .btn-danger {
                    padding: 10px 20px;
                    background: #ff0000;
                    border: none;
                    border-radius: 4px;
                    color: #fff;
                    font-weight: 600;
                    cursor: pointer;
                }
                
                .btn-danger:hover {
                    background: #cc0000;
                }
                
                .version-list {
                    max-height: 400px;
                    overflow-y: auto;
                }
                
                .version-item {
                    padding: 15px;
                    margin-bottom: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                }
                
                .version-header {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }
                
                .version-number {
                    font-weight: 600;
                    color: #00ff88;
                }
                
                .version-timestamp {
                    color: #666;
                    font-size: 12px;
                }
                
                .version-summary {
                    color: #ccc;
                    font-size: 13px;
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.close();
                this.closeMagnifyDialog();
                this.closeRejectDialog();
                this.closeVersionHistory();
            }
        });
    }

    /**
     * Open panel with a plan
     */
    async open(planId) {
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${planId}`);
            const data = await response.json();
            
            if (data.plan) {
                this.currentPlan = data.plan;
                this.displayPlan();
                document.getElementById('plan-review-panel').style.display = 'flex';
            }
        } catch (error) {
            console.error('Error loading plan:', error);
            alert('Failed to load plan');
        }
    }

    /**
     * Display plan in the panel
     */
    displayPlan() {
        if (!this.currentPlan) return;
        
        // Update plan info
        document.getElementById('plan-name').textContent = this.currentPlan.name;
        document.getElementById('plan-type').textContent = this.currentPlan.plan_type;
        
        const stateBadge = document.getElementById('plan-state');
        stateBadge.textContent = this.currentPlan.current_state;
        stateBadge.className = `state-badge state-${this.currentPlan.current_state}`;
        
        document.getElementById('plan-version').textContent = `v${this.currentPlan.current_version}`;
        document.getElementById('plan-domains').textContent = this.currentPlan.domains.join(', ') || 'None';
        
        // Display current version content
        const currentVersion = this.currentPlan.versions[this.currentPlan.current_version - 1];
        document.getElementById('plan-content').textContent = currentVersion.content;
        
        // Display steps
        const stepsList = document.getElementById('plan-steps-list');
        stepsList.innerHTML = '';
        
        currentVersion.steps.forEach((step, index) => {
            const stepDiv = document.createElement('div');
            stepDiv.className = 'step-item';
            stepDiv.innerHTML = `
                <span class="step-order">${index + 1}</span>
                <div class="step-command">${step.command}</div>
                <div class="step-description">${step.description}</div>
            `;
            stepsList.appendChild(stepDiv);
        });
        
        // Update button states
        this.updateButtonStates();
    }

    /**
     * Update button states based on plan state
     */
    updateButtonStates() {
        const state = this.currentPlan.current_state;
        
        // Solidify button only enabled if not already solidified
        document.querySelector('.solidify-btn').disabled = (state === 'solidified' || state === 'approved');
        
        // Approve button only enabled if solidified
        document.querySelector('.approve-btn').disabled = (state !== 'solidified');
    }

    /**
     * Show magnify dialog
     */
    showMagnifyDialog() {
        document.getElementById('magnify-dialog').style.display = 'flex';
    }

    /**
     * Close magnify dialog
     */
    closeMagnifyDialog() {
        document.getElementById('magnify-dialog').style.display = 'none';
    }

    /**
     * Magnify plan with domain
     */
    async magnify() {
        const domain = document.getElementById('magnify-domain-select').value;
        this.closeMagnifyDialog();
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/magnify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Plan magnified with ${domain} domain`, 'success');
                }
            } else {
                alert('Failed to magnify plan: ' + data.error);
            }
        } catch (error) {
            console.error('Magnify error:', error);
            alert('Failed to magnify plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Simplify plan
     */
    async simplify() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/simplify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog('✓ Plan simplified', 'success');
                }
            } else {
                alert('Failed to simplify plan: ' + data.error);
            }
        } catch (error) {
            console.error('Simplify error:', error);
            alert('Failed to simplify plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Enable edit mode
     */
    enableEdit() {
        const contentDiv = document.getElementById('plan-content');
        const currentContent = contentDiv.textContent;
        
        contentDiv.innerHTML = `
            <textarea id="plan-edit-textarea" style="width: 100%; min-height: 250px; background: #000; color: #fff; border: 1px solid #00ff88; padding: 10px; font-family: 'Courier New', monospace; font-size: 13px;">${currentContent}</textarea>
            <div style="margin-top: 10px; display: flex; gap: 10px;">
                <button onclick="planReviewPanel.saveEdit()" style="padding: 8px 16px; background: #00ff88; color: #000; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">Save</button>
                <button onclick="planReviewPanel.cancelEdit()" style="padding: 8px 16px; background: #333; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">Cancel</button>
            </div>
        `;
    }

    /**
     * Save edit
     */
    async saveEdit() {
        const textarea = document.getElementById('plan-edit-textarea');
        const newContent = textarea.value;
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: newContent,
                    summary: 'User modifications'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog('✓ Plan updated', 'success');
                }
            } else {
                alert('Failed to save plan: ' + data.error);
            }
        } catch (error) {
            console.error('Save error:', error);
            alert('Failed to save plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Cancel edit
     */
    cancelEdit() {
        this.displayPlan();
    }

    /**
     * Solidify plan
     */
    async solidify() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/solidify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog('✓ Plan solidified and ready for execution', 'success');
                }
            } else {
                alert('Failed to solidify plan: ' + data.error);
            }
        } catch (error) {
            console.error('Solidify error:', error);
            alert('Failed to solidify plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Approve plan
     */
    async approve() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: 'user' })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog('✓ Plan approved and ready for execution', 'success');
                }
                // Close panel after approval
                setTimeout(() => this.close(), 2000);
            } else {
                alert('Failed to approve plan: ' + data.error);
            }
        } catch (error) {
            console.error('Approve error:', error);
            alert('Failed to approve plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Show reject dialog
     */
    showRejectDialog() {
        document.getElementById('reject-dialog').style.display = 'flex';
    }

    /**
     * Close reject dialog
     */
    closeRejectDialog() {
        document.getElementById('reject-dialog').style.display = 'none';
        document.getElementById('reject-reason').value = '';
    }

    /**
     * Reject plan
     */
    async reject() {
        const reason = document.getElementById('reject-reason').value.trim();
        
        if (!reason) {
            alert('Please provide a reason for rejection');
            return;
        }
        
        this.closeRejectDialog();
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/plans/${this.currentPlan.id}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason, user_id: 'user' })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentPlan = data.plan;
                this.displayPlan();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✗ Plan rejected: ${reason}`, 'error');
                }
                // Close panel after rejection
                setTimeout(() => this.close(), 2000);
            } else {
                alert('Failed to reject plan: ' + data.error);
            }
        } catch (error) {
            console.error('Reject error:', error);
            alert('Failed to reject plan');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Show version history
     */
    showVersionHistory() {
        const historyList = document.getElementById('version-history-list');
        historyList.innerHTML = '';
        
        this.currentPlan.versions.forEach((version, index) => {
            const versionDiv = document.createElement('div');
            versionDiv.className = 'version-item';
            versionDiv.innerHTML = `
                <div class="version-header">
                    <span class="version-number">Version ${version.version}</span>
                    <span class="version-timestamp">${new Date(version.timestamp).toLocaleString()}</span>
                </div>
                <div class="version-summary">${version.changes_summary || 'No summary'}</div>
            `;
            historyList.appendChild(versionDiv);
        });
        
        document.getElementById('version-history-dialog').style.display = 'flex';
    }

    /**
     * Close version history
     */
    closeVersionHistory() {
        document.getElementById('version-history-dialog').style.display = 'none';
    }

    /**
     * Show diff between versions
     */
    showDiff() {
        // TODO: Implement diff viewer
        alert('Diff viewer coming soon!');
    }

    /**
     * Close panel
     */
    close() {
        document.getElementById('plan-review-panel').style.display = 'none';
        this.currentPlan = null;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanReviewPanel;
}