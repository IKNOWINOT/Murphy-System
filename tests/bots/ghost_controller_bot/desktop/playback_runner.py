
#!/usr/bin/env python3
"""
Murphy Ghost Controller — playback_runner.py

Executes desktop automation steps via PyAutoGUI / OCR.
Supports multi-cursor mode: each step can carry an optional ``cursor_id``
field so that independent agents can operate their own virtual pointers on
the same physical desktop without interfering with each other.

Multi-cursor dispatch strategy:
  - Each cursor_id tracks its own (x, y) state in _CURSOR_STATE dict.
  - Calls to click(), type_text() etc. that pass a cursor_id will use that
    cursor's tracked position as the default coordinates.
  - The physical mouse pointer is still singular (OS limitation), but the
    logical positions are fully independent — ideal for simulation / replay
    and for software that virtualises input (e.g. window managers, VMs).
"""
import sys, json, time, argparse

# ---------------------------------------------------------------------------
# Multi-cursor state registry
# ---------------------------------------------------------------------------

_CURSOR_STATE: dict = {}   # cursor_id -> {"x": int, "y": int}

def _cursor_pos(cursor_id: str = "default") -> tuple:
    """Return the registered (x, y) for cursor_id, defaulting to (0, 0)."""
    state = _CURSOR_STATE.get(cursor_id, {})
    return state.get("x", 0), state.get("y", 0)

def _cursor_move(cursor_id: str = "default", x: int = 0, y: int = 0) -> None:
    """Update the logical position of cursor_id."""
    _CURSOR_STATE.setdefault(cursor_id, {})
    _CURSOR_STATE[cursor_id]["x"] = x
    _CURSOR_STATE[cursor_id]["y"] = y

def register_cursor(cursor_id: str, x: int = 0, y: int = 0) -> None:
    """Pre-register a cursor with an initial position."""
    _cursor_move(cursor_id, x, y)

def list_cursors() -> list:
    """Return all registered cursor_ids and their positions."""
    return [{"cursor_id": k, "x": v.get("x", 0), "y": v.get("y", 0)}
            for k, v in _CURSOR_STATE.items()]

# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------

def have(name):
    try: __import__(name); return True
    except Exception: return False

def focus_app(app, cursor_id: str = "default"):
    print(f'[focus_app cursor={cursor_id}] -> {app}')

def type_text(txt, cursor_id: str = "default"):
    if have('pyautogui'):
        import pyautogui
        pyautogui.typewrite(txt, interval=0.02)
    else:
        print(f'[type cursor={cursor_id}] {txt[:60]}...')

def click(x=None, y=None, image=None, confidence=0.8, cursor_id: str = "default"):
    """Click at (x, y).

    If x/y are None the last registered position for cursor_id is used,
    enabling independent pointer streams per virtual cursor.
    """
    cx, cy = _cursor_pos(cursor_id)
    px = x if x is not None else cx
    py = y if y is not None else cy
    _cursor_move(cursor_id, px, py)   # update tracked position on click

    if have('pyautogui'):
        import pyautogui
        if image:
            try:
                p = pyautogui.locateCenterOnScreen(image, confidence=confidence)
                if p:
                    pyautogui.click(p)
                    _cursor_move(cursor_id, int(p.x), int(p.y))
                    return True
                print('[click-image] not found', image); return False
            except Exception as e:
                print('[click-image] error', e); return False
        else:
            pyautogui.click(x=px, y=py); return True
    else:
        print(f'[click cursor={cursor_id}] ({px},{py}) image={image} (pyautogui missing)')
        return False

def move_cursor(x: int, y: int, cursor_id: str = "default"):
    """Move the cursor to (x, y) without clicking."""
    _cursor_move(cursor_id, x, y)
    if have('pyautogui'):
        import pyautogui
        pyautogui.moveTo(x, y)
    else:
        print(f'[move cursor={cursor_id}] -> ({x},{y})')

def double_click(x=None, y=None, cursor_id: str = "default"):
    """Double-click at (x, y) or at the cursor's current position."""
    cx, cy = _cursor_pos(cursor_id)
    px = x if x is not None else cx
    py = y if y is not None else cy
    _cursor_move(cursor_id, px, py)
    if have('pyautogui'):
        import pyautogui
        pyautogui.doubleClick(x=px, y=py)
        return True
    else:
        print(f'[double_click cursor={cursor_id}] ({px},{py}) (pyautogui missing)')
        return False

