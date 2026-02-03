#!/usr/bin/env python3
"""
Systematic UI Testing - Test EVERY function from user perspective
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:3002"

class UITester:
    def __init__(self):
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
        self.test_count = 0
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def test(self, name, func):
        """Run a single test"""
        self.test_count += 1
        self.log(f"Test {self.test_count}: {name}", "TEST")
        try:
            result = func()
            if result:
                self.results["passed"].append(name)
                self.log(f"✅ PASSED: {name}", "PASS")
                return True
            else:
                self.results["failed"].append(name)
                self.log(f"❌ FAILED: {name}", "FAIL")
                return False
        except Exception as e:
            self.results["failed"].append(f"{name}: {str(e)}")
            self.log(f"❌ ERROR: {name} - {str(e)}", "ERROR")
            return False
    
    def api_call(self, method, endpoint, data=None, expected_status=200):
        """Make API call and verify response"""
        url = f"{BASE_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, timeout=10)
            
            if response.status_code != expected_status:
                self.log(f"Expected {expected_status}, got {response.status_code}", "WARN")
                return None
            
            try:
                return response.json()
            except:
                return response.text
        except Exception as e:
            self.log(f"API call failed: {str(e)}", "ERROR")
            return None

def main():
    tester = UITester()
    
    print("="*80)
    print("MURPHY UI SYSTEMATIC TESTING")
    print("Testing EVERY function from user perspective")
    print("="*80)
    print()
    
    # ============================================================================
    # PHASE 1: BACKEND AVAILABILITY
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 1: BACKEND AVAILABILITY")
    print("="*80)
    
    tester.test("Backend is running", lambda: tester.api_call("GET", "/api/status") is not None)
    
    # ============================================================================
    # PHASE 2: SYSTEM STATUS & INITIALIZATION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 2: SYSTEM STATUS & INITIALIZATION")
    print("="*80)
    
    def test_system_status():
        data = tester.api_call("GET", "/api/status")
        if not data:
            return False
        return "systems" in data and "commands" in data
    
    tester.test("Get system status", test_system_status)
    
    def test_health_check():
        data = tester.api_call("GET", "/api/monitoring/health")
        return data is not None
    
    tester.test("Health check endpoint", test_health_check)
    
    def test_initialization():
        data = tester.api_call("POST", "/api/initialize", {
            "name": "Test User",
            "business_type": "Testing",
            "goal": "Systematic Testing"
        })
        return data is not None
    
    tester.test("Initialize system with user data", test_initialization)
    
    # ============================================================================
    # PHASE 3: LLM & TEXT GENERATION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 3: LLM & TEXT GENERATION")
    print("="*80)
    
    def test_llm_generate():
        data = tester.api_call("POST", "/api/llm/generate", {
            "prompt": "Hello, this is a test message",
            "user_context": {"name": "Test User"}
        })
        if not data:
            return False
        return "response" in data or "text" in data
    
    tester.test("LLM text generation", test_llm_generate)
    
    def test_llm_status():
        data = tester.api_call("GET", "/api/llm/status")
        return data is not None and "providers" in data
    
    tester.test("LLM status and key rotation", test_llm_status)
    
    # ============================================================================
    # PHASE 4: COMMAND EXECUTION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 4: COMMAND EXECUTION")
    print("="*80)
    
    def test_command_help():
        data = tester.api_call("POST", "/api/command/execute", {
            "command": "help",
            "args": {}
        })
        return data is not None
    
    tester.test("Execute help command", test_command_help)
    
    def test_command_status():
        data = tester.api_call("POST", "/api/command/execute", {
            "command": "status",
            "args": {}
        })
        return data is not None
    
    tester.test("Execute status command", test_command_status)
    
    # ============================================================================
    # PHASE 5: LIBRARIAN & KNOWLEDGE
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 5: LIBRARIAN & KNOWLEDGE")
    print("="*80)
    
    def test_librarian_ask():
        data = tester.api_call("POST", "/api/librarian/ask", {
            "question": "What can Murphy do?",
            "context": {}
        })
        return data is not None and "response" in data
    
    tester.test("Librarian knowledge query", test_librarian_ask)
    
    def test_librarian_commands():
        data = tester.api_call("GET", "/api/librarian/search-commands?query=help")
        return data is not None
    
    tester.test("Search commands in Librarian", test_librarian_commands)
    
    # ============================================================================
    # PHASE 6: ARTIFACTS & GENERATION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 6: ARTIFACTS & GENERATION")
    print("="*80)
    
    def test_artifact_generate():
        data = tester.api_call("POST", "/api/artifacts/generate", {
            "type": "document",
            "content": "Test document content",
            "metadata": {"title": "Test Document"}
        })
        return data is not None
    
    tester.test("Generate artifact", test_artifact_generate)
    
    def test_artifact_list():
        data = tester.api_call("GET", "/api/artifacts")
        return data is not None
    
    tester.test("List all artifacts", test_artifact_list)
    
    # ============================================================================
    # PHASE 7: SWARM & MULTI-AGENT
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 7: SWARM & MULTI-AGENT")
    print("="*80)
    
    def test_swarm_create():
        data = tester.api_call("POST", "/api/swarm/task/create", {
            "task": "Test task",
            "agents": ["agent1", "agent2"]
        })
        return data is not None
    
    tester.test("Create swarm task", test_swarm_create)
    
    def test_swarm_list():
        data = tester.api_call("GET", "/api/swarm/tasks")
        return data is not None
    
    tester.test("List swarm tasks", test_swarm_list)
    
    # ============================================================================
    # PHASE 8: WORKFLOW ORCHESTRATION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 8: WORKFLOW ORCHESTRATION")
    print("="*80)
    
    def test_workflow_create():
        data = tester.api_call("POST", "/api/workflow/create", {
            "name": "Test Workflow",
            "steps": [
                {"action": "step1", "params": {}},
                {"action": "step2", "params": {}}
            ]
        })
        return data is not None
    
    tester.test("Create workflow", test_workflow_create)
    
    # ============================================================================
    # PHASE 9: GATES & DECISION MAKING
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 9: GATES & DECISION MAKING")
    print("="*80)
    
    def test_gates_generate():
        data = tester.api_call("POST", "/api/gates/generate", {
            "task": {
                "description": "Test task",
                "revenue_potential": 10000,
                "budget": 1000
            }
        })
        return data is not None and "gates" in data
    
    tester.test("Generate decision gates", test_gates_generate)
    
    def test_gates_sensors():
        data = tester.api_call("GET", "/api/gates/sensors/status")
        return data is not None
    
    tester.test("Get gate sensors status", test_gates_sensors)
    
    # ============================================================================
    # PHASE 10: PIPELINE & KNOWLEDGE FLOW
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 10: PIPELINE & KNOWLEDGE FLOW")
    print("="*80)
    
    def test_pipeline_explode():
        data = tester.api_call("POST", "/api/pipeline/explode", {
            "request": "Automate my business"
        })
        return data is not None
    
    tester.test("Explode vague request into plan", test_pipeline_explode)
    
    def test_pipeline_status():
        data = tester.api_call("GET", "/api/pipeline/status")
        return data is not None
    
    tester.test("Get pipeline status", test_pipeline_status)
    
    # ============================================================================
    # PHASE 11: BUSINESS AUTOMATION
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 11: BUSINESS AUTOMATION")
    print("="*80)
    
    def test_business_products():
        data = tester.api_call("GET", "/api/business/products")
        return data is not None
    
    tester.test("List business products", test_business_products)
    
    # ============================================================================
    # PHASE 12: AUTOMATION SCHEDULING
    # ============================================================================
    print("\n" + "="*80)
    print("PHASE 12: AUTOMATION SCHEDULING")
    print("="*80)
    
    def test_automation_list():
        data = tester.api_call("GET", "/api/automation/list")
        return data is not None
    
    tester.test("List scheduled automations", test_automation_list)
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(tester.results["passed"]) + len(tester.results["failed"])
    passed = len(tester.results["passed"])
    failed = len(tester.results["failed"])
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ({(passed/total*100):.1f}%)")
    print(f"Failed: {failed} ({(failed/total*100):.1f}%)")
    
    if tester.results["failed"]:
        print("\n❌ FAILED TESTS:")
        for test in tester.results["failed"]:
            print(f"  - {test}")
    
    if tester.results["passed"]:
        print("\n✅ PASSED TESTS:")
        for test in tester.results["passed"]:
            print(f"  - {test}")
    
    print("\n" + "="*80)
    
    # Save results
    with open("test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed/total*100):.1f}%",
            "results": tester.results
        }, f, indent=2)
    
    print("Results saved to test_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)