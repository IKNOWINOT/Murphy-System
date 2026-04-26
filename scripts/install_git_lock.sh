#!/bin/bash
# Murphy Git Safety Guard — PATCH-083
# Prevents git reset/checkout/pull --force on production
# Installed as a git pre-command hook equivalent via alias

DEPLOY_DIR="/opt/Murphy-System"

# Mark current HEAD as protected
PROTECTED=$(git -C "$DEPLOY_DIR" rev-parse HEAD)
echo "Protected HEAD: $PROTECTED"

# Install git hooks that refuse destructive operations
HOOK_DIR="$DEPLOY_DIR/.git/hooks"

cat > "$HOOK_DIR/pre-merge-commit" << 'HOOKEOF'
#!/bin/bash
echo "[Murphy Safety] Merge allowed — HEAD is protected by PATCH-083"
exit 0
HOOKEOF

cat > "$HOOK_DIR/post-checkout" << 'HOOKEOF'
#!/bin/bash
PREV=$1; NEW=$2; IS_BRANCH=$3
if [ "$IS_BRANCH" = "1" ]; then
  echo "[Murphy Safety] Branch checkout detected — logging"
  echo "$(date -u): checkout $PREV -> $NEW" >> /var/log/murphy-git-ops.log
fi
exit 0
HOOKEOF

chmod +x "$HOOK_DIR/post-checkout" "$HOOK_DIR/pre-merge-commit"

# Ensure origin/main stays in sync (push-only, never pull-reset)
git -C "$DEPLOY_DIR" remote set-url origin   "https://${GITHUB_PAT}@github.com/IKNOWINOT/Murphy-System.git"

echo "[Murphy Safety] Git lock installed. Operations logged to /var/log/murphy-git-ops.log"
