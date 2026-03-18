/**
 * murphy_auth.js — Profile-Gated Terminal Authentication
 * Murphy System
 *
 * On page load, calls GET /api/profiles/me.
 *   - 401 / missing session  → redirect to landing page signup
 *   - Profile exists         → load terminal_config, show/hide features
 *
 * Usage (add to any terminal HTML before closing </body>):
 *   <script src="/murphy_auth.js"></script>
 *
 * The script reads the API port from:
 *   1. The URL query param  ?apiPort=XXXX
 *   2. The global window.MURPHY_API_PORT constant
 *   3. Default 8000
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * License: BSL 1.1
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Config
  // ---------------------------------------------------------------------------

  const DEFAULT_PORT = 8000;
  const LANDING_PAGE = "/ui/landing";
  const PROFILE_ENDPOINT = "/api/profiles/me";
  const TERMINAL_CONFIG_ENDPOINT = "/api/profiles/me/terminal-config";

  function _apiPort() {
    const params = new URLSearchParams(window.location.search);
    if (params.has("apiPort")) return parseInt(params.get("apiPort"), 10);
    if (window.MURPHY_API_PORT) return window.MURPHY_API_PORT;
    return DEFAULT_PORT;
  }

  function _baseUrl() {
    return window.location.origin;
  }

  // ---------------------------------------------------------------------------
  // Profile fetch
  // ---------------------------------------------------------------------------

  async function fetchProfile() {
    const url = _baseUrl() + PROFILE_ENDPOINT;
    const token = _getSessionToken();
    const headers = token ? { Authorization: "Bearer " + token } : {};
    try {
      const res = await fetch(url, { headers });
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  async function fetchTerminalConfig() {
    const url = _baseUrl() + TERMINAL_CONFIG_ENDPOINT;
    const token = _getSessionToken();
    const headers = token ? { Authorization: "Bearer " + token } : {};
    try {
      const res = await fetch(url, { headers });
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  // ---------------------------------------------------------------------------
  // Feature gating
  // ---------------------------------------------------------------------------

  /**
   * Show or hide terminal sections based on terminal_config.features.
   *
   * Elements declare which feature they belong to via data-feature="key":
   *   <section data-feature="automation_library">...</section>
   *
   * If the config says feature is false/absent, the section is hidden.
   */
  function applyTerminalConfig(config) {
    if (!config || !config.features) return;
    const features = config.features;

    document.querySelectorAll("[data-feature]").forEach(function (el) {
      const key = el.getAttribute("data-feature");
      const allowed = features[key] === true;
      el.style.display = allowed ? "" : "none";
    });

    // Expose config for inline scripts that need it
    window.MURPHY_TERMINAL_CONFIG = config;

    // Fire a custom event so terminal pages can react
    window.dispatchEvent(
      new CustomEvent("murphy:config_loaded", { detail: config })
    );
  }

  /**
   * Architect terminal guard:
   * - founder_admin → allow
   * - otherwise     → show "Create org or go to your terminal" prompt
   */
  function guardArchitectTerminal(profile) {
    if (!document.body.dataset.terminal === "architect") return;
    if (profile.role === "founder_admin") return;

    const overlay = document.createElement("div");
    overlay.id = "murphy-arch-guard";
    overlay.style.cssText = [
      "position:fixed;top:0;left:0;width:100%;height:100%;",
      "background:rgba(0,0,0,.85);color:#00ff41;",
      "font-family:monospace;display:flex;align-items:center;",
      "justify-content:center;z-index:9999;flex-direction:column;gap:1rem;",
    ].join("");

    overlay.innerHTML = [
      "<h2 style='color:#00ffff'>Architect Terminal — Admin Access Required</h2>",
      "<p>Your current role is <strong>" + profile.role + "</strong>.</p>",
      "<p>To access the Architect Terminal you must be a founder or admin.</p>",
      "<button onclick=\"location.href='" + LANDING_PAGE + "?action=create_org'\"",
      "  style='padding:.5rem 1.5rem;background:#00ff41;color:#000;",
      "  border:none;cursor:pointer;font-family:monospace;font-size:1rem'>",
      "  Create an Organization (become Founder)",
      "</button>",
      "<button onclick=\"location.href='" + LANDING_PAGE + "'\"",
      "  style='padding:.5rem 1.5rem;background:#333;color:#0f0;",
      "  border:none;cursor:pointer;font-family:monospace;font-size:1rem'>",
      "  Go to Landing Page",
      "</button>",
    ].join("");

    document.body.appendChild(overlay);
  }

  // ---------------------------------------------------------------------------
  // Redirect helpers
  // ---------------------------------------------------------------------------

  function redirectToSignup(reason) {
    const url =
      LANDING_PAGE +
      "?auth_required=1&reason=" +
      encodeURIComponent(reason || "not_authenticated");
    window.location.href = url;
  }

  // ---------------------------------------------------------------------------
  // Session token helpers (localStorage-based for alpha)
  // ---------------------------------------------------------------------------

  function _getSessionToken() {
    return localStorage.getItem("murphy_session_token") || "";
  }

  function _getUserId() {
    return localStorage.getItem("murphy_user_id") || "";
  }

  /** Called by the landing page after successful login to persist the session. */
  window.murphyAuth = {
    setSession: function (userId, token) {
      localStorage.setItem("murphy_user_id", userId);
      localStorage.setItem("murphy_session_token", token);
    },
    clearSession: function () {
      localStorage.removeItem("murphy_user_id");
      localStorage.removeItem("murphy_session_token");
    },
    getUserId: _getUserId,
    getToken: _getSessionToken,
  };

  // ---------------------------------------------------------------------------
  // OAuth success handler
  // ---------------------------------------------------------------------------

  /**
   * When the backend OAuth callback redirects here with ?oauth_success=1 it
   * sets a `murphy_session` HttpOnly cookie.  To make the Bearer-token header
   * available to subsequent API calls, we fetch the token from the server via
   * GET /api/auth/session-token (which validates the cookie server-side and
   * returns the token in the JSON body).  Direct cookie access is not possible
   * because `murphy_session` is flagged HttpOnly.
   *
   * The query params are removed from the URL after processing so a manual
   * refresh does not re-trigger the handler.
   *
   * @returns {Promise<void>}
   */
  async function _handleOAuthSuccess() {
    var params = new URLSearchParams(window.location.search);
    if (params.get("oauth_success") !== "1") return;

    // Strip the OAuth query params from the address bar without reloading
    // (done first so a failed fetch doesn't leave stale params).
    history.replaceState(null, "", window.location.pathname);

    // Persist the provider name so UI can show "Connected via Google" etc.
    var provider = params.get("provider") || "";
    if (provider) {
      localStorage.setItem("murphy_oauth_provider", provider);
    }

    // Ask the server to hand back the active session token (readable server-side
    // from the HttpOnly cookie) and mirror it to localStorage so that
    // MurphyAPI._buildHeaders() can include it as a Bearer token.
    try {
      var res = await fetch("/api/auth/session-token", { credentials: "include" });
      if (res.ok) {
        var data = await res.json();
        if (data && data.session_token) {
          localStorage.setItem("murphy_session_token", data.session_token);
        }
      }
    } catch (err) {
      // Silently ignore network errors — cookie-based auth still works for
      // server-rendered requests; only the Bearer-token path is affected.
    }
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  async function boot() {
    await _handleOAuthSuccess();

    const profile = await fetchProfile();

    if (!profile) {
      redirectToSignup("session_missing_or_expired");
      return;
    }

    if (!profile.email_validated) {
      redirectToSignup("email_not_validated");
      return;
    }

    if (!profile.eula_accepted) {
      redirectToSignup("eula_not_accepted");
      return;
    }

    // Expose profile globally
    window.MURPHY_PROFILE = profile;
    window.dispatchEvent(
      new CustomEvent("murphy:profile_loaded", { detail: profile })
    );

    // Check architect gate
    const isArchitectPage =
      document.body.dataset.terminal === "architect" ||
      window.location.pathname.includes("terminal_architect");
    if (isArchitectPage) {
      guardArchitectTerminal(profile);
    }

    // Apply terminal config
    const config = await fetchTerminalConfig();
    if (config) {
      applyTerminalConfig(config);
    } else if (profile.terminal_config) {
      applyTerminalConfig(profile.terminal_config);
    }
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
