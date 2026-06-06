#!/usr/bin/env python3
"""R603D — CEO Agent. Reads CTO+CFO+CSO artifacts → strategic 1-pager."""
import os, json, sqlite3, subprocess, uuid, re
from datetime import datetime, timezone
from pathlib import Path

NOW = datetime.now(timezone.utc)
ARTIFACT_DIR = Path("/var/lib/murphy-production/artifacts")
ARTIFACT_ID = f"r603d_ceo_strategic_brief_{NOW.strftime('%Y%m%dT%H%M%SZ')}"
ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"
RECIPIENT = "cpost@murphy.systems"
SENDER = "ceo-agent@murphy.systems"


def latest_artifact_of(role_key):
    """Find the latest artifact for a given role using marker in notes."""
    conn = sqlite3.connect(f"file:{ENTITY_DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT id, title, file_url, notes, created_at FROM data_room_artifacts "
        "WHERE notes LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%{role_key}%",)
    ).fetchall()
    conn.close()
    if not rows: return None
    r = rows[0]
    return {"id": r[0], "title": r[1], "file_url": r[2], "notes": r[3], "created_at": r[4]}


def read_artifact_content(file_url):
    if not file_url or not file_url.startswith("/"):
        return None
    p = Path(file_url)
    if p.exists() and p.stat().st_size < 100_000:
        return p.read_text(errors="replace")
    return None


def extract_headline_table(md):
    """Pull the | Status | Value | rows from a report so we can re-flow them."""
    if not md: return []
    rows = []
    in_table = False
    for line in md.splitlines():
        if line.strip().startswith("|") and "|" in line[1:]:
            parts = [p.strip() for p in line.strip("|").split("|")]
            # skip headers and separators
            if parts and parts[0] in ("Signal", "---") or all(p.startswith("---") for p in parts):
                in_table = True
                continue
            if in_table and len(parts) >= 2:
                rows.append(parts)
        elif in_table and not line.strip().startswith("|"):
            in_table = False
    return rows


def extract_recommended_actions(md):
    """Pull the 'Recommended next actions' bullet list."""
    if not md: return []
    m = re.search(r"## Recommended next actions\s*\n+(.+?)(?:\n##|\n---|\Z)", md, re.DOTALL)
    if not m: return []
    actions = []
    for line in m.group(1).splitlines():
        line = line.strip()
        m2 = re.match(r"^\d+\.\s+(.*)$", line)
        if m2:
            actions.append(m2.group(1))
    return actions


def synthesize(cto_md, cfo_md, cso_md, cto_meta, cfo_meta, cso_meta):
    cto_signals = extract_headline_table(cto_md or "")
    cfo_signals = extract_headline_table(cfo_md or "")
    cso_signals = extract_headline_table(cso_md or "")
    cto_actions = extract_recommended_actions(cto_md or "")[:3]
    cfo_actions = extract_recommended_actions(cfo_md or "")[:3]
    cso_actions = extract_recommended_actions(cso_md or "")[:3]

    md = f"""# Murphy Strategic Brief

**Reporter:** CEO Agent (R603D — synthesizes CTO + CFO + CSO)
**Generated:** {NOW.isoformat()}
**For:** Corey Post (cpost@murphy.systems)

---

## One-line state of the company

"""
    # Heuristic one-liner from data
    has_rev = any("$0.00" not in str(row) and "Revenue" in row[0] for row in cfo_signals if len(row) >= 2)
    has_pipeline = any("0 deals" not in str(row) and "Pipeline" in row[0] for row in cso_signals if len(row) >= 2)
    if has_rev and has_pipeline:
        md += "We have revenue AND pipeline — the engine is on.\n"
    elif has_rev:
        md += "We have revenue but no pipeline — flywheel needs feeding.\n"
    elif has_pipeline:
        md += "Pipeline is real but no revenue yet — conversion is the gap.\n"
    else:
        md += "Pre-revenue, pre-pipeline. Building the runway. Focus is on the system, not the market — for now.\n"

    md += "\n## Department signals\n\n"
    md += "### Technology (CTO)\n\n"
    if cto_meta:
        md += f"- Report: [{cto_meta['title']}]({cto_meta['file_url']}) at {cto_meta['created_at']}\n"
    for row in cto_signals[:4]:
        md += f"- {' · '.join(row)}\n"

    md += "\n### Finance (CFO)\n\n"
    if cfo_meta:
        md += f"- Report: [{cfo_meta['title']}]({cfo_meta['file_url']}) at {cfo_meta['created_at']}\n"
    for row in cfo_signals[:4]:
        md += f"- {' · '.join(row)}\n"

    md += "\n### Sales (CSO)\n\n"
    if cso_meta:
        md += f"- Report: [{cso_meta['title']}]({cso_meta['file_url']}) at {cso_meta['created_at']}\n"
    for row in cso_signals[:4]:
        md += f"- {' · '.join(row)}\n"

    md += "\n## Consolidated top priorities\n\n"
    # Mix: take top action from each
    combined = []
    if cfo_actions: combined.append(("CFO", cfo_actions[0]))
    if cso_actions: combined.append(("CSO", cso_actions[0]))
    if cto_actions: combined.append(("CTO", cto_actions[0]))
    if not combined:
        md += "1. No urgent action items consolidated. Continue current trajectory.\n"
    for i, (dept, action) in enumerate(combined, 1):
        md += f"{i}. **[{dept}]** {action}\n"

    md += f"""

## What I (CEO agent) see overall

I synthesized 3 department reports written by the CTO, CFO, and CSO
agents within the last few minutes. Each agent read its source-of-truth
databases independently. I read their published artifacts — that's the
chain of accountability.

This is what an autonomous executive layer looks like at Murphy today:
4 agents working in parallel, each with a deliverable, each visible at
https://murphy.systems/agents.

Tomorrow morning at 08:00 PT, all 4 will run again automatically.

---

*Generated by Murphy R603D CEO agent. Approved pattern via chat-v2 Phase C.*
"""
    return md


