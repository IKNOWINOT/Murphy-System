#!/usr/bin/env python3
"""
Integration Test Framework
Provides utilities for testing automation workflows
"""

import os
import json
import time
import psycopg2
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'automation_platform')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# n8n configuration
N8N_HOST = os.getenv('N8N_HOST', 'localhost')
N8N_PORT = os.getenv('N8N_PORT', '5678')
N8N_BASE_URL = f'http://{N8N_HOST}:{N8N_PORT}'

class TestResult:
    """Test result container"""
    def __init__(self, test_name: str, passed: bool, message: str, duration: float, details: Optional[Dict] = None):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.duration = duration
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()

class TestFramework:
    """Integration test framework"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.db_conn = None
        
    def connect_db(self):
        """Connect to database"""
        try:
            self.db_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def close_db(self):
        """Close database connection"""
        if self.db_conn:
            self.db_conn.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[tuple]:
        """Execute database query"""
        cursor = self.db_conn.cursor()
        try:
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                self.db_conn.commit()
                return []
        except Exception as e:
            self.db_conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def call_webhook(self, path: str, data: Dict, method: str = 'POST') -> Dict:
        """Call n8n webhook"""
        url = f"{N8N_BASE_URL}/webhook/{path}"
        try:
            if method == 'POST':
                response = requests.post(url, json=data, timeout=30)
            elif method == 'GET':
                response = requests.get(url, params=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return {
                'status_code': response.status_code,
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                'success': response.status_code in [200, 201]
            }
        except Exception as e:
            return {
                'status_code': 0,
                'data': str(e),
                'success': False
            }
    
    def wait_for_processing(self, table: str, condition: str, max_wait: int = 30) -> bool:
        """Wait for database record to be processed"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            result = self.execute_query(f"SELECT COUNT(*) FROM {table} WHERE {condition}")
            if result and result[0][0] > 0:
                return True
            time.sleep(1)
        return False
    
    def run_test(self, test_name: str, test_func, *args, **kwargs) -> TestResult:
        """Run a single test"""
        print(f"\n🧪 Running: {test_name}")
        start_time = time.time()
        
        try:
            result = test_func(*args, **kwargs)
            duration = time.time() - start_time
            
            if isinstance(result, dict):
                passed = result.get('passed', False)
                message = result.get('message', 'Test completed')
                details = result.get('details', {})
            else:
                passed = bool(result)
                message = 'Test passed' if passed else 'Test failed'
                details = {}
            
            test_result = TestResult(test_name, passed, message, duration, details)
            self.results.append(test_result)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {test_name} ({duration:.2f}s)")
            if message:
                print(f"   {message}")
            
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            test_result = TestResult(test_name, False, f"Exception: {str(e)}", duration)
            self.results.append(test_result)
            print(f"❌ FAIL - {test_name} ({duration:.2f}s)")
            print(f"   Exception: {str(e)}")
            return test_result
    
    def generate_report(self) -> Dict:
        """Generate test report"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration for r in self.results)
        
        return {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_duration': total_duration
            },
            'results': [
                {
                    'test_name': r.test_name,
                    'passed': r.passed,
                    'message': r.message,
                    'duration': r.duration,
                    'timestamp': r.timestamp,
                    'details': r.details
                }
                for r in self.results
            ]
        }
    
    def print_summary(self):
        """Print test summary"""
        report = self.generate_report()
        summary = report['summary']
        
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        print(f"Total Tests:    {summary['total_tests']}")
        print(f"Passed:         {summary['passed']} ✅")
        print(f"Failed:         {summary['failed']} ❌")
        print(f"Pass Rate:      {summary['pass_rate']:.1f}%")
        print(f"Total Duration: {summary['total_duration']:.2f}s")
        print("="*70)
        
        if summary['failed'] > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"   - {result.test_name}: {result.message}")
        
        print()
    
    def save_report(self, filename: str):
        """Save test report to file"""
        report = self.generate_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Test report saved to: {filename}")

# Test data generators
class TestDataGenerator:
    """Generate test data for workflows"""
    
    @staticmethod
    def generate_lead(client_id: int = 1, **kwargs) -> Dict:
        """Generate test lead data"""
        timestamp = int(time.time())
        return {
            'client_id': client_id,
            'email': kwargs.get('email', f'test{timestamp}@example.com'),
            'first_name': kwargs.get('first_name', 'Test'),
            'last_name': kwargs.get('last_name', 'User'),
            'company': kwargs.get('company', 'Test Company'),
            'phone': kwargs.get('phone', '+1234567890'),
            'source': kwargs.get('source', 'test'),
            'metadata': kwargs.get('metadata', {})
        }
    
    @staticmethod
    def generate_document(client_id: int = 1, **kwargs) -> Dict:
        """Generate test document data"""
        timestamp = int(time.time())
        return {
            'client_id': client_id,
            'filename': kwargs.get('filename', f'test_doc_{timestamp}.pdf'),
            'file_type': kwargs.get('file_type', 'application/pdf'),
            'file_size': kwargs.get('file_size', 1024),
            'source': kwargs.get('source', 'test'),
            'metadata': kwargs.get('metadata', {})
        }
    
    @staticmethod
    def generate_task(client_id: int = 1, **kwargs) -> Dict:
        """Generate test task data"""
        return {
            'client_id': client_id,
            'title': kwargs.get('title', 'Test Task'),
            'description': kwargs.get('description', 'Test task description'),
            'priority': kwargs.get('priority', 'medium'),
            'category': kwargs.get('category', 'general'),
            'due_date': kwargs.get('due_date', None),
            'metadata': kwargs.get('metadata', {})
        }
    
    @staticmethod
    def generate_error(client_id: int = 1, **kwargs) -> Dict:
        """Generate test error data"""
        return {
            'client_id': client_id,
            'workflow_id': kwargs.get('workflow_id', 'TEST_WORKFLOW'),
            'error_type': kwargs.get('error_type', 'TestError'),
            'error_message': kwargs.get('error_message', 'Test error message'),
            'error_severity': kwargs.get('error_severity', 'medium'),
            'error_category': kwargs.get('error_category', 'other'),
            'context': kwargs.get('context', {})
        }

if __name__ == '__main__':
    print("Test Framework Module")
    print("Import this module to use the test framework")