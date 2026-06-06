The outreach log is accessible via the API endpoint `GET /api/crm/activities`, which returns CRM activities including inbound replies. This endpoint is defined in `src/runtime/app.py` and confirmed to exist. The capacity watchdog alerts when no inbound replies are detected for over 7 days, suggesting a need to refresh APC outreach copy. The issue is properly triaged as a low engineering incident requiring manual review.

Relevant code snippets:

From src/capacity_watchdog.py:
```python
        # Reply staleness
        days = m.get("days_since_reply", 0)
        if days > SCALE_THRESHOLDS["reply_stale_days"] and not _on_cooldown("reply_stale_days"):
            msg = f"No inbound replies in {days} days. APC outreach may need copy refresh. Check outreach log at /api/crm/activities."
            _notify_corey(msg, "info", {"days_since_reply": days})
            _mark_fired("reply_stale_days")
            alerts.append("REPLY_STALE")
```

From src/runtime/app.py:
```python
    @app.get("/api/crm/activities")
    async def crm_activities(contact_id: str = "", limit: int = 50):
        db = _crm_db()
        q = "SELECT id,contact_id,type,notes,created_at FROM activities"
        params = []
        if contact_id: q += " WHERE contact_id=?"; params.append(contact_id)
        q += f" ORDER BY created_at DESC LIMIT {int(limit)}"
        rows = db.execute(q, params).fetchall()
        db.close()
        return JSONResponse({"success": True, "activities": [dict(zip(["id","contact_id","type","notes","created_at"], r)) for r in rows]})
```