# Murphy System — MultiCursor Browser: Agent Controller Reference

**File:** `src/agent_module_loader.py` → `MultiCursorBrowser`  
**Updated:** 2026-03-25  
**Version:** 2.0 (Playwright-complete superset + de-facto agent controller)

---

## Overview

`MultiCursorBrowser` (MCB) is the **de-facto agent controller** for all Murphy
agents that perform any browser, UI, or desktop interaction.  It is a complete
superset of every Playwright `Page` method, extended with Murphy-specific
capabilities: multi-cursor split-screen zones, parallel execution, desktop
automation, agent checkpointing, recording/playback, and extended assertions.

The controller follows the **Copilot skill-checkout pattern**: every agent
checks out its own MCB instance at construction time, keyed by its unique
`agent_id`.  This is the single source of truth for what that agent is allowed
to do in the browser.

---

## Agent Startup Protocol

```python
from src.agent_module_loader import MultiCursorBrowser

class MyAgent:
    def __init__(self):
        # 1. Checkout MCB controller — registered by agent identity
        self._mcb = MultiCursorBrowser.get_controller(agent_id="my_agent_id")

    async def do_browser_work(self):
        # 2. Launch browser when needed (headless by default)
        await self._mcb.launch(headless=True)

    async def shutdown(self):
        # 3. Close browser and release controller on shutdown
        await self._mcb.close()
        MultiCursorBrowser.release_controller("my_agent_id")
```

All `BaseSwarmAgent` subclasses, `ShadowAgent`, and `DecisionLearner` perform
this checkout automatically in their `__init__` methods.

---

## Controller Registry API

```python
# Get or create controller for an agent
mcb = MultiCursorBrowser.get_controller(agent_id="shadow_agent_xyz")

# List all registered agent controllers
agents = MultiCursorBrowser.list_controllers()
# → ["shadow_agent_xyz", "copilot_decision_learner", "swarm_ctrl_01", ...]

# Release controller on agent shutdown (does NOT close browser)
MultiCursorBrowser.release_controller("shadow_agent_xyz")
```

---

## Zone Layout System

MCB supports up to **64 physical zones** per instance (virtual tab stacking above 12):

| Zones | Layout Name | Grid |
|-------|-------------|------|
| 1 | `single` | 1×1 |
| 2 | `dual_h` | 1×2 side-by-side |
| 2 | `dual_v` | 2×1 stacked |
| 3 | `triple_h` | 1×3 |
| 4 | `quad` | 2×2 |
| 6 | `hexa` | 2×3 |
| 9 | `nona` | 3×3 |
| 12 | `dodeca` | 3×4 |
| 16 | `hex4` | 4×4 |
| >16 | `virtual` | Tabs within existing zones |

```python
browser = MultiCursorBrowser()
await browser.launch()
zones = browser.auto_layout(4)   # → quad (2×2), returns 4 zone dicts
await browser.navigate(zones[0]["zone_id"], "https://murphy.systems")
await browser.navigate(zones[1]["zone_id"], "https://murphy.systems/ui/admin")
# Both pages load simultaneously in their own zones
```

---

## Complete Action Reference

### Navigation
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `navigate(zone, url)` | `page.goto()` | Navigate to URL |
| `go_back(zone)` | `page.go_back()` | Browser back |
| `go_forward(zone)` | `page.go_forward()` | Browser forward |
| `reload(zone)` | `page.reload()` | Reload page |
| `wait_for_url(zone, url)` | `page.wait_for_url()` | Wait for URL match |
| `bring_to_front(zone)` | `page.bring_to_front()` | Bring tab to front |

