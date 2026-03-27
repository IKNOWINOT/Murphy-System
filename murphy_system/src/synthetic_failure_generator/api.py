"""
Synthetic Failure Generator REST API
=====================================

Flask API server for the Synthetic Failure Generator service.

Endpoints:
- POST /generate/semantic - Generate semantic failures
- POST /generate/control - Generate control plane failures
- POST /generate/interface - Generate interface failures
- POST /generate/organizational - Generate organizational failures
- POST /generate/batch - Generate batch of failures
- POST /pipeline/run - Run injection pipeline
- POST /simulate - Simulate failure execution
- POST /training/confidence - Generate confidence training data
- POST /training/gate_policy - Generate gate policy data
- POST /test/monte_carlo - Run Monte Carlo simulation
- POST /test/adversarial - Run adversarial swarm
- POST /test/historical - Replay historical disaster
- GET /disasters - Get historical disasters
- GET /statistics - Get generation statistics
- GET /safety/report - Get safety report
- GET /health - Health check
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request
from flask_cors import CORS

from flask_security import configure_secure_app

from .control_failures import ControlPlaneFailureGenerator
from .injection_pipeline import FailureInjectionPipeline
from .interface_failures import InterfaceFailureGenerator
from .models import BaseScenario, FailureType
from .organizational_failures import OrganizationalFailureGenerator
from .safety_enforcer import SafetyEnforcer
from .semantic_failures import SemanticFailureGenerator
from .test_modes import TestModeExecutor
from .training_output import TrainingOutputGenerator

logger = logging.getLogger(__name__)


app = Flask(__name__)
configure_secure_app(app, service_name="synthetic-failure-generator")

# Initialize components
semantic_gen = SemanticFailureGenerator()
control_gen = ControlPlaneFailureGenerator()
interface_gen = InterfaceFailureGenerator()
organizational_gen = OrganizationalFailureGenerator()
pipeline = FailureInjectionPipeline()
training_gen = TrainingOutputGenerator()
test_executor = TestModeExecutor()
safety_enforcer = SafetyEnforcer()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'synthetic_failure_generator',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'components': {
            'semantic_generator': 'operational',
            'control_generator': 'operational',
            'interface_generator': 'operational',
            'organizational_generator': 'operational',
            'injection_pipeline': 'operational',
            'training_generator': 'operational',
            'test_executor': 'operational',
            'safety_enforcer': 'operational'
        },
        'safety_status': safety_enforcer.get_safety_report()['safety_status']
    })


@app.route('/generate/semantic', methods=['POST'])
def generate_semantic():
    """Generate semantic failures"""
    data = request.json
    artifact_graph = data.get('artifact_graph', {})
    count = data.get('count', 10)

    failures = semantic_gen.generate_batch(artifact_graph, count)

    return jsonify({
        'failures': [f.to_dict() for f in failures],
        'count': len(failures)
    })


@app.route('/generate/control', methods=['POST'])
def generate_control():
    """Generate control plane failures"""
    data = request.json
    gate_library = data.get('gate_library', [])
    count = data.get('count', 10)

    failures = control_gen.generate_batch(gate_library, count)

    return jsonify({
        'failures': [f.to_dict() for f in failures],
        'count': len(failures)
    })


@app.route('/generate/interface', methods=['POST'])
def generate_interface():
    """Generate interface failures"""
    data = request.json
    count = data.get('count', 10)

    failures = interface_gen.generate_batch(count)

    return jsonify({
        'failures': [f.to_dict() for f in failures],
        'count': len(failures)
    })


@app.route('/generate/organizational', methods=['POST'])
def generate_organizational():
    """Generate organizational failures"""
    data = request.json
    count = data.get('count', 10)

    failures = organizational_gen.generate_batch(count)

    return jsonify({
        'failures': [f.to_dict() for f in failures],
        'count': len(failures)
    })


@app.route('/generate/batch', methods=['POST'])
def generate_batch():
    """Generate batch of all failure types"""
    data = request.json
    count_per_type = data.get('count_per_type', 5)

    all_failures = []

    # Generate each type
    all_failures.extend(semantic_gen.generate_batch({}, count_per_type))
    all_failures.extend(control_gen.generate_batch([], count_per_type))
    all_failures.extend(interface_gen.generate_batch(count_per_type))
    all_failures.extend(organizational_gen.generate_batch(count_per_type))

    return jsonify({
        'failures': [f.to_dict() for f in all_failures],
        'total_count': len(all_failures),
        'by_type': {
            'semantic': count_per_type * 4,
            'control': count_per_type * 4,
            'interface': count_per_type * 4,
            'organizational': count_per_type * 4
        }
    })


@app.route('/pipeline/run', methods=['POST'])
def run_pipeline():
    """Run injection pipeline"""
    data = request.json

    # Create base scenario
    base_scenario = pipeline.create_base_scenario(
        scenario_name=data.get('scenario_name', 'test_scenario'),
        artifact_graph=data.get('artifact_graph', {}),
        interface_definitions=data.get('interface_definitions', {}),
        gate_library=data.get('gate_library', []),
        initial_confidence=data.get('initial_confidence', 0.8),
        initial_risk=data.get('initial_risk', 0.1)
    )

    # Get failure types
    failure_type_names = data.get('failure_types', ['UNIT_MISMATCH'])
    failure_types = [FailureType[name] for name in failure_type_names]

    count_per_type = data.get('count_per_type', 5)

    # Run pipeline
    results = pipeline.run_pipeline(
        base_scenario,
        failure_types,
        count_per_type
    )

    return jsonify({
        'results': [r.to_dict() for r in results],
        'count': len(results)
    })


@app.route('/simulate', methods=['POST'])
def simulate():
    """Simulate failure execution"""
    data = request.json

    synthetic_packet = data.get('synthetic_packet', {})
    failure_case_data = data.get('failure_case', {})

    # Validate safety
    is_valid, error = safety_enforcer.validate_packet(synthetic_packet)
    if not is_valid:
        return jsonify({'error': error}), 400

    # Note: Would need to reconstruct FailureCase from data
    # For now, return placeholder
    return jsonify({
        'message': 'Simulation endpoint - implementation pending',
        'packet_id': synthetic_packet.get('packet_id', 'unknown')
    })


@app.route('/training/confidence', methods=['POST'])
def generate_confidence_training():
    """Generate confidence model training data"""
    data = request.json

    # Would need simulation results
    # For now, return statistics
    stats = training_gen.get_statistics()

    return jsonify({
        'message': 'Confidence training data generation',
        'statistics': stats
    })


@app.route('/training/gate_policy', methods=['POST'])
def generate_gate_policy_training():
    """Generate gate policy training data"""
    data = request.json

    stats = training_gen.get_statistics()

    return jsonify({
        'message': 'Gate policy training data generation',
        'statistics': stats
    })


@app.route('/test/monte_carlo', methods=['POST'])
def run_monte_carlo():
    """Run Monte Carlo simulation"""
    data = request.json

    # Create base scenario
    base_scenario = pipeline.create_base_scenario(
        scenario_name='monte_carlo_test',
        artifact_graph=data.get('artifact_graph', {}),
        interface_definitions=data.get('interface_definitions', {}),
        gate_library=data.get('gate_library', [])
    )

    num_iterations = data.get('num_iterations', 100)

    results = test_executor.monte_carlo_simulation(
        base_scenario,
        num_iterations
    )

    return jsonify({
        'results': [r.to_dict() for r in results],
        'count': len(results),
        'iterations': num_iterations
    })


@app.route('/test/adversarial', methods=['POST'])
def run_adversarial():
    """Run adversarial swarm generation"""
    data = request.json

    base_scenario = pipeline.create_base_scenario(
        scenario_name='adversarial_test',
        artifact_graph=data.get('artifact_graph', {}),
        interface_definitions=data.get('interface_definitions', {}),
        gate_library=data.get('gate_library', [])
    )

    swarm_size = data.get('swarm_size', 50)
    optimization_target = data.get('optimization_target', 'maximize_loss')

    results = test_executor.adversarial_swarm_generation(
        base_scenario,
        swarm_size,
        optimization_target
    )

    return jsonify({
        'results': [r.to_dict() for r in results],
        'count': len(results),
        'swarm_size': swarm_size,
        'optimization_target': optimization_target
    })


@app.route('/test/historical', methods=['POST'])
def replay_historical():
    """Replay historical disaster"""
    data = request.json

    disaster_name = data.get('disaster_name', 'Boeing 737 MAX MCAS')

    base_scenario = pipeline.create_base_scenario(
        scenario_name=f'historical_{disaster_name}',
        artifact_graph=data.get('artifact_graph', {}),
        interface_definitions=data.get('interface_definitions', {}),
        gate_library=data.get('gate_library', [])
    )

    result = test_executor.historical_disaster_replay(
        disaster_name,
        base_scenario
    )

    return jsonify({
        'result': result.to_dict(),
        'disaster_name': disaster_name
    })


@app.route('/disasters', methods=['GET'])
def get_disasters():
    """Get historical disasters"""
    disasters = test_executor.historical_disasters

    return jsonify({
        'disasters': [d.to_dict() for d in disasters],
        'count': len(disasters)
    })


@app.route('/statistics', methods=['GET'])
def get_statistics():
    """Get generation statistics"""
    stats = training_gen.get_statistics()

    return jsonify(stats)


@app.route('/safety/report', methods=['GET'])
def get_safety_report():
    """Get safety enforcement report"""
    report = safety_enforcer.get_safety_report()

    return jsonify(report)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8059, debug=False)
