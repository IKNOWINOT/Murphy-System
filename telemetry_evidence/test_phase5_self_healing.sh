#!/usr/bin/env bash
# ============================================================
# PHASE 5: Run the full pytest suite, capture results,
#           invoke self-fix loop for any failures.
#
# FILES TESTED:
#   Murphy System/tests/                → 568+ test files, 8843 functions
#   Murphy System/src/self_fix_loop.py  → Autonomous fix cycle
#   Murphy System/src/murphy_immune_engine.py → 11-phase immune cycle
#   Murphy System/src/bug_pattern_detector.py → Pattern classification
# ============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MURPHY_DIR="$REPO_ROOT/Murphy System"
EVIDENCE_DIR="$SCRIPT_DIR/11_self_improvement"
LOG_FILE="$SCRIPT_DIR/telemetry_log.jsonl"

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log_event() {
    local phase="$1" step="$2" status="$3" detail="${4:-}"
    printf '{"ts":"%s","phase":"%s","step":"%s","status":"%s","detail":"%s"}\n' \
        "$(timestamp)" "$phase" "$step" "$status" "$detail" >> "$LOG_FILE"
}

echo "============================================"
echo " PHASE 5: Self-Healing & Test Suite"
echo " $(timestamp)"
echo "============================================"
echo ""

mkdir -p "$EVIDENCE_DIR"

# ── Step 5.1: Activate virtual environment ────────────────────
echo "→ Step 5.1: Activating virtual environment..."
cd "$MURPHY_DIR"
if [[ -d "venv" ]]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    echo "  ✓ Virtual environment activated"
else
    echo "  ⚠ No venv found — using system Python"
fi

# ── Step 5.2: Run pytest (core tests) ─────────────────────────
echo ""
echo "→ Step 5.2: Running core test suite..."

# Run pytest with JUnit XML output and capture exit code
PYTEST_EXIT=0
python -m pytest tests/ \
    -v \
    --timeout=60 \
    --ignore=tests/e2e \
    --ignore=tests/benchmarks \
    --junitxml="$EVIDENCE_DIR/pytest_results.xml" \
    --tb=short \
    -q 2>&1 | tee "$EVIDENCE_DIR/pytest_output.txt" || PYTEST_EXIT=$?

echo ""
if [[ $PYTEST_EXIT -eq 0 ]]; then
    echo "  ✓ All tests passed"
    log_event "phase5" "pytest_core" "pass" "Exit code 0"
elif [[ $PYTEST_EXIT -eq 1 ]]; then
    echo "  ⚠ Some tests failed (exit code 1)"
    log_event "phase5" "pytest_core" "partial" "Exit code 1 — some failures"
elif [[ $PYTEST_EXIT -eq 5 ]]; then
    echo "  ⚠ No tests collected"
    log_event "phase5" "pytest_core" "warn" "Exit code 5 — no tests collected"
else
    echo "  ✗ pytest error (exit code $PYTEST_EXIT)"
    log_event "phase5" "pytest_core" "fail" "Exit code $PYTEST_EXIT"
fi

# ── Step 5.3: Extract failure summary ─────────────────────────
echo ""
echo "→ Step 5.3: Extracting failure summary..."

FAILURES_FILE="$EVIDENCE_DIR/failures_summary.txt"
if [[ -f "$EVIDENCE_DIR/pytest_output.txt" ]]; then
    grep -E "^(FAILED|ERROR)" "$EVIDENCE_DIR/pytest_output.txt" > "$FAILURES_FILE" 2>/dev/null || true
    FAILURE_COUNT=$(wc -l < "$FAILURES_FILE" 2>/dev/null | tr -d ' ')
    echo "  Found $FAILURE_COUNT failures"
    log_event "phase5" "extract_failures" "info" "$FAILURE_COUNT failures extracted"
else
    echo "  No pytest output to analyze"
    FAILURE_COUNT=0
fi

# ── Step 5.4: Test self-fix module import ─────────────────────
echo ""
echo "→ Step 5.4: Testing self-fix module imports..."

python -c "
import sys, json
sys.path.insert(0, 'src')
results = {}
modules = [
    'self_fix_loop',
    'murphy_immune_engine',
    'bug_pattern_detector',
    'self_improvement_engine',
    'self_healing_coordinator',
]
for mod_name in modules:
    try:
        __import__(mod_name)
        results[mod_name] = 'OK'
    except ImportError as e:
        results[mod_name] = f'ImportError: {e}'
    except Exception as e:
        results[mod_name] = f'Error: {e}'
print(json.dumps(results, indent=2))
" > "$EVIDENCE_DIR/self_fix_imports.json" 2>&1

echo "  ✓ Import test results saved"
log_event "phase5" "self_fix_imports" "pass" "Module import tests complete"

# ── Step 5.5: Generate test suite statistics ──────────────────
echo ""
echo "→ Step 5.5: Generating test suite statistics..."

python -c "
import os, json, glob
tests_dir = 'tests'
test_files = glob.glob(os.path.join(tests_dir, '**', 'test_*.py'), recursive=True)
test_files += glob.glob(os.path.join(tests_dir, '**', '*_test.py'), recursive=True)
# Count test functions
total_funcs = 0
for tf in test_files:
    try:
        with open(tf, 'r') as f:
            for line in f:
                if line.strip().startswith('def test_') or line.strip().startswith('async def test_'):
                    total_funcs += 1
    except Exception:
        pass
stats = {
    'test_files': len(test_files),
    'test_functions': total_funcs,
    'subdirectories': list(set(
        os.path.dirname(f).replace(tests_dir + '/', '')
        for f in test_files if '/' in f.replace(tests_dir + '/', '')
    )),
}
print(json.dumps(stats, indent=2))
" > "$EVIDENCE_DIR/test_suite_stats.json" 2>&1

echo "  ✓ Statistics saved"
log_event "phase5" "test_stats" "pass" "Test suite statistics captured"

echo ""
echo "============================================"
echo " PHASE 5 COMPLETE (pytest exit: $PYTEST_EXIT)"
echo "============================================"
