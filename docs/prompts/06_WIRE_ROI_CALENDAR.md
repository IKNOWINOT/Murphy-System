# Prompt 06 — Wire ROI Calendar (Unified Dashboard)

> **Prerequisites:** Prompts 00-05 must pass.
> Read `IMMOVABLE_CONSTRAINTS.md` and `ENGINEERING_STANDARD.md` first.

---

## Goal

Wire the ROI Calendar as the unified single-pane-of-glass dashboard (Part 6).
Every user type sees the ROI Calendar as their primary interface.  Real-time
cost tracking, ROI calculations, and live event feeds are operational.

---

## Success Criteria

- [ ] `roi_calendar.html` served by production server
- [ ] `POST /api/roi-calendar/events` — creates task entry with `human_cost_estimate`
- [ ] `GET /api/roi-calendar/summary` — returns cost/ROI summary
- [ ] `GET /api/roi-calendar/export` — exports data (CSV/JSON)
- [ ] Red bar (human cost w/ benefits) displays correctly
- [ ] Green bar (actual system cost) displays correctly
- [ ] Progress percentage calculated correctly
- [ ] Live event feed operational (🆕 🅰️ ✅ 👁 ⚙)
- [ ] `cost_explosion_gate.py` integrated for real-time cost tracking
- [ ] `cost_optimization_advisor.py` integrated for ROI calculation
- [ ] RBAC per user type (owner/admin/operator/viewer) enforced
- [ ] CI passes after changes

---

## Steps

### Step 1 — Verify roi_calendar.html is served

```bash
# Check if route exists in murphy_production_server.py
grep -n "roi.calendar\|roi_calendar" murphy_production_server.py | head -20
grep -n "roi.calendar\|roi_calendar" "Murphy System/murphy_production_server.py" | head -20
```

If not present, add:

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.get("/roi-calendar")
async def serve_roi_calendar():
    """Serve the ROI Calendar unified dashboard. ROICAL-WIRE-001"""
    try:
        return FileResponse("Murphy System/roi_calendar.html")
    except Exception as e:  # ROICAL-WIRE-ERR-001
        logger.error("roi_calendar.html not found: %s", e)
        return {"status": "error", "detail": "ROI Calendar not available"}, 404
```

---

### Step 2 — Wire POST /api/roi-calendar/events

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.post("/api/roi-calendar/events")
async def create_roi_event(payload: dict):
    """Create a new ROI Calendar task entry. ROICAL-WIRE-002

    Required fields:
      - event_type: str (e.g. 'client_onboarded', 'task_completed')
      - description: str
      - human_cost_estimate: float (hours of equivalent human labor)
    """
    try:
        from src.cost_explosion_gate import CostExplosionGate
        gate = CostExplosionGate()
        event = gate.record_event(
            event_type=payload.get("event_type"),
            description=payload.get("description"),
            human_cost_estimate=payload.get("human_cost_estimate", 0.0),
            actual_cost=payload.get("actual_cost", 0.0),
        )
        return {"status": "ok", "event_id": str(event.id)}
    except Exception as e:  # ROICAL-WIRE-ERR-002
        logger.error("roi-calendar/events error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 3 — Wire GET /api/roi-calendar/summary

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.get("/api/roi-calendar/summary")
async def get_roi_summary():
    """Return cost/ROI summary for the ROI Calendar dashboard. ROICAL-WIRE-003

    Returns:
      - human_cost_total: float (total human cost equivalent in hours)
      - actual_system_cost: float (actual cost incurred)
      - roi_multiplier: float (human_cost / actual_cost)
      - progress_pct: float (0-100)
      - events: list of recent events
    """
    try:
        from src.cost_optimization_advisor import CostOptimizationAdvisor
        advisor = CostOptimizationAdvisor()
        summary = advisor.get_roi_summary()
        return {"status": "ok", "summary": summary}
    except Exception as e:  # ROICAL-WIRE-ERR-003
        logger.error("roi-calendar/summary error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 4 — Wire GET /api/roi-calendar/export

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.get("/api/roi-calendar/export")
async def export_roi_data(format: str = "csv"):
    """Export ROI Calendar data. ROICAL-WIRE-004

    Query param: format = 'csv' | 'json'
    """
    try:
        from src.cost_optimization_advisor import CostOptimizationAdvisor
        advisor = CostOptimizationAdvisor()
        data = advisor.export(format=format)
        if format == "csv":
            from fastapi.responses import Response
            return Response(content=data, media_type="text/csv")
        return {"status": "ok", "data": data}
    except Exception as e:  # ROICAL-WIRE-ERR-004
        logger.error("roi-calendar/export error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 5 — Verify red bar / green bar / progress logic

Check `roi_calendar.html` for the following elements:

```bash
grep -n "human.cost\|red.bar\|green.bar\|progress\|roi.multiplier" \
    "Murphy System/roi_calendar.html" | head -20
