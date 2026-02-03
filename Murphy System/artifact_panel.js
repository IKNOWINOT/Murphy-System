/**
 * Artifact Panel - UI for artifact generation and management
 */

const ArtifactPanel = {
    artifacts: [],
    selectedArtifact: null,
    
    init() {
        console.log('Initializing Artifact Panel...');
        this.setupEventListeners();
        this.loadArtifacts();
    },
    
    setupEventListeners() {
        // Listen for WebSocket events
        if (window.socket) {
            window.socket.on('artifact_generated', (data) => {
                this.handleArtifactGenerated(data);
            });
            
            window.socket.on('artifact_updated', (data) => {
                this.handleArtifactUpdated(data);
            });
            
            window.socket.on('artifact_deleted', (data) => {
                this.handleArtifactDeleted(data);
            });
            
            window.socket.on('artifact_converted', (data) => {
                this.handleArtifactConverted(data);
            });
        }
    },
    
    async loadArtifacts() {
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/list`);
            const data = await response.json();
            
            if (data.artifacts) {
                this.artifacts = data.artifacts;
                this.renderArtifactList();
            }
        } catch (error) {
            console.error('Error loading artifacts:', error);
        }
    },
    
    renderArtifactList() {
        const container = document.getElementById('artifact-list');
        if (!container) return;
        
        if (this.artifacts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No artifacts yet</p>
                    <p class="hint">Generate artifacts from solidified documents</p>
                </div>
            `;
            return;
        }
        
        const html = this.artifacts.map(artifact => `
            <div class="artifact-item" data-id="${artifact.id}" onclick="ArtifactPanel.selectArtifact('${artifact.id}')">
                <div class="artifact-header">
                    <span class="artifact-type-badge ${artifact.type}">${artifact.type.toUpperCase()}</span>
                    <span class="artifact-status ${artifact.status}">${artifact.status}</span>
                </div>
                <div class="artifact-name">${artifact.name}</div>
                <div class="artifact-meta">
                    <span>Version ${artifact.version}</span>
                    <span>Quality: ${(artifact.quality_score * 100).toFixed(0)}%</span>
                </div>
                <div class="artifact-date">${new Date(artifact.created_at).toLocaleString()}</div>
            </div>
        `).join('');
        
        container.innerHTML = html;
    },
    
    async selectArtifact(artifactId) {
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}`);
            const artifact = await response.json();
            
            this.selectedArtifact = artifact;
            this.showArtifactDetails(artifact);
        } catch (error) {
            console.error('Error loading artifact details:', error);
        }
    },
    
    showArtifactDetails(artifact) {
        const modal = document.getElementById('artifact-detail-modal');
        if (!modal) return;
        
        const content = `
            <div class="modal-header">
                <h2>${artifact.name}</h2>
                <button onclick="ArtifactPanel.closeDetailModal()" class="close-btn">×</button>
            </div>
            
            <div class="modal-body">
                <div class="artifact-info-grid">
                    <div class="info-item">
                        <label>Type:</label>
                        <span class="artifact-type-badge ${artifact.type}">${artifact.type.toUpperCase()}</span>
                    </div>
                    <div class="info-item">
                        <label>Status:</label>
                        <span class="artifact-status ${artifact.status}">${artifact.status}</span>
                    </div>
                    <div class="info-item">
                        <label>Version:</label>
                        <span>${artifact.version}</span>
                    </div>
                    <div class="info-item">
                        <label>Quality Score:</label>
                        <span>${(artifact.quality_score * 100).toFixed(0)}%</span>
                    </div>
                    <div class="info-item">
                        <label>File Size:</label>
                        <span>${this.formatFileSize(artifact.file_size)}</span>
                    </div>
                    <div class="info-item">
                        <label>Created:</label>
                        <span>${new Date(artifact.created_at).toLocaleString()}</span>
                    </div>
                </div>
                
                ${artifact.validation_results && artifact.validation_results.length > 0 ? `
                    <div class="validation-section">
                        <h3>Validation Results</h3>
                        ${artifact.validation_results.map(v => `
                            <div class="validation-result ${v.valid ? 'valid' : 'invalid'}">
                                <div class="validation-status">
                                    ${v.valid ? '✓ Valid' : '✗ Invalid'}
                                </div>
                                ${v.issues && v.issues.length > 0 ? `
                                    <div class="validation-issues">
                                        <strong>Issues:</strong>
                                        <ul>
                                            ${v.issues.map(issue => `<li>${issue}</li>`).join('')}
                                        </ul>
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                
                <div class="content-preview">
                    <h3>Content Preview</h3>
                    <pre>${this.truncateContent(artifact.content, 500)}</pre>
                </div>
                
                <div class="action-buttons">
                    <button onclick="ArtifactPanel.downloadArtifact('${artifact.id}')" class="btn-primary">
                        Download
                    </button>
                    <button onclick="ArtifactPanel.showVersionHistory('${artifact.id}')" class="btn-secondary">
                        Version History
                    </button>
                    <button onclick="ArtifactPanel.showConvertDialog('${artifact.id}')" class="btn-secondary">
                        Convert Format
                    </button>
                    <button onclick="ArtifactPanel.deleteArtifact('${artifact.id}')" class="btn-danger">
                        Delete
                    </button>
                </div>
            </div>
        `;
        
        modal.innerHTML = content;
        modal.style.display = 'block';
    },
    
    closeDetailModal() {
        const modal = document.getElementById('artifact-detail-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },
    
    async showGenerateDialog() {
        // Get list of solidified documents
        let documents = [];
        try {
            const response = await fetch(`${API_BASE}/api/documents/list`);
            const data = await response.json();
            documents = data.documents.filter(d => d.state === 'solidified');
        } catch (error) {
            console.error('Error loading documents:', error);
        }
        
        // Get supported artifact types
        let types = [];
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/types`);
            const data = await response.json();
            types = data.types;
        } catch (error) {
            console.error('Error loading artifact types:', error);
        }
        
        const modal = document.getElementById('artifact-generate-modal');
        if (!modal) return;
        
        const content = `
            <div class="modal-header">
                <h2>Generate Artifact</h2>
                <button onclick="ArtifactPanel.closeGenerateModal()" class="close-btn">×</button>
            </div>
            
            <div class="modal-body">
                <div class="form-group">
                    <label>Select Document:</label>
                    <select id="generate-document-select" class="form-control">
                        <option value="">-- Select a solidified document --</option>
                        ${documents.map(doc => `
                            <option value="${doc.id}">${doc.title}</option>
                        `).join('')}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Artifact Type:</label>
                    <select id="generate-type-select" class="form-control">
                        <option value="">-- Select artifact type --</option>
                        ${types.map(type => `
                            <option value="${type}">${type.toUpperCase()}</option>
                        `).join('')}
                    </select>
                </div>
                
                <div class="type-descriptions">
                    <div class="type-desc" data-type="pdf">
                        <strong>PDF:</strong> Professional document with sections, formatting, and structure
                    </div>
                    <div class="type-desc" data-type="docx">
                        <strong>DOCX:</strong> Word document with title page, table of contents, and sections
                    </div>
                    <div class="type-desc" data-type="code">
                        <strong>CODE:</strong> Production-ready code with documentation and tests
                    </div>
                    <div class="type-desc" data-type="design">
                        <strong>DESIGN:</strong> Visual mockup or diagram in SVG format
                    </div>
                    <div class="type-desc" data-type="data">
                        <strong>DATA:</strong> Structured data in JSON format
                    </div>
                    <div class="type-desc" data-type="report">
                        <strong>REPORT:</strong> Analytical report with findings and recommendations
                    </div>
                    <div class="type-desc" data-type="presentation">
                        <strong>PRESENTATION:</strong> Slide deck in HTML format
                    </div>
                    <div class="type-desc" data-type="contract">
                        <strong>CONTRACT:</strong> Legal agreement template
                    </div>
                </div>
                
                <div class="action-buttons">
                    <button onclick="ArtifactPanel.generateArtifact()" class="btn-primary">
                        Generate Artifact
                    </button>
                    <button onclick="ArtifactPanel.closeGenerateModal()" class="btn-secondary">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        modal.innerHTML = content;
        modal.style.display = 'block';
        
        // Add event listener for type selection
        const typeSelect = document.getElementById('generate-type-select');
        if (typeSelect) {
            typeSelect.addEventListener('change', (e) => {
                document.querySelectorAll('.type-desc').forEach(desc => {
                    desc.style.display = 'none';
                });
                const selected = document.querySelector(`.type-desc[data-type="${e.target.value}"]`);
                if (selected) {
                    selected.style.display = 'block';
                }
            });
        }
    },
    
    closeGenerateModal() {
        const modal = document.getElementById('artifact-generate-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },
    
    async generateArtifact() {
        const documentId = document.getElementById('generate-document-select')?.value;
        const type = document.getElementById('generate-type-select')?.value;
        
        if (!documentId || !type) {
            addLog('Please select both document and artifact type', 'error');
            return;
        }
        
        try {
            addLog(`Generating ${type.toUpperCase()} artifact...`, 'info');
            
            const response = await fetch(`${API_BASE}/api/artifacts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: type,
                    document_id: documentId
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                addLog(`✓ Artifact generated successfully: ${data.artifact.name}`, 'success');
                this.closeGenerateModal();
                this.loadArtifacts();
            } else {
                addLog(`✗ Failed to generate artifact: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error generating artifact:', error);
            addLog(`✗ Error: ${error.message}`, 'error');
        }
    },
    
    async downloadArtifact(artifactId) {
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}/download`);
            const blob = await response.blob();
            
            const artifact = this.artifacts.find(a => a.id === artifactId);
            const filename = artifact ? artifact.name : 'artifact';
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            addLog(`✓ Downloaded: ${filename}`, 'success');
        } catch (error) {
            console.error('Error downloading artifact:', error);
            addLog(`✗ Download failed: ${error.message}`, 'error');
        }
    },
    
    async showVersionHistory(artifactId) {
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}/versions`);
            const data = await response.json();
            
            const modal = document.getElementById('artifact-version-modal');
            if (!modal) return;
            
            const content = `
                <div class="modal-header">
                    <h2>Version History</h2>
                    <button onclick="ArtifactPanel.closeVersionModal()" class="close-btn">×</button>
                </div>
                
                <div class="modal-body">
                    ${data.versions.length === 0 ? `
                        <p>No version history available</p>
                    ` : `
                        <div class="version-list">
                            ${data.versions.map(v => `
                                <div class="version-item">
                                    <div class="version-header">
                                        <strong>Version ${v.version}</strong>
                                        <span class="version-date">${new Date(v.created_at).toLocaleString()}</span>
                                    </div>
                                    <div class="version-details">
                                        <span>Quality: ${(v.quality_score * 100).toFixed(0)}%</span>
                                        <span>Status: ${v.status}</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>
            `;
            
            modal.innerHTML = content;
            modal.style.display = 'block';
        } catch (error) {
            console.error('Error loading version history:', error);
        }
    },
    
    closeVersionModal() {
        const modal = document.getElementById('artifact-version-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },
    
    async showConvertDialog(artifactId) {
        const types = ['pdf', 'docx', 'code', 'design', 'data', 'report', 'presentation', 'contract'];
        
        const modal = document.getElementById('artifact-convert-modal');
        if (!modal) return;
        
        const content = `
            <div class="modal-header">
                <h2>Convert Artifact Format</h2>
                <button onclick="ArtifactPanel.closeConvertModal()" class="close-btn">×</button>
            </div>
            
            <div class="modal-body">
                <div class="form-group">
                    <label>Target Format:</label>
                    <select id="convert-format-select" class="form-control">
                        <option value="">-- Select format --</option>
                        ${types.map(type => `
                            <option value="${type}">${type.toUpperCase()}</option>
                        `).join('')}
                    </select>
                </div>
                
                <div class="action-buttons">
                    <button onclick="ArtifactPanel.convertArtifact('${artifactId}')" class="btn-primary">
                        Convert
                    </button>
                    <button onclick="ArtifactPanel.closeConvertModal()" class="btn-secondary">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        modal.innerHTML = content;
        modal.style.display = 'block';
    },
    
    closeConvertModal() {
        const modal = document.getElementById('artifact-convert-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },
    
    async convertArtifact(artifactId) {
        const format = document.getElementById('convert-format-select')?.value;
        
        if (!format) {
            addLog('Please select a target format', 'error');
            return;
        }
        
        try {
            addLog(`Converting artifact to ${format.toUpperCase()}...`, 'info');
            
            const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}/convert`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format: format })
            });
            
            const data = await response.json();
            
            if (data.success) {
                addLog(`✓ Artifact converted successfully`, 'success');
                this.closeConvertModal();
                this.loadArtifacts();
            } else {
                addLog(`✗ Conversion failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error converting artifact:', error);
            addLog(`✗ Error: ${error.message}`, 'error');
        }
    },
    
    async deleteArtifact(artifactId) {
        if (!confirm('Are you sure you want to delete this artifact?')) {
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/api/artifacts/${artifactId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                addLog('✓ Artifact deleted', 'success');
                this.closeDetailModal();
                this.loadArtifacts();
            } else {
                addLog(`✗ Delete failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error deleting artifact:', error);
            addLog(`✗ Error: ${error.message}`, 'error');
        }
    },
    
    handleArtifactGenerated(data) {
        addLog(`✓ New artifact generated: ${data.name}`, 'success');
        this.loadArtifacts();
    },
    
    handleArtifactUpdated(data) {
        addLog(`✓ Artifact updated: ${data.artifact_id}`, 'info');
        this.loadArtifacts();
    },
    
    handleArtifactDeleted(data) {
        addLog(`✓ Artifact deleted: ${data.artifact_id}`, 'info');
        this.loadArtifacts();
    },
    
    handleArtifactConverted(data) {
        addLog(`✓ Artifact converted to ${data.format}`, 'success');
        this.loadArtifacts();
    },
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },
    
    truncateContent(content, maxLength) {
        if (!content) return 'No content available';
        if (content.length <= maxLength) return content;
        return content.substring(0, maxLength) + '...';
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ArtifactPanel.init());
} else {
    ArtifactPanel.init();
}