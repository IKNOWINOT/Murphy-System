#!/usr/bin/env bash
# fetch_eqemu_assets.sh — Download and organize EQEmu server assets
#
# Usage:
#   ./scripts/fetch_eqemu_assets.sh [OPTIONS]
#
# Options:
#   --install-dir DIR   Installation directory (default: $HOME/eqemu-server)
#   --components LIST   Components to fetch: server,database,quests,maps,all (default: all)
#   --method METHOD     Download method: source, release, docker (default: source)
#   --help              Show this help message
#
# Components fetched:
#   server   — EQEmu server source or pre-built binaries
#   database — PEQ database SQL dumps
#   quests   — Quest files (Perl/Lua)
#   maps     — Zone map files
#   spire    — Spire web toolkit
#   all      — All of the above

set -euo pipefail

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
header()  { printf "\n${BOLD}${CYAN}==> %s${NC}\n" "$*"; }

# ---------------------------------------------------------------------------
# Upstream URLs
# ---------------------------------------------------------------------------
EQEMU_SERVER_REPO="https://github.com/EQEmu/EQEmu.git"
EQEMU_RELEASE_TAG="v23.10.3"
EQEMU_RELEASE_ZIP="https://github.com/EQEmu/EQEmu/releases/download/${EQEMU_RELEASE_TAG}/eqemu-server-linux-x64.zip"
AKK_STACK_REPO="https://github.com/EQEmu/akk-stack.git"
SPIRE_REPO="https://github.com/EQEmu/spire.git"
PEQ_QUESTS_REPO="https://github.com/ProjectEQ/projecteqquests.git"
PEQ_DB_REPO="https://github.com/ProjectEQ/peqphpeditor.git"
EQEMU_MAPS_REPO="https://github.com/EQEmu/zone-utilities.git"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
INSTALL_DIR="${HOME}/eqemu-server"
COMPONENTS="all"
METHOD="source"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
show_help() {
    sed -n '2,/^$/{ s/^# \?//; p }' "$0"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir)
            INSTALL_DIR="$2"; shift 2 ;;
        --components)
            COMPONENTS="$2"; shift 2 ;;
        --method)
            METHOD="$2"; shift 2 ;;
        --help|-h)
            show_help ;;
        *)
            error "Unknown option: $1"
            show_help ;;
    esac
done

# Validate method
case "$METHOD" in
    source|release|docker) ;;
    *)
        error "Invalid method: $METHOD (must be source, release, or docker)"
        exit 1 ;;
esac

# Expand components list
if [[ "$COMPONENTS" == "all" ]]; then
    COMP_LIST="server database quests maps spire"
else
    COMP_LIST="${COMPONENTS//,/ }"
fi

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------
header "Setting up directory structure at ${INSTALL_DIR}"

mkdir -p "${INSTALL_DIR}/server"
mkdir -p "${INSTALL_DIR}/quests"
mkdir -p "${INSTALL_DIR}/maps"
mkdir -p "${INSTALL_DIR}/database"
mkdir -p "${INSTALL_DIR}/spire"

success "Directory structure created"

# ---------------------------------------------------------------------------
# Helper: shallow git clone
# ---------------------------------------------------------------------------
shallow_clone() {
    local url="$1"
    local dest="$2"
    local branch="${3:-}"

    if [[ -d "${dest}/.git" ]]; then
        warn "Already cloned: ${dest} — pulling latest"
        if ! git -C "${dest}" pull --ff-only 2>&1; then
            warn "git pull failed for ${dest} — continuing with existing checkout"
        fi
        return 0
    fi

    # Remove non-git contents if directory exists but is not a repo
    if [[ -d "${dest}" ]]; then
        warn "Directory ${dest} exists but is not a git repo — replacing"
        rm -rf "${dest}"
    fi

    local clone_args=(clone --depth 1)
    if [[ -n "${branch}" ]]; then
        clone_args+=(--branch "${branch}")
    fi
    clone_args+=("${url}" "${dest}")

    info "Cloning ${url} → ${dest}"
    if git "${clone_args[@]}"; then
        success "Cloned $(basename "${url}" .git)"
        return 0
    else
        error "Failed to clone ${url}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Helper: download release ZIP
# ---------------------------------------------------------------------------
download_release() {
    local url="$1"
    local dest_dir="$2"
    local filename
    filename="$(basename "${url}")"
    local dest_file="${dest_dir}/${filename}"

    info "Downloading release asset: ${url}"
    if curl -fSL --progress-bar -o "${dest_file}" "${url}"; then
        success "Downloaded ${filename} ($(du -h "${dest_file}" | cut -f1))"
        # Attempt unzip if it's a zip file
        if [[ "${filename}" == *.zip ]]; then
            if command -v unzip &>/dev/null; then
                info "Extracting ${filename}..."
                unzip -qo "${dest_file}" -d "${dest_dir}"
                success "Extracted ${filename}"
            else
                warn "unzip not found — archive saved but not extracted"
            fi
        fi
        return 0
    else
        error "Failed to download ${url}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
TOTAL=0
OK=0
FAIL=0

track() {
    TOTAL=$((TOTAL + 1))
    if "$@"; then
        OK=$((OK + 1))
    else
        FAIL=$((FAIL + 1))
    fi
}

# ---------------------------------------------------------------------------
# Fetch each component
# ---------------------------------------------------------------------------
for comp in ${COMP_LIST}; do
    case "${comp}" in
        server)
            header "Fetching EQEmu Server (method=${METHOD})"
            case "${METHOD}" in
                source)
                    track shallow_clone "${EQEMU_SERVER_REPO}" "${INSTALL_DIR}/server" "master"
                    ;;
                release)
                    track download_release "${EQEMU_RELEASE_ZIP}" "${INSTALL_DIR}/server"
                    ;;
                docker)
                    header "Fetching akk-stack Docker environment"
                    track shallow_clone "${AKK_STACK_REPO}" "${INSTALL_DIR}/server"
                    ;;
            esac
            ;;

        database)
            header "Fetching PEQ Database"
            track shallow_clone "${PEQ_DB_REPO}" "${INSTALL_DIR}/database"
            ;;

        quests)
            header "Fetching PEQ Quests"
            track shallow_clone "${PEQ_QUESTS_REPO}" "${INSTALL_DIR}/quests"
            ;;

        maps)
            header "Fetching Zone Maps / Utilities"
            track shallow_clone "${EQEMU_MAPS_REPO}" "${INSTALL_DIR}/maps"
            ;;

        spire)
            header "Fetching Spire Web Toolkit"
            track shallow_clone "${SPIRE_REPO}" "${INSTALL_DIR}/spire" "master"
            ;;

        *)
            warn "Unknown component: ${comp} — skipping"
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
header "Fetch Summary"
printf "  Install directory : ${BOLD}%s${NC}\n" "${INSTALL_DIR}"
printf "  Method            : ${BOLD}%s${NC}\n" "${METHOD}"
printf "  Components        : ${BOLD}%s${NC}\n" "${COMP_LIST}"
printf "  Succeeded         : ${GREEN}%d${NC} / %d\n" "${OK}" "${TOTAL}"
if [[ ${FAIL} -gt 0 ]]; then
    printf "  Failed            : ${RED}%d${NC}\n" "${FAIL}"
fi

echo ""
info "Directory layout:"
ls -1d "${INSTALL_DIR}"/*/ 2>/dev/null | while read -r d; do
    printf "  📂 %s\n" "${d}"
done

if [[ ${FAIL} -gt 0 ]]; then
    error "Some components failed to download. Re-run with individual --components to retry."
    exit 1
fi

success "All done!"
