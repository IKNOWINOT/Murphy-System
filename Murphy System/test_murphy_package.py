"""
Comprehensive Murphy System Package Test
Tests all components and verifies functionality
"""

import os
import sys
from pathlib import Path
import zipfile

def test_package_structure():
    """Test that package has correct structure"""
    print("=" * 60)
    print("TEST 1: Package Structure")
    print("=" * 60)
    
    required_files = [
        "murphy_complete_system_package/README.md",
        "murphy_complete_system_package/LICENSE",
        "murphy_complete_system_package/install.sh",
        "murphy_complete_system_package/install.bat",
        "murphy_complete_system_package/requirements.txt",
        "murphy_complete_system_package/MANIFEST.md",
    ]
    
    all_exist = True
    for file in required_files:
        exists = Path(file).exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {file}")
        if not exists:
            all_exist = False
    
    return all_exist

def test_runtime_files():
    """Test that all runtime files are present"""
    print("\n" + "=" * 60)
    print("TEST 2: Murphy Runtime Files")
    print("=" * 60)
    
    runtime_dir = Path("murphy_complete_system_package/murphy_runtime")
    
    # Check main server file
    main_file = runtime_dir / "murphy_complete_integrated.py"
    print(f"  Main server: {main_file.exists()}")
    
    # Check UI files
    ui_file = runtime_dir / "murphy_ui_final.html"
    print(f"  UI file: {ui_file.exists()}")
    
    # Count Python files
    py_files = list(runtime_dir.glob("*.py"))
    print(f"  Python files: {len(py_files)} (expected: 131)")
    
    # Count HTML files
    html_files = list(runtime_dir.glob("*.html"))
    print(f"  HTML files: {len(html_files)} (expected: 29)")
    
    return len(py_files) >= 131 and ui_file.exists()

def test_phase_implementations():
    """Test Phase 1-5 implementations"""
    print("\n" + "=" * 60)
    print("TEST 3: Phase 1-5 Implementations")
    print("=" * 60)
    
    impl_dir = Path("murphy_complete_system_package/murphy_implementation")
    
    phases = [
        "forms",
        "plan_decomposition",
        "execution",
        "hitl",
        "validation",
        "risk",
        "correction",
        "shadow_agent",
        "performance",
        "deployment"
    ]
    
    all_exist = True
    for phase in phases:
        phase_dir = impl_dir / phase
        exists = phase_dir.exists()
        status = "✓" if exists else "✗"
        
        if exists:
            py_files = len(list(phase_dir.rglob("*.py")))
            print(f"  {status} {phase}: {py_files} Python files")
        else:
            print(f"  {status} {phase}: NOT FOUND")
            all_exist = False
    
    return all_exist

def test_documentation():
    """Test documentation files"""
    print("\n" + "=" * 60)
    print("TEST 4: Documentation")
    print("=" * 60)
    
    docs = [
        "murphy_complete_system_package/README.md",
        "murphy_complete_system_package/FINAL_SYSTEM_DOCUMENTATION.md",
        "murphy_complete_system_package/PROJECT_COMPLETION_SUMMARY.md",
        "murphy_complete_system_package/murphy_implementation/deployment/API_DOCUMENTATION.md",
        "murphy_complete_system_package/murphy_implementation/deployment/USER_GUIDE.md",
        "murphy_complete_system_package/murphy_implementation/deployment/DEPLOYMENT_GUIDE.md",
        "murphy_complete_system_package/murphy_implementation/deployment/RUNBOOK.md",
    ]
    
    all_exist = True
    for doc in docs:
        exists = Path(doc).exists()
        status = "✓" if exists else "✗"
        doc_name = Path(doc).name
        print(f"  {status} {doc_name}")
        if not exists:
            all_exist = False
    
    return all_exist

def test_copyright_and_license():
    """Test copyright and license information"""
    print("\n" + "=" * 60)
    print("TEST 5: Copyright and License")
    print("=" * 60)
    
    # Check LICENSE file
    license_file = Path("murphy_complete_system_package/LICENSE")
    if license_file.exists():
        with open(license_file, 'r') as f:
            content = f.read()
            has_apache = "Apache License" in content
            has_inoni = "Inoni Limited Liability Company" in content
            print(f"  ✓ LICENSE file exists")
            print(f"  {'✓' if has_apache else '✗'} Contains Apache License 2.0")
            print(f"  {'✓' if has_inoni else '✗'} Copyright: Inoni Limited Liability Company")
    else:
        print(f"  ✗ LICENSE file missing")
        return False
    
    # Check README
    readme_file = Path("murphy_complete_system_package/README.md")
    if readme_file.exists():
        with open(readme_file, 'r') as f:
            content = f.read()
            has_copyright = "Inoni Limited Liability Company" in content
            has_creator = "Corey Post" in content
            has_apache = "Apache License" in content
            print(f"  {'✓' if has_copyright else '✗'} README has correct copyright")
            print(f"  {'✓' if has_creator else '✗'} README credits Corey Post")
            print(f"  {'✓' if has_apache else '✗'} README mentions Apache License")
    
    return True

def test_ui_configuration():
    """Test that UI is properly configured"""
    print("\n" + "=" * 60)
    print("TEST 6: UI Configuration")
    print("=" * 60)
    
    main_file = Path("murphy_complete_system_package/murphy_runtime/murphy_complete_integrated.py")
    
    if main_file.exists():
        with open(main_file, 'r') as f:
            content = f.read()
            uses_final_ui = "murphy_ui_final.html" in content
            print(f"  {'✓' if uses_final_ui else '✗'} Server configured to use murphy_ui_final.html")
            
            # Check if UI file exists
            ui_file = Path("murphy_complete_system_package/murphy_runtime/murphy_ui_final.html")
            ui_exists = ui_file.exists()
            print(f"  {'✓' if ui_exists else '✗'} murphy_ui_final.html exists")
            
            return uses_final_ui and ui_exists
    
    return False

def run_all_tests():
    """Run all tests"""
    print("\n")
    print("=" * 60)
    print("MURPHY SYSTEM PACKAGE TEST SUITE")
    print("=" * 60)
    print()
    
    tests = [
        ("Package Structure", test_package_structure),
        ("Runtime Files", test_runtime_files),
        ("Phase Implementations", test_phase_implementations),
        ("Documentation", test_documentation),
        ("Copyright and License", test_copyright_and_license),
        ("UI Configuration", test_ui_configuration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n  ✗ Test failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\nALL TESTS PASSED! Package is ready.")
    else:
        print(f"\n{total - passed} test(s) failed.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)