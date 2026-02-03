"""
Test Suite: Insurance Risk-Based Gate Generation
Demonstrates actuarial risk assessment and gate generation
"""

import json
from insurance_risk_gates import (
    InsuranceRiskGateGenerator,
    InsuranceRiskSensorAgent,
    ActuarialRiskCalculator,
    RiskExposure,
    LossFrequency,
    LossSeverity,
    RiskControl,
    ControlEffectiveness
)

def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")

def test_actuarial_formulas():
    """Test basic actuarial formulas"""
    print_section("TEST 1: Actuarial Risk Formulas")
    
    calculator = ActuarialRiskCalculator()
    
    # Create test data
    frequency = LossFrequency(
        historical_events=10,
        time_period=365,
        confidence_level=0.85
    )
    
    severity = LossSeverity(
        average_loss=5000.0,
        maximum_loss=10000.0,
        loss_distribution='lognormal'
    )
    
    exposure = RiskExposure(
        exposure_value=50000.0,
        exposure_type='revenue',
        time_period=30
    )
    
    controls = [
        RiskControl(
            control_id='quality_check',
            control_type='detective',
            effectiveness=ControlEffectiveness.ADEQUATE,
            cost=100
        ),
        RiskControl(
            control_id='approval_gate',
            control_type='preventive',
            effectiveness=ControlEffectiveness.STRONG,
            cost=50
        )
    ]
    
    # Calculate metrics
    print("📊 INPUT DATA")
    print(f"Frequency: {frequency.annual_frequency():.2f} events/year")
    print(f"Probability: {frequency.probability()*100:.1f}%")
    print(f"Average Severity: ${severity.average_loss:,.2f}")
    print(f"Maximum Severity: ${severity.maximum_loss:,.2f}")
    print(f"Exposure: ${exposure.exposure_value:,.2f}")
    print(f"Controls: {len(controls)} controls")
    
    print("\n📈 CALCULATED METRICS")
    
    # Expected Loss
    expected_loss = calculator.expected_loss(frequency, severity)
    print(f"Expected Loss (EL): ${expected_loss:,.2f}/year")
    print(f"  Formula: Frequency × Severity = {frequency.annual_frequency():.2f} × ${severity.average_loss:,.2f}")
    
    # Risk Score
    risk_score = calculator.risk_score(expected_loss, controls)
    print(f"\nRisk Score: {risk_score:,.2f}")
    print(f"  Formula: EL / (1 + Control Effectiveness)")
    print(f"  Lower score = Better (controls working)")
    
    # Value at Risk
    var_95 = calculator.value_at_risk(exposure, 0.95)
    print(f"\nValue at Risk (95%): ${var_95:,.2f}")
    print(f"  95% confidence that loss won't exceed this amount")
    
    # Retention Limit
    retention = calculator.retention_limit(exposure, 0.3)
    print(f"\nRetention Limit: ${retention:,.2f}")
    print(f"  Amount to self-insure (risk appetite: 30%)")
    
    # Premium
    premium = calculator.premium_calculation(expected_loss, 0.25, 0.10)
    print(f"\nInsurance Premium: ${premium:,.2f}/year")
    print(f"  Formula: EL / (1 - Expense Ratio - Profit Margin)")
    print(f"  Expense Ratio: 25%, Profit Margin: 10%")
    
    print("\n✅ All actuarial formulas calculated successfully")

def test_simple_task_risk():
    """Test risk assessment for simple task"""
    print_section("TEST 2: Simple Task Risk Assessment")
    
    generator = InsuranceRiskGateGenerator()
    
    task = {
        'id': 'task_simple_001',
        'type': 'content_creation',
        'description': 'Write a blog post about AI',
        'complexity': 'simple',
        'revenue_potential': 100,
        'budget': 500
    }
    
    context = {
        'token_budget': 500,
        'has_quality_check': True,
        'requires_approval': False,
        'has_monitoring': True
    }
    
    print("📋 TASK DETAILS")
    print(f"Task ID: {task['id']}")
    print(f"Type: {task['type']}")
    print(f"Complexity: {task['complexity']}")
    print(f"Revenue Potential: ${task['revenue_potential']}")
    print(f"Budget: ${task['budget']}")
    
    # Assess risk
    assessment = generator.assess_task_risk(task, context)
    
    print("\n🎯 RISK ASSESSMENT")
    print(f"Exposure: ${assessment['exposure']['value']:,.2f} ({assessment['exposure']['type']})")
    print(f"Annual Frequency: {assessment['frequency']['annual']:.2f} events/year")
    print(f"Probability: {assessment['frequency']['probability']*100:.1f}%")
    print(f"Average Severity: ${assessment['severity']['average']:,.2f}")
    print(f"Expected Loss: ${assessment['metrics']['expected_loss']:,.2f}/year")
    print(f"Risk Score: {assessment['metrics']['risk_score']:,.2f}")
    print(f"Risk Category: {assessment['category'].upper()}")
    print(f"Requires Gates: {'YES' if assessment['requires_gates'] else 'NO'}")
    
    # Generate gates
    gates = generator.generate_gates_from_risk(assessment, task)
    
    print(f"\n🚪 GENERATED GATES: {len(gates)}")
    for i, gate in enumerate(gates, 1):
        print(f"\n{i}. {gate['gate_type'].upper()}")
        print(f"   Question: {gate['question']}")
        print(f"   Options: {', '.join(gate['options'])}")
        print(f"   Required: {'YES' if gate['required'] else 'NO'}")
        print(f"   Priority: {gate['priority']}/10")

