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

# ---------------------------------------------------------------------------
# Configuration — env vars or positional args
# ---------------------------------------------------------------------------
MURPHY_URL="${1:-${MURPHY_URL:-http://localhost:5000}}"
FOUNDER_KEY="${2:-${FOUNDER_KEY:-}}"
TEST_KEY="${3:-${TEST_KEY:-}}"

if [[ -z "$FOUNDER_KEY" ]]; then
  echo "ERROR: FOUNDER_KEY is required (env var or second argument)" >&2
  exit 1
fi
if [[ -z "$TEST_KEY" ]]; then
  echo "ERROR: TEST_KEY is required (env var or third argument)" >&2
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
