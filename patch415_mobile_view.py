#!/usr/bin/env python3
"""
PATCH-415 — Mobile + tablet view for Murphy OS
================================================

WHAT THIS IS:
  Responsive CSS layer for /static/murphy-os.html. Adds proper mobile (≤640px)
  and tablet (641-960px) layouts on top of the existing desktop UI.

WHY IT EXISTS:
  Phase 1 (PATCH-413) shipped a beautiful 3-column desktop OS. Mobile users
  currently get a broken layout: sidebar hidden but no replacement, topbar
  nav buttons overflow, world strip wraps ugly, drill panel covers content.
  Murphy is supposed to be operable everywhere — phone, tablet, desktop.

HOW IT FITS:
  Single CSS injection before the final </style> tag. No JS changes needed
  except a small mobile-menu toggle.

KEY BREAKPOINTS:
  - ≤640px (phone): single column, hamburger menu, full-width drill, FAB
  - 641-960px (tablet): main + collapsible sidebar, drill still slides over
  - >960px (desktop): unchanged — current layout preserved

KEY UX DECISIONS:
  - On phone: tabs in topbar become a horizontal scrollable strip
  - World strip wraps to 2 lines on phone (still scannable)
  - Sidebar becomes a slide-in drawer triggered by hamburger ☰
  - Drill panel takes full screen on phone (was a side drawer)
  - Ask Murphy bar stays pinned at bottom — most important affordance

LAST UPDATED: 2026-05-25 by PATCH-415
"""
import shutil
from pathlib import Path

OS_FILE = Path("/opt/Murphy-System/static/murphy-os.html")
BACKUP = OS_FILE.with_suffix(".html.pre-415")

src = OS_FILE.read_text()

if "PATCH-415" in src:
    print("  ⚠ PATCH-415 already applied — skipping (idempotent)")
    raise SystemExit(0)

shutil.copy(OS_FILE, BACKUP)
print(f"  ✓ Backed up to {BACKUP}")

# ── Mobile CSS block ────────────────────────────────────────────────────────
MOBILE_CSS = '''
/* ── PATCH-415: Mobile + tablet responsive layer ─────────────────────── */

/* Tablet: 641-960px — sidebar becomes overlay drawer */
@media (max-width: 960px) {
  .sidebar {
    display: block !important;
    position: fixed;
    top: 80px;
    left: 0;
    bottom: 60px;
    width: 220px;
    z-index: 80;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    background: var(--panel-bg, #0a0e1a);
    border-right: 1px solid rgba(255,255,255,0.08);
    overflow-y: auto;
    padding-top: 8px;
  }
  .sidebar.open { transform: translateX(0); }

  .mobile-menu-btn {
    display: flex !important;
    background: transparent;
    border: 1px solid rgba(94,224,196,0.3);
    color: #5ee0c4;
    font-size: 18px;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    align-items: center;
  }

  .topbar { padding: 0 12px; }
  .topbar-center { overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
  .topbar-center::-webkit-scrollbar { display: none; }
  .nav-tab { white-space: nowrap; flex-shrink: 0; }

  /* Drill panel: still side drawer on tablet but narrower */
  #drill-panel { width: 90vw !important; max-width: 480px; }

  /* World strip wraps to multiple lines */
  .world-strip { flex-wrap: wrap; padding: 8px 12px; row-gap: 4px; }
}

/* Phone: ≤640px — total layout reflow */
@media (max-width: 640px) {
  /* Hide brand text, keep dot */
  .brand { gap: 6px; }
  .brand-dot { width: 16px; height: 16px; }
  .live-pill { display: none; }

  /* Topbar nav becomes horizontal scroll strip */
  .topbar { padding: 0 8px; height: 56px; }
  .topbar-center { gap: 4px; padding: 0 6px; }
  .nav-tab { padding: 6px 10px; font-size: 12px; }

  .topbar-right { gap: 6px; }
  .llm-badge { display: none; }
  .dispatch-btn-top { padding: 6px 10px; font-size: 11px; }
  .dispatch-btn-top::before { content: "▶ "; }

  /* World strip: smaller, more compact */
  .world-strip {
    font-size: 10px !important;
    padding: 6px 10px !important;
    gap: 10px !important;
    overflow-x: auto;
    flex-wrap: nowrap;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
  }
  .world-strip::-webkit-scrollbar { display: none; }

  /* Terminal strip: shrink */
  .terminal-strip {
    font-size: 10px !important;
    padding: 4px 10px !important;
    height: 24px;
  }

  /* Shell: single column always */
  .shell {
    grid-template-columns: 1fr !important;
    padding-bottom: 70px; /* room for fixed ask-bar */
  }

  /* Sidebar drawer covers more on phone */
  .sidebar {
    top: 90px;
    bottom: 60px;
    width: 80vw;
    max-width: 280px;
    box-shadow: 4px 0 24px rgba(0,0,0,0.6);
  }

  /* Sidebar items: bigger touch targets */
  .sidebar-item {
    padding: 14px 16px !important;
    font-size: 14px !important;
  }
  .sidebar-icon { font-size: 18px !important; }

  /* Main content padding */
  .page { padding: 12px !important; }
  .col { padding: 14px 12px; }

  /* Overview: stack all 3 cols */
  .overview-grid {
    grid-template-columns: 1fr !important;
    grid-template-rows: auto auto auto;
  }
  .overview-grid .col { border-right: none; border-bottom: 1px solid var(--border, rgba(255,255,255,0.08)); }

  /* Agents grid: single column, full-width cards */
  .agents-grid { grid-template-columns: 1fr !important; gap: 12px; }

  /* Pipeline stages: 1 col on phone */
  .pipeline-stage-cols { grid-template-columns: 1fr !important; }

  /* Generic 3-col / 5-col grids → 1-col */
  [style*="grid-template-columns: repeat(3"],
  [style*="grid-template-columns: repeat(5"] {
    grid-template-columns: 1fr !important;
  }

  /* Drill panel: full-screen modal on phone */
  #drill-panel {
    width: 100vw !important;
    max-width: 100vw !important;
    top: 0 !important;
    height: 100vh;
    border-radius: 0;
    border-left: none;
    z-index: 200;
  }
  /* Drill close button bigger on phone */
  .drill-close { font-size: 22px !important; padding: 10px 14px !important; }

  /* Ask Murphy bar: always pinned, bigger touch */
  .ask-bar {
    width: 100% !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    padding: 10px 12px !important;
    border-radius: 0 !important;
    border-top: 1px solid rgba(94,224,196,0.3);
    background: rgba(10,14,26,0.98);
    backdrop-filter: blur(10px);
  }
  .ask-input { font-size: 14px !important; }
  .ask-go { padding: 10px 14px !important; }

  /* Buttons in pipeline / cards: stack vertically */
  .pipeline-card-actions { flex-direction: column !important; gap: 6px !important; }
  .pipeline-card-actions button { width: 100%; }

  /* Tables: scroll horizontally */
  table { display: block; overflow-x: auto; white-space: nowrap; }
}

/* The hamburger button only renders on tablet/phone */
.mobile-menu-btn { display: none; }

/* Backdrop behind open sidebar on mobile */
.sidebar-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 70;
}
.sidebar-backdrop.open { display: block; }
@media (min-width: 961px) {
  .sidebar-backdrop { display: none !important; }
}
'''

