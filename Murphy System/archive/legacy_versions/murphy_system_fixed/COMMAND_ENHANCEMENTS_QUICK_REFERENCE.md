# Murphy System - Command Enhancements Quick Reference

## Table of Contents
1. [Command Aliases](#command-aliases)
2. [Tab Autocomplete](#tab-autocomplete)
3. [Command Chaining](#command-chaining)
4. [Command Scripts](#command-scripts)
5. [Command Scheduling](#command-scheduling)
6. [Command History](#command-history)
7. [Risk Levels](#risk-levels)

---

## Command Aliases

Quick shortcuts for common commands.

### Single-Character Aliases
```
h     → /help
s     → /status
i     → /initialize
c     → /clear
```

### Multi-Word Aliases
```
ls, sl     → /state list
se         → /state evolve
sr         → /state regenerate
srb        → /state rollback
oa         → /org agents
oc         → /org chart
ll         → /llm status
```

### Module Shortcuts
```
swarm      → /swarm status
gate       → /gate list
domain     → /domain list
constraint → /constraint list
artifact   → /artifact list
doc        → /document create
verify     → /verify content
```

### Managing Custom Aliases
```bash
/alias list                    # Show all aliases
/alias create <name> <cmd>     # Create custom alias
/alias delete <name>           # Delete custom alias
```

**Example:**
```bash
/alias create check /status /llm status
check                           # Runs both commands
```

---

## Tab Autocomplete

Press **Tab** to autocomplete commands or see suggestions.

### Usage
1. Type partial command: `/sta`
2. Press **Tab**
3. See suggestions or autocomplete

### Examples
```bash
/s<TAB>          # Shows: status, state list, script list, swarm status
/st<TAB>         # Autocompletes to: /state 
/state l<TAB>    # Autocompletes to: /state list 
/org a<TAB>      # Autocompletes to: /org agents 
```

### Suggestion Display
- ✓ Green check = Command is implemented
- ○ Orange circle = Command is planned
- Shows module name and description
- Click to select

---

## Command Chaining

Use `|` to chain multiple commands together.

### Basic Usage
```bash
/command1 | /command2 | /command3
```

### Examples
```bash
# Initialize and check status
/initialize | /status

# List states then evolve first one
/state list | /state evolve 1

# Full workflow chain
/initialize | /state list | /org agents | /status

# Get status and then list agents
/status | /org agents
```

### Chain Behavior
- Commands execute left to right
- Output from command N becomes input to command N+1
- Chain stops on error
- Shows visual markers: ├─ and └─

---

## Command Scripts

Execute multiple commands with a single script.

### Built-in Scripts
```bash
/init-and-explore    → Initialize, status, states, agents
/full-workflow       → Initialize, states, evolve, gates
/agent-check         → Check agents, LLMs, system status
```

### Script Commands
```bash
/script list                          # List all scripts
/script run <name>                    # Run a script
/script create <name> <cmd1> <cmd2>   # Create custom script
/script delete <name>                 # Delete script
```

### Examples
```bash
# List available scripts
/script list

# Run built-in script
/script run init-and-explore

# Create custom script
/script create my-routine /status /state list /org agents

# Run custom script
/script run my-routine

# Delete script
/script delete my-routine
```

### Script Workflow
Scripts execute commands sequentially:
- Each command completes before next starts
- Script stops on error
- Shows progress for each command

---

## Command Scheduling

Schedule commands to run at specific times.

### Schedule Commands
```bash
/schedule list                     # List scheduled commands
/schedule add <HH:MM> <command>    # Schedule a command
/schedule remove <id>              # Remove scheduled command
```

### Examples
```bash
# Schedule status check for 10:00 AM
/schedule add 10:00 /status

# Schedule state evolution for 2:30 PM
/schedule add 14:30 /state evolve 1

# Schedule multiple commands
/schedule add 09:00 /initialize
/schedule add 09:15 /status
/schedule add 09:30 /org agents

# View scheduled commands
/schedule list

# Remove a scheduled command
/schedule remove 1234567890
```

### Time Format
- 24-hour format: HH:MM
- Example: 10:00, 14:30, 23:45
- If time has passed today, schedules for tomorrow

### Scheduler Behavior
- Checks every second
- Executes command at scheduled time
- Must have tab open to execute
- Stores result (completed/failed)

---

## Command History

View your command execution history.

### History Commands
```bash
/history           # View command history
/history clear     # Clear command history
```

### History Features
- Shows last 1000 commands
- Includes timestamp
- Shows success/failure
- Shows risk level
- Persists across sessions

### Example Output
```
Command history:
  1. /status
  2. /state list
  3. /state evolve 1
  4. /initialize | /status
```

### Arrow Keys
- **Arrow Up** - Navigate back in history
- **Arrow Down** - Navigate forward in history

---

## Risk Levels

Commands are classified by risk level.

### LOW Risk
Executes immediately, no confirmation.
```
help, status, initialize, clear
state list, org agents, org chart
llm status, gate list, domain list
constraint list, artifact list
```

### MEDIUM Risk
Shows risk level, may require confirmation.
```
state evolve, state regenerate
swarm create, gate validate
domain analyze, constraint add
document magnify, document simplify
```

### HIGH Risk
Requires confirmation before execution.
```
state rollback, org assign
swarm execute, gate create
domain create, document solidify
artifact delete
```

### Risk Colors
- 🟢 GREEN = LOW
- 🟡 YELLOW = MEDIUM
- 🔴 RED = HIGH

### Example
```bash
/status                  # LOW - executes immediately
/state evolve 1          # MEDIUM - shows risk level
/state rollback 1        # HIGH - requires confirmation
```

---

## Advanced Examples

### Example 1: Morning Routine Script
```bash
/script create morning-routine /initialize /status /org agents /llm status
/script run morning-routine
```

### Example 2: Scheduled Daily Checks
```bash
/schedule add 09:00 /status
/schedule add 12:00 /state list
/schedule add 18:00 /org agents
```

### Example 3: Custom Alias for Common Task
```bash
/alias create check-all /status /llm status /org agents
check-all
```

### Example 4: Complex Chain
```bash
/initialize | /state list | /state evolve 1 | /gate list | /status
```

### Example 5: Using History
```bash
# View recent commands
/history

# Use arrow keys to navigate
# Press Enter to re-execute
```

---

## Tips & Tricks

1. **Use aliases for frequently used commands**
   ```bash
   # Instead of typing /state list every time
   /alias create sl /state list
   sl  # Much faster!
   ```

2. **Chain commands for workflows**
   ```bash
   # One command instead of four
   /init | /status | /state list | /org agents
   ```

3. **Create scripts for repetitive tasks**
   ```bash
   # Save time with scripts
   /script create daily /status /state list /org agents
   /script run daily
   ```

4. **Schedule maintenance tasks**
   ```bash
   # Automate regular checks
   /schedule add 10:00 /status
   /schedule add 14:00 /llm status
   ```

5. **Use Tab to explore commands**
   ```bash
   # Don't remember exact command?
   /sw<TAB>  # See all swarm commands
   ```

6. **Check risk before executing**
   ```bash
   # Unsure about a command?
   # Try it with low-risk first
   /state list     # LOW - safe to try
   /state evolve   # MEDIUM - shows risk
   /state rollback # HIGH - be careful!
   ```

7. **Review history to audit actions**
   ```bash
   /history  # See what you've done
   ```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Execute command |
| Tab | Autocomplete |
| Arrow Up | Previous command in history |
| Arrow Down | Next command in history |
| Escape | Clear suggestions |

---

## Storage & Persistence

All enhancements use **localStorage** for persistence:

- **Custom aliases**: Survive page refresh
- **Command history**: Survive page refresh (1000 entries)
- **Custom scripts**: Survive page refresh
- **Scheduled commands**: Survive page refresh

**Note:** localStorage is browser-specific. Data doesn't sync across browsers or devices.

---

## Troubleshooting

### Autocomplete not working?
- Make sure terminal input is focused
- Press Tab after typing partial command
- Check browser console for errors

### Custom alias not working?
- Check alias was created: `/alias list`
- Verify alias name is correct
- Try recreating: `/alias create <name> <command>`

### Script not executing?
- Check script exists: `/script list`
- Verify script name is correct
- Check terminal for error messages

### Scheduled command didn't run?
- Verify time format (HH:MM)
- Check if tab was open at scheduled time
- Review scheduled commands: `/schedule list`
- Check terminal for errors

### Command chain stops early?
- Review terminal output for errors
- Check each command in the chain
- Test commands individually first

---

## Need More Help?

Type `/help` in the terminal to see all available commands.

For detailed documentation, see:
- `PRIORITY3_IMPLEMENTATION_COMPLETE.md` - Full implementation details
- `priority3_plan.md` - Implementation plan
- `MURPHY_SYSTEM_MASTER_SPECIFICATION.md` - Master system specification

---

**Version:** Murphy System v2.0  
**Priority 3 Status:** ✅ Complete  
**Date:** January 21, 2026