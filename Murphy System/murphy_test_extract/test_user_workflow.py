"""
End-to-End User Workflow Test for Murphy System
Tests the complete user experience from document creation to task execution
"""

import requests
import json
import time

class UserWorkflowTest:
    """Simulates a complete user workflow"""
    
    def __init__(self, base_url="http://localhost:6666"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.results = []
        self.doc_id = None
        
    def log(self, test_name, passed, details=""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "status": status, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  → {details}")
    
    def test_1_check_server_health(self):
        """Test 1: Check if server is running"""
        print("\n=== Test 1: Server Health Check ===")
        try:
            response = requests.get(f"{self.base_url}/api/domains", timeout=5)
            self.log(
                "Server is running",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            return True
        except Exception as e:
            self.log("Server is running", False, f"Error: {e}")
            return False
    
    def test_2_get_available_domains(self):
        """Test 2: Get available domains"""
        print("\n=== Test 2: Get Available Domains ===")
        try:
            response = requests.get(f"{self.api_base}/domains")
            data = response.json()
            
            self.log(
                "GET /api/domains returns data",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            domains = data.get('domains', data) if isinstance(data, dict) else data
            
            self.log(
                "All 9 standard domains available",
                len(domains) >= 9,
                f"Found {len(domains)} domains"
            )
            
            # Check domain structure
            if domains:
                first_domain = domains[0] if isinstance(domains, list) else list(domains.values())[0]
                has_required_keys = all(k in first_domain for k in ['name', 'type', 'purpose', 'gates'])
                self.log(
                    "Domains have correct structure",
                    has_required_keys,
                    f"Keys: {list(first_domain.keys())[:5]}"
                )
            
            return True
        except Exception as e:
            self.log("Get available domains", False, f"Error: {e}")
            return False
    
    def test_3_create_living_document(self):
        """Test 3: Create a living document"""
        print("\n=== Test 3: Create Living Document ===")
        try:
            response = requests.post(f"{self.api_base}/documents", json={
                'title': 'Smart Home Automation System',
                'content': 'Design and implement a comprehensive smart home automation system with voice control, energy monitoring, security integration, and mobile app interface. The system should support IoT devices from multiple manufacturers and provide real-time analytics with budget constraints of $50,000.',
                'type': 'technical'
            })
            
            self.log(
                "POST /api/documents creates document",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.doc_id = data.get('doc_id')
            
            if self.doc_id:
                self.log(
                    "Document has doc_id",
                    self.doc_id is not None,
                    f"Doc ID: {self.doc_id}"
                )
                
                self.log(
                    "Document has expertise_depth attribute",
                    'expertise_depth' in data,
                    f"Expertise depth: {data.get('expertise_depth')}"
                )
                
                # Check for old naming (domain_depth should NOT exist)
                self.log(
                    "Document does NOT have domain_depth (old naming)",
                    'domain_depth' not in data,
                    "Old naming convention removed"
                )
            
            return self.doc_id is not None
        except Exception as e:
            self.log("Create living document", False, f"Error: {e}")
            return False
    
    def test_4_magnify_document(self):
        """Test 4: Magnify document with domain expertise"""
        print("\n=== Test 4: Magnify Document ===")
        if not self.doc_id:
            self.log("Magnify document", False, "No document ID available")
            return False
        
        try:
            # Test with new parameter name (domain_name)
            response = requests.post(
                f"{self.api_base}/documents/{self.doc_id}/magnify",
                json={'domain_name': 'engineering'}
            )
            
            self.log(
                "Magnify with domain_name parameter works",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            
            self.log(
                "Magnify increases expertise_depth",
                data.get('expertise_depth', 0) > 0,
                f"Expertise depth: {data.get('expertise_depth')}"
            )
            
            # Test backward compatibility with old parameter name (domain)
            response_old = requests.post(
                f"{self.api_base}/documents/{self.doc_id}/magnify",
                json={'domain': 'financial'}
            )
            
            self.log(
                "Backward compatibility: 'domain' parameter works",
                response_old.status_code == 200,
                f"Status: {response_old.status_code}"
            )
            
            # Test domain validation
            response_invalid = requests.post(
                f"{self.api_base}/documents/{self.doc_id}/magnify",
                json={'domain_name': 'invalid_domain_xyz'}
            )
            
            self.log(
                "Invalid domain returns error (validation working)",
                response_invalid.status_code in [400, 404],
                f"Status: {response_invalid.status_code}"
            )
            
            return True
        except Exception as e:
            self.log("Magnify document", False, f"Error: {e}")
            return False
    
    def test_5_simplify_document(self):
        """Test 5: Simplify document"""
        print("\n=== Test 5: Simplify Document ===")
        if not self.doc_id:
            self.log("Simplify document", False, "No document ID available")
            return False
        
        try:
            response = requests.post(
                f"{self.api_base}/documents/{self.doc_id}/simplify"
            )
            
            self.log(
                "Simplify endpoint works",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            
            self.log(
                "Simplify returns expertise_depth",
                'expertise_depth' in data,
                f"Expertise depth: {data.get('expertise_depth')}"
            )
            
            return True
        except Exception as e:
            self.log("Simplify document", False, f"Error: {e}")
            return False
    
    def test_6_solidify_document(self):
        """Test 6: Solidify document and generate tasks"""
        print("\n=== Test 6: Solidify Document ===")
        if not self.doc_id:
            self.log("Solidify document", False, "No document ID available")
            return False
        
        try:
            response = requests.post(
                f"{self.api_base}/documents/{self.doc_id}/solidify"
            )
            
            self.log(
                "Solidify endpoint works",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            
            self.log(
                "Solidify returns success",
                data.get('success') == True,
                "Success flag present"
            )
            
            # Check prompts
            prompts = data.get('prompts', {})
            self.log(
                "Solidify generates prompts",
                len(prompts) > 0,
                f"Generated {len(prompts)} prompts"
            )
            
            # Check tasks
            tasks = data.get('tasks', [])
            if tasks:
                self.log(
                    "Solidify generates tasks",
                    len(tasks) > 0,
                    f"Generated {len(tasks)} tasks"
                )
                
                # Check task structure
                first_task = tasks[0]
                has_domain_name = 'domain_name' in first_task
                has_domain_object = 'domain_object' in first_task
                has_old_domain = 'domain' in first_task and 'domain_name' not in first_task
                
                self.log(
                    "Tasks use domain_name parameter (new naming)",
                    has_domain_name,
                    f"Task keys: {list(first_task.keys())[:5]}"
                )
                
                self.log(
                    "Tasks include domain_object",
                    has_domain_object and first_task['domain_object'] is not None,
                    "Domain object included in task"
                )
                
                self.log(
                    "Tasks do not use old 'domain' naming",
                    not has_old_domain,
                    "No name collisions"
                )
            
            # Check gates
            gates = data.get('gates', [])
            if gates:
                self.log(
                    "Solidify generates gates",
                    len(gates) > 0,
                    f"Generated {len(gates)} gates"
                )
                
                # Check gate structure
                first_gate = gates[0]
                has_domain_name = 'domain_name' in first_gate
                has_domain_object = 'domain_object' in first_gate
                
                self.log(
                    "Gates use domain_name parameter",
                    has_domain_name,
                    f"Gate domain_name: {first_gate.get('domain_name')}"
                )
                
                self.log(
                    "Gates include domain_object",
                    has_domain_object,
                    "Domain object included in gate"
                )
            
            return True
        except Exception as e:
            self.log("Solidify document", False, f"Error: {e}")
            return False
    
    def test_7_analyze_domain(self):
        """Test 7: Analyze domain coverage"""
        print("\n=== Test 7: Analyze Domain Coverage ===")
        try:
            response = requests.post(
                f"{self.api_base}/analyze-domain",
                json={
                    'request': 'Build a cloud infrastructure system with budget constraints and security requirements'
                }
            )
            
            self.log(
                "POST /api/analyze-domain works",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            
            self.log(
                "Analysis returns matched_domains",
                'matched_domains' in data,
                f"Matched domains: {list(data.get('matched_domains', {}).keys())}"
            )
            
            self.log(
                "Analysis returns coverage score",
                'coverage' in data,
                f"Coverage: {data.get('coverage', 0):.2f}"
            )
            
            return True
        except Exception as e:
            self.log("Analyze domain", False, f"Error: {e}")
            return False
    
    def run_complete_workflow(self):
        """Run complete user workflow test"""
        print("=" * 70)
        print("MURPHY SYSTEM - END-TO-END USER WORKFLOW TEST")
        print("=" * 70)
        print(f"Testing against: {self.base_url}")
        print("=" * 70)
        
        # Run all tests
        self.test_1_check_server_health()
        self.test_2_get_available_domains()
        self.test_3_create_living_document()
        self.test_4_magnify_document()
        self.test_5_simplify_document()
        self.test_6_solidify_document()
        self.test_7_analyze_domain()
        
        # Print summary
        print("\n" + "=" * 70)
        print("WORKFLOW TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if "PASS" in r['status'])
        failed = sum(1 for r in self.results if "FAIL" in r['status'])
        
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {failed} ✗")
        print(f"Success Rate: {(passed/len(self.results)*100):.1f}%")
        print("=" * 70)
        
        if failed > 0:
            print("\nFAILED TESTS:")
            for result in self.results:
                if "FAIL" in result['status']:
                    print(f"  ✗ {result['test']}")
                    if result['details']:
                        print(f"    {result['details']}")
        
        return failed == 0

if __name__ == "__main__":
    tester = UserWorkflowTest()
    success = tester.run_complete_workflow()
    exit(0 if success else 1)