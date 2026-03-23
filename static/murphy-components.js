/* murphy-components.js — Murphy System Shared Web Components & Modules
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 *
 * Licensed under the Business Source License 1.1 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://mariadb.com/bsl11/
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 1 — WEB COMPONENTS
 * ═══════════════════════════════════════════════════════════════════ */


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
          <a href="/ui/workspace" class="murphy-notif-bell" id="mh-notif-${this._uid()}" title="Notifications" style="position:relative;margin-left:8px;text-decoration:none;color:var(--text-secondary,#aaa);font-size:16px;cursor:pointer;">
            🔔<span class="murphy-notif-badge" id="mh-notif-count-${this._uid()}" style="display:none;position:absolute;top:-6px;right:-8px;min-width:16px;height:16px;line-height:16px;text-align:center;border-radius:8px;background:#ff4444;color:#fff;font-size:9px;font-weight:700;padding:0 4px;">0</span>
          </a>
        </div>
      </header>`;

    this._pollStatus(apiUrl);
    this._pollNotifications(apiUrl);
  }

  _uid() {
    if (!this.__uid) this.__uid = Math.random().toString(36).slice(2, 7);
    return this.__uid;
  }

  _pollNotifications(apiUrl) {
    const update = async () => {
      try {
        const userId = localStorage.getItem('murphy_user_id') || 'default';
        const r = await fetch(`${apiUrl}/collaboration/notifications/${userId}/count`, { signal: AbortSignal.timeout(3000) });
        if (!r.ok) return;
        const d = await r.json();
        const count = d.unread ?? d.count ?? 0;
        const badge = this.querySelector(`[id^="mh-notif-count-"]`);
        if (badge) {
          if (count > 0) {
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.style.display = 'inline-block';
          } else {
            badge.style.display = 'none';
          }
        }
      } catch { /* ignore — notifications are optional */ }
    };
    update();
    setInterval(update, 30000);
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
      { icon: '⬡', label: 'ORCHESTRATOR', href: '/ui/terminal-orchestrator' },
      { icon: '✦', label: 'ORG CHART',    href: '/ui/terminal-orgchart' },
      { icon: '⬢', label: 'INTEGRATIONS', href: '/ui/terminal-integrations' },
      { icon: '◈', label: 'ARCHITECT',    href: '/ui/terminal-architect' },
      { icon: '◎', label: 'WORKER',       href: '/ui/terminal-worker' },
      { icon: '⊞', label: 'COSTS',        href: '/ui/terminal-costs' },
      { icon: '⋮', label: 'WORKFLOWS',    href: '/ui/workflow-canvas' },
      { icon: '🏭', label: 'PRODUCTION',   href: '/ui/production-wizard' },
      { icon: '📈', label: 'TRADING',      href: '/ui/trading' },
      { icon: '🛡', label: 'RISK',         href: '/ui/risk-dashboard' },
      { icon: '📝', label: 'PAPER TRADE',  href: '/ui/paper-trading' },
      { icon: '🎯', label: 'GRANTS',       href: '/ui/grant-wizard' },
      { icon: '☑', label: 'COMPLIANCE',   href: '/ui/compliance' },
      { icon: '📅', label: 'CALENDAR',     href: '/ui/calendar' },
      { icon: '🧠', label: 'MEETINGS',     href: '/ui/meeting-intelligence' },
      { icon: '⚡', label: 'AMBIENT',      href: '/ui/ambient' },
      { icon: '💬', label: 'WORKSPACE',    href: '/ui/workspace' },
      { icon: '🏘', label: 'COMMUNITY',    href: '/ui/community' },
      { icon: '📋', label: 'MANAGEMENT',   href: '/ui/management' },
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
      { icon:'⬡', label:'Orchestrator Dashboard',  href:'/ui/terminal-orchestrator',   shortcut:'' },
      { icon:'✦', label:'Org Chart',               href:'/ui/terminal-orgchart',        shortcut:'' },
      { icon:'⬢', label:'Integration Wiring',      href:'/ui/terminal-integrations',   shortcut:'' },
      { icon:'◈', label:'Architect Terminal',       href:'/ui/terminal-architect',       shortcut:'' },
      { icon:'◎', label:'Worker Terminal',          href:'/ui/terminal-worker',          shortcut:'' },
      { icon:'⊞', label:'Cost Dashboard',           href:'/ui/terminal-costs',           shortcut:'' },
      { icon:'⋮', label:'Workflow Builder',         href:'/ui/workflow-canvas', shortcut:'' },
      { icon:'📈', label:'Trading Dashboard',       href:'/ui/trading',                  shortcut:'' },
      { icon:'🛡', label:'Risk Dashboard',           href:'/ui/risk-dashboard',           shortcut:'' },
      { icon:'📝', label:'Paper Trading',            href:'/ui/paper-trading',            shortcut:'' },
      { icon:'🎯', label:'Grant Wizard',             href:'/ui/grant-wizard',             shortcut:'' },
      { icon:'☑', label:'Compliance Settings',      href:'/ui/compliance',               shortcut:'' },
      { icon:'📅', label:'Calendar',                 href:'/ui/calendar',                 shortcut:'' },
      { icon:'🧠', label:'Meeting Intelligence',     href:'/ui/meeting-intelligence',     shortcut:'' },
      { icon:'⚡', label:'Ambient Intelligence',     href:'/ui/ambient',                  shortcut:'' },
      { icon:'💬', label:'Workspace',                href:'/ui/workspace',                shortcut:'' },
      { icon:'🏘', label:'Community Forum',          href:'/ui/community',                shortcut:'' },
      { icon:'📋', label:'Management',               href:'/ui/management',               shortcut:'' },
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


/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 2 — UTILITY MODULES
 * ═══════════════════════════════════════════════════════════════════ */


/* ── MurphyAPI ────────────────────────────────────────────────── */

/**
 * HTTP client for the Murphy API with retry logic and circuit breaker.
 */
class MurphyAPI {
  /** @param {string} [baseUrl='/api'] Root URL for all API requests. */
  constructor(baseUrl = '/api') {
    this._baseUrl = baseUrl.replace(/\/+$/, '');
    this._maxRetries = 3;
    this._timeout = 10000;
    this._cbFailures = 0;
    this._cbThreshold = 5;
    this._cbCooldown = 30000;
    this._cbOpenedAt = 0;
    this._cbState = 'closed'; // closed | open | half-open
  }

  /**
   * Perform a GET request.
   * @param {string} path   API path (e.g. '/health').
   * @param {object} [opts] Additional fetch options.
   * @returns {Promise<{ok:boolean, data:*, error:string|null, status:number}>}
   */
  async get(path, opts = {}) {
    return this._request('GET', path, undefined, opts);
  }

  /**
   * Perform a POST request.
   * @param {string} path   API path.
   * @param {*}      body   JSON-serialisable body.
   * @param {object} [opts] Additional fetch options.
   * @returns {Promise<{ok:boolean, data:*, error:string|null, status:number}>}
   */
  async post(path, body, opts = {}) {
    return this._request('POST', path, body, opts);
  }

  /**
   * Perform a PUT request.
   * @param {string} path   API path.
   * @param {*}      body   JSON-serialisable body.
   * @param {object} [opts] Additional fetch options.
   * @returns {Promise<{ok:boolean, data:*, error:string|null, status:number}>}
   */
  async put(path, body, opts = {}) {
    return this._request('PUT', path, body, opts);
  }

  /**
   * Perform a DELETE request.
   * @param {string} path   API path.
   * @param {object} [opts] Additional fetch options.
   * @returns {Promise<{ok:boolean, data:*, error:string|null, status:number}>}
   */
  async delete(path, opts = {}) {
    return this._request('DELETE', path, undefined, opts);
  }

  /* ── internals ────────────────────────────────────────────── */

  _buildHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('murphy_session_token');
      if (token) {
        headers['Authorization'] = 'Bearer ' + token;
      } else {
        const key = localStorage.getItem('murphy_api_key');
        if (key) headers['X-API-Key'] = key;
      }
      const userId = localStorage.getItem('murphy_user_id');
      if (userId) headers['X-User-ID'] = userId.replace(/[\r\n]/g, '');
    } catch { /* localStorage unavailable */ }
    return headers;
  }

  _checkCircuit() {
    if (this._cbState === 'closed') return true;
    if (this._cbState === 'open') {
      if (Date.now() - this._cbOpenedAt >= this._cbCooldown) {
        this._cbState = 'half-open';
        return true;
      }
      return false;
    }
    return true; // half-open allows one request
  }

  _recordSuccess() {
    this._cbFailures = 0;
    this._cbState = 'closed';
  }

  _recordFailure() {
    this._cbFailures += 1;
    if (this._cbFailures >= this._cbThreshold) {
      this._cbState = 'open';
      this._cbOpenedAt = Date.now();
    }
  }

  async _request(method, path, body, opts) {
    if (!this._checkCircuit()) {
      return { ok: false, data: null, error: 'Circuit breaker is open — too many consecutive failures', status: 0 };
    }

    const url = `${this._baseUrl}${path}`;
    const fetchOpts = {
      method,
      headers: { ...this._buildHeaders(), ...(opts.headers || {}) },
      ...opts,
    };
    if (body !== undefined) fetchOpts.body = JSON.stringify(body);

    let lastError = null;
    for (let attempt = 0; attempt <= this._maxRetries; attempt++) {
      let timeoutId;
      try {
        const controller = new AbortController();
        timeoutId = setTimeout(() => controller.abort(), opts.timeout || this._timeout);
        fetchOpts.signal = controller.signal;

        const response = await fetch(url, fetchOpts);
        clearTimeout(timeoutId);

        if (response.status >= 500) {
          lastError = `Server error ${response.status}`;
          this._recordFailure();
          if (attempt < this._maxRetries) {
            await this._backoff(attempt);
            continue;
          }
          return { ok: false, data: null, error: lastError, status: response.status };
        }

        this._recordSuccess();

        let data = null;
        const ct = response.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          data = await response.json();
        } else {
          data = await response.text();
        }

        const parsed = this._parseResponse(data, response.status);
        if (!response.ok) {
          const errMsg = parsed?.error?.message || `HTTP ${response.status}`;
          return { ok: false, data: parsed, error: errMsg, status: response.status };
        }
        return { ok: true, data: parsed, error: null, status: response.status };

      } catch (err) {
        clearTimeout(timeoutId);
        lastError = err.name === 'AbortError' ? 'Request timed out' : err.message;
        this._recordFailure();
        if (attempt < this._maxRetries) {
          await this._backoff(attempt);
          continue;
        }
      }
    }
    return { ok: false, data: null, error: lastError, status: 0 };
  }

  _backoff(attempt) {
    const ms = Math.min(1000 * Math.pow(2, attempt), 8000);
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Normalise various backend error formats into the standard envelope.
   * Handles: Flask {status/message}, FastAPI {detail}, custom {error/code},
   * and the standard {success, data/error} envelope.
   * @param {*} data  Parsed response body.
   * @param {number} status HTTP status code.
   * @returns {{success:boolean, data?:*, error?:{code:string,message:string}}}
   */
  _parseResponse(data, status) {
    if (data === null || data === undefined) return { success: status < 400, data };
    if (typeof data !== 'object') return { success: status < 400, data };
    // Already standard envelope
    if ('success' in data) return data;
    // Flask legacy: { status: 'error', message: '...' }
    if ('status' in data && data.status === 'error') {
      return { success: false, error: { code: 'LEGACY_ERROR', message: data.message || 'Unknown error' } };
    }
    // FastAPI validation: { detail: '...' }
    if ('detail' in data) {
      return { success: false, error: { code: `HTTP_${status}`, message: String(data.detail) } };
    }
    // Custom: { error: '...', code: '...' }
    if ('error' in data && typeof data.error === 'string') {
      return { success: false, error: { code: data.code || 'ERROR', message: data.error } };
    }
    return { success: status < 400, data };
  }
}


/* ── MurphyToast ──────────────────────────────────────────────── */

/**
 * Singleton toast notification manager.
 */
class MurphyToast {
  constructor() {
    if (MurphyToast._instance) return MurphyToast._instance;
    MurphyToast._instance = this;
    this._container = null;
    this._iconMap = {
      success: 'check',
      warning: 'alert',
      danger:  'x',
      info:    'info',
    };
  }

  /**
   * Display a toast notification.
   * @param {string} message          Text to show.
   * @param {'success'|'warning'|'danger'|'info'} [type='info'] Visual style.
   * @param {number} [duration=4000]  Auto-dismiss time in ms.
   */
  show(message, type = 'info', duration = 4000) {
    this._ensureContainer();
    const toast = document.createElement('div');
    toast.className = `murphy-toast murphy-toast-${type}`;
    toast.style.cssText = 'display:flex;align-items:flex-start;gap:8px;padding:10px 14px;margin-bottom:8px;'
      + 'border-radius:4px;font-size:12px;line-height:1.5;color:#fff;min-width:240px;max-width:380px;'
      + 'box-shadow:0 4px 12px rgba(0,0,0,.4);animation:murphyToastSlideIn .25s ease-out;'
      + 'background:' + this._bgColor(type) + ';';

    const iconName = this._iconMap[type] || 'info';
    toast.innerHTML = `
      <svg width="16" height="16" style="flex-shrink:0;margin-top:1px;"><use href="static/murphy-icons.svg#${iconName}"/></svg>
      <span style="flex:1;">${this._escapeHtml(message)}</span>
      <button style="background:none;border:none;color:inherit;cursor:pointer;font-size:14px;line-height:1;padding:0;" aria-label="Close">&times;</button>`;

    toast.querySelector('button').addEventListener('click', () => this._dismiss(toast));
    this._container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => this._dismiss(toast), duration);
    }
  }

  _bgColor(type) {
    const map = { success: '#1a7a3a', warning: '#a06a00', danger: '#a02020', info: '#1a5a8a' };
    return map[type] || map.info;
  }

  _dismiss(el) {
    if (!el || !el.parentNode) return;
    el.style.animation = 'murphyToastSlideOut .2s ease-in forwards';
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }

  _ensureContainer() {
    if (this._container && document.body.contains(this._container)) return;
    this._container = document.createElement('div');
    this._container.className = 'murphy-toast-container';
    this._container.style.cssText = 'position:fixed;top:16px;right:16px;z-index:700;display:flex;flex-direction:column;pointer-events:auto;';
    document.body.appendChild(this._container);

    if (!document.getElementById('murphy-toast-keyframes')) {
      const style = document.createElement('style');
      style.id = 'murphy-toast-keyframes';
      style.textContent = `
        @keyframes murphyToastSlideIn { from { transform:translateX(110%); opacity:0; } to { transform:translateX(0); opacity:1; } }
        @keyframes murphyToastSlideOut { from { transform:translateX(0); opacity:1; } to { transform:translateX(110%); opacity:0; } }`;
      document.head.appendChild(style);
    }
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}


/* ── MurphyModal ──────────────────────────────────────────────── */

/**
 * Programmatic modal dialog with focus trap.
 */
class MurphyModal {
  /**
   * Show a modal dialog.
   * @param {object}   config
   * @param {string}   config.title          Modal heading text.
   * @param {string}   config.body           HTML string for the body.
   * @param {Array<{label:string, variant:string, onClick:function}>} [config.actions] Footer buttons.
   * @param {function} [config.onClose]      Called when modal is dismissed.
   * @returns {function} close — call to programmatically close the modal.
   */
  show({ title, body, actions = [], onClose }) {
    const backdrop = document.createElement('div');
    backdrop.className = 'murphy-modal-backdrop';
    backdrop.style.cssText = 'position:fixed;inset:0;z-index:800;background:rgba(0,0,0,.55);'
      + 'display:flex;align-items:center;justify-content:center;animation:murphyModalFadeIn .2s ease-out;';

    const modal = document.createElement('div');
    modal.className = 'murphy-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', title);
    modal.style.cssText = 'background:var(--bg-secondary, #1a1a2e);border:1px solid var(--border-dim, #333);'
      + 'border-radius:6px;min-width:360px;max-width:560px;max-height:80vh;display:flex;flex-direction:column;'
      + 'box-shadow:0 8px 32px rgba(0,0,0,.5);animation:murphyModalFadeIn .2s ease-out;';

    const headerHtml = `<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border-dim,#333);">
      <span style="font-weight:600;font-size:14px;color:var(--text-primary,#eee);">${this._escapeHtml(title)}</span>
      <button class="murphy-modal-close" style="background:none;border:none;color:var(--text-secondary,#aaa);cursor:pointer;font-size:18px;line-height:1;" aria-label="Close">&times;</button>
    </div>`;

    const bodyHtml = `<div style="padding:18px;overflow-y:auto;flex:1;font-size:13px;line-height:1.6;color:var(--text-secondary,#ccc);">${body}</div>`;

    let footerHtml = '';
    if (actions.length) {
      const btns = actions.map(a => {
        const variant = a.variant || 'default';
        return `<button class="murphy-modal-btn murphy-modal-btn-${variant}" data-variant="${variant}">${this._escapeHtml(a.label)}</button>`;
      }).join('');
      footerHtml = `<div style="padding:12px 18px;border-top:1px solid var(--border-dim,#333);display:flex;gap:8px;justify-content:flex-end;">${btns}</div>`;
    }

    modal.innerHTML = headerHtml + bodyHtml + footerHtml;
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);

    this._injectKeyframes();

    const close = () => {
      backdrop.style.animation = 'murphyModalFadeOut .15s ease-in forwards';
      backdrop.addEventListener('animationend', () => {
        backdrop.remove();
        if (typeof onClose === 'function') onClose();
      }, { once: true });
    };

    modal.querySelector('.murphy-modal-close').addEventListener('click', close);
    backdrop.addEventListener('click', e => { if (e.target === backdrop) close(); });

    const escHandler = e => {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);

    actions.forEach((a, i) => {
      const btn = modal.querySelectorAll('.murphy-modal-btn')[i];
      if (btn && typeof a.onClick === 'function') {
        btn.addEventListener('click', () => a.onClick(close));
      }
    });

    this._trapFocus(modal);

    const firstFocusable = modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (firstFocusable) firstFocusable.focus();

    return close;
  }

  _trapFocus(el) {
    const handler = e => {
      if (e.key !== 'Tab') return;
      const focusable = el.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      const first = focusable[0];
      const last  = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    el.addEventListener('keydown', handler);
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  _injectKeyframes() {
    if (document.getElementById('murphy-modal-keyframes')) return;
    const style = document.createElement('style');
    style.id = 'murphy-modal-keyframes';
    style.textContent = `
      @keyframes murphyModalFadeIn { from { opacity:0; transform:scale(.95); } to { opacity:1; transform:scale(1); } }
      @keyframes murphyModalFadeOut { from { opacity:1; transform:scale(1); } to { opacity:0; transform:scale(.95); } }
      .murphy-modal-btn { padding:6px 16px;border-radius:3px;border:1px solid var(--border-dim,#444);background:var(--bg-tertiary,#222);color:var(--text-primary,#eee);cursor:pointer;font-size:12px; }
      .murphy-modal-btn-primary { background:var(--accent,#00b4d8);border-color:var(--accent,#00b4d8);color:#000; }
      .murphy-modal-btn-danger { background:#a02020;border-color:#a02020; }
      .murphy-modal-btn:hover { filter:brightness(1.15); }`;
    document.head.appendChild(style);
  }
}


/* ── MurphyHealth ─────────────────────────────────────────────── */

/**
 * Polls the system health endpoint and manages an offline banner.
 */
class MurphyHealth {
  /**
   * @param {MurphyAPI} api An initialised MurphyAPI instance.
   */
  constructor(api) {
    this._api = api;
    this._interval = null;
    this._callbacks = [];
    this._banner = null;
    this._lastOnline = true;
  }

  /**
   * Start periodic health polling.
   * @param {number} [interval=15000] Poll interval in ms.
   */
  start(interval = 15000) {
    this.stop();
    this._poll();
    this._interval = setInterval(() => this._poll(), interval);
  }

  /**
   * Stop health polling.
   */
  stop() {
    if (this._interval) {
      clearInterval(this._interval);
      this._interval = null;
    }
  }

  /**
   * Register a callback to receive health updates.
   * @param {function} callback Receives a health data object.
   */
  onUpdate(callback) {
    if (typeof callback === 'function') this._callbacks.push(callback);
  }

  async _poll() {
    const result = await this._api.get('/health');
    if (result.ok) {
      const data = typeof result.data === 'object' ? result.data : { status: 'online' };
      if (!data.status) data.status = 'online';
      this._emit(data);
      this._setOnline(true);
    } else {
      this._emit({ status: 'offline', error: result.error });
      this._setOnline(false);
    }
  }

  _emit(data) {
    for (const cb of this._callbacks) {
      try { cb(data); } catch { /* consumer error */ }
    }
  }

  _setOnline(online) {
    if (online === this._lastOnline) return;
    this._lastOnline = online;
    if (!online) {
      this._showBanner();
    } else {
      this._hideBanner();
    }
  }

  _showBanner() {
    if (this._banner && document.body.contains(this._banner)) return;
    this._banner = document.createElement('div');
    this._banner.className = 'murphy-offline-banner';
    this._banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:900;background:#a02020;color:#fff;'
      + 'text-align:center;padding:8px;font-size:12px;font-weight:600;letter-spacing:1px;';
    this._banner.textContent = '⚠ MURPHY SYSTEM OFFLINE — Reconnecting…';
    document.body.prepend(this._banner);
  }

  _hideBanner() {
    if (this._banner && this._banner.parentNode) {
      this._banner.remove();
      this._banner = null;
    }
  }
}


/* ── MurphyTable ──────────────────────────────────────────────── */

/**
 * Sortable, searchable, paginated data table.
 */
class MurphyTable {
  /**
   * @param {HTMLElement} container  DOM element to render into.
   * @param {object}      config
   * @param {Array<{key:string, label:string, sortable?:boolean, render?:function}>} config.columns
   * @param {Array<object>} [config.data=[]]      Initial data rows.
   * @param {boolean}       [config.searchable=true]
   * @param {boolean}       [config.sortable=true]
   * @param {number}        [config.pageSize=20]
   */
  constructor(container, { columns, data = [], searchable = true, sortable = true, pageSize = 20 }) {
    this._container = container;
    this._columns   = columns;
    this._allData   = data;
    this._searchable = searchable;
    this._sortable  = sortable;
    this._pageSize  = pageSize;
    this._searchTerm = '';
    this._sortKey   = null;
    this._sortDir   = 'asc';
    this._page      = 0;
  }

  /**
   * Replace table data and re-render.
   * @param {Array<object>} data New rows.
   */
  setData(data) {
    this._allData = data;
    this._page = 0;
    this.render();
  }

  /**
   * Render the table into the container element.
   */
  render() {
    const filtered = this._filtered();
    const sorted   = this._sorted(filtered);
    const totalPages = Math.max(1, Math.ceil(sorted.length / this._pageSize));
    if (this._page >= totalPages) this._page = totalPages - 1;
    const pageRows = sorted.slice(this._page * this._pageSize, (this._page + 1) * this._pageSize);

    let html = '';

    if (this._searchable) {
      html += `<div style="margin-bottom:8px;">
        <input type="text" class="murphy-table-search" placeholder="Search…" value="${this._escapeAttr(this._searchTerm)}"
          style="width:100%;padding:6px 10px;background:var(--bg-secondary,#1a1a2e);color:var(--text-primary,#eee);border:1px solid var(--border-dim,#333);border-radius:3px;font-size:12px;">
      </div>`;
    }

    html += '<table class="murphy-table" style="width:100%;border-collapse:collapse;font-size:12px;">';
    html += '<thead><tr>';
    for (const col of this._columns) {
      const canSort = this._sortable && col.sortable !== false;
      let arrow = '';
      if (canSort && this._sortKey === col.key) {
        arrow = this._sortDir === 'asc' ? ' ▲' : ' ▼';
      }
      const cursor = canSort ? 'cursor:pointer;' : '';
      html += `<th data-key="${col.key}" style="padding:8px 10px;text-align:left;border-bottom:1px solid var(--border-dim,#333);color:var(--text-dim,#888);font-size:10px;letter-spacing:1px;${cursor}user-select:none;">${this._escapeHtml(col.label)}${arrow}</th>`;
    }
    html += '</tr></thead><tbody>';

    for (const row of pageRows) {
      html += '<tr>';
      for (const col of this._columns) {
        const val = typeof col.render === 'function' ? col.render(row[col.key], row) : this._escapeHtml(String(row[col.key] ?? ''));
        html += `<td style="padding:6px 10px;border-bottom:1px solid var(--border-dim,#222);color:var(--text-secondary,#ccc);">${val}</td>`;
      }
      html += '</tr>';
    }

    if (pageRows.length === 0) {
      html += `<tr><td colspan="${this._columns.length}" style="padding:20px;text-align:center;color:var(--text-dim,#666);">No data</td></tr>`;
    }

    html += '</tbody></table>';

    if (totalPages > 1) {
      html += '<div style="display:flex;justify-content:center;gap:4px;margin-top:10px;">';
      for (let p = 0; p < totalPages; p++) {
        const active = p === this._page ? 'background:var(--accent,#00b4d8);color:#000;' : 'background:var(--bg-tertiary,#222);color:var(--text-secondary,#ccc);';
        html += `<button class="murphy-table-page" data-page="${p}" style="padding:4px 10px;border:1px solid var(--border-dim,#333);border-radius:2px;cursor:pointer;font-size:11px;${active}">${p + 1}</button>`;
      }
      html += '</div>';
    }

    this._container.innerHTML = html;
    this._bind();
  }

  _bind() {
    const searchInput = this._container.querySelector('.murphy-table-search');
    if (searchInput) {
      searchInput.addEventListener('input', e => {
        this._searchTerm = e.target.value;
        this._page = 0;
        this.render();
      });
    }
    this._container.querySelectorAll('th[data-key]').forEach(th => {
      const col = this._columns.find(c => c.key === th.dataset.key);
      if (!col || !this._sortable || col.sortable === false) return;
      th.addEventListener('click', () => {
        if (this._sortKey === col.key) {
          this._sortDir = this._sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          this._sortKey = col.key;
          this._sortDir = 'asc';
        }
        this.render();
      });
    });
    this._container.querySelectorAll('.murphy-table-page').forEach(btn => {
      btn.addEventListener('click', () => {
        this._page = parseInt(btn.dataset.page, 10);
        this.render();
      });
    });
  }

  _filtered() {
    if (!this._searchTerm) return this._allData;
    const term = this._searchTerm.toLowerCase();
    return this._allData.filter(row =>
      this._columns.some(col => String(row[col.key] ?? '').toLowerCase().includes(term))
    );
  }

  _sorted(data) {
    if (!this._sortKey) return data;
    const dir = this._sortDir === 'asc' ? 1 : -1;
    const key = this._sortKey;
    return [...data].sort((a, b) => {
      const va = a[key] ?? '';
      const vb = b[key] ?? '';
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  _escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}


/* ── MurphyChart ──────────────────────────────────────────────── */

/**
 * Lightweight Canvas-based chart renderer.
 */
class MurphyChart {
  /**
   * @param {HTMLCanvasElement} canvas  Target canvas element.
   * @param {'sparkline'|'gauge'|'bar'|'timeline'} type Chart type.
   * @param {object} [options={}]       Rendering options (color, lineWidth, max, labels, etc.).
   */
  constructor(canvas, type, options = {}) {
    this._canvas  = canvas;
    this._ctx     = canvas.getContext('2d');
    this._type    = type;
    this._opts    = Object.assign({
      color: '#00b4d8',
      bgColor: 'rgba(0,180,216,0.12)',
      lineWidth: 2,
      max: 100,
      labels: [],
      fontColor: '#aaa',
      fontSize: 10,
    }, options);
    this._data = [];
  }

  /**
   * Update chart data and redraw.
   * @param {Array<number|{value:number, label?:string, time?:number, color?:string}>} data
   */
  update(data) {
    this._data = data;
    this._draw();
  }

  _draw() {
    const ctx = this._ctx;
    const w = this._canvas.width;
    const h = this._canvas.height;
    ctx.clearRect(0, 0, w, h);

    switch (this._type) {
      case 'sparkline': this._drawSparkline(ctx, w, h); break;
      case 'gauge':     this._drawGauge(ctx, w, h);     break;
      case 'bar':       this._drawBar(ctx, w, h);       break;
      case 'timeline':  this._drawTimeline(ctx, w, h);  break;
    }
  }

  _drawSparkline(ctx, w, h) {
    const values = this._data.map(d => typeof d === 'number' ? d : d.value);
    if (values.length < 2) return;
    const max = this._opts.max || Math.max(...values, 1);
    const step = w / (values.length - 1);
    const pad = 4;
    const usableH = h - pad * 2;

    const points = values.map((v, i) => ({
      x: i * step,
      y: pad + usableH - (v / max) * usableH,
    }));

    // filled area
    ctx.beginPath();
    ctx.moveTo(points[0].x, h);
    for (const p of points) ctx.lineTo(p.x, p.y);
    ctx.lineTo(points[points.length - 1].x, h);
    ctx.closePath();
    ctx.fillStyle = this._opts.bgColor;
    ctx.fill();

    // line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.strokeStyle = this._opts.color;
    ctx.lineWidth = this._opts.lineWidth;
    ctx.stroke();
  }

  _drawGauge(ctx, w, h) {
    const value = typeof this._data[0] === 'number' ? this._data[0] : (this._data[0]?.value ?? 0);
    const max   = this._opts.max || 100;
    const pct   = Math.min(value / max, 1);
    const cx    = w / 2;
    const cy    = h * 0.6;
    const r     = Math.min(cx, cy) - 8;
    const startAngle = Math.PI;
    const endAngle   = 2 * Math.PI;

    // background arc
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, endAngle);
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 10;
    ctx.lineCap = 'round';
    ctx.stroke();

    // value arc
    const gaugeEnd = startAngle + pct * Math.PI;
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, gaugeEnd);
    ctx.strokeStyle = pct < 0.5 ? '#1a7a3a' : pct < 0.8 ? '#a06a00' : '#a02020';
    ctx.lineWidth = 10;
    ctx.lineCap = 'round';
    ctx.stroke();

    // label
    ctx.fillStyle = this._opts.fontColor;
    ctx.font = `bold ${Math.round(r * 0.4)}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`${Math.round(pct * 100)}%`, cx, cy - 4);
  }

  _drawBar(ctx, w, h) {
    const items = this._data.map(d => typeof d === 'number' ? { value: d, label: '' } : d);
    if (!items.length) return;
    const max = this._opts.max || Math.max(...items.map(i => i.value), 1);
    const barW = Math.max(8, (w / items.length) * 0.6);
    const gap  = (w - barW * items.length) / (items.length + 1);
    const labelH = 18;
    const usableH = h - labelH;

    items.forEach((item, i) => {
      const x = gap + i * (barW + gap);
      const barH = (item.value / max) * (usableH - 4);
      ctx.fillStyle = item.color || this._opts.color;
      ctx.fillRect(x, usableH - barH, barW, barH);

      if (item.label) {
        ctx.fillStyle = this._opts.fontColor;
        ctx.font = `${this._opts.fontSize}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(item.label, x + barW / 2, usableH + 2);
      }
    });
  }

  _drawTimeline(ctx, w, h) {
    const items = this._data.map(d => typeof d === 'object' ? d : { value: d });
    if (!items.length) return;

    const cy   = h / 2;
    const padX = 20;
    const lineW = w - padX * 2;

    // horizontal line
    ctx.beginPath();
    ctx.moveTo(padX, cy);
    ctx.lineTo(padX + lineW, cy);
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 2;
    ctx.stroke();

    const step = items.length > 1 ? lineW / (items.length - 1) : 0;
    items.forEach((item, i) => {
      const x = padX + i * step;

      // dot
      ctx.beginPath();
      ctx.arc(x, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = item.color || this._opts.color;
      ctx.fill();

      // label below
      if (item.label) {
        ctx.fillStyle = this._opts.fontColor;
        ctx.font = `${this._opts.fontSize}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(item.label, x, cy + 10);
      }
    });
  }
}


/* ── MurphyTheme ──────────────────────────────────────────────── */

/**
 * Singleton theme manager — dark only.
 * Murphy System uses a dark theme exclusively. There is no light mode.
 */
class MurphyTheme {
  constructor() {
    if (MurphyTheme._instance) return MurphyTheme._instance;
    MurphyTheme._instance = this;
    this._theme = 'dark';
  }

  /**
   * Initialise theme and apply dark mode to body.
   */
  init() {
    this._theme = 'dark';
    this._apply();
  }

  /**
   * Get the current theme name.
   * @returns {'dark'}
   */
  get() {
    return this._theme;
  }

  /**
   * Register a callback for theme changes (no-op: dark only).
   * @param {Function} _cb
   */
  onChange(_cb) {
    /* dark-only — nothing to notify */
  }

  /**
   * Toggle theme (no-op: dark only).
   */
  toggle() {
    /* dark-only — always dark */
  }

  _apply() {
    /* Murphy System is dark-only; no action needed on theme class application. */
  }
}


/* ── MurphyJargon ─────────────────────────────────────────────── */

/**
 * Glossary of Murphy-specific terms with hover tooltips.
 */
class MurphyJargon {
  constructor() {
    this._regex = null;
    this._terms = {
      'MFGC': 'Murphy Flow Graph Compiler — compiles high-level plans into executable DAGs.',
      'HITL': 'Human-In-The-Loop — a checkpoint where a human must approve or guide the next step.',
      'Gate': 'A decision point in a workflow that blocks progress until conditions are met.',
      'Swarm': 'A group of agents collaborating in parallel on a shared objective.',
      'Wingman': 'An AI assistant that pairs with a human operator to co-pilot tasks.',
      'Causality Engine': 'The subsystem that tracks cause-and-effect relationships across events.',
      'Confidence Engine': 'Scores how certain the system is about a recommended action.',
      'Orchestrator': 'The central controller that schedules and routes work across agents.',
      'Architect': 'The planning module that designs solutions before workers execute.',
      'Worker': 'An execution agent that carries out a discrete unit of work.',
      'DAG': 'Directed Acyclic Graph — the execution plan structure used by MFGC.',
      'Flow Graph': 'A visual representation of a workflow as connected nodes and edges.',
      'Gap Closure': 'The process of identifying and filling missing capabilities in the system.',
      'Librarian': 'An AI module that retrieves and summarises knowledge from the document store.',
      'Terminal': 'The browser-based command interface for interacting with Murphy subsystems.',
      'Insight': 'An observation surfaced by the Causality or Confidence engines.',
      'Integration': 'A connector between Murphy and an external service or API.',
      'Playbook': 'A reusable, parameterised sequence of actions for a common scenario.',
      'Sentinel': 'A background monitor that watches for anomalies and triggers alerts.',
      'Rollback': 'Reverting a workflow or action to a previous known-good state.',
      'Quorum': 'The minimum number of agent votes needed to approve a swarm decision.',
      'Persona': 'A role-based configuration that shapes how an agent behaves and communicates.',
      'Dispatch': 'The act of assigning a task from the orchestrator to a worker.',
      'Telemetry': 'System-wide metrics and traces used for observability and debugging.',
      'Canary': 'A test deployment sent to a small subset before full rollout.',
      'Circuit Breaker': 'A fault-tolerance pattern that stops calls to a failing service.',
      'Backpressure': 'A flow-control mechanism that slows input when downstream is overloaded.',
      'Capability Map': 'A registry of skills and tools available to each agent.',
      'Cost Guard': 'A policy that caps spending on API calls or compute per workflow.',
    };
  }

  /**
   * Scan DOM for elements with `data-jargon` attribute and attach hover tooltips.
   */
  init() {
    document.querySelectorAll('[data-jargon]').forEach(el => {
      const key = el.getAttribute('data-jargon');
      const def = this._terms[key];
      if (!def) return;
      this._attachTooltip(el, `${key}: ${def}`);
    });
  }

  /**
   * Automatically scan text content for known jargon terms and wrap matches in tooltip spans.
   */
  autoScan() {
    const regex = this._getRegex();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        if (node.parentElement && (node.parentElement.closest('.murphy-jargon-tip') || node.parentElement.tagName === 'SCRIPT' || node.parentElement.tagName === 'STYLE')) {
          return NodeFilter.FILTER_REJECT;
        }
        regex.lastIndex = 0;
        return regex.test(node.textContent) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });

    const nodes = [];
    let current;
    while ((current = walker.nextNode())) nodes.push(current);

    for (const textNode of nodes) {
      const frag = document.createDocumentFragment();
      let lastIdx = 0;
      let match;
      const text = textNode.textContent;
      regex.lastIndex = 0;
      while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIdx) {
          frag.appendChild(document.createTextNode(text.slice(lastIdx, match.index)));
        }
        const span = document.createElement('span');
        span.className = 'murphy-jargon-tip';
        span.textContent = match[0];
        span.style.cssText = 'border-bottom:1px dotted var(--text-dim,#666);cursor:help;position:relative;';
        this._attachTooltip(span, `${match[0]}: ${this._terms[match[0]]}`);
        frag.appendChild(span);
        lastIdx = regex.lastIndex;
      }
      if (lastIdx < text.length) {
        frag.appendChild(document.createTextNode(text.slice(lastIdx)));
      }
      textNode.parentNode.replaceChild(frag, textNode);
    }
  }

  _getRegex() {
    if (!this._regex) {
      const termKeys = Object.keys(this._terms).sort((a, b) => b.length - a.length);
      this._regex = new RegExp(`\\b(${termKeys.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`, 'g');
    }
    return this._regex;
  }

  _attachTooltip(el, text) {
    el.style.position = el.style.position || 'relative';
    const tip = document.createElement('div');
    tip.className = 'murphy-jargon-tooltip';
    tip.textContent = text;
    tip.style.cssText = 'display:none;position:absolute;bottom:calc(100% + 6px);left:0;min-width:200px;max-width:320px;'
      + 'background:var(--bg-secondary,#1a1a2e);border:1px solid var(--border-dim,#333);border-radius:3px;'
      + 'padding:8px 10px;font-size:11px;line-height:1.5;color:var(--text-secondary,#ccc);z-index:950;'
      + 'white-space:normal;pointer-events:none;box-shadow:0 4px 12px rgba(0,0,0,.4);';
    el.appendChild(tip);
    el.addEventListener('mouseenter', () => { tip.style.display = 'block'; });
    el.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  }
}


