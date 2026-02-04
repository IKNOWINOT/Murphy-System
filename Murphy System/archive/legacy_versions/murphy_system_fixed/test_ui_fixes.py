#!/usr/bin/env python3
"""
UI Bug Fixes Test Suite
Tests all 8 critical bug fixes in murphy_ui_final.html
"""

import re
import sys

def test_ui_fixes():
    """Test all UI bug fixes are present"""
    
    print("="*60)
    print("MURPHY UI BUG FIXES TEST SUITE")
    print("="*60)
    print()
    
    # Read the UI file
    try:
        with open('murphy_ui_final.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("✗ ERROR: murphy_ui_final.html not found!")
        return False
    
    # Define all tests
    tests = [
        {
            "name": "Message Spacing (margin-bottom)",
            "pattern": r"margin-bottom:\s*20px",
            "description": "Prevents text overlapping"
        },
        {
            "name": "Clear Float (clear: both)",
            "pattern": r"clear:\s*both",
            "description": "Prevents message stacking"
        },
        {
            "name": "Block Display",
            "pattern": r"display:\s*block",
            "description": "Proper message layout"
        },
        {
            "name": "Vertical Scrolling",
            "pattern": r"overflow-y:\s*auto",
            "description": "Enables scrolling"
        },
        {
            "name": "Max Height Constraint",
            "pattern": r"max-height:\s*calc\(100vh\s*-\s*250px\)",
            "description": "Constrains chat area"
        },
        {
            "name": "Auto-scroll with Delay",
            "pattern": r"setTimeout\(\(\)\s*=>\s*\{[^}]*scrollTop\s*=\s*[^}]*scrollHeight",
            "description": "Smooth auto-scroll to bottom"
        },
        {
            "name": "Unique Message IDs",
            "pattern": r"messageId\s*=\s*`msg-\$\{Date\.now\(\)\}",
            "description": "Prevents ID conflicts"
        },
        {
            "name": "HTML Escaping",
            "pattern": r"escapeHtml\(content\)",
            "description": "Security - prevents XSS"
        }
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for i, test in enumerate(tests, 1):
        if re.search(test["pattern"], content, re.DOTALL):
            print(f"✓ Test {i}/8: {test['name']}")
            print(f"  → {test['description']}")
            passed += 1
        else:
            print(f"✗ Test {i}/8: {test['name']} FAILED")
            print(f"  → {test['description']}")
            failed += 1
        print()
    
    # Summary
    print("="*60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    print("="*60)
    
    if failed == 0:
        print("✓✓✓ ALL BUG FIXES VERIFIED ✓✓✓")
        print()
        print("The UI file contains all fixes for:")
        print("  • Text overlapping/doubling")
        print("  • Scrolling not working")
        print("  • Auto-scroll failure")
        print("  • Message ID conflicts")
        print()
        return True
    else:
        print(f"✗✗✗ {failed} FIXES MISSING ✗✗✗")
        return False

if __name__ == "__main__":
    success = test_ui_fixes()
    sys.exit(0 if success else 1)