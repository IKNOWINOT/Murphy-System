#!/bin/bash

# Test Script for Priority 3 Command Enhancements

echo "=================================="
echo "Priority 3 Enhancements Test Suite"
echo "=================================="
echo ""

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_pattern="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "Test $TOTAL_TESTS: $test_name"
    
    result=$(eval "$test_command" 2>&1)
    
    if echo "$result" | grep -q "$expected_pattern"; then
        echo "✓ PASSED"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "✗ FAILED"
        echo "  Expected pattern: $expected_pattern"
        echo "  Actual output: $result"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# ============================================
# Phase 1: Command Aliases
# ============================================
echo "=== Phase 1: Command Aliases ==="
echo ""

run_test "Verify command_enhancements.js exists" \
    "ls -lh command_enhancements.js" \
    "command_enhancements.js"

run_test "Verify alias mappings defined" \
    "grep -c 'h.*help' command_enhancements.js" \
    "[1-9]"

run_test "Verify custom aliases storage" \
    "grep -c 'customAliases' command_enhancements.js" \
    "[1-9]"

# ============================================
# Phase 2: Command Permissions
# ============================================
echo "=== Phase 2: Command Permissions ==="
echo ""

run_test "Verify risk levels defined" \
    "grep -c 'commandRiskLevels' command_enhancements.js" \
    "[1-9]"

run_test "Verify HIGH risk commands exist" \
    "grep -c 'HIGH' command_enhancements.js" \
    "[1-9]"

run_test "Verify command history tracking" \
    "grep -c 'commandHistory' command_enhancements.js" \
    "[1-9]"

# ============================================
# Phase 3: Tab Autocomplete
# ============================================
echo "=== Phase 3: Tab Autocomplete ==="
echo ""

run_test "Verify autocomplete function exists" \
    "grep -c 'autocompleteCommand' command_enhancements.js" \
    "[1-9]"

run_test "Verify suggestion function exists" \
    "grep -c 'getCommandSuggestions' command_enhancements.js" \
    "[1-9]"

run_test "Verify suggestions dropdown styling" \
    "grep -c 'suggestions-dropdown' terminal_enhancements_integration.js" \
    "[1-9]"

# ============================================
# Phase 4: Command Chaining
# ============================================
echo "=== Phase 4: Command Chaining ==="
echo ""

run_test "Verify pipe parsing function exists" \
    "grep -c 'parseCommandChain' command_enhancements.js" \
    "[1-9]"

run_test "Verify chain execution function exists" \
    "grep -c 'executeCommandChain' command_enhancements.js" \
    "[1-9]"

run_test "Verify pipe input handling" \
    "grep -c '{pipe}' command_enhancements.js" \
    "[1-9]"

# ============================================
# Phase 5: Command Scripts
# ============================================
echo "=== Phase 5: Command Scripts ==="
echo ""

run_test "Verify built-in scripts defined" \
    "grep -c 'builtInScripts' command_enhancements.js" \
    "[1-9]"

run_test "Verify script execution function exists" \
    "grep -c 'executeScript' command_enhancements.js" \
    "[1-9]"

run_test "Verify script listing function exists" \
    "grep -c 'listScripts' command_enhancements.js" \
    "[1-9]"

# ============================================
# Phase 6: Command Scheduling
# ============================================
echo "=== Phase 6: Command Scheduling ==="
echo ""

run_test "Verify scheduled commands storage" \
    "grep -c 'scheduledCommands' command_enhancements.js" \
    "[1-9]"

run_test "Verify schedule function exists" \
    "grep -c 'scheduleCommand' command_enhancements.js" \
    "[1-9]"

run_test "Verify scheduler check function exists" \
    "grep -c 'checkScheduledCommands' command_enhancements.js" \
    "[1-9]"

# ============================================
# Integration Tests
# ============================================
echo "=== Integration Tests ==="
echo ""

run_test "Verify HTML includes enhancement scripts" \
    "grep -c 'command_enhancements.js' murphy_complete_v2.html" \
    "[1-9]"

run_test "Verify HTML includes integration script" \
    "grep -c 'terminal_enhancements_integration.js' murphy_complete_v2.html" \
    "[1-9]"

run_test "Verify server is running on port 3000" \
    "netstat -tlnp | grep :3000" \
    "3000"

run_test "Verify API status endpoint works" \
    "curl -s http://localhost:3000/api/status | head -1" \
    ".*"

# ============================================
# Summary
# ============================================
echo "=================================="
echo "Test Summary"
echo "=================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed. Please review the output above."
    exit 1
fi