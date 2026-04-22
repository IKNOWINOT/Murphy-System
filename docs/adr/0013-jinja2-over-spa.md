# ADR-0013: Frontend consolidation — Jinja2 over SPA for product pages

* **Status:** Accepted
* **Date:** 2026-04-22
* **Roadmap row closed:** Item 11
* **Implementation spans:** root `*.html` (69 files), `templates/`, `static/`,
  `src/runtime/app.py` route handlers
* **Triage:** see "Per-file classification" §

## Context

The repo currently has **69 root-level `.html` files**. They are a mix of:

* Server-rendered "page-shaped" responses (login, signup, dashboard, demo)
* Static marketing pages (pricing, privacy, careers, blog, legal)
* Heavy product pages with embedded JS (terminals, dashboards, wizards)
* Demo / political / one-off pages (`steve2028merch.html`, `voteforsteve2028.html`,
  `stevewiki.html`)

There is **no SPA framework already in use** — no React/Vue/Svelte build, no
bundler, no routing library. Every page is shipped as a hand-edited static
`.html` file that calls `fetch('/api/...')` directly. This has three concrete
problems:

1. **No layout sharing.** The 69 files duplicate header / nav / auth-bar /
   footer markup. A theme change is 69 edits.
2. **Marketing pages live in the product tree.** Crawlers and ops people see
   `pricing.html` next to `hitl_dashboard.html`. There is no separation
   between "external surface" and "authenticated app surface."
3. **Routes aren't typed.** Each handler builds its own redirect/render path;
   there is no shared `render(template, **ctx)` primitive. CSP, request-id
   propagation, and CSRF tokens are added per file or not at all.

The Class S Roadmap, Item 11, asks for "Jinja2 (minimal) or SPA (modern)" and
defers the choice. This ADR makes the choice.

## Decision

We adopt **Jinja2 server-side templates** for product pages and move marketing
pages out of the product tree. We do **not** adopt a SPA framework.

The case for Jinja2 (and against an SPA today):

* **No existing build pipeline.** Adding Vite/Webpack + React/Vue is
  hundreds of LOC of `package.json`, lockfile, CI integration, and a new
  deploy artifact for a problem that is fundamentally "share a header and a
  nav across 69 pages."
* **FastAPI ships first-class Jinja2 support** (`fastapi.templating.Jinja2Templates`).
  Zero new runtime dependencies — `jinja2` is already transitively present via
  Starlette.
* **No team allocated to maintain a SPA.** SPAs require dedicated frontend
  ownership; HTMX-style sprinkles do not. We are sized for the latter.
* **Reversibility.** A Jinja2 page is *also* a perfectly good starting point
  for a future SPA migration. The reverse is not true.
* **CLAUDE.md §2 (simplicity first).** Jinja2 is the smallest decision that
  solves the stated problem.

The owner can override this decision by writing a counter-ADR before any
template migration PR lands.

## Per-file classification