/* ── MurphyKeyboard ───────────────────────────────────────────── */

/**
 * Global keyboard shortcut manager.
 */
class MurphyKeyboard {
  constructor() {
    this._bindings = [];
    this._listening = false;
  }

  /**
   * Register a keyboard shortcut.
   * @param {string}   shortcut    e.g. 'ctrl+k', 'ctrl+/', 'escape'.
   * @param {function} callback    Invoked when shortcut fires.
   * @param {string}   description Human-readable description.
   */
  register(shortcut, callback, description) {
    this._bindings.push({
      shortcut: shortcut.toLowerCase(),
      callback,
      description: description || shortcut,
      parsed: this._parse(shortcut),
    });
  }

  /**
   * Attach the global keydown listener. Call once after registering shortcuts.
   */
  init() {
    if (this._listening) return;
    this._listening = true;
    document.addEventListener('keydown', e => this._handle(e));
  }

  /**
   * Display a modal listing all registered shortcuts.
   */
  showHelp() {
    const rows = this._bindings.map(b =>
      `<tr>
        <td style="padding:4px 12px 4px 0;"><kbd style="background:var(--bg-tertiary,#222);padding:2px 8px;border-radius:3px;font-size:11px;border:1px solid var(--border-dim,#444);">${this._escapeHtml(b.shortcut)}</kbd></td>
        <td style="padding:4px 0;font-size:12px;color:var(--text-secondary,#ccc);">${this._escapeHtml(b.description)}</td>
      </tr>`
    ).join('');
    const body = `<table style="width:100%;">${rows}</table>`;
    const modal = new MurphyModal();
    modal.show({ title: 'Keyboard Shortcuts', body, actions: [{ label: 'Close', variant: 'default', onClick: (close) => close() }] });
  }

