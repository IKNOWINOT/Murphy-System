/**
 * Murphy System - Librarian Panel Component
 * 
 * Provides intelligent guidance through natural language interaction
 */

class LibrarianPanel {
    constructor(apiBase) {
        this.apiBase = apiBase;
        this.conversationHistory = [];
        this.isProcessing = false;
    }

    /**
     * Initialize the Librarian panel
     */
    init() {
        this.createPanel();
        this.attachEventListeners();
        this.showWelcomeMessage();
    }

    /**
     * Create the Librarian panel HTML
     */
    createPanel() {
        const panelHTML = `
            <div id="librarian-panel" class="system-panel" style="display: none;">
                <div class="panel-header">
                    <h2>🧙 Librarian - Intelligent Guide</h2>
                    <button class="close-btn" onclick="librarianPanel.close()">×</button>
                </div>
                
                <div class="panel-content">
                    <!-- Conversation Area -->
                    <div id="librarian-conversation" class="librarian-conversation">
                        <!-- Messages will be added here -->
                    </div>
                    
                    <!-- Input Area -->
                    <div class="librarian-input-area">
                        <input 
                            type="text" 
                            id="librarian-input" 
                            class="librarian-input"
                            placeholder="Ask me anything about Murphy System..."
                            autocomplete="off"
                        />
                        <button id="librarian-send-btn" class="librarian-send-btn">
                            Send
                        </button>
                    </div>
                    
                    <!-- Quick Actions -->
                    <div class="librarian-quick-actions">
                        <button class="quick-action-btn" onclick="librarianPanel.quickAction('guide')">
                            📖 Guide Me
                        </button>
                        <button class="quick-action-btn" onclick="librarianPanel.quickAction('search')">
                            🔍 Search Knowledge
                        </button>
                        <button class="quick-action-btn" onclick="librarianPanel.quickAction('transcripts')">
                            📜 View History
                        </button>
                        <button class="quick-action-btn" onclick="librarianPanel.quickAction('overview')">
                            📊 System Overview
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Add to body
        document.body.insertAdjacentHTML('beforeend', panelHTML);
        
        // Add styles
        this.addStyles();
    }

    /**
     * Add CSS styles for Librarian panel
     */
    addStyles() {
        const styles = `
            <style>
                .system-panel {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    width: 600px;
                    max-width: 90vw;
                    max-height: 80vh;
                    background: #1a1a1a;
                    border: 2px solid #00ff88;
                    border-radius: 8px;
                    box-shadow: 0 8px 32px rgba(0, 255, 136, 0.3);
                    z-index: 1000;
                    display: flex;
                    flex-direction: column;
                }
                
                .panel-header {
                    padding: 15px 20px;
                    background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%);
                    color: #000;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-radius: 6px 6px 0 0;
                }
                
                .panel-header h2 {
                    margin: 0;
                    font-size: 18px;
                    font-weight: 600;
                }
                
