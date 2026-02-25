# Module-Based Commands Implementation

## What Changed

### Before (Incorrect)
Commands were organized by arbitrary categories (System, State, Execution, etc.) with no connection to actual Murphy System modules.

### After (Correct)
Commands are now organized by **actual Murphy System modules** from the runtime, showing clear mapping between commands and the code that implements them.

## New Command Structure

### Commands by Module

```
murphy_complete_v2.html now contains:

availableCommands = {
    'command_system.py': [...],
    'system_librarian.py': [...],
    'advanced_swarm_system.py': [...],
    'gate_builder.py': [...],
    'state_machine.py': [...],
    'organization_chart_system.py': [...],
    'constraint_system.py': [...],
    'domain_engine.py': [...],
    'document_processor.py': [...],
    'memory_artifact_system.py': [...],
    'verification_layer.py': [...],
    'llm_integration.py': [...]
}
```

Each command entry includes:
- `name`: Command name
- `description`: What it does
- `options`: Required parameters
- `implemented`: Boolean flag (✓ or ○)

## New /help Output

### `/help` (Show all modules)
```
=== Murphy System Commands by Module ===

[command_system.py] (4 implemented, 0 planned)
  ✓ /help                    - Show all commands by module
  ✓ /status                  - Show system status
  ✓ /initialize              - Initialize Murphy System
  ✓ /clear                   - Clear terminal output

[system_librarian.py] (0 implemented, 4 planned)
  ○ /librarian search <query>     - Search knowledge base
  ○ /librarian transcripts        - View system transcripts
  ○ /librarian overview           - Get system overview
  ○ /librarian knowledge <topic>  - Get knowledge about topic

[advanced_swarm_system.py] (0 implemented, 4 planned)
  ○ /swarm create <type>     - Create swarm
  ○ /swarm execute <task>    - Execute swarm task
  ○ /swarm status            - Show active swarms
  ○ /swarm results           - Get swarm results

... (continues for all modules)

Total: 13 implemented, 35 planned

Type /help <module.py> to see commands for a specific module
Legend: ✓ = Implemented, ○ = Planned
```

### `/help system_librarian.py` (Show specific module)
```
=== system_librarian.py ===

  ○ /librarian search <query>
     Search knowledge base
  ○ /librarian transcripts
     View system transcripts
  ○ /librarian overview
     Get system overview
  ○ /librarian knowledge <topic>
     Get knowledge about topic

Legend: ✓ = Implemented, ○ = Planned
```

## Command Handlers

Each module now has a dedicated handler function:

- `handleStateCommand()` - state_machine.py commands
- `handleOrgCommand()` - organization_chart_system.py commands
- `handleLibrarianCommand()` - system_librarian.py commands
- `handleSwarmCommand()` - advanced_swarm_system.py commands
- `handleGateCommand()` - gate_builder.py commands
- `handleDocumentCommand()` - document_processor.py commands
- `handleArtifactCommand()` - memory_artifact_system.py commands
- `handleDomainCommand()` - domain_engine.py commands
- `handleConstraintCommand()` - constraint_system.py commands
- `handleVerifyCommand()` - verification_layer.py commands
- `handleLLMCommand()` - llm_integration.py commands

## Command Syntax

### Multi-word Commands
Commands now support module-based syntax:

```bash
/state list              # List all states
/state evolve <id>       # Evolve a state
/librarian search <query> # Search knowledge base
/swarm create CREATIVE   # Create creative swarm
/gate validate <id>      # Validate gate
```

### Backward Compatibility
Old single-word commands still work:

```bash
/states                  # Same as /state list
/agents                  # Same as /org agents
/evolve <id>             # Same as /state evolve <id>
```

## Implementation Status

### ✓ Fully Implemented (13 commands)
1. `/help` - Show commands by module
2. `/help <module>` - Show module-specific commands
3. `/status` - System status
4. `/initialize` - Initialize system
5. `/clear` - Clear terminal
6. `/state list` - List states
7. `/state evolve` - Evolve state
8. `/state regenerate` - Regenerate state
9. `/state rollback` - Rollback state
10. `/org agents` - List agents
11. `/llm status` - LLM status
12. `/agents` - (alias for /org agents)
13. `/states` - (alias for /state list)

### ○ Planned (35 commands)
All other commands show "not yet implemented" warnings but have proper handlers ready for backend integration.

## Benefits of Module-Based Organization

1. **Clear Mapping**: Each command maps to actual Murphy System module
2. **Discoverability**: Users can see which module provides which functionality
3. **Maintainability**: Easy to add commands when modules are added
4. **Documentation**: Help system documents actual system architecture
5. **Honesty**: Clear distinction between implemented (✓) and planned (○)

## Next Steps

To make planned commands functional:

1. **Wire to Backend**: Connect each handler to corresponding backend module
2. **Add API Endpoints**: Create backend endpoints for each command
3. **Implement Logic**: Add actual functionality from murphy_system_runtime
4. **Add Aristotle Verification**: Use Aristotle for deterministic verification
5. **Update Status**: Change `implemented: false` to `implemented: true`

## Files Modified

- `murphy_complete_v2.html` - Complete rewrite of command system
  - New `availableCommands` structure (organized by module)
  - New `showHelp()` function (shows modules)
  - New `processCommand()` function (handles multi-word commands)
  - 11 new handler functions (one per module)
  - Removed old help functions

## Testing

```bash
# Test the new help system
/help                           # Show all modules
/help system_librarian.py       # Show librarian commands
/help state_machine.py          # Show state commands

# Test multi-word commands
/state list                     # List states
/librarian search "constraints" # Search (shows not implemented)
/swarm create CREATIVE          # Create swarm (shows not implemented)

# Test backward compatibility
/states                         # Still works
/agents                         # Still works
/evolve <id>                    # Still works
```

## Public URL

https://3000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai

## Summary

The command system now accurately reflects the Murphy System architecture by organizing commands according to actual runtime modules. This provides:

- **Transparency**: Clear about what's implemented vs planned
- **Accuracy**: Commands map to real modules
- **Scalability**: Easy to add commands as modules are wired
- **Documentation**: Help system documents actual system structure

**Status**: Module-based command organization complete. Ready for backend integration.