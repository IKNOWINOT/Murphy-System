/**
 * murphy_auth.js — Compatibility shim for PATCH-162
 * Redirects to the canonical murphy-auth-guard.js
 * Pages still referencing "murphy_auth.js" (relative path) are served this file
 * via the /static/ route once they are corrected.
 * This shim re-exports MurphyAuth so existing page code works unchanged.
 */
/* Load canonical auth guard synchronously */
(function() {
  var s = document.createElement('script');
  s.src = '/static/murphy-auth-guard.js';
  s.async = false;
  document.head.appendChild(s);
})();
