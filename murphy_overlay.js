/**
 * murphy_overlay.js — Highlight Overlay & Right-Click Context Menu
 * Murphy System
 *
 * Renders shadow-agent automation suggestions as coloured text highlights
 * anywhere on the page.  Right-clicking a highlight shows a context menu:
 *   • "Ignore this suggestion"  → POST /api/overlay/suggestions/{id}/ignore
 *   • "Accept and automate"     → POST /api/overlay/suggestions/{id}/accept
 *   • "View similar in marketplace" → opens marketplace search
 *
 * The backend (OverlayManager) is the source of truth.  This script polls
 * for pending suggestions and renders them.  All state changes are persisted
 * server-side; the frontend is stateless beyond the DOM.
 *
 * Usage:
 *   <script src="/murphy_overlay.js"></script>
 *
 * Reads the API port from ?apiPort=, window.MURPHY_API_PORT, or 8000.
 *
 * Copyright © 2020 Inoni Limited Liability Company
 * License: BSL 1.1
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Config
  // ---------------------------------------------------------------------------

  const POLL_INTERVAL_MS = 5000;
  const OVERLAY_API_BASE = "/api/overlay";
  const MARKETPLACE_URL = "/ui/landing#marketplace";
  const HIGHLIGHT_COLORS = {
    automation: "rgba(0, 255, 65, 0.25)",
    api_call: "rgba(0, 200, 255, 0.25)",
    workflow: "rgba(255, 200, 0, 0.20)",
    documentation: "rgba(180, 100, 255, 0.20)",
    marketplace: "rgba(255, 140, 0, 0.25)",
  };

  function _apiPort() {
    const params = new URLSearchParams(window.location.search);
    if (params.has("apiPort")) return parseInt(params.get("apiPort"), 10);
    if (window.MURPHY_API_PORT) return window.MURPHY_API_PORT;
    return 8000;
  }

  function _baseUrl() {
    return "http://127.0.0.1:" + _apiPort();
  }

  function _token() {
    return (window.murphyAuth && window.murphyAuth.getToken()) ||
           localStorage.getItem("murphy_session_token") || "";
  }

  // ---------------------------------------------------------------------------
  // Internal state
  // ---------------------------------------------------------------------------

  const _rendered = new Map();  // suggestion_id → DOM span
  let _contextMenu = null;
  let _pollTimer = null;

  // ---------------------------------------------------------------------------
  // API helpers
  // ---------------------------------------------------------------------------

  async function _api(method, path, body) {
    const token = _token();
    const opts = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
    };
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(_baseUrl() + path, opts);
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  async function fetchPending() {
    return _api("GET", OVERLAY_API_BASE + "/suggestions?state=pending");
  }

  async function acceptSuggestion(id) {
    return _api("POST", OVERLAY_API_BASE + "/suggestions/" + id + "/accept");
  }

  async function ignoreSuggestion(id) {
    return _api("POST", OVERLAY_API_BASE + "/suggestions/" + id + "/ignore");
  }

  // ---------------------------------------------------------------------------
  // Inject global overlay stylesheet
  // ---------------------------------------------------------------------------

  function _injectStyles() {
    if (document.getElementById("murphy-overlay-styles")) return;
    const style = document.createElement("style");
    style.id = "murphy-overlay-styles";
    style.textContent = [
      ".murphy-highlight {",
      "  border-radius: 3px;",
      "  cursor: pointer;",
      "  position: relative;",
      "  transition: filter .15s ease;",
      "}",
      ".murphy-highlight:hover { filter: brightness(1.3); }",
      "#murphy-context-menu {",
      "  position: fixed;",
      "  background: #111;",
      "  border: 1px solid #00ff41;",
      "  color: #b0ffb0;",
      "  font-family: 'Courier New', monospace;",
      "  font-size: .85rem;",
      "  z-index: 99999;",
      "  min-width: 220px;",
      "  box-shadow: 0 4px 16px rgba(0,255,65,.2);",
      "  border-radius: 4px;",
      "  overflow: hidden;",
      "}",
      "#murphy-context-menu .murphy-cm-header {",
      "  background: #1a1a1a;",
      "  padding: .45rem .8rem;",
      "  color: #00ffff;",
      "  font-size: .78rem;",
      "  border-bottom: 1px solid #333;",
      "  white-space: nowrap;",
      "  overflow: hidden;",
      "  text-overflow: ellipsis;",
      "  max-width: 220px;",
      "}",
      "#murphy-context-menu button {",
      "  display: block;",
      "  width: 100%;",
      "  background: none;",
      "  border: none;",
      "  border-bottom: 1px solid #222;",
      "  color: #b0ffb0;",
      "  font-family: inherit;",
      "  font-size: .85rem;",
      "  padding: .5rem .8rem;",
      "  text-align: left;",
      "  cursor: pointer;",
      "}",
      "#murphy-context-menu button:hover { background: #1e3320; color: #00ff41; }",
      "#murphy-context-menu button.danger:hover { background: #331010; color: #ff4040; }",
    ].join("\n");
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------------------
  // Context menu
  // ---------------------------------------------------------------------------

  function _showContextMenu(x, y, suggestion) {
    _hideContextMenu();

    const menu = document.createElement("div");
    menu.id = "murphy-context-menu";
    _contextMenu = menu;

    const header = document.createElement("div");
    header.className = "murphy-cm-header";
    header.textContent = "💡 " + (suggestion.title || "Shadow Agent Suggestion");
    menu.appendChild(header);

    function _btn(label, className, onClick) {
      const btn = document.createElement("button");
      if (className) btn.className = className;
      btn.textContent = label;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        _hideContextMenu();
        onClick();
      });
      menu.appendChild(btn);
    }

    _btn("✅  Accept and automate", "", async function () {
      const result = await acceptSuggestion(suggestion.suggestion_id);
      if (result) {
        _removeHighlight(suggestion.suggestion_id);
        window.dispatchEvent(
          new CustomEvent("murphy:suggestion_accepted", { detail: suggestion })
        );
      }
    });

    _btn("🚫  Ignore this suggestion", "danger", async function () {
      const result = await ignoreSuggestion(suggestion.suggestion_id);
      if (result) {
        _removeHighlight(suggestion.suggestion_id);
      }
    });

    _btn("🔍  View similar in marketplace", "", function () {
      const search = encodeURIComponent(suggestion.title || "");
      window.open(MARKETPLACE_URL + "?q=" + search, "_blank");
    });

    document.body.appendChild(menu);

    // Position near cursor, keep inside viewport
    const vw = window.innerWidth, vh = window.innerHeight;
    const mw = 240, mh = 160;
    menu.style.left = Math.min(x + 4, vw - mw) + "px";
    menu.style.top = Math.min(y + 4, vh - mh) + "px";
  }

  function _hideContextMenu() {
    if (_contextMenu && _contextMenu.parentNode) {
      _contextMenu.parentNode.removeChild(_contextMenu);
    }
    _contextMenu = null;
  }

  // ---------------------------------------------------------------------------
  // Highlight rendering
  // ---------------------------------------------------------------------------

  /**
   * Wrap every occurrence of suggestion.highlighted_text in the document
   * body with a coloured <span> that carries the right-click handler.
   */
  function _renderHighlight(suggestion) {
    if (_rendered.has(suggestion.suggestion_id)) return;

    const text = suggestion.highlighted_text;
    if (!text) return;

    const color =
      HIGHLIGHT_COLORS[suggestion.category] || HIGHLIGHT_COLORS.automation;

    // Walk text nodes and wrap matches
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: function (node) {
          // Skip scripts, styles, the overlay menu itself
          const tag = node.parentElement && node.parentElement.tagName;
          if (["SCRIPT", "STYLE", "NOSCRIPT"].includes(tag)) {
            return NodeFilter.FILTER_REJECT;
          }
          if (
            node.parentElement &&
            node.parentElement.closest &&
            node.parentElement.closest("#murphy-context-menu")
          ) {
            return NodeFilter.FILTER_REJECT;
          }
          return node.textContent.includes(text)
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_SKIP;
        },
      }
    );

    const nodes = [];
    let node;
    while ((node = walker.nextNode())) nodes.push(node);

    nodes.forEach(function (textNode) {
      const idx = textNode.textContent.indexOf(text);
      if (idx === -1) return;

      const before = document.createTextNode(textNode.textContent.slice(0, idx));
      const after = document.createTextNode(
        textNode.textContent.slice(idx + text.length)
      );

      const span = document.createElement("span");
      span.className = "murphy-highlight";
      span.dataset.suggestionId = suggestion.suggestion_id;
      span.title =
        suggestion.description || "Shadow agent suggestion — right-click for options";
      span.style.background = color;
      span.textContent = text;

      span.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        _showContextMenu(e.clientX, e.clientY, suggestion);
      });

      const parent = textNode.parentNode;
      parent.insertBefore(before, textNode);
      parent.insertBefore(span, textNode);
      parent.insertBefore(after, textNode);
      parent.removeChild(textNode);
    });

    _rendered.set(suggestion.suggestion_id, true);
  }

  function _removeHighlight(suggestionId) {
    document.querySelectorAll(
      "[data-suggestion-id='" + suggestionId + "']"
    ).forEach(function (span) {
      const parent = span.parentNode;
      if (parent) {
        parent.replaceChild(
          document.createTextNode(span.textContent),
          span
        );
      }
    });
    _rendered.delete(suggestionId);
  }

  // ---------------------------------------------------------------------------
  // Poll loop
  // ---------------------------------------------------------------------------

  async function _poll() {
    const data = await fetchPending();
    if (!data) return;
    const suggestions = Array.isArray(data) ? data : data.suggestions || [];
    suggestions.forEach(_renderHighlight);
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  window.murphyOverlay = {
    /**
     * Add a suggestion locally (without a server round-trip).
     * Useful for alpha mode where the backend may not be running.
     */
    addLocal: function (suggestion) {
      _renderHighlight(suggestion);
    },

    /** Force an immediate poll instead of waiting for the timer. */
    refresh: function () {
      _poll();
    },

    /** Stop the poll loop (e.g. when navigating away). */
    stop: function () {
      if (_pollTimer) clearInterval(_pollTimer);
    },
  };

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  function _boot() {
    _injectStyles();

    // Dismiss context menu on any click outside it
    document.addEventListener("click", function (e) {
      if (_contextMenu && !_contextMenu.contains(e.target)) {
        _hideContextMenu();
      }
    });

    // Dismiss on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") _hideContextMenu();
    });

    // Start poll loop
    _poll();
    _pollTimer = setInterval(_poll, POLL_INTERVAL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _boot);
  } else {
    _boot();
  }
})();