# ── JS toggle for mobile menu ──────────────────────────────────────────────
MOBILE_JS = '''
// ── PATCH-415: Mobile sidebar drawer toggle ──────────────────────────────
function toggleMobileMenu() {
  const sb = document.querySelector('.sidebar');
  const bd = document.querySelector('.sidebar-backdrop');
  if (!sb) return;
  const isOpen = sb.classList.contains('open');
  if (isOpen) {
    sb.classList.remove('open');
    bd && bd.classList.remove('open');
  } else {
    sb.classList.add('open');
    bd && bd.classList.add('open');
  }
}
// Auto-close sidebar when a sidebar item is tapped on mobile
document.addEventListener('click', function(e) {
  const item = e.target.closest('.sidebar-item');
  if (item && window.innerWidth <= 960) {
    setTimeout(() => {
      const sb = document.querySelector('.sidebar');
      const bd = document.querySelector('.sidebar-backdrop');
      sb && sb.classList.remove('open');
      bd && bd.classList.remove('open');
    }, 100);
  }
});
'''

# ── Hamburger button HTML — inject into topbar brand area ──────────────────
HAMBURGER_HTML = '''<button class="mobile-menu-btn" onclick="toggleMobileMenu()" aria-label="Menu">☰</button>
    '''

# ── Backdrop element — inject right after <body> ───────────────────────────
BACKDROP_HTML = '<div class="sidebar-backdrop" onclick="toggleMobileMenu()"></div>\n'

# ── Apply injections ───────────────────────────────────────────────────────
# 1. Add CSS before the final </style> tag (line 2179)
# Use rfind to get the LAST </style>
last_style = src.rfind('</style>')
if last_style < 0:
    print("  ✗ no </style> tag found — aborting")
    raise SystemExit(1)
src = src[:last_style] + MOBILE_CSS + '\n' + src[last_style:]
print("  ✓ injected mobile CSS before final </style>")

# 2. Add hamburger button as first child of .brand div
brand_anchor = '<div class="brand">'
brand_replacement = '<div class="brand">\n    ' + HAMBURGER_HTML
if brand_anchor in src:
    src = src.replace(brand_anchor, brand_replacement, 1)
    print("  ✓ injected hamburger button in .brand")
else:
    print("  ⚠ .brand anchor not found — hamburger NOT injected")

# 3. Add backdrop right after <body>
body_anchor = '<body>'
if body_anchor in src and 'sidebar-backdrop' not in src.split('<script')[0]:
    src = src.replace(body_anchor, body_anchor + '\n' + BACKDROP_HTML, 1)
    print("  ✓ injected sidebar backdrop after <body>")

# 4. Add JS toggle — inject before the first <script> opening that contains real code
# Find a JS function definition we know exists (switchPage) and inject before it
js_anchor = 'function switchPage'
if js_anchor in src:
    src = src.replace(js_anchor, MOBILE_JS + '\n' + js_anchor, 1)
    print("  ✓ injected mobile JS toggle before switchPage()")
else:
    # Fallback: append a new <script> block before </body>
    body_close = src.rfind('</body>')
    src = src[:body_close] + '\n<script>' + MOBILE_JS + '</script>\n' + src[body_close:]
    print("  ✓ injected mobile JS as new <script> block before </body>")

OS_FILE.write_text(src)
print(f"\n  ✓ Total size: {len(src)} bytes (was {BACKUP.stat().st_size})")
