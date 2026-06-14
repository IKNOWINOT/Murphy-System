"""
Ship 31bh — HITL email builder with Accept / Reject / Revise.

Builds the multipart/alternative envelope that goes to all 4 recipients.
Visual aesthetic matches Ship 31ay (Modern Victorian + Gatsby Tech):
  - Midnight (#0a0f1e) background
  - Gold (#d4af37) accents
  - Centered card layout
  - Three distinct action buttons
"""
import html as _html
from datetime import datetime, timezone


def build_hitl_email(
    hitl_id: str,
    subject_matter: str,
    murphy_original: str,
    base44_critique: str = "",
    base44_suggestion: str = "",
    action_summary: str = "",
    context_lines: list = None,
    base_url: str = "https://murphy.systems",
) -> dict:
    """Return {subject, text, html} ready for the SMTP sender."""
    context_lines = context_lines or []
    
    subject = f"[Murphy HITL] {subject_matter}: {action_summary[:80]}"
    
    accept_url = f"{base_url}/api/hitl/{hitl_id}/accept"
    reject_url = f"{base_url}/api/hitl/{hitl_id}/reject"
    revise_url = f"{base_url}/hitl/{hitl_id}/revise"
    
    # Plain-text fallback
    text = f"""Murphy HITL — {subject_matter}

Action: {action_summary}

────────── ORIGINAL DRAFT ──────────
{murphy_original}

"""
    if base44_critique:
        text += f"────────── BASE44 CRITIQUE ──────────\n{base44_critique}\n\n"
    if base44_suggestion:
        text += f"────────── BASE44 SUGGESTED REVISION ──────────\n{base44_suggestion}\n\n"
    if context_lines:
        text += "────────── CONTEXT ──────────\n"
        for line in context_lines:
            text += f"  • {line}\n"
        text += "\n"
    text += f"""────────── ACTIONS ──────────

  ACCEPT (approve & execute):  {accept_url}
  REJECT (cancel):             {reject_url}
  REVISE (edit and send):      {revise_url}

— Murphy
HITL ID: {hitl_id}
"""

    # HTML envelope
    suggestion_block = ""
    if base44_suggestion:
        suggestion_block = f"""
        <div style="margin-top:20px;padding:18px;background:#1a2233;border-left:3px solid #d4af37;border-radius:4px">
          <div style="color:#d4af37;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px">Base44 Suggested Revision</div>
          <div style="color:#e8e6df;font-size:14px;line-height:1.7;white-space:pre-wrap">{_html.escape(base44_suggestion)}</div>
        </div>
        """
    
    critique_block = ""
    if base44_critique:
        critique_block = f"""
        <div style="margin-top:16px;padding:14px;background:#0f1525;border-left:3px solid #7a8aa8;border-radius:4px">
          <div style="color:#7a8aa8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">Base44 Critique</div>
          <div style="color:#9ca7bc;font-size:13px;line-height:1.6">{_html.escape(base44_critique)}</div>
        </div>
        """
    
    context_block = ""
    if context_lines:
        items = "".join(f"<li style='margin-bottom:6px'>{_html.escape(c)}</li>" for c in context_lines)
        context_block = f"""
        <div style="margin-top:20px;padding:14px;background:#0f1525;border-radius:4px">
          <div style="color:#7a8aa8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px">Context</div>
          <ul style="color:#9ca7bc;font-size:13px;line-height:1.6;margin:0;padding-left:20px">{items}</ul>
        </div>
        """
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:40px 20px;background:#0a0f1e;font-family:Georgia,'Times New Roman',serif">
  <div style="max-width:640px;margin:0 auto;background:#141a2c;border:1px solid #2a3142;border-radius:8px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.5)">
    
    <!-- Monogram header -->
    <div style="background:linear-gradient(135deg,#141a2c 0%,#1a2240 100%);padding:32px 40px;text-align:center;border-bottom:1px solid #d4af37">
      <div style="display:inline-block;width:48px;height:48px;border:1px solid #d4af37;border-radius:50%;line-height:46px;text-align:center;color:#d4af37;font-size:24px;font-family:Georgia,serif;letter-spacing:-1px">M</div>
      <div style="color:#d4af37;font-size:11px;letter-spacing:4px;text-transform:uppercase;margin-top:14px">Murphy · Human In The Loop</div>
      <div style="color:#7a8aa8;font-size:12px;margin-top:4px">{_html.escape(subject_matter)}</div>
    </div>
    
    <!-- Body -->
    <div style="padding:36px 40px">
      
      <div style="color:#e8e6df;font-size:16px;line-height:1.6;margin-bottom:24px">
        <strong style="color:#d4af37">Action:</strong> {_html.escape(action_summary)}
      </div>
      
      <div style="padding:18px;background:#0f1525;border-left:3px solid #d4af37;border-radius:4px">
        <div style="color:#d4af37;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px">Murphy Original Draft</div>
        <div style="color:#e8e6df;font-size:14px;line-height:1.7;white-space:pre-wrap">{_html.escape(murphy_original)}</div>
      </div>
      
      {critique_block}
      {suggestion_block}
      {context_block}
      
      <!-- Action buttons -->
      <table cellpadding="0" cellspacing="0" border="0" style="width:100%;margin-top:32px">
        <tr>
          <td style="padding:0 6px" align="center">
            <a href="{accept_url}" style="display:block;background:#1e7e4a;color:#fff;padding:14px 0;text-decoration:none;border-radius:6px;font-family:Georgia,serif;font-size:14px;letter-spacing:1px;text-transform:uppercase;font-weight:bold;border:1px solid #2a9456">Accept</a>
          </td>
          <td style="padding:0 6px" align="center">
            <a href="{revise_url}" style="display:block;background:#d4af37;color:#0a0f1e;padding:14px 0;text-decoration:none;border-radius:6px;font-family:Georgia,serif;font-size:14px;letter-spacing:1px;text-transform:uppercase;font-weight:bold;border:1px solid #e8c54f">Revise</a>
          </td>
          <td style="padding:0 6px" align="center">
            <a href="{reject_url}" style="display:block;background:#7e1e2a;color:#fff;padding:14px 0;text-decoration:none;border-radius:6px;font-family:Georgia,serif;font-size:14px;letter-spacing:1px;text-transform:uppercase;font-weight:bold;border:1px solid #94262f">Reject</a>
          </td>
        </tr>
      </table>
      
      <div style="text-align:center;margin-top:20px">
        <div style="color:#5a6478;font-size:11px;letter-spacing:1px">
          <span style="color:#1e7e4a">●</span> approve &amp; execute &nbsp; · &nbsp;
          <span style="color:#d4af37">●</span> edit then send &nbsp; · &nbsp;
          <span style="color:#7e1e2a">●</span> cancel
        </div>
      </div>
    </div>
    
    <!-- Footer -->
    <div style="background:#0a0f1e;padding:20px 40px;border-top:1px solid #2a3142;text-align:center">
      <div style="color:#5a6478;font-size:11px;letter-spacing:1px">
        HITL ID: <span style="color:#7a8aa8;font-family:Menlo,monospace">{hitl_id}</span>
      </div>
      <div style="color:#5a6478;font-size:10px;margin-top:6px">
        Inoni LLC · Portland, OR · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
      </div>
    </div>
    
  </div>
