/* murphy-components.js — Murphy System Shared Web Components
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 */

/* ── MurphyHeader ─────────────────────────────────────────────── */
class MurphyHeader extends HTMLElement {
  connectedCallback() {
    const title   = this.getAttribute('title')    || 'MURPHY SYSTEM';
    const sub     = this.getAttribute('subtitle') || '';
    const apiUrl  = this.getAttribute('api-url')  || '/api';

    this.innerHTML = `
      <header class="murphy-header">
        <div>
          <div class="murphy-header-title">☠ ${title} ☠</div>
          ${sub ? `<div class="murphy-header-sub">${sub}</div>` : ''}
        </div>
        <div class="murphy-header-controls" id="mh-controls-${this._uid()}">
          <span class="status-pill status-idle" id="mh-api-${this._uid()}">● API</span>
          <span class="status-pill status-idle" id="mh-mfgc-${this._uid()}">● MFGC</span>
        </div>
      </header>`;

    this._pollStatus(apiUrl);
  }

  _uid() {
    if (!this.__uid) this.__uid = Math.random().toString(36).slice(2, 7);
    return this.__uid;
  }

  _pollStatus(apiUrl) {
    const update = async () => {
      try {
        const r = await fetch(`${apiUrl}/health`, { signal: AbortSignal.timeout(3000) });
        const d = await r.json();
        const apiEl  = this.querySelector(`[id^="mh-api-"]`);
        const mfgcEl = this.querySelector(`[id^="mh-mfgc-"]`);
        if (apiEl)  { apiEl.className  = 'status-pill status-running'; apiEl.textContent  = '● API LIVE'; }
        if (mfgcEl) {
          const ok = d.mfgc_enabled !== false;
          mfgcEl.className = ok ? 'status-pill status-running' : 'status-pill status-idle';
          mfgcEl.textContent = ok ? '● MFGC ON' : '○ MFGC OFF';
        }
      } catch {
        const apiEl = this.querySelector(`[id^="mh-api-"]`);
        if (apiEl) { apiEl.className = 'status-pill status-error'; apiEl.textContent = '✕ API DOWN'; }
      }
    };
    update();
    setInterval(update, 15000);
  }
}
customElements.define('murphy-header', MurphyHeader);


/* ── MurphySidebar ───────────────────────────────────────────── */
class MurphySidebar extends HTMLElement {
  connectedCallback() {
    const active = this.getAttribute('active') || '';

    const navItems = [
      { icon: '⬡', label: 'ORCHESTRATOR', href: '/terminal_orchestrator.html' },
      { icon: '✦', label: 'ORG CHART',    href: '/terminal_orgchart.html' },
      { icon: '⬢', label: 'INTEGRATIONS', href: '/terminal_integrations.html' },
      { icon: '◈', label: 'ARCHITECT',    href: '/terminal_architect.html' },
      { icon: '◎', label: 'WORKER',       href: '/terminal_worker.html' },
      { icon: '⊞', label: 'COSTS',        href: '/terminal_costs.html' },
      { icon: '⋮', label: 'WORKFLOWS',    href: '/strategic/gap_closure/lowcode/workflow_builder_ui.html' },
    ];

    const links = navItems.map(item => `
      <li>
        <a href="${item.href}" class="${active === item.label ? 'active' : ''}">
          <span class="nav-icon">${item.icon}</span>
          <span class="nav-label">${item.label}</span>
        </a>
      </li>`).join('');

    this.innerHTML = `
      <nav class="murphy-sidebar" id="ms-sidebar">
        <div style="padding:10px 8px; border-bottom:1px solid var(--border-dim); display:flex; align-items:center; justify-content:space-between;">
          <span style="font-size:9px;letter-spacing:2px;color:var(--text-dim);" class="nav-label">NAVIGATION</span>
          <button class="btn" style="padding:2px 6px;font-size:12px;" id="ms-toggle" title="Toggle sidebar">⇔</button>
        </div>
        <ul class="sidebar-nav">${links}</ul>
      </nav>`;

    this.querySelector('#ms-toggle').addEventListener('click', () => {
      const s = this.querySelector('#ms-sidebar');
      s.classList.toggle('collapsed');
    });
  }
}
customElements.define('murphy-sidebar', MurphySidebar);


/* ── MurphyStatusBar ─────────────────────────────────────────── */
class MurphyStatusBar extends HTMLElement {
  connectedCallback() {
    const apiUrl = this.getAttribute('api-url') || '/api';

    this.innerHTML = `
      <div class="murphy-status-bar">
        <span class="status-item"><span class="dot dot-green"></span><span id="msb-running">0</span> RUNNING</span>
        <span class="status-item"><span class="dot dot-yellow"></span><span id="msb-waiting">0</span> HITL WAITING</span>
        <span class="status-item"><span class="dot dot-red"></span><span id="msb-stuck">0</span> STUCK</span>
        <span style="flex:1"></span>
        <span id="msb-clock" style="color:var(--text-secondary)"></span>
      </div>`;

    this._tick();
    setInterval(() => this._tick(), 1000);
    this._pollCounts(apiUrl);
    setInterval(() => this._pollCounts(apiUrl), 10000);
  }

  _tick() {
    const el = this.querySelector('#msb-clock');
    if (el) el.textContent = new Date().toISOString().replace('T', ' ').split('.')[0] + ' UTC';
  }

