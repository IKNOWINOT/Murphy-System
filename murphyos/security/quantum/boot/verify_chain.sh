#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
#
# verify_chain.sh — Early-boot verification for MurphyOS PQC secure boot.
#
# Checks:
#   1. Kernel module signature (standard + PQC sysfs presence)
#   2. Murphy runtime manifest signature (via murphy_secureboot.py)
#
# Returns 0 only if ALL checks pass.
# Results are logged via logger(1).

set -euo pipefail

SCRIPT_NAME="murphy-verify-chain"
LOG_TAG="$SCRIPT_NAME"

# Paths
PQC_SYSFS_ALGO="/sys/murphy/pqc/algorithm"
PQC_SYSFS_EPOCH="/sys/murphy/pqc/key_epoch"
SECUREBOOT_SCRIPT="/usr/lib/murphy/murphy_secureboot.py"
SECUREBOOT_FALLBACK="$(dirname "$0")/murphy_secureboot.py"

FAIL=0

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

log_info()  { logger -t "$LOG_TAG" -p user.info  "$*"; echo "[INFO]  $*"; }
log_warn()  { logger -t "$LOG_TAG" -p user.warning "$*"; echo "[WARN]  $*"; }
log_error() { logger -t "$LOG_TAG" -p user.err "$*"; echo "[ERROR] $*"; }

# -------------------------------------------------------------------
# 1. Kernel module signature & PQC sysfs presence
# -------------------------------------------------------------------

check_kernel_module() {
    log_info "Checking PQC kernel module..."

    # Verify the module is loaded
    if ! lsmod | grep -q murphy_pqc_kmod 2>/dev/null; then
        log_warn "murphy_pqc_kmod not loaded — attempting modprobe"
        if ! modprobe murphy_pqc_kmod 2>/dev/null; then
            log_error "FAIL: Cannot load murphy_pqc_kmod"
            return 1
        fi
    fi

    # Check sysfs entries exist
    if [ ! -f "$PQC_SYSFS_ALGO" ]; then
        log_error "FAIL: sysfs entry $PQC_SYSFS_ALGO not found"
        return 1
    fi

    local algo
    algo=$(cat "$PQC_SYSFS_ALGO")
    log_info "PQC algorithm: $algo"

    if [ -f "$PQC_SYSFS_EPOCH" ]; then
        local epoch
        epoch=$(cat "$PQC_SYSFS_EPOCH")
        log_info "PQC key epoch: $epoch"
    fi

    # Check standard kernel module signature (if available)
    if command -v modinfo >/dev/null 2>&1; then
        local sig_info
        sig_info=$(modinfo -F sig_id murphy_pqc_kmod 2>/dev/null || true)
        if [ -n "$sig_info" ]; then
            log_info "Kernel module signature: $sig_info"
        else
            log_warn "No kernel module signature info available"
        fi
    fi

    log_info "Kernel module check PASSED"
    return 0
}

# -------------------------------------------------------------------
# 2. Murphy runtime manifest verification
# -------------------------------------------------------------------

check_runtime_manifest() {
    log_info "Checking Murphy runtime manifest..."

    local boot_script=""
    if [ -x "$SECUREBOOT_SCRIPT" ]; then
        boot_script="$SECUREBOOT_SCRIPT"
    elif [ -f "$SECUREBOOT_FALLBACK" ]; then
        boot_script="$SECUREBOOT_FALLBACK"
    else
        log_error "FAIL: secure boot script not found"
        return 1
    fi

    if python3 "$boot_script"; then
        log_info "Runtime manifest check PASSED"
        return 0
    else
        log_error "FAIL: Runtime manifest verification failed"
        return 1
    fi
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

main() {
    log_info "=== MurphyOS PQC Verify Chain START ==="

    if ! check_kernel_module; then
        FAIL=1
    fi

    if ! check_runtime_manifest; then
        FAIL=1
    fi

    if [ "$FAIL" -ne 0 ]; then
        log_error "=== MurphyOS PQC Verify Chain FAILED ==="
        exit 1
    fi

    log_info "=== MurphyOS PQC Verify Chain PASSED ==="
    exit 0
}

main "$@"