  _parse(shortcut) {
    const parts = shortcut.toLowerCase().split('+').map(s => s.trim());
    return {
      ctrl:  parts.includes('ctrl') || parts.includes('control'),
      meta:  parts.includes('meta') || parts.includes('cmd'),
      shift: parts.includes('shift'),
      alt:   parts.includes('alt'),
      key:   parts.filter(p => !['ctrl', 'control', 'meta', 'cmd', 'shift', 'alt'].includes(p))[0] || '',
    };
  }

  _handle(e) {
    for (const binding of this._bindings) {
      const p = binding.parsed;
      const ctrlMatch = p.ctrl ? (e.ctrlKey || e.metaKey) : (!e.ctrlKey && !e.metaKey);
      const shiftMatch = p.shift ? e.shiftKey : !e.shiftKey;
      const altMatch = p.alt ? e.altKey : !e.altKey;
      const keyMatch = e.key.toLowerCase() === p.key || e.code.toLowerCase() === p.key;

      if (ctrlMatch && shiftMatch && altMatch && keyMatch) {
        e.preventDefault();
        binding.callback(e);
        return;
      }
    }
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}


/* ── MurphyTerminalPanel ──────────────────────────────────────── */

/**
 * In-browser terminal emulator panel with command history.
 */
class MurphyTerminalPanel {
  /**
   * @param {HTMLElement} container    DOM element to render into.
   * @param {object}      config
   * @param {string}      config.apiEndpoint  URL to POST commands to.
   * @param {string}      [config.prompt='murphy>'] Prompt prefix.
   * @param {function}    [config.onCommand]  Optional hook called with each command string.
   */
  constructor(container, { apiEndpoint, prompt = 'murphy>', onCommand }) {
    this._container   = container;
    this._apiEndpoint = apiEndpoint;
    this._prompt      = prompt;
    this._onCommand   = onCommand;
    this._history     = [];
    this._historyIdx  = -1;
    this._render();
  }