  async _pollCounts(apiUrl) {
    try {
      const r = await fetch(`${apiUrl}/orchestrator/overview`, { signal: AbortSignal.timeout(3000) });
      const d = await r.json();
      const s = d.summary || {};
      const running = this.querySelector('#msb-running');
      const waiting = this.querySelector('#msb-waiting');
      const stuck   = this.querySelector('#msb-stuck');
      if (running) running.textContent = s.active_workflows ?? 0;
      if (waiting) waiting.textContent = s.hitl_pending    ?? 0;
      if (stuck)   stuck.textContent   = s.stuck_workflows ?? 0;
    } catch { /* ignore */ }
  }
}
customElements.define('murphy-status-bar', MurphyStatusBar);


/* ── MurphyCommandPalette ────────────────────────────────────── */
class MurphyCommandPalette extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="cmd-palette-overlay" id="mcp-overlay">
        <div class="cmd-palette">
          <input type="text" id="mcp-input" placeholder="⌘ Type a command or search…" autocomplete="off">
          <div id="mcp-results" style="max-height:300px;overflow-y:auto;"></div>
          <div style="padding:6px 14px;font-size:9px;color:var(--text-dim);border-top:1px solid var(--border-dim);">
            ↑↓ navigate · ↵ open · Esc close
          </div>
        </div>
      </div>`;

    this._commands = [
      { icon:'⬡', label:'Orchestrator Dashboard',  href:'/terminal_orchestrator.html',   shortcut:'' },
      { icon:'✦', label:'Org Chart',               href:'/terminal_orgchart.html',        shortcut:'' },
      { icon:'⬢', label:'Integration Wiring',      href:'/terminal_integrations.html',   shortcut:'' },
      { icon:'◈', label:'Architect Terminal',       href:'/terminal_architect.html',       shortcut:'' },
      { icon:'◎', label:'Worker Terminal',          href:'/terminal_worker.html',          shortcut:'' },
      { icon:'⊞', label:'Cost Dashboard',           href:'/terminal_costs.html',           shortcut:'' },
      { icon:'⋮', label:'Workflow Builder',         href:'/strategic/gap_closure/lowcode/workflow_builder_ui.html', shortcut:'' },
    ];

    this._selected = 0;
    this._filtered = [...this._commands];

    const input   = this.querySelector('#mcp-input');
    const overlay = this.querySelector('#mcp-overlay');

    input.addEventListener('input', () => this._filter(input.value));
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); this._move(1); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); this._move(-1); }
      if (e.key === 'Enter')     { this._open(); }
      if (e.key === 'Escape')    { this._hide(); }
    });

    overlay.addEventListener('click', e => { if (e.target === overlay) this._hide(); });

    document.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); this._show(); }
    });

    this._render();
  }

  _filter(q) {
    const lq = q.toLowerCase();
    this._filtered = this._commands.filter(c => c.label.toLowerCase().includes(lq));
    this._selected = 0;
    this._render();
  }

  _render() {
    const el = this.querySelector('#mcp-results');
    if (!el) return;
    el.innerHTML = this._filtered.map((c, i) => `
      <div class="cmd-result${i === this._selected ? ' selected' : ''}" data-idx="${i}">
        <span class="cmd-icon">${c.icon}</span>
        <span class="cmd-label">${c.label}</span>
        ${c.shortcut ? `<span class="cmd-shortcut">${c.shortcut}</span>` : ''}
      </div>`).join('');

    el.querySelectorAll('.cmd-result').forEach(row => {
      row.addEventListener('click', () => {
        this._selected = parseInt(row.dataset.idx);
        this._open();
      });
    });
  }

  _move(dir) {
    this._selected = Math.max(0, Math.min(this._filtered.length - 1, this._selected + dir));
    this._render();
  }

  _open() {
    const c = this._filtered[this._selected];
    if (c) window.location.href = c.href;
    this._hide();
  }

  _show() {
    const overlay = this.querySelector('#mcp-overlay');
    const input   = this.querySelector('#mcp-input');
    if (overlay) overlay.classList.add('active');
    if (input)   { input.value = ''; this._filter(''); input.focus(); }
  }

  _hide() {
    const overlay = this.querySelector('#mcp-overlay');
    if (overlay) overlay.classList.remove('active');
  }
}
customElements.define('murphy-command-palette', MurphyCommandPalette);


/* ── MurphyTooltip ───────────────────────────────────────────── */
class MurphyTooltip extends HTMLElement {
  connectedCallback() {
    const text = this.getAttribute('text') || '';
    const slot = this.innerHTML;
    this.style.position = 'relative';
    this.style.display  = 'inline-block';
    this.style.cursor   = 'default';
    this.innerHTML = `
      ${slot}
      <div style="
        display:none;
        position:absolute;
        bottom:calc(100% + 6px);
        left:0;
        min-width:180px;
        max-width:280px;
        background:var(--bg-secondary);
        border:1px solid var(--border-dim);
        border-radius:2px;
        padding:7px 10px;
        font-size:10px;
        line-height:1.5;
        color:var(--text-secondary);
        z-index:9999;
        white-space:normal;
        pointer-events:none;
      " class="mt-tip">${text}</div>`;

    this.addEventListener('mouseenter', () => {
      const tip = this.querySelector('.mt-tip');
      if (tip) tip.style.display = 'block';
    });
    this.addEventListener('mouseleave', () => {
      const tip = this.querySelector('.mt-tip');
      if (tip) tip.style.display = 'none';
    });
  }
}
customElements.define('murphy-tooltip', MurphyTooltip);
