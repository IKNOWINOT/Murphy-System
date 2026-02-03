#!/usr/bin/env python3
"""
Test UI Backend Communication
Verifies all endpoints the UI needs are working correctly
"""

import requests
import json
import time

BASE_URL = "http://localhost:3002"

def test_endpoint(method, endpoint, data=None, description=""):
    """Test a single endpoint"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Method: {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS")
            try:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)[:200]}...")
            except:
                print(f"Response: {response.text[:200]}...")
            return True
        else:
            print(f"❌ FAILED - Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def main():
    print("="*60)
    print("MURPHY UI BACKEND COMMUNICATION TEST")
    print("="*60)
    
    tests = [
        # System Status
        ("GET", "/api/status", None, "System Status Check"),
        
        # Health Check
        ("GET", "/api/monitoring/health", None, "Health Monitoring"),
        
        # Initialize System
        ("POST", "/api/initialize", {
            "user_name": "Test User",
            "business_type": "Testing",
            "goal": "Verify Communication"
        }, "System Initialization"),
        
        # LLM Generation
        ("POST", "/api/llm/generate", {
            "prompt": "Hello, this is a test message",
            "user_context": {
                "name": "Test User",
                "business_type": "Testing",
                "goal": "Verify Communication"
            }
        }, "LLM Text Generation"),
        
        # Command Execution
        ("POST", "/api/command/execute", {
            "command": "system_status",
            "args": {}
        }, "Command Execution"),
        
        # Librarian Query
        ("POST", "/api/librarian/ask", {
            "question": "What can Murphy do?",
            "context": {}
        }, "Librarian Knowledge Query"),
    ]
    
    results = []
    for test in tests:
        result = test_endpoint(*test)
        results.append(result)
        time.sleep(0.5)  # Small delay between tests
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - UI Backend Communication Working!")
    else:
        print(f"\n⚠️  {total-passed} tests failed - Check backend configuration")
    
    print("\n" + "="*60)
    print("ENDPOINTS USED BY UI:")
    print("="*60)
    print("✓ GET  /api/status              - System status")
    print("✓ GET  /api/monitoring/health   - Health check")
    print("✓ POST /api/initialize          - User onboarding")
    print("✓ POST /api/llm/generate        - AI text generation")
    print("✓ POST /api/command/execute     - Command execution")
    print("✓ POST /api/librarian/ask       - Knowledge queries")
    print("\n✓ Socket.IO on port 3002        - Real-time updates")
    print("="*60)

if __name__ == "__main__":
    main()