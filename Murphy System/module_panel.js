/**
 * Module System Panel
 * Combines SwissKiss and Module Compiler features
 */

class ModulePanel {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.currentModule = null;
        this.modules = [];
        this.loadedModules = [];
    }

    init() {
        console.log('Initializing Module Panel...');
        this.loadModules();
        this.loadLoadedModules();
    }

    /**
     * Load all registered modules
     */
    async loadModules() {
        try {
            const response = await fetch(`${this.apiBase}/api/modules`);
            const data = await response.json();
            
            if (data.success) {
                this.modules = data.modules;
                this.updateModuleList();
            }
        } catch (error) {
            console.error('Failed to load modules:', error);
        }
    }

    /**
     * Load all loaded (active) modules
     */
    async loadLoadedModules() {
        try {
            const response = await fetch(`${this.apiBase}/api/modules/loaded`);
            const data = await response.json();
            
            if (data.success) {
                this.loadedModules = data.modules;
                this.updateLoadedModulesList();
            }
        } catch (error) {
            console.error('Failed to load loaded modules:', error);
        }
    }

    /**
     * Compile module from GitHub repository
     */
    async compileFromGitHub(githubUrl, filePath, category) {
        const body = {
            github_url: githubUrl,
            category: category || 'general'
        };
        
        if (filePath) {
            body.file_path = filePath;
        }

        try {
            const response = await fetch(`${this.apiBase}/api/modules/compile/github`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (data.success) {
                this.currentModule = data.module;
                this.displayModuleSpec(data.module);
                this.loadModules(); // Refresh list
                return { success: true, module: data.module };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Compile module from local file
     */
    async compileFromFile(sourcePath, category) {
        const body = {
            source_path: sourcePath,
            category: category || 'general'
        };

        try {
            const response = await fetch(`${this.apiBase}/api/modules/compile/file`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (data.success) {
                this.currentModule = data.module;
                this.displayModuleSpec(data.module);
                this.loadModules(); // Refresh list
                return { success: true, module: data.module };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Analyze GitHub repository without compiling
     */
    async analyzeGitHubRepo(githubUrl) {
        const body = {
            github_url: githubUrl
        };

        try {
            const response = await fetch(`${this.apiBase}/api/github/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (data.success) {
                this.displayAnalysis(data.analysis);
                return { success: true, analysis: data.analysis };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Load module into runtime
     */
    async loadModule(moduleId) {
        try {
            const response = await fetch(`${this.apiBase}/api/modules/${moduleId}/load`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            const data = await response.json();

            if (data.success) {
                this.loadLoadedModules(); // Refresh list
                return { success: true };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Unload module from runtime
     */
    async unloadModule(moduleId) {
        try {
            const response = await fetch(`${this.apiBase}/api/modules/${moduleId}/unload`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            const data = await response.json();

            if (data.success) {
                this.loadLoadedModules(); // Refresh list
                return { success: true };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Get module specification
     */
    async getModuleSpec(moduleId) {
        try {
            const response = await fetch(`${this.apiBase}/api/modules/${moduleId}`);
            const data = await response.json();

            if (data.success) {
                this.currentModule = data.module;
                this.displayModuleSpec(data.module);
                return { success: true, module: data.module };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Search modules by capability
     */
    async searchModules(capabilityName) {
        try {
            const response = await fetch(`${this.apiBase}/api/modules/search?capability=${encodeURIComponent(capabilityName)}`);
            const data = await response.json();

            if (data.success) {
                return { success: true, modules: data.modules };
            } else {
                return { success: false, error: data.message };
            }
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Display module specification
     */
    displayModuleSpec(module) {
        const container = document.getElementById('module-spec-content');
        if (!container) return;

        const licenseStatus = module.license_allowed ? 
            `<span class="status-success">✓ Allowed</span>` : 
            `<span class="status-error">✗ Not Allowed</span>`;

        const riskLevel = module.risk_score < 0.3 ? 'Low' : 
                          module.risk_score < 0.6 ? 'Medium' : 
                          module.risk_score < 0.8 ? 'High' : 'Critical';

        const capabilitiesHtml = module.capabilities.map(cap => `
            <div class="capability-item">
                <strong>${cap.name}</strong>
                <p>${cap.description}</p>
                <div class="capability-meta">
                    <span>Determinism: ${cap.determinism}</span>
                    <span>Resource: CPU ${cap.resource_profile.cpu_limit} cores</span>
                </div>
                ${cap.test_vectors.length > 0 ? `
                    <div class="test-vectors">
                        <strong>Test Vectors (${cap.test_vectors.length})</strong>
                        <ul>
                            ${cap.test_vectors.slice(0, 3).map(tv => `
                                <li>${tv.name}: ${tv.description}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `).join('');

        container.innerHTML = `
            <div class="module-spec-header">
                <h3>${module.module_name}</h3>
                <span class="module-id">ID: ${module.module_id}</span>
            </div>

            <div class="module-spec-section">
                <h4>Basic Information</h4>
                <table class="module-info-table">
                    <tr>
                        <td>Source Path</td>
                        <td>${module.source_path}</td>
                    </tr>
                    <tr>
                        <td>GitHub URL</td>
                        <td>${module.github_url ? `<a href="${module.github_url}" target="_blank">${module.github_url}</a>` : 'N/A'}</td>
                    </tr>
                    <tr>
                        <td>License</td>
                        <td>${module.license_type} ${licenseStatus}</td>
                    </tr>
                    <tr>
                        <td>Risk Score</td>
                        <td>${module.risk_score.toFixed(2)} (${riskLevel})</td>
                    </tr>
                    <tr>
                        <td>Verification</td>
                        <td>${module.verification_status}</td>
                    </tr>
                    <tr>
                        <td>Manual Review Required</td>
                        <td>${module.requires_manual_review ? 'Yes' : 'No'}</td>
                    </tr>
                </table>
            </div>

            <div class="module-spec-section">
                <h4>Languages</h4>
                <div class="languages-list">
                    ${Object.entries(module.languages).map(([lang, bytes]) => `
                        <span class="language-tag">${lang}: ${(bytes / 1024).toFixed(1)}KB</span>
                    `).join('')}
                </div>
            </div>

            <div class="module-spec-section">
                <h4>Dependencies (${module.dependencies.length})</h4>
                <div class="dependencies-list">
                    ${module.dependencies.map(dep => `
                        <span class="dependency-tag">${dep.name} ${dep.version || ''}</span>
                    `).join('')}
                </div>
            </div>

            <div class="module-spec-section">
                <h4>Capabilities (${module.capabilities.length})</h4>
                <div class="capabilities-list">
                    ${capabilitiesHtml}
                </div>
            </div>

            ${module.risk_issues.length > 0 ? `
                <div class="module-spec-section">
                    <h4>Risk Issues (${module.risk_issues.length})</h4>
                    <div class="risk-issues-list">
                        ${module.risk_issues.map(issue => `
                            <div class="risk-issue ${issue.severity}">
                                <strong>${issue.file}:${issue.line}</strong>
                                <span>${issue.description}</span>
                                <span class="pattern">${issue.pattern}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}

            <div class="module-spec-section">
                <h4>Sandbox Profile</h4>
                <div class="sandbox-profile">
                    <p><strong>Type:</strong> ${module.sandbox_profile.profile_type}</p>
                    <p><strong>CPU Limit:</strong> ${module.sandbox_profile.resource_limits.cpu_limit} cores</p>
                    <p><strong>Memory Limit:</strong> ${module.sandbox_profile.resource_limits.memory_limit}</p>
                    <p><strong>Network Required:</strong> ${module.sandbox_profile.resource_limits.network_required ? 'Yes' : 'No'}</p>
                </div>
            </div>
        `;
    }

    /**
     * Display GitHub analysis
     */
    displayAnalysis(analysis) {
        const container = document.getElementById('github-analysis-content');
        if (!container) return;

        const licenseStatus = analysis.license_allowed ? 
            `<span class="status-success">✓ Allowed</span>` : 
            `<span class="status-error">✗ Not Allowed</span>`;

        const safetyStatus = analysis.safe_to_use ? 
            `<span class="status-success">✓ Safe to Use</span>` : 
            `<span class="status-warning">⚠ Requires Review</span>`;

        container.innerHTML = `
            <div class="analysis-header">
                <h3>${analysis.owner}/${analysis.repo}</h3>
                <a href="${analysis.repo_url}" target="_blank">View on GitHub</a>
            </div>

            <div class="analysis-section">
                <h4>Repository Summary</h4>
                <p class="readme-summary">${analysis.readme_summary}</p>
            </div>

            <div class="analysis-section">
                <h4>License</h4>
                <p>${analysis.license_type} ${licenseStatus}</p>
            </div>

            <div class="analysis-section">
                <h4>Dependencies (${analysis.dependencies.length})</h4>
                <div class="dependencies-list">
                    ${analysis.dependencies.map(dep => `
                        <span class="dependency-tag">${dep.name} ${dep.version || ''}</span>
                    `).join('')}
                </div>
            </div>

            <div class="analysis-section">
                <h4>Languages</h4>
                <div class="languages-list">
                    ${Object.entries(analysis.languages).map(([lang, bytes]) => `
                        <span class="language-tag">${lang}: ${(bytes / 1024).toFixed(1)}KB</span>
                    `).join('')}
                </div>
            </div>

            <div class="analysis-section">
                <h4>Risk Assessment</h4>
                <p><strong>Risk Score:</strong> ${analysis.risk_score.toFixed(2)}</p>
                <p><strong>Status:</strong> ${safetyStatus}</p>
                ${analysis.risk_issues.length > 0 ? `
                    <div class="risk-issues-list">
                        ${analysis.risk_issues.map(issue => `
                            <div class="risk-issue ${issue.severity}">
                                <strong>${issue.file}:${issue.line}</strong>
                                <span>${issue.description}</span>
                                <span class="pattern">${issue.pattern}</span>
                            </div>
                        `).join('')}
                    </div>
                ` : '<p class="status-success">No security issues found</p>'}
            </div>
        `;
    }

    /**
     * Update module list in UI
     */
    updateModuleList() {
        const container = document.getElementById('module-list');
        if (!container) return;

        if (this.modules.length === 0) {
            container.innerHTML = '<p class="no-items">No modules registered</p>';
            return;
        }

        container.innerHTML = this.modules.map(module => `
            <div class="module-item" data-module-id="${module.module_id}">
                <div class="module-item-header">
                    <strong>${module.module_name}</strong>
                    <span class="module-id">${module.module_id.slice(0, 8)}...</span>
                </div>
                <div class="module-item-meta">
                    <span>Capabilities: ${module.capabilities.length}</span>
                    <span>License: ${module.license_type}</span>
                    <span>Risk: ${module.risk_score.toFixed(2)}</span>
                </div>
                <div class="module-item-actions">
                    <button onclick="ModulePanel.selectModule('${module.module_id}')" class="btn btn-sm btn-secondary">View</button>
                    <button onclick="ModulePanel.loadModule('${module.module_id}')" class="btn btn-sm btn-primary">Load</button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Update loaded modules list
     */
    updateLoadedModulesList() {
        const container = document.getElementById('loaded-modules-list');
        if (!container) return;

        if (this.loadedModules.length === 0) {
            container.innerHTML = '<p class="no-items">No modules loaded</p>';
            return;
        }

        container.innerHTML = this.loadedModules.map(module => `
            <div class="module-item loaded">
                <div class="module-item-header">
                    <strong>${module.module_name}</strong>
                    <span class="status-success">Active</span>
                </div>
                <div class="module-item-meta">
                    <span>Capabilities: ${module.capabilities.length}</span>
                </div>
                <div class="module-item-actions">
                    <button onclick="ModulePanel.unloadModule('${module.module_id}')" class="btn btn-sm btn-warning">Unload</button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Select module for viewing
     */
    static selectModule(moduleId) {
        window.modulePanel.getModuleSpec(moduleId);
        // Switch to spec tab
        document.getElementById('module-tab-spec').click();
    }

    /**
     * Get auth token from localStorage
     */
    getAuthToken() {
        const auth = JSON.parse(localStorage.getItem('murphy_auth') || '{}');
        return auth.token || '';
    }
}

// Auto-initialize when DOM is ready
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        window.ModulePanel = new ModulePanel(API_BASE);
        window.ModulePanel.init();
    });
}