### Interaction
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `click(zone, sel)` | `page.click()` | Left click |
| `double_click(zone, sel)` | `page.dblclick()` | Double click |
| `right_click(zone, sel)` | `page.click(button="right")` | Right click |
| `tap(zone, sel)` | `page.tap()` | Mobile touch tap |
| `hover(zone, sel)` | `page.hover()` | Mouse hover |
| `focus(zone, sel)` | `page.focus()` | Focus element |
| `drag(zone, src, dst)` | `page.drag_and_drop()` | Drag and drop |
| `scroll(zone, sel)` | `page.mouse.wheel()` | Scroll |
| `dispatch_event(zone, sel, event)` | `page.dispatch_event()` | Fire custom DOM event |

### Text Input
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `fill(zone, sel, val)` | `page.fill()` | Set input value (clears first) |
| `type(zone, sel, text)` | `page.type()` | Type characters one by one |
| `press(zone, sel, key)` | `page.press()` | Press keyboard key |
| `keyboard_down(zone, key)` | `page.keyboard.down()` | Key down |
| `keyboard_up(zone, key)` | `page.keyboard.up()` | Key up |
| `keyboard_insert_text(zone, text)` | `page.keyboard.insert_text()` | Insert text |

### Forms
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `check(zone, sel)` | `page.check()` | Check checkbox |
| `uncheck(zone, sel)` | `page.uncheck()` | Uncheck checkbox |
| `set_checked(zone, sel, bool)` | `page.set_checked()` | Set checkbox state |
| `select_option(zone, sel)` | `page.select_option()` | Select dropdown option |
| `set_input_files(zone, sel)` | `page.set_input_files()` | Set file input |

### Read / Query
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `get_text(zone, sel)` | `page.inner_text()` | Visible text content |
| `text_content(zone, sel)` | `page.text_content()` | Full text (incl. hidden) |
| `get_inner_html(zone, sel)` | `page.inner_html()` | Inner HTML |
| `get_content(zone)` | `page.content()` | Full page HTML |
| `get_title(zone)` | `page.title()` | Page title |
| `get_url(zone)` | `page.url` | Current URL |
| `get_attribute(zone, sel, attr)` | `page.get_attribute()` | Element attribute |
| `input_value(zone, sel)` | `page.input_value()` | Input field value |
| `get_bounding_box(zone, sel)` | `page.eval_on_selector()` | Element bounding box |

### Semantic Locators (Playwright 1.14+)
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `get_by_role(zone, role)` | `page.get_by_role()` | ARIA role |
| `get_by_text(zone, text)` | `page.get_by_text()` | Visible text |
| `get_by_label(zone, text)` | `page.get_by_label()` | Form label |
| `get_by_placeholder(zone, text)` | `page.get_by_placeholder()` | Input placeholder |
| `get_by_alt_text(zone, text)` | `page.get_by_alt_text()` | Alt text |
| `get_by_title(zone, text)` | `page.get_by_title()` | Title attribute |
| `get_by_test_id(zone, id)` | `page.get_by_test_id()` | data-testid |

### Visibility / State
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `is_visible(zone, sel)` | `page.is_visible()` | Element visible? |
| `is_hidden(zone, sel)` | `page.is_hidden()` | Element hidden? |
| `is_enabled(zone, sel)` | `page.is_enabled()` | Element enabled? |
| `is_disabled(zone, sel)` | `page.is_disabled()` | Element disabled? |
| `is_editable(zone, sel)` | `page.is_editable()` | Element editable? |

### JavaScript
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `evaluate(zone, expr)` | `page.evaluate()` | Evaluate JS expression |
| `evaluate_handle(zone, expr)` | `page.evaluate_handle()` | Evaluate JS, get handle |
| `eval_on_selector(zone, sel, expr)` | `page.eval_on_selector()` | Eval JS on element |
| `eval_on_selector_all(zone, sel, expr)` | `page.eval_on_selector_all()` | Eval JS on all matches |
| `add_init_script(zone, script)` | `page.add_init_script()` | Script before page load |
| `add_script_tag(zone, content)` | `page.add_script_tag()` | Inject script tag |
| `expose_function(zone, name, fn)` | `page.expose_function()` | Expose Python fn to JS |
| `expose_binding(zone, name, fn)` | `page.expose_binding()` | Expose binding to JS |

