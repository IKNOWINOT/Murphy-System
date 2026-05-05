"""
illuminate_router.py — Illuminate API Routes (PATCH-192)
Mounts at /api/illuminate/*
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

logger = logging.getLogger("illuminate_router")
router = APIRouter(prefix="/api/illuminate", tags=["illuminate"])


def _il():
    try:
        import src.illuminate as il
    except ImportError:
        import illuminate as il
    il.ensure_tables()
    return il


# ── Domain Search ────────────────────────────────────────────────────────────
@router.get("/domain-search")
async def domain_search(domain: str, verify: bool = False):
    """Find all emails at a company domain."""
    try:
        result = _il().domain_search(domain, verify=verify)
        return JSONResponse({"success": True, **result})
    except Exception as e:
        logger.error("[Illuminate] domain_search error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Email Finder ─────────────────────────────────────────────────────────────
@router.get("/email-finder")
async def email_finder(first: str, last: str, domain: str, verify: bool = True):
    """Find the most likely email for a person at a company."""
    try:
        result = _il().email_finder(first, last, domain, verify=verify)
        return JSONResponse({"success": True, **result})
    except Exception as e:
        logger.error("[Illuminate] email_finder error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Email Verifier ───────────────────────────────────────────────────────────
@router.get("/verify")
async def email_verify(email: str):
    """Verify a single email address."""
    try:
        result = _il().email_verifier(email)
        return JSONResponse({"success": True, **result})
    except Exception as e:
        logger.error("[Illuminate] verify error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Bulk Domain Search ───────────────────────────────────────────────────────
@router.post("/bulk-search")
async def bulk_search(request: Request):
    """Bulk domain search. Body: {domains: [str], verify: bool}"""
    try:
        body = await request.json()
        domains = body.get("domains", [])
        verify  = body.get("verify", False)
        if not domains:
            return JSONResponse({"success": False, "error": "domains required"}, status_code=400)
        results = _il().bulk_domain_search(domains, verify=verify)
        return JSONResponse({"success": True, "results": results, "count": len(results)})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Stats ────────────────────────────────────────────────────────────────────
@router.get("/stats")
async def illuminate_stats():
    """Return Illuminate database statistics."""
    try:
        stats = _il().get_stats()
        return JSONResponse({"success": True, **stats})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── List contacts ────────────────────────────────────────────────────────────
@router.get("/contacts")
async def list_contacts(domain: Optional[str] = None, limit: int = 50, verified_only: bool = False):
    """List discovered contacts, optionally filtered by domain."""
    try:
        import sqlite3 as _sq
        with _sq.connect("/var/lib/murphy-production/illuminate.db", timeout=5) as conn:
            conn.row_factory = _sq.Row
            q = "SELECT * FROM il_contacts WHERE 1=1"
            params = []
            if domain:
                q += " AND domain=?"
                params.append(domain)
            if verified_only:
                q += " AND verified=1"
            q += " ORDER BY found_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
        return JSONResponse({"success": True, "count": len(rows), "contacts": [dict(r) for r in rows]})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Push to CRM ──────────────────────────────────────────────────────────────
@router.post("/push-to-crm")
async def push_to_crm(request: Request):
    """
    Push Illuminate contacts to Murphy CRM as prospects.
    Body: {contact_ids: [str]} or {domain: str} to push all from a domain.
    """
    try:
        body    = await request.json()
        ids     = body.get("contact_ids", [])
        domain  = body.get("domain", "")
        import sqlite3 as _sq, uuid, json
        from datetime import datetime, timezone

        with _sq.connect("/var/lib/murphy-production/illuminate.db", timeout=5) as conn:
            conn.row_factory = _sq.Row
            if ids:
                placeholders = ",".join("?" * len(ids))
                rows = conn.execute(f"SELECT * FROM il_contacts WHERE id IN ({placeholders})", ids).fetchall()
            elif domain:
                rows = conn.execute("SELECT * FROM il_contacts WHERE domain=? AND dnc_blocked=0", (domain,)).fetchall()
            else:
                return JSONResponse({"success": False, "error": "contact_ids or domain required"}, status_code=400)

        pushed = 0
        skipped = 0
        with _sq.connect("/var/lib/murphy-production/crm.db", timeout=5) as crm:
            for row in rows:
                email = row["email"]
                # DNC check
                existing = crm.execute("SELECT id FROM contacts WHERE LOWER(email)=?", (email.lower(),)).fetchone()
                if existing:
                    skipped += 1
                    continue
                cid = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                tags = json.dumps(["illuminate", f"icp_{row['icp_score']}", row["source"]])
                custom = json.dumps({
                    "icp_score": row["icp_score"],
                    "confidence": row["confidence"],
                    "source": row["source"],
                    "illuminate_id": row["id"],
                })
                crm.execute(
                    "INSERT INTO contacts (id,name,email,phone,company,contact_type,tags,custom_fields,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (cid, row["full_name"] or row["email"], email, "", row["company"],
                     "prospect", tags, custom, now)
                )
                pushed += 1
            crm.commit()

        return JSONResponse({"success": True, "pushed": pushed, "skipped": skipped})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
