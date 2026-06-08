/**
 * <murphy-readout> — drill-down readout web component (PCR-020 / Phase 4a)
 *
 * Renders any action result with three levels of inspection:
 *   Level 1 (default):  output summary + click to expand
 *   Level 2 (expanded): inputs + source refs
 *   Level 3 (deep):     follow parent_result_id chain
 *
 * Backed by /api/provenance/<result_id> (GET, owner-only).
 *
 * Usage:
 *   <murphy-readout result-id="r_abc123" expanded="0"></murphy-readout>
 *
 * Or programmatically:
 *   const r = document.createElement('murphy-readout');
 *   r.setAttribute('result-id', 'r_abc123');
 *   document.body.appendChild(r);
 *
 * The component fetches its data on connectedCallback. If the result-id
 * is the literal string "preview", it renders a built-in demo card.
 *
 * Plan: docs/strategy/final_shape_of_complete_plan.md (Phase 4a)
 */
(function() {
  if (window.customElements && window.customElements.get('murphy-readout')) return;

  const STYLE = `
    :host { display:block; font-family:-apple-system,BlinkMacSystemFont,sans-serif; }
    .card { background:#0e1820; border:1px solid #1f2a35; border-radius:8px;
            padding:10px 12px; margin:6px 0; color:#cfe1ec; font-size:13px; }
    .hdr { display:flex; justify-content:space-between; align-items:center;
           cursor:pointer; user-select:none; }
    .action { color:#5ee0c4; font-weight:600; }
    .when { color:#8aa; font-size:11px; }
    .summary { margin-top:6px; line-height:1.4; }
    .level { margin-top:8px; padding-top:8px; border-top:1px solid #1a2530;
             font-size:12px; color:#a8c0d0; }
    .label { color:#789; text-transform:uppercase; font-size:10px;
             letter-spacing:1px; margin-bottom:3px; }
    .kv { background:#0a141c; border-radius:4px; padding:6px 8px;
          font-family:ui-monospace,monospace; font-size:11px;
          white-space:pre-wrap; word-break:break-all; max-height:200px;
          overflow:auto; }
    .ref { color:#7aafd1; cursor:pointer; }
    .ref:hover { text-decoration:underline; }
    .chev { color:#5ee0c4; font-size:10px; margin-left:6px; }
    .err { color:#ff7a7a; font-style:italic; }
    .loading { color:#789; font-style:italic; }
  `;

  class MurphyReadout extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._expanded = false;
      this._data = null;
      this._loading = false;
      this._error = null;
    }

    static get observedAttributes() { return ['result-id', 'expanded']; }

    attributeChangedCallback(name, _old, val) {
      if (name === 'expanded') {
        this._expanded = (val === '1' || val === 'true');
        this._render();
      }
      if (name === 'result-id') {
        this._fetch();
      }
    }

    connectedCallback() {
      this._render();
      this._fetch();
    }

    async _fetch() {
      const rid = this.getAttribute('result-id');
      if (!rid) return;
      if (rid === 'preview') {
        this._data = this._previewData();
        this._render();
        return;
      }
      this._loading = true;
      this._render();
      try {
        const r = await fetch('/api/provenance/' + encodeURIComponent(rid), {
          credentials: 'include'
        });
        if (r.ok) {
          this._data = await r.json();
          this._error = null;
        } else if (r.status === 404) {
          this._error = 'No provenance recorded for this result.';
        } else if (r.status === 401 || r.status === 403) {
          this._error = 'Not authorized.';
        } else {
          this._error = 'Could not load (HTTP ' + r.status + ').';
        }
      } catch (e) {
        this._error = 'Network error.';
      } finally {
        this._loading = false;
        this._render();
      }
    }

    _previewData() {
      return {
        result_id: 'preview',
        produced_at: new Date().toISOString(),
        produced_by: 'demo',
        action_name: 'Demo readout (no real provenance)',
        inputs_json: '{"example":"this is what a readout looks like"}',
        source_refs_json: '[]',
        output_summary: 'This is a preview card. Real readouts show the actual upstream chain.',
        parent_result_id: null,
        cost_usd: 0
      };
    }

    _toggle() {
      this._expanded = !this._expanded;
      this._render();
    }

    _render() {
      const root = this.shadowRoot;
      if (!root) return;
      let body = '';
      if (this._loading) {
        body = '<div class="card"><div class="loading">Loading readout…</div></div>';
      } else if (this._error) {
        body = '<div class="card"><div class="err">' + this._esc(this._error) + '</div></div>';
      } else if (!this._data) {
        body = '<div class="card"><div class="loading">No data.</div></div>';
      } else {
        body = this._renderCard(this._data);
      }
      root.innerHTML = '<style>' + STYLE + '</style>' + body;
      const hdr = root.querySelector('.hdr');
      if (hdr) hdr.addEventListener('click', () => this._toggle());
      root.querySelectorAll('.ref[data-rid]').forEach(el => {
        el.addEventListener('click', (ev) => {
          ev.stopPropagation();
          this.setAttribute('result-id', el.getAttribute('data-rid'));
        });
      });
    }

    _renderCard(d) {
      const when = (d.produced_at || '').replace('T', ' ').slice(0, 19);
      const cost = (d.cost_usd != null && d.cost_usd > 0)
                   ? ' · $' + Number(d.cost_usd).toFixed(4) : '';
      const head = '<div class="hdr">' +
                     '<div><span class="action">' + this._esc(d.action_name || '(unnamed action)') + '</span>' +
                     '<span class="chev">' + (this._expanded ? '▼' : '▶') + '</span></div>' +
                     '<div class="when">' + this._esc(when) + cost + '</div>' +
                   '</div>';
      const summary = d.output_summary
                      ? '<div class="summary">' + this._esc(d.output_summary) + '</div>' : '';
      let level2 = '';
      let level3 = '';
      if (this._expanded) {
        if (d.inputs_json) {
          level2 += '<div class="level"><div class="label">Inputs</div>' +
                    '<div class="kv">' + this._esc(this._pretty(d.inputs_json)) + '</div></div>';
        }
        const refs = this._safeParse(d.source_refs_json, []);
        if (refs && refs.length) {
          level2 += '<div class="level"><div class="label">Source refs</div>' +
                    '<div class="kv">' +
                    refs.map(r => this._esc(JSON.stringify(r))).join('\n') +
                    '</div></div>';
        }
        if (d.produced_by) {
          level2 += '<div class="level"><div class="label">Produced by</div>' +
                    this._esc(d.produced_by) + '</div>';
        }
        if (d.parent_result_id) {
          level3 = '<div class="level"><div class="label">Upstream result</div>' +
                   '<span class="ref" data-rid="' + this._esc(d.parent_result_id) + '">' +
                   this._esc(d.parent_result_id) + ' →</span></div>';
        }
      }
      return '<div class="card">' + head + summary + level2 + level3 + '</div>';
    }

    _esc(s) {
      if (s == null) return '';
      return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[c]));
    }

    _pretty(j) {
      try { return JSON.stringify(JSON.parse(j), null, 2); }
      catch (_) { return j; }
    }

    _safeParse(j, fallback) {
      if (!j) return fallback;
      try { return JSON.parse(j); } catch (_) { return fallback; }
    }
  }

  window.customElements.define('murphy-readout', MurphyReadout);
})();
