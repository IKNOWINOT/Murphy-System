"""
PATCH-417 — Outbound Review Queue routes (murphy-edge edition)
================================================================

WHAT THIS IS:
  FastAPI route handlers for the outbound email review queue. Imported and
  initialized by murphy_edge.py via init_outbound_routes(app).

WHY IT EXISTS:
  See PATCH-417 module header. Briefly: every email a swarm agent (or any
  non-founder caller) tries to send goes through this queue. Founder reviews,
  approves with optional edits, or rejects with reason. Hard prereq for
  Phase 5a swarm sales going live.

HOW IT FITS:
  - Uses the outbound_email_queue table in /var/lib/murphy-production/murphy_mail.db
    (table created by patch417_outbound_review_queue.py)
  - Reads request.state.{tier, department, actor_account_id} set by
    modular_auth middleware (PATCH-414b)
  - Emits to event_bus when present

ENDPOINTS:
  POST /api/mail/outbound/submit                — any auth, queues a draft
  GET  /api/mail/outbound/queue                 — founder-only, lists by status
  GET  /api/mail/outbound/{queue_id}            — founder-only, full detail
  POST /api/mail/outbound/{queue_id}/approve    — founder-only, sends
  POST /api/mail/outbound/{queue_id}/reject     — founder-only, with reason
  GET  /api/mail/outbound/stats                 — any auth, aggregate counts

LAST UPDATED: 2026-05-25 by PATCH-417b
"""
from __future__ import annotations

import json
import sqlite3
import secrets
import logging
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("murphy.mail_outbound")

DB_PATH = "/var/lib/murphy-production/murphy_mail.db"
HOUSEHOLD_DB = "/var/lib/murphy-production/murphy_household.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(event_type: str, payload: dict) -> None:
    """Best-effort event bus emission."""
    try:
        from event_bus import publish
        publish(event_type, payload)
    except Exception as e:
        log.debug("event_bus emit failed for %s: %s", event_type, e)



# ─── PATCH-435: Autonomy policy check + send helper ────────────────────
POLICY_DB = '/var/lib/murphy-production/murphy_mail.db'


def _check_autonomy_policy(agent_role, action_type='email_outbound'):
    """PATCH-435: Look up policy for (role, action_type).
    
    Returns dict {allowed, master_enabled, min_confidence, max_per_day,
    runs_today, has_audit_gate, reason} — always returns a dict, never
    raises. If agent_role is missing/empty, returns allowed=False.
    """
    if not agent_role:
        return {'allowed': False, 'reason': 'no_agent_role'}
    try:
        c = sqlite3.connect(POLICY_DB)
        c.row_factory = sqlite3.Row
        row = c.execute(
            'SELECT * FROM agent_action_policy WHERE role=? AND action_type=?',
            (agent_role, action_type)
        ).fetchone()
        c.close()
    except Exception as e:
        return {'allowed': False, 'reason': f'db_error:{e}'}
    if not row:
        return {'allowed': False, 'reason': 'no_policy_row'}
    r = dict(row)
    if not r.get('master_enabled'):
        return {'allowed': False, 'reason': 'master_disabled', **r}
    if not r.get('has_audit_gate'):
        return {'allowed': False, 'reason': 'no_audit_gate', **r}
    if r.get('runs_today', 0) >= r.get('max_per_day', 0):
        return {'allowed': False, 'reason': 'daily_cap_reached', **r}
    # PATCH-438: policy now allows two paths — audit_gate OR mfgc_authority
    if not (r.get('has_audit_gate') or r.get('has_mfgc_authority')):
        return {'allowed': False, 'reason': 'no_gate_path', **r}
    return {'allowed': True, **r}


