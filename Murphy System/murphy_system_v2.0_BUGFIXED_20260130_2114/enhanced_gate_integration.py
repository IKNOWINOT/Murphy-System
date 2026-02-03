"""
Enhanced Gate Integration
Adds: Static Agent Sensor Gates, Agent API Gates, Date Validation Gates,
Research Gates (Opinion vs Fact), and stores all controls in Librarian
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

class EnhancedGateIntegration:
    """Integrates all gate types with Librarian storage"""
    
    def __init__(self, librarian, generative_gate_system):
        self.librarian = librarian
        self.gate_system = generative_gate_system
        self.initialize_controls()
    
    def initialize_controls(self):
        """Store all gate controls in Librarian for generative use"""
        
        # Static Agent Sensor Gate Controls
        sensor_controls = {
            "type": "sensor_gate_controls",
            "description": "Static agent sensor gates make API calls for information",
            "controls": [
                {
                    "name": "quality_sensor_gate",
                    "purpose": "Monitor output quality metrics",
                    "api_calls": ["quality_check", "content_validation", "accuracy_score"],
                    "thresholds": {"min_quality": 0.8, "max_errors": 5}
                },
                {
                    "name": "cost_sensor_gate",
                    "purpose": "Track token usage and costs",
                    "api_calls": ["token_counter", "cost_calculator", "budget_tracker"],
                    "thresholds": {"max_tokens": 100000, "max_cost": 1000}
                },
                {
                    "name": "compliance_sensor_gate",
                    "purpose": "Verify regulatory compliance",
                    "api_calls": ["compliance_checker", "regulation_validator", "audit_logger"],
                    "thresholds": {"compliance_score": 0.95}
                }
            ]
        }
        self.librarian.knowledge_base["sensor_gate_controls"] = json.dumps(sensor_controls)
        
        # Agent API Gate Controls
        api_controls = {
            "type": "agent_api_gate_controls",
            "description": "Agent API gates nominated by Groq and Librarian",
            "controls": [
                {
                    "name": "groq_api_gate",
                    "purpose": "LLM API calls for content generation",
                    "apis": ["groq_llama", "groq_mixtral", "aristotle_math"],
                    "utilization_tracking": True,
                    "rate_limits": {"requests_per_minute": 60, "tokens_per_day": 1000000}
                },
                {
                    "name": "librarian_api_gate",
                    "purpose": "Knowledge base queries and storage",
                    "apis": ["semantic_search", "vector_store", "knowledge_retrieval"],
                    "utilization_tracking": True,
                    "rate_limits": {"queries_per_minute": 100}
                },
                {
                    "name": "external_api_gate",
                    "purpose": "Third-party API integrations",
                    "apis": ["web_search", "data_providers", "payment_processors"],
                    "utilization_tracking": True,
                    "cost_tracking": True
                }
            ]
        }
        self.librarian.knowledge_base["agent_api_gate_controls"] = json.dumps(api_controls)
        
        # Deterministic Date Validation Controls
        date_controls = {
            "type": "date_validation_gate_controls",
            "description": "Deterministic date validation gates compare to web search",
            "controls": [
                {
                    "name": "data_freshness_gate",
                    "purpose": "Validate data is within required timeframe",
                    "validation_method": "web_search_comparison",
                    "thresholds": {
                        "max_age_days": 30,
                        "requires_web_verification": True
                    }
                },
                {
                    "name": "deadline_validation_gate",
                    "purpose": "Ensure task completion before deadline",
                    "validation_method": "deterministic_date_check",
                    "thresholds": {
                        "buffer_days": 2,
                        "requires_confirmation": True
                    }
                },
                {
                    "name": "temporal_consistency_gate",
                    "purpose": "Verify dates are logically consistent",
                    "validation_method": "deterministic_analysis",
                    "checks": ["start_before_end", "no_future_dates", "reasonable_duration"]
                }
            ]
        }
        self.librarian.knowledge_base["date_validation_gate_controls"] = json.dumps(date_controls)
        
        # Research Gate Controls (Opinion vs Fact)
        research_controls = {
            "type": "research_gate_controls",
            "description": "Research gates with clear labeling of opinion vs fact",
            "controls": [
                {
                    "name": "fact_verification_gate",
                    "purpose": "Verify factual claims with sources",
                    "validation_method": "deterministic_analysis",
                    "requirements": {
                        "source_required": True,
                        "cross_reference_count": 3,
                        "label": "FACT"
                    }
                },
                {
                    "name": "opinion_labeling_gate",
                    "purpose": "Clearly label opinions and recommendations",
                    "validation_method": "content_analysis",
                    "requirements": {
                        "explicit_label": "OPINION",
                        "reasoning_required": True,
                        "disclaimer": "This is a recommendation based on available information"
                    }
                },
                {
                    "name": "source_quality_gate",
                    "purpose": "Assess quality and reliability of sources",
                    "validation_method": "deterministic_analysis",
                    "criteria": {
                        "peer_reviewed": 1.0,
                        "industry_report": 0.8,
                        "news_article": 0.6,
                        "blog_post": 0.4,
                        "social_media": 0.2
                    }
                }
            ]
        }
        self.librarian.knowledge_base["research_gate_controls"] = json.dumps(research_controls)
        
        # Reasoning vs Generative Controls
        reasoning_controls = {
            "type": "reasoning_generative_controls",
            "description": "Reasoning is deterministic analysis, generative is data-based",
            "controls": [
                {
                    "name": "deterministic_reasoning_gate",
                    "purpose": "Logical analysis based on rules and constraints",
                    "method": "deterministic",
                    "characteristics": [
                        "Rule-based decision making",
                        "Logical inference",
                        "Mathematical calculations",
                        "Constraint satisfaction"
                    ]
                },
                {
                    "name": "generative_data_gate",
                    "purpose": "Content generation based on measured variables",
                    "method": "generative",
                    "characteristics": [
                        "Data-driven generation",
                        "Statistical patterns",
                        "Learned representations",
                        "Probabilistic outputs"
                    ]
                }
            ]
        }
        self.librarian.knowledge_base["reasoning_generative_controls"] = json.dumps(reasoning_controls)
    
    def generate_enhanced_gates(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate gates using all control types"""
        
        gates = []
        
        # 1. Add Sensor Gates
        sensor_gates = self._generate_sensor_gates(task)
        gates.extend(sensor_gates)
        
        # 2. Add API Gates
        api_gates = self._generate_api_gates(task)
        gates.extend(api_gates)
        
        # 3. Add Date Validation Gates
        date_gates = self._generate_date_gates(task)
        gates.extend(date_gates)
        
        # 4. Add Research Gates
        research_gates = self._generate_research_gates(task)
        gates.extend(research_gates)
        
        # 5. Add Insurance Risk Gates (existing)
        try:
            # The generative gate system needs analysis and context
            analysis = {"task_type": "unknown", "complexity": "simple"}
            context = {"task": task}
            risk_gate_list = self.gate_system.generate_gates(analysis, context)
            # Convert to dict format
            for gate in risk_gate_list:
                if hasattr(gate, 'dict'):
                    gates.append(gate.dict())
                elif isinstance(gate, dict):
                    gates.append(gate)
        except Exception as e:
            print(f"Warning: Could not generate risk gates: {e}")
        
        # Count risk gates
        risk_gate_count = sum(1 for g in gates if g.get('gate_type') == 'risk' or 'risk' in str(g.get('gate_type', '')).lower())
        
        return {
            "success": True,
            "gates": gates,
            "gate_count": len(gates),
            "categories": {
                "sensor": len(sensor_gates),
                "api": len(api_gates),
                "date": len(date_gates),
                "research": len(research_gates),
                "risk": risk_gate_count
            }
        }
    
    def _generate_sensor_gates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate static agent sensor gates"""
        gates = []
        
        # Quality sensor gate
        gates.append({
            "gate_id": f"sensor_quality_{datetime.now().timestamp()}",
            "gate_type": "sensor",
            "sensor_type": "quality",
            "description": "Monitor output quality metrics",
            "api_calls": ["quality_check", "content_validation", "accuracy_score"],
            "thresholds": {"min_quality": 0.8, "max_errors": 5},
            "required": True,
            "confidence": 0.95
        })
        
        # Cost sensor gate
        if task.get("budget"):
            gates.append({
                "gate_id": f"sensor_cost_{datetime.now().timestamp()}",
                "gate_type": "sensor",
                "sensor_type": "cost",
                "description": "Track token usage and costs",
                "api_calls": ["token_counter", "cost_calculator", "budget_tracker"],
                "thresholds": {
                    "max_tokens": 100000,
                    "max_cost": task.get("budget", 1000)
                },
                "required": True,
                "confidence": 0.98
            })
        
        # Compliance sensor gate
        if task.get("requirements", {}).get("compliance"):
            gates.append({
                "gate_id": f"sensor_compliance_{datetime.now().timestamp()}",
                "gate_type": "sensor",
                "sensor_type": "compliance",
                "description": "Verify regulatory compliance",
                "api_calls": ["compliance_checker", "regulation_validator", "audit_logger"],
                "regulations": task["requirements"]["compliance"],
                "thresholds": {"compliance_score": 0.95},
                "required": True,
                "confidence": 0.90
            })
        
        return gates
    
    def _generate_api_gates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate agent API gates"""
        gates = []
        
        # Groq API gate for LLM calls
        gates.append({
            "gate_id": f"api_groq_{datetime.now().timestamp()}",
            "gate_type": "api",
            "api_provider": "groq",
            "description": "LLM API calls for content generation",
            "apis": ["groq_llama", "groq_mixtral"],
            "utilization_tracking": True,
            "rate_limits": {"requests_per_minute": 60, "tokens_per_day": 1000000},
            "required": True,
            "confidence": 0.95
        })
        
        # Librarian API gate for knowledge retrieval
        if task.get("requirements", {}).get("research"):
            gates.append({
                "gate_id": f"api_librarian_{datetime.now().timestamp()}",
                "gate_type": "api",
                "api_provider": "librarian",
                "description": "Knowledge base queries and storage",
                "apis": ["semantic_search", "vector_store", "knowledge_retrieval"],
                "utilization_tracking": True,
                "rate_limits": {"queries_per_minute": 100},
                "required": True,
                "confidence": 0.92
            })
        
        # External API gate if needed
        if task.get("requirements", {}).get("api_integrations"):
            gates.append({
                "gate_id": f"api_external_{datetime.now().timestamp()}",
                "gate_type": "api",
                "api_provider": "external",
                "description": "Third-party API integrations",
                "apis": task["requirements"]["api_integrations"],
                "utilization_tracking": True,
                "cost_tracking": True,
                "required": True,
                "confidence": 0.85
            })
        
        return gates
    
    def _generate_date_gates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate deterministic date validation gates"""
        gates = []
        
        requirements = task.get("requirements", {})
        
        # Data freshness gate
        if requirements.get("data_freshness"):
            gates.append({
                "gate_id": f"date_freshness_{datetime.now().timestamp()}",
                "gate_type": "date_validation",
                "validation_type": "data_freshness",
                "description": "Validate data is within required timeframe",
                "validation_method": "web_search_comparison",
                "requirement": requirements["data_freshness"],
                "thresholds": {
                    "max_age_days": 30,
                    "requires_web_verification": True
                },
                "required": True,
                "confidence": 0.95
            })
        
        # Deadline validation gate
        if requirements.get("deadline"):
            gates.append({
                "gate_id": f"date_deadline_{datetime.now().timestamp()}",
                "gate_type": "date_validation",
                "validation_type": "deadline",
                "description": "Ensure task completion before deadline",
                "validation_method": "deterministic_date_check",
                "deadline": requirements["deadline"],
                "thresholds": {
                    "buffer_days": 2,
                    "requires_confirmation": True
                },
                "required": True,
                "confidence": 0.98
            })
        
        return gates
    
    def _generate_research_gates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate research gates with opinion vs fact labeling"""
        gates = []
        
        requirements = task.get("requirements", {})
        
        # Fact verification gate
        if requirements.get("fact_checking"):
            gates.append({
                "gate_id": f"research_fact_{datetime.now().timestamp()}",
                "gate_type": "research",
                "research_type": "fact_verification",
                "description": "Verify factual claims with sources",
                "validation_method": "deterministic_analysis",
                "requirements": {
                    "source_required": True,
                    "cross_reference_count": 3,
                    "label": "FACT"
                },
                "required": True,
                "confidence": 0.90
            })
        
        # Opinion labeling gate
        if requirements.get("opinion_labeling"):
            gates.append({
                "gate_id": f"research_opinion_{datetime.now().timestamp()}",
                "gate_type": "research",
                "research_type": "opinion_labeling",
                "description": "Clearly label opinions and recommendations",
                "validation_method": "content_analysis",
                "requirements": {
                    "explicit_label": "OPINION",
                    "reasoning_required": True,
                    "disclaimer": "This is a recommendation based on available information"
                },
                "required": True,
                "confidence": 0.88
            })
        
        # Source quality gate
        if requirements.get("research_depth"):
            gates.append({
                "gate_id": f"research_source_{datetime.now().timestamp()}",
                "gate_type": "research",
                "research_type": "source_quality",
                "description": "Assess quality and reliability of sources",
                "validation_method": "deterministic_analysis",
                "criteria": {
                    "peer_reviewed": 1.0,
                    "industry_report": 0.8,
                    "news_article": 0.6,
                    "blog_post": 0.4,
                    "social_media": 0.2
                },
                "required": True,
                "confidence": 0.85
            })
        
        return gates

def integrate_enhanced_gates(app, librarian, generative_gate_system):
    """Integrate enhanced gate system with Flask app"""
    
    enhanced_gates = EnhancedGateIntegration(librarian, generative_gate_system)
    
    @app.route('/api/gates/enhanced/generate', methods=['POST'])
    def generate_enhanced_gates():
        """Generate gates using all control types"""
        from flask import request, jsonify
        
        try:
            data = request.json
            task = data.get('task', {})
            
            result = enhanced_gates.generate_enhanced_gates(task)
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/gates/controls/<control_type>', methods=['GET'])
    def get_gate_controls(control_type):
        """Get specific gate control definitions from Librarian"""
        from flask import jsonify
        
        try:
            # Get control from Librarian knowledge base
            control_key = f"{control_type}_controls"
            if control_key in librarian.knowledge_base:
                control_data = json.loads(librarian.knowledge_base[control_key])
                return jsonify({
                    'success': True,
                    'control_type': control_type,
                    'controls': control_data
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'No controls found for type: {control_type}'
                }), 404
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return enhanced_gates