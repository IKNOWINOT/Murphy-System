"""
Test Phase 2: Command Response Integration
"""

import requests
import json
import time

BASE_URL = "http://localhost:3001"

def test_phase2():
    """Test Phase 2 integration"""
    print("\n" + "="*60)
    print("PHASE 2: COMMAND RESPONSE INTEGRATION TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Server is running
    print("\nTest 1: Server Health Check")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running")
            results.append(("Server Health", True))
        else:
            print(f"✗ Server returned status {response.status_code}")
            results.append(("Server Health", False))
    except Exception as e:
        print(f"✗ Server health check failed: {str(e)}")
        results.append(("Server Health", False))
    
    # Test 2: Initialize system
    print("\nTest 2: Initialize System")
    try:
        response = requests.post(f"{BASE_URL}/api/initialize", timeout=10)
        data = response.json()
        
        if data.get('success'):
            print(f"✓ System initialized successfully")
            print(f"  System ID: {data.get('system_id')}")
            print(f"  Agents: {data.get('agents_created')}")
            print(f"  States: {data.get('states_created')}")
            print(f"  Gates: {data.get('gates_created')}")
            results.append(("Initialize System", True))
        else:
            print(f"✗ Initialization failed: {data.get('error')}")
            results.append(("Initialize System", False))
    except Exception as e:
        print(f"✗ Initialization failed: {str(e)}")
        results.append(("Initialize System", False))
    
    # Test 3: Get status (with LLM)
    print("\nTest 3: Get System Status (LLM-Enhanced)")
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=15)
        data = response.json()
        
        if response.status_code == 200:
            print("✓ Status retrieved successfully")
            print(f"  System ID: {data.get('system_id')}")
            print(f"  LLM Enabled: {data.get('llm_enabled')}")
            print(f"  LLM Status: {'Present' if data.get('llm_status') else 'Not present'}")
            print(f"  Metrics: {data.get('metrics')}")
            
            if data.get('llm_status'):
                print(f"  LLM Status Text: {data.get('llm_status')[:100]}...")
            
            results.append(("Get Status", True))
        else:
            print(f"✗ Status request failed: {response.status_code}")
            results.append(("Get Status", False))
    except Exception as e:
        print(f"✗ Status request failed: {str(e)}")
        results.append(("Get Status", False))
    
    # Test 4: Get help (with LLM)
    print("\nTest 4: Get Help (LLM-Enhanced)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/command/help",
            json={'topic': 'state commands'},
            timeout=15
        )
        data = response.json()
        
        if data.get('success'):
            print("✓ Help retrieved successfully")
            print(f"  LLM Generated: {data.get('llm_generated')}")
            print(f"  Topic: {data.get('topic')}")
            
            help_text = data.get('help', '')
            if len(help_text) > 100:
                print(f"  Help Text: {help_text[:200]}...")
            else:
                print(f"  Help Text: {help_text}")
            
            results.append(("Get Help", True))
        else:
            print(f"✗ Help request failed")
            results.append(("Get Help", False))
    except Exception as e:
        print(f"✗ Help request failed: {str(e)}")
        results.append(("Get Help", False))
    
    # Test 5: Get states
    print("\nTest 5: Get States")
    try:
        response = requests.get(f"{BASE_URL}/api/states", timeout=10)
        data = response.json()
        
        if data.get('success'):
            states = data.get('states', [])
            print(f"✓ States retrieved successfully")
            print(f"  Number of states: {len(states)}")
            if states:
                print(f"  First state: {states[0].get('name')}")
            if data.get('insights'):
                print(f"  Insights: {data.get('insights')[:100]}...")
            results.append(("Get States", True))
        else:
            print(f"✗ States request failed")
            results.append(("Get States", False))
    except Exception as e:
        print(f"✗ States request failed: {str(e)}")
        results.append(("Get States", False))
    
    # Test 6: Evolve state (with LLM explanation)
    print("\nTest 6: Evolve State (with LLM Explanation)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/states/state_1/evolve",
            timeout=15
        )
        data = response.json()
        
        if data.get('success'):
            print(f"✓ State evolved successfully")
            print(f"  Children created: {data.get('children_created')}")
            
            if data.get('explanation'):
                explanation = data.get('explanation')
                print(f"  LLM Explanation: {explanation[:200]}...")
            else:
                print("  No LLM explanation (LLM may not be available)")
            
            results.append(("Evolve State", True))
        else:
            print(f"✗ State evolution failed: {data.get('error')}")
            results.append(("Evolve State", False))
    except Exception as e:
        print(f"✗ State evolution failed: {str(e)}")
        results.append(("Evolve State", False))
    
    # Test 7: Get agents (with LLM insights)
    print("\nTest 7: Get Agents (with LLM Insights)")
    try:
        response = requests.get(f"{BASE_URL}/api/agents", timeout=15)
        data = response.json()
        
        if data.get('success'):
            agents = data.get('agents', [])
            print(f"✓ Agents retrieved successfully")
            print(f"  Number of agents: {len(agents)}")
            if agents:
                print(f"  First agent: {agents[0].get('name')} ({agents[0].get('role')})")
            if data.get('insights'):
                insights = data.get('insights')
                print(f"  LLM Insights: {insights[:200]}...")
            
            results.append(("Get Agents", True))
        else:
            print(f"✗ Agents request failed")
            results.append(("Get Agents", False))
    except Exception as e:
        print(f"✗ Agents request failed: {str(e)}")
        results.append(("Get Agents", False))
    
    # Test 8: Get gates
    print("\nTest 8: Get Gates")
    try:
        response = requests.get(f"{BASE_URL}/api/gates", timeout=10)
        data = response.json()
        
        if data.get('success'):
            gates = data.get('gates', [])
            print(f"✓ Gates retrieved successfully")
            print(f"  Number of gates: {len(gates)}")
            if gates:
                print(f"  First gate: {gates[0].get('name')} ({gates[0].get('type')})")
            results.append(("Get Gates", True))
        else:
            print(f"✗ Gates request failed")
            results.append(("Get Gates", False))
    except Exception as e:
        print(f"✗ Gates request failed: {str(e)}")
        results.append(("Get Gates", False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    return passed == total


if __name__ == "__main__":
    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(3)
    
    success = test_phase2()
    exit(0 if success else 1)