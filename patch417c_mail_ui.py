#!/usr/bin/env python3
"""
PATCH-417c — Mail tab UI: real queue review interface
=======================================================

WHAT THIS IS:
  Upgrades the Mail tab in murphy-os.html from placeholder text to a live
  review queue interface. Connects to the PATCH-417 endpoints on murphy-edge.

WHY IT EXISTS:
  The backend queue works (PATCH-417 + 417b). Without a UI, the founder still
  has to curl the API to approve swarm emails. The OS Mail tab is the actual
  human-in-the-loop surface that gates Phase 5a from going live.

HOW IT FITS:
  - Patches /opt/Murphy-System/static/murphy-os.html
  - Replaces the "Phase 7a will populate this..." placeholder with a real
    React-free vanilla JS list bound to /api/mail/outbound/queue
  - Adds polling (every 30s) and a stats badge on the Mail tab
  - Approve/Reject buttons hit /approve and /reject endpoints

LAST UPDATED: 2026-05-25 by PATCH-417c
"""
import shutil
from pathlib import Path

OS_PATH = Path("/opt/Murphy-System/static/murphy-os.html")


# Replace the entire mail-outbound-queue placeholder div content with a live container
OLD_BLOCK = '''        <div style="background:#0d1428;border:1px solid rgba(94,224,196,0.2);border-radius:8px;padding:20px;margin-bottom:16px;">
          <h3 style="color:#5ee0c4;margin:0 0 12px;font-size:14px;">📤 Outbound review queue</h3>
          <div id="mail-outbound-queue" style="display:flex;flex-direction:column;gap:8px;color:#cde;">
            <div style="color:#8aa;font-style:italic;">Phase 7a will populate this with emails Murphy is about to send, awaiting your review.</div>
          </div>
        </div>'''

NEW_BLOCK = '''        <!-- PATCH-417c: live outbound review queue -->
        <div style="background:#0d1428;border:1px solid rgba(94,224,196,0.2);border-radius:8px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3 style="color:#5ee0c4;margin:0;font-size:14px;">📤 Outbound review queue</h3>
            <div style="display:flex;gap:8px;align-items:center;">
              <span id="mail-stats-pending" style="background:rgba(255,200,80,0.15);color:#fc8;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;">— pending</span>
              <span id="mail-stats-sent" style="background:rgba(94,224,196,0.15);color:#5ee0c4;padding:3px 10px;border-radius:12px;font-size:11px;">— sent</span>
              <span id="mail-stats-rejected" style="background:rgba(255,100,100,0.15);color:#f88;padding:3px 10px;border-radius:12px;font-size:11px;">— rejected</span>
              <button onclick="mailRefresh()" style="background:transparent;border:1px solid rgba(94,224,196,0.3);color:#5ee0c4;padding:3px 10px;border-radius:4px;font-size:11px;cursor:pointer;">↻</button>
            </div>
          </div>
          <div id="mail-outbound-queue" style="display:flex;flex-direction:column;gap:10px;color:#cde;">
            <div style="color:#8aa;font-style:italic;">Loading queue…</div>
          </div>
        </div>'''


