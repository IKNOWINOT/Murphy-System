#!/usr/bin/env bash
# test_production_auth.sh — Murphy System
#
# End-to-end smoke test for the Murphy System API authentication layer.
# Tests that:
#   - Requests without a key on non-health endpoints return 401
#   - The health endpoint is always 200 (no key required)
#   - A valid key via Authorization: Bearer gets 200
#   - A valid key via X-API-Key header gets 200
#   - An invalid key gets 401
#
# Usage:
#   # Set environment variables, then run:
#   MURPHY_URL=http://localhost:5000 \
#   FOUNDER_KEY=founder_abc123       \
#   TEST_KEY=test_xyz456             \
#   ./scripts/test_production_auth.sh
#
#   # Or pass as positional arguments:
#   ./scripts/test_production_auth.sh http://localhost:5000 founder_abc123 test_xyz456
#
# Exit codes:
#   0 — all tests passed
#   1 — one or more tests failed

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Production Auth Smoke Tests

End-to-end smoke test for the Murphy System API authentication layer.
Validates that authentication is working correctly in production.

Usage:
  $(basename "$0") [OPTIONS] [URL] [FOUNDER_KEY] [TEST_KEY]

Arguments:
  URL           Murphy API URL (default: \$MURPHY_URL or http://localhost:5000)
  FOUNDER_KEY   Founder API key (required, or set \$FOUNDER_KEY)
  TEST_KEY      Test API key (required, or set \$TEST_KEY)

Options:
  -h, --help    Show this help message and exit
  --version     Show version information
  -v, --verbose Show detailed request/response info

Environment variables:
  MURPHY_URL    API base URL
  FOUNDER_KEY   Founder API key
  TEST_KEY      Test API key

Tests performed:
  • Health endpoints (/health, /healthz, /ready) return 200 without auth
  • Protected endpoints return 401 without auth
  • Invalid keys return 401
  • Valid keys (Bearer and X-API-Key) return 200

Examples:
  # Using environment variables
  export MURPHY_URL=http://localhost:5000
  export FOUNDER_KEY=founder_abc123
  export TEST_KEY=test_xyz456
  $(basename "$0")

  # Using positional arguments
  $(basename "$0") http://localhost:5000 founder_abc123 test_xyz456

  # Generate keys first, then test
  source <(./scripts/generate_secrets.sh)
  $(basename "$0") http://localhost:5000 \$FOUNDER_API_KEY \$TEST_API_KEY

Exit codes:
  0  All tests passed
  1  One or more tests failed

EOF
  exit 0
}

# ── Parse flags ──────────────────────────────────────────────────────────────
VERBOSE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --version)
      echo "Murphy System Production Auth Tests v1.0.0"
      exit 0
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Configuration — env vars or positional args
# ---------------------------------------------------------------------------
MURPHY_URL="${1:-${MURPHY_URL:-http://localhost:5000}}"
FOUNDER_KEY="${2:-${FOUNDER_KEY:-}}"
TEST_KEY="${3:-${TEST_KEY:-}}"

if [[ -z "$FOUNDER_KEY" ]]; then
  echo "ERROR: FOUNDER_KEY is required (env var or second argument)" >&2
  echo ""
  echo "Generate keys with: ./scripts/generate_secrets.sh" >&2
  echo "Then set FOUNDER_KEY environment variable or pass as argument" >&2
  echo ""
  echo "Use --help for more information" >&2
  exit 1
fi
if [[ -z "$TEST_KEY" ]]; then
  echo "ERROR: TEST_KEY is required (env var or third argument)" >&2
  echo ""
  echo "Generate keys with: ./scripts/generate_secrets.sh" >&2
  echo "Then set TEST_KEY environment variable or pass as argument" >&2
  echo ""
  echo "Use --help for more information" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Helper: run a curl request and check the HTTP status code
# ---------------------------------------------------------------------------
PASS=0
FAIL=0

check() {
  local description="$1"
  local expected_status="$2"
  shift 2
  local actual_status
  actual_status=$(curl -s -o /dev/null -w "%{http_code}" "$@")
  if [[ "$actual_status" == "$expected_status" ]]; then
    echo "  PASS  [$actual_status] $description"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  [got $actual_status, want $expected_status] $description"
    FAIL=$((FAIL + 1))
  fi
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
echo ""
echo "Murphy System — Auth Smoke Tests"
echo "Target: $MURPHY_URL"
echo "-----------------------------------"

# Health endpoints — always 200, no key needed
check "GET /health returns 200 (no key)"   "200" "${MURPHY_URL}/health"
check "GET /healthz returns 200 (no key)"  "200" "${MURPHY_URL}/healthz"
check "GET /ready returns 200 (no key)"    "200" "${MURPHY_URL}/ready"

# Protected endpoint — no key → 401
check "GET /api/status — no key → 401" \
  "401" "${MURPHY_URL}/api/status"

# Protected endpoint — invalid key → 401
check "GET /api/status — invalid key (Bearer) → 401" \
  "401" "${MURPHY_URL}/api/status" \
  -H "Authorization: Bearer invalid-key-abc"

check "GET /api/status — invalid key (X-API-Key) → 401" \
  "401" "${MURPHY_URL}/api/status" \
  -H "X-API-Key: invalid-key-abc"

# Protected endpoint — founder key via Bearer → 200
check "GET /api/status — founder key (Bearer) → 200" \
  "200" "${MURPHY_URL}/api/status" \
  -H "Authorization: Bearer ${FOUNDER_KEY}"

# Protected endpoint — founder key via X-API-Key → 200
check "GET /api/status — founder key (X-API-Key) → 200" \
  "200" "${MURPHY_URL}/api/status" \
  -H "X-API-Key: ${FOUNDER_KEY}"

# Protected endpoint — test key via Bearer → 200
check "GET /api/status — test key (Bearer) → 200" \
  "200" "${MURPHY_URL}/api/status" \
  -H "Authorization: Bearer ${TEST_KEY}"

# Protected endpoint — test key via X-API-Key → 200
check "GET /api/status — test key (X-API-Key) → 200" \
  "200" "${MURPHY_URL}/api/status" \
  -H "X-API-Key: ${TEST_KEY}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "-----------------------------------"
echo "Results: ${PASS} passed, ${FAIL} failed"
if [[ "$FAIL" -gt 0 ]]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
exit 0
