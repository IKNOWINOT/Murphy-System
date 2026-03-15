
"""GhostController desktop bridge (stub)
Captures keyboard/mouse/focus events and posts them to a local endpoint.
Requires: pynput, pygetwindow, requests
"""
import time, json, threading, requests
from datetime import datetime, timezone
from pynput import keyboard, mouse
import pygetwindow as gw

ENDPOINT = 'http://127.0.0.1:8765/events'  # your local relay

events = []

def now(): return datetime.now(timezone.utc).isoformat()

def focus_title():
    try:
        win = gw.getActiveWindow()
        return win.title if win else 'Unknown'
    except Exception:
        return 'Unknown'

def on_key(key):
    try:
        k = key.char if hasattr(key,'char') else str(key)
    except Exception:
        k = '?'
    events.append({'ts': now(), 'kind':'key', 'data': {'key':k}})

def on_move(x, y):
    events.append({'ts': now(), 'kind':'mouse', 'data': {'x':x,'y':y}})

def focus_watcher():
    last = None
    while True:
        ti = focus_title()
        if ti != last:
            events.append({'ts': now(), 'kind':'focus', 'data': {'title':ti}})
            last = ti
        time.sleep(0.5)

def flusher():
    while True:
        if events:
            chunk = events[:]
            del events[:]
            try:
                requests.post(ENDPOINT, json={'events':chunk}, timeout=2)
            except Exception:
                pass
        time.sleep(1.0)

def main():
    threading.Thread(target=focus_watcher, daemon=True).start()
    threading.Thread(target=flusher, daemon=True).start()
    with keyboard.Listener(on_press=on_key) as kl, mouse.Listener(on_move=on_move) as ml:
        kl.join(); ml.join()

if __name__ == '__main__':
    main()