  /**
   * Execute a command by posting to the API endpoint and displaying the response.
   * @param {string} command Command string.
   */
  async execute(command) {
    const trimmed = command.trim();
    if (!trimmed) return;
    this._history.push(trimmed);
    this._historyIdx = this._history.length;
    this.appendOutput(`${this._prompt} ${trimmed}`, 'term-cmd');
    if (typeof this._onCommand === 'function') this._onCommand(trimmed);

    try {
      const res = await fetch(this._apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: trimmed }),
        signal: AbortSignal.timeout(15000),
      });
      const data = await res.json();
      if (res.ok) {
        this.appendOutput(data.output ?? JSON.stringify(data, null, 2), 'term-success');
      } else {
        this.appendOutput(data.error ?? `Error ${res.status}`, 'term-error');
      }
    } catch (err) {
      this.appendOutput(`Network error: ${err.message}`, 'term-error');
    }
  }

  /**
   * Append a line of text to the terminal output area.
   * @param {string} text      Content to display.
   * @param {string} [className=''] Optional CSS class (term-success, term-error, term-cmd).
   */
  appendOutput(text, className = '') {
    const output = this._container.querySelector('.murphy-terminal-output');
    if (!output) return;
    const line = document.createElement('div');
    line.className = `murphy-terminal-line ${className}`;
    line.style.cssText = 'padding:2px 0;white-space:pre-wrap;word-break:break-word;';
    if (className === 'term-error') line.style.color = '#e04040';
    else if (className === 'term-success') line.style.color = '#40c060';
    else if (className === 'term-cmd') line.style.color = 'var(--accent,#00b4d8)';
    line.textContent = text;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
  }

  /**
   * Clear all terminal output.
   */
  clear() {
    const output = this._container.querySelector('.murphy-terminal-output');
    if (output) output.innerHTML = '';
  }

  _render() {
    this._container.innerHTML = `
      <div class="murphy-terminal-panel" style="display:flex;flex-direction:column;height:100%;background:var(--bg-primary,#0d0d1a);border:1px solid var(--border-dim,#333);border-radius:4px;overflow:hidden;font-family:monospace;">
        <div style="display:flex;align-items:center;gap:6px;padding:8px 12px;background:var(--bg-secondary,#1a1a2e);border-bottom:1px solid var(--border-dim,#333);">
          <span style="width:10px;height:10px;border-radius:50%;background:#e04040;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#e0a020;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#40c060;"></span>
          <span style="flex:1;text-align:center;font-size:10px;color:var(--text-dim,#666);">MURPHY TERMINAL</span>
        </div>
        <div class="murphy-terminal-output" style="flex:1;overflow-y:auto;padding:10px 12px;font-size:12px;line-height:1.6;color:var(--text-secondary,#ccc);"></div>
        <div style="display:flex;align-items:center;padding:6px 12px;border-top:1px solid var(--border-dim,#333);background:var(--bg-secondary,#1a1a2e);">
          <span style="color:var(--accent,#00b4d8);font-size:12px;margin-right:6px;">${this._escapeHtml(this._prompt)}</span>
          <input type="text" class="murphy-terminal-input" style="flex:1;background:transparent;border:none;outline:none;color:var(--text-primary,#eee);font-family:monospace;font-size:12px;" autocomplete="off" spellcheck="false">
        </div>
      </div>`;

    const input = this._container.querySelector('.murphy-terminal-input');
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        this.execute(input.value);
        input.value = '';
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (this._historyIdx > 0) {
          this._historyIdx -= 1;
          input.value = this._history[this._historyIdx] || '';
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (this._historyIdx < this._history.length - 1) {
          this._historyIdx += 1;
          input.value = this._history[this._historyIdx] || '';
        } else {
          this._historyIdx = this._history.length;
          input.value = '';
        }
      }
    });
  }

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}


