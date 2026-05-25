"""
PATCH-435 — Wire the agent_action_policy table into the email submit path
==========================================================================

WHAT THIS IS:
  Modifies src/patch417_outbound_queue.py so that when an agent submits a
  draft email, the system checks the agent_action_policy table for
  (agent_role, 'email_outbound'). If master_enabled=1 AND the audit gate
  scores >= min_confidence AND runs_today < max_per_day, the email is
  auto-approved, sent immediately via Postfix, and the daily counter is
  incremented. Otherwise it stays in pending_review for human review.

WHY:
  Founder directive 2026-05-25: "Yes but as a toggle that I can turn off
  and on or base on confidence level." PATCH-434 built the policy table
  and the dial. PATCH-435 makes the dial actually do something.

HOW IT FITS:
  - Reads policy from murphy_mail.db.agent_action_policy
  - Calls existing DeliverableAuditGate (PATCH-425) for confidence score
  - Reuses existing inline SMTP send by extracting it into a helper
  - Emits 'mail.outbound.auto_approved' or 'mail.outbound.auto_send_failed'
    event for audit
  - All 24 policies start at master_enabled=0, so the new branch is
    INERT until the founder explicitly enables a (role, action_type)

KEY INVARIANT:
  If agent_role is empty/null, the policy lookup MUST fail closed →
  status stays pending_review. No role = no autonomy.

LAST UPDATED: 2026-05-25 by PATCH-435
"""
import ast
import shutil
import sqlite3
from pathlib import Path

NL = chr(10)

PATCH_FILE = Path("/opt/Murphy-System/src/patch417_outbound_queue.py")
src = PATCH_FILE.read_text()

if "PATCH-435" in src:
    print("  ⚠ PATCH-435 already applied — skipping")
    raise SystemExit(0)

# ─── Step 1: add the policy check helper at top of file ────────────────
# Find the _emit helper as anchor — we insert our helpers right after it
anchor = "def _emit(event_type: str, payload: dict) -> None:"
if anchor not in src:
    print("  ✗ couldn't find _emit anchor")
    raise SystemExit(1)

# Locate end of the _emit function (next 'def' at column 0)
emit_start = src.index(anchor)
remainder = src[emit_start:]
# Find next 'def ' at start of line after _emit body
lines = remainder.split(NL)
emit_end_relative = 0
seen_body = False
for i, line in enumerate(lines[1:], 1):
    if line.startswith("def ") or line.startswith("class ") or line.startswith("@app"):
        emit_end_relative = i
        break
    if line.strip():
        seen_body = True
if not emit_end_relative:
    print("  ✗ couldn't find end of _emit function")
    raise SystemExit(1)
insertion_point = emit_start + sum(len(l)+1 for l in lines[:emit_end_relative])

