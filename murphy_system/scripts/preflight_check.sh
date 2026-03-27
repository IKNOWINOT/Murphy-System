#!/usr/bin/env bash
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Deploy Preflight Check Script
#
# Validates that the environment is ready for a production Hetzner deployment.
# Safe to run multiple times (idempotent, read-only checks only).
#
# Usage:
#   ./scripts/preflight_check.sh
#
# Exit code: 0 if all critical checks pass, 1 if any critical check fails.

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Deploy Preflight Check

Validates that the environment is ready for a production Hetzner deployment.
Safe to run multiple times (idempotent, read-only checks only).

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help     Show this help message and exit
  --version      Show version information
  -v, --verbose  Show detailed output for each check

Checks performed:
  1. Required Tools
     • kubectl, docker, curl installed and in PATH

  2. Kubeconfig / Cluster Access
     • ~/.kube/config exists, or
     • KUBECONFIG env var points to valid file, or
     • HETZNER_KUBECONFIG is set (GitHub Actions)

  3. Secret Placeholder Validation
     • k8s/secret.yaml has no 'change-me' values

  4. Kubernetes Namespace
     • 'murphy-system' namespace exists (warning if not)

  5. cert-manager
     • cert-manager installed with letsencrypt-prod ClusterIssuer

  6. Nginx Ingress Controller
     • IngressClass 'nginx' exists or ingress-nginx pods running

Exit codes:
  0  All critical checks passed (warnings OK)
  1  One or more critical checks failed

Examples:
  $(basename "$0")             # Run preflight checks
  $(basename "$0") --help      # Show this help
  $(basename "$0") --verbose   # Detailed output

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
case "${1:-}" in
  -h|--help)
    show_help
    ;;
  --version)
    echo "Murphy System Preflight Check v1.0.0"
    exit 0
    ;;
esac

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS="✅ PASS"
FAIL="❌ FAIL"
WARN="⚠️  WARN"

_CRITICAL_FAILURES=0
_WARNINGS=0

pass() { echo "  ${PASS}  $1"; }
fail() { echo "  ${FAIL}  $1"; _CRITICAL_FAILURES=$((_CRITICAL_FAILURES + 1)); }
warn() { echo "  ${WARN}  $1"; _WARNINGS=$((_WARNINGS + 1)); }

check_tool() {
    local tool="$1"
    if command -v "$tool" &>/dev/null; then
        pass "$tool is installed ($(command -v "$tool"))"
    else
        fail "$tool is not installed or not in PATH"
    fi
}

# ---------------------------------------------------------------------------
# Determine k8s manifest directory relative to this script
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/../k8s"

# ---------------------------------------------------------------------------
# 1. Check required tools
# ---------------------------------------------------------------------------
echo ""
echo "=== 1. Required Tools ==="
check_tool kubectl
check_tool docker
check_tool curl

# ---------------------------------------------------------------------------
# 2. Validate kubeconfig / HETZNER_KUBECONFIG access
# ---------------------------------------------------------------------------
echo ""
echo "=== 2. Kubeconfig / Cluster Access ==="
if [[ -f "${HOME}/.kube/config" ]]; then
    pass "~/.kube/config exists"
elif [[ -n "${KUBECONFIG:-}" && -f "${KUBECONFIG}" ]]; then
    pass "KUBECONFIG env var points to an existing file: ${KUBECONFIG}"
elif [[ -n "${HETZNER_KUBECONFIG:-}" ]]; then
    pass "HETZNER_KUBECONFIG secret is set (GitHub Actions context)"
else
    fail "No kubeconfig found (~/.kube/config, KUBECONFIG, or HETZNER_KUBECONFIG)"
fi

# ---------------------------------------------------------------------------
# 3. Validate secret.yaml has no placeholder values
# ---------------------------------------------------------------------------
echo ""
echo "=== 3. Secret Placeholder Validation ==="
SECRET_YAML="${K8S_DIR}/secret.yaml"
if [[ ! -f "${SECRET_YAML}" ]]; then
    fail "secret.yaml not found at ${SECRET_YAML}"
else
    if grep -q "change-me" "${SECRET_YAML}"; then
        fail "secret.yaml still contains 'change-me' placeholder values — replace before deploying"
    else
        pass "secret.yaml has no 'change-me' placeholder values"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Check if namespace exists
# ---------------------------------------------------------------------------
echo ""
echo "=== 4. Kubernetes Namespace ==="
if command -v kubectl &>/dev/null; then
    if kubectl get namespace murphy-system --ignore-not-found 2>/dev/null | grep -q murphy-system; then
        pass "Namespace 'murphy-system' exists"
    else
        warn "Namespace 'murphy-system' does not exist (will be created on deploy)"
    fi
else
    warn "kubectl not available — skipping namespace check"
fi

# ---------------------------------------------------------------------------
# 5. Check if cert-manager is installed
# ---------------------------------------------------------------------------
echo ""
echo "=== 5. cert-manager ==="
if command -v kubectl &>/dev/null; then
    if kubectl get clusterissuer --ignore-not-found 2>/dev/null | grep -q letsencrypt-prod; then
        pass "cert-manager ClusterIssuer 'letsencrypt-prod' found"
    elif kubectl get namespace cert-manager --ignore-not-found 2>/dev/null | grep -q cert-manager; then
        warn "cert-manager namespace exists but no letsencrypt-prod ClusterIssuer found — create one before deploying"
    else
        fail "cert-manager does not appear to be installed (no cert-manager namespace or ClusterIssuer)"
    fi
else
    warn "kubectl not available — skipping cert-manager check"
fi

# ---------------------------------------------------------------------------
# 6. Check if nginx ingress controller is installed
# ---------------------------------------------------------------------------
echo ""
echo "=== 6. Nginx Ingress Controller ==="
if command -v kubectl &>/dev/null; then
    if kubectl get ingressclass nginx --ignore-not-found 2>/dev/null | grep -q nginx; then
        pass "IngressClass 'nginx' found"
    elif kubectl get pods -n ingress-nginx --ignore-not-found 2>/dev/null | grep -q "ingress-nginx"; then
        pass "ingress-nginx pods found in ingress-nginx namespace"
    else
        fail "nginx ingress controller not found — install it before deploying"
    fi
else
    warn "kubectl not available — skipping ingress controller check"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  PREFLIGHT CHECK SUMMARY"
echo "========================================"

if [[ $_CRITICAL_FAILURES -eq 0 && $_WARNINGS -eq 0 ]]; then
    echo "  ${PASS}  All checks passed. Ready to deploy!"
    exit 0
elif [[ $_CRITICAL_FAILURES -eq 0 ]]; then
    echo "  ${WARN}  ${_WARNINGS} warning(s). Review warnings before deploying."
    exit 0
else
    echo "  ${FAIL}  ${_CRITICAL_FAILURES} critical failure(s), ${_WARNINGS} warning(s)."
    echo "         Fix all FAIL items before deploying."
    exit 1
fi