/* ── MurphyLibrarianChat ──────────────────────────────────────── */

/**
 * Floating chat panel for the Murphy Librarian AI assistant.
 */
class MurphyLibrarianChat {
  /**
   * @param {MurphyAPI} api An initialised MurphyAPI instance.
   */
  constructor(api) {
    this._api     = api;
    this._context = '';
    this._open    = false;
    this._mode    = 'ask';   // 'ask' (knowledge) or 'execute' (action)
    this._history = this._loadHistory();
    this._createButton();
    this._createPanel();
  }

  /**
   * Send a message to the Librarian and display the response.
   * @param {string} message User message text.
   */
  async send(message) {
    const trimmed = message.trim();
    if (!trimmed) return;
    const modeLabel = this._mode === 'ask' ? '📖' : '⚡';
    this._addBubble(`${modeLabel} ${trimmed}`, 'user');
    this._history.push({ role: 'user', text: `${modeLabel} ${trimmed}` });
    this._saveHistory();

    const result = await this._api.post('/librarian/ask', {
      query: trimmed,
      context: this._context,
      mode: this._mode,
    });
    if (result.ok) {
      const reply = result.data?.answer ?? result.data?.response ?? (typeof result.data === 'string' ? result.data : JSON.stringify(result.data));
      this._addBubble(reply, 'assistant');
      this._history.push({ role: 'assistant', text: reply });
    } else {
      this._addBubble(`Error: ${result.error || 'Unable to reach Librarian'}`, 'assistant');
      this._history.push({ role: 'assistant', text: `Error: ${result.error}` });
    }
    this._saveHistory();
  }

