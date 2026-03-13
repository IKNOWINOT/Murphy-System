#!/usr/bin/env bash
# run_benchmarks.sh — Murphy System external benchmark runner
#
# Usage:
#   bash scripts/run_benchmarks.sh [all|swe-bench|gaia|agent-bench|web-arena|tool-bench|tau-bench|terminal-bench]
#
# Examples:
#   bash scripts/run_benchmarks.sh all
#   bash scripts/run_benchmarks.sh swe-bench
#   bash scripts/run_benchmarks.sh gaia agent-bench
#
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MURPHY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RESULTS_DIR="${MURPHY_DIR}/documentation/testing"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [BENCHMARK...]

Available benchmarks:
  all            Run all benchmarks
  swe-bench      Software engineering (SWE-bench Lite)
  gaia           Multi-step tool-use assistant (GAIA)
  agent-bench    8-environment agent tasks (AgentBench)
  web-arena      Web automation (WebArena)
  tool-bench     Tool/API selection (ToolBench/BFCL)
  tau-bench      Multi-turn HITL workflows (τ-Bench)
  terminal-bench CLI/system automation (Terminal-Bench)

Environment variables:
  MURPHY_BENCHMARK_MAX_TASKS  Max tasks per suite (default: 5)
  MURPHY_BENCHMARK_RESULTS_DIR  Output directory for JSON/MD reports

EOF
    exit 1
}

# ---------------------------------------------------------------------------
# Install benchmark dependencies
# ---------------------------------------------------------------------------

install_deps() {
    info "Installing benchmark dependencies from requirements_benchmarks.txt ..."
    pip install -r "${MURPHY_DIR}/requirements_benchmarks.txt" --quiet
}

# ---------------------------------------------------------------------------
# Build pytest -k filter from requested benchmarks
# ---------------------------------------------------------------------------

build_filter() {
    local benchmarks=("$@")
    local filters=()
    for b in "${benchmarks[@]}"; do
        case "$b" in
            all)            filters=(); break ;;
            swe-bench)      filters+=("swe_bench") ;;
            gaia)           filters+=("gaia") ;;
            agent-bench)    filters+=("agent_bench") ;;
            web-arena)      filters+=("web_arena") ;;
            tool-bench)     filters+=("tool_bench") ;;
            tau-bench)      filters+=("tau_bench") ;;
            terminal-bench) filters+=("terminal_bench") ;;
            *)
                error "Unknown benchmark: '$b'"
                usage
                ;;
        esac
    done

    if [ ${#filters[@]} -eq 0 ]; then
        echo ""
    else
        local IFS=" or "
        echo "${filters[*]}"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    if [ $# -eq 0 ]; then
        usage
    fi

    install_deps

    local requested=("$@")
    local k_filter
    k_filter="$(build_filter "${requested[@]}")"

    info "Results will be written to: ${RESULTS_DIR}"
    mkdir -p "${RESULTS_DIR}"

    # Build pytest command
    local pytest_args=(
        "tests/benchmarks/test_external_benchmarks.py"
        "-v"
        "--tb=short"
        "--no-header"
    )
    if [ -n "$k_filter" ]; then
        pytest_args+=("-k" "$k_filter")
    fi

    export MURPHY_RUN_EXTERNAL_BENCHMARKS=1
    export MURPHY_BENCHMARK_RESULTS_DIR="${RESULTS_DIR}"

    info "Running: pytest ${pytest_args[*]}"
    cd "${MURPHY_DIR}"
    python -m pytest "${pytest_args[@]}"

    info "Benchmark run complete. Results in: ${RESULTS_DIR}"
    if [ -f "${RESULTS_DIR}/BENCHMARK_EXTERNAL_RESULTS.md" ]; then
        info "Markdown report: ${RESULTS_DIR}/BENCHMARK_EXTERNAL_RESULTS.md"
    fi
}

main "$@"