# JS block to inject before </script> (end of main script)
JS_BLOCK = '''
// ── PATCH-417c: Mail outbound review queue ─────────────────────────
async function mailRefresh() {
  const container = document.getElementById('mail-outbound-queue');
  if (!container) return;

  try {
    // Stats
    const statsResp = await fetch(BASE + '/api/mail/outbound/stats', {credentials: 'include'});
    if (statsResp.ok) {
      const s = await statsResp.json();
      document.getElementById('mail-stats-pending').textContent = (s.pending_review || 0) + ' pending';
      document.getElementById('mail-stats-sent').textContent = (s.sent || 0) + ' sent';
      document.getElementById('mail-stats-rejected').textContent = (s.rejected || 0) + ' rejected';
    }

    // Queue items
    const resp = await fetch(BASE + '/api/mail/outbound/queue?status=pending_review&limit=50', {credentials: 'include'});
    if (!resp.ok) {
      container.innerHTML = '<div style="color:#f88;">Could not load queue: HTTP ' + resp.status + '</div>';
      return;
    }
    const data = await resp.json();
    const items = data.items || [];
    if (items.length === 0) {
      container.innerHTML = '<div style="color:#8aa;font-style:italic;padding:8px;">Queue is empty. No emails awaiting review.</div>';
      return;
    }

    container.innerHTML = items.map(it => {
      const urgencyColor = it.urgency === 'high' ? '#f88' : (it.urgency === 'low' ? '#8aa' : '#fc8');
      const toStr = Array.isArray(it.to) ? it.to.join(', ') : (it.to || '');
      const agentLabel = it.agent_class ? (it.agent_class + ' / ' + (it.agent_role || '')) : (it.agent_role || 'unknown');
      const safeBody = (it.body_preview || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const safeSubject = (it.subject || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return `
        <div style="border:1px solid rgba(94,224,196,0.12);border-radius:6px;padding:12px;background:rgba(10,14,26,0.6);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-size:11px;color:${urgencyColor};font-weight:600;text-transform:uppercase;">${it.urgency}</span>
            <span style="font-size:10px;color:#8aa;">${agentLabel} · ${new Date(it.created_at).toLocaleTimeString()}</span>
          </div>
          <div style="font-size:11px;color:#8aa;margin-bottom:4px;">To: ${toStr}</div>
          <div style="font-size:13px;color:#cde;font-weight:600;margin-bottom:6px;">${safeSubject}</div>
          <div style="font-size:12px;color:#aab;line-height:1.5;margin-bottom:10px;font-style:italic;">${safeBody}${(it.body_preview||'').length>=200?'…':''}</div>
          <div style="display:flex;gap:8px;">
            <button onclick="mailApprove('${it.queue_id}')"
              style="background:rgba(94,224,196,0.15);color:#5ee0c4;border:1px solid rgba(94,224,196,0.4);padding:5px 14px;border-radius:4px;font-size:11px;cursor:pointer;">✓ Approve & send</button>
            <button onclick="mailReject('${it.queue_id}')"
              style="background:rgba(255,100,100,0.1);color:#f88;border:1px solid rgba(255,100,100,0.3);padding:5px 14px;border-radius:4px;font-size:11px;cursor:pointer;">✗ Reject</button>
            <button onclick="mailViewFull('${it.queue_id}')"
              style="background:transparent;color:#8aa;border:1px solid rgba(255,255,255,0.1);padding:5px 14px;border-radius:4px;font-size:11px;cursor:pointer;margin-left:auto;">↗ Full view</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('mailRefresh failed', err);
    container.innerHTML = '<div style="color:#f88;">Error: ' + err.message + '</div>';
  }
}

async function mailApprove(queueId) {
  if (!confirm('Approve and send this email?')) return;
  try {
    const resp = await fetch(BASE + '/api/mail/outbound/' + queueId + '/approve', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',
      body: '{}',
    });
    const data = await resp.json();
    if (data.ok) {
      mailRefresh();
    } else {
      alert('Approve failed: ' + (data.error || JSON.stringify(data)));
    }
  } catch (err) {
    alert('Network error: ' + err.message);
  }
}

async function mailReject(queueId) {
  const reason = prompt('Reason for rejection (will be shown to the swarm agent for learning):', '');
  if (reason === null) return;  // user hit cancel
  try {
    const resp = await fetch(BASE + '/api/mail/outbound/' + queueId + '/reject', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include',
      body: JSON.stringify({reason: reason || 'no_reason'}),
    });
    const data = await resp.json();
    if (data.ok) {
      mailRefresh();
    } else {
      alert('Reject failed: ' + (data.error || JSON.stringify(data)));
    }
  } catch (err) {
    alert('Network error: ' + err.message);
  }
}

async function mailViewFull(queueId) {
  try {
    const resp = await fetch(BASE + '/api/mail/outbound/' + queueId, {credentials: 'include'});
    const data = await resp.json();
    if (!data.ok) {
      alert('Could not load: ' + (data.error || 'unknown'));
      return;
    }
    // Use the existing drill panel
    if (typeof openDrillPanel === 'function') {
      const it = data.item;
      const bodyHTML = '<div style="padding:18px;color:#cde;font-size:13px;line-height:1.6;">' +
        '<h3 style="color:#5ee0c4;margin:0 0 12px;">' + (it.subject || '') + '</h3>' +
        '<div style="font-size:11px;color:#8aa;margin-bottom:14px;">' +
        'From: ' + (it.from_address || '') + '<br>' +
        'To: ' + (Array.isArray(it.to_addresses) ? it.to_addresses.join(', ') : '') + '<br>' +
        'Agent: ' + (it.agent_class || '') + ' / ' + (it.agent_role || '') + '<br>' +
        'Submitted: ' + it.created_at +
        '</div>' +
        '<pre style="background:#0a0e1a;padding:12px;border-radius:4px;white-space:pre-wrap;color:#cde;font-family:inherit;font-size:12px;">' +
        (it.body || '').replace(/</g, '&lt;') + '</pre>' +
        '</div>';
      openDrillPanel(bodyHTML, 'Email — ' + (it.subject || queueId));
    } else {
      alert(JSON.stringify(data.item, null, 2).substring(0, 800));
    }
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

// Auto-refresh when Mail tab becomes visible. Hooks into switchPage if it exists.
(function() {
  let mailPollTimer = null;
  const origSwitch = window.switchPage;
  if (typeof origSwitch === 'function') {
    window.switchPage = function(page) {
      origSwitch(page);
      if (page === 'mail') {
        mailRefresh();
        if (mailPollTimer) clearInterval(mailPollTimer);
        mailPollTimer = setInterval(mailRefresh, 30000);
      } else if (mailPollTimer) {
        clearInterval(mailPollTimer);
        mailPollTimer = null;
      }
    };
  }
  // Also do an initial fetch in case mail tab is the default
  setTimeout(() => { if (document.getElementById('mail-outbound-queue')) mailRefresh(); }, 1500);
})();
'''


def main():
    print("═" * 64)
    print("  PATCH-417c — Mail tab UI")
    print("═" * 64)

    src = OS_PATH.read_text()
    if "PATCH-417c" in src:
        print("  ⚠ PATCH-417c already applied — skipping")
        return

    if OLD_BLOCK not in src:
        print("  ✗ Old placeholder block not found — html may have drifted")
        print("    Looking for first 80 chars:")
        idx = src.find('id="mail-outbound-queue"')
        if idx > 0:
            print(f"    found mail-outbound-queue at offset {idx}")
            print(f"    context: ...{src[max(0,idx-80):idx+100]}...")
        return

    new = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

    # Inject JS_BLOCK before the LAST </script> tag in the file
    last_script = new.rfind("</script>")
    if last_script < 0:
        print("  ✗ no </script> found")
        return
    new = new[:last_script] + JS_BLOCK + "\n" + new[last_script:]

    backup = OS_PATH.with_suffix(".html.pre-417c")
    shutil.copy(OS_PATH, backup)
    OS_PATH.write_text(new)
    print(f"  ✓ HTML patched: {len(src)} → {len(new)} bytes")
    print(f"  ✓ backup at {backup}")


if __name__ == "__main__":
    main()
