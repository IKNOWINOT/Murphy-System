"""
Comprehensive Test Suite for Murphy System Naming Convention Fixes
Tests individual modules, integration points, and end-to-end workflows
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from domain_engine import DomainEngine, Domain, DomainType

class TestNamingConventions:
    """Test suite for naming convention fixes"""
    
    def __init__(self):
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            status = "✓ PASS"
        else:
            self.failed_tests += 1
            status = "✗ FAIL"
        
        self.test_results.append({
            'test': test_name,
            'status': status,
            'details': details
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"  → {details}")
    
    def test_domain_engine_basic(self):
        """Test DomainEngine basic functionality"""
        print("\n=== Testing DomainEngine Basic ===")
        
        engine = DomainEngine()
        
        # Test 1: Domains initialized
        self.log_test(
            "DomainEngine initialized with domains",
            len(engine.domains) > 0,
            f"Found {len(engine.domains)} domains"
        )
        
        # Test 2: All 9 standard domains present
        expected_domains = ['business', 'engineering', 'financial', 'legal', 
                           'operations', 'marketing', 'hr', 'sales', 'product']
        for domain_name in expected_domains:
            self.log_test(
                f"Domain '{domain_name}' exists",
                domain_name in engine.domains,
                f"Domain object present"
            )
        
        # Test 3: Domain objects have required attributes
        if 'engineering' in engine.domains:
            eng_domain = engine.domains['engineering']
            required_attrs = ['name', 'domain_type', 'purpose', 'sub_domains', 
                            'key_questions', 'constraints', 'gates']
            for attr in required_attrs:
                self.log_test(
                    f"Domain has attribute '{attr}'",
                    hasattr(eng_domain, attr),
                    f"Attribute present in Domain object"
                )
        
        # Test 4: Domain.to_dict() works
        if 'engineering' in engine.domains:
            eng_dict = engine.domains['engineering'].to_dict()
            self.log_test(
                "Domain.to_dict() returns correct structure",
                isinstance(eng_dict, dict) and 'name' in eng_dict,
                f"Keys: {list(eng_dict.keys())[:5]}..."
            )
    
    def test_domain_engine_analysis(self):
        """Test DomainEngine analysis methods"""
        print("\n=== Testing DomainEngine Analysis ===")
        
        engine = DomainEngine()
        
        # Test 1: analyze_request returns proper structure
        test_request = "Build a new cloud infrastructure system with budget constraints and security requirements"
        analysis = engine.analyze_request(test_request)
        
        self.log_test(
            "analyze_request() returns proper structure",
            'matched_domains' in analysis and 'coverage' in analysis,
            f"Found {len(analysis.get('matched_domains', {}))} matched domains"
        )
        
        # Test 2: Returns list of domain names (strings)
        if 'matched_domains' in analysis:
            domain_names = list(analysis['matched_domains'].keys())
            self.log_test(
                "Domain names are strings",
                all(isinstance(name, str) for name in domain_names),
                f"Sample domains: {domain_names[:3]}"
            )
        
        # Test 3: DomainEngine has cross-impact matrix
        has_matrix = hasattr(engine, 'cross_impact_matrix') and engine.cross_impact_matrix is not None
        self.log_test(
            "DomainEngine has cross-impact matrix",
            has_matrix,
            "Cross-impact matrix available"
        )
    
    def test_living_document_class(self):
        """Test LivingDocument class with naming fixes"""
        print("\n=== Testing LivingDocument Class ===")
        
        # Import from backend
        sys.path.insert(0, os.path.dirname(__file__))
        from murphy_complete_backend import LivingDocument
        
        # Test 1: LivingDocument initialization
        doc = LivingDocument("DOC-1", "Test Doc", "Test content", "general")
        self.log_test(
            "LivingDocument initializes correctly",
            doc.doc_id == "DOC-1" and doc.expertise_depth == 0,
            "Document created with expertise_depth = 0"
        )
        
        # Test 2: expertise_depth attribute (not domain_depth)
        self.log_test(
            "LivingDocument has expertise_depth attribute",
            hasattr(doc, 'expertise_depth') and not hasattr(doc, 'domain_depth'),
            "Naming convention: expertise_depth (not domain_depth)"
        )
        
        # Test 3: magnify() method with domain_name parameter
        result = doc.magnify("engineering")
        self.log_test(
            "magnify() accepts domain_name parameter",
            'domain_name' in result.get('history', [{}])[-1] if result['history'] else False,
            f"History: {result['history'][-1] if result['history'] else 'N/A'}"
        )
        
        # Test 4: magnify() increases expertise_depth
        initial_depth = doc.expertise_depth
        doc.magnify("engineering")
        self.log_test(
            "magnify() increases expertise_depth",
            doc.expertise_depth > initial_depth,
            f"Depth: {initial_depth} → {doc.expertise_depth}"
        )
        
        # Test 5: to_dict() returns expertise_depth
        doc_dict = doc.to_dict()
        self.log_test(
            "to_dict() includes expertise_depth",
            'expertise_depth' in doc_dict and 'domain_depth' not in doc_dict,
            f"Dict keys: {list(doc_dict.keys())}"
        )
        
        # Test 6: history uses domain_name
        if doc_dict.get('history'):
            last_action = doc_dict['history'][-1]
            self.log_test(
                "History uses domain_name (not domain)",
                'domain_name' in last_action and 'domain' not in last_action,
                f"History entry: {last_action}"
            )
    
    def test_runtime_methods(self):
        """Test MurphySystemRuntime methods with naming fixes"""
        print("\n=== Testing Runtime Methods ===")
        
        sys.path.insert(0, os.path.dirname(__file__))
        from murphy_complete_backend import MurphySystemRuntime
        
        runtime = MurphySystemRuntime()
        
        # Test 1: DomainEngine integration
        self.log_test(
            "Runtime has DomainEngine",
            runtime.domain_engine is not None,
            "DomainEngine available in runtime"
        )
        
        # Test 2: Create living document
        doc = runtime.create_living_document(
            "Test Document",
            "This is a comprehensive technical document for engineering and financial planning with budget constraints and system architecture requirements",
            "general"
        )
        self.log_test(
            "create_living_document() works",
            doc.doc_id in runtime.living_documents,
            f"Created: {doc.doc_id}"
        )
        
        # Test 3: Document has expertise_depth
        doc_dict = doc.to_dict()
        self.log_test(
            "Document has expertise_depth attribute",
            'expertise_depth' in doc_dict,
            f"Expertise depth: {doc_dict['expertise_depth']}"
        )
        
        # Test 4: Solidify document for prompt generation
        doc.solidify()
        self.log_test(
            "Document can be solidified",
            doc.state == "SOLIDIFIED",
            "State: SOLIDIFIED"
        )
        
        # Test 5: generate_prompts_from_document() uses domain_names
        import asyncio
        async def test_prompts():
            prompts = await runtime.generate_prompts_from_document(doc.doc_id)
            return prompts
        
        prompts = asyncio.run(test_prompts())
        self.log_test(
            "generate_prompts_from_document() returns domain-specific prompts",
            len(prompts) > 1 and 'master' in prompts,
            f"Generated prompts for: {list(prompts.keys())}"
        )
        
        # Test 6: assign_swarm_tasks() uses domain_name and domain_object
        tasks = runtime.assign_swarm_tasks(prompts)
        if tasks:
            first_task = tasks[0]
            has_domain_name = 'domain_name' in first_task
            has_domain_object = 'domain_object' in first_task
            has_old_domain = 'domain' in first_task and 'domain_name' not in first_task
            
            self.log_test(
                "Tasks use domain_name parameter",
                has_domain_name,
                f"Task structure keys: {list(first_task.keys())[:5]}"
            )
            
            self.log_test(
                "Tasks include domain_object",
                has_domain_object and first_task['domain_object'] is not None,
                "Domain object included in task"
            )
            
            self.log_test(
                "Tasks do not use old 'domain' naming",
                not has_old_domain,
                "No name collisions with 'domain' key"
            )
        
        # Test 7: generate_domain_gates() uses domain_name and domain_object
        if prompts:
            for domain_name in prompts.keys():
                if domain_name == 'master':
                    continue
                gates = runtime.generate_domain_gates(domain_name)
                if gates:
                    first_gate = gates[0]
                    has_domain_name = 'domain_name' in first_gate
                    has_domain_object = 'domain_object' in first_gate
                    
                    self.log_test(
                        f"Gates for '{domain_name}' use domain_name",
                        has_domain_name,
                        f"Gate domain_name: {first_gate.get('domain_name')}"
                    )
                    
                    self.log_test(
                        f"Gates include domain_object",
                        has_domain_object,
                        "Domain object included in gate"
                    )
                    break
    
    def test_api_endpoints(self):
        """Test API endpoints with proper naming"""
        print("\n=== Testing API Endpoints ===")
        
        # Import Flask app
        sys.path.insert(0, os.path.dirname(__file__))
        from murphy_complete_backend import app, MurphySystemRuntime
        
        # Create test client
        with app.test_client() as client:
            # Test 1: Create document endpoint
            response = client.post('/api/documents', json={
                'title': 'Test Document',
                'content': 'Test content for API testing',
                'type': 'general'
            })
            self.log_test(
                "POST /api/documents works",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            if response.status_code == 200:
                data = response.get_json()
                doc_id = data.get('doc_id')
                
                # Test 2: Magnify endpoint with domain_name parameter
                response = client.post(f'/api/documents/{doc_id}/magnify', json={
                    'domain_name': 'engineering'
                })
                self.log_test(
                    "POST /api/documents/{id}/magnify accepts domain_name",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    result = response.get_json()
                    self.log_test(
                        "Magnify returns expertise_depth",
                        'expertise_depth' in result,
                        f"Expertise depth: {result.get('expertise_depth')}"
                    )
                
                # Test 3: Backward compatibility with 'domain' parameter
                response = client.post(f'/api/documents/{doc_id}/magnify', json={
                    'domain': 'engineering'
                })
                self.log_test(
                    "POST /api/documents/{id}/magnify accepts old 'domain' parameter",
                    response.status_code == 200,
                    "Backward compatibility maintained"
                )
                
                # Test 4: Invalid domain validation
                response = client.post(f'/api/documents/{doc_id}/magnify', json={
                    'domain_name': 'invalid_domain_xyz'
                })
                self.log_test(
                    "Invalid domain returns error",
                    response.status_code == 400 or response.status_code == 404,
                    f"Status: {response.status_code} (validation working)"
                )
                
                # Test 5: Simplify endpoint
                response = client.post(f'/api/documents/{doc_id}/simplify')
                self.log_test(
                    "POST /api/documents/{id}/simplify works",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    result = response.get_json()
                    self.log_test(
                        "Simplify returns expertise_depth",
                        'expertise_depth' in result,
                        f"Expertise depth: {result.get('expertise_depth')}"
                    )
                
                # Test 6: Solidify endpoint
                response = client.post(f'/api/documents/{doc_id}/solidify')
                self.log_test(
                    "POST /api/documents/{id}/solidify works",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                # Test 7: Get domains endpoint
                response = client.get('/api/domains')
                self.log_test(
                    "GET /api/domains works",
                    response.status_code == 200,
                    f"Status: {response.status_code}"
                )
                
                if response.status_code == 200:
                    data = response.get_json()
                    self.log_test(
                        "Domains endpoint returns domain list",
                        'domains' in data or isinstance(data, list),
                        f"Found {len(data.get('domains', data))} domains"
                    )
    
    def test_domain_integration(self):
        """Test DomainEngine integration across modules"""
        print("\n=== Testing DomainEngine Integration ===")
        
        sys.path.insert(0, os.path.dirname(__file__))
        from murphy_complete_backend import MurphySystemRuntime
        
        runtime = MurphySystemRuntime()
        
        # Test 1: Runtime can access DomainEngine
        self.log_test(
            "Runtime can access DomainEngine",
            runtime.domain_engine is not None,
            "DomainEngine integrated in runtime"
        )
        
        # Test 2: DomainEngine has all standard domains
        if runtime.domain_engine:
            standard_domains = ['business', 'engineering', 'financial', 'legal', 
                               'operations', 'marketing', 'hr', 'sales', 'product']
            all_present = all(d in runtime.domain_engine.domains for d in standard_domains)
            self.log_test(
                "All 9 standard domains available",
                all_present,
                f"Domains: {list(runtime.domain_engine.domains.keys())}"
            )
        
        # Test 3: Can retrieve Domain object by name
        if runtime.domain_engine:
            eng_domain = runtime.domain_engine.domains.get('engineering')
            self.log_test(
                "Can retrieve Domain object by name",
                eng_domain is not None and isinstance(eng_domain, Domain),
                f"Domain type: {type(eng_domain).__name__}"
            )
        
        # Test 4: Domain objects have gates
        if runtime.domain_engine and eng_domain:
            has_gates = hasattr(eng_domain, 'gates') and len(eng_domain.gates) > 0
            self.log_test(
                "Domain objects have gates defined",
                has_gates,
                f"Gates: {eng_domain.gates[:3]}"
            )
        
        # Test 5: Domain.to_dict() serializes correctly
        if runtime.domain_engine and eng_domain:
            domain_dict = eng_domain.to_dict()
            has_required = all(k in domain_dict for k in ['name', 'type', 'purpose', 'gates'])
            self.log_test(
                "Domain.to_dict() serializes correctly",
                has_required,
                f"Dict keys: {list(domain_dict.keys())}"
            )
    
    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 70)
        print("MURPHY SYSTEM NAMING CONVENTION FIXES - COMPREHENSIVE TEST SUITE")
        print("=" * 70)
        
        try:
            self.test_domain_engine_basic()
        except Exception as e:
            print(f"\n✗ DomainEngine Basic Tests FAILED: {e}")
        
        try:
            self.test_domain_engine_analysis()
        except Exception as e:
            print(f"\n✗ DomainEngine Analysis Tests FAILED: {e}")
        
        try:
            self.test_living_document_class()
        except Exception as e:
            print(f"\n✗ LivingDocument Class Tests FAILED: {e}")
        
        try:
            self.test_runtime_methods()
        except Exception as e:
            print(f"\n✗ Runtime Methods Tests FAILED: {e}")
        
        try:
            self.test_api_endpoints()
        except Exception as e:
            print(f"\n✗ API Endpoints Tests FAILED: {e}")
        
        try:
            self.test_domain_integration()
        except Exception as e:
            print(f"\n✗ Domain Integration Tests FAILED: {e}")
        
        # Print summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests} ✓")
        print(f"Failed: {self.failed_tests} ✗")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        print("=" * 70)
        
        # Print failed tests
        if self.failed_tests > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if "FAIL" in result['status']:
                    print(f"  ✗ {result['test']}")
                    if result['details']:
                        print(f"    {result['details']}")
        
        return self.failed_tests == 0

if __name__ == "__main__":
    tester = TestNamingConventions()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)