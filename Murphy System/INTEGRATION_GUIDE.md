# Integration Guide - Option C Systems

## Overview

This guide provides step-by-step instructions for integrating the Option C systems into the Murphy backend.

## Files to Integrate

### 1. Enhanced Librarian System
**File:** `enhanced_librarian_system.py` (1,200+ lines)

### 2. Executive Bot System
**File:** `executive_bot_system.py` (800+ lines)

### 3. Hybrid Command System
**File:** `hybrid_command_system.py` (700+ lines)

### 4. Enhanced Librarian UI
**File:** `enhanced_librarian_ui.js` (600+ lines)

---

## Step 1: Add Imports to Backend

**File:** `murphy_backend_complete.py`

**Location:** After existing imports, around line 50-100

**Add this code:**

```python
# Enhanced Systems Integration (Option C)
from enhanced_librarian_system import EnhancedLibrarianSystem, DiscoveryPhase
from executive_bot_system import ExecutiveBotManager, BotRole
from hybrid_command_system import HybridCommandSystem
```

---

## Step 2: Initialize Systems

**File:** `murphy_backend_complete.py`

**Location:** After librarian initialization, look for:
```python
librarian_system = LibrarianSystem()
logger.info("Librarian System initialized")
```

**Add this code after that line:**

```python
# Initialize Enhanced Systems (Option C)
enhanced_librarian_system = None
executive_bot_manager = None
hybrid_command_system = None

try:
    if LIBRARIAN_AVAILABLE and llm_manager:
        enhanced_librarian_system = EnhancedLibrarianSystem(llm_client=llm_manager)
        executive_bot_manager = ExecutiveBotManager(llm_client=llm_manager)
        hybrid_command_system = HybridCommandSystem(
            librarian_system=enhanced_librarian_system,
            executive_bots=executive_bot_manager
        )
        logger.info("✓ Enhanced systems initialized with LLM support")
    else:
        enhanced_librarian_system = EnhancedLibrarianSystem()
        executive_bot_manager = ExecutiveBotManager()
        hybrid_command_system = HybridCommandSystem(
            librarian_system=enhanced_librarian_system,
            executive_bots=executive_bot_manager
        )
        logger.info("✓ Enhanced systems initialized (LLM not available)")
except Exception as e:
    logger.error(f"✗ Enhanced systems initialization failed: {e}")
    enhanced_librarian_system = EnhancedLibrarianSystem()
    executive_bot_manager = ExecutiveBotManager()
    hybrid_command_system = HybridCommandSystem()
```

---

## Step 3: Add API Endpoints

**File:** `murphy_backend_complete.py`

**Location:** Before `if __name__ == '__main__':` (at the end of the file)

**Add these 12 new endpoints:**

```python
# ==================== ENHANCED LIBRARIAN ENDPOINTS (Option C) ====================

@app.route('/api/librarian/enhanced', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_enhanced_ask():
    """Enhanced librarian endpoint with discovery workflow"""
    try:
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not user_input:
            return jsonify({
                'success': False,
                'message': 'Input is required'
            }), 400
        
        result = enhanced_librarian_system.ask(user_input)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Enhanced librarian error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/interpret', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_interpret_command():
    """Interpret a command in natural language"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        result = hybrid_command_system.interpret_command(command)
        
        return jsonify({
            'success': True,
            'data': result.__dict__ if hasattr(result, '__dict__') else result
        })
    
    except Exception as e:
        logger.error(f"Command interpretation error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/librarian/natural-to-command', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def librarian_natural_to_command():
    """Convert natural language to command"""
    try:
        data = request.get_json()
        natural = data.get('natural', '')
        
        if not natural:
            return jsonify({
                'success': False,
                'message': 'Natural language text is required'
            }), 400
        
        hybrid = hybrid_command_system.natural_to_command(natural)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Natural to command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== EXECUTIVE BOT ENDPOINTS (Option C) ====================

@app.route('/api/executive/bots', methods=['GET'])
def get_executive_bots():
    """Get all executive bots"""
    try:
        bots = executive_bot_manager.get_all_bots()
        
        return jsonify({
            'success': True,
            'bots': bots
        })
    
    except Exception as e:
        logger.error(f"Get executive bots error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/execute', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_command():
    """Execute a command on an executive bot"""
    try:
        data = request.get_json()
        bot_role = data.get('bot', '')
        command = data.get('command', '')
        context = data.get('context', '')
        
        if not bot_role or not command:
            return jsonify({
                'success': False,
                'message': 'Bot role and command are required'
            }), 400
        
        result = executive_bot_manager.execute_command(bot_role, command, context)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/workflow/<workflow_name>', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def execute_executive_workflow(workflow_name):
    """Execute an executive workflow"""
    try:
        result = executive_bot_manager.coordinate_workflow(workflow_name)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"Execute executive workflow error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/executive/terminology/<bot_role>', methods=['GET'])
def get_bot_terminology(bot_role):
    """Get domain terminology for a bot"""
    try:
        terminology = executive_bot_manager.get_bot_terminology(bot_role)
        
        return jsonify({
            'success': True,
            'terminology': terminology
        })
    
    except Exception as e:
        logger.error(f"Get bot terminology error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ==================== HYBRID COMMAND ENDPOINTS (Option C) ====================

@app.route('/api/commands/parse', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def parse_hybrid_command():
    """Parse a hybrid command"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        hybrid = hybrid_command_system.parse_hybrid_command(command)
        
        return jsonify({
            'success': True,
            'data': hybrid.__dict__ if hasattr(hybrid, '__dict__') else hybrid
        })
    
    except Exception as e:
        logger.error(f"Parse hybrid command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/dropdown-data', methods=['GET'])
def get_command_dropdown_data():
    """Get data for command dropdown interface"""
    try:
        data = hybrid_command_system.get_command_dropdown_data()
        
        return jsonify({
            'success': True,
            'data': data
        })
    
    except Exception as e:
        logger.error(f"Get command dropdown data error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/workflows', methods=['GET'])
def get_workflows():
    """Get all available workflows"""
    try:
        workflows = hybrid_command_system.get_available_workflows()
        
        return jsonify({
            'success': True,
            'workflows': workflows
        })
    
    except Exception as e:
        logger.error(f"Get workflows error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/commands/validate', methods=['POST'])
@require_auth(auth_system if AUTH_AVAILABLE else None)
def validate_command():
    """Validate command syntax"""
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        validation = hybrid_command_system.validate_command_syntax(command)
        
        return jsonify({
            'success': True,
            'data': validation
        })
    
    except Exception as e:
        logger.error(f"Validate command error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
```