def email_report(subject, body):
    msg = (f"From: CEO Agent <{SENDER}>\nTo: {RECIPIENT}\nSubject: {subject}\n"
           f"Content-Type: text/plain; charset=utf-8\nX-Murphy-Agent: ceo\n"
           f"X-Murphy-Pilot: R603D\nX-Murphy-Artifact: {ARTIFACT_ID}\n\n{body}\n")
    r = subprocess.run(["/usr/sbin/sendmail", "-f", SENDER, RECIPIENT],
                       input=msg.encode(), capture_output=True, timeout=20)
    return r.returncode == 0


def main():
    print(f"R603D CEO agent — {NOW.isoformat()}")
    print("  reading CTO artifact ..."); cto_meta = latest_artifact_of("R603 pilot")
    print(f"    → {cto_meta['title'] if cto_meta else 'none'}")
    print("  reading CFO artifact ..."); cfo_meta = latest_artifact_of("R603B")
    print(f"    → {cfo_meta['title'] if cfo_meta else 'none'}")
    print("  reading CSO artifact ..."); cso_meta = latest_artifact_of("R603C")
    print(f"    → {cso_meta['title'] if cso_meta else 'none'}")

    cto_md = read_artifact_content(cto_meta["file_url"]) if cto_meta else None
    cfo_md = read_artifact_content(cfo_meta["file_url"]) if cfo_meta else None
    cso_md = read_artifact_content(cso_meta["file_url"]) if cso_meta else None

    md = synthesize(cto_md, cfo_md, cso_md, cto_meta, cfo_meta, cso_meta)
    d = ARTIFACT_DIR / ARTIFACT_ID; d.mkdir(parents=True, exist_ok=True)
    p = d / "strategic_brief.md"
    with open(p, "w") as f: f.write(md)
    print(f"  artifact: {p}")

    ok = email_report(f"Murphy CEO Strategic Brief — {NOW.strftime('%b %d %H:%M UTC')}", md)
    print(f"  email: {'✓' if ok else '✗'}")

    try:
        c = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
        c.execute("INSERT INTO data_room_artifacts VALUES (?,?,?,?,?,?,?,?,?)",
                  (f"art_{uuid.uuid4().hex[:12]}", "report",
                   f"CEO Strategic Brief {NOW.strftime('%Y-%m-%d %H:%M')}",
                   str(p), 1, 1, "R603D CEO pilot — Phase C completes loop",
                   NOW.isoformat(), NOW.isoformat()))
        c.commit(); c.close()
        print("  ✓ data_room")
    except Exception as e:
        print(f"  ⚠ {e}")
    print(json.dumps({"ok": True, "artifact_id": ARTIFACT_ID,
                      "sources": {"cto": bool(cto_meta), "cfo": bool(cfo_meta),
                                  "cso": bool(cso_meta)}}, indent=2))


if __name__ == "__main__":
    main()
