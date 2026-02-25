/**
 * Enhanced Librarian UI
 * 
 * Provides interface for:
 * - Discovery workflow
 * - Command interpretation dropdown
 * - Natural language to command conversion
 * - Bot status display
 * - Workflow visualization
 */

class EnhancedLibrarianUI {
    constructor(apiBase) {
        this.apiBase = apiBase || window.API_BASE || '';
        this.currentPhase = 'initial';
        this.discoveryAnswers = {};
        this.selectedCommand = null;
    }
    
    /**
     * Send input to enhanced librarian
     */
    async sendToLibrarian(input) {
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/enhanced`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ input })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.handleLibrarianResponse(result.data);
                return result.data;
            }
            
            throw new Error(result.message || 'Failed to get response');
            
        } catch (error) {
            console.error('Librarian error:', error);
            return {
                type: 'error',
                message: error.message
            };
        }
    }
    
    /**
     * Handle librarian response
     */
    handleLibrarianResponse(data) {
        switch (data.type) {
            case 'question':
                this.displayQuestion(data);
                break;
            case 'info':
                this.displayInfo(data);
                break;
            case 'system_ready':
                this.displaySystemReady(data);
                break;
            case 'error':
                this.displayError(data);
                break;
            default:
                this.displayMessage(data);
        }
        
        if (data.phase) {
            this.currentPhase = data.phase;
        }
    }
    
    /**
     * Display question with options
     */
    displayQuestion(data) {
        // This would integrate with the terminal or a dedicated UI
        const terminal = document.getElementById('terminal-output');
        if (terminal) {
            // Add librarian message
            this.addTerminalLog(data.librarian_response || data.question, 'info');
            
            // Add the question
            this.addTerminalLog(data.follow_up, 'question');
            
            // Add options if available
            if (data.options && data.options.length > 0) {
                this.addTerminalLog('Options:', 'info');
                data.options.forEach((opt, idx) => {
                    this.addTerminalLog(`  ${idx + 1}. ${opt}`, 'option');
                });
            }
            
            // Add hint if available
            if (data.hint) {
                this.addTerminalLog(`Hint: ${data.hint}`, 'hint');
            }
        }
    }
    
    /**
     * Display info message
     */
    displayInfo(data) {
        const terminal = document.getElementById('terminal-output');
        if (terminal) {
            this.addTerminalLog(data.message, 'success');
            this.addTerminalLog(data.follow_up, 'info');
            
            if (data.options) {
                data.options.forEach((opt, idx) => {
                    this.addTerminalLog(`  ${idx + 1}. ${opt}`, 'option');
                });
            }
        }
    }
    
    /**
     * Display system ready message
     */
    displaySystemReady(data) {
        const terminal = document.getElementById('terminal-output');
        if (terminal) {
            this.addTerminalLog(data.message, 'success');
            this.addTerminalLog(data.librarian_response, 'info');
            
            // Show workflow examples
            if (data.workflows && data.workflows.length > 0) {
                this.addTerminalLog('\nAvailable Workflows:', 'info');
                data.workflows.forEach(wf => {
                    this.addTerminalLog(`  • ${wf.name}: ${wf.description}`, 'info');
                });
            }
            
            // Show command examples
            if (data.command_examples && data.command_examples.length > 0) {
                this.addTerminalLog('\nExample Commands:', 'info');
                data.command_examples.forEach(cmd => {
                    this.addTerminalLog(`  ${cmd}`, 'command');
                });
            }
        }
    }
    
    /**
     * Display error
     */
    displayError(data) {
        const terminal = document.getElementById('terminal-output');
        if (terminal) {
            this.addTerminalLog(`Error: ${data.message}`, 'error');
        }
    }
    
    /**
     * Display message
     */
    displayMessage(data) {
        const terminal = document.getElementById('terminal-output');
        if (terminal) {
            this.addTerminalLog(data.message, 'info');
        }
    }
    
    /**
     * Add log to terminal
     */
    addTerminalLog(message, type = 'info') {
        // This would integrate with the existing terminal
        if (typeof addTerminalLog === 'function') {
            addTerminalLog(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
    
    /**
     * Interpret a command in natural language
     */
    async interpretCommand(command) {
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/interpret`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ command })
            });
            
            const result = await response.json();
            
            if (result.success) {
                return result.data;
            }
            
            throw new Error(result.message || 'Interpretation failed');
            
        } catch (error) {
            console.error('Interpretation error:', error);
            return null;
        }
    }
    
    /**
     * Convert natural language to command
     */
    async naturalToCommand(natural) {
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/natural-to-command`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ natural })
            });
            
            const result = await response.json();
            
            if (result.success) {
                return result.data;
            }
            
            throw new Error(result.message || 'Conversion failed');
            
        } catch (error) {
            console.error('Conversion error:', error);
            return null;
        }
    }
    
    /**
     * Show command interpretation dropdown
     */
    async showCommandInterpretation(command) {
        const interpretation = await this.interpretCommand(command);
        
        if (!interpretation) {
            return;
        }
        
        // Create or get dropdown element
        let dropdown = document.getElementById('command-interpretation-dropdown');
        if (!dropdown) {
            dropdown = this.createInterpretationDropdown();
        }
        
        // Populate dropdown
        this.populateInterpretationDropdown(dropdown, interpretation);
        
        // Show dropdown
        dropdown.classList.remove('hidden');
    }
    
    /**
     * Create interpretation dropdown
     */
    createInterpretationDropdown() {
        const dropdown = document.createElement('div');
        dropdown.id = 'command-interpretation-dropdown';
        dropdown.className = 'command-dropdown hidden';
        dropdown.innerHTML = `
            <div class="dropdown-header">
                <h3>Command Interpretation</h3>
                <button class="close-dropdown">×</button>
            </div>
            <div class="dropdown-content">
                <!-- Content will be populated -->
            </div>
        `;
        
        document.body.appendChild(dropdown);
        
        // Close button handler
        dropdown.querySelector('.close-dropdown').addEventListener('click', () => {
            dropdown.classList.add('hidden');
        });
        
        return dropdown;
    }
    
    /**
     * Populate interpretation dropdown
     */
    populateInterpretationDropdown(dropdown, interpretation) {
        const content = dropdown.querySelector('.dropdown-content');
        
        content.innerHTML = `
            <div class="interpretation-section">
                <h4>Original Command</h4>
                <code class="command-text">${interpretation.original_command}</code>
            </div>
            
            <div class="interpretation-section">
                <h4>Natural Language</h4>
                <p class="natural-language">${interpretation.natural_language}</p>
            </div>
            
            <div class="interpretation-section">
                <h4>Bot Role</h4>
                <span class="bot-role badge">${interpretation.bot_role}</span>
            </div>
            
            <div class="interpretation-section">
                <h4>Domain</h4>
                <span class="domain badge">${interpretation.domain}</span>
            </div>
            
            <div class="interpretation-section">
                <h4>Explanation</h4>
                <div class="explanation">${interpretation.explanation}</div>
            </div>
            
            ${interpretation.related_commands && interpretation.related_commands.length > 0 ? `
            <div class="interpretation-section">
                <h4>Related Commands</h4>
                <ul class="related-commands">
                    ${interpretation.related_commands.map(cmd => `
                        <li><code>${cmd}</code></li>
                    `).join('')}
                </ul>
            </div>
            ` : ''}
            
            <div class="dropdown-actions">
                <button class="btn btn-primary execute-command">Execute Command</button>
                <button class="btn btn-secondary close-dropdown">Close</button>
            </div>
        `;
        
        // Execute button handler
        content.querySelector('.execute-command').addEventListener('click', () => {
            // Execute the command
            if (typeof executeTerminalCommand === 'function') {
                executeTerminalCommand(interpretation.original_command);
            }
            dropdown.classList.add('hidden');
        });
        
        // Close button handler
        content.querySelectorAll('.close-dropdown').forEach(btn => {
            btn.addEventListener('click', () => {
                dropdown.classList.add('hidden');
            });
        });
    }
    
    /**
     * Get command dropdown data
     */
    async getCommandDropdownData() {
        try {
            const response = await fetch(`${this.apiBase}/api/commands/dropdown-data`);
            const result = await response.json();
            
            if (result.success) {
                return result.data;
            }
            
            throw new Error(result.message || 'Failed to get dropdown data');
            
        } catch (error) {
            console.error('Dropdown data error:', error);
            return null;
        }
    }
    
    /**
     * Show command builder dropdown
     */
    async showCommandBuilder() {
        const data = await this.getCommandDropdownData();
        
        if (!data) {
            return;
        }
        
        // Create or get dropdown
        let dropdown = document.getElementById('command-builder-dropdown');
        if (!dropdown) {
            dropdown = this.createCommandBuilderDropdown();
        }
        
        // Populate dropdown
        this.populateCommandBuilderDropdown(dropdown, data);
        
        // Show dropdown
        dropdown.classList.remove('hidden');
    }
    
    /**
     * Create command builder dropdown
     */
    createCommandBuilderDropdown() {
        const dropdown = document.createElement('div');
        dropdown.id = 'command-builder-dropdown';
        dropdown.className = 'command-dropdown hidden';
        dropdown.innerHTML = `
            <div class="dropdown-header">
                <h3>Command Builder</h3>
                <button class="close-dropdown">×</button>
            </div>
            <div class="dropdown-content">
                <div class="command-builder">
                    <div class="builder-section">
                        <label>Action</label>
                        <select id="builder-action"></select>
                    </div>
                    
                    <div class="builder-section">
                        <label>Bot Role</label>
                        <select id="builder-bot"></select>
                    </div>
                    
                    <div class="builder-section">
                        <label>Arguments</label>
                        <input type="text" id="builder-args" placeholder="e.g., Engineer">
                    </div>
                    
                    <div class="builder-section">
                        <label>Context (Comment)</label>
                        <input type="text" id="builder-comment" placeholder="e.g., #implement feature">
                    </div>
                    
                    <div class="builder-preview">
                        <label>Preview</label>
                        <code id="builder-preview"></code>
                    </div>
                    
                    <div class="dropdown-actions">
                        <button class="btn btn-primary build-command">Build Command</button>
                        <button class="btn btn-secondary close-dropdown">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(dropdown);
        
        // Close button handler
        dropdown.querySelector('.close-dropdown').addEventListener('click', () => {
            dropdown.classList.add('hidden');
        });
        
        return dropdown;
    }
    
    /**
     * Populate command builder dropdown
     */
    populateCommandBuilderDropdown(dropdown, data) {
        const actionSelect = dropdown.querySelector('#builder-action');
        const botSelect = dropdown.querySelector('#builder-bot');
        
        // Populate actions
        actionSelect.innerHTML = '<option value="">Select action</option>';
        data.actions.forEach(action => {
            actionSelect.innerHTML += `
                <option value="${action.name}" data-example="${action.example}">
                    ${action.name} - ${action.description}
                </option>
            `;
        });
        
        // Populate bot roles
        botSelect.innerHTML = '<option value="">Select bot</option>';
        data.bot_roles.forEach(bot => {
            botSelect.innerHTML += `<option value="${bot}">${bot}</option>`;
        });
        
        // Add update preview handlers
        const updatePreview = () => {
            const action = actionSelect.value;
            const bot = botSelect.value;
            const args = dropdown.querySelector('#builder-args').value;
            const comment = dropdown.querySelector('#builder-comment').value;
            
            let preview = '';
            if (action) {
                preview = `/${action}`;
                if (args) {
                    preview += ` ${args}`;
                }
                if (comment) {
                    const commentText = comment.startsWith('#') ? comment : `#${comment}`;
                    preview += ` ${commentText}`;
                }
            }
            
            dropdown.querySelector('#builder-preview').textContent = preview || 'Enter command details...';
        };
        
        actionSelect.addEventListener('change', () => {
            // Set example in args field
            const selectedOption = actionSelect.options[actionSelect.selectedIndex];
            const example = selectedOption.dataset.example;
            if (example) {
                // Parse example
                const match = example.match(/^\/(\w+)\s+(\S+)?\s*(#.*)?$/);
                if (match) {
                    dropdown.querySelector('#builder-args').value = match[2] || '';
                    dropdown.querySelector('#builder-comment').value = match[3] || '';
                }
            }
            updatePreview();
        });
        
        botSelect.addEventListener('change', updatePreview);
        dropdown.querySelector('#builder-args').addEventListener('input', updatePreview);
        dropdown.querySelector('#builder-comment').addEventListener('input', updatePreview);
        
        // Build command button handler
        dropdown.querySelector('.build-command').addEventListener('click', () => {
            const preview = dropdown.querySelector('#builder-preview').textContent;
            if (preview && preview !== 'Enter command details...') {
                // Execute the command
                if (typeof executeTerminalCommand === 'function') {
                    executeTerminalCommand(preview);
                }
                dropdown.classList.add('hidden');
            }
        });
        
        // Cancel button handler
        dropdown.querySelector('.dropdown-actions .close-dropdown').addEventListener('click', () => {
            dropdown.classList.add('hidden');
        });
    }
    
    /**
     * Get executive bots
     */
    async getExecutiveBots() {
        try {
            const response = await fetch(`${this.apiBase}/api/executive/bots`);
            const result = await response.json();
            
            if (result.success) {
                return result.bots;
            }
            
            throw new Error(result.message || 'Failed to get bots');
            
        } catch (error) {
            console.error('Get bots error:', error);
            return [];
        }
    }
    
    /**
     * Get bot terminology
     */
    async getBotTerminology(botRole) {
        try {
            const response = await fetch(`${this.apiBase}/api/executive/terminology/${botRole}`);
            const result = await response.json();
            
            if (result.success) {
                return result.terminology;
            }
            
            throw new Error(result.message || 'Failed to get terminology');
            
        } catch (error) {
            console.error('Get terminology error:', error);
            return [];
        }
    }
    
    /**
     * Execute workflow
     */
    async executeWorkflow(workflowName) {
        try {
            const response = await fetch(`${this.apiBase}/api/executive/workflow/${workflowName}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                return result.data;
            }
            
            throw new Error(result.message || 'Workflow execution failed');
            
        } catch (error) {
            console.error('Workflow execution error:', error);
            return null;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Create global instance
    window.enhancedLibrarianUI = new EnhancedLibrarianUI();
    
    // Add command to terminal help
    if (typeof addTerminalCommand === 'function') {
        addTerminalCommand('/librarian interpret <command>', 'Interpret a command in natural language');
        addTerminalCommand('/librarian natural <command>', 'Convert command to natural language');
        addTerminalCommand('/librarian start', 'Begin system discovery');
        addTerminalCommand('/command build', 'Open command builder');
        addTerminalCommand('/workflow execute <name>', 'Execute a workflow');
    }
});