</body></html>"""

    return {
        "subject":   subject,
        "text":      text,
        "html":      html,
        "accept_url": accept_url,
        "reject_url": reject_url,
        "revise_url": revise_url,
    }


if __name__ == "__main__":
    out = build_hitl_email(
        hitl_id="hitl_demo_abc123",
        subject_matter="prospect_reply",
        murphy_original="Hi Tom,\n\nThanks for your inquiry about the chillers.\nWe can ship within 2 weeks at $24,500 per unit.\n\nBest,\nMurphy",
        base44_critique="Tone is appropriate. Consider adding lead time confidence interval.",
        base44_suggestion="Hi Tom,\n\nThanks for the inquiry. We can ship within 10-14 business days at $24,500 per unit, with shipping confirmed once the deposit clears.\n\nBest,\nMurphy",
        action_summary="Reply to Tom Briggs at Apex GC re: chiller quote",
        context_lines=["Deal value: $66,000", "Prospect since: 2026-05-22", "Last contact: 4 days ago"],
    )
    # Write the HTML out for a visual check
    with open("/tmp/hitl_demo.html", "w") as f:
        f.write(out["html"])
    print("Subject:", out["subject"])
    print(f"\nHTML saved to /tmp/hitl_demo.html ({len(out['html'])} bytes)")
    print(f"Plain text preview:\n{out['text'][:400]}...")