  /**
   * Apply an MSS operator (magnify/simplify/solidify) to the last assistant message.
   * @param {'magnify'|'simplify'|'solidify'} op MSS operator name.
   */
  async applyMSS(op) {
    const lastMsg = this._getLastAssistantText();
    if (!lastMsg) {
      this._addBubble('No previous response to apply ' + op + ' to. Send a message first.', 'assistant');
      return;
    }
    const labels = { magnify: '🔍 Magnify', simplify: '✂️ Simplify', solidify: '🔒 Solidify' };
    this._addBubble(labels[op] + ' applied…', 'user');
    this._history.push({ role: 'user', text: labels[op] + ' applied…' });
    this._saveHistory();

    const result = await this._api.post('/mss/' + op, { text: lastMsg, context: this._context });
    if (result.ok) {
      const r = result.data?.result || result.data || {};
      const output = r.output || r.text || r.plan || JSON.stringify(r, null, 2);
      this._addBubble(output, 'assistant');
      this._history.push({ role: 'assistant', text: output });
    } else {
      const errMsg = result.error || result.data?.error?.message || 'MSS operator not available';
      this._addBubble('Error: ' + errMsg, 'assistant');
      this._history.push({ role: 'assistant', text: 'Error: ' + errMsg });
    }
    this._saveHistory();
  }

  _getLastAssistantText() {
    for (let i = this._history.length - 1; i >= 0; i--) {
      if (this._history[i].role === 'assistant') return this._history[i].text;
    }
    return '';
  }

  /**
   * Update the current page context sent with queries.
   * @param {string} context Identifier for the current view.
   */
  setContext(context) {
    this._context = context;
  }

