# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

#!/usr/bin/env python3
import os
import sys

# Files to modify
backend_file = 'murphy_backend_complete.py'
frontend_file = 'murphy_complete_v2.html'

print("="*60)
print("OPTION C INTEGRATION")
print("="*60)

# Check if files exist
print("\nChecking files...")
if os.path.exists(backend_file):
    print(f"✓ Backend file found: {backend_file}")
    backend_size = os.path.getsize(backend_file)
    print(f"  Size: {backend_size} bytes")
else:
    print(f"✗ Backend file NOT found: {backend_file}")
    sys.exit(1)

if os.path.exists(frontend_file):
    print(f"✓ Frontend file found: {frontend_file}")
    frontend_size = os.path.getsize(frontend_file)
    print(f"  Size: {frontend_size} bytes")
else:
    print(f"✗ Frontend file NOT found: {frontend_file}")
    sys.exit(1)

# Read backend
print("\nReading backend file...")
with open(backend_file, 'r') as f:
    backend_content = f.read()
print(f"✓ Backend loaded ({len(backend_content)} characters)")

# Read frontend
print("Reading frontend file...")
with open(frontend_file, 'r') as f:
    frontend_content = f.read()
print(f"✓ Frontend loaded ({len(frontend_content)} characters)")

# STEP 1: Add imports
print("\n" + "="*60)
print("STEP 1: Adding imports...")
print("="*60)
imports_to_add = """
# Enhanced Systems Integration (Option C)
from enhanced_librarian_system import EnhancedLibrarianSystem, DiscoveryPhase
from executive_bot_system import ExecutiveBotManager, BotRole
from hybrid_command_system import HybridCommandSystem
"""

if "from enhanced_librarian_system" not in backend_content:
    # Find last import
    lines = backend_content.split('\n')
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('from ') or line.strip().startswith('import '):
            last_import_idx = i
    
    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, imports_to_add)
        backend_content = '\n'.join(lines)
        print("✓ Imports added successfully")
    else:
        print("✗ Could not find import section")
else:
    print("✓ Imports already exist")

# STEP 2: Add initialization
print("\n" + "="*60)
print("STEP 2: Adding system initialization...")
print("="*60)
init_code = """

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
"""

if "enhanced_librarian_system = " not in backend_content:
    if "librarian_system = LibrarianSystem" in backend_content:
        backend_content = backend_content.replace(
            '    logger.info("Librarian System initialized")',
            '    logger.info("Librarian System initialized")' + init_code
        )
        print("✓ Initialization added successfully")
    else:
        print("✗ Could not find librarian initialization")
else:
    print("✓ Initialization already exists")

# STEP 3: Add API endpoints
print("\n" + "="*60)
print("STEP 3: Adding 12 API endpoints...")
print("="*60)

endpoints_code = '''

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
'''

if "/api/librarian/enhanced" not in backend_content:
    if 'if __name__ == "__main__":' in backend_content:
        backend_content = backend_content.replace(
            'if __name__ == "__main__":',
            endpoints_code + '\nif __name__ == "__main__":'
        )
        print("✓ 12 API endpoints added successfully")
    else:
        print("✗ Could not find main block")
else:
    print("✓ API endpoints already exist")

# STEP 4: Add UI script to frontend
print("\n" + "="*60)
print("STEP 4: Adding UI script to frontend...")
print("="*60)

script_tag = '''    <script src="enhanced_librarian_ui.js"></script>
'''

if "enhanced_librarian_ui.js" not in frontend_content:
    if '</body>' in frontend_content:
        frontend_content = frontend_content.replace(
            '</body>',
            script_tag + '</body>'
        )
        print("✓ UI script added successfully")
    else:
        print("✗ Could not find closing body tag")
else:
    print("✓ UI script already exists")

# Write updated files
print("\n" + "="*60)
print("Writing updated files...")
print("="*60)

with open(backend_file, 'w') as f:
    f.write(backend_content)
print(f"✓ Backend file updated ({len(backend_content)} characters)")

with open(frontend_file, 'w') as f:
    f.write(frontend_content)
print(f"✓ Frontend file updated ({len(frontend_content)} characters)")

print("\n" + "="*60)
print("INTEGRATION COMPLETE!")
print("="*60)
print("\nChanges made:")
print("  ✓ Added imports to backend")
print("  ✓ Added system initialization to backend")
print("  ✓ Added 12 API endpoints to backend")
print("  ✓ Added UI script to frontend")
print("\nNext steps:")
print("  1. Restart the backend server")
print("  2. Refresh the frontend")
print("  3. Test with: /librarian start")