---

## Step 4: Update Status Endpoint

**File:** `murphy_backend_complete.py`

**Find the `/api/status` endpoint** and add enhanced systems to the response:

```python
# In the status endpoint return statement, add:
"enhanced_systems": {
    "librarian": enhanced_librarian_system is not None,
    "executive_bots": executive_bot_manager is not None,
    "hybrid_commands": hybrid_command_system is not None
},
```

---

## Step 5: Add UI Script to Frontend

**File:** `murphy_complete_v2.html`

**Location:** Before `</body>` tag (near the end of the file)

**Add this line:**

```html
<script src="enhanced_librarian_ui.js"></script>
```

---

## Step 6: Update Terminal Help

**File:** `murphy_complete_v2.html`

**Find the terminal help section** and add these new commands:

```javascript
// Add to terminal command help
addTerminalCommand('/librarian interpret <command>', 'Interpret a command in natural language');
addTerminalCommand('/librarian natural <command>', 'Convert command to natural language');
addTerminalCommand('/librarian start', 'Begin system discovery');
addTerminalCommand('/command build', 'Open command builder');
addTerminalCommand('/workflow execute <name>', 'Execute a workflow');
```

---

## Testing the Integration

### Test 1: Verify System Status

```bash
curl http://localhost:5000/api/status
```

**Expected Response:** Should include `"enhanced_systems"` with all systems showing `true`

### Test 2: Start Discovery

```bash
curl -X POST http://localhost:5000/api/librarian/enhanced \
  -H "Content-Type: application/json" \
  -d '{"input": "I need to automate my software company"}'
```

**Expected Response:** Should return a question about business type

### Test 3: Interpret Command

```bash
curl -X POST http://localhost:5000/api/librarian/interpret \
  -H "Content-Type: application/json" \
  -d '{"command": "/swarm generate Engineer #build feature"}'
```

**Expected Response:** Should return natural language interpretation

### Test 4: Get Executive Bots

```bash
curl http://localhost:5000/api/executive/bots
```

**Expected Response:** Should list CEO, CTO, CFO, and other bots

### Test 5: Execute Workflow

```bash
curl -X POST http://localhost:5000/api/executive/workflow/executive_planning
```

**Expected Response:** Should execute the executive planning workflow

### Test 6: Get Command Dropdown Data

```bash
curl http://localhost:5000/api/commands/dropdown-data
```

**Expected Response:** Should return actions, bot_roles, domains, and workflows

---

## Troubleshooting

### Issue: Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'enhanced_librarian_system'`

**Solution:** Ensure all three system files are in the same directory as the backend file

### Issue: Initialization Errors

**Symptom:** `NameError: name 'enhanced_librarian_system' is not defined`

**Solution:** Check that the initialization code was added correctly after librarian initialization

### Issue: 404 on New Endpoints

**Symptom:** New endpoints return 404

**Solution:** 
1. Check that endpoints were added before `if __name__ == '__main__':`
2. Restart the backend server
3. Check for syntax errors in the backend file

### Issue: Frontend Not Loading UI

**Symptom:** Command interpretation dropdown not working

**Solution:**
1. Check browser console for JavaScript errors
2. Verify `enhanced_librarian_ui.js` is in the same directory
3. Check that script tag was added to HTML
4. Clear browser cache

---

## Complete Integration Checklist

- [ ] Import statements added to backend
- [ ] System initialization code added
- [ ] 12 new API endpoints added
- [ ] Status endpoint updated
- [ ] UI script added to frontend
- [ ] Terminal help updated
- [ ] Backend restarted
- [ ] All 6 test cases pass
- [ ] Frontend loads without errors
- [ ] Discovery workflow works
- [ ] Command interpretation works
- [ ] Executive bots respond
- [ ] Workflows execute successfully

---

## Summary

After completing these 6 steps, the Option C systems will be fully integrated and operational:

✅ Enhanced Librarian with discovery workflow  
✅ Executive Bots (CEO, CTO, CFO)  
✅ Hybrid Command System  
✅ 12 new API endpoints  
✅ Frontend UI integration  
✅ Complete business automation capability  

**Total time to complete:** ~30-45 minutes  
**Files modified:** 2 (backend and frontend)  
**New endpoints:** 12  
**New capabilities:** Complete business automation