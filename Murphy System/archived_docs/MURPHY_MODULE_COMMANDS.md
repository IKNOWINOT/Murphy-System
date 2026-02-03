# Murphy System - Commands by Module

Based on the actual Murphy System Runtime modules, here's how commands should be organized:

## Core System Modules

### 1. system_librarian.py
**Commands:**
- `/librarian search <query>` - Search knowledge base
- `/librarian transcripts` - View system transcripts
- `/librarian overview` - Get system overview
- `/librarian knowledge <topic>` - Get knowledge about topic

### 2. mfgc_core.py (Multi-Factor Generative Constraint)
**Commands:**
- `/mfgc phases` - Show 7 MFGC phases
- `/mfgc expand` - Expand domain expertise
- `/mfgc constrain` - Apply constraints
- `/mfgc collapse` - Collapse to essentials
- `/mfgc execute` - Execute MFGC workflow

### 3. advanced_swarm_system.py
**Commands:**
- `/swarm create <type>` - Create swarm (CREATIVE, ANALYTICAL, HYBRID, ADVERSARIAL, SYNTHESIS, OPTIMIZATION)
- `/swarm execute <task>` - Execute swarm task
- `/swarm status` - Show active swarms
- `/swarm results` - Get swarm results

### 4. gate_builder.py
**Commands:**
- `/gate list` - List all gates
- `/gate validate <gate_id>` - Validate specific gate
- `/gate create <type>` - Create new gate
- `/gate status` - Show gate validation status

### 5. constraint_system.py
**Commands:**
- `/constraint add <type>` - Add constraint (BUDGET, REGULATORY, ARCHITECTURAL, etc.)
- `/constraint list` - List all constraints
- `/constraint validate` - Validate constraints
- `/constraint conflicts` - Check for conflicts

### 6. organization_chart_system.py
**Commands:**
- `/org chart` - Show organization chart
- `/org agents` - List all agents
- `/org roles` - Show role definitions
- `/org assign <agent> <role>` - Assign agent to role

### 7. domain_engine.py
**Commands:**
- `/domain list` - List all domains
- `/domain create <name>` - Create new domain
- `/domain analyze <request>` - Analyze domain coverage
- `/domain impact` - Show cross-domain impact matrix

### 8. contractual_audit.py
**Commands:**
- `/audit gap` - Show productivity gap analysis
- `/audit drift` - Check agent drift
- `/audit contract` - View contract vs actual work
- `/audit report` - Generate audit report

### 9. learning_engine (learning_engine/)
**Commands:**
- `/learn enable` - Enable learning mode
- `/learn patterns` - Show learned patterns
- `/learn feedback` - Provide feedback
- `/learn adapt` - Adapt based on feedback

### 10. command_system.py
**Commands:**
- `/help` - Show all commands by module
- `/help <module>` - Show commands for specific module
- `/status` - System status
- `/initialize` - Initialize system

### 11. research_engine.py
**Commands:**
- `/research <topic>` - Conduct research
- `/research sources` - Show research sources
- `/research depth <level>` - Set research depth

### 12. reasoning_engine.py
**Commands:**
- `/reason <problem>` - Apply reasoning
- `/reason criteria <list>` - Set reasoning criteria
- `/reason method <type>` - Set reasoning method

### 13. document_processor.py
**Commands:**
- `/document create` - Create new document
- `/document magnify <domain>` - Add domain expertise
- `/document simplify` - Distill to essentials
- `/document solidify` - Lock for generation

### 14. task_executor.py
**Commands:**
- `/task create <description>` - Create task
- `/task assign <agent>` - Assign task to agent
- `/task status` - Show task status
- `/task complete <id>` - Mark task complete

### 15. state_machine.py
**Commands:**
- `/state list` - List all states
- `/state evolve <id>` - Evolve state
- `/state regenerate <id>` - Regenerate state
- `/state rollback <id>` - Rollback state

### 16. memory_artifact_system.py
**Commands:**
- `/artifact list` - List all artifacts
- `/artifact view <id>` - View artifact
- `/artifact create` - Create artifact
- `/artifact search <query>` - Search artifacts

### 17. llm_integration.py
**Commands:**
- `/llm status` - Show LLM status
- `/llm switch <provider>` - Switch LLM provider
- `/llm test` - Test LLM connection

### 18. verification_layer.py
**Commands:**
- `/verify <content>` - Verify with Aristotle
- `/verify gate <id>` - Verify gate
- `/verify state <id>` - Verify state

## Command Format

Each command should follow this structure:

```javascript
{
    command: "/module action",
    module: "module_name.py",
    description: "What it does",
    options: ["--option1", "--option2"],
    examples: ["/module action --option1=value"]
}
```

## Implementation Plan

1. **Extract module capabilities** from each .py file
2. **Map commands to modules** based on actual functions
3. **Create command registry** with module associations
4. **Update /help** to show commands grouped by module
5. **Wire each command** to its backend module
6. **Add Aristotle verification** for critical commands

This is the CORRECT way to organize commands - by actual Murphy System modules, not arbitrary categories.