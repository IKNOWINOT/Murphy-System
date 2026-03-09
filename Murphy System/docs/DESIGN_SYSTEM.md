# Murphy System — Design System

> **Version:** 1.0  
> **License:** BSL 1.1  
> **Last updated:** 2026-03-08

---

## Overview

The Murphy Design System provides a unified visual language across all 14 interfaces in the Murphy System. It enforces the **"Calm Authority"** aesthetic — a command center that feels like premium SaaS — ensuring that deeply technical automation capabilities are presented with clarity and simplicity.

**Core principle:** A non-technical business owner operates Murphy as easily as a DevOps engineer. Complexity is hidden behind clarity — not by removing features, but by organizing them so the user never feels lost.

---

## Files

| File | Purpose | Size |
|------|---------|------|
| `static/murphy-design-system.css` | Shared stylesheet — tokens, reset, components, responsive, print, animations | ~1800 lines |
| `static/murphy-components.js` | Vanilla JS module — API client, UI components, Librarian chat, terminal panel | ~1700 lines |
| `static/murphy-canvas.js` | Canvas rendering engine — nodes, edges, ports, interaction, auto-layout | ~1900 lines |
| `static/murphy-icons.svg` | SVG sprite sheet — 42 icons, 24×24, 2px stroke | ~300 lines |
| `static/favicon.svg` | Browser favicon — teal arrow on dark background | Minimal |

---

## Color Palette

### Dark Theme (default)

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-base` | `#0C1017` | Page background |
| `--bg-surface` | `#131A24` | Cards, panels |
| `--bg-elevated` | `#1A2332` | Modals, dropdowns, hover states |
| `--bg-input` | `#0F1620` | Input fields, code blocks |
| `--border-subtle` | `#1E2A3A` | Dividers, inner borders |
| `--border-default` | `#2A3A4E` | Card borders, outlines |
| `--border-focus` | `#00D4AA` | Focus rings, active state |
| `--text-primary` | `#E6ECF2` | Headings, body text |
| `--text-secondary` | `#8899AA` | Labels, descriptions |
| `--text-muted` | `#566778` | Placeholders, disabled text |
| `--teal` | `#00D4AA` | Primary accent |
| `--teal-glow` | `rgba(0,212,170,0.12)` | Subtle accent backgrounds |

### Theme Policy — Dark Only

Murphy System uses a **dark theme exclusively**. There is no light theme and no theme toggle.

**Rationale:** Operators stare at Murphy interfaces for extended periods. Black backgrounds with soft accent colors (teal, cyan, muted gold) reduce eye fatigue and create a calming, focused environment. White backgrounds are not appropriate for a system that runs continuously in an operations context.

The `body.murphy-light` CSS class and the `MurphyTheme.toggle()` method are not supported. `MurphyTheme.init()` always applies the dark theme. Do not add light mode variants when building new interfaces.

### Semantic Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--success` | `#22C55E` | Healthy, completed, approved |
| `--warning` | `#FFA63E` | Attention needed, pending |
| `--danger` | `#EF4444` | Errors, critical, blocked |
| `--info` | `#3B9EFF` | Informational, links, hints |

### Gate Colors

| Gate | Color | Token |
|------|-------|-------|
| Executive | `#FFD700` | `--gate-executive` |
| Operations | `#00D4AA` | `--gate-operations` |
| QA | `#8B6CE7` | `--gate-qa` |
| HITL | `#FFA63E` | `--gate-hitl` |
| Compliance | `#EF4444` | `--gate-compliance` |
| Budget | `#3B9EFF` | `--gate-budget` |

### Role Accents

Each terminal interface has a unique accent color to help users identify which view they're in:

| Interface | Accent | Token |
|-----------|--------|-------|
| Onboarding Wizard | Gold `#FFD166` | `--accent-gold` |
| Landing Page | Teal `#00D4AA` | `--accent-teal` |
| Architect Terminal | Teal `#00D4AA` | `--accent-teal` |
| Enhanced Terminal | Pink `#E879F9` | `--accent-pink` |
| Operations Terminal | Blue `#3B9EFF` | `--accent-blue` |
| Worker Terminal | Amber `#FFA63E` | `--accent-amber` |
| Costs Terminal | Coral `#FF6B6B` | `--accent-coral` |
| Org Chart Terminal | Green `#22C55E` | `--accent-green` |
| Unified Hub | Violet `#8B6CE7` | `--accent-violet` |
| Integrations Terminal | Sky `#38BDF8` | `--accent-sky` |
| Workflow Canvas | Cyan `#22D3EE` | `--accent-cyan` |
| System Visualizer | Indigo `#818CF8` | `--accent-indigo` |

