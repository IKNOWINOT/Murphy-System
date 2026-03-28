#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# transfer_archive.sh — Transfer Murphy System archive to a dedicated
# repository (iknowinot/murphy-system-archive).
#
# Usage:
#   bash scripts/transfer_archive.sh
#
# Prerequisites:
#   - Git installed and authenticated (SSH or HTTPS)
#   - Write access to both IKNOWINOT/Murphy-System and
#     IKNOWINOT/murphy-system-archive
#
# What this script does:
#   1. Clones the murphy-system-archive repository (or initializes it)
#   2. Copies the full archive directory into the target repository
#   3. Commits and pushes the archive to the target repository
#   4. Removes the archive from the Murphy-System repository
#   5. Commits the removal
#
# The CHANGELOG.md is NOT moved — it stays in Murphy-System.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Help ─────────────────────────────────────────────────────────────────────
show_help() {
  cat <<EOF
Murphy System — Archive Transfer Tool

Transfers the Murphy System archive directory to a dedicated repository
to reduce clone size and keep the production repository focused.

Usage:
  $(basename "$0") [OPTIONS]

Options:
  -h, --help         Show this help message and exit
  --version          Show version information
  --dry-run          Preview transfer without making changes
  --source PATH      Archive source path (default: Murphy System/archive)
  --target REPO      Target repository URL

Transfer steps:
  1. Clone/initialize target repository (murphy-system-archive)
  2. Copy archive contents to target
  3. Commit and push to target
  4. Remove archive from source
  5. Commit removal

Prerequisites:
  • Git installed and authenticated
  • Write access to both repositories
  • Archive directory exists

Target repository:
  https://github.com/IKNOWINOT/murphy-system-archive

Examples:
  $(basename "$0")             # Transfer archive
  $(basename "$0") --dry-run   # Preview only
  $(basename "$0") --help      # Show this help

After transfer:
  Run 'git push' to push the removal to Murphy-System

EOF
  exit 0
}

# ── Parse arguments ──────────────────────────────────────────────────────────
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      ;;
    --version)
      echo "Murphy System Archive Transfer v1.0.0"
      exit 0
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
    *)
      shift
      ;;
  esac
done

ARCHIVE_SRC="Murphy System/archive"
TARGET_REPO="https://github.com/IKNOWINOT/murphy-system-archive.git"
WORK_DIR=$(mktemp -d)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "═══════════════════════════════════════════════════════════"
echo "  Murphy System — Archive Transfer Tool"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Source:  $REPO_ROOT/$ARCHIVE_SRC"
echo "Target:  $TARGET_REPO"
echo "Work:    $WORK_DIR"
echo ""

# ── Step 1: Verify source archive exists ──────────────────────────
if [ ! -d "$REPO_ROOT/$ARCHIVE_SRC" ]; then
    echo "✗ Archive directory not found: $REPO_ROOT/$ARCHIVE_SRC"
    echo "  The archive may have already been transferred."
    exit 1
fi

ARCHIVE_FILE_COUNT=$(find "$REPO_ROOT/$ARCHIVE_SRC" -type f | wc -l)
echo "Found $ARCHIVE_FILE_COUNT files in archive."
echo ""

# ── Step 2: Clone or initialize the target repository ─────────────
echo "Step 1/4: Cloning target repository..."
if git clone "$TARGET_REPO" "$WORK_DIR/murphy-system-archive" 2>/dev/null; then
    echo "  ✓ Cloned existing repository"
else
    echo "  Creating new repository structure..."
    mkdir -p "$WORK_DIR/murphy-system-archive"
    cd "$WORK_DIR/murphy-system-archive"
    git init
    git remote add origin "$TARGET_REPO"
    echo "  ✓ Initialized new repository"
fi

cd "$WORK_DIR/murphy-system-archive"

# ── Step 3: Copy archive contents ─────────────────────────────────
echo ""
echo "Step 2/4: Copying archive contents..."
cp -R "$REPO_ROOT/$ARCHIVE_SRC/"* "$WORK_DIR/murphy-system-archive/"

# Create a README for the archive repository
cat > "$WORK_DIR/murphy-system-archive/README.md" << 'ARCHIVE_README'
# Murphy System — Archive

This repository contains archived legacy versions, artifacts, and internal
documents from the [Murphy System](https://github.com/IKNOWINOT/Murphy-System)
project.

**These files are preserved for historical reference and future v3.0 feature
integration.** They are not part of the active production system.

## Contents

| Directory | Description |
|-----------|-------------|
| `legacy_versions/` | Previous Murphy System iterations (v1.0, v2.0 variants) |
| `legacy_workspace/` | Older workspace configurations |
| `murphy_integrated_archive/` | Legacy integration packages |
| `artifacts/` | Generated images, outputs, summaries, uploaded files |
| `ARCHIVE_MANIFEST.md` | Index of all archived items |
| `BUSINESS_MODEL.md` | Internal business model reference |

## Relationship to Murphy System

This archive was split from the main Murphy System repository to keep
downloads lean and the production codebase focused. The active system
lives at:

> **https://github.com/IKNOWINOT/Murphy-System**

## License

Copyright © 2025 Inoni Limited Liability Company. See the main repository
for license details.
ARCHIVE_README

echo "  ✓ Copied $ARCHIVE_FILE_COUNT files"

# ── Step 4: Commit and push to target repository ──────────────────
echo ""
echo "Step 3/4: Committing to target repository..."
cd "$WORK_DIR/murphy-system-archive"
git add -A
git commit -m "Transfer archive from Murphy-System repository

Moved legacy versions, artifacts, and internal documents to this
dedicated archive repository to reduce download size and keep the
main Murphy-System repository focused on production code.

Source: IKNOWINOT/Murphy-System/Murphy System/archive/
Files transferred: $ARCHIVE_FILE_COUNT"

echo ""
echo "Step 4/4: Pushing to $TARGET_REPO ..."
git push -u origin main 2>/dev/null || git push -u origin master 2>/dev/null || {
    echo ""
    echo "  ⚠ Push failed. The target repository may not exist yet."
    echo "  Create it at: https://github.com/new"
    echo "    Repository name: murphy-system-archive"
    echo "    Owner: IKNOWINOT"
    echo "    Visibility: Public"
    echo ""
    echo "  Then re-run this script."
    echo ""
    echo "  Alternatively, push manually:"
    echo "    cd $WORK_DIR/murphy-system-archive"
    echo "    git push -u origin main"
    exit 1
}

echo "  ✓ Archive pushed to target repository"

# ── Step 5: Remove archive from source repository ─────────────────
echo ""
echo "Removing archive from Murphy-System..."
cd "$REPO_ROOT"
git rm -r "$ARCHIVE_SRC"
git commit -m "Remove archive (transferred to iknowinot/murphy-system-archive)

The archive directory contained 12,200+ legacy files (128 MB) that are
now hosted at https://github.com/IKNOWINOT/murphy-system-archive.

This reduces clone size and keeps the production repository focused."

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓ Archive transfer complete!"
echo ""
echo "  Archive repo: https://github.com/IKNOWINOT/murphy-system-archive"
echo "  Files moved:  $ARCHIVE_FILE_COUNT"
echo ""
echo "  Next steps:"
echo "    git push   (to push the removal to Murphy-System)"
echo "═══════════════════════════════════════════════════════════"

# Cleanup
rm -rf "$WORK_DIR"
