# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Backend Integration Script for Option C Systems

This script will:
1. Add imports for enhanced systems
2. Initialize the systems
3. Add 12 new API endpoints
4. Update the frontend to include the UI script
"""

import re
import sys

def read_backend_file():
    """Read the backend file"""
    try:
        with open('/workspace/murphy_backend_complete.py', 'r') as f:
            return f.read()
    except FileNotFoundError:
        print("ERROR: Backend file not found")
        sys.exit(1)

def write_backend_file(content):
    """Write the backend file"""
    try:
        with open('/workspace/murphy_backend_complete.py', 'w') as f:
            f.write(content)
        print("Backend file updated successfully")
    except Exception as e:
        print(f"ERROR: Failed to write backend file: {e}")
        sys.exit(1)

def add_imports(content):
    """Add imports for enhanced systems"""
    # Check if imports already exist
    if "from enhanced_librarian_system" in content:
        print("✓ Enhanced system imports already exist")
        return content
    
    # Find the last import statement
    lines = content.split('\n')
    import_idx = -1
    last_import_line = ""
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from ') or stripped.startswith('import '):
            import_idx = i
            last_import_line = stripped
    
    if import_idx >= 0:
        # Add new imports after the last import
        new_imports = """
# Enhanced Systems Integration (Option C)
from enhanced_librarian_system import EnhancedLibrarianSystem, DiscoveryPhase
from executive_bot_system import ExecutiveBotManager, BotRole
from hybrid_command_system import HybridCommandSystem
"""
        lines.insert(import_idx + 1, new_imports)
        content = '\n'.join(lines)
        print("✓ Added enhanced system imports")
    else:
        print("⚠ No imports found, appending to beginning")
        new_imports = """# Enhanced Systems Integration (Option C)
from enhanced_librarian_system import EnhancedLibrarianSystem, DiscoveryPhase
from executive_bot_system import ExecutiveBotManager, BotRole
from hybrid_command_system import HybridCommandSystem

"""
        content = new_imports + content
    
    return content

def add_initialization(content):
    """Add system initialization"""
    # Check if already initialized
    if "enhanced_librarian_system = " in content:
        print("✓ Enhanced systems initialization already exists")
        return content
    
    # Find where to add initialization (after librarian initialization)
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
    
    # Find librarian initialization and add after it
    if "librarian_system = LibrarianSystem" in content:
        content = content.replace(
            "    logger.info(&quot;Librarian System initialized&quot;)",
            "    logger.info(&quot;Librarian System initialized&quot;)" + init_code
        )
        print("✓ Added enhanced systems initialization")
    else:
        print("⚠ Librarian initialization not found, appending before Flask app")
        # Find Flask app creation
        if "app = Flask(" in content:
            content = content.replace(
                "app = Flask(",
                init_code + "\napp = Flask("
            )
            print("✓ Added enhanced systems initialization before Flask app")
        else:
            print("⚠ Could not find Flask app, appending to end")
            content += init_code
    
    return content

def add_api_endpoints(content):
    """Add new API endpoints"""
    # Check if endpoints already exist
    if "/api/librarian/enhanced" in content:
        print("✓ Enhanced API endpoints already exist")
        return content
    
    new_endpoints = """

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
"""
    
    # Add endpoints before if __name__ == '__main__':
    if 'if __name__ == "__main__":' in content:
        content = content.replace(
            'if __name__ == "__main__":',
            new_endpoints + '\n\nif __name__ == "__main__":'
        )
        print("✓ Added 12 new API endpoints")
    else:
        print("⚠ Could not find main block, appending to end")
        content += new_endpoints
    
    return content

def update_status_endpoint(content):
    """Update status endpoint to include enhanced systems"""
    # Check if already updated
    if '"enhanced_systems"' in content:
        print("✓ Status endpoint already includes enhanced systems")
        return content
    
    # Find the status endpoint
    pattern = r'(@app\.route\([\'"]/api/status[\'"].*?\))'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Find the endpoint function
        endpoint_start = match.end()
        
        # Find the return statement in the endpoint
        return_pattern = r'return jsonify\(\{.*?\}\)'
        return_match = re.search(return_pattern, content[endpoint_start:], re.DOTALL)
        
        if return_match:
            return_end = endpoint_start + return_match.end()
            return_statement = return_match.group()
            
            # Add enhanced systems to the response
            new_return = return_statement.rstrip('}') + """
        "enhanced_systems": {
            "librarian": enhanced_librarian_system is not None,
            "executive_bots": executive_bot_manager is not None,
            "hybrid_commands": hybrid_command_system is not None
        },"""
            
            content = content[:return_start] + new_return + content[return_end:]
            print("✓ Updated status endpoint with enhanced systems")
    
    return content

def update_frontend_file():
    """Update frontend to include enhanced librarian UI"""
    try:
        frontend_path = '/workspace/murphy_complete_v2.html'
        
        with open(frontend_path, 'r') as f:
            content = f.read()
        
        # Check if script already included
        if 'enhanced_librarian_ui.js' in content:
            print("✓ Frontend already includes enhanced_librarian_ui.js")
            return True
        
        # Find a good place to add the script (before closing body tag)
        if '</body>' in content:
            script_tag = '''    <script src="enhanced_librarian_ui.js"></script>
'''
            content = content.replace('</body>', script_tag + '</body>')
            
            with open(frontend_path, 'w') as f:
                f.write(content)
            
            print("✓ Added enhanced_librarian_ui.js to frontend")
            return True
        else:
            print("⚠ Could not find closing body tag in frontend")
            return False
    
    except FileNotFoundError:
        print("⚠ Frontend file not found, skipping")
        return False
    except Exception as e:
        print(f"⚠ Error updating frontend: {e}")
        return False

def main():
    """Main integration process"""
    print("\n" + "="*60)
    print("BACKEND INTEGRATION - Option C Systems")
    print("="*60 + "\n")
    
    # Step 1: Read backend file
    print("Step 1: Reading backend file...")
    content = read_backend_file()
    print(f"✓ Backend file loaded ({len(content)} characters)\n")
    
    # Step 2: Add imports
    print("Step 2: Adding enhanced system imports...")
    content = add_imports(content)
    print()
    
    # Step 3: Add initialization
    print("Step 3: Adding enhanced system initialization...")
    content = add_initialization(content)
    print()
    
    # Step 4: Add API endpoints
    print("Step 4: Adding 12 new API endpoints...")
    content = add_api_endpoints(content)
    print()
    
    # Step 5: Update status endpoint
    print("Step 5: Updating status endpoint...")
    content = update_status_endpoint(content)
    print()
    
    # Step 6: Write backend file
    print("Step 6: Writing updated backend file...")
    write_backend_file(content)
    print()
    
    # Step 7: Update frontend
    print("Step 7: Updating frontend file...")
    update_frontend_file()
    print()
    
    print("="*60)
    print("INTEGRATION COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Restart the backend server")
    print("2. Test the new endpoints")
    print("3. Verify frontend loads enhanced_librarian_ui.js")
    print("\nNew API endpoints:")
    print("- POST /api/librarian/enhanced")
    print("- POST /api/librarian/interpret")
    print("- POST /api/librarian/natural-to-command")
    print("- GET /api/executive/bots")
    print("- POST /api/executive/execute")
    print("- POST /api/executive/workflow/<name>")
    print("- GET /api/executive/terminology/<role>")
    print("- POST /api/commands/parse")
    print("- GET /api/commands/dropdown-data")
    print("- GET /api/commands/workflows")
    print("- POST /api/commands/validate")
    print()

if __name__ == '__main__':
    main()