---

## Typography

| Usage | Font | Size | Weight |
|-------|------|------|--------|
| UI text | `Inter, system-ui, sans-serif` | 15px base | 400 regular, 500 medium, 600 semibold, 700 bold |
| Code/terminal | `JetBrains Mono, monospace` | 13px | 400 regular, 500 medium |
| Small labels | Inter | 11px (`--text-xs`) | 500 |
| Section headers | Inter | 18px (`--text-lg`) | 600 |
| Hero numbers | Inter | 48px (`--text-3xl`) | 700 |

Fonts are loaded via Google Fonts. Both families support Latin Extended.

---

## Spacing & Sizing

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight gaps, icon padding |
| `--space-2` | 8px | Inline element spacing |
| `--space-3` | 12px | Small card padding |
| `--space-4` | 16px | Default card padding, form gaps |
| `--space-5` | 24px | Section spacing |
| `--space-6` | 32px | Large section spacing |
| `--space-7` | 48px | Page sections |
| `--space-8` | 64px | Hero spacing |

### Border Radius

| Token | Value |
|-------|-------|
| `--radius-sm` | 4px |
| `--radius-md` | 8px |
| `--radius-lg` | 12px |
| `--radius-xl` | 16px |
| `--radius-full` | 9999px |

---

## Layout

```
┌──────────────────────────────────────────────────┐
│ Topbar (56px, fixed)                    [🌙][🔔] │
├──────────┬───────────────────────────────────────┤
│ Sidebar  │ Content Area                          │
│ (240px)  │ max-width: 1200px (centered)          │
│          │ or full-width for canvas UIs           │
│ Collaps. │                                       │
│ to 56px  │                                       │
│          │                               [💬]    │
└──────────┴───────────────────────────────────────┘
```

- **Sidebar:** 240px wide, collapsible to 56px (icon-only). Fixed left.
- **Topbar:** 56px height, fixed top. Contains breadcrumb, search, notifications.
- **Content:** Scrollable main area. Centered `max-width: 1200px` for dashboard UIs, full-width for canvas UIs.
- **Librarian Chat:** Floating button bottom-right on every page. Opens 350px slide-in panel.

### Responsive Breakpoints

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Desktop | > 1024px | Full sidebar + topbar + content |
| Tablet | 768–1024px | Sidebar collapsed by default |
| Mobile | < 768px | Sidebar hidden, hamburger menu, stacked layout |

---

## Components

### Buttons — `.murphy-btn`

```html
<button class="murphy-btn murphy-btn-primary">Save Changes</button>
<button class="murphy-btn murphy-btn-secondary">Cancel</button>
<button class="murphy-btn murphy-btn-danger">Delete</button>
<button class="murphy-btn murphy-btn-ghost">More Options</button>
<button class="murphy-btn murphy-btn-sm">Small</button>
<button class="murphy-btn murphy-btn-lg">Large</button>
<button class="murphy-btn murphy-btn-icon"><svg>...</svg></button>
```

Variants: `primary` (teal fill), `secondary` (border only), `danger` (red), `ghost` (transparent). Sizes: `sm`, default, `lg`. States: `:hover`, `:active`, `:disabled`, `.murphy-btn-loading`.

### Cards — `.murphy-card`

```html
<div class="murphy-card">
  <div class="murphy-card-header">Title</div>
  <div class="murphy-card-body">Content</div>
  <div class="murphy-card-footer">Actions</div>
</div>
```

Subtle hover lift effect. Background: `--bg-surface`. Border: `--border-subtle`.

### Stat Cards — `.murphy-stat-card`

```html
<div class="murphy-stat-card">
  <div class="murphy-stat-card-label">Active Workflows</div>
  <div class="murphy-stat-card-value">42</div>
  <div class="murphy-stat-card-change murphy-stat-card-change-up">+12%</div>
</div>
```

Hero-sized numbers. Color-coded change indicators. Used on dashboards.

### Form Elements — `.murphy-input`, `.murphy-select`, `.murphy-textarea`

```html
<label class="murphy-label">Name</label>
<input class="murphy-input" placeholder="Enter name">
<select class="murphy-select"><option>Option 1</option></select>
<textarea class="murphy-textarea" rows="4"></textarea>
```

Error state: `.murphy-input-error`. Error message: `.murphy-input-error-msg`.

### Tables — `.murphy-table`

