/**
 * murphy-nav.js — PATCH-154c
 * Unified nav: topbar shows parent groups, sidebar shows active group's children.
 * Clicking a topbar parent swaps the sidebar to that group.
 * Active group is inferred from the current URL on load.
 * © 2020 Inoni Limited Liability Company by Corey Post | BSL 1.1
 */
(function () {
  "use strict";

  // ── Global fetch interceptor — auto-adds Bearer token for /api/ calls ──────
  (function patchFetch() {
    var _origFetch = window.fetch.bind(window);
    window.fetch = function(url, opts) {
      opts = opts || {};
      var urlStr = (url && url.toString) ? url.toString() : String(url);
      // Only intercept internal /api/ calls
      if (urlStr.indexOf('/api/') !== -1) {
        var tok = localStorage.getItem('murphy_session_token');
        // Ensure token exists and is non-empty
        if (tok && tok.trim() !== '') {
          opts.headers = opts.headers || {};
          // Don't overwrite an existing Authorization header
          if (!opts.headers['Authorization'] && !opts.headers['authorization']) {
            opts.headers['Authorization'] = 'Bearer ' + tok;
          }
        }
        // Always send credentials for cookie fallback too
        if (!opts.credentials) opts.credentials = 'same-origin';
      }
      return _origFetch(url, opts);
    };
  })();


  // ---------------------------------------------------------------------------
  // Nav structure — parents in topbar, children in sidebar
  // ---------------------------------------------------------------------------
  var NAV = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "📊",
      href: "/ui/dashboard",
      children: [
        { icon: "📊", label: "Overview",             href: "/ui/dashboard" },
        { icon: "📅", label: "ROI Calendar",         href: "/ui/roi-calendar" },
        { icon: "🧠", label: "Ambient Intelligence", href: "/ui/ambient-intelligence" },
        { icon: "💬", label: "Matrix",               href: "/ui/matrix-integration" },
        { icon: "🗨️", label: "Chat",                 href: "/ui/matrix-chat" },
        { icon: "⚙️", label: "Management",           href: "/ui/management" },
        { icon: "🔧", label: "Admin Panel",          href: "/ui/admin-panel" },
      ],
    },
    {
      id: "automations",
      label: "Automations",
      icon: "⚡",
      href: "/ui/automations",
      children: [
        { icon: "⚡", label: "Automations",          href: "/ui/automations" },
        { icon: "🔀", label: "Workflow Canvas",      href: "/ui/workflow-canvas" },
        { icon: "🏗", label: "Production Wizard",    href: "/ui/production-wizard" },
        { icon: "📡", label: "Comm Hub",             href: "/ui/communication-hub" },
        { icon: "🎙", label: "Meetings",             href: "/ui/meeting-intelligence" },
        { icon: "🤖", label: "HITL Dashboard",       href: "/ui/hitl-dashboard" },
      ],
    },
    {
      id: "forge",
      label: "Forge",
      icon: "🔨",
      href: "/ui/forge",
      children: [
        { icon: "🔨", label: "Forge",               href: "/ui/forge" },
        { icon: "🧠", label: "Swarm Command",       href: "/ui/swarm-command" },
        { icon: "🌍", label: "World Intelligence",  href: "/ui/world-intelligence" },
        { icon: "🔧", label: "Self-Healing",        href: "/ui/self-healing" },
        { icon: "⏰", label: "Scheduler",           href: "/ui/scheduler" },
        { icon: "🔌", label: "Integrations",        href: "/ui/integrations" },
        { icon: "🎙", label: "Voice",               href: "/ui/voice" },
        { icon: "📚", label: "Teacher",             href: "/ui/teacher" },
        { icon: "🎮", label: "Game Studio",         href: "/ui/game-studio" },
        { icon: "🧬", label: "Dev Module",          href: "/ui/dev-module" },
        { icon: "📊", label: "Org Chart",           href: "/ui/orgchart" },
        { icon: "📖", label: "Docs",                href: "/ui/docs" },
      ],
    },
    {
      id: "workspace",
      label: "Workspace",
      icon: "🗂",
      href: "/ui/workspace",
      children: [
        { icon: "🗂", label: "Workspace",           href: "/ui/workspace" },
        { icon: "📄", label: "Workdocs",            href: "/ui/workdocs" },
        { icon: "📋", label: "Boards",              href: "/ui/boards" },
        { icon: "📆", label: "Calendar",            href: "/ui/calendar" },
        { icon: "👤", label: "CRM",                 href: "/ui/crm" },
        { icon: "⏱", label: "Time Tracking",       href: "/ui/time-tracking" },
      ],
    },
    {
      id: "finance",
      label: "Finance",
      icon: "💰",
      href: "/ui/wallet",
      children: [
        { icon: "💸", label: "Grants & Loans",     href: "/ui/financing-options" },
        { icon: "💰", label: "Wallet",             href: "/ui/wallet" },
        { icon: "📈", label: "Trading",            href: "/ui/trading-dashboard" },
        { icon: "📉", label: "Paper Trading",      href: "/ui/paper-trading-dashboard" },
        { icon: "🧪", label: "Backtester",         href: "/ui/backtester" },
        { icon: "⚠️", label: "Risk Dashboard",     href: "/ui/risk-dashboard" },
        { icon: "💼", label: "Portfolio",          href: "/ui/portfolio" },
        { icon: "🏷", label: "Pricing",            href: "/ui/pricing" },
      ],
    },
    {
      id: "compliance",
      label: "Compliance",
      icon: "🛡",
      href: "/ui/compliance-center",
      children: [
        { icon: "🛡", label: "Compliance",        href: "/ui/compliance-center" },
        { icon: "🔐", label: "Security Ops",       href: "/ui/security-ops" },
        { icon: "⚖️", label: "Legal",              href: "/ui/legal" },
        { icon: "🔒", label: "Privacy",            href: "/ui/privacy" },
      ],
    },
    {
      id: "people",
      label: "People",
      icon: "👥",
      href: "/ui/org-portal",
      children: [
        { icon: "👥", label: "Org Portal",        href: "/ui/org-portal" },
        { icon: "🧙", label: "Onboarding",        href: "/ui/onboarding-wizard" },
        { icon: "🌐", label: "Community",         href: "/ui/community-forum" },
        { icon: "🤝", label: "Partner Request",   href: "/ui/partner-request" },
        { icon: "🚪", label: "Guest Portal",      href: "/ui/guest-portal" },
        { icon: "💼", label: "Careers",           href: "/ui/careers" },
      ],
    },
    {
      id: "more",
      label: "More",
      icon: "…",
      href: "/ui/demo",
      children: [
        { icon: "🎯", label: "Demo",              href: "/ui/demo" },
        { icon: "📝", label: "Blog",              href: "/ui/blog" },
        { icon: "🏠", label: "Landing",           href: "/ui/murphy-landing-page" },
      ],
    },
  ];

  // ---------------------------------------------------------------------------
  // Resolve which group is active from the current URL
  // ---------------------------------------------------------------------------
  function resolveActiveGroup(path) {
    // Exact or prefix match on children first
    for (var i = 0; i < NAV.length; i++) {
      var g = NAV[i];
      if (g.children) {
        for (var j = 0; j < g.children.length; j++) {
          if (g.children[j].href === path) {
            return g.id;
          }
        }
      }
      if (g.href === path || path.indexOf(g.href + '/') === 0) {
        return g.id;
      }
    }
    return "dashboard"; // default fallback
  }    for (var j = 0; j < g.children.length; j++) {
        if (path === g.children[j].href) return g.id;
      }
    }
    // Prefix match on group root href
    for (var i = 0; i < NAV.length; i++) {
      if (path.indexOf(NAV[i].href) === 0) return NAV[i].id;
    }
    // Fallback: dashboard
    return "dashboard";
  }

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var currentPath   = window.location.pathname;
  var activeGroupId = resolveActiveGroup(currentPath);

  // ---------------------------------------------------------------------------
  // CSS — injected once into <head>
  // ---------------------------------------------------------------------------
  var CSS = [
    /* ── Reset ── */
    "#murphy-shared-nav*,#murphy-shared-sidebar*{box-sizing:border-box;}",

    /* ── Topbar ── */
    "#murphy-shared-nav{",
    "  position:sticky;top:0;z-index:1100;",
    "  background:rgba(10,10,10,.97);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);",
    "  border-bottom:1px solid rgba(0,212,170,.13);",
    "  display:flex;align-items:center;justify-content:space-between;",
    "  padding:0 1.5rem;gap:1rem;font-family:Inter,system-ui,sans-serif;",
    "  height:52px;",
    "}",

    /* Brand */
    ".mn-brand{display:flex;align-items:center;gap:.55rem;color:#00D4AA;font-weight:700;",
    "  font-size:1rem;text-decoration:none;letter-spacing:.03em;flex-shrink:0;}",
    ".mn-brand:hover{color:#00ffcc;text-decoration:none;}",

    /* Top-level group buttons */
    ".mn-links{display:flex;align-items:center;gap:2px;height:100%;}",
    ".mn-group-btn{",
    "  display:flex;align-items:center;gap:.28rem;",
    "  color:#8a9baa;background:transparent;border:none;",
    "  font-family:Inter,system-ui,sans-serif;font-size:.8rem;font-weight:500;",
    "  padding:0 .65rem;height:100%;cursor:pointer;",
    "  border-bottom:2px solid transparent;",
    "  transition:color .15s,border-color .15s;white-space:nowrap;",
    "}",
    ".mn-group-btn:hover{color:#c9d8e2;}",
    ".mn-group-btn.mn-active{color:#00D4AA;border-bottom-color:#00D4AA;}",

    /* Right side */
    ".mn-right{display:flex;align-items:center;gap:.7rem;flex-shrink:0;}",

    /* LIVE pill */
    ".mn-live-pill{display:inline-flex;align-items:center;gap:.35rem;",
    "  background:rgba(0,255,65,.06);border:1px solid rgba(0,255,65,.2);",
    "  border-radius:999px;padding:.2rem .7rem;",
    "  font-size:.68rem;font-family:'Courier New',monospace;color:#00ff41;}",
    ".mn-dot{width:6px;height:6px;background:#00ff41;border-radius:50%;flex-shrink:0;",
    "  animation:mnPulse 2s infinite;}",
    "@keyframes mnPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.5)}}",

    /* User menu */
    ".mn-user{position:relative;}",
    ".mn-user-btn{display:flex;align-items:center;gap:.4rem;",
    "  background:rgba(0,212,170,.09);border:1px solid rgba(0,212,170,.2);",
    "  border-radius:20px;padding:.26rem .75rem;color:#00D4AA;font-size:.78rem;",
    "  cursor:pointer;transition:all .15s;font-family:inherit;}",
    ".mn-user-btn:hover{background:rgba(0,212,170,.18);border-color:#00D4AA;}",
    ".mn-user-dropdown{display:none;position:absolute;right:0;top:calc(100% + 6px);",
    "  min-width:230px;background:#0f1520;border:1px solid rgba(0,212,170,.18);",
    "  border-radius:10px;padding:6px 0;z-index:1400;",
    "  box-shadow:0 12px 32px rgba(0,0,0,.7);animation:mnFade .12s ease;}",
    "@keyframes mnFade{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}",
    ".mn-user:hover .mn-user-dropdown,.mn-user:focus-within .mn-user-dropdown{display:block;}",
    ".mn-user-info{padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.07);}",
    ".mn-uname{font-weight:600;color:#e6ecf2;font-size:.82rem;margin-bottom:2px;}",
    ".mn-uemail{color:#566778;font-size:.74rem;}",
    ".mn-user-dropdown a{display:flex;align-items:center;gap:.4rem;padding:7px 16px;",
    "  color:#c9d1d9;text-decoration:none;font-size:.8rem;transition:color .15s,background .15s;}",
    ".mn-user-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.09);text-decoration:none;}",
    ".mn-ud-divider{height:1px;background:rgba(255,255,255,.07);margin:4px 0;}",
    ".mn-signout{color:#f87171!important;}",
    ".mn-signout:hover{color:#ff4f4f!important;background:rgba(248,113,113,.08)!important;}",

    /* ── Sidebar ── */
    "#murphy-shared-sidebar{",
    "  width:220px;flex-shrink:0;",
    "  background:#050a0f;",
    "  border-right:1px solid rgba(0,212,170,.1);",
    "  display:flex;flex-direction:column;overflow-y:auto;",
    "  padding:8px 8px 24px;",
    "  scrollbar-width:thin;scrollbar-color:rgba(0,212,170,.2) transparent;",
    "}",
    "#murphy-shared-sidebar::-webkit-scrollbar{width:4px;}",
    "#murphy-shared-sidebar::-webkit-scrollbar-thumb{background:rgba(0,212,170,.2);border-radius:4px;}",

    /* Sidebar group label */
    ".mns-group-label{",
    "  display:flex;align-items:center;gap:.4rem;",
    "  font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;",
    "  color:rgba(0,212,170,.6);padding:12px 10px 6px;",
    "}",

    /* Sidebar links */
    ".mns-link{",
    "  display:flex;align-items:center;gap:8px;",
    "  padding:7px 10px;border-radius:7px;",
    "  color:rgba(176,190,197,.75);font-size:.8rem;",
    "  text-decoration:none;transition:all .15s;margin-bottom:1px;white-space:nowrap;",
    "}",
    ".mns-link:hover{color:#e0e6ea;background:rgba(255,255,255,.05);text-decoration:none;}",
    ".mns-link.mns-active{color:#00D4AA;background:rgba(0,212,170,.1);}",
    ".mns-icon{font-size:.9rem;width:18px;text-align:center;flex-shrink:0;}",

    /* Sidebar footer */
    ".mns-footer{",
    "  padding:10px;margin-top:auto;",
    "  border-top:1px solid rgba(0,212,170,.1);",
    "  font-size:.74rem;color:rgba(0,212,170,.5);",
    "}",
    ".mns-footer-name{font-weight:600;color:rgba(0,212,170,.8);margin-bottom:2px;}",
    ".mns-footer a{display:block;margin-top:8px;color:#f87171;font-size:.72rem;text-decoration:none;}",
    ".mns-footer a:hover{color:#ff4f4f;}",

    /* Sidebar slide transition */
    "#mns-children{transition:opacity .15s;}",
    "#mns-children.mns-fade{opacity:0;}",

    /* Layout helpers */
    "html,body{height:100%;margin:0;padding:0;}",
    "body{display:flex;flex-direction:column;min-height:100vh;overflow-x:hidden;}",
    ".murphy-app-shell{display:flex;flex:1;min-height:0;overflow:visible;}",
    ".murphy-app-main{flex:1;overflow-y:auto;overflow-x:hidden;background:#0a0a0a;min-width:0;}",

    /* Mobile */
    /* Hamburger */
    ".mn-hamburger{display:none;flex-direction:column;justify-content:center;",
    "  gap:4px;background:transparent;border:none;cursor:pointer;padding:6px;}",
    ".mn-hamburger span{display:block;width:20px;height:2px;background:#00D4AA;",
    "  border-radius:2px;transition:all .2s;}",

    /* Mobile drawer overlay */
    "#mn-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1199;}",
    "#mn-overlay.mn-open{display:block;}",
    "#murphy-shared-sidebar.mn-open{display:flex!important;position:fixed;",
    "  top:52px;left:0;bottom:0;z-index:1200;box-shadow:4px 0 20px rgba(0,0,0,.6);}",

    "@media(max-width:768px){",
    "  .mn-links{display:none;}",
    "  #murphy-shared-sidebar{display:none!important;}",
    "  .mn-hamburger{display:flex;}",
    "  .murphy-app-shell{flex-direction:column;overflow:visible;}",
    "  .murphy-app-main{overflow-y:auto;-webkit-overflow-scrolling:touch;",
    "    min-height:0;flex:1;width:100%;max-width:100vw;}",
    "  body{overflow-y:auto;overflow-x:hidden;height:auto;min-height:100vh;}",
    "}",
  ].join("\n");

  // ---------------------------------------------------------------------------
  // Build the topbar HTML
  // ---------------------------------------------------------------------------
  function buildTopbar(user) {
    var groupBtns = NAV.map(function (g) {
      var isActive = g.id === activeGroupId;
      return (
        '<button class="mn-group-btn' + (isActive ? " mn-active" : "") + '" ' +
        'data-group="' + g.id + '" ' +
        'aria-label="' + g.label + '">' +
        '<span aria-hidden="true">' + g.icon + '</span> ' + g.label +
        '</button>'
      );
    }).join("");

    var userMenu = (
      '<div class="mn-user">' +
      '<button class="mn-user-btn">👤 ' + user.name + '</button>' +
      '<div class="mn-user-dropdown">' +
      '<div class="mn-user-info">' +
      '<div class="mn-uname">' + user.name + '</div>' +
      '<div class="mn-uemail">' + user.email + '</div>' +
      '</div>' +
      '<a href="/ui/management">⚙️ Settings</a>' +
      '<a href="/ui/management#billing">💳 Billing</a>' +
      '<a href="/ui/wallet">💰 Wallet</a>' +
      '<a href="/ui/compliance-dashboard">🛡 Compliance</a>' +
      '<a href="/ui/change-password">🔑 Change Password</a>' +
      '<div class="mn-ud-divider"></div>' +
      '<a href="/api/auth/logout" class="mn-signout">↩ Sign Out</a>' +
      '</div></div>'
    );

    return (
      '<nav id="murphy-shared-nav" role="navigation" aria-label="Murphy System navigation">' +
      '<a href="/ui/murphy-landing-page" class="mn-brand" aria-label="Murphy System home">' +
      '<svg width="26" height="26" viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="8" fill="#00D4AA"/>' +
      '<text x="16" y="22" text-anchor="middle" fill="#0a0a0a" font-size="18" font-weight="800" font-family="Inter,sans-serif">M</text></svg>' +
      'Murphy System</a>' +
      '<div class="mn-links">' + groupBtns + '</div>' +
      '<div class="mn-right">' +
      '<div class="mn-live-pill"><span class="mn-dot"></span>LIVE</div>' +
      userMenu +
      '<button class="mn-hamburger" id="mn-hamburger-btn" aria-label="Menu">' +
      '<span></span><span></span><span></span></button>' +
      '</div></nav>'
    );
  }

  // ---------------------------------------------------------------------------
  // Build sidebar children list for a given group ID
  // ---------------------------------------------------------------------------
  function buildSidebarChildren(groupId) {
    var group = null;
    for (var i = 0; i < NAV.length; i++) {
      if (NAV[i].id === groupId) { group = NAV[i]; break; }
    }
    if (!group) return "";

    var links = group.children.map(function (c) {
      var isActive = currentPath === c.href;
      return (
        '<a class="mns-link' + (isActive ? " mns-active" : "") + '" href="' + c.href + '">' +
        '<span class="mns-icon" aria-hidden="true">' + c.icon + '</span>' + c.label +
        '</a>'
      );
    }).join("");

    return (
      '<div class="mns-group-label">' +
      '<span aria-hidden="true">' + group.icon + '</span>' + group.label +
      '</div>' + links
    );
  }

  // ---------------------------------------------------------------------------
  // Build the full sidebar HTML
  // ---------------------------------------------------------------------------
  function buildSidebar(user) {
    return (
      '<div id="murphy-shared-sidebar" role="navigation" aria-label="Section navigation">' +
      '<div id="mns-children">' + buildSidebarChildren(activeGroupId) + '</div>' +
      '<div class="mns-footer">' +
      '<div class="mns-footer-name">' + user.name + '</div>' +
      '<div>' + user.email + '</div>' +
      '<a href="/api/auth/logout">↩ Sign Out</a>' +
      '</div>' +
      '</div>'
    );
  }

  // ---------------------------------------------------------------------------
  // Wire topbar button clicks → swap sidebar children
  // ---------------------------------------------------------------------------
  function wireTopbarButtons(navEl, sidebarEl) {
    navEl.querySelectorAll(".mn-group-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var groupId = btn.getAttribute("data-group");

        // Update active button
        navEl.querySelectorAll(".mn-group-btn").forEach(function (b) {
          b.classList.toggle("mn-active", b === btn);
        });

        // Swap sidebar children with a quick fade
        var childrenEl = sidebarEl.querySelector("#mns-children");
        if (!childrenEl) return;

        childrenEl.classList.add("mns-fade");
        setTimeout(function () {
          childrenEl.innerHTML = buildSidebarChildren(groupId);
          activeGroupId = groupId;
          childrenEl.classList.remove("mns-fade");
        }, 120);

        // Navigate to the group's root href
        var group = null;
        for (var i = 0; i < NAV.length; i++) {
          if (NAV[i].id === groupId) { group = NAV[i]; break; }
        }
        if (group) window.location.href = group.href;
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Inject CSS
  // ---------------------------------------------------------------------------
  function injectStyles() {
    if (document.getElementById("murphy-nav-css-154c")) return;
    var s = document.createElement("style");
    s.id = "murphy-nav-css-154c";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ---------------------------------------------------------------------------
  // User context
  // ---------------------------------------------------------------------------
  function getUser() {
    try {
      var ctx = window.__MURPHY_USER_CONTEXT__;
      if (ctx && ctx.email) return ctx;
    } catch (e) {}
    return { email: "cpost@murphy.systems", name: "Corey Post" };
  }

  // ---------------------------------------------------------------------------
  // Main injection
  // ---------------------------------------------------------------------------
  function boot() {
    // Skip nav on auth-only pages (login, signup, reset)
    var _authPages = ['/ui/login', '/ui/signup', '/ui/reset-password', '/ui/change-password'];
    var _path = window.location.pathname;
    if (_authPages.some(function(p){ return _path === p || _path.startsWith(p + '?'); })) return;

    // Idempotent
    if (document.getElementById("murphy-shared-nav")) return;

    injectStyles();

    var user = getUser();

    // ── Topbar ──
    var navWrap = document.createElement("div");
    navWrap.innerHTML = buildTopbar(user);
    var navEl = navWrap.firstChild;

    // Insert topbar before the shell (not before main inside shell)
    var shell = document.querySelector(".murphy-app-shell,.shell,.layout,.app-layout,.page-wrap");
    var main = document.querySelector("main");
    var insertTarget = shell || main;
    if (insertTarget && insertTarget.parentNode) {
      insertTarget.parentNode.insertBefore(navEl, insertTarget);
    } else {
      document.body.insertBefore(navEl, document.body.firstChild);
    }

    // ── Sidebar ──
    var sidebarEl = null;
    // Skip sidebar injection if page opts out (has its own sidebar)
    if (document.body.getAttribute('data-skip-nav-sidebar') !== 'true') {
      // Replace any existing #murphy-shared-sidebar with fresh one
      var existingSidebar = document.getElementById("murphy-shared-sidebar");
      var sbWrap = document.createElement("div");
      sbWrap.innerHTML = buildSidebar(user);
      sidebarEl = sbWrap.firstChild;

      if (existingSidebar) {
        existingSidebar.parentNode.replaceChild(sidebarEl, existingSidebar);
      } else {
        // Try to find the shell div to prepend into
        var shell = document.querySelector(
          ".murphy-app-shell,.shell,.layout,.app-layout,.page-wrap,.td-layout,.pt-layout"
        );
        if (shell) {
          shell.insertBefore(sidebarEl, shell.firstChild);
        }
        // If no shell found, sidebar stays out — nav.js topbar still works standalone
      }
    }

    // ── Wire interactions ──
    if (sidebarEl) { wireTopbarButtons(navEl, sidebarEl); }

    // ── Mobile hamburger + overlay ──
    var overlay = document.getElementById("mn-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "mn-overlay";
      document.body.appendChild(overlay);
    }
    var hbBtn = document.getElementById("mn-hamburger-btn");
    function closeMobileNav() {
      if (sidebarEl) sidebarEl.classList.remove("mn-open");
      overlay.classList.remove("mn-open");
    }
    if (hbBtn && sidebarEl) {
      hbBtn.addEventListener("click", function() {
        var open = sidebarEl.classList.toggle("mn-open");
        overlay.classList[open ? "add" : "remove"]("mn-open");
      });
      overlay.addEventListener("click", closeMobileNav);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

})();