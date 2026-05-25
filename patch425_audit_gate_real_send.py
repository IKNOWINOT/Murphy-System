#!/usr/bin/env python3
"""
PATCH-425 — Audit gate + real SMTP in outbound approve path
=============================================================

WHAT THIS IS:
  Replaces the outbound queue's stub-v1 approve handler with:
    1. A DeliverableAuditGate run BEFORE approval becomes effective
    2. A real SMTP send via local Postfix (mirror of PATCH-424 logic)
    3. Honest status: 'sent' only after Postfix accepts; 'failed' on SMTP
       error; new 'audit_failed' status when the gate refuses

WHY IT EXISTS:
  Two latent lies live in src/patch417_outbound_queue.py's approve handler:

  (a) sent_via="stub_v1" — it marks rows as 'sent' without ever touching SMTP.
      Comment in source: "Real SMTP path lands when monolith gets a real
      send route or we wire Postfix directly." PATCH-424 made that real.

  (b) No compliance check before delivery. The founder is the only gate. For
      Phase 5 safety, deliverable_audit_gate runs as a structural pre-check
      so swarm-agent drafts that hallucinate or omit required content can
      never reach the wire, even if a tired founder hits approve.

HOW IT FITS:
  - Edits src/patch417_outbound_queue.py in-place (one handler)
  - DeliverableAuditGate is already in src/deliverable_audit_gate.py
    (0 imports until now — first real consumer)
  - The 'prompt' fed to the audit gate is reconstructed from the draft's
    own subject + agent_profile (i.e. "what was this email supposed to do")
  - On audit FAIL: queue row gets status='audit_failed' + audit_report JSON
    column populated, response 422
  - On audit WARN: log but allow (founder discretion); audit_report still
    stored
  - On audit PASS: proceed to real SMTP send via local Postfix
  - SMTP errors no longer report success — status goes to 'failed' with
    failure_reason populated

NEW DB COLUMN:
  audit_report TEXT — JSON of the AuditReport (or NULL for legacy rows)
  audit_verdict TEXT — 'pass'|'warn'|'fail'|NULL (for fast queries)
  Added via ALTER TABLE; idempotent.

NEW ENDPOINT:
  GET /api/mail/outbound/{queue_id}/audit — fetch the audit report for a
  given draft. Useful for OS Mail tab to show "why this failed" UI.

ALSO: bypass option
  POST /api/mail/outbound/{queue_id}/approve?force=1 — founder-only override
  that lets you push through despite a FAIL verdict (with the report still
  attached for the audit trail). Use sparingly.

LAST UPDATED: 2026-05-25 by PATCH-425
"""
import ast
import shutil
import sqlite3
from pathlib import Path

NL = chr(10)
APP_PATH = Path("/opt/Murphy-System/src/patch417_outbound_queue.py")
DB_PATH = "/var/lib/murphy-production/murphy_mail.db"

src = APP_PATH.read_text()
if "PATCH-425" in src:
    print("  ⚠ PATCH-425 marker already in module — skipping")
    raise SystemExit(0)

# ---------------------------------------------------------------------
# Step 1 — ensure the DB has the new audit columns
# ---------------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(outbound_email_queue)")
cols = [r[1] for r in cur.fetchall()]
added = []
if "audit_report" not in cols:
    cur.execute("ALTER TABLE outbound_email_queue ADD COLUMN audit_report TEXT")
    added.append("audit_report")
if "audit_verdict" not in cols:
    cur.execute("ALTER TABLE outbound_email_queue ADD COLUMN audit_verdict TEXT")
    added.append("audit_verdict")
conn.commit()
conn.close()
print(f"  ✓ DB schema: added columns {added or '(none — already present)'}")

# ---------------------------------------------------------------------
# Step 2 — find + replace the approve handler
# ---------------------------------------------------------------------

# Anchor: the exact start of the old handler
OLD_START = '    # ── POST /api/mail/outbound/{queue_id}/approve ───────────────────────'
OLD_END_MARKER = '    # ── POST /api/mail/outbound/{queue_id}/reject ────────────────────────'

start_idx = src.find(OLD_START)
end_idx = src.find(OLD_END_MARKER, start_idx)
if start_idx < 0 or end_idx < 0:
    print(f"  ✗ Couldn't locate approve handler block")
    print(f"    OLD_START found at: {start_idx}")
    print(f"    OLD_END_MARKER found at: {end_idx}")
    raise SystemExit(1)

