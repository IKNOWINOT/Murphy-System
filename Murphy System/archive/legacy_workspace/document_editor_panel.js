/**
 * Murphy System - Document Editor Panel Component
 * 
 * Integrated UI for creating, editing, and managing living documents
 * Triggers automatically in workflow when documents are created/edited
 */

class DocumentEditorPanel {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.currentDocument = null;
        this.isProcessing = false;
        this.isEditing = false;
    }

    /**
     * Initialize the Document Editor panel
     */
    init() {
        this.createPanel();
        this.attachEventListeners();
    }

    /**
     * Create the Document Editor panel HTML
     */
    createPanel() {
        const panelHTML = `
            <div id="document-editor-panel" class="system-panel" style="display: none;">
                <div class="panel-header">
                    <h2>📄 Living Document Editor</h2>
                    <button class="close-btn" onclick="documentEditorPanel.close()">×</button>
                </div>
                
                <div class="panel-content">
                    <!-- Document Info -->
                    <div id="document-info" class="document-info">
                        <div class="info-row">
                            <span class="info-label">Document:</span>
                            <span id="doc-name" class="info-value">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Type:</span>
                            <span id="doc-type" class="info-value">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">State:</span>
                            <span id="doc-state" class="state-badge">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Expertise Depth:</span>
                            <div class="depth-indicator">
                                <div id="depth-bar" class="depth-bar"></div>
                                <span id="depth-value" class="depth-value">0</span>
                            </div>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Domains:</span>
                            <div id="doc-domains" class="domain-tags"></div>
                        </div>
                    </div>

                    <!-- Document Content Editor -->
                    <div class="document-editor">
                        <div class="editor-header">
                            <h3>Document Content</h3>
                            <div class="editor-controls">
                                <button class="control-btn" onclick="documentEditorPanel.showVersionHistory()">
                                    📜 History
                                </button>
                                <button class="control-btn" onclick="documentEditorPanel.showTemplates()">
                                    📋 Templates
                                </button>
                            </div>
                        </div>
                        <div id="document-content" class="document-content" contenteditable="false">
                            <!-- Document content will be displayed here -->
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="document-actions">
                        <button class="action-btn magnify-btn" onclick="documentEditorPanel.showMagnifyDialog()">
                            🔍 Magnify
                        </button>
                        <button class="action-btn simplify-btn" onclick="documentEditorPanel.simplify()">
                            ⚡ Simplify
                        </button>
                        <button class="action-btn edit-btn" onclick="documentEditorPanel.toggleEdit()">
                            ✏️ Edit
                        </button>
                        <button class="action-btn solidify-btn" onclick="documentEditorPanel.solidify()">
                            🔒 Solidify
                        </button>
                        <button class="action-btn template-btn" onclick="documentEditorPanel.showSaveTemplateDialog()">
                            💾 Save as Template
                        </button>
                    </div>
                </div>
            </div>

            <!-- Magnify Dialog -->
            <div id="doc-magnify-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content">
                    <h3>Magnify Document with Domain</h3>
                    <p>Select a domain to add expertise:</p>
                    <select id="doc-magnify-domain-select" class="domain-select">
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
                        <button class="btn-primary" onclick="documentEditorPanel.magnify()">Magnify</button>
                        <button class="btn-secondary" onclick="documentEditorPanel.closeMagnifyDialog()">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Save Template Dialog -->
            <div id="save-template-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content">
                    <h3>Save as Template</h3>
                    <p>Enter a name for this template:</p>
                    <input type="text" id="template-name-input" class="template-name-input" placeholder="Template name...">
                    <div class="dialog-actions">
                        <button class="btn-primary" onclick="documentEditorPanel.saveAsTemplate()">Save</button>
                        <button class="btn-secondary" onclick="documentEditorPanel.closeSaveTemplateDialog()">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Templates Dialog -->
            <div id="templates-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content large">
                    <h3>Document Templates</h3>
                    <div id="templates-list" class="templates-list">
                        <!-- Templates will be listed here -->
                    </div>
                    <div class="dialog-actions">
                        <button class="btn-secondary" onclick="documentEditorPanel.closeTemplates()">Close</button>
                    </div>
                </div>
            </div>

            <!-- Version History Dialog -->
            <div id="doc-version-history-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content large">
                    <h3>Version History</h3>
                    <div id="doc-version-history-list" class="version-list">
                        <!-- Version history will be listed here -->
                    </div>
                    <div class="dialog-actions">
                        <button class="btn-secondary" onclick="documentEditorPanel.closeVersionHistory()">Close</button>
                    </div>
                </div>
            </div>

            <!-- Prompts Dialog -->
            <div id="prompts-dialog" class="modal-dialog" style="display: none;">
                <div class="dialog-content large">
                    <h3>Generative Prompts</h3>
                    <p>Document has been solidified into the following prompts:</p>
                    <div id="prompts-list" class="prompts-list">
                        <!-- Prompts will be listed here -->
                    </div>
                    <div class="dialog-actions">
                        <button class="btn-primary" onclick="documentEditorPanel.executePrompts()">Execute Prompts</button>
                        <button class="btn-secondary" onclick="documentEditorPanel.closePrompts()">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', panelHTML);
        this.addStyles();
    }

    /**
     * Add CSS styles for Document Editor panel
     */
    addStyles() {
        const styles = `
            <style>
                .document-info {
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 15px;
                    margin-bottom: 15px;
                }
                
                .depth-indicator {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    flex: 1;
                }
                
                .depth-bar {
                    flex: 1;
                    height: 20px;
                    background: #1a1a1a;
                    border: 1px solid #333;
                    border-radius: 10px;
                    position: relative;
                    overflow: hidden;
                }
                
                .depth-bar::after {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    bottom: 0;
                    background: linear-gradient(90deg, #00ff88 0%, #00cc6a 100%);
                    transition: width 0.3s ease;
                }
                
                .depth-value {
                    font-weight: 600;
                    color: #00ff88;
                    min-width: 30px;
                    text-align: right;
                }
                
                .domain-tags {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 5px;
                }
                
                .domain-tag {
                    padding: 3px 10px;
                    background: #2a2a2a;
                    border: 1px solid #00ff88;
                    border-radius: 12px;
                    font-size: 11px;
                    color: #00ff88;
                }
                
                .document-editor {
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    margin-bottom: 15px;
                }
                
                .editor-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 10px 15px;
                    border-bottom: 1px solid #333;
                }
                
                .editor-header h3 {
                    margin: 0;
                    font-size: 14px;
                    color: #00ff88;
                }
                
                .editor-controls {
                    display: flex;
                    gap: 8px;
                }
                
                .document-content {
                    padding: 15px;
                    min-height: 300px;
                    max-height: 400px;
                    overflow-y: auto;
                    color: #fff;
                    line-height: 1.6;
                    white-space: pre-wrap;
                    font-family: 'Georgia', serif;
                    font-size: 14px;
                }
                
                .document-content[contenteditable="true"] {
                    border: 2px solid #00ff88;
                    background: #0f0f0f;
                }
                
                .document-actions {
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }
                
                .template-btn {
                    background: #cc00cc;
                    color: #fff;
                }
                
                .template-btn:hover {
                    background: #aa00aa;
                }
                
                .template-name-input {
                    width: 100%;
                    padding: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                    margin-bottom: 15px;
                }
                
                .templates-list {
                    max-height: 400px;
                    overflow-y: auto;
                }
                
                .template-item {
                    padding: 15px;
                    margin-bottom: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .template-item:hover {
                    border-color: #00ff88;
                    background: #1a1a1a;
                }
                
                .template-name {
                    font-weight: 600;
                    color: #00ff88;
                    margin-bottom: 5px;
                }
                
                .template-type {
                    color: #666;
                    font-size: 12px;
                }
                
                .prompts-list {
                    max-height: 400px;
                    overflow-y: auto;
                }
                
                .prompt-item {
                    padding: 15px;
                    margin-bottom: 10px;
                    background: #0a0a0a;
                    border-left: 3px solid #00ff88;
                    border-radius: 4px;
                }
                
                .prompt-swarm-type {
                    display: inline-block;
                    padding: 3px 10px;
                    background: #2a2a2a;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    color: #00ff88;
                    margin-bottom: 8px;
                }
                
                .prompt-text {
                    color: #ccc;
                    font-size: 13px;
                    line-height: 1.5;
                }
                
                .prompt-tokens {
                    color: #666;
                    font-size: 11px;
                    margin-top: 5px;
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
                if (this.isEditing) {
                    this.cancelEdit();
                } else {
                    this.close();
                }
                this.closeMagnifyDialog();
                this.closeSaveTemplateDialog();
                this.closeTemplates();
                this.closeVersionHistory();
                this.closePrompts();
            }
        });
    }

    /**
     * Open panel with a document
     */
    async open(docId) {
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${docId}`);
            const data = await response.json();
            
            if (data.document) {
                this.currentDocument = data.document;
                this.displayDocument();
                document.getElementById('document-editor-panel').style.display = 'flex';
            }
        } catch (error) {
            console.error('Error loading document:', error);
            alert('Failed to load document');
        }
    }

    /**
     * Create new document
     */
    async createNew(docType = 'custom', name = 'New Document') {
        try {
            const response = await fetch(`${this.apiBase}/api/documents`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    doc_type: docType,
                    description: `New ${docType} document`,
                    content: 'Start writing your document here...',
                    domains: [],
                    tags: []
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                document.getElementById('document-editor-panel').style.display = 'flex';
                this.toggleEdit(); // Start in edit mode
            }
        } catch (error) {
            console.error('Error creating document:', error);
            alert('Failed to create document');
        }
    }

    /**
     * Display document in the panel
     */
    displayDocument() {
        if (!this.currentDocument) return;
        
        // Update document info
        document.getElementById('doc-name').textContent = this.currentDocument.name;
        document.getElementById('doc-type').textContent = this.currentDocument.doc_type;
        
        const stateBadge = document.getElementById('doc-state');
        stateBadge.textContent = this.currentDocument.current_state;
        stateBadge.className = `state-badge state-${this.currentDocument.current_state}`;
        
        // Update depth indicator
        const depth = this.currentDocument.expertise_depth;
        const maxDepth = 5; // Assume max depth of 5
        const percentage = Math.min((depth / maxDepth) * 100, 100);
        
        const depthBar = document.getElementById('depth-bar');
        depthBar.style.setProperty('--depth-percentage', `${percentage}%`);
        depthBar.style.width = `${percentage}%`;
        
        document.getElementById('depth-value').textContent = depth;
        
        // Update domain tags
        const domainsDiv = document.getElementById('doc-domains');
        domainsDiv.innerHTML = '';
        
        if (this.currentDocument.domains.length === 0) {
            domainsDiv.innerHTML = '<span style="color: #666;">No domains</span>';
        } else {
            this.currentDocument.domains.forEach(domain => {
                const tag = document.createElement('span');
                tag.className = 'domain-tag';
                tag.textContent = domain;
                domainsDiv.appendChild(tag);
            });
        }
        
        // Display current version content
        const currentVersion = this.currentDocument.versions[this.currentDocument.current_version - 1];
        const contentDiv = document.getElementById('document-content');
        contentDiv.textContent = currentVersion.content;
        contentDiv.contentEditable = false;
        
        // Update edit button text
        const editBtn = document.querySelector('.edit-btn');
        editBtn.textContent = '✏️ Edit';
        this.isEditing = false;
    }

    /**
     * Show magnify dialog
     */
    showMagnifyDialog() {
        document.getElementById('doc-magnify-dialog').style.display = 'flex';
    }

    /**
     * Close magnify dialog
     */
    closeMagnifyDialog() {
        document.getElementById('doc-magnify-dialog').style.display = 'none';
    }

    /**
     * Magnify document with domain
     */
    async magnify() {
        const domain = document.getElementById('doc-magnify-domain-select').value;
        this.closeMagnifyDialog();
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${this.currentDocument.id}/magnify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Document magnified with ${domain} domain (depth: ${this.currentDocument.expertise_depth})`, 'success');
                }
            } else {
                alert('Failed to magnify document: ' + data.error);
            }
        } catch (error) {
            console.error('Magnify error:', error);
            alert('Failed to magnify document');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Simplify document
     */
    async simplify() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${this.currentDocument.id}/simplify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Document simplified (depth: ${this.currentDocument.expertise_depth})`, 'success');
                }
            } else {
                alert('Failed to simplify document: ' + data.error);
            }
        } catch (error) {
            console.error('Simplify error:', error);
            alert('Failed to simplify document');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Toggle edit mode
     */
    toggleEdit() {
        const contentDiv = document.getElementById('document-content');
        const editBtn = document.querySelector('.edit-btn');
        
        if (this.isEditing) {
            // Save changes
            this.saveEdit();
        } else {
            // Enable editing
            contentDiv.contentEditable = true;
            contentDiv.focus();
            editBtn.textContent = '💾 Save';
            this.isEditing = true;
        }
    }

    /**
     * Save edit
     */
    async saveEdit() {
        const contentDiv = document.getElementById('document-content');
        const newContent = contentDiv.textContent;
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${this.currentDocument.id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: newContent,
                    summary: 'User modifications'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                if (window.addTerminalLog) {
                    window.addTerminalLog('✓ Document updated', 'success');
                }
            } else {
                alert('Failed to save document: ' + data.error);
            }
        } catch (error) {
            console.error('Save error:', error);
            alert('Failed to save document');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Cancel edit
     */
    cancelEdit() {
        this.displayDocument();
    }

    /**
     * Solidify document
     */
    async solidify() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${this.currentDocument.id}/solidify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Document solidified into ${data.prompts.length} generative prompts`, 'success');
                }
                // Show prompts dialog
                this.showPrompts(data.prompts);
            } else {
                alert('Failed to solidify document: ' + data.error);
            }
        } catch (error) {
            console.error('Solidify error:', error);
            alert('Failed to solidify document');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Show prompts dialog
     */
    showPrompts(prompts) {
        const promptsList = document.getElementById('prompts-list');
        promptsList.innerHTML = '';
        
        prompts.forEach((prompt, index) => {
            const promptDiv = document.createElement('div');
            promptDiv.className = 'prompt-item';
            promptDiv.innerHTML = `
                <span class="prompt-swarm-type">${prompt.swarm_type}</span>
                <div class="prompt-text">${prompt.prompt_text}</div>
                <div class="prompt-tokens">Estimated tokens: ${prompt.estimated_tokens}</div>
            `;
            promptsList.appendChild(promptDiv);
        });
        
        document.getElementById('prompts-dialog').style.display = 'flex';
    }

    /**
     * Close prompts dialog
     */
    closePrompts() {
        document.getElementById('prompts-dialog').style.display = 'none';
    }

    /**
     * Execute prompts (trigger swarm execution)
     */
    executePrompts() {
        this.closePrompts();
        if (window.addTerminalLog) {
            window.addTerminalLog('🚀 Executing generative prompts via swarms...', 'info');
            window.addTerminalLog('(Swarm execution will be implemented in Phase 4)', 'info');
        }
        // TODO: Integrate with swarm execution system in Phase 4
    }

    /**
     * Show save template dialog
     */
    showSaveTemplateDialog() {
        document.getElementById('save-template-dialog').style.display = 'flex';
        document.getElementById('template-name-input').value = `${this.currentDocument.name} Template`;
    }

    /**
     * Close save template dialog
     */
    closeSaveTemplateDialog() {
        document.getElementById('save-template-dialog').style.display = 'none';
    }

    /**
     * Save as template
     */
    async saveAsTemplate() {
        const templateName = document.getElementById('template-name-input').value.trim();
        
        if (!templateName) {
            alert('Please enter a template name');
            return;
        }
        
        this.closeSaveTemplateDialog();
        
        if (this.isProcessing) return;
        this.isProcessing = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/documents/${this.currentDocument.id}/template`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: templateName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Template '${templateName}' created`, 'success');
                }
            } else {
                alert('Failed to save template: ' + data.error);
            }
        } catch (error) {
            console.error('Save template error:', error);
            alert('Failed to save template');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Show templates dialog
     */
    async showTemplates() {
        try {
            const response = await fetch(`${this.apiBase}/api/templates`);
            const data = await response.json();
            
            const templatesList = document.getElementById('templates-list');
            templatesList.innerHTML = '';
            
            if (data.templates.length === 0) {
                templatesList.innerHTML = '<p style="color: #666; text-align: center; padding: 20px;">No templates available</p>';
            } else {
                data.templates.forEach(template => {
                    const templateDiv = document.createElement('div');
                    templateDiv.className = 'template-item';
                    templateDiv.onclick = () => this.createFromTemplate(template.id, template.name);
                    templateDiv.innerHTML = `
                        <div class="template-name">${template.name}</div>
                        <div class="template-type">${template.doc_type}</div>
                    `;
                    templatesList.appendChild(templateDiv);
                });
            }
            
            document.getElementById('templates-dialog').style.display = 'flex';
        } catch (error) {
            console.error('Load templates error:', error);
            alert('Failed to load templates');
        }
    }

    /**
     * Close templates dialog
     */
    closeTemplates() {
        document.getElementById('templates-dialog').style.display = 'none';
    }

    /**
     * Create document from template
     */
    async createFromTemplate(templateId, templateName) {
        this.closeTemplates();
        
        const docName = prompt(`Enter name for new document (from template: ${templateName}):`, `New ${templateName}`);
        if (!docName) return;
        
        try {
            const response = await fetch(`${this.apiBase}/api/templates/${templateId}/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: docName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentDocument = data.document;
                this.displayDocument();
                if (window.addTerminalLog) {
                    window.addTerminalLog(`✓ Document '${docName}' created from template`, 'success');
                }
            } else {
                alert('Failed to create from template: ' + data.error);
            }
        } catch (error) {
            console.error('Create from template error:', error);
            alert('Failed to create from template');
        }
    }

    /**
     * Show version history
     */
    showVersionHistory() {
        const historyList = document.getElementById('doc-version-history-list');
        historyList.innerHTML = '';
        
        this.currentDocument.versions.forEach((version, index) => {
            const versionDiv = document.createElement('div');
            versionDiv.className = 'version-item';
            versionDiv.innerHTML = `
                <div class="version-header">
                    <span class="version-number">Version ${version.version} (Depth: ${version.expertise_depth})</span>
                    <span class="version-timestamp">${new Date(version.timestamp).toLocaleString()}</span>
                </div>
                <div class="version-summary">${version.changes_summary || 'No summary'}</div>
            `;
            historyList.appendChild(versionDiv);
        });
        
        document.getElementById('doc-version-history-dialog').style.display = 'flex';
    }

    /**
     * Close version history
     */
    closeVersionHistory() {
        document.getElementById('doc-version-history-dialog').style.display = 'none';
    }

    /**
     * Close panel
     */
    close() {
        if (this.isEditing) {
            if (confirm('You have unsaved changes. Discard them?')) {
                document.getElementById('document-editor-panel').style.display = 'none';
                this.currentDocument = null;
                this.isEditing = false;
            }
        } else {
            document.getElementById('document-editor-panel').style.display = 'none';
            this.currentDocument = null;
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DocumentEditorPanel;
}