                .close-btn {
                    background: none;
                    border: none;
                    color: #000;
                    font-size: 28px;
                    cursor: pointer;
                    line-height: 1;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                
                .close-btn:hover {
                    opacity: 0.7;
                }
                
                .panel-content {
                    padding: 20px;
                    flex: 1;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                }
                
                .librarian-conversation {
                    flex: 1;
                    overflow-y: auto;
                    margin-bottom: 15px;
                    padding: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    min-height: 300px;
                    max-height: 400px;
                }
                
                .librarian-message {
                    margin-bottom: 15px;
                    padding: 10px;
                    border-radius: 6px;
                    animation: fadeIn 0.3s ease-in;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .librarian-message.user {
                    background: #1a3a4a;
                    border-left: 3px solid #00aaff;
                    margin-left: 20px;
                }
                
                .librarian-message.librarian {
                    background: #1a3a1a;
                    border-left: 3px solid #00ff88;
                    margin-right: 20px;
                }
                
                .message-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                    font-size: 12px;
                    opacity: 0.7;
                }
                
                .message-content {
                    color: #fff;
                    line-height: 1.5;
                }
                
                .intent-badge {
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 10px;
                    font-weight: 600;
                    text-transform: uppercase;
                    margin-left: 8px;
                }
                
                .intent-query { background: #0066cc; }
                .intent-action { background: #cc6600; }
                .intent-guidance { background: #6600cc; }
                .intent-learning { background: #00cc66; }
                .intent-creation { background: #cc0066; }
                .intent-analysis { background: #cccc00; }
                .intent-troubleshooting { background: #cc0000; }
                .intent-exploration { background: #00cccc; }
                
                .confidence-indicator {
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 10px;
                    margin-left: 8px;
                }
                
                .confidence-very_high { background: #00ff00; color: #000; }
                .confidence-high { background: #88ff00; color: #000; }
                .confidence-medium { background: #ffff00; color: #000; }
                .confidence-low { background: #ff8800; color: #000; }
                .confidence-very_low { background: #ff0000; color: #fff; }
                
                .suggested-commands {
                    margin-top: 10px;
                    padding: 8px;
                    background: rgba(0, 255, 136, 0.1);
                    border-radius: 4px;
                }
                
                .suggested-commands-title {
                    font-size: 11px;
                    font-weight: 600;
                    color: #00ff88;
                    margin-bottom: 5px;
                }
                
                .command-chip {
                    display: inline-block;
                    padding: 4px 8px;
                    margin: 3px;
                    background: #2a2a2a;
                    border: 1px solid #00ff88;
                    border-radius: 4px;
                    font-size: 11px;
                    font-family: 'Courier New', monospace;
                    color: #00ff88;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .command-chip:hover {
                    background: #00ff88;
                    color: #000;
                }
                
                .workflow-section {
                    margin-top: 10px;
                    padding: 8px;
                    background: rgba(0, 170, 255, 0.1);
                    border-radius: 4px;
                }
                
                .workflow-title {
                    font-size: 11px;
                    font-weight: 600;
                    color: #00aaff;
                    margin-bottom: 5px;
                }
                
                .workflow-step {
                    padding: 4px 0;
                    font-size: 11px;
                    color: #ccc;
                }
                
                .follow-up-questions {
                    margin-top: 10px;
                    padding: 8px;
                    background: rgba(255, 255, 0, 0.1);
                    border-radius: 4px;
                }
                
                .follow-up-title {
                    font-size: 11px;
                    font-weight: 600;
                    color: #ffff00;
                    margin-bottom: 5px;
                }
                
                .follow-up-question {
                    padding: 4px 8px;
                    margin: 3px 0;
                    background: #2a2a2a;
                    border-left: 2px solid #ffff00;
                    font-size: 11px;
                    color: #ccc;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .follow-up-question:hover {
                    background: #3a3a3a;
                    border-left-color: #ffff88;
                }
                
                .librarian-input-area {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 15px;
                }
                
                .librarian-input {
                    flex: 1;
                    padding: 10px;
                    background: #0a0a0a;
                    border: 1px solid #333;
                    border-radius: 4px;
                    color: #fff;
                    font-size: 14px;
                }
                
                .librarian-input:focus {
                    outline: none;
                    border-color: #00ff88;
                }
                
                .librarian-send-btn {
                    padding: 10px 20px;
                    background: #00ff88;
                    border: none;
                    border-radius: 4px;
                    color: #000;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .librarian-send-btn:hover {
                    background: #00cc6a;
                }
                
                .librarian-send-btn:disabled {
                    background: #333;
                    color: #666;
                    cursor: not-allowed;
                }
                
                .librarian-quick-actions {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }
                
                .quick-action-btn {
                    padding: 8px 12px;
                    background: #2a2a2a;
                    border: 1px solid #444;
                    border-radius: 4px;
                    color: #fff;
                    font-size: 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                
                .quick-action-btn:hover {
                    background: #3a3a3a;
                    border-color: #00ff88;
                }
                
                .loading-indicator {
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border: 2px solid #00ff88;
                    border-top-color: transparent;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        const input = document.getElementById('librarian-input');
        const sendBtn = document.getElementById('librarian-send-btn');
        
        // Send on Enter key
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isProcessing) {
                this.sendMessage();
            }
        });
        
        // Send on button click
        sendBtn.addEventListener('click', () => {
            if (!this.isProcessing) {
                this.sendMessage();
            }
        });
    }

    /**
     * Show welcome message
     */
    showWelcomeMessage() {
        const welcomeMsg = {
            type: 'librarian',
            content: `Welcome! I'm the Murphy System Librarian. I can help you:

• Understand system capabilities
• Find the right commands
• Guide you through workflows
• Answer questions about concepts
• Suggest next steps

Ask me anything, or use the quick actions below!`,
            timestamp: new Date()
        };
        
        this.addMessage(welcomeMsg);
    }

    /**
     * Send user message
     */
    async sendMessage() {
        const input = document.getElementById('librarian-input');
        const sendBtn = document.getElementById('librarian-send-btn');
        const query = input.value.trim();
        
        if (!query) return;
        
        // Add user message
        this.addMessage({
            type: 'user',
            content: query,
            timestamp: new Date()
        });
        
        // Clear input and disable
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;
        this.isProcessing = true;
        
        // Show loading
        this.addLoadingMessage();
        
        try {
            // Call API
            const response = await fetch(`${this.apiBase}/api/librarian/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            
            // Remove loading
            this.removeLoadingMessage();
            
            // Add librarian response
            this.addMessage({
                type: 'librarian',
                content: data.message,
                intent: data.intent,
                commands: data.commands,
                workflow: data.workflow,
                followUp: data.follow_up_questions,
                confidenceLevel: data.confidence_level,
                timestamp: new Date()
            });
            
        } catch (error) {
            console.error('Librarian error:', error);
            this.removeLoadingMessage();
            this.addMessage({
                type: 'librarian',
                content: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date()
            });
        } finally {
            input.disabled = false;
            sendBtn.disabled = false;
            this.isProcessing = false;
            input.focus();
        }
    }

    /**
     * Add message to conversation
     */
    addMessage(message) {
        const conversation = document.getElementById('librarian-conversation');
        const messageDiv = document.createElement('div');
        messageDiv.className = `librarian-message ${message.type}`;
        
        let html = `
            <div class="message-header">
                <span>${message.type === 'user' ? '👤 You' : '🧙 Librarian'}</span>
                <span>${this.formatTime(message.timestamp)}</span>
            </div>
            <div class="message-content">${this.formatContent(message.content)}</div>
        `;
        
        // Add intent badge for librarian messages
        if (message.type === 'librarian' && message.intent) {
            html += `
                <div style="margin-top: 8px;">
                    <span class="intent-badge intent-${message.intent.category}">
                        ${message.intent.category}
                    </span>
                    <span class="confidence-indicator confidence-${message.confidenceLevel}">
                        ${Math.round(message.intent.confidence * 100)}%
                    </span>
                </div>
            `;
        }
        
        // Add suggested commands
        if (message.commands && message.commands.length > 0) {
            html += `
                <div class="suggested-commands">
                    <div class="suggested-commands-title">💡 Suggested Commands:</div>
                    ${message.commands.map(cmd => 
                        `<span class="command-chip" onclick="librarianPanel.executeCommand('${cmd}')">${cmd}</span>`
                    ).join('')}
                </div>
            `;
        }
        
        // Add workflow
        if (message.workflow) {
            html += `
                <div class="workflow-section">
                    <div class="workflow-title">📋 ${message.workflow.name}:</div>
                    ${message.workflow.steps.map((step, i) => 
                        `<div class="workflow-step">${i + 1}. ${step.command} - ${step.description}</div>`
                    ).join('')}
                </div>
            `;
        }
        
        // Add follow-up questions
        if (message.followUp && message.followUp.length > 0) {
            html += `
                <div class="follow-up-questions">
                    <div class="follow-up-title">❓ Follow-up Questions:</div>
                    ${message.followUp.map(q => 
                        `<div class="follow-up-question" onclick="librarianPanel.askFollowUp('${q.replace(/'/g, "\\'")}')">${q}</div>`
                    ).join('')}
                </div>
            `;
        }
        
        messageDiv.innerHTML = html;
        conversation.appendChild(messageDiv);
        
        // Scroll to bottom
        conversation.scrollTop = conversation.scrollHeight;
        
        // Store in history
        this.conversationHistory.push(message);
    }

    /**
     * Add loading message
     */
    addLoadingMessage() {
        const conversation = document.getElementById('librarian-conversation');
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'librarian-loading';
        loadingDiv.className = 'librarian-message librarian';
        loadingDiv.innerHTML = `
            <div class="message-content">
                <span class="loading-indicator"></span> Thinking...
            </div>
        `;
        conversation.appendChild(loadingDiv);
        conversation.scrollTop = conversation.scrollHeight;
    }

    /**
     * Remove loading message
     */
    removeLoadingMessage() {
        const loading = document.getElementById('librarian-loading');
        if (loading) {
            loading.remove();
        }
    }

    /**
     * Format message content
     */
    formatContent(content) {
        return content.replace(/\n/g, '<br>');
    }

    /**
     * Format timestamp
     */
    formatTime(date) {
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }

    /**
     * Execute command from suggestion
     */
    executeCommand(command) {
        // Close librarian panel
        this.close();
        
        // Execute command in terminal
        if (window.executeTerminalCommand) {
            window.executeTerminalCommand(command);
        } else {
            console.log('Execute command:', command);
        }
    }

    /**
     * Ask follow-up question
     */
    askFollowUp(question) {
        const input = document.getElementById('librarian-input');
        input.value = question;
        input.focus();
    }

    /**
     * Quick action handlers
     */
    async quickAction(action) {
        switch (action) {
            case 'guide':
                await this.sendMessageDirect('I need guidance on what to do next');
                break;
            case 'search':
                const searchQuery = prompt('What would you like to search for?');
                if (searchQuery) {
                    await this.searchKnowledge(searchQuery);
                }
                break;
            case 'transcripts':
                await this.showTranscripts();
                break;
            case 'overview':
                await this.showOverview();
                break;
        }
    }

    /**
     * Send message programmatically
     */
    async sendMessageDirect(query) {
        const input = document.getElementById('librarian-input');
        input.value = query;
        await this.sendMessage();
    }

    /**
     * Search knowledge base
     */
    async searchKnowledge(query) {
        this.addMessage({
            type: 'user',
            content: `Search: ${query}`,
            timestamp: new Date()
        });
        
        this.addLoadingMessage();
        
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            this.removeLoadingMessage();
            
            let content = `Found ${data.count} results for "${query}":\n\n`;
            data.results.forEach((result, i) => {
                content += `${i + 1}. [${result.type.toUpperCase()}] ${result.name}\n   ${result.description}\n\n`;
            });
            
            this.addMessage({
                type: 'librarian',
                content: content || 'No results found.',
                timestamp: new Date()
            });
            
        } catch (error) {
            console.error('Search error:', error);
            this.removeLoadingMessage();
        }
    }

    /**
     * Show conversation transcripts
     */
    async showTranscripts() {
        this.addMessage({
            type: 'user',
            content: 'Show conversation history',
            timestamp: new Date()
        });
        
        this.addLoadingMessage();
        
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/transcripts?limit=5`);
            const data = await response.json();
            this.removeLoadingMessage();
            
            let content = `Recent conversations (${data.count}):\n\n`;
            data.transcripts.forEach((t, i) => {
                content += `${i + 1}. "${t.user_input}"\n   Intent: ${t.intent_category} (${Math.round(t.confidence * 100)}%)\n   Response: ${t.message.substring(0, 100)}...\n\n`;
            });
            
            this.addMessage({
                type: 'librarian',
                content: content,
                timestamp: new Date()
            });
            
        } catch (error) {
            console.error('Transcripts error:', error);
            this.removeLoadingMessage();
        }
    }

    /**
     * Show system overview
     */
    async showOverview() {
        this.addMessage({
            type: 'user',
            content: 'Show system overview',
            timestamp: new Date()
        });
        
        this.addLoadingMessage();
        
        try {
            const response = await fetch(`${this.apiBase}/api/librarian/overview`);
            const data = await response.json();
            this.removeLoadingMessage();
            
            let content = `System Overview:\n\n`;
            content += `Total Interactions: ${data.total_interactions}\n\n`;
            content += `Intent Distribution:\n`;
            Object.entries(data.intent_distribution).forEach(([intent, count]) => {
                content += `  • ${intent}: ${count}\n`;
            });
            content += `\nKnowledge Base:\n`;
            content += `  • Commands: ${data.knowledge_base_size.commands}\n`;
            content += `  • Concepts: ${data.knowledge_base_size.concepts}\n`;
            content += `  • Workflows: ${data.knowledge_base_size.workflows}\n`;
            
            this.addMessage({
                type: 'librarian',
                content: content,
                timestamp: new Date()
            });
            
        } catch (error) {
            console.error('Overview error:', error);
            this.removeLoadingMessage();
        }
    }

    /**
     * Open panel
     */
    open() {
        document.getElementById('librarian-panel').style.display = 'flex';
        document.getElementById('librarian-input').focus();
    }

    /**
     * Close panel
     */
    close() {
        document.getElementById('librarian-panel').style.display = 'none';
    }

    /**
     * Toggle panel
     */
    toggle() {
        const panel = document.getElementById('librarian-panel');
        if (panel.style.display === 'none') {
            this.open();
        } else {
            this.close();
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LibrarianPanel;
}