def _run_audit_gate(subject, body_text, agent_role, queue_id, to_count):
    """PATCH-435: Run DeliverableAuditGate, return (verdict, score, report_dict).
    Returns (None, 0.0, None) on any error — caller must treat error as fail.
    """
    try:
        import sys as _sys
        if '/opt/Murphy-System' not in _sys.path:
            _sys.path.insert(0, '/opt/Murphy-System')
        from src.deliverable_audit_gate import DeliverableAuditGate
        gate = DeliverableAuditGate(pass_threshold=0.55, warn_threshold=0.30, min_length=80)
        synth_prompt = (
            f'Write a professional outbound email from a {agent_role} '
            f'on subject: {subject}. Must address recipient clearly, '
            f'deliver coherent message, include clear ask, avoid placeholders.'
        )
        report = gate.audit(
            prompt=synth_prompt, deliverable=body_text,
            expected_format='email',
            metadata={'queue_id': queue_id, 'agent_role': agent_role,
                      'to_count': to_count, 'pathway': 'patch435_auto'}
        )
        return report.verdict.value, float(getattr(report, 'overall_score', 0.0)), report.to_dict()
    except Exception as e:
        log.exception('PATCH-435 audit gate error')
        return None, 0.0, {'error': str(e)}


def _send_via_postfix(from_addr, to_list, subject, body_text):
    """PATCH-435 + Ship 31ab: Send via local Postfix on 127.0.0.1:25.
    Renders the body through the canonical Murphy brand template
    (Victorian-techno) with auto-attached free-tier counter + signup CTA.
    Returns (ok: bool, err: str|None, sent_via: str).
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.utils import formatdate, make_msgid
    try:
        # Render through brand kit so every outbound looks like Murphy
        try:
            import sys as _sys
            if '/opt/Murphy-System' not in _sys.path:
                _sys.path.insert(0, '/opt/Murphy-System')
            from src.email_brand import render_branded_email
            from src import free_tier_counter as _ftc

            # Ship 31ac: spellcheck gate — fix LLM-side typos before send
            try:
                from src.spellcheck_gate import scan_and_fix
                body_text, _bc = scan_and_fix(body_text)
                subject, _sc = scan_and_fix(subject)
                if _bc or _sc:
                    log.info('Ship 31ac spellcheck: %d body + %d subject fixes',
                             len(_bc), len(_sc))
            except Exception:
                log.exception('Ship 31ac spellcheck failed (sending anyway)')


            primary_to = to_list[0] if to_list else ''
            free_tier_dict = None
            if primary_to:
                try:
                    # Ship 31ab: increment FIRST so the card shows the
                    # post-send state ("3 of 5 used" not "2 of 5 used")
                    _ftc.increment_and_get(primary_to)
                    st = _ftc.get_state(primary_to)
                    if not st.get('claimed'):
                        tok = _ftc.get_or_create_claim_token(primary_to)
                        st['claim_url'] = f'https://murphy.systems/claim/{tok}'
                        st['email_addr'] = primary_to
                        free_tier_dict = st
                except Exception:
                    log.exception('Ship 31ab free_tier lookup failed')

            html, plain = render_branded_email(
                answer=body_text,
                subject=subject,
                role_label=None,
                free_tier=free_tier_dict,
            )

            msg = MIMEMultipart('alternative')
            msg['From'] = from_addr
            msg['To'] = ', '.join(to_list)
            msg['Subject'] = subject
            msg['Reply-To'] = from_addr
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain='murphy.systems')
            # Ship 31ae — Gmail/Yahoo 2024 bulk-sender header compliance
            try:
                from src.deliverability_headers import add_deliverability_headers
                add_deliverability_headers(
                    msg, from_addr=from_addr,
                    recipient_email=to_list[0] if to_list else None,
                    campaign_id='stranger-reply', is_transactional=True,
                )
            except Exception:
                log.exception('Ship 31ae header injection failed (sending anyway)')
            msg.attach(MIMEText(plain, 'plain', 'utf-8'))
            msg.attach(MIMEText(html, 'html', 'utf-8'))
        except Exception:
            log.exception('Ship 31ab brand render failed — falling back to plain')
            from email.message import EmailMessage
            msg = EmailMessage()
            msg['From'] = from_addr
            msg['To'] = ', '.join(to_list)
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain='murphy.systems')
            # Ship 31ae — Gmail/Yahoo 2024 bulk-sender header compliance
            try:
                from src.deliverability_headers import add_deliverability_headers
                add_deliverability_headers(
                    msg, from_addr=from_addr,
                    recipient_email=to_list[0] if to_list else None,
                    campaign_id='stranger-reply', is_transactional=True,
                )
            except Exception:
                log.exception('Ship 31ae header injection failed (sending anyway)')
            msg.set_content(body_text)

        with smtplib.SMTP('127.0.0.1', 25, timeout=10) as smtp:
            smtp.send_message(msg)
        return True, None, 'smtp_postfix_branded'
    except Exception as e:
        log.exception('PATCH-435 SMTP send failed')
        return False, str(e), None


def _increment_daily_counter(agent_role, action_type='email_outbound'):
    """PATCH-435: Increment runs_today + runs_total for a (role, action) policy."""
    try:
        c = sqlite3.connect(POLICY_DB)
        c.execute(
            'UPDATE agent_action_policy '
            'SET runs_today = runs_today + 1, runs_total = runs_total + 1 '
            'WHERE role=? AND action_type=?',
            (agent_role, action_type)
        )
        c.commit()
        c.close()
    except Exception:
        log.exception('PATCH-435 counter increment failed')


# ─── PATCH-438: MFGC authority check ───────────────────────────────────
def _check_mfgc_authority(agent_role, action_type, policy_row=None):
    """Look up MFGC authority for a (role, action_type).
    
    Returns dict {allowed, mind_confidence, required, phase, reason}.
    Reads live Swarm Mind stats and compares against the action's
    mfgc_min_confidence threshold. If mind is offline or unreachable,
    returns allowed=False (fail closed).
    """
    if not policy_row:
        return {'allowed': False, 'reason': 'no_policy_row'}
    required = policy_row.get('mfgc_min_confidence')
    phase = policy_row.get('mfgc_phase')
    if required is None or phase is None:
        return {'allowed': False, 'reason': 'no_mfgc_threshold',
                'mind_confidence': 0.0, 'required': None, 'phase': None}
    # Read live Swarm Mind confidence FROM DB (process-independent — the
    # per-process get_mind() returns running=False unless that process is
    # the monolith. Confidence is persisted to cycle_log every ~10min.)
    try:
        import sqlite3 as _sq438
        from datetime import datetime as _dt438, timezone as _tz438
        _mc = _sq438.connect('/var/lib/murphy-production/murphy_mind.db')
        # Average of last 10 cycles to smooth out single-cycle noise
        avg_row = _mc.execute(
            'SELECT AVG(confidence), MAX(cycle), MAX(timestamp) '
            'FROM cycle_log WHERE cycle > (SELECT MAX(cycle)-10 FROM cycle_log)'
        ).fetchone()
        _mc.close()
        mind_conf  = float(avg_row[0] or 0.0)
        mind_cycle = int(avg_row[1] or 0)
        # Staleness check — confidence is only fresh if last cycle was < 30min ago
        if avg_row[2]:
            last_ts = _dt438.fromisoformat(avg_row[2].replace('Z', '+00:00'))
            staleness_s = (_dt438.now(_tz438.utc) - last_ts).total_seconds()
        else:
            staleness_s = 99999
        mind_running = staleness_s < 1800  # 30 minutes
    except Exception as e:
        return {'allowed': False, 'reason': f'mind_db_error:{e}'}
    if not mind_running:
        return {'allowed': False, 'reason': 'mind_stale',
                'mind_confidence': mind_conf, 'required': required,
                'phase': phase, 'staleness_s': staleness_s}
    if mind_conf < required:
        return {'allowed': False, 'reason': 'below_mfgc_threshold',
                'mind_confidence': mind_conf, 'required': required,
                'phase': phase, 'mind_cycle': mind_cycle}
    return {'allowed': True, 'mind_confidence': mind_conf,
            'required': required, 'phase': phase,
            'mind_cycle': mind_cycle, 'mind_running': mind_running}

def init_outbound_routes(app) -> None:
    """Register all PATCH-417 routes on the given FastAPI app.

    Called by murphy_edge.py via _register_patch("mail_outbound", ...).
    """

    # ── POST /api/mail/outbound/submit ────────────────────────────────────
    @app.post("/api/mail/outbound/submit")
    async def outbound_submit(request: Request):
        """Queue a draft email for founder review.

        Body:
            to: str | list[str]   — required
            subject: str           — required
            body: str              — required
            from?: str             — optional sender override
            urgency?: str          — low | normal | high (default normal)
            body_format?: str      — plain | html (default plain)
            cc?: list[str]         — optional

        Returns:
            {ok, queue_id, status, review_url}
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"},
                                status_code=400)

        to = body.get("to")
        if isinstance(to, str):
            to = [to]
        if not to or not body.get("subject") or not body.get("body"):
            return JSONResponse({
                "ok": False, "error": "missing_required",
                "required": ["to", "subject", "body"]}, status_code=400)

        agent_pid = getattr(request.state, "actor_account_id", None)
        tier = getattr(request.state, "tier", None) or "anonymous"
        dept = getattr(request.state, "department", None)

        # Pull richer agent context from household DB if employee
        agent_role = None
        agent_class = None
        if tier == "employee" and agent_pid:
            try:
                conn = sqlite3.connect(HOUSEHOLD_DB)
                row = conn.execute(
                    "SELECT role, notes FROM household_profiles "
                    "WHERE profile_id=?", (agent_pid,)).fetchone()
                conn.close()
                if row:
                    agent_role = row[0]
                    try:
                        meta = json.loads(row[1] or "{}")
                        agent_class = meta.get("class")
                    except Exception:
                        pass
            except Exception:
                pass

        queue_id = "mq_" + secrets.token_hex(8)
        now = _now()
        from_addr = body.get("from") or (
            "swarm@murphy.systems" if tier == "employee"
            else "founder@murphy.systems"
        )

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                INSERT INTO outbound_email_queue
                    (queue_id, from_address, to_addresses, cc_addresses,
                     subject, body, body_format, agent_profile_id,
                     agent_role, agent_class, urgency, status,
                     created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'pending_review', ?, ?, ?)
            """, (
                queue_id, from_addr, json.dumps(to),
                json.dumps(body.get("cc", [])) if body.get("cc") else None,
                body.get("subject"), body.get("body"),
                body.get("body_format", "plain"),
                agent_pid, agent_role, agent_class,
                body.get("urgency", "normal"),
                now, now,
                json.dumps({"tier": tier, "dept": dept,
                            "submitted_via": "edge_mail_outbound"})
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            log.exception("outbound_submit db_insert failed")
            return JSONResponse({"ok": False, "error": f"db_insert: {e}"},
                                status_code=500)

        _emit("mail.outbound.submitted", {
            "queue_id": queue_id, "agent": agent_pid, "to": to,
            "subject": body.get("subject"),
            "urgency": body.get("urgency", "normal"),
        })

        # ─── PATCH-435: Autonomy policy check ───────────────────────
        # If policy says (role, email_outbound) is master_enabled AND
        # audit gate scores >= min_confidence AND under daily cap,
        # auto-approve and send NOW. Otherwise leave in pending_review.
        autonomy_outcome = 'human_review'
        autonomy_detail = None
        policy = _check_autonomy_policy(agent_role, 'email_outbound')
        if policy.get('allowed'):
            # Run audit gate synchronously
            verdict, score, report = _run_audit_gate(
                subject=body.get('subject', ''),
                body_text=body.get('body', ''),
                agent_role=agent_role,
                queue_id=queue_id,
                to_count=len(to),
            )
            min_conf = float(policy.get('min_confidence', 1.0))
            if verdict is None:
                autonomy_outcome = 'audit_gate_error'
                autonomy_detail = {'reason': 'gate_threw_exception', 'verdict': None}
            elif score < min_conf:
                autonomy_outcome = 'below_confidence_threshold'
                autonomy_detail = {'verdict': verdict, 'score': score,
                                    'required': min_conf}
            else:
                # Confidence cleared — send via Postfix
                ok, err, sent_via = _send_via_postfix(
                    from_addr, to, body.get('subject', ''), body.get('body', '')
                )
                send_now = _now()
                if ok:
                    autonomy_outcome = 'auto_approved'
                    autonomy_detail = {'verdict': verdict, 'score': score,
                                        'sent_via': sent_via}
                    try:
                        c2 = sqlite3.connect(DB_PATH)
                        c2.execute(
                            'UPDATE outbound_email_queue SET status=?, '
                            'approved_by=?, approved_at=?, sent_at=?, sent_via=?, '
                            'audit_report=?, audit_verdict=?, updated_at=? '
                            'WHERE queue_id=?',
                            ('sent', 'autonomy_policy', send_now, send_now,
                             sent_via, json.dumps(report) if report else None,
                             verdict, send_now, queue_id)
                        )
                        c2.commit()
                        c2.close()
                    except Exception:
                        log.exception('PATCH-435 status update failed')
                    _increment_daily_counter(agent_role, 'email_outbound')
                    _emit('mail.outbound.auto_approved', {
                        'queue_id': queue_id, 'agent_role': agent_role,
                        'score': score, 'verdict': verdict, 'to': to,
                        'subject': body.get('subject'),
                    })
                else:
                    autonomy_outcome = 'auto_send_failed'
                    autonomy_detail = {'verdict': verdict, 'score': score,
                                        'smtp_error': err}
                    try:
                        c2 = sqlite3.connect(DB_PATH)
                        c2.execute(
                            'UPDATE outbound_email_queue SET status=?, '
                            'failure_reason=?, updated_at=? WHERE queue_id=?',
                            ('auto_send_failed', err, send_now, queue_id)
                        )
                        c2.commit()
                        c2.close()
                    except Exception:
                        log.exception('PATCH-435 fail-status update failed')
                    _emit('mail.outbound.auto_send_failed', {
                        'queue_id': queue_id, 'agent_role': agent_role,
                        'error': err, 'subject': body.get('subject'),
                    })
        else:
            autonomy_detail = {'reason': policy.get('reason'),
                                'master_enabled': policy.get('master_enabled'),
                                'has_audit_gate': policy.get('has_audit_gate')}


        # PATCH-435: response reflects autonomy outcome
        response_status = "sent" if autonomy_outcome == "auto_approved" else "pending_review"
        return JSONResponse({
            "ok": True, "queue_id": queue_id,
            "status": response_status,
            "review_url": f"/api/mail/outbound/{queue_id}",
            "autonomy_outcome": autonomy_outcome,
            "autonomy_detail": autonomy_detail,
        })

    # ── GET /api/mail/outbound/queue ─────────────────────────────────────
    @app.get("/api/mail/outbound/queue")
    async def outbound_list(request: Request):
        """List queued emails by status. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)

        status_filter = request.query_params.get("status", "pending_review")
        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid_pagination"},
                                status_code=400)

        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT queue_id, from_address, to_addresses, subject, body,
                   agent_profile_id, agent_role, agent_class, urgency,
                   status, created_at
            FROM outbound_email_queue
            WHERE status = ?
            ORDER BY
                CASE urgency
                    WHEN 'high' THEN 0
                    WHEN 'normal' THEN 1
                    ELSE 2
                END,
                created_at DESC
            LIMIT ? OFFSET ?
        """, (status_filter, limit, offset)).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM outbound_email_queue WHERE status = ?",
            (status_filter,)).fetchone()[0]
        conn.close()

        items = [{
            "queue_id":         r[0],
            "from":             r[1],
            "to":               json.loads(r[2]) if r[2] else [],
            "subject":          r[3],
            "body_preview":     (r[4] or "")[:200],
            "agent_profile_id": r[5],
            "agent_role":       r[6],
            "agent_class":      r[7],
            "urgency":          r[8],
            "status":           r[9],
            "created_at":       r[10],
        } for r in rows]

        return JSONResponse({
            "ok": True, "count": len(items), "total": total,
            "status_filter": status_filter, "items": items,
        })

    # ── GET /api/mail/outbound/stats ─────────────────────────────────────
    @app.get("/api/mail/outbound/stats")
    async def outbound_stats(request: Request):
        """Aggregate counts across queue states. Any authed caller."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT status, COUNT(*) FROM outbound_email_queue GROUP BY status
        """).fetchall()
        conn.close()
        stats = {r[0]: r[1] for r in rows}
        return JSONResponse({
            "ok": True,
            "total":          sum(stats.values()),
            "pending_review": stats.get("pending_review", 0),
            "approved":       stats.get("approved", 0),
            "rejected":       stats.get("rejected", 0),
            "sent":           stats.get("sent", 0),
            "failed":         stats.get("failed", 0),
        })

    # ── GET /api/mail/outbound/{queue_id} ────────────────────────────────
    @app.get("/api/mail/outbound/{queue_id}")
    async def outbound_get(queue_id: str, request: Request):
        """Full row detail. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)

        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT * FROM outbound_email_queue WHERE queue_id=?",
            (queue_id,)).fetchone()
        cols = [c[1] for c in conn.execute(
            "PRAGMA table_info(outbound_email_queue)").fetchall()]
        conn.close()

        if not row:
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        item = dict(zip(cols, row))
        for jf in ("to_addresses", "cc_addresses", "metadata"):
            if item.get(jf):
                try:
                    item[jf] = json.loads(item[jf])
                except Exception:
                    pass
        return JSONResponse({"ok": True, "item": item})

    # ── POST /api/mail/outbound/{queue_id}/approve ───────────────────────
    # PATCH-425: real SMTP + audit gate
    @app.post("/api/mail/outbound/{queue_id}/approve")
    async def outbound_approve(queue_id: str, request: Request):
        """Approve and send. Founder only.
        
        Pre-flight: runs DeliverableAuditGate. On FAIL refuses unless
        ?force=1 query param is set. On PASS/WARN proceeds to real
        SMTP delivery via local Postfix.
        
        Body (optional): {edits: {subject?, body?, to?}}
        Query (optional): force=1 to override an audit FAIL
        """
        import smtplib
        from email.message import EmailMessage
        from email.utils import formatdate, make_msgid
        
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        edits = body.get("edits", {}) or {}
        force = request.query_params.get("force") in ("1", "true", "yes")
        
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT from_address, to_addresses, subject, body, status,
                   agent_profile_id, agent_role, body_format, metadata
            FROM outbound_email_queue WHERE queue_id=?
        """, (queue_id,)).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        if row[4] != "pending_review":
            conn.close()
            return JSONResponse({
                "ok": False, "error": "not_pending",
                "current_status": row[4]}, status_code=409)
        
        from_addr = row[0]
        to_list = edits.get("to") or json.loads(row[1])
        if isinstance(to_list, str):
            to_list = [to_list]
        subject = edits.get("subject") or row[2]
        body_text = edits.get("body") or row[3]
        agent_pid = row[5]
        agent_role = row[6] or "unknown"
        # Ship 31al: read body_format + metadata to choose plain vs branded multipart
        body_format = (row[7] if len(row) > 7 else None) or "plain"
        try:
            queue_metadata = json.loads(row[8]) if (len(row) > 8 and row[8]) else {}
        except Exception:
            queue_metadata = {}
        # If body_text was edited via founder review and looks like the legacy
        # plain text, prefer it (founder intent wins).
        if edits.get("body"):
            body_format = "plain"
        
        now = _now()
        approver_pid = getattr(request.state, "actor_account_id", "founder")
        
        # ── PATCH-425: Run DeliverableAuditGate ──────────────────────────
        audit_report_dict = None
        audit_verdict = None
        try:
            import sys as _sys
            if "/opt/Murphy-System" not in _sys.path:
                _sys.path.insert(0, "/opt/Murphy-System")
            from src.deliverable_audit_gate import DeliverableAuditGate
            gate = DeliverableAuditGate(
                pass_threshold=0.55,    # outbound email is lighter than full forge
                warn_threshold=0.30,
                min_length=80,          # short cold outreach is OK
            )
            # Synthesize a "prompt" for the audit gate from the email's own
            # subject + role context. The gate then checks coverage,
            # completeness, coherence, length adequacy of the body.
            synth_prompt = (
                f"Write a professional outbound email from a {agent_role} "
                f"on subject: {subject}. The email must address the recipient clearly, "
                f"deliver a coherent message, include a clear ask, and avoid "
                f"empty/placeholder content."
            )
            report = gate.audit(
                prompt=synth_prompt,
                deliverable=body_text,
                expected_format="email",
                metadata={
                    "queue_id": queue_id,
                    "agent_profile_id": agent_pid,
                    "agent_role": agent_role,
                    "to_count": len(to_list),
                },
            )
            audit_report_dict = report.to_dict()
            audit_verdict = report.verdict.value  # "pass"|"warn"|"fail"
            
            # Persist the audit report so OS Mail tab can show it
            conn.execute("""
                UPDATE outbound_email_queue
                SET audit_report=?, audit_verdict=?, updated_at=?
                WHERE queue_id=?
            """, (json.dumps(audit_report_dict), audit_verdict, now, queue_id))
            conn.commit()
            
            if audit_verdict == "fail" and not force:
                conn.execute("""
                    UPDATE outbound_email_queue
                    SET status=?, updated_at=?
                    WHERE queue_id=?
                """, ("audit_failed", now, queue_id))
                conn.commit()
                conn.close()
                _emit("mail.outbound.audit_failed", {
                    "queue_id": queue_id, "verdict": audit_verdict,
                    "score": audit_report_dict.get("overall_score"),
                })
                return JSONResponse({
                    "ok": False,
                    "queue_id": queue_id,
                    "error": "audit_failed",
                    "audit_verdict": audit_verdict,
                    "overall_score": audit_report_dict.get("overall_score"),
                    "failed_checks": [
                        c for c in audit_report_dict.get("checks", [])
                        if c.get("status") == "fail"
                    ],
                    "hint": "POST again with ?force=1 to override (founder discretion)",
                }, status_code=422)
        except Exception as _audit_exc:
            # Don't block delivery on audit gate bugs — log and proceed
            try:
                import logging
                logging.getLogger(__name__).warning(
                    "PATCH-425 audit gate errored, allowing send: %s", _audit_exc)
            except Exception:
                pass
            audit_verdict = "skipped"
        
        # ── PATCH-425 + Ship 31al: Real SMTP delivery (branded when html) ──
        msg = None
        smtp_message_id = None
        if body_format == "html":
            # Branded multipart/alternative path
            try:
                from src.email_mime_builder import build_multipart_message
                plain_body = queue_metadata.get("plain_body") or body_text
                msg_str = build_multipart_message(
                    to_addr=to_list[0] if to_list else "",
                    subject=subject,
                    plain_body=plain_body,
                    from_addr=from_addr or "sales@murphy.systems",
                )
                # Parse string back into EmailMessage for header injection + smtplib
                import email as _email
                msg = _email.message_from_string(msg_str)
                # Override To with the full list when multiple recipients
                if len(to_list) > 1:
                    del msg["To"]
                    msg["To"] = ", ".join(to_list)
                # Reuse the Message-ID build_multipart_message set
                smtp_message_id = msg.get("Message-ID")
            except Exception as mp_exc:
                # Render failed — fall through to plain-text path
                try:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Ship 31al: multipart build failed (%s), falling back to plain", mp_exc)
                except Exception:
                    pass
                msg = None

        if msg is None:
            # Plain text path (legacy default)
            msg = EmailMessage()
            msg["From"] = from_addr or "sales@murphy.systems"
            msg["To"] = ", ".join(to_list)
            msg["Subject"] = subject
            msg["Date"] = formatdate(localtime=False)
            msg["Message-ID"] = make_msgid(domain="murphy.systems")
            msg.set_content(body_text)
            smtp_message_id = msg["Message-ID"]

        # Ship 31ae — bulk-sender header compliance (applies to both paths)
        try:
            from src.deliverability_headers import add_deliverability_headers
            add_deliverability_headers(
                msg, from_addr=from_addr or "sales@murphy.systems",
                recipient_email=to_list[0] if to_list else None,
                campaign_id='outbound', is_transactional=True,
            )
        except Exception:
            pass
        
        send_ok = False
        send_err = None
        if not smtp_message_id:
            smtp_message_id = msg["Message-ID"]
        sent_via = "postfix_localhost"
        try:
            with smtplib.SMTP("127.0.0.1", 25, timeout=10) as smtp:
                smtp.ehlo()
                refused = smtp.send_message(msg)
            if refused:
                send_err = f"partial_refused: {refused}"
            else:
                send_ok = True
        except Exception as exc:
            send_err = f"{type(exc).__name__}: {exc}"
        
        # Mark approved regardless (audit either passed or was overridden)
        conn.execute("""
            UPDATE outbound_email_queue
            SET status='approved', approved_by=?, approved_at=?, updated_at=?,
                subject=?, body=?, to_addresses=?
            WHERE queue_id=?
        """, (approver_pid, now, now, subject, body_text,
              json.dumps(to_list), queue_id))
        
        if send_ok:
            conn.execute("""
                UPDATE outbound_email_queue
                SET status='sent', sent_at=?, sent_via=?, updated_at=?
                WHERE queue_id=?
            """, (now, sent_via, now, queue_id))
        else:
            conn.execute("""
                UPDATE outbound_email_queue
                SET status='failed', failure_reason=?, updated_at=?
                WHERE queue_id=?
            """, (send_err, now, queue_id))
        conn.commit()
        conn.close()
        
        _emit("mail.outbound.approved" if send_ok else "mail.outbound.failed",
              {"queue_id": queue_id, "approver": approver_pid,
               "to": to_list, "subject": subject,
               "audit_verdict": audit_verdict,
               "forced": force})
        if send_ok:
            _emit("mail.outbound.sent",
                  {"queue_id": queue_id, "sent_via": sent_via,
                   "message_id": smtp_message_id})
        
        return JSONResponse({
            "ok": send_ok,
            "queue_id": queue_id,
            "status": "sent" if send_ok else "failed",
            "sent_via": sent_via if send_ok else None,
            "message_id": smtp_message_id if send_ok else None,
            "error": send_err,
            "audit_verdict": audit_verdict,
            "audit_score": (audit_report_dict or {}).get("overall_score"),
            "forced": force,
        })
    
    # ── PATCH-425: GET audit report ─────────────────────────────────────
    @app.get("/api/mail/outbound/{queue_id}/audit")
    async def outbound_audit_report(queue_id: str, request: Request):
        """Fetch the audit gate report for a queued draft.
        
        Returns NULL audit_report for drafts not yet processed by approve.
        """
        if getattr(request.state, "tier", None) not in ("founder", "kin"):
            return JSONResponse({"ok": False, "error": "forbidden"},
                                status_code=403)
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT audit_report, audit_verdict, status, subject "
            "FROM outbound_email_queue WHERE queue_id=?",
            (queue_id,)).fetchone()
        conn.close()
        if not row:
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        return JSONResponse({
            "ok": True,
            "queue_id": queue_id,
            "status": row[2],
            "subject": row[3],
            "audit_verdict": row[1],
            "audit_report": json.loads(row[0]) if row[0] else None,
        })


    # ── POST /api/mail/outbound/{queue_id}/reject ────────────────────────
    @app.post("/api/mail/outbound/{queue_id}/reject")
    async def outbound_reject(queue_id: str, request: Request):
        """Reject with a reason. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        reason = body.get("reason", "no_reason_given")
        now = _now()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            UPDATE outbound_email_queue
            SET status='rejected', reject_reason=?, updated_at=?
            WHERE queue_id=? AND status='pending_review'
        """, (reason, now, queue_id))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return JSONResponse({
                "ok": False, "error": "not_found_or_not_pending"},
                status_code=404)

        _emit("mail.outbound.rejected",
              {"queue_id": queue_id, "reason": reason})

        return JSONResponse({
            "ok": True, "queue_id": queue_id,
            "status": "rejected", "reason": reason,
        })


    log.info("PATCH-417 mail_outbound: 6 routes registered")