```html
<table class="murphy-table murphy-table-striped">
  <thead class="murphy-table-header">
    <tr><th class="murphy-table-sortable">Name</th><th>Status</th></tr>
  </thead>
  <tbody>
    <tr class="murphy-table-row"><td>Item 1</td><td>Active</td></tr>
  </tbody>
</table>
```

Sortable columns, striped rows, hover highlight. Always use with `MurphyTable` JS class for search/sort/pagination.

### Badges — `.murphy-badge`

```html
<span class="murphy-badge murphy-badge-success">Active</span>
<span class="murphy-badge murphy-badge-warning">Pending</span>
<span class="murphy-badge murphy-badge-danger">Error</span>
<span class="murphy-badge murphy-badge-info">Info</span>
```

### Gate Indicators — `.murphy-gate-indicator`

```html
<div class="murphy-gate-indicator murphy-gate-indicator-executive murphy-gate-indicator-open">
  Executive Gate
</div>
```

Shows gate open/closed state with color coding. Hex variant: `.murphy-gate-indicator-hex` for topology view.

### Modals — `.murphy-modal`

Created via `MurphyModal.show({title, body, actions})`. Focus-trapped, Escape to close, backdrop click to close.

### Toasts — `.murphy-toast`

Created via `MurphyToast.show(message, type, duration)`. Types: success, warning, danger, info. Auto-dismiss. Top-right container.

### Skeleton Loading — `.murphy-skeleton`

```html
<div class="murphy-skeleton" style="width:200px;height:20px"></div>
```

Shimmer animation placeholder. Used while API data loads.

### Empty States — `.murphy-empty-state`

```html
<div class="murphy-empty-state">
  <div class="murphy-empty-state-icon">📋</div>
  <div class="murphy-empty-state-title">No workflows yet</div>
  <div class="murphy-empty-state-text">Create your first workflow to get started.</div>
</div>
```

### Progress Bar — `.murphy-progress-bar`

```html
<div class="murphy-progress-bar">
  <div class="murphy-progress-bar-header">
    <span>Progress</span><span>75%</span>
  </div>
  <div class="murphy-progress-bar-track">
    <div class="murphy-progress-bar-fill" style="width:75%"></div>
  </div>
</div>
```

Variants: `-success`, `-warning`, `-danger` on the fill element.

### Tooltips — `.murphy-tooltip`

```html
<span class="murphy-tooltip" data-tooltip="Explanation here">Hover me</span>
```

CSS-only tooltips via `::before`/`::after`.

---

## Canvas Components (Graphical UIs)

### Terminal Panel — `.murphy-terminal-panel`

Embedded monospace terminal used in Workflow Canvas and System Visualizer. Features:
- Header with traffic-light dots (red/yellow/green)
- Scrollable output area with syntax highlighting
- Command input line with prompt character
- Color-coded log levels: `.term-success`, `.term-error`, `.term-warning`, `.term-info`

```html
<div class="murphy-terminal-panel">
  <div class="murphy-terminal-panel-header">
    <span class="murphy-terminal-panel-header-dot"></span>
    <span class="murphy-terminal-panel-header-dot"></span>
    <span class="murphy-terminal-panel-header-dot"></span>
    <span>Terminal</span>
  </div>
  <div class="murphy-terminal-output" id="output"></div>
  <div class="murphy-terminal-input">
    <span class="murphy-terminal-input-prompt">→</span>
    <input type="text" placeholder="Type command...">
  </div>
</div>
```

### Canvas Container — `.murphy-canvas-container`

Full-width container for the HTML5 `<canvas>` element used by `murphy-canvas.js`.

### Split Pane — `.murphy-split-pane`

Resizable top/bottom split for canvas + terminal layout:

```html
<div class="murphy-split-pane">
  <div class="murphy-split-pane-top"><!-- Canvas --></div>
  <div class="murphy-split-pane-handle"></div>
  <div class="murphy-split-pane-bottom"><!-- Terminal --></div>
</div>
```

Handle is draggable. Double-click to collapse/expand terminal.

### Node Cards — `.murphy-node-card`

Overlay HTML elements positioned over canvas coordinates for rich node content:

```html
<div class="murphy-node-card murphy-node-card-operations">
  <div class="murphy-node-card-health"></div>
  <div class="murphy-node-card-title">Module Name</div>
  <div class="murphy-node-card-type">Operations</div>
</div>
```

Node type border colors match gate colors. Port elements (`.murphy-node-card-port`) on left/right sides.

---

## Librarian Chat Integration

The Librarian chat widget appears on every interface as a floating button (bottom-right) that opens a slide-in conversational panel.

