"""
Integration Script: Generative Decision Gates
Integrates the generative gate system into murphy_complete_integrated.py
"""

import sys

def integrate_generative_gates():
    """Integrate generative gate system into Murphy"""
    
    print("=" * 80)
    print("INTEGRATING GENERATIVE DECISION GATE SYSTEM")
    print("=" * 80)
    
    # Read the current murphy file
    with open('murphy_complete_integrated.py', 'r') as f:
        murphy_content = f.read()
    
    # Check if already integrated
    if 'generative_gate_system' in murphy_content:
        print("✓ Generative gate system already integrated")
        return True
    
    # Find the agent_communication_system import
    import_marker = "from agent_communication_system import"
    if import_marker not in murphy_content:
        print("✗ Could not find import marker")
        return False
    
    # Add import
    new_import = """from generative_gate_system import (
    GenerativeGateSystem, get_generative_gate_system,
    SensorAgent, QualitySensorAgent, CostSensorAgent, ComplianceSensorAgent,
    GateTypeEnum, ConfidenceLevelEnum, GateSpecModel, RuleModel, ObservationModel
)
"""
    
    murphy_content = murphy_content.replace(
        import_marker,
        new_import + "\n" + import_marker
    )
    
    # Find where to add initialization (after agent communication hub)
    init_marker = "# Agent Communication Hub - Initialize at module level"
    if init_marker not in murphy_content:
        print("✗ Could not find initialization marker")
        return False
    
    # Add generative gate system initialization
    new_init = """
# Generative Decision Gate System - Initialize at module level
try:
    generative_gate_system = get_generative_gate_system()
    SYSTEMS_AVAILABLE['generative_gates'] = True
    logger.info("✓ Generative Decision Gate System initialized at module level")
except Exception as e:
    logger.error(f"✗ Generative Decision Gate System failed: {e}")
    generative_gate_system = None

"""
    
    # Find the position to insert initialization
    init_pos = murphy_content.find(init_marker)
    if init_pos == -1:
        print("✗ Could not find exact initialization position")
        return False
    
    # Find the end of the agent communication hub block
    # Look for the next "# " comment or empty line after several lines
    search_start = init_pos + len(init_marker)
    next_section = murphy_content.find('\n# ', search_start)
    
    if next_section == -1:
        # If no next section found, insert before if __name__
        next_section = murphy_content.find("if __name__ == '__main__':")
    
    # Insert our initialization before the next section
    murphy_content = murphy_content[:next_section] + new_init + murphy_content[next_section:]
    
    # Add new API endpoints before the if __name__ == '__main__'
    new_endpoints = """

# ============================================================================
# GENERATIVE DECISION GATE ENDPOINTS
# ============================================================================

@app.route('/api/gates/generate', methods=['POST'])
def generate_gates_for_task():
    &quot;&quot;&quot;Generate decision gates dynamically for a task&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        task = data.get('task', {})
        business_context = data.get('business_context', {})
        
        # Analyze task
        analysis = generative_gate_system.analyze_task(task, business_context)
        
        # Generate gates
        context = {**task, **business_context}
        gates = generative_gate_system.generate_gates(analysis, context)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'gates': [gate.dict() for gate in gates],
            'gate_count': len(gates)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/sensors/status', methods=['GET'])
def get_sensors_status():
    &quot;&quot;&quot;Get status of all sensor agents&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        status = generative_gate_system.get_system_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/sensors/<sensor_id>', methods=['GET'])
def get_sensor_details(sensor_id):
    &quot;&quot;&quot;Get details of a specific sensor&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        sensor = next((s for s in generative_gate_system.sensors if s.sensor_id == sensor_id), None)
        if not sensor:
            return jsonify({'success': False, 'error': 'Sensor not found'}), 404
        
        return jsonify({
            'success': True,
            'sensor': sensor.get_status()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/learn', methods=['POST'])
def learn_from_outcome():
    &quot;&quot;&quot;Learn from task outcome to improve future gate generation&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        task_id = data.get('task_id')
        gates = [GateSpecModel(**g) for g in data.get('gates', [])]
        outcome = data.get('outcome', {})
        
        generative_gate_system.learn_from_outcome(task_id, gates, outcome)
        
        return jsonify({
            'success': True,
            'message': 'Learning recorded',
            'patterns_count': len(generative_gate_system.historical_patterns)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/capabilities', methods=['GET'])
def get_capabilities():
    &quot;&quot;&quot;Get list of available capabilities&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        from generative_gate_system import CapabilityRegistry
        capabilities = list(CapabilityRegistry._capabilities.keys())
        
        return jsonify({
            'success': True,
            'capabilities': capabilities,
            'count': len(capabilities)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gates/capabilities/verify', methods=['POST'])
def verify_capability():
    &quot;&quot;&quot;Verify if a capability exists&quot;&quot;&quot;
    if not generative_gate_system:
        return jsonify({'success': False, 'error': 'Generative gate system not initialized'}), 503
    
    try:
        data = request.json
        capability = data.get('capability')
        
        from generative_gate_system import CapabilityRegistry
        exists = CapabilityRegistry.verify_capability(capability)
        alternatives = CapabilityRegistry.suggest_alternatives(capability) if not exists else []
        
        return jsonify({
            'success': True,
            'capability': capability,
            'exists': exists,
            'alternatives': alternatives
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

"""
    
    # Find the if __name__ == '__main__' section
    main_marker = "if __name__ == '__main__':"
    if main_marker in murphy_content:
        murphy_content = murphy_content.replace(main_marker, new_endpoints + "\n" + main_marker)
    else:
        murphy_content += new_endpoints
    
    # Write back
    with open('murphy_complete_integrated.py', 'w') as f:
        f.write(murphy_content)
    
    print("\n✓ Added generative gate system import")
    print("✓ Added generative gate system initialization")
    print("✓ Added 6 new API endpoints:")
    print("  1. POST /api/gates/generate - Generate gates for task")
    print("  2. GET /api/gates/sensors/status - Get all sensors status")
    print("  3. GET /api/gates/sensors/<sensor_id> - Get sensor details")
    print("  4. POST /api/gates/learn - Learn from task outcome")
    print("  5. GET /api/gates/capabilities - Get available capabilities")
    print("  6. POST /api/gates/capabilities/verify - Verify capability exists")
    
    return True

if __name__ == '__main__':
    success = integrate_generative_gates()
    if success:
        print("\n" + "=" * 80)
        print("INTEGRATION COMPLETE")
        print("=" * 80)
        print("\nGenerative Decision Gate System successfully integrated into Murphy!")
        print("\nNew capabilities:")
        print("• Dynamic gate generation based on context")
        print("• Sensor agents monitoring quality, cost, compliance")
        print("• Rule generation from observations")
        print("• Learning from outcomes")
        print("• Capability verification (prevents hallucination)")
        print("• Circuit breaker protection")
        print("• Defensive programming patterns")
        sys.exit(0)
    else:
        print("\n✗ Integration failed")
        sys.exit(1)