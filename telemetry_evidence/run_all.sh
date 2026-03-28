#!/usr/bin/env bash
# ============================================================
# Master runner: executes all phases sequentially
#
# Usage: bash telemetry_evidence/run_all.sh
#
# This script orchestrates the complete Murphy System telemetry
# test run, executing Phases 0–8 in order. Each phase captures
# evidence to telemetry_evidence/ and logs events to
# telemetry_log.jsonl.
#
# The Loop Logic (What Happens When Something Fails):
#
#   ┌─────────────────────────────────────────────┐
#   │                 RUN TEST                     │
#   └──────────────────┬──────────────────────────┘
#                      │
#                 ✅ Pass? ─── YES → 📝 Log → Next
#                      │
#                     NO
#                      │
#              ┌───────┴────────┐
#              │  📝 LOG ERROR  │
#              └───────┬────────┘
#                      │
#              ┌───────┴────────┐
#              │  🔍 DIAGNOSE   │
#              └───────┬────────┘
#                      │
#              ┌───────┴────────┐
#              │  📋 PLAN FIX   │
#              └───────┬────────┘
#                      │
#              ┌───────┴────────┐
#              │  🔄 RE-TEST    │
#              └───────┬────────┘
#                      │
#                 ✅ Pass? ─── YES → 📝 Log "FIXED" → Next
#                      │
#                     NO → Escalate to FINAL_REPORT
# ============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$SCRIPT_DIR/telemetry_log.jsonl"

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log_event() {
    local phase="$1" step="$2" status="$3" detail="${4:-}"
    printf '{"ts":"%s","phase":"%s","step":"%s","status":"%s","detail":"%s"}\n' \
        "$(timestamp)" "$phase" "$step" "$status" "$detail" >> "$LOG_FILE"
}

echo "🚀 MURPHY SYSTEM — FULL TELEMETRY TEST RUN"
echo "============================================"
echo "Start time: $(timestamp)"
echo "Repository: $REPO_ROOT"
echo "Evidence:   $SCRIPT_DIR"
echo "============================================"
echo ""

# Initialize log
echo "" > "$LOG_FILE"
log_event "master" "run_all_start" "info" "$(timestamp)"

# Track phase results
PHASE_RESULTS=()
run_phase() {
    local phase_num="$1"
    local phase_name="$2"
    local phase_cmd="$3"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " Phase $phase_num: $phase_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    log_event "master" "phase${phase_num}_start" "info" "$phase_name"

    local exit_code=0
    eval "$phase_cmd" || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        PHASE_RESULTS+=("✅ Phase $phase_num ($phase_name): PASSED")
        log_event "master" "phase${phase_num}_end" "pass" "exit=$exit_code"
    else
        PHASE_RESULTS+=("⚠️  Phase $phase_num ($phase_name): exit=$exit_code")
        log_event "master" "phase${phase_num}_end" "warn" "exit=$exit_code"
    fi
}

# ── Execute Phases ────────────────────────────────────────────

cd "$REPO_ROOT"

# Phase 0: Setup
run_phase 0 "Environment Setup" "bash '$SCRIPT_DIR/00_setup.sh'"

# Activate venv if available
MURPHY_DIR="$REPO_ROOT/Murphy System"
if [[ -d "$MURPHY_DIR/venv" ]]; then
    # shellcheck disable=SC1091
    source "$MURPHY_DIR/venv/bin/activate"
fi

# Phase 1: Health
run_phase 1 "Health & Telemetry" "python3 '$SCRIPT_DIR/test_phase1_health.py'"

# Phase 2: API Core
run_phase 2 "Core API Sweep" "python3 '$SCRIPT_DIR/test_phase2_api_core.py'"

# Phase 3: UI Interfaces
run_phase 3 "UI Interfaces" "python3 '$SCRIPT_DIR/test_phase3_ui.py'"

# Phase 4: Security
run_phase 4 "Security Plane" "python3 '$SCRIPT_DIR/test_phase4_security.py'"

# Phase 5: Self-Healing & Tests
run_phase 5 "Self-Healing & Tests" "bash '$SCRIPT_DIR/test_phase5_self_healing.sh'"

# Phase 6: Sales Demo
run_phase 6 "Sales Readiness" "python3 '$SCRIPT_DIR/test_phase6_sales_demo.py'"

# Phase 7: Fix Loop
run_phase 7 "Diagnose & Fix" "python3 '$SCRIPT_DIR/test_phase7_fix_loop.py'"

# Phase 8: Final Report
run_phase 8 "Final Report" "python3 '$SCRIPT_DIR/generate_final_report.py'"

# ── Final Summary ─────────────────────────────────────────────

echo ""
echo ""
echo "🏁 MURPHY SYSTEM — TEST RUN COMPLETE"
echo "============================================"
echo "End time: $(timestamp)"
echo ""
echo "Phase Results:"
for result in "${PHASE_RESULTS[@]}"; do
    echo "  $result"
done
echo ""
echo "Evidence:     $SCRIPT_DIR/"
echo "Telemetry:    $LOG_FILE"
echo "Final Report: $SCRIPT_DIR/FINAL_REPORT.md"
echo "============================================"

log_event "master" "run_all_end" "info" "$(timestamp)"
