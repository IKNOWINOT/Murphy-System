"""GhostControllerBot - Tracks OS attention, keystrokes, and application state to learn and automate tasks with ADHD-awareness, scalable agent mode, and optional Google Docs logging."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict
from threading import Thread
from pynput import keyboard, mouse
import pygetwindow as gw
from .gpt_oss_runner import GPTOSSRunner

# Optional Google Docs API dependency
try:
    from googleapiclient.discovery import build as _build_google_service
    from google.oauth2.credentials import Credentials as _GoogleCredentials
    _HAS_GOOGLE_API = True
except ImportError:
    _HAS_GOOGLE_API = False


class GhostControllerBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b"):
        self.runner = GPTOSSRunner(model_path=model_path)
        self.current_task_profile: Dict[str, Any] = {}
        self.keystrokes = []
        self.mouse_log = []
        self.active_window = None
        self.tracking = False
        self.last_activity_time = time.time()
        self.chain_log: list[dict] = []
        self.google_logging_enabled = False  # Optional Google Docs integration
        self.google_doc_id = None  # ID reference if enabled

    def get_active_window(self) -> str:
        try:
            win = gw.getActiveWindow()
            return win.title if win else "Unknown"
        except Exception:
            return "Unknown"

    def log_keystroke(self, key):
        self.last_activity_time = time.time()
        try:
            key_val = key.char if hasattr(key, 'char') else str(key)
            self.keystrokes.append((datetime.now(timezone.utc).isoformat(), key_val))
        except Exception:
            pass

    def log_mouse(self, x, y):
        self.last_activity_time = time.time()
        self.mouse_log.append((datetime.now(timezone.utc).isoformat(), x, y))

    def start_learning_task(self):
        self.tracking = True
        self.keystrokes.clear()
        self.mouse_log.clear()
        self.active_window = self.get_active_window()
        self.last_activity_time = time.time()

        def watch_keys():
            with keyboard.Listener(on_press=self.log_keystroke) as listener:
                listener.join()

        def watch_mouse():
            with mouse.Listener(on_move=self.log_mouse) as listener:
                listener.join()

        self.keyboard_thread = Thread(target=watch_keys, daemon=True)
        self.mouse_thread = Thread(target=watch_mouse, daemon=True)
        self.keyboard_thread.start()
        self.mouse_thread.start()

    def stop_learning_task(self, task_description: str) -> Dict[str, Any]:
        self.tracking = False

        profile = {
            "task_description": task_description,
            "keystrokes": self.keystrokes,
            "mouse_path": self.mouse_log,
            "active_window": self.active_window,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.current_task_profile = profile
        self.chain_log.append(profile)

        if self.google_logging_enabled and self.google_doc_id:
            self.push_to_google_doc(profile)

        return profile

    def push_to_google_doc(self, task_profile: dict) -> None:
        """Push a task profile to the connected Google Doc.

        Uses the Google Docs API via *google-api-python-client*.  If the
        library is unavailable or credentials are missing the method
        falls back to a structured local log so no data is silently lost.

        Requires:
            - ``google-api-python-client``, ``google-auth-oauthlib``
            - OAuth2 credentials stored at ``~/.murphy/google_credentials.json``
        """
        if not _HAS_GOOGLE_API:
            self._fallback_log(task_profile,
                               reason="google-api-python-client not installed")
            return

        try:
            creds_path = os.path.expanduser("~/.murphy/google_credentials.json")
            if not os.path.exists(creds_path):
                self._fallback_log(task_profile,
                                   reason="Credentials file not found at " + creds_path)
                return

            creds = _GoogleCredentials.from_authorized_user_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/documents"],
            )
            service = _build_google_service("docs", "v1", credentials=creds)

            body_text = json.dumps(task_profile, indent=2)
            requests = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": f"\n--- Murphy Task Log ---\n{body_text}\n",
                    }
                }
            ]
            service.documents().batchUpdate(
                documentId=self.google_doc_id, body={"requests": requests}
            ).execute()
            print("[Google Logging] Task logged to Google Doc ID:", self.google_doc_id)

        except Exception as exc:
            self._fallback_log(task_profile, reason=str(exc))

    # ------------------------------------------------------------------

    def _fallback_log(self, task_profile: dict, *, reason: str) -> None:
        """Write the task profile to a local JSON file when Google Docs
        integration is unavailable."""
        fallback_dir = os.path.expanduser("~/.murphy/logs")
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, "google_doc_fallback.jsonl")
        entry = {"reason": reason, "profile": task_profile,
                 "timestamp": datetime.utcnow().isoformat()}
        with open(fallback_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"[Google Logging] Fallback: logged locally ({reason})")

    def interpret_task_flow(self) -> Dict[str, Any]:
        prompt = f"""
You are GhostControllerBot.
Based on the keystrokes, mouse paths, and application focus, summarize the user's task.
Also suggest a script that could replicate the task in the future.

Task Profile:
{json.dumps(self.current_task_profile, indent=2)}

Return a JSON object with: task_summary, automation_script (pseudo-steps), and confidence.
"""
        try:
            output = self.runner.chat(prompt)
            return json.loads(output)
        except Exception as e:
            return {"error": str(e)}

    def detect_adhd_deviation(self, threshold_seconds: int = 30) -> bool:
        return (time.time() - self.last_activity_time > threshold_seconds)

    def notify_user_if_idle_or_mistake(self):
        if self.detect_adhd_deviation():
            print("⚠️ Attention Warning: You've been idle. Do you want to resume or save current progress?")
        if self.current_task_profile.get("task_description") == "":
            print("❌ Error: No task description set. Unable to process task automation.")

    def save_chain_log_to_json(self, file_path: str = "task_chains.json") -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.chain_log, f, indent=2)

    def respond_to_roll_call(self, task_description: str) -> dict:
        prompt = f"""
You are GhostControllerBot.
Task: {task_description}
Can you assist by observing, recording, or automating this task based on user attention and input patterns?
Return: {{"can_help": true, "confidence": float, "suggested_subtask": str}}
"""
        try:
            raw = self.runner.chat(prompt, stop_token="}")
            return json.loads(raw + "}")
        except Exception as e:
            return {"can_help": False, "error": str(e)}