| Bucket | Count | Treatment |
|---|---:|---|
| **Marketing** (move to `templates/marketing/`, render via marketing routes) | 12 | `blog.html`, `careers.html`, `community_forum.html`, `docs.html`, `financing_options.html`, `legal.html`, `murphy_landing_page.html`, `pricing.html`, `privacy.html`, `partner_request.html`, `grant_application.html`, `roi_calendar.html` |
| **Auth surface** (move to `templates/auth/`, share `_layout_auth.html`) | 4 | `login.html`, `signup.html`, `reset_password.html`, `change_password.html` |
| **Product / dashboards** (move to `templates/app/`, share `_layout_app.html`) | 26 | `admin_panel.html`, `aionmind.html`, `ambient_intelligence.html`, `automations.html`, `boards.html`, `calendar.html`, `communication_hub.html`, `compliance_dashboard.html`, `crm.html`, `dashboard.html`, `dashboards.html`, `dev_module.html`, `dispatch.html`, `grant_dashboard.html`, `grant_wizard.html`, `guest_portal.html`, `hitl_dashboard.html`, `management.html`, `meeting_intelligence.html`, `module_instances.html`, `onboarding_wizard.html`, `org_portal.html`, `portfolio.html`, `production_wizard.html`, `service_module.html`, `time_tracking.html`, `wallet.html`, `workdocs.html`, `workspace.html`, `workflow_canvas.html` |
| **Terminals** (move to `templates/terminal/`, share `_layout_terminal.html`) | 9 | `terminal_architect.html`, `terminal_costs.html`, `terminal_enhanced.html`, `terminal_integrated.html`, `terminal_integrations.html`, `terminal_orchestrator.html`, `terminal_orgchart.html`, `terminal_unified.html`, `terminal_worker.html`, `murphy_ui_integrated_terminal.html` |
| **Trading & finance** | 4 | `paper_trading_dashboard.html`, `trading_dashboard.html`, `risk_dashboard.html`, `system_visualizer.html` |
| **Demo / fixtures** (move to `templates/demo/` — keep, mark non-prod) | 4 | `demo.html`, `demo_config.html`, `game_creation.html`, `matrix_integration.html` |
| **Smoke / dev** (move to `templates/dev/` — gated by `MURPHY_RUNTIME_MODE`) | 2 | `murphy-smoke-test.html`, `murphy_ui_integrated.html` |
| **Out-of-scope (proposed: archive)** | 4 | `steve2028merch.html`, `voteforsteve2028.html`, `stevewiki.html`, `steve_candidate.png` (not html but co-located) — propose moving to a separate `archive/` repo or a `static/legacy/` path; not part of the Murphy product |

Total: 65 + 4 archive candidates = 69 ✓

## Migration order (one PR per bucket)

1. **Scaffolding PR** — add `templates/{_layouts,marketing,auth,app,terminal,demo,dev}/`
   skeleton, register `Jinja2Templates(directory="templates")` in
   `src/runtime/app.py`, ship the four `_layout_*.html` files. No file moves.
2. **Auth bucket** (4 files) — smallest, highest leverage (login/signup are the
   most-changed pages).
3. **Marketing bucket** (12 files) — also moves them out of the product tree;
   marketing routes get their own router (see Item 1).
4. **Terminals bucket** (9 files) — tightly related, shared chrome.
5. **Product/dashboards bucket** (26 files, split into 2–3 PRs by domain).
6. **Trading & finance** (4 files).
7. **Demo / dev** (6 files), then archive bucket cleanup.

Each PR (a) moves the file under `templates/`, (b) extracts shared chrome
into `_layout_*.html`, (c) flips its handler to `templates.TemplateResponse(...)`,
(d) deletes the root copy. No PR migrates more than ~10 files; CLAUDE.md §3
holds.

## Consequences

* The repo root finally contains zero `.html` files (verified by a CI guard
  added in the scaffolding PR — `tests/contracts/test_no_root_html.py`).
* CSP, request-ID injection, and CSRF tokens are added once in the layout
  files instead of 69 times.
* Marketing pages can be served from a different router (and eventually a
  different host) without touching product code.
* `static/` becomes the canonical home for shared CSS/JS; per-page assets
  stay co-located but referenced via `url_for('static', ...)`.

## Rejected alternatives

* **React/Vue SPA.** Rejected for reasons enumerated in Decision §.
* **HTMX-only (no templates).** Rejected — solves only the JS problem, not
  the layout-duplication problem.
* **Astro / Eleventy (static-site generators).** Rejected for product pages
  (need request context); reasonable for marketing-only but adds a second
  build pipeline. Marketing-via-Jinja keeps the toolchain at one.
* **Status quo (do nothing).** Rejected — every theme change is a 69-file
  diff today, and that cost only grows.

## Verification

* `tests/contracts/test_no_root_html.py` (added in scaffolding PR) asserts
  zero `*.html` files at the repo root after Phase 7.
* Each migration PR runs the existing route smoke tests; the response body
  must contain the same key strings as before (template fidelity check).
