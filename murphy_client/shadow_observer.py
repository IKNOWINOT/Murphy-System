"""
PATCH-329 — Murphy Client: Shadow Observer Engine
File: /opt/Murphy-System/murphy_client/shadow_observer.py

This is the CLIENT-SIDE component. It runs on the user's machine,
watches what they do, and phones home to /api/oo/observe.

Installed as a background service via:
  murphy_client.py --install
  (sets up OS-level service that starts on login)

It watches:
  - Files created/modified in designated work folders
  - Clipboard events (with opt-in)
  - Application focus (which app they're using)
  - HTTP calls via system proxy (opt-in)
  - Manual logs (user can call murphy.log("did X"))
"""

import os
import sys
import time
import json
import threading
import sqlite3
import hashlib
import requests
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

CLIENT_DB = os.path.expanduser("~/.murphy/local_observations.db")
CONFIG_FILE = os.path.expanduser("~/.murphy/config.json")
MURPHY_CLOUD = "https://murphy.systems"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "account_id": None,
    "api_key": None,
    "automation_hours_start": "23:00",
    "automation_hours_end": "06:00",
    "watch_folders": [],
    "observe_clipboard": False,
    "observe_app_focus": True,
    "sync_interval_seconds": 300,   # 5 min batch upload
    "version": "1.0.0"
}