def test_complex_task_risk():
    """Test risk assessment for complex task"""
    print_section("TEST 3: Complex Task Risk Assessment")
    
    generator = InsuranceRiskGateGenerator()
    
    task = {
        'id': 'task_complex_001',
        'type': 'system_development',
        'description': 'Build complete e-commerce platform with payment processing',
        'complexity': 'complex',
        'revenue_potential': 50000,
        'budget': 10000,
        'duration_days': 90
    }
    
    context = {
        'token_budget': 15000,
        'has_quality_check': False,
        'requires_approval': True,
        'has_monitoring': True,
        'has_sensitive_data': True,
        'industry': 'finance'
    }
    
    print("📋 TASK DETAILS")
    print(f"Task ID: {task['id']}")
    print(f"Type: {task['type']}")
    print(f"Complexity: {task['complexity']}")
    print(f"Revenue Potential: ${task['revenue_potential']:,}")
    print(f"Budget: ${task['budget']:,}")
    print(f"Duration: {task['duration_days']} days")
    print(f"Sensitive Data: {context['has_sensitive_data']}")
    print(f"Industry: {context['industry']}")
    
    # Assess risk
    assessment = generator.assess_task_risk(task, context)
    
    print("\n🎯 RISK ASSESSMENT")
    print(f"Exposure: ${assessment['exposure']['value']:,.2f} ({assessment['exposure']['type']})")
    print(f"Annual Exposure: ${assessment['exposure']['annual']:,.2f}")
    print(f"Annual Frequency: {assessment['frequency']['annual']:.2f} events/year")
    print(f"Probability: {assessment['frequency']['probability']*100:.1f}%")
    print(f"Average Severity: ${assessment['severity']['average']:,.2f}")
    print(f"Maximum Severity: ${assessment['severity']['maximum']:,.2f}")
    print(f"Tail Risk: {assessment['severity']['tail_risk']*100:.1f}%")
    
    print("\n💰 FINANCIAL METRICS")
    print(f"Expected Loss: ${assessment['metrics']['expected_loss']:,.2f}/year")
    print(f"Risk Score: {assessment['metrics']['risk_score']:,.2f}")
    print(f"Value at Risk (95%): ${assessment['metrics']['value_at_risk_95']:,.2f}")
    print(f"Retention Limit: ${assessment['metrics']['retention_limit']:,.2f}")
    print(f"Transfer Amount: ${assessment['metrics']['transfer_amount']:,.2f}")
    
    print("\n🛡️ CONTROLS")
    print(f"Control Count: {assessment['controls']['count']}")
    print(f"Control Effectiveness: {assessment['controls']['effectiveness']*100:.1f}%")
    
    print(f"\n⚠️ RISK CATEGORY: {assessment['category'].upper()}")
    print(f"Requires Gates: {'YES' if assessment['requires_gates'] else 'NO'}")
    
    # Generate gates
    gates = generator.generate_gates_from_risk(assessment, task)
    
    print(f"\n🚪 GENERATED GATES: {len(gates)}")
    for i, gate in enumerate(gates, 1):
        print(f"\n{i}. {gate['gate_type'].upper()} (Priority: {gate['priority']}/10)")
        print(f"   Question: {gate['question']}")
        print(f"   Options:")
        for opt in gate['options']:
            print(f"     • {opt}")
        print(f"   Reasoning: {gate['reasoning']}")
        print(f"   Required: {'YES ⚠️' if gate['required'] else 'NO'}")

def test_high_revenue_task():
    """Test task with high revenue potential"""
    print_section("TEST 4: High Revenue Task")
    
    generator = InsuranceRiskGateGenerator()
    
    task = {
        'id': 'task_revenue_001',
        'type': 'product_launch',
        'description': 'Launch new SaaS product with marketing campaign',
        'complexity': 'medium',
        'revenue_potential': 100000,
        'budget': 5000,
        'duration_days': 60
    }
    
    context = {
        'token_budget': 8000,
        'has_quality_check': True,
        'requires_approval': True,
        'has_monitoring': True
    }
    
    print("📋 TASK DETAILS")
    print(f"Task: {task['description']}")
    print(f"Revenue Potential: ${task['revenue_potential']:,} 💰")
    print(f"Budget: ${task['budget']:,}")
    print(f"Revenue/Budget Ratio: {task['revenue_potential']/task['budget']:.1f}x")
    
    # Assess risk
    assessment = generator.assess_task_risk(task, context)
    
    print("\n🎯 RISK ASSESSMENT")
    print(f"Exposure: ${assessment['exposure']['value']:,.2f} (HIGH)")
    print(f"Expected Loss: ${assessment['metrics']['expected_loss']:,.2f}/year")
    print(f"Risk Score: {assessment['metrics']['risk_score']:,.2f}")
    
    # Generate gates
    gates = generator.generate_gates_from_risk(assessment, task)
    
    print(f"\n🚪 GENERATED GATES: {len(gates)}")
    
    # Show only required gates
    required_gates = [g for g in gates if g['required']]
    print(f"\n⚠️ REQUIRED GATES: {len(required_gates)}")
    for gate in required_gates:
        print(f"\n• {gate['gate_type'].upper()}")
        print(f"  {gate['question']}")
        print(f"  Priority: {gate['priority']}/10")

