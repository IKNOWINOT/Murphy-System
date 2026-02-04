"""
Murphy System - Complete Backend with Form Integration
Extended version that adds Phase 1-5 form endpoints to the original backend

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import original backend
from murphy_complete_backend import (
    app, socketio, runtime, 
    MURPHY_AVAILABLE, DOMAIN_ENGINE_AVAILABLE
)

# Import form intake system
from src.form_intake.schemas import (
    PlanUploadForm, PlanGenerationForm, TaskExecutionForm,
    ValidationForm, CorrectionForm
)
from src.form_intake.handlers import FormHandler

# Import integration classes
from src.confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
from src.execution_engine.integrated_form_executor import IntegratedFormExecutor
from src.learning_engine.integrated_correction_system import IntegratedCorrectionSystem
from src.supervisor_system.integrated_hitl_monitor import IntegratedHITLMonitor

from flask import request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize integrated components
form_handler = FormHandler()
confidence_engine = UnifiedConfidenceEngine()
form_executor = IntegratedFormExecutor()
correction_system = IntegratedCorrectionSystem()
hitl_monitor = IntegratedHITLMonitor()

logger.info("Form integration components initialized")

# ============================================================================
# FORM ENDPOINTS - Phase 1-5 Integration
# ============================================================================

@app.route('/api/forms/plan-upload', methods=['POST'])
async def upload_plan():
    """
    Upload a pre-existing plan for execution
    
    Request body:
    {
        "plan_name": "string",
        "plan_data": {...},
        "format": "json|yaml|markdown"
    }
    """
    try:
        data = request.json
        
        # Validate form
        form = PlanUploadForm(**data)
        
        # Process form
        result = await form_handler.handle_plan_upload(form)
        
        return jsonify({
            'success': True,
            'submission_id': result['submission_id'],
            'plan_id': result['plan_id'],
            'tasks_count': result['tasks_count'],
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error uploading plan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/forms/plan-generation', methods=['POST'])
async def generate_plan():
    """
    Generate a plan from natural language description
    
    Request body:
    {
        "description": "string",
        "domain": "string",
        "constraints": [...],
        "preferences": {...}
    }
    """
    try:
        data = request.json
        
        # Validate form
        form = PlanGenerationForm(**data)
        
        # Process form
        result = await form_handler.handle_plan_generation(form)
        
        return jsonify({
            'success': True,
            'submission_id': result['submission_id'],
            'plan_id': result['plan_id'],
            'generated_plan': result['plan'],
            'tasks_count': result['tasks_count'],
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error generating plan: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/forms/task-execution', methods=['POST'])
async def execute_task():
    """
    Execute a task with Murphy validation
    
    Request body:
    {
        "task_id": "string",
        "task_type": "string",
        "parameters": {...},
        "constraints": [...],
        "validation_required": true
    }
    """
    try:
        data = request.json
        
        # Validate form
        form = TaskExecutionForm(**data)
        
        # Validate with unified confidence engine
        task_data = form.dict()
        confidence_report = confidence_engine.calculate_confidence(task_data)
        
        if not confidence_report.gate_result.approved:
            return jsonify({
                'success': False,
                'status': 'rejected',
                'reason': confidence_report.gate_result.reason,
                'confidence_report': {
                    'combined_confidence': confidence_report.combined_confidence,
                    'uncertainty_scores': confidence_report.uncertainty_scores.dict(),
                    'gate_result': confidence_report.gate_result.dict()
                }
            }), 403
        
        # Execute task
        result = await form_executor.execute_form_task(task_data)
        
        return jsonify({
            'success': True,
            'task_id': result.task_id,
            'status': result.status.value,
            'output': result.output,
            'confidence_report': {
                'combined_confidence': confidence_report.combined_confidence,
                'uncertainty_scores': confidence_report.uncertainty_scores.dict()
            },
            'timestamp': result.timestamp.isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error executing task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/forms/validation', methods=['POST'])
async def validate_task():
    """
    Validate a task without executing it
    
    Request body:
    {
        "task_data": {...},
        "validation_criteria": [...]
    }
    """
    try:
        data = request.json
        
        # Validate form
        form = ValidationForm(**data)
        
        # Perform validation
        task_data = form.task_data
        confidence_report = confidence_engine.calculate_confidence(task_data)
        
        return jsonify({
            'success': True,
            'approved': confidence_report.gate_result.approved,
            'confidence': confidence_report.combined_confidence,
            'gdh_confidence': confidence_report.gdh_confidence,
            'uncertainty_scores': {
                'UD': confidence_report.uncertainty_scores.UD,
                'UA': confidence_report.uncertainty_scores.UA,
                'UI': confidence_report.uncertainty_scores.UI,
                'UR': confidence_report.uncertainty_scores.UR,
                'UG': confidence_report.uncertainty_scores.UG,
                'total': confidence_report.uncertainty_scores.total
            },
            'gate_result': {
                'approved': confidence_report.gate_result.approved,
                'reason': confidence_report.gate_result.reason,
                'recommendations': confidence_report.gate_result.recommendations
            },
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error validating task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/forms/correction', methods=['POST'])
async def submit_correction():
    """
    Submit a correction for a task
    
    Request body:
    {
        "task_id": "string",
        "correction_type": "string",
        "original_output": {...},
        "corrected_output": {...},
        "explanation": "string"
    }
    """
    try:
        data = request.json
        
        # Validate form
        form = CorrectionForm(**data)
        
        # Capture correction
        correction = correction_system.capture_correction(
            task_id=form.task_id,
            correction_data=form.dict(),
            method='api'
        )
        
        return jsonify({
            'success': True,
            'correction_id': correction.correction_id,
            'task_id': correction.task_id,
            'patterns_extracted': len(correction.patterns) if hasattr(correction, 'patterns') else 0,
            'timestamp': correction.timestamp.isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error submitting correction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/forms/submission/<submission_id>', methods=['GET'])
def get_submission_status(submission_id: str):
    """Get status of a form submission"""
    try:
        status = form_handler.get_submission_status(submission_id)
        
        if not status:
            return jsonify({
                'success': False,
                'error': 'Submission not found'
            }), 404
        
        return jsonify({
            'success': True,
            'submission': status
        })
    
    except Exception as e:
        logger.error(f"Error getting submission status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# CORRECTION & LEARNING ENDPOINTS
# ============================================================================

@app.route('/api/corrections/patterns', methods=['GET'])
def get_correction_patterns():
    """Get extracted correction patterns"""
    try:
        task_type = request.args.get('task_type')
        min_frequency = int(request.args.get('min_frequency', 2))
        
        patterns = correction_system.get_correction_patterns(
            task_type=task_type,
            min_frequency=min_frequency
        )
        
        return jsonify({
            'success': True,
            'patterns': [p.dict() for p in patterns],
            'count': len(patterns)
        })
    
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/corrections/statistics', methods=['GET'])
def get_correction_statistics():
    """Get correction system statistics"""
    try:
        stats = correction_system.get_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/corrections/training-data', methods=['GET'])
def get_training_data():
    """Get training data for shadow agent"""
    try:
        task_type = request.args.get('task_type')
        limit = request.args.get('limit', type=int)
        
        training_data = correction_system.get_training_data(
            task_type=task_type,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'training_data': training_data,
            'count': len(training_data)
        })
    
    except Exception as e:
        logger.error(f"Error getting training data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# HITL ENDPOINTS
# ============================================================================

@app.route('/api/hitl/interventions/pending', methods=['GET'])
def get_pending_interventions():
    """Get pending intervention requests"""
    try:
        interventions = hitl_monitor.get_pending_interventions()
        
        return jsonify({
            'success': True,
            'interventions': [i.dict() for i in interventions],
            'count': len(interventions)
        })
    
    except Exception as e:
        logger.error(f"Error getting interventions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hitl/interventions/<request_id>/respond', methods=['POST'])
def respond_to_intervention(request_id: str):
    """Respond to an intervention request"""
    try:
        data = request.json
        
        response = hitl_monitor.submit_intervention_response(
            request_id=request_id,
            response_data=data
        )
        
        return jsonify({
            'success': True,
            'response': response.dict()
        })
    
    except Exception as e:
        logger.error(f"Error responding to intervention: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hitl/statistics', methods=['GET'])
def get_hitl_statistics():
    """Get HITL checkpoint statistics"""
    try:
        stats = hitl_monitor.get_checkpoint_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting HITL statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# SYSTEM INFO ENDPOINTS
# ============================================================================

@app.route('/api/system/info', methods=['GET'])
def get_system_info():
    """Get integrated system information"""
    return jsonify({
        'success': True,
        'system': {
            'name': 'Murphy System - Integrated',
            'version': '2.0.0',
            'components': {
                'murphy_runtime': MURPHY_AVAILABLE,
                'domain_engine': DOMAIN_ENGINE_AVAILABLE,
                'form_intake': True,
                'murphy_validation': True,
                'correction_capture': True,
                'shadow_agent': True,
                'hitl_monitor': True
            },
            'endpoints': {
                'original': 'All original endpoints preserved',
                'forms': '/api/forms/*',
                'corrections': '/api/corrections/*',
                'hitl': '/api/hitl/*',
                'system': '/api/system/*'
            }
        }
    })


# ============================================================================
# STARTUP
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('MURPHY_PORT', 8000))
    print("=" * 60)
    print("Murphy System - Integrated Backend")
    print("=" * 60)
    print(f"Murphy Runtime Available: {MURPHY_AVAILABLE}")
    print(f"Domain Engine Available: {DOMAIN_ENGINE_AVAILABLE}")
    print("Form Integration: ✓")
    print("Murphy Validation: ✓")
    print("Correction Capture: ✓")
    print("Shadow Agent: ✓")
    print("HITL Monitor: ✓")
    print(f"Starting server on http://localhost:{port}")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
