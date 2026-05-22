"""
PATCH-345 route injection — appends Mythos Engine endpoints to app.py
Run this on the server: python3 patch345_mythos_routes.py
"""

ROUTES_CODE = '''
    # =======================================================================
    # PATCH-345 — MYTHOS ENGINE ROUTES
    # Recursive self-authoring: sense what is missing → author the function
    # =======================================================================

    @app.get("/api/mythos/sense")
    async def mythos_sense(deep: bool = False):
        """Murphy senses what is broken/missing in itself. Returns NeedSignals."""
        try:
            from src.mythos_engine import MythosEngine
            engine = MythosEngine()
            signals = engine.sense(deep=deep)
            return JSONResponse({
                "success": True,
                "count": len(signals),
                "signals": [s.to_dict() for s in signals],
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/mythos/receive")
    async def mythos_receive(request: Request):
        """Take a NeedSignal (or signal_id from a previous sense) and author a function."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            from src.mythos_engine import MythosEngine, NeedSignal
            engine = MythosEngine()

            # Accept a full signal dict or a quick description
            if "signal" in body:
                sig_data = body["signal"]
                signal = NeedSignal(
                    signal_id=sig_data.get("signal_id", "sig_manual_" + __import__("uuid").uuid4().hex[:8]),
                    domain=sig_data.get("domain", "general"),
                    severity=sig_data.get("severity", "medium"),
                    title=sig_data.get("title", "Manual need"),
                    description=sig_data.get("description", ""),
                    sensing_context=sig_data.get("sensing_context", {}),
                    suggested_function_name=sig_data.get("suggested_function_name", "fix_manual_need"),
                    suggested_route=sig_data.get("suggested_route"),
                    criteria_sense=sig_data.get("criteria_sense", []),
                    criteria_receive=sig_data.get("criteria_receive", []),
                )
            elif "description" in body:
                # Quick mode: just a description string
                desc = body["description"]
                import re as _re
                fn_name = "fix_" + _re.sub(r"[^a-z0-9]+", "_", desc.lower())[:40]
                signal = NeedSignal(
                    signal_id="sig_manual_" + __import__("uuid").uuid4().hex[:8],
                    domain=body.get("domain", "general"),
                    severity=body.get("severity", "medium"),
                    title=desc[:80],
                    description=desc,
                    sensing_context={"source": "manual", "input": desc},
                    suggested_function_name=fn_name,
                    suggested_route=body.get("route"),
                    criteria_sense=[f"Manual need: {desc[:60]}"],
                    criteria_receive=body.get("criteria", ["Function must address the described need"]),
                )
            else:
                return JSONResponse({"success": False, "error": "Provide 'signal' or 'description' in request body"}, status_code=400)

            entry = engine.receive(signal)
            return JSONResponse({"success": True, "entry": entry.to_dict()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/mythos/cycle")
    async def mythos_cycle(request: Request):
        """Full recursive sense→receive loop. Returns cycle report."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        max_cycles = int(body.get("max_cycles", 3))
        deep = bool(body.get("deep", False))
        try:
            from src.mythos_engine import MythosEngine
            engine = MythosEngine()
            report = engine.cycle(max_cycles=max_cycles, deep=deep)
            return JSONResponse({"success": True, "report": report})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/mythos/registry")
    async def mythos_registry(limit: int = 50, domain: str = "", status: str = ""):
        """All functions authored by the Mythos Engine."""
        try:
            from src.mythos_engine import MythosEngine
            engine = MythosEngine()
            entries = engine.get_registry(
                limit=limit,
                domain=domain or None,
                status=status or None,
            )
            # Strip code from list view (keep it for single entry endpoint)
            for e in entries:
                e["code_preview"] = str(e.get("code", ""))[:200]
                e.pop("code", None)
            return JSONResponse({"success": True, "count": len(entries), "entries": entries})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/mythos/registry/{entry_id}")
    async def mythos_registry_entry(entry_id: str):
        """Full entry including complete authored code and criteria."""
        try:
            from src.mythos_engine import MythosEngine
            engine = MythosEngine()
            entry = engine.get_entry(entry_id)
            if not entry:
                return JSONResponse({"success": False, "error": "Entry not found"}, status_code=404)
            return JSONResponse({"success": True, "entry": entry})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/mythos/cycles")
    async def mythos_cycles():
        """History of all Mythos cycle runs."""
        try:
            from src.mythos_engine import MythosEngine
            engine = MythosEngine()
            return JSONResponse({"success": True, "cycles": engine.get_cycles()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/mythos/wire")
    async def mythos_wire(request: Request):
        """Mark a registry entry as wired to a route/UI page."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        entry_id = body.get("entry_id")
        route_path = body.get("route_path")
        if not entry_id:
            return JSONResponse({"success": False, "error": "'entry_id' required"}, status_code=400)
        try:
            from src.mythos_engine import _get_db
            import sqlite3 as _sq3
            conn = _get_db()
            conn.execute(
                "UPDATE mythos_registry SET validation_status='injected', route_path=?, updated_at=? WHERE entry_id=?",
                (route_path, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), entry_id)
            )
            conn.commit()
            conn.close()
            return JSONResponse({"success": True, "entry_id": entry_id, "route_path": route_path, "status": "injected"})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/mythos/status")
    async def mythos_status():
        """Mythos Engine health and registry stats."""
        try:
            from src.mythos_engine import _get_db
            conn = _get_db()
            total = conn.execute("SELECT COUNT(*) FROM mythos_registry").fetchone()[0]
            by_status = dict(conn.execute(
                "SELECT validation_status, COUNT(*) FROM mythos_registry GROUP BY validation_status"
            ).fetchall())
            by_domain = dict(conn.execute(
                "SELECT domain, COUNT(*) FROM mythos_registry GROUP BY domain"
            ).fetchall())
            by_severity = dict(conn.execute(
                "SELECT severity, COUNT(*) FROM mythos_registry GROUP BY severity"
            ).fetchall())
            last_cycle = conn.execute(
                "SELECT * FROM mythos_cycles ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            return JSONResponse({
                "success": True,
                "engine": "MythosEngine v1 — PATCH-345",
                "total_entries": total,
                "by_status": by_status,
                "by_domain": by_domain,
                "by_severity": by_severity,
                "last_cycle": dict(last_cycle) if last_cycle else None,
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

'''

if __name__ == "__main__":
    import os, ast

    app_path = "/opt/Murphy-System/src/runtime/app.py"
    anchor = "    @app.exception_handler(_SHTTPException)"

    with open(app_path) as f:
        content = f.read()

    if "PATCH-345" in content:
        print("PATCH-345 already present — skipping injection")
    elif anchor not in content:
        print("ERROR: anchor not found in app.py")
    else:
        idx = content.find(anchor)
        content = content[:idx] + ROUTES_CODE + content[idx:]
        # Validate syntax
        try:
            ast.parse(content)
            with open(app_path, "w") as f:
                f.write(content)
            print(f"PATCH-345 injected at line {content[:idx].count(chr(10))+1}")
        except SyntaxError as e:
            print(f"SYNTAX ERROR at line {e.lineno}: {e.msg}")
            lines = content.split(chr(10))
            for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+3)):
                print(f"  L{i+1}: {repr(lines[i])}")
