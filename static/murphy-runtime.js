/**
 * murphy-runtime.js — Compatibility shim for PATCH-162
 * Loads the canonical auth guard + session context.
 */
(function() {
  function loadScript(src) {
    var s = document.createElement('script');
    s.src = src;
    s.async = false;
    document.head.appendChild(s);
  }
  loadScript('/static/murphy-auth-guard.js');
  loadScript('/static/murphy-session-context.js');
})();