POLICY_HELPER = NL.join([
    "",
    "# ─── PATCH-435: Autonomy policy check + send helper ────────────────────",
    "POLICY_DB = '/var/lib/murphy-production/murphy_mail.db'",
    "",
    "",
    "def _check_autonomy_policy(agent_role, action_type='email_outbound'):",
    '    """PATCH-435: Look up policy for (role, action_type).',
    "    ",
    "    Returns dict {allowed, master_enabled, min_confidence, max_per_day,",
    "    runs_today, has_audit_gate, reason} — always returns a dict, never",
    "    raises. If agent_role is missing/empty, returns allowed=False.",
    '    """',
    "    if not agent_role:",
    "        return {'allowed': False, 'reason': 'no_agent_role'}",
    "    try:",
    "        c = sqlite3.connect(POLICY_DB)",
    "        c.row_factory = sqlite3.Row",
    "        row = c.execute(",
    "            'SELECT * FROM agent_action_policy WHERE role=? AND action_type=?',",
    "            (agent_role, action_type)",
    "        ).fetchone()",
    "        c.close()",
    "    except Exception as e:",
    "        return {'allowed': False, 'reason': f'db_error:{e}'}",
    "    if not row:",
    "        return {'allowed': False, 'reason': 'no_policy_row'}",
    "    r = dict(row)",
    "    if not r.get('master_enabled'):",
    "        return {'allowed': False, 'reason': 'master_disabled', **r}",
    "    if not r.get('has_audit_gate'):",
    "        return {'allowed': False, 'reason': 'no_audit_gate', **r}",
    "    if r.get('runs_today', 0) >= r.get('max_per_day', 0):",
    "        return {'allowed': False, 'reason': 'daily_cap_reached', **r}",
    "    return {'allowed': True, **r}",
    "",
    "",
    "def _run_audit_gate(subject, body_text, agent_role, queue_id, to_count):",
    '    """PATCH-435: Run DeliverableAuditGate, return (verdict, score, report_dict).',
    "    Returns (None, 0.0, None) on any error — caller must treat error as fail.",
    '    """',
    "    try:",
    "        import sys as _sys",
    "        if '/opt/Murphy-System' not in _sys.path:",
    "            _sys.path.insert(0, '/opt/Murphy-System')",
    "        from src.deliverable_audit_gate import DeliverableAuditGate",
    "        gate = DeliverableAuditGate(pass_threshold=0.55, warn_threshold=0.30, min_length=80)",
    "        synth_prompt = (",
    "            f'Write a professional outbound email from a {agent_role} '",
    "            f'on subject: {subject}. Must address recipient clearly, '",
    "            f'deliver coherent message, include clear ask, avoid placeholders.'",
    "        )",
    "        report = gate.audit(",
    "            prompt=synth_prompt, deliverable=body_text,",
    "            expected_format='email',",
    "            metadata={'queue_id': queue_id, 'agent_role': agent_role,",
    "                      'to_count': to_count, 'pathway': 'patch435_auto'}",
    "        )",
    "        return report.verdict.value, float(getattr(report, 'score', 0.0)), report.to_dict()",
    "    except Exception as e:",
    "        log.exception('PATCH-435 audit gate error')",
    "        return None, 0.0, {'error': str(e)}",
    "",
    "",
    "def _send_via_postfix(from_addr, to_list, subject, body_text):",
    '    """PATCH-435: Send via local Postfix on 127.0.0.1:25.',
    "    Returns (ok: bool, err: str|None, sent_via: str).",
    '    """',
    "    import smtplib",
    "    from email.message import EmailMessage",
    "    from email.utils import formatdate, make_msgid",
    "    try:",
    "        msg = EmailMessage()",
    "        msg['From'] = from_addr",
    "        msg['To'] = ', '.join(to_list)",
    "        msg['Subject'] = subject",
    "        msg['Date'] = formatdate(localtime=True)",
    "        msg['Message-ID'] = make_msgid(domain='murphy.systems')",
    "        msg.set_content(body_text)",
    "        with smtplib.SMTP('127.0.0.1', 25, timeout=10) as smtp:",
    "            smtp.send_message(msg)",
    "        return True, None, 'smtp_postfix'",
    "    except Exception as e:",
    "        log.exception('PATCH-435 SMTP send failed')",
    "        return False, str(e), None",
    "",
    "",
    "def _increment_daily_counter(agent_role, action_type='email_outbound'):",
    '    """PATCH-435: Increment runs_today + runs_total for a (role, action) policy."""',
    "    try:",
    "        c = sqlite3.connect(POLICY_DB)",
    "        c.execute(",
    "            'UPDATE agent_action_policy '",
    "            'SET runs_today = runs_today + 1, runs_total = runs_total + 1 '",
    "            'WHERE role=? AND action_type=?',",
    "            (agent_role, action_type)",
    "        )",
    "        c.commit()",
    "        c.close()",
    "    except Exception:",
    "        log.exception('PATCH-435 counter increment failed')",
    "",
    "",
])

new_src = src[:insertion_point] + POLICY_HELPER + src[insertion_point:]

# ─── Step 2: insert the autonomy branch into outbound_submit ────────────
# Find the return JSONResponse({"ok": True, "queue_id": queue_id, "status": "pending_review", ...
# That's the SUCCESS return from submit. We branch BEFORE it.
submit_anchor = NL.join([
    '        _emit("mail.outbound.submitted", {',
    '            "queue_id": queue_id, "agent": agent_pid, "to": to,',
    '            "subject": body.get("subject"),',
    '            "urgency": body.get("urgency", "normal"),',
    '        })',
])
if submit_anchor not in new_src:
    print("  ✗ couldn't find submit anchor — flow may have changed")
    raise SystemExit(1)

