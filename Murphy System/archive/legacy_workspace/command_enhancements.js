// Murphy System - Command Enhancements Module
// Priority 3: Command System Enhancement

// ============================================
// Phase 1: Command Aliases
// ============================================

const commandAliases = {
    // Single-character aliases
    'h': 'help',
    's': 'status',
    'i': 'initialize',
    'c': 'clear',
    
    // Common multi-word aliases
    'ls': 'state list',
    'sl': 'state list',
    'se': 'state evolve',
    'sr': 'state regenerate',
    'srb': 'state rollback',
    
    'oa': 'org agents',
    'oc': 'org chart',
    
    'll': 'llm status',
    
    // Module shortcuts
    'swarm': 'swarm status',
    'gate': 'gate list',
    'domain': 'domain list',
    'constraint': 'constraint list',
    'artifact': 'artifact list',
    'doc': 'document create',
    'verify': 'verify content'
};

// User-defined custom aliases (stored in localStorage)
let customAliases = {};

// Load custom aliases from localStorage
function loadCustomAliases() {
    try {
        const saved = localStorage.getItem('murphy_custom_aliases');
        if (saved) {
            customAliases = JSON.parse(saved);
        }
    } catch (e) {
        console.error('Error loading custom aliases:', e);
    }
}

// Save custom aliases to localStorage
function saveCustomAliases() {
    try {
        localStorage.setItem('murphy_custom_aliases', JSON.stringify(customAliases));
    } catch (e) {
        console.error('Error saving custom aliases:', e);
    }
}

// Resolve alias to full command
function resolveAlias(command) {
    // First check built-in aliases
    if (commandAliases[command]) {
        return commandAliases[command];
    }
    
    // Then check custom aliases
    if (customAliases[command]) {
        return customAliases[command];
    }
    
    // Return original if no alias found
    return command;
}

// ============================================
// Phase 2: Command Permissions and Risk Validation
// ============================================

const commandRiskLevels = {
    'help': 'LOW',
    'status': 'LOW',
    'initialize': 'LOW',
    'clear': 'LOW',
    
    'state list': 'LOW',
    'state evolve': 'MEDIUM',
    'state regenerate': 'MEDIUM',
    'state rollback': 'HIGH',
    
    'org agents': 'LOW',
    'org chart': 'LOW',
    'org assign': 'HIGH',
    
    'swarm create': 'MEDIUM',
    'swarm execute': 'HIGH',
    'swarm status': 'LOW',
    
    'gate list': 'LOW',
    'gate validate': 'MEDIUM',
    'gate create': 'HIGH',
    
    'domain list': 'LOW',
    'domain create': 'HIGH',
    'domain analyze': 'LOW',
    
    'constraint add': 'MEDIUM',
    'constraint list': 'LOW',
    
    'document create': 'LOW',
    'document magnify': 'MEDIUM',
    'document simplify': 'MEDIUM',
    'document solidify': 'HIGH',
    
    'artifact create': 'MEDIUM',
    'artifact delete': 'HIGH',
    
    'llm status': 'LOW',
    'llm switch': 'MEDIUM'
};

const riskColors = {
    'LOW': '#00ff41',
    'MEDIUM': '#ffaa00',
    'HIGH': '#ff4141',
    'CRITICAL': '#ff00ff'
};

const riskConfirmations = {
    'HIGH': true,  // Always require confirmation
    'CRITICAL': true
};

// Command execution history for audit trail
let commandHistory = [];

// Get risk level for a command
function getCommandRiskLevel(command) {
    // Check exact match first
    if (commandRiskLevels[command]) {
        return commandRiskLevels[command];
    }
    
    // Check partial match for multi-word commands
    const parts = command.split(' ');
    const baseCommand = parts.slice(0, 2).join(' ');
    if (commandRiskLevels[baseCommand]) {
        return commandRiskLevels[baseCommand];
    }
    
    return 'LOW';  // Default to low risk
}

// Check if command requires confirmation
function requiresConfirmation(command) {
    const risk = getCommandRiskLevel(command);
    return riskConfirmations[risk] || false;
}

// Log command execution
function logCommandExecution(command, success, risk) {
    const entry = {
        timestamp: new Date().toISOString(),
        command: command,
        success: success,
        risk: risk,
        user: 'current'
    };
    
    commandHistory.push(entry);
    
    // Keep only last 1000 entries
    if (commandHistory.length > 1000) {
        commandHistory = commandHistory.slice(-1000);
    }
    
    // Save to localStorage
    try {
        localStorage.setItem('murphy_command_history', JSON.stringify(commandHistory));
    } catch (e) {
        console.error('Error saving command history:', e);
    }
}

// ============================================
// Phase 3: Tab Autocomplete
// ============================================

