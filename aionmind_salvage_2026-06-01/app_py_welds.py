# Salvaged from app.py 2026-06-01
# Six chat-side welds: R421 (aionmind bridge), R423/b/c (kernel result shape),
# R424/b (endpoint→capability bridge), R426 (task_config inject), R427 (/op route).
# These were inside create_app() — paste back into a standalone AionMind app to reuse.

# ═══ R427: /op canvas route ═══
    # _R427_OP_CANVAS — unified TaskBundle surface


# ═══ R421/R423/R424/R426: chat-side AionMind welds ═══
            # ─── R421 (2026-06-01): _R421_AIONMIND_BRIDGE ─────────────────
            # Route through AionMind tool-calling chat by default. Tools
            # registered by R420 (1,806 internal endpoints + 11 generic)
            # become callable via natural language.
            # Toggle off: MURPHY_CHAT_USE_AIONMIND=0
            import os as _r421_os
            if _r421_os.environ.get("MURPHY_CHAT_USE_AIONMIND", "1") != "0":
                try:
                    from src.aionmind.chat_router import aionmind_chat as _r421_aion
                    from src.aionmind.chat_router import ChatRequest as _R421Req
                    _r421_chat_req = _R421Req(
                        message=message,
                        agent_id=f"chat_{session_id}",
                        include_memory=True,
                        auto_approve=False,
                    )
                    _r421_result = await _r421_aion(_r421_chat_req, req)
                    # Reshape AionMind {ok, response, tool_calls, tools_used}
                    # to /api/chat {success, reply, session_id, _tools_used}
                    return JSONResponse({
                        "success": bool(_r421_result.get("ok", True)),
                        "reply": _r421_result.get("response", ""),
                        "session_id": session_id,
                        "_tools_used": _r421_result.get("tools_used", 0),
                        "_tool_calls": [
                            {"tool_id": tc.get("tool_id"), "reason": tc.get("reason", "")}
                            for tc in (_r421_result.get("tool_calls") or [])[:5]
                            if isinstance(tc, dict)
                        ],
                        "_via": "aionmind",
                    })
                except Exception as _r421_e:
                    logger.warning("R421 bridge failed, falling back to legacy: %s", _r421_e)
                    # fall through to existing legacy handler
            # ─── end R421 ─────────────────────────────────────────────────


            # ═══════════════════════════════════════════════════════════════
            # PATCH-R355 PROMPT-GUARD WITH FULL ERROR DISCIPLINE
            # Founder R355 directive: "Every choice has only a certain number of
            # things that can go wrong. Number them. Full error coding: who/what/
            # when/where/how/why. Plan ancillary code changes."
            #
            # FME (Failure Modes Enumerated):
            #   E_PROMPT_0001: message missing (handled above, line 25173)
            #   E_PROMPT_0002: message > ceiling → truncate + WARN log
            #   E_PROMPT_0003: JSON parse failed (handled by FastAPI middleware)
            #
            # SME (Success Modes Enumerated):
            #   S1: message <= ceiling → pass unchanged
            #   S2: message > ceiling → truncate, log audit, continue
            #   S3: caller wants to see what was truncated → R355_truncated_chars
            #       added to history + audit chain (transparent degradation)
            #
            # Ancillary changes for R355:
            #   /var/lib/murphy-production/error_codes.json (R355 STREAM A)
            #   .agents/rules/error_discipline.md (R355 standing rule)
            #
            # Rollback: restore app.py.pre-r355 + restart
            # ═══════════════════════════════════════════════════════════════
            _R355_CEILING = 1200            # ~300 tokens conservative
            _R355_TAIL_KEEP = 1136          # CEILING - 64 (separator)
            _R355_PREFIX_KEEP = 60
            _R355_truncated_chars = 0       # exposed in history for transparency

            if len(message) > _R355_CEILING:
                _R355_truncated_chars = len(message) - _R355_CEILING
                # Structured WARNING — WHO/WHAT/WHEN/WHERE/HOW/WHY
                logger.warning(
                    "[E_PROMPT_0002] who=%s what=%s when=%s where=%s how=%s why=%s",
                    body.get("session_id") or "anon",                     # who
                    "/api/chat",                                          # what
                    _ct.strftime("%Y-%m-%dT%H:%M:%SZ", _ct.gmtime()),     # when
                    "app.py:25184",                                       # where
                    f"len={len(message)}>ceiling={_R355_CEILING}",        # how
                    "Substrate LLM hallucinates past ~300 tokens; truncating tail-preserved",  # why
                )
                # Tail-preserving truncation (closing instruction usually carries the ask)
                _suffix = message[-_R355_TAIL_KEEP:]
                _prefix = message[:_R355_PREFIX_KEEP]
                message = (
                    _prefix
                    + " [...E_PROMPT_0002 truncated "
                    + str(_R355_truncated_chars)
                    + " chars...] "
                    + _suffix
                )


            history = []
            try:
                _r = _cs.connect("/var/lib/murphy-production/murphy_mind.db").execute(
                    "SELECT turns FROM chat_sessions WHERE session_id=?", (session_id,)
                ).fetchone()
                if _r:
                    history = _cj.loads(_r[0])[-8:]
            except Exception:
                pass

            from src.self_audit import snapshot as _snap
            audit = _snap()
            # R405 Phase 2: set tenant_id for cost attribution
            _r405_tenant = req.headers.get("X-Tenant-ID", "").strip() or session_id or "platform"
            try:
                from src.llm_cost_ledger import set_tenant as _r405_set, reset_tenant as _r405_reset
                _r405_tok = _r405_set(_r405_tenant)
            except Exception:
                _r405_tok = None
            try:
                from src.murphy_voice import reply_in_voice as _riv
                reply = _riv(message, audit=audit, history=history, channel="chat")
            finally:
                if _r405_tok is not None:
                    try:
                        from src.llm_cost_ledger import reset_tenant as _r405_reset
                        _r405_reset(_r405_tok)
                    except Exception:
                        pass
            # PATCH-REFLECTION-001 — capture resolutions Murphy just emitted
            _last_res = getattr(_riv, "last_resolutions", [])

            history.append({"u": message, "m": reply, "t": _ct.time(), "resolutions": _last_res, "r355_truncated": _R355_truncated_chars})
            history = history[-16:]
            try:
                _conn = _cs.connect("/var/lib/murphy-production/murphy_mind.db")
                _conn.execute(
                    "INSERT OR REPLACE INTO chat_sessions (session_id, turns, updated) VALUES (?,?,?)",
                    (session_id, _cj.dumps(history), _ct.time()),
                )
                _conn.commit()
            except Exception:
                pass

            return JSONResponse({"success": True, "reply": reply, "session_id": session_id})
        except Exception as _e:
            return JSONResponse({"success": False, "error": str(_e)}, status_code=500)
