#!/usr/bin/env python3
"""
Run all integration tests
Executes all test suites and generates comprehensive report
"""

import os
import sys
import json
from datetime import datetime

# Import test modules
from test_intake_v1 import run_intake_tests
from test_docs_v1 import run_docs_tests
from test_tasks_v1 import run_tasks_tests
from test_monitoring_v1 import run_monitoring_tests

def create_test_results_dir():
    """Create test results directory"""
    os.makedirs('test_results', exist_ok=True)

def generate_consolidated_report():
    """Generate consolidated test report from all test results"""
    report_files = [
        'test_results/intake_v1_results.json',
        'test_results/docs_v1_results.json',
        'test_results/tasks_v1_results.json',
        'test_results/monitor_v1_results.json'
    ]
    
    consolidated = {
        'test_run_timestamp': datetime.now().isoformat(),
        'test_suites': [],
        'overall_summary': {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'pass_rate': 0,
            'total_duration': 0
        }
    }
    
    for report_file in report_files:
        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                data = json.load(f)
                suite_name = os.path.basename(report_file).replace('_results.json', '')
                
                consolidated['test_suites'].append({
                    'suite_name': suite_name,
                    'summary': data['summary'],
                    'results': data['results']
                })
                
                # Update overall summary
                consolidated['overall_summary']['total_tests'] += data['summary']['total_tests']
                consolidated['overall_summary']['passed'] += data['summary']['passed']
                consolidated['overall_summary']['failed'] += data['summary']['failed']
                consolidated['overall_summary']['total_duration'] += data['summary']['total_duration']
    
    # Calculate overall pass rate
    if consolidated['overall_summary']['total_tests'] > 0:
        consolidated['overall_summary']['pass_rate'] = (
            consolidated['overall_summary']['passed'] / 
            consolidated['overall_summary']['total_tests'] * 100
        )
    
    # Save consolidated report
    with open('test_results/consolidated_report.json', 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    return consolidated

def print_consolidated_summary(report):
    """Print consolidated test summary"""
    print("\n" + "="*70)
    print("📊 CONSOLIDATED TEST SUMMARY")
    print("="*70)
    print(f"Test Run: {report['test_run_timestamp']}")
    print(f"Total Tests:    {report['overall_summary']['total_tests']}")
    print(f"Passed:         {report['overall_summary']['passed']} ✅")
    print(f"Failed:         {report['overall_summary']['failed']} ❌")
    print(f"Pass Rate:      {report['overall_summary']['pass_rate']:.1f}%")
    print(f"Total Duration: {report['overall_summary']['total_duration']:.2f}s")
    print("="*70)
    
    print("\n📦 Test Suite Breakdown:")
    for suite in report['test_suites']:
        summary = suite['summary']
        status = "✅" if summary['failed'] == 0 else "❌"
        print(f"  {status} {suite['suite_name']}: {summary['passed']}/{summary['total_tests']} passed ({summary['pass_rate']:.1f}%)")
    
    if report['overall_summary']['failed'] > 0:
        print("\n❌ Failed Tests:")
        for suite in report['test_suites']:
            for result in suite['results']:
                if not result['passed']:
                    print(f"   - [{suite['suite_name']}] {result['test_name']}: {result['message']}")
    
    print("\n" + "="*70)
    
    if report['overall_summary']['pass_rate'] == 100:
        print("🎉 ALL TESTS PASSED!")
    elif report['overall_summary']['pass_rate'] >= 80:
        print("✅ TESTS MOSTLY PASSED - Some issues to address")
    else:
        print("⚠️  TESTS NEED ATTENTION - Multiple failures detected")
    
    print("="*70 + "\n")

def main():
    """Run all integration tests"""
    print("="*70)
    print("🚀 RUNNING ALL INTEGRATION TESTS")
    print("="*70)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Create test results directory
    create_test_results_dir()
    
    # Run all test suites
    print("\n" + "="*70)
    print("Running Test Suites...")
    print("="*70 + "\n")
    
    try:
        # INTAKE_v1 Tests
        run_intake_tests()
        print("\n")
        
        # DOCS_v1 Tests
        run_docs_tests()
        print("\n")
        
        # TASKS_v1 Tests
        run_tasks_tests()
        print("\n")
        
        # MONITOR_v1 Tests
        run_monitoring_tests()
        print("\n")
        
        # Generate consolidated report
        print("="*70)
        print("Generating Consolidated Report...")
        print("="*70)
        
        report = generate_consolidated_report()
        print_consolidated_summary(report)
        
        print(f"📄 Consolidated report saved to: test_results/consolidated_report.json")
        print(f"📄 Individual reports saved in: test_results/\n")
        
        # Exit with appropriate code
        if report['overall_summary']['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()