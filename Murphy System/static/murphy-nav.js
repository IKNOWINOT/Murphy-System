/**
 * murphy-nav.js — Unified Department Navigation Bar
 * Murphy System © 2020 Inoni LLC / Corey Post / BSL 1.1
 *
 * Features:
 * - Sticky top bar with department dropdown menus
 * - ALL AI system pages included (Swarm, Chain, HITL, Org, CRM, etc.)
 * - Hide/Show toggle (persisted in localStorage)
 * - Active page highlighting
 * - Mobile hamburger fallback
 *
 * Usage: <script src="/static/murphy-nav.js"></script>
 */
(function () {
  "use strict";

  var STORAGE_KEY = "murphy_nav_hidden";

  var DEPARTMENTS = [
    {
      label: "AI Systems", icon: "🤖", href: "/ui/swarm-command",
      children: [
        { label: "🧠 Swarm Command",        href: "/ui/swarm-command" },
        { label: "🔗 Chain Center",          href: "/ui/chain-center" },
        { label: "🌐 Ambient Intelligence",  href: "/ui/ambient" },
        { label: "🌍 World Intelligence",    href: "/ui/world-intelligence" },
        { label: "⌨ Terminal",              href: "/ui/terminal" },
        { label: "🖥 Terminal Unified",     href: "/ui/terminal-unified" },
        { label: "🔭 System Visualizer",    href: "/ui/system-visualizer" },
        { label: "🛠 Self Healing",         href: "/ui/self-healing" },
        { label: "👁 Self Vision",          href: "/ui/self-vision" },
        { label: "📡 Dispatch",             href: "/ui/dispatch" },
        { label: "🎙 Meeting Intelligence", href: "/ui/meeting-intelligence" },
      ],
    },
    {
      label: "Org & People", icon: "🏢", href: "/ui/orgchart",
      children: [
        { label: "🗂 Org Chart",            href: "/ui/orgchart" },
        { label: "🏢 Org Portal",           href: "/ui/org-portal" },
        { label: "📢 All Hands",            href: "/ui/all-hands" },
        { label: "👁 Agent Monitor",        href: "/ui/agent-monitor" },
        { label: "📋 Management",           href: "/ui/management" },
        { label: "💼 Careers",              href: "/ui/careers" },
        { label: "🧙 Onboarding Wizard",    href: "/ui/onboarding" },
        { label: "🚦 Getting Started",      href: "/ui/getting-started" },
      ],
    },
    {
      label: "Operations", icon: "⚙", href: "/ui/dashboard",
      children: [
        { label: "📊 Dashboard",            href: "/ui/dashboard" },
        { label: "🏭 Ops Center",           href: "/ui/ops-center" },
        { label: "⏱ Automations",           href: "/ui/automations" },
        { label: "🤖 Workflows",            href: "/ui/workflows" },
        { label: "📋 Task Catalog",         href: "/ui/task-catalog" },
        { label: "📅 Calendar",             href: "/ui/calendar" },
        { label: "🏭 Production Wizard",    href: "/ui/production-wizard" },
        { label: "🖥 Workspace",            href: "/ui/workspace" },
      ],
    },
    {
      label: "Sales & CRM", icon: "💼", href: "/ui/crm",
      children: [
        { label: "📇 CRM",                  href: "/ui/crm" },
        { label: "✅ HITL Dashboard",       href: "/ui/hitl-dashboard" },
        { label: "📅 Book Audit",           href: "/book" },
        { label: "🏷 Pricing",             href: "/ui/pricing" },
        { label: "🤝 Partner Request",      href: "/ui/partner-request" },
        { label: "🎬 Demo",                 href: "/ui/demo" },
        { label: "📄 Resume",               href: "/ui/resume" },
        { label: "⚙ How We Work",          href: "/how-we-work" },
      ],
    },
    {
      label: "Finance", icon: "💰", href: "/ui/grant-wizard",
      children: [
        { label: "🎯 Grant Wizard",         href: "/ui/grant-wizard" },
        { label: "📊 Grant Dashboard",      href: "/ui/grant-dashboard" },
        { label: "📝 Grant Application",    href: "/ui/grant-application" },
        { label: "💰 Financing Options",    href: "/ui/financing-options" },
        { label: "💳 Wallet",               href: "/ui/wallet" },
        { label: "📅 ROI Calendar",         href: "/ui/roi-calendar" },
        { label: "📈 Paper Trading",        href: "/ui/paper-trading" },
        { label: "🧾 Terminal Costs",       href: "/ui/terminal-costs" },
      ],
    },
    {
      label: "Compliance", icon: "🛡", href: "/ui/compliance",
      children: [
        { label: "🛡 Compliance Dashboard", href: "/ui/compliance" },
        { label: "🔐 Security",             href: "/ui/security" },
        { label: "🔒 Security Ops",         href: "/ui/security-ops" },
        { label: "⚖ Legal",               href: "/ui/legal" },
        { label: "🔒 Privacy",              href: "/ui/privacy" },
        { label: "🛡 Admin Panel",          href: "/ui/admin" },
      ],
    },
    {
      label: "Build", icon: "🔨", href: "/ui/forge",
      children: [
        { label: "🔨 Forge",               href: "/ui/forge" },
        { label: "🎮 Game Studio",          href: "/ui/game-studio" },
        { label: "🏗 Terminal Architect",   href: "/ui/terminal-architect" },
        { label: "🎛 Orchestrator",         href: "/ui/terminal-orchestrator" },
        { label: "🔬 Research",             href: "/ui/research" },
        { label: "📡 Communication Hub",    href: "/ui/communication-hub" },
        { label: "🔢 Matrix Integration",   href: "/ui/matrix-integration" },
      ],
    },
    {
      label: "Settings", icon: "⚙", href: "/ui/management",
      children: [
        { label: "👤 Account Settings",     href: "/ui/management" },
        { label: "🔑 Change Password",      href: "/ui/change-password" },
        { label: "📖 Docs",                href: "/ui/docs" },
        { label: "💬 Community",            href: "/ui/community" },
        { label: "✍ Blog",                href: "/ui/blog" },
      ],
    },
  ];

  var PILOT = { email: "cpost@murphy.systems", name: "Corey Post" };

  function injectStyles() {
    if (document.getElementById("mnav-styles")) return;
    var s = document.createElement("style");
    s.id = "mnav-styles";
    s.textContent = [
      /* toggle button */
      "#mnav-toggle-btn{position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:2000;",
      "background:#111827;border:1px solid #1e2332;border-top:none;border-radius:0 0 8px 8px;",
      "color:#00D4AA;font-size:10px;font-family:Inter,sans-serif;font-weight:700;letter-spacing:.06em;",
      "padding:2px 14px 4px;cursor:pointer;transition:background .2s,color .2s;",
      "display:flex;align-items:center;gap:5px;white-space:nowrap;}",
      "#mnav-toggle-btn:hover{background:#1e2d3d;color:#fff;}",
      "#mnav-toggle-btn .mnav-arrow{font-size:9px;transition:transform .25s;}",
      /* nav bar */
      "#murphy-shared-nav{position:sticky;top:0;z-index:1500;",
      "background:rgba(10,10,15,.97);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);",
      "border-bottom:1px solid #1e2332;display:flex;align-items:center;",
      "padding:0 16px;gap:0;height:44px;font-family:Inter,system-ui,sans-serif;",
      "transition:margin-top .25s ease,opacity .25s ease;}",
      "#murphy-shared-nav.mnav-hidden{margin-top:-44px;opacity:0;pointer-events:none;}",
      /* brand */
      ".mn-brand{display:flex;align-items:center;gap:7px;color:#00D4AA;font-weight:800;",
      "font-size:.88rem;text-decoration:none;letter-spacing:.04em;flex-shrink:0;margin-right:8px;}",
      ".mn-brand-icon{width:24px;height:24px;background:#00D4AA;border-radius:6px;",
      "display:flex;align-items:center;justify-content:center;",
      "color:#0a0a0a;font-weight:900;font-size:13px;}",
      /* dept links */
      ".mn-links{display:flex;align-items:center;flex:1;overflow:hidden;}",
      ".mn-dept{position:relative;}",
      ".mn-dept-btn{display:flex;align-items:center;gap:4px;color:#9ba8b7;font-size:.78rem;",
      "font-weight:500;padding:0 10px;height:44px;cursor:pointer;border:none;background:transparent;",
      "white-space:nowrap;transition:color .15s,background .15s;font-family:inherit;text-decoration:none;}",
      ".mn-dept-btn:hover,.mn-dept:hover .mn-dept-btn,.mn-dept-btn.active{color:#00D4AA;background:rgba(0,212,170,.07);}",
      ".mn-caret{font-size:8px;opacity:.6;transition:transform .2s;}",
      ".mn-dept:hover .mn-caret{transform:rotate(180deg);opacity:1;}",
      /* dropdown */
      ".mn-dropdown{display:none;position:absolute;top:100%;left:0;min-width:220px;",
      "background:#0e1117;border:1px solid #1e2332;border-radius:0 0 10px 10px;padding:6px 0;",
      "z-index:1600;box-shadow:0 12px 32px rgba(0,0,0,.6);}",
      ".mn-dept:hover .mn-dropdown,.mn-dept:focus-within .mn-dropdown{display:block;}",
      ".mn-dropdown a{display:flex;align-items:center;gap:8px;padding:7px 16px;color:#9ba8b7;",
      "text-decoration:none;font-size:.79rem;white-space:nowrap;transition:color .15s,background .15s;}",
      ".mn-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.07);}",
      ".mn-dropdown a.active{color:#00D4AA;font-weight:600;}",
      ".mn-dept-heading{padding:5px 16px 3px;font-size:.68rem;font-weight:700;color:#00D4AA;",
      "letter-spacing:.09em;text-transform:uppercase;border-bottom:1px solid #1e2332;margin-bottom:3px;}",
      /* right */
      ".mn-right{display:flex;align-items:center;gap:6px;flex-shrink:0;margin-left:auto;padding-left:10px;}",
      /* user menu */
      ".mn-user{position:relative;}",
      ".mn-user-btn{display:flex;align-items:center;gap:6px;background:rgba(0,212,170,.08);",
      "border:1px solid rgba(0,212,170,.2);border-radius:20px;padding:4px 12px;color:#00D4AA;",
      "font-size:.75rem;font-weight:600;cursor:pointer;font-family:inherit;",
      "transition:background .2s,border-color .2s;white-space:nowrap;}",
      ".mn-user-btn:hover{background:rgba(0,212,170,.18);border-color:#00D4AA;}",
      ".mn-user-dropdown{display:none;position:absolute;right:0;top:calc(100% + 6px);min-width:230px;",
      "background:#0e1117;border:1px solid #1e2332;border-radius:10px;padding:6px 0;",
      "z-index:1600;box-shadow:0 12px 32px rgba(0,0,0,.6);}",
      ".mn-user:hover .mn-user-dropdown,.mn-user:focus-within .mn-user-dropdown{display:block;}",
      ".mn-user-info{padding:10px 16px;border-bottom:1px solid #1e2332;margin-bottom:4px;}",
      ".mn-uname{font-weight:700;color:#e6ecf2;font-size:.82rem;}",
      ".mn-uemail{color:#5a6474;font-size:.73rem;margin-top:2px;}",
      ".mn-user-dropdown a{display:flex;align-items:center;gap:8px;padding:7px 16px;",
      "color:#9ba8b7;text-decoration:none;font-size:.79rem;white-space:nowrap;",
      "transition:color .15s,background .15s;}",
      ".mn-user-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.07);}",
      ".mn-signout{color:#f87171!important;}",
      ".mn-signout:hover{background:rgba(248,113,113,.08)!important;}",
      /* live dot */
      ".mn-live-dot{width:7px;height:7px;border-radius:50%;background:#00D4AA;",
      "animation:mn-pulse 1.6s infinite;flex-shrink:0;}",
      "@keyframes mn-pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.4;transform:scale(.75);}}",
      /* hamburger */
      ".mn-hamburger{display:none;background:none;border:none;color:#9ba8b7;font-size:1.3rem;",
      "cursor:pointer;padding:4px 8px;}",
      /* mobile */
      "@media(max-width:768px){",
      ".mn-links{display:none;}",
      ".mn-hamburger{display:block;}",
      "#murphy-shared-nav.mn-mobile-open .mn-links{display:flex;flex-direction:column;",
      "align-items:flex-start;position:fixed;top:44px;left:0;right:0;background:#0e1117;",
      "border-bottom:1px solid #1e2332;padding:8px 0;z-index:1500;",
      "max-height:calc(100vh - 44px);overflow-y:auto;}",
      "#murphy-shared-nav.mn-mobile-open .mn-dept{width:100%;}",
      "#murphy-shared-nav.mn-mobile-open .mn-dept-btn{width:100%;height:40px;padding:0 20px;}",
      "#murphy-shared-nav.mn-mobile-open .mn-dropdown{display:block!important;position:static;",
      "box-shadow:none;border:none;border-top:1px solid #1e2332;background:#080b10;border-radius:0;}}",
    ].join("");
    document.head.appendChild(s);
  }

  function buildNav() {
    var currentPath = window.location.pathname;

    var deptLinks = DEPARTMENTS.map(function (dept) {
      var isActive = dept.children.some(function (c) { return c.href === currentPath; });
      var dropItems =
        '<div class="mn-dept-heading">' + dept.icon + " " + dept.label + "</div>" +
        dept.children.map(function (c) {
          return '<a href="' + c.href + '"' + (c.href === currentPath ? ' class="active"' : "") + ">" + c.label + "</a>";
        }).join("");
      return (
        '<div class="mn-dept">' +
        '<a class="mn-dept-btn' + (isActive ? " active" : "") + '" href="' + dept.href + '">' +
        "<span>" + dept.icon + "</span>" +
        "<span>" + dept.label + "</span>" +
        '<span class="mn-caret">▾</span>' +
        "</a>" +
        '<div class="mn-dropdown" role="menu">' + dropItems + "</div>" +
        "</div>"
      );
    }).join("");

    var userMenu =
      '<div class="mn-user">' +
      '<button class="mn-user-btn" aria-haspopup="true">' +
      '<span class="mn-live-dot"></span>' +
      "<span>" + PILOT.name + "</span>" +
      '<span style="opacity:.5;font-size:.7rem;">▾</span>' +
      "</button>" +
      '<div class="mn-user-dropdown" role="menu">' +
      '<div class="mn-user-info">' +
      '<div class="mn-uname">' + PILOT.name + "</div>" +
      '<div class="mn-uemail">' + PILOT.email + "</div>" +
      "</div>" +
      '<a href="/ui/management">⚙ Account Settings</a>' +
      '<a href="/ui/management#billing">💳 Billing</a>' +
      '<a href="/ui/wallet">💰 Wallet</a>' +
      '<a href="/ui/compliance">🛡 Compliance</a>' +
      '<a href="/ui/calendar">📅 Calendar</a>' +
      '<a href="/ui/orgchart">🗂 Org Chart</a>' +
      '<a href="/ui/change-password">🔑 Change Password</a>' +
      '<a href="/ui/login" class="mn-signout">↩ Sign Out</a>' +
      "</div></div>";

    return (
      '<nav id="murphy-shared-nav" role="navigation" aria-label="Murphy System navigation">' +
      '<a href="/ui/landing" class="mn-brand" aria-label="Murphy home">' +
      '<div class="mn-brand-icon">M</div>' +
      "<span>Murphy</span>" +
      "</a>" +
      '<div class="mn-links" role="menubar">' + deptLinks + "</div>" +
      '<div class="mn-right">' +
      '<button class="mn-hamburger" id="mnav-hamburger" aria-label="Toggle menu">☰</button>' +
      userMenu +
      "</div>" +
      "</nav>"
    );
  }

  function buildToggleBtn() {
    return (
      '<button id="mnav-toggle-btn" aria-label="Toggle navigation bar" title="Hide/show nav">' +
      '<span class="mnav-arrow">▲</span>' +
      '<span class="mnav-label">NAV</span>' +
      "</button>"
    );
  }

  function inject() {
    if (document.getElementById("murphy-shared-nav")) return;
    injectStyles();

    // Insert toggle button first (always visible at top)
    var tbWrap = document.createElement("div");
    tbWrap.innerHTML = buildToggleBtn();
    document.body.insertBefore(tbWrap.firstChild, document.body.firstChild);

    // Insert nav bar after toggle button
    var navWrap = document.createElement("div");
    navWrap.innerHTML = buildNav();
    var navEl = navWrap.firstChild;
    var toggleBtn = document.getElementById("mnav-toggle-btn");
    document.body.insertBefore(navEl, toggleBtn.nextSibling);

    // Restore persisted hidden state
    var isHidden = localStorage.getItem(STORAGE_KEY) === "1";
    if (isHidden) {
      navEl.classList.add("mnav-hidden");
      toggleBtn.querySelector(".mnav-arrow").style.transform = "rotate(180deg)";
    }

    // Toggle click handler
    toggleBtn.addEventListener("click", function () {
      var hidden = navEl.classList.toggle("mnav-hidden");
      toggleBtn.querySelector(".mnav-arrow").style.transform = hidden ? "rotate(180deg)" : "";
      localStorage.setItem(STORAGE_KEY, hidden ? "1" : "0");
    });

    // Mobile hamburger
    var hamburger = document.getElementById("mnav-hamburger");
    if (hamburger) {
      hamburger.addEventListener("click", function (e) {
        e.stopPropagation();
        navEl.classList.toggle("mn-mobile-open");
      });
      document.addEventListener("click", function (e) {
        if (!navEl.contains(e.target)) navEl.classList.remove("mn-mobile-open");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
