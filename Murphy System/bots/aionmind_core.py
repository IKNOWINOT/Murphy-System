"""AionMind Core orchestrates user queries across bots."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .input_parser import parse_user_input
from .jsonbot_schema import validate_json
from .tool_dispatcher import dispatch
from .memory_manager_bot import store_stm
from .cache_manager import get_cache, set_cache
from .gpt_oss_runner import GPTOSSRunner

import hashlib

SESSION_FILE = Path('session_store.json')


def load_session(user_id: str) -> Dict[str, Any]:
    try:
        data = json.loads(SESSION_FILE.read_text())
        return data.get(user_id, {})
    except Exception:
        return {}


def save_session(user_id: str, session: Dict[str, Any]) -> None:
    try:
        data = json.loads(SESSION_FILE.read_text())
    except Exception:
        data = {}
    data[user_id] = session
    SESSION_FILE.write_text(json.dumps(data, indent=2))


def format_output(task: Dict[str, Any], result: Dict[str, Any], tone: str = 'direct') -> str:
    if result.get('status') == 'success':
        res = result['result']
        if tone == 'casual':
            return f"Done! Here's what I found:\n{res}"
        if tone == 'verbose':
            return f"Task `{task['task_type']}` assigned to `{task['assigned_to']}` has been successfully completed. Output:\n{res}"
        return f"✅ Task `{task['task_type']}` complete: {res}"
    return f"⚠️ {result.get('reason')}"


def synthesize_outputs(results: List[Dict[str, Any]]) -> str:
    summary = [f"- {r['result']}" for r in results if r.get('status') == 'success']
    if summary:
        joined = '\n'.join(summary)
        runner = GPTOSSRunner(model_path="./models/gpt-oss-20b")
        prompt = f"Summarize the following outputs for user understanding:\n{joined}"
        return runner.chat(prompt)
    return 'No successful results.'


def route_with_cache(task: Dict[str, Any]) -> Dict[str, Any]:
    key_src = json.dumps(task, sort_keys=True).encode()
    key = 'task_' + hashlib.sha1(key_src).hexdigest()
    cached = get_cache(key)
    if cached is not None:
        return {"status": "success", "result": cached}
    result = route_with_cache(task)
    if result.get("status") == "success":
        set_cache(key, result["result"])  # default TTL
    return result


def handle_user_query(user_id: str, query: str) -> str:
    session = load_session(user_id)
    tone = session.get('tone', 'direct')
    task = parse_user_input(query)
    if not task:
        runner = GPTOSSRunner(model_path="./models/gpt-oss-20b")
        fallback = runner.chat(
            f"User query: {query}\nPlease generate a polite response indicating we couldn't process this."
        )
        return f"❌ {fallback}"
    valid, error = validate_json(task)
    if not valid:
        return f"❌ Invalid task: {error}"
    result = dispatch(task)
    response = format_output(task, result, tone=tone)
    store_stm(task['task_type'], response, {'bot': task['assigned_to'], 'tags': [task['task_type']]})
    session['current_task'] = task['task_type']
    session['last_bot'] = task['assigned_to']
    save_session(user_id, session)
    return response