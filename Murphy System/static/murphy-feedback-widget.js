/* Murphy Global Feedback Widget (GFB-006)
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 *
 * Drop-in web component: <murphy-feedback-widget api-url="/api"></murphy-feedback-widget>
 * Renders a floating feedback button + modal form that submits to /api/feedback/submit.
 */

class MurphyFeedbackWidget extends HTMLElement {
  connectedCallback() {
    const api = this.getAttribute('api-url') || '/api';
    this._api = api;
    this.innerHTML = `
      <style>
        .mfb-trigger{position:fixed;bottom:24px;right:24px;z-index:9999;
          background:var(--murphy-accent,#6366f1);color:#fff;border:none;
          border-radius:50%;width:56px;height:56px;font-size:24px;cursor:pointer;
          box-shadow:0 4px 12px rgba(0,0,0,.25);transition:transform .2s}
        .mfb-trigger:hover{transform:scale(1.1)}
        .mfb-overlay{display:none;position:fixed;inset:0;z-index:10000;
          background:rgba(0,0,0,.5);align-items:center;justify-content:center}
        .mfb-overlay.open{display:flex}
        .mfb-modal{background:var(--murphy-bg,#1a1a2e);color:var(--murphy-text,#e0e0e0);
          border-radius:12px;padding:24px;width:min(480px,90vw);max-height:85vh;
          overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.4)}
        .mfb-modal h2{margin:0 0 16px;font-size:1.25rem;color:var(--murphy-accent,#6366f1)}
        .mfb-modal label{display:block;margin:8px 0 4px;font-size:.85rem;opacity:.8}
        .mfb-modal input,.mfb-modal textarea,.mfb-modal select{
          width:100%;padding:8px 10px;border:1px solid #333;border-radius:6px;
          background:var(--murphy-input-bg,#16162a);color:var(--murphy-text,#e0e0e0);
          font-family:inherit;font-size:.9rem;box-sizing:border-box}
        .mfb-modal textarea{min-height:80px;resize:vertical}
        .mfb-row{display:flex;gap:12px}
        .mfb-row>*{flex:1}
        .mfb-actions{display:flex;gap:8px;margin-top:16px;justify-content:flex-end}
        .mfb-btn{padding:8px 18px;border:none;border-radius:6px;cursor:pointer;font-size:.9rem}
        .mfb-btn-primary{background:var(--murphy-accent,#6366f1);color:#fff}
        .mfb-btn-secondary{background:#333;color:#ccc}
        .mfb-msg{margin-top:12px;padding:8px;border-radius:6px;font-size:.85rem;display:none}
        .mfb-msg.ok{display:block;background:#064e3b;color:#6ee7b7}
        .mfb-msg.err{display:block;background:#7f1d1d;color:#fca5a5}
      </style>
      <button class="mfb-trigger" title="Send Feedback">💬</button>
      <div class="mfb-overlay">
        <div class="mfb-modal">
          <h2>☠ Report an Issue</h2>
          <label for="mfb-title">Title *</label>
          <input id="mfb-title" placeholder="Short summary of the problem" maxlength="256">
          <label for="mfb-desc">Description *</label>
          <textarea id="mfb-desc" placeholder="What happened? Be as detailed as possible." maxlength="8192"></textarea>
          <div class="mfb-row">
            <div>
              <label for="mfb-sev">Severity</label>
              <select id="mfb-sev">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label for="mfb-comp">Component</label>
              <input id="mfb-comp" placeholder="e.g. Dashboard, Calendar">
            </div>
          </div>
          <label for="mfb-steps">Steps to Reproduce</label>
          <textarea id="mfb-steps" placeholder="1. Go to ...\n2. Click on ..." maxlength="4096"></textarea>
          <div class="mfb-row">
            <div>
              <label for="mfb-exp">Expected Behavior</label>
              <input id="mfb-exp" placeholder="What should happen?" maxlength="2048">
            </div>
            <div>
              <label for="mfb-act">Actual Behavior</label>
              <input id="mfb-act" placeholder="What actually happened?" maxlength="2048">
            </div>
          </div>
          <div class="mfb-msg" id="mfb-msg"></div>
          <div class="mfb-actions">
            <button class="mfb-btn mfb-btn-secondary" id="mfb-cancel">Cancel</button>
            <button class="mfb-btn mfb-btn-primary" id="mfb-submit">Submit Feedback</button>
          </div>
        </div>
      </div>`;

    const trigger = this.querySelector('.mfb-trigger');
    const overlay = this.querySelector('.mfb-overlay');
    const cancel  = this.querySelector('#mfb-cancel');
    const submit  = this.querySelector('#mfb-submit');

    trigger.addEventListener('click', () => overlay.classList.add('open'));
    cancel.addEventListener('click', () => { overlay.classList.remove('open'); this._resetMsg(); });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.classList.remove('open'); this._resetMsg(); } });
    submit.addEventListener('click', () => this._submit());
  }

  _resetMsg() {
    const m = this.querySelector('#mfb-msg');
    m.className = 'mfb-msg'; m.textContent = '';
  }

  async _submit() {
    const msg = this.querySelector('#mfb-msg');
    const title = this.querySelector('#mfb-title').value.trim();
    const desc  = this.querySelector('#mfb-desc').value.trim();
    if (title.length < 5 || desc.length < 10) {
      msg.className = 'mfb-msg err';
      msg.textContent = 'Title (min 5 chars) and description (min 10 chars) are required.';
      return;
    }
    const body = {
      user_id: localStorage.getItem('murphy_user_id') || 'anonymous',
      title, description: desc,
      severity: this.querySelector('#mfb-sev').value,
      source: 'website_widget',
      page_url: window.location.href,
      component: this.querySelector('#mfb-comp').value || null,
      steps_to_reproduce: this.querySelector('#mfb-steps').value || null,
      expected_behavior: this.querySelector('#mfb-exp').value || null,
      actual_behavior: this.querySelector('#mfb-act').value || null,
      tags: [], metadata: {}
    };
    try {
      const r = await fetch(`${this._api}/feedback/submit`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
      });
      const d = await r.json();
      if (d.success) {
        msg.className = 'mfb-msg ok';
        msg.textContent = `Feedback submitted (${d.feedback_id}). A remediation plan has been generated.`;
        this.querySelector('#mfb-title').value = '';
        this.querySelector('#mfb-desc').value = '';
        this.querySelector('#mfb-steps').value = '';
        this.querySelector('#mfb-exp').value = '';
        this.querySelector('#mfb-act').value = '';
        this.querySelector('#mfb-comp').value = '';
      } else {
        msg.className = 'mfb-msg err';
        msg.textContent = d.message || 'Submission failed.';
      }
    } catch(e) {
      msg.className = 'mfb-msg err';
      msg.textContent = 'Network error: ' + e.message;
    }
  }
}
customElements.define('murphy-feedback-widget', MurphyFeedbackWidget);
