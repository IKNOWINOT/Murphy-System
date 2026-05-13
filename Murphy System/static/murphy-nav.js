/**
 * murphy-nav.js — PATCH-285
 * Department-based top nav with dropdowns. No nav on landing/login pages.
 * Topbar has department dropdowns. Sidebar shows active dept children.
 * © 2020 Inoni Limited Liability Company by Corey Post | BSL 1.1
 */
(function () {
  "use strict";

  // ── Auto-add Bearer token to all /api/ calls ─────────────────────────────
  (function patchFetch() {
    var _origFetch = window.fetch.bind(window);
    window.fetch = function(url, opts) {
      opts = opts || {};
      var urlStr = (url && url.toString) ? url.toString() : String(url);
      if (urlStr.indexOf('/api/') !== -1) {
        var tok = localStorage.getItem('murphy_session_token');
        if (tok && tok.trim() !== '') {
          opts.headers = opts.headers || {};
          if (!opts.headers['Authorization'] && !opts.headers['authorization']) {
            opts.headers['Authorization'] = 'Bearer ' + tok;
          }
        }
        if (!opts.credentials) opts.credentials = 'same-origin';
      }
      return _origFetch(url, opts);
    };
  })();

  // ── Pages that should NOT show nav (public/auth pages) ───────────────────
  var NO_NAV_PATHS = ['/', '/ui/login', '/ui/signup', '/ui/landing',
    '/ui/demo', '/book', '/how-we-work', '/resume', '/ui/reset-password',
    '/ui/change-password', '/shadow-marketplace'];
  var currentPath = window.location.pathname;
  for (var ni = 0; ni < NO_NAV_PATHS.length; ni++) {
    if (currentPath === NO_NAV_PATHS[ni] || currentPath === NO_NAV_PATHS[ni] + '/') return;
  }
  // Session check handled by profile fetch below (supports cookie + token)

  // ── Department Nav Structure ──────────────────────────────────────────────
  var NAV = [
    {
      id: "command",
      label: "Command",
      icon: "🧠",
      href: "/ui/dashboard",
      children: [
        { icon: "📊", label: "Dashboard",            href: "/ui/dashboard" },
        { icon: "🧠", label: "Swarm Command",        href: "/ui/swarm-command" },
        { icon: "🤖", label: "HITL Review",          href: "/ui/hitl-dashboard" },
        { icon: "💬", label: "Ambient Intelligence", href: "/ui/ambient-intelligence" },
        { icon: "📅", label: "ROI Calendar",         href: "/ui/roi-calendar" },
        { icon: "🔧", label: "Admin Panel",          href: "/ui/admin-panel" },
        { icon: "⚙️", label: "Management",           href: "/ui/management" },
      ],
    },
    {
      id: "sales",
      label: "Sales",
      icon: "💼",
      href: "/ui/crm",
      children: [
        { icon: "👤", label: "CRM",                  href: "/ui/crm" },
        { icon: "🎯", label: "AI Job Hunter",        href: "/ui/ai-job-hunter" },
        { icon: "📋", label: "Proposals",            href: "/ui/capital" },
        { icon: "📅", label: "Book a Meeting",       href: "/book" },
        { icon: "🌍", label: "Demo Center",          href: "/ui/demo" },
        { icon: "🏷", label: "Pricing",              href: "/ui/pricing" },
        { icon: "🤝", label: "Partner Request",      href: "/ui/partner-request" },
      ],
    },
    {
      id: "production",
      label: "Production",
      icon: "⚡",
      href: "/ui/automations",
      children: [
        { icon: "⚡", label: "Automations",          href: "/ui/automations" },
        { icon: "🔀", label: "Workflow Canvas",      href: "/ui/workflow-canvas" },
        { icon: "🏗", label: "Production Wizard",    href: "/ui/production-wizard" },
        { icon: "🔗", label: "Chain Center",         href: "/ui/chain-center" },
        { icon: "📡", label: "Comm Hub",             href: "/ui/communication-hub" },
        { icon: "🎙", label: "Meeting Intelligence", href: "/ui/meeting-intelligence" },
        { icon: "🔨", label: "Forge",                href: "/ui/forge" },
      ],
    },
    {
      id: "workspace",
      label: "Workspace",
      icon: "🗂",
      href: "/ui/workspace",
      children: [
        { icon: "🗂", label: "Workspace",            href: "/ui/workspace" },
        { icon: "📄", label: "Workdocs",             href: "/ui/workdocs" },
        { icon: "📋", label: "Boards",               href: "/ui/boards" },
        { icon: "📆", label: "Calendar",             href: "/ui/calendar" },
        { icon: "⏱", label: "Time Tracking",        href: "/ui/time-tracking" },
        { icon: "🌐", label: "Matrix Chat",          href: "/ui/matrix-chat" },
        { icon: "📖", label: "Docs",                 href: "/ui/docs" },
      ],
    },
    {
      id: "finance",
      label: "Finance",
      icon: "💰",
      href: "/ui/wallet",
      children: [
        { icon: "💰", label: "Wallet",               href: "/ui/wallet" },
        { icon: "💸", label: "Grants & Loans",       href: "/ui/financing" },
        { icon: "📈", label: "Trading",              href: "/ui/trading" },
        { icon: "⚠️", label: "Risk Dashboard",       href: "/ui/risk-dashboard" },
        { icon: "💼", label: "Portfolio",            href: "/ui/portfolio" },
        { icon: "📊", label: "Capital Proposals",    href: "/ui/capital" },
      ],
    },
    {
      id: "compliance",
      label: "Compliance",
      icon: "🛡",
      href: "/ui/compliance",
      children: [
        { icon: "🛡", label: "Compliance Center",    href: "/ui/compliance" },
        { icon: "🔐", label: "Security Scan",        href: "/ui/security-scan" },
        { icon: "🕵", label: "Honeypot",             href: "/ui/honeypot" },
        { icon: "⚖️", label: "Legal",               href: "/ui/legal" },
        { icon: "🔒", label: "Privacy",              href: "/ui/privacy" },
      ],
    },
    {
      id: "engineering",
      label: "Engineering",
      icon: "🔧",
      href: "/ui/dev-module",
      children: [
        { icon: "🔧", label: "Dev Module",           href: "/ui/dev-module" },
        { icon: "🧬", label: "Self-Healing",         href: "/ui/self-healing" },
        { icon: "📊", label: "Org Chart",            href: "/ui/orgchart" },
        { icon: "🎮", label: "Game Studio",          href: "/ui/game-studio" },
        { icon: "📚", label: "Teacher",              href: "/ui/teacher" },
        { icon: "🔌", label: "Integrations",         href: "/ui/integrations" },
        { icon: "🎙", label: "Voice",                href: "/ui/voice" },
      ],
    },
    {
      id: "people",
      label: "People",
      icon: "👥",
      href: "/ui/org-portal",
      children: [
        { icon: "👥", label: "Org Portal",           href: "/ui/org-portal" },
        { icon: "🧙", label: "Onboarding",           href: "/ui/onboarding-wizard" },
        { icon: "🌐", label: "Community",            href: "/ui/community" },
        { icon: "🚪", label: "Guest Portal",         href: "/ui/guest-portal" },
        { icon: "💼", label: "Careers",              href: "/ui/careers" },
        { icon: "🤖", label: "Shadow Marketplace",   href: "/shadow-marketplace" },
      ],
    },
  ];

  // ── Active group detection ────────────────────────────────────────────────
  function resolveActiveGroup(path) {
    for (var i = 0; i < NAV.length; i++) {
      var g = NAV[i];
      if (g.children) {
        for (var j = 0; j < g.children.length; j++) {
          if (g.children[j].href === path) return g.id;
        }
      }
      if (path.indexOf(g.href) === 0) return g.id;
    }
    return "command";
  }

  var activeGroupId = resolveActiveGroup(currentPath);

  // ── CSS ───────────────────────────────────────────────────────────────────
  var CSS = [
    "#murphy-shared-nav*,#murphy-shared-sidebar*{box-sizing:border-box;}",

    /* Topbar */
    "#murphy-shared-nav{position:sticky;top:0;z-index:1100;",
    "  background:rgba(8,10,16,.97);backdrop-filter:blur(14px);",
    "  border-bottom:1px solid rgba(0,212,170,.12);",
    "  display:flex;align-items:center;height:52px;padding:0 1.2rem;gap:.5rem;",
    "  font-family:Inter,system-ui,sans-serif;}",

    /* Brand */
    ".mn-brand{display:flex;align-items:center;gap:.5rem;color:#00D4AA;font-weight:800;",
    "  font-size:.95rem;text-decoration:none;letter-spacing:.04em;flex-shrink:0;margin-right:.5rem;}",
    ".mn-brand:hover{color:#00ffcc;text-decoration:none;}",

    /* Department buttons with dropdown */
    ".mn-links{display:flex;align-items:stretch;height:100%;flex:1;gap:0;}",
    ".mn-dept{position:relative;display:flex;align-items:center;}",
    ".mn-dept-btn{display:flex;align-items:center;gap:.25rem;",
    "  color:#8a9baa;background:transparent;border:none;border-bottom:2px solid transparent;",
    "  font-family:Inter,system-ui,sans-serif;font-size:.78rem;font-weight:500;",
    "  padding:0 .6rem;height:100%;cursor:pointer;white-space:nowrap;",
    "  transition:color .15s,border-color .15s;}",
    ".mn-dept-btn:hover{color:#c9d8e2;}",
    ".mn-dept-btn.mn-active{color:#00D4AA;border-bottom-color:#00D4AA;}",
    ".mn-caret{font-size:.6rem;opacity:.6;transition:transform .15s;}",
    ".mn-dept:hover .mn-caret{transform:rotate(180deg);}",

    /* Dropdown panel */
    ".mn-dropdown{display:none;position:absolute;top:100%;left:0;",
    "  min-width:200px;background:#0c1018;border:1px solid rgba(0,212,170,.18);",
    "  border-radius:10px;padding:6px 0;z-index:1400;",
    "  box-shadow:0 16px 40px rgba(0,0,0,.8);",
    "  animation:mnFade .12s ease;}",
    "@keyframes mnFade{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}",
    ".mn-dept:hover .mn-dropdown,.mn-dept:focus-within .mn-dropdown{display:block;}",
    ".mn-dd-item{display:flex;align-items:center;gap:.5rem;padding:7px 14px;",
    "  color:#b0bec5;text-decoration:none;font-size:.78rem;transition:all .15s;white-space:nowrap;}",
    ".mn-dd-item:hover{color:#00D4AA;background:rgba(0,212,170,.08);text-decoration:none;}",
    ".mn-dd-item.mn-dd-active{color:#00D4AA;background:rgba(0,212,170,.1);}",

    /* Right side */
    ".mn-right{display:flex;align-items:center;gap:.6rem;flex-shrink:0;margin-left:auto;}",

    /* Live pill */
    ".mn-live-pill{display:inline-flex;align-items:center;gap:.3rem;",
    "  background:rgba(0,255,65,.05);border:1px solid rgba(0,255,65,.18);",
    "  border-radius:999px;padding:.18rem .6rem;",
    "  font-size:.66rem;font-family:'Courier New',monospace;color:#00ff41;}",
    ".mn-dot{width:6px;height:6px;background:#00ff41;border-radius:50%;",
    "  animation:mnPulse 2s infinite;}",
    "@keyframes mnPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.5)}}",

    /* User menu */
    ".mn-user{position:relative;}",
    ".mn-user-btn{display:flex;align-items:center;gap:.4rem;",
    "  background:rgba(0,212,170,.09);border:1px solid rgba(0,212,170,.2);",
    "  border-radius:20px;padding:.24rem .7rem;color:#00D4AA;font-size:.76rem;",
    "  cursor:pointer;transition:all .15s;font-family:inherit;}",
    ".mn-user-btn:hover{background:rgba(0,212,170,.18);border-color:#00D4AA;}",
    ".mn-user-dropdown{display:none;position:absolute;right:0;top:calc(100% + 6px);",
    "  min-width:210px;background:#0c1018;border:1px solid rgba(0,212,170,.18);",
    "  border-radius:10px;padding:6px 0;z-index:1500;",
    "  box-shadow:0 12px 32px rgba(0,0,0,.8);}",
    ".mn-user:hover .mn-user-dropdown,.mn-user:focus-within .mn-user-dropdown{display:block;}",
    ".mn-user-info{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.07);}",
    ".mn-uname{font-weight:600;color:#e6ecf2;font-size:.8rem;margin-bottom:2px;}",
    ".mn-uemail{color:#566778;font-size:.72rem;}",
    ".mn-user-dropdown a{display:flex;align-items:center;gap:.4rem;padding:7px 14px;",
    "  color:#c9d1d9;text-decoration:none;font-size:.78rem;transition:all .15s;}",
    ".mn-user-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.09);text-decoration:none;}",
    ".mn-ud-divider{height:1px;background:rgba(255,255,255,.07);margin:4px 0;}",
    ".mn-signout{color:#f87171!important;}",
    ".mn-signout:hover{color:#ff4f4f!important;background:rgba(248,113,113,.08)!important;}",

    /* Layout */
    "html,body{height:100%;margin:0;padding:0;}",
    "body{display:flex;flex-direction:column;min-height:100vh;overflow-x:hidden;}",
    ".murphy-app-shell{display:flex;flex:1;min-height:0;}",
    ".murphy-app-main{flex:1;overflow-y:auto;background:#080a10;min-width:0;}",

    /* Mobile */
    ".mn-hamburger{display:none;flex-direction:column;justify-content:center;",
    "  gap:4px;background:transparent;border:none;cursor:pointer;padding:6px;}",
    ".mn-hamburger span{display:block;width:20px;height:2px;background:#00D4AA;border-radius:2px;}",
    "#mn-mobile-drawer{display:none;position:fixed;top:52px;left:0;right:0;bottom:0;",
    "  background:#080a10;z-index:1200;overflow-y:auto;padding:12px;}",
    "#mn-mobile-drawer.mn-open{display:block;}",
    "#mn-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1199;}",
    "#mn-overlay.mn-open{display:block;}",
    ".mn-mobile-section{margin-bottom:16px;}",
    ".mn-mobile-dept{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;",
    "  color:rgba(0,212,170,.6);padding:8px 4px 4px;}",
    ".mn-mobile-link{display:flex;align-items:center;gap:8px;padding:8px 10px;",
    "  color:#b0bec5;text-decoration:none;font-size:.82rem;border-radius:7px;}",
    ".mn-mobile-link:hover{color:#00D4AA;background:rgba(0,212,170,.08);}",

    "@media(max-width:768px){",
    "  .mn-links{display:none!important;}",
    "  .mn-live-pill{display:none;}",
    "  .mn-hamburger{display:flex;}",
    "  .murphy-app-shell{flex-direction:column;}",
    "  .murphy-app-main{min-height:calc(100vh - 52px);}",
    "}",
  ].join("\n");

  // ── Build topbar HTML ─────────────────────────────────────────────────────
  function buildTopbar(user) {
    var deptBtns = NAV.map(function(g) {
      var isActive = g.id === activeGroupId;
      var items = (g.children || []).map(function(c) {
        var isCurr = c.href === currentPath;
        return '<a class="mn-dd-item' + (isCurr ? ' mn-dd-active' : '') + '" href="' + c.href + '">' +
          '<span>' + c.icon + '</span>' + c.label + '</a>';
      }).join('');
      return '<div class="mn-dept">' +
        '<button class="mn-dept-btn' + (isActive ? ' mn-active' : '') + '" data-group="' + g.id + '">' +
        g.icon + ' ' + g.label + ' <span class="mn-caret">▾</span>' +
        '</button>' +
        '<div class="mn-dropdown">' + items + '</div>' +
        '</div>';
    }).join('');

    var uname = (user && (user.full_name || user.email)) ? (user.full_name || user.email.split('@')[0]) : 'User';
    var uemail = (user && user.email) ? user.email : '';
    var role   = (user && user.role) ? user.role : 'user';

    return '<nav id="murphy-shared-nav">' +
      '<a class="mn-brand" href="/ui/dashboard">☠ Murphy</a>' +
      '<div class="mn-links">' + deptBtns + '</div>' +
      '<div class="mn-right">' +
        '<span class="mn-live-pill"><span class="mn-dot"></span>LIVE</span>' +
        '<div class="mn-user">' +
          '<button class="mn-user-btn">👤 ' + uname + ' ▾</button>' +
          '<div class="mn-user-dropdown">' +
            '<div class="mn-user-info"><div class="mn-uname">' + uname + '</div>' +
            '<div class="mn-uemail">' + uemail + ' · ' + role + '</div></div>' +
            '<a href="/ui/dashboard">📊 Dashboard</a>' +
            '<a href="/ui/management">⚙️ Settings</a>' +
            '<a href="/resume">📄 Murphy Resume</a>' +
            '<div class="mn-ud-divider"></div>' +
            '<a href="#" class="mn-signout" id="mn-signout-btn">🚪 Sign Out</a>' +
          '</div>' +
        '</div>' +
        '<button class="mn-hamburger" id="mn-hamburger" aria-label="Menu">' +
          '<span></span><span></span><span></span>' +
        '</button>' +
      '</div>' +
    '</nav>';
  }

  // ── Build mobile drawer ───────────────────────────────────────────────────
  function buildMobileDrawer() {
    var sections = NAV.map(function(g) {
      var links = (g.children || []).map(function(c) {
        return '<a class="mn-mobile-link" href="' + c.href + '">' + c.icon + ' ' + c.label + '</a>';
      }).join('');
      return '<div class="mn-mobile-section"><div class="mn-mobile-dept">' + g.icon + ' ' + g.label + '</div>' + links + '</div>';
    }).join('');
    return '<div id="mn-mobile-drawer">' + sections + '</div><div id="mn-overlay"></div>';
  }

  // ── Inject everything ─────────────────────────────────────────────────────
  function inject(user) {
    // CSS
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    // Topbar — insert before body content
    var navEl = document.createElement('div');
    navEl.innerHTML = buildTopbar(user);
    document.body.insertBefore(navEl.firstChild, document.body.firstChild);

    // Mobile drawer
    var drawerEl = document.createElement('div');
    drawerEl.innerHTML = buildMobileDrawer();
    while (drawerEl.firstChild) document.body.appendChild(drawerEl.firstChild);

    // Wrap main content in app shell if not already wrapped
    if (!document.querySelector('.murphy-app-shell')) {
      var shell = document.createElement('div');
      shell.className = 'murphy-app-shell';
      var main = document.createElement('div');
      main.className = 'murphy-app-main';
      // Move all body children (except nav and drawers) into shell > main
      var children = Array.from(document.body.children);
      var skip = ['murphy-shared-nav', 'mn-mobile-drawer', 'mn-overlay'];
      children.forEach(function(el) {
        if (!skip.some(function(id) { return el.id === id; })) {
          main.appendChild(el);
        }
      });
      shell.appendChild(main);
      document.body.appendChild(shell);
    }

    // Event: sign out
    var soBtn = document.getElementById('mn-signout-btn');
    if (soBtn) soBtn.addEventListener('click', function(e) {
      e.preventDefault();
      localStorage.removeItem('murphy_session_token');
      localStorage.removeItem('murphy_user');
      window.location.href = '/ui/login';
    });

    // Event: hamburger
    var hb = document.getElementById('mn-hamburger');
    var drawer = document.getElementById('mn-mobile-drawer');
    var overlay = document.getElementById('mn-overlay');
    if (hb && drawer) {
      hb.addEventListener('click', function() {
        var open = drawer.classList.contains('mn-open');
        drawer.classList.toggle('mn-open', !open);
        overlay.classList.toggle('mn-open', !open);
      });
      overlay.addEventListener('click', function() {
        drawer.classList.remove('mn-open');
        overlay.classList.remove('mn-open');
      });
    }
  }

  // ── Load user + inject — supports localStorage token OR browser session cookie ──
  var token = localStorage.getItem('murphy_session_token');
  fetch('/api/account/profile', {
    credentials: 'include',
    headers: token ? {'Authorization': 'Bearer ' + token} : {}
  })
  .then(function(r) {
    if (r.status === 401 || r.status === 403) return null; // not authed — no nav
    return r.ok ? r.json() : {};
  })
  .then(function(data) {
    if (data === null) return;
    inject(data || {});
  })
  .catch(function() { inject({}); });

})();