old_block = src[start_idx:end_idx]
print(f"  ✓ located approve handler ({len(old_block)} chars)")

# New handler — wires audit gate + real SMTP
NEW_BLOCK = (
    '    # ── POST /api/mail/outbound/{queue_id}/approve ───────────────────────' + NL +
    '    # PATCH-425: real SMTP + audit gate' + NL +
    '    @app.post("/api/mail/outbound/{queue_id}/approve")' + NL +
    '    async def outbound_approve(queue_id: str, request: Request):' + NL +
    '        """Approve and send. Founder only.' + NL +
    '        ' + NL +
    '        Pre-flight: runs DeliverableAuditGate. On FAIL refuses unless' + NL +
    '        ?force=1 query param is set. On PASS/WARN proceeds to real' + NL +
    '        SMTP delivery via local Postfix.' + NL +
    '        ' + NL +
    '        Body (optional): {edits: {subject?, body?, to?}}' + NL +
    '        Query (optional): force=1 to override an audit FAIL' + NL +
    '        """' + NL +
    '        import smtplib' + NL +
    '        from email.message import EmailMessage' + NL +
    '        from email.utils import formatdate, make_msgid' + NL +
    '        ' + NL +
    '        if getattr(request.state, "tier", None) != "founder":' + NL +
    '            return JSONResponse({"ok": False, "error": "founder_only"},' + NL +
    '                                status_code=403)' + NL +
    '        try:' + NL +
    '            body = await request.json()' + NL +
    '        except Exception:' + NL +
    '            body = {}' + NL +
    '        edits = body.get("edits", {}) or {}' + NL +
    '        force = request.query_params.get("force") in ("1", "true", "yes")' + NL +
    '        ' + NL +
    '        conn = sqlite3.connect(DB_PATH)' + NL +
    '        row = conn.execute("""' + NL +
    '            SELECT from_address, to_addresses, subject, body, status,' + NL +
    '                   agent_profile_id, agent_role' + NL +
    '            FROM outbound_email_queue WHERE queue_id=?' + NL +
    '        """, (queue_id,)).fetchone()' + NL +
    '        if not row:' + NL +
    '            conn.close()' + NL +
    '            return JSONResponse({"ok": False, "error": "not_found"},' + NL +
    '                                status_code=404)' + NL +
    '        if row[4] != "pending_review":' + NL +
    '            conn.close()' + NL +
    '            return JSONResponse({' + NL +
    '                "ok": False, "error": "not_pending",' + NL +
    '                "current_status": row[4]}, status_code=409)' + NL +
    '        ' + NL +
    '        from_addr = row[0]' + NL +
    '        to_list = edits.get("to") or json.loads(row[1])' + NL +
    '        if isinstance(to_list, str):' + NL +
    '            to_list = [to_list]' + NL +
    '        subject = edits.get("subject") or row[2]' + NL +
    '        body_text = edits.get("body") or row[3]' + NL +
    '        agent_pid = row[5]' + NL +
    '        agent_role = row[6] or "unknown"' + NL +
    '        ' + NL +
    '        now = _now()' + NL +
    '        approver_pid = getattr(request.state, "actor_account_id", "founder")' + NL +
    '        ' + NL +
    '        # ── PATCH-425: Run DeliverableAuditGate ──────────────────────────' + NL +
    '        audit_report_dict = None' + NL +
    '        audit_verdict = None' + NL +
    '        try:' + NL +
    '            import sys as _sys' + NL +
    '            if "/opt/Murphy-System" not in _sys.path:' + NL +
    '                _sys.path.insert(0, "/opt/Murphy-System")' + NL +
    '            from src.deliverable_audit_gate import DeliverableAuditGate' + NL +
    '            gate = DeliverableAuditGate(' + NL +
    '                pass_threshold=0.55,    # outbound email is lighter than full forge' + NL +
    '                warn_threshold=0.30,' + NL +
    '                min_length=80,          # short cold outreach is OK' + NL +
    '            )' + NL +
    '            # Synthesize a "prompt" for the audit gate from the email\'s own' + NL +
    '            # subject + role context. The gate then checks coverage,' + NL +
    '            # completeness, coherence, length adequacy of the body.' + NL +
    '            synth_prompt = (' + NL +
    '                f"Write a professional outbound email from a {agent_role} "' + NL +
    '                f"on subject: {subject}. The email must address the recipient '
                                                                          'clearly, "' + NL +
    '                f"deliver a coherent message, include a clear ask, and avoid "' + NL +
    '                f"empty/placeholder content."' + NL +
    '            )' + NL +
    '            report = gate.audit(' + NL +
    '                prompt=synth_prompt,' + NL +
    '                deliverable=body_text,' + NL +
    '                expected_format="email",' + NL +
    '                metadata={' + NL +
    '                    "queue_id": queue_id,' + NL +
    '                    "agent_profile_id": agent_pid,' + NL +
    '                    "agent_role": agent_role,' + NL +
    '                    "to_count": len(to_list),' + NL +
    '                },' + NL +
    '            )' + NL +
    '            audit_report_dict = report.to_dict()' + NL +
    '            audit_verdict = report.verdict.value  # "pass"|"warn"|"fail"' + NL +
    '            ' + NL +
    '            # Persist the audit report so OS Mail tab can show it' + NL +
    '            conn.execute("""' + NL +
    '                UPDATE outbound_email_queue' + NL +
    '                SET audit_report=?, audit_verdict=?, updated_at=?' + NL +
    '                WHERE queue_id=?' + NL +
    '            """, (json.dumps(audit_report_dict), audit_verdict, now, queue_id))' + NL +
    '            conn.commit()' + NL +
    '            ' + NL +
    '            if audit_verdict == "fail" and not force:' + NL +
    '                conn.execute("""' + NL +
    '                    UPDATE outbound_email_queue' + NL +
    '                    SET status=?, updated_at=?' + NL +
    '                    WHERE queue_id=?' + NL +
    '                """, ("audit_failed", now, queue_id))' + NL +
    '                conn.commit()' + NL +
    '                conn.close()' + NL +
    '                _emit("mail.outbound.audit_failed", {' + NL +
    '                    "queue_id": queue_id, "verdict": audit_verdict,' + NL +
    '                    "score": audit_report_dict.get("overall_score"),' + NL +
    '                })' + NL +
    '                return JSONResponse({' + NL +
    '                    "ok": False,' + NL +
    '                    "queue_id": queue_id,' + NL +
    '                    "error": "audit_failed",' + NL +
    '                    "audit_verdict": audit_verdict,' + NL +
    '                    "overall_score": audit_report_dict.get("overall_score"),' + NL +
    '                    "failed_checks": [' + NL +
    '                        c for c in audit_report_dict.get("checks", [])' + NL +
    '                        if c.get("status") == "fail"' + NL +
    '                    ],' + NL +
    '                    "hint": "POST again with ?force=1 to override (founder discretion)",' + NL +
    '                }, status_code=422)' + NL +
    '        except Exception as _audit_exc:' + NL +
    '            # Don\'t block delivery on audit gate bugs — log and proceed' + NL +
    '            try:' + NL +
    '                import logging' + NL +
    '                logging.getLogger(__name__).warning(' + NL +
    '                    "PATCH-425 audit gate errored, allowing send: %s", _audit_exc)' + NL +
    '            except Exception:' + NL +
    '                pass' + NL +
    '            audit_verdict = "skipped"' + NL +
    '        ' + NL +
    '        # ── PATCH-425: Real SMTP delivery ────────────────────────────────' + NL +
    '        msg = EmailMessage()' + NL +
    '        msg["From"] = from_addr or "sales@murphy.systems"' + NL +
    '        msg["To"] = ", ".join(to_list)' + NL +
    '        msg["Subject"] = subject' + NL +
    '        msg["Date"] = formatdate(localtime=False)' + NL +
    '        msg["Message-ID"] = make_msgid(domain="murphy.systems")' + NL +
    '        msg.set_content(body_text)' + NL +
    '        ' + NL +
    '        send_ok = False' + NL +
    '        send_err = None' + NL +
    '        smtp_message_id = msg["Message-ID"]' + NL +
    '        sent_via = "postfix_localhost"' + NL +
    '        try:' + NL +
    '            with smtplib.SMTP("127.0.0.1", 25, timeout=10) as smtp:' + NL +
    '                smtp.ehlo()' + NL +
    '                refused = smtp.send_message(msg)' + NL +
    '            if refused:' + NL +
    '                send_err = f"partial_refused: {refused}"' + NL +
    '            else:' + NL +
    '                send_ok = True' + NL +
    '        except Exception as exc:' + NL +
    '            send_err = f"{type(exc).__name__}: {exc}"' + NL +
    '        ' + NL +
    '        # Mark approved regardless (audit either passed or was overridden)' + NL +
    '        conn.execute("""' + NL +
    '            UPDATE outbound_email_queue' + NL +
    '            SET status=\'approved\', approved_by=?, approved_at=?, updated_at=?,' + NL +
    '                subject=?, body=?, to_addresses=?' + NL +
    '            WHERE queue_id=?' + NL +
    '        """, (approver_pid, now, now, subject, body_text,' + NL +
    '              json.dumps(to_list), queue_id))' + NL +
    '        ' + NL +
    '        if send_ok:' + NL +
    '            conn.execute("""' + NL +
    '                UPDATE outbound_email_queue' + NL +
    '                SET status=\'sent\', sent_at=?, sent_via=?, updated_at=?' + NL +
    '                WHERE queue_id=?' + NL +
    '            """, (now, sent_via, now, queue_id))' + NL +
    '        else:' + NL +
    '            conn.execute("""' + NL +
    '                UPDATE outbound_email_queue' + NL +
    '                SET status=\'failed\', failure_reason=?, updated_at=?' + NL +
    '                WHERE queue_id=?' + NL +
    '            """, (send_err, now, queue_id))' + NL +
    '        conn.commit()' + NL +
    '        conn.close()' + NL +
    '        ' + NL +
    '        _emit("mail.outbound.approved" if send_ok else "mail.outbound.failed",' + NL +
    '              {"queue_id": queue_id, "approver": approver_pid,' + NL +
    '               "to": to_list, "subject": subject,' + NL +
    '               "audit_verdict": audit_verdict,' + NL +
    '               "forced": force})' + NL +
    '        if send_ok:' + NL +
    '            _emit("mail.outbound.sent",' + NL +
    '                  {"queue_id": queue_id, "sent_via": sent_via,' + NL +
    '                   "message_id": smtp_message_id})' + NL +
    '        ' + NL +
    '        return JSONResponse({' + NL +
    '            "ok": send_ok,' + NL +
    '            "queue_id": queue_id,' + NL +
    '            "status": "sent" if send_ok else "failed",' + NL +
    '            "sent_via": sent_via if send_ok else None,' + NL +
    '            "message_id": smtp_message_id if send_ok else None,' + NL +
    '            "error": send_err,' + NL +
    '            "audit_verdict": audit_verdict,' + NL +
    '            "audit_score": (audit_report_dict or {}).get("overall_score"),' + NL +
    '            "forced": force,' + NL +
    '        })' + NL +
    '    ' + NL +
    '    # ── PATCH-425: GET audit report ─────────────────────────────────────' + NL +
    '    @app.get("/api/mail/outbound/{queue_id}/audit")' + NL +
    '    async def outbound_audit_report(queue_id: str, request: Request):' + NL +
    '        """Fetch the audit gate report for a queued draft.' + NL +
    '        ' + NL +
    '        Returns NULL audit_report for drafts not yet processed by approve.' + NL +
    '        """' + NL +
    '        if getattr(request.state, "tier", None) not in ("founder", "kin"):' + NL +
    '            return JSONResponse({"ok": False, "error": "forbidden"},' + NL +
    '                                status_code=403)' + NL +
    '        conn = sqlite3.connect(DB_PATH)' + NL +
    '        row = conn.execute(' + NL +
    '            "SELECT audit_report, audit_verdict, status, subject "' + NL +
    '            "FROM outbound_email_queue WHERE queue_id=?",' + NL +
    '            (queue_id,)).fetchone()' + NL +
    '        conn.close()' + NL +
    '        if not row:' + NL +
    '            return JSONResponse({"ok": False, "error": "not_found"},' + NL +
    '                                status_code=404)' + NL +
    '        return JSONResponse({' + NL +
    '            "ok": True,' + NL +
    '            "queue_id": queue_id,' + NL +
    '            "status": row[2],' + NL +
    '            "subject": row[3],' + NL +
    '            "audit_verdict": row[1],' + NL +
    '            "audit_report": json.loads(row[0]) if row[0] else None,' + NL +
    '        })' + NL +
    '' + NL +
    '' + NL
)

new_src = src[:start_idx] + NEW_BLOCK + src[end_idx:]

# Parse to be sure
ast.parse(new_src)
print("  ✓ AST parses")

backup = APP_PATH.with_suffix(".py.pre-425")
shutil.copy(APP_PATH, backup)
APP_PATH.write_text(new_src)
print(f"  ✓ wrote {APP_PATH} (backup: {backup.name})")
print()
print("  Restart murphy-edge to activate.")