### Network / Mocking
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `route_fulfill(zone, pattern)` | `page.route()` + `route.fulfill()` | Mock response |
| `route_abort(zone, pattern)` | `page.route()` + `route.abort()` | Abort request |
| `route_from_har(zone, har)` | `page.route_from_har()` | Replay from HAR file |
| `unroute(zone, pattern)` | `page.unroute()` | Remove route |
| `set_extra_headers(zone, headers)` | `page.set_extra_http_headers()` | Add HTTP headers |
| `wait_for_request(zone, pattern)` | `page.expect_request()` | Wait for request |
| `wait_for_response(zone, pattern)` | `page.expect_response()` | Wait for response |

### Cookies / Storage
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `get_cookies(zone)` | `context.cookies()` | Get all cookies |
| `set_cookies(zone, cookies)` | `context.add_cookies()` | Set cookies |
| `clear_cookies(zone)` | `context.clear_cookies()` | Clear all cookies |
| `storage_state(zone)` | `context.storage_state()` | Get storage state |

### Permissions / Environment
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `grant_permissions(zone, perms)` | `context.grant_permissions()` | Grant permissions |
| `clear_permissions(zone)` | `context.clear_permissions()` | Clear permissions |
| `set_geolocation(zone, geo)` | `context.set_geolocation()` | Set fake location |
| `set_offline(zone, bool)` | `context.set_offline()` | Toggle offline mode |
| `emulate_media(zone, media)` | `page.emulate_media()` | Emulate print/screen |
| `set_viewport(zone, w, h)` | `page.set_viewport_size()` | Set viewport size |

### Time Control
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `clock_install(zone)` | `page.clock.install()` | Install fake clock |
| `clock_set_fixed_time(zone, t)` | `page.clock.set_fixed_time()` | Fix time |
| `clock_fast_forward(zone, ms)` | `page.clock.fast_forward()` | Skip time forward |
| `clock_run_for(zone, ms)` | `page.clock.run_for()` | Run clock for N ms |

### Accessibility
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `accessibility_snapshot(zone)` | `page.accessibility.snapshot()` | Full a11y tree |

### Screenshots / PDF
| Method | Playwright Equivalent | Description |
|--------|----------------------|-------------|
| `screenshot(zone, path)` | `page.screenshot()` | Save screenshot |
| `pdf(zone, path)` | `page.pdf()` | Generate PDF |

### Assertions (Murphy extended)
| Method | Description |
|--------|-------------|
| `assert_text(zone, sel, expected)` | Text contains expected |
| `assert_visible(zone, sel)` | Element is visible |
| `assert_url(zone, expected)` | URL contains expected |
| `assert_title(zone, expected)` | Title contains expected |
| `assert_count(zone, sel, n)` | Exactly N elements match |
| `assert_enabled(zone, sel)` | Element is enabled |
| `assert_disabled(zone, sel)` | Element is disabled |
| `assert_hidden(zone, sel)` | Element is hidden |
| `assert_editable(zone, sel)` | Element is editable |
| `assert_value(zone, sel, val)` | Input value equals val |
| `assert_attribute(zone, sel, attr, val)` | Attribute equals val |
| `assert_class(zone, sel, cls)` | Element has CSS class |
| `assert_checked(zone, sel)` | Checkbox is checked |

### Multi-Cursor Extensions
| Method | Description |
|--------|-------------|
| `auto_layout(n)` | Create N zones in tightest grid |
| `split_zone(zone, "h"\|"v")` | Halve a zone |
| `spawn_child(zone)` | Create nested MCB (max depth 8) |
| `parallel_probe(probes)` | Navigate multiple zones simultaneously |
| `parallel(coros)` | Execute coroutines in parallel |

