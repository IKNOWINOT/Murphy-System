#!/usr/bin/env python3
"""
lead_quality_audit.py — Classify real-domain CRM leads by quality.
PATCH-LEAD-QUALITY-AUDIT 2026-05-27
"""
import json, re, sqlite3, sys
CRM_DB = "/var/lib/murphy-production/crm.db"

ROLE_PREFIXES = ("sales@","info@","hello@","support@","contact@","admin@",
                 "agent@","team@","hi@","orders@","partners@","partner@",
                 "operations@","founders@","startups@","wellsglobal@",
                 "info.tkeuk@")  # last is the tkelevator one

DECISION_MAKER_TITLES = ("founder","ceo","cto","coo","cfo","president",
                         "owner","vp","head of","chief")
OPERATOR_TITLES = ("director","manager","lead","operator","superintendent")

def _parse_notes(notes):
    """Extract structured fields from 'Source: X | ICP: N | Title: Y | URL: Z'."""
    out = {}
    if not notes: return out
    for part in notes.split("|"):
        part = part.strip()
        if ":" in part:
            k, _, v = part.partition(":")
            out[k.strip().lower()] = v.strip()
    return out

def _email_pattern(email):
    if not email: return "unknown"
    low = email.lower()
    if any(low.startswith(p) for p in ROLE_PREFIXES): return "role"
    return "personal"

def _title_kind(title_str):
    if not title_str: return "unknown"
    low = title_str.lower()
    if any(t in low for t in DECISION_MAKER_TITLES): return "decision_maker"
    if any(t in low for t in OPERATOR_TITLES): return "operator"
    return "other"

def _score(lead):
    """A=top, B=workable, C=skip."""
    score = 0
    if lead["email_pattern"] == "personal": score += 2
    if lead["title_kind"] == "decision_maker": score += 2
    if lead["title_kind"] == "operator": score += 1
    if lead["icp"] >= 60: score += 2
    elif lead["icp"] >= 45: score += 1
    if lead["has_url"]: score += 1
    if lead["email_status"] == "valid": score += 1
    if lead["email_status"] == "bounced_invalid": score -= 3
    
    if score >= 6: return "A"
    if score >= 4: return "B"
    return "C"

def run():
    con = sqlite3.connect(CRM_DB)
    rows = con.execute("""
        SELECT c.id, c.email, c.name, c.company, c.email_status,
               d.id AS deal_id, d.value, d.notes, d.stage
        FROM contacts c JOIN deals d ON d.contact_id = c.id
        WHERE d.archived = 0 AND c.contact_type = 'lead'
    """).fetchall()
    
    leads = []
    for r in rows:
        notes_parsed = _parse_notes(r[7])
        title = notes_parsed.get("title", "")
        try:
            icp = int(re.search(r"\d+", notes_parsed.get("icp","0")).group())
        except (AttributeError, ValueError):
            icp = 0
        url = notes_parsed.get("url", "")
        lead = {
            "deal_id": r[5],
            "contact_id": r[0],
            "email": r[1],
            "name": r[2] or "",
            "company": r[3] or "",
            "value": r[6],
            "email_status": r[4] or "unknown",
            "source": notes_parsed.get("source",""),
            "icp": icp,
            "title": title,
            "title_kind": _title_kind(title),
            "email_pattern": _email_pattern(r[1]),
            "has_url": bool(url and url.startswith("http")),
            "url": url[:80],
        }
        lead["tier"] = _score(lead)
        leads.append(lead)
    
    leads.sort(key=lambda x: ({"A":0,"B":1,"C":2}[x["tier"]], -x["value"], -x["icp"]))
    
    summary = {
        "total": len(leads),
        "tier_A": sum(1 for l in leads if l["tier"]=="A"),
        "tier_B": sum(1 for l in leads if l["tier"]=="B"),
        "tier_C": sum(1 for l in leads if l["tier"]=="C"),
        "by_source": {},
        "by_email_pattern": {},
    }
    for l in leads:
        summary["by_source"][l["source"]] = summary["by_source"].get(l["source"],0) + 1
        summary["by_email_pattern"][l["email_pattern"]] = summary["by_email_pattern"].get(l["email_pattern"],0) + 1
    
    return {"summary": summary, "leads": leads}

if __name__ == "__main__":
    out = run()
    print(json.dumps(out, indent=2))
