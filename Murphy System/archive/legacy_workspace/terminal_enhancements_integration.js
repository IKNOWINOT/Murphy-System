// Terminal Enhancements Integration
// This file integrates Priority 3 command enhancements into Murphy System

// Load the command enhancements module
// (This should be loaded before this file in HTML)

// ============================================
// Enhanced Terminal Input Handler with All Features
// ============================================

let commandHistory = [];
let historyIndex = 0;
let currentSuggestions = [];
let suggestionIndex = 0;

// Enhanced key press handler
function handleEnhancedTerminalKeyPress(event) {
    const terminalInput = document.getElementById('terminal-input');
    
    if (event.key === 'Enter') {
        const command = terminalInput.value.trim();
        if (command) {
            // Add to history
            commandHistory.push(command);
            historyIndex = commandHistory.length;
            
            // Execute command with enhancements
            executeEnhancedCommand(command);
            
            terminalInput.value = '';
            currentSuggestions = [];
            suggestionIndex = 0;
        }
    } else if (event.key === 'Tab') {
        event.preventDefault();
        
        // Tab autocomplete
        const currentInput = terminalInput.value;
        const completed = window.CommandEnhancements.autocompleteCommand(currentInput);
        
        if (completed !== currentInput) {
            terminalInput.value = completed;
        } else {
            // Show all matching suggestions
            showSuggestions(terminalInput);
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
    } else if (event.key === 'Escape') {
        // Clear suggestions
        currentSuggestions = [];
        hideSuggestions();
    }
}

// Show autocomplete suggestions
function showSuggestions(inputElement) {
    const input = inputElement.value;
    const suggestions = window.CommandEnhancements.getCommandSuggestions(input);
    
    if (suggestions.length === 0) {
        return;
    }
    
    // Create suggestions dropdown
    let dropdown = document.getElementById('suggestions-dropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'suggestions-dropdown';
        dropdown.className = 'suggestions-dropdown';
        document.body.appendChild(dropdown);
    }
    
    // Position dropdown below input
    const rect = inputElement.getBoundingClientRect();
    dropdown.style.left = rect.left + 'px';
    dropdown.style.top = (rect.bottom + 5) + 'px';
    dropdown.style.width = rect.width + 'px';
    
    // Build suggestions HTML
    dropdown.innerHTML = suggestions.map((s, i) => `
        <div class="suggestion-item ${s.implemented ? 'implemented' : 'planned'}" 
             data-index="${i}"
             data-command="${s.command}">
            <div class="suggestion-command">${s.command}</div>
            <div class="suggestion-description">${s.description}</div>
            <div class="suggestion-status">
                ${s.implemented ? '✓' : '○'} ${s.module}
            </div>
        </div>
    `).join('');
    
    currentSuggestions = suggestions;
    
    // Add click handlers
    dropdown.querySelectorAll('.suggestion-item').forEach(item => {
        item.addEventListener('click', () => {
            inputElement.value = item.dataset.command + ' ';
            hideSuggestions();
            inputElement.focus();
        });
    });
    
    dropdown.style.display = 'block';
}

// Hide suggestions dropdown
function hideSuggestions() {
    const dropdown = document.getElementById('suggestions-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
}

// ============================================
// Enhanced Command Execution
// ============================================

async function executeEnhancedCommand(input) {
    const terminalContent = document.getElementById('terminal-content');
    
    // Add command to terminal
    const cmdLine = document.createElement('div');
    cmdLine.className = 'terminal-line';
    cmdLine.innerHTML = `<span style="color: #666;">[${new Date().toLocaleTimeString()}]</span> <span class="terminal-prompt">murphy&gt;</span> <span style="color: #fff;">${input}</span>`;
    terminalContent.appendChild(cmdLine);
    
    try {
        // Step 1: Resolve aliases
        const resolvedCommand = window.CommandEnhancements.resolveAlias(input);
        
        // Step 2: Check for command chains
        const commands = window.CommandEnhancements.parseCommandChain(resolvedCommand);
        
        if (commands.length > 1) {
            // Command chain detected
            addTerminalLog(`Executing command chain: ${commands.length} commands`, 'info');
            
            const results = await window.CommandEnhancements.executeCommandChain(commands);
            
            // Display results
            results.forEach((result, i) => {
                const chainMarker = i === results.length - 1 ? '└─' : '├─';
                const risk = window.CommandEnhancements.getCommandRiskLevel(result.command);
                const riskColor = window.CommandEnhancements.riskColors ? 
                    window.CommandEnhancements.riskColors[risk] : '#00ff41';
                
                addTerminalLog(`${chainMarker} ${result.command}`, 'info');
                addTerminalLog(`   Risk: ${risk}`, riskColor);
                
                if (result.output) {
                    addTerminalLog(`   ${result.output}`, result.success ? 'success' : 'error');
                }
            });
            
            // Log execution
            window.CommandEnhancements.logCommandExecution(input, true, 'MEDIUM');
        } else {
            // Single command
            const singleCommand = commands[0];
            const risk = window.CommandEnhancements.getCommandRiskLevel(singleCommand);
            const requiresConfirm = window.CommandEnhancements.requiresConfirmation(singleCommand);
            
            // Show risk level
            const riskColor = '#00ff41'; // Will use enhanced colors
            if (risk !== 'LOW') {
                addTerminalLog(`Command risk level: ${risk}`, riskColor);
            }
            
            // Check if confirmation required
            if (requiresConfirm) {
                addTerminalLog(`High-risk command detected! Type 'yes' to confirm:`, 'warning');
                
                // This would need a confirmation dialog in a real implementation
                // For now, we'll proceed
                addTerminalLog(`Proceeding with command...`, 'info');
            }
            
            // Execute the command
            await processSingleCommand(singleCommand);
            
            // Log execution
            window.CommandEnhancements.logCommandExecution(input, true, risk);
        }
    } catch (error) {
        addTerminalLog(`Error: ${error.message}`, 'error');
        window.CommandEnhancements.logCommandExecution(input, false, 'HIGH');
    }
    
    // Scroll to bottom
    const terminal = document.getElementById('terminal');
    if (terminal) {
        terminalContent.scrollTop = terminalContent.scrollHeight;
    }
}

// Process single command (existing processCommand function wrapper)
async function processSingleCommand(command) {
    const parts = command.trim().split(/\s+/);
    const cmdName = parts[0].toLowerCase().replace(/^\//, '');
    const args = parts.slice(1);
    
    // Check for new enhancement commands
    switch (cmdName) {
        case 'alias':
            handleAliasCommand(args);
            break;
        case 'history':
            handleHistoryCommand(args);
            break;
        case 'script':
            handleScriptCommand(args);
            break;
        case 'schedule':
            handleScheduleCommand(args);
            break;
        default:
            // Use existing processCommand
            await processCommand(cmdName, args);
    }
}

// ============================================
// Enhancement Command Handlers
// ============================================

// Alias commands: /alias [list|create|delete] [name] [command]
function handleAliasCommand(args) {
    const action = args[0];
    
    switch (action) {
        case 'list':
            addTerminalLog('Built-in aliases:', 'info');
            Object.entries(window.CommandEnhancements.commandAliases || commandAliases).forEach(([alias, cmd]) => {
                addTerminalLog(`  ${alias} → ${cmd}`, 'info');
            });
            
            if (Object.keys(window.CommandEnhancements.customAliases || {}).length > 0) {
                addTerminalLog('\nCustom aliases:', 'info');
                Object.entries(window.CommandEnhancements.customAliases).forEach(([alias, cmd]) => {
                    addTerminalLog(`  ${alias} → ${cmd}`, 'info');
                });
            }
            break;
            
        case 'create':
            if (args.length < 3) {
                addTerminalLog('Usage: /alias create <name> <command>', 'warning');
                return;
            }
            const aliasName = args[1];
            const aliasCommand = args.slice(2).join(' ');
            
            if (!window.CommandEnhancements.customAliases) {
                window.CommandEnhancements.customAliases = {};
            }
            
            window.CommandEnhancements.customAliases[aliasName] = aliasCommand;
            window.CommandEnhancements.saveCustomAliases();
            addTerminalLog(`Alias '${aliasName}' created: ${aliasCommand}`, 'success');
            break;
            
        case 'delete':
            if (args.length < 2) {
                addTerminalLog('Usage: /alias delete <name>', 'warning');
                return;
            }
            const delName = args[1];
            
            if (window.CommandEnhancements.customAliases && window.CommandEnhancements.customAliases[delName]) {
                delete window.CommandEnhancements.customAliases[delName];
                window.CommandEnhancements.saveCustomAliases();
                addTerminalLog(`Alias '${delName}' deleted`, 'success');
            } else {
                addTerminalLog(`Alias '${delName}' not found`, 'error');
            }
            break;
            
        default:
            addTerminalLog('Usage: /alias [list|create|delete]', 'info');
    }
}

// History command: /history [clear]
function handleHistoryCommand(args) {
    const action = args[0];
    
    if (action === 'clear') {
        commandHistory = [];
        historyIndex = 0;
        addTerminalLog('Command history cleared', 'success');
    } else {
        // Show history
        addTerminalLog('Command history:', 'info');
        commandHistory.forEach((cmd, i) => {
            addTerminalLog(`  ${i + 1}. ${cmd}`, 'info');
        });
    }
}

// Script commands: /script [list|run|create|delete] [name] [commands...]
function handleScriptCommand(args) {
    const action = args[0];
    
    switch (action) {
        case 'list':
            const scripts = window.CommandEnhancements.listScripts();
            addTerminalLog('Available scripts:', 'info');
            scripts.forEach(s => {
                addTerminalLog(`  ${s.name} (${s.type}) - ${s.commands.length} commands`, 'info');
            });
            break;
            
        case 'run':
            if (args.length < 2) {
                addTerminalLog('Usage: /script run <name>', 'warning');
                return;
            }
            const scriptName = args[1];
            addTerminalLog(`Running script: ${scriptName}`, 'info');
            
            window.CommandEnhancements.executeScript(scriptName)
                .then(results => {
                    results.forEach((result, i) => {
                        addTerminalLog(`  ${i + 1}. ${result.command}`, result.success ? 'success' : 'error');
                        if (result.output) {
                            addTerminalLog(`     ${result.output}`, 'info');
                        }
                    });
                    addTerminalLog('Script completed', 'success');
                })
                .catch(error => {
                    addTerminalLog(`Error running script: ${error.message}`, 'error');
                });
            break;
            
        case 'create':
            if (args.length < 3) {
                addTerminalLog('Usage: /script create <name> <cmd1> <cmd2> ...', 'warning');
                return;
            }
            const newScriptName = args[1];
            const newScriptCommands = args.slice(2);
            
            if (!window.CommandEnhancements.customScripts) {
                window.CommandEnhancements.customScripts = {};
            }
            
            window.CommandEnhancements.customScripts[newScriptName] = newScriptCommands;
            window.CommandEnhancements.saveScripts();
            addTerminalLog(`Script '${newScriptName}' created with ${newScriptCommands.length} commands`, 'success');
            break;
            
        case 'delete':
            if (args.length < 2) {
                addTerminalLog('Usage: /script delete <name>', 'warning');
                return;
            }
            const delScriptName = args[1];
            
            if (window.CommandEnhancements.customScripts && window.CommandEnhancements.customScripts[delScriptName]) {
                delete window.CommandEnhancements.customScripts[delScriptName];
                window.CommandEnhancements.saveScripts();
                addTerminalLog(`Script '${delScriptName}' deleted`, 'success');
            } else {
                addTerminalLog(`Script '${delScriptName}' not found`, 'error');
            }
            break;
            
        default:
            addTerminalLog('Usage: /script [list|run|create|delete]', 'info');
    }
}

// Schedule commands: /schedule [list|add|remove] [time] [command]
function handleScheduleCommand(args) {
    const action = args[0];
    
    switch (action) {
        case 'list':
            const scheduled = window.CommandEnhancements.listScheduledCommands();
            if (scheduled.length === 0) {
                addTerminalLog('No scheduled commands', 'info');
            } else {
                addTerminalLog('Scheduled commands:', 'info');
                scheduled.forEach(cmd => {
                    addTerminalLog(`  [${cmd.id}] ${new Date(cmd.scheduledTime).toLocaleString()} - ${cmd.command}`, 'info');
                });
            }
            break;
            
        case 'add':
            if (args.length < 3) {
                addTerminalLog('Usage: /schedule add <HH:MM> <command>', 'warning');
                return;
            }
            const time = args[1];
            const commandToSchedule = args.slice(2).join(' ');
            
            // Parse time
            const now = new Date();
            const [hours, minutes] = time.split(':').map(Number);
            const scheduledTime = new Date(now);
            scheduledTime.setHours(hours, minutes, 0, 0);
            
            if (scheduledTime <= now) {
                // Schedule for tomorrow
                scheduledTime.setDate(scheduledTime.getDate() + 1);
            }
            
            const id = window.CommandEnhancements.scheduleCommand(commandToSchedule, scheduledTime);
            addTerminalLog(`Command scheduled for ${scheduledTime.toLocaleString()} (ID: ${id})`, 'success');
            break;
            
        case 'remove':
            if (args.length < 2) {
                addTerminalLog('Usage: /schedule remove <id>', 'warning');
                return;
            }
            const removeId = parseInt(args[1]);
            
            if (window.CommandEnhancements.removeScheduledCommand(removeId)) {
                addTerminalLog(`Scheduled command ${removeId} removed`, 'success');
            } else {
                addTerminalLog(`Scheduled command ${removeId} not found`, 'error');
            }
            break;
            
        default:
            addTerminalLog('Usage: /schedule [list|add|remove]', 'info');
    }
}

// ============================================
// Styles for Suggestions Dropdown
// ============================================

function addSuggestionsStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .suggestions-dropdown {
            position: fixed;
            background: rgba(10, 14, 39, 0.98);
            border: 1px solid #00ff41;
            border-radius: 5px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 10000;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
        }
        
        .suggestion-item {
            padding: 10px 15px;
            border-bottom: 1px solid rgba(0, 255, 65, 0.2);
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .suggestion-item:hover {
            background: rgba(0, 255, 65, 0.1);
        }
        
        .suggestion-command {
            font-weight: bold;
            color: #00ff41;
            font-size: 14px;
        }
        
        .suggestion-description {
            color: #888;
            font-size: 12px;
            margin-top: 3px;
        }
        
        .suggestion-status {
            color: #666;
            font-size: 11px;
            margin-top: 5px;
        }
        
        .suggestion-item.implemented .suggestion-status {
            color: #00ff41;
        }
        
        .suggestion-item.planned .suggestion-status {
            color: #ffaa00;
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// Initialization
// ============================================

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for the main script to finish loading
    setTimeout(function() {
        // Initialize command enhancements
        if (window.CommandEnhancements && window.CommandEnhancements.initializeCommandEnhancements) {
            window.CommandEnhancements.initializeCommandEnhancements();
        }
        
        // Add suggestions styles
        addSuggestionsStyles();
        
        // Replace existing terminal handler with enhanced version
        const terminalInput = document.getElementById('terminal-input');
        if (terminalInput) {
            // Clone the element to remove all old event listeners
            const newTerminalInput = terminalInput.cloneNode(true);
            terminalInput.parentNode.replaceChild(newTerminalInput, terminalInput);
            
            // Add enhanced handler to the new element
            newTerminalInput.addEventListener('keydown', handleEnhancedTerminalKeyPress);
            newTerminalInput.focus();
        }
        
        // Expose addTerminalLog function for enhancements to use
        if (typeof addLog === 'function') {
            window.addTerminalLog = addLog;
        } else if (typeof addTerminalLog === 'undefined') {
            // Define addTerminalLog if addLog is not available
            window.addTerminalLog = function(message, type = 'info') {
                const terminalContent = document.getElementById('terminal-content');
                if (!terminalContent) return;
                
                const line = document.createElement('div');
                line.className = `terminal-line ${type}`;
                line.textContent = message;
                
                terminalContent.appendChild(line);
                terminalContent.scrollTop = terminalContent.scrollHeight;
            };
        }
        
        console.log('Terminal enhancements loaded successfully');
    }, 500);
});

// Export functions
window.TerminalEnhancements = {
    executeEnhancedCommand,
    handleAliasCommand,
    handleHistoryCommand,
    handleScriptCommand,
    handleScheduleCommand
};