### Desktop Automation
| Method | Description |
|--------|-------------|
| `desktop_click(x, y)` | Click at screen coordinates |
| `desktop_type(text)` | Type text globally |
| `desktop_hotkey(key)` | Press keyboard shortcut |
| `desktop_ocr(zone)` | Extract all text via OCR |
| `mouse_move(zone, x, y)` | Move mouse to position |
| `mouse_down(zone, button)` | Press mouse button |
| `mouse_up(zone, button)` | Release mouse button |
| `touchscreen_tap(zone, x, y)` | Touchscreen tap at coordinates |

### Agent Lifecycle
| Method | Description |
|--------|-------------|
| `checkpoint(id)` | Save zone/cursor state |
| `rollback(id)` | Restore saved state |
| `start_recording()` | Begin action recording |
| `stop_recording()` | End recording, return actions |
| `playback(actions)` | Replay recorded actions |
| `replay(actions)` | Alias for playback, returns bool |

---

## Nested MCB (Agent-in-Agent)

```python
parent = MultiCursorBrowser()
await parent.launch()
zones = parent.auto_layout(2)

# Spawn a child MCB sharing the same browser process
# but with isolated BrowserContext (cookies, storage)
child = await parent.spawn_child(zones[1]["zone_id"])
await child.navigate("main", "https://murphy.systems/ui/admin")

# max nesting depth: 8 levels
```

---

## Commissioning Tests

The full commissioning test suite is at `tests/ui/commissioning/`:

```
tests/ui/commissioning/
├── __init__.py
├── mcb_harness.py              # Core harness (identify→spec→probe→fix→verify)
├── test_commissioning_flows.py # 69 tests covering all pages and the complete chain
└── gap_registry.json           # Persisted gap tracking
tests/ui/screenshots/
├── landing/                    # Landing page screenshots
├── login/                      # Auth page screenshots
├── onboarding/                 # Onboarding wizard screenshots
├── production/                 # Production wizard screenshots
├── grants/                     # Grant wizard + dashboard screenshots
├── compliance/                 # Compliance dashboard screenshots
├── partner/                    # Partner request screenshots
├── pricing/                    # Pricing page screenshots
├── chain/                      # End-to-end chain screenshots
└── rosetta/                    # Rosetta viewpoint map exports
```

**Run commissioning tests:**
```bash
pytest tests/ui/commissioning/ -v --override-ini="addopts="
```

---

## Affected Files Summary

The following files were updated to wire MCB as agent controller:

| File | Change |
|------|--------|
| `src/agent_module_loader.py` | Added 50+ new action types, `get_controller()`, `release_controller()`, `list_controllers()`, convenience methods, full Playwright implementation |
| `src/true_swarm_system.py` | `BaseSwarmAgent.__init__` checks out MCB controller |
| `src/shadow_agent_integration.py` | `ShadowAgent.__post_init__` checks out MCB controller |
| `src/copilot_tenant/decision_learner.py` | `DecisionLearner.__init__` checks out MCB controller |
| `ARCHITECTURE_MAP.md` | Added Section 14: MultiCursor Agent Controller |
| `docs/MULTICURSOR_AGENT_CONTROLLER.md` | This file — full reference |
| `tests/ui/commissioning/mcb_harness.py` | Commissioning test harness |
| `tests/ui/commissioning/test_commissioning_flows.py` | 69 commissioning tests |

---

## Landing Page Changes (Bug Fixes + Overhaul)

As part of the same change set, the following UI files were updated:

| File | Change |
|------|--------|
| `murphy_landing_page.html` + `Murphy System/` copy | Full overhaul: Solutions, Industries, inline Demo, Partner, Under the Hood, updated nav/footer/hero |
| `login.html` + `Murphy System/` copy | Bug fix: `[object Object]` error normalisation + JSON parse fallback |
| `signup.html` + `Murphy System/` copy | Bug fix: same error normalisation + JSON parse fallback |