```

The UI must display:
- 🔴 **Red bar** — human cost with benefits (hours × hourly rate × benefits multiplier)
- 🟢 **Green bar** — actual system cost (LLM + compute + licensing)
- **Progress %** — `(tasks_completed / tasks_total) × 100`

---

### Step 6 — Wire live event feed

The live event feed must show event types:
- 🆕 New Task — when a new ROI Calendar task is created
- ✅ Complete — when a task is marked done
- 👁 HITL Review — when an item is escalated for human review
- ⚙ Update — when a task is modified

```bash
grep -n "live.feed\|websocket\|sse\|event.stream\|new.task\|complete\|hitl.review" \
    "Murphy System/roi_calendar.html" | head -30
```

If the live feed is not present, add a Server-Sent Events endpoint:

```python
# murphy_production_server.py
# [DOC-UPDATE: API_ROUTES.md]
@app.get("/api/roi-calendar/stream")
async def roi_calendar_stream():
    """SSE stream for live ROI Calendar events. ROICAL-WIRE-005"""
    try:
        from sse_starlette.sse import EventSourceResponse
        from src.live_feed_service import LiveFeedService
        feed = LiveFeedService()
        return EventSourceResponse(feed.subscribe("roi_calendar"))
    except Exception as e:  # ROICAL-WIRE-ERR-005
        logger.error("roi-calendar/stream error: %s", e)
        return {"status": "error", "detail": str(e)}, 500
```

---

### Step 7 — Wire RBAC per user type

Check `murphy_terminal.py` for `USER_TYPE_UI_LINKS` and apply RBAC:

```bash
grep -n "USER_TYPE_UI_LINKS\|owner\|admin\|operator\|viewer" \
    "Murphy System/murphy_terminal.py" | head -20
```

For each endpoint, add role check:

```python
# Pattern for role-based access control
def _require_role(request, allowed_roles: list):
    """Check user role for ROI Calendar endpoints. ROICAL-RBAC-001"""
    user_role = request.headers.get("X-Murphy-Role", "viewer")
    if user_role not in allowed_roles:
        raise PermissionError(f"Role '{user_role}' not in {allowed_roles}")
```

Role access matrix:
| Endpoint | owner | admin | operator | viewer |
|----------|-------|-------|----------|--------|
| POST /api/roi-calendar/events | ✓ | ✓ | ✓ | ✗ |
| GET /api/roi-calendar/summary | ✓ | ✓ | ✓ | ✓ |
| GET /api/roi-calendar/export | ✓ | ✓ | ✗ | ✗ |
| GET /api/roi-calendar/stream | ✓ | ✓ | ✓ | ✓ |

---

### Step 8 — Verify tests

```bash
cd "Murphy System"
python -m pytest tests/ -v -k "roi or calendar or cost" --tb=short 2>&1 | tail -40
```

---

### Record completion in tracker

```python
from src.prompt_execution_tracker import PromptExecutionTracker

tracker = PromptExecutionTracker()
tracker.mark_prompt_complete("06_WIRE_ROI_CALENDAR", results={
    "endpoints_added": [
        "/roi-calendar",
        "/api/roi-calendar/events",
        "/api/roi-calendar/summary",
        "/api/roi-calendar/export",
        "/api/roi-calendar/stream",
    ],
    "rbac_active": True,
    "live_feed_active": True,
    "cost_tracking_active": True,
    "concept_blocks": ["ROI Calendar Dashboard", "Cost Tracking Integration"],
    "doc_updates": ["API_ROUTES.md", "USER_MANUAL.md", "CHANGELOG.md"],
})
```

---

## [DOC-UPDATE: API_ROUTES.md, USER_MANUAL.md, CHANGELOG.md]
