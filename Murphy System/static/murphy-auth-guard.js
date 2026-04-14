/**
 * murphy-auth-guard.js — Universal Session & Auth Guard
 * Murphy System — COMM-AUTH-GUARD-001
 *
 * Provides consistent authentication checking across ALL protected pages.
 * Include this script on any page that requires an authenticated session.
 *
 * Features:
 *   - Session token validation via cookie or localStorage
 *   - Automatic redirect to login on missing/invalid session
 *   - CSRF token generation and injection into forms
 *   - Centralised error display utility
 *   - Event backbone connection helper
 *
 * Usage:
 *   <script src="/static/murphy-auth-guard.js"></script>
 *   <script>
 *     MurphyAuth.requireAuth();          // redirect if not logged in
 *     MurphyAuth.getToken();             // get current session token
 *     MurphyAuth.apiFetch('/api/...', { method: 'POST', body: ... });
 *   </script>
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * Creator: Corey Post
 * License: BSL 1.1
 */

/* global window, document, localStorage, fetch, console */
/* eslint-disable no-console */

var MurphyAuth = (function () {
  'use strict';

  // ─── Configuration ──────────────────────────────────────────────────
  var LOGIN_URL = '/ui/login';
  var SESSION_KEY = 'murphy_session_token';
  var USER_ID_KEY = 'murphy_user_id';
  var CSRF_KEY = 'murphy_csrf_token';
  var SESSION_CHECK_ENDPOINT = '/api/auth/session-check';
  var LOG_PREFIX = '[MurphyAuth]';

  // ─── Token Management ──────────────────────────────────────────────
  function getToken() {
    // 1. Check cookie
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.indexOf('murphy_session=') === 0) {
        return c.substring('murphy_session='.length);
      }
    }
    // 2. Check localStorage
    try {
      var token = localStorage.getItem(SESSION_KEY);
      if (token) return token;
    } catch (_) {
      /* localStorage unavailable — COMM-AUTH-GUARD-002 */
    }
    return null;
  }

  function getUserId() {
    try {
      return localStorage.getItem(USER_ID_KEY) || null;
    } catch (_) {
      return null;
    }
  }

  function isLoggedIn() {
    return !!getToken();
  }

  function logout() {
    try {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(USER_ID_KEY);
    } catch (_) { /* COMM-AUTH-GUARD-003 */ }
    document.cookie = 'murphy_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = LOGIN_URL;
  }

  // ─── Auth Guard ─────────────────────────────────────────────────────

  /**
   * Require authentication. If no valid session exists, redirect to login.
   * @param {Object} [opts] - Options
   * @param {string} [opts.redirectTo] - Override login redirect URL
   * @param {string} [opts.requiredRole] - Require specific role (future)
   */
  function requireAuth(opts) {
    opts = opts || {};
    var token = getToken();
    if (!token) {
      console.warn(LOG_PREFIX, 'No session token found — redirecting to login');
      var next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = (opts.redirectTo || LOGIN_URL) + '?next=' + next;
      return false;
    }
    return true;
  }

  // ─── CSRF Token ─────────────────────────────────────────────────────

  function getCsrfToken() {
    try {
      var token = localStorage.getItem(CSRF_KEY);
      if (!token) {
        token = _generateId(32);
        localStorage.setItem(CSRF_KEY, token);
      }
      return token;
    } catch (_) {
      return _generateId(32);
    }
  }

  function _generateId(len) {
    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    var result = '';
    for (var i = 0; i < len; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  // ─── API Fetch Wrapper ──────────────────────────────────────────────

  /**
   * Authenticated fetch wrapper. Automatically includes session token
   * and CSRF token. Handles 401 responses by redirecting to login.
   *
   * @param {string} url - API endpoint URL
   * @param {Object} [options] - Fetch options
   * @returns {Promise<Response>}
   */
  function apiFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.credentials = options.credentials || 'same-origin';

    var token = getToken();
    if (token && !options.headers['Authorization']) {
      options.headers['Authorization'] = 'Bearer ' + token;
    }

    // Add CSRF token for state-changing requests
    var method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
      options.headers['X-CSRF-Token'] = getCsrfToken();
    }

    return fetch(url, options).then(function (res) {
      if (res.status === 401) {
        console.warn(LOG_PREFIX, 'Session expired (401) — redirecting to login');
        var next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = LOGIN_URL + '?next=' + next;
        return Promise.reject(new Error('Session expired'));
      }
      return res;
    });
  }

  // ─── Error Display ──────────────────────────────────────────────────

  /**
   * Show a user-visible error toast/banner.
   * @param {string} message - Error message to display
   * @param {Object} [opts] - Display options
   * @param {number} [opts.duration] - Auto-dismiss after ms (0 = persistent)
   * @param {string} [opts.level] - 'error' | 'warning' | 'info'
   */
  function showError(message, opts) {
    opts = opts || {};
    var level = opts.level || 'error';
    var duration = typeof opts.duration === 'number' ? opts.duration : 6000;

    console.error(LOG_PREFIX, '[' + level.toUpperCase() + ']', message);

    // Try to find an existing error container
    var container = document.getElementById('murphy-error-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'murphy-error-container';
      container.style.cssText = 'position:fixed;top:12px;right:12px;z-index:99999;display:flex;flex-direction:column;gap:8px;max-width:420px;';
      document.body.appendChild(container);
    }

    var colors = {
      error: { bg: 'rgba(239,68,68,0.95)', border: '#ef4444' },
      warning: { bg: 'rgba(255,166,62,0.95)', border: '#ffa63e' },
      info: { bg: 'rgba(59,158,255,0.95)', border: '#3b9eff' }
    };
    var c = colors[level] || colors.error;

    var toast = document.createElement('div');
    toast.style.cssText = 'background:' + c.bg + ';border:1px solid ' + c.border +
      ';border-radius:8px;padding:12px 16px;color:#fff;font-size:13px;font-family:Inter,system-ui,sans-serif;' +
      'box-shadow:0 4px 12px rgba(0,0,0,0.3);cursor:pointer;transition:opacity 0.3s;';
    toast.textContent = message;
    toast.onclick = function () {
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 300);
    };

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(function () {
        toast.style.opacity = '0';
        setTimeout(function () { toast.remove(); }, 300);
      }, duration);
    }
  }

  // ─── Event Backbone Client ──────────────────────────────────────────

  /**
   * Subscribe to the event backbone SSE stream.
   * @param {Object} opts
   * @param {string} [opts.channel] - Event channel (default: 'system')
   * @param {function} opts.onEvent - Callback for each event
   * @param {function} [opts.onError] - Error callback
   * @returns {Object} - { close: function }
   */
  function subscribeEvents(opts) {
    opts = opts || {};
    var channel = opts.channel || 'system';
    var subscriberId = null;
    var eventSource = null;

    // Step 1: Subscribe to get a subscriber ID
    apiFetch('/api/events/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: channel })
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (!data.success || !data.subscriberId) {
        console.error(LOG_PREFIX, 'Event subscription failed:', data);
        if (opts.onError) opts.onError(new Error('Subscription failed'));
        return;
      }
      subscriberId = data.subscriberId;

      // Step 2: Connect to SSE stream
      eventSource = new EventSource('/api/events/stream/' + subscriberId);
      eventSource.onmessage = function (e) {
        try {
          var event = JSON.parse(e.data);
          if (opts.onEvent) opts.onEvent(event);
        } catch (parseErr) {
          console.warn(LOG_PREFIX, 'Event parse error:', parseErr.message);
        }
      };
      eventSource.onerror = function (err) {
        console.warn(LOG_PREFIX, 'EventSource error — will reconnect:', err);
        if (opts.onError) opts.onError(err);
      };
    })
    .catch(function (err) {
      console.error(LOG_PREFIX, 'Event subscribe request failed:', err.message);
      if (opts.onError) opts.onError(err);
    });

    return {
      close: function () {
        if (eventSource) {
          try { eventSource.close(); } catch (_) { /* COMM-EVE-001 */ }
          eventSource = null;
        }
      }
    };
  }

  // ─── Public API ─────────────────────────────────────────────────────
  return {
    getToken: getToken,
    getUserId: getUserId,
    isLoggedIn: isLoggedIn,
    logout: logout,
    requireAuth: requireAuth,
    getCsrfToken: getCsrfToken,
    apiFetch: apiFetch,
    showError: showError,
    subscribeEvents: subscribeEvents
  };

})();
