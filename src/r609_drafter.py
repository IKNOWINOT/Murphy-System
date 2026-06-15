#!/usr/bin/env python3
"""
Ship 31ca — R609 Drafter (the missing self-authoring link)

Reads pending r609 proposals → searches API catalogue + module catalogue
for candidates that could close the gap → drafts a PatchProposal via
murphy_self_patch_loop → marks the r609 proposal as 'drafted'.

The drafted PatchProposal lands at /api/self/proposals where the
founder approves/rejects. requires_human_review=True always.

Adjacent module — kernel hot path untouched. Reversible: delete this
file + remove systemd timer + restore self_patch_proposals.json from
the ship_31ca_* snapshot.

CITL-safe: never writes source files. Only drafts proposals for review.
"""
from __future__ import annotations
import json, sqlite3, logging, sys, re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/opt/Murphy-System")

SELF_PLAN_DB = "/var/lib/murphy-production/self_plan.db"
API_REGISTRY_DB = "/var/lib/murphy-production/api_registry.db"
WIRER_DB = "/var/lib/murphy-production/wirer_findings.db"

logging.basicConfig(level=logging.INFO, format="  %(message)s")
log = logging.getLogger("r609_drafter")
NOW = datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────────────────
# Catalogue search — find capabilities relevant to a gap
# ──────────────────────────────────────────────────────────

def search_api_registry(keywords: list[str], limit: int = 5) -> list[dict]:
    """Search the 4,778 sanitized APIs for ones matching the gap."""
    if not keywords: return []
    c = sqlite3.connect(f"file:{API_REGISTRY_DB}?mode=ro", uri=True)
    try:
        clauses, params = [], []
        for kw in keywords[:5]:
            clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?)")
            params += [f"%{kw.lower()}%"]*3
        sql = (f"SELECT id, name, description, base_url, tags FROM api_registry "
               f"WHERE status='active' AND ({' OR '.join(clauses)}) LIMIT ?")
        params.append(limit)
        rows = c.execute(sql, params).fetchall()
    except Exception as e:
        log.warning(f"  api_registry search failed: {e}")
        rows = []
    finally:
        c.close()
    return [{"id": r[0], "name": r[1], "desc": r[2], "url": r[3], "tags": r[4]} for r in rows]


def search_modules(keywords: list[str], limit: int = 5) -> list[str]:
    """Search src/*.py module names for capabilities matching the gap."""
    src = Path("/opt/Murphy-System/src")
    if not src.exists(): return []
    hits = []
    for kw in keywords[:5]:
        kw_l = kw.lower()
        for p in src.glob("*.py"):
            if kw_l in p.stem.lower() and str(p) not in hits:
                hits.append(str(p))
                if len(hits) >= limit: return hits
    return hits


# ──────────────────────────────────────────────────────────
# Read pending r609 proposals
# ──────────────────────────────────────────────────────────

def read_pending_proposals(owner: str = "platform_cto", limit: int = 5) -> list[dict]:
    """Read open proposals from r609's self_plan.db."""
    c = sqlite3.connect(f"file:{SELF_PLAN_DB}?mode=ro", uri=True)
    try:
        rows = c.execute(
            "SELECT proposal_id, title, description, affected_module, change_type, "
            "risk_level, context FROM proposals "
            "WHERE status='pending' AND context LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{owner}%", limit)
        ).fetchall()
    except Exception as e:
        log.warning(f"  self_plan query failed: {e}")
        rows = []
    finally:
        c.close()
    return [{"id": r[0], "title": r[1], "desc": r[2], "module": r[3],
             "change_type": r[4], "risk": r[5], "context": r[6]} for r in rows]


def mark_drafted(proposal_id: str):
    """Mark a r609 proposal as drafted so we don't redraft it."""
    c = sqlite3.connect(SELF_PLAN_DB)
    try:
        c.execute("UPDATE proposals SET status='drafted', processed_at=? "
                  "WHERE proposal_id=?", (NOW, proposal_id))
        c.commit()
    finally:
        c.close()


# ──────────────────────────────────────────────────────────
# Extract search keywords from a proposal
# ──────────────────────────────────────────────────────────