def load_config() -> dict:
    Path(os.path.expanduser("~/.murphy")).mkdir(exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    Path(os.path.expanduser("~/.murphy")).mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DB
# ─────────────────────────────────────────────────────────────────────────────

def init_local_db():
    Path(os.path.expanduser("~/.murphy")).mkdir(exist_ok=True)
    conn = sqlite3.connect(CLIENT_DB)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS local_observations (
            id TEXT PRIMARY KEY,
            action_type TEXT,
            action_data TEXT,
            observed_at TEXT,
            synced INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS work_queue (
            id TEXT PRIMARY KEY,
            task_type TEXT,
            task_data TEXT,
            scheduled_for TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def log_observation(action_type: str, action_data: dict):
    """Log an observation to local DB for batch sync."""
    import uuid as _uuid
    conn = sqlite3.connect(CLIENT_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO local_observations (id, action_type, action_data, observed_at)
        VALUES (?, ?, ?, ?)
    """, (str(_uuid.uuid4()), action_type, json.dumps(action_data),
          datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SYNC ENGINE — uploads batched observations to murphy.systems
# ─────────────────────────────────────────────────────────────────────────────

def sync_to_cloud(config: dict):
    """
    Upload unsynced observations to murphy.systems/api/oo/observe.
    Runs every sync_interval_seconds.
    """
    if not config.get('account_id') or not config.get('api_key'):
        return

    conn = sqlite3.connect(CLIENT_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, action_type, action_data FROM local_observations WHERE synced=0 LIMIT 50")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return

    synced_ids = []
    for obs_id, action_type, action_data_str in rows:
        try:
            action_data = json.loads(action_data_str)
            resp = requests.post(
                f"{MURPHY_CLOUD}/api/oo/observe",
                json={
                    "account_id": config['account_id'],
                    "action_type": action_type,
                    "action_data": action_data
                },
                headers={"X-API-Key": config['api_key']},
                timeout=10
            )
            if resp.status_code in (200, 201):
                synced_ids.append(obs_id)
        except Exception:
            pass  # Offline? Queue will persist.

    if synced_ids:
        conn = sqlite3.connect(CLIENT_DB)
        cur = conn.cursor()
        placeholders = ','.join(['?'] * len(synced_ids))
        cur.execute(f"UPDATE local_observations SET synced=1 WHERE id IN ({placeholders})",
                    synced_ids)
        conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# FILE WATCHER — watches designated folders for activity
# ─────────────────────────────────────────────────────────────────────────────

class FileWatcher(threading.Thread):
    """Watches folders for file create/modify events."""

    def __init__(self, folders: list, callback):
        super().__init__(daemon=True)
        self.folders = folders
        self.callback = callback
        self._seen = {}

    def run(self):
        while True:
            for folder in self.folders:
                if not os.path.exists(folder):
                    continue
                try:
                    for fname in os.listdir(folder):
                        fpath = os.path.join(folder, fname)
                        if not os.path.isfile(fpath):
                            continue
                        mtime = os.path.getmtime(fpath)
                        if fpath not in self._seen or self._seen[fpath] != mtime:
                            self._seen[fpath] = mtime
                            action = "file_created" if fpath not in self._seen else "file_modified"
                            self.callback(action, {
                                "filename": fname,
                                "folder": folder,
                                "extension": os.path.splitext(fname)[1],
                                "size_bytes": os.path.getsize(fpath)
                            })
                except Exception:
                    pass
            time.sleep(30)


# ─────────────────────────────────────────────────────────────────────────────
# APP FOCUS WATCHER (macOS + Windows)
# ─────────────────────────────────────────────────────────────────────────────

class AppFocusWatcher(threading.Thread):
    """Watches which application the user is using."""

    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self._last_app = None

    def _get_active_app(self) -> Optional[str]:
        try:
            if platform.system() == 'Darwin':
                import subprocess
                result = subprocess.run(
                    ['osascript', '-e',
                     'tell application "System Events" to get name of first application process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
            elif platform.system() == 'Windows':
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
        except Exception:
            return None
        return None

    def run(self):
        # Map of app → work category
        APP_CATEGORIES = {
            'mail': 'email', 'outlook': 'email', 'gmail': 'email',
            'calendar': 'scheduling', 'google calendar': 'scheduling',
            'excel': 'spreadsheet', 'sheets': 'spreadsheet', 'numbers': 'spreadsheet',
            'word': 'document', 'docs': 'document', 'pages': 'document',
            'quickbooks': 'invoicing', 'xero': 'invoicing', 'freshbooks': 'invoicing',
            'chrome': 'browsing', 'safari': 'browsing', 'firefox': 'browsing',
            'slack': 'communication', 'teams': 'communication', 'zoom': 'meeting',
        }

        app_start_time = None

        while True:
            current_app = self._get_active_app()
            if current_app and current_app != self._last_app:
                # Log time spent in previous app
                if self._last_app and app_start_time:
                    duration_s = (datetime.utcnow() -
                                  datetime.fromisoformat(app_start_time)).total_seconds()
                    if duration_s > 30:  # Ignore < 30s focus
                        category = next(
                            (v for k, v in APP_CATEGORIES.items()
                             if k in self._last_app.lower()), 'other'
                        )
                        self.callback("app_used", {
                            "app": self._last_app,
                            "category": category,
                            "duration_seconds": int(duration_s)
                        })

                self._last_app = current_app
                app_start_time = datetime.utcnow().isoformat()

            time.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATION HOURS CHECK
# ─────────────────────────────────────────────────────────────────────────────

def is_automation_window(config: dict) -> bool:
    """Check if current time is within the user's automation window."""
    now = datetime.now()
    current_time = now.hour * 60 + now.minute

    start_str = config.get('automation_hours_start', '23:00')
    end_str = config.get('automation_hours_end', '06:00')

    try:
        sh, sm = map(int, start_str.split(':'))
        eh, em = map(int, end_str.split(':'))
        start_m = sh * 60 + sm
        end_m = eh * 60 + em

        if start_m > end_m:  # Overnight window (e.g. 23:00 - 06:00)
            return current_time >= start_m or current_time <= end_m
        else:  # Same-day window
            return start_m <= current_time <= end_m
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────────────────────────────────────────

class MurphyClient:
    def __init__(self):
        self.config = load_config()
        init_local_db()

    def setup(self):
        """Interactive first-run setup."""
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  Murphy Client — First Time Setup")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        print("Complete your onboarding at murphy.systems/start")
        print("Then come back and enter your credentials below.\n")

        account_id = input("Account ID (from your Murphy dashboard): ").strip()
        api_key = input("API Key (from murphy.systems/settings): ").strip()
        auto_start = input("Automation hours start (default 23:00): ").strip() or "23:00"
        auto_end = input("Automation hours end (default 06:00): ").strip() or "06:00"

        self.config['account_id'] = account_id
        self.config['api_key'] = api_key
        self.config['automation_hours_start'] = auto_start
        self.config['automation_hours_end'] = auto_end
        save_config(self.config)
        print("\n✓ Murphy Client configured. Run 'murphy_client.py --start' to begin.\n")

    def start(self):
        """Start all observer threads and sync loop."""
        if not self.config.get('account_id'):
            print("Not configured. Run: murphy_client.py --setup")
            sys.exit(1)

        print(f"[Murphy] Starting shadow observer for account {self.config['account_id'][:8]}...")
        print(f"[Murphy] Automation hours: {self.config['automation_hours_start']} – {self.config['automation_hours_end']}")

        # Start file watcher if folders configured
        if self.config.get('watch_folders'):
            fw = FileWatcher(self.config['watch_folders'], log_observation)
            fw.start()
            print(f"[Murphy] Watching {len(self.config['watch_folders'])} folder(s)")

        # Start app focus watcher
        if self.config.get('observe_app_focus'):
            af = AppFocusWatcher(log_observation)
            af.start()
            print("[Murphy] App focus observer active")

        # Main sync loop
        print("[Murphy] Sync loop started. Running silently in background.")
        while True:
            try:
                # Sync observations to cloud
                sync_to_cloud(self.config)

                # Log heartbeat during automation window
                if is_automation_window(self.config):
                    log_observation("automation_window_active", {
                        "window": f"{self.config['automation_hours_start']} – {self.config['automation_hours_end']}",
                        "timestamp": datetime.utcnow().isoformat()
                    })

            except Exception as e:
                pass  # Never crash the background agent

            time.sleep(self.config.get('sync_interval_seconds', 300))

    def log(self, message: str, category: str = "manual"):
        """Manual observation log. Users can call this from scripts."""
        log_observation("manual_log", {
            "message": message,
            "category": category,
            "timestamp": datetime.utcnow().isoformat()
        })
        print(f"[Murphy] Logged: {message}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    client = MurphyClient()

    if '--setup' in sys.argv:
        client.setup()
    elif '--log' in sys.argv:
        idx = sys.argv.index('--log')
        msg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'activity'
        client.log(msg)
    else:
        client.start()
