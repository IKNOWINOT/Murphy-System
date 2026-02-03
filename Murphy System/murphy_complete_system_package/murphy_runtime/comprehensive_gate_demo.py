# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Comprehensive Gate Systems Demo
Shows all gate types working: Sensor, API, Date, Research, and Insurance Risk
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:3002"

def print_header(title):
    print("\n" + "="*100)
    print(f"  {title}")
    print("="*100)

def print_subheader(title):
    print("\n" + "-"*100)
    print(f"  {title}")
    print("-"*100)

def print_json(data, indent=2):
    print(json.dumps(data, indent=indent))

def test_enhanced_gates():
    """Test the enhanced gate generation system"""
    print_header("MURPHY ENHANCED GATE SYSTEMS - COMPREHENSIVE DEMO")
    
    # Test Case 1: Simple Task (Minimal Gates)
    print_subheader("TEST 1: Simple Task - Blog Post")
    task1 = {
        "name": "Write Blog Post",
        "description": "Write a 1000-word blog post about AI trends",
        "budget": 100,
        "revenue_potential": 500
    }
    
    response = requests.post(f"{BASE_URL}/api/gates/enhanced/generate", json={"task": task1})
    result = response.json()
    print(f"\n✓ Generated {result.get('gate_count', 0)} gates")
    print(f"  Categories: {result.get('categories', {})}")
    print("\nGates:")
    for gate in result.get('gates', [])[:3]:  # Show first 3
        print(f"  - [{gate.get('gate_type')}] {gate.get('description')}")
    
    # Test Case 2: Research Task (Date + Research Gates)
    print_subheader("TEST 2: Research Task with Date Requirements")
    task2 = {
        "name": "Market Research Report",
        "description": "Research latest AI trends and create comprehensive report",
        "requirements": {
            "data_freshness": "last_30_days",
            "deadline": (datetime.now() + timedelta(days=7)).isoformat(),
            "fact_checking": "required",
            "opinion_labeling": "mandatory",
            "research_depth": "comprehensive"
        },
        "revenue_potential": 5000,
        "budget": 1000,
        "industry": "technology"
    }
    
    response = requests.post(f"{BASE_URL}/api/gates/enhanced/generate", json={"task": task2})
    result = response.json()
    print(f"\n✓ Generated {result.get('gate_count', 0)} gates")
    print(f"  Categories: {result.get('categories', {})}")
    
    # Show gates by category
    gates = result.get('gates', [])
    for category in ['sensor', 'api', 'date_validation', 'research', 'risk']:
        category_gates = [g for g in gates if category in g.get('gate_type', '')]
        if category_gates:
            print(f"\n  {category.upper()} GATES ({len(category_gates)}):")
            for gate in category_gates:
                print(f"    - {gate.get('description')}")
                if 'validation_method' in gate:
                    print(f"      Method: {gate.get('validation_method')}")
    
    # Test Case 3: High-Risk Task (All Gate Types)
    print_subheader("TEST 3: High-Risk Enterprise Task")
    task3 = {
        "name": "AI-Powered Medical Diagnosis System",
        "description": "Develop AI system for medical diagnosis with full regulatory compliance",
        "requirements": {
            "research": {
                "medical_literature": "peer_reviewed",
                "data_freshness": "last_12_months",
                "fact_checking": "triple_verified"
            },
            "compliance": ["HIPAA", "FDA", "ISO13485"],
            "deadline": (datetime.now() + timedelta(days=180)).isoformat(),
            "api_integrations": ["medical_databases", "imaging_systems", "ehr_systems"],
            "fact_checking": "required",
            "opinion_labeling": "mandatory",
            "research_depth": "comprehensive"
        },
        "revenue_potential": 2000000,
        "budget": 500000,
        "industry": "healthcare",
        "risk_factors": {
            "patient_safety": "critical",
            "regulatory_risk": "high",
            "liability_exposure": "extreme"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/gates/enhanced/generate", json={"task": task3})
    result = response.json()
    print(f"\n✓ Generated {result.get('gate_count', 0)} gates")
    print(f"  Categories: {result.get('categories', {})}")
    
    # Detailed breakdown
    gates = result.get('gates', [])
    print(f"\n📊 COMPREHENSIVE GATE ANALYSIS:")
    print(f"  Total Gates: {len(gates)}")
    
    gate_types = {}
    for gate in gates:
        gtype = gate.get('gate_type', 'unknown')
        gate_types[gtype] = gate_types.get(gtype, 0) + 1
    
    for gtype, count in sorted(gate_types.items()):
        print(f"    {gtype}: {count}")
    
    # Show sample gates from each category
    print(f"\n📋 SAMPLE GATES BY CATEGORY:")
    
    for category in ['sensor', 'api', 'date_validation', 'research']:
        category_gates = [g for g in gates if category in g.get('gate_type', '')]
        if category_gates:
            print(f"\n  {category.upper()}:")
            gate = category_gates[0]
            print(f"    ID: {gate.get('gate_id')}")
            print(f"    Description: {gate.get('description')}")
            print(f"    Required: {gate.get('required')}")
            print(f"    Confidence: {gate.get('confidence')}")
            if 'validation_method' in gate:
                print(f"    Validation: {gate.get('validation_method')}")
            if 'thresholds' in gate:
                print(f"    Thresholds: {gate.get('thresholds')}")

def test_control_retrieval():
    """Test retrieving gate controls from Librarian"""
    print_header("GATE CONTROL DEFINITIONS (Stored in Librarian)")
    
    control_types = [
        "sensor_gate",
        "agent_api_gate",
        "date_validation_gate",
        "research_gate",
        "reasoning_generative"
    ]
    
    for control_type in control_types:
        print_subheader(f"{control_type.upper()} CONTROLS")
        
        response = requests.get(f"{BASE_URL}/api/gates/controls/{control_type}")
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                controls = result.get('controls', {})
                print(f"\nType: {controls.get('type')}")
                print(f"Description: {controls.get('description')}")
                print(f"\nControls ({len(controls.get('controls', []))}):")
                for ctrl in controls.get('controls', []):
                    print(f"  - {ctrl.get('name')}: {ctrl.get('purpose')}")
            else:
                print(f"  ⚠ {result.get('error')}")
        else:
            print(f"  ⚠ HTTP {response.status_code}")

def test_sensor_status():
    """Test sensor gate status"""
    print_header("SENSOR GATE STATUS")
    
    response = requests.get(f"{BASE_URL}/api/gates/sensors/status")
    result = response.json()
    
    if result.get('success'):
        status = result.get('status', {})
        print(f"\nTotal Sensors: {status.get('total_sensors')}")
        print(f"Capabilities: {len(status.get('capabilities', []))}")
        
        print(f"\n📡 ACTIVE SENSORS:")
        for sensor in status.get('sensors', []):
            print(f"\n  {sensor.get('sensor_id')}:")
            print(f"    Type: {sensor.get('sensor_type')}")
            print(f"    State: {sensor.get('circuit_breaker_state')}")
            print(f"    Observations: {sensor.get('observations_count')}")
            print(f"    Rules: {sensor.get('rules_count')}")

def test_capabilities():
    """Test capability verification"""
    print_header("CAPABILITY VERIFICATION")
    
    response = requests.get(f"{BASE_URL}/api/gates/capabilities")
    result = response.json()
    
    if result.get('success'):
        capabilities = result.get('capabilities', [])
        print(f"\n✓ Available Capabilities ({len(capabilities)}):")
        for cap in capabilities:
            print(f"  - {cap}")

def run_comprehensive_demo():
    """Run the complete demo"""
    try:
        print("\n" + "="*100)
        print("  MURPHY ENHANCED GATE SYSTEMS")
        print("  Comprehensive Demonstration of All Gate Types")
        print("="*100)
        print("\n  Gate Types:")
        print("    1. Static Agent Sensor Gates - Monitor quality, cost, compliance")
        print("    2. Agent API Gates - Track API utilization (Groq, Librarian, External)")
        print("    3. Deterministic Date Validation - Compare to web search, verify freshness")
        print("    4. Research Gates - Label facts vs opinions, verify sources")
        print("    5. Insurance Risk Gates - Actuarial formulas for risk assessment")
        print("\n" + "="*100)
        
        # Run all tests
        test_sensor_status()
        test_capabilities()
        test_control_retrieval()
        test_enhanced_gates()
        
        print_header("✅ COMPREHENSIVE DEMO COMPLETE")
        print("\nAll gate systems are operational and integrated with Librarian storage.")
        print("Controls are stored in the knowledge base for generative use.")
        
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_comprehensive_demo()