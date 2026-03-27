#!/usr/bin/env bash
# Murphy System — Production Readiness Check
# Copyright © 2020 Inoni Limited Liability Company
# License: BSL-1.1
#
# Validates that all K8s resources are deployed and healthy.
# Usage: ./scripts/production_readiness_check.sh [namespace]

set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Production Readiness Check

Validates that all Kubernetes resources are deployed and healthy for
production deployment.

Usage:
  $(basename "$0") [OPTIONS] [namespace]

Arguments:
  namespace    Kubernetes namespace to check (default: murphy-system)

Options:
  -h, --help   Show this help message and exit
  --version    Show version information

Checks performed:
  • Core Resources (Deployment, Service, Ingress, HPA, ConfigMap, Secret, PVC)
  • Security & Reliability (NetworkPolicy, PDB, ResourceQuota, LimitRange)
  • Data Services (Redis, PostgreSQL deployments and services)
  • Backup & Recovery (CronJob, Backup PVC)
  • Pod Health (Running state verification)
  • Health Endpoints (API, Redis, PostgreSQL connectivity)

Examples:
  $(basename "$0")                    # Check default namespace
  $(basename "$0") my-namespace       # Check specific namespace
  $(basename "$0") --help             # Show this help

Exit codes:
  0  All checks passed
  1  One or more checks failed

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
case "${1:-}" in
  -h|--help)
    show_help
    ;;
  --version)
    echo "Murphy System Production Readiness Check v1.0.0"
    exit 0
    ;;
esac

NAMESPACE="${1:-murphy-system}"
PASS=0
FAIL=0
WARN=0

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ${name}${NC}"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}❌ ${name}${NC}"
    FAIL=$((FAIL + 1))
  fi
}

warn_check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ${name}${NC}"
    PASS=$((PASS + 1))
  else
    echo -e "${YELLOW}⚠️  ${name}${NC}"
    WARN=$((WARN + 1))
  fi
}

echo "Murphy System — Production Readiness Check"
echo "Namespace: ${NAMESPACE}"
echo "=========================================="
echo ""

echo "--- Core Resources ---"
check "Namespace exists" "kubectl get namespace ${NAMESPACE}"
check "Deployment murphy-api" "kubectl get deployment murphy-api -n ${NAMESPACE}"
check "Service murphy-api" "kubectl get service murphy-api -n ${NAMESPACE}"
check "Ingress murphy-api" "kubectl get ingress murphy-api -n ${NAMESPACE}"
check "HPA murphy-api" "kubectl get hpa murphy-api -n ${NAMESPACE}"
check "ConfigMap murphy-config" "kubectl get configmap murphy-config -n ${NAMESPACE}"
check "Secret murphy-secrets" "kubectl get secret murphy-secrets -n ${NAMESPACE}"
check "PVC murphy-data" "kubectl get pvc murphy-data -n ${NAMESPACE}"

echo ""
echo "--- Security & Reliability ---"
check "NetworkPolicy" "kubectl get networkpolicy -n ${NAMESPACE} --no-headers | grep -q ."
check "PodDisruptionBudget" "kubectl get pdb -n ${NAMESPACE} --no-headers | grep -q ."
check "ResourceQuota" "kubectl get resourcequota -n ${NAMESPACE} --no-headers | grep -q ."
check "LimitRange" "kubectl get limitrange -n ${NAMESPACE} --no-headers | grep -q ."

echo ""
echo "--- Data Services ---"
check "Redis deployment" "kubectl get deployment murphy-redis -n ${NAMESPACE}"
check "Redis service" "kubectl get service murphy-redis -n ${NAMESPACE}"
check "Redis PVC" "kubectl get pvc murphy-redis-data -n ${NAMESPACE}"
check "PostgreSQL deployment" "kubectl get deployment postgres -n ${NAMESPACE}"
check "PostgreSQL service" "kubectl get service postgres -n ${NAMESPACE}"
check "PostgreSQL PVC" "kubectl get pvc postgres-data -n ${NAMESPACE}"

echo ""
echo "--- Backup & Recovery ---"
check "Backup CronJob" "kubectl get cronjob murphy-backup -n ${NAMESPACE}"
check "Backup PVC" "kubectl get pvc murphy-backup-storage -n ${NAMESPACE}"

echo ""
echo "--- Pod Health ---"
check "API pods running" "kubectl get pods -n ${NAMESPACE} -l component=api --field-selector=status.phase=Running --no-headers | grep -q ."
warn_check "Redis pod running" "kubectl get pods -n ${NAMESPACE} -l component=redis --field-selector=status.phase=Running --no-headers | grep -q ."
warn_check "PostgreSQL pod running" "kubectl get pods -n ${NAMESPACE} -l component=postgres --field-selector=status.phase=Running --no-headers | grep -q ."

echo ""
echo "--- Health Endpoints ---"
warn_check "API health endpoint" "kubectl exec -n ${NAMESPACE} deploy/murphy-api -- curl -sf http://localhost:8000/api/health"
warn_check "Redis connectivity" "kubectl exec -n ${NAMESPACE} deploy/murphy-redis -- sh -c 'redis-cli -a \"\$REDIS_PASSWORD\" ping' | grep -q PONG"
warn_check "PostgreSQL connectivity" "kubectl exec -n ${NAMESPACE} deploy/postgres -- sh -c 'pg_isready -U murphy -d murphy_db'"

echo ""
echo "=========================================="
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}Production readiness check FAILED${NC}"
  exit 1
else
  echo -e "${GREEN}Production readiness check PASSED${NC}"
  exit 0
fi
