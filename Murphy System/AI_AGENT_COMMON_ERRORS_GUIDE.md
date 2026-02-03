# AI Agent Common Errors and Prevention Guide

## Overview
This document identifies common errors AI agents make and provides strategies to prevent them, particularly in the context of implementing complex systems like Murphy.

## Known Weaknesses in AI Agent Behavior

### 1. Incomplete Context Analysis
**Error:** Starting implementation without fully understanding requirements
**Prevention:**
- Always scan entire codebase before making changes
- Read all relevant documentation files
- Check for existing implementations that might conflict
- Verify import statements and dependencies

### 2. Premature File Operations
**Error:** Creating, deleting, or modifying files before verifying their current state
**Prevention:**
- Use `grep`, `cat`, `head`, `tail` to inspect files first
- Check file existence with `ls` or `test`
- Read method signatures before calling functions
- Verify parameter names and types

### 3. Syntax Errors from Incomplete Replacements
**Error:** Using str-replace with incorrect old_str (partial matches, duplicates)
**Prevention:**
- Always include sufficient context in old_str (at least 3-5 lines)
- Check for duplicate code blocks
- Verify the replacement target exists and is unique
- Test after each major replacement

### 4. Dependency Chain Violations
**Error:** Initializing components in wrong order (parent before child)
**Prevention:**
- Map out dependency chains before implementation
- Check __init__ signatures for required parameters
- Initialize base components first
- Test initialization incrementally

### 5. Method Signature Mismatches
**Error:** Calling functions with wrong parameter names or types
**Prevention:**
- Always grep method definitions before calling
- Check for optional vs required parameters
- Verify return types
- Match parameter names exactly

### 6. Missing Error Handling
**Error:** Not handling exceptions from external systems
**Prevention:**
- Wrap all external API calls in try-except
- Check for None returns
- Validate responses before use
- Provide meaningful error messages

### 7. Overlooking Async/Sync Differences
**Error:** Calling async methods synchronously or vice versa
**Prevention:**
- Check if methods are async (async def)
- Use asyncio.run() or event loops for async calls
- Provide fallback sync implementations when needed
- Document async requirements

### 8. Hardcoding Values
**Error:** Using hardcoded values instead of configuration
**Prevention:**
- Use environment variables for secrets
- Create configuration classes
- Avoid magic numbers
- Document configuration options

### 9. Incomplete Testing
**Error:** Not testing after making changes
**Prevention:**
- Test every new endpoint immediately
- Verify server restarts successfully
- Check logs for errors
- Test happy path and error cases

### 10. Ignoring Logs and Errors
**Error:** Continuing despite visible errors in logs
**Prevention:**
- Always check server logs after restart
- Investigate WARNING messages
- Fix errors before proceeding
- Document workarounds with TODO comments

### 11. Race Conditions in Background Processes
**Error:** Not waiting for background processes to start
**Prevention:**
- Use `sleep` after starting background services
- Check process status with `ps aux`
- Verify port availability with `netstat`
- Use health check endpoints

### 12. File Path Issues
**Error:** Using wrong file paths (absolute vs relative)
**Prevention:**
- Always use relative paths from workspace
- Use proper file operations tools
- Don't construct paths manually
- Verify files exist before operations

### 13. Documentation Drift
**Error:** Code changes without documentation updates
**Prevention:**
- Update docs immediately after changes
- Keep changelogs
- Document API changes
- Mark tasks complete in todo.md

### 14. Breaking Existing Functionality
**Error:** Changes break previously working features
**Prevention:**
- Test existing endpoints after changes
- Run integration tests
- Check for regressions
- Preserve backward compatibility

### 15. Over-Engineering
**Error:** Building complex solutions for simple problems
**Prevention:**
- Start with simplest solution
- Add complexity only when needed
- Follow YAGNI principle
- Prefer standard library over custom code

## Specific Anti-Patterns

### Anti-Pattern 1: "Assume It Works"
```python
# BAD - Assumes method exists and works
artifact = artifact_manager.get_artifact(id)

# GOOD - Check first
if artifact_manager and hasattr(artifact_manager, 'get_artifact'):
    artifact = artifact_manager.get_artifact(id)
```

### Anti-Pattern 2: "String Replacement Roulette"
```python
# BAD - Too little context
str_replace(file, "def foo", "def bar")

# GOOD - Sufficient context
str_replace(file, 
    "def foo():\n    return 42",
    "def bar():\n    return 43"
)
```

### Anti-Pattern 3: "Copy-Paste Blindness"
```python
# BAD - Copied from similar but different API
artifact.generate(content=content)

# GOOD - Checked actual signature
artifact.generate(document=document, prompts=prompts)
```

### Anti-Pattern 4: "Silent Failure"
```python
# BAD - Ignores errors
try:
    result = risky_operation()
except:
    pass

# GOOD - Logs errors
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise
```

## Best Practices Checklist

Before any operation:
- [ ] Read the file or documentation first
- [ ] Check for existing implementations
- [ ] Verify method signatures
- [ ] Map out dependencies
- [ ] Plan the approach

During implementation:
- [ ] Use grep to verify code exists
- [ ] Include context in replacements
- [ ] Handle all error cases
- [ ] Log important events
- [ ] Test incrementally

After implementation:
- [ ] Restart services
- [ ] Check logs for errors
- [ ] Test new functionality
- [ ] Test existing functionality
- [ ] Update documentation

## State of the Art Standards

1. **Type Hints**: Always use type hints for function parameters and returns
2. **Docstrings**: Complete docstrings with Args, Returns, Raises
3. **Error Handling**: Comprehensive error handling with meaningful messages
4. **Logging**: Structured logging at appropriate levels
5. **Testing**: Unit tests for all critical paths
6. **Documentation**: README, API docs, examples
7. **Code Review**: Self-review against this checklist
8. **Version Control**: Clear commit messages
9. **Configuration**: Externalized configuration
10. **Monitoring**: Metrics and health checks

## Implementation Order Rules

1. **Infrastructure first**: Setup, configuration, dependencies
2. **Core components**: Base classes, utilities
3. **Dependent components**: Things that depend on core
4. **Integration layers**: Connecting components
5. **API layer**: Endpoints and handlers
6. **Testing**: Unit, integration, e2e
7. **Documentation**: All docs

## Syntax Closing Rules

1. **Always match braces**: { }, ( ), [ ]
2. **Close strings**: " ", ' ', """ """
3. **Close code blocks**: if, for, while, try, def, class
4. **End imports**: No hanging imports
5. **Complete functions**: All code paths return
6. **Close files**: File operations completed
7. **Release resources**: Context managers used
8. **End statements**: Semicolons where needed

## Quality Gates

Before marking a task complete:
1. ✅ No syntax errors
2. ✅ All tests passing
3. ✅ No warnings in logs
4. ✅ Documentation updated
5. ✅ Existing features working
6. ✅ New features tested
7. ✅ Code reviewed against this guide