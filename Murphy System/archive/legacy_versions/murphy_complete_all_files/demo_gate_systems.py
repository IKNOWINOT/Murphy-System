"""
Demo Script for Murphy Gate Systems
Tests all gate types: Static Agent Sensor Gates, Agent API Gates, 
Deterministic Date Validation, Research Gates, and Insurance Risk Gates
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:3002"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_result(name, data):
    print(f"\n{name}:")
    print(json.dumps(data, indent=2))
    print("-" * 80)

# ============================================================================
# TEST 1: STATIC AGENT SENSOR GATES
# ============================================================================
def test_sensor_gates():
    print_section("TEST 1: STATIC AGENT SENSOR GATES")
    
    # Get all sensors status
    response = requests.get(f"{BASE_URL}/api/gates/sensors/status")
    print_result("All Sensors Status", response.json())
    
    # Get specific sensor details
    sensors = ["quality_sensor", "cost_sensor", "compliance_sensor"]
    for sensor_id in sensors:
        response = requests.get(f"{BASE_URL}/api/gates/sensors/{sensor_id}")
        print_result(f"Sensor: {sensor_id}", response.json())

# ============================================================================
# TEST 2: AGENT API GATES (Librarian-nominated APIs)
# ============================================================================
def test_api_gates():
    print_section("TEST 2: AGENT API GATES (Librarian Integration)")
    
    # Get capabilities list
    response = requests.get(f"{BASE_URL}/api/gates/capabilities")
    print_result("Available Capabilities", response.json())
    
    # Verify specific capability
    test_capabilities = [
        "web_search",
        "data_analysis", 
        "content_generation",
        "risk_assessment"
    ]
    
    for capability in test_capabilities:
        response = requests.post(
            f"{BASE_URL}/api/gates/capabilities/verify",
            json={"capability": capability}
        )
        print_result(f"Verify Capability: {capability}", response.json())

# ============================================================================
# TEST 3: DETERMINISTIC DATE VALIDATION GATES
# ============================================================================
def test_date_validation_gates():
    print_section("TEST 3: DETERMINISTIC DATE VALIDATION GATES")
    
    # Test task with date requirements
    task = {
        "name": "Market Research Report",
        "description": "Research latest AI trends and create report",
        "requirements": {
            "data_freshness": "last_30_days",
            "deadline": (datetime.now() + timedelta(days=7)).isoformat(),
            "sources_required": ["web_search", "academic_papers", "industry_reports"]
        },
        "revenue_potential": 5000,
        "budget": 1000,
        "industry": "technology"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/gates/generate",
        json={"task": task}
    )
    result = response.json()
    print_result("Date Validation Gates Generated", result)
    
    # Check for date-specific gates
    if result.get("success"):
        gates = result.get("gates", [])
        date_gates = [g for g in gates if "date" in g.get("type", "").lower() or 
                      "time" in g.get("type", "").lower()]
        print(f"\n✓ Found {len(date_gates)} date-related gates")
        for gate in date_gates:
            print(f"  - {gate.get('type')}: {gate.get('description')}")

# ============================================================================
# TEST 4: RESEARCH GATES (Opinion vs Fact Labeling)
# ============================================================================
def test_research_gates():
    print_section("TEST 4: RESEARCH GATES (Opinion vs Fact)")
    
    # Test research task requiring clear fact/opinion distinction
    task = {
        "name": "Investment Analysis Report",
        "description": "Analyze cryptocurrency market and provide investment recommendations",
        "requirements": {
            "research_depth": "comprehensive",
            "fact_checking": "required",
            "opinion_labeling": "mandatory",
            "sources": ["market_data", "expert_opinions", "historical_analysis"]
        },
        "revenue_potential": 50000,
        "budget": 5000,
        "industry": "finance"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/gates/generate",
        json={"task": task}
    )
    result = response.json()
    print_result("Research Gates Generated", result)
    
    # Check for research-specific gates
    if result.get("success"):
        gates = result.get("gates", [])
        research_gates = [g for g in gates if "research" in g.get("type", "").lower() or 
                         "fact" in g.get("type", "").lower() or
                         "opinion" in g.get("type", "").lower()]
        print(f"\n✓ Found {len(research_gates)} research-related gates")
        for gate in research_gates:
            print(f"  - {gate.get('type')}: {gate.get('description')}")

# ============================================================================
# TEST 5: INSURANCE RISK GATES (Actuarial Formulas)
# ============================================================================
def test_insurance_risk_gates():
    print_section("TEST 5: INSURANCE RISK GATES (Actuarial Analysis)")
    
    # High-risk task to trigger multiple insurance gates
    task = {
        "name": "Enterprise E-commerce Platform",
        "description": "Build complete e-commerce platform with payment processing",
        "requirements": {
            "complexity": "high",
            "security": "critical",
            "compliance": ["PCI-DSS", "GDPR", "SOC2"],
            "uptime_requirement": "99.99%"
        },
        "revenue_potential": 500000,
        "budget": 50000,
        "industry": "finance",
        "risk_factors": {
            "data_breach_potential": "high",
            "financial_transactions": True,
            "customer_data_volume": "large"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/gates/generate",
        json={"task": task}
    )
    result = response.json()
    print_result("Insurance Risk Gates Generated", result)
    
    # Analyze risk assessment
    if result.get("success"):
        risk_assessment = result.get("risk_assessment", {})
        print("\n📊 ACTUARIAL RISK ANALYSIS:")
        print(f"  Expected Loss: ${risk_assessment.get('expected_loss', 0):,.2f}")
        print(f"  Risk Score: {risk_assessment.get('risk_score', 0):,.0f}")
        print(f"  Value at Risk (95%): ${risk_assessment.get('var_95', 0):,.2f}")
        print(f"  Retention Limit: ${risk_assessment.get('retention_limit', 0):,.2f}")
        print(f"  Insurance Premium: ${risk_assessment.get('insurance_premium', 0):,.2f}")
        
        gates = result.get("gates", [])
        print(f"\n✓ Generated {len(gates)} risk-based gates")
        for gate in gates:
            print(f"  - {gate.get('type')}: {gate.get('description')}")
            print(f"    Threshold: {gate.get('threshold')}")

# ============================================================================
# TEST 6: COMBINED GATE SYSTEM (All Types Together)
# ============================================================================
def test_combined_gates():
    print_section("TEST 6: COMBINED GATE SYSTEM (All Types)")
    
    # Complex task requiring all gate types
    task = {
        "name": "AI-Powered Medical Diagnosis System",
        "description": "Develop AI system for medical diagnosis with regulatory compliance",
        "requirements": {
            "research": {
                "medical_literature": "peer_reviewed",
                "data_freshness": "last_12_months",
                "fact_checking": "triple_verified"
            },
            "compliance": ["HIPAA", "FDA", "ISO13485"],
            "deadline": (datetime.now() + timedelta(days=180)).isoformat(),
            "api_integrations": ["medical_databases", "imaging_systems", "ehr_systems"]
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
    
    response = requests.post(
        f"{BASE_URL}/api/gates/generate",
        json={"task": task}
    )
    result = response.json()
    print_result("Combined Gate System Analysis", result)
    
    if result.get("success"):
        gates = result.get("gates", [])
        
        # Categorize gates
        gate_categories = {
            "sensor": [],
            "api": [],
            "date": [],
            "research": [],
            "risk": []
        }
        
        for gate in gates:
            gate_type = gate.get("type", "").lower()
            if "sensor" in gate_type or "quality" in gate_type:
                gate_categories["sensor"].append(gate)
            elif "api" in gate_type or "capability" in gate_type:
                gate_categories["api"].append(gate)
            elif "date" in gate_type or "time" in gate_type:
                gate_categories["date"].append(gate)
            elif "research" in gate_type or "fact" in gate_type:
                gate_categories["research"].append(gate)
            else:
                gate_categories["risk"].append(gate)
        
        print("\n📋 GATE BREAKDOWN BY CATEGORY:")
        for category, category_gates in gate_categories.items():
            print(f"\n  {category.upper()} GATES: {len(category_gates)}")
            for gate in category_gates:
                print(f"    - {gate.get('description')}")

# ============================================================================
# TEST 7: LIBRARIAN STORAGE VERIFICATION
# ============================================================================
def test_librarian_storage():
    print_section("TEST 7: LIBRARIAN STORAGE (Controls in Database)")
    
    # Verify controls are stored in Librarian
    response = requests.post(
        f"{BASE_URL}/api/librarian/search",
        json={
            "query": "gate control requirements",
            "top_k": 10
        }
    )
    print_result("Librarian Search: Gate Controls", response.json())
    
    # Search for specific control types
    control_types = [
        "sensor gate controls",
        "api gate controls",
        "date validation controls",
        "research gate controls",
        "insurance risk controls"
    ]
    
    for control_type in control_types:
        response = requests.post(
            f"{BASE_URL}/api/librarian/search",
            json={"query": control_type, "top_k": 3}
        )
        result = response.json()
        if result.get("success"):
            results = result.get("results", [])
            print(f"\n✓ Found {len(results)} entries for '{control_type}'")

# ============================================================================
# MAIN DEMO EXECUTION
# ============================================================================
def run_full_demo():
    print("\n" + "="*80)
    print("  MURPHY GATE SYSTEMS - COMPREHENSIVE DEMO")
    print("  Testing: Sensor Gates, API Gates, Date Validation,")
    print("           Research Gates, and Insurance Risk Gates")
    print("="*80)
    
    try:
        # Run all tests
        test_sensor_gates()
        test_api_gates()
        test_date_validation_gates()
        test_research_gates()
        test_insurance_risk_gates()
        test_combined_gates()
        test_librarian_storage()
        
        print_section("✅ DEMO COMPLETE - ALL SYSTEMS TESTED")
        
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_full_demo()