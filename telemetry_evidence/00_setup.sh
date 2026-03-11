#!/usr/bin/env bash
# ============================================================
# PHASE 0: Clone, install, create evidence folders, cold-boot
# ============================================================
# FILES USED:
#   setup_and_start.sh          → One-step venv + deps + .env + server launch
#   install.sh                  → Curl-pipe installer (alternative)
#   requirements.txt            → Core dependencies
#   Murphy System/murphy_system_1.0_runtime.py  → FastAPI entry point
#   Murphy System/src/runtime/app.py            → create_app() factory
#   Murphy System/src/config.py                 → Pydantic BaseSettings
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MURPHY_DIR="$REPO_ROOT/Murphy System"
EVIDENCE_DIR="$SCRIPT_DIR"
LOG_FILE="$EVIDENCE_DIR/telemetry_log.jsonl"

# Helpers
timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log_event() {
    local phase="$1" step="$2" status="$3" detail="${4:-}"
    printf '{"ts":"%s","phase":"%s","step":"%s","status":"%s","detail":"%s"}\n' \
        "$(timestamp)" "$phase" "$step" "$status" "$detail" >> "$LOG_FILE"
}

echo "============================================"
echo " PHASE 0: Environment Setup & Cold Boot"
echo " $(timestamp)"
echo "============================================"
echo ""

# ── Step 0.1: Verify repository structure ─────────────────────
echo "→ Step 0.1: Verifying repository structure..."
REQUIRED_FILES=(
    "$MURPHY_DIR/murphy_system_1.0_runtime.py"
    "$MURPHY_DIR/src/runtime/app.py"
    "$MURPHY_DIR/requirements.txt"
)
ALL_PRESENT=true
for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        echo "  ✓ $(basename "$f")"
    else
        echo "  ✗ MISSING: $f"
        ALL_PRESENT=false
    fi
done

if $ALL_PRESENT; then
    log_event "phase0" "verify_structure" "pass" "All required files present"
    echo "  → All required files present"
else
    log_event "phase0" "verify_structure" "fail" "Missing required files"
    echo "  → ERROR: Missing required files"
    exit 1
fi

# ── Step 0.2: Create/activate virtual environment ─────────────
echo ""
echo "→ Step 0.2: Creating virtual environment..."
cd "$MURPHY_DIR"

if [[ ! -d "venv" ]]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
    log_event "phase0" "create_venv" "pass" "Created new venv"
else
    echo "  ✓ Virtual environment already exists"
    log_event "phase0" "create_venv" "pass" "Existing venv found"
fi

# shellcheck disable=SC1091
source venv/bin/activate

# ── Step 0.3: Install dependencies ────────────────────────────
echo ""
echo "→ Step 0.3: Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt 2>&1 | tail -5
pip install --quiet pytest pytest-asyncio pytest-cov httpx requests 2>&1 | tail -3

log_event "phase0" "install_deps" "pass" "Dependencies installed"
echo "  ✓ Dependencies installed"

# ── Step 0.4: Initialize .env if missing ──────────────────────
echo ""
echo "→ Step 0.4: Checking .env configuration..."
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        echo "  ✓ Created .env from .env.example"
        log_event "phase0" "init_env" "pass" "Created .env from example"
    else
        cat > .env <<'ENVEOF'
MURPHY_ENV=development
MURPHY_PORT=8000
MURPHY_HOST=0.0.0.0
MURPHY_LOG_LEVEL=INFO
ENVEOF
        echo "  ✓ Created minimal .env"
        log_event "phase0" "init_env" "pass" "Created minimal .env"
    fi
else
    echo "  ✓ .env already exists"
    log_event "phase0" "init_env" "pass" "Existing .env found"
fi

# ── Step 0.5: Cold-boot the server (background) ──────────────
echo ""
echo "→ Step 0.5: Cold-booting Murphy System..."
MURPHY_PID=""
if command -v lsof &>/dev/null && lsof -i :8000 &>/dev/null; then
    echo "  ⚠ Port 8000 already in use — skipping server start"
    log_event "phase0" "cold_boot" "skip" "Port 8000 already in use"
else
    cd "$MURPHY_DIR"
    nohup python murphy_system_1.0_runtime.py > "$EVIDENCE_DIR/02_boot/server_stdout.log" 2>&1 &
    MURPHY_PID=$!
    echo "$MURPHY_PID" > "$EVIDENCE_DIR/02_boot/murphy.pid"
    echo "  → Server starting (PID: $MURPHY_PID)"
    log_event "phase0" "cold_boot" "pass" "Server PID=$MURPHY_PID"

    # Wait for server readiness (up to 30 seconds)
    echo "  → Waiting for server readiness..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
            echo "  ✓ Server ready after ${i}s"
            log_event "phase0" "server_ready" "pass" "Ready after ${i}s"
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "  ⚠ Server not ready after 30s — tests may fail"
            log_event "phase0" "server_ready" "warn" "Timeout after 30s"
        fi
        sleep 1
    done
fi

# ── Step 0.6: Capture environment snapshot ────────────────────
echo ""
echo "→ Step 0.6: Capturing environment snapshot..."
{
    echo "=== Python Version ==="
    python3 --version
    echo ""
    echo "=== Pip Packages ==="
    pip list --format=columns 2>/dev/null | head -30
    echo ""
    echo "=== Environment Variables ==="
    env | grep -i murphy || echo "(none set)"
    echo ""
    echo "=== Timestamp ==="
    timestamp
} > "$EVIDENCE_DIR/01_install/environment_snapshot.txt" 2>&1

log_event "phase0" "env_snapshot" "pass" "Saved to 01_install/environment_snapshot.txt"
echo "  ✓ Environment snapshot saved"

echo ""
echo "============================================"
echo " PHASE 0 COMPLETE"
echo "============================================"