STOP = {"the","a","an","is","to","of","and","or","for","in","on","with","by",
        "be","that","this","it","as","at","from","module","file","module:",
        "gap","missing","needs","needed","should","would","could"}

def extract_keywords(text: str, n: int = 6) -> list[str]:
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", text or "")
    out, seen = [], set()
    for w in words:
        wl = w.lower()
        if wl in STOP or wl in seen: continue
        seen.add(wl); out.append(w)
        if len(out) >= n: break
    return out


# ──────────────────────────────────────────────────────────
# Draft → file with murphy_self_patch_loop
# ──────────────────────────────────────────────────────────

def draft_one(proposal: dict) -> str | None:
    """Build a PatchProposal from a r609 proposal + catalogue search, file it."""
    title = proposal.get("title") or "(no title)"
    desc  = proposal.get("desc") or ""
    affected = proposal.get("module") or ""

    keywords = extract_keywords(f"{title} {desc} {affected}")
    if not keywords:
        log.info(f"  no keywords from proposal {proposal['id']} — skipping")
        return None

    api_hits = search_api_registry(keywords)
    mod_hits = search_modules(keywords)

    if not api_hits and not mod_hits:
        log.info(f"  no catalogue match for {proposal['id']} ({title[:50]})")
        return None

    # Build the proposed change description
    parts = [f"R609 gap: {title}", "", f"Description: {desc[:300]}", ""]
    if affected: parts.append(f"Affected module: {affected}")
    parts.append("")
    parts.append("CANDIDATES FROM CATALOGUE:")
    if mod_hits:
        parts.append("\nExisting Murphy modules (may already solve this):")
        for m in mod_hits[:3]:
            parts.append(f"  - {m}")
    if api_hits:
        parts.append("\nAPIs from registry (4,778 sanitized) that could help:")
        for a in api_hits[:3]:
            parts.append(f"  - {a['name']} ({a['url']}): {(a['desc'] or '')[:120]}")
    parts.append("")
    parts.append("RECOMMENDED ACTION: Founder review — pick which candidate fits,")
    parts.append("then approve a follow-on patch that wires it. This proposal does")
    parts.append("NOT modify source. It is a research-and-recommend artifact only.")

    proposed_change = "\n".join(parts)

    # File via murphy_self_patch_loop
    try:
        from src.murphy_self_patch_loop import (
            PatchProposal, PatchKind, add_proposal, _save_store)
        pp = PatchProposal(
            symptom=f"R609 identified gap: {title[:120]}",
            diagnosis=desc[:500],
            affected_file=affected or "(unknown — needs scoping)",
            affected_function="(to be determined by founder)",
            patch_kind=PatchKind.CODE_DIFF,
            proposed_change=proposed_change,
            unified_diff="",  # drafter never writes diffs — that's a follow-on
            rationale=f"Drafted by r609_drafter from r609 proposal {proposal['id']}. "
                      f"Catalogue search returned {len(mod_hits)} module hits + "
                      f"{len(api_hits)} API hits.",
            risk_level="LOW",  # research artifact only
            requires_human_review=True,
        )
        add_proposal(pp)
        _save_store()
        return pp.proposal_id
    except Exception as e:
        log.warning(f"  failed to file PatchProposal: {e}")
        return None


# ──────────────────────────────────────────────────────────
# Main loop — called by systemd timer
# ──────────────────────────────────────────────────────────

def run_cycle(limit: int = 5) -> dict:
    log.info(f"r609_drafter cycle @ {NOW}")
    pending = read_pending_proposals(limit=limit)
    log.info(f"  read {len(pending)} pending r609 proposals")
    drafted, skipped = [], []
    for p in pending:
        pid = draft_one(p)
        if pid:
            drafted.append((p["id"], pid))
            mark_drafted(p["id"])
            log.info(f"  ✅ drafted: r609={p['id'][:12]} → patch={pid}")
        else:
            skipped.append(p["id"])
    summary = {"timestamp": NOW, "pending_read": len(pending),
               "drafted": len(drafted), "skipped": len(skipped),
               "drafted_ids": drafted}
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_cycle()
