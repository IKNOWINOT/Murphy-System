#!/bin/bash

# Final Integration Verification for Priority 3

echo "=========================================="
echo "Priority 3 Integration Verification"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    echo -n "Test $TOTAL_TESTS: $test_name ... "
    
    result=$(eval "$test_command" 2>&1)
    
    if echo "$result" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Expected: $expected_pattern"
        echo "  Got: $result"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=== Server Status ==="
echo ""

run_test "Server is running on port 3000" \
    "netstat -tlnp 2>/dev/null | grep :3000" \
    "3000"

run_test "API status endpoint responds" \
    "curl -s http://localhost:3000/api/status | head -1" \
    ".*"

run_test "API returns LLM status" \
    "curl -s http://localhost:3000/api/status | grep -o 'groq'" \
    "groq"

echo ""
echo "=== Frontend Files ==="
echo ""

run_test "Main HTML file is served" \
    "curl -s -I http://localhost:3000/ | head -1" \
    "200 OK"

run_test "HTML includes command_enhancements.js" \
    "curl -s http://localhost:3000/ | grep 'command_enhancements.js'" \
    "command_enhancements.js"

run_test "HTML includes terminal_enhancements_integration.js" \
    "curl -s http://localhost:3000/ | grep 'terminal_enhancements_integration.js'" \
    "terminal_enhancements_integration.js"

echo ""
echo "=== JavaScript Modules ==="
echo ""

run_test "command_enhancements.js is served" \
    "curl -s -I http://localhost:3000/command_enhancements.js | head -1" \
    "200 OK"

run_test "command_enhancements.js has correct MIME type" \
    "curl -s -I http://localhost:3000/command_enhancements.js | grep -i 'application/javascript'" \
    "application/javascript"

run_test "command_enhancements.js contains alias mappings" \
    "curl -s http://localhost:3000/command_enhancements.js | grep -o 'commandAliases'" \
    "commandAliases"

run_test "command_enhancements.js contains risk levels" \
    "curl -s http://localhost:3000/command_enhancements.js | grep -o 'commandRiskLevels'" \
    "commandRiskLevels"

run_test "command_enhancements.js contains autocomplete" \
    "curl -s http://localhost:3000/command_enhancements.js | grep -o 'autocompleteCommand'" \
    "autocompleteCommand"

run_test "terminal_enhancements_integration.js is served" \
    "curl -s -I http://localhost:3000/terminal_enhancements_integration.js | head -1" \
    "200 OK"

run_test "terminal_enhancements_integration.js has correct MIME type" \
    "curl -s -I http://localhost:3000/terminal_enhancements_integration.js | grep -i 'application/javascript'" \
    "application/javascript"

run_test "terminal_enhancements_integration.js contains enhanced handler" \
    "curl -s http://localhost:3000/terminal_enhancements_integration.js | grep -o 'handleEnhancedTerminalKeyPress'" \
    "handleEnhancedTerminalKeyPress"

echo ""
echo "=== API Endpoints ==="
echo ""

run_test "Initialize endpoint works" \
    "curl -s -X POST http://localhost:3000/api/initialize | grep -o 'initialized'" \
    "initialized"

run_test "States endpoint works" \
    "curl -s http://localhost:3000/api/states | head -1" \
    ".*"

run_test "Agents endpoint works" \
    "curl -s http://localhost:3000/api/agents | head -1" \
    ".*"

echo ""
echo "=== Public Access ==="
echo ""

PUBLIC_URL="https://3000-7ced438b-5e53-49d7-a2f0-8056ffbc558b.sandbox-service.public.prod.myninja.ai"

run_test "Frontend is accessible from public URL" \
    "curl -s -I $PUBLIC_URL | head -1" \
    "200 OK"

run_test "API is accessible from public URL" \
    "curl -s $PUBLIC_URL/api/status | grep -o 'running'" \
    "running"

run_test "JavaScript files are accessible from public URL" \
    "curl -s -I $PUBLIC_URL/command_enhancements.js | head -1" \
    "200 OK"

echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All integration tests passed!${NC}"
    echo ""
    echo "=========================================="
    echo "Access Information"
    echo "=========================================="
    echo ""
    echo "Frontend URL:"
    echo "  $PUBLIC_URL/"
    echo ""
    echo "With murphy_complete_v2.html:"
    echo "  $PUBLIC_URL/murphy_complete_v2.html"
    echo ""
    echo "API Base URL:"
    echo "  $PUBLIC_URL/api/"
    echo ""
    echo "Status Check:"
    echo "  $PUBLIC_URL/api/status"
    echo ""
    echo "Ready for user testing!"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
    exit 1
fi