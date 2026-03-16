#!/usr/bin/env bash
# Murphy System — Monitoring Verification Script
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
#
# Usage:
#   bash verify_monitoring.sh [--namespace murphy-system] [--port-forward]
#
# Checks:
#   1. Prometheus pod is running
#   2. Grafana pod is running
#   3. Prometheus is scraping murphy-api targets
#   4. Alert rules are loaded
#   5. Murphy API /metrics endpoint is accessible
# Then prints a full UI access summary.

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
NAMESPACE="${NAMESPACE:-murphy-system}"
PROM_PORT="${PROM_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
MURPHY_PORT="${MURPHY_PORT:-8000}"
UI_PORT="${UI_PORT:-8090}"
USE_PORT_FORWARD=false

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --port-forward) USE_PORT_FORWARD=true; shift ;;
    --prom-port) PROM_PORT="$2"; shift 2 ;;
    --grafana-port) GRAFANA_PORT="$2"; shift 2 ;;
    --murphy-port) MURPHY_PORT="$2"; shift 2 ;;
    --ui-port) UI_PORT="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; WARN=0
check_pass() { echo -e "  ${GREEN}✓${RESET} $1"; ((PASS++)); }
check_fail() { echo -e "  ${RED}✗${RESET} $1"; ((FAIL++)); }
check_warn() { echo -e "  ${YELLOW}⚠${RESET} $1"; ((WARN++)); }
section()    { echo -e "\n${BOLD}${CYAN}▶ $1${RESET}"; }

# ── Port-forward helpers ──────────────────────────────────────────────────────
PF_PROM_PID=""
PF_GRAFANA_PID=""

cleanup() {
  [[ -n "$PF_PROM_PID"    ]] && kill "$PF_PROM_PID"    2>/dev/null || true
  [[ -n "$PF_GRAFANA_PID" ]] && kill "$PF_GRAFANA_PID" 2>/dev/null || true
}
trap cleanup EXIT

start_port_forward() {
  local svc="$1" local_port="$2" remote_port="$3"
  kubectl port-forward "service/${svc}" "${local_port}:${remote_port}" \
    -n "$NAMESPACE" >/dev/null 2>&1 &
  echo $!
}

# ── 1. K8s pod checks ─────────────────────────────────────────────────────────
section "Kubernetes Pod Health (namespace: ${NAMESPACE})"

if ! command -v kubectl &>/dev/null; then
  check_warn "kubectl not found — skipping K8s checks"
