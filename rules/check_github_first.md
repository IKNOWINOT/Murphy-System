# Rule: Check GitHub First (LOCKED 2026-05-25)

## Founder directive (verbatim)
"Every time you do work look for the outline of what I'm describing in
the GitHub first."

## Why
Murphy's primary source of truth is the GitHub repo, not just the running
codebase on the server. Patches, design docs, outlines, and architectural
intent live in the repo. Checking the server only (with grep) showed me
the *built* state but missed the *intended* state. The founder corrected
me twice in one session for proposing things that were already designed
or in progress in the repo.

## The repo
- **GitHub URL:** https://github.com/IKNOWINOT/Murphy-System
- **Server clone:** /opt/Murphy-System (checked out, kept current via git pull)
- **License:** BSL 1.1, © Inoni LLC

## Workflow BEFORE proposing or building anything

### Step 1 — search the repo for the concept
```bash
ssh -i /app/murphy_key root@5.78.41.114 'cd /opt/Murphy-System && git pull --quiet 2>&1 | tail -3'

# Then search across the whole repo (not just src/)
ssh -i /app/murphy_key root@5.78.41.114 'cd /opt/Murphy-System && \
    grep -rli "<concept>" . --include="*.py" --include="*.md" \
                          --include="*.txt" --include="*.yaml" \
                          --include="*.json" 2>/dev/null | head -20'
```

### Step 2 — check for design docs / outlines
```bash
ssh -i /app/murphy_key root@5.78.41.114 'cd /opt/Murphy-System && \
    find docs/ outlines/ design/ patches/ -type f 2>/dev/null | \
    xargs grep -li "<concept>" 2>/dev/null | head -10'
```

### Step 3 — check open issues / PRs (when needed)
Use `gh` CLI on the server if installed, otherwise fetch via the GitHub
REST API with a personal access token (founder may need to supply one).

### Step 4 — check recent commits for related work
```bash
ssh -i /app/murphy_key root@5.78.41.114 'cd /opt/Murphy-System && \
    git log --oneline --all --since="14 days ago" | head -20'

ssh -i /app/murphy_key root@5.78.41.114 'cd /opt/Murphy-System && \
    git log --all --grep="<concept>" --oneline | head -10'
```

### Step 5 — only THEN propose

Only after Steps 1-4 come up empty should I propose new architecture.
If anything turns up, my proposal must START with "I found X — here's
how I'll extend/connect to it" rather than "let me build Y from scratch."

## What to report back to founder

When I find an existing outline / module / patch, surface:
- File path(s) found
- Brief summary of what it covers
- Gap between what exists and what the founder is asking for
- Specific extension plan that connects to existing code

When nothing is found:
- State explicitly: "I checked the repo and found no existing outline for X"
- Then propose

## Companion rule
This complements the existing rule from memory.md:
"CHECK EXISTING ARCHITECTURE FIRST — grep -rlE in /opt/Murphy-System/src"

The grep rule covers the *built code*. This rule covers the *whole repo*
including docs, outlines, and historical patches that may not yet be built.
