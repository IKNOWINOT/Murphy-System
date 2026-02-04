#!/usr/bin/env python3
"""
Test script to verify Murphy System startup fixes
Tests that the system can import and initialize without crashing
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all imports work (even if components unavailable)"""
    print("Testing imports...")
    
    try:
        # Import the module by path
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "murphy_system_runtime", 
            Path(__file__).parent / "murphy_system_1.0_runtime.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if key classes are defined (may be None)
        has_ucp = hasattr(module, 'UniversalControlPlane')
        has_iba = hasattr(module, 'InoniBusinessAutomation')
        has_uie = hasattr(module, 'UnifiedIntegrationEngine')
        has_tpo = hasattr(module, 'TwoPhaseOrchestrator')
        
        print("✅ Module loaded successfully")
        print(f"   UniversalControlPlane: {'available' if has_ucp else 'not defined'}")
        print(f"   InoniBusinessAutomation: {'available' if has_iba else 'not defined'}")
        print(f"   UnifiedIntegrationEngine: {'available' if has_uie else 'not defined'}")
        print(f"   TwoPhaseOrchestrator: {'available' if has_tpo else 'not defined'}")
        return True
    except Exception as e:
        print(f"❌ Import failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_core_dependencies():
    """Test that core dependencies are available"""
    print("\nTesting core dependencies...")
    
    deps = {
        'fastapi': 'FastAPI web framework',
        'uvicorn': 'ASGI server',
        'pydantic': 'Data validation',
        'aiohttp': 'Async HTTP client',
        'httpx': 'HTTP client',
    }
    
    missing = []
    for dep, description in deps.items():
        try:
            __import__(dep)
            print(f"  ✅ {dep:15} - {description}")
        except ImportError:
            print(f"  ❌ {dep:15} - {description} (MISSING)")
            missing.append(dep)
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
        return False
    else:
        print("\n✅ All core dependencies available")
        return True

def test_murphy_system_class():
    """Test that MurphySystem class can be imported"""
    print("\nTesting MurphySystem class...")
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "murphy_system_runtime", 
            Path(__file__).parent / "murphy_system_1.0_runtime.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, 'MurphySystem'):
            print("✅ MurphySystem class found in module")
            print("   Note: Initialization may fail if dependencies missing")
            return True
        else:
            print("❌ MurphySystem class not found in module")
            return False
    except Exception as e:
        print(f"❌ Failed to load module: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_requirements_file():
    """Test that requirements file doesn't have python>=3.11"""
    print("\nTesting requirements file...")
    
    req_file = Path(__file__).parent / "requirements_murphy_1.0.txt"
    if not req_file.exists():
        print("⚠️  requirements_murphy_1.0.txt not found")
        return False
    
    content = req_file.read_text()
    if "python>=" in content and not content.startswith("#") and "python>=" in content.split("\n")[0:10]:
        # Check if it's actually uncommented in first 10 lines
        for line in content.split("\n")[:10]:
            if line.strip().startswith("python>=") and not line.strip().startswith("#"):
                print("❌ Found uncommented 'python>=' in requirements (should be removed/commented)")
                return False
    
    print("✅ requirements_murphy_1.0.txt looks good (no invalid python>= entry)")
    return True

def main():
    """Run all tests"""
    print("="*80)
    print("Murphy System Startup Fixes - Test Suite")
    print("="*80)
    print()
    
    results = []
    
    # Test 1: Requirements file
    results.append(("Requirements file", test_requirements_file()))
    
    # Test 2: Core dependencies
    results.append(("Core dependencies", test_core_dependencies()))
    
    # Test 3: Imports
    results.append(("Imports", test_imports()))
    
    # Test 4: MurphySystem class
    results.append(("MurphySystem class", test_murphy_system_class()))
    
    # Summary
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Murphy System startup fixes are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. See above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