// Get command suggestions based on input
function getCommandSuggestions(input) {
    const suggestions = [];
    const trimmedInput = input.trim().toLowerCase();
    
    if (!trimmedInput) {
        return [];
    }
    
    // Iterate through all available commands
    Object.keys(availableCommands).forEach(module => {
        availableCommands[module].forEach(cmd => {
            const fullCommand = cmd.name;
            
            // Check if command starts with input
            if (fullCommand.toLowerCase().startsWith(trimmedInput)) {
                suggestions.push({
                    command: fullCommand,
                    module: module,
                    implemented: cmd.implemented,
                    description: cmd.description
                });
            }
        });
    });
    
    // Also check aliases
    Object.keys(commandAliases).forEach(alias => {
        if (alias.toLowerCase().startsWith(trimmedInput)) {
            suggestions.push({
                command: alias,
                module: 'aliases',
                implemented: true,
                description: `Alias for: ${commandAliases[alias]}`
            });
        }
    });
    
    // Sort suggestions: implemented first, then alphabetically
    suggestions.sort((a, b) => {
        if (a.implemented !== b.implemented) {
            return b.implemented - a.implemented;
        }
        return a.command.localeCompare(b.command);
    });
    
    return suggestions;
}

// Complete command with Tab
function autocompleteCommand(input) {
    const suggestions = getCommandSuggestions(input);
    
    if (suggestions.length === 0) {
        return input;
    }
    
    if (suggestions.length === 1) {
        // Only one match, complete it
        return suggestions[0].command + ' ';
    }
    
    // Multiple matches, find common prefix
    const first = suggestions[0].command;
    let commonPrefix = first;
    
    for (let i = 1; i < suggestions.length; i++) {
        const current = suggestions[i].command;
        let j = 0;
        
        while (j < Math.min(commonPrefix.length, current.length) && 
               commonPrefix[j].toLowerCase() === current[j].toLowerCase()) {
            j++;
        }
        
        commonPrefix = commonPrefix.slice(0, j);
    }
    
    return commonPrefix + ' ';
}

// ============================================
// Phase 4: Command Chaining with | Operator
// ============================================