### Chat Bubbles — `.murphy-chat-bubble`

```html
<div class="murphy-chat-bubble murphy-chat-bubble-user">
  What does the HITL gate do?
  <div class="murphy-chat-bubble-timestamp">2:30 PM</div>
</div>
<div class="murphy-chat-bubble murphy-chat-bubble-assistant">
  The HITL gate requires human approval before Murphy takes action...
  <div class="murphy-chat-bubble-timestamp">2:30 PM</div>
</div>
```

### Chat Input — `.murphy-chat-input`

```html
<div class="murphy-chat-input">
  <textarea placeholder="Ask the Librarian..."></textarea>
  <button class="murphy-chat-input-send">Send</button>
</div>
```

### Integration

```javascript
const api = new MurphyAPI('/api');
const chat = new MurphyLibrarianChat(api);
chat.setContext('terminal_unified#dashboard');
```

The Librarian widget is context-aware — it knows which page and view the user is currently on. Users can ask "What am I looking at?" and get a plain-English explanation.

---

## JavaScript Components

### MurphyAPI

Fetch wrapper with authentication, retry logic, and circuit breaker:

```javascript
const api = new MurphyAPI('/api');
const result = await api.get('/status');
// result: { ok: true, data: {...}, status: 200 }
```

- Reads API key from `localStorage('murphy_api_key')`
- Sends as `X-API-Key` header
- 3 retries with exponential backoff for 5xx errors
- Circuit breaker: opens after 5 consecutive failures, half-open after 30s

### MurphyToast

```javascript
MurphyToast.show('Workflow saved', 'success');
MurphyToast.show('Connection lost', 'danger', 6000);
```

### MurphyModal

```javascript
const close = MurphyModal.show({
  title: 'Confirm Delete',
  body: '<p>Are you sure?</p>',
  actions: [
    { label: 'Cancel', variant: 'secondary', onClick: () => close() },
    { label: 'Delete', variant: 'danger', onClick: () => { deleteItem(); close(); } }
  ]
});
```

### MurphyHealth

Polls `/api/health` and shows/hides offline banner:

```javascript
const health = new MurphyHealth(api);
health.onUpdate(data => console.log(data.status));
health.start(15000);
```

### MurphyTable

```javascript
const table = new MurphyTable(container, {
  columns: [
    { key: 'name', label: 'Name', sortable: true },
    { key: 'status', label: 'Status', render: v => `<span class="murphy-badge">${v}</span>` }
  ],
  data: items,
  searchable: true,
  pageSize: 20
});
```

### MurphyChart

```javascript
const chart = new MurphyChart(canvasEl, 'sparkline', { color: '#00D4AA' });
chart.update([10, 25, 18, 42, 35, 55, 48]);
```

Types: `sparkline`, `gauge`, `bar`, `timeline`.

### MurphyTheme

```javascript
MurphyTheme.init(); // applies dark theme (only supported theme)
MurphyTheme.get();  // always returns 'dark'
```

