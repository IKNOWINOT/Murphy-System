/**
 * murphy-nav.js — Shared Navigation Component for the Murphy System
 *
 * Include this script in any Murphy HTML page to render a consistent
 * top-level navigation bar with category dropdowns. The nav ensures the
 * grant / financing system is always visible and displays the pilot
 * account (cpost@murphy.systems / Corey Post) as the logged-in user.
 *
 * Usage (add before </body>):
 *   <script src="/static/murphy-nav.js"></script>
 *
 * The script auto-inserts the nav before the first <main> or <body>
 * child. If a <nav class="murphy-topbar"> already exists it is left
 * in place (idempotent).
 */
(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Nav structure — mirrors src/nav_registry.py
  // ---------------------------------------------------------------------------
  var NAV_STRUCTURE = [
    {
      label: "Home",
      href: "/ui/landing",
      icon: "🏠",
    },
    {
      label: "Terminal",
      href: "/ui/terminal-unified",
      icon: "⌨",
    },
    {
      label: "Dashboard",
      href: "/ui/dashboard",
      icon: "📊",
    },
    {
      label: "Automations",
      href: "/ui/automations",
      icon: "⏱",
      children: [
        { label: "Workflows", href: "/ui/workflows" },
        { label: "Dispatch", href: "/ui/dispatch" },
        { label: "Communication Hub", href: "/ui/communication-hub" },
        { label: "Agent Monitor", href: "/ui/agent-monitor" },
        { label: "Admin Panel", href: "/ui/admin" },
      ],
    },
    {
      label: "Finance",
      href: "/ui/grant-wizard",
      icon: "💰",
      children: [
        { label: "Grant Wizard", href: "/ui/grant-wizard" },
        { label: "Grant Dashboard", href: "/ui/grant-dashboard" },
        { label: "Grant Application", href: "/ui/grant-application" },
        { label: "Financing Options", href: "/ui/financing-options" },
        { label: "Wallet", href: "/ui/wallet" },
        { label: "Pricing", href: "/ui/pricing" },
      ],
    },
    {
      label: "Compliance",
      href: "/ui/compliance",
      icon: "🛡",
      children: [
        { label: "Compliance Dashboard", href: "/ui/compliance" },
        { label: "Legal", href: "/ui/legal" },
        { label: "Privacy", href: "/ui/privacy" },
      ],
    },
    {
      label: "Onboarding",
      href: "/ui/onboarding",
      icon: "🧙",
      children: [
        { label: "Onboarding Wizard", href: "/ui/onboarding" },
        { label: "Demo", href: "/ui/demo" },
        { label: "Docs", href: "/ui/docs" },
        { label: "Community", href: "/ui/community" },
      ],
    },
    {
      label: "Settings",
      href: "/ui/management",
      icon: "⚙",
      children: [
        { label: "Account Settings", href: "/ui/management" },
        { label: "Change Password", href: "/ui/change-password" },
        { label: "Calendar", href: "/ui/calendar" },
        { label: "Org Portal", href: "/ui/org-portal" },
      ],
    },
  ];

  // ---------------------------------------------------------------------------
  // Pilot account display
  // ---------------------------------------------------------------------------
  var PILOT = {
    email: "cpost@murphy.systems",
    name: "Corey Post",
  };

  // ---------------------------------------------------------------------------
  // Build CSS (injected once)
  // ---------------------------------------------------------------------------
  function injectStyles() {
    if (document.getElementById("murphy-nav-styles")) return;
    var style = document.createElement("style");
    style.id = "murphy-nav-styles";
    style.textContent = [
      ".murphy-shared-topbar{position:sticky;top:0;z-index:1100;background:rgba(10,10,10,.95);",
      "backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);",
      "border-bottom:1px solid #1e2332;display:flex;align-items:center;",
      "justify-content:space-between;padding:.6rem 1.5rem;gap:1rem;font-family:Inter,sans-serif;}",
      ".murphy-shared-topbar .mn-brand{display:flex;align-items:center;gap:.5rem;",
      "color:#00D4AA;font-weight:700;font-size:1rem;text-decoration:none;}",
      ".murphy-shared-topbar .mn-brand svg{flex-shrink:0;}",
      ".murphy-shared-topbar .mn-links{display:flex;align-items:center;gap:.15rem;flex-wrap:wrap;}",
      ".murphy-shared-topbar .mn-item{position:relative;}",
      ".murphy-shared-topbar .mn-link{display:flex;align-items:center;gap:.3rem;color:#c9d1d9;",
      "text-decoration:none;font-size:.82rem;padding:.35rem .65rem;border-radius:6px;",
      "white-space:nowrap;transition:color .2s,background .2s;cursor:pointer;border:none;",
      "background:transparent;}",
      ".murphy-shared-topbar .mn-link:hover,.murphy-shared-topbar .mn-link.active",
      "{color:#00D4AA;background:rgba(0,212,170,.08);}",
      ".murphy-shared-topbar .mn-dropdown{display:none;position:absolute;top:calc(100% + 4px);left:0;",
      "min-width:200px;background:#111827;border:1px solid #1e2332;border-radius:8px;",
      "padding:4px 0;z-index:1200;box-shadow:0 8px 24px rgba(0,0,0,.5);}",
      ".murphy-shared-topbar .mn-item:hover .mn-dropdown,.murphy-shared-topbar .mn-item:focus-within .mn-dropdown",
      "{display:block;}",
      ".murphy-shared-topbar .mn-dropdown a{display:block;padding:7px 14px;color:#c9d1d9;",
      "text-decoration:none;font-size:.8rem;white-space:nowrap;transition:color .2s,background .2s;}",
      ".murphy-shared-topbar .mn-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.08);}",
      ".murphy-shared-topbar .mn-right{display:flex;align-items:center;gap:.5rem;flex-shrink:0;}",
      ".murphy-shared-topbar .mn-user{position:relative;}",
      ".murphy-shared-topbar .mn-user-btn{display:flex;align-items:center;gap:.4rem;",
      "background:rgba(0,212,170,.1);border:1px solid rgba(0,212,170,.2);border-radius:20px;",
      "padding:.3rem .8rem;color:#00D4AA;font-size:.78rem;cursor:pointer;",
      "transition:background .2s,border-color .2s;}",
      ".murphy-shared-topbar .mn-user-btn:hover{background:rgba(0,212,170,.18);border-color:#00D4AA;}",
      ".murphy-shared-topbar .mn-user-dropdown{display:none;position:absolute;right:0;",
      "top:calc(100% + 6px);min-width:220px;background:#111827;border:1px solid #1e2332;",
      "border-radius:8px;padding:8px 0;z-index:1200;box-shadow:0 8px 24px rgba(0,0,0,.5);}",
      ".murphy-shared-topbar .mn-user:hover .mn-user-dropdown,.murphy-shared-topbar .mn-user:focus-within .mn-user-dropdown",
      "{display:block;}",
      ".murphy-shared-topbar .mn-user-info{padding:10px 14px;border-bottom:1px solid #1e2332;font-size:.78rem;}",
      ".murphy-shared-topbar .mn-user-info .mn-uname{font-weight:600;color:#e6ecf2;margin-bottom:2px;}",
      ".murphy-shared-topbar .mn-user-info .mn-uemail{color:#8892a0;}",
      ".murphy-shared-topbar .mn-user-dropdown a{display:block;padding:7px 14px;color:#c9d1d9;",
      "text-decoration:none;font-size:.8rem;transition:color .2s,background .2s;}",
      ".murphy-shared-topbar .mn-user-dropdown a:hover{color:#00D4AA;background:rgba(0,212,170,.08);}",
      ".murphy-shared-topbar .mn-user-dropdown .mn-signout{color:#F87171 !important;}",
      "@media(max-width:700px){.murphy-shared-topbar .mn-links{display:none;}",
      ".murphy-shared-topbar.mn-open .mn-links{display:flex;flex-direction:column;",
      "position:absolute;top:100%;left:0;right:0;background:#0a0a0a;border-bottom:1px solid #1e2332;",
      "padding:1rem;gap:.25rem;z-index:1100;}}",
    ].join("");
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------------------
  // Build HTML
  // ---------------------------------------------------------------------------
  function buildNav() {
    var links = NAV_STRUCTURE.map(function (item) {
      if (!item.children || item.children.length === 0) {
        return (
          '<div class="mn-item">' +
          '<a class="mn-link" href="' + item.href + '">' +
          '<span aria-hidden="true">' + item.icon + '</span> ' + item.label +
          '</a></div>'
        );
      }
      var dropItems = item.children.map(function (c) {
        return '<a href="' + c.href + '">' + c.label + '</a>';
      }).join("");
      return (
        '<div class="mn-item">' +
        '<a class="mn-link" href="' + item.href + '" aria-haspopup="true">' +
        '<span aria-hidden="true">' + item.icon + '</span> ' + item.label + ' ▾' +
        '</a>' +
        '<div class="mn-dropdown" role="menu">' + dropItems + '</div>' +
        '</div>'
      );
    }).join("");

    var userMenu = (
      '<div class="mn-user">' +
      '<button class="mn-user-btn" aria-haspopup="true" aria-expanded="false">' +
      '<span aria-hidden="true">👤</span> ' + PILOT.name +
      '</button>' +
      '<div class="mn-user-dropdown" role="menu">' +
      '<div class="mn-user-info">' +
      '<div class="mn-uname">' + PILOT.name + '</div>' +
      '<div class="mn-uemail">' + PILOT.email + '</div>' +
      '</div>' +
      '<a href="/ui/management">⚙ Account Settings</a>' +
      '<a href="/ui/management#billing">💳 Billing</a>' +
      '<a href="/ui/wallet">💰 Wallet</a>' +
      '<a href="/ui/compliance">🛡 Compliance</a>' +
      '<a href="/ui/calendar">📅 Calendar</a>' +
      '<a href="/ui/change-password">🔑 Change Password</a>' +
      '<a href="/ui/login" class="mn-signout">↩ Sign Out</a>' +
      '</div></div>'
    );

    return (
      '<nav class="murphy-shared-topbar" role="navigation" aria-label="Murphy System navigation" id="murphy-shared-nav">' +
      '<a href="/ui/landing" class="mn-brand" aria-label="Murphy System home">' +
      '<svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">' +
      '<rect width="32" height="32" rx="8" fill="#00D4AA"/>' +
      '<text x="16" y="22" text-anchor="middle" fill="#0a0a0a" font-size="18" font-weight="800" font-family="Inter,sans-serif">M</text>' +
      '</svg>' +
      '<span>Murphy System</span>' +
      '</a>' +
      '<div class="mn-links" role="menubar">' + links + '</div>' +
      '<div class="mn-right">' + userMenu + '</div>' +
      '</nav>'
    );
  }

  // ---------------------------------------------------------------------------
  // Inject nav into the page
  // ---------------------------------------------------------------------------
  function inject() {
    // Idempotent — skip if already present
    if (document.getElementById("murphy-shared-nav")) return;

    injectStyles();

    var nav = document.createElement("div");
    nav.innerHTML = buildNav();
    var navEl = nav.firstChild;

    // Insert before <main> or as first child of <body>
    var main = document.querySelector("main");
    if (main && main.parentNode) {
      main.parentNode.insertBefore(navEl, main);
    } else {
      document.body.insertBefore(navEl, document.body.firstChild);
    }

    // Mark current page link as active
    var currentPath = window.location.pathname;
    var allLinks = navEl.querySelectorAll("a.mn-link");
    allLinks.forEach(function (a) {
      if (a.getAttribute("href") === currentPath) {
        a.classList.add("active");
      }
    });
  }

  // Run after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