AUTONOMY_BRANCH = NL.join([
    submit_anchor,
    "",
    "        # ─── PATCH-435: Autonomy policy check ───────────────────────",
    "        # If policy says (role, email_outbound) is master_enabled AND",
    "        # audit gate scores >= min_confidence AND under daily cap,",
    "        # auto-approve and send NOW. Otherwise leave in pending_review.",
    "        autonomy_outcome = 'human_review'",
    "        autonomy_detail = None",
    "        policy = _check_autonomy_policy(agent_role, 'email_outbound')",
    "        if policy.get('allowed'):",
    "            # Run audit gate synchronously",
    "            verdict, score, report = _run_audit_gate(",
    "                subject=body.get('subject', ''),",
    "                body_text=body.get('body', ''),",
    "                agent_role=agent_role,",
    "                queue_id=queue_id,",
    "                to_count=len(to),",
    "            )",
    "            min_conf = float(policy.get('min_confidence', 1.0))",
    "            if verdict is None:",
    "                autonomy_outcome = 'audit_gate_error'",
    "                autonomy_detail = {'reason': 'gate_threw_exception', 'verdict': None}",
    "            elif score < min_conf:",
    "                autonomy_outcome = 'below_confidence_threshold'",
    "                autonomy_detail = {'verdict': verdict, 'score': score,",
    "                                    'required': min_conf}",
    "            else:",
    "                # Confidence cleared — send via Postfix",
    "                ok, err, sent_via = _send_via_postfix(",
    "                    from_addr, to, body.get('subject', ''), body.get('body', '')",
    "                )",
    "                send_now = _now()",
    "                if ok:",
    "                    autonomy_outcome = 'auto_approved'",
    "                    autonomy_detail = {'verdict': verdict, 'score': score,",
    "                                        'sent_via': sent_via}",
    "                    try:",
    "                        c2 = sqlite3.connect(DB_PATH)",
    "                        c2.execute(",
    "                            'UPDATE outbound_email_queue SET status=?, '",
    "                            'approved_by=?, approved_at=?, sent_at=?, sent_via=?, '",
    "                            'audit_report=?, audit_verdict=?, updated_at=? '",
    "                            'WHERE queue_id=?',",
    "                            ('sent', 'autonomy_policy', send_now, send_now,",
    "                             sent_via, json.dumps(report) if report else None,",
    "                             verdict, send_now, queue_id)",
    "                        )",
    "                        c2.commit()",
    "                        c2.close()",
    "                    except Exception:",
    "                        log.exception('PATCH-435 status update failed')",
    "                    _increment_daily_counter(agent_role, 'email_outbound')",
    "                    _emit('mail.outbound.auto_approved', {",
    "                        'queue_id': queue_id, 'agent_role': agent_role,",
    "                        'score': score, 'verdict': verdict, 'to': to,",
    "                        'subject': body.get('subject'),",
    "                    })",
    "                else:",
    "                    autonomy_outcome = 'auto_send_failed'",
    "                    autonomy_detail = {'verdict': verdict, 'score': score,",
    "                                        'smtp_error': err}",
    "                    try:",
    "                        c2 = sqlite3.connect(DB_PATH)",
    "                        c2.execute(",
    "                            'UPDATE outbound_email_queue SET status=?, '",
    "                            'failure_reason=?, updated_at=? WHERE queue_id=?',",
    "                            ('auto_send_failed', err, send_now, queue_id)",
    "                        )",
    "                        c2.commit()",
    "                        c2.close()",
    "                    except Exception:",
    "                        log.exception('PATCH-435 fail-status update failed')",
    "                    _emit('mail.outbound.auto_send_failed', {",
    "                        'queue_id': queue_id, 'agent_role': agent_role,",
    "                        'error': err, 'subject': body.get('subject'),",
    "                    })",
    "        else:",
    "            autonomy_detail = {'reason': policy.get('reason'),",
    "                                'master_enabled': policy.get('master_enabled'),",
    "                                'has_audit_gate': policy.get('has_audit_gate')}",
    "",
])

# We want to insert the branch AFTER the existing _emit("mail.outbound.submitted")
# but BEFORE the existing 'return JSONResponse({"ok": True, ...})'. Find that return:
return_anchor = '        return JSONResponse({' + NL + '            "ok": True, "queue_id": queue_id,'
if return_anchor not in new_src:
    print("  ✗ couldn't find submit return anchor")
    raise SystemExit(1)

# Replace the emit anchor with emit anchor + autonomy branch
new_src = new_src.replace(submit_anchor, AUTONOMY_BRANCH, 1)

# Now update the response to include autonomy_outcome so caller knows what happened
old_return = (
    '        return JSONResponse({' + NL +
    '            "ok": True, "queue_id": queue_id,' + NL +
    '            "status": "pending_review",' + NL +
    '            "review_url": f"/api/mail/outbound/{queue_id}",' + NL +
    '        })'
)
new_return = (
    '        # PATCH-435: response reflects autonomy outcome' + NL +
    '        response_status = "sent" if autonomy_outcome == "auto_approved" else "pending_review"' + NL +
    '        return JSONResponse({' + NL +
    '            "ok": True, "queue_id": queue_id,' + NL +
    '            "status": response_status,' + NL +
    '            "review_url": f"/api/mail/outbound/{queue_id}",' + NL +
    '            "autonomy_outcome": autonomy_outcome,' + NL +
    '            "autonomy_detail": autonomy_detail,' + NL +
    '        })'
)
if old_return in new_src:
    new_src = new_src.replace(old_return, new_return, 1)
    print("  ✓ updated submit response to surface autonomy_outcome")
else:
    print("  ⚠ couldn't update return — autonomy will run silently (still functional)")

# Validate syntax before writing
ast.parse(new_src)

shutil.copy(PATCH_FILE, PATCH_FILE.with_suffix(".py.pre-435"))
PATCH_FILE.write_text(new_src)
print(f"  ✓ wrote patch417_outbound_queue.py ({len(new_src)} bytes, was {len(src)})")
print(f"  ✓ backup at {PATCH_FILE.with_suffix('.py.pre-435')}")
print()
print("  ▶ Restart murphy-edge to pick up the change")