  _setMode(mode) {
    this._mode = mode;
    const askBtn = this._panel.querySelector('.murphy-mode-ask');
    const execBtn = this._panel.querySelector('.murphy-mode-execute');
    if (askBtn && execBtn) {
      const activeStyle = 'background:#0d9488;color:#fff;';
      const inactiveStyle = 'background:transparent;color:var(--text-secondary,#aaa);';
      askBtn.style.cssText = askBtn.style.cssText.replace(/background:[^;]+;color:[^;]+;/, mode === 'ask' ? activeStyle : inactiveStyle);
      execBtn.style.cssText = execBtn.style.cssText.replace(/background:[^;]+;color:[^;]+;/, mode === 'execute' ? activeStyle : inactiveStyle);
    }
    const input = this._panel.querySelector('.murphy-chat-input');
    if (input) {
      input.placeholder = mode === 'ask' ? 'Ask a question…' : 'Describe a task to execute…';
    }
  }

  _createButton() {
    this._btn = document.createElement('button');
    this._btn.className = 'murphy-chat-fab';
    this._btn.setAttribute('aria-label', 'Open Murphy Librarian');
    this._btn.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:600;width:56px;height:56px;'
      + 'border-radius:50%;border:none;cursor:pointer;background:#0d9488;color:#fff;box-shadow:0 4px 16px rgba(0,0,0,.4);'
      + 'display:flex;align-items:center;justify-content:center;transition:transform .15s;';
    this._btn.innerHTML = '<span style="font-family:monospace;font-size:16px;font-weight:700;letter-spacing:-1px;line-height:1;color:#fff;">&gt;_</span>';
    this._btn.addEventListener('click', () => this._toggle());
    document.body.appendChild(this._btn);
  }

