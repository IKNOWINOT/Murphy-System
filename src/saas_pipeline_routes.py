""
PATCH-327 — Owner-Operator SaaS Pipeline Routes
"""
import uuid
import sqlite3
import json
from datetime import datetime, timedelta
from fastapi import Request
from starlette.responses import JSONResponse

SaaS_DB = "/var/lib/murphy-production/crm.db"

def register_saas_routes(app):
    """Register SaaS pipeline routes as public (no auth required)."""
    
    # Mark these routes as public by registering them on the app without middleware
    
    @app.post("/api/saas/lead", tags=["public"])
    async def saas_lead(request: Request):
        """POST /api/saas/lead - Capture inbound lead from website form."""
        try:
            data = await request.json()
        except:
            data = {}
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return JSONResponse({"error": "Valid email required"}, status_code=400)
        
        # Score lead (1-10)
        score = 5
        if data.get("company_size", 0) >= 50: score += 3
        elif data.get("company_size", 0) >= 20: score += 2
        elif data.get("company_size", 0) >= 10: score += 1
        if any(i in (data.get("industry") or "").lower() for i in ["manuf", "finance", "health", "energy", "logistics"]): score += 2
        if data.get("annual_revenue", 0) >= 10000000: score += 2
        elif data.get("annual_revenue", 0) >= 1000000: score += 1
        if any(c in (data.get("use_case") or "").lower() for c in ["lead", "appoint", "proposal", "automat"]): score += 1
        if data.get("team_size", 0) >= 20: score += 2
        elif data.get("team_size", 0) >= 10: score += 1
        score = min(10, max(1, score))
        
        routing = "nurture" if score < 7 else ("book" if score <= 9 else "enterprise")
        
        try:
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT id FROM saas_subscribers WHERE email=?", (email,))
            existing = cur.fetchone()
            
            if existing:
                subscriber_id = existing[0]
                cur.execute("UPDATE saas_subscribers SET company_name=?, contact_name=?, phone=?, lead_score=?, status=?, updated_at=datetime('now') WHERE email=?",
                    (data.get("company_name"), data.get("contact_name"), data.get("phone"), score, routing, email))
            else:
                subscriber_id = str(uuid.uuid4())
                cur.execute("INSERT INTO saas_subscribers (id, email, company_name, contact_name, phone, lead_score, status, source, notes) VALUES (?, ?, ?, ?, ?, ?, ?, 'website_form', ?)",
                    (subscriber_id, email, data.get("company_name"), data.get("contact_name"), data.get("phone"), score, routing, data.get("notes", "")))
            
            conn.commit()
            conn.close()
            return JSONResponse({"subscriber_id": subscriber_id, "email": email, "lead_score": score, "routing": routing}, status_code=201)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.get("/api/saas/lead-score/{email}", tags=["public"])
    async def saas_lead_score(email: str):
        """GET /api/saas/lead-score/{email} - Look up lead score."""
        try:
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT id, lead_score, status FROM saas_subscribers WHERE email=?", (email.lower(),))
            row = cur.fetchone()
            conn.close()
            if not row:
                return JSONResponse({"error": "Not found"}, status_code=404)
            return JSONResponse({"subscriber_id": row[0], "lead_score": row[1], "status": row[2]})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.post("/api/saas/appointment/book", tags=["public"])
    async def saas_book_appt(request: Request):
        """POST /api/saas/appointment/book - Book discovery call."""
        try:
            data = await request.json()
            subscriber_id = data.get("subscriber_id", "")
            if not subscriber_id:
                return JSONResponse({"error": "subscriber_id required"}, status_code=400)
            
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT email, contact_name FROM saas_subscribers WHERE id=?", (subscriber_id,))
            sub = cur.fetchone()
            if not sub:
                conn.close()
                return JSONResponse({"error": "Subscriber not found"}, status_code=404)
            
            appt_id = str(uuid.uuid4())
            cur.execute("INSERT INTO appointments (id, contact_id, name, email, slot_date, slot_time, status, source) VALUES (?, ?, ?, ?, ?, ?, 'pending', 'saas_booking')",
                (appt_id, subscriber_id, sub[1] or sub[0], sub[0], data.get("date", ""), data.get("time", "")))
            cur.execute("UPDATE saas_subscribers SET status='demo_booked', updated_at=datetime('now') WHERE id=?", (subscriber_id,))
            conn.commit()
            conn.close()
            return JSONResponse({"appointment_id": appt_id, "status": "booked"}, status_code=201)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.post("/api/saas/contract/generate", tags=["public"])
    async def saas_gen_contract(request: Request):
        """POST /api/saas/contract/generate - Generate proposal & contract."""
        try:
            data = await request.json()
            subscriber_id = data.get("subscriber_id", "")
            total_value = data.get("total_contract_value", 0)
            if not subscriber_id or total_value <= 0:
                return JSONResponse({"error": "Missing fields"}, status_code=400)
            
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT email FROM saas_subscribers WHERE id=?", (subscriber_id,))
            sub = cur.fetchone()
            if not sub:
                conn.close()
                return JSONResponse({"error": "Subscriber not found"}, status_code=404)
            
            contract_id = str(uuid.uuid4())
            cur.execute("INSERT INTO saas_contracts (id, subscriber_id, total_contract_value, contract_json, status) VALUES (?, ?, ?, ?, 'draft')",
                (contract_id, subscriber_id, total_value, json.dumps({"total": total_value})))
            cur.execute("UPDATE saas_subscribers SET status='proposal_sent', updated_at=datetime('now') WHERE id=?", (subscriber_id,))
            conn.commit()
            conn.close()
            return JSONResponse({"contract_id": contract_id, "sent_to": sub[0]}, status_code=201)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.post("/api/saas/payment/received", tags=["public"])
    async def saas_log_payment(request: Request):
        """POST /api/saas/payment/received - Log payment & trigger backlog activation."""
        try:
            data = await request.json()
            contract_id = data.get("contract_id", "")
            payment_amount = data.get("payment_amount", 0)
            if not contract_id or payment_amount <= 0:
                return JSONResponse({"error": "Missing fields"}, status_code=400)
            
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT total_contract_value, payment_pct_received FROM saas_contracts WHERE id=?", (contract_id,))
            contract = cur.fetchone()
            if not contract:
                conn.close()
                return JSONResponse({"error": "Contract not found"}, status_code=404)
            
            total_value, prev_pct = contract
            total_received = (total_value * (prev_pct / 100)) + payment_amount if prev_pct else payment_amount
            payment_pct = (total_received / total_value) * 100
            activation_date = None
            
            if payment_pct >= 60 and (not prev_pct or prev_pct < 60):
                activation_date = (datetime.now() + timedelta(days=180)).isoformat()
            
            cur.execute("UPDATE saas_contracts SET payment_pct_received=?, backlog_activation_date=COALESCE(backlog_activation_date, ?), updated_at=datetime('now') WHERE id=?",
                (payment_pct, activation_date, contract_id))
            conn.commit()
            conn.close()
            return JSONResponse({"contract_id": contract_id, "payment_pct": round(payment_pct, 1), "backlog_activation_date": activation_date})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.get("/api/saas/dashboard/{subscriber_id}", tags=["public"])
    async def saas_dashboard(subscriber_id: str):
        """GET /api/saas/dashboard/{id} - Owner-operator dashboard."""
        try:
            conn = sqlite3.connect(SaaS_DB)
            cur = conn.cursor()
            cur.execute("SELECT id, email, company_name FROM saas_subscribers WHERE id=?", (subscriber_id,))
            sub = cur.fetchone()
            if not sub:
                conn.close()
                return JSONResponse({"error": "Not found"}, status_code=404)
            
            cur.execute("SELECT id, total_contract_value, payment_pct_received, status FROM saas_contracts WHERE subscriber_id=?", (subscriber_id,))
            contracts = [{"id": r[0], "value": r[1], "payment_pct": r[2], "status": r[3]} for r in cur.fetchall()]
            conn.close()
            return JSONResponse({"subscriber": {"id": sub[0], "email": sub[1], "company": sub[2]}, "contracts": contracts})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