def drag_to(from_x: int, from_y: int, to_x: int, to_y: int,
            cursor_id: str = "default", duration: float = 0.3):
    """Drag from (from_x, from_y) to (to_x, to_y)."""
    _cursor_move(cursor_id, to_x, to_y)
    if have('pyautogui'):
        import pyautogui
        pyautogui.moveTo(from_x, from_y)
        pyautogui.dragTo(to_x, to_y, duration=duration)
        return True
    else:
        print(f'[drag cursor={cursor_id}] ({from_x},{from_y})->({to_x},{to_y}) (pyautogui missing)')
        return False

def scroll(clicks: int = 3, x=None, y=None, cursor_id: str = "default"):
    """Scroll the wheel at the cursor's position."""
    cx, cy = _cursor_pos(cursor_id)
    px = x if x is not None else cx
    py = y if y is not None else cy
    if have('pyautogui'):
        import pyautogui
        pyautogui.scroll(clicks, x=px, y=py)
    else:
        print(f'[scroll cursor={cursor_id}] clicks={clicks} at ({px},{py})')

def wait(s=0.5):
    time.sleep(s)

def assert_window_title(substr, cursor_id: str = "default"):
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        title = w.title if w else ''
        ok = (substr or '').lower() in (title or '').lower()
        print(f'[assert_window cursor={cursor_id}] want~="{substr}" got="{title}" -> {"PASS" if ok else "FAIL"}')
        return ok
    except Exception as e:
        print('[assert_window] unavailable', e); return False

def assert_ocr_contains(substr, region=None, cursor_id: str = "default"):
    try:
        import pytesseract, PIL.ImageGrab as IG
        box = tuple(region) if region and len(region) == 4 else None
        img = IG.grab(bbox=box) if box else IG.grab()
        txt = pytesseract.image_to_string(img) or ''
        ok = (substr or '').lower() in txt.lower()
        print(f'[assert_ocr cursor={cursor_id}] want~="{substr}" -> {"PASS" if ok else "FAIL"}')
        return ok
    except Exception as e:
        print('[assert_ocr] unavailable', e); return False

def post_validation(url, payload):
    try:
        import requests; requests.post(url, json=payload, timeout=2)
    except Exception as e:
        print('[validate post] error', e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec', nargs='?')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--validate-url', default='http://127.0.0.1:8775/validate')
    a = ap.parse_args()
    obj = json.load(open(a.spec, 'r', encoding='utf-8')) if a.spec else json.load(sys.stdin)
    steps = obj.get('steps', [])
    if not a.force:
        print('[info] Dry-run default. Use --force to click/type.')
    for s in steps:
        act = s.get('action')
        args = s.get('args', {})
        cid = args.get('cursor_id', 'default')
        ok = True
        if act == 'focus_app':
            focus_app(args.get('app', ''), cursor_id=cid)
        elif act == 'type' and not a.dry_run and a.force:
            type_text(args.get('text', ''), cursor_id=cid)
        elif act == 'click' and not a.dry_run and a.force:
            ok = click(args.get('x'), args.get('y'), args.get('image'),
                       args.get('confidence', 0.8), cursor_id=cid)
        elif act == 'double_click' and not a.dry_run and a.force:
            ok = double_click(args.get('x'), args.get('y'), cursor_id=cid)
        elif act == 'drag' and not a.dry_run and a.force:
            ok = drag_to(args.get('from_x', 0), args.get('from_y', 0),
                         args.get('to_x', 0), args.get('to_y', 0), cursor_id=cid)
        elif act == 'scroll':
            scroll(args.get('clicks', 3), args.get('x'), args.get('y'), cursor_id=cid)
        elif act == 'move_cursor':
            move_cursor(args.get('x', 0), args.get('y', 0), cursor_id=cid)
        elif act == 'wait':
            wait(args.get('seconds', 0.5))
        elif act == 'assert_window':
            ok = assert_window_title(args.get('contains', ''), cursor_id=cid)
        elif act == 'assert_ocr':
            ok = assert_ocr_contains(args.get('contains', ''), args.get('region'), cursor_id=cid)
        else:
            print(f'[skip] {act}')
        post_validation(a.validate_url, {
            'microtask_id': s.get('id', 'step'),
            'passed': bool(ok),
            'details': act,
            'cursor_id': cid,
        })
    print('[done]')

if __name__ == '__main__':
    main()

