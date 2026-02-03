"""
Comprehensive test script for all security fixes
"""

import requests
import json
import time

BASE_URL = "http://localhost:3002"

def print_test(test_name, passed, details=""):
    """Print test result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"  → {details}")

def test_1_authentication_available():
    """Test 1: Authentication system is available"""
    try:
        r = requests.get(f"{BASE_URL}/api/status")
        data = r.json()
        auth_available = data['components'].get('authentication', False)
        print_test("Authentication system available", auth_available)
        return auth_available
    except Exception as e:
        print_test("Authentication system available", False, str(e))
        return False

def test_2_login_works():
    """Test 2: Login endpoint works"""
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login", 
                         json={"username": "admin", "password": "admin123"})
        data = r.json()
        has_token = 'token' in data and data.get('success')
        print_test("Login endpoint works", has_token)
        return data.get('token') if has_token else None
    except Exception as e:
        print_test("Login endpoint works", False, str(e))
        return None

def test_3_protected_endpoints_require_auth(token):
    """Test 3: Protected endpoints require authentication"""
    try:
        # Test without token
        r = requests.post(f"{BASE_URL}/api/initialize")
        unauthorized = r.status_code == 401
        
        # Test with token
        r = requests.post(f"{BASE_URL}/api/initialize",
                        headers={"Authorization": f"Bearer {token}"})
        authorized = r.status_code == 200
        
        passed = unauthorized and authorized
        print_test("Protected endpoints require auth", passed,
                  f"Without token: {r.status_code == 401}, With token: {authorized}")
        return passed
    except Exception as e:
        print_test("Protected endpoints require auth", False, str(e))
        return False

def test_4_invalid_credentials_rejected():
    """Test 4: Invalid credentials are rejected"""
    try:
        r = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"username": "invalid", "password": "wrong"})
        rejected = r.status_code == 401
        print_test("Invalid credentials rejected", rejected)
        return rejected
    except Exception as e:
        print_test("Invalid credentials rejected", False, str(e))
        return False

def test_5_rate_limiting_works():
    """Test 5: Rate limiting works"""
    try:
        # Make 6 rapid login attempts (limit is 5 per minute)
        responses = []
        for i in range(6):
            r = requests.post(f"{BASE_URL}/api/auth/login",
                             json={"username": "admin", "password": "admin123"})
            responses.append(r.status_code)
            time.sleep(0.1)  # Small delay between requests
        
        # First 5 should succeed, 6th should be rate limited
        rate_limited = responses[-1] == 429
        print_test("Rate limiting works", rate_limited,
                  f"Last request status: {responses[-1]} (expected 429)")
        return rate_limited
    except Exception as e:
        print_test("Rate limiting works", False, str(e))
        return False

def test_6_thread_safety():
    """Test 6: Thread safety with locks"""
    # This is a basic check - just verify locks are defined
    try:
        import murphy_backend_complete as backend
        has_locks = all(hasattr(backend, lock) for lock in 
                      ['state_lock', 'agents_lock', 'components_lock', 'gates_lock'])
        print_test("Thread safety locks defined", has_locks)
        return has_locks
    except Exception as e:
        print_test("Thread safety locks defined", False, str(e))
        return False

def test_7_health_monitoring():
    """Test 7: Health monitoring with checks executed"""
    try:
        r = requests.get(f"{BASE_URL}/api/monitoring/health")
        data = r.json()
        health_score = data['health']['overall']['score']
        components = len(data['health']['components'])
        passed = health_score > 0 and components > 0
        print_test("Health monitoring executes checks", passed,
                  f"Score: {health_score}%, Components: {components}")
        return passed
    except Exception as e:
        print_test("Health monitoring executes checks", False, str(e))
        return False

def test_8_socket_global():
    """Test 8: Socket.IO connection is globally accessible"""
    try:
        with open('murphy_complete_v2.html', 'r') as f:
            html = f.read()
        
        import re
        has_global_socket = bool(re.search(r'window\.socket\s*=\s*io\(', html))
        no_local_socket = not bool(re.findall(r'(?<!window\.)\bsocket\.on\(', html))
        passed = has_global_socket and no_local_socket
        
        print_test("Socket.IO globally accessible", passed,
                  f"window.socket found: {has_global_socket}, No local socket.on: {no_local_socket}")
        return passed
    except Exception as e:
        print_test("Socket.IO globally accessible", False, str(e))
        return False

def test_9_write_endpoints_protected():
    """Test 9: All write endpoints are protected"""
    protected_endpoints = [
        ('POST', '/api/initialize'),
        ('POST', '/api/shadow/observe'),
        ('POST', '/api/cooperative/workflows'),
        ('POST', '/api/attention/form'),
    ]
    
    try:
        all_protected = True
        for method, endpoint in protected_endpoints:
            r = requests.request(method, f"{BASE_URL}{endpoint}")
            if r.status_code != 401:
                all_protected = False
                print(f"  ⚠️  {method} {endpoint} returned {r.status_code} (expected 401)")
        
        print_test("All write endpoints protected", all_protected,
                  f"Tested {len(protected_endpoints)} endpoints")
        return all_protected
    except Exception as e:
        print_test("All write endpoints protected", False, str(e))
        return False

def run_all_tests():
    """Run all security tests"""
    print("="*70)
    print("SECURITY FIXES VERIFICATION TESTS")
    print("="*70)
    print()
    
    results = []
    
    # Run tests
    results.append(("Authentication Available", test_1_authentication_available()))
    token = test_2_login_works()
    results.append(("Login Works", bool(token)))
    
    if token:
        results.append(("Protected Endpoints Require Auth", test_3_protected_endpoints_require_auth(token)))
        results.append(("All Write Endpoints Protected", test_9_write_endpoints_protected()))
    else:
        results.append(("Protected Endpoints Require Auth", False))
        results.append(("All Write Endpoints Protected", False))
    
    results.append(("Invalid Credentials Rejected", test_4_invalid_credentials_rejected()))
    results.append(("Rate Limiting Works", test_5_rate_limiting_works()))
    results.append(("Thread Safety Locks Defined", test_6_thread_safety()))
    results.append(("Health Monitoring Executes Checks", test_7_health_monitoring()))
    results.append(("Socket.IO Globally Accessible", test_8_socket_global()))
    
    # Summary
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nTests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {test_name}")
    
    print()
    print("="*70)
    
    if passed == total:
        print("✓✓✓ ALL SECURITY FIXES VERIFIED ✓✓✓")
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
    
    print("="*70)
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)