// Parse command chain
function parseCommandChain(input) {
    if (!input.includes('|')) {
        return [input.trim()];
    }
    
    // Split by pipe operator, but respect quoted strings
    const commands = [];
    let current = '';
    let inQuotes = false;
    let quoteChar = '';
    
    for (let i = 0; i < input.length; i++) {
        const char = input[i];
        
        if ((char === '"' || char === "'") && (i === 0 || input[i-1] !== '\\')) {
            if (!inQuotes) {
                inQuotes = true;
                quoteChar = char;
            } else if (char === quoteChar) {
                inQuotes = false;
            }
            current += char;
        } else if (char === '|' && !inQuotes) {
            commands.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }
    
    if (current.trim()) {
        commands.push(current.trim());
    }
    
    return commands;
}

// Execute command chain
async function executeCommandChain(commands) {
    let lastOutput = null;
    const results = [];
    
    for (let i = 0; i < commands.length; i++) {
        const cmd = commands[i];
        
        // Replace {pipe} with output from previous command
        const actualCmd = cmd.replace(/\{pipe\}/g, lastOutput || '');
        
        try {
            const result = await executeSingleCommand(actualCmd, lastOutput);
            lastOutput = result.output;
            results.push({
                command: actualCmd,
                success: result.success,
                output: result.output
            });
            
            if (!result.success) {
                // Stop on error
                break;
            }
        } catch (error) {
            results.push({
                command: actualCmd,
                success: false,
                output: `Error: ${error.message}`
            });
            break;
        }
    }
    
    return results;
}

// Execute single command with pipe input
async function executeSingleCommand(command, pipeInput) {
    // Parse command
    const parts = command.split(' ');
    const cmdName = parts[0].toLowerCase();
    const args = parts.slice(1);
    
    // If pipe input exists, prepend to args
    if (pipeInput) {
        args.unshift(pipeInput);
    }
    
    // Execute the command
    return await processCommand(cmdName, args);
}

// ============================================
// Phase 5: Command Scripts
// ============================================

// Built-in scripts
const builtInScripts = {
    'init-and-explore': [
        'initialize',
        'status',
        'state list',
        'org agents'
    ],
    'full-workflow': [
        'initialize',
        'state list',
        'state evolve 1',
        'state list',
        'gate list'
    ],
    'agent-check': [
        'org agents',
        'llm status',
        'status'
    ]
};

// User-defined scripts
let customScripts = {};

// Load scripts from localStorage
function loadScripts() {
    try {
        const saved = localStorage.getItem('murphy_scripts');
        if (saved) {
            customScripts = JSON.parse(saved);
        }
    } catch (e) {
        console.error('Error loading scripts:', e);
    }
}

// Save scripts to localStorage
function saveScripts() {
    try {
        localStorage.setItem('murphy_scripts', JSON.stringify(customScripts));
    } catch (e) {
        console.error('Error saving scripts:', e);
    }
}

// List all available scripts
function listScripts() {
    const scripts = [];
    
    // Built-in scripts
    Object.keys(builtInScripts).forEach(name => {
        scripts.push({
            name: name,
            type: 'built-in',
            commands: builtInScripts[name]
        });
    });
    
    // Custom scripts
    Object.keys(customScripts).forEach(name => {
        scripts.push({
            name: name,
            type: 'custom',
            commands: customScripts[name]
        });
    });
    
    return scripts;
}

// Execute a script
async function executeScript(scriptName) {
    let commands = [];
    
    // Check built-in scripts
    if (builtInScripts[scriptName]) {
        commands = builtInScripts[scriptName];
    }
    // Check custom scripts
    else if (customScripts[scriptName]) {
        commands = customScripts[scriptName];
    }
    else {
        throw new Error(`Script '${scriptName}' not found`);
    }
    
    const results = [];
    for (let i = 0; i < commands.length; i++) {
        const cmd = commands[i];
        try {
            const result = await executeCommandChain([cmd]);
            results.push(result[0]);
            
            if (!result[0].success) {
                break;
            }
        } catch (error) {
            results.push({
                command: cmd,
                success: false,
                output: `Error: ${error.message}`
            });
            break;
        }
    }
    
    return results;
}

// ============================================
// Phase 6: Command Scheduling
// ============================================

// Scheduled commands storage
let scheduledCommands = [];

// Load scheduled commands from localStorage
function loadScheduledCommands() {
    try {
        const saved = localStorage.getItem('murphy_scheduled');
        if (saved) {
            scheduledCommands = JSON.parse(saved);
            // Convert timestamp strings back to Date objects
            scheduledCommands.forEach(cmd => {
                cmd.scheduledTime = new Date(cmd.scheduledTime);
            });
        }
    } catch (e) {
        console.error('Error loading scheduled commands:', e);
    }
}

// Save scheduled commands to localStorage
function saveScheduledCommands() {
    try {
        localStorage.setItem('murphy_scheduled', JSON.stringify(scheduledCommands));
    } catch (e) {
        console.error('Error saving scheduled commands:', e);
    }
}

// Schedule a command
function scheduleCommand(command, time) {
    const scheduledCmd = {
        id: Date.now(),
        command: command,
        scheduledTime: time,
        status: 'pending'
    };
    
    scheduledCommands.push(scheduledCmd);
    saveScheduledCommands();
    
    return scheduledCmd.id;
}

// List scheduled commands
function listScheduledCommands() {
    return scheduledCommands.filter(cmd => cmd.status === 'pending');
}

// Remove scheduled command
function removeScheduledCommand(id) {
    const index = scheduledCommands.findIndex(cmd => cmd.id === id);
    if (index !== -1) {
        scheduledCommands.splice(index, 1);
        saveScheduledCommands();
        return true;
    }
    return false;
}

// Check for due commands (call periodically)
function checkScheduledCommands() {
    const now = new Date();
    const dueCommands = [];
    
    scheduledCommands.forEach(cmd => {
        if (cmd.status === 'pending' && cmd.scheduledTime <= now) {
            dueCommands.push(cmd);
            cmd.status = 'executing';
        }
    });
    
    saveScheduledCommands();
    
    // Execute due commands
    dueCommands.forEach(cmd => {
        executeCommandChain([cmd.command])
            .then(result => {
                cmd.status = result[0].success ? 'completed' : 'failed';
                cmd.result = result[0];
                cmd.executedAt = new Date();
                saveScheduledCommands();
            })
            .catch(error => {
                cmd.status = 'failed';
                cmd.error = error.message;
                cmd.executedAt = new Date();
                saveScheduledCommands();
            });
    });
    
    return dueCommands;
}

// ============================================
// Initialization
// ============================================

// Initialize all enhancement systems
function initializeCommandEnhancements() {
    loadCustomAliases();
    loadScripts();
    loadScheduledCommands();
    
    // Start scheduler check every second
    setInterval(checkScheduledCommands, 1000);
    
    console.log('Command enhancements initialized');
}

// Export functions for use in main application
window.CommandEnhancements = {
    resolveAlias,
    getCommandRiskLevel,
    requiresConfirmation,
    logCommandExecution,
    getCommandSuggestions,
    autocompleteCommand,
    parseCommandChain,
    executeCommandChain,
    listScripts,
    executeScript,
    scheduleCommand,
    listScheduledCommands,
    removeScheduledCommand,
    initializeCommandEnhancements,
    loadCustomAliases,
    saveCustomAliases,
    loadScripts,
    saveScripts
};