  _createPanel() {
    this._panel = document.createElement('div');
    this._panel.className = 'murphy-chat-panel';
    this._panel.style.cssText = 'position:fixed;top:0;right:-360px;z-index:650;width:350px;height:100%;'
      + 'background:var(--bg-primary,#0d0d1a);border-left:1px solid var(--border-dim,#333);'
      + 'display:flex;flex-direction:column;transition:right .25s ease;box-shadow:-4px 0 24px rgba(0,0,0,.4);';

    this._panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--border-dim,#333);background:var(--bg-secondary,#1a1a2e);">
        <span style="font-weight:600;font-size:13px;color:var(--text-primary,#eee);letter-spacing:1px;">MURPHY LIBRARIAN</span>
        <button class="murphy-chat-close" style="background:none;border:none;color:var(--text-secondary,#aaa);cursor:pointer;font-size:18px;" aria-label="Close">&times;</button>
      </div>
      <div style="display:flex;gap:0;padding:0;border-bottom:1px solid var(--border-dim,#333);background:var(--bg-secondary,#1a1a2e);">
        <button class="murphy-mode-ask" style="flex:1;padding:8px 0;border:none;cursor:pointer;font-size:12px;font-weight:600;border-radius:0;background:#0d9488;color:#fff;transition:background .15s;" aria-label="Ask mode" title="Ask a question — get knowledge answers">📖 Ask</button>
        <button class="murphy-mode-execute" style="flex:1;padding:8px 0;border:none;cursor:pointer;font-size:12px;font-weight:600;border-radius:0;background:transparent;color:var(--text-secondary,#aaa);transition:background .15s;" aria-label="Execute mode" title="Execute a task — run commands and automations">⚡ Execute</button>
      </div>
      <div style="display:flex;gap:4px;padding:6px 14px;border-bottom:1px solid var(--border-dim,#333);background:var(--bg-primary,#0d0d1a);">
        <button class="murphy-mss-magnify" style="flex:1;padding:6px 0;border:1px solid #6366f1;background:transparent;color:#a5b4fc;cursor:pointer;font-size:11px;font-weight:600;border-radius:4px;transition:background .15s;" title="Magnify — expand detail and resolution on the last response">🔍 Magnify</button>
        <button class="murphy-mss-simplify" style="flex:1;padding:6px 0;border:1px solid #f59e0b;background:transparent;color:#fcd34d;cursor:pointer;font-size:11px;font-weight:600;border-radius:4px;transition:background .15s;" title="Simplify — reduce noise and complexity">✂️ Simplify</button>
        <button class="murphy-mss-solidify" style="flex:1;padding:6px 0;border:1px solid #10b981;background:transparent;color:#6ee7b7;cursor:pointer;font-size:11px;font-weight:600;border-radius:4px;transition:background .15s;" title="Solidify — lock into actionable plan">🔒 Solidify</button>
      </div>
      <div class="murphy-chat-messages" style="flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:8px;"></div>
      <div style="padding:10px 14px;border-top:1px solid var(--border-dim,#333);display:flex;gap:8px;">
        <input type="text" class="murphy-chat-input" placeholder="Ask a question…"
          style="flex:1;padding:8px 10px;background:var(--bg-secondary,#1a1a2e);color:var(--text-primary,#eee);border:1px solid var(--border-dim,#333);border-radius:3px;font-size:12px;outline:none;" autocomplete="off">
        <button class="murphy-chat-send" style="padding:6px 14px;background:#0d9488;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:12px;">Send</button>
      </div>`;

    this._panel.querySelector('.murphy-chat-close').addEventListener('click', () => this._toggle());
    this._panel.querySelector('.murphy-mode-ask').addEventListener('click', () => this._setMode('ask'));
    this._panel.querySelector('.murphy-mode-execute').addEventListener('click', () => this._setMode('execute'));
    this._panel.querySelector('.murphy-mss-magnify').addEventListener('click', () => this.applyMSS('magnify'));
    this._panel.querySelector('.murphy-mss-simplify').addEventListener('click', () => this.applyMSS('simplify'));
    this._panel.querySelector('.murphy-mss-solidify').addEventListener('click', () => this.applyMSS('solidify'));

    const input   = this._panel.querySelector('.murphy-chat-input');
    const sendBtn = this._panel.querySelector('.murphy-chat-send');
    sendBtn.addEventListener('click', () => { this.send(input.value); input.value = ''; });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { this.send(input.value); input.value = ''; }
    });

    document.body.appendChild(this._panel);

    this._restoreBubbles();
  }

  _toggle() {
    this._open = !this._open;
    this._panel.style.right = this._open ? '0' : '-360px';
    this._btn.style.transform = this._open ? 'scale(0.85)' : 'scale(1)';
    if (this._open) {
      const input = this._panel.querySelector('.murphy-chat-input');
      if (input) setTimeout(() => input.focus(), 260);
    }
  }

  _addBubble(text, role) {
    const messages = this._panel.querySelector('.murphy-chat-messages');
    if (!messages) return;
    const bubble = document.createElement('div');
    bubble.className = `murphy-chat-bubble murphy-chat-${role}`;
    const align = role === 'user' ? 'align-self:flex-end;background:#0d9488;' : 'align-self:flex-start;background:var(--bg-secondary,#1a1a2e);border:1px solid var(--border-dim,#333);';
    bubble.style.cssText = `max-width:85%;padding:8px 12px;border-radius:8px;font-size:12px;line-height:1.5;color:var(--text-primary,#eee);${align}word-wrap:break-word;`;
    if (role === 'user') {
      bubble.textContent = text;
    } else {
      // Render assistant messages with markdown formatting
      if (typeof MurphyMarkdown !== 'undefined') {
        MurphyMarkdown.injectStyles();
        bubble.innerHTML = MurphyMarkdown.render(text);
      } else {
        bubble.textContent = text;
      }
    }
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  _restoreBubbles() {
    for (const msg of this._history) {
      this._addBubble(msg.text, msg.role);
    }
  }

  _loadHistory() {
    try {
      const raw = sessionStorage.getItem('murphy_chat_history');
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }

  _saveHistory() {
    try { sessionStorage.setItem('murphy_chat_history', JSON.stringify(this._history)); } catch { /* storage unavailable */ }
  }
}


/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 2b — LLM OUTPUT FORMATTER (Markdown → safe HTML)
 *  Renders LLM responses with professional formatting similar to
 *  ChatGPT/Claude: headings, bold, italic, code blocks, lists, links.
 * ═══════════════════════════════════════════════════════════════════ */

const MurphyMarkdown = {
  /**
   * Convert markdown text to safe HTML for LLM output display.
   * Handles: headers, bold, italic, code blocks, inline code,
   * unordered/ordered lists, horizontal rules, links, line breaks.
   */
  render(text) {
    if (!text) return '';
    let html = this._escapeHtml(text);

    // Fenced code blocks: ```lang\n...\n```
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre class="murphy-md-code-block"><code class="murphy-md-code-lang-${lang || 'text'}">${code.trim()}</code></pre>`
    );

    // Inline code: `code`
    html = html.replace(/`([^`\n]+)`/g, '<code class="murphy-md-inline-code">$1</code>');

    // Headings (### → h5, ## → h4, # → h3) — only at line start
    html = html.replace(/^#### (.+)$/gm, '<h6 class="murphy-md-h6">$1</h6>');
    html = html.replace(/^### (.+)$/gm, '<h5 class="murphy-md-h5">$1</h5>');
    html = html.replace(/^## (.+)$/gm, '<h4 class="murphy-md-h4">$1</h4>');
    html = html.replace(/^# (.+)$/gm, '<h3 class="murphy-md-h3">$1</h3>');

    // Bold + italic: ***text*** or ___text___
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');

    // Bold: **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

    // Italic: *text* or _text_  (not inside words)
    html = html.replace(/(?<!\w)\*([^*\n]+)\*(?!\w)/g, '<em>$1</em>');
    html = html.replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, '<em>$1</em>');

    // Horizontal rule: --- or ***
    html = html.replace(/^(---|\*\*\*)$/gm, '<hr class="murphy-md-hr">');

    // Unordered lists: - item or * item
    html = html.replace(/^[\-\*] (.+)$/gm, '<li class="murphy-md-li">$1</li>');
    html = html.replace(/((?:<li class="murphy-md-li">.*<\/li>\n?)+)/g, '<ul class="murphy-md-ul">$1</ul>');

    // Ordered lists: 1. item
    html = html.replace(/^\d+\. (.+)$/gm, '<li class="murphy-md-oli">$1</li>');
    html = html.replace(/((?:<li class="murphy-md-oli">.*<\/li>\n?)+)/g, '<ol class="murphy-md-ol">$1</ol>');

    // Links: [text](url) — whitelist safe protocols only
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
      const trimmed = url.trim();
      if (!/^(https?:|mailto:|\/)/i.test(trimmed)) return text;
      const safeUrl = this._escapeHtml(trimmed);
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="murphy-md-link">${text}</a>`;
    });

    // Line breaks: double newline → paragraph break, single → <br>
    html = html.replace(/\n\n/g, '</p><p class="murphy-md-p">');
    html = html.replace(/\n/g, '<br>');

    // Wrap in container
    return `<div class="murphy-md"><p class="murphy-md-p">${html}</p></div>`;
  },

  /** Escape HTML entities to prevent XSS */
  _escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(text).replace(/[&<>"']/g, c => map[c]);
  },

  /** Inject styles into the document (idempotent) */
  injectStyles() {
    if (document.getElementById('murphy-md-styles')) return;
    const style = document.createElement('style');
    style.id = 'murphy-md-styles';
    style.textContent = `
      .murphy-md { line-height: 1.6; word-wrap: break-word; }
      .murphy-md p.murphy-md-p { margin: 0 0 0.5em 0; }
      .murphy-md p.murphy-md-p:last-child { margin-bottom: 0; }
      .murphy-md h3.murphy-md-h3, .murphy-md h4.murphy-md-h4,
      .murphy-md h5.murphy-md-h5, .murphy-md h6.murphy-md-h6 {
        margin: 0.8em 0 0.3em; font-weight: 700; line-height: 1.3;
        color: var(--text-primary, #eee);
      }
      .murphy-md h3.murphy-md-h3 { font-size: 1.15em; }
      .murphy-md h4.murphy-md-h4 { font-size: 1.05em; }
      .murphy-md h5.murphy-md-h5 { font-size: 0.95em; }
      .murphy-md h6.murphy-md-h6 { font-size: 0.9em; color: var(--text-dim, #aaa); }
      .murphy-md strong { font-weight: 700; color: var(--text-primary, #fff); }
      .murphy-md em { font-style: italic; }
      .murphy-md-inline-code {
        background: var(--bg-elevated, #1e293b); padding: 1px 5px;
        border-radius: 3px; font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.88em; color: var(--color-success, #0d9488);
      }
      .murphy-md-code-block {
        background: var(--bg-elevated, #0f172a); border: 1px solid var(--border-dim, #334155);
        border-radius: 6px; padding: 0.75em 1em; margin: 0.5em 0;
        overflow-x: auto; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.85em;
        line-height: 1.5; color: var(--text-primary, #e2e8f0);
      }
      .murphy-md-code-block code { background: none; padding: 0; }
      .murphy-md-ul, .murphy-md-ol { margin: 0.4em 0 0.4em 1.5em; padding: 0; }
      .murphy-md-li, .murphy-md-oli { margin: 0.15em 0; }
      .murphy-md-hr { border: none; border-top: 1px solid var(--border-dim, #334155); margin: 0.8em 0; }
      .murphy-md-link { color: var(--color-success, #0d9488); text-decoration: underline; }
      .murphy-md-link:hover { opacity: 0.8; }
    `;
    document.head.appendChild(style);
  }
};

/* ═══════════════════════════════════════════════════════════════════
 *  SECTION 3 — EXPORTS & GLOBALS
 * ═══════════════════════════════════════════════════════════════════ */

/* ── MurphyWebSocket ──────────────────────────────────────────────── */
/**
 * WebSocket client with automatic reconnection and exponential backoff.
 * Usage:
 *   const ws = new MurphyWebSocket('/ws/terminal')
 *     .on('message', data => console.log(data))
 *     .connect();
 */
class MurphyWebSocket {
  constructor(path, options = {}) {
    this._path = path;
    this._reconnectDelay = options.reconnectDelay || 3000;
    this._maxReconnectDelay = options.maxReconnectDelay || 30000;
    this._currentDelay = this._reconnectDelay;
    this._handlers = { message: [], open: [], close: [], error: [] };
    this._ws = null;
    this._shouldReconnect = true;
  }

  /** Open the WebSocket connection. Returns `this` for chaining. */
  connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this._ws = new WebSocket(`${protocol}//${location.host}${this._path}`);
    this._ws.onopen = (e) => { this._currentDelay = this._reconnectDelay; this._emit('open', e); };
    this._ws.onmessage = (e) => {
      let data = e.data;
      try { data = JSON.parse(e.data); } catch (_) { /* leave as string */ }
      this._emit('message', data);
    };
    this._ws.onclose = (e) => { this._emit('close', e); if (this._shouldReconnect) this._reconnect(); };
    this._ws.onerror = (e) => { this._emit('error', e); };
    return this;
  }

  /** Send a JSON-serialisable message. */
  send(data) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(data));
    }
  }

  /** Register an event handler. Returns `this` for chaining. */
  on(event, handler) { (this._handlers[event] = this._handlers[event] || []).push(handler); return this; }

  /** Close the connection and disable auto-reconnect. */
  disconnect() { this._shouldReconnect = false; if (this._ws) this._ws.close(); }

  _emit(event, data) { (this._handlers[event] || []).forEach(h => h(data)); }

  _reconnect() {
    setTimeout(() => {
      this._currentDelay = Math.min(this._currentDelay * 1.5, this._maxReconnectDelay);
      this.connect();
    }, this._currentDelay);
  }
}

window.MurphyAPI            = MurphyAPI;
window.MurphyWebSocket      = MurphyWebSocket;
window.MurphyToast          = MurphyToast;
window.MurphyModal          = MurphyModal;
window.MurphyHealth         = MurphyHealth;
window.MurphyTable          = MurphyTable;
window.MurphyChart          = MurphyChart;
window.MurphyTheme          = MurphyTheme;
window.MurphyJargon         = MurphyJargon;
window.MurphyKeyboard       = MurphyKeyboard;
window.MurphyTerminalPanel  = MurphyTerminalPanel;
window.MurphyLibrarianChat  = MurphyLibrarianChat;
window.MurphyMarkdown       = MurphyMarkdown;

/* ES module export — only when loaded as type="module" */
try {
  if (typeof globalThis !== 'undefined' && typeof globalThis[Symbol.for('murphy-components-exported')] === 'undefined') {
    globalThis[Symbol.for('murphy-components-exported')] = true;
  }
} catch (_) { /* non-module context */ }