Murphy System is dark-only. Do not call `MurphyTheme.toggle()` — the method is deprecated and will be removed. See the [Theme Policy](#theme-policy--dark-only) section above.

### MurphyJargon

Auto-tooltips for technical terms:

```javascript
MurphyJargon.init(); // scans [data-jargon] elements
MurphyJargon.autoScan(); // finds known terms in DOM text
```

25+ terms defined: MFGC, HITL, Gate, Swarm, Wingman, Causality Engine, Confidence Engine, etc.

### MurphyKeyboard

```javascript
MurphyKeyboard.register('ctrl+k', openSearch, 'Open search');
MurphyKeyboard.init();
MurphyKeyboard.showHelp(); // shows shortcut reference modal
```

### MurphyTerminalPanel

Embedded terminal component for graphical UIs:

```javascript
const terminal = new MurphyTerminalPanel(container, {
  apiEndpoint: '/api/workflow-terminal/execute',
  prompt: 'workflow>'
});
terminal.appendOutput('Workflow started...', 'term-success');
```

---

## Canvas Engine

The `murphy-canvas.js` module provides the rendering engine for both graphical UIs (Workflow Canvas and System Visualizer).

### MurphyCanvas

Core canvas with pan, zoom, grid, and minimap:

```javascript
const canvas = new MurphyCanvas(containerEl, {
  gridSize: 20,
  showGrid: true,
  showMinimap: true
});
canvas.addNode(new MurphyNode({ id: '1', x: 100, y: 100, type: 'action', label: 'API Call' }));
canvas.render();
```

### MurphyNode

Visual nodes with ports, icons, and health indicators:

- Types: `trigger` (green), `action` (teal), `logic` (violet), `gate` (gate-colored), `integration` (sky), `module` (for topology)
- States: selected (glow), running (pulse), error (red pulse)
- Ports: input (left) and output (right) connection points

### MurphyEdge

Animated connections between node ports:

- Bezier curves with directional animation
- Thickness represents throughput (1–5px)
- Color represents health (green/amber/red/gray)

### MurphyCanvasInteraction

Full interaction layer:

- Click to select, Shift+click for multi-select
- Drag nodes to move (grid-snapping)
- Drag from output port to input port to connect
- Rubber-band selection for multiple nodes
- Delete/Backspace to remove, Ctrl+Z/Y for undo/redo
- Scroll to zoom, drag empty space to pan
- Touch: tap, long-press drag, pinch zoom

### MurphyAutoLayout

Automatic layout algorithms:

- **Force-directed:** For system topology — repulsion, attraction, gravity, domain clustering
- **DAG layout:** For workflows — left-to-right layered layout with edge crossing minimization
- **Circular:** Fallback arrangement

---

## Accessibility

The design system enforces WCAG AA compliance:

- **Contrast:** All text/background combinations meet 4.5:1 ratio minimum
- **Focus:** Visible focus rings (`--border-focus: #00D4AA`) on all interactive elements
- **Skip link:** `.murphy-skip-link` allows keyboard users to skip to main content
- **ARIA:** All interactive components include appropriate ARIA labels and roles
- **Keyboard:** Full keyboard navigation via `MurphyKeyboard`. Tab order follows visual order.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables animations
- **Screen reader:** Semantic HTML, meaningful alt text, live regions for dynamic content

---

## Animations

| Name | Usage | Duration |
|------|-------|----------|
| `shimmer` | Skeleton loading placeholders | Continuous |
| `fadeIn` | Cards, modals appearing | 200ms |
| `slideIn` | Panels sliding from left/bottom | 350ms |
| `slideInRight` | Right panels, chat widget | 350ms |
| `pulse` | Health indicators, running states | 2s infinite |
| `nodeGlow` | Selected canvas nodes | 2s infinite |
| `spin` | Loading spinners | 1s infinite |

Utility classes: `.murphy-animate-fade`, `.murphy-animate-slide`, `.murphy-animate-pulse`.

---

## Icons

The `murphy-icons.svg` sprite sheet contains 42 icons. Use with:

```html
<svg class="murphy-icon" width="20" height="20">
  <use href="static/murphy-icons.svg#icon-dashboard"></use>
</svg>
```

Available icons: `dashboard`, `terminal`, `settings`, `user`, `users`, `chart`, `shield`, `alert`, `check`, `x`, `search`, `menu`, `chevron-up`, `chevron-down`, `chevron-left`, `chevron-right`, `sun`, `moon`, `bell`, `plus`, `refresh`, `code`, `globe`, `cpu`, `database`, `lock`, `unlock`, `layers`, `activity`, `zap`, `clock`, `dollar-sign`, `plug`, `file-text`, `message-circle`, `git-branch`, `workflow`, `topology`, `chat`, `play`, `pause`, `stop`.

All icons are 24×24 viewBox, 2px stroke, `currentColor` fill for easy theming.

---

## Print Styles

When printing, the design system:
- Hides sidebar, topbar, toast container, modals, and skip link
- Forces white background, black text
- Removes shadows and box-shadows
- Ensures cards have visible borders

---

## Integration Guide

### Adding the design system to a new page

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Murphy System — Page Title</title>
  <link rel="icon" href="static/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="static/murphy-design-system.css">
</head>
<body>
  <a href="#main" class="murphy-skip-link">Skip to content</a>
  
  <!-- Sidebar + Topbar + Content -->
  
  <main id="main">
    <!-- Page content -->
  </main>

  <script src="static/murphy-components.js"></script>
  <script>
    const api = new MurphyAPI('/api');
    const health = new MurphyHealth(api);
    const chat = new MurphyLibrarianChat(api);
    MurphyTheme.init();
    MurphyJargon.init();
    MurphyKeyboard.init();
    health.start();
  </script>
</body>
</html>
```

### Adding canvas UIs

```html
<script src="static/murphy-canvas.js"></script>
<script>
  const canvas = new MurphyCanvas(document.getElementById('canvas-container'));
  const interaction = new MurphyCanvasInteraction(canvas);
  const layout = new MurphyAutoLayout(canvas);
  canvas.render();
</script>
```
