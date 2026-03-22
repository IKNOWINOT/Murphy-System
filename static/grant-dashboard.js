/* grant-dashboard.js — Murphy System Grant Dashboard
 * © 2020 Inoni Limited Liability Company by Corey Post
 * License: BSL 1.1
 */

(function () {
  'use strict';

  /* ─────────────────────────────────────────────────────────────
     CONSTANTS
  ───────────────────────────────────────────────────────────── */

  var REFRESH_INTERVAL_MS = 30000;
  var SESSION_KEY = 'murphy_grant_session_id';

  var STATUS_CONFIG = {
    draft:      { label: 'Draft',      cssClass: 'status-draft'      },
    in_review:  { label: 'In Review',  cssClass: 'status-in-review'  },
    approved:   { label: 'Approved',   cssClass: 'status-approved'   },
    submitted:  { label: 'Submitted',  cssClass: 'status-submitted'  },
    waiting:    { label: 'Waiting',    cssClass: 'status-waiting'    },
    complete:   { label: 'Complete',   cssClass: 'status-complete'   }
  };

  var FILTER_ALL = 'all';

  /* ─────────────────────────────────────────────────────────────
     STATE
  ───────────────────────────────────────────────────────────── */

  var sessionId     = getOrCreateSessionId();
  var applications  = [];
  var activeFilter  = FILTER_ALL;
  var refreshTimer  = null;

  /* ─────────────────────────────────────────────────────────────
     SESSION
  ───────────────────────────────────────────────────────────── */

  function getOrCreateSessionId() {
    var existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    var newId = generateUUID();
    localStorage.setItem(SESSION_KEY, newId);
    return newId;
  }

  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /* ─────────────────────────────────────────────────────────────
     API
  ───────────────────────────────────────────────────────────── */

  function loadApplications() {
    return fetch('/api/grants/sessions/' + encodeURIComponent(sessionId) + '/applications', {
      method: 'GET',
      credentials: 'include'
    })
      .then(function (res) {
        if (!res.ok) throw new Error('Server returned ' + res.status);
        return res.json();
      });
  }

  /* ─────────────────────────────────────────────────────────────
     RENDERING
  ───────────────────────────────────────────────────────────── */

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatCurrency(value) {
    var n = parseInt(value, 10) || 0;
    return '$' + n.toLocaleString('en-US');
  }

  function formatRelativeDate(isoString) {
    if (!isoString) return 'Unknown';
    var d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    var now = Date.now();
    var diffMs = now - d.getTime();
    var diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return diffMin + 'm ago';
    var diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + 'h ago';
    var diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return diffDay + 'd ago';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  function getStatusConfig(status) {
    var key = (status || '').toLowerCase().replace(/[\s-]+/g, '_');
    return STATUS_CONFIG[key] || { label: status || 'Unknown', cssClass: 'status-draft' };
  }

  function renderApplicationCard(app) {
    var cfg = getStatusConfig(app.status);
    var appId = app.app_id || app.application_id || app.id || '';
    var estimatedValue = app.estimated_value
      ? (app.estimated_value > 1 ? formatCurrency(app.estimated_value) : 'Up to ' + Math.round(app.estimated_value * 100) + '%')
      : 'TBD';

    var card = document.createElement('div');
    card.className = 'dashboard-card';
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', 'Open application for ' + (app.program_name || 'Application'));
    card.dataset.appId = appId;

    card.innerHTML = [
      '<div class="dashboard-card-header">',
        '<h3>' + escapeHtml(app.program_name || 'Application') + '</h3>',
        '<span class="status-badge ' + cfg.cssClass + '">' + escapeHtml(cfg.label) + '</span>',
      '</div>',
      '<div class="dashboard-card-value">' + escapeHtml(estimatedValue) + '</div>',
      '<div class="dashboard-card-meta">',
        '<span title="Last updated">🕐 ' + escapeHtml(formatRelativeDate(app.updated_at || app.created_at)) + '</span>',
        (app.deadline ? ' · 📅 Due ' + escapeHtml(formatRelativeDate(app.deadline)) : ''),
      '</div>',
      '<div class="dashboard-card-footer">',
        '<a href="/ui/grant-application?app_id=' + encodeURIComponent(appId) + '&session_id=' + encodeURIComponent(sessionId) + '"',
           ' class="murphy-btn murphy-btn-primary murphy-btn-sm">Continue →</a>',
      '</div>'
    ].join('');

    card.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') return;
      window.location.href = '/ui/grant-application?app_id=' + encodeURIComponent(appId) +
        '&session_id=' + encodeURIComponent(sessionId);
    });

    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        window.location.href = '/ui/grant-application?app_id=' + encodeURIComponent(appId) +
          '&session_id=' + encodeURIComponent(sessionId);
      }
    });

    return card;
  }

  function renderDashboard() {
    var grid = document.getElementById('applications-grid');
    var emptyState = document.getElementById('empty-state');
    var countEl = document.getElementById('app-count');
    if (!grid) return;

    var filtered = applications.filter(function (app) {
      if (activeFilter === FILTER_ALL) return true;
      var key = (app.status || '').toLowerCase().replace(/[\s-]+/g, '_');
      return key === activeFilter;
    });

    if (countEl) {
      countEl.textContent = filtered.length + ' application' + (filtered.length !== 1 ? 's' : '');
    }

    if (filtered.length === 0) {
      grid.innerHTML = '';
      grid.style.display = 'none';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    grid.style.display = 'grid';
    grid.innerHTML = '';

    filtered.forEach(function (app) {
      grid.appendChild(renderApplicationCard(app));
    });
  }

  /* ─────────────────────────────────────────────────────────────
     FILTER BAR
  ───────────────────────────────────────────────────────────── */

  function initFilterBar() {
    var bar = document.getElementById('filter-bar');
    if (!bar) return;

    bar.addEventListener('click', function (e) {
      var btn = e.target.closest('.filter-btn[data-filter]');
      if (!btn) return;

      activeFilter = btn.dataset.filter;

      bar.querySelectorAll('.filter-btn').forEach(function (b) {
        b.classList.toggle('active', b.dataset.filter === activeFilter);
      });

      renderDashboard();
    });
  }

  /* ─────────────────────────────────────────────────────────────
     LOAD & REFRESH
  ───────────────────────────────────────────────────────────── */

  function loadAndRender() {
    updateLastRefreshed(true);

    loadApplications()
      .then(function (data) {
        applications = Array.isArray(data) ? data : (data.applications || []);
        renderDashboard();
        updateLastRefreshed(false);
      })
      .catch(function (err) {
        console.error('[Grant Dashboard] Load failed:', err);
        updateLastRefreshed(false);
        var grid = document.getElementById('applications-grid');
        if (grid && applications.length === 0) {
          grid.innerHTML = [
            '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--danger);font-family:var(--font-ui,Inter,sans-serif);">',
              '<p style="margin:0;">Unable to load applications. <button class="murphy-btn murphy-btn-ghost murphy-btn-sm" onclick="location.reload()">Retry</button></p>',
            '</div>'
          ].join('');
        }
      });
  }

  function updateLastRefreshed(loading) {
    var el = document.getElementById('last-refreshed');
    if (!el) return;
    el.textContent = loading ? 'Refreshing…' : 'Updated ' + new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }

  function scheduleRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadAndRender, REFRESH_INTERVAL_MS);
  }

  /* ─────────────────────────────────────────────────────────────
     BOOT
  ───────────────────────────────────────────────────────────── */

  function init() {
    initFilterBar();
    loadAndRender();
    scheduleRefresh();

    // Expose for manual refresh
    window.murphyGrantDashboard = {
      refresh: loadAndRender,
      sessionId: sessionId
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