def test_sensor_agent_integration():
    """Test insurance risk sensor agent"""
    print_section("TEST 5: Insurance Risk Sensor Agent")
    
    sensor = InsuranceRiskSensorAgent()
    
    task = {
        'id': 'task_integration_001',
        'type': 'data_analysis',
        'description': 'Analyze customer data and generate insights',
        'complexity': 'medium',
        'revenue_potential': 5000,
        'budget': 2000
    }
    
    context = {
        'token_budget': 3000,
        'has_quality_check': True,
        'requires_approval': False,
        'has_monitoring': True,
        'has_sensitive_data': True
    }
    
    print("📋 TASK DETAILS")
    print(f"Task: {task['description']}")
    print(f"Has Sensitive Data: {context['has_sensitive_data']}")
    
    # Analyze and generate gates
    assessment, gates = sensor.analyze_and_generate_gates(task, context)
    
    print("\n🎯 RISK ASSESSMENT")
    print(f"Risk Score: {assessment['metrics']['risk_score']:,.2f}")
    print(f"Risk Category: {assessment['category'].upper()}")
    print(f"Expected Loss: ${assessment['metrics']['expected_loss']:,.2f}/year")
    
    print(f"\n🚪 GATES GENERATED: {len(gates)}")
    for gate in gates:
        print(f"• {gate['gate_type']}: {gate['question'][:60]}...")
    
    print("\n✅ Sensor agent integration successful")

def test_comparative_scenarios():
    """Compare risk across different scenarios"""
    print_section("TEST 6: Comparative Risk Analysis")
    
    generator = InsuranceRiskGateGenerator()
    
    scenarios = [
        {
            'name': 'Low Risk - Simple Blog Post',
            'task': {
                'id': 'scenario_1',
                'complexity': 'simple',
                'revenue_potential': 50,
                'budget': 200
            },
            'context': {
                'token_budget': 200,
                'has_quality_check': True,
                'requires_approval': False
            }
        },
        {
            'name': 'Medium Risk - Marketing Campaign',
            'task': {
                'id': 'scenario_2',
                'complexity': 'medium',
                'revenue_potential': 5000,
                'budget': 1000
            },
            'context': {
                'token_budget': 1500,
                'has_quality_check': True,
                'requires_approval': True
            }
        },
        {
            'name': 'High Risk - Financial System',
            'task': {
                'id': 'scenario_3',
                'complexity': 'complex',
                'revenue_potential': 50000,
                'budget': 10000
            },
            'context': {
                'token_budget': 15000,
                'has_quality_check': False,
                'requires_approval': True,
                'has_sensitive_data': True,
                'industry': 'finance'
            }
        }
    ]
    
    print("📊 COMPARATIVE RISK ANALYSIS\n")
    print(f"{'Scenario':<30} {'Risk Score':<15} {'Expected Loss':<20} {'Gates':<10} {'Category':<10}")
    print("-" * 85)
    
    for scenario in scenarios:
        assessment = generator.assess_task_risk(scenario['task'], scenario['context'])
        gates = generator.generate_gates_from_risk(assessment, scenario['task'])
        
        print(f"{scenario['name']:<30} "
              f"{assessment['metrics']['risk_score']:<15.2f} "
              f"${assessment['metrics']['expected_loss']:<19,.2f} "
              f"{len(gates):<10} "
              f"{assessment['category']:<10}")
    
    print("\n✅ Comparative analysis complete")

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" INSURANCE RISK-BASED GATE GENERATION - TEST SUITE")
    print("=" * 80)
    
    try:
        test_actuarial_formulas()
        test_simple_task_risk()
        test_complex_task_risk()
        test_high_revenue_task()
        test_sensor_agent_integration()
        test_comparative_scenarios()
        
        print_section("TEST SUITE COMPLETE")
        print("✅ All tests passed successfully!")
        print("\n📚 Key Learnings:")
        print("• Insurance actuarial formulas provide rigorous risk assessment")
        print("• Expected Loss = Frequency × Severity")
        print("• Risk Score = Expected Loss / (1 + Control Effectiveness)")
        print("• Gates are generated based on quantitative risk thresholds")
        print("• Higher risk = More gates with higher priority")
        print("• Controls reduce risk score and gate requirements")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()