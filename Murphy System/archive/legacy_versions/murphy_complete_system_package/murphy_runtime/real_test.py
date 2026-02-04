# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

import requests
import json

print('=' * 60)
print('MURPHY SYSTEM - REAL TEST EXECUTION')
print('=' * 60)

base_url = 'http://localhost:3002'
results = {'passed': 0, 'failed': 0}

# Test 1: System Status
print('\n[TEST 1] System Status')
print('-' * 60)
try:
    response = requests.get(f'{base_url}/api/status', timeout=5)
    data = response.json()
    print(f'Status Code: {response.status_code}')
    print(f'System Status: {data.get("status")}')
    print(f'Initialized: {data.get("initialized")}')
    systems = data.get('systems', {})
    print(f'Total Systems: {len(systems)}')
    print(f'Systems Operational: {sum(1 for v in systems.values() if v)}')
    print(f'Total Commands: {data.get("commands", {}).get("total")}')
    print('✅ PASS')
    results['passed'] += 1
except Exception as e:
    print(f'❌ FAIL: {e}')
    results['failed'] += 1

# Test 2: Health Check
print('\n[TEST 2] Health Check')
print('-' * 60)
try:
    response = requests.get(f'{base_url}/api/monitoring/health', timeout=5)
    print(f'Status Code: {response.status_code}')
    if response.status_code == 500:
        print(f'Error Response: {response.text[:200]}')
        print('❌ FAIL: Health endpoint returning 500')
        results['failed'] += 1
    else:
        data = response.json()
        print(f'Overall Health: {data.get("status")}')
        print('✅ PASS')
        results['passed'] += 1
except Exception as e:
    print(f'❌ FAIL: {e}')
    results['failed'] += 1

# Test 3: LLM Generation
print('\n[TEST 3] LLM Text Generation')
print('-' * 60)
try:
    response = requests.post(
        f'{base_url}/api/llm/generate',
        json={'prompt': 'Write a one-sentence test message.', 'max_tokens': 50},
        timeout=30
    )
    data = response.json()
    print(f'Status Code: {response.status_code}')
    success = data.get('success')
    print(f'Success: {success}')
    if 'response' in data:
        print(f'Generated Text: {data["response"]}')
        print('✅ PASS')
        results['passed'] += 1
    else:
        print(f'Full Response: {data}')
        print('❌ FAIL: No response field')
        results['failed'] += 1
except Exception as e:
    print(f'❌ FAIL: {e}')
    results['failed'] += 1

# Test 4: Librarian Ask
print('\n[TEST 4] Librarian Query')
print('-' * 60)
try:
    response = requests.post(
        f'{base_url}/api/librarian/ask',
        json={'query': 'What is Murphy?'},
        timeout=30
    )
    data = response.json()
    print(f'Status Code: {response.status_code}')
    success = data.get('success')
    print(f'Success: {success}')
    if response.status_code == 500:
        print(f'Error: {data.get("error")}')
        print('❌ FAIL')
        results['failed'] += 1
    elif success and 'response' in data:
        resp = data['response']
        if isinstance(resp, dict) and 'message' in resp:
            print(f'Message: {resp["message"]}')
        print('✅ PASS')
        results['passed'] += 1
    else:
        print(f'Response: {data}')
        print('❌ FAIL')
        results['failed'] += 1
except Exception as e:
    print(f'❌ FAIL: {e}')
    results['failed'] += 1

# Test 5: Command Execution
print('\n[TEST 5] Command Execution')
print('-' * 60)
try:
    response = requests.post(
        f'{base_url}/api/command/execute',
        json={'command': 'list_commands', 'params': {}},
        timeout=10
    )
    data = response.json()
    print(f'Status Code: {response.status_code}')
    success = data.get('success')
    print(f'Success: {success}')
    if success:
        result = data.get('result', {})
        print(f'Commands Found: {result.get("total", 0)}')
        print('✅ PASS')
        results['passed'] += 1
    else:
        print(f'Error: {data.get("error")}')
        print('❌ FAIL')
        results['failed'] += 1
except Exception as e:
    print(f'❌ FAIL: {e}')
    results['failed'] += 1

print('\n' + '=' * 60)
print('TEST EXECUTION COMPLETE')
print(f'PASSED: {results["passed"]}/5')
print(f'FAILED: {results["failed"]}/5')
print('=' * 60)