else
  # Prometheus
  PROM_POD=$(kubectl get pods -n "$NAMESPACE" \
    -l "app=murphy-system,component=prometheus" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
  if [[ -n "$PROM_POD" ]]; then
    check_pass "Prometheus pod running: $PROM_POD"
  else
    check_fail "Prometheus pod NOT running in namespace '$NAMESPACE'"
  fi

  # Grafana
  GRAFANA_POD=$(kubectl get pods -n "$NAMESPACE" \
    -l "app=murphy-system,component=grafana" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
  if [[ -n "$GRAFANA_POD" ]]; then
    check_pass "Grafana pod running: $GRAFANA_POD"
  else
    check_fail "Grafana pod NOT running in namespace '$NAMESPACE'"
  fi

  # Murphy API
  MURPHY_POD=$(kubectl get pods -n "$NAMESPACE" \
    -l "app=murphy-system,component=api" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
  if [[ -n "$MURPHY_POD" ]]; then
    check_pass "Murphy API pod running: $MURPHY_POD"
  else
    check_warn "Murphy API pod not found with label component=api — check deployment"
  fi

  # Start port-forwards if requested
  if [[ "$USE_PORT_FORWARD" == "true" ]]; then
    echo -e "  ${CYAN}→ Starting port-forwards…${RESET}"
    PF_PROM_PID=$(start_port_forward prometheus "$PROM_PORT" 9090)
    PF_GRAFANA_PID=$(start_port_forward grafana "$GRAFANA_PORT" 3000)
    sleep 3
  fi
fi

# ── 2. Prometheus API checks ──────────────────────────────────────────────────
section "Prometheus Connectivity (http://localhost:${PROM_PORT})"
PROM_BASE="http://localhost:${PROM_PORT}"

if curl -sf "${PROM_BASE}/-/ready" >/dev/null 2>&1; then
  check_pass "Prometheus is ready"
else
  check_fail "Prometheus not reachable at ${PROM_BASE} (try --port-forward)"
fi

if curl -sf "${PROM_BASE}/-/healthy" >/dev/null 2>&1; then
  check_pass "Prometheus is healthy"
else
  check_warn "Prometheus health check did not respond"
fi

# Scrape targets
section "Prometheus Scrape Targets"
TARGETS_JSON=$(curl -sf "${PROM_BASE}/api/v1/targets" 2>/dev/null || echo '{}')
ACTIVE_TARGETS=$(echo "$TARGETS_JSON" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
    t=[x for x in d.get('data',{}).get('activeTargets',[]) if x.get('job')=='murphy-api']; \
    [print(x['scrapeUrl'], x['health']) for x in t]" 2>/dev/null || echo "")

if [[ -n "$ACTIVE_TARGETS" ]]; then
  while IFS= read -r line; do
    if echo "$line" | grep -q "up"; then
      check_pass "murphy-api target UP: $(echo "$line" | awk '{print $1}')"
    else
      check_fail "murphy-api target DOWN: $line"
    fi
  done <<< "$ACTIVE_TARGETS"
else
  check_warn "No murphy-api targets found — Prometheus may not be scraping yet"
fi

# Alert rules
section "Prometheus Alert Rules"
RULES_JSON=$(curl -sf "${PROM_BASE}/api/v1/rules" 2>/dev/null || echo '{}')
RULE_COUNT=$(echo "$RULES_JSON" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
    rules=[r for g in d.get('data',{}).get('groups',[]) for r in g.get('rules',[])]; \
    print(len(rules))" 2>/dev/null || echo "0")

if [[ "$RULE_COUNT" -gt 0 ]]; then
  check_pass "$RULE_COUNT alert rule(s) loaded"
  # List firing alerts
  FIRING=$(echo "$RULES_JSON" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); \
      rules=[r for g in d.get('data',{}).get('groups',[]) for r in g.get('rules',[]) \
             if r.get('state')=='firing']; \
      [print(r['name']) for r in rules]" 2>/dev/null || echo "")
  if [[ -n "$FIRING" ]]; then
    check_warn "FIRING alerts: $(echo "$FIRING" | tr '\n' ' ')"
  else
    check_pass "No alerts currently firing"
  fi
else
  check_warn "No alert rules loaded — check prometheus-config.yaml ConfigMap"
fi

# ── 3. Grafana checks ─────────────────────────────────────────────────────────
section "Grafana Connectivity (http://localhost:${GRAFANA_PORT})"
GRAFANA_BASE="http://localhost:${GRAFANA_PORT}"

if curl -sf "${GRAFANA_BASE}/api/health" >/dev/null 2>&1; then
  check_pass "Grafana is healthy"
else
  check_fail "Grafana not reachable at ${GRAFANA_BASE} (try --port-forward)"
fi

# ── 4. Murphy API /metrics ─────────────────────────────────────────────────────
section "Murphy API Metrics Endpoint (http://localhost:${MURPHY_PORT})"
MURPHY_BASE="http://localhost:${MURPHY_PORT}"

if curl -sf "${MURPHY_BASE}/metrics" | grep -q "murphy_requests_total" 2>/dev/null; then
  check_pass "murphy_requests_total metric present"
else
  check_warn "/metrics endpoint not accessible locally — verify in-cluster with kubectl port-forward"
fi

if curl -sf "${MURPHY_BASE}/api/health" >/dev/null 2>&1; then
  check_pass "Murphy API /api/health OK"
else
  check_warn "Murphy API not reachable at ${MURPHY_BASE}"
fi

# ── 5. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  VERIFICATION SUMMARY${RESET}"
echo -e "  ${GREEN}Passed:${RESET} $PASS   ${RED}Failed:${RESET} $FAIL   ${YELLOW}Warnings:${RESET} $WARN"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

# ── 6. UI Access Links ────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}  MURPHY SYSTEM — UI PAGE DIRECTORY${RESET}"
echo -e "${BOLD}  (start static server: cd 'Murphy System' && python -m http.server ${UI_PORT})${RESET}"
echo ""
echo -e "  ${BOLD}Backend Services${RESET}"
echo -e "  ├─ Murphy API              http://localhost:${MURPHY_PORT}"
echo -e "  ├─ API Docs (Swagger)      http://localhost:${MURPHY_PORT}/docs"
echo -e "  ├─ Prometheus              http://localhost:${PROM_PORT}"
echo -e "  └─ Grafana                 http://localhost:${GRAFANA_PORT}  (admin / admin)"
echo ""
echo -e "  ${BOLD}UI Pages  →  http://localhost:${UI_PORT}/<page>?apiPort=${MURPHY_PORT}${RESET}"
echo ""
echo -e "  ${BOLD}Entry Points${RESET}"
echo -e "  ├─ Landing Page            http://localhost:${UI_PORT}/murphy_landing_page.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Onboarding Wizard       http://localhost:${UI_PORT}/onboarding_wizard.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Sign Up                 http://localhost:${UI_PORT}/signup.html?apiPort=${MURPHY_PORT}"
echo -e "  └─ Pricing                 http://localhost:${UI_PORT}/pricing.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "  ${BOLD}Terminals & Dashboards${RESET}"
echo -e "  ├─ Unified Hub             http://localhost:${UI_PORT}/terminal_unified.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Architect Terminal      http://localhost:${UI_PORT}/terminal_architect.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Enhanced Terminal       http://localhost:${UI_PORT}/terminal_enhanced.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Integrated Terminal     http://localhost:${UI_PORT}/terminal_integrated.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Worker Terminal         http://localhost:${UI_PORT}/terminal_worker.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Orchestrator Terminal   http://localhost:${UI_PORT}/terminal_orchestrator.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Costs Terminal          http://localhost:${UI_PORT}/terminal_costs.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Org Chart Terminal      http://localhost:${UI_PORT}/terminal_orgchart.html?apiPort=${MURPHY_PORT}"
echo -e "  └─ Integrations Terminal   http://localhost:${UI_PORT}/terminal_integrations.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "  ${BOLD}Graphical / Canvas${RESET}"
echo -e "  ├─ Workflow Canvas         http://localhost:${UI_PORT}/workflow_canvas.html?apiPort=${MURPHY_PORT}"
echo -e "  └─ System Visualizer       http://localhost:${UI_PORT}/system_visualizer.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "  ${BOLD}Operational${RESET}"
echo -e "  ├─ Production Wizard       http://localhost:${UI_PORT}/production_wizard.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Matrix Integration      http://localhost:${UI_PORT}/matrix_integration.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Compliance Dashboard    http://localhost:${UI_PORT}/compliance_dashboard.html?apiPort=${MURPHY_PORT}"
echo -e "  └─ Workspace               http://localhost:${UI_PORT}/workspace.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "  ${BOLD}Dev / QA${RESET}"
echo -e "  └─ API Smoke Test          http://localhost:${UI_PORT}/murphy-smoke-test.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "  ${BOLD}Strategic Features${RESET}"
echo -e "  ├─ Observability Dashboard http://localhost:${UI_PORT}/strategic/gap_closure/observability/dashboard.html?apiPort=${MURPHY_PORT}"
echo -e "  ├─ Community Portal        http://localhost:${UI_PORT}/strategic/gap_closure/community/community_portal.html?apiPort=${MURPHY_PORT}"
echo -e "  └─ Workflow Builder        http://localhost:${UI_PORT}/strategic/gap_closure/lowcode/workflow_builder_ui.html?apiPort=${MURPHY_PORT}"
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

if [[ "$FAIL" -gt 0 ]]; then
  echo -e "\n${RED}${BOLD}  $FAIL check(s) failed. Review the output above.${RESET}\n"
  exit 1
else
  echo -e "\n${GREEN}${BOLD}  All checks passed.${RESET}\n"